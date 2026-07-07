# Phase-2 → Phase-3 Debt Ledger

**Status:** Living · **Purpose:** the explicit list of every knowingly-simplified Phase-2 semantic
and its Phase-3 end-state (risk AR-5). The danger isn't any single simplification — each is flagged
in the design — it's *interaction*: UI, ledger rollups, and operator habits calcifying around the
simplified shapes until Phase 3 becomes a breaking migration of live orgs. The mitigation is to
**name the placeholder objects with their final names now** and version the operator-facing API so
gate-era responses extend rather than mutate.

Each row: what A1–A6 ship, the Phase-3 target, and what keeps the seam honest.

| # | Phase-2 simplification | Phase-3 end-state | Seam that stays honest |
|---|---|---|---|
| D1 | **Meter per node** (A1: one standing meter; run token carries `default_meter_id`). Control-plane §5's "meter per routed task" arrives in A5. | Real **Assignment-bound** meters, one per Assignment with rework-funding rules. | Ledger interface is already `open_meter / reserve / record / close_meter`; `Meter` already carries `taskId` (nullable now). No rename at Phase 3. |
| D2 | **Directory status** reduced to `provisioning \| idle \| engaged \| paused \| dead`. | Full domain status incl. `gated` with a kind. | Status is a string enum in one place; Phase 3 *adds* members, never repurposes existing ones. |
| D3 | **"rejected + reason"** stands in for a ClarificationGate (data-plane §4). | Real **ClarificationGate**: versioned briefs, rework funding follows brief version. | The A2A `rejected` state carries a reason message today; the gate wraps the same transition. |
| D4 | **`input-required`** stands in for EscalationGate; no ApprovalGate/DependencyGate/InterventionGate yet. | Five Gate kinds with owners and resolutions (domain §Gates). | "All suspension is a Gate" (invariant 8) — Phase 2 simply has one informal suspension; the API is versioned so gate objects extend the task-status response. |
| D5 | **Workspace persists across tasks** within an actuation; `memory.json` is a scratch stub (agent-runtime §5, workspace §1). | Fresh workspace **per Assignment** + platform-managed **durable memory**. | Workspace layout (`brief/ work/ out/`) and the memory boundary already exist; Phase 3 changes provisioning lifetime, not the contract. |
| D6 | **Step `kind`** is `coordination \| production` (added in A1 for the SC-1 overhead metric). | Same tag, plus the full Step **delta taxonomy** (artifact-diff / tool-effect / progress / none). | `Step.deltaNote` field is reserved now; the closed delta enum slots into it. |
| D7 | **No incremental re-actuation** — v1 is deactuate → edit → re-actuate. | Add/remove nodes on a live org. | Actuator is a desired-vs-actual reconciler (A2); incremental diffing is new logic behind the same state machine. |
| D8 | **Chart edit while live rejected** (HTTP 409). | Structural edits reconcile live (paired with D7). | The 409 is a policy check, not a data shape — lifting it doesn't migrate anything. |
| D9 | **A3 delivers over plain HTTP** `POST /inbox` (push) with a minimal Agent Card; agents *record* deliveries, no task lifecycle yet. | Full `a2a-sdk` task server (working / input-required / completed) + the step loop that acts on deliveries (A4). | A2A is confined to one adapter seam (risk AR-4): the router speaks envelopes, the agent's receive endpoint swaps for the a2a-sdk server without touching the loop. |

## Not debts — deliberate Phase-2 assets

- **`mock` model provider.** Added as a first-class provider (the docs named `anthropic`/`gemini`
  as the closed v1 enum). This is the testing/demo spine (risk IM-2), not a placeholder — it stays.
- **Idempotency keys on `record`** and **meter continuity on redelivery** (risk AR-3): built in A1
  though redelivery only arrives in A3. These are permanent correctness, not simplifications.
- **Bus idempotency-key dedupe + coalescing** (A3, borrowed from Paperclip's `agent_wakeup_requests`
  `coalescedCount`): permanent robustness — a redelivered publish collapses to one message, and many
  nudges to a busy node bump a counter instead of piling up N rows.
- **Coordination/production step tagging** and **per-provider concurrency caps**: Phase-2 additions
  that survive into Phase 3 unchanged (SC-1, SC-3).

## Rule

Any PR that closes one of D1–D8 updates this file and the affected design doc in the same change
(risk IM-6). Prefer *extending* an API shape over mutating it, so a live org actuated on Phase 2
still parses under Phase 3.
