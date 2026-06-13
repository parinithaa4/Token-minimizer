"""Shared pytest fixtures.

Every test uses the built-in ``mock`` provider with an in-memory SQLite store
and the in-memory cache — no real API keys, no network, no Redis.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from llm_gateway.app import create_app
from llm_gateway.config import (
    GatewayConfig,
    KeyConfig,
    ProviderConfig,
    RouteConfig,
)

DEV_KEY = "sk-test-dev"
CHEAP_KEY = "sk-test-cheap"
TINY_KEY = "sk-test-tiny"
TINY_TOKENS_KEY = "sk-test-tiny-tokens"


def _test_config() -> GatewayConfig:
    return GatewayConfig(
        providers={"mock": ProviderConfig(name="mock", type="mock")},
        routes={
            "mock-echo": RouteConfig("mock-echo", "mock", "mock-echo"),
            "mock-cheap": RouteConfig("mock-cheap", "mock", "mock-cheap"),
        },
        keys=[
            KeyConfig(key=DEV_KEY, name="dev", allowed_models=[], max_usd=10.0),
            KeyConfig(
                key=CHEAP_KEY,
                name="cheap",
                allowed_models=["mock-cheap"],
                max_usd=5.0,
            ),
            # Budget so small that even one request's estimate exceeds it.
            KeyConfig(key=TINY_KEY, name="tiny", allowed_models=[], max_usd=1e-9),
            KeyConfig(
                key=TINY_TOKENS_KEY,
                name="tiny-tokens",
                allowed_models=[],
                max_tokens=1,
            ),
        ],
        database_url="sqlite:///:memory:",
        redis_url=None,
    )


@pytest.fixture
def config() -> GatewayConfig:
    return _test_config()


@pytest.fixture
def app(config):
    return create_app(config)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def auth():
    def _h(key: str = DEV_KEY) -> dict:
        return {"Authorization": f"Bearer {key}"}

    return _h
