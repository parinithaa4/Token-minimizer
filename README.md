<div align="center">

# llm-gateway

**A token-frugal, self-hostable LLM gateway / proxy.**

OpenAI-compatible · honest token & cost accounting · virtual keys & budgets · response cache · built-in **JTF** savings

[English](README.md) · [Русский](README.ru.md)

</div>

---

`llm-gateway` is a single-binary-ish FastAPI reverse proxy you put in front of
OpenAI, Anthropic, Ollama, or a built-in offline **mock** provider. Your apps
keep talking the OpenAI Chat Completions protocol; the gateway adds virtual API
keys, per-key **budgets**, a response **cache**, honest **cost accounting**, and
— the differentiator — built-in **JTF (JSON Token Format)** savings
observability and opt-in compression.

It runs, and its full test suite passes, **with no real API keys and no
network** thanks to the built-in mock provider.

## Why another gateway?

| | llm-gateway | LiteLLM | Helicone |
|---|---|---|---|
| OpenAI-compatible proxy | ✅ | ✅ | ✅ (passthrough) |
| Virtual keys + budgets | ✅ built-in (SQLite) | ✅ | ✅ (SaaS-first) |
| Response cache (Redis/in-mem) | ✅ | ✅ | ✅ |
| Cost accounting | ✅ honest, per-token | ✅ | ✅ |
| **JTF token-savings observability** | ✅ **always-on, non-destructive** | ❌ | ❌ |
| **JTF prompt compression (opt-in)** | ✅ **experimental, lossless** | ❌ | ❌ |
| Runs fully offline (mock provider) | ✅ | partial | ❌ |
| Self-hostable, no SaaS dependency | ✅ | ✅ | partial |

The honest angle: **most gateways estimate cost and stop there.** This one also
tells you, for every request, how many tokens you *would* save by encoding your
JSON-heavy prompts more efficiently — and lets you actually do it when you opt
in. That's the [JTF](#jtf-the-differentiator) feature.

## Architecture

```
                    ┌──────────────────────────────────────────────┐
  OpenAI SDK  ──▶   │  FastAPI app  (app.py)                        │
  (base_url =       │    auth (Bearer vkey) ─ require_key           │
   gateway)         │    POST /v1/chat/completions  (+ SSE stream)  │
                    │    GET  /v1/models                            │
                    │    GET  /admin/usage  /admin/pricing          │
                    │    GET  /dashboard  (Electric Cyan admin UI)  │
                    └───────────────┬──────────────────────────────┘
                                    ▼
                    ┌──────────────────────────────────────────────┐
                    │  Gateway service  (gateway.py)                │
                    │   1. route(model) → provider+upstream+fallback│
                    │   2. authorize model vs vkey allow-list       │
                    │   3. JTF analyze (always) / compress (opt-in) │
                    │   4. cache lookup  (hit ⇒ $0, flagged)        │
                    │   5. pre-flight budget check  (over ⇒ 402)    │
                    │   6. provider.chat(...)  (+ fallback)         │
                    │   7. cost = usage × price → record atomically │
                    └───┬───────────┬───────────┬──────────┬────────┘
                        ▼           ▼           ▼          ▼
                  providers/    cache.py     store.py   pricing.py
                  mock·openai·  Redis | in-  SQLite     per-Mtok
                  anthropic·    memory       keys+usage seed table
                  ollama
```

- **`gateway.py`** is framework-agnostic: it takes/returns plain dicts, so it's
  driveable from FastAPI, a CLI, or tests without HTTP.
- **`store.py`** — SQLite for keys + usage; atomic `UPDATE` for budget safety.
- **`cache.py`** — Redis when configured & reachable, transparent in-memory
  fallback otherwise (so tests need no Redis).
- **`_vendor/jtf/`** — the JTF reference lib, vendored (MIT, credited) so the
  differentiating feature has zero extra runtime deps.

## Quickstart

```sh
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run the server (zero config: mock provider + a dev key "sk-gw-dev").
uvicorn llm_gateway.app:app --reload
```

Then, in another shell, a working request against the offline **mock** provider:

```sh
curl -s http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-gw-dev" \
  -H "Content-Type: application/json" \
  -d '{"model":"mock-echo","messages":[{"role":"user","content":"hello"}]}'
```

