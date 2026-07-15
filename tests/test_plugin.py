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

    skills = {call[0][0]: call[0][1] for call in ctx.skill_calls}
    assert set(skills) == {
        "studio",
        "prompt-generic-image",
        "prompt-seedream-5-lite",
        "prompt-seedream-5-pro",
    }
    assert skills["studio"] == PLUGIN_DIR / "skills" / "studio" / "SKILL.md"
    tools = {call["name"]: call for call in ctx.tool_calls}
    assert set(tools) == {
        "advanced_image_wizard",
        "advanced_image_catalog",
        "advanced_image_generate",
    }
    assert all(call["toolset"] == "image_gen" for call in tools.values())
    assert all(call["is_async"] is True for call in tools.values())
    assert ctx.hook_calls[0][0][0] == "pre_tool_call"

    assert plugin.block_raw_image_generate("advanced_image_generate") is None
    blocked = plugin.block_raw_image_generate("image_generate")
    assert blocked and blocked["action"] == "block"
    assert "advanced_image_generate" in blocked["message"]


def external_catalog_yaml(*, async_api: bool = False, tpm: int = 60000) -> str:
    async_block = """
      async:
        job_id_path: id
        poll_endpoint: https://supplier.test/tasks/{job_id}
        status_path: status
        success_values: [completed]
        failure_values: [failed]
        poll_interval_seconds: 0.2
        timeout_seconds: 2
""" if async_api else ""
    image_path = "output.url" if async_api else "data.0.url"
    return f"""version: 1
defaults:
  provider: atlascloud
  model: seedream-5-pro
providers:
  atlascloud:
    display_name: AtlasCloud
    adapter: http-json
    enabled: true
    api:
      endpoint: https://supplier.test/generate
      api_key_env: TEST_IMAGE_API_KEY
      request:
        model_field: model
        prompt_field: prompt
        aspect_ratio_field: aspect
{async_block}      response:
        image_path: {image_path}
        request_id_path: request_id
    limits:
      qps: 1000
      tpm: {tpm}
      max_concurrency: 2
      max_wait_seconds: 1
      retry:
        max_attempts: 2
        base_delay_seconds: 0
        max_delay_seconds: 0.1
    models:
      seedream-5-pro:
        display_name: Seedream 5 Pro
        family: seedream-5-pro
        upstream_model: seedream-upstream
        prompt_skill: prompt-seedream-5-pro
        modalities: [text, image, reference]
        max_reference_images: 4
      seedream-5-lite:
        display_name: Seedream 5 Lite
        family: seedream-5-lite
        upstream_model: seedream-lite-upstream
        prompt_skill: prompt-seedream-5-lite
        modalities: [text, image, reference]
        max_reference_images: 4
  bytedance:
    display_name: ByteDance
    adapter: http-json
    enabled: false
    api:
      endpoint: https://disabled.test/generate
    models:
      seedream-5-pro:
        family: seedream-5-pro
        upstream_model: seedream-other-upstream
        prompt_skill: prompt-seedream-5-pro
        modalities: [text, image, reference]
        max_reference_images: 4
      seedream-5-lite:
        family: seedream-5-lite
        upstream_model: seedream-lite-other-upstream
        prompt_skill: prompt-seedream-5-lite
        modalities: [text, image, reference]
        max_reference_images: 4
"""


def runtime_modules(plugin_name: str):
    plugin = load_plugin(plugin_name)
    prefix = plugin.__name__
    return (
        plugin,
        sys.modules[f"{prefix}.runtime.catalog"],
        sys.modules[f"{prefix}.runtime.providers"],
        sys.modules[f"{prefix}.runtime.wizard"],
    )


def test_catalog_keeps_model_skill_provider_neutral(tmp_path, monkeypatch):
    _plugin, catalog_mod, _providers_mod, _wizard_mod = runtime_modules("advanced_imagegen_catalog")
    config = tmp_path / "advanced-imagegen.yaml"
    config.write_text(external_catalog_yaml(), encoding="utf-8")
    monkeypatch.setenv("TEST_IMAGE_API_KEY", "secret-for-test")
    catalog = catalog_mod.Catalog(PLUGIN_DIR, config)

    atlas = catalog.providers["atlascloud"].models["seedream-5-pro"]
    bytedance = catalog.providers["bytedance"].models["seedream-5-pro"]
    assert atlas.family == bytedance.family == "seedream-5-pro"
    assert atlas.prompt_skill == bytedance.prompt_skill == "prompt-seedream-5-pro"
    atlas_lite = catalog.providers["atlascloud"].models["seedream-5-lite"]
    bytedance_lite = catalog.providers["bytedance"].models["seedream-5-lite"]
    assert atlas_lite.family == bytedance_lite.family == "seedream-5-lite"
    assert atlas_lite.prompt_skill == bytedance_lite.prompt_skill == "prompt-seedream-5-lite"
    public = catalog.public_catalog(include_disabled=True)
    assert public["defaults"] == {"provider": "atlascloud", "model": "seedream-5-pro"}
    assert next(p for p in public["providers"] if p["id"] == "atlascloud")["configured"] is True


