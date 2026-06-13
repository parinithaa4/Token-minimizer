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

import json
import logging
import os
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from .cache import build_cache
from .config import GatewayConfig, load_config
from .dashboard import DASHBOARD_HTML
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


def _sse_event(obj: dict) -> str:
    """Format one OpenAI-style SSE frame: ``data: {json}\\n\\n``."""
    return "data: " + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n\n"


def _chunk_obj(
    stream_id: str,
    created: int,
    model: str,
    *,
    delta: dict,
    finish_reason: str | None = None,
) -> dict:
    """Build an OpenAI ``chat.completion.chunk`` object."""
    return {
        "id": stream_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }


async def _sse_from_chunks(agen, *, model: str) -> AsyncIterator[str]:
    """Translate normalized gateway :class:`StreamChunk`s into OpenAI SSE text.

    Emits, in order: a role-priming chunk, one chunk per content delta, a final
    chunk with ``finish_reason`` (and usage when available), then the
    ``data: [DONE]`` sentinel. Stepping this generator once drives the gateway's
    budget pre-check before any frame is produced.
    """
    stream_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    # Pull the first gateway chunk first — this triggers validation + the budget
    # pre-check inside ``chat_completion_stream`` (may raise GatewayError).
    aiter = agen.__aiter__()
    try:
        first = await aiter.__anext__()
    except StopAsyncIteration:
        first = None

    # Role-priming frame (OpenAI sends an initial delta with just the role).
    yield _sse_event(
        _chunk_obj(stream_id, created, model, delta={"role": "assistant"})
    )

    finish_reason: str | None = None
    usage: dict | None = None

    def _emit(chunk) -> str | None:
        nonlocal finish_reason, usage
        if chunk.finish_reason is not None:
            finish_reason = chunk.finish_reason
        if chunk.prompt_tokens is not None or chunk.completion_tokens is not None:
            pt = chunk.prompt_tokens or 0
            ct = chunk.completion_tokens or 0
            usage = {
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "total_tokens": pt + ct,
            }
        if chunk.delta_content:
            return _sse_event(
                _chunk_obj(
                    stream_id,
                    created,
                    model,
                    delta={"content": chunk.delta_content},
                )
            )
        return None

    if first is not None:
        frame = _emit(first)
        if frame is not None:
            yield frame
        async for chunk in aiter:
            frame = _emit(chunk)
            if frame is not None:
                yield frame

    # Terminal chunk: empty delta + finish_reason, plus usage when known.
    final = _chunk_obj(
        stream_id, created, model, delta={}, finish_reason=finish_reason or "stop"
    )
    if usage is not None:
        final["usage"] = usage
    yield _sse_event(final)
    yield "data: [DONE]\n\n"


async def _prepend(first: str, rest: AsyncIterator[str]) -> AsyncIterator[str]:
    """Yield an already-fetched first frame, then the remainder of ``rest``."""
    yield first
    async for item in rest:
        yield item


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
        payload = body.model_dump(exclude_none=True)
        jtf_compress = (x_jtf_compress or "").strip().lower() in ("1", "true", "yes")
        # Per-request cache override: X-Cache: no-store disables caching.
        cache_enabled = (x_cache or "").strip().lower() not in ("no-store", "off", "false")

        # --- Streaming path (OpenAI-style SSE). ---
        if body.stream:
            sse = _sse_from_chunks(
                gateway.chat_completion_stream(
                    vkey=vkey, payload=payload, jtf_compress=jtf_compress
                ),
                model=body.model,
            )
            # Drive the generator once *before* returning the response. This runs
            # validation + the budget pre-check (which may raise GatewayError →
            # 402) so an over-budget request never produces a partial stream. The
            # already-fetched first frame is replayed by ``_prepend``.
            first_frame = await sse.__anext__()
            return StreamingResponse(
                _prepend(first_frame, sse),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

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

    def _require_admin(request: Request) -> None:
        """Optional admin gate. If ``config.admin_token`` is set, require it via
        ``X-Admin-Token`` header or ``?admin_token=`` query (the dashboard uses
        the latter). When unset, ``/admin/*`` stays open for the quickstart.
        """
        token = config.admin_token
        if not token:
            return
        supplied = request.headers.get("x-admin-token") or request.query_params.get(
            "admin_token"
        )
        if supplied != token:
            raise GatewayError(
                401, "invalid or missing admin token", "authentication_error",
                code="invalid_admin_token",
            )

    @app.get("/admin/usage")
    async def admin_usage(request: Request):
        """Per-key observability snapshot + portfolio totals.

        Self-hosted/internal. If ``admin_token`` is configured it must be
        supplied (header ``X-Admin-Token`` or ``?admin_token=``); otherwise the
        endpoint is open so the quickstart and dashboard work out of the box.
        """
        _require_admin(request)
        keys = store.list_keys()
        out = []
        tot_requests = tot_cache_hits = 0
        tot_tokens = tot_jtf = 0
        tot_cost = 0.0
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
            budget_used_ratio = (
                None
                if vk.max_usd is None or vk.max_usd <= 0
                else min(1.0, u.cost_usd / vk.max_usd)
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
                    "budget_used_ratio": (
                        None if budget_used_ratio is None else round(budget_used_ratio, 4)
                    ),
                    "budget_tokens": vk.max_tokens,
                    "budget_remaining_tokens": budget_remaining_tokens,
                    "jtf_potential_tokens_saved": u.jtf_potential_tokens_saved,
                }
            )
            tot_requests += u.requests
            tot_cache_hits += u.cache_hits
            tot_tokens += u.total_tokens
            tot_cost += u.cost_usd
            tot_jtf += u.jtf_potential_tokens_saved

        totals = {
            "keys": len(keys),
            "requests": tot_requests,
            "cache_hits": tot_cache_hits,
            "cache_hit_rate": round(tot_cache_hits / tot_requests, 4)
            if tot_requests
            else 0.0,
            "total_tokens": tot_tokens,
            "cost_usd": round(tot_cost, 6),
            "jtf_potential_tokens_saved": tot_jtf,
        }
        return {"totals": totals, "keys": out}

    @app.get("/admin/pricing")
    async def admin_pricing(request: Request):
        _require_admin(request)
        return {"prices_per_mtok_usd": pricing.as_dict()}

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard():
        """Serve the self-contained admin dashboard (inline HTML/CSS/JS).

        The page fetches ``/admin/usage`` client-side and renders totals +
        per-key cards. If ``admin_token`` is configured, append it to the URL as
        ``/dashboard?admin_token=...`` — the page forwards it to the fetch.
        """
        return HTMLResponse(content=DASHBOARD_HTML)

    return app


def _mask(key: str) -> str:
    if len(key) <= 8:
        return key[:2] + "***"
    return f"{key[:6]}...{key[-2:]}"


# Module-level ASGI app for ``uvicorn llm_gateway.app:app``.
app = create_app()
