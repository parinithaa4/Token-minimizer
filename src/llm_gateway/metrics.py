"""
metrics.py — TRR, TRRnet and delta-C savings measures (paper Section IV).

Pure functions over per-request records, so you can compute them either
live (streaming aggregation in gateway.py) or offline (reading the SQLite
request_log for a report / paper-reproduction script). Drop into
src/llm_gateway/metrics.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RequestRecord:
    """One logged request -- enough to reconstruct the paper's metrics."""
    input_tokens: int          # a_i  (tokens of the ORIGINAL, unpruned prompt)
    output_tokens: int         # b_i
    pruned_input_tokens: int   # a_i^pr -- after prompt shortening (0 for cache hits)
    tier: str                  # "l1", "l2", "economy", "balanced", "frontier"
    was_cache_hit: bool
    was_wrong_cache_hit: bool = False  # judged incorrect on review / forced a retry
    price_in_per_mtok: float = 0.0     # price actually paid, per 1M input tokens
    price_out_per_mtok: float = 0.0
    frontier_price_in_per_mtok: float = 0.0   # "send everything to frontier" baseline
    frontier_price_out_per_mtok: float = 0.0


def token_reduction_ratio(records: list[RequestRecord]) -> float:
    """TRR -- Eq. 5."""
    t0 = sum(r.input_tokens + r.output_tokens for r in records)
    if t0 == 0:
        return 0.0
    t1 = sum(
        (0 if r.was_cache_hit else r.pruned_input_tokens + r.output_tokens)
        for r in records
    )
    return (t0 - t1) / t0


def hit_rate(records: list[RequestRecord]) -> float:
    if not records:
        return 0.0
    return sum(1 for r in records if r.was_cache_hit) / len(records)


def l2_share_and_precision(records: list[RequestRecord]) -> tuple[float, float]:
    """rho (share of requests answered by L2) and P (precision of those hits)."""
    l2_hits = [r for r in records if r.was_cache_hit and r.tier == "l2"]
    if not records:
        return 0.0, 1.0
    rho = len(l2_hits) / len(records)
    if not l2_hits:
        return rho, 1.0
    correct = sum(1 for r in l2_hits if not r.was_wrong_cache_hit)
    precision = correct / len(l2_hits)
    return rho, precision


def token_reduction_ratio_net(records: list[RequestRecord]) -> float:
    """
    TRRnet ~= H - rho*(1-P)  -- Eq. 6 (approximation for uniform request size).
    """
    H = hit_rate(records)
    rho, P = l2_share_and_precision(records)
    return H - rho * (1.0 - P)


def token_reduction_ratio_net_exact(records: list[RequestRecord]) -> float:
    """
    Size-aware TRRnet: subtracts the full (input+output) token cost of every
    wrong L2 hit, since the user has to redo that request from scratch.
    More accurate than Eq. 6 when request sizes vary a lot.
    """
    t0 = sum(r.input_tokens + r.output_tokens for r in records)
    if t0 == 0:
        return 0.0
    wrong_hit_cost = sum(
        (r.input_tokens + r.output_tokens) for r in records
        if r.was_cache_hit and r.tier == "l2" and r.was_wrong_cache_hit
    )
    raw_saved = t0 * token_reduction_ratio(records)
    net_saved = raw_saved - wrong_hit_cost
    return max(0.0, net_saved / t0)


def delta_cost(records: list[RequestRecord]) -> tuple[float, float, float]:
    """
    Delta-C -- Eq. 9. Returns (C_base, C_tmg, delta_c_fraction).
    C_base: cost if every request had gone to the frontier tier.
    C_tmg:  actual cost paid (cache hits cost $0).
    """
    c_base = 0.0
    c_tmg = 0.0
    for r in records:
        c_base += (
            r.input_tokens * r.frontier_price_in_per_mtok
            + r.output_tokens * r.frontier_price_out_per_mtok
        ) / 1_000_000

        if r.was_cache_hit:
            continue
        c_tmg += (
            r.pruned_input_tokens * r.price_in_per_mtok
            + r.output_tokens * r.price_out_per_mtok
        ) / 1_000_000

    if c_base == 0:
        return c_base, c_tmg, 0.0
    return c_base, c_tmg, (c_base - c_tmg) / c_base


def summarize(records: list[RequestRecord]) -> dict:
    """One-shot report matching the shape of the paper's Table I / III."""
    H = hit_rate(records)
    rho, P = l2_share_and_precision(records)
    trr = token_reduction_ratio(records)
    trr_net = token_reduction_ratio_net_exact(records)
    c_base, c_tmg, dc = delta_cost(records)
    avg_tokens = (
        sum(
            (r.pruned_input_tokens + r.output_tokens) if not r.was_cache_hit else 0
            for r in records
        ) / len(records)
    ) if records else 0.0

    return {
        "n_requests": len(records),
        "hit_rate": round(H, 4),
        "l2_share_rho": round(rho, 4),
        "l2_precision_P": round(P, 4),
        "TRR_pct": round(trr * 100, 2),
        "TRRnet_pct": round(trr_net * 100, 2),
        "avg_tokens_per_req": round(avg_tokens, 1),
        "cost_base_usd": round(c_base, 4),
        "cost_tmg_usd": round(c_tmg, 4),
        "delta_C_pct": round(dc * 100, 2),
    }