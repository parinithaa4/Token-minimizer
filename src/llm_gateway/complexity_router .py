"""
complexity_router.py — difficulty scorer S(u) and Economy/Balanced/Frontier
tier selection, per TokenMinGate Section V (Eq. 10) and Section VII-B
(the "leans upward" safety rule).

Drop into src/llm_gateway/complexity_router.py and call from gateway.py
after prompt pruning (Algorithm 1, lines 15-17), replacing / sitting in
front of the static `routing:` config-file mapping. See INTEGRATION.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Tier(str, Enum):
    ECONOMY = "economy"
    BALANCED = "balanced"
    FRONTIER = "frontier"


# Reasoning-signal words called out in the paper text (Section V).
DEFAULT_REASONING_WORDS = {
    "derive", "evaluate", "synthesize", "prove", "optimize", "analyze",
    "compare", "justify", "critique", "design", "architect", "debug",
    "refactor", "reconcile", "diagnose",
}

# Crude instruction-count heuristic: numbered/bulleted steps or imperative
# connective words. Tune per-deployment, or replace with a real parser.
_INSTRUCTION_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:\d+[.)]|[-*\u2022])\s+|(?:\bplease\b|\bthen\b|\bnext\b)",
    re.IGNORECASE,
)

_CODE_FENCE_PATTERN = re.compile(
    r"```|`[^`\n]+`|\bdef \w+\(|\bclass \w+[:(]|;\s*$", re.MULTILINE
)


@dataclass
class ComplexityWeights:
    """w1..w4 and theta scale factors from Eq. 10."""
    w_len: float = 0.30
    w_inst: float = 0.25
    w_reason: float = 0.25
    w_code: float = 0.20

    theta_len_tokens: int = 400     # length at which the length term saturates
    theta_inst_count: int = 4       # instruction count at which that term saturates
    theta_reason_count: int = 3     # reasoning-word count at which that term saturates


@dataclass
class TierThresholds:
    economy_max: float = 0.35        # S(u) <  economy_max                -> Economy
    balanced_max: float = 0.75       # economy_max <= S(u) < balanced_max -> Balanced
    # S(u) >= balanced_max -> Frontier
    upward_lean_low: float = 0.35    # ambiguous band bumped to Balanced (Sec. VII-B)
    upward_lean_high: float = 0.40


DEFAULT_TIER_MODELS: dict[Tier, dict[str, str]] = {
    Tier.ECONOMY: {"openai": "gpt-4o-mini", "anthropic": "claude-3-5-haiku"},
    Tier.BALANCED: {"openai": "gpt-4o", "anthropic": "claude-3-5-sonnet"},
    Tier.FRONTIER: {"openai": "o1", "anthropic": "claude-3-opus"},
}


def _rough_token_count(text: str) -> int:
    # Cheap stand-in for a real tokenizer; swap in tiktoken / Anthropic's
    # counter if Eq. 10's |u|_tok needs to be exact.
    return max(1, len(text) // 4)


def _count_instructions(text: str) -> int:
    return len(_INSTRUCTION_PATTERN.findall(text))


def _count_reasoning_words(text: str, vocab: set[str]) -> int:
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return sum(1 for w in words if w in vocab)


def _has_code(text: str) -> bool:
    return bool(_CODE_FENCE_PATTERN.search(text))


def complexity_score(
    prompt: str,
    weights: ComplexityWeights = ComplexityWeights(),
    reasoning_vocab: set[str] = None,
) -> float:
    """S(u) -- Eq. 10."""
    reasoning_vocab = reasoning_vocab or DEFAULT_REASONING_WORDS

    tok_len = _rough_token_count(prompt)
    n_inst = _count_instructions(prompt)
    n_reason = _count_reasoning_words(prompt, reasoning_vocab)
    has_code = _has_code(prompt)

    term_len = weights.w_len * min(1.0, tok_len / weights.theta_len_tokens)
    term_inst = weights.w_inst * min(1.0, n_inst / weights.theta_inst_count)
    term_reason = weights.w_reason * min(1.0, n_reason / weights.theta_reason_count)
    term_code = weights.w_code * (1.0 if has_code else 0.0)

    return term_len + term_inst + term_reason + term_code


def select_tier(
    prompt: str,
    weights: ComplexityWeights = ComplexityWeights(),
    thresholds: TierThresholds = TierThresholds(),
    reasoning_vocab: set[str] = None,
) -> tuple[Tier, float]:
    """
    Returns (tier, score). Implements Section VII-B's safety rule: ambiguous
    scores get bumped to Balanced, and prompts with code or reasoning-heavy
    language skip Economy entirely.
    """
    reasoning_vocab = reasoning_vocab or DEFAULT_REASONING_WORDS
    score = complexity_score(prompt, weights, reasoning_vocab)

    has_code = _has_code(prompt)
    n_reason = _count_reasoning_words(prompt, reasoning_vocab)

    if thresholds.upward_lean_low <= score < thresholds.upward_lean_high:
        return Tier.BALANCED, score

    if score < thresholds.economy_max:
        if has_code or n_reason > 0:
            return Tier.BALANCED, score  # skip Economy per Sec. VII-B
        return Tier.ECONOMY, score

    if score < thresholds.balanced_max:
        return Tier.BALANCED, score

    return Tier.FRONTIER, score


class ComplexityRouter:
    """Stateful wrapper you can hand a request straight to from gateway.py."""

    def __init__(
        self,
        weights: ComplexityWeights = None,
        thresholds: TierThresholds = None,
        tier_models: dict[Tier, dict[str, str]] = None,
        reasoning_vocab: set[str] = None,
    ) -> None:
        self.weights = weights or ComplexityWeights()
        self.thresholds = thresholds or TierThresholds()
        self.tier_models = tier_models or DEFAULT_TIER_MODELS
        self.reasoning_vocab = reasoning_vocab or DEFAULT_REASONING_WORDS

    def route(self, prompt: str, provider_family: str = "anthropic") -> dict:
        tier, score = select_tier(prompt, self.weights, self.thresholds, self.reasoning_vocab)
        model = self.tier_models[tier].get(provider_family)
        if model is None:
            raise ValueError(f"No model configured for tier={tier} provider={provider_family}")
        return {"tier": tier.value, "score": round(score, 4), "model": model}