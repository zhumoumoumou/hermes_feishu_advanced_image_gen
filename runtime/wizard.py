"""Persistent multi-turn provider/model/prompt/confirmation wizard."""

from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from .catalog import Catalog, CatalogError


WIZARD_SCHEMA = {
    "name": "advanced_image_wizard",
    "description": (
        "Guided multi-turn image generation. Start a wizard, let the user choose a supplier "
        "and model, load the returned model prompt skill, discuss and draft the prompt, show "
        "the confirmation summary, and call confirm only after explicit user approval."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["start", "select", "draft", "confirm", "status", "cancel"],
            },
            "wizard_id": {"type": "string"},
            "user_request": {"type": "string"},
            "provider": {"type": "string"},
            "model": {"type": "string"},
            "prompt": {"type": "string"},
            "aspect_ratio": {
                "type": "string",
                "enum": ["landscape", "portrait", "square"],
                "default": "square",
            },
            "image_url": {"type": "string"},
            "reference_image_urls": {"type": "array", "items": {"type": "string"}},
            "destination": {"type": "string"},
            "filename_prefix": {"type": "string"},
            "variants": {"type": "integer", "minimum": 1, "maximum": 4},
            "variant_instructions": {"type": "array", "items": {"type": "string"}},
            "qa_profile": {
                "type": "string",
                "enum": ["standard", "strict", "transparent", "exact-text"],
            },
            "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
            "required_text": {"type": "string"},
            "max_iterations": {"type": "integer", "minimum": 0, "maximum": 2},
            "require_human_approval": {"type": "boolean"},
            "confirmed": {
                "type": "boolean",
                "description": "Must be true only after the user explicitly approves the summary.",
            },
        },
        "required": ["action"],
    },
}


CATALOG_SCHEMA = {
    "name": "advanced_image_catalog",
    "description": "Inspect, validate, or reload configured image suppliers and models.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "describe", "validate", "reload"]},
            "provider": {"type": "string"},
            "model": {"type": "string"},
            "include_disabled": {"type": "boolean", "default": False},
        },
        "required": ["action"],
    },
}


