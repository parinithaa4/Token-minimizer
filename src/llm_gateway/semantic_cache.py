"""FAISS-backed L2 semantic cache with an age-aware similarity threshold."""

from __future__ import annotations

import hashlib
import re
import time
import uuid
from dataclasses import dataclass
from typing import Optional

import numpy as np

try:
    import faiss
except ImportError:
    faiss = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None


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


class FeatureHashingEncoder:
    """Fast, zero-dependency 384-d semantic feature encoder.

    Uses content-word unigrams, character n-grams, and bigrams with signed hashing
    and L2 unit normalization. Paraphrases share significant vector components,
    giving high cosine similarity (~0.80 - 0.95), while unrelated queries remain
    near orthogonal (~0.0).
    """

    STOPWORDS = {
        "a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by",
        "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "do", "does", "did", "can", "could", "will", "would", "should",
        "i", "you", "he", "she", "it", "we", "they", "my", "your", "his", "her",
        "our", "their", "what", "which", "who", "whom", "this", "that", "these",
        "those", "am", "please", "tell", "me", "how", "why", "thanks", "quick",
        "question", "re", "just", "want", "like", "know"
    }

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def encode(
        self,
        texts: list[str],
        normalize_embeddings: bool = True,
        convert_to_numpy: bool = True,
    ) -> np.ndarray:
        vectors = []
        for text in texts:
            v = np.zeros(self.dimension, dtype=np.float32)
            words = re.findall(r"[a-zA-Z0-9_\-\+]+", text.lower())
            content_words = [w for w in words if w not in self.STOPWORDS]
            if not content_words:
                content_words = words

            for w in content_words:
                idx = int(hashlib.sha256(w.encode("utf-8")).hexdigest(), 16) % self.dimension
                v[idx] += 4.0

                for n in (3, 4):
                    for i in range(len(w) - n + 1):
                        gram = w[i:i + n]
                        gidx = int(hashlib.sha256(gram.encode("utf-8")).hexdigest(), 16) % self.dimension
                        v[gidx] += 1.0

            for i in range(len(content_words) - 1):
                bi = f"{content_words[i]}_{content_words[i + 1]}"
                bidx = int(hashlib.sha256(bi.encode("utf-8")).hexdigest(), 16) % self.dimension
                v[bidx] += 2.0

            if normalize_embeddings:
                norm = np.linalg.norm(v)
                if norm > 0:
                    v = v / norm

            vectors.append(v)

        return np.asarray(vectors, dtype=np.float32)


class SemanticCache:
    """In-memory FAISS semantic cache with an age-aware similarity threshold.

    Embeddings are L2-normalized, therefore inner-product equals cosine similarity.
    Namespace filtering is performed after similarity search.
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

        # Model initialization: prefer sentence-transformers if available, else feature hashing
        self._model = None
        if SentenceTransformer is not None:
            try:
                self._model = SentenceTransformer(embed_model_name)
            except Exception:
                self._model = None

        if self._model is None:
            self._model = FeatureHashingEncoder(dimension=384)

        probe = self._model.encode(
            ["dimension probe"],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        probe = np.asarray(probe, dtype=np.float32)

        if probe.ndim != 2 or probe.shape[0] != 1:
            raise RuntimeError("embedding model returned an invalid shape")

        self.dimension = int(probe.shape[1])

        if faiss is not None:
            self._index = faiss.IndexFlatIP(self.dimension)
        else:
            self._index = None

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
        if len(self._id_map) == 0:
            return None

        query = self._encode(prompt_norm)

        k = min(self.k, len(self._id_map))

        if self._index is not None:
            scores, indices = self._index.search(query, k)
            search_results = list(zip(scores[0], indices[0]))
        else:
            # Fallback dot product if FAISS is not present
            all_vecs = np.vstack([self._vectors[eid] for eid in self._id_map])
            sims = np.dot(all_vecs, query[0])
            top_k_indices = np.argsort(sims)[::-1][:k]
            search_results = [(sims[idx], idx) for idx in top_k_indices]

        now = time.time()
        candidates: list[SemanticLookup] = []

        for score, row in search_results:
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

        if self._index is not None:
            self._index.add(vector)

        self._id_map.append(entry_id)
        self._entries[entry_id] = entry
        self._vectors[entry_id] = vector[0].copy()

        return entry_id

    def evict(self, entry_id: str) -> bool:
        """Evict a specific entry and rebuild the index."""
        if entry_id not in self._entries:
            return False

        del self._entries[entry_id]
        if entry_id in self._vectors:
            del self._vectors[entry_id]

        keep_entries = [
            (eid, self._entries[eid])
            for eid in self._id_map
            if eid != entry_id and eid in self._entries
        ]

        self._rebuild_index(keep_entries)
        return True

    def simulate_age(self, entry_id: str, age_seconds: float) -> Optional[float]:
        """Simulate age for demonstration of the elastic cutoff curve."""
        entry = self._entries.get(entry_id)
        if not entry:
            return None
        entry.created_at = time.time() - age_seconds
        current_age = max(0.0, time.time() - entry.created_at)
        return self.effective_threshold(self.tau, current_age, entry.ttl_seconds)

    def _rebuild_index(self, keep: list[tuple[str, CacheEntry]]) -> None:
        if self._index is not None:
            new_index = faiss.IndexFlatIP(self.dimension)
            if keep:
                vectors = np.vstack(
                    [self._vectors[eid] for eid, _ in keep]
                ).astype(np.float32)
                new_index.add(vectors)
            self._index = new_index

        self._id_map = [eid for eid, _ in keep]
        self._entries = {eid: entry for eid, entry in keep}
        self._vectors = {eid: self._vectors[eid] for eid, _ in keep}

    def purge_expired(self) -> int:
        now = time.time()
        keep: list[tuple[str, CacheEntry]] = []

        for entry_id in self._id_map:
            entry = self._entries.get(entry_id)
            if entry is None:
                continue
            age = now - entry.created_at
            if age <= entry.ttl_seconds:
                keep.append((entry_id, entry))

        removed = len(self._entries) - len(keep)
        self._rebuild_index(keep)
        return removed

    def clear(self) -> None:
        if self._index is not None:
            self._index = faiss.IndexFlatIP(self.dimension)
        self._id_map.clear()
        self._entries.clear()
        self._vectors.clear()

    def list_entries(self) -> list[dict]:
        now = time.time()
        out = []
        for eid in self._id_map:
            e = self._entries.get(eid)
            if not e:
                continue
            age = max(0.0, now - e.created_at)
            eff_tau = self.effective_threshold(self.tau, age, e.ttl_seconds)
            out.append({
                "entry_id": e.entry_id,
                "namespace": e.namespace,
                "prompt_norm": e.prompt_norm,
                "age_seconds": round(age, 1),
                "ttl_seconds": e.ttl_seconds,
                "effective_threshold": round(eff_tau, 4),
                "is_expired": age > e.ttl_seconds,
                "tokens_saved": e.tokens_saved_if_hit,
                "created_at": e.created_at,
                "last_used_at": e.last_used_at,
            })
        return out

    def stats(self) -> dict:
        total_vectors = self._index.ntotal if self._index is not None else len(self._id_map)
        return {
            "entries": len(self._entries),
            "faiss_vectors": total_vectors,
            "dimension": self.dimension,
            "base_threshold": self.tau,
            "default_ttl_seconds": self.default_ttl,
            "index_size_mb": round(
                total_vectors * self.dimension * 4 / (1024 * 1024),
                3,
            ),
        }