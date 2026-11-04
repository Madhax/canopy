# 02 · The Daily Brief — the check-in as a designed surface

> **Status:** Proposed 2026-08-16 · **Reads with:** `README.md`, `01-operations-envelope.md`, `../../execution/operator-experience.md` (the inbox/digest this builds on), `../organizations/05-ux-portfolio.md` (the home this lands beside), `../../risks/usefulness.md` U-2, `../../canopy-inc.md` §2 P2 (the attention budget this renders)

## 0. The problem

The operator's day with the fleet is currently assembled by hand: the inbox for gates, GitHub for PRs, the portfolio for vitals, the cost explorer for spend — four surfaces and no ordering. For a fifteen-minute daily session, the surface must be one page whose *order is the priority order*, whose ratifications are batched, and which says "nothing needs you" honestly when true. U-2 named this ("while you were away"); the C-series built its honesty rules; nobody designed the page.

## 1. The brief

`GET /api/brief` — a portfolio-scoped aggregate (org filter optional), computed on read from existing stores plus the notification read-cursor. Five sections, strict order:

1. **Ratify** — everything only the operator can do, batched by kind, counts in the header:
   - **Pull requests awaiting merge** — from the GitHub connector's read surface (or, pre-connector, links the teams' PR-create attestations recorded). Each with its receipt line (cost, rework rounds, verify verdicts) — the evidence beside the ask.
   - **Plan reviews** — batches the envelope routed to needs-you, batch-approvable (§2).
   - **Governed actions** — merges, publishes, outward comments; never batched, each explicit (consequence class stays deliberate).
   - **Graduation and structure proposals** — envelope nominations (`01` §4), forge proposals, champion-suggested cards.
2. **Parked** — every parked gate fleet-wide: reason code, age, team, one-click resolve or bulk-resolve per reason class. Items older than their team's `reviewLatencyBudgetH` render first, flagged.
3. **Anomalies** — SLO breaches and tripwires: stall flags, capacity parks, credential warnings, restart events, guardrail breaches, refire strikes (`04` §2), 403-spike tripwires (`05` §4). Each with the drill-down link into the existing inspector surfaces.
4. **Receipts delta** — since the last brief: merged units with costs, acceptance/rework rates, spend vs. weekly ceiling per org, windows and runway (source-tiered, per C-series honesty), approvals *you* made yesterday (the operator's own load, counted — P2 made visible).
5. **All clear** — when sections 1–3 are empty, the brief says so in one line, and that line is the product working.

**BR-1** The brief is computed, never stored — a read model over gates, notifications, attestations, ledger, capacity, receipts. **BR-2** Reading the brief advances the notification cursor (the existing digest semantics); "since last brief" is cursor-defined, so irregular check-ins stay correct. **BR-3** Every number carries source and age (the capacity console's honesty rules, inherited wholesale). **BR-4** A `[brief] hour = 8` config emits a `brief-ready` notification daily via the notify seam (§4) — the brief exists whether or not the nudge fires.

## 2. Batch ratification

**BR-5** Plan-review batches are approvable as a set: one action approves N batch-gates, applied per-item idempotently; partial failure reports per item and never blocks the rest. The batch card leads with the aggregate — *"you are dispatching 6 engagements, Σ 1.4M tokens, 3 teams"* — with per-item expansion for editing (an edited item leaves the batch and resolves individually; editing is the review working as designed). **BR-6** Nothing else batches: governed actions, acceptances, and structure proposals are deliberately one-at-a-time. The line follows the envelope's: bounded token spend batches; consequence never does.

## 3. Away from the desk

The corpus defers network deployment and multi-user auth (localhost only), so the brief is a desktop surface in v1 — stated, not hidden. Two crutches until a hosted posture exists: **BR-7** an optional daily **brief summary email** (counts per section + all-clear line, no bodies — it is a nudge, not a remote control) through the notify seam; **BR-8** the page channel (§4) for what cannot wait. Approving from a phone is explicitly out of scope until the platform has real authn/z — a governed action approved over an unauthenticated channel would be a hole, not a feature.

## 4. The page channel

**BR-9** A `notify` seam in the registry mold (sandbox/bus precedent): providers `console` (default), `email` (SMTP config), `webhook` (generic JSON POST — covers Slack/Discord/ntfy/Pushover without bespoke packs). Configured in `canopy.toml [notify]`; a `canopy notify test` path proves delivery end-to-end (required by the readiness checklist, `06`).

**BR-10 — The closed page set.** Exactly five event classes may page between briefs; everything else waits:

| Event | Meaning |
|---|---|
| `fleet-park` | an org's teams parked collectively (capacity park rung, org budget exhaustion at 100%) |
| `credential-failure` | auth-class session failures on a provider account (`03` §2) |
| `boundary-violation` | a guardrail/tripwire fired on the recursion boundary or consequential class (`05` §4) — includes the auto-tighten receipt (`01` §4) |
| `supervisor-restart-loop` | the control plane restarted ≥3 times in 10 minutes (`03` §1) |
| `disk-critical` | data volume below the hard watermark (`03` §4) |

**BR-11** The set is closed *in code*, not config — adding a page class is a design amendment, because every addition taxes the operator's trust that a page means it. Capacity holds, stalls, parks, and rework storms remain brief-class (`info`/`attention`), per the C-series' pages-nobody discipline.

## 5. Open questions

1. Should the brief render a *plan for the day* (expected completions, scheduled cadences) alongside the retrospective? Cheap and probably yes; deferred to keep v1 to the priority queue.
2. Bulk-resolve semantics for parked clarifications sharing a directive-shaped answer — resolve-with-new-directive in one act (teach while unblocking)? Attractive; needs X4 UI first.
3. Does the brief live at `/brief` or as the portfolio home's default morning state? Leaning: own route, linked first from home — the home answers "how is everything," the brief answers "what do I do."
