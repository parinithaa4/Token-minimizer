"""Tests for Google Gemini provider integration, smart auto-routing, and SupaDB connection verification."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from llm_gateway.app import create_app
from llm_gateway.config import GatewayConfig, ProviderConfig, RouteConfig, load_config
from llm_gateway.gateway import Gateway
from llm_gateway.pricing import PricingTable
from llm_gateway.providers import build_provider
from llm_gateway.providers.base import ProviderError
from llm_gateway.providers.gemini import GeminiProvider
from llm_gateway.store import Store
from llm_gateway.supadb import SupaDB, persist_env_vars


# ==============================================================================
# 1. Gemini Provider Tests
# ==============================================================================

def test_build_provider_gemini():
    cfg = ProviderConfig(name="gemini", type="gemini", api_key="test-key-123")
    prov = build_provider(cfg)
    assert isinstance(prov, GeminiProvider)
    assert prov.name == "gemini"
    assert prov.base_url == "https://generativelanguage.googleapis.com/v1beta/openai"


def test_gemini_key_resolution_order(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_API_KEY", raising=False)

    # 1. No key at all -> ProviderError
    cfg_none = ProviderConfig(name="gemini", type="gemini")
    prov_none = GeminiProvider(cfg_none)
    with pytest.raises(ProviderError) as exc_info:
        prov_none._get_api_key()
    assert "Gemini provider has no API key" in str(exc_info.value)

    # 2. Key from GOOGLE_API_KEY
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key-abc")
    prov = GeminiProvider(cfg_none)
    assert prov._get_api_key() == "google-key-abc"

    # 3. Key from GEMINI_API_KEY takes precedence
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key-xyz")
    assert prov._get_api_key() == "gemini-key-xyz"

    # 4. Explicit api_key on config takes top precedence
    cfg_explicit = ProviderConfig(name="gemini", type="gemini", api_key="explicit-key")
    prov_explicit = GeminiProvider(cfg_explicit)
    assert prov_explicit._get_api_key() == "explicit-key"


@pytest.mark.asyncio
async def test_gemini_chat_request_payload_and_headers():
    cfg = ProviderConfig(name="gemini", type="gemini", api_key="secret-gemini-key")
    prov = GeminiProvider(cfg)

    fake_response_data = {
        "id": "chatcmpl-gemini-1",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello from Gemini 1.5!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 15, "completion_tokens": 8, "total_tokens": 23},
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_response_data

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        res = await prov.chat(
            upstream_model="gemini-1.5-flash",
            messages=[{"role": "user", "content": "Hi"}],
            params={"temperature": 0.5},
        )

    assert res.prompt_tokens == 15
    assert res.completion_tokens == 8
    assert res.response["choices"][0]["message"]["content"] == "Hello from Gemini 1.5!"

    # Verify headers sent
    mock_client.post.assert_called_once()
    _, kwargs = mock_client.post.call_args
    headers = kwargs["headers"]
    assert headers["Authorization"] == "Bearer secret-gemini-key"
    assert headers["x-goog-api-key"] == "secret-gemini-key"
    assert kwargs["json"]["model"] == "gemini-1.5-flash"


# ==============================================================================
# 2. Smart Routing Tests
# ==============================================================================

def test_smart_routing_resolves_gemini_when_key_present(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-live-gemini-key")

    cfg = GatewayConfig(
        providers={
            "gemini": ProviderConfig(name="gemini", type="gemini", api_key_env="GEMINI_API_KEY"),
            "mock": ProviderConfig(name="mock", type="mock"),
        },
        routes={
            "gemini-1.5-flash": RouteConfig(model="gemini-1.5-flash", provider="gemini", upstream_model="gemini-1.5-flash"),
            "gemini-1.5-pro": RouteConfig(model="gemini-1.5-pro", provider="gemini", upstream_model="gemini-1.5-pro"),
            "mock-cheap": RouteConfig(model="mock-cheap", provider="mock", upstream_model="mock-cheap"),
            "mock-echo": RouteConfig(model="mock-echo", provider="mock", upstream_model="mock-echo"),
        },
        complexity_tier_models={
            "economy": "gemini-1.5-flash",
            "balanced": "gemini-1.5-pro",
            "frontier": "gemini-1.5-pro",
        },
    )

    from llm_gateway.cache import build_cache
    gw = Gateway(config=cfg, store=Store("sqlite:///:memory:"), cache=build_cache(cfg))

    assert gw._is_provider_ready("gemini-1.5-flash") is True
    assert gw._is_provider_ready("gemini-1.5-pro") is True

    # Automatic routing resolves to Gemini
    assert gw._resolve_auto_model("economy") == "gemini-1.5-flash"
    assert gw._resolve_auto_model("balanced") == "gemini-1.5-pro"
    assert gw._resolve_auto_model("frontier") == "gemini-1.5-pro"

    # Recognizes both old and new auto aliases
    assert gw._is_auto_model("tokenguard") is True
    assert gw._is_auto_model("tokenguard-auto") is True
    assert gw._is_auto_model("tokenmingate") is True
    assert gw._is_auto_model("auto") is True


def test_smart_routing_falls_back_to_mock_when_no_keys(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    cfg = GatewayConfig(
        providers={
            "gemini": ProviderConfig(name="gemini", type="gemini", api_key_env="GEMINI_API_KEY"),
            "mock": ProviderConfig(name="mock", type="mock"),
        },
        routes={
            "gemini-1.5-flash": RouteConfig(model="gemini-1.5-flash", provider="gemini", upstream_model="gemini-1.5-flash"),
            "mock-cheap": RouteConfig(model="mock-cheap", provider="mock", upstream_model="mock-cheap"),
            "mock-echo": RouteConfig(model="mock-echo", provider="mock", upstream_model="mock-echo"),
        },
    )

    from llm_gateway.cache import build_cache
    gw = Gateway(config=cfg, store=Store("sqlite:///:memory:"), cache=build_cache(cfg))

    assert gw._is_provider_ready("gemini-1.5-flash") is False
    assert gw._is_provider_ready("mock-cheap") is True

    # With no keys, cleanly falls back to mock routes without crashing
    assert gw._resolve_auto_model("economy") == "mock-cheap"
    assert gw._resolve_auto_model("balanced") == "mock-echo"


# ==============================================================================
# 3. SupaDB Connection & Sync Verification
# ==============================================================================

def test_supadb_check_connection_diagnostics():
    db = SupaDB(database_url="sqlite:///:memory:")

    # 1. Missing or placeholder key -> key_required
    res = db.check_connection(url="https://test.supabase.co", key="")
    assert res["connected"] is False
    assert res["status"] == "key_required"

    res_dummy = db.check_connection(url="https://test.supabase.co", key="sb_live_service_role_secret")
    assert res_dummy["connected"] is False
    assert res_dummy["status"] == "key_required"

    # 2. Unauthorized response
    mock_401 = MagicMock()
    mock_401.status_code = 401
    mock_401.text = '{"message":"Invalid API key"}'

    with patch("httpx.Client.get", return_value=mock_401):
        res_unauth = db.check_connection(url="https://test.supabase.co", key="invalid-jwt-token")
        assert res_unauth["connected"] is False
        assert res_unauth["status"] == "unauthorized"

    # 3. Connected but schema missing
    mock_root = MagicMock()
    mock_root.status_code = 200

    mock_no_teams = MagicMock()
    mock_no_teams.status_code = 404

    def side_effect_schema(url, headers):
        if "teams" in url:
            return mock_no_teams
        return mock_root

    with patch("httpx.Client.get", side_effect=side_effect_schema):
        res_schema = db.check_connection(url="https://test.supabase.co", key="valid-key")
        assert res_schema["connected"] is True
        assert res_schema["status"] == "schema_needed"
        assert res_schema["tables_ready"] is False

    # 4. Fully connected with tables verified
    mock_teams_ok = MagicMock()
    mock_teams_ok.status_code = 200

    def side_effect_ok(url, headers):
        if "teams" in url:
            return mock_teams_ok
        return mock_root

    with patch("httpx.Client.get", side_effect=side_effect_ok):
        res_ok = db.check_connection(url="https://test.supabase.co", key="valid-key")
        assert res_ok["connected"] is True
        assert res_ok["status"] == "connected"
        assert res_ok["tables_ready"] is True


def test_persist_env_vars(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("PORT=8080\nOLD_VAR=123\n")

    persist_env_vars({"GEMINI_API_KEY": "AIzaSyTestKey", "NEW_VAR": "456"}, env_path=env_file)

    content = env_file.read_text()
    assert "GEMINI_API_KEY=AIzaSyTestKey" in content
    assert "NEW_VAR=456" in content
    assert "PORT=8080" in content
    assert os.environ.get("GEMINI_API_KEY") == "AIzaSyTestKey"


# ==============================================================================
# 4. API Endpoints Tests
# ==============================================================================

def test_api_config_keys_endpoints(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)

    # 1. GET /api/config/keys
    r_get = client.get("/api/config/keys")
    assert r_get.status_code == 200
    data = r_get.json()
    assert "gemini" in data
    assert "supabase" in data
    assert "openai" in data

    # 2. POST /api/config/keys (with persist_env_vars mocked to not dirty .env)
    with patch("llm_gateway.app.persist_env_vars"):
        r_post = client.post(
            "/api/config/keys",
            json={
                "gemini_api_key": "AIzaSyTestApiKey12345",
                "supabase_url": "https://test.supabase.co",
            },
        )
    assert r_post.status_code == 200
    res_data = r_post.json()
    assert res_data["success"] is True

    # Verify update reflected in GET
    r_get_after = client.get("/api/config/keys")
    data_after = r_get_after.json()
    assert data_after["gemini"]["configured"] is True
    assert data_after["gemini"]["masked"].startswith("AIza")
