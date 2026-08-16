# 07 · Selection and Evidence — from comparing variants to choosing teams

> **Status:** Proposed 2026-08-16 (drafted in operator session) — adoption is the operator's call, like the rest of the series
> **Reads with:** `README.md` (the non-goal boundary this doc half-lifts), `01-experiment-model.md` (trials as blocks), `02-rubric-and-judging.md` (floors, tiers), `03-search-and-iteration.md` (generators — this doc adds one; §8's "deliberately not designed here" — this doc designs the safe half), `../../canopy-inc.md` §7 (frontier and forge as the named customers), `../organizations/02-capacity-model.md` §4 (the tier-of-truth pattern reused for evidence), `../../risks/problem-fit.md` (PF-2 — this is its formation-level form)
> **Sequencing:** milestone **L7**, after L5 (needs the mutation vocabulary and tags); the evidence harvest can backfill from every trial scored since L1.

## 0. The question this adds

The series as adopted answers **comparison**: given a standing team, a task corpus, and a challenger, is the challenger better? The operator's recurring question is prior to that — **selection**: *which formation should fulfill this intent?* It is asked at team creation (the wizard's formation cards), at intent submission ("is this team the right shape for this ask?"), and by `canopy-frontier` and `canopy-forge` whenever they design or tune a team. Today the answer comes from catalog beliefs — hand-authored formations with no evidence attached.

The full pipeline is **beliefs → evidence → defaults**: the catalog states beliefs; the bench (01–06) produces evidence; selection turns evidence into defaults-with-provenance. This doc designs the third stage and upgrades the second to feed it. It deliberately does *not* design live routing of production intents (§5).

## 1. Why the lineage cannot answer selection

Champion–challenger over a one-mutation lineage is **one-factor-at-a-time search**. That is the right shape for attribution ("B4 differs from B1 by exactly this") but the wrong shape for selection, three ways:

1. **Its unit of evidence doesn't transfer.** "B1 beat A on `ex-maint`'s twenty tasks" is a fact about two frozen blueprints and one corpus. A fresh docs team can inherit nothing from it. What transfers is the **factor**: *a verify edge on the reviewer seat*, *a model tier on an engineer-class role*, *a manager layer at width four* — structural choices whose effects can be estimated across teams, conditional on the work.
2. **It is blind to interactions.** One mutation at a time never observes that the cheap model tier is fine *with* a verify edge and disastrous without one — precisely the kind of fact selection needs, and the textbook argument against OFAT experimentation.
3. **It is greedy and local.** Hill-climbing from the incumbent explores the incumbent's neighborhood. Selection needs coverage of the formation space, however coarse.

## 2. Design of experiments, applied

Classical DOE maps onto the bench with almost no new machinery, because `01` §6 already built the hard parts: **blocking** (every trial is a paired comparison on the same task — a randomized block), **nuisance recording** (capacity snapshots), and **honest units** (paired win rates with n). Three additions complete it:

**Factors (data, not code).** The mutation vocabulary (`03` §2) re-read as a factor space. The catalog gains `factors[]`: each factor a key, a kind, and an ordered set of levels, with mutations mapped to level changes:

| Factor (v1 candidates) | Levels (example) | Kind |
|---|---|---|
| `verify.review` | absent · verify-edge | topology |
| `depth` | flat · one-manager | topology |
| `width.production` | 1 · 2 · 3 ICs | topology |
| `tier.production` / `tier.manager` | fable · sonnet · haiku | binding |
| `salary.class` | trim · default · generous | economics |
| `memory` | fresh · carry | policy |

Five to seven factors, deliberately coarse — v1's job is main effects and a few two-factor interactions, not a response surface. The factor vocabulary is catalog data; extending it is a forge proposal like any catalog change.

