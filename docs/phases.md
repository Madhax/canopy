# Canopy — The Three Phases: Build → Actuate → Execute

**Status:** Design overview (Phases 1–3 implemented; vocabulary corrected to Team/Organization/Pod per `design/organizations/`, adopted 2026-08-09)
**Reads with:** `domain-model.md` (authoritative abstractions), `org-chart-editor.md` (Phase 1 spec, esp. §10 "Seams for actuate & execute"), `design/organizations/05-ux-portfolio.md` (the portfolio home above the phases).

Canopy turns an organization chart into a running system. That happens in three distinct phases,
each consuming the artifact the previous one produced, and each scoped to one **Team** — the
actuatable chart unit: you **build** a team, **actuate** it into a live set of agents, then
**execute** work through it.

Above the three verbs sits the **portfolio home**: the operator's landing surface, where
**Organizations** — named, budgeted, isolated groups of teams — and their teams are legible at a
glance, and where shared provider capacity is governed (`design/organizations/05`–`06`). The phases
are the per-team navigation below it; a fourth, post-MVP surface joins them:

> Teams are **Built**, **Actuated**, **Executed** — and **Improved** in the lab: the experiments
> series (`design/experiments/`) compares frozen team variants on the same tasks and promotes a
> winner only through a governed gate. Navigation gains the **Lab** section when the L-series lands.

```
   ┌────────────┐      team         ┌────────────┐   provisioned   ┌────────────┐
   │  1. Build  │ ───document────▶  │ 2. Actuate │ ─────team──────▶│ 3. Execute │
   │  (editor)  │                   │(provisioner)│                 │ (engine)   │
   └────────────┘                   └────────────┘                 └────────────┘
     shape the team                   make it ready                  give it intent
```

The boundary between phases is deliberate: **building never runs anything, actuating never does
work, execution never edits the chart.** Each phase has a clean, checkable hand-off.

---

## Phase 1 — Build

**What it is:** the WYSIWYG org-chart editor and its thin persistence server (`org-chart-editor.md`).

**What you do:** pick a team type, drop roles and formations onto a canvas, wire reporting
lines and sibling dependencies, nest child teams, set salaries and per-agent extensions, and bind
connector instances (`design/builder-connectors.md`).

**The artifact it produces:** a serialized **Team document** (`canopy.team`, schemaVersion 2;
v1 `canopy.organization` documents import forever) — chart + role bindings + salaries, explicitly
excluding memory, secrets, and in-flight work. This document is the input to Phase 2. It is
versionable, diffable, and hand-offable; nothing about it assumes a runtime — and it carries no
organization membership, so it stays portable between organizations and operators.

**Done when:** the document passes export-mode validation (a single legal, runnable structure).

---

## Phase 2 — Actuate

**What it is:** the **team actuator** — it takes a validated Team document and *spins up the
agents*, provisioning each node into a live, addressable runtime agent that is ready to receive
work. Actuation is the moment the chart stops being a drawing and becomes a standing team waiting
for intent.

**What it does, per node (the seams reserved in `org-chart-editor.md` §10):**

- **Provision an agent** for each `agent` in the chart — its role instructions and `extensions`
  seed the agent's persona; its `salary` funds its BudgetMeters.
- **Wire the reporting graph** — each `managerId` becomes a delegation/escalation route; a manager
  can only delegate to its direct reports.
- **Establish standing dependencies** — each design-time dependency becomes the manager's default
  Dependency declaration when it later fans out an Intent.
- **Mount child teams** — each nested team attaches as an opaque reporting edge.
- **Run readiness checks** — confirm every agent has been allocated its workspace, credentials
  (runtime-owned, never in the document), model/tool grants (including connector instances serving
  every connector-backed grant), and budget, and reports *ready*. A team is "actuated" only when
  its whole tree is green.

**The artifact it produces:** a **provisioned team** — the same structure, now backed by
live agents with durable, isolated workspaces, waiting idle. No work has happened yet.

**What it deliberately is not:** it does not give the team a goal, and it does not execute.
Actuation is reversible and idempotent — you can tear down and re-actuate from the same document.

---

## Phase 3 — Execute

**What it is:** the **execution engine** (`execution/README.md`) — it gives an actuated team a
standing **Intent** and drives the work through the chart until every responsibility ends in
something checkable.

**What it does:**

- **Seed the root Intent** — the operator hands the root agent a goal (or a Cadence or connector
  trigger generates one); the root decomposes it into Assignments for its reports, and delegation
  flows down the reporting lines.
- **Honor the gates** — DependencyGates hold work until upstream artifacts reach their declared
  threshold; ApprovalGates pause consequential actions for human/manager consent; InterventionGates
  surface stalls upward (and hold work reversibly when a provider capacity window exhausts —
  `design/organizations/04`).
- **Meter the spend** — every model and tool call is metered against each agent's BudgetMeter
  between steps; managers see burn rate, plan progress, and stalls in real time and can intervene
  before a runaway task becomes a runaway bill.
- **Collect the deliverables** — every discharged responsibility yields an artifact or an
  attestation; acceptance is contract-based, not vibes-based, and rolls up the tree.

**The artifact it produces:** completed work — artifacts and attestations — plus a full provenance
trail from each SpendEvent up to the root Intent.

**What it deliberately is not:** it never edits the chart. Only the user, back in Phase 1, makes a
permanent structural change to a team — and when the lab suggests one, it arrives as a governed
promotion the operator ratifies, never as a self-edit (`design/experiments/03` §7).

---

## Why the split matters

- **A clean serialization boundary.** The Phase-1 document is the contract. Phases 2 and 3 are free
  to evolve their runtimes without changing what a chart *means*.
- **Reversibility.** You can re-actuate a torn-down team, or re-run an intent, from the same
  document — because the document holds no runtime state.
- **Auditability.** Each phase's output is inspectable on its own: a document you can read, a
  provisioned team you can check for readiness, a run you can trace end to end.

All three phases are live today, team-scoped, under the portfolio home. The Lab joins them
post-MVP as the fourth surface: Build → Actuate → Execute → **Improve**.
