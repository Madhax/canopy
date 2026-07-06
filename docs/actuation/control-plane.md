# Control Plane — Services, API, and Persistence

The phase-2 control plane extends the phase-1 FastAPI server (same process, same port 8700 in v1) with the modules below. Every module follows the topology rules: ABC interface, own tables, Pydantic boundaries, registry-selected implementations.

## 1. Persistence

SQLite via a thin repository layer (`sqlite3` + hand-written repos or SQLAlchemy Core — implementer's choice, but no ORM entanglement across module boundaries). One file `data/canopy.db`, WAL mode. Phase-1 organization documents migrate from JSON files into an `organizations` table (`id`, `document` JSON, `updated_at`) — the phase-1 REST contract is unchanged. Postgres later = repo-layer swap (`roadmap.md`).

Tables by owner (prefixed per module): `profiles.*` (agent_profiles, agent_bindings, secrets), `actuation.*` (actuations, actuation_nodes), `directory.*` (agents), `gateway.*` (steps), `ledger.*` (meters, spend_events), `router.*` (channels, messages, queues), `artifacts.*` (artifacts, artifact_blobs metadata), `activity.*` (events).

## 2. Actuator

Owns the desired-vs-actual reconciliation for an organization. State machine per actuation:

```
requested → validating → provisioning → live
                │              │            │ (node crash) → degraded → (reconcile) → live
                └── failed ◄───┘            │
 live → draining → stopped        (deactuate: drain queues, stop agents, revoke tokens, destroy sandboxes)
```

Per-node sub-state: `pending → sandbox_created → booting → registered → ready` (or `failed`). Provisioning walks the org tree **top-down** (root first — reports need their manager's identity known; nested child orgs recurse at their mount, each child org's agents provisioned like any other subtree). For each node:

1. Mint identity + **run token** (random 256-bit, stored hashed, scoped to `{actuationId, agentNodeId}`).
2. Compile the **agent charter**: role instructions (RoleTemplate base + node extensions + profile `systemPreamble`), manager id, report ids, salary numbers, org/intent context stub. Stored on the actuation node record; served to the agent at boot.
3. `SandboxProvider.create(spec)` → workspace dir + process spawn (`sandbox.md`).
4. Await agent registration (agent calls `POST /api/dp/register` with its A2A endpoint) within a boot timeout; health-check its A2A card; mark `ready`.

Reconciler loop (Paperclip-recovery-style): every 15 s and on startup, compare directory liveness (agent heartbeats) against desired state; restart dead nodes (with backoff, max N attempts → `degraded` + activity event). **Chart edits while `live` are rejected** in v1 (HTTP 409 from the phase-1 PUT when an actuation is live) — deactuate, edit, re-actuate.

## 3. Agent Directory

Registry of live agents: `{ actuationId, agentNodeId, endpointUrl, agentCardJson, status, lastHeartbeatAt }`. Status is the domain's observable set, reduced for phase 2: `provisioning | idle | engaged | paused | dead`. Agents heartbeat every 10 s (`POST /api/dp/heartbeat` with current status + optional progress note). The directory feeds the router (where to deliver) and the UI (live chart badges).

## 4. Model Gateway

The only path to LLM APIs. `POST /api/dp/llm/complete` (run-token auth):

1. Resolve token → node → binding → profile → secret.
2. **Budget check first** (invariant 7): `BudgetLedger.reserve(meterId)` — if the meter is exhausted, return `402 BUDGET_EXHAUSTED` *without dispatching*; the ledger flips the meter state and the directory marks the node `paused` (phase-2's simplified hard-stop; a full InterventionGate arrives in phase 3).
3. Dispatch via the provider adapter; record a **Step** `{ id, actuationId, nodeId, taskId, inputTokens, outputTokens, durationMs, stopReason, deltaNote? }`.
4. Emit a **SpendEvent** attributed `(org, actuation, node, taskId, stepId, provider, model, tokens, estCost)`; return the normalized result.

Streaming is deliberately deferred (agents are non-interactive; buffered responses simplify metering). Cost estimation uses a static per-model price table in config, clearly labeled estimate.

## 5. Budget Ledger

Phase-2 simplification of the economics layer, forward-compatible with phase 3: at actuation, each node gets **one standing meter** funded from its chart salary `perAssignmentAllowance` **per received task** (a fresh meter per task delivered by the router — approximating "per-assignment allowance" without full Assignment objects). Warn threshold and hard-stop come from the chart's salary block. All mutations are single SQLite transactions (reserve → spend → settle), so hard-stops are race-free. Rollups (`GET /api/organizations/{id}/spend?groupBy=node|task|model`) power the UI's burn view. Phase 3 replaces "meter per routed task" with real Assignment-bound meters — the ledger interface (`open_meter`, `reserve`, `record`, `close_meter`) already matches.

## 6. Message Router

Detailed in `data-plane.md`. Control-plane surface: `POST /api/dp/a2a/{targetNodeId}` (run-token auth; the *only* way any agent reaches any other), channel table enforcing topology, per-agent durable delivery queues, and the operator intent entrypoint (`POST /api/organizations/{id}/intents` → routed to the root agent as an A2A task).

## 7. Artifact Store

`workspace.md` details the agent-facing flow. Storage: content blobs under `data/artifacts/<sha256[0:2]>/<sha256>`, metadata rows `{ ref, orgId, producedByNodeId, taskId, type, filename, size, sha256, version, prevVersion, createdAt }`. Refs follow the domain grammar `org://<org-slug>/<node-or-team>/<name>@<version>`; immutable; new versions link back. Interface (`put/get/resolve/list`) is object-store-shaped so S3/GCS is a backend swap.

## 8. Activity Log

Append-only `{ ts, actor (operator|system|nodeId), kind, subjectIds, payload }` for every mutating action and lifecycle transition: actuation state changes, registrations, message deliveries (metadata, not bodies — bodies live in `router.messages`), budget warns/stops, artifact publishes, intent submissions/completions. Backs the UI activity feed and is the audit substrate invariants lean on.

## 9. REST API additions (operator-facing, `/api`)

| Method & path | Purpose |
|---|---|
| `POST /organizations/{id}/actuations` | Actuate (validates bindings/readiness → `202` with actuation id) |
| `GET /organizations/{id}/actuations/current` | Full actuation state incl. per-node status (UI polls or SSE) |
| `DELETE /organizations/{id}/actuations/current` | Deactuate (drain → teardown) |
| `POST /organizations/{id}/intents` | Submit intent `{ text, targetNodeId? (default root) }` → `{ intentId, taskId }` |
| `GET /organizations/{id}/intents/{intentId}` | Status + final artifact refs + spend rollup |
| `GET/POST/PUT/DELETE /organizations/{id}/profiles`, `/bindings`, `/secrets` | Profile management (`agent-profile.md`) |
| `GET /organizations/{id}/spend` | Ledger rollups |
| `GET /organizations/{id}/activity` | Activity feed (cursor-paginated) |
| `GET /artifacts/{ref}` | Artifact metadata; `?content=1` streams the blob |

Data-plane API (`/api/dp/*`, run-token auth only): `register`, `heartbeat`, `llm/complete`, `a2a/{targetNodeId}`, `inbox/poll`, `artifacts` (put), `artifacts/{ref}` (get, grant-checked). Loopback-bound in v1.

## 10. UI additions (phase-1 editor extensions)

Org settings gains **Profiles & Secrets**; node inspector gains the **Binding picker**; toolbar gains **Actuate/Deactuate** with a readiness dialog (binding/validation results); actuated canvas shows per-node status pills (idle/engaged/paused/dead) and burn sparkline from the ledger; a new **Intent** panel submits intents and shows the live task tree + resulting artifacts; activity feed drawer. The editor stays usable read-only while live (structure locked, status live).
