# 04 · UX — The Experiment Bench (authoring and configuration)

> **Status:** Proposal — experiments working group, 2026-08-10
> **Reads with:** `01`–`03` (this series), `../organizations/05-ux-portfolio.md` (IA rules, ScopeBar, org theming), `../connectors/04-operations.md` (the five-minute-path discipline this doc inherits), `../../execution/operator-experience.md`

## 1. Where the lab lives

The portfolio IA (`../organizations/05` §1) gains one org-scoped section — **Lab** — beside Teams on the organization page. Scope rules unchanged: the lab is a *place inside an organization*, wearing its theme; there is no cross-org lab view (invariant 12 applies to experiments like everything else — only the operator bridges).

| Route | Surface |
|---|---|
| `/orgs/:orgId/lab` | Lab home — experiment cards |
| `/orgs/:orgId/lab/new` | Create flow (§2) |
| `/lab/:expKey` | Experiment page — the observatory (`05`) |
| `/lab/:expKey/rubric` | Rubric editor (§3) |
| `/lab/:expKey/tasks` | Task manager (§4) |
| `/lab/:expKey/variants/new` | Variant composer (§5) |
| `/lab/:expKey/trials/:trialId` | Trial comparison page (`05` §2) |

**Lab home** — one card per experiment: state chip, purpose line, champion chip with tenure ("champion: B1 · 12 days"), trials-run count, spend vs. ceiling bar, evaluation-overhead %, and an attention chip when something needs the operator (`champion-suggested`, `panel-split`, audit queue, holdout pool low). Concluded experiments recede below running ones with their final receipt line.

## 2. The create flow

Five steps, each skippable to defaults — the connectors series' governing test applies: **the common case is a template, not a form.** An operator who picks a team and accepts defaults gets a running manual A/B against the solo baseline in under five minutes; every advanced control lives behind its step's "advanced" line.

1. **Purpose.** One sentence (it becomes the card line) + the experiment key.
2. **Seed and baseline.** Pick the seed variant: an existing Team (snapshot, `01` §3) or a formation stamped fresh. The **solo baseline toggle is on by default**, pre-picked to the seed's primary production role — turning it off is a deliberate act (it is the PF-1 control group). Preview both charts side by side.
3. **Tasks.** Enable sources (curated / replay / generated). The replay importer opens the org's closed-intent picker immediately so the operator leaves this step with a real pool, not an empty promise. Holdout percentage (default 25%) shown as a concrete consequence: "5 of your 20 tasks will be reserved for promotion checks."
4. **Rubric.** Starts from a domain template (`software-delivery` shipped first; templates are catalog data, `02` §2). The template is shown *as its consequences*: the factor list with weights, floors, and panel config — not a blank matrix. Edits here create v1; the full editor (§3) is one click away.
5. **Policy, envelope, budget.** Policy defaults `manual` (L1) or `champion-challenger` with the model-downgrade sweep once generators exist; envelope pre-filled from the seed (its roles, its node count +2, its model tier and below); budget ceiling with a projected-trials hint ("≈ $25 ≙ roughly 20 trials at this team's historical cost per intent").

## 3. The rubric editor

The surface where "engineers modify the factors" lives. Anatomy:

