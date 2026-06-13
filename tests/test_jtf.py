"""JTF: JSON-heavy prompt reports non-zero potential savings; opt-in compress
actually reduces the forwarded token count."""

from __future__ import annotations

import json

from llm_gateway._vendor import jtf
from llm_gateway.jtf_ops import analyze_messages, compress_messages
from llm_gateway.tokens import count_prompt_tokens
from tests.conftest import DEV_KEY


# A tabular JSON array — exactly the shape JTF compresses well (it factors the
# repeated keys into a single header row).
def _json_heavy_payload() -> dict:
    rows = [
        {"id": i, "name": f"user_{i}", "email": f"user_{i}@example.com", "active": True}
        for i in range(40)
    ]
    return {"users": rows}


def _json_heavy_prompt() -> str:
    return (
        "Please summarise this dataset:\n"
        + json.dumps(_json_heavy_payload())
    )


def test_vendored_jtf_roundtrips():
    obj = _json_heavy_payload()
    assert jtf.decode(jtf.encode(obj)) == obj


def test_analysis_reports_nonzero_savings():
    messages = [{"role": "user", "content": _json_heavy_prompt()}]
    analysis = analyze_messages(messages)
    assert analysis.json_blocks >= 1
    assert analysis.original_tokens > 0
    assert analysis.saved_tokens > 0
    assert 0 < analysis.savings_ratio < 1


def test_compress_reduces_forwarded_tokens():
    messages = [{"role": "user", "content": _json_heavy_prompt()}]
    before = count_prompt_tokens(messages)
    compressed, realized = compress_messages(messages)
    after = count_prompt_tokens(compressed)
    assert realized.json_blocks >= 1
    assert after < before  # fewer tokens forwarded
    # Original messages were not mutated.
    assert messages[0]["content"] == _json_heavy_prompt()


def test_analysis_zero_for_non_json_prompt():
    messages = [{"role": "user", "content": "just a normal sentence, no json here"}]
    analysis = analyze_messages(messages)
    assert analysis.json_blocks == 0
    assert analysis.saved_tokens == 0


def test_endpoint_reports_jtf_metadata(client, auth):
    r = client.post(
        "/v1/chat/completions",
        json={
            "model": "mock-echo",
            "messages": [{"role": "user", "content": _json_heavy_prompt()}],
        },
        headers=auth(DEV_KEY),
    )
    assert r.status_code == 200
    jtf_meta = r.json()["usage"]["gateway"]["jtf"]
    assert jtf_meta["json_blocks"] >= 1
    assert jtf_meta["potential_tokens_saved"] > 0
    assert int(r.headers["X-JTF-Potential-Tokens-Saved"]) > 0
    assert r.headers["X-JTF-Compressed"] == "false"  # opt-in, not requested


def test_endpoint_compress_header_reduces_prompt_tokens(client, auth):
    body = {
        "model": "mock-echo",
        "messages": [{"role": "user", "content": _json_heavy_prompt()}],
    }
    baseline = client.post(
        "/v1/chat/completions", json=body, headers=auth(DEV_KEY)
    )
    compressed = client.post(
        "/v1/chat/completions",
        json=body,
        headers={**auth(DEV_KEY), "X-JTF-Compress": "true"},
    )
    assert compressed.status_code == 200
    assert compressed.headers["X-JTF-Compressed"] == "true"
    # The mock echoes prompt tokens it received, so a compressed prompt yields
    # strictly fewer prompt_tokens than the uncompressed baseline.
    assert (
        compressed.json()["usage"]["prompt_tokens"]
        < baseline.json()["usage"]["prompt_tokens"]
    )
    assert compressed.json()["usage"]["gateway"]["jtf"]["compressed"] is True
    assert compressed.json()["usage"]["gateway"]["jtf"]["realized_tokens_saved"] > 0
