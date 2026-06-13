"""Admin CLI for the gateway: create and list virtual API keys.

Usage::

    python -m llm_gateway.cli create-key --name alice --max-usd 5 \
        --models mock-echo,mock-cheap
    python -m llm_gateway.cli list-keys
    python -m llm_gateway.cli usage

The CLI writes to the same SQLite DB the server reads (``GATEWAY_CONFIG`` /
``database_url``), so keys created here are immediately usable by a running
gateway that shares the DB file.
"""

from __future__ import annotations

import argparse
import secrets
import sys

from .config import load_config
from .store import Store, VirtualKey


def _store_from_config() -> Store:
    config = load_config()
    return Store(config.database_url)


def cmd_create_key(args) -> int:
    store = _store_from_config()
    # Seed configured keys too, so this DB is consistent with the server.
    for k in load_config().keys:
        store.upsert_key(
            VirtualKey(
                key=k.key,
                name=k.name,
                allowed_models=k.allowed_models,
                max_usd=k.max_usd,
                max_tokens=k.max_tokens,
                cache_enabled=k.cache_enabled,
            )
        )

    key = args.key or f"sk-gw-{secrets.token_urlsafe(24)}"
    models = [m.strip() for m in (args.models or "").split(",") if m.strip()]
    vk = VirtualKey(
        key=key,
        name=args.name,
        allowed_models=models,
        max_usd=args.max_usd,
        max_tokens=args.max_tokens,
        cache_enabled=not args.no_cache,
    )
    store.upsert_key(vk)
    print(f"created key: {key}")
    print(f"  name           : {vk.name}")
    print(f"  allowed_models : {models or '(all routed models)'}")
    print(f"  max_usd        : {vk.max_usd}")
    print(f"  max_tokens     : {vk.max_tokens}")
    print(f"  cache_enabled  : {vk.cache_enabled}")
    return 0


def cmd_list_keys(_args) -> int:
    store = _store_from_config()
    keys = store.list_keys()
    if not keys:
        print("(no keys; run create-key or seed config.yaml)")
        return 0
    for vk in keys:
        print(
            f"{vk.key}\tname={vk.name}\tmodels={vk.allowed_models or 'ALL'}"
            f"\tmax_usd={vk.max_usd}\tmax_tokens={vk.max_tokens}"
        )
    return 0


def cmd_usage(_args) -> int:
    store = _store_from_config()
    for vk in store.list_keys():
        u = store.get_usage(vk.key)
        print(
            f"{vk.name}: requests={u.requests} tokens={u.total_tokens} "
            f"cost=${u.cost_usd:.6f} cache_hits={u.cache_hits} "
            f"jtf_saved={u.jtf_potential_tokens_saved}"
        )
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="llm-gateway", description="gateway admin CLI")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("create-key", help="create a virtual API key")
    c.add_argument("--name", default="default")
    c.add_argument("--key", default=None, help="explicit key value (else generated)")
    c.add_argument("--models", default=None, help="comma-separated allowed models")
    c.add_argument("--max-usd", type=float, default=None)
    c.add_argument("--max-tokens", type=int, default=None)
    c.add_argument("--no-cache", action="store_true")
    c.set_defaults(func=cmd_create_key)

    sub.add_parser("list-keys", help="list virtual keys").set_defaults(
        func=cmd_list_keys
    )
    sub.add_parser("usage", help="print per-key usage").set_defaults(func=cmd_usage)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
