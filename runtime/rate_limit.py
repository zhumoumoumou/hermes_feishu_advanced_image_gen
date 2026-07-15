"""Per-process asynchronous QPS, TPM, concurrency, and retry policies."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LimitPolicy:
    qps: float = 1.0
    tpm: int = 60000
    max_concurrency: int = 1
    max_wait_seconds: float = 30.0
    max_attempts: int = 2
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 8.0

    @classmethod
    def from_mappings(cls, provider: dict[str, Any], model: dict[str, Any]) -> "LimitPolicy":
        merged = dict(provider or {})
        merged.update(model or {})
        retry = dict((provider or {}).get("retry") or {})
        retry.update((model or {}).get("retry") or {})
        return cls(
            qps=max(0.01, float(merged.get("qps", 1))),
            tpm=max(1, int(merged.get("tpm", 60000))),
            max_concurrency=max(1, int(merged.get("max_concurrency", 1))),
            max_wait_seconds=max(0.1, float(merged.get("max_wait_seconds", 30))),
            max_attempts=max(1, min(6, int(retry.get("max_attempts", 2)))),
            base_delay_seconds=max(0.0, float(retry.get("base_delay_seconds", 1))),
            max_delay_seconds=max(0.1, float(retry.get("max_delay_seconds", 8))),
        )


def estimate_prompt_tokens(prompt: str) -> int:
    """Conservative provider-neutral estimate used only for local TPM admission."""
    return max(1, math.ceil(len(prompt.encode("utf-8")) / 4))


class AsyncRateLimiter:
    """Token buckets for request and text-token admission plus a semaphore."""

    def __init__(self, policy: LimitPolicy):
        self.policy = policy
        self._semaphore = asyncio.Semaphore(policy.max_concurrency)
        self._lock = asyncio.Lock()
        self._request_capacity = max(1.0, policy.qps)
        self._request_tokens = self._request_capacity
        self._text_capacity = float(policy.tpm)
        self._text_tokens = self._text_capacity
        self._last_refill: float | None = None

    def _refill(self, now: float) -> None:
        if self._last_refill is None:
            self._last_refill = now
            return
        elapsed = max(0.0, now - self._last_refill)
        self._last_refill = now
        self._request_tokens = min(
            self._request_capacity,
            self._request_tokens + elapsed * self.policy.qps,
        )
        self._text_tokens = min(
            self._text_capacity,
            self._text_tokens + elapsed * (self.policy.tpm / 60.0),
        )

    async def acquire(self, prompt_tokens: int) -> None:
        if prompt_tokens > self.policy.tpm:
            raise TimeoutError(
                f"Estimated prompt tokens ({prompt_tokens}) exceed the model TPM limit ({self.policy.tpm})."
            )
        await self._semaphore.acquire()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.policy.max_wait_seconds
        try:
            while True:
                async with self._lock:
                    now = loop.time()
                    self._refill(now)
                    request_wait = max(0.0, (1.0 - self._request_tokens) / self.policy.qps)
                    text_rate = self.policy.tpm / 60.0
                    text_wait = max(0.0, (prompt_tokens - self._text_tokens) / text_rate)
                    wait_for = max(request_wait, text_wait)
                    if wait_for <= 0:
                        self._request_tokens -= 1.0
                        self._text_tokens -= prompt_tokens
                        return
                if loop.time() + wait_for > deadline:
                    raise TimeoutError("Local QPS/TPM admission exceeded max_wait_seconds")
                await asyncio.sleep(max(0.001, wait_for))
        except BaseException:
            self._semaphore.release()
            raise

    def release(self) -> None:
        self._semaphore.release()