_WIZARD_ID_RE = re.compile(r"^[a-f0-9]{16}$")
_DRAFT_FIELDS = {
    "prompt",
    "aspect_ratio",
    "image_url",
    "reference_image_urls",
    "destination",
    "filename_prefix",
    "variants",
    "variant_instructions",
    "qa_profile",
    "acceptance_criteria",
    "required_text",
    "max_iterations",
    "require_human_approval",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WizardStore:
    def __init__(self, root: Path | None = None):
        if root is None:
            try:
                from hermes_constants import get_hermes_home

                root = get_hermes_home() / "state" / "advanced-imagegen" / "wizards"
            except Exception:
                root = Path(os.path.expanduser("~/.hermes/state/advanced-imagegen/wizards"))
        self.root = Path(root).resolve()

    def _path(self, wizard_id: str) -> Path:
        if not _WIZARD_ID_RE.fullmatch(wizard_id):
            raise ValueError("Invalid wizard_id")
        path = self.root / f"{wizard_id}.json"
        from agent.file_safety import is_write_denied

        if is_write_denied(str(path)):
            raise PermissionError(f"Wizard state path is not writable: {path}")
        return path

    def load(self, wizard_id: str) -> dict[str, Any]:
        path = self._path(wizard_id)
        if not path.is_file():
            raise FileNotFoundError(f"Unknown wizard_id: {wizard_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Wizard state is corrupted")
        return data

    def save(self, state: dict[str, Any]) -> None:
        path = self._path(str(state["wizard_id"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)


def _summary(state: dict[str, Any]) -> dict[str, Any]:
    selection = state.get("selection") or {}
    draft = state.get("draft") or {}
    return {
        "provider": selection.get("provider"),
        "model": selection.get("model"),
        "prompt_skill": selection.get("prompt_skill"),
        "prompt": draft.get("prompt"),
        "aspect_ratio": draft.get("aspect_ratio", "square"),
        "image_url": draft.get("image_url"),
        "reference_image_urls": draft.get("reference_image_urls", []),
        "variants": draft.get("variants", 1),
        "variant_instructions": draft.get("variant_instructions", []),
        "qa_profile": draft.get("qa_profile", "standard"),
        "acceptance_criteria": draft.get("acceptance_criteria", []),
        "required_text": draft.get("required_text"),
        "destination": draft.get("destination"),
    }


class WizardService:
    def __init__(
        self,
        catalog: Catalog,
        execute: Callable[[dict[str, Any], str], Awaitable[str]],
        *,
        store: WizardStore | None = None,
    ):
        self.catalog = catalog
        self.execute = execute
        self.store = store or WizardStore()
        self._lock = asyncio.Lock()

    async def handle(self, args: dict[str, Any], task_id: str = "") -> str:
        action = str(args.get("action") or "")
        try:
            if action == "start":
                return await self._start(args)
            wizard_id = str(args.get("wizard_id") or "")
            if not wizard_id:
                return self._error("wizard_id is required", "invalid_request")
            if action == "select":
                return await self._select(wizard_id, args)
            if action == "draft":
                return await self._draft(wizard_id, args)
            if action == "confirm":
                return await self._confirm(wizard_id, args, task_id)
            if action == "status":
                return await self._status(wizard_id)
            if action == "cancel":
                return await self._cancel(wizard_id)
            return self._error(f"Unsupported wizard action: {action}", "invalid_request")
        except (CatalogError, FileNotFoundError, PermissionError, ValueError) as exc:
            return self._error(str(exc), "wizard_error")

    async def _start(self, args: dict[str, Any]) -> str:
        state = {
            "wizard_id": uuid.uuid4().hex[:16],
            "status": "awaiting_selection",
            "created_at": _now(),
            "updated_at": _now(),
            "user_request": str(args.get("user_request") or ""),
            "selection": None,
            "draft": None,
            "result": None,
        }
        async with self._lock:
            self.store.save(state)
        return json.dumps(
            {
                "success": True,
                "wizard_id": state["wizard_id"],
                "status": state["status"],
                "catalog": self.catalog.public_catalog(),
                "next_action": "Ask the user to choose a provider and model, then call action=select.",
            },
            ensure_ascii=False,
        )

    async def _select(self, wizard_id: str, args: dict[str, Any]) -> str:
        if not args.get("provider") or not args.get("model"):
            return self._error("provider and model are required for action=select", "invalid_request")
        provider, model = self.catalog.get(str(args.get("provider") or ""), str(args.get("model") or ""))
        skill = model.prompt_skill
        if skill and ":" not in skill:
            skill = f"advanced-imagegen:{skill}"
        async with self._lock:
            state = self.store.load(wizard_id)
            if state.get("status") in {"generating", "completed", "cancelled"}:
                return self._error(f"Cannot change selection while status={state.get('status')}", "invalid_state")
            state["selection"] = {
                "provider": provider.id,
                "provider_display_name": provider.display_name,
                "model": model.id,
                "model_display_name": model.display_name,
                "model_family": model.family,
                "prompt_skill": skill,
                "modalities": list(model.modalities),
                "max_reference_images": model.max_reference_images,
            }
            state["status"] = "optimizing_prompt"
            state["updated_at"] = _now()
            self.store.save(state)
        return json.dumps(
            {
                "success": True,
                "wizard_id": wizard_id,
                "status": "optimizing_prompt",
                "selection": state["selection"],
                "next_action": (
                    f"Load {skill} with skill_view, discuss the prompt and input-image roles with "
                    "the user, then call action=draft with the agreed candidate."
                ),
            },
            ensure_ascii=False,
        )

    async def _draft(self, wizard_id: str, args: dict[str, Any]) -> str:
        prompt = str(args.get("prompt") or "").strip()
        if not prompt:
            return self._error("prompt is required for action=draft", "invalid_request")
        async with self._lock:
            state = self.store.load(wizard_id)
            if not state.get("selection"):
                return self._error("Select a provider and model before drafting", "invalid_state")
            if state.get("status") in {"generating", "completed", "cancelled"}:
                return self._error(f"Cannot update draft while status={state.get('status')}", "invalid_state")
            selection = state["selection"]
            refs = [str(item) for item in (args.get("reference_image_urls") or [])]
            if args.get("image_url") and "image" not in selection.get("modalities", []):
                return self._error("Selected model does not support image-to-image input", "modality_not_supported")
            if refs and not ({"image", "reference"} & set(selection.get("modalities", []))):
                return self._error("Selected model does not support reference images", "modality_not_supported")
            if len(refs) > int(selection.get("max_reference_images") or 0):
                return self._error("Too many reference images for the selected model", "invalid_request")
            draft = {key: args[key] for key in _DRAFT_FIELDS if key in args}
            draft["prompt"] = prompt
            draft.setdefault("aspect_ratio", "square")
            draft.setdefault("variants", 1)
            draft.setdefault("qa_profile", "standard")
            draft.setdefault("max_iterations", 1)
            state["draft"] = draft
            state["status"] = "awaiting_confirmation"
            state["updated_at"] = _now()
            self.store.save(state)
        return json.dumps(
            {
                "success": True,
                "wizard_id": wizard_id,
                "status": "awaiting_confirmation",
                "confirmation_required": True,
                "confirmation_summary": _summary(state),
                "next_action": (
                    "Show this complete summary to the user. Do not generate yet. After the user "
                    "explicitly approves it, call action=confirm with confirmed=true."
                ),
            },
            ensure_ascii=False,
        )

    async def _confirm(self, wizard_id: str, args: dict[str, Any], task_id: str) -> str:
        if args.get("confirmed") is not True:
            return self._error("confirmed=true is required after explicit user approval", "confirmation_required")
        async with self._lock:
            state = self.store.load(wizard_id)
            if state.get("status") == "completed" and state.get("result") is not None:
                cached = dict(state["result"])
                cached.setdefault("wizard_id", wizard_id)
                cached["wizard_status"] = "completed"
                return json.dumps(cached, ensure_ascii=False)
            if state.get("status") != "awaiting_confirmation" or not state.get("draft"):
                return self._error(f"Wizard is not ready to generate (status={state.get('status')})", "invalid_state")
            state["status"] = "generating"
            state["updated_at"] = _now()
            self.store.save(state)
            generation_args = dict(state["draft"])
            generation_args["provider"] = state["selection"]["provider"]
            generation_args["model"] = state["selection"]["model"]
            generation_args["wizard_id"] = wizard_id
        try:
            raw = await self.execute(generation_args, task_id)
            result = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(result, dict):
                raise ValueError("Generation returned an invalid manifest")
        except Exception as exc:  # noqa: BLE001 - persist a recoverable wizard failure
            result = {"success": False, "status": "generation_error", "error": str(exc), "wizard_id": wizard_id}
        async with self._lock:
            state = self.store.load(wizard_id)
            state["status"] = "completed" if result.get("success") else "failed"
            state["result"] = result
            state["updated_at"] = _now()
            self.store.save(state)
        result.setdefault("wizard_id", wizard_id)
        result["wizard_status"] = state["status"]
        return json.dumps(result, ensure_ascii=False)

    async def _status(self, wizard_id: str) -> str:
        async with self._lock:
            state = self.store.load(wizard_id)
        return json.dumps(
            {
                "success": True,
                "wizard_id": wizard_id,
                "status": state.get("status"),
                "user_request": state.get("user_request"),
                "selection": state.get("selection"),
                "confirmation_summary": _summary(state) if state.get("draft") else None,
                "result": state.get("result"),
                "updated_at": state.get("updated_at"),
            },
            ensure_ascii=False,
        )

    async def _cancel(self, wizard_id: str) -> str:
        async with self._lock:
            state = self.store.load(wizard_id)
            if state.get("status") == "generating":
                return self._error("A running provider request cannot be cancelled by this foundation release", "invalid_state")
            if state.get("status") != "completed":
                state["status"] = "cancelled"
                state["updated_at"] = _now()
                self.store.save(state)
        return json.dumps({"success": True, "wizard_id": wizard_id, "status": state.get("status")})

    @staticmethod
    def _error(message: str, code: str) -> str:
        return json.dumps({"success": False, "error": message, "error_code": code}, ensure_ascii=False)


def build_wizard_handler(service: WizardService):
    async def _handler(args: dict[str, Any], **kwargs: Any) -> str:
        return await service.handle(args, task_id=str(kwargs.get("task_id") or ""))

    return _handler


def build_catalog_handler(catalog: Catalog, reset_runtime: Callable[[], None]):
    async def _handler(args: dict[str, Any], **_: Any) -> str:
        action = str(args.get("action") or "")
        try:
            if action == "list":
                payload = catalog.public_catalog(bool(args.get("include_disabled", False)))
                return json.dumps({"success": True, **payload}, ensure_ascii=False)
            if action == "describe":
                provider, model = catalog.get(args.get("provider"), args.get("model"))
                return json.dumps(
                    {
                        "success": True,
                        "provider": provider.public_dict(),
                        "model": model.public_dict(),
                        "config_path": str(catalog.config_path),
                    },
                    ensure_ascii=False,
                )
            if action in {"validate", "reload"}:
                catalog.reload()
                reset_runtime()
                return json.dumps(
                    {
                        "success": True,
                        "status": "valid" if action == "validate" else "reloaded",
                        **catalog.public_catalog(True),
                    },
                    ensure_ascii=False,
                )
            return json.dumps({"success": False, "error": f"Unsupported catalog action: {action}"})
        except Exception as exc:  # noqa: BLE001
            return json.dumps(
                {
                    "success": False,
                    "error": str(exc),
                    "error_code": "catalog_error",
                    "config_path": str(catalog.config_path),
                },
                ensure_ascii=False,
            )

    return _handler