```jsonc
{
  "id": "chatcmpl-mock-…",
  "object": "chat.completion",
  "model": "mock-echo",
  "choices": [{"index":0,"message":{"role":"assistant","content":"[mock] You said: hello"},"finish_reason":"stop"}],
  "usage": {
    "prompt_tokens": 9, "completion_tokens": 8, "total_tokens": 17,
    "gateway": {
      "cache_hit": false, "cost_usd": 0.000025, "provider": "mock",
      "jtf": {"json_blocks": 0, "potential_tokens_saved": 0, "compressed": false}
    }
  }
}
```

### Use it from the OpenAI SDK

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-gw-dev")
resp = client.chat.completions.create(
    model="mock-echo",
    messages=[{"role": "user", "content": "hello"}],
)
print(resp.choices[0].message.content)
```

Point `base_url` at the gateway and existing OpenAI code just works.

### Streaming (`stream: true`)

Set `"stream": true` and the gateway returns OpenAI-style **Server-Sent Events**
(`Content-Type: text/event-stream`): a sequence of `data: {chunk}\n\n` frames of
`chat.completion.chunk` objects (each with a `choices[].delta`), terminated by
`data: [DONE]\n\n`. The OpenAI SDK consumes this natively:

```python
stream = client.chat.completions.create(
    model="mock-echo",
    messages=[{"role": "user", "content": "stream me"}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

Or with `curl`:

```sh
curl -N http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-gw-dev" -H "Content-Type: application/json" \
  -d '{"model":"mock-echo","messages":[{"role":"user","content":"hi"}],"stream":true}'
```

How it behaves:

- The **budget pre-check runs before the stream starts** — an over-budget
  request fails with **HTTP 402** (clean JSON error), never a half-broken stream.
- Streamed content and token **usage are accumulated and recorded per key
  *after* the stream completes** (the final chunk also carries a `usage` block).
- **Caching is bypassed for streaming requests** (there's no single object to
  serve mid-flight) — non-streaming requests still use the exact-match cache.
- The **mock** provider simulates a token-by-token stream; **OpenAI** streams
  via passthrough; **Anthropic** translates its Messages SSE deltas to OpenAI
  chunks.

## Configuration

With **no** config the gateway boots on the mock provider with a dev key — great
for trying it and for CI. For real upstreams, copy `config.example.yaml` to
`config.yaml` and run with `GATEWAY_CONFIG=config.yaml`. The file has three
sections:

- **`providers`** — adapters + upstream creds (read from env via `api_key_env`).
- **`routing`** — client-facing `model` → `provider` + `upstream_model` (+ optional `fallback`).
- **`keys`** — virtual keys with `allowed_models`, `max_usd`, `max_tokens`, `cache_enabled`.

Manage keys from the CLI (writes the same SQLite DB the server reads):

```sh
llm-gateway create-key --name alice --max-usd 5 --models mock-echo,mock-cheap
llm-gateway list-keys
llm-gateway usage
```

### Budgets

Each key may have `max_usd` and/or `max_tokens`. A request whose projected cost
would exceed the cap is rejected **before** spending, with **HTTP 402** and a
clear JSON error:

```json
{"error":{"message":"budget exceeded: spend $… would exceed cap $1.00",
          "type":"insufficient_quota","code":"budget_exceeded"}}
```

### Caching

The cache key is a SHA-256 of `(upstream_model, messages, sampling params)`. An
identical second request returns the cached response, is **billed $0**, and is
flagged via `X-Cache: HIT` and `usage.gateway.cache_hit`. Disable per request
with `X-Cache: no-store`, or per key with `cache_enabled: false`. Uses Redis when
`redis_url` is set and reachable, otherwise an in-memory dict.

### Cost accounting

Prices live in a seed table (`pricing.py`), USD **per 1M tokens**, LiteLLM-style:

| model family | input $/Mtok | output $/Mtok |
|---|---|---|
| claude-3-opus | 5 | 25 |
| claude-3.5-sonnet | 3 | 15 |
| claude-3.5-haiku | 1 | 5 |
| gpt-4o | 2.5 *(verify)* | 10 *(verify)* |

Versioned ids (`claude-3-5-sonnet-20241022`) resolve to the family price by
longest-prefix match. Entries marked *verify* should be re-checked against the
provider's current price sheet before billing — list prices drift. You can
refresh from a LiteLLM-style JSON via `pricing.load_litellm_prices(doc)` (pure,
no network).

## JTF: the differentiator

[JTF — JSON Token Format](src/llm_gateway/_vendor/jtf/) is a lossless,
round-trippable encoding of the JSON data model that costs **fewer tokens** than
`json.dumps` for structured data (it factors repeated object keys into a single
header row, builds a value dictionary for repeated strings, etc.). The gateway
uses it two ways:

1. **Observability — always on, non-destructive.** Every request is scanned for
   JSON-shaped content and we report how many tokens JTF *would* save. The
   forwarded prompt is **never** altered. Surfaced in
   `usage.gateway.jtf.potential_tokens_saved`, the `X-JTF-Potential-Tokens-Saved`
   header, and `/admin/usage`. This is the brand promise: honest token
   accounting, with the savings you're leaving on the table made visible.

2. **Compression — opt-in, experimental.** Send `X-JTF-Compress: true` and the
   gateway re-encodes large, clearly-JSON message blocks into JTF *before*
   forwarding, reducing the prompt token count.

> ⚠️ **Honest caveat.** JTF compression is lossless on the wire
> (`decode(encode(x)) == x`), but **the upstream model must understand JTF** to
> use the data correctly. That's why it is **opt-in and conservative**: it only
> touches unambiguously-JSON spans above a size threshold, only when JTF
> actually wins, marks the block with a `[[JTF/v2]]` header, and never mutates
> your original request object. Treat it as experimental — measure quality on
> your workload, or pair it with a system prompt that teaches the model the
> format. The *observability* side has no such caveat: it's free and always
> correct.

## Observability

- Structured request logging (per-request rows in SQLite `request_log`).
- `GET /admin/usage` — portfolio **totals** plus per key: requests, tokens,
  $ spent, **budget remaining**, **cache-hit rate**, and **JTF potential tokens
  saved**.
- `GET /admin/pricing` — the active pricing table.
- Response headers: `X-Cache`, `X-Cost-USD`, `X-Provider`, `X-JTF-*`.

### Dashboard

A polished, self-contained admin dashboard is served at **`GET /dashboard`**.
It auto-refreshes (every 4s, with a live indicator), fetches `/admin/usage`, and
renders a totals header (total requests · tokens · $ spent · cache-hit rate ·
JTF tokens saved) plus per-key cards with a **$ spent vs budget progress bar**
(cyan → amber → red as it fills), cache-hit rate, and JTF savings. It renders
gracefully with zero data and is mobile-responsive. Vanilla JS, no build step,
clean inline SVG icons, and it honors `prefers-reduced-motion`.

![llm-gateway dashboard — usage, budgets, cache, JTF savings](docs/dashboard.png)

> The dashboard lives at `/dashboard`. With an `admin_token` configured (see
> below), open it as `/dashboard?admin_token=<token>` — the page forwards the
> token to its data fetch.

### Admin auth (optional)

`/admin/*` is **open by default** so the quickstart and dashboard work out of
the box. To gate it, set `admin_token` in `config.yaml` (or `$GATEWAY_ADMIN_TOKEN`).
Then supply it as the `X-Admin-Token` header, or as `?admin_token=...` for the
dashboard. The `/dashboard` HTML page itself stays public; the **data** behind
it (`/admin/usage`) is what's protected.

## Docker

```sh
docker compose up --build      # gateway on :8000 + redis on :6379
```

`docker-compose.yml` wires the gateway to Redis automatically; the gateway still
runs fine if Redis is down (in-memory fallback).

## Development & tests

```sh
pip install -e ".[dev]"
ruff check .
pytest                 # all green, no keys, no network
```

Tests cover auth (401), routing/OpenAI shape, budgets (402), caching (hit billed
$0), cost math, the Anthropic translation, both JTF paths, **SSE streaming**, and
the **dashboard + `/admin/usage`** shape — all on the mock provider.

## Roadmap

- **Semantic cache** (embedding-based near-duplicate hits), beyond exact-match.
- **More providers**: Google Gemini, Mistral, Bedrock, Azure OpenAI.
- Admin-token auth for `/admin/*`, Prometheus metrics, rate limiting.
- Postgres store option for higher concurrency.

## License

MIT © 2026 Maxim Chumakov. Vendors the JTF reference implementation
(MIT, also © 2026 Maxim Chumakov) under `src/llm_gateway/_vendor/jtf/`.
