"""Controlled generation, QA, retry, persistence, and delivery orchestration."""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any


ADVANCED_IMAGE_GENERATE_SCHEMA = {
    "name": "advanced_image_generate",
    "description": (
        "Execute an already-confirmed image request against a selected supplier/model, then run "
        "file checks, visual QA, targeted retries, safe persistence, and delivery controls. "
        "For interactive user requests, start advanced_image_wizard first."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "Complete generation/edit prompt."},
            "provider": {
                "type": "string",
                "description": "Supplier id from advanced_image_catalog; defaults to hermes-native.",
            },
            "model": {
                "type": "string",
                "description": "Model id under the selected supplier; defaults to that supplier's configured model.",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["landscape", "portrait", "square"],
                "default": "square",
            },
            "image_url": {"type": "string", "description": "Optional primary edit target."},
            "reference_image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional supporting reference images.",
            },
            "destination": {
                "type": "string",
                "description": (
                    "Optional final file (one variant) or directory. Defaults to the active "
                    "profile's output/advanced-imagegen directory."
                ),
            },
            "filename_prefix": {"type": "string", "default": "image"},
            "variants": {"type": "integer", "minimum": 1, "maximum": 4, "default": 1},
            "variant_instructions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "One deliberate design-axis instruction per variant.",
            },
            "qa_profile": {
                "type": "string",
                "enum": ["standard", "strict", "transparent", "exact-text"],
                "default": "standard",
                "description": "Acceptance policy; semantic visual QA is mandatory.",
            },
            "acceptance_criteria": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Concrete conditions that every delivered image must satisfy.",
            },
            "required_text": {
                "type": "string",
                "description": "Exact text that must appear, including punctuation and case.",
            },
            "max_iterations": {
                "type": "integer",
                "minimum": 0,
                "maximum": 2,
                "default": 1,
                "description": "Maximum targeted retries after the initial generation.",
            },
            "require_human_approval": {
                "type": "boolean",
                "default": False,
                "description": "Return needs_review instead of machine-accepted delivery.",
            },
            "overwrite": {"type": "boolean", "default": False},
            "chroma_key": {
                "type": "string",
                "pattern": "^#[0-9a-fA-F]{6}$",
                "default": "#00ff00",
                "description": "Flat key color used by transparent QA/profile post-processing.",
            },
            "wizard_id": {"type": "string", "description": "Wizard audit id when invoked after confirmation."},
        },
        "required": ["prompt"],
    },
}


_QA_SCHEMA = {
    "type": "object",
    "properties": {
        "passed": {"type": "boolean"},
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "summary": {"type": "string"},
        "failures": {"type": "array", "items": {"type": "string"}},
        "correction_prompt": {"type": "string"},
    },
    "required": ["passed", "score", "summary", "failures", "correction_prompt"],
    "additionalProperties": False,
}

_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def block_raw_image_generate(tool_name: str = "", **_: Any) -> dict[str, str] | None:
    """Prevent model-facing calls from bypassing the controlled workflow."""
    if tool_name != "image_generate":
        return None
    return {
        "action": "block",
        "message": (
            "Direct image_generate calls are disabled by advanced-imagegen. "
            "Start advanced_image_wizard for provider/model selection, model-specific prompt "
            "guidance, user confirmation, generation, QA, and delivery controls. Use "
            "advanced_image_generate only for an already-confirmed execution request."
        ),
    }


def build_handler(ctx, provider_manager=None):
    async def _handler(args: dict, **kwargs: Any) -> str:
        return await orchestrate(
            ctx,
            args,
            task_id=str(kwargs.get("task_id") or ""),
            provider_manager=provider_manager,
        )

    return _handler


def _clamp(value: Any, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _clean_prefix(value: Any) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "image")).strip("-.")
    return clean[:64] or "image"


def _parse_result(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {"success": False, "error": f"Unexpected image_generate result: {type(raw).__name__}"}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"success": False, "error": raw}
    except json.JSONDecodeError:
        return {"success": False, "error": raw}


