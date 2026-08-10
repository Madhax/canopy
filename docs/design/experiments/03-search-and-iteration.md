# 03 · Search and Iteration — the next challenger, the envelope, and the lab itself

> **Status:** Proposal — experiments working group, 2026-08-10
> **Reads with:** `01-experiment-model.md`, `02-rubric-and-judging.md`, `../../manager-responsibilities.md` (the ⛔ this section extends, not violates), `../../org-roadmap.md` §2 (the trust ladder and recursion boundary), `../../roles.md`, `../../teams.md`

## 1. The variant space

A challenger differs from its parent along one of six axes — together they span "team structure, size, and the models being used":

| Axis | What varies | Examples |
|---|---|---|
| Topology | nodes and reporting edges | remove the triager; add a second engineer; flatten a middle manager |
| Roles | which RoleTemplate a node instantiates | `support-engineer` → `qa-engineer` at the triage slot |
| Instructions | per-node extensions (never catalog roles — that authoring loop is O5's, and it composes: an O5 role revision arrives here as a challenger) | tighter repro protocol on the triager |
| Salaries | per-node allowances | trim the lead's coordination budget 30% |
| Models | per-node profile bindings | the flagship: `backend-engineer` down a tier |
| Schedule | the team's knob defaults | pace the team to half duty-cycle, does quality hold? |

## 2. The mutation vocabulary

A closed enum, one mutation per variant by convention (`01` §3):

`add-node · remove-node · swap-role · reparent · rebind-model · resize-salary · edit-extensions · swap-formation · import · manual`

Each variant's `mutation` records kind, target, detail, `proposedBy`, and an optional `predictedEffect` — the proposer's stated expectation, confirmed or embarrassed by the leaderboard later (`05` §1). The lineage tree renders these edges; after 100 iterations, *"what have we tried and what did each change buy"* is a picture, not an archaeology project.

## 3. Generators — where the next B comes from

**G0 — the operator.** The bench's variant composer (`04` §5). Always available; the only generator at L1.

**G1 — mechanical sweeps.** Deterministic generators for the searches that don't need judgment, shipped as platform code:

- **`model-downgrade`** (the flagship): for each node, walk the model-tier ladder downward one variant at a time; a downgrade survives if all floors hold and cost strictly improves — **dominance, not weighting**. The sweep stops at the first floor breach per node and records the frontier: *the cheapest binding per role at undiminished quality.* This answers the user story — "a cheaper model for a role with no degradation is a preferable team" — as a standing, mechanical fact-finder.
- **`salary-trim`**: same ladder logic over allowances (does the work fit in less budget, or does the hard-stop rate spike?).
- **`flatten`**: remove one management layer; the structural form of the PF-1 question.

Sweeps are enumerable, so their variants auto-enroll inside the envelope (§5) without ceremony.

**G2 — the proposer.** A `structure-proposer` role (new catalog role, lab formation §6): reads the scored lineage, verdict rationales, and run transcripts — **never holdout tasks** (`02` §7) — and produces a **VariantProposal artifact**: `{mutation, rationale, predictedEffect}`. The proposer is the retro-running manager the experiment needs: "B2's failures cluster in reproduction; propose restoring the triager but on the cheap tier." Its proposals are artifacts; the platform instantiates them (§7); its predictions are scored against outcomes, giving the proposer itself an accuracy stat — a proposer that can't beat the sweeps at suggesting mutations is itself evidence, and gets retired like any underperformer.

## 4. Policies — how the loop runs

```jsonc
"policy": {
  "kind": "champion-challenger",     // champion-challenger | sweep | manual
  "maxActiveChallengers": 2,         // concurrent challengers beside champion + baseline
  "trialsPerChallenger": 9,          // rotation trials before verdict-or-retire
  "generators": ["sweep:model-downgrade", "proposer"],
  "cadenceId": "cd_…"                // §8 — continuous mode
}
```

- **`champion-challenger`** (the steady state): the champion defends; generators feed challengers up to `maxActiveChallengers`; each challenger gets its trial budget, then either triggers the promotion predicate (`02` §4) or retires with its record. The champion changes only through promotion — ratified, receipted, reversible (the lineage keeps every prior champion one click from reinstatement).
- **`sweep`**: batch mode — enumerate, run, report the frontier. Ends with a report, not a standing loop.
- **`manual`**: no generators; the operator enrolls every variant. L1's only mode.

## 5. The envelope — pre-approved search space

The envelope is the operator's standing consent, and the line between retroactive and prospective governance:

```jsonc
"envelope": {
  "maxNodes": 6,
  "allowedRoles": ["engineering-lead", "backend-engineer", "qa-engineer", "support-engineer"],
  "modelTiers": ["fable", "sonnet", "haiku"],
  "salaryCeilingTokens": 250000,
  "mutations": ["rebind-model", "remove-node", "add-node", "resize-salary"],
  "autoInstantiate": true,
  "maxTrialsPerDay": 6
}
```

Inside the envelope, generated challengers instantiate and trial **without asking** — the operator reviews the lineage when they choose to; that is the "human in the loop as retroactive input" posture, made explicit and bounded. Outside it — a novel role, a bigger team, a mutation kind not listed — instantiation opens an ApprovalGate with the proposal as payload, exactly the staged-delegation review pattern (drafts reviewed as the real thing, not prose). The envelope is editable mid-experiment; tightening it retires now-out-of-bounds candidates, visibly.

## 6. Is the lab itself a Canopy team? — the honest split

The instinct is right in half and wrong in half, and the halves are separable:

**The bookkeeping is platform machinery.** Scheduling trials, dispatching intents, harvesting metrics, aggregating panels, computing win rates, enforcing the envelope — deterministic, free, and *constitutive of the instrument's trustworthiness*. An agent that "decides" scores or "remembers" the leaderboard would corrupt the measurement with the very stochasticity the experiment exists to control. This half is `experiments.py` beside `scheduler.py`: a control-plane module with tables, not a team. (Its actions cost no tokens and appear in no meter — like the engine itself.)

**The cognition is agent work, and belongs in a team.** Three jobs inside the loop are judgment, not bookkeeping — authoring tasks, judging exhibits, proposing mutations — and running them as catalog roles in a real team buys exactly what teams are for: metering (evaluation overhead becomes a visible ledger line, `01` §7), transcripts and inspectability (why did judge 2 prefer exhibit 1 — read the reasoning), gates (a task-author's generated task *is* reviewed via the standing approval flow), and cadenced operation. So the catalog gains a **`experiment-lab` formation**: `lab-lead` (manager), `task-author`, `evaluator` ×N, `structure-proposer` — instantiated per organization (one lab serves all its experiments), arriving at L3/L5 as its roles become load-bearing (`06` §1).

The boundary that keeps this honest: **the lab has no authority over the experiment record.** Lab agents produce artifacts — VerdictCards, task drafts, VariantProposals. The platform aggregates, records, instantiates, and enforces; the operator ratifies. The lab-lead manages lab *work* (assignment flow, quality of judging), never experiment *outcomes*. And until the lab formation exists, every one of its jobs has a degraded-but-honest fallback: curated tasks, human verdicts, operator-authored variants — L1 runs a complete A/B with no lab at all, which is the proof the machinery doesn't secretly depend on it.

## 7. The recursion boundary, extended

`manager-responsibilities.md` is deliberate: no org restructures itself; only the user, through the editor, changes a chart. This series *extends* that rule rather than breaching it, with the same three-part shape the org-roadmap's recursion boundary uses (propose / ratify / platform-enforced wall):

1. **Proposals are artifacts.** The proposer authors team *documents* — data, the thing O5 already establishes an org may author. It holds no tool that edits any team.
2. **Instantiation is a platform act** under standing consent (the envelope) or explicit consent (the gate). Ephemeral variant teams are sandboxed competitors, not the production org.
3. **Production changes only through the one door.** Promotion (`05` §3) is a governed action: ApprovalGate, owned by the operator, previewing exactly what changes, receipted in the feed. A month of unattended iteration can *suggest*; it cannot *ship*.
4. **The lab never experiments on itself.** Meta-experiments (variants of the lab formation, judge-tier searches judged by the judges under test) are forbidden in v1 — the circularity needs its own design (open question 3). The lab's own structure is operator-owned, through the editor, like any team.

## 8. Continuous operation and course correction

**Continuous mode** is a Cadence on the experiment (`policy.cadenceId`): *"run up to N trials nightly."* Trials are `batch`, runway-courteous (skip-with-receipt when capacity is tight — the `cadence.skipped reason=capacity` precedent), and confined to `activeHours` if set. The unattended bar is the org-roadmap's §5 bar, applied to the lab: a month on cadence, acceptance-rate boring, costs published, zero recursion-boundary violations.

**Course correction is a first-class surface, not an interrupt.** Everything the operator does after 100 unattended iterations:

| Action | Where | Effect |
|---|---|---|
| Overturn a verdict | trial page | human tier supersedes; calibration stat updates; leaderboard recomputes |
| Retire a variant / prune a lineage branch | leaderboard, lineage | stops its trials; record stays |
| Reinstate a prior champion | variant page | governed, like promotion |
| Tighten/loosen the envelope | bench | out-of-bounds candidates retire visibly |
| Re-weight the rubric | rubric editor | version bump; future trials; explicit re-score if wanted |
| Pause / conclude | experiment header | stops scheduling; never kills in-flight runs |

**Deliberately not designed here:** routing production work across specialized champions (the per-tag leaderboard will make "solo for trivial, full pod for gnarly" visible and tempting — that is a dispatch-policy product feature with its own design debt, not an experiment feature); genetic/bandit search policies (champion–challenger plus sweeps must prove insufficient first).

## 9. Resolved decisions and open questions

**Resolved:** one lab per organization, serving all its experiments (per-experiment labs multiply idle judges); sweeps are platform code, not agent behavior (determinism is their value); the proposer's predictions are scored (an unaccountable advisor is a vibes machine); promotion is never automatic, at any accumulated win rate (the trust ladder does not have an unattended top rung).

**Open:** (1) proposer context budget — reading 100 trials of transcripts is expensive; likely the platform serves it a compacted lineage digest, which is itself a bias choice to design carefully. (2) Multiple proposers in parallel (diversity) vs. one (attribution) — leaning one until its accuracy stat plateaus. (3) Meta-experiments (§7.4) — the judge-tier question is real and currently answerable only by human audit; design the circularity break before lifting the ban. (4) Cross-experiment generator learning ("model-downgrade usually survives on writer roles") — attractive, deferred with meta-learning (`README` non-goals).
