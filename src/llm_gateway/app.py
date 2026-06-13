"""FastAPI application: OpenAI-compatible endpoints + admin observability.

Endpoints:
  POST /v1/chat/completions   — OpenAI-compatible chat completions (non-stream)
  GET  /v1/models             — list routed models (OpenAI shape)
  GET  /admin/usage           — per-key usage, budget remaining, cache-hit rate
  GET  /healthz               — liveness

Auth: clients send ``Authorization: Bearer <vkey>``. The vkey is resolved
against the store; missing/invalid → 401.

Gateway metadata (cache hit, cost, JTF savings) is exposed both as response
headers (``X-Cache``, ``X-Cost-USD``, ``X-JTF-*``) and inside
``response["usage"]["gateway"]`` so SDK users get it without reading headers.
"""

from __future__ import annotations

import logging
import os

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse

from .cache import build_cache
from .config import GatewayConfig, load_config
from .gateway import Gateway, GatewayError
from .pricing import PricingTable
from .schemas import (
    ChatCompletionRequest,
    ErrorBody,
    ErrorResponse,
    ModelCard,
    ModelList,
)
from .store import KeyUsage, Store, VirtualKey

log = logging.getLogger("llm_gateway")


def _error_response(status: int, message: str, err_type: str, code: str | None = None):
    body = ErrorResponse(error=ErrorBody(message=message, type=err_type, code=code))
    return JSONResponse(status_code=status, content=body.model_dump())


def seed_store_from_config(store: Store, config: GatewayConfig) -> None:
    """Insert configured virtual keys into the store (idempotent upsert)."""
    for k in config.keys:
        store.upsert_key(
            VirtualKey(
                key=k.key,
                name=k.name,
                allowed_models=k.allowed_models,
                max_usd=k.max_usd,
                max_tokens=k.max_tokens,
                cache_enabled=k.cache_enabled,
            )
        )