async def _resolve_image(source: str, task_id: str) -> tuple[bytes, str]:
    from tools.image_source import ResolveContext, resolve_image_source

    resolved = await resolve_image_source(source, ResolveContext(task_id=task_id or None))
    return resolved.data, resolved.mime


def _inspect_image(data: bytes, qa_profile: str) -> dict[str, Any]:
    from PIL import Image

    failures: list[str] = []
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            width, height = image.size
            mode = image.mode
            fmt = image.format or ""
            has_alpha = "A" in mode or "transparency" in image.info
            report: dict[str, Any] = {
                "passed": True,
                "width": width,
                "height": height,
                "mode": mode,
                "format": fmt,
                "has_alpha": has_alpha,
                "failures": failures,
            }
            if width < 64 or height < 64:
                failures.append(f"Image is unexpectedly small ({width}x{height}).")
            if qa_profile == "transparent":
                rgba = image.convert("RGBA")
                alpha = rgba.getchannel("A")
                values = list(
                    alpha.get_flattened_data()
                    if hasattr(alpha, "get_flattened_data")
                    else alpha.getdata()
                )
                transparent_fraction = sum(a < 16 for a in values) / max(1, len(values))
                corners = [
                    rgba.getpixel((0, 0))[3],
                    rgba.getpixel((width - 1, 0))[3],
                    rgba.getpixel((0, height - 1))[3],
                    rgba.getpixel((width - 1, height - 1))[3],
                ]
                report.update(
                    transparent_fraction=round(transparent_fraction, 4),
                    corner_alpha=corners,
                )
                if not has_alpha:
                    failures.append("Transparent delivery has no alpha channel.")
                if any(a > 16 for a in corners):
                    failures.append("Transparent delivery has opaque corner pixels.")
                if not 0.01 <= transparent_fraction <= 0.98:
                    failures.append("Transparent coverage is implausible.")
            report["passed"] = not failures
            return report
    except Exception as exc:  # noqa: BLE001 - converted into a controlled QA failure
        return {"passed": False, "failures": [f"Image file could not be decoded: {exc}"]}


