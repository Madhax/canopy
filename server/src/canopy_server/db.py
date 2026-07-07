"""SQLite handle: connections, transactions, and a per-module schema registry.

One file ``data/canopy.db`` in WAL mode backs the whole control plane in v1 (topology.md §4).
Postgres later is a repository-layer swap — callers depend on this handle and on their module's
repo, never on ``sqlite3`` directly (topology rule 2: no shared tables; rule 1: interface first).

Two deliberate choices support the money path (risk IM-5, "the one bug class Canopy can't shrug
off"):

* **A fresh connection per operation.** No shared connection across threads (FastAPI runs sync
  endpoints in a worker pool), so there is no cross-thread ``sqlite3`` misuse and no long-held
  locks. WAL keeps readers and the single writer from blocking each other.
* **``transaction()`` opens ``BEGIN IMMEDIATE``.** The ledger's reserve→spend→settle sequence
  takes the write lock up front, so a hard-stop check and the spend it authorizes are one atomic
  unit and can never interleave with another agent's step.

Modules register their DDL with :func:`register_schema` at import time; :meth:`Db.ensure_schema`
applies every registered schema (idempotent ``CREATE TABLE IF NOT EXISTS``). This keeps each
table's definition inside its owning module while still creating them all against one file — and
means a module booted standalone (the extraction smoke test, risk AR-1) creates exactly its own
tables and no others.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# Module DDL, in registration order. Populated by register_schema() at import time.
_SCHEMAS: list[str] = []


def register_schema(sql: str) -> None:
    """Register a module's ``CREATE TABLE IF NOT EXISTS`` script (called at import time)."""
    if sql not in _SCHEMAS:
        _SCHEMAS.append(sql)


class Db:
    """A handle to one SQLite database file. Cheap to construct; holds no open connection."""

    def __init__(self, path: Path):
        self.path = path
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.path,
            timeout=30,
            isolation_level=None,  # autocommit; we manage BEGIN/COMMIT explicitly
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """A short-lived autocommit connection for reads and single-statement writes."""
        conn = self._open()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """A write transaction under ``BEGIN IMMEDIATE`` — commits on success, rolls back on error.

        Use this for any multi-statement mutation that must be atomic, above all the ledger's
        reserve/spend/settle (risk IM-5). ``IMMEDIATE`` acquires the write lock at ``BEGIN`` so
        the read-check-write cannot race another writer.
        """
        conn = self._open()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def ensure_schema(self) -> None:
        """Apply every registered module schema. Idempotent; safe to call repeatedly."""
        conn = self._open()
        try:
            for sql in _SCHEMAS:
                conn.executescript(sql)
        finally:
            conn.close()
