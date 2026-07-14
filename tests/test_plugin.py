from __future__ import annotations

import asyncio
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
HERMES_AGENT = PLUGIN_DIR.parents[1] / "hermes-agent"
sys.path.insert(0, str(HERMES_AGENT))


def load_module(relative_path: str, name: str):
    path = PLUGIN_DIR / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_plugin(name: str = "advanced_imagegen_test"):
    spec = importlib.util.spec_from_file_location(
        name,
        PLUGIN_DIR / "__init__.py",
        submodule_search_locations=[str(PLUGIN_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def png_bytes(background=(40, 80, 120), foreground=None) -> bytes:
    pytest.importorskip("PIL")
    from PIL import Image

    image = Image.new("RGB", (128, 128), background)
    if foreground:
        for x in range(32, 96):
            for y in range(32, 96):
                image.putpixel((x, y), foreground)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class FakeContext:
    def __init__(self):
        self.generation_calls = []
        self.skill_calls = []
        self.tool_calls = []
        self.hook_calls = []

    def register_skill(self, *args, **kwargs):
        self.skill_calls.append((args, kwargs))

    def register_tool(self, **kwargs):
        self.tool_calls.append(kwargs)

    def register_hook(self, *args, **kwargs):
        self.hook_calls.append((args, kwargs))

    def dispatch_tool(self, name, args, **kwargs):
        assert name == "image_generate"
        self.generation_calls.append((args, kwargs))
        return json.dumps(
            {
                "success": True,
                "image": f"memory://{len(self.generation_calls)}",
                "provider": "fake-provider",
                "model": "fake-model",
                "modality": "text-to-image",
                "aspect_ratio": args["aspect_ratio"],
            }
        )


def test_registers_skill_tool_and_bypass_gate():
    plugin = load_plugin()
    ctx = FakeContext()
    plugin.register(ctx)

    assert ctx.skill_calls[0][0][0] == "studio"
    assert ctx.skill_calls[0][0][1] == PLUGIN_DIR / "skills" / "studio" / "SKILL.md"
    assert ctx.tool_calls[0]["name"] == "advanced_image_generate"
    assert ctx.tool_calls[0]["toolset"] == "image_gen"
    assert ctx.tool_calls[0]["is_async"] is True
    assert ctx.hook_calls[0][0][0] == "pre_tool_call"

    assert plugin.block_raw_image_generate("advanced_image_generate") is None
    blocked = plugin.block_raw_image_generate("image_generate")
    assert blocked and blocked["action"] == "block"
    assert "advanced_image_generate" in blocked["message"]


def test_acceptance_persists_and_returns_manifest(tmp_path, monkeypatch):
    plugin = load_plugin("advanced_imagegen_accept")
    orchestrator = sys.modules[f"{plugin.__name__}.orchestrator"]
    ctx = FakeContext()
    candidate = png_bytes()

    async def resolve(_source, _task_id):
        return candidate, "image/png"

    async def qa(*_args, **_kwargs):
        return {
            "passed": True,
            "score": 94,
            "summary": "All criteria pass.",
            "failures": [],
            "correction_prompt": "",
            "qa_provider": "fake-qa",
            "qa_model": "fake-vision",
        }

    monkeypatch.setattr(orchestrator, "_resolve_image", resolve)
    monkeypatch.setattr(orchestrator, "_visual_qa", qa)
    result = json.loads(
        asyncio.run(
            orchestrator.orchestrate(
                ctx,
                {
                    "prompt": "A blue product photograph",
                    "destination": str(tmp_path / "hero.webp"),
                    "acceptance_criteria": ["One centered product"],
                    "max_iterations": 1,
                },
            )
        )
    )

    assert result["success"] is True
    assert result["status"] == "accepted"
    item = result["items"][0]
    assert item["status"] == "accepted"
    assert item["path"].endswith("hero.png")
    assert Path(item["path"]).read_bytes() == candidate
    assert item["provider"] == "fake-provider"
    assert len(ctx.generation_calls) == 1


def test_failed_qa_drives_one_targeted_retry(tmp_path, monkeypatch):
    plugin = load_plugin("advanced_imagegen_retry")
    orchestrator = sys.modules[f"{plugin.__name__}.orchestrator"]
    ctx = FakeContext()
    candidate = png_bytes()
    qa_results = [
        {
            "passed": False,
            "score": 61,
            "summary": "Composition failed.",
            "failures": ["No requested negative space on the right."],
            "correction_prompt": "Move the subject left and preserve the style.",
        },
        {
            "passed": True,
            "score": 91,
            "summary": "Corrected.",
            "failures": [],
            "correction_prompt": "",
        },
    ]

    async def resolve(_source, _task_id):
        return candidate, "image/png"

    async def qa(*_args, **_kwargs):
        return qa_results.pop(0)

    monkeypatch.setattr(orchestrator, "_resolve_image", resolve)
    monkeypatch.setattr(orchestrator, "_visual_qa", qa)
    result = json.loads(
        asyncio.run(
            orchestrator.orchestrate(
                ctx,
                {
                    "prompt": "Editorial hero with negative space",
                    "destination": str(tmp_path),
                    "max_iterations": 1,
                },
            )
        )
    )

    assert result["status"] == "accepted"
    assert len(ctx.generation_calls) == 2
    retry_prompt = ctx.generation_calls[1][0]["prompt"]
    assert "No requested negative space" in retry_prompt
    assert "Move the subject left" in retry_prompt
    assert "Editorial hero with negative space" in retry_prompt
    assert result["items"][0]["attempt_count"] == 2


def test_visual_qa_enforces_profile_threshold():
    plugin = load_plugin("advanced_imagegen_threshold")
    orchestrator = sys.modules[f"{plugin.__name__}.orchestrator"]

    class Llm:
        async def acomplete_structured(self, **_kwargs):
            class Result:
                parsed = {
                    "passed": True,
                    "score": 80,
                    "summary": "Almost there.",
                    "failures": [],
                    "correction_prompt": "Increase fidelity.",
                }
                provider = "fake-qa"
                model = "fake-vision"

            return Result()

    class Context:
        llm = Llm()

    result = asyncio.run(
        orchestrator._visual_qa(
            Context(),
            png_bytes(),
            "image/png",
            "A product image",
            [],
            "",
            "strict",
            {"passed": True},
        )
    )
    assert result["passed"] is False
    assert "below the 85 threshold" in result["failures"][0]


def test_transparent_profile_removes_key_and_requires_review(tmp_path, monkeypatch):
    plugin = load_plugin("advanced_imagegen_transparent")
    orchestrator = sys.modules[f"{plugin.__name__}.orchestrator"]
    ctx = FakeContext()
    keyed = png_bytes((0, 255, 0), (220, 20, 20))

    async def resolve(_source, _task_id):
        return keyed, "image/png"

    async def qa(*_args, **_kwargs):
        return {
            "passed": True,
            "score": 95,
            "summary": "Clean cutout.",
            "failures": [],
            "correction_prompt": "",
        }

    monkeypatch.setattr(orchestrator, "_resolve_image", resolve)
    monkeypatch.setattr(orchestrator, "_visual_qa", qa)
    result = json.loads(
        asyncio.run(
            orchestrator.orchestrate(
                ctx,
                {
                    "prompt": "A red square asset",
                    "destination": str(tmp_path),
                    "qa_profile": "transparent",
                    "require_human_approval": True,
                    "max_iterations": 0,
                },
            )
        )
    )

    assert result["status"] == "needs_review"
    path = Path(result["items"][0]["path"])
    from PIL import Image

    with Image.open(path) as delivered:
        assert delivered.mode == "RGBA"
        assert delivered.getpixel((0, 0))[3] == 0
        assert delivered.getpixel((64, 64))[3] == 255


def test_generation_failure_is_not_delivery(tmp_path, monkeypatch):
    plugin = load_plugin("advanced_imagegen_failure")
    orchestrator = sys.modules[f"{plugin.__name__}.orchestrator"]

    class FailingContext(FakeContext):
        def dispatch_tool(self, name, args, **kwargs):
            return json.dumps({"success": False, "error": "provider unavailable"})

    result = json.loads(
        asyncio.run(
            orchestrator.orchestrate(
                FailingContext(),
                {"prompt": "An image", "destination": str(tmp_path)},
            )
        )
    )
    assert result["success"] is False
    assert result["status"] == "generation_error"
    assert result["items"][0]["path"] is None


def test_chroma_key_removal_and_inspection(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image

    remover = load_module("scripts/remove_chroma_key.py", "advanced_imagegen_remove")
    inspector = load_module("scripts/inspect_image.py", "advanced_imagegen_inspect")

    source = Image.new("RGB", (12, 12), (0, 255, 0))
    for x in range(3, 9):
        for y in range(3, 9):
            source.putpixel((x, y), (220, 20, 20))

    key = remover.detect_border_key(source)
    assert key == (0, 255, 0)
    result = remover.remove_key(source, key, 12, 220, True, True, 0)
    output = tmp_path / "cutout.png"
    result.save(output)

    report = inspector.inspect(output)
    assert report["has_alpha"] is True
    assert report["corner_alpha"] == [0, 0, 0, 0]
    assert report["transparent_fraction"] > 0.5
    assert result.getpixel((6, 6))[3] == 255
