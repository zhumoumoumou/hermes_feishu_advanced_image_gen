"""Advanced controlled image-generation workflow plugin for Hermes."""

import importlib.util
import sys
from pathlib import Path


def _load_orchestrator_standalone():
    """Support file-based loaders that do not assign a package name."""
    name = "advanced_imagegen_orchestrator"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    path = Path(__file__).resolve().with_name("orchestrator.py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load advanced-imagegen orchestrator from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


try:
    from .orchestrator import (
        ADVANCED_IMAGE_GENERATE_SCHEMA,
        block_raw_image_generate,
        build_handler,
    )
except ImportError:
    _orchestrator = _load_orchestrator_standalone()
    ADVANCED_IMAGE_GENERATE_SCHEMA = _orchestrator.ADVANCED_IMAGE_GENERATE_SCHEMA
    block_raw_image_generate = _orchestrator.block_raw_image_generate
    build_handler = _orchestrator.build_handler


_PLUGIN_DIR = Path(__file__).resolve().parent


def register(ctx) -> None:
    """Register the workflow skill, orchestrator tool, and bypass gate."""
    skills_dir = _PLUGIN_DIR / "skills"
    for child in sorted(skills_dir.iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.is_file():
            ctx.register_skill(
                child.name,
                skill_md,
                "Plan, generate, edit, and verify production images.",
            )
    ctx.register_tool(
        name="advanced_image_generate",
        toolset="image_gen",
        schema=ADVANCED_IMAGE_GENERATE_SCHEMA,
        handler=build_handler(ctx),
        is_async=True,
        description="Controlled image generation with QA, retry, persistence, and delivery status.",
        emoji="🎨",
    )
    ctx.register_hook("pre_tool_call", block_raw_image_generate)
