"""FastAPI application: OpenAI-compatible endpoints + TokenMinGate employee application.

Endpoints:
  POST /v1/chat/completions   — OpenAI-compatible chat completions (non-stream & SSE stream)
  GET  /v1/models             — list routed models (OpenAI shape)
  GET  /admin/usage           — per-key usage, budget remaining, cache-hit rate
  GET  /admin/pricing         — active pricing table
  GET  /healthz               — liveness
  GET  /                      — Unified TokenMinGate Employee Application
  GET  /dashboard             — TokenMinGate Dashboard
  
TokenMinGate Application & SupaDB Endpoints:
  POST /auth/login            — Employee authentication
  POST /auth/register         — Employee registration
  GET  /auth/demo-users       — List 1-click demo profiles
  GET  /auth/me               — Get current employee profile
  POST /api/chat/pipeline     — Execute Algorithm 1 with full step-by-step trace
  POST /api/cache/feedback    — Mark L2 cache answer accurate / wrong (updates P & TRRnet)
  GET  /api/metrics/research-summary — Paper Tables I, II, III and KPI calculations
  GET  /api/ledger            — Filterable request audit trail
  GET  /api/cache/entries     — Inspect L2 cache entries & current effective tau
  POST /api/cache/simulate-age — Simulate answer aging to observe dynamic tau_eff rise
  POST /api/cache/evict       — Evict specific cache entry
  POST /api/cache/purge       — Purge expired cache entries
  GET  /api/db/status         — SupaDB / Supabase engine status
  POST /api/db/sync-supabase  — Synchronize local data to Supabase cloud
  GET  /api/db/schema.sql     — View Supabase SQL migration script
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

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
from .supadb import SupaDB

log = logging.getLogger("llm_gateway")


# --- Request & Response Models for TokenMinGate Application ---

class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    team_id: str = "support"


class PipelineChatRequest(BaseModel):
    model: str = "tokenmingate"
    messages: list[dict[str, Any]]
    team_id: str | None = None
    user_id: str | None = None
    app_id: str | None = "web"
    ttl_seconds: float = 604800.0
    tau: float = 0.84
    temperature: float = 0.0


class FeedbackRequest(BaseModel):
    log_id: int
    is_wrong_answer: bool
    notes: str | None = None


class SimulateAgeRequest(BaseModel):
    entry_id: str
    age_seconds: float


class EvictCacheRequest(BaseModel):
    entry_id: str


class SyncSupabaseRequest(BaseModel):
    supabase_url: str
    supabase_key: str


def _error_response(status: int, message: str, err_type: str, code: str | None = None):
    body = ErrorResponse(error=ErrorBody(message=message, type=err_type, code=code))
    return JSONResponse(status_code=status, content=body.model_dump())


def _sse_event(obj: dict) -> str:
    return "data: " + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n\n"


def _chunk_obj(
    stream_id: str,
    created: int,
    model: str,
    *,
    delta: dict,
    finish_reason: str | None = None,
) -> dict:
    return {
        "id": stream_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }


async def _sse_from_chunks(agen, *, model: str) -> AsyncIterator[str]:
    stream_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    aiter = agen.__aiter__()
    try:
        first = await aiter.__anext__()
    except StopAsyncIteration:
        first = None

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

    final = _chunk_obj(
        stream_id, created, model, delta={}, finish_reason=finish_reason or "stop"
    )
    if usage is not None:
        final["usage"] = usage
    yield _sse_event(final)
    yield "data: [DONE]\n\n"


async def _prepend(first: str, rest: AsyncIterator[str]) -> AsyncIterator[str]:
    yield first
    async for item in rest:
        yield item


def seed_store_from_config(store: Store, config: GatewayConfig) -> None:
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
    config = config or load_config()
    db_url = config.database_url
    if os.environ.get("GATEWAY_TEST_MODE") == "1":
        db_url = "sqlite:///:memory:"

    store = Store(db_url)
    seed_store_from_config(store, config)
    cache = build_cache(config.redis_url)
    pricing = PricingTable()
    supadb = SupaDB(database_url=db_url, connection=store._conn)
    gateway = Gateway(config, store, cache, pricing, supadb=supadb)

    app = FastAPI(
        title="TokenMinGate LLM Gateway",
        version="0.2.0",
        description="Cost-cutting LLM gateway with semantic caching, age-aware validation, and model routing.",
    )
    app.state.gateway = gateway
    app.state.store = store
    app.state.config = config
    app.state.cache = cache
    app.state.pricing = pricing
    app.state.supadb = supadb

    # ----- auth dependency --------------------------------------------------

    async def require_key(
        authorization: str | None = Header(default=None),
    ) -> VirtualKey:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise GatewayError(
                401,
                "missing or malformed Authorization header (expected 'Bearer <key>')",
                "authentication_error",
                code="invalid_api_key",
            )
        token = authorization.split(" ", 1)[1].strip()
        vkey = store.get_key(token)
        if vkey is None:
            # Check supadb registered employees
            emp = supadb.get_employee_by_key(token)
            if emp:
                vkey = VirtualKey(
                    key=emp.api_key,
                    name=emp.name,
                    allowed_models=[],
                    max_usd=100.0,
                    max_tokens=1_000_000,
                    cache_enabled=True,
                )
                store.upsert_key(vkey)

        if vkey is None:
            raise GatewayError(
                401, "invalid API key", "authentication_error", code="invalid_api_key"
            )
        return vkey

    # ----- exception handler ------------------------------------------------

    @app.exception_handler(GatewayError)
    async def _gw_error_handler(_request: Request, exc: GatewayError):
        return _error_response(exc.status_code, exc.message, exc.err_type, exc.code)

    # ----- Core OpenAI-compatible endpoints ---------------------------------

    @app.get("/healthz")
    async def healthz():
        return {
            "status": "ok",
            "models": gateway.available_models(),
            "supadb_mode": supadb.get_status()["mode"],
        }

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
        cache_enabled = (x_cache or "").strip().lower() not in ("no-store", "off", "false")

        if body.stream:
            sse = _sse_from_chunks(
                gateway.chat_completion_stream(
                    vkey=vkey, payload=payload, jtf_compress=jtf_compress
                ),
                model=body.model,
            )
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

        response = dict(result.response)
        usage = dict(response.get("usage", {}))
        usage["gateway"] = {
            "cache_hit": result.cache_hit,
            "cache_tier": result.cache_tier,
            "cost_usd": round(result.cost_usd, 8),
            "provider": result.provider,
            "tier": result.tier,
            "jtf": result.jtf,
        }
        response["usage"] = usage

        headers = {
            "X-Cache": "HIT" if result.cache_hit else "MISS",
            "X-Cache-Tier": result.cache_tier or "NONE",
            "X-Cost-USD": f"{result.cost_usd:.8f}",
            "X-Provider": result.provider,
            "X-Tier": result.tier,
            "X-JTF-Potential-Tokens-Saved": str(
                result.jtf.get("potential_tokens_saved", 0)
            ),
            "X-JTF-Compressed": "true" if result.jtf_compressed else "false",
        }
        return JSONResponse(content=response, headers=headers)

    # ----- Employee Authentication Endpoints --------------------------------

    @app.post("/auth/login")
    async def auth_login(req: LoginRequest):
        emp = supadb.authenticate(req.email, req.password)
        if not emp:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid work email or password"},
            )
        # Ensure key in memory store
        store.upsert_key(
            VirtualKey(
                key=emp.api_key,
                name=emp.name,
                allowed_models=[],
                max_usd=100.0,
                max_tokens=1_000_000,
                cache_enabled=True,
            )
        )
        return {
            "id": emp.id,
            "email": emp.email,
            "name": emp.name,
            "role": emp.role,
            "team_id": emp.team_id,
            "app_id": emp.app_id,
            "api_key": emp.api_key,
        }

    @app.post("/auth/register")
    async def auth_register(req: RegisterRequest):
        try:
            emp = supadb.register_employee(
                email=req.email,
                password=req.password,
                name=req.name,
                team_id=req.team_id,
            )
            store.upsert_key(
                VirtualKey(
                    key=emp.api_key,
                    name=emp.name,
                    allowed_models=[],
                    max_usd=100.0,
                    max_tokens=1_000_000,
                    cache_enabled=True,
                )
            )
            return {
                "id": emp.id,
                "email": emp.email,
                "name": emp.name,
                "role": emp.role,
                "team_id": emp.team_id,
                "api_key": emp.api_key,
            }
        except Exception as e:
            return JSONResponse(
                status_code=400, content={"detail": f"Registration failed: {e}"}
            )

    @app.get("/auth/demo-users")
    async def auth_demo_users():
        return supadb.list_employees()

    @app.get("/auth/me")
    async def auth_me(vkey: VirtualKey = Depends(require_key)):
        emp = supadb.get_employee_by_key(vkey.key)
        if emp:
            return {
                "id": emp.id,
                "email": emp.email,
                "name": emp.name,
                "role": emp.role,
                "team_id": emp.team_id,
                "api_key": emp.api_key,
            }
        return {"name": vkey.name, "api_key": vkey.key, "team_id": "platform", "role": "developer"}

    # ----- Interactive Gateway Pipeline Execution ---------------------------

    @app.post("/api/chat/pipeline")
    async def api_chat_pipeline(
        req: PipelineChatRequest,
        vkey: VirtualKey = Depends(require_key),
    ):
        if req.tau:
            gateway.semantic_cache.tau = float(req.tau)

        payload = {
            "model": req.model,
            "messages": req.messages,
            "team_id": req.team_id or "default",
            "user_id": req.user_id or vkey.name,
            "app_id": req.app_id or "web",
            "ttl_seconds": req.ttl_seconds,
            "temperature": req.temperature,
        }

        result = await gateway.chat_completion(
            vkey=vkey,
            payload=payload,
            cache_enabled=True,
            jtf_compress=False,
        )

        user_content = " ".join(
            str(m.get("content", "")) for m in req.messages if m.get("role") == "user"
        )
        delta_c = (
            ((result.baseline_cost_usd - result.cost_usd) / result.baseline_cost_usd * 100)
            if result.baseline_cost_usd > 0
            else 0.0
        )

        pipeline_trace = {
            "namespace": {
                "hash": result.namespace,
                "team_id": payload["team_id"],
                "provider": result.provider,
                "temperature": req.temperature,
            },
            "l1_cache": {
                "checked": True,
                "hit": result.cache_tier == "l1",
                "saved_tokens": result.tokens_saved if result.cache_tier == "l1" else 0,
            },
            "l2_cache": {
                "checked": result.cache_tier != "l1",
                "hit": result.cache_tier == "l2",
                "similarity": result.similarity,
                "effective_threshold": result.effective_threshold,
                "base_threshold": gateway.semantic_cache.tau,
                "age_seconds": 0.0,
                "ttl_seconds": req.ttl_seconds,
            },
            "pruning": {
                "original_tokens": result.prompt_tokens + result.tokens_saved,
                "pruned_tokens": result.pruned_tokens,
                "tokens_saved": result.tokens_saved if not result.cache_hit else 0,
                "reduction_pct": round(
                    (result.tokens_saved / (result.prompt_tokens + result.tokens_saved) * 100)
                    if (result.prompt_tokens + result.tokens_saved) > 0
                    else 0.0,
                    1,
                ),
            },
            "complexity": {
                "score": result.complexity_score,
                "tier": result.tier,
                "model": result.model,
                "signals": result.complexity_signals,
            },
            "savings": {
                "tokens_used": result.prompt_tokens + result.completion_tokens,
                "tokens_saved": result.tokens_saved,
                "cost_usd": result.cost_usd,
                "baseline_cost_usd": result.baseline_cost_usd,
                "delta_c_pct": round(delta_c, 1),
                "latency_ms": result.latency_ms,
            },
            "tier": result.tier,
            "log_id": result.log_id,
        }

        return {
            "choices": result.response.get("choices", []),
            "usage": result.response.get("usage", {}),
            "cache_hit": result.cache_hit,
            "pipeline": pipeline_trace,
        }

    # ----- Cache Feedback & Management --------------------------------------

    @app.post("/api/cache/feedback")
    async def api_cache_feedback(req: FeedbackRequest):
        ok = supadb.update_feedback(req.log_id, req.is_wrong_answer, req.notes)
        return {"success": ok}

    @app.get("/api/cache/entries")
    async def api_cache_entries():
        return gateway.semantic_cache.list_entries()

    @app.post("/api/cache/simulate-age")
    async def api_cache_simulate_age(req: SimulateAgeRequest):
        eff_tau = gateway.semantic_cache.simulate_age(req.entry_id, req.age_seconds)
        return {"effective_threshold": eff_tau}

    @app.post("/api/cache/evict")
    async def api_cache_evict(req: EvictCacheRequest):
        ok = gateway.semantic_cache.evict(req.entry_id)
        return {"success": ok}

    @app.post("/api/cache/purge")
    async def api_cache_purge():
        removed = gateway.semantic_cache.purge_expired()
        return {"removed": removed}

    @app.post("/api/cache/clear")
    async def api_cache_clear():
        gateway.semantic_cache.clear()
        gateway.cache.clear()
        return {"success": True}

    # ----- Observability & Paper Research Metrics ---------------------------

    @app.get("/api/metrics/research-summary")
    async def api_research_summary():
        return supadb.calculate_research_metrics()

    @app.get("/api/ledger")
    async def api_ledger(
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        team_id: str | None = None,
        user_id: str | None = None,
        tier: str | None = None,
        search: str | None = None,
    ):
        rows, total = supadb.get_ledger(limit, offset, team_id, user_id, tier, search)
        return {"rows": rows, "total": total}

    # ----- SupaDB Engine & Sync ---------------------------------------------

    @app.get("/api/db/status")
    async def api_db_status():
        return supadb.get_status()

    @app.post("/api/db/sync-supabase")
    async def api_sync_supabase(req: SyncSupabaseRequest):
        res = supadb.sync_to_supabase(req.supabase_url, req.supabase_key)
        return res

    @app.get("/api/db/schema.sql")
    async def api_schema_sql():
        schema_path = Path(__file__).parent.parent.parent / "supabase_schema.sql"
        if schema_path.exists():
            return PlainTextResponse(schema_path.read_text(encoding="utf-8"))
        return PlainTextResponse("-- supabase_schema.sql not found on disk")

    # ----- Admin Endpoints (compatible with original quickstart) ------------

    def _require_admin(request: Request) -> None:
        token = config.admin_token
        if not token:
            return
        supplied = request.headers.get("x-admin-token") or request.query_params.get(
            "admin_token"
        )
        if supplied != token:
            raise GatewayError(
                401,
                "invalid or missing admin token",
                "authentication_error",
                code="invalid_admin_token",
            )

    @app.get("/admin/usage")
    async def admin_usage(request: Request):
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

    @app.get("/", response_class=HTMLResponse)
    @app.get("/dashboard", response_class=HTMLResponse)
    async def serve_dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    return app


def _mask(key: str) -> str:
    if len(key) <= 8:
        return key[:2] + "***"
    return f"{key[:6]}...{key[-2:]}"


app = create_app()
