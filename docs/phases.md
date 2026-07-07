# Canopy — The Three Phases: Build → Actuate → Execute

**Status:** Design overview (Phase 1 implemented; Phase 2 in progress — A1–A3 shipped; Phase 3 forthcoming)
**Reads with:** `domain-model.md` (authoritative abstractions), `org-chart-editor.md` (Phase 1 spec, esp. §10 "Seams for actuate & execute").

Canopy turns an organization chart into a running system. That happens in three distinct phases,
each consuming the artifact the previous one produced. The phases are the top-level navigation of
the product (the left sidebar): you **build** an organization, **actuate** it into a live set of
agents, then **execute** work through it.

```
   ┌────────────┐   organization    ┌────────────┐   provisioned   ┌────────────┐
   │  1. Build  │ ───document────▶  │ 2. Actuate │ ──organization──▶│ 3. Execute │
   │  (editor)  │                   │(provisioner)│                 │ (engine)   │
   └────────────┘                   └────────────┘                 └────────────┘
     shape the org                    make it ready                  give it intent
```

The boundary between phases is deliberate: **building never runs anything, actuating never does
work, execution never edits the chart.** Each phase has a clean, checkable hand-off.

---

## Phase 1 — Build (implemented)

**What it is:** the WYSIWYG org-chart editor and its thin persistence server (`org-chart-editor.md`).

**What you do:** pick an organization type, drop roles and formations onto a canvas, wire reporting
lines and sibling dependencies, nest child organizations, set salaries and per-agent extensions.

**The artifact it produces:** a serialized **Organization document** — chart + role bindings +
salaries, explicitly excluding memory, secrets, and in-flight work. This document is the input to
Phase 2. It is versionable, diffable, and hand-offable; nothing about it assumes a runtime.

**Done when:** the document passes export-mode validation (a single legal, runnable structure).

---

## Phase 2 — Actuate (in progress: A1 profiles/gateway/ledger + A2 sandbox/runtime boot + A3 router/bus shipped)

**What it is:** the **organization actuator** — it takes a validated Organization document and
*spins up the agents*, provisioning each node into a live, addressable runtime agent that is ready
to receive work. Actuation is the moment the chart stops being a drawing and becomes a standing
organization waiting for intent.

**What it does, per node (the seams already reserved in `org-chart-editor.md` §10):**

- **Provision an agent** for each `agent` in the chart — its role instructions and `extensions`
  seed the agent's persona; its `salary` funds its BudgetMeters.
- **Wire the reporting graph** — each `managerId` becomes a delegation/escalation route; a manager
  can only delegate to its direct reports.
- **Establish standing dependencies** — each design-time dependency becomes the manager's default
  Dependency declaration when it later fans out an Intent.
- **Mount child organizations** — each nested org attaches as a sub-org-opaque reporting edge.
- **Run readiness checks** — confirm every agent has been allocated its workspace, credentials
  (runtime-owned, never in the document), model/tool grants, and budget, and reports *ready*. An
  organization is "actuated" only when its whole tree is green.

**The artifact it produces:** a **provisioned organization** — the same structure, now backed by
live agents with durable, isolated workspaces, waiting idle. No work has happened yet.

**What it deliberately is not:** it does not give the organization a goal, and it does not execute.
Actuation is reversible and idempotent — you can tear down and re-actuate from the same document.

**Open questions (to resolve when Phase 2 is built):** the sandbox/isolation backend; how model and
tool grants are declared (the catalog's tool-grant story, kept out of the Phase-1 document by
design); and how readiness failures surface back to the operator.

---

## Phase 3 — Execute (forthcoming)

**What it is:** the **execution engine** — it gives an actuated organization a standing **Intent**
and drives the work through the chart until every responsibility ends in something checkable.

**What it does:**

- **Seed the root Intent** — the operator hands the root agent a goal; the root decomposes it into
  Assignments for its reports, and delegation flows down the reporting lines.
- **Honor the gates** — DependencyGates hold work until upstream artifacts are accepted;
  ApprovalGates pause consequential actions for human/manager consent; InterventionGates surface
  stalls upward.
- **Meter the spend** — every model and tool call is metered against each agent's BudgetMeter
  between steps; managers see burn rate, plan progress, and stalls in real time and can intervene
  before a runaway task becomes a runaway bill.
- **Collect the deliverables** — every discharged responsibility yields an artifact or an
  attestation; acceptance is contract-based, not vibes-based, and rolls up the tree.

**The artifact it produces:** completed work — artifacts and attestations — plus a full provenance
trail from each SpendEvent up to the root Intent.

**What it deliberately is not:** it never edits the chart. Only the user, back in Phase 1, makes a
permanent structural change to an organization.

---

## Why the split matters

- **A clean serialization boundary.** The Phase-1 document is the contract. Phases 2 and 3 are free
  to evolve their runtimes without changing what a chart *means*.
- **Reversibility.** You can re-actuate a torn-down org, or re-run an intent, from the same
  document — because the document holds no runtime state.
- **Auditability.** Each phase's output is inspectable on its own: a document you can read, a
  provisioned org you can check for readiness, a run you can trace end to end.

Phase 1 is live today. The sidebar shows Phases 2 and 3 so the whole trajectory is visible; they
open onto descriptions of what's coming rather than working screens, until the actuator and engine
land.