def create_app(config: GatewayConfig | None = None) -> FastAPI:
    """Application factory.

    Defaults to an **in-memory** SQLite store so a fresh app (and every test)
    starts clean with the mock provider. A real deployment passes a config with
    a file-backed ``database_url`` and real providers.
    """
    config = config or load_config()
    # Tests and zero-config runs use an in-memory DB unless told otherwise.
    db_url = config.database_url
    if os.environ.get("GATEWAY_TEST_MODE") == "1":
        db_url = "sqlite:///:memory:"

    store = Store(db_url)
    seed_store_from_config(store, config)
    cache = build_cache(config.redis_url)
    pricing = PricingTable()
    gateway = Gateway(config, store, cache, pricing)

    app = FastAPI(
        title="llm-gateway",
        version="0.1.0",
        description="Token-frugal, self-hostable OpenAI-compatible LLM gateway.",
    )
    app.state.gateway = gateway
    app.state.store = store
    app.state.config = config
    app.state.cache = cache
    app.state.pricing = pricing

    # ----- auth dependency --------------------------------------------------

    async def require_key(
        authorization: str | None = Header(default=None),
    ) -> VirtualKey:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise GatewayError(
                401,
                "missing or malformed Authorization header "
                "(expected 'Bearer <key>')",
                "authentication_error",
                code="invalid_api_key",
            )
        token = authorization.split(" ", 1)[1].strip()
        vkey = store.get_key(token)
        if vkey is None:
            raise GatewayError(
                401, "invalid API key", "authentication_error", code="invalid_api_key"
            )
        return vkey

    # ----- exception handler ------------------------------------------------

    @app.exception_handler(GatewayError)
    async def _gw_error_handler(_request: Request, exc: GatewayError):
        return _error_response(exc.status_code, exc.message, exc.err_type, exc.code)

    # ----- endpoints --------------------------------------------------------

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "models": gateway.available_models()}

    @app.get("/v1/models", response_model=ModelList)
    async def list_models(_vkey: VirtualKey = Depends(require_key)):
        cards = [ModelCard(id=m) for m in gateway.available_models()]
        return ModelList(data=cards)

    @app.post("/v1/chat/completions")
    async def chat_completions(
        body: ChatCompletionRequest,
        request: Request,
        vkey: VirtualKey = Depends(require_key),
        x_jtf_compress: str | None = Header(default=None),
        x_cache: str | None = Header(default=None),
    ):
        if body.stream:
            raise GatewayError(
                400,
                "streaming is not supported yet (see roadmap); set stream=false",
                "invalid_request_error",
            )

        payload = body.model_dump(exclude_none=True)
        jtf_compress = (x_jtf_compress or "").strip().lower() in ("1", "true", "yes")
        # Per-request cache override: X-Cache: no-store disables caching.
        cache_enabled = (x_cache or "").strip().lower() not in ("no-store", "off", "false")

        result = await gateway.chat_completion(
            vkey=vkey,
            payload=payload,
            cache_enabled=cache_enabled,
            jtf_compress=jtf_compress,
        )

        # Embed gateway metadata inside usage so SDK users see it without headers.
        response = dict(result.response)
        usage = dict(response.get("usage", {}))
        usage["gateway"] = {
            "cache_hit": result.cache_hit,
            "cost_usd": round(result.cost_usd, 8),
            "provider": result.provider,
            "jtf": result.jtf,
        }
        response["usage"] = usage

        headers = {
            "X-Cache": "HIT" if result.cache_hit else "MISS",
            "X-Cost-USD": f"{result.cost_usd:.8f}",
            "X-Provider": result.provider,
            "X-JTF-Potential-Tokens-Saved": str(
                result.jtf.get("potential_tokens_saved", 0)
            ),
            "X-JTF-Compressed": "true" if result.jtf_compressed else "false",
        }
        return JSONResponse(content=response, headers=headers)

    @app.get("/admin/usage")
    async def admin_usage(_request: Request):
        """Per-key observability snapshot. Self-hosted/internal — no auth gate.

        In a real deployment you'd protect this with an admin token; kept open
        here so the quickstart and dashboards work out of the box.
        """
        keys = store.list_keys()
        out = []
        for vk in keys:
            u: KeyUsage = store.get_usage(vk.key)
            hit_rate = (u.cache_hits / u.requests) if u.requests else 0.0
            budget_remaining_usd = (
                None if vk.max_usd is None else max(0.0, vk.max_usd - u.cost_usd)
            )
            budget_remaining_tokens = (
                None
                if vk.max_tokens is None
                else max(0, vk.max_tokens - u.total_tokens)
            )
            out.append(
                {
                    "key_name": vk.name,
                    "key": _mask(vk.key),
                    "requests": u.requests,
                    "cache_hits": u.cache_hits,
                    "cache_hit_rate": round(hit_rate, 4),
                    "prompt_tokens": u.prompt_tokens,
                    "completion_tokens": u.completion_tokens,
                    "total_tokens": u.total_tokens,
                    "cost_usd": round(u.cost_usd, 6),
                    "budget_usd": vk.max_usd,
                    "budget_remaining_usd": (
                        None if budget_remaining_usd is None else round(budget_remaining_usd, 6)
                    ),
                    "budget_tokens": vk.max_tokens,
                    "budget_remaining_tokens": budget_remaining_tokens,
                    "jtf_potential_tokens_saved": u.jtf_potential_tokens_saved,
                }
            )
        return {"keys": out}

    @app.get("/admin/pricing")
    async def admin_pricing(_request: Request):
        return {"prices_per_mtok_usd": pricing.as_dict()}

    return app


def _mask(key: str) -> str:
    if len(key) <= 8:
        return key[:2] + "***"
    return f"{key[:6]}...{key[-2:]}"


# Module-level ASGI app for ``uvicorn llm_gateway.app:app``.
app = create_app()
