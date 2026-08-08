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

## Status — E6 close-out (Phase 3, execution milestones E1–E6)

| # | Status | Where it closed |
|---|---|---|
| D1 | **Closed** | E1: assignment-bound meters (engine funds one per Assignment; the gateway's injected `meter_resolver` maps taskId → the assignment's meter). E2a added the rework-funding rule (parent-meter transfer on rejection). |
| D2 | **Closed** | E1: `gated` added to the directory status enum; existing members untouched. |
| D3 | **Closed** | E2b: real ClarificationGate (`revise-brief` re-intakes on a bumped brief version); rework funding follows the brief version (E2a). |
| D4 | **Closed** | E2a/E2b: all five gate kinds (clarification / dependency / approval / escalation / intervention) with owners, one resolution endpoint, idempotent opens. |
| D5 | **Closed** (memory) / **narrowed** (workspace) | Durable memory: written at close (E1), inspect/reset via the inspector (E5), survives re-actuation (E6 vector). Workspace: the scratch dir stays per-node-per-actuation in MVP-1 — per-assignment isolation where it matters is the E4 repo worktree (one per assignment); a per-assignment scratch lifetime remains open, tracked here. |
| D6 | **Closed** | E1: `work_step.delta_kind` ships the closed delta enum (artifact / tool-effect / progress / message / none). |
| D7 | Open | Post-MVP (incremental re-actuation). E6 hardened the adjacent seam instead: open work now **survives** deactuate → re-actuate (lookups are org+node — the position owns its work, like memory). |
| D8 | Open | Post-MVP (live structural edits), paired with D7. |
| D9 | **Superseded** | The 2026-07-26 runtime pivot (`docs/execution/amendments-2026-07-26.md`, `cli-runtime.md`): real work runs as headless CLI sessions over the data plane + Canopy MCP server; the step loop is `canopy-agent`'s runtime. The a2a-sdk task server was not adopted — A3's HTTP inbox remains the bus delivery seam, still confined to one adapter. |