def test_seedream_skills_encode_official_prompt_patterns():
    pro = (PLUGIN_DIR / "skills" / "prompt-seedream-5-pro" / "SKILL.md").read_text(encoding="utf-8")
    lite = (PLUGIN_DIR / "skills" / "prompt-seedream-5-lite" / "SKILL.md").read_text(encoding="utf-8")

    for content in (pro, lite):
        assert "subject + action + environment" in content
        assert "double quotes" in content
        assert "arrows, boxes, or scribbles" in content
        assert "exact count" in content
        assert "Never interpret silence as confirmation" in content
    assert "not a separate Pro variant" in pro
    assert "Image 2 supplies the character identity only" in lite


def test_invalid_enabled_placeholder_falls_back_to_native(tmp_path):
    _plugin, catalog_mod, _providers_mod, _wizard_mod = runtime_modules("advanced_imagegen_bad_catalog")
    config = tmp_path / "advanced-imagegen.yaml"
    config.write_text(
        external_catalog_yaml().replace("https://supplier.test/generate", "https://REPLACE_WITH_ENDPOINT/generate"),
        encoding="utf-8",
    )
    catalog = catalog_mod.Catalog(PLUGIN_DIR, config)
    assert "hermes-native" in catalog.providers
    assert "atlascloud" not in catalog.providers
    assert any("placeholder endpoint" in error for error in catalog.errors)


def test_http_json_provider_maps_request_and_response(tmp_path, monkeypatch):
    _plugin, catalog_mod, providers_mod, _wizard_mod = runtime_modules("advanced_imagegen_http")
    import httpx

    config = tmp_path / "advanced-imagegen.yaml"
    config.write_text(external_catalog_yaml(), encoding="utf-8")
    monkeypatch.setenv("TEST_IMAGE_API_KEY", "secret-for-test")
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        seen["idempotency"] = request.headers.get("idempotency-key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"data": [{"url": "https://images.test/result.png"}], "request_id": "req-1"})

    catalog = catalog_mod.Catalog(PLUGIN_DIR, config)
    adapter = providers_mod.HttpJsonAdapter(transport=httpx.MockTransport(handler))
    manager = providers_mod.ProviderManager(FakeContext(), catalog, {"http-json": adapter})
    result = asyncio.run(
        manager.generate(
            {
                "provider": "atlascloud",
                "model": "seedream-5-pro",
                "prompt": "A precise product image",
                "aspect_ratio": "landscape",
                "idempotency_key": "stable-key",
            }
        )
    )
    assert result["image"] == "https://images.test/result.png"
    assert result["provider"] == "atlascloud"
    assert result["model"] == "seedream-5-pro"
    assert result["upstream_model"] == "seedream-upstream"
    assert seen["auth"] == "Bearer secret-for-test"
    assert seen["idempotency"] == "stable-key"
    assert seen["body"] == {
        "model": "seedream-upstream",
        "prompt": "A precise product image",
        "aspect": "landscape",
    }


def test_http_json_async_polling(tmp_path, monkeypatch):
    _plugin, catalog_mod, providers_mod, _wizard_mod = runtime_modules("advanced_imagegen_async")
    import httpx

    config = tmp_path / "advanced-imagegen.yaml"
    config.write_text(external_catalog_yaml(async_api=True), encoding="utf-8")
    monkeypatch.setenv("TEST_IMAGE_API_KEY", "secret-for-test")
    methods = []

    def handler(request):
        methods.append(request.method)
        if request.method == "POST":
            return httpx.Response(202, json={"id": "job-7"})
        return httpx.Response(200, json={"status": "completed", "output": {"url": "https://images.test/async.png"}})

    catalog = catalog_mod.Catalog(PLUGIN_DIR, config)
    manager = providers_mod.ProviderManager(
        FakeContext(),
        catalog,
        {"http-json": providers_mod.HttpJsonAdapter(transport=httpx.MockTransport(handler))},
    )
    result = asyncio.run(
        manager.generate({"provider": "atlascloud", "model": "seedream-5-pro", "prompt": "Async image"})
    )
    assert result["image"] == "https://images.test/async.png"
    assert methods == ["POST", "GET"]


def test_http_429_is_retried_and_normalized(tmp_path, monkeypatch):
    _plugin, catalog_mod, providers_mod, _wizard_mod = runtime_modules("advanced_imagegen_retry_429")
    import httpx

    config = tmp_path / "advanced-imagegen.yaml"
    config.write_text(external_catalog_yaml(), encoding="utf-8")
    monkeypatch.setenv("TEST_IMAGE_API_KEY", "secret-for-test")
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"error": {"message": "slow down", "code": "quota"}})
        return httpx.Response(200, json={"data": [{"url": "https://images.test/retried.png"}]})

    manager = providers_mod.ProviderManager(
        FakeContext(),
        catalog_mod.Catalog(PLUGIN_DIR, config),
        {"http-json": providers_mod.HttpJsonAdapter(transport=httpx.MockTransport(handler))},
    )
    result = asyncio.run(
        manager.generate({"provider": "atlascloud", "model": "seedream-5-pro", "prompt": "Retry image"})
    )
    assert calls == 2
    assert result["attempt"] == 2


