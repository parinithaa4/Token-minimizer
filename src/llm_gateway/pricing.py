"""Pricing table and cost computation.

Prices are USD per **1,000,000 tokens** (per-Mtok), the unit most providers
publish. The seed table below uses LiteLLM-style public list prices. Entries
flagged ``"verify": True`` should be re-checked against the provider's current
price sheet before relying on them for billing — list prices change often.

The table can be refreshed from a LiteLLM-style JSON document
(``model_prices_and_context_window.json``) via :func:`load_litellm_prices`,
but this is entirely optional and never requires network access at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    """Per-Mtok input/output price for a model."""

    input_per_mtok: float
    output_per_mtok: float
    verify: bool = False
    source: str = "seed"


# Seed pricing. USD per 1M tokens. (input, output)
# Anthropic and OpenAI public list prices as of early 2026; verify before billing.
_SEED_PRICES: dict[str, ModelPrice] = {
    # Anthropic Claude (input / output, $ per Mtok)
    "claude-3-opus": ModelPrice(5.0, 25.0, source="litellm-seed"),
    "claude-opus": ModelPrice(5.0, 25.0, source="litellm-seed"),
    "claude-3-5-sonnet": ModelPrice(3.0, 15.0, source="litellm-seed"),
    "claude-sonnet": ModelPrice(3.0, 15.0, source="litellm-seed"),
    "claude-3-5-haiku": ModelPrice(1.0, 5.0, source="litellm-seed"),
    "claude-3-haiku": ModelPrice(1.0, 5.0, source="litellm-seed"),
    "claude-haiku": ModelPrice(1.0, 5.0, source="litellm-seed"),
    # OpenAI
    "gpt-4o": ModelPrice(2.5, 10.0, verify=True, source="litellm-seed"),
    "gpt-4o-mini": ModelPrice(0.15, 0.6, verify=True, source="litellm-seed"),
    "gpt-4-turbo": ModelPrice(10.0, 30.0, verify=True, source="litellm-seed"),
    # The built-in mock provider: deterministic, free-to-run, but we assign it
    # a non-zero price so cost-accounting and budget tests are meaningful.
    "mock-echo": ModelPrice(1.0, 2.0, source="mock"),
    "mock-cheap": ModelPrice(0.10, 0.20, source="mock"),
}


class PricingTable:
    """Resolves a model name to its per-token cost and computes request cost.

    Lookup is by exact match first, then by longest known prefix, so that
    versioned model ids (``claude-3-5-sonnet-20241022``) resolve to the base
    family price without needing an entry per snapshot.
    """

    def __init__(self, prices: dict[str, ModelPrice] | None = None):
        self._prices: dict[str, ModelPrice] = dict(_SEED_PRICES)
        if prices:
            self._prices.update(prices)

    def add(self, model: str, price: ModelPrice) -> None:
        self._prices[model] = price

    def get(self, model: str) -> ModelPrice | None:
        if model in self._prices:
            return self._prices[model]
        # Longest-prefix match for versioned ids.
        best: str | None = None
        for known in self._prices:
            if model.startswith(known) and (best is None or len(known) > len(best)):
                best = known
        return self._prices[best] if best else None

    def cost_usd(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """USD cost for a request. Unknown models cost ``0.0`` (logged elsewhere)."""
        price = self.get(model)
        if price is None:
            return 0.0
        return (
            prompt_tokens / 1_000_000 * price.input_per_mtok
            + completion_tokens / 1_000_000 * price.output_per_mtok
        )

    def as_dict(self) -> dict[str, dict]:
        return {
            m: {
                "input_per_mtok": p.input_per_mtok,
                "output_per_mtok": p.output_per_mtok,
                "verify": p.verify,
                "source": p.source,
            }
            for m, p in self._prices.items()
        }


def load_litellm_prices(doc: dict) -> dict[str, ModelPrice]:
    """Parse a LiteLLM-style price document into :class:`ModelPrice` entries.

    LiteLLM publishes ``input_cost_per_token`` / ``output_cost_per_token`` in
    USD **per token**; we convert to per-Mtok. This function is pure (no I/O):
    callers load the JSON themselves so refreshing prices never forces a
    network call at import or request time.
    """
    out: dict[str, ModelPrice] = {}
    for model, spec in doc.items():
        if not isinstance(spec, dict):
            continue
        inp = spec.get("input_cost_per_token")
        outp = spec.get("output_cost_per_token")
        if inp is None or outp is None:
            continue
        out[model] = ModelPrice(
            input_per_mtok=float(inp) * 1_000_000,
            output_per_mtok=float(outp) * 1_000_000,
            verify=True,
            source="litellm",
        )
    return out
