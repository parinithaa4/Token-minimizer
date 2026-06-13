"""Mock provider — deterministic, offline, free.

This is what the test suite and the zero-config first run use. It performs no
network I/O. It echoes a short, deterministic completion derived from the last
user message and reports a token ``usage`` block computed with the gateway's
deterministic estimator, so cost/budget/cache tests are fully reproducible.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from ..config import ProviderConfig
from ..tokens import count_prompt_tokens, count_tokens, message_text
from .base import ProviderResult


class MockProvider:
    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg
        self.name = cfg.name

    @staticmethod
    def _completion_text(messages: list[dict]) -> str:
        """Deterministic echo of the last user (or last) message."""
        last_user = ""
        for m in messages:
            if m.get("role") == "user":
                last_user = message_text(m.get("content"))
        if not last_user and messages:
            last_user = message_text(messages[-1].get("content"))
        snippet = last_user.strip().replace("\n", " ")
        if len(snippet) > 200:
            snippet = snippet[:200]
        return f"[mock] You said: {snippet}" if snippet else "[mock] (empty prompt)"

    async def chat(
        self,
        *,
        upstream_model: str,
        messages: list[dict],
        params: dict,
    ) -> ProviderResult:
        text = self._completion_text(messages)
        prompt_tokens = count_prompt_tokens(messages)
        completion_tokens = count_tokens(text)

        response: dict[str, Any] = {
            "id": f"chatcmpl-mock-{uuid.uuid4().hex[:20]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": upstream_model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }
        return ProviderResult(
            response=response,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
