"""Deterministic request-complexity scoring and model-tier routing.

This is intentionally heuristic rather than an ML classifier. It implements
the baseline complexity score used by TokenMinGate:

S(u) =
    w1 * length_signal
  + w2 * instruction_signal
  + w3 * reasoning_signal
  + w4 * code_signal

Tiers:
    Economy   : S < 0.35
    Balanced  : 0.35 <= S < 0.75
    Frontier  : S >= 0.75
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ComplexityResult:
    score: float
    tier: str
    length_signal: float
    instruction_signal: float
    reasoning_signal: float
    code_signal: float


class ComplexityRouter:
    """Deterministic complexity router.

    The router does not call an LLM and does not claim to measure intelligence.
    It provides a reproducible routing heuristic for experiments.
    """

    def __init__(
        self,
        *,
        length_threshold: int = 500,
        instruction_threshold: int = 5,
        reasoning_threshold: int = 3,
        w_length: float = 0.25,
        w_instruction: float = 0.20,
        w_reasoning: float = 0.35,
        w_code: float = 0.20,
    ) -> None:
        weights = (
            w_length,
            w_instruction,
            w_reasoning,
            w_code,
        )

        if any(w < 0 for w in weights):
            raise ValueError("complexity weights must be non-negative")

        total = sum(weights)
        if total <= 0:
            raise ValueError("complexity weights must sum to > 0")

        self.length_threshold = max(1, length_threshold)
        self.instruction_threshold = max(1, instruction_threshold)
        self.reasoning_threshold = max(1, reasoning_threshold)

        self.w_length = w_length / total
        self.w_instruction = w_instruction / total
        self.w_reasoning = w_reasoning / total
        self.w_code = w_code / total

    @staticmethod
    def _count_instructions(text: str) -> int:
        patterns = [
            r"\bwrite\b",
            r"\bcreate\b",
            r"\bbuild\b",
            r"\bimplement\b",
            r"\bcalculate\b",
            r"\bcompare\b",
            r"\banalyze\b",
            r"\bexplain\b",
            r"\bderive\b",
            r"\bfix\b",
            r"\bdebug\b",
            r"\bsummarize\b",
            r"\bevaluate\b",
            r"\bdesign\b",
            r"\bconvert\b",
            r"\bextract\b",
        ]

        return sum(len(re.findall(pattern, text)) for pattern in patterns)

    @staticmethod
    def _count_reasoning_signals(text: str) -> int:
        patterns = [
            r"\bwhy\b",
            r"\bjustify\b",
            r"\bderive\b",
            r"\bprove\b",
            r"\breason\b",
            r"\banalyze\b",
            r"\bevaluate\b",
            r"\btrade[- ]?off\b",
            r"\bpros and cons\b",
            r"\bstep[- ]by[- ]step\b",
            r"\bcomplexity\b",
            r"\bcompare\b",
            r"\bimplications?\b",
        ]

        return sum(len(re.findall(pattern, text)) for pattern in patterns)

    @staticmethod
    def _code_signal(text: str) -> float:
        code_patterns = [
            r"```",
            r"\bpython\b",
            r"\bjavascript\b",
            r"\btypescript\b",
            r"\bjava\b",
            r"\bc\+\+\b",
            r"\bsql\b",
            r"\bfunction\b",
            r"\bclass\b",
            r"\bapi\b",
            r"\bregex\b",
            r"\bjson\b",
            r"\bstack trace\b",
            r"\bexception\b",
            r"\bcompile\b",
            r"\bdebug\b",
        ]

        hits = sum(bool(re.search(pattern, text, re.IGNORECASE))
                   for pattern in code_patterns)

        return min(1.0, hits / 3.0)

    def score(self, prompt: str) -> ComplexityResult:
        text = prompt.strip()
        words = len(re.findall(r"\S+", text))

        length_signal = min(1.0, words / self.length_threshold)

        instruction_count = self._count_instructions(text)
        instruction_signal = min(
            1.0,
            instruction_count / self.instruction_threshold,
        )

        reasoning_count = self._count_reasoning_signals(text)
        reasoning_signal = min(
            1.0,
            reasoning_count / self.reasoning_threshold,
        )

        code_signal = self._code_signal(text)

        score = (
            self.w_length * length_signal
            + self.w_instruction * instruction_signal
            + self.w_reasoning * reasoning_signal
            + self.w_code * code_signal
        )

        score = max(0.0, min(1.0, score))

        if score < 0.35:
            tier = "economy"
        elif score < 0.75:
            tier = "balanced"
        else:
            tier = "frontier"

        return ComplexityResult(
            score=round(score, 6),
            tier=tier,
            length_signal=round(length_signal, 6),
            instruction_signal=round(instruction_signal, 6),
            reasoning_signal=round(reasoning_signal, 6),
            code_signal=round(code_signal, 6),
        )

    def route(
        self,
        prompt: str,
        *,
        provider_family: str = "default",
        models: dict[str, str] | None = None,
    ) -> dict:
        result = self.score(prompt)

        return {
            "score": result.score,
            "tier": result.tier,
            "provider_family": provider_family,
            "model": (models or {}).get(result.tier),
            "signals": {
                "length": result.length_signal,
                "instruction": result.instruction_signal,
                "reasoning": result.reasoning_signal,
                "code": result.code_signal,
            },
        }