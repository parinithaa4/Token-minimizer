"""End-to-end smoke test against the zero-config default app.

This mirrors the README quickstart: build the app with NO config (mock provider
+ seeded dev key), POST a chat completion, and assert a 200 with usage. No real
keys, no network.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from llm_gateway.app import create_app
from llm_gateway.config import default_config


def test_default_app_smoke():
    app = create_app(default_config())
    client = TestClient(app)

    health = client.get("/healthz")
    assert health.status_code == 200
    assert "mock-echo" in health.json()["models"]

    r = client.post(
        "/v1/chat/completions",
        json={
            "model": "mock-echo",
            "messages": [{"role": "user", "content": "smoke test"}],
        },
        headers={"Authorization": "Bearer sk-gw-dev"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["choices"][0]["message"]["content"]
    assert body["usage"]["total_tokens"] > 0
    assert body["usage"]["gateway"]["provider"] == "mock"
