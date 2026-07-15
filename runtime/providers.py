"""Supplier adapters, error normalization, retries, and admission control."""

from __future__ import annotations

import asyncio
import base64
import copy
import json
import os
import random
import time
import uuid
from typing import Any, Protocol

from .catalog import Catalog, CatalogError
from .rate_limit import AsyncRateLimiter, LimitPolicy, estimate_prompt_tokens
from .types import GenerationRequest, GenerationResult, ModelSpec, ProviderSpec


class GenerationError(RuntimeError):
    """Normalized provider error safe to return to the agent."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_error",
        category: str = "provider",
        retryable: bool = False,
        status_code: int | None = None,
        provider_code: str | None = None,
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.category = category
        self.retryable = retryable
        self.status_code = status_code
        self.provider_code = provider_code
        self.retry_after = retry_after

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": False,
            "error": str(self),
            "error_code": self.code,
            "error_category": self.category,
            "retryable": self.retryable,
            "status_code": self.status_code,
            "provider_code": self.provider_code,
        }


class ProviderAdapter(Protocol):
    async def generate(
        self,
        provider: ProviderSpec,
        model: ModelSpec,
        request: GenerationRequest,
    ) -> GenerationResult: ...


def _parse_json_result(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        raise GenerationError(raw, code="provider_contract", category="contract")
    raise GenerationError(
        f"Provider returned unsupported result type: {type(raw).__name__}",
        code="provider_contract",
        category="contract",
    )


class HermesNativeAdapter:
    """Wrap the active Hermes image_generate provider chain as one supplier."""

    def __init__(self, ctx):
        self.ctx = ctx

    async def generate(
        self,
        provider: ProviderSpec,
        model: ModelSpec,
        request: GenerationRequest,
    ) -> GenerationResult:
        args: dict[str, Any] = {
            "prompt": request.prompt,
            "aspect_ratio": request.aspect_ratio,
        }
        if request.image_url:
            args["image_url"] = request.image_url
        if request.reference_image_urls:
            args["reference_image_urls"] = list(request.reference_image_urls)
        try:
            raw = await asyncio.to_thread(
                self.ctx.dispatch_tool,
                "image_generate",
                args,
                task_id=request.task_id,
            )
        except Exception as exc:  # noqa: BLE001
            raise GenerationError(
                f"Hermes native generation failed: {exc}",
                code="native_exception",
                retryable=True,
            ) from exc
        parsed = _parse_json_result(raw)
        image = parsed.get("image") or parsed.get("image_url") or parsed.get("url")
        if parsed.get("success") is False or not image:
            error_type = str(parsed.get("error_type") or "native_provider_error")
            retryable = error_type in {"rate_limit", "timeout", "provider_exception", "server_error"}
            raise GenerationError(
                str(parsed.get("error") or "Hermes native provider returned no image"),
                code=error_type,
                category="native",
                retryable=retryable,
                provider_code=error_type,
            )
        return GenerationResult(
            image=str(image),
            provider=provider.id,
            model=model.id,
            modality=str(parsed.get("modality") or ("image" if request.image_url else "text")),
            aspect_ratio=str(parsed.get("aspect_ratio") or request.aspect_ratio),
            upstream_provider=str(parsed.get("provider") or "") or None,
            upstream_model=str(parsed.get("model") or "") or None,
            request_id=str(parsed.get("request_id") or "") or None,
            raw=parsed,
        )


def _path_parts(path: str) -> list[str]:
    return [part for part in str(path or "").split(".") if part]


def _path_get(data: Any, path: str, default: Any = None) -> Any:
    current = data
    for part in _path_parts(path):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return default
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    return current


def _path_set(data: dict[str, Any], path: str, value: Any) -> None:
    parts = _path_parts(path)
    if not parts:
        return
    current = data
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value


def _merge_api(provider: ProviderSpec, model: ModelSpec) -> dict[str, Any]:
    base = copy.deepcopy(provider.config.get("api") or {})
    override = model.config.get("api") or {}
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key].update(copy.deepcopy(value))
        else:
            base[key] = copy.deepcopy(value)
    return base


def _retry_after(headers: Any) -> float | None:
    value = headers.get("retry-after") if headers else None
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def _http_error(status: int, payload: Any, headers: Any) -> GenerationError:
    message = _path_get(payload, "error.message") or _path_get(payload, "message") or f"HTTP {status}"
    provider_code = _path_get(payload, "error.code") or _path_get(payload, "code")
    if status in {401}:
        category, code, retryable = "authentication", "authentication_failed", False
    elif status in {403}:
        category, code, retryable = "permission", "permission_denied", False
    elif status in {400, 404, 405, 409, 422}:
        category, code, retryable = "request", "invalid_request", False
    elif status == 429:
        category, code, retryable = "rate_limit", "provider_rate_limit", True
    elif status in {408, 425} or status >= 500:
        category, code, retryable = "provider", "provider_unavailable", True
    else:
        category, code, retryable = "provider", "provider_http_error", False
    return GenerationError(
        str(message),
        code=code,
        category=category,
        retryable=retryable,
        status_code=status,
        provider_code=str(provider_code) if provider_code is not None else None,
        retry_after=_retry_after(headers),
    )


class HttpJsonAdapter:
    """Declarative JSON adapter supporting synchronous and polled async APIs."""

    def __init__(self, *, transport: Any = None):
        self.transport = transport

    @staticmethod
    async def _normalize_image(source: str, mode: str, task_id: str) -> str:
        if mode != "data-url" or source.startswith(("http://", "https://", "data:")):
            return source
        from tools.image_source import ResolveContext, resolve_image_source

        resolved = await resolve_image_source(source, ResolveContext(task_id=task_id or None))
        encoded = base64.b64encode(resolved.data).decode("ascii")
        return f"data:{resolved.mime};base64,{encoded}"

    @staticmethod
    def _headers(api: dict[str, Any], request: GenerationRequest) -> dict[str, str]:
        headers = {str(k): str(v) for k, v in (api.get("headers") or {}).items()}
        headers.setdefault("Content-Type", "application/json")
        api_key_env = str(api.get("api_key_env") or "")
        if api_key_env:
            api_key = os.getenv(api_key_env, "")
            if not api_key:
                raise GenerationError(
                    f"Required credential environment variable is not set: {api_key_env}",
                    code="credential_missing",
                    category="configuration",
                )
            header = str(api.get("auth_header") or "Authorization")
            scheme = str(api.get("auth_scheme") or "Bearer").strip()
            headers[header] = f"{scheme} {api_key}".strip()
        if request.idempotency_key:
            headers[str(api.get("idempotency_header") or "Idempotency-Key")] = request.idempotency_key
        return headers

    async def _body(self, api: dict[str, Any], model: ModelSpec, request: GenerationRequest) -> dict[str, Any]:
        request_cfg = api.get("request") or {}
        body = copy.deepcopy(request_cfg.get("static_body") or {})
        _path_set(body, str(request_cfg.get("model_field") or "model"), model.upstream_model)
        _path_set(body, str(request_cfg.get("prompt_field") or "prompt"), request.prompt)
        aspect_map = request_cfg.get("aspect_ratio_map") or {}
        aspect = aspect_map.get(request.aspect_ratio, request.aspect_ratio)
        _path_set(body, str(request_cfg.get("aspect_ratio_field") or "aspect_ratio"), aspect)
        image_mode = str(request_cfg.get("input_image_mode") or "passthrough")
        if request.image_url:
            image = await self._normalize_image(request.image_url, image_mode, request.task_id)
            _path_set(body, str(request_cfg.get("image_url_field") or "image_url"), image)
        if request.reference_image_urls:
            refs = [
                await self._normalize_image(source, image_mode, request.task_id)
                for source in request.reference_image_urls
            ]
            _path_set(
                body,
                str(request_cfg.get("reference_images_field") or "reference_image_urls"),
                refs,
            )
        return body

    @staticmethod
    def _json(response: Any) -> dict[str, Any]:
        try:
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise GenerationError(
                "Provider returned a non-JSON response",
                code="provider_contract",
                category="contract",
                status_code=response.status_code,
            ) from exc
        if not isinstance(payload, dict):
            raise GenerationError(
                "Provider JSON response must be an object",
                code="provider_contract",
                category="contract",
                status_code=response.status_code,
            )
        return payload

    async def _request(self, client: Any, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await client.request(method, url, **kwargs)
        except Exception as exc:  # noqa: BLE001
            try:
                import httpx

                retryable = isinstance(exc, (httpx.TimeoutException, httpx.TransportError))
            except Exception:
                retryable = True
            raise GenerationError(
                f"Provider network error: {exc}",
                code="provider_network_error",
                category="network",
                retryable=retryable,
            ) from exc
        if response.status_code >= 400:
            try:
                payload = response.json()
                if not isinstance(payload, dict):
                    payload = {"message": f"HTTP {response.status_code}"}
            except Exception:
                payload = {
                    "message": (response.text or f"HTTP {response.status_code}")[:1000],
                }
            raise _http_error(response.status_code, payload, response.headers)
        payload = self._json(response)
        return payload

    async def _poll(
        self,
        client: Any,
        api: dict[str, Any],
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        async_cfg = api.get("async") or {}
        job_id = _path_get(payload, str(async_cfg.get("job_id_path") or "id"))
        if not job_id:
            raise GenerationError(
                "Async provider response did not contain a job id",
                code="provider_contract",
                category="contract",
            )
        endpoint = str(async_cfg.get("poll_endpoint") or "").format(job_id=job_id)
        if not endpoint:
            raise GenerationError("async.poll_endpoint is required", code="provider_config", category="configuration")
        interval = max(0.2, float(async_cfg.get("poll_interval_seconds", 2)))
        timeout = max(interval, float(async_cfg.get("timeout_seconds", 180)))
        status_path = str(async_cfg.get("status_path") or "status")
        success_values = {str(v).lower() for v in async_cfg.get("success_values", ["succeeded", "completed", "success"])}
        failure_values = {str(v).lower() for v in async_cfg.get("failure_values", ["failed", "error", "cancelled"])}
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            current = await self._request(client, "GET", endpoint, headers=headers)
            status = str(_path_get(current, status_path, "")).lower()
            if status in success_values:
                return current
            if status in failure_values:
                error_path = str(async_cfg.get("error_path") or "error.message")
                raise GenerationError(
                    str(_path_get(current, error_path, f"Async job {job_id} failed")),
                    code="async_job_failed",
                    category="provider",
                    provider_code=status or None,
                )
            await asyncio.sleep(interval)
        raise GenerationError(
            f"Async generation job {job_id} timed out after {timeout:g}s",
            code="async_job_timeout",
            category="timeout",
            retryable=True,
        )

    async def generate(
        self,
        provider: ProviderSpec,
        model: ModelSpec,
        request: GenerationRequest,
    ) -> GenerationResult:
        import httpx

        api = _merge_api(provider, model)
        endpoint = str(api.get("endpoint") or "")
        if not endpoint:
            raise GenerationError("api.endpoint is required", code="provider_config", category="configuration")
        headers = self._headers(api, request)
        body = await self._body(api, model, request)
        timeout = max(1.0, float(api.get("request_timeout_seconds", 60)))
        async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
            payload = await self._request(client, "POST", endpoint, headers=headers, json=body)
            if isinstance(api.get("async"), dict):
                payload = await self._poll(client, api, payload, headers)
        response_cfg = api.get("response") or {}
        image_path = str(response_cfg.get("image_path") or "data.0.url")
        image = _path_get(payload, image_path)
        if isinstance(image, list):
            image = image[0] if image else None
        if not isinstance(image, str) or not image:
            error_path = str(response_cfg.get("error_path") or "error.message")
            message = _path_get(payload, error_path) or f"No image at response path {image_path}"
            raise GenerationError(str(message), code="provider_contract", category="contract")
        request_id = _path_get(payload, str(response_cfg.get("request_id_path") or "request_id"))
        return GenerationResult(
            image=image,
            provider=provider.id,
            model=model.id,
            modality="image" if request.image_url or request.reference_image_urls else "text",
            aspect_ratio=request.aspect_ratio,
            upstream_provider=provider.id,
            upstream_model=model.upstream_model,
            request_id=str(request_id) if request_id else None,
            raw=payload,
        )


class ProviderManager:
    """Resolve selections and execute them under provider/model policies."""

    def __init__(self, ctx, catalog: Catalog, adapters: dict[str, ProviderAdapter] | None = None):
        self.ctx = ctx
        self.catalog = catalog
        self.adapters: dict[str, ProviderAdapter] = {
            "hermes-native": HermesNativeAdapter(ctx),
            "http-json": HttpJsonAdapter(),
        }
        if adapters:
            self.adapters.update(adapters)
        self._limiters: dict[tuple[str, str], AsyncRateLimiter] = {}

    def reset_runtime(self) -> None:
        self._limiters.clear()

    @staticmethod
    def _request_from_args(args: dict[str, Any], task_id: str = "") -> GenerationRequest:
        return GenerationRequest(
            provider_id=str(args.get("provider") or ""),
            model_id=str(args.get("model") or ""),
            prompt=str(args.get("prompt") or ""),
            aspect_ratio=str(args.get("aspect_ratio") or "square"),
            image_url=str(args.get("image_url")) if args.get("image_url") else None,
            reference_image_urls=tuple(str(item) for item in (args.get("reference_image_urls") or [])),
            task_id=task_id,
            idempotency_key=str(args.get("idempotency_key") or uuid.uuid4().hex),
        )

    async def generate(self, args: dict[str, Any], *, task_id: str = "") -> dict[str, Any]:
        request = self._request_from_args(args, task_id)
        if not request.prompt.strip():
            raise GenerationError("prompt is required", code="invalid_request", category="request")
        if request.aspect_ratio not in {"landscape", "portrait", "square"}:
            raise GenerationError(
                f"Unsupported aspect_ratio: {request.aspect_ratio}",
                code="invalid_request",
                category="request",
            )
        try:
            provider, model = self.catalog.get(request.provider_id or None, request.model_id or None)
        except CatalogError as exc:
            raise GenerationError(str(exc), code="selection_invalid", category="configuration") from exc
        request = GenerationRequest(
            provider_id=provider.id,
            model_id=model.id,
            prompt=request.prompt,
            aspect_ratio=request.aspect_ratio,
            image_url=request.image_url,
            reference_image_urls=request.reference_image_urls,
            task_id=request.task_id,
            idempotency_key=request.idempotency_key,
        )
        if request.image_url and "image" not in model.modalities:
            raise GenerationError(
                f"Model {provider.id}/{model.id} does not support image-to-image input",
                code="modality_not_supported",
                category="request",
            )
        if request.reference_image_urls:
            if "reference" not in model.modalities and "image" not in model.modalities:
                raise GenerationError(
                    f"Model {provider.id}/{model.id} does not support reference images",
                    code="modality_not_supported",
                    category="request",
                )
            if len(request.reference_image_urls) > model.max_reference_images:
                raise GenerationError(
                    f"Model {provider.id}/{model.id} accepts at most {model.max_reference_images} reference images",
                    code="too_many_reference_images",
                    category="request",
                )
        adapter = self.adapters.get(provider.adapter)
        if adapter is None:
            raise GenerationError(
                f"No runtime adapter registered for {provider.adapter}",
                code="adapter_missing",
                category="configuration",
            )
        policy = LimitPolicy.from_mappings(
            provider.config.get("limits") or {},
            model.config.get("limits") or {},
        )
        key = (provider.id, model.id)
        limiter = self._limiters.setdefault(key, AsyncRateLimiter(policy))
        try:
            await limiter.acquire(estimate_prompt_tokens(request.prompt))
        except TimeoutError as exc:
            raise GenerationError(
                str(exc),
                code="local_rate_limit",
                category="rate_limit",
            ) from exc
        try:
            last_error: GenerationError | None = None
            for attempt in range(1, policy.max_attempts + 1):
                try:
                    result = await adapter.generate(provider, model, request)
                    payload = result.to_dict()
                    payload["attempt"] = attempt
                    return payload
                except GenerationError as exc:
                    last_error = exc
                    if not exc.retryable or attempt >= policy.max_attempts:
                        raise
                    delay = exc.retry_after
                    if delay is None:
                        delay = min(
                            policy.max_delay_seconds,
                            policy.base_delay_seconds * (2 ** (attempt - 1)),
                        )
                        delay += random.uniform(0, min(0.25, delay * 0.1))
                    await asyncio.sleep(delay)
                except Exception as exc:  # noqa: BLE001 - normalize adapter bugs/contracts
                    raise GenerationError(
                        f"Provider adapter raised {type(exc).__name__}: {exc}",
                        code="adapter_exception",
                        category="adapter",
                    ) from exc
            raise last_error or GenerationError("Provider failed without an error")
        finally:
            limiter.release()
