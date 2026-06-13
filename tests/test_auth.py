"""Auth: missing/invalid key → 401; valid key works."""

from __future__ import annotations

from tests.conftest import DEV_KEY


def _chat_body():
    return {
        "model": "mock-echo",
        "messages": [{"role": "user", "content": "hello"}],
    }


def test_missing_key_returns_401(client):
    r = client.post("/v1/chat/completions", json=_chat_body())
    assert r.status_code == 401
    err = r.json()["error"]
    assert err["type"] == "authentication_error"


def test_malformed_header_returns_401(client):
    r = client.post(
        "/v1/chat/completions",
        json=_chat_body(),
        headers={"Authorization": "Token abc"},
    )
    assert r.status_code == 401


def test_invalid_key_returns_401(client):
    r = client.post(
        "/v1/chat/completions",
        json=_chat_body(),
        headers={"Authorization": "Bearer sk-not-a-real-key"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_api_key"


def test_valid_key_works(client, auth):
    r = client.post("/v1/chat/completions", json=_chat_body(), headers=auth(DEV_KEY))
    assert r.status_code == 200


def test_models_endpoint_requires_key(client, auth):
    assert client.get("/v1/models").status_code == 401
    r = client.get("/v1/models", headers=auth())
    assert r.status_code == 200
    ids = {m["id"] for m in r.json()["data"]}
    assert {"mock-echo", "mock-cheap"} <= ids
