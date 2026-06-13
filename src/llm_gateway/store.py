"""SQLite-backed store for virtual API keys and usage accounting.

Why SQLite: zero-ops, file-or-memory, and perfectly adequate for dev/test and
small self-hosted deployments. Usage is updated inside a single transaction
with row-level ``UPDATE`` so concurrent requests can't lose increments.

The store is intentionally synchronous — SQLite calls are fast and FastAPI's
default threadpool handles the blocking. For high concurrency you'd swap this
for Postgres; the interface is small enough that that's a contained change.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass


@dataclass
class VirtualKey:
    key: str
    name: str
    allowed_models: list[str]
    max_usd: float | None
    max_tokens: int | None
    cache_enabled: bool


@dataclass
class KeyUsage:
    key: str
    requests: int = 0
    cache_hits: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    jtf_potential_tokens_saved: int = 0


def _sqlite_path(database_url: str) -> str:
    """Map a ``sqlite:///...`` URL (or bare path) to a sqlite3 path."""
    if database_url.startswith("sqlite:///"):
        return database_url[len("sqlite:///") :]
    if database_url.startswith("sqlite://"):
        return database_url[len("sqlite://") :]
    return database_url


class Store:
    def __init__(self, database_url: str = "sqlite:///:memory:"):
        path = _sqlite_path(database_url)
        # ``check_same_thread=False`` + a lock lets the FastAPI threadpool share
        # one connection safely. An in-memory DB must keep a single connection.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    key TEXT PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT 'default',
                    allowed_models TEXT NOT NULL DEFAULT '[]',
                    max_usd REAL,
                    max_tokens INTEGER,
                    cache_enabled INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS usage (
                    key TEXT PRIMARY KEY,
                    requests INTEGER NOT NULL DEFAULT 0,
                    cache_hits INTEGER NOT NULL DEFAULT 0,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    cost_usd REAL NOT NULL DEFAULT 0.0,
                    jtf_saved INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (key) REFERENCES api_keys(key)
                );
                CREATE TABLE IF NOT EXISTS request_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    key TEXT,
                    model TEXT,
                    provider TEXT,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    cost_usd REAL,
                    cache_hit INTEGER,
                    jtf_saved INTEGER,
                    status INTEGER
                );
                """
            )
            self._conn.commit()

    # ----- key management ---------------------------------------------------

    def upsert_key(self, vk: VirtualKey) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO api_keys (key, name, allowed_models, max_usd,
                                      max_tokens, cache_enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    name=excluded.name,
                    allowed_models=excluded.allowed_models,
                    max_usd=excluded.max_usd,
                    max_tokens=excluded.max_tokens,
                    cache_enabled=excluded.cache_enabled
                """,
                (
                    vk.key,
                    vk.name,
                    json.dumps(vk.allowed_models),
                    vk.max_usd,
                    vk.max_tokens,
                    1 if vk.cache_enabled else 0,
                    time.time(),
                ),
            )
            self._conn.execute(
                "INSERT OR IGNORE INTO usage (key) VALUES (?)", (vk.key,)
            )
            self._conn.commit()

    def get_key(self, key: str) -> VirtualKey | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM api_keys WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        return VirtualKey(
            key=row["key"],
            name=row["name"],
            allowed_models=json.loads(row["allowed_models"]),
            max_usd=row["max_usd"],
            max_tokens=row["max_tokens"],
            cache_enabled=bool(row["cache_enabled"]),
        )

    def list_keys(self) -> list[VirtualKey]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM api_keys").fetchall()
        return [
            VirtualKey(
                key=r["key"],
                name=r["name"],
                allowed_models=json.loads(r["allowed_models"]),
                max_usd=r["max_usd"],
                max_tokens=r["max_tokens"],
                cache_enabled=bool(r["cache_enabled"]),
            )
            for r in rows
        ]

    # ----- usage ------------------------------------------------------------

    def get_usage(self, key: str) -> KeyUsage:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM usage WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return KeyUsage(key=key)
        return KeyUsage(
            key=row["key"],
            requests=row["requests"],
            cache_hits=row["cache_hits"],
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            total_tokens=row["total_tokens"],
            cost_usd=row["cost_usd"],
            jtf_potential_tokens_saved=row["jtf_saved"],
        )

    def would_exceed_budget(
        self, key: str, vk: VirtualKey, projected_cost: float, projected_tokens: int
    ) -> str | None:
        """Return a human reason if charging this request breaks the budget.

        Checked *before* forwarding so we can reject with 402 without spending.
        Uses already-recorded usage plus the projected cost/tokens of this call.
        """
        usage = self.get_usage(key)
        if vk.max_usd is not None and usage.cost_usd + projected_cost > vk.max_usd:
            return (
                f"budget exceeded: spend ${usage.cost_usd:.6f} + "
                f"${projected_cost:.6f} would exceed cap ${vk.max_usd:.2f}"
            )
        if (
            vk.max_tokens is not None
            and usage.total_tokens + projected_tokens > vk.max_tokens
        ):
            return (
                f"budget exceeded: tokens {usage.total_tokens} + "
                f"{projected_tokens} would exceed cap {vk.max_tokens}"
            )
        return None

    def record_usage(
        self,
        key: str,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        cache_hit: bool,
        jtf_saved: int,
    ) -> None:
        """Atomically add a request's usage to the key's running totals."""
        total = prompt_tokens + completion_tokens
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO usage (key) VALUES (?)", (key,)
            )
            self._conn.execute(
                """
                UPDATE usage SET
                    requests = requests + 1,
                    cache_hits = cache_hits + ?,
                    prompt_tokens = prompt_tokens + ?,
                    completion_tokens = completion_tokens + ?,
                    total_tokens = total_tokens + ?,
                    cost_usd = cost_usd + ?,
                    jtf_saved = jtf_saved + ?
                WHERE key = ?
                """,
                (
                    1 if cache_hit else 0,
                    prompt_tokens,
                    completion_tokens,
                    total,
                    cost_usd,
                    jtf_saved,
                    key,
                ),
            )
            self._conn.commit()

    def log_request(
        self,
        *,
        key: str | None,
        model: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        cache_hit: bool,
        jtf_saved: int,
        status: int,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO request_log
                    (ts, key, model, provider, prompt_tokens, completion_tokens,
                     cost_usd, cache_hit, jtf_saved, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    time.time(),
                    key,
                    model,
                    provider,
                    prompt_tokens,
                    completion_tokens,
                    cost_usd,
                    1 if cache_hit else 0,
                    jtf_saved,
                    status,
                ),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
