"""Anthropic provider — translates OpenAI ⇄ Anthropic Messages API.

Anthropic's ``/v1/messages`` differs from OpenAI in three ways we handle here:

* the ``system`` prompt is a top-level field, not a message with role
  ``system``;
* ``max_tokens`` is **required**;
* the response shape is ``{content: [{type:"text", text:...}], usage:
  {input_tokens, output_tokens}}`` rather than ``choices`` / ``usage`` with
  ``prompt_tokens``.

The translation is lossless for the common text case. The pure functions
:func:`to_anthropic_request` and :func:`from_anthropic_response` are unit-test
friendly and reused by docs/examples.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..config import ProviderConfig
from ..tokens import count_prompt_tokens, count_tokens, message_text
from .base import ProviderError, ProviderResult, StreamChunk

DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 1024


def to_anthropic_request(
    upstream_model: str, messages: list[dict], params: dict
) -> dict[str, Any]:
    """Convert an OpenAI chat request to an Anthropic Messages request body."""
    system_parts: list[str] = []
    conv: list[dict] = []
    for m in messages:
        role = m.get("role")
        text = message_text(m.get("content"))
        if role == "system":
            if text:
                system_parts.append(text)
            continue
        # Anthropic only knows "user" and "assistant".
        a_role = "assistant" if role == "assistant" else "user"
        conv.append({"role": a_role, "content": text})

    body: dict[str, Any] = {
        "model": upstream_model,
        "messages": conv,
        "max_tokens": int(params.get("max_tokens") or DEFAULT_MAX_TOKENS),
    }
    if system_parts:
        body["system"] = "\n\n".join(system_parts)
    if params.get("temperature") is not None:
        body["temperature"] = params["temperature"]
    if params.get("top_p") is not None:
        body["top_p"] = params["top_p"]
    if params.get("stop") is not None:
        stop = params["stop"]
        body["stop_sequences"] = [stop] if isinstance(stop, str) else list(stop)
    return body


def from_anthropic_response(data: dict, requested_model: str) -> dict[str, Any]:
    """Convert an Anthropic Messages response to an OpenAI chat.completion."""
    text_parts = []
    for block in data.get("content", []) or []:
        if isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(block.get("text", ""))
    text = "".join(text_parts)

    usage = data.get("usage", {}) or {}
    prompt_tokens = int(usage.get("input_tokens", 0))
    completion_tokens = int(usage.get("output_tokens", 0))

    stop_reason = data.get("stop_reason")
    finish = {
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
    }.get(stop_reason, "stop")

    return {
        "id": data.get("id") or f"chatcmpl-{uuid.uuid4().hex[:20]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": requested_model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": finish,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


class AnthropicProvider:
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
                "Anthropic provider has no API key configured "
                "(set api_key or api_key_env)",
                status_code=500,
                provider_name=self.name,
            )

        body = to_anthropic_request(upstream_model, messages, params)
        headers = {
            "x-api-key": key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        url = f"{self.base_url}/messages"

        try:
            async with httpx.AsyncClient(timeout=self.cfg.timeout) as client:
                resp = await client.post(url, json=body, headers=headers)
        except httpx.HTTPError as exc:  # pragma: no cover - network path
            raise ProviderError(
                f"Anthropic request failed: {exc}",
                status_code=502,
                provider_name=self.name,
            ) from exc

        if resp.status_code >= 400:  # pragma: no cover - network path
            raise ProviderError(
                f"Anthropic upstream error {resp.status_code}: {resp.text[:500]}",
                status_code=resp.status_code,
                provider_name=self.name,
            )

        data = resp.json()
        openai_shaped = from_anthropic_response(data, upstream_model)
        usage = openai_shaped["usage"]
        prompt_tokens = usage["prompt_tokens"] or count_prompt_tokens(messages)
        completion_tokens = usage["completion_tokens"] or count_tokens(
            openai_shaped["choices"][0]["message"]["content"]
        )
        return ProviderResult(
            response=openai_shaped,
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
        """Stream Anthropic's Messages SSE, translating deltas to OpenAI shape.

        Anthropic emits typed events: ``message_start`` (carries input token
        usage), ``content_block_delta`` (``delta.text`` — the incremental text),
        ``message_delta`` (carries ``usage.output_tokens`` + ``stop_reason``),
        and ``message_stop``. We translate each text delta into a
        :class:`StreamChunk` and surface usage/stop on the terminal chunk.
        """
        key = self.cfg.resolved_key()
        if not key:
            raise ProviderError(
                "Anthropic provider has no API key configured "
                "(set api_key or api_key_env)",
                status_code=500,
                provider_name=self.name,
            )

        body = to_anthropic_request(upstream_model, messages, params)
        body["stream"] = True
        headers = {
            "x-api-key": key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        url = f"{self.base_url}/messages"

        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        stop_reason: str | None = None
        accumulated: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=self.cfg.timeout) as client:
                async with client.stream("POST", url, json=body, headers=headers) as resp:
                    if resp.status_code >= 400:
                        text = (await resp.aread()).decode("utf-8", "replace")
                        raise ProviderError(
                            f"Anthropic upstream error {resp.status_code}: {text[:500]}",
                            status_code=resp.status_code,
                            provider_name=self.name,
                        )
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        data_str = line[len("data:") :].strip()
                        if not data_str:
                            continue
                        try:
                            event = json.loads(data_str)
                        except (json.JSONDecodeError, ValueError):
                            continue
                        etype = event.get("type")
                        if etype == "message_start":
                            usage = (event.get("message") or {}).get("usage") or {}
                            prompt_tokens = usage.get("input_tokens", prompt_tokens)
                        elif etype == "content_block_delta":
                            delta = event.get("delta") or {}
                            text = delta.get("text") or ""
                            if text:
                                accumulated.append(text)
                                yield StreamChunk(delta_content=text)
                        elif etype == "message_delta":
                            usage = event.get("usage") or {}
                            if "output_tokens" in usage:
                                completion_tokens = usage["output_tokens"]
                            d = event.get("delta") or {}
                            if d.get("stop_reason"):
                                stop_reason = d["stop_reason"]
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Anthropic request failed: {exc}",
                status_code=502,
                provider_name=self.name,
            ) from exc

        if prompt_tokens is None:
            prompt_tokens = count_prompt_tokens(messages)
        if completion_tokens is None:
            completion_tokens = count_tokens("".join(accumulated))
        finish = {
            "end_turn": "stop",
            "max_tokens": "length",
            "stop_sequence": "stop",
        }.get(stop_reason, "stop")
        yield StreamChunk(
            delta_content="",
            finish_reason=finish,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
