# 02 · Rubric and Judging — factors, weights, evaluators, and the Goodhart wall

> **Status:** Adopted 2026-08-09 (operator decision) — proposed by the experiments working group
> **Reads with:** `01-experiment-model.md`, `../../domain-model.md` (§Economics — the Goodhart-proofing precedent), `../../execution/work-model.md` (the records measured factors read), `../organizations/02-capacity-model.md` §4 (the tier-of-truth pattern this reuses), `../../testing.md`

## 1. Four sources of truth

Every rubric factor declares its **source** — where its number comes from. The sources are ordered by a simple principle: *measure what the platform can measure; judge only what instruments cannot reach; let humans outrank machines.*

| Source | What it is | Examples | Authority |
|---|---|---|---|
| **measured** | Read from stock records — ledger, engine, gates, steps. Deterministic, free, un-gameable by the subjects. | cost, rework rounds, operator load, active time | Authoritative for its factor, always. |
| **programmatic** | A **probe executor** runs a check against the run's deliverable — a test suite, a schema validation, a lint. Deterministic per run. | the regression-suite probe, "CSV contract holds" | Authoritative for its factor; where a programmatic probe exists for `correctness`, judged correctness becomes advisory commentary. |
| **judged** | A blinded evaluator panel compares exhibits (§5). Stochastic; mitigated by panels, calibration, and audit. | fix quality, completeness, brief-adherence | The default for quality; overridden by human. |
| **human** | The operator's recorded verdict — a first-class reading, not an edit to someone else's. | overrides, audits, promotion ratification | Outranks everything. Never averaged with machine verdicts; supersedes them. |

Preference verdicts (which run was better overall) carry the same tiering: **human > panel > solo judge**, the capacity ledger's most-authoritative-recent rule applied to judgment. A trial's displayed verdict is always the most authoritative one that exists, and the superseded ones remain visible, struck through, in the record.

## 2. The factor catalog

The starting vocabulary — every key stable, every default a starting point the rubric editor exists to change. Weights below are the shipped **software-delivery template**; other domain templates (content, support) re-weight the same vocabulary and are catalog data (`catalog.json` gains `rubricTemplates[]` — rubrics are data, like roles).

| Key | Source | Default weight | Direction | Notes |
|---|---|---|---|---|
| `correctness` | programmatic (probe) *else* judged | **40** | higher | The factor every rubric must carry, and the one that must carry a **floor** (§4). Where the domain has an executable check — target-app's acceptance suite, a replayed bug's regression test — correctness is measured, not opined. |
| `solution-quality` | judged | 20 | higher | Craft: clarity, maintainability, appropriateness of approach. Per-factor judge instructions are rubric data (§6). |
| `completeness` | judged | 0 (advisory) | higher | All parts of the ask addressed. Folded into `solution-quality` by default; split it out when briefs are multi-part. |
| `brief-adherence` | judged | 0 (advisory) | higher | Scope fidelity — did what was asked, no more. The judged ancestor of X2's future mechanical tripwire. |
| `cost` | measured | **20** | lower | Cache-aware estimated USD (`fmtCostHonest` rules; the F1 lesson is load-bearing here — raw-token cost would reward cache-blind teams). Tokens shown alongside. |
| `operator-load` | measured | 10 | lower | Count of operator-owned gates the run opened (escalations, clarifications, approvals needing a human, interventions). The org-roadmap's "human minutes per merged PR", mechanized. **Keep the weight modest**: punishing questions teaches guessing — a clarification at intake is the cheap form of a failure caught late. |
| `rework` | measured | 5 | lower | Rejection→rework rounds before acceptance. |
| `active-time` | measured | 5 | lower | Σ step durations. Excludes gate-wait, capacity holds, operator latency (`01` §6). |
| `elapsed-time` | measured | 0 (advisory) | lower | Wall clock, displayed, unweighted by default — it measures the operator and the subscription as much as the team. |
| `coordination-overhead` | measured | 0 (advisory) | lower | Coordination-step share of spend (the SC-1 metric, already tagged on every step). The structural-efficiency lens; advisory so flat teams don't win on bureaucracy-avoidance alone while quality floors do the real guarding. |
| `consistency` | measured | 0 (advisory) | higher | Inverse variance of this variant's composite across trials. Meaningful only at n ≥ ~5; the leaderboard suppresses it below that. |

**Guardrails** are not factors and carry no weights — they disqualify the run (score 0, flagged, never averaged):

