"""Ollama provider — local, self-hosted models (optional).

Ollama exposes an OpenAI-compatible endpoint at ``/v1/chat/completions`` on
``http://localhost:11434`` by default, so this adapter is a thin pass-through
much like the OpenAI one — no API key needed. Included to demonstrate the
"bring your own self-hosted model" story; not exercised by the test suite.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..config import ProviderConfig
from ..tokens import count_prompt_tokens, count_tokens, message_text
from .base import ProviderError, ProviderResult

DEFAULT_BASE_URL = "http://localhost:11434/v1"


class OllamaProvider:
    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg
        self.name = cfg.name
        self.base_url = (cfg.base_url or DEFAULT_BASE_URL).rstrip("/")

    async def chat(
        self,
        *,
        upstream_model: str,
        messages: list[dict],
        params: dict,
    ) -> ProviderResult:  # pragma: no cover - requires a local Ollama
        body: dict[str, Any] = {
            "model": upstream_model,
            "messages": messages,
            "stream": False,
        }
        for k, v in params.items():
            if v is not None and k != "stream":
                body[k] = v

        url = f"{self.base_url}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=self.cfg.timeout) as client:
                resp = await client.post(url, json=body)
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Ollama request failed: {exc}",
                status_code=502,
                provider_name=self.name,
            ) from exc

        if resp.status_code >= 400:
            raise ProviderError(
                f"Ollama upstream error {resp.status_code}: {resp.text[:500]}",
                status_code=resp.status_code,
                provider_name=self.name,
            )

        data = resp.json()
        usage = data.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens", count_prompt_tokens(messages)))
        completion_tokens = int(
            usage.get(
                "completion_tokens",
                count_tokens(
                    message_text(
                        (data.get("choices") or [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                ),
            )
        )
        return ProviderResult(
            response=data,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
