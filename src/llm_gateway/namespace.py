"""
namespace.py — request namespace hashing, per TokenMinGate Eq. 1.

    N = Hash(team_id || system_prompt || provider_family || temp_bucket)

Cache entries (both L1 and L2) are only ever reused by requests carrying
the same N, which keeps one team/app/config from seeing another's saved
answers. Drop into src/llm_gateway/namespace.py.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class NamespaceKey:
    team_id: str
    system_prompt: str
    provider_family: str
    temperature: float

    def temp_bucket(self, bucket_width: float = 0.1) -> str:
        """Bucket temperature so 0.71 and 0.73 land in the same namespace
        but 0.71 and 0.91 don't."""
        bucket = round(self.temperature / bucket_width) * bucket_width
        return f"{bucket:.2f}"

    def hash(self) -> str:
        raw = "||".join([
            self.team_id,
            self.system_prompt or "",
            self.provider_family,
            self.temp_bucket(),
        ])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def namespace_for_request(
    team_id: str,
    system_prompt: str,
    provider_family: str,
    temperature: float,
) -> str:
    return NamespaceKey(team_id, system_prompt, provider_family, temperature).hash()


def normalize_prompt(prompt: str) -> str:
    """u -- the cleaned prompt used as the L1 cache key input (Section III-B):
    extra whitespace collapsed, lowercased."""
    return " ".join(prompt.strip().lower().split())


def l1_key(namespace: str, normalized_prompt: str) -> str:
    """K_L1 = SHA-256(N || u)"""
    raw = f"{namespace}||{normalized_prompt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()