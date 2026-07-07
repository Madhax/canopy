# Operator Experience — Running an Organization, Day After Day

**Status:** Implementation-ready draft · **Date:** 2026-07-06
**Upstream:** `engine.md` §6–7 (every surface here reads those APIs), `../org-chart-editor.md` (the editor this extends), `../risks/usefulness.md` (U-1/U-2: this doc is the second-session answer), `../risks/scalability.md` (SC-4: attention must scale).
**What this doc is:** the phase-3 UI. Phase 1 answered "shape the org," phase 2 "is it alive" — phase 3 answers the operator's standing questions: **What is my organization doing? What is it costing me, and where? What needs *me* right now? What happened while I was away? And what exactly is any one agent up to?** These five questions structure the design; every screen exists to answer one of them.

---

## 1. Information architecture

The app grows an **Operate** mode alongside the editor (the phases are the product's navigation, per `../phases.md`):

| Route | Surface |
|---|---|
| `/organizations/:id/operate` | **Mission control** — the live chart + org pulse |
| `/organizations/:id/operate/agents/:nodeId` | **Agent inspector** — full introspection of one node |
| `/organizations/:id/operate/intents` · `/intents/:intentId` | **Intent console** — submit, review plans, track trees, collect deliverables |
| `/organizations/:id/operate/inbox` | **Inbox** — gates awaiting resolution + notifications + digest |
| `/organizations/:id/operate/costs` | **Cost explorer** — rollups, burn, coordination share |

Editor ↔ Operate switching preserves the org; the editor stays read-only while actuated (unchanged v1 policy). All live data arrives over one SSE channel (`GET /organizations/{id}/events`) with polling fallback; every surface is a projection of engine state — the UI stores nothing.

## 2. Mission control — "what is my organization doing?"

The phase-1 canvas, actuated, with an operations overlay:

- **Node states** render the full status enum: `idle` (dim), `engaged` (pulse + current assignment title), `gated` (amber, gate-kind icon), `paused`, `dead` (red). Badges: queue depth, meter arc (green→amber at warn→red at stop), runtime kind/tier (from the envelope), WIP count.
- **Assignment flow overlay** (toggle): active assignment edges drawn down the reporting lines, dependency gates shown as padlocks between siblings — the intent tree projected onto the chart, live. Clicking any element deep-links into the inspector or intent console.
- **Org pulse header**: actuation state · open intents · burn rate (tokens/min, est cost/hr) · open gates by kind · attention count (the inbox badge). This header is the "finally see what your agents cost" observability product U-1 asks Actuate to be — always visible, in every Operate view.
- **Empty/idle state** sells the next action: no open intents → a prominent intent composer; no cadences → "put this org on a schedule."

## 3. Agent inspector — "what exactly is this agent doing?"

The requirement stated directly: *introspect the state of any one agent.* One aggregate endpoint (`GET /agents/{nodeId}/state`) feeds a tabbed panel; everything is read-only except the marked actions.

| Tab | Contents |
|---|---|
| **Overview** | identity, role (`key@version`), charter (compiled instructions, manager, reports), profile binding, envelope (grants, runtime kind, tier), salary policy, live status + heartbeat age, lifetime stats (assignments done, acceptance rate, avg cost per assignment, escalation count) |
| **Assignment** | the current assignment: brief (all versions, diffed), contract, directives, issued-by chain up to the intent — "why is this agent doing this?" answered structurally |
| **Plan & Steps** | plan versions, stage list with cursor + per-stage actuals vs envelope, and the Step table (time, kind, tokens, delta kind + ref) — the drill-down `Assignment → Plan → Stage → Step → SpendEvent`, each step expandable to its spend record |
| **Spend** | this node's meter (allowance/spent/reserved, warn line), historical per-assignment spend sparkline, share of org spend |
| **Gates & Queue** | open + historical gates (kind, opened-by, age, resolution), queued assignments with priority — **actions:** resolve (owner surface §5), reprioritize, X1 **Intervene** (pause/redirect/cancel this assignment) |
| **Memory** | durable memory entries (the agent's accumulated experience) — **actions:** reset (the "backfill the position" act, confirm-gated) |
| **Session** | the live/last session log (structured events from the adapter: turns, tool calls, interrupts) — the debugging view for "what is it *actually* doing right now" |
| **Workspace** | read-only listing of `assignments/<id>/` (brief/work/out file tree, sizes, mtimes; text preview ≤ 256 KB) — inspection honors invariant 2's spirit: the platform (and its operator) can look, no *agent* ever can |

The inspector is also reachable from every mention of a node anywhere in the app (chart, inbox rows, cost tables, intent trees) — introspection is one click from any signal.

## 4. Intent console — "give it work, watch it work"

- **Composer**: intent text, target node (default root), episodic/standing toggle, allowance override with a projected-cost hint ("this org's median intent cost: ~N tokens") — U-3's wallet guard.
- **Plan review** (X3 checkpoint, default-on for root assignments): when the root's decomposition lands, the intent view shows the proposed plan/delegations — per-child briefs, contracts, dependencies, funded allowances — with **Approve / Edit brief / Reject**. This is U-3's human-approved delegation, built as the first checkpoint instance, and it doubles as the operator's education in how their org thinks.
- **Tree view**: the assignment tree with live states, per-node spend, gate markers; collapsible; each node deep-links to the inspector.
- **Deliverable card**: on completion — artifact refs (download via existing artifact API), attestation claims + evidence, total cost (with coordination/production split), duration, and the provenance chain. A **Rerun** affordance seeds a new intent from the same text.
- **Cadences**: a small management list (name, cron, target, last/next fire, enabled) + "make this recurring" on any completed intent — the U-1 retention hook placed where satisfaction is highest.

## 5. Inbox — "what needs me, and what happened while I was away?"

One surface for both, because both answer "why am I opening the app today?" (U-2):

- **Needs you** (top, badge-counted): open gates owned by the operator, grouped by kind, oldest first, each row showing the assignment, the ask, and cost-so-far. **Inline resolution** without leaving the list: approve/deny (approval), answer (escalation), revise brief (clarification), top-up slider / redirect / reassign (picker of valid siblings-of-role) / constrain (directive text) / cancel (intervention). Low-stakes classes support bulk-approve (SC-4's batching, shipped from v1 of this screen).
- **Digest** ("since you were last here", from the notifications read-cursor): completed intents with deliverable links, budget warns, auto-resolutions managers performed (with their bounds), stalls detected/recovered, nodes restarted. Grouped by kind, not a raw feed — the raw feed remains the activity drawer.
- Severity discipline per `engine.md` §7: `attention` items are precisely those where the org is *blocked on the operator* — the badge never cries wolf, which is what keeps it meaningful at 50 agents (SC-4).

## 6. Cost explorer — "where is the money going?"

Reads the extended rollups (`spend?groupBy=…&split=…`):

- **By intent** — what each ask actually cost, coordination vs production split rendered as a stacked bar ("overhead %" is a first-class stat, per SC-1: measured, not hidden).
- **By node** — spend ranking with acceptance-rate and rework columns alongside (cost without quality context invites the wrong conclusions); per-node salary utilization (median assignment spend vs allowance) with a "salary looks mis-set" hint when the ratio is chronically extreme in either direction.
- **By model/provider** and **over time** (burn line, warn/stop event markers).
- Every number drills down: intent → assignments → steps — the same chain the inspector walks, entered from the money end.

## 7. Build notes

Components extend the phase-1 stack (React Query + zustand; no new state architecture): `OperateLayout`, `OrgPulse`, `LiveCanvas` (the editor canvas in projection mode + overlay), `AgentInspector` (+ eight tab components), `IntentComposer`, `PlanReviewCard`, `AssignmentTree`, `DeliverableCard`, `InboxList` (+ per-kind resolution forms), `DigestPanel`, `CostExplorer`, `useOrgEvents` (SSE hook with polling fallback), `useNotifications` (badge + cursor). Live-update discipline: SSE events invalidate targeted queries; step events are throttled client-side (the inspector's step table paginates; mission control only consumes aggregates). Performance bar: smooth at 25 live nodes / 10 events/s — beyond that, aggregate server-side first (SC-3's measurement culture applies to the UI too).

## 8. MVP cut

Everything in §2–§5 ships in MVP-1 (it *is* the product's answer to "the ongoing user experience"); §6 ships the by-intent and by-node views, deferring time-series charts to a fast-follow. Post-MVP: milestone board (derived Milestone view), re-org advisor (queue-depth / channel-telemetry suggestions), activity timeline replay, standing-directive management (X4), manager-scorecard view (F4 — the data is already collected).
