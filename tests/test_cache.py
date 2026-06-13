"""Caching: identical request twice → 2nd is a cache hit (flagged), bills 0."""

from __future__ import annotations

from tests.conftest import DEV_KEY


def _body():
    return {
        "model": "mock-echo",
        "messages": [{"role": "user", "content": "cache me please"}],
        "temperature": 0.0,
    }


def test_second_identical_request_is_cache_hit(client, auth):
    first = client.post("/v1/chat/completions", json=_body(), headers=auth(DEV_KEY))
    assert first.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    first_cost = float(first.headers["X-Cost-USD"])
    assert first_cost > 0

    second = client.post("/v1/chat/completions", json=_body(), headers=auth(DEV_KEY))
    assert second.status_code == 200
    assert second.headers["X-Cache"] == "HIT"
    assert float(second.headers["X-Cost-USD"]) == 0.0

    # Same content returned both times.
    assert (
        first.json()["choices"][0]["message"]["content"]
        == second.json()["choices"][0]["message"]["content"]
    )
    # Body metadata also flags the hit.
    assert second.json()["usage"]["gateway"]["cache_hit"] is True


def test_cache_hit_bills_zero_and_counts_in_hit_rate(client, auth):
    client.post("/v1/chat/completions", json=_body(), headers=auth(DEV_KEY))
    client.post("/v1/chat/completions", json=_body(), headers=auth(DEV_KEY))

    rows = client.get("/admin/usage").json()["keys"]
    dev = next(r for r in rows if r["key_name"] == "dev")
    assert dev["requests"] == 2
    assert dev["cache_hits"] == 1
    assert dev["cache_hit_rate"] == 0.5
    # Only the first (miss) request was billed.
    assert dev["cost_usd"] > 0


def test_cache_can_be_disabled_per_request(client, auth):
    client.post("/v1/chat/completions", json=_body(), headers=auth(DEV_KEY))
    # X-Cache: no-store forces a fresh call (still a MISS).
    headers = {**auth(DEV_KEY), "X-Cache": "no-store"}
    r = client.post("/v1/chat/completions", json=_body(), headers=headers)
    assert r.headers["X-Cache"] == "MISS"


def test_different_params_are_separate_cache_entries(client, auth):
    a = client.post(
        "/v1/chat/completions",
        json={**_body(), "temperature": 0.1},
        headers=auth(DEV_KEY),
    )
    b = client.post(
        "/v1/chat/completions",
        json={**_body(), "temperature": 0.9},
        headers=auth(DEV_KEY),
    )
    assert a.headers["X-Cache"] == "MISS"
    assert b.headers["X-Cache"] == "MISS"  # different params => not a hit