- `contract-match` — the deliverable matches the assignment's contract type (a `TestReport` where a `PullRequest` was due fails structurally);
- `clean-hands` — no attempted grant violations of `consequential` class in the run's ToolEvents, no recursion-boundary breach;
- `completion` — the run reached `accepted` without an unresolved hard-stop, `failed`, or `cancelled`.

A guardrail breach is a *finding*, prominently displayed; three of them across a variant's trials is a better argument for retirement than any composite.

## 3. The rubric schema

```jsonc
// table: experiment_rubric — (experimentId, version) PK; versions append-only
{
  "experimentId": "ex_m4k2p9q1",
  "version": 1,
  "factors": [
    { "key": "correctness", "source": "programmatic", "probe": "regression-suite",
      "weight": 40, "direction": "higher",
      "floor": { "kind": "non-inferior", "reference": "champion", "marginPct": 0 } },
    { "key": "solution-quality", "source": "judged", "weight": 20, "direction": "higher",
      "judgeInstructions": "Assess the fix as a maintainer would: is it the right shape…" },
    { "key": "cost", "source": "measured", "metric": "estCostUsd", "weight": 20, "direction": "lower" },
    { "key": "operator-load", "source": "measured", "metric": "operatorGates", "weight": 10, "direction": "lower" },
    { "key": "rework", "source": "measured", "metric": "reworkRounds", "weight": 5, "direction": "lower" },
    { "key": "active-time", "source": "measured", "metric": "activeMs", "weight": 5, "direction": "lower" }
  ],
  "guardrails": ["contract-match", "clean-hands", "completion"],
  "judging": {
    "mode": "pairwise-blind",
    "panel": 3,
    "aggregation": "majority-preference-median-grades",
    "humanAuditPct": 10,
    "showReference": false
  },
  "promotion": {                       // §4 — the predicate, itself rubric data
    "minScoredTrials": 5, "minWinRate": 0.6,
    "holdout": { "minTasks": 3, "minWinRate": 0.5 }
  },
  "createdBy": "operator", "createdAt": "…"
}
```

**Versioning is the honesty mechanism.** Trials pin `rubricVersion` at creation; scores are stable forever under later edits. Editing the rubric creates version N+1 and applies to *future* trials. **Re-scoring is explicit**: the operator may re-run scoring of past trials under a new version — this creates a parallel verdict set labeled `rubric v2`, and the leaderboard states which version it ranks under. Nothing is ever silently rescored; a score without its rubric version is not a score (`05` §6).

## 4. Scoring math

Deliberately simple — paired comparisons and floors, no statistics theater:

- **Per factor, per trial:** measured/programmatic values normalize pairwise — for `lower`-direction factors, `n_f(v) = other / (v + other)` over the trial's pair (0.5 = tie); judged factors take the panel's median grade on a 1–5 scale, normalized. With more than two runs per trial, normalization is against the trial mean.
- **Composite:** `S(v, trial) = Σ w_f · n_f(v)` over weighted factors, weights normalized to 100. Guardrail breach ⇒ composite 0, flagged.
- **Floors** are constraints, not weights — the mechanism behind *"cheaper with no degradation."* `non-inferior` floors compare the challenger's factor against the named reference (usually `champion`) per trial; a floor breach makes the trial a **loss regardless of composite**. This is deliberate: without floors, a 40-point correctness weight still lets enough cost savings buy a correctness deficit. Efficiency searches want quality as a *constraint* and economics as the objective; the floor mechanism expresses that without a second scoring system.
- **Across trials:** the headline is the **paired win rate** (wins / scored trials against the champion, same tasks), with the mean composite as the tiebreak lens. Sample size is displayed with every rate, always.
- **Promotion predicate** (rubric data, §3): win rate ≥ `minWinRate` over ≥ `minScoredTrials` scored rotation trials, all floors held, then confirmation on the holdout set (`01` §5). Only then does `champion-suggested` fire — and promotion itself remains a governed action (`05` §3).

## 5. The judging pipeline

