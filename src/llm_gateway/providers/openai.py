"""OpenAI provider — forwards to OpenAI's ``/v1/chat/completions``.

Since the gateway speaks OpenAI's wire format natively, this adapter is a thin
pass-through: it substitutes the upstream model name, attaches the configured
upstream key, and returns the upstream JSON unchanged. No real key is needed
for tests (they use the mock provider); this path is never hit there.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..config import ProviderConfig
from ..tokens import count_prompt_tokens, count_tokens, message_text
from .base import ProviderError, ProviderResult, StreamChunk

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
        base = (self.base_url or "https://api.openai.com/v1").rstrip("/")
        url = f"{base}/chat/completions"

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

    async def stream_chat(  # pragma: no cover - network path
        self,
        *,
        upstream_model: str,
        messages: list[dict],
        params: dict,
    ) -> AsyncIterator[StreamChunk]:
        """Stream OpenAI's native SSE and re-emit normalized chunks.

        OpenAI already speaks the chunk shape we want, so this is a thin
        translation: parse each ``data:`` line, lift ``choices[].delta.content``
        and the terminal ``finish_reason``. ``stream_options.include_usage`` asks
        the upstream to send a final usage frame; if absent we estimate.
        """
        key = self.cfg.resolved_key()
        if not key:
            raise ProviderError(
                "OpenAI provider has no API key configured "
                "(set api_key or api_key_env)",
                status_code=500,
                provider_name=self.name,
            )

        body: dict[str, Any] = {
            "model": upstream_model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        for k, v in params.items():
            if v is not None:
                body[k] = v

        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        base = (self.base_url or "https://api.openai.com/v1").rstrip("/")
        url = f"{base}/chat/completions"

        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        accumulated = []
        finish_reason: str | None = None
        try:
            async with httpx.AsyncClient(timeout=self.cfg.timeout) as client:
                async with client.stream("POST", url, json=body, headers=headers) as resp:
                    if resp.status_code >= 400:
                        text = (await resp.aread()).decode("utf-8", "replace")
                        raise ProviderError(
                            f"OpenAI upstream error {resp.status_code}: {text[:500]}",
                            status_code=resp.status_code,
                            provider_name=self.name,
                        )
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[len("data:") :].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            frame = json.loads(data_str)
                        except (json.JSONDecodeError, ValueError):
                            continue
                        usage = frame.get("usage")
                        if usage:
                            prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
                            completion_tokens = usage.get(
                                "completion_tokens", completion_tokens
                            )
                        for choice in frame.get("choices", []) or []:
                            delta = choice.get("delta", {}) or {}
                            content = delta.get("content")
                            if content:
                                accumulated.append(content)
                                yield StreamChunk(delta_content=content)
                            if choice.get("finish_reason"):
                                finish_reason = choice["finish_reason"]
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"OpenAI request failed: {exc}",
                status_code=502,
                provider_name=self.name,
            ) from exc

        if prompt_tokens is None:
            prompt_tokens = count_prompt_tokens(messages)
        if completion_tokens is None:
            completion_tokens = count_tokens("".join(accumulated))
        yield StreamChunk(
            delta_content="",
            finish_reason=finish_reason or "stop",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


def _first_message(data: dict) -> Any:  # pragma: no cover - network path helper
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return ""
