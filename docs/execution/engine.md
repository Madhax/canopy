# Execution Engine — The Control-Plane Module That Drives Work

**Status:** Implementation-ready draft · **Date:** 2026-07-06
**Upstream:** `work-model.md` (objects and state machines), `../actuation/control-plane.md` (module conventions), `../actuation/data-plane.md` (bus/router), `../domain-model.md` (invariants).
**What this doc is:** the Execution Engine (`engine/` package in `canopy_server`), its collaborations with the existing A1–A3 modules, the cadence scheduler, the notification service, and the operator REST API. Follows the topology rules: ABC + registry where a seam is plausible, own tables (`work_*`), Pydantic boundaries, ids-not-references.

---

## 1. Position among the existing modules

```
                         ┌──────────────── EXECUTION ENGINE (new) ────────────────┐
                         │  intents · assignments · briefs · gates · plans ·      │
                         │  deliverables · directives · memory · cadences ·       │
                         │  triggers · notifications                              │
                         └──┬───────────┬───────────┬───────────┬───────────┬─────┘
                            │ funds     │ routes    │ meters    │ stores    │ audits
                            ▼           ▼           ▼           ▼           ▼
                      BudgetLedger  Router+Bus   Gateway     ArtifactStore  ActivityLog
                      (A1, as-is)   (A3, as-is)  (A1; mock    (built in E1;  (A1, as-is)
                                                  CI spine)    A4 scope)
```

The engine **owns work truth**; runtimes own nothing. Every runtime interaction is a report ("intake complete", "plan declared", "step happened", "delivering refs") or a request ("delegate", "escalate", "produce artifact"), arriving through the data-plane API (§5) — run-token-authenticated, so a request can only concern the caller's own assignment. The engine validates against the charter-derived topology (delegation targets must be the caller's reports), mutates state, and publishes any resulting wake-ups onto the bus.

The **Artifact Store** (designed in `../actuation/workspace.md` and `control-plane.md` §7, scheduled as A4, not yet built) is a prerequisite and ships as milestone E1 exactly as designed there — nothing about it changes in phase 3.

## 2. The delegation flow (one assignment, end to end)

```
manager session calls MCP delegate(reportNodeId, brief, refs[], contract, dependsOn?[])
  1. engine: verify reportNodeId ∈ caller charter reports (inv. 4); verify refs are readable
     by the caller (grant rule, workspace.md §2)
  2. open meter: ledger.open_meter(allowance = report's salary.perAssignmentAllowance,
     task_id = new assignment id)                                    ── closes D1
  3. insert work_assignment(state='briefed', brief v1 with refs)
  4. dependsOn: for each named sibling assignment not yet accepted → open dependency Gate
     (state 'gated' immediately — genuinely idle, consuming nothing)
  5. ungated: publish to bus inbox topic of the report          ── existing A3 delivery
  6. return {assignmentId} to the manager session (its step's delta: 'message')

report adapter receives delivery → intake:
  7. adapter materializes brief/ (fetch_artifact per ref — engine authorizes against the
     brief's granted set), runs the feasibility check prompt
  8. OK → report 'intake-complete' → engine sets 'planning'
     defective → MCP open_clarification(question) → gate(clarification, owner=manager)

planning:
  9. session declares plan via MCP declare_plan(stages[]) → engine stores plan v1, stamps
     envelope defaults; if a checkpoint applies (X3: root assignments by default) →
     gate(approval, owner=operator) with the plan as payload — U-3's approve/edit surface
 10. approved (or no checkpoint) → 'executing'; adapter drives the session (cli-runtime.md)

executing:
 11. every assistant turn → step report → ledger record (SpendEvent) → trigger sweep
 11a. managers: after fan-out, MCP finish_turn → engine opens a dependency gate on the
     MANAGER'S OWN assignment (payload = outstanding child ids) — "awaiting reports" is not a
     special state, it is gated(dependency) like any other wait (invariant 8); the gate
     auto-resolves as children close, resuming the manager session with their deliverables
 12. finish → adapter uploads out/ files → produce_artifact refs → MCP finish(summary, refs)
     → engine inserts work_deliverable, state 'delivering', notifies the manager (bus wake)

acceptance:
 13. manager session resumes with the deliverable in context → MCP accept(assignmentId, note)
     or reject(assignmentId, note [, revisedBrief])
     accept → assignment 'accepted'→'closed'; meter closed; memory entry written;
              any dependency gates watching this assignment re-check and auto-resolve (§ work-model 3)
     reject → 'rejected' → re-queue to 'planning'; rework funding per brief-version rule
 14. root assignment closed → intent completed → deliverable card + notification
```

