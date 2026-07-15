"""Profile-local supplier and model catalog."""

from __future__ import annotations

import copy
import os
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from .types import ModelSpec, ProviderSpec


class CatalogError(ValueError):
    """Raised for an invalid or unavailable provider/model selection."""


_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SUPPORTED_ADAPTERS = {"hermes-native", "http-json"}

_BUILTIN = {
    "defaults": {"provider": "hermes-native", "model": "active"},
    "providers": {
        "hermes-native": {
            "display_name": "Hermes Agent Native Image Generation",
            "adapter": "hermes-native",
            "enabled": True,
            "limits": {
                "qps": 1,
                "tpm": 60000,
                "max_concurrency": 1,
                "max_wait_seconds": 30,
                "retry": {"max_attempts": 2, "base_delay_seconds": 1, "max_delay_seconds": 8},
            },
            "models": {
                "active": {
                    "display_name": "Active Hermes image model",
                    "family": "hermes-active",
                    "upstream_model": "__active__",
                    "prompt_skill": "prompt-generic-image",
                    # Conservative until Hermes' dynamic provider capability
                    # probe refreshes this entry at runtime.
                    "modalities": ["text"],
                    "max_reference_images": 0,
                }
            },
        }
    },
}


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _active_config_path() -> Path:
    override = os.getenv("ADVANCED_IMAGEGEN_CONFIG", "").strip()
    if override:
        return Path(os.path.expanduser(override)).resolve()
    try:
        from hermes_constants import get_hermes_home

        return (get_hermes_home() / "advanced-imagegen.yaml").resolve()
    except Exception:
        return Path(os.path.expanduser("~/.hermes/advanced-imagegen.yaml")).resolve()


def _validate_limits(errors: list[str], label: str, raw: Any) -> None:
    if raw is None:
        return
    if not isinstance(raw, dict):
        errors.append(f"{label} limits must be a mapping")
        return
    numeric = {
        "qps": float,
        "tpm": int,
        "max_concurrency": int,
        "max_wait_seconds": float,
    }
    for key, caster in numeric.items():
        if key not in raw:
            continue
        try:
            if caster(raw[key]) <= 0:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"{label} limits.{key} must be positive")
    retry = raw.get("retry")
    if retry is not None and not isinstance(retry, dict):
        errors.append(f"{label} limits.retry must be a mapping")


