"""Configuration loading: ``config.yaml`` and/or environment variables.

The config has three sections:

* ``providers`` — adapter instances and their upstream credentials/base URLs.
* ``routing``   — maps a client-facing ``model`` name to a provider and the
  upstream model name, with an optional ``fallback`` model.
* ``keys``      — seed virtual API keys (vkeys) with allowed models and budgets.

Everything has sane defaults so the app boots with **zero** config using only
the built-in ``mock`` provider — which is exactly what the test suite relies on.
Environment variables (e.g. ``OPENAI_API_KEY``) fill in upstream secrets so
they need not be committed to ``config.yaml``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - yaml is a hard dep, but be defensive
    yaml = None


@dataclass
class ProviderConfig:
    name: str
    type: str  # "mock" | "openai" | "anthropic" | "ollama"
    base_url: str | None = None
    api_key: str | None = None
    api_key_env: str | None = None
    timeout: float = 60.0

    def resolved_key(self) -> str | None:
        if self.api_key:
            return self.api_key
        if self.api_key_env:
            return os.environ.get(self.api_key_env)
        return None


@dataclass
class RouteConfig:
    model: str  # client-facing name
    provider: str  # provider.name
    upstream_model: str  # name to send upstream
    fallback: str | None = None  # client-facing model to retry with


@dataclass
class KeyConfig:
    key: str
    name: str = "default"
    allowed_models: list[str] = field(default_factory=list)  # empty => all routed
    max_usd: float | None = None
    max_tokens: int | None = None
    cache_enabled: bool = True


@dataclass
class GatewayConfig:
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    routes: dict[str, RouteConfig] = field(default_factory=dict)
    keys: list[KeyConfig] = field(default_factory=list)
    redis_url: str | None = None
    database_url: str = "sqlite:///./gateway.db"
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600

    def route_for(self, model: str) -> RouteConfig | None:
        return self.routes.get(model)


def default_config() -> GatewayConfig:
    """Zero-dependency default: a single ``mock`` provider and two routes.

    This is what tests and the first-run experience use — no real keys, no
    network, no config file required.
    """
    providers = {
        "mock": ProviderConfig(name="mock", type="mock"),
    }
    routes = {
        "mock-echo": RouteConfig(
            model="mock-echo", provider="mock", upstream_model="mock-echo"
        ),
        "mock-cheap": RouteConfig(
            model="mock-cheap", provider="mock", upstream_model="mock-cheap"
        ),
    }
    keys = [
        KeyConfig(
            key="sk-gw-dev",
            name="dev",
            allowed_models=[],  # all routed models
            max_usd=10.0,
            max_tokens=None,
        ),
    ]
    return GatewayConfig(
        providers=providers,
        routes=routes,
        keys=keys,
        redis_url=os.environ.get("REDIS_URL"),
    )


def _parse_providers(raw: dict) -> dict[str, ProviderConfig]:
    out: dict[str, ProviderConfig] = {}
    for name, spec in (raw or {}).items():
        spec = spec or {}
        out[name] = ProviderConfig(
            name=name,
            type=spec.get("type", name),
            base_url=spec.get("base_url"),
            api_key=spec.get("api_key"),
            api_key_env=spec.get("api_key_env"),
            timeout=float(spec.get("timeout", 60.0)),
        )
    return out


def _parse_routes(raw: Any) -> dict[str, RouteConfig]:
    out: dict[str, RouteConfig] = {}
    # Accept either a mapping {model: {...}} or a list [{model: ...}, ...].
    items: list[tuple[str, dict]] = []
    if isinstance(raw, dict):
        items = list(raw.items())
    elif isinstance(raw, list):
        for entry in raw:
            entry = entry or {}
            items.append((entry["model"], entry))
    for model, spec in items:
        spec = spec or {}
        out[model] = RouteConfig(
            model=model,
            provider=spec["provider"],
            upstream_model=spec.get("upstream_model", model),
            fallback=spec.get("fallback"),
        )
    return out


def _parse_keys(raw: Any) -> list[KeyConfig]:
    out: list[KeyConfig] = []
    for spec in raw or []:
        spec = spec or {}
        out.append(
            KeyConfig(
                key=spec["key"],
                name=spec.get("name", "default"),
                allowed_models=list(spec.get("allowed_models", []) or []),
                max_usd=spec.get("max_usd"),
                max_tokens=spec.get("max_tokens"),
                cache_enabled=bool(spec.get("cache_enabled", True)),
            )
        )
    return out


def load_config(path: str | None = None) -> GatewayConfig:
    """Load config from ``path`` (or ``$GATEWAY_CONFIG``), else the default.

    Missing file → :func:`default_config`. This keeps the mock-only path
    frictionless for tests and local first-run.
    """
    path = path or os.environ.get("GATEWAY_CONFIG")
    if not path:
        return default_config()
    p = Path(path)
    if not p.exists():
        return default_config()
    if yaml is None:  # pragma: no cover
        raise RuntimeError("PyYAML is required to load a config file")

    raw = yaml.safe_load(p.read_text()) or {}

    providers = _parse_providers(raw.get("providers", {}))
    # Always guarantee a mock provider exists so the mock routes never break.
    if "mock" not in providers:
        providers["mock"] = ProviderConfig(name="mock", type="mock")

    routes = _parse_routes(raw.get("routing", raw.get("routes", {})))
    # Ensure the built-in mock routes are always available for smoke/health.
    for m in ("mock-echo", "mock-cheap"):
        routes.setdefault(
            m, RouteConfig(model=m, provider="mock", upstream_model=m)
        )

    keys = _parse_keys(raw.get("keys", []))

    cache = raw.get("cache", {}) or {}
    return GatewayConfig(
        providers=providers,
        routes=routes,
        keys=keys,
        redis_url=raw.get("redis_url") or os.environ.get("REDIS_URL"),
        database_url=raw.get("database_url", "sqlite:///./gateway.db"),
        cache_enabled=bool(cache.get("enabled", True)),
        cache_ttl_seconds=int(cache.get("ttl_seconds", 3600)),
    )
