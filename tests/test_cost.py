"""Cost accounting: per-key usage recorded as tokens × price."""

from __future__ import annotations

from llm_gateway.pricing import ModelPrice, PricingTable
from tests.conftest import DEV_KEY


def test_pricing_math_per_mtok():
    pt = PricingTable()
    # mock-echo seeded at $1/Mtok input, $2/Mtok output.
    cost = pt.cost_usd("mock-echo", prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert cost == 3.0  # 1*1 + 1*2


def test_pricing_prefix_match_for_versioned_ids():
    pt = PricingTable()
    base = pt.get("claude-3-5-sonnet")
    versioned = pt.get("claude-3-5-sonnet-20241022")
    assert versioned == base


def test_litellm_loader_converts_per_token_to_per_mtok():
    from llm_gateway.pricing import load_litellm_prices

    doc = {
        "some-model": {
            "input_cost_per_token": 0.000002,  # $2 / Mtok
            "output_cost_per_token": 0.000006,  # $6 / Mtok
        }
    }
    prices = load_litellm_prices(doc)
    p: ModelPrice = prices["some-model"]
    assert round(p.input_per_mtok, 6) == 2.0
    assert round(p.output_per_mtok, 6) == 6.0


def test_recorded_cost_matches_pricing(client, auth):
    r = client.post(
        "/v1/chat/completions",
        json={"model": "mock-echo", "messages": [{"role": "user", "content": "cost check"}]},
        headers=auth(DEV_KEY),
    )
    assert r.status_code == 200
    usage = r.json()["usage"]
    pt = PricingTable()
    expected = pt.cost_usd(
        "mock-echo", usage["prompt_tokens"], usage["completion_tokens"]
    )
    # Header, body metadata, and admin usage all agree.
    assert float(r.headers["X-Cost-USD"]) == round(expected, 8)
    assert usage["gateway"]["cost_usd"] == round(expected, 8)

    rows = client.get("/admin/usage").json()["keys"]
    dev = next(row for row in rows if row["key_name"] == "dev")
    assert dev["cost_usd"] == round(expected, 6)
    assert dev["prompt_tokens"] == usage["prompt_tokens"]
    assert dev["completion_tokens"] == usage["completion_tokens"]


def test_unknown_model_price_is_zero():
    pt = PricingTable()
    assert pt.cost_usd("totally-unknown-xyz", 1000, 1000) == 0.0