1. **Exhibit materialization.** At `judging`, the harness copies each run's deliverable artifacts into neutral **exhibits** — `exhibit-1`, `exhibit-2`, order randomized per judge — with team slugs, node ids, branch names (`canopy/<assignmentId>`), and cost traces scrubbed from the presentation layer. *Honest limit:* content can still carry stylistic tells (a diff's variable naming, a doc's voice); full anonymity is impossible and is not claimed. The mitigations are the panel, calibration probes, and human audit — not pretending the blindfold is perfect.
2. **Judging assignments are ordinary assignments.** Each panel member is an `evaluator` node in the org's lab team (`03` §6); each receives one assignment: the task brief, the exhibits (refs granted via the brief — the stock grant vehicle), the rubric's judged factors with their instructions, and a required deliverable: a **VerdictCard** artifact — `{preference: 1|2|tie, grades: {factor: 1–5}, rationale}` per judged factor. Judge work is metered, transcripted, and inspectable exactly like all work — *what did the judges cost and how did they reason* is a first-class drill-down, not a black box.
3. **Aggregation is platform math, never an agent.** Majority preference; median grades; a **split panel** (no majority, or grade spread > 2) flags the trial `attention` and queues it for human audit. No "head judge" agent synthesizes the panel — an agent aggregator would be an unauditable thumb on the scale.
4. **Calibration probes.** The harness periodically seeds probe trials whose exhibits have a known better side (an accepted deliverable vs. an operator-marked degraded copy). Judges never know which trials are probes. Panel accuracy on probes — *"agrees with ground truth 87% · n 23"* — is displayed on the rubric page, and falling accuracy is the signal to change judge instructions, panel size, or judge model tier. The knob-chip closed loop, applied to judgment itself.
5. **Human audit and override.** `humanAuditPct` of scored trials are sampled into the operator's audit queue. On any trial page the operator can record a human verdict — per-factor grades and/or preference with a note — which supersedes the panel verdict (tier rule, §1) and feeds the calibration stat. Panel-vs-human disagreement is the lab's own quality metric.

## 6. What engineers can change, and how

The user-facing rule: **factors, weights, floors, judge instructions, panel size, and promotion predicates are data** — edited in the rubric editor (`04` §3) or via `PUT /api/experiments/{id}/rubric` (new version), no deploy. The seams behind that rule:

| Change | Mechanism | Code? |
|---|---|---|
| Re-weight, add floor, change panel/promotion config | rubric version bump | no |
| New **judged** factor | rubric data: key + instructions + weight | no |
| New **programmatic** probe | probe executor registry — a keyed, grant-gated executor in the repo-executor mold (`probes.py`; e.g. `regression-suite`, `acceptance-suite`, `schema-check`) | yes, once per probe kind |
| New **measured** metric | the metric menu in `experiment_run.metrics` (`01` §8) | yes — the menu is closed on purpose; a measured metric is a claim about what stock records mean, and that claim gets reviewed |
| New domain template | `catalog.json` `rubricTemplates[]` | catalog data |

## 7. The Goodhart wall

The rubric is a target; assume everything that can optimize against it will. The wall is an information-flow contract, enforced by construction:

| Party | Sees | Never sees |
|---|---|---|
| Variant teams | their own briefs, refs, meters | the rubric, the experiment, other variants, judges |
| The proposer (`03` §3) | scored lineage, rotation-task verdicts, transcripts | **holdout tasks**, raw judge identities |
| Judges | task brief, anonymized exhibits, judged-factor instructions | team identities, costs, measured metrics, prior verdicts on the trial |
| The operator | everything | — (and is the only party who can change the rubric) |

Precedents honored: agents never set their own tripwires (`domain-model.md` §Plan — envelopes are platform-set); here, subjects never see their own scoring function, and the judges of quality are structurally ignorant of cost — a judge who knows exhibit 2 cost a tenth as much will find reasons to prefer it.

## 8. Open questions

1. **Statistical rigor** (debt LAB-D2, `06` §6). Win rates with minimum n are honest but crude; sequential testing or Elo-style ratings may earn their place once experiments run hundreds of trials. Deliberately not v1.
2. **Judge model tier.** Cheaper judges are themselves a downgrade-sweep question. Leaning: the panel's own accuracy stat (§5.4) decides — run the judge-tier experiment when the machinery exists to score it.
3. **Panel diversity.** Three identical evaluator roles vs. three lens-specialized ones (correctness-lens, maintainability-lens, adherence-lens). Lens specialization fits the formation model naturally; decide at L3 against probe accuracy.
4. **Absolute grading drift.** Median 1–5 grades drift as judges' standards shift; pairwise preference is drift-immune, which is why preference is the headline and grades are the texture. Revisit if grades start driving decisions.