Also closed in E6 (an A1-era duplicate, flagged at E1): **`gateway_step` is retired** — `work_step`
is the one Step record (runtimes report it carrying the gateway's step id) and the ledger's
SpendEvent is the authoritative money audit. The table is dropped by a one-shot migration; the
gateway response shape is unchanged.

## Live-run findings — the first real operator run (E8 connector-governance, 2026-08-06/07)

The first end-to-end run with a real operator, real cli-claude sessions (claude-fable-5), and a
real repo target. Everything below was observed live, not theorized. F1 is the material one:
the run proved the ledger's input side blind.

| # | Finding | Class | End-state |
|---|---|---|---|
| F1 | **Input tokens undercounted ~100×.** The cli adapter settles only `usage.input_tokens` + `output_tokens` from stream-json assistant events; the context window — briefs, CLAUDE.md, every repo file read — arrives as `cache_creation_input_tokens` / `cache_read_input_tokens` and is dropped. An analyst that read the whole design corpus recorded `input_tokens: 65`. | metering (bug + design decision) | Extend `work_step`/`SpendEvent` with the two cache-token columns; settle all four components; cost estimation weights them cache-aware (reads ≈ 0.1× input rate). Then re-decide the meter currency — raw-token allowances would exhaust a Fable session in two turns; cost-weighted metering (or re-sized allowances) is the honest option. Absorbs debt E-D1's spirit: the meter must reflect real consumption. |
| F2 | **Cost explorer split degenerates to 100%/0%.** All `est_cost_micros` were 0 (model price for `claude-fable-5` absent from the boot-time price table), and the by-node share math divides costs, not tokens — first row rendered 100%. Recorded events keep their stored 0 even after the price lands. | reporting | Share math falls back to tokens when costs are all zero; unknown model price surfaces as "no price for X — tokens only" (IM-4/IM-5: estimates are honest, never silently zero). Consider query-time cost estimation so late-added prices reprice history. |
| F3 | **Stall trigger false-positives on manager wake-turns.** Each child delivery wakes the lead for a short review turn — status polls + thinking are all no-delta steps, so `stall_none_steps=5` trips and re-fires every sweep; the operator saw a repeating "needs you" intervention that resolved itself. Worse with Fable (long thinking between tool calls). The UI card also showed a wrong node label ("box1"). | triggers + UI | Exempt turns that end in `finish_turn` (or reset the counter on any settled `message` delta); consider a higher threshold for manager assignments. Fix the intervention-card node label. |
| F4 | **Open gates are not prominent.** A plan-review gate blocking the entire org sat in the inbox rail unnoticed. The operator's single most urgent action must be unmissable. | UI | Gate badge/count on the Execute header and pulse; open-gate cards promoted into the main column; attention state on the affected intent chip and plan-outline node. |
| F5 | **The org's state is not readable at a glance.** `/execute` lands on a default (possibly unactuated) org; the pulse shows states but no narrative ("3 analysts executing, writer blocked on 2 deliveries, nothing needs you"). `delivering` reads as stuck; dependency gates count as "open gates" and read as operator work. | UI | Landing view = actuated-org picker (live orgs first, with pulse); a one-line narrative summary per intent; visually separate operator-actionable gates from internal wiring. |
| F6 | **Intent composer is a single-line input.** A real intent is many paragraphs of markdown; it is unreadable to write and collapsed when displayed. | UI | Multiline textarea (auto-grow), markdown-aware display of submitted intents in chips/plan views. |
| F7 | **Deliverable previews crowd the page.** Artifact text renders compressed/unformatted, auto-opens, and stays expanded after acceptance. General theme: closed/accepted work keeps the same visual weight as work that needs the operator. | UI | Render artifact markdown; collapse behind an expander (auto-open only while a verdict is pending, auto-collapse on resolution); accepted/closed items visually recede. |
| F8 | **Boot-time config forces restarts mid-operation.** The run required three restarts: `[repo] source`, the catalog (lru-cached), and the price table are all read once at boot. The operator also wants the work-target repo mapped **per actuated org** (like profiles/bindings), not one global source — a prerequisite for running several orgs against different repos. | config/architecture | Per-org repo source (org settings surface + store field; `RepoManager` reads the org's mapping, falling back to config then fixture). Catalog and prices become reloadable (or at least `POST /admin/reload`). Dovetails with O2's GitHub pack. |
| F9 | **Notification hygiene.** Stale unread notifications read as pending actions (compounded by F3's spam); duplicate org names on cards are indistinguishable. | UI | Auto-read notifications whose subject gate is resolved; disambiguate org cards (id suffix / created date). |
| F11 | **Provider-limit exhaustion is invisible.** The operator's subscription hit its session limit mid-run; every resume died in ~1s with "You've hit your session limit · resets HH:MM" (visible only in the adapter log's `session_result` error). The operator saw a generic stall intervention, not the cause. | runtime + UX | The adapter should recognize limit/auth errors in `result` events and surface them distinctly: a `provider-limit` notification carrying the reset time, back off until then instead of retrying, and auto-resume when the window reopens. Generic stall is the wrong shape for "the credit card is empty." |
| F16 | **Agent logs and transcripts are not org-owned.** The audit spine (steps, tool events, spend, activity) is in the DB, but the *complete* record of what an agent actually did — the CLI conversation transcript — lives in the operator's `~/.claude/projects/<path-key>/`, outside `data/`; adapter logs and stderr are sharded per-actuation under `data/sandboxes/<actuationId>/` with no rotation or retention policy; the raw stream-json is parsed and discarded. For a platform whose pillar is auditability, the org doesn't own its agents' conversations. | audit/architecture | Assignment-keyed, actuation-independent log home under `data/` (pairs with F13's stable workdir): adapter log + stderr + a copy of (or pointer to) the session transcript, referenced from the assignment and readable via the inspector. Add a retention/rotation policy. Consider archiving the raw stream per session — it is the ground truth F1's metering and F14's liveness both derive from. |
| F15 | **The meter arc reads as progress and always shows ~0%.** The percentage on node/assignment rows is budget consumption (spent ÷ allowance) — with six-figure token allowances (and F1's undercount) it renders 0–1% all run, and operators read it as "no progress." | UI + metrics | Show **stage-based progress** as the primary per-assignment number (completed stages ÷ plan stages — the living plan already carries states), with the budget meter as a separate, labeled affordance ("budget: 0.4%"). Blocked on nothing; honest today even before F1's metering fix lands. |
| F14 | **Liveness needs a first-class signal, not step inference.** (Operator ask, after the third spurious/ambiguous stall of the run.) Settled steps are a lagging indicator: a healthy session mid-thought and a crash-looping session both settle nothing, so the stall sweep can't tell deep work from death — it gated real work repeatedly and dressed provider failures as stalls. | engine + runtime | The adapter already observes the truth — every stream-json event is proof of life, and `session_exit` codes are proof of death. Report it: a per-assignment `lastActivityAt` (any stream event) + `sessionHealth` (running / erroring / dead, with the last error) pushed over the dp on a heartbeat cadence. The stall sweep then keys on *activity*, not settled steps; "erroring" surfaces as F11's provider notification, and only true silence (process up, no stream events past threshold) opens a stall intervention. UI shows the liveness state on the node card ("thinking · last event 40s ago"). |
| F13 | **Session resume breaks across re-actuation.** The CLI stores conversations per project *directory*, and the sandbox workdir embeds the actuation id — after deactuate → re-actuate, `--resume <sessionRef>` fails with "No conversation found" because the transcript lives under the old actuation's path key. The position survived; its conversation didn't. Worked around live by copying the transcript into the new path's project key. | runtime | Make the assignment workdir path actuation-independent (org + node + assignment), the same move E6 made for work/meters/memory — then session refs survive re-actuation natively. Interim: the adapter could detect "No conversation found" and fall back to a fresh session instead of crash-looping into the stall trigger. |
| F12 | **Inspector session log keyed to the original actuation.** Continuation semantics keep the assignment's original `actuationId`; the inspector reads `logs/<node>.log` under that actuation's sandbox, so after a re-actuation the log tail shows the *old* process's events. | inspector | Read the log from the **current** actuation's sandbox (directory row / live actuation id), falling back to the assignment's original. |
| F10 | **Windows cli-runtime fixes (closed during the run).** (a) Bare `claude` is invisible to `CreateProcess` (no PATHEXT) — probe and spawn now resolve via `shutil.which`. (b) A multi-line `-p` argument is mangled by the npm `claude.CMD` shim (`cmd.exe` treats newlines as command separators — flags after the prompt silently dropped; sessions answered in plain text and settled zero events). The prompt now rides stdin. (c) Workspace trust is path-separator-sensitive: `D:\…` and `D:/…` are distinct entries in `~/.claude.json`; the sandbox resolves the forward-slash form. | runtime | (a) and (b) are fixed in `agent/src/canopy_agent/cli_runtime.py` + `server/src/canopy_server/actuator.py` (this working tree). (c) is an operator-setup note for `cli-runtime.md` §8 — document the trust requirement and the exact key shape. |

### Status — live-run fixes (branch `live-run-fixes`, 2026-08-07)

| # | Status | Where it closed |
|---|---|---|
| F1 | **Closed** | Cache-aware metering: `work_step`/`SpendEvent` carry both cache-token columns; settlement and cost estimation weight all four components. The meter-currency re-decision stays open (tracked in the F1 row's end-state). |
| F2 | **Closed** | Token-share fallback when costs are all zero; "no price for X" surfaces honestly. |
| F3 | **Closed** | With F14: liveness-aware no-delta trigger (grace window while the session streams); intervention-card node label fixed. |
| F4 | **Closed** | Header gate badge + pulse chip; open-gate cards promoted into the main column; attention ring on intent chips and plan rows. |
| F5 | **Closed** | `/execute` lands on the actuated-org picker (live first, pulse narrative per card); one-line org narrative in the pulse strip; `delivering` relabeled "awaiting review"; operator gates (🔒, danger) toned apart from internal wiring (🔗, muted). |
| F6 | **Closed** | Auto-growing textarea composer (Ctrl+Enter submits); markdown-aware display of intents (chips = first line; plan view renders the full text). |
| F7 | **Closed** | Markdown rendering for document artifacts; deliverable cards collapse behind an expander — auto-open only while the verdict is pending, auto-collapse and recede on resolution. |
| F8 | **Closed** | Per-org repo source (org settings + store field; `RepoManager` resolves org → config → fixture at run time). |
| F9 | **Closed** | Gate resolution auto-reads its notifications; duplicate org names disambiguated with an id suffix on picker cards and the org select. |
| F10 | **Closed** | (a)/(b) fixed in `cli_runtime.py`/`actuator.py`; (c) documented in `cli-runtime.md` §8 (trust key shape, forward-slash form). |
| F11 | **Closed** | Adapter recognizes provider-limit errors in `result` events: distinct `provider-limit` notification, backoff instead of hammering, generic stall no longer the shape of "the credit card is empty". |
| F12 | **Closed** | Inspector reads the current actuation's sandbox (newest existing on disk), falling back to the assignment's original; superseded in the common case by F16's stable log home. |
| F13 | **Closed** | Assignment workdir is actuation-independent (`data/work/<orgId>/<nodeId>`, env `CANOPY_WORK_ROOT`) — session refs survive re-actuation natively; the "No conversation found" fresh-session fallback stays as a net. |
| F14 | **Closed** | First-class liveness: per-assignment `lastActivityAt` + `sessionHealth` on a heartbeat cadence; the stall sweep keys on activity, not settled steps. |
| F15 | **Closed** | Stage-based progress (done/total from the living plan) is the primary number on node cards and plan rows; the budget meter is a separate affordance labeled "budget". |
| F16 | **Closed** | Org-owned audit home under `data/work/<orgId>/<nodeId>`: adapter log (size-rotated), per-session stderr (rotated), transcript pointer stored on the assignment, transcript copy archived per session; inspector reads the stable home. |

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
