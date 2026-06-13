"""Budgets: exceeding spend → 402; under budget → 200 with usage decremented."""

from __future__ import annotations

from tests.conftest import DEV_KEY, TINY_KEY, TINY_TOKENS_KEY


def _body(content="hello budget"):
    return {"model": "mock-echo", "messages": [{"role": "user", "content": content}]}


def test_tiny_usd_budget_rejected_with_402(client, auth):
    r = client.post("/v1/chat/completions", json=_body(), headers=auth(TINY_KEY))
    assert r.status_code == 402
    err = r.json()["error"]
    assert err["type"] == "insufficient_quota"
    assert err["code"] == "budget_exceeded"


def test_tiny_token_budget_rejected_with_402(client, auth):
    r = client.post(
        "/v1/chat/completions", json=_body(), headers=auth(TINY_TOKENS_KEY)
    )
    assert r.status_code == 402
    assert r.json()["error"]["code"] == "budget_exceeded"


def test_under_budget_succeeds_and_decrements(client, auth):
    # First, confirm a healthy request succeeds.
    r = client.post("/v1/chat/completions", json=_body(), headers=auth(DEV_KEY))
    assert r.status_code == 200
    cost = float(r.headers["X-Cost-USD"])
    assert cost > 0

    # Budget remaining drops by exactly the recorded cost.
    usage = _usage_for(client, "dev")
    assert usage["requests"] == 1
    assert usage["cost_usd"] > 0
    assert usage["budget_remaining_usd"] == round(
        usage["budget_usd"] - usage["cost_usd"], 6
    )


def test_budget_accumulates_across_requests(client, auth):
    for _ in range(3):
        r = client.post(
            "/v1/chat/completions",
            json=_body("accumulate me uniquely " + str(_)),
            headers=auth(DEV_KEY),
        )
        assert r.status_code == 200
    usage = _usage_for(client, "dev")
    assert usage["requests"] == 3
    assert usage["total_tokens"] > 0


def _usage_for(client, key_name: str) -> dict:
    rows = client.get("/admin/usage").json()["keys"]
    for row in rows:
        if row["key_name"] == key_name:
            return row
    raise AssertionError(f"no usage row for {key_name}")
