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

import time
import uuid
from typing import Any

import httpx

from ..config import ProviderConfig
from ..tokens import count_prompt_tokens, count_tokens, message_text
from .base import ProviderError, ProviderResult

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
