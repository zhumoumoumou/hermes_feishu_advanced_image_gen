"""Provider-neutral image generation contracts."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelSpec:
    provider_id: str
    id: str
    display_name: str
    family: str
    upstream_model: str
    prompt_skill: str
    modalities: tuple[str, ...] = ("text",)
    max_reference_images: int = 0
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict, compare=False)

    def public_dict(self, plugin_name: str = "advanced-imagegen") -> dict[str, Any]:
        skill = self.prompt_skill
        if skill and ":" not in skill:
            skill = f"{plugin_name}:{skill}"
        return {
            "id": self.id,
            "display_name": self.display_name,
            "family": self.family,
            "modalities": list(self.modalities),
            "max_reference_images": self.max_reference_images,
            "prompt_skill": skill or None,
            "enabled": self.enabled,
        }


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    display_name: str
    adapter: str
    enabled: bool
    models: dict[str, ModelSpec]
    config: dict[str, Any] = field(default_factory=dict, compare=False)

    def public_dict(self, *, plugin_name: str = "advanced-imagegen") -> dict[str, Any]:
        api = self.config.get("api") if isinstance(self.config.get("api"), dict) else {}
        credential_env = str(api.get("api_key_env") or "")
        credential_ready = not credential_env or bool(os.getenv(credential_env))
        transport_ready = self.adapter == "hermes-native" or bool(api.get("endpoint"))
        return {
            "id": self.id,
            "display_name": self.display_name,
            "adapter": self.adapter,
            "enabled": self.enabled,
            "configured": transport_ready and credential_ready,
            "credential_env": credential_env or None,
            "models": [
                model.public_dict(plugin_name)
                for model in self.models.values()
                if model.enabled
            ],
        }


@dataclass(frozen=True)
class GenerationRequest:
    provider_id: str
    model_id: str
    prompt: str
    aspect_ratio: str = "square"
    image_url: str | None = None
    reference_image_urls: tuple[str, ...] = ()
    task_id: str = ""
    idempotency_key: str = ""


@dataclass
class GenerationResult:
    image: str
    provider: str
    model: str
    modality: str
    aspect_ratio: str
    upstream_provider: str | None = None
    upstream_model: str | None = None
    request_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": True,
            "image": self.image,
            "provider": self.provider,
            "model": self.model,
            "modality": self.modality,
            "aspect_ratio": self.aspect_ratio,
            "upstream_provider": self.upstream_provider,
            "upstream_model": self.upstream_model,
            "request_id": self.request_id,
        }
