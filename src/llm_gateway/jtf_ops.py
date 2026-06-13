"""JTF (JSON Token Format) integration — the gateway's differentiator.

Two distinct, clearly-separated capabilities:

1. **Observability (always on, non-destructive).** For every request we scan
   the prompt for JSON-shaped content and compute how many tokens JTF *would*
   save if it re-encoded that content. This number is reported in the response
   metadata and ``/admin/usage`` but the forwarded prompt is **never** altered.
   This is honest token accounting — the brand promise.

2. **Compression (opt-in, experimental).** When a client sends
   ``X-JTF-Compress: true`` we actually re-encode large, clearly-JSON message
   blocks into JTF before forwarding. This is lossless (``decode(encode(x)) ==
   x``) but the *upstream model must understand JTF*, so it is conservative and
   opt-in by design. We only touch content that is unambiguously a JSON object
   or array above a size threshold, and we wrap it so a downstream consumer can
   tell it apart.

Both paths use the vendored JTF library (``_vendor/jtf``) — zero network, zero
extra runtime dependency.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ._vendor import jtf
from .tokens import count_tokens, message_text

# Only consider JSON blocks at least this many characters long for either
# analysis or compression — tiny objects rarely beat JTF's structural overhead
# and would add noise.
_MIN_JSON_CHARS = 40

# A short marker prefix so the re-encoded block is self-describing and a
# JTF-aware consumer (or a debugging human) can recognise it.
JTF_BLOCK_PREFIX = "[[JTF/v2]]\n"


@dataclass
class JTFAnalysis:
    """Result of a non-destructive JTF savings scan over a prompt."""

    json_blocks: int = 0
    original_tokens: int = 0
    jtf_tokens: int = 0

    @property
    def saved_tokens(self) -> int:
        return max(0, self.original_tokens - self.jtf_tokens)

    @property
    def savings_ratio(self) -> float:
        if self.original_tokens <= 0:
            return 0.0
        return self.saved_tokens / self.original_tokens

    def as_dict(self) -> dict:
        return {
            "json_blocks": self.json_blocks,
            "original_json_tokens": self.original_tokens,
            "jtf_json_tokens": self.jtf_tokens,
            "potential_tokens_saved": self.saved_tokens,
            "potential_savings_ratio": round(self.savings_ratio, 4),
        }


def _iter_json_candidates(text: str):
    """Yield ``(start, end, parsed_obj)`` for top-level JSON object/array spans.

    Handles two common shapes:
      * the *entire* string is one JSON document, or
      * a JSON document is embedded in surrounding prose (we scan for the first
        balanced ``{...}`` / ``[...]`` span and try to parse it).

    This is deliberately conservative; anything that does not cleanly parse is
    skipped so we never corrupt a prompt.
    """
    stripped = text.strip()
    if len(stripped) >= _MIN_JSON_CHARS and stripped[0] in "{[":
        try:
            obj = json.loads(stripped)
            if isinstance(obj, (dict, list)):
                start = text.index(stripped[0])
                yield (start, start + len(stripped), obj)
                return
        except (json.JSONDecodeError, ValueError):
            pass

    # Embedded scan: find balanced spans starting at each { or [.
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in "{[":
            span = _balanced_span(text, i)
            if span is not None:
                candidate = text[i:span]
                if len(candidate) >= _MIN_JSON_CHARS:
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, (dict, list)):
                            yield (i, span, obj)
                            i = span
                            continue
                    except (json.JSONDecodeError, ValueError):
                        pass
        i += 1


def _balanced_span(text: str, start: int):
    """Return index just past the balanced bracket span opened at ``start``.

    Respects string literals and escapes; returns ``None`` if unbalanced.
    """
    open_ch = text[start]
    close_ch = "}" if open_ch == "{" else "]"
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
    return None


def analyze_messages(messages: list[dict]) -> JTFAnalysis:
    """Non-destructively estimate potential JTF token savings across a prompt."""
    analysis = JTFAnalysis()
    for m in messages:
        text = message_text(m.get("content"))
        if not text:
            continue
        for _start, _end, obj in _iter_json_candidates(text):
            original = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
            try:
                encoded = jtf.encode(obj)
            except Exception:
                continue
            analysis.json_blocks += 1
            analysis.original_tokens += count_tokens(original)
            analysis.jtf_tokens += count_tokens(encoded)
    return analysis


def compress_messages(messages: list[dict]) -> tuple[list[dict], JTFAnalysis]:
    """Return a *new* message list with large JSON blocks re-encoded as JTF.

    Lossless and conservative: only clearly-JSON spans above the size threshold
    are replaced, and only when JTF actually produces a shorter token count.
    The original ``messages`` list is not mutated. Also returns the realised
    :class:`JTFAnalysis` describing what was compressed.
    """
    analysis = JTFAnalysis()
    new_messages: list[dict] = []
    for m in messages:
        content = m.get("content")
        text = message_text(content)
        # Only operate on plain-string content; structured multimodal content
        # is passed through untouched to stay conservative.
        if not isinstance(content, str) or not text:
            new_messages.append(dict(m))
            continue

        rebuilt = []
        cursor = 0
        changed = False
        for start, end, obj in _iter_json_candidates(text):
            try:
                encoded = jtf.encode(obj)
            except Exception:
                continue
            orig_tok = count_tokens(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
            jtf_tok = count_tokens(encoded)
            if jtf_tok >= orig_tok:
                continue  # no win; leave as-is
            analysis.json_blocks += 1
            analysis.original_tokens += orig_tok
            analysis.jtf_tokens += jtf_tok
            rebuilt.append(text[cursor:start])
            rebuilt.append(JTF_BLOCK_PREFIX + encoded)
            cursor = end
            changed = True
        rebuilt.append(text[cursor:])

        new_m = dict(m)
        if changed:
            new_m["content"] = "".join(rebuilt)
        new_messages.append(new_m)
    return new_messages, analysis
