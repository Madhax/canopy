# canopy-server

FastAPI thin control plane for the Canopy org-chart editor (Phase 1). Persists and validates
serialized Organization documents. See [`../docs/org-chart-editor.md`](../docs/org-chart-editor.md)
§5–§6 for the contract this implements.

## Dev

From the repo root:

```sh
uv sync --project server        # install deps
pnpm dev                        # runs this + the UI (uvicorn :8700, vite :5173)
```

Standalone:

```sh
uv run --project server uvicorn canopy_server.main:app --reload --port 8700
uv run --project server pytest server/tests -q
```

## Layout (Phase 1)

- `models.py` — Pydantic v2 schema for Organization documents and the catalog.
- `validation/` — the authoritative rule set (`codes.py`, `rules.py`).
- `catalog.py` — loads `../catalog/catalog.json`, integrity-checked at import.
- `store.py` — JSON file store with atomic writes (`CANOPY_DATA_DIR`, default `./data`).
- `routes/` — `health`, `catalog`, `organizations`.
- `main.py` — app factory; serves the built UI (`ui/dist`) in production.

## Phase 2 — Actuation (milestones A1 + A2 + A3)

Phase 2 turns the thin store into a control plane that provisions running agents. Implementations
are selected by `../canopy.toml` (see `docs/actuation/topology.md`); every module owns its own
SQLite tables and sits behind an ABC so it can be extracted later without touching the others.

**A1 — profiles, secrets, gateway, ledger:**

- `db.py` — SQLite handle (`data/canopy.db`, WAL). `transaction()` opens `BEGIN IMMEDIATE` so the
  ledger's reserve→record is race-free (the money path).
- `sqlite_store.py` — organization store on SQLite; migrates phase-1 `organizations/*.json`
  non-destructively on first run. Phase-1 REST contract unchanged.
- `secretstore.py` — Fernet-encrypted API keys; plaintext revealed only to the gateway.
- `profiles.py` — Agent Profiles + Bindings (which model powers each node), kept out of the chart.
- `ledger.py` — Budget Ledger: salaries → meters → spend, mechanical hard-stop, step-id idempotent.
- `gateway/` — the Model Gateway: `mock` (default), `anthropic`, `gemini` adapters; Steps +
  SpendEvents; budget-check-before-dispatch; per-provider concurrency caps.
- `runtokens.py`, `activity.py` — least-privilege agent identity; append-only audit log.

**A2 — sandbox + runtime boot:**

- `sandbox/` — `SandboxProvider` ABC + `SubprocessSandbox` (Windows-safe tree-kill, clean env).
- `directory.py` — Agent Directory: node → endpoint / card / status / heartbeat.
- `charter.py` — compiles what an agent is told at boot (role instructions + extensions + preamble).
- `actuator.py` — provision/teardown state machine + reconciler (restarts stale nodes).
- `../agent/` — the standalone **`canopy-agent`** package (separate pyproject; never imports the
  control plane). `pnpm dev` spawns it per node automatically — no new command.
- `routes/actuations.py` — actuate / deactuate / current; `routes/dp.py` adds charter/register/
  heartbeat to the run-token data plane.

**A3 — router + bus:**

- `bus.py` — `Bus` ABC + `SqliteBus`: per-topic FIFO, atomic claim with visibility timeout, DLQ.
  The queue semantics follow Paperclip's `agent_wakeup_requests` (the DX reference) — including
  **idempotency-key dedupe** and **coalescing** (`coalesced_count`) so a hot node's inbox can't
  explode.
- `router.py` — `MessageRouter`: channels derived from the chart, topology enforcement (403
  `CHANNEL_FORBIDDEN` for sibling calls), mediated send onto the bus. The second chokepoint —
  agents never learn peer addresses, only node ids.
- delivery workers (`main.py` `_delivery_loop`) forward queued messages to *idle* agents' `/inbox`;
  `routes/dp.py` adds `POST /api/dp/a2a/{target}` (the only way an agent reaches a peer).

### Try the gateway without the Actuator (A2)

```sh
# mint a run token + meter for an org, then curl the gateway as a fake agent
uv run --project server python -m canopy_server.devkit mint-session --org <ORG_ID>
# -> prints a runToken and a ready-to-run curl for POST /api/dp/llm/complete (mock, $0 spend)
```

### Load test the fabric (zero API spend)

```sh
uv run --project server python ../scripts/loadtest_gateway.py --agents 50 --steps 20
```

Reveals the SQLite write-contention ceiling with the deterministic mock provider (risk AR-1).
Batching step+spend writes is the documented lever when that ceiling bites.
