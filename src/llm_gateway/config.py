"""Configuration loading: ``config.yaml`` and/or environment variables.

Configuration sections:

* ``providers`` — adapter instances and their upstream credentials/base URLs.
* ``routing``   — maps a client-facing model name to a provider/upstream model.
* ``keys``      — seed virtual API keys with allowed models and budgets.
* ``cache``     — L1 exact-response cache settings.
* ``semantic_cache`` — optional FAISS/MiniLM L2 semantic cache.
* ``complexity_routing`` — optional deterministic model-tier routing.

Everything has sane defaults so the application can still boot with zero
configuration using the built-in ``mock`` provider.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - yaml is a hard dependency
    yaml = None


# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------


@dataclass
class ProviderConfig:
    name: str
    type: str  # "mock" | "openai" | "anthropic" | "ollama"
    base_url: str | None = None
    api_key: str | None = None
    api_key_env: str | None = None
    timeout: float = 60.0

    def resolved_key(self) -> str | None:
        """Resolve the provider API key.

        A literal api_key takes precedence over an environment variable.
        """
        if self.api_key:
            return self.api_key

        if self.api_key_env:
            return os.environ.get(self.api_key_env)

        return None


# ---------------------------------------------------------------------------
# Routing configuration
# ---------------------------------------------------------------------------


@dataclass
class RouteConfig:
    model: str
    provider: str
    upstream_model: str
    fallback: str | None = None


# ---------------------------------------------------------------------------
# Virtual API key configuration
# ---------------------------------------------------------------------------


@dataclass
class KeyConfig:
    key: str
    name: str = "default"
    allowed_models: list[str] = field(default_factory=list)
    max_usd: float | None = None
    max_tokens: int | None = None
    cache_enabled: bool = True


# ---------------------------------------------------------------------------
# Gateway configuration
# ---------------------------------------------------------------------------


@dataclass
class GatewayConfig:
    providers: dict[str, ProviderConfig] = field(
        default_factory=dict
    )

    routes: dict[str, RouteConfig] = field(
        default_factory=dict
    )

    keys: list[KeyConfig] = field(
        default_factory=list
    )

    # Existing gateway settings
    redis_url: str | None = None
    database_url: str = "sqlite:///./gateway.db"

    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600

    # Optional shared secret for /admin/*
    admin_token: str | None = None

    # ------------------------------------------------------------------
    # TokenMinGate: semantic L2 cache
    # ------------------------------------------------------------------

    semantic_cache_enabled: bool = False

    semantic_cache_threshold: float = 0.84

    semantic_cache_ttl_seconds: int = 7 * 24 * 60 * 60

    semantic_cache_model: str = (
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    semantic_cache_k: int = 8

    # ------------------------------------------------------------------
    # TokenMinGate: complexity routing
    # ------------------------------------------------------------------

    complexity_routing_enabled: bool = False

    # The client can explicitly request this model to enable automatic
    # Economy/Balanced/Frontier routing.
    complexity_auto_model: str = "tokenguard-auto"

    # Maps complexity tier -> client-facing gateway model.
    #
    # Example:
    #
    # economy  -> mock-cheap
    # balanced -> mock-echo
    # frontier -> mock-echo
    #
    complexity_tier_models: dict[str, str] = field(
        default_factory=dict
    )

    # Used by namespace.py when a vkey does not expose a team_id.
    default_team_id: str = "default"

    def route_for(
        self,
        model: str,
    ) -> RouteConfig | None:
        return self.routes.get(model)


# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------


def default_config() -> GatewayConfig:
    """Return a zero-config development configuration.

    The default path uses only the built-in mock provider. This keeps the
    existing test suite and local smoke tests independent of external APIs.
    """

    providers = {
        "mock": ProviderConfig(
            name="mock",
            type="mock",
        ),
    }

    routes = {
        "mock-echo": RouteConfig(
            model="mock-echo",
            provider="mock",
            upstream_model="mock-echo",
        ),
        "mock-cheap": RouteConfig(
            model="mock-cheap",
            provider="mock",
            upstream_model="mock-cheap",
        ),
    }

    keys = [
        KeyConfig(
            key="sk-gw-dev",
            name="dev",
            allowed_models=[],
            max_usd=10.0,
            max_tokens=None,
        ),
    ]

    return GatewayConfig(
        providers=providers,
        routes=routes,
        keys=keys,
        redis_url=os.environ.get("REDIS_URL"),
        admin_token=os.environ.get(
            "GATEWAY_ADMIN_TOKEN"
        ),
        semantic_cache_enabled=False,
        complexity_routing_enabled=False,
    )


# ---------------------------------------------------------------------------
# YAML parsers
# ---------------------------------------------------------------------------


def _parse_providers(
    raw: dict,
) -> dict[str, ProviderConfig]:
    out: dict[str, ProviderConfig] = {}

    for name, spec in (raw or {}).items():
        spec = spec or {}

        out[name] = ProviderConfig(
            name=name,
            type=spec.get("type", name),
            base_url=spec.get("base_url"),
            api_key=spec.get("api_key"),
            api_key_env=spec.get("api_key_env"),
            timeout=float(
                spec.get("timeout", 60.0)
            ),
        )

    return out


def _parse_routes(
    raw: Any,
) -> dict[str, RouteConfig]:
    out: dict[str, RouteConfig] = {}

    # Mapping:
    #
    # routing:
    #   my-model:
    #     provider: openai
    #
    # or list:
    #
    # routing:
    #   - model: my-model
    #     provider: openai

    items: list[tuple[str, dict]] = []

    if isinstance(raw, dict):
        items = list(raw.items())

    elif isinstance(raw, list):
        for entry in raw:
            entry = entry or {}

            if "model" not in entry:
                raise ValueError(
                    "routing list entry is missing 'model'"
                )

            items.append(
                (
                    entry["model"],
                    entry,
                )
            )

    for model, spec in items:
        spec = spec or {}

        if "provider" not in spec:
            raise ValueError(
                f"routing model {model!r} is missing 'provider'"
            )

        out[model] = RouteConfig(
            model=model,
            provider=spec["provider"],
            upstream_model=spec.get(
                "upstream_model",
                model,
            ),
            fallback=spec.get("fallback"),
        )

    return out


def _parse_keys(
    raw: Any,
) -> list[KeyConfig]:
    out: list[KeyConfig] = []

    for spec in raw or []:
        spec = spec or {}

        if "key" not in spec:
            raise ValueError(
                "key configuration is missing 'key'"
            )

        max_usd = spec.get("max_usd")
        max_tokens = spec.get("max_tokens")

        out.append(
            KeyConfig(
                key=spec["key"],
                name=spec.get(
                    "name",
                    "default",
                ),
                allowed_models=list(
                    spec.get(
                        "allowed_models",
                        [],
                    )
                    or []
                ),
                max_usd=(
                    float(max_usd)
                    if max_usd is not None
                    else None
                ),
                max_tokens=(
                    int(max_tokens)
                    if max_tokens is not None
                    else None
                ),
                cache_enabled=bool(
                    spec.get(
                        "cache_enabled",
                        True,
                    )
                ),
            )
        )

    return out


# ---------------------------------------------------------------------------
# Main configuration loader
# ---------------------------------------------------------------------------


def load_config(
    path: str | None = None,
) -> GatewayConfig:
    """Load configuration from YAML.

    Resolution order:

    1. Explicit ``path`` argument.
    2. ``GATEWAY_CONFIG`` environment variable.
    3. Built-in zero-config defaults.

    A missing configuration file falls back to the built-in mock setup.
    """

    path = path or os.environ.get(
        "GATEWAY_CONFIG"
    )

    if not path:
        return default_config()

    config_path = Path(path)

    if not config_path.exists():
        return default_config()

    if yaml is None:  # pragma: no cover
        raise RuntimeError(
            "PyYAML is required to load a config file"
        )

    raw = yaml.safe_load(
        config_path.read_text()
    ) or {}

    # ------------------------------------------------------------------
    # Providers
    # ------------------------------------------------------------------

    providers = _parse_providers(
        raw.get(
            "providers",
            {},
        )
    )

    # Always keep the built-in mock provider.
    if "mock" not in providers:
        providers["mock"] = ProviderConfig(
            name="mock",
            type="mock",
        )

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    routes = _parse_routes(
        raw.get(
            "routing",
            raw.get(
                "routes",
                {},
            ),
        )
    )

    # Preserve the existing smoke-test models.
    for model in (
        "mock-echo",
        "mock-cheap",
    ):
        routes.setdefault(
            model,
            RouteConfig(
                model=model,
                provider="mock",
                upstream_model=model,
            ),
        )

    # ------------------------------------------------------------------
    # Virtual keys
    # ------------------------------------------------------------------

    keys = _parse_keys(
        raw.get(
            "keys",
            [],
        )
    )

    # ------------------------------------------------------------------
    # Existing L1 cache
    # ------------------------------------------------------------------

    cache = raw.get(
        "cache",
        {},
    ) or {}

    # ------------------------------------------------------------------
    # New TokenMinGate semantic cache
    # ------------------------------------------------------------------

    semantic_cache = raw.get(
        "semantic_cache",
        {},
    ) or {}

    semantic_enabled = bool(
        semantic_cache.get(
            "enabled",
            False,
        )
    )

    semantic_threshold = float(
        semantic_cache.get(
            "threshold",
            0.84,
        )
    )

    if not 0.0 <= semantic_threshold < 1.0:
        raise ValueError(
            "semantic_cache.threshold must be >= 0 and < 1"
        )

    semantic_ttl = int(
        semantic_cache.get(
            "ttl_seconds",
            7 * 24 * 60 * 60,
        )
    )

    if semantic_ttl <= 0:
        raise ValueError(
            "semantic_cache.ttl_seconds must be > 0"
        )

    semantic_k = int(
        semantic_cache.get(
            "k",
            8,
        )
    )

    if semantic_k <= 0:
        raise ValueError(
            "semantic_cache.k must be > 0"
        )

    semantic_model = str(
        semantic_cache.get(
            "model",
            "sentence-transformers/all-MiniLM-L6-v2",
        )
    )

    # ------------------------------------------------------------------
    # New TokenMinGate complexity router
    # ------------------------------------------------------------------

    complexity = raw.get(
        "complexity_routing",
        {},
    ) or {}

    complexity_enabled = bool(
        complexity.get(
            "enabled",
            False,
        )
    )

    complexity_auto_model = str(
        complexity.get(
            "auto_model",
            "tokenguard-auto",
        )
    )

    tier_models_raw = (
        complexity.get(
            "tier_models",
            {},
        )
        or {}
    )

    if not isinstance(
        tier_models_raw,
        dict,
    ):
        raise ValueError(
            "complexity_routing.tier_models must be a mapping"
        )

    tier_models = {
        str(tier): str(model)
        for tier, model in tier_models_raw.items()
    }

    # ------------------------------------------------------------------
    # Final configuration
    # ------------------------------------------------------------------

    return GatewayConfig(
        providers=providers,
        routes=routes,
        keys=keys,

        redis_url=(
            raw.get("redis_url")
            or os.environ.get("REDIS_URL")
        ),

        database_url=raw.get(
            "database_url",
            "sqlite:///./gateway.db",
        ),

        cache_enabled=bool(
            cache.get(
                "enabled",
                True,
            )
        ),

        cache_ttl_seconds=int(
            cache.get(
                "ttl_seconds",
                3600,
            )
        ),

        admin_token=(
            raw.get("admin_token")
            or os.environ.get(
                "GATEWAY_ADMIN_TOKEN"
            )
        ),

        # TokenMinGate semantic cache
        semantic_cache_enabled=semantic_enabled,
        semantic_cache_threshold=semantic_threshold,
        semantic_cache_ttl_seconds=semantic_ttl,
        semantic_cache_model=semantic_model,
        semantic_cache_k=semantic_k,

        # TokenMinGate complexity routing
        complexity_routing_enabled=complexity_enabled,
        complexity_auto_model=complexity_auto_model,
        complexity_tier_models=tier_models,

        default_team_id=str(
            raw.get(
                "default_team_id",
                "default",
            )
        ),
    )