"""Plugin registration and long-lived runtime service wiring."""

from __future__ import annotations

from pathlib import Path

from .orchestrator import (
    ADVANCED_IMAGE_GENERATE_SCHEMA,
    block_raw_image_generate,
    build_handler,
    orchestrate,
)
from .runtime import Catalog, ProviderManager, WizardService
from .runtime.wizard import (
    CATALOG_SCHEMA,
    WIZARD_SCHEMA,
    build_catalog_handler,
    build_wizard_handler,
)


PLUGIN_DIR = Path(__file__).resolve().parent

_SKILL_DESCRIPTIONS = {
    "studio": "Plan, generate, edit, and verify production images.",
    "prompt-generic-image": "Turn a general image request into a confirmed production prompt.",
    "prompt-seedream-5-lite": "Optimize reasoning-, retrieval-, and knowledge-aware Seedream 5 Lite prompts.",
    "prompt-seedream-5-pro": "Optimize production-grade dense, precise, realistic, and multilingual Seedream 5 Pro prompts.",
}


def register(ctx) -> None:
    """Register skills, supplier catalog, wizard, executor, and raw-tool gate."""
    skills_dir = PLUGIN_DIR / "skills"
    for child in sorted(skills_dir.iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.is_file():
            ctx.register_skill(
                child.name,
                skill_md,
                _SKILL_DESCRIPTIONS.get(child.name, "Advanced image generation guidance."),
            )

    catalog = Catalog(PLUGIN_DIR)
    manager = ProviderManager(ctx, catalog)

    async def _execute(args: dict, task_id: str) -> str:
        return await orchestrate(
            ctx,
            args,
            task_id=task_id,
            provider_manager=manager,
        )

    wizard = WizardService(catalog, _execute)
    ctx.register_tool(
        name="advanced_image_wizard",
        toolset="image_gen",
        schema=WIZARD_SCHEMA,
        handler=build_wizard_handler(wizard),
        is_async=True,
        description="Multi-turn supplier/model selection, prompt refinement, confirmation, and generation.",
        emoji="🧭",
    )
    ctx.register_tool(
        name="advanced_image_catalog",
        toolset="image_gen",
        schema=CATALOG_SCHEMA,
        handler=build_catalog_handler(catalog, manager.reset_runtime),
        is_async=True,
        description="Inspect, validate, and reload configured image suppliers and models.",
        emoji="🗂️",
    )
    ctx.register_tool(
        name="advanced_image_generate",
        toolset="image_gen",
        schema=ADVANCED_IMAGE_GENERATE_SCHEMA,
        handler=build_handler(ctx, manager),
        is_async=True,
        description="Execute a confirmed image request with QA, retries, persistence, and delivery status.",
        emoji="🎨",
    )
    ctx.register_hook("pre_tool_call", block_raw_image_generate)
