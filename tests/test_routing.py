"""Routing: requests reach the mock provider and return OpenAI-shaped output."""

from __future__ import annotations

from tests.conftest import CHEAP_KEY, DEV_KEY


def test_openai_shaped_response(client, auth):
    r = client.post(
        "/v1/chat/completions",
        json={
            "model": "mock-echo",
            "messages": [{"role": "user", "content": "ping"}],
        },
        headers=auth(DEV_KEY),
    )
    assert r.status_code == 200
    data = r.json()
    # OpenAI shape.
    assert data["object"] == "chat.completion"
    assert data["id"].startswith("chatcmpl")
    assert data["model"] == "mock-echo"
    assert isinstance(data["choices"], list) and data["choices"]
    msg = data["choices"][0]["message"]
    assert msg["role"] == "assistant"
    assert "ping" in msg["content"]  # mock echoes the prompt
    # Usage with all three counters.
    usage = data["usage"]
    assert usage["prompt_tokens"] > 0
    assert usage["completion_tokens"] > 0
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]


def test_response_headers_present(client, auth):
    r = client.post(
        "/v1/chat/completions",
        json={"model": "mock-echo", "messages": [{"role": "user", "content": "hi"}]},
        headers=auth(),
    )
    assert r.headers["X-Cache"] == "MISS"
    assert r.headers["X-Provider"] == "mock"
    assert "X-Cost-USD" in r.headers


def test_unknown_model_404(client, auth):
    r = client.post(
        "/v1/chat/completions",
        json={"model": "no-such-model", "messages": [{"role": "user", "content": "x"}]},
        headers=auth(),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "model_not_found"


def test_model_allowlist_enforced(client, auth):
    # cheap key may only use mock-cheap.
    ok = client.post(
        "/v1/chat/completions",
        json={"model": "mock-cheap", "messages": [{"role": "user", "content": "x"}]},
        headers=auth(CHEAP_KEY),
    )
    assert ok.status_code == 200

    denied = client.post(
        "/v1/chat/completions",
        json={"model": "mock-echo", "messages": [{"role": "user", "content": "x"}]},
        headers=auth(CHEAP_KEY),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["type"] == "permission_error"
