"""Research metrics for TokenMinGate experiments."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RequestRecord:
    """Measured or simulated request-level benchmark record."""

    input_tokens: int
    output_tokens: int

    pruned_input_tokens: int

    tier: str

    was_cache_hit: bool
    was_wrong_cache_hit: bool = False

    price_in_per_mtok: float = 0.0
    price_out_per_mtok: float = 0.0

    frontier_price_in_per_mtok: float = 0.0
    frontier_price_out_per_mtok: float = 0.0

    latency_ms: float = 0.0

    semantic_similarity: float | None = None
    semantic_threshold: float | None = None


def hit_rate(records: list[RequestRecord]) -> float:
    if not records:
        return 0.0

    return sum(
        r.was_cache_hit
        for r in records
    ) / len(records)


def l2_share_and_precision(
    records: list[RequestRecord],
) -> tuple[float, float]:
    l2_hits = [
        r for r in records
        if r.was_cache_hit and r.tier == "l2"
    ]

    if not records:
        return 0.0, 1.0

    rho = len(l2_hits) / len(records)

    if not l2_hits:
        return rho, 1.0

    correct = sum(
        not r.was_wrong_cache_hit
        for r in l2_hits
    )

    return rho, correct / len(l2_hits)


def token_reduction_ratio(
    records: list[RequestRecord],
) -> float:
    """TRR.

    Baseline:
        original input + output

    Gateway:
        zero tokens for cache hits
        otherwise pruned input + output
    """

    baseline = sum(
        r.input_tokens + r.output_tokens
        for r in records
    )

    if baseline <= 0:
        return 0.0

    gateway_tokens = sum(
        0
        if r.was_cache_hit
        else r.pruned_input_tokens + r.output_tokens
        for r in records
    )

    return max(
        0.0,
        (baseline - gateway_tokens) / baseline,
    )


def token_reduction_ratio_net_exact(
    records: list[RequestRecord],
) -> float:
    """Size-aware TRRnet.

    Incorrect semantic-cache hits are charged again because the original
    request must be recomputed.
    """

    baseline = sum(
        r.input_tokens + r.output_tokens
        for r in records
    )

    if baseline <= 0:
        return 0.0

    raw_saved = baseline * token_reduction_ratio(records)

    wrong_hit_cost = sum(
        r.input_tokens + r.output_tokens
        for r in records
        if (
            r.was_cache_hit
            and r.tier == "l2"
            and r.was_wrong_cache_hit
        )
    )

    return max(
        0.0,
        (raw_saved - wrong_hit_cost) / baseline,
    )


def delta_cost(
    records: list[RequestRecord],
) -> tuple[float, float, float]:
    """Return baseline cost, TokenMinGate cost, and reduction fraction."""

    baseline_cost = 0.0
    gateway_cost = 0.0

    for r in records:
        baseline_cost += (
            r.input_tokens
            * r.frontier_price_in_per_mtok
            + r.output_tokens
            * r.frontier_price_out_per_mtok
        ) / 1_000_000

        if r.was_cache_hit:
            continue

        gateway_cost += (
            r.pruned_input_tokens
            * r.price_in_per_mtok
            + r.output_tokens
            * r.price_out_per_mtok
        ) / 1_000_000

    if baseline_cost <= 0:
        return 0.0, gateway_cost, 0.0

    reduction = (
        baseline_cost - gateway_cost
    ) / baseline_cost

    return baseline_cost, gateway_cost, reduction


def summarize(
    records: list[RequestRecord],
) -> dict:
    if not records:
        return {
            "n_requests": 0,
            "hit_rate": 0.0,
            "l2_share_rho": 0.0,
            "l2_precision_P": 1.0,
            "TRR_pct": 0.0,
            "TRRnet_pct": 0.0,
            "avg_tokens_per_req": 0.0,
            "avg_latency_ms": 0.0,
            "cost_base_usd": 0.0,
            "cost_tmg_usd": 0.0,
            "delta_C_pct": 0.0,
        }

    hit = hit_rate(records)

    rho, precision = l2_share_and_precision(
        records
    )

    trr = token_reduction_ratio(records)

    trr_net = token_reduction_ratio_net_exact(
        records
    )

    base_cost, gateway_cost, delta_c = delta_cost(
        records
    )

    avg_tokens = sum(
        (
            0
            if r.was_cache_hit
            else r.pruned_input_tokens + r.output_tokens
        )
        for r in records
    ) / len(records)

    avg_latency = sum(
        r.latency_ms
        for r in records
    ) / len(records)

    return {
        "n_requests": len(records),
        "hit_rate": round(hit, 4),
        "l2_share_rho": round(rho, 4),
        "l2_precision_P": round(precision, 4),
        "TRR_pct": round(trr * 100, 2),
        "TRRnet_pct": round(trr_net * 100, 2),
        "avg_tokens_per_req": round(avg_tokens, 1),
        "avg_latency_ms": round(avg_latency, 2),
        "cost_base_usd": round(base_cost, 6),
        "cost_tmg_usd": round(gateway_cost, 6),
        "delta_C_pct": round(delta_c * 100, 2),
    }