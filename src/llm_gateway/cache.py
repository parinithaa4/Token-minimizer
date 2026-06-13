"""Response cache with a Redis backend and an in-memory fallback.

The cache key is a stable hash of the *semantically relevant* request fields
(model + messages + sampling params). Identical requests hit the cache, are
billed $0, and are flagged in the response so callers can see the saving.

If a ``redis_url`` is configured and ``redis`` is importable the cache uses
Redis (with TTL); otherwise it falls back to a process-local dict with manual
TTL expiry. Tests run on the in-memory path — no Redis required.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Protocol


def make_cache_key(model: str, messages: list[dict], params: dict) -> str:
    """Deterministic cache key from the request's billable inputs.

    ``params`` should contain only sampling-affecting fields (temperature,
    top_p, max_tokens, stop, n). Order-independent via ``sort_keys``.
    """
    payload = {
        "model": model,
        "messages": messages,
        "params": {k: params[k] for k in sorted(params) if params[k] is not None},
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return f"llmgw:cache:{digest}"


class CacheBackend(Protocol):
    def get(self, key: str) -> dict | None: ...
    def set(self, key: str, value: dict, ttl: int) -> None: ...
    def clear(self) -> None: ...


class InMemoryCache:
    """Process-local cache with lazy TTL expiry. Used when Redis is absent."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[float, dict]] = {}

    def get(self, key: str) -> dict | None:
        item = self._data.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at and expires_at < time.time():
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: dict, ttl: int) -> None:
        expires_at = time.time() + ttl if ttl > 0 else 0.0
        self._data[key] = (expires_at, value)

    def clear(self) -> None:
        self._data.clear()


class RedisCache:  # pragma: no cover - exercised only with a live Redis
    """Redis-backed cache. Values are JSON-encoded."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, key: str) -> dict | None:
        raw = self._client.get(key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None

    def set(self, key: str, value: dict, ttl: int) -> None:
        blob = json.dumps(value, ensure_ascii=False)
        if ttl > 0:
            self._client.setex(key, ttl, blob)
        else:
            self._client.set(key, blob)

    def clear(self) -> None:
        # Scoped flush of our namespace only.
        for k in self._client.scan_iter(match="llmgw:cache:*"):
            self._client.delete(k)


def build_cache(redis_url: str | None) -> CacheBackend:
    """Return a Redis cache if reachable, else an in-memory cache.

    Never raises on Redis being unavailable — it transparently degrades so the
    gateway (and the test suite) keep working without Redis.
    """
    if redis_url:
        try:  # pragma: no cover - depends on a live Redis
            import redis

            client = redis.Redis.from_url(redis_url)
            client.ping()
            return RedisCache(client)
        except Exception:
            # Fall through to in-memory on any connection/import failure.
            pass
    return InMemoryCache()
