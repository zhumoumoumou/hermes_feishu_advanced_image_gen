"""Advanced multi-provider image-generation orchestration for Hermes."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


def _standalone_bootstrap():
    """Support file-based loaders that do not assign a package name."""
    package_name = "advanced_imagegen_runtime_package"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(Path(__file__).resolve().parent)]
        package.__package__ = package_name
        sys.modules[package_name] = package
    return importlib.import_module(f"{package_name}.bootstrap")


if __package__:
    from .bootstrap import register
    from .orchestrator import ADVANCED_IMAGE_GENERATE_SCHEMA, block_raw_image_generate
else:
    _bootstrap = _standalone_bootstrap()
    register = _bootstrap.register
    ADVANCED_IMAGE_GENERATE_SCHEMA = _bootstrap.ADVANCED_IMAGE_GENERATE_SCHEMA
    block_raw_image_generate = _bootstrap.block_raw_image_generate


__all__ = ["ADVANCED_IMAGE_GENERATE_SCHEMA", "block_raw_image_generate", "register"]
