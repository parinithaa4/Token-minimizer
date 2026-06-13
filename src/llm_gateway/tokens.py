"""Token estimation utilities.

The gateway always *prefers* a provider's reported ``usage`` for billing. This
module provides a deterministic fallback estimator (used by the mock provider
and for pre-flight JTF savings analysis) so that token math is reproducible
without a real tokenizer installed.

If ``tiktoken`` happens to be available it is used for a more accurate count,
but it is never required — tests run without it.
"""

from __future__ import annotations

from typing import Any

_TIKTOKEN_ENC = None
_TIKTOKEN_TRIED = False


def _try_tiktoken():
    global _TIKTOKEN_ENC, _TIKTOKEN_TRIED
    if not _TIKTOKEN_TRIED:
        _TIKTOKEN_TRIED = True
        try:  # pragma: no cover - environment dependent
            import tiktoken

            _TIKTOKEN_ENC = tiktoken.get_encoding("cl100k_base")
        except Exception:  # pragma: no cover
            _TIKTOKEN_ENC = None
    return _TIKTOKEN_ENC


def count_tokens(text: str) -> int:
    """Estimate the token count of ``text``.

    Uses ``tiktoken`` when present; otherwise a deterministic heuristic of
    ``ceil(len / 4)`` (the widely used "~4 chars per token" rule), with a
    floor of 1 for non-empty strings.
    """
    if not text:
        return 0
    enc = _try_tiktoken()
    if enc is not None:  # pragma: no cover - environment dependent
        return len(enc.encode(text))
    return max(1, (len(text) + 3) // 4)


def message_text(content: Any) -> str:
    """Flatten an OpenAI message ``content`` (str or content-part list) to text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                if isinstance(part.get("text"), str):
                    parts.append(part["text"])
                elif isinstance(part.get("content"), str):
                    parts.append(part["content"])
            elif isinstance(part, str):
                parts.append(part)
        return "\n".join(parts)
    return str(content)


def count_prompt_tokens(messages: list[dict]) -> int:
    """Estimate prompt tokens for a list of chat messages.

    Adds a small per-message overhead (~4 tokens) approximating the role and
    delimiter tokens OpenAI's tokenizers add per message.
    """
    total = 0
    for m in messages:
        total += 4
        total += count_tokens(message_text(m.get("content")))
        if m.get("name"):
            total += 1
    return total + 2  # priming tokens
