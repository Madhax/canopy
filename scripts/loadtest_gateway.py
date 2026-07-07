"""Gateway fabric load test — measure the write-contention ceiling, free (risk AR-1).

"50 fake agents × 20 steps each is an afternoon's test that reveals the real write-contention
ceiling with zero API spend." Run it, set a measured budget ("v1 comfortably supports N concurrent
agents"), and publish it — rather than discovering it in a user's demo.

    uv run --project server python scripts/loadtest_gateway.py --agents 50 --steps 20

Uses the deterministic mock provider through the *real* gateway → ledger → SQLite path, so the
numbers reflect actual reserve/record/step-insert transaction throughput on one process/one file.
"""

from __future__ import annotations

import argparse
import asyncio
import tempfile
import time
from pathlib import Path

from canopy_server.activity import ActivityLog
from canopy_server.db import Db
from canopy_server.gateway import DefaultModelGateway
from canopy_server.gateway.base import CompletionRequest, Message
from canopy_server.ids import new_actuation_id, new_agent_id
from canopy_server.ledger import SqliteLedger
from canopy_server.profiles import ProfileParams, ProfileStore
from canopy_server.runtokens import RunTokenStore
from canopy_server.secretstore import LocalEncryptedSecretStore


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", type=int, default=50)
    ap.add_argument("--steps", type=int, default=20)
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="canopy-load-"))
    db = Db(tmp / "canopy.db")
    profiles = ProfileStore(db)
    gateway = DefaultModelGateway(
        db,
        profiles,
        LocalEncryptedSecretStore(db, tmp),
        SqliteLedger(db),
        RunTokenStore(db),
        ActivityLog(db),
        prices={},
        concurrency={"mock": args.agents},
    )
    ledger = SqliteLedger(db)
    runtokens = RunTokenStore(db)

    tokens: list[str] = []
    for i in range(args.agents):
        profile = profiles.create_profile(
            "loadorg", name=f"agent{i}", provider="mock", model="mock-1",
            params=ProfileParams(maxOutputTokens=64),
        )
        node = new_agent_id()
        profiles.set_binding("loadorg", node, profile.id)
        actuation = new_actuation_id()
        meter = ledger.open_meter(actuation, node, 10_000_000)
        token, _ = runtokens.issue(actuation, node, "loadorg", default_meter_id=meter.id)
        tokens.append(token)

    req = CompletionRequest(messages=[Message(role="user", content="do the thing")])

    async def run_agent(token: str) -> None:
        for _ in range(args.steps):
            await gateway.complete(token, req, kind="production")

    start = time.perf_counter()
    await asyncio.gather(*(run_agent(t) for t in tokens))
    elapsed = time.perf_counter() - start

    total = args.agents * args.steps
    print(
        f"{total} steps in {elapsed:.2f}s -> {total / elapsed:.0f} steps/s"
        f"  ({args.agents} agents x {args.steps} steps, mock provider, $0 spend)"
    )
    print(f"  db: {tmp / 'canopy.db'}")


if __name__ == "__main__":
    asyncio.run(main())
