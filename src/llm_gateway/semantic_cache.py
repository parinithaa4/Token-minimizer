"""
semantic_cache.py — L2 similarity cache with age-aware threshold (tau_eff)

Implements the semantic ("near-duplicate") cache described in TokenMinGate
Section III-B and the age-based cut-off in Section IV-A (Eq. 2).

    tau_eff(a_i) = tau + (1 - tau) * min(1, a_i / T_k)

Dependencies:
    pip install faiss-cpu sentence-transformers numpy

Drop this into src/llm_gateway/semantic_cache.py and wire it into
gateway.py's request path — after an L1 miss, before prompt pruning /
DISPATCH (see Algorithm 1, lines 5-14 and 19). See INTEGRATION.md.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Optional

import numpy as np

try:
    import faiss
except ImportError as e:
    raise ImportError(
        "semantic_cache requires faiss-cpu. Install with: pip install faiss-cpu"
    ) from e

try:
    from sentence_transformers import SentenceTransformer
except ImportError as e:
    raise ImportError(
        "semantic_cache requires sentence-transformers. "
        "Install with: pip install sentence-transformers"
    ) from e


DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"  # 384-dim, 22.7M params
EMBED_DIM = 384


@dataclass
class CacheEntry:
    """One saved (prompt, response) pair in the L2 index."""
    entry_id: str
    namespace: str
    prompt_norm: str
    response: dict
    created_at: float
    last_used_at: float
    ttl_seconds: float          # T_k -- max lifespan for this entry's "type"
    tokens_saved_if_hit: int    # tokens of the original request (for TRR bookkeeping)


class SemanticCache:
    """
    FAISS-backed similarity cache with an age-rising acceptance threshold.

    A saved entry is only reusable while cos_sim(query, entry) >= tau_eff(age).
    As an entry approaches its TTL, tau_eff climbs to 1.0 -- i.e. it becomes
    unreusable except by a near-identical prompt (paper Fig. 2/3).
    """

    def __init__(
        self,
        base_threshold: float = 0.84,                 # tau -- paper's chosen operating point
        default_ttl_seconds: float = 7 * 24 * 3600,    # default T_k (7 days)
        embed_model_name: str = DEFAULT_MODEL_NAME,
        k_neighbors: int = 5,
    ) -> None:
        if not (0.0 <= base_threshold < 1.0):
            raise ValueError("base_threshold (tau) must be in [0, 1)")
        self.tau = base_threshold
        self.default_ttl = default_ttl_seconds
        self.k = k_neighbors

        self._model = SentenceTransformer(embed_model_name)
        # Inner product on L2-normalized vectors == cosine similarity.
        self._index = faiss.IndexFlatIP(EMBED_DIM)
        self._id_map: list[str] = []          # FAISS row -> entry_id
        self._entries: dict[str, CacheEntry] = {}

    # ---------- embedding ----------

    def _encode(self, text: str) -> np.ndarray:
        vec = self._model.encode([text], normalize_embeddings=True)
        return np.asarray(vec, dtype="float32")

    # ---------- age-based threshold (Eq. 2) ----------

    @staticmethod
    def effective_threshold(tau: float, age_seconds: float, ttl_seconds: float) -> float:
        if ttl_seconds <= 0:
            return 1.0
        normalized_age = min(1.0, max(0.0, age_seconds / ttl_seconds))
        return tau + (1.0 - tau) * normalized_age

    # ---------- lookup (Algorithm 1, lines 5-14) ----------

    def lookup(self, namespace: str, prompt_norm: str) -> Optional[CacheEntry]:
        """Return the best matching, still-valid entry for this namespace, or None."""
        if self._index.ntotal == 0:
            return None

        query = self._encode(prompt_norm)
        k = min(self.k, self._index.ntotal)
        scores, idxs = self._index.search(query, k)

        now = time.time()
        for score, row in zip(scores[0], idxs[0]):
            if row == -1:
                continue
            entry_id = self._id_map[row]
            entry = self._entries.get(entry_id)
            if entry is None or entry.namespace != namespace:
                continue

            age = now - entry.created_at
            if age > entry.ttl_seconds:
                continue  # expired outright

            tau_eff = self.effective_threshold(self.tau, age, entry.ttl_seconds)
            if score >= tau_eff:
                entry.last_used_at = now
                return entry
        return None

    # ---------- admission (Algorithm 1, line 19 / ADMITTOCACHE) ----------

    def admit(
        self,
        namespace: str,
        prompt_norm: str,
        response: dict,
        tokens_saved_if_hit: int,
        ttl_seconds: Optional[float] = None,
    ) -> str:
        vec = self._encode(prompt_norm)
        entry_id = str(uuid.uuid4())
        now = time.time()

        entry = CacheEntry(
            entry_id=entry_id,
            namespace=namespace,
            prompt_norm=prompt_norm,
            response=response,
            created_at=now,
            last_used_at=now,
            ttl_seconds=ttl_seconds or self.default_ttl,
            tokens_saved_if_hit=tokens_saved_if_hit,
        )

        self._index.add(vec)
        self._id_map.append(entry_id)
        self._entries[entry_id] = entry
        return entry_id

    # ---------- housekeeping ----------

    def purge_expired(self) -> int:
        """
        FAISS's IndexFlatIP has no cheap delete-by-id, so we rebuild the
        index from scratch, dropping anything past its TTL. Call this
        periodically (e.g. from a background task), not on every request.
        """
        now = time.time()
        keep = [
            (eid, e) for eid, e in self._entries.items()
            if (now - e.created_at) <= e.ttl_seconds
        ]
        removed = len(self._entries) - len(keep)

        new_index = faiss.IndexFlatIP(EMBED_DIM)
        new_id_map: list[str] = []
        if keep:
            vecs = np.vstack([self._encode(e.prompt_norm) for _, e in keep])
            new_index.add(vecs)
            new_id_map = [eid for eid, _ in keep]

        self._index = new_index
        self._id_map = new_id_map
        self._entries = {eid: e for eid, e in keep}
        return removed

    def stats(self) -> dict:
        """Matches paper Eq. 11's index-memory estimate: M_index = 4 * N * d bytes."""
        return {
            "entries": len(self._entries),
            "index_size_mb": round(self._index.ntotal * EMBED_DIM * 4 / (1024 * 1024), 3),
        }