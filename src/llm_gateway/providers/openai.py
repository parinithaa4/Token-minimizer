"""OpenAI provider — forwards to OpenAI's ``/v1/chat/completions``.

Since the gateway speaks OpenAI's wire format natively, this adapter is a thin
pass-through: it substitutes the upstream model name, attaches the configured
upstream key, and returns the upstream JSON unchanged. No real key is needed
for tests (they use the mock provider); this path is never hit there.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..config import ProviderConfig
from ..tokens import count_prompt_tokens, count_tokens, message_text
from .base import ProviderError, ProviderResult

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider:
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
    ) -> ProviderResult:
        key = self.cfg.resolved_key()
        if not key:
            raise ProviderError(
                "OpenAI provider has no API key configured "
                "(set api_key or api_key_env)",
                status_code=500,
                provider_name=self.name,
            )

        body: dict[str, Any] = {"model": upstream_model, "messages": messages}
        for k, v in params.items():
            if v is not None:
                body[k] = v
        body.pop("stream", None)  # non-streaming gateway

        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        url = f"{self.base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=self.cfg.timeout) as client:
                resp = await client.post(url, json=body, headers=headers)
        except httpx.HTTPError as exc:  # pragma: no cover - network path
            raise ProviderError(
                f"OpenAI request failed: {exc}",
                status_code=502,
                provider_name=self.name,
            ) from exc

        if resp.status_code >= 400:  # pragma: no cover - network path
            raise ProviderError(
                f"OpenAI upstream error {resp.status_code}: {resp.text[:500]}",
                status_code=resp.status_code,
                provider_name=self.name,
            )

        data = resp.json()
        usage = data.get("usage") or {}
        prompt_tokens = int(
            usage.get("prompt_tokens", count_prompt_tokens(messages))
        )
        completion_tokens = int(
            usage.get(
                "completion_tokens",
                count_tokens(message_text(_first_message(data))),
            )
        )
        return ProviderResult(
            response=data,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


def _first_message(data: dict) -> Any:  # pragma: no cover - network path helper
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return ""
