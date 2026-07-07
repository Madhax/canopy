# Execution (Phase 3) — Design Suite

**Status:** Implementation-ready draft · **Date:** 2026-07-06
**Phase:** Build → Actuate → **Execute**. Phase 1 (`../org-chart-editor.md`) produces the Organization document. Phase 2 (`../actuation/`) turns it into live, addressable agents (A1–A3 shipped: gateway, ledger, run tokens, actuator, subprocess sandbox, bus, router, agent boot). Phase 3 gives the actuated organization real work-layer semantics — Assignments, the five Gate kinds, Plans, assignment-bound meters, durable memory, cadences — and, just as importantly, the **ongoing operator experience**: this phase defines what it feels like to *run* an organization day after day.
**Authoritative upstream:** `../domain-model.md` (every invariant binds here — this is the phase the work layer was written for), `../manager-responsibilities.md` (extensions X1–X4/R1–R4; §"Adopted extensions" below says which land now), `../actuation/phase3-debts.md` (debts D1–D9; this suite closes D1–D6 and D9), `../actuation/agent-envelope.md` (the `cli` runtime kind this phase makes real).

## The one constraint that shapes everything

**There is no Claude API key.** The operator runs Canopy on a machine with a logged-in Claude Code CLI (subscription auth). Phase 3's agent execution therefore wraps **headless Claude Code sessions** as the agent runtime (`cli-runtime.md`) instead of routing completions through the Model Gateway's `anthropic` adapter. The consequences are absorbed deliberately:

- **Metering is session-observed, not gateway-mediated.** The adapter parses the CLI's `stream-json` output; every assistant turn lands as a Step with provider-reported usage, and SpendEvents flow into the existing ledger unchanged. Budget enforcement moves from *before each model call* to *before each session turn* — a coarser but still mechanical hard-stop, recorded as debt **E-D1** (`cli-runtime.md` §7).
- **The Model Gateway does not disappear.** The `mock` provider remains the CI/testing spine (risk IM-2), and the `loop` runtime kind stays alive against it — every engine behavior in this suite is testable without a Claude login or a dollar of spend.
- **Credential posture is trusted-local.** The CLI's OAuth material lives in an operator-provisioned config dir passed to sandboxes; agents never see an API key because none exists. See `cli-runtime.md` §8 for the honest trust statement.

## The documents

Read in this order:

| Doc | What it designs |
|---|---|
| `work-model.md` | The work layer made concrete: Intent, Assignment lifecycle, Brief versioning, the five Gates, Plan/PlanStage/Step (+ delta taxonomy), Deliverables (artifact + attestation), Directives, durable memory. SQLite schemas and state machines. Closes debts D1–D6. |
| `engine.md` | The Execution Engine control-plane module: intent intake, delegation, dependency resolution, gate service, acceptance and rework funding, cadence scheduler, intervention triggers, notifications. REST API. |
| `cli-runtime.md` | The `cli-claude` runtime kind: wrapping headless Claude Code sessions per assignment, the Canopy MCP tool plane, session-observed metering, budget gating between turns, suspend/resume across gates. Closes debt D9. |
| `operator-experience.md` | The ongoing UX: mission control, the per-agent inspector (full introspection of any node), the cost explorer, the notification center and approvals inbox, the intent console. Routes, components, SSE. |
| `mvp.md` | **MVP-1: the software team.** A three-role `product-engineering-pod` (lead / backend engineer / QA) building and testing code in a real local git repo. Role isolation by construction, salary in use end-to-end, build milestones E1–E7 for Claude Code. |

## Phase-3 definition of done (MVP-1)

1. Actuate the three-node software-team org; submit the intent *"Add feature X to the sample repo, with passing tests."*
2. The **lead** decomposes it into a plan the operator reviews and approves (plan-review checkpoint), then delegates: implement → engineer, verify → QA, with QA's assignment behind a DependencyGate on the engineer's accepted PullRequest.
3. The **engineer** (a headless Claude Code session in its own workspace/worktree) implements and unit-tests, produces a `PullRequest` artifact (branch + diff), and cannot run e2e verification or touch QA's world — by generated session permissions and server-side grant checks, not by prompt.
4. The **QA agent** fetches the PR ref, runs the test suite, and discharges a `TestReport`. A failing report rejects the engineer's deliverable and funds rework per the brief-version rule — visibly on the engineer's meter.
5. Every turn of every session is a metered Step; the operator watches burn per node live, sees a **warn glow** at 80%, and when the engineer's meter hard-stops mid-assignment, resolves the InterventionGate from the inbox with a top-up — work resumes from the suspended session.
6. The operator can open **any agent** and see: charter, live status, current assignment + plan cursor, every step with tokens and delta, meter state, open gates, queue, memory, session log, and workspace listing — the full introspection surface.
7. The intent completes with a deliverable card (merged-ready branch + test report), a full provenance chain (SpendEvent → Step → Assignment → Intent), and a notification the operator finds in the inbox on their next visit.
8. Everything above also runs headless in CI against the `mock` provider + fake-CLI shim, with zero real spend.

