"""Provider base types."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class StreamChunk:
    """One streamed delta from a provider, normalized to the OpenAI shape.

    ``delta_content`` is the incremental assistant text for this chunk (may be
    empty for the role-priming chunk or the final stop chunk). ``finish_reason``
    is set only on the terminal chunk. ``prompt_tokens`` / ``completion_tokens``
    carry the final usage when the provider reports it (typically on the last
    chunk); they are ``None`` on intermediate chunks.
    """

    delta_content: str = ""
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class ProviderError(Exception):
    """Raised when a provider cannot fulfil a request.

    ``status_code`` is propagated to the client where sensible (e.g. upstream
    4xx). ``provider_name`` aids logging.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 502,
        provider_name: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.provider_name = provider_name


@dataclass
class ProviderResult:
    """Normalized provider output: an OpenAI-shaped ``chat.completion`` dict.

    ``response`` is the full OpenAI-shaped JSON (``id``, ``choices``,
    ``usage``...). ``usage`` is pulled out for convenience/billing.
    """

    response: dict[str, Any]
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class Provider(Protocol):
    """Adapter interface. Implementations may be sync or async-callable."""

    name: str

    async def chat(
        self,
        *,
        upstream_model: str,
        messages: list[dict],
        params: dict,
    ) -> ProviderResult:
        """Run a non-streaming chat completion and return a normalized result."""
        ...

    def stream_chat(
        self,
        *,
        upstream_model: str,
        messages: list[dict],
        params: dict,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion as normalized :class:`StreamChunk` deltas.

        Optional: providers that cannot stream omit this and the gateway falls
        back to a single-shot non-streaming call adapted into one chunk.
        """
        ...
