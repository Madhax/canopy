# 06 — Status and direction

*What is built today, what is designed but not built, where the docs disagree about
it — and where the roadmap points. Short, and honest about its own limits.*

## A caution about dates

The design docs mostly date from early-to-mid July 2026, and building continued after
they were written. Some docs were amended in place without date bumps; others went
stale. So the statements below are **what the documents themselves say** — the
freshest in-repo record is named at the end. When in doubt, trust the running system
over any document, and the newest document over the oldest.

**A key to the letter codes** used below (and occasionally in docs 03–05). The
design docs number their milestones and debts by suite: **A** = actuation build
milestones, **E** = execution milestones, **E-D** = execution debts, **D** =
actuation debts, **X** = manager-proposal items, **O** = the roadmap's
teams. So "E-D1" reads "execution debt number one."

## Built (per the docs' own statements)

- **Phase 1 — the org chart editor** — implemented. The one unambiguous status line
  in the suite ([phases.md](../phases.md)): "Phase 1 implemented; Phase 2 in
  progress — A1–A3 shipped; Phase 3 designed." The machine-readable catalog
  (`catalog/catalog.json`) ships hand-transcribed.
- **Phase 2 — actuation fabric** — substantially built. Milestones A1–A3 shipped per
  phases.md; the actuation suite's own debt ledger
  ([phase3-debts.md](../actuation/phase3-debts.md)), updated through execution
  milestone E6, treats the full A1–A6 fabric plus much of Phase 3 as landed.
- **Execution machinery (per the debt ledger's close-out)** — real assignment-bound
  budget meters with rework funding; all five gate kinds with owners; durable
  per-position memory surviving re-actuation; the step "delta" taxonomy; and the
  runtime pivot: **real work runs as supervised, windowless Claude Code sessions,
  wired back to Canopy through the platform's own reporting channel.** Open work
  survives deactuate → re-actuate.

## Designed, not (confirmed) built

- **The Operate-mode cockpit** — Mission Control, Agent Inspector, Intent Console,
  Inbox, Cost Explorer ([operator-experience.md](../execution/operator-experience.md))
  — a Phase-3 *design*, despite its confident prose.
- **Hard sandboxes** — the container/micro-VM tiers (T2/T3). Today's isolation is
  soft, and the runtime doc answers how in its own words: MVP runs CLI sessions as
  ordinary subprocesses under the trusted-local waiver
  (`execution.allow_trusted_local = true`); containers remain future work (the
  build may have moved since).
- **Pieces of the envelope model** — the Tool Proxy as specified, tier-refusal
  checks, MCP tool curation, grant packs, and the `actor`, `workflow`, and
  `human-proxy` runtime kinds. (Grants-as-data itself is real — the catalog carries
  tool grants.)
- **Manager mid-flight powers** — scope-drift alarms (X2), standing directives (X4),
  manager-initiated interventions; plan-review checkpoints (X3) appear already
  folded into the rulebook, but the proposal doc was never retired, so the two
  sources disagree on paper.
- **Live chart edits** — editing a running team (debts D7/D8) remains open: tear
  down, edit, re-actuate.
- **Cadences** (scheduled recurring work) — labeled *stretch* (E7).
- **The O2 GitHub integration** — automated issue ingestion, pushing, PR creation.
  The E8 capstone run does all of this deliberately by hand: "the team proposed, the
  human ratifies."
- **Deferred by design** — Blueprints (clone a team — which also parks use-case #31),
  multi-user login, hosted/network deployment, marketplace distribution, and the
  infrastructure swap list: heavier-duty off-the-shelf messaging and database
  technologies (Redis/NATS buses, Postgres), cloud stores, other AI providers.

## Where the docs disagree with each other

Collected from all three analyses; none is smoothed over in this series:

1. **How far did the build get?** The amendments log (2026-07-26) says "E1 is
   implemented; E2+ is not," while the actuation debt ledger's close-out reads as
   updated *through E6*. These were written at different times; the debt ledger is
   the later record. The truth is a moving target the docs only sample.
2. **The A2A protocol layer was never adopted** — a plain mailbox shipped instead.
   The data-plane doc's A2A sections are historical intent; the router/bus model
   survives.
3. **The budget model went through three generations** — "meter per routed task"
   (control-plane doc) → one standing meter per node (as first built) → real
   assignment-bound meters with rework funding (current). The oldest description was
   never exactly true.
4. **The threat model lags the CLI runtime** — it still promises "no key in any
   agent environment" and pre-call budget stops; the wrapped-session design weakens
   both (login credential on disk in the sandbox; turn-boundary enforcement, debt
   E-D1) and discloses it — but only in its own doc.
5. **Small drift**: the editor spec says 16 formations, the teams doc lists 17;
   several docs say "~75 roles" while the roles doc's own tables count about 87; the
   `cli-runtime` doc says "as built in E3" while the later amendments log lists E3
   as not yet built; "user" vs. "operator," "tick" vs. "turn" (this series
   standardizes on operator and turn); salary numbers everywhere are uncalibrated
   placeholders.

## Where the roadmap points

The long-range direction is an explicitly **aspirational** ladder with one
principle: *"Canopy grows by Canopy working on Canopy."* Milestones are expressed
not as features but as teams that should exist and run:

- **O1** — a fixture software team proving the machinery;
- **O2** — `canopy-docs`: a documentation-fixing team, the first to touch a real
  repository (seeded by the by-hand E8 capstone);
- **O3–O5** — a bug-closing team, a feature-building team, a role-improving team;
- **O6–O7** — content and community-support teams;
- **O8** — "Canopy Inc.": all of them mounted as child teams under one root with the
  standing intent *"grow Canopy"*;
- **O9+** — explicitly "vision, not promise."

Standing rules for the whole ladder: self-hosted teams only ever *propose* changes as
branches and pull requests — a human ratifies every merge; authority climbs a "trust
ladder" slowly; every rung publishes its costs; and a rung only counts as existing
after running unattended on a schedule for a month with published numbers.

## How to check status yourself

Two pointers beat every summary, including this one:
[actuation/phase3-debts.md](../actuation/phase3-debts.md) — the living debt ledger
with its close-out section, the best in-repo record of what actually shipped — and
[execution/amendments-2026-07-26.md](../execution/amendments-2026-07-26.md) — the
changelog of what the design decided late. When they disagree with older docs, they
win; when they disagree with the running system, the system wins.

---

**Where this comes from:**
[phases.md](../phases.md) (the authoritative status line) ·
[actuation/phase3-debts.md](../actuation/phase3-debts.md) (the debt ledger and
close-outs) ·
[execution/amendments-2026-07-26.md](../execution/amendments-2026-07-26.md) (late
decisions; E-status statements) ·
[execution/cli-runtime.md](../execution/cli-runtime.md) (the trusted-local waiver,
subprocess MVP) ·
[actuation/roadmap.md](../actuation/roadmap.md) (planned swaps — aspirational) ·
[team-roadmap.md](../team-roadmap.md) (the self-hosting ladder — aspirational) ·
[execution/e8-runbook.md](../execution/e8-runbook.md) (what O2 will automate) ·
[execution/operator-experience.md](../execution/operator-experience.md) (the
designed cockpit) · status flags from all three underlying analyses.
