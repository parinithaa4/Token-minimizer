"""Provider translation unit tests (no network)."""

from __future__ import annotations

from llm_gateway.providers.anthropic import (
    from_anthropic_response,
    to_anthropic_request,
)


def test_openai_to_anthropic_request_lifts_system_and_requires_max_tokens():
    messages = [
        {"role": "system", "content": "be terse"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "bye"},
    ]
    body = to_anthropic_request(
        "claude-3-5-sonnet", messages, {"temperature": 0.2, "max_tokens": 256}
    )
    assert body["model"] == "claude-3-5-sonnet"
    assert body["system"] == "be terse"
    assert body["max_tokens"] == 256
    assert body["temperature"] == 0.2
    # System message is removed from the conversation array.
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user"]


def test_anthropic_to_openai_response_shape():
    anthropic_resp = {
        "id": "msg_123",
        "content": [{"type": "text", "text": "hello there"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 11, "output_tokens": 5},
    }
    out = from_anthropic_response(anthropic_resp, "claude-3-5-sonnet")
    assert out["object"] == "chat.completion"
    assert out["choices"][0]["message"]["content"] == "hello there"
    assert out["choices"][0]["finish_reason"] == "stop"
    assert out["usage"]["prompt_tokens"] == 11
    assert out["usage"]["completion_tokens"] == 5
    assert out["usage"]["total_tokens"] == 16


def test_max_tokens_finish_reason_maps_to_length():
    out = from_anthropic_response(
        {"content": [], "stop_reason": "max_tokens", "usage": {}}, "m"
    )
    assert out["choices"][0]["finish_reason"] == "length"