Operator-issued root assignments follow the same path with `issued_by='operator'` and the operator as gate owner.

## 3. Gate service

One module (`engine/gates.py`) owns open/resolve, the owner chain, and resumption:

- **Open**: insert row, move assignment to `gated`, snapshot `session_ref`, release node (directory → `gated`), notify owner (§7). Idempotent per (assignment, kind, reason-hash) — trigger sweeps never double-open.
- **Resolve**: validate resolver (owner, or anyone up the owner's management chain, or operator), apply the resolution action (see table in `work-model.md` §3), write `resolution`, re-queue the assignment front-of-line with a `resume` envelope carrying the resolution payload. The adapter turns that payload into the next session input (`cli-runtime.md` §6).
- **Bounded auto-resolution (SC-4's attention scaler, minimal form):** a manager node may carry `autoResolve` policy in its role/extensions data — MVP ships exactly one: `topUpPct: 20, oncePerAssignment: true` for hard-stop interventions on its reports. The engine applies it without waking the operator, logs it to activity, and routes to the operator only beyond bounds. Everything else routes to its owner untouched.

## 4. Cadence scheduler

`work_cadence` table: `{id, org_id, node_id, name, cron, intent_text, enabled, last_fired_at}`. A 30 s scheduler loop (same lifespan-task pattern as the reconciler) fires due cadences: each occurrence creates an ordinary **episodic intent** targeted at the cadence's node, tagged `cadence_id` — from there it is indistinguishable from operator work (same meters, gates, notifications). Misfire policy: skip if the previous occurrence's intent is still open (coalescing, like the bus's nudge dedupe); log the skip. This is deliberately small — U-1 calls cadences the retention mechanism, and they compose entirely from existing machinery.

## 5. Data-plane API additions (`/api/dp/*`, run-token auth)

The engine's agent-facing surface. The MCP server (`cli-runtime.md` §4) is a thin adapter over exactly these endpoints — `loop`-runtime agents call them directly, which keeps one authorization path for both runtimes.

| Endpoint | Purpose |
|---|---|
| `GET  /dp/assignment/current` | the caller's active assignment: brief (latest version), refs, contract, directives, memory block |
| `POST /dp/assignment/events` | runtime reports: `intake-complete`, `step` (usage + delta), `stage-update`, `awaiting-reports` (managers — see §2 11a), `delivering` |
| `POST /dp/plan` / `PUT /dp/plan` | declare / revise the plan (revision bumps version; visible) |
| `POST /dp/delegate` | managers: create child assignment (flow §2); body includes `dependsOn` sibling ids |
| `GET  /dp/reports/status` | R1: subtree telemetry (assignment states, plan cursors, meters, open gates of reports — recursive, sub-org-opaque) |
| `POST /dp/gates` | open clarification / escalation / approval-request from the agent side |
| `POST /dp/accept` / `POST /dp/reject` | managers: acceptance decisions on their reports' deliverables |
| `POST /dp/finish` | deliverable submission `{kind, refs[], attestation?, summary}` |
| `POST /dp/attest` | record an ActionAttestation (engine checks the governed-action approval linkage) |
| `GET  /dp/meter` | the caller's current meter state (adapters poll between turns) |
| `POST /dp/artifacts`, `GET /dp/artifacts/{ref}` | Artifact Store put/fetch (A4 scope, grant-checked) |

## 6. Operator REST API (`/api`, extends `control-plane.md` §9)

| Method & path | Purpose |
|---|---|
| `POST /organizations/{id}/intents` | now creates work_intent + root assignment; body gains `kind` (episodic default), `targetNodeId?`, `allowanceOverride?` |
| `GET  /organizations/{id}/intents` · `GET /intents/{intentId}` | list / detail: assignment tree, states, spend rollup, deliverable card |
| `GET  /organizations/{id}/assignments?node=&state=` | filterable assignment list |
| `GET  /assignments/{id}` | full drill-down: brief versions, plan (stages + cursor), steps (with deltas), meter, gates, deliverable, directives |
| `POST /assignments/{id}/intervene` | X1: open judgment intervention `{note}` |
| `POST /gates/{id}/resolve` | the one resolution endpoint: `{action: resume|revise-brief|approve|deny|answer|constrain|reassign|top-up|cancel, ...payload}` |
| `GET  /organizations/{id}/gates?state=open&owner=operator` | the approvals/attention inbox feed |
| `GET  /organizations/{id}/agents/{nodeId}/state` | the inspector aggregate (`operator-experience.md` §3) |
| `GET/DELETE /organizations/{id}/agents/{nodeId}/memory` | inspect / reset durable memory |
| `GET/POST/PUT/DELETE /organizations/{id}/cadences` | cadence CRUD |
| `GET  /organizations/{id}/notifications?since=` · `POST /notifications/read` | notification center feed + read cursor |
| `GET  /organizations/{id}/events` (SSE) | live stream: status changes, steps (throttled), gates, notifications — the UI's push channel |

Spend rollups extend, not mutate (D-rule): `GET /organizations/{id}/spend` gains `groupBy=intent|assignment|stage` and `split=coordination|production`.

## 7. Notification service

In-app only (per scope decision); the delivery layer is a seam (`Notifier` ABC; v1 implementation writes rows + SSE).

```sql
CREATE TABLE work_notification (
    id         TEXT PRIMARY KEY,             -- nt_xxxxxxxx
    org_id     TEXT NOT NULL,
    severity   TEXT NOT NULL,                -- attention | warning | info
    kind       TEXT NOT NULL,                -- gate-waiting | budget-warn | hard-stop | stall |
                                             -- intent-completed | deliverable-rejected | node-dead |
                                             -- cadence-fired | plan-review-waiting
    subject_ids TEXT NOT NULL DEFAULT '[]',
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    read_at    TEXT
);
```

**Severity discipline** (what "owners should be alerted of" means operationally): `attention` = the org is blocked on the operator (gate they own, hard-stop beyond auto-resolution, node dead past restart budget) — badge count, top of inbox. `warning` = degrading but running (budget warn, stall detected and routed to a manager, repeated rejection). `info` = normal pulse (intent completed, cadence fired). The "while you were away" digest is `GET /notifications?since=<last read>` grouped by kind — no extra state. Every notification also lands in the ActivityLog (audit) — notifications are the *attention* subset, activity is the *record*.

## 8. Failure and recovery semantics

- **Crash/restart of the control plane**: work state is SQLite; the trigger sweep and cadence scheduler are stateless loops; in-flight session turns re-report idempotently (step ids dedupe in the ledger; assignment events carry monotonic seq).
- **Agent death mid-assignment**: reconciler restarts the sandbox (A2, unchanged); the adapter finds `assignment/current` still `executing` with a `session_ref` and resumes the session; if the session is unresumable it restarts from the last engine-known state (brief + plan + produced refs survive upstream — only unproduced scratch is lost).
- **Deactuation with open work**: assignments freeze as-is (`paused` en masse); re-actuation resumes queues. Intents survive actuations — they belong to the org, not the actuation.
- **Dead letters** (bus DLQ) surface as `attention` notifications naming the assignment.

## 9. What deliberately does not exist

No engine-side scheduling of agent "background thinking" (all work hangs off assignments); no cross-team channels (single-team MVP; the enforcement point sits in the router untouched); no automatic re-decomposition on failure (a failed child surfaces to its manager's session — judgment, not machinery); no milestone engine (post-MVP derived view); no per-role engine logic of any kind (invariant 11 — everything role-specific arrived via the charter and the catalog).
