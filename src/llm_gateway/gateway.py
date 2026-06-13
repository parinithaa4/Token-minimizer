"""The Gateway service: orchestrates routing, budgets, cache, cost and JTF.

This is the heart of the system and is deliberately framework-agnostic — it
takes plain dicts and returns a :class:`GatewayResult`, so it can be driven by
FastAPI (see ``app.py``), a CLI, or a test harness without HTTP. Auth is
handled by the caller (the app layer) which resolves the vkey; everything that
*affects billing* lives here.

Request lifecycle:

1. Resolve the route (``model`` → provider + upstream model + fallback).
2. Authorize the model against the vkey's allow-list.
3. JTF: always analyze potential savings; optionally compress if opted in.
4. Cache lookup — a hit short-circuits, is billed $0, and is flagged.
5. Pre-flight budget check using an estimated cost; reject with 402 if over.
6. Call the provider (with fallback on provider error).
7. Compute real cost from the provider's ``usage``, record it atomically,
   cache the response, and return it with rich gateway metadata.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .cache import CacheBackend, make_cache_key
from .config import GatewayConfig
from .jtf_ops import analyze_messages, compress_messages
from .pricing import PricingTable
from .providers import Provider, ProviderError, build_provider
from .store import Store, VirtualKey
from .tokens import count_prompt_tokens

log = logging.getLogger("llm_gateway")

# Sampling-affecting params that participate in the cache key and are forwarded.
_PARAM_FIELDS = ("temperature", "top_p", "max_tokens", "n", "stop")


class GatewayError(Exception):
    """A request-level failure with an HTTP status and OpenAI error type."""

    def __init__(self, status_code: int, message: str, err_type: str, code: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.err_type = err_type
        self.code = code


@dataclass
class GatewayResult:
    response: dict[str, Any]
    cache_hit: bool
    cost_usd: float
    prompt_tokens: int
    completion_tokens: int
    provider: str
    model: str
    jtf: dict = field(default_factory=dict)
    jtf_compressed: bool = False


class Gateway:
    def __init__(
        self,
        config: GatewayConfig,
        store: Store,
        cache: CacheBackend,
        pricing: PricingTable | None = None,
    ):
        self.config = config
        self.store = store
        self.cache = cache
        self.pricing = pricing or PricingTable()
        self._providers: dict[str, Provider] = {
            name: build_provider(cfg) for name, cfg in config.providers.items()
        }

    # ----- helpers ----------------------------------------------------------

    def provider_for(self, name: str) -> Provider:
        prov = self._providers.get(name)
        if prov is None:
            raise GatewayError(
                500, f"provider {name!r} is not configured", "configuration_error"
            )
        return prov

    def available_models(self) -> list[str]:
        return list(self.config.routes.keys())

    @staticmethod
    def _extract_params(payload: dict) -> dict:
        return {f: payload.get(f) for f in _PARAM_FIELDS}

    # ----- main entrypoint --------------------------------------------------

    async def chat_completion(
        self,
        *,
        vkey: VirtualKey,
        payload: dict,
        cache_enabled: bool = True,
        jtf_compress: bool = False,
    ) -> GatewayResult:
        model = payload.get("model")
        if not model:
            raise GatewayError(400, "'model' is required", "invalid_request_error")

        messages = [dict(m) for m in payload.get("messages", [])]
        if not messages:
            raise GatewayError(
                400, "'messages' must be a non-empty list", "invalid_request_error"
            )

        route = self.config.route_for(model)
        if route is None:
            raise GatewayError(
                404,
                f"model {model!r} is not available on this gateway",
                "model_not_found",
                code="model_not_found",
            )

        # Authorization: model allow-list on the vkey ([] => all routed models).
        if vkey.allowed_models and model not in vkey.allowed_models:
            raise GatewayError(
                403,
                f"key {vkey.name!r} is not permitted to use model {model!r}",
                "permission_error",
            )

        params = self._extract_params(payload)

        # --- JTF: always analyze (non-destructive); optionally compress. ---
        jtf_analysis = analyze_messages(messages)
        forwarded_messages = messages
        jtf_compressed = False
        realized_saved = 0
        if jtf_compress:
            forwarded_messages, realized = compress_messages(messages)
            if realized.json_blocks > 0:
                jtf_compressed = True
                realized_saved = realized.saved_tokens

        jtf_meta = jtf_analysis.as_dict()
        jtf_meta["compressed"] = jtf_compressed
        jtf_meta["realized_tokens_saved"] = realized_saved

        # --- Cache lookup (on the *forwarded* request so compression counts). ---
        key_enabled = cache_enabled and vkey.cache_enabled and self.config.cache_enabled
        cache_key = make_cache_key(route.upstream_model, forwarded_messages, params)
        if key_enabled:
            cached = self.cache.get(cache_key)
            if cached is not None:
                # Billed $0; recorded as a request + cache hit for hit-rate.
                self.store.record_usage(
                    vkey.key,
                    prompt_tokens=0,
                    completion_tokens=0,
                    cost_usd=0.0,
                    cache_hit=True,
                    jtf_saved=jtf_analysis.saved_tokens,
                )
                self.store.log_request(
                    key=vkey.key,
                    model=model,
                    provider=route.provider,
                    prompt_tokens=0,
                    completion_tokens=0,
                    cost_usd=0.0,
                    cache_hit=True,
                    jtf_saved=jtf_analysis.saved_tokens,
                    status=200,
                )
                return GatewayResult(
                    response=cached,
                    cache_hit=True,
                    cost_usd=0.0,
                    prompt_tokens=cached.get("usage", {}).get("prompt_tokens", 0),
                    completion_tokens=cached.get("usage", {}).get("completion_tokens", 0),
                    provider=route.provider,
                    model=model,
                    jtf=jtf_meta,
                    jtf_compressed=jtf_compressed,
                )

        # --- Pre-flight budget check (estimate before spending). ---
        est_prompt = count_prompt_tokens(forwarded_messages)
        est_completion = int(params.get("max_tokens") or 256)
        est_cost = self.pricing.cost_usd(
            route.upstream_model, est_prompt, est_completion
        )
        reason = self.store.would_exceed_budget(
            vkey.key, vkey, est_cost, est_prompt + est_completion
        )
        if reason is not None:
            self.store.log_request(
                key=vkey.key,
                model=model,
                provider=route.provider,
                prompt_tokens=0,
                completion_tokens=0,
                cost_usd=0.0,
                cache_hit=False,
                jtf_saved=0,
                status=402,
            )
            raise GatewayError(402, reason, "insufficient_quota", code="budget_exceeded")

        # --- Provider call (with optional single fallback). ---
        result, used_route = await self._call_with_fallback(
            route, forwarded_messages, params
        )

        cost = self.pricing.cost_usd(
            used_route.upstream_model, result.prompt_tokens, result.completion_tokens
        )

        # --- Atomic usage recording. ---
        self.store.record_usage(
            vkey.key,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cost_usd=cost,
            cache_hit=False,
            jtf_saved=jtf_analysis.saved_tokens,
        )
        self.store.log_request(
            key=vkey.key,
            model=model,
            provider=used_route.provider,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            cost_usd=cost,
            cache_hit=False,
            jtf_saved=jtf_analysis.saved_tokens,
            status=200,
        )

        # --- Cache store. ---
        if key_enabled:
            self.cache.set(cache_key, result.response, self.config.cache_ttl_seconds)

        return GatewayResult(
            response=result.response,
            cache_hit=False,
            cost_usd=cost,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            provider=used_route.provider,
            model=model,
            jtf=jtf_meta,
            jtf_compressed=jtf_compressed,
        )

    async def _call_with_fallback(self, route, messages, params):
        """Call the route's provider; on ProviderError, try the fallback once."""
        try:
            provider = self.provider_for(route.provider)
            result = await provider.chat(
                upstream_model=route.upstream_model,
                messages=messages,
                params=params,
            )
            return result, route
        except ProviderError as exc:
            if route.fallback:
                fb = self.config.route_for(route.fallback)
                if fb is not None:
                    log.warning(
                        "provider %s failed (%s); falling back to %s",
                        route.provider,
                        exc,
                        fb.provider,
                    )
                    provider = self.provider_for(fb.provider)
                    result = await provider.chat(
                        upstream_model=fb.upstream_model,
                        messages=messages,
                        params=params,
                    )
                    return result, fb
            raise GatewayError(
                exc.status_code,
                exc.message,
                "upstream_error",
            ) from exc