**Campaigns (a generator peer).** A new generator beside the sweeps (`03` §3): `campaign:<key>` takes chosen factors × levels and emits a **fractional-factorial batch** of variants — a design matrix, recorded on each variant as `mutation.kind: "campaign-cell"` with the full level assignment (the sanctioned multi-mutation exception to `01` §3's convention, since the design matrix *is* the attribution). A 2×2×2 campaign at half fraction is four variants; with the solo baseline and champion, six teams over an eight-task rotation is a weekend of batch capacity, and it estimates three main effects and the interactions a lineage would never see. Campaigns run inside the envelope like sweeps; out-of-envelope cells open the standard gate; the champion still changes only through governed promotion — a campaign produces *knowledge*, not a coup.

**Staged fidelity (racing).** Evaluation overhead is the binding cost (LAB-D4), so campaigns screen before they judge: every cell runs guardrails + measured + programmatic factors first (free — the records exist anyway); only cells surviving floors advance to judged panels; successive halving drops dominated cells at each round. Sequential allocation is confined to *within a campaign's fixed cells* — open-ended bandit search over the variant space stays out (`README` non-goals), because a fixed design is auditable and a bandit's regret curve is not a lineage.

**Stratification.** Effects are estimated **per task stratum** (L4's tags, graduated from display slices to first-class covariates): `verify.review: +quality on gnarly (n 11), Δ≈0 on trivial (n 9)` is the selection-relevant shape of truth. v1 keeps a small controlled stratum vocabulary (`size:{trivial|standard|gnarly}` · `kind:{bug|feature|docs|design|analysis}` · `checkable:{probe|judged}`) rather than freeform tags; freeform tags remain for display.

## 3. The evidence store

A new read-model, `experiment_effect` — recomputed from scored trials, never hand-written:

```jsonc
{
  "factorKey": "tier.production", "from": "fable", "to": "sonnet",
  "stratum": {"kind": "bug", "size": "gnarly", "checkable": "probe"},
  "pairedWinRate": 0.42, "medianCompositeDelta": -0.06,
  "floorBreaches": 1, "n": 12,
  "tier": "bench",                    // belief | bench | production   (§4)
  "provenance": {"experiments": ["ex_…"], "rubricVersions": [1,2],
                  "modelSnapshot": "2026-08", "asOf": "…"}
}
```

Rules, in the capacity console's honesty tradition: evidence is **descriptive and conditional** — paired effects under stated strata, never causal claims beyond the design; every displayed effect wears its **n, tier, and provenance**; effects **pool across experiments only within the owning Organization** and only where strata match (invariant 12 — evidence is org state); and effects **expire from recommendation** when their model snapshot is superseded (a Fable-era effect is history, not guidance — staleness is shown, not hidden). Publishing an org's evidence into the shared catalog — Canopy Inc.'s bench results shipping as everyone's formation defaults — is a deliberate **release act by the operator**, the formation-level answer to PF-2.

## 4. The selection surface

Where evidence meets choice — three surfaces, all advisory:

- **The wizard.** Formation cards carry **evidence chips**: `verify edge: quality +, gnarly work · n 14` with a provenance popover; card order becomes evidence-informed where evidence exists. Where it doesn't, cards say so: `catalog belief — no bench evidence yet`. The tier ladder is `belief < bench < production` (production = receipts from standing teams running that shape — the strongest and cheapest evidence of all, harvested from `canopy-receipts`' corpus rather than from trials).
- **Intent submission.** When an intent's inferred stratum has evidence contradicting the receiving team's shape ("gnarly-class ask; this team runs without a verify edge; bench says that costs quality"), a passive advisory chip appears. **Never a block, never a reroute** — the operator outranks the store.
- **The org's own designers.** `canopy-frontier` cites effects in design docs; `canopy-forge` consumes the **thin-evidence report** — strata the org works weekly that lack evidence (`n < 8`) — as its campaign queue. That is the active-learning loop stated qualitatively: run next the campaign whose answer would most change a default, and let the operator ratify the spend like any experiment.

## 5. The boundary: selection is never exploration on live work

The tempting general solution — contextual bandits routing production intents across candidate formations, learning online — is **rejected**, not deferred, for production traffic. Canopy Inc.'s own operating principle (`../../canopy-inc.md` §2 P3) is the reason: *work products are never experiments.* A live intent dispatched by an exploration policy is an experiment run on someone's real ask, with regret paid in real consequences. Exploration lives in the lab (replayed and generated tasks; someday shadow mode, `01` §10.1 — explore in shadow, exploit in production); production selection is always **exploitation of ratified evidence plus the operator's judgment**. Routing across specialized *champions* on stratum evidence remains the separate dispatch-policy design `03` §8 named — this doc supplies the evidence layer it would consume, and stops there.

## 6. Milestone L7

| # | Name | Ships | Done means |
|---|---|---|---|
| **L7** | Selection & evidence | catalog `factors[]` + stratum vocabulary; `campaign:<key>` generator with design matrices + `campaign-cell` mutations; staged-fidelity trial scheduling (screen → judge, successive halving); `experiment_effect` read-model + recompute + queries; wizard evidence chips + tier/provenance popovers; intent-page advisory chip; thin-evidence report | a 3-factor half-fraction campaign on `mock` over 8 tasks yields effect rows matching golden vectors (design matrix → paired effects → strata); chips render with n/tier/staleness; adversarial: no selection surface can dispatch, block, or reroute an intent; effects never pool across orgs; superseded-model effects excluded from recommendation queries |

## 7. Debts this doc knowingly opens

- **LAB-D6 — transfer validity.** Evidence from one repo, one domain, one era generalizes imperfectly; strata and staleness scope it, but a chip can still mislead. Mitigation: provenance is one click away, production-tier evidence outranks bench, and the wizard's language is advisory ("bench says", never "best"). Sunset: never fully — honesty forever.
- **LAB-D7 — evidence staleness.** Model updates under the fleet invalidate old effects. Mechanized: effects carry `modelSnapshot`; recommendation queries exclude superseded snapshots; the report nags to re-run load-bearing campaigns after a model change.
- **LAB-D8 — stratum inference.** Someone must tag intents with strata for the advisory surface; auto-inference is a judged call with its own error rate. v1: inferred, displayed, operator-correctable; the correction stream is the calibration data.

## 8. Resolved decisions and open questions

**Resolved here:** the transferable unit of evidence is the factor, not the variant; campaigns are a generator peer inside the existing envelope/governance, not a new authority; selection surfaces are advisory-only, with the operator's choice as the decision; evidence is org-scoped with catalog publication as a governed release; racing is bounded to fixed campaign cells.

**Open:** (1) the v1 factor list — which five earn a slot first (leaning: `verify.review`, `depth`, `tier.production`, `salary.class`, `width.production`); (2) whether production receipts and bench trials share one effect schema or two joined views (leaning: one schema, `tier` distinguishes); (3) minimum campaign size before effects publish to chips (leaning: reuse `n ≥ 8` per stratum, the pool-health threshold); (4) how the intent-page stratum inference composes with `canopy-intake`'s classification — the same judgment, one owner wanted.
