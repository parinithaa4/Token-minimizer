"""Namespace isolation for cache reuse.

N = SHA256(team_id || system_prompt || provider_family || temp_bucket)

The namespace prevents semantically similar requests from different teams,
system prompts, provider families, or temperature buckets from sharing
responses.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


def normalize_prompt(prompt: str) -> str:
    """Normalize prompt text for cache identity and embedding."""
    return " ".join(
        prompt.strip().lower().split()
    )


def normalize_system_prompt(prompt: str) -> str:
    return normalize_prompt(prompt)


@dataclass(frozen=True)
class NamespaceKey:
    team_id: str
    system_prompt: str
    provider_family: str
    temperature: float

    def temp_bucket(self, bucket_width: float = 0.1) -> str:
        if bucket_width <= 0:
            raise ValueError("bucket_width must be > 0")

        bucket = round(
            float(self.temperature) / bucket_width
        ) * bucket_width

        return f"{bucket:.2f}"

    def hash(self) -> str:
        values = [
            self.team_id.strip(),
            normalize_system_prompt(self.system_prompt),
            self.provider_family.strip().lower(),
            self.temp_bucket(),
        ]

        raw = "||".join(values)

        return hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()


def namespace_for_request(
    team_id: str,
    system_prompt: str,
    provider_family: str,
    temperature: float,
) -> str:
    return NamespaceKey(
        team_id=team_id,
        system_prompt=system_prompt,
        provider_family=provider_family,
        temperature=temperature,
    ).hash()


def l1_key(
    namespace: str,
    normalized_prompt: str,
) -> str:
    raw = (
        f"{namespace}||"
        f"{normalize_prompt(normalized_prompt)}"
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()