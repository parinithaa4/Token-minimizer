"""Provider adapters.

A provider takes a normalized (OpenAI-shaped) request and returns an
OpenAI-shaped response with a ``usage`` block. The gateway is provider-agnostic
above this seam: routing picks a provider + upstream model name, and the
provider handles any request/response translation (e.g. Anthropic's Messages
API) and the actual network call.
"""

from .anthropic import AnthropicProvider
from .base import Provider, ProviderError, ProviderResult
from .mock import MockProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider

__all__ = [
    "Provider",
    "ProviderError",
    "ProviderResult",
    "MockProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "build_provider",
]


def build_provider(cfg) -> Provider:
    """Instantiate a provider from its :class:`ProviderConfig`."""
    t = cfg.type
    if t == "mock":
        return MockProvider(cfg)
    if t == "openai":
        return OpenAIProvider(cfg)
    if t == "anthropic":
        return AnthropicProvider(cfg)
    if t == "ollama":
        return OllamaProvider(cfg)
    raise ProviderError(f"unknown provider type: {t!r}")