class Catalog:
    """Load built-ins plus a profile-local YAML overlay."""

    def __init__(self, plugin_dir: Path, config_path: Path | None = None):
        self.plugin_dir = Path(plugin_dir).resolve()
        self.config_path = Path(config_path).resolve() if config_path else _active_config_path()
        self.providers: dict[str, ProviderSpec] = {}
        self.defaults: dict[str, str] = {}
        self.errors: list[str] = []
        try:
            self.reload()
        except CatalogError:
            # Keep the plugin and catalog diagnostics available even when an
            # operator has introduced a bad profile overlay. Native remains a
            # safe recovery path until the YAML is fixed and reloaded.
            self.defaults = dict(_BUILTIN["defaults"])
            self.providers = self._build_specs(_BUILTIN)
            self._refresh_native_capabilities()

    def reload(self) -> None:
        overlay: dict[str, Any] = {}
        if self.config_path.is_file():
            try:
                import yaml

                loaded = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
                if not isinstance(loaded, dict):
                    raise CatalogError("catalog root must be a mapping")
                overlay = loaded
            except Exception as exc:  # noqa: BLE001 - retained for catalog diagnostics
                self.providers = {}
                self.errors = [f"Cannot load {self.config_path}: {exc}"]
                raise CatalogError(self.errors[0]) from exc

        merged = _deep_merge(_BUILTIN, overlay)
        self.errors = self._validate_mapping(merged)
        if self.errors:
            raise CatalogError("; ".join(self.errors))
        self.defaults = {
            "provider": str((merged.get("defaults") or {}).get("provider") or "hermes-native"),
            "model": str((merged.get("defaults") or {}).get("model") or "active"),
        }
        self.providers = self._build_specs(merged)
        self._refresh_native_capabilities()

    def _refresh_native_capabilities(self) -> None:
        """Reflect the active Hermes backend without making catalog loading fragile."""
        provider = self.providers.get("hermes-native")
        if provider is None or "active" not in provider.models:
            return
        try:
            from tools.image_generation_tool import _active_image_capabilities

            capabilities = _active_image_capabilities()
            raw_modalities = capabilities.get("modalities") or ["text"]
            modalities = tuple(str(item) for item in raw_modalities)
            max_refs = max(0, int(capabilities.get("max_reference_images") or 0))
            model = replace(
                provider.models["active"],
                modalities=modalities,
                max_reference_images=max_refs,
            )
            models = dict(provider.models)
            models["active"] = model
            self.providers["hermes-native"] = replace(provider, models=models)
        except Exception:
            return

    def _validate_mapping(self, data: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        providers = data.get("providers")
        if not isinstance(providers, dict) or not providers:
            return ["providers must be a non-empty mapping"]
        for provider_id, raw_provider in providers.items():
            if not isinstance(provider_id, str) or not _ID_RE.fullmatch(provider_id):
                errors.append(f"invalid provider id: {provider_id!r}")
                continue
            if not isinstance(raw_provider, dict):
                errors.append(f"provider {provider_id} must be a mapping")
                continue
            adapter = str(raw_provider.get("adapter") or "")
            if adapter not in _SUPPORTED_ADAPTERS:
                errors.append(f"provider {provider_id} uses unsupported adapter {adapter!r}")
            raw_api = raw_provider.get("api")
            api = raw_api if isinstance(raw_api, dict) else {}
            if adapter == "http-json" and raw_api is not None and not isinstance(raw_api, dict):
                errors.append(f"provider {provider_id} api must be a mapping")
            if adapter == "http-json" and raw_provider.get("enabled", True):
                if not isinstance(api, dict) or not str(api.get("endpoint") or "").strip():
                    errors.append(f"enabled http-json provider {provider_id} requires api.endpoint")
                elif "REPLACE_WITH_" in str(api.get("endpoint")):
                    errors.append(f"enabled provider {provider_id} still uses a placeholder endpoint")
                elif not str(api.get("endpoint")).startswith(("http://", "https://")):
                    errors.append(f"provider {provider_id} api.endpoint must use http or https")
            if isinstance(api, dict):
                for section in ("request", "response", "async"):
                    if section in api and not isinstance(api[section], dict):
                        errors.append(f"provider {provider_id} api.{section} must be a mapping")
            _validate_limits(errors, f"provider {provider_id}", raw_provider.get("limits"))
            models = raw_provider.get("models")
            if not isinstance(models, dict) or not models:
                errors.append(f"provider {provider_id} requires at least one model")
                continue
            for model_id, raw_model in models.items():
                if not isinstance(model_id, str) or not _ID_RE.fullmatch(model_id):
                    errors.append(f"invalid model id {provider_id}/{model_id!r}")
                    continue
                if not isinstance(raw_model, dict):
                    errors.append(f"model {provider_id}/{model_id} must be a mapping")
                    continue
                skill = str(raw_model.get("prompt_skill") or "").split(":")[-1]
                if skill and not (self.plugin_dir / "skills" / skill / "SKILL.md").is_file():
                    errors.append(f"model {provider_id}/{model_id} references missing skill {skill}")
                modalities = raw_model.get("modalities", ["text"])
                if not isinstance(modalities, list) or "text" not in modalities:
                    errors.append(f"model {provider_id}/{model_id} modalities must include text")
                if raw_provider.get("enabled", True) and "REPLACE_WITH_" in str(raw_model.get("upstream_model") or ""):
                    errors.append(f"enabled model {provider_id}/{model_id} still uses a placeholder upstream_model")
                try:
                    if int(raw_model.get("max_reference_images") or 0) < 0:
                        raise ValueError
                except (TypeError, ValueError):
                    errors.append(f"model {provider_id}/{model_id} max_reference_images must be non-negative")
                _validate_limits(errors, f"model {provider_id}/{model_id}", raw_model.get("limits"))
        return errors

    @staticmethod
    def _build_specs(data: dict[str, Any]) -> dict[str, ProviderSpec]:
        result: dict[str, ProviderSpec] = {}
        for provider_id, raw_provider in data["providers"].items():
            models: dict[str, ModelSpec] = {}
            for model_id, raw_model in raw_provider["models"].items():
                modalities = tuple(str(item) for item in raw_model.get("modalities", ["text"]))
                models[model_id] = ModelSpec(
                    provider_id=provider_id,
                    id=model_id,
                    display_name=str(raw_model.get("display_name") or model_id),
                    family=str(raw_model.get("family") or model_id),
                    upstream_model=str(raw_model.get("upstream_model") or model_id),
                    prompt_skill=str(raw_model.get("prompt_skill") or "prompt-generic-image"),
                    modalities=modalities,
                    max_reference_images=max(0, int(raw_model.get("max_reference_images") or 0)),
                    enabled=bool(raw_model.get("enabled", True)),
                    config=copy.deepcopy(raw_model),
                )
            result[provider_id] = ProviderSpec(
                id=provider_id,
                display_name=str(raw_provider.get("display_name") or provider_id),
                adapter=str(raw_provider.get("adapter")),
                enabled=bool(raw_provider.get("enabled", True)),
                models=models,
                config=copy.deepcopy(raw_provider),
            )
        return result

    def get(self, provider_id: str | None, model_id: str | None) -> tuple[ProviderSpec, ModelSpec]:
        provider_key = str(provider_id or self.defaults.get("provider") or "hermes-native")
        provider = self.providers.get(provider_key)
        if provider is None:
            raise CatalogError(f"Unknown image provider: {provider_key}")
        if not provider.enabled:
            raise CatalogError(f"Image provider is disabled: {provider_key}")
        model_key = str(model_id or (self.defaults.get("model") if provider_key == self.defaults.get("provider") else ""))
        if not model_key:
            enabled_models = [model for model in provider.models.values() if model.enabled]
            if len(enabled_models) == 1:
                return provider, enabled_models[0]
            raise CatalogError(f"Model is required for provider {provider_key}")
        model = provider.models.get(model_key)
        if model is None:
            raise CatalogError(f"Unknown image model: {provider_key}/{model_key}")
        if not model.enabled:
            raise CatalogError(f"Image model is disabled: {provider_key}/{model_key}")
        return provider, model

    def public_catalog(self, include_disabled: bool = False) -> dict[str, Any]:
        providers = []
        for provider in self.providers.values():
            if include_disabled or provider.enabled:
                entry = provider.public_dict()
                if include_disabled:
                    entry["models"] = [model.public_dict() for model in provider.models.values()]
                providers.append(entry)
        return {
            "config_path": str(self.config_path),
            "defaults": dict(self.defaults),
            "providers": providers,
            "validation_errors": list(self.errors),
        }
