"""SSE streaming (``stream: true``) over the mock provider.

These exercise the end-to-end OpenAI-style SSE path with the Starlette
``TestClient`` (which buffers and returns the streamed body), and assert the
non-streaming path is untouched. No network, mock provider only.
"""

from __future__ import annotations

import json

from llm_gateway.providers.mock import MockProvider
from tests.conftest import DEV_KEY, TINY_KEY


def _stream_body(content="stream this please across a few chunks"):
    return {
        "model": "mock-echo",
        "messages": [{"role": "user", "content": content}],
        "stream": True,
    }


def _parse_sse(text: str):
    """Return the list of ``data:`` payloads (strings) from an SSE body."""
    out = []
    for block in text.split("\n\n"):
        block = block.strip()
        if block.startswith("data:"):
            out.append(block[len("data:") :].strip())
    return out


def test_stream_yields_multiple_chunks_and_done(client, auth):
    r = client.post("/v1/chat/completions", json=_stream_body(), headers=auth(DEV_KEY))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")

    payloads = _parse_sse(r.text)
    # role-priming chunk + >=1 content chunk + final chunk + [DONE]
    assert len(payloads) >= 4
    assert payloads[-1] == "[DONE]"

    # Every non-DONE payload is a valid chat.completion.chunk with a delta.
    objs = [json.loads(p) for p in payloads if p != "[DONE]"]
    for obj in objs:
        assert obj["object"] == "chat.completion.chunk"
        assert "delta" in obj["choices"][0]

    # First chunk primes the assistant role.
    assert objs[0]["choices"][0]["delta"].get("role") == "assistant"

    # There is more than one content-bearing chunk (token-by-token simulation).
    content_chunks = [o for o in objs if o["choices"][0]["delta"].get("content")]
    assert len(content_chunks) >= 2


def test_stream_delta_shape_and_reassembly(client, auth):
    r = client.post(
        "/v1/chat/completions",
        json=_stream_body("reassemble me exactly"),
        headers=auth(DEV_KEY),
    )
    objs = [json.loads(p) for p in _parse_sse(r.text) if p != "[DONE]"]

    assembled = "".join(
        o["choices"][0]["delta"].get("content", "") for o in objs
    )
    # The mock echoes the user content; reassembled stream == that echo.
    assert "reassemble me exactly" in assembled
    assert assembled == "[mock] You said: reassemble me exactly"

    # Exactly one terminal chunk carries a finish_reason of "stop".
    finishes = [
        o["choices"][0]["finish_reason"]
        for o in objs
        if o["choices"][0]["finish_reason"]
    ]
    assert finishes == ["stop"]


def test_stream_includes_usage_on_final_chunk(client, auth):
    r = client.post("/v1/chat/completions", json=_stream_body(), headers=auth(DEV_KEY))
    objs = [json.loads(p) for p in _parse_sse(r.text) if p != "[DONE]"]
    final = objs[-1]
    usage = final["usage"]
    assert usage["prompt_tokens"] > 0
    assert usage["completion_tokens"] > 0
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]


def test_stream_records_usage_after_completion(client, auth):
    before = _usage(client, "dev")
    assert before["requests"] == 0

    r = client.post("/v1/chat/completions", json=_stream_body(), headers=auth(DEV_KEY))
    assert r.status_code == 200
    # Consume the body fully (TestClient already did) — usage now recorded.

    after = _usage(client, "dev")
    assert after["requests"] == 1
    assert after["total_tokens"] > 0
    assert after["cost_usd"] > 0


def test_stream_budget_precheck_returns_402_not_broken_stream(client, auth):
    r = client.post(
        "/v1/chat/completions",
        json=_stream_body("anything"),
        headers=auth(TINY_KEY),
    )
    # Over-budget: a clean 402 JSON error, never a partial event-stream.
    assert r.status_code == 402
    assert not r.headers["content-type"].startswith("text/event-stream")
    err = r.json()["error"]
    assert err["type"] == "insufficient_quota"
    assert err["code"] == "budget_exceeded"


def test_non_streaming_path_unchanged(client, auth):
    r = client.post(
        "/v1/chat/completions",
        json={"model": "mock-echo", "messages": [{"role": "user", "content": "hi"}]},
        headers=auth(DEV_KEY),
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert body["object"] == "chat.completion"
    assert body["usage"]["gateway"]["provider"] == "mock"


async def test_mock_provider_stream_chunks_reassemble():
    """Unit-level: the mock provider's stream reassembles to its echo and the
    terminal chunk carries usage."""
    from llm_gateway.config import ProviderConfig

    prov = MockProvider(ProviderConfig(name="mock", type="mock"))
    messages = [{"role": "user", "content": "token by token"}]
    chunks = [
        c
        async for c in prov.stream_chat(
            upstream_model="mock-echo", messages=messages, params={}
        )
    ]
    text = "".join(c.delta_content for c in chunks)
    assert text == "[mock] You said: token by token"
    last = chunks[-1]
    assert last.finish_reason == "stop"
    assert last.prompt_tokens and last.completion_tokens


def _usage(client, key_name: str) -> dict:
    rows = client.get("/admin/usage").json()["keys"]
    for row in rows:
        if row["key_name"] == key_name:
            return row
    raise AssertionError(f"no usage row for {key_name}")