def test_http_auth_error_is_not_retried(tmp_path, monkeypatch):
    _plugin, catalog_mod, providers_mod, _wizard_mod = runtime_modules("advanced_imagegen_auth_error")
    import httpx

    config = tmp_path / "advanced-imagegen.yaml"
    config.write_text(external_catalog_yaml(), encoding="utf-8")
    monkeypatch.setenv("TEST_IMAGE_API_KEY", "bad-test-key")
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(401, text="invalid credential")

    manager = providers_mod.ProviderManager(
        FakeContext(),
        catalog_mod.Catalog(PLUGIN_DIR, config),
        {"http-json": providers_mod.HttpJsonAdapter(transport=httpx.MockTransport(handler))},
    )
    with pytest.raises(providers_mod.GenerationError) as exc_info:
        asyncio.run(
            manager.generate({"provider": "atlascloud", "model": "seedream-5-pro", "prompt": "Auth image"})
        )
    assert calls == 1
    assert exc_info.value.code == "authentication_failed"
    assert exc_info.value.category == "authentication"
    assert exc_info.value.retryable is False


def test_local_tpm_admission_fails_before_api(tmp_path, monkeypatch):
    _plugin, catalog_mod, providers_mod, _wizard_mod = runtime_modules("advanced_imagegen_tpm")
    import httpx

    config = tmp_path / "advanced-imagegen.yaml"
    config.write_text(external_catalog_yaml(tpm=1), encoding="utf-8")
    monkeypatch.setenv("TEST_IMAGE_API_KEY", "secret-for-test")
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"data": [{"url": "https://images.test/never.png"}]})

    manager = providers_mod.ProviderManager(
        FakeContext(),
        catalog_mod.Catalog(PLUGIN_DIR, config),
        {"http-json": providers_mod.HttpJsonAdapter(transport=httpx.MockTransport(handler))},
    )
    with pytest.raises(providers_mod.GenerationError) as exc_info:
        asyncio.run(
            manager.generate(
                {"provider": "atlascloud", "model": "seedream-5-pro", "prompt": "This prompt is longer than one token"}
            )
        )
    assert exc_info.value.code == "local_rate_limit"
    assert calls == 0


def test_wizard_requires_confirmation_before_execution(tmp_path):
    _plugin, catalog_mod, _providers_mod, wizard_mod = runtime_modules("advanced_imagegen_wizard")
    catalog = catalog_mod.Catalog(PLUGIN_DIR, tmp_path / "missing.yaml")
    calls = []

    async def execute(args, task_id):
        calls.append((args, task_id))
        return json.dumps({"success": True, "status": "accepted", "items": []})

    service = wizard_mod.WizardService(
        catalog,
        execute,
        store=wizard_mod.WizardStore(tmp_path / "wizard-state"),
    )
    started = json.loads(asyncio.run(service.handle({"action": "start", "user_request": "Create a hero"})))
    wizard_id = started["wizard_id"]
    selected = json.loads(
        asyncio.run(
            service.handle(
                {"action": "select", "wizard_id": wizard_id, "provider": "hermes-native", "model": "active"}
            )
        )
    )
    assert selected["selection"]["prompt_skill"] == "advanced-imagegen:prompt-generic-image"
    drafted = json.loads(
        asyncio.run(
            service.handle(
                {
                    "action": "draft",
                    "wizard_id": wizard_id,
                    "prompt": "A confirmed hero image",
                    "aspect_ratio": "landscape",
                    "qa_profile": "strict",
                }
            )
        )
    )
    assert drafted["status"] == "awaiting_confirmation"
    assert calls == []
    refused = json.loads(
        asyncio.run(service.handle({"action": "confirm", "wizard_id": wizard_id, "confirmed": False}))
    )
    assert refused["error_code"] == "confirmation_required"
    assert calls == []
    completed = json.loads(
        asyncio.run(
            service.handle(
                {"action": "confirm", "wizard_id": wizard_id, "confirmed": True},
                task_id="task-1",
            )
        )
    )
    assert completed["wizard_status"] == "completed"
    assert len(calls) == 1
    assert calls[0][0]["provider"] == "hermes-native"
    assert calls[0][0]["wizard_id"] == wizard_id


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
