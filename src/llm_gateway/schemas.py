"""Pydantic v2 schemas for the OpenAI-compatible wire format.

These mirror the subset of the OpenAI Chat Completions API that the gateway
implements (non-streaming). They are intentionally permissive: unknown fields
on the request are preserved via ``model_config`` so we can forward them
upstream unchanged.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    """A single chat message in the OpenAI shape."""

    model_config = ConfigDict(extra="allow")

    role: str
    # ``content`` may be a plain string or a list of content parts (OpenAI
    # multimodal). We keep it as ``Any`` to round-trip both losslessly.
    content: Any = None
    name: str | None = None


class ChatCompletionRequest(BaseModel):
    """OpenAI ``POST /v1/chat/completions`` request body."""

    model_config = ConfigDict(extra="allow")

    model: str
    messages: list[ChatMessage]
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    n: int | None = None
    stop: Any | None = None
    stream: bool | None = False
    user: str | None = None


class Usage(BaseModel):
    """Token accounting block returned with every completion."""

    model_config = ConfigDict(extra="allow")

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionChoice(BaseModel):
    model_config = ConfigDict(extra="allow")

    index: int = 0
    message: ChatMessage
    finish_reason: str | None = "stop"


class ChatCompletionResponse(BaseModel):
    """OpenAI ``chat.completion`` response object."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:24]}")
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[ChatCompletionChoice]
    usage: Usage


class ModelCard(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "llm-gateway"


class ModelList(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelCard]


class ErrorBody(BaseModel):
    message: str
    type: str
    code: str | None = None
    param: str | None = None


class ErrorResponse(BaseModel):
    """OpenAI-style error envelope: ``{"error": {...}}``."""

    error: ErrorBody
