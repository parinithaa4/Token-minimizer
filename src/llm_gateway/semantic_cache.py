"""FAISS-backed L2 semantic cache with an age-aware similarity threshold."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Optional

import numpy as np

try:
    import faiss
except ImportError as exc:
    raise ImportError(
        "Semantic cache requires faiss-cpu. "
        "Install with: pip install faiss-cpu"
    ) from exc

try:
    from sentence_transformers import SentenceTransformer
except ImportError as exc:
    raise ImportError(
        "Semantic cache requires sentence-transformers. "
        "Install with: pip install sentence-transformers"
    ) from exc


DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass
class CacheEntry:
    entry_id: str
    namespace: str
    prompt_norm: str
    response: dict
    created_at: float
    last_used_at: float
    ttl_seconds: float
    tokens_saved_if_hit: int


@dataclass(frozen=True)
class SemanticLookup:
    entry: CacheEntry
    similarity: float
    effective_threshold: float
    age_seconds: float


class SemanticCache:
    """In-memory FAISS semantic cache.

    Embeddings are L2-normalized, therefore FAISS inner-product similarity
    equals cosine similarity.

    Namespace filtering is performed after FAISS retrieval.
    """

    def __init__(
        self,
        *,
        base_threshold: float = 0.84,
        default_ttl_seconds: float = 7 * 24 * 3600,
        embed_model_name: str = DEFAULT_MODEL_NAME,
        k_neighbors: int = 8,
    ) -> None:
        if not 0.0 <= base_threshold < 1.0:
            raise ValueError("base_threshold must be in [0, 1)")

        if default_ttl_seconds <= 0:
            raise ValueError("default_ttl_seconds must be > 0")

        if k_neighbors <= 0:
            raise ValueError("k_neighbors must be > 0")

        self.tau = float(base_threshold)
        self.default_ttl = float(default_ttl_seconds)
        self.k = int(k_neighbors)

        self._model = SentenceTransformer(embed_model_name)

        probe = self._model.encode(
            ["dimension probe"],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        probe = np.asarray(probe, dtype=np.float32)

        if probe.ndim != 2 or probe.shape[0] != 1:
            raise RuntimeError("embedding model returned an invalid shape")

        self.dimension = int(probe.shape[1])

        self._index = faiss.IndexFlatIP(self.dimension)
        self._id_map: list[str] = []
        self._entries: dict[str, CacheEntry] = {}
        self._vectors: dict[str, np.ndarray] = {}

    def _encode(self, text: str) -> np.ndarray:
        vector = self._model.encode(
            [text],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        vector = np.asarray(vector, dtype=np.float32)

        if vector.shape != (1, self.dimension):
            raise RuntimeError(
                f"embedding shape {vector.shape} does not match "
                f"expected {(1, self.dimension)}"
            )

        return vector

    @staticmethod
    def effective_threshold(
        tau: float,
        age_seconds: float,
        ttl_seconds: float,
    ) -> float:
        if ttl_seconds <= 0:
            return 1.0

        age_ratio = min(
            1.0,
            max(0.0, age_seconds / ttl_seconds),
        )

        return tau + (1.0 - tau) * age_ratio

    def lookup(
        self,
        namespace: str,
        prompt_norm: str,
    ) -> Optional[SemanticLookup]:
        if self._index.ntotal == 0:
            return None

        query = self._encode(prompt_norm)

        k = min(self.k, self._index.ntotal)
        scores, indices = self._index.search(query, k)

        now = time.time()

        candidates: list[SemanticLookup] = []

        for score, row in zip(scores[0], indices[0]):
            if row < 0 or row >= len(self._id_map):
                continue

            entry_id = self._id_map[row]
            entry = self._entries.get(entry_id)

            if entry is None:
                continue

            if entry.namespace != namespace:
                continue

            age = max(0.0, now - entry.created_at)

            if age > entry.ttl_seconds:
                continue

            threshold = self.effective_threshold(
                self.tau,
                age,
                entry.ttl_seconds,
            )

            similarity = float(score)

            if similarity >= threshold:
                candidates.append(
                    SemanticLookup(
                        entry=entry,
                        similarity=similarity,
                        effective_threshold=threshold,
                        age_seconds=age,
                    )
                )

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: item.similarity,
            reverse=True,
        )

        selected = candidates[0]
        selected.entry.last_used_at = now

        return selected

    def admit(
        self,
        namespace: str,
        prompt_norm: str,
        response: dict,
        tokens_saved_if_hit: int,
        ttl_seconds: Optional[float] = None,
    ) -> str:
        vector = self._encode(prompt_norm)

        entry_id = str(uuid.uuid4())
        now = time.time()

        entry = CacheEntry(
            entry_id=entry_id,
            namespace=namespace,
            prompt_norm=prompt_norm,
            response=response,
            created_at=now,
            last_used_at=now,
            ttl_seconds=float(
                ttl_seconds
                if ttl_seconds is not None
                else self.default_ttl
            ),
            tokens_saved_if_hit=max(0, int(tokens_saved_if_hit)),
        )

        self._index.add(vector)
        self._id_map.append(entry_id)
        self._entries[entry_id] = entry
        self._vectors[entry_id] = vector[0].copy()

        return entry_id

    def purge_expired(self) -> int:
        now = time.time()

        keep: list[tuple[str, CacheEntry]] = []

        for entry_id, entry in self._entries.items():
            age = now - entry.created_at

            if age <= entry.ttl_seconds:
                keep.append((entry_id, entry))

        removed = len(self._entries) - len(keep)

        new_index = faiss.IndexFlatIP(self.dimension)
        new_id_map: list[str] = []

        if keep:
            vectors = np.vstack(
                [
                    self._vectors[entry_id]
                    for entry_id, _ in keep
                ]
            ).astype(np.float32)

            new_index.add(vectors)
            new_id_map = [entry_id for entry_id, _ in keep]

        self._index = new_index
        self._id_map = new_id_map
        self._entries = {
            entry_id: entry
            for entry_id, entry in keep
        }
        self._vectors = {
            entry_id: self._vectors[entry_id]
            for entry_id, _ in keep
        }

        return removed

    def clear(self) -> None:
        self._index = faiss.IndexFlatIP(self.dimension)
        self._id_map.clear()
        self._entries.clear()
        self._vectors.clear()

    def stats(self) -> dict:
        return {
            "entries": len(self._entries),
            "faiss_vectors": self._index.ntotal,
            "dimension": self.dimension,
            "base_threshold": self.tau,
            "default_ttl_seconds": self.default_ttl,
            "index_size_mb": round(
                self._index.ntotal
                * self.dimension
                * 4
                / (1024 * 1024),
                3,
            ),
        }