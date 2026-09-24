"""The Gateway service: orchestrates routing, budgets, cache, cost and JTF.

Implements the multi-layer TokenMinGate pipeline:
1. Namespace isolation: N = SHA256(team_id || system_prompt || provider_family || temp_bucket)
2. L1 Exact-match cache: zero tokens, $0.00 cost, <1ms latency
3. L2 Semantic cache: FAISS-backed, age-aware similarity bar tau_eff(ai) = tau + (1-tau)*min(1, ai/Tk)
4. Syntax-safe prompt pruning: removes redundant conversational fluff without breaking code/JSON
5. Complexity router: scores difficulty S(u) across length, instructions, reasoning, and code signals
6. Model tiers: Economy (<0.35), Balanced (0.35-0.75), Frontier (>=0.75) with safety margin rule
7. Provider dispatch: OpenAI, Anthropic, Mock
8. Honest token and cost ledger per user/team/app with human feedback loop (TRR and TRRnet)
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from .cache import CacheBackend, make_cache_key
from .complexity_router import ComplexityRouter
from .config import GatewayConfig
from .jtf_ops import analyze_messages, compress_messages
from .namespace import l1_key, namespace_for_request, normalize_prompt
from .pricing import PricingTable
from .prompt_pruner import SyntaxSafePruner, syntax_safe_prune
from .providers import Provider, ProviderError, StreamChunk, build_provider
from .semantic_cache import SemanticCache
from .store import Store, VirtualKey
from .supadb import RequestLogEntry, SupaDB
from .tokens import count_prompt_tokens

log = logging.getLogger("llm_gateway")

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
    # TokenMinGate Diagnostics
    tier: str = "balanced"
    cache_tier: str | None = None
    namespace: str = ""
    baseline_cost_usd: float = 0.0
    tokens_saved: int = 0
    pruned_prompt: str = ""
    pruned_tokens: int = 0
    complexity_score: float = 0.0
    complexity_signals: dict = field(default_factory=dict)
    similarity: float | None = None
    effective_threshold: float | None = None
    latency_ms: float = 0.0
    log_id: int = 0


class Gateway:
    def __init__(
        self,
        config: GatewayConfig,
        store: Store,
        cache: CacheBackend,
        pricing: PricingTable | None = None,
        semantic_cache: SemanticCache | None = None,
        complexity_router: ComplexityRouter | None = None,
        pruner: SyntaxSafePruner | None = None,
        supadb: SupaDB | None = None,
    ):
        self.config = config
        self.store = store
        self.cache = cache
        self.pricing = pricing or PricingTable()
        self.semantic_cache = semantic_cache or SemanticCache(base_threshold=0.84)
        self.complexity_router = complexity_router or ComplexityRouter()
        self.pruner = pruner or SyntaxSafePruner()
        self.supadb = supadb or SupaDB()

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
        routes = list(self.config.routes.keys())
        if "tokenmingate" not in routes:
            routes.insert(0, "tokenmingate")
        return routes

    @staticmethod
    def _extract_params(payload: dict) -> dict:
        return {f: payload.get(f) for f in _PARAM_FIELDS}

    def _resolve_auto_model(self, tier: str) -> str:
        """Map complexity tier to available model."""
        routes = self.config.routes
        if tier == "economy":
            for m in ["mock-cheap", "gpt-4o-mini", "claude-3-5-haiku"]:
                if m in routes:
                    return m
        elif tier == "balanced":
            for m in ["mock-echo", "gpt-4o", "claude-3-5-sonnet"]:
                if m in routes:
                    return m
        else:  # frontier
            for m in ["mock-echo", "o1", "claude-3-opus", "gpt-4o"]:
                if m in routes:
                    return m
        # Fallback to first configured route
        return next(iter(routes.keys()), "mock-echo")

    # ----- main entrypoint (TokenMinGate Algorithm 1) -----------------------

    async def chat_completion(
        self,
        *,
        vkey: VirtualKey,
        payload: dict,
        cache_enabled: bool = True,
        jtf_compress: bool = False,
    ) -> GatewayResult:
        t0 = time.perf_counter()
        raw_model = payload.get("model")
        if not raw_model:
            raise GatewayError(400, "'model' is required", "invalid_request_error")

        messages = [dict(m) for m in payload.get("messages", [])]
        if not messages:
            raise GatewayError(
                400, "'messages' must be a non-empty list", "invalid_request_error"
            )

        params = self._extract_params(payload)

        # Extract system & user prompt components for TokenMinGate
        system_prompt = next(
            (str(m.get("content", "")) for m in messages if m.get("role") == "system"),
            "",
        )
        user_prompts = [
            str(m.get("content", "")) for m in messages if m.get("role") == "user"
        ]
        raw_user_prompt = " ".join(user_prompts) if user_prompts else ""
        norm_user_prompt = normalize_prompt(raw_user_prompt)

        # Metadata & Tenant parameters
        team_id = str(payload.get("team_id") or getattr(vkey, "team_id", None) or "default")
        user_id = str(payload.get("user_id") or getattr(vkey, "user_id", None) or vkey.name)
        app_id = str(payload.get("app_id") or "web")
        temperature = float(params.get("temperature") or 0.0)

        # Provider family
        provider_family = "openai"
        if raw_model in self.config.routes:
            provider_family = self.config.routes[raw_model].provider

        # Step 1: Compute Namespace code N
        namespace_hash = namespace_for_request(
            team_id=team_id,
            system_prompt=system_prompt,
            provider_family=provider_family,
            temperature=temperature,
        )

        # JTF Analysis & Optional Compression
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

        # Dynamic Route Determination
        is_auto_route = raw_model in ("tokenmingate", "auto", "default")
        model = raw_model
        if is_auto_route:
            pre_score = self.complexity_router.score(raw_user_prompt)
            model = self._resolve_auto_model(pre_score.tier)

        route = self.config.route_for(model)
        if route is None:
            raise GatewayError(
                404,
                f"model {model!r} is not available on this gateway",
                "model_not_found",
                code="model_not_found",
            )

        # Authorization
        if vkey.allowed_models and model not in vkey.allowed_models:
            raise GatewayError(
                403,
                f"key {vkey.name!r} is not permitted to use model {model!r}",
                "permission_error",
            )

        key_enabled = cache_enabled and vkey.cache_enabled and self.config.cache_enabled
        cache_key = make_cache_key(route.upstream_model, forwarded_messages, params)

        # Effective prompt from forwarded messages
        forwarded_user_prompts = [
            str(m.get("content", "")) for m in forwarded_messages if m.get("role") == "user"
        ]
        effective_user_prompt = " ".join(forwarded_user_prompts) if forwarded_user_prompts else raw_user_prompt
        norm_user_prompt = normalize_prompt(effective_user_prompt)

        # Baseline cost projection (assuming full Frontier tier)
        est_prompt_tokens = count_prompt_tokens(messages)
        baseline_cost_usd = self.pricing.cost_usd("claude-3-opus", est_prompt_tokens, 256)
        if baseline_cost_usd <= 0:
            baseline_cost_usd = 0.0035

        # --------------------------------------------------------------------
        # Step 2: Check L1 Exact-Match Cache
        # --------------------------------------------------------------------
        if key_enabled:
            cached_l1 = self.cache.get(cache_key)
            if cached_l1 is not None:
                lat_ms = (time.perf_counter() - t0) * 1000
                cached_usage = cached_l1.get("usage", {})
                p_tok = cached_usage.get("prompt_tokens", est_prompt_tokens)
                c_tok = cached_usage.get("completion_tokens", 50)
                tot_tok = p_tok + c_tok

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
                log_id = self.supadb.log_request(
                    RequestLogEntry(
                        id=None,
                        ts=time.time(),
                        key=vkey.key,
                        user_id=user_id,
                        team_id=team_id,
                        app_id=app_id,
                        prompt=raw_user_prompt,
                        pruned_prompt=raw_user_prompt,
                        model=model,
                        provider=route.provider,
                        tier="l1",
                        prompt_tokens=p_tok,
                        pruned_tokens=0,
                        completion_tokens=c_tok,
                        total_tokens=tot_tok,
                        tokens_saved=tot_tok,
                        cost_usd=0.0,
                        baseline_cost_usd=baseline_cost_usd,
                        cache_hit=True,
                        cache_tier="l1",
                        similarity=1.0,
                        threshold=1.0,
                        latency_ms=round(lat_ms, 2),
                        is_wrong_answer=False,
                        status=200,
                    )
                )

                return GatewayResult(
                    response=cached_l1,
                    cache_hit=True,
                    cost_usd=0.0,
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    provider=route.provider,
                    model=model,
                    jtf=jtf_meta,
                    jtf_compressed=jtf_compressed,
                    tier="l1",
                    cache_tier="l1",
                    namespace=namespace_hash,
                    baseline_cost_usd=baseline_cost_usd,
                    tokens_saved=tot_tok,
                    similarity=1.0,
                    effective_threshold=1.0,
                    latency_ms=round(lat_ms, 2),
                    log_id=log_id,
                )

            # ----------------------------------------------------------------
            # Step 3: Check L2 Semantic Cache with elastic tau_eff(ai)
            # ----------------------------------------------------------------
            sem_lookup = self.semantic_cache.lookup(namespace_hash, norm_user_prompt)
            if sem_lookup is not None:
                lat_ms = (time.perf_counter() - t0) * 1000
                cached_resp = sem_lookup.entry.response
                cached_usage = cached_resp.get("usage", {})
                p_tok = cached_usage.get("prompt_tokens", est_prompt_tokens)
                c_tok = cached_usage.get("completion_tokens", 50)
                tot_tok = p_tok + c_tok

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
                log_id = self.supadb.log_request(
                    RequestLogEntry(
                        id=None,
                        ts=time.time(),
                        key=vkey.key,
                        user_id=user_id,
                        team_id=team_id,
                        app_id=app_id,
                        prompt=raw_user_prompt,
                        pruned_prompt=raw_user_prompt,
                        model=model,
                        provider=route.provider,
                        tier="l2",
                        prompt_tokens=p_tok,
                        pruned_tokens=0,
                        completion_tokens=c_tok,
                        total_tokens=tot_tok,
                        tokens_saved=tot_tok,
                        cost_usd=0.0,
                        baseline_cost_usd=baseline_cost_usd,
                        cache_hit=True,
                        cache_tier="l2",
                        similarity=round(sem_lookup.similarity, 4),
                        threshold=round(sem_lookup.effective_threshold, 4),
                        latency_ms=round(lat_ms, 2),
                        is_wrong_answer=False,
                        status=200,
                    )
                )

                return GatewayResult(
                    response=cached_resp,
                    cache_hit=True,
                    cost_usd=0.0,
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    provider=route.provider,
                    model=model,
                    jtf=jtf_meta,
                    jtf_compressed=jtf_compressed,
                    tier="l2",
                    cache_tier="l2",
                    namespace=namespace_hash,
                    baseline_cost_usd=baseline_cost_usd,
                    tokens_saved=tot_tok,
                    similarity=round(sem_lookup.similarity, 4),
                    effective_threshold=round(sem_lookup.effective_threshold, 4),
                    latency_ms=round(lat_ms, 2),
                    log_id=log_id,
                )

        # --------------------------------------------------------------------
        # Step 4: Syntax-Safe Prompt Pruning u' = SyntaxSafePrune(u)
        # --------------------------------------------------------------------
        prune_res = self.pruner.prune(raw_user_prompt)
        pruned_prompt = prune_res.pruned_text
        pruning_tokens_saved = prune_res.tokens_saved

        # --------------------------------------------------------------------
        # Step 5: Complexity Router S(u') and Tier Determination
        # --------------------------------------------------------------------
        comp_res = self.complexity_router.score(pruned_prompt)
        assigned_tier = comp_res.tier

        if is_auto_route:
            model = self._resolve_auto_model(assigned_tier)
            route = self.config.route_for(model)

        # --------------------------------------------------------------------
        # Step 6: Pre-flight Budget Check
        # --------------------------------------------------------------------
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
            self.supadb.log_request(
                RequestLogEntry(
                    id=None,
                    ts=time.time(),
                    key=vkey.key,
                    user_id=user_id,
                    team_id=team_id,
                    app_id=app_id,
                    prompt=raw_user_prompt,
                    pruned_prompt=pruned_prompt,
                    model=model,
                    provider=route.provider,
                    tier=assigned_tier,
                    prompt_tokens=est_prompt,
                    pruned_tokens=prune_res.pruned_tokens,
                    completion_tokens=0,
                    total_tokens=est_prompt,
                    tokens_saved=0,
                    cost_usd=0.0,
                    baseline_cost_usd=baseline_cost_usd,
                    cache_hit=False,
                    cache_tier=None,
                    similarity=None,
                    threshold=None,
                    latency_ms=0.0,
                    status=402,
                )
            )
            raise GatewayError(402, reason, "insufficient_quota", code="budget_exceeded")

        # --------------------------------------------------------------------
        # Step 7: Provider Call Dispatch
        # --------------------------------------------------------------------
        result, used_route = await self._call_with_fallback(
            route, forwarded_messages, params
        )

        lat_ms = (time.perf_counter() - t0) * 1000
        cost = self.pricing.cost_usd(
            used_route.upstream_model, result.prompt_tokens, result.completion_tokens
        )
        total_tokens_used = result.prompt_tokens + result.completion_tokens

        # --------------------------------------------------------------------
        # Step 8: Atomic Usage & Audit Recording
        # --------------------------------------------------------------------
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
        log_id = self.supadb.log_request(
            RequestLogEntry(
                id=None,
                ts=time.time(),
                key=vkey.key,
                user_id=user_id,
                team_id=team_id,
                app_id=app_id,
                prompt=raw_user_prompt,
                pruned_prompt=pruned_prompt,
                model=model,
                provider=used_route.provider,
                tier=assigned_tier,
                prompt_tokens=result.prompt_tokens,
                pruned_tokens=prune_res.pruned_tokens,
                completion_tokens=result.completion_tokens,
                total_tokens=total_tokens_used,
                tokens_saved=pruning_tokens_saved,
                cost_usd=cost,
                baseline_cost_usd=baseline_cost_usd,
                cache_hit=False,
                cache_tier=None,
                similarity=None,
                threshold=None,
                latency_ms=round(lat_ms, 2),
                is_wrong_answer=False,
                status=200,
            )
        )

        # --------------------------------------------------------------------
        # Step 9: Cache Admission (L1 + L2)
        # --------------------------------------------------------------------
        if key_enabled:
            # L1 Exact Cache
            self.cache.set(cache_key, result.response, self.config.cache_ttl_seconds)

            # L2 Semantic Cache
            ttl_req = float(payload.get("ttl_seconds") or (7 * 24 * 3600))
            if norm_user_prompt:
                self.semantic_cache.admit(
                    namespace=namespace_hash,
                    prompt_norm=norm_user_prompt,
                    response=result.response,
                    tokens_saved_if_hit=total_tokens_used,
                    ttl_seconds=ttl_req,
                )

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
            tier=assigned_tier,
            cache_tier=None,
            namespace=namespace_hash,
            baseline_cost_usd=baseline_cost_usd,
            tokens_saved=pruning_tokens_saved,
            pruned_prompt=pruned_prompt,
            pruned_tokens=prune_res.pruned_tokens,
            complexity_score=comp_res.score,
            complexity_signals={
                "length": comp_res.length_signal,
                "instruction": comp_res.instruction_signal,
                "reasoning": comp_res.reasoning_signal,
                "code": comp_res.code_signal,
            },
            similarity=None,
            effective_threshold=None,
            latency_ms=round(lat_ms, 2),
            log_id=log_id,
        )

    # ----- streaming entrypoint --------------------------------------------

    async def chat_completion_stream(
        self,
        *,
        vkey: VirtualKey,
        payload: dict,
        jtf_compress: bool = False,
    ) -> AsyncIterator[StreamChunk]:
        model = payload.get("model")
        if not model:
            raise GatewayError(400, "'model' is required", "invalid_request_error")

        messages = [dict(m) for m in payload.get("messages", [])]
        if not messages:
            raise GatewayError(
                400, "'messages' must be a non-empty list", "invalid_request_error"
            )

        if model in ("tokenmingate", "auto", "default"):
            user_prompts = [
                str(m.get("content", "")) for m in messages if m.get("role") == "user"
            ]
            comp = self.complexity_router.score(" ".join(user_prompts))
            model = self._resolve_auto_model(comp.tier)

        route = self.config.route_for(model)
        if route is None:
            raise GatewayError(
                404,
                f"model {model!r} is not available on this gateway",
                "model_not_found",
                code="model_not_found",
            )

        if vkey.allowed_models and model not in vkey.allowed_models:
            raise GatewayError(
                403,
                f"key {vkey.name!r} is not permitted to use model {model!r}",
                "permission_error",
            )

        params = self._extract_params(payload)

        jtf_analysis = analyze_messages(messages)
        forwarded_messages = messages
        if jtf_compress:
            forwarded_messages, realized = compress_messages(messages)

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
            raise GatewayError(
                402, reason, "insufficient_quota", code="budget_exceeded"
            )

        provider = self.provider_for(route.provider)
        if not hasattr(provider, "stream_chat"):
            raise GatewayError(
                400,
                f"provider {route.provider!r} does not support streaming",
                "invalid_request_error",
            )

        prompt_tokens = 0
        completion_tokens = 0
        try:
            async for chunk in provider.stream_chat(
                upstream_model=route.upstream_model,
                messages=forwarded_messages,
                params=params,
            ):
                if chunk.prompt_tokens is not None:
                    prompt_tokens = chunk.prompt_tokens
                if chunk.completion_tokens is not None:
                    completion_tokens = chunk.completion_tokens
                yield chunk
        except ProviderError as exc:
            self.store.log_request(
                key=vkey.key,
                model=model,
                provider=route.provider,
                prompt_tokens=0,
                completion_tokens=0,
                cost_usd=0.0,
                cache_hit=False,
                jtf_saved=0,
                status=exc.status_code,
            )
            raise GatewayError(exc.status_code, exc.message, "upstream_error") from exc

        cost = self.pricing.cost_usd(
            route.upstream_model, prompt_tokens, completion_tokens
        )
        self.store.record_usage(
            vkey.key,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            cache_hit=False,
            jtf_saved=jtf_analysis.saved_tokens,
        )
        self.store.log_request(
            key=vkey.key,
            model=model,
            provider=route.provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            cache_hit=False,
            jtf_saved=jtf_analysis.saved_tokens,
            status=200,
        )

    async def _call_with_fallback(self, route, messages, params):
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
