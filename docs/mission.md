# Mission — What Canopy Is For

**Status:** Adopted vision (operator-ratified) · **Date:** 2026-08-16
**Upstream:** none. This is the root of the documentation tree; every other document in this repository is downstream of it.
**Reads with:** `org-roadmap.md` (this mission applied reflexively — Canopy staffing itself), `design/doctrine.md` (how this document reaches every running agent), `risks/README.md` (the register that keeps this document honest).

---

## 1. The mission

> **Canopy turns one human's direction into the sustained, governed output of an organization.**

In full: Canopy makes delegation to AI **safe enough, legible enough, and cheap enough that one person can run an organization** — not a session, an organization: standing teams doing real work under structure the operator can read, budgets they can see, and consequences only they can ratify.

The bet underneath is specific. The bottleneck to delegating real work to AI is not model capability — capability is the commodity, and it compounds without our help. The bottleneck is **trust**: knowing what a delegate may do, seeing what it is doing, bounding what it can spend, and verifying what it produced. Structure is the technology humans invented for scaling exactly that — reporting lines, job descriptions, budgets, acceptance, audit. Canopy's contribution is making that structure *executable*. The chart is not a picture of the system; it is the system (`domain-model.md`).

Three currencies flow through every Canopy design decision, and the mission names their order: **trust** is what the product manufactures, **attention** is what it must conserve, **tokens** are what it spends. A feature that buys throughput by spending operator attention is regression, not progress.

## 2. The center of gravity: one operator (decision record)

**Decided 2026-08-16: the mission is centered on a single operator.** The alternative considered — "governable AI labor" in general, with teams of humans as operators and one-person operation as merely the strongest evidence — is recorded and deliberately not chosen as the center.

Why one operator:

1. **Attention is the binding constraint.** The scaling limit on a fleet is not tokens or compute; it is the operator's judgment budget (`risks/scalability.md` SC-4: "at 5 agents this is engagement; at 50 it's a pager"). Centering one operator makes attention a first-class, budgeted resource: approvals per day are as real a currency as tokens per assignment, and every surface — inbox severity discipline, plan review, digest vs. needs-you — is designed against that budget.
2. **The general claim is unfalsifiable until the narrow one is proven.** "Organizations can govern AI labor" is demonstrated only by the hardest version: one person, a real backlog, published costs, a month unattended (`org-roadmap.md` §5). You cannot claim governable-in-general before governable-by-one.
3. **It matches the product's actual physics.** Every governing primitive — gate ownership, acceptance, ratification of governed actions — already resolves to a single accountable human. Multi-operator is a widening of that seat, not a re-founding; nothing in this decision forecloses it.

## 3. Success, defined

The mission is achieved for a given organization when the operator's remaining duties are exactly two:

1. **Approve direction** — the mission, standing intents, doctrine, and the documents that set course.
2. **Approve consequences** — the pull requests, publishes, merges, and external actions that leave the walls.

Everything between — planning, delegation, implementation, verification, rework, escalation — happens inside the structure: visible at any depth the operator cares to inspect, but not requiring the operator's hands. Inspection is a right, never a duty.

For Canopy itself this has a concrete, checkable form: **the operator approves the direction documents and approves the incoming pull requests; the fleet produces everything in between.** The source of truth is the GitHub repository; direction enters as documents, work returns as PRs. `org-roadmap.md` is this mission applied reflexively — the self-hosting ladder is not a dogfooding tactic but the mission's standing acceptance test, and its §5 metrics (cost per closed unit, acceptance rate, human-minutes per merged PR, a month unattended) are the mission's measurement.

## 4. Standing commitments

These commitments are mission-level: they bind every organization Canopy runs, not just the self-hosting ladder. `org-roadmap.md` §2 states their ladder-specific application; where phrasings diverge, this section wins.

1. **Agents propose; humans ratify; the platform executes.** Every consequence that leaves the walls — a merge, a publish, a message to a stranger, an action in the world — is a governed action: consented before (an ApprovalGate owned by a human), evidenced after (an attestation). For self-hosted organizations this is the **recursion boundary**: orgs edit the codebase as artifacts — branches, diffs, proposed PRs — and never touch the running instance; deploy and self-update are not grants that exist; the control plane is never in any org's tool surface.
2. **The trust ladder.** Authority escalates only when the current level has become boring — artifact-only work, then proposal of consequential actions, then (much later, if ever) consequential external action. A rung never starts until the previous rung's acceptance rate makes the escalation unremarkable. Trust is earned in the ledger, not asserted in the pitch.
3. **Receipts, not theater.** Every unit of work is benchmarkable and published: ledger-attributed cost, verified outcome, rework rounds, human minutes. Wins and losses both — the ledger is the product's honesty, and the answer to PF-1 is a feed, not an event.
4. **Real work runs in real walls.** Isolation strength must match the work's blast radius; where it temporarily cannot, the waiver is explicit, logged, and scheduled for retirement — never silent, never normalized.
5. **Governance precedes autonomy.** No capability runs unattended before the machinery that governs it exists: capacity governance before cadenced fleets, plan review before dispatch, acceptance before merge. And autonomy enters at exactly one place — intake. A trigger replaces the operator *typing*, never the operator *deciding* (`design/standing-orgs.md`, principle 2).

## 5. What Canopy is not

Three adjacent framings are deliberately rejected; each rejection is enforced somewhere concrete.

- **Not an agent framework.** The engine has no idea what a software engineer is; roles, teams, and formations are catalog data (`domain-model.md` invariant 11). Canopy's value is not agents — it is the structure that makes agents governable. If a better agent runtime appears, Canopy should be able to wrap it in a week and be *more* valuable for it.
- **Not a simulation.** Charts that are watched rather than worked are the named failure mode (`risks/marketing.md` MK-3, "SimCity for agents"). Every responsibility ends in an artifact or an attestation; nothing is done by vibes; demo magic that does not survive contact with a real backlog is cut.
- **Not an autonomous company.** The aspiration is explicitly *not* an organization that runs itself. The operator's two approvals (§3) are not scaffolding to be engineered away; they are the product. Removing the human from direction and consequence would not complete the mission — it would abandon it.

## 6. How every team knows this

Purpose must cascade the way structure already does: **doctrine** (this document) attaches to the Organization, **purpose** to the Team, **duty** to the Role, **task** to the Assignment — and an agent's compiled context is the chain above it, in that order. The mechanism is specified in `design/doctrine.md`; until it ships, the channel is manual and mandatory: this document is upstream of every design doc, quoted at the head of every team charter the operator authors, and its §4 commitments are the standing test applied in every plan review and acceptance.