- **Factor table** — one row per factor: key, source badge (measured ⚙ / programmatic ▣ / judged ◉), weight slider with live re-normalization (weights always display as a share of 100), direction, floor editor (`non-inferior to champion, margin 0%`), and for judged factors an instructions editor (plain text, versioned with the rubric). Adding a factor offers the catalog vocabulary (`02` §2) plus "new judged factor" (free) and "new probe" (shows what exists in the probe registry; a missing probe is a named gap, not a silent zero).
- **Judging panel config** — mode (pairwise-blind), panel size, aggregation, `humanAuditPct`, `showReference`. Beside it, the **calibration strip**: panel-vs-ground-truth accuracy from probe trials and panel-vs-human agreement from audits, each with n ("agrees with you 87% · n 23"). This is the closed loop that tells the operator whether their judges deserve their weight.
- **Promotion predicate** — minScoredTrials / minWinRate / holdout requirements, rendered as a sentence: *"A challenger is suggested when it wins ≥60% of ≥5 scored trials with all floors held, then confirms on ≥3 holdout tasks."*
- **Version rail** — every version listed with author, date, and a diff chip ("v3: cost 20→15, added floor on solution-quality"). Activating an edit creates the next version; a **re-score** action re-runs past trials under the selected version with explicit consequence copy ("creates a parallel verdict set; the leaderboard will show which version ranks it; nothing is overwritten") — per `02` §3, silent re-scoring does not exist.
- **Advisory lint, never blocking:** "`correctness` has no floor", "economics outweigh quality factors", "panel of 1 — no majority possible", "operator-load weighted high: this can teach guessing (`02` §2)". The operator's weights are the operator's; the lint exists so a foot-gun is loaded knowingly.

## 4. The task manager

- **Pool table** — origin badge, tags, state, holdout lock. Holdout rows show title and tags but **mask the body** outside this surface's explicit reveal (the redaction is the visible form of the `02` §7 wall; the audit log records reveals).
- **Replay importer** — the org's closed intents, filterable by team/tag/date, each row showing historical cost and outcome. Import copies text + pins `baseRef` (`01` §4).
- **Generated queue** — task-author proposals awaiting review, batch approve/reject, each with the author's stated coverage rationale ("varies the CSV edge-cases axis"). Rejection with note feeds the author's next batch (a stock rework loop).
- **Pool health strip** — rotation-pool size vs. the noise threshold (`01` §10.4), holdout remaining, tag balance. "Holdout pool low (1 left): promotions will block" is a bench warning, not a mid-promotion surprise.

## 5. The variant composer

Manual challenger authoring, built on the existing chart editor in read-annotate mode:

- **Start from parent** — pick any lineage node; the composer opens the parent's chart with a **mutation picker**: rebind model (per node, tier dropdown), swap role, add/remove node, resize salary, edit extensions, reparent. Each edit is recorded as *the* mutation; a second edit flips the variant to `manual` with a nudge ("two changes = ambiguous attribution — consider two variants").
- **Diff overlay** — the parent-diff rendered on the chart: added nodes in sprout green, removed as gray stumps, rebound models as a chip on the node, salary changes as ±%. The same overlay renders on variant pages (`05` §3) — authoring and reviewing share one visual language.
- **Envelope validation inline** — out-of-envelope edits are allowed but flagged at the field: *"outside envelope (role not allowed): enrolling will open an approval."* The composer never silently widens the envelope.
- **Enroll** — names the variant (B-next by default), snapshots, and schedules its first trial (or its approval gate).

## 6. Configuration honesty rules

The bench inherits the house discipline (`../organizations/06` §6 ethos), applied to authoring:

1. Every default shown with its consequence, in units the operator has ("≈ 20 trials", "5 tasks reserved"), never as a bare number.
2. Every wall the config creates is *visible in the config*: holdout masking, envelope boundaries, the baseline toggle's PF-1 role.
3. Lint advises, gates govern: nothing in the bench blocks on taste; the only hard stops are structural (no seed team, empty task pool, guardrail-free rubric).
4. Anything the lab's agents will do on the operator's behalf (generate tasks, judge, propose) is previewed at configuration time as *who* does it and *what it costs* — the lab is staff, and staff appears on the payroll the operator just configured.

## 7. Components

`LabHome`, `ExperimentCard`, `CreateExperimentFlow` (5 steps), `RubricEditor` (`FactorTable`, `JudgingConfig`, `CalibrationStrip`, `PromotionEditor`, `VersionRail`), `TaskManager` (`ReplayImporter`, `GeneratedQueue`, `PoolHealthStrip`), `VariantComposer` (`MutationPicker`, `ChartDiffOverlay`), `EnvelopeEditor`. Data via `useExperiment(expKey)` on `GET /api/experiments/{id}` and mutations per `06` §3; live updates ride the org-tagged SSE stream with `experiment` events.