def _parse_hex_color(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _make_transparent(data: bytes, chroma_key: str) -> bytes:
    import importlib.util
    import sys

    from PIL import Image

    try:
        from .scripts.remove_chroma_key import remove_key
    except ImportError:
        module_name = "advanced_imagegen_remove_chroma_key"
        module = sys.modules.get(module_name)
        if module is None:
            path = Path(__file__).resolve().parent / "scripts" / "remove_chroma_key.py"
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load chroma-key helper from {path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        remove_key = module.remove_key

    with Image.open(io.BytesIO(data)) as image:
        result = remove_key(
            image.convert("RGB"),
            _parse_hex_color(chroma_key),
            12,
            220,
            True,
            True,
            0,
        )
        output = io.BytesIO()
        result.save(output, format="PNG")
        return output.getvalue()


def _qa_instructions(
    prompt: str,
    criteria: list[str],
    required_text: str,
    qa_profile: str,
    file_report: dict[str, Any],
) -> str:
    threshold = 85 if qa_profile in {"strict", "transparent", "exact-text"} else 75
    criteria_text = "\n".join(f"- {item}" for item in criteria) or "- Faithfully satisfy the prompt."
    exact_text = required_text or "(none)"
    return f"""You are the acceptance gate for a production image workflow.
Inspect the attached candidate against the request. Be strict, visual, and evidence-based.
Reject visible defects, constraint drift, unintended text/logos/watermarks, broken anatomy,
bad object geometry, or failed edit invariants. For exact text, compare every character.

Original request:
{prompt}

Acceptance criteria:
{criteria_text}

Required text verbatim: {exact_text}
QA profile: {qa_profile}
Machine file report: {json.dumps(file_report, ensure_ascii=False)}
Passing threshold: {threshold}/100.

Set passed=true only when all hard requirements pass and score reaches the threshold.
correction_prompt must be a concise, targeted instruction that fixes only observed failures
while preserving every other original constraint. Return JSON only."""


async def _visual_qa(
    ctx,
    data: bytes,
    mime: str,
    prompt: str,
    criteria: list[str],
    required_text: str,
    qa_profile: str,
    file_report: dict[str, Any],
) -> dict[str, Any]:
    from agent.plugin_llm import PluginLlmImageInput, PluginLlmTextInput

    result = await ctx.llm.acomplete_structured(
        instructions=_qa_instructions(prompt, criteria, required_text, qa_profile, file_report),
        input=[
            PluginLlmTextInput(text="Evaluate this candidate image for final delivery."),
            PluginLlmImageInput(data=data, mime_type=mime or "image/png", file_name="candidate"),
        ],
        json_schema=_QA_SCHEMA,
        json_mode=True,
        schema_name="advanced_imagegen_acceptance",
        temperature=0.0,
        max_tokens=900,
        timeout=120,
        purpose="advanced-imagegen visual acceptance QA",
    )
    parsed = result.parsed
    if not isinstance(parsed, dict):
        raise ValueError("Visual QA returned no structured result")
    failures = parsed.get("failures")
    parsed["failures"] = [str(item) for item in failures] if isinstance(failures, list) else []
    parsed["score"] = _clamp(parsed.get("score"), 0, 100, 0)
    threshold = 85 if qa_profile in {"strict", "transparent", "exact-text"} else 75
    parsed["passed"] = bool(parsed.get("passed")) and parsed["score"] >= threshold
    if parsed.get("passed") is False and parsed["score"] < threshold and not parsed["failures"]:
        parsed["failures"] = [f"Visual QA score {parsed['score']} is below the {threshold} threshold."]
    parsed["qa_provider"] = result.provider
    parsed["qa_model"] = result.model
    return parsed


def _generation_prompt(base: str, variant_instruction: str, qa_profile: str, chroma_key: str) -> str:
    parts = [base.strip()]
    if variant_instruction:
        parts.append(f"Variant direction (change only this design axis): {variant_instruction.strip()}")
    if qa_profile == "transparent":
        parts.append(
            f"Place the subject on a perfectly flat solid {chroma_key} chroma-key background. "
            "The background must be uniform with no shadow, gradient, texture, reflection, floor "
            f"plane, or lighting variation. Keep crisp separated edges and do not use {chroma_key} "
            "inside the subject. No watermark or extra text."
        )
    return "\n\n".join(parts)


def _retry_prompt(original: str, failures: list[str], correction: str) -> str:
    observed = "\n".join(f"- {item}" for item in failures) or "- Candidate failed acceptance QA."
    targeted = correction.strip() or "Correct the listed failures."
    return f"""{original}

TARGETED ACCEPTANCE RETRY:
Observed failures:
{observed}
Correction: {targeted}
Preserve every original requirement and every unmentioned visual property. Do not introduce
new subjects, text, logos, watermarks, layout changes, or style changes."""


def _candidate_path(
    destination: str,
    prefix: str,
    job_id: str,
    variant: int,
    variants: int,
    extension: str,
    rejected: bool,
    overwrite: bool,
) -> Path:
    from hermes_constants import get_hermes_home

    if destination:
        raw = Path(os.path.expanduser(destination)).resolve()
        exact_file = variants == 1 and bool(raw.suffix)
    else:
        raw = (get_hermes_home() / "output" / "advanced-imagegen").resolve()
        exact_file = False

    if exact_file:
        stem = raw.stem + ("-rejected" if rejected else "")
        candidate = raw.with_name(stem + extension)
    else:
        directory = raw
        variant_suffix = f"-v{variant}" if variants > 1 else ""
        rejected_suffix = "-rejected" if rejected else ""
        candidate = directory / f"{prefix}-{job_id}{variant_suffix}{rejected_suffix}{extension}"

    from agent.file_safety import is_write_denied

    if is_write_denied(str(candidate)):
        raise PermissionError(f"Destination is outside the configured safe write roots: {candidate}")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    if overwrite or not candidate.exists():
        return candidate
    for version in range(2, 10000):
        versioned = candidate.with_name(f"{candidate.stem}-v{version}{candidate.suffix}")
        if not versioned.exists():
            return versioned
    raise FileExistsError(f"Could not allocate a non-destructive destination for {candidate}")


def _persist(data: bytes, path: Path) -> None:
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


async def orchestrate(ctx, args: dict, task_id: str = "", provider_manager=None) -> str:
    """Run the bounded delivery state machine and return a compact manifest."""
    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        return json.dumps({"success": False, "status": "invalid_request", "error": "prompt is required"})

    job_id = uuid.uuid4().hex[:10]
    variants = _clamp(args.get("variants"), 1, 4, 1)
    max_iterations = _clamp(args.get("max_iterations"), 0, 2, 1)
    aspect_ratio = str(args.get("aspect_ratio") or "square")
    if aspect_ratio not in {"landscape", "portrait", "square"}:
        aspect_ratio = "square"
    qa_profile = str(args.get("qa_profile") or "standard")
    if qa_profile not in {"standard", "strict", "transparent", "exact-text"}:
        qa_profile = "standard"
    chroma_key = str(args.get("chroma_key") or "#00ff00")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", chroma_key):
        chroma_key = "#00ff00"
    criteria = [str(item).strip() for item in (args.get("acceptance_criteria") or []) if str(item).strip()]
    required_text = str(args.get("required_text") or "")
    if required_text and qa_profile == "standard":
        qa_profile = "exact-text"
    variant_directions = [str(item) for item in (args.get("variant_instructions") or [])]
    prefix = _clean_prefix(args.get("filename_prefix"))
    destination = str(args.get("destination") or "")
    overwrite = bool(args.get("overwrite", False))
    require_human = bool(args.get("require_human_approval", False))
    selected_provider = str(args.get("provider") or "hermes-native")
    selected_model = str(args.get("model") or ("active" if selected_provider == "hermes-native" else ""))
    items: list[dict[str, Any]] = []

    for variant in range(1, variants + 1):
        direction = variant_directions[variant - 1] if variant <= len(variant_directions) else ""
        original_prompt = _generation_prompt(prompt, direction, qa_profile, chroma_key)
        current_prompt = original_prompt
        last_data: bytes | None = None
        last_mime = "image/png"
        last_generation: dict[str, Any] = {}
        last_qa: dict[str, Any] = {}
        attempts: list[dict[str, Any]] = []
        item_status = "rejected"

        for attempt in range(1, max_iterations + 2):
            generation_args: dict[str, Any] = {"prompt": current_prompt, "aspect_ratio": aspect_ratio}
            if args.get("image_url"):
                generation_args["image_url"] = args["image_url"]
            if args.get("reference_image_urls"):
                generation_args["reference_image_urls"] = args["reference_image_urls"]
            try:
                generation_args["provider"] = selected_provider
                if selected_model:
                    generation_args["model"] = selected_model
                if args.get("wizard_id"):
                    generation_args["idempotency_key"] = f"{args['wizard_id']}-{variant}-{attempt}"
                if provider_manager is not None:
                    last_generation = await provider_manager.generate(generation_args, task_id=task_id)
                else:
                    raw = await asyncio.to_thread(
                        ctx.dispatch_tool,
                        "image_generate",
                        generation_args,
                        task_id=task_id,
                    )
                    last_generation = _parse_result(raw)
            except Exception as exc:  # noqa: BLE001 - report provider failures in manifest
                if hasattr(exc, "to_dict"):
                    last_generation = exc.to_dict()
                else:
                    last_generation = {"success": False, "error": str(exc)}

            source = last_generation.get("image") or last_generation.get("image_url") or last_generation.get("url")
            if not source or last_generation.get("success") is False:
                attempts.append({"attempt": attempt, "status": "generation_error", "error": last_generation.get("error", "No image returned")})
                item_status = "generation_error"
                break

            try:
                data, mime = await _resolve_image(str(source), task_id)
                if qa_profile == "transparent":
                    data = await asyncio.to_thread(_make_transparent, data, chroma_key)
                    mime = "image/png"
                last_data, last_mime = data, mime or "image/png"
            except Exception as exc:  # noqa: BLE001
                attempts.append({"attempt": attempt, "status": "materialization_error", "error": str(exc)})
                item_status = "materialization_error"
                break

            file_report = await asyncio.to_thread(_inspect_image, last_data, qa_profile)
            if not file_report.get("passed"):
                last_qa = {
                    "passed": False,
                    "score": 0,
                    "summary": "Machine file inspection failed.",
                    "failures": file_report.get("failures", []),
                    "correction_prompt": "Regenerate a valid, decodable image with the requested file properties.",
                    "file": file_report,
                }
            else:
                try:
                    last_qa = await _visual_qa(
                        ctx,
                        last_data,
                        last_mime,
                        original_prompt,
                        criteria,
                        required_text,
                        qa_profile,
                        file_report,
                    )
                    last_qa["file"] = file_report
                except Exception as exc:  # noqa: BLE001 - visual QA is fail-closed
                    last_qa = {
                        "passed": False,
                        "score": 0,
                        "summary": "Visual acceptance QA could not complete.",
                        "failures": [str(exc)],
                        "correction_prompt": "",
                        "file": file_report,
                        "qa_error": True,
                    }

            attempts.append(
                {
                    "attempt": attempt,
                    "status": "passed" if last_qa.get("passed") else "failed_qa",
                    "score": last_qa.get("score", 0),
                    "failures": last_qa.get("failures", []),
                }
            )
            if last_qa.get("passed"):
                item_status = "needs_review" if require_human else "accepted"
                break
            if last_qa.get("qa_error"):
                item_status = "qa_error"
                break
            if attempt <= max_iterations:
                current_prompt = _retry_prompt(
                    original_prompt,
                    [str(item) for item in last_qa.get("failures", [])],
                    str(last_qa.get("correction_prompt") or ""),
                )

        final_path = ""
        if last_data is not None:
            try:
                extension = ".png" if qa_profile == "transparent" else _EXTENSIONS.get(last_mime, ".png")
                path = _candidate_path(
                    destination,
                    prefix,
                    job_id,
                    variant,
                    variants,
                    extension,
                    item_status not in {"accepted", "needs_review"},
                    overwrite,
                )
                await asyncio.to_thread(_persist, last_data, path)
                final_path = str(path)
            except Exception as exc:  # noqa: BLE001
                item_status = "persistence_error"
                attempts.append({"attempt": len(attempts), "status": "persistence_error", "error": str(exc)})

        items.append(
            {
                "variant": variant,
                "status": item_status,
                "path": final_path or None,
                "attempt_count": len([entry for entry in attempts if entry.get("attempt")]),
                "attempts": attempts,
                "final_prompt": current_prompt,
                "provider": last_generation.get("provider"),
                "model": last_generation.get("model"),
                "upstream_provider": last_generation.get("upstream_provider"),
                "upstream_model": last_generation.get("upstream_model"),
                "request_id": last_generation.get("request_id"),
                "modality": last_generation.get("modality"),
                "aspect_ratio": last_generation.get("aspect_ratio", aspect_ratio),
                "qa": last_qa or None,
            }
        )

    statuses = {item["status"] for item in items}
    if statuses <= {"accepted"}:
        overall = "accepted"
    elif statuses <= {"accepted", "needs_review"} and "needs_review" in statuses:
        overall = "needs_review"
    elif len(statuses) > 1:
        overall = "partial_failure"
    else:
        overall = next(iter(statuses), "error")
    manifest = {
        "success": overall in {"accepted", "needs_review"},
        "status": overall,
        "orchestrator": "advanced-imagegen/0.3.0",
        "job_id": job_id,
        "wizard_id": args.get("wizard_id") or None,
        "provider": selected_provider,
        "model": selected_model or None,
        "qa_profile": qa_profile,
        "variants": variants,
        "max_iterations": max_iterations,
        "human_approval_required": require_human,
        "items": items,
    }
    return json.dumps(manifest, ensure_ascii=False)
