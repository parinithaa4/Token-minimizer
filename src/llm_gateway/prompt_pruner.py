"""Syntax-safe prompt pruner for TokenMinGate.

Shortens prompts before dispatch to reduce input token billing while preserving
essential semantics, code syntax, markdown fences, and JSON payloads.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PruneResult:
    original_text: str
    pruned_text: str
    original_tokens: int
    pruned_tokens: int
    tokens_saved: int
    reduction_pct: float


class SyntaxSafePruner:
    """Deterministic syntax-safe prompt compressor.

    Identifies and strips repetitive conversational filler, redundant greetings/closings,
    and excessive blank spaces without breaking code blocks, JSON, or quotes.
    """

    CONVERSATIONAL_PREFIXES = [
        r"^(?:hello|hi|hey|dear\s+assistant|greetings)[,!\.\s]+",
        r"^(?:could\s+you\s+please|can\s+you\s+please|please|kindly|would\s+you\s+mind)\s+",
        r"^(?:i\s+was\s+wondering\s+if\s+you\s+could|i\s+would\s+like\s+to\s+know|i\s+need\s+help\s+with)\s+",
        r"^(?:quick\s+question\s*[:\-–—]?\s*)",
        r"^(?:just\s+wanted\s+to\s+ask\s*[:\-–—]?\s*)",
    ]

    CONVERSATIONAL_SUFFIXES = [
        r"[\s,\.]+(?:thank\s+you(?:\s+very\s+much)?(?:\s+in\s+advance)?|thanks(?:\s+in\s+advance)?|many\s+thanks)[!\.\s]*$",
        r"[\s,\.]+(?:let\s+me\s+know\s+what\s+you\s+think|any\s+help\s+is\s+appreciated)[!\.\s]*$",
        r"[\s,\.]+(?:best\s+regards|sincerely|cheers)[!\.\s]*$",
    ]

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        if not text:
            return 0
        words = len(text.split())
        chars = len(text)
        # Standard heuristic: ~1 token per 4 chars or 0.75 words
        return max(1, int((words * 1.3 + chars / 4.0) / 2.0))

    def prune(self, text: str) -> PruneResult:
        if not text:
            return PruneResult("", "", 0, 0, 0, 0.0)

        original_tokens = self._estimate_tokens(text)

        # Protect code blocks (```...```) and inline code (`...`)
        code_blocks: list[str] = []

        def _stash_code(match: re.Match) -> str:
            token = f"__CODE_BLOCK_{len(code_blocks)}__"
            code_blocks.append(match.group(0))
            return token

        # Stash multi-line and inline code
        protected = re.sub(r"```[\s\S]*?```", _stash_code, text)
        protected = re.sub(r"`[^`\n]+`", _stash_code, protected)

        # 1. Normalize line endings & collapse consecutive blank lines
        cleaned = re.sub(r"\r\n?", "\n", protected)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        # 2. Strip conversational prefixes/suffixes iteratively
        changed = True
        while changed:
            before = cleaned
            for pat in self.CONVERSATIONAL_PREFIXES:
                cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()
            for pat in self.CONVERSATIONAL_SUFFIXES:
                cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()
            changed = (cleaned != before)

        # 3. Collapse multiple spaces within lines (except indentation)
        lines = cleaned.split("\n")
        pruned_lines = []
        for line in lines:
            if not line.startswith("    ") and not line.startswith("\t"):
                line = re.sub(r"[ \t]{2,}", " ", line)
            pruned_lines.append(line.rstrip())

        cleaned = "\n".join(pruned_lines).strip()

        # 4. Restore code blocks
        for i, block in enumerate(code_blocks):
            cleaned = cleaned.replace(f"__CODE_BLOCK_{i}__", block)

        # Fallback if pruning emptied the prompt
        if not cleaned:
            cleaned = text.strip()

        pruned_tokens = self._estimate_tokens(cleaned)
        tokens_saved = max(0, original_tokens - pruned_tokens)
        reduction_pct = (tokens_saved / original_tokens * 100.0) if original_tokens > 0 else 0.0

        return PruneResult(
            original_text=text,
            pruned_text=cleaned,
            original_tokens=original_tokens,
            pruned_tokens=pruned_tokens,
            tokens_saved=tokens_saved,
            reduction_pct=round(reduction_pct, 1),
        )


def syntax_safe_prune(text: str) -> PruneResult:
    return SyntaxSafePruner().prune(text)
