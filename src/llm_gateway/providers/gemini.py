"""Gemini provider — connects to Google's official OpenAI-compatible endpoint.

Base URL: https://generativelanguage.googleapis.com/v1beta/openai
Supported Models:
  - gemini-1.5-flash
  - gemini-1.5-pro
  - gemini-2.0-flash
  - gemini-2.0-flash-exp
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ..config import ProviderConfig
from ..tokens import count_prompt_tokens, count_tokens
from .base import ProviderError, ProviderResult, StreamChunk

log = logging.getLogger("llm_gateway.providers.gemini")

DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


class GeminiProvider:
    """Official Google Gemini provider via Google's OpenAI-compatible endpoint."""

    def __init__(self, cfg: ProviderConfig):
        self.cfg = cfg
        self.name = cfg.name
        self.base_url = (cfg.base_url or DEFAULT_GEMINI_BASE_URL).rstrip("/")

    def _get_api_key(self) -> str:
        key = self.cfg.resolved_key()
        if not key:
            for env_var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY"):
                val = os.environ.get(env_var)
                if val and not val.startswith("your-"):
                    key = val
                    break
        if not key:
            raise ProviderError(
                "Gemini provider has no API key configured. "
                "Set GEMINI_API_KEY or GOOGLE_API_KEY in your environment or .env file.",
                status_code=500,
                provider_name=self.name,
            )
        return key

    async def chat(
        self,
        *,
        upstream_model: str,
        messages: list[dict],
        params: dict,
    ) -> ProviderResult:
        key = self._get_api_key()
        body: dict[str, Any] = {"model": upstream_model, "messages": messages}
        for k, v in params.items():
            if v is not None:
                body[k] = v
        body.pop("stream", None)

        headers = {
            "Authorization": f"Bearer {key}",
            "x-goog-api-key": key,
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=self.cfg.timeout) as client:
                resp = await client.post(url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Gemini request failed: {exc}",
                status_code=502,
                provider_name=self.name,
            ) from exc

        if resp.status_code >= 400:
            err_msg = resp.text[:500]
            try:
                err_json = resp.json()
                if isinstance(err_json, list) and err_json and "error" in err_json[0]:
                    err_msg = err_json[0]["error"].get("message", err_msg)
                elif isinstance(err_json, dict) and "error" in err_json:
                    err_msg = err_json["error"].get("message", err_msg)
            except Exception:
                pass
            raise ProviderError(
                f"Gemini upstream error {resp.status_code}: {err_msg}",
                status_code=resp.status_code,
                provider_name=self.name,
            )

        data = resp.json()
        usage = data.get("usage") or {}
        prompt_tokens = int(
            usage.get("prompt_tokens")
            or count_prompt_tokens(messages, model=upstream_model)
        )
        completion_text = ""
        choices = data.get("choices") or []
        if choices:
            completion_text = choices[0].get("message", {}).get("content", "") or ""
        completion_tokens = int(
            usage.get("completion_tokens")
            or count_tokens(completion_text, model=upstream_model)
        )

        return ProviderResult(
            response=data,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    async def stream_chat(
        self,
        *,
        upstream_model: str,
        messages: list[dict],
        params: dict,
    ) -> AsyncIterator[StreamChunk]:
        key = self._get_api_key()
        body: dict[str, Any] = {
            "model": upstream_model,
            "messages": messages,
            "stream": True,
        }
        for k, v in params.items():
            if v is not None and k != "stream":
                body[k] = v

        headers = {
            "Authorization": f"Bearer {key}",
            "x-goog-api-key": key,
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

        prompt_tokens: int | None = None
        completion_tokens: int | None = None

        try:
            client = httpx.AsyncClient(timeout=self.cfg.timeout)
            req = client.build_request("POST", url, json=body, headers=headers)
            resp = await client.send(req, stream=True)
            if resp.status_code >= 400:
                body_bytes = await resp.aread()
                await resp.aclose()
                await client.aclose()
                raise ProviderError(
                    f"Gemini upstream stream error {resp.status_code}: {body_bytes[:500].decode(errors='replace')}",
                    status_code=resp.status_code,
                    provider_name=self.name,
                )

            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if data_str == "[DONE]":
                    break
                try:
                    payload = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                if "usage" in payload and payload["usage"]:
                    u = payload["usage"]
                    if u.get("prompt_tokens") is not None:
                        prompt_tokens = int(u["prompt_tokens"])
                    if u.get("completion_tokens") is not None:
                        completion_tokens = int(u["completion_tokens"])

                choices = payload.get("choices") or []
                delta_text = ""
                finish_reason = None
                if choices:
                    c = choices[0]
                    finish_reason = c.get("finish_reason")
                    delta = c.get("delta") or {}
                    delta_text = delta.get("content") or ""

                yield StreamChunk(
                    delta_content=delta_text,
                    finish_reason=finish_reason,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )

            await resp.aclose()
            await client.aclose()
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Gemini streaming failed: {exc}",
                status_code=502,
                provider_name=self.name,
            ) from exc

    # Alias for backward compatibility
    chat_stream = stream_chat