## Adopted extensions (from `../manager-responsibilities.md`)

| Extension | Disposition |
|---|---|
| **R1** manager telemetry read | **Core.** `subtree_status` / `inspect_report` MCP tools; also the API the operator UI uses. |
| **R2** reassignment = cancel-with-continuation | **Core.** Gate resolution action. |
| **R3** queue priority (FIFO + manager-set priority) | **Core**, minimal: priority field honored by delivery; front-of-queue resume on gate resolution. |
| **R4** directive timing (mid-flight, next turn boundary) | **Core.** Needed for the *constrain* resolution. |
| **X1** judgment-opened InterventionGate | **Core for the user/operator** (pause/redirect/cancel any assignment from the UI). Manager-*agent*-initiated intervention is post-MVP (needs intervention etiquette/cost design). |
| **X3** checkpoints (governed transitions) | **Core, minimal instance:** plan review on root assignments, default-on (this is U-3's human-approved delegation). Generalized checkpoints (per-stage, spend-conditional) post-MVP. |
| **X2** scope-divergence trigger | **Post-MVP.** Requires the delta taxonomy to be live and calibrated tolerances; the taxonomy ships now (D6) so the tripwire can land later without migration. |
| **X4** standing directives | **Post-MVP.** The promotion path depends on it being worth promoting; MVP directives are assignment-scoped only, per the domain default. |

## Non-goals (Phase 3 / MVP-1)

Calibration of envelopes from historical actuals (static role defaults ship instead; the tables record what calibration will later fit); scope-divergence and envelope-overrun triggers (budget warn, hard-stop, and stall land now); work pools; incremental re-actuation (D7/D8 stay open — deactuate → edit → re-actuate); multi-user/auth; Blueprints; brokered channels and cross-team grants (single-team MVP has no consumer; the channel enforcement point exists); consequential-action executors (telephony, external email — the ApprovalGate machinery lands, the executors are catalog/proxy work); OS-notification/webhook alert delivery (in-app only; the notifier is a seam).

## Use-case coverage (the acceptance check against `../use-cases.md`)

The instruction this suite answers: *most of the out-of-the-box use cases must be supported by the phase-3 mechanisms.* "Supported" means the work model can express the flow and the engine can run it — per-use-case readiness then depends only on catalog content (role instructions, grants) and executors (Tool Proxy backends / MCP packs), not on new engine semantics.

| Mechanism this suite delivers | Use cases it unlocks (by # in `use-cases.md`) |
|---|---|
| Episodic intents + delegation + dependencies + artifact flow | 1, 3, 4, 6, 7, 8, 9, 17, 19, 21, 22, 29 |
| ActionAttestations as first-class deliverables | 10, 13, 14, 23, 24, 25, 26, 27, 28 |
| ApprovalGates on governed actions | 5, 15, 20, 26, 27 (publish/offer/permit/deposit consent) |
| EscalationGate / ClarificationGate / InterventionGate | 2, 13, 23 (incident, support, floor exceptions) |
| Cadences generating episodic intents | 12, 14, 16, 18, 30 |
| Standing intents (goal = root standing intent) | 10, 11, 25, 28, 30 |
| Milestones (derived status) | 22, 26 — **post-MVP**, small derived view over existing objects |
| Nested orgs at runtime (already actuate) | 31 (cloning itself stays deferred with Blueprints) |

Score: 30 of 31 use cases are expressible on phase-3 core (#22 and #26 run today and gain the derived milestone view post-MVP); #31 waits on Blueprints by design. What MVP-1 actually *runs* end-to-end is #1, #3, and #9's shape (feature + review + docs are all lead→IC→artifact→acceptance flows) — the software-delivery column — plus #29 (instruct only the root and watch delegation) and #30 as the E7 stretch cadence.

## Debt ledger effects (`../actuation/phase3-debts.md`)

D1 (assignment-bound meters), D2 (full status enum incl. `gated`), D3 (ClarificationGate), D4 (five gate kinds), D5 (workspace per assignment + durable memory), D6 (step delta taxonomy), D9 (full task lifecycle in the adapter) — **closed by this suite**; each closing milestone updates that file per its rule. D7/D8 (incremental re-actuation, live chart edits) remain open, acknowledged in SC-2's terms. New debts opened by the no-API-key constraint are listed in `cli-runtime.md` §7 (E-D1..E-D4).
