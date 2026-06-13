"""Admin dashboard + the extended ``/admin/usage`` JSON it consumes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from llm_gateway.app import create_app
from llm_gateway.config import KeyConfig
from tests.conftest import DEV_KEY, _test_config


def _seed_usage(client, auth):
    """Drive a couple of requests so the dashboard has real data to render."""
    for content in ("dashboard seed one", "dashboard seed two"):
        r = client.post(
            "/v1/chat/completions",
            json={"model": "mock-echo", "messages": [{"role": "user", "content": content}]},
            headers=auth(DEV_KEY),
        )
        assert r.status_code == 200


def test_dashboard_returns_200_html(client):
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    html = r.text
    # Core markup + brand design tokens are present.
    assert "<title>llm-gateway" in html
    assert 'id="totals"' in html
    assert 'id="cards"' in html
    assert "Virtual keys" in html
    assert "--cyan: #34E7FF" in html  # exact brand accent
    assert "/admin/usage" in html  # it fetches the usage endpoint
    assert "chat.completion.chunk" not in html  # it's a dashboard, not the API


def test_dashboard_renders_with_zero_data(client):
    # Fresh app, no requests issued — dashboard must still serve cleanly.
    r = client.get("/dashboard")
    assert r.status_code == 200
    usage = client.get("/admin/usage").json()
    assert usage["totals"]["requests"] == 0
    assert all(k["requests"] == 0 for k in usage["keys"])


def test_admin_usage_shape_with_totals(client, auth):
    _seed_usage(client, auth)
    data = client.get("/admin/usage").json()

    assert "totals" in data and "keys" in data
    t = data["totals"]
    for field in (
        "keys",
        "requests",
        "cache_hits",
        "cache_hit_rate",
        "total_tokens",
        "cost_usd",
        "jtf_potential_tokens_saved",
    ):
        assert field in t, f"missing totals.{field}"
    assert t["requests"] == 2
    assert t["total_tokens"] > 0
    assert t["cost_usd"] > 0

    dev = next(k for k in data["keys"] if k["key_name"] == "dev")
    for field in (
        "key",
        "requests",
        "total_tokens",
        "cost_usd",
        "budget_usd",
        "budget_used_ratio",
        "cache_hit_rate",
        "jtf_potential_tokens_saved",
    ):
        assert field in dev, f"missing key.{field}"
    # budget_used_ratio is a 0..1 fraction for a key with a max_usd cap.
    assert 0.0 <= dev["budget_used_ratio"] <= 1.0


def test_admin_usage_budget_used_ratio_none_when_uncapped():
    cfg = _test_config()
    cfg.keys.append(KeyConfig(key="sk-test-uncapped", name="uncapped", max_usd=None))
    client = TestClient(create_app(cfg))
    rows = client.get("/admin/usage").json()["keys"]
    uncapped = next(r for r in rows if r["key_name"] == "uncapped")
    assert uncapped["budget_usd"] is None
    assert uncapped["budget_used_ratio"] is None


def test_admin_token_gate_enforced_when_configured():
    cfg = _test_config()
    cfg.admin_token = "s3cret-admin"
    client = TestClient(create_app(cfg))

    # Without the token: 401.
    assert client.get("/admin/usage").status_code == 401
    # Header form works.
    ok = client.get("/admin/usage", headers={"X-Admin-Token": "s3cret-admin"})
    assert ok.status_code == 200
    # Query-param form works (this is what the dashboard uses).
    ok2 = client.get("/admin/usage?admin_token=s3cret-admin")
    assert ok2.status_code == 200
    # Wrong token: 401.
    assert client.get("/admin/usage?admin_token=nope").status_code == 401
    # The dashboard page itself is always served (token is applied client-side).
    assert client.get("/dashboard").status_code == 200
