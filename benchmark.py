"""
benchmark.py — reproduces a paper-style Table I / III report against
synthetic traffic that mimics TokenMinGate's test mix (paraphrase clusters,
common/rare questions, a code-and-reasoning tail).

This uses synthetic prompts so it runs with no API keys and no network,
matching the repo's existing "no real keys, no network" testing philosophy.
Swap `generate_traffic()` for a reader over your real request_log table to
benchmark on live traffic instead.

Usage:
    pip install faiss-cpu sentence-transformers numpy
    python benchmark.py --n 10000 --tau 0.84
"""

from __future__ import annotations

import argparse
import random
import time

from llm_gateway.semantic_cache import SemanticCache
from llm_gateway.complexity_router import ComplexityRouter
from llm_gateway.namespace import namespace_for_request, normalize_prompt
from llm_gateway.metrics import RequestRecord, summarize


BASE_QUESTIONS = [
    "How do I reset my VPN password?",
    "What is our refund policy for enterprise customers?",
    "Summarize the Q3 revenue report in two sentences.",
    "Write a Python function to parse a CSV file and return a dict.",
    "Explain why the staging build is failing on deploy.",
    "Sort these support tickets by priority: urgent, low, medium.",
    "Derive the time complexity of merge sort and justify each step.",
    "Fix the formatting on this JSON payload.",
    "What time zone is the EMEA standup in?",
    "Evaluate whether we should migrate from REST to GraphQL, with pros and cons.",
]

PARAPHRASE_TEMPLATES = [
    "{q}",
    "Quick question -- {q_lower}",
    "{q} Thanks!",
    "Can you tell me: {q_lower}",
    "re: {q}",
]

PRICES = {
    "economy": (0.15, 0.60),
    "balanced": (2.50, 10.00),
    "frontier": (3.00, 12.00),
}


def _paraphrase(q: str) -> str:
    tmpl = random.choice(PARAPHRASE_TEMPLATES)
    return tmpl.format(q=q, q_lower=q[0].lower() + q[1:])


def generate_traffic(n: int) -> list[str]:
    """Mirrors the paper's traffic mix: mostly paraphrases of a small
    question pool, so an exact-match cache misses often but a semantic
    cache catches most of them."""
    return [_paraphrase(random.choice(BASE_QUESTIONS)) for _ in range(n)]


def run_benchmark(n: int, tau: float, provider_family: str = "anthropic") -> dict:
    cache = SemanticCache(base_threshold=tau, default_ttl_seconds=7 * 24 * 3600)
    router = ComplexityRouter()
    frontier_price = PRICES["frontier"]

    namespace = namespace_for_request(
        team_id="bench-team", system_prompt="", provider_family=provider_family, temperature=0.7,
    )

    records: list[RequestRecord] = []
    prompts = generate_traffic(n)

    for prompt in prompts:
        norm = normalize_prompt(prompt)
        input_tokens = max(8, len(prompt) // 4)
        output_tokens = random.randint(40, 400)

        hit = cache.lookup(namespace, norm)
        if hit is not None:
            # Simulate the paper's observed precision P at this tau
            # (P ~= 0.98 at tau=0.84, P ~= 0.81 at tau=0.70; see Table II).
            p_correct = 0.982 if tau >= 0.84 else max(0.81, 0.5 + tau / 2)
            wrong = random.random() > p_correct
            records.append(RequestRecord(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                pruned_input_tokens=0,
                tier="l2",
                was_cache_hit=True,
                was_wrong_cache_hit=wrong,
                frontier_price_in_per_mtok=frontier_price[0],
                frontier_price_out_per_mtok=frontier_price[1],
            ))
            continue

        route = router.route(prompt, provider_family=provider_family)
        pruned_tokens = int(input_tokens * random.uniform(0.7, 0.95))  # pruning shaves ~5-30%
        price_in, price_out = PRICES[route["tier"]]

        records.append(RequestRecord(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            pruned_input_tokens=pruned_tokens,
            tier=route["tier"],
            was_cache_hit=False,
            price_in_per_mtok=price_in,
            price_out_per_mtok=price_out,
            frontier_price_in_per_mtok=frontier_price[0],
            frontier_price_out_per_mtok=frontier_price[1],
        ))

        cache.admit(
            namespace, norm,
            response={"text": "..."},
            tokens_saved_if_hit=input_tokens + output_tokens,
        )

    return summarize(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=10_000)
    parser.add_argument("--tau", type=float, default=0.84)
    parser.add_argument("--provider", type=str, default="anthropic")
    args = parser.parse_args()

    random.seed(7)
    t0 = time.time()
    report = run_benchmark(args.n, args.tau, args.provider)
    elapsed = time.time() - t0

    print(f"\nBenchmark: n={args.n}  tau={args.tau}  provider={args.provider}  (ran in {elapsed:.1f}s)\n")
    for k, v in report.items():
        print(f"  {k:22s} {v}")