# 05 · UX — The Observatory (leaderboard, lineage, trials, verdicts)

> **Status:** Adopted 2026-08-09 (operator decision) — proposed by the experiments working group
> **Reads with:** `01`–`04` (this series), `../organizations/06-ux-capacity.md` (the honesty-rule pattern), `../../execution/operator-experience.md` (inspector reuse), `../../actuation/phase3-debts.md` F4/F5/F15 (the attention lessons this doc inherits)

The observatory answers, in order: **who is winning and by how much · what have we tried · what does any single comparison actually look like · what needs me · what did this all cost.** It is a read-and-govern surface: everything renders from the experiment record; the only writes are verdicts, overrides, and governance actions.

## 1. The experiment page

**Header strip** — state, champion chip (key, tenure, composite), trials scored / voided, spend vs. ceiling, **evaluation overhead %** (judge+author spend ÷ variant spend — the lab's own SC-1 stat, always visible), and the attention chip.

**Leaderboard** — one row per variant:

| Column | Content |
|---|---|
| Variant | key, label, status chip (champion ★ / active / retired / graduated), structure stat line ("4 nodes · depth 2 · 1 mgr") |
| Composite | mean composite with rubric badge (`v1`) and evidence chips: source-tier glyphs + n ("0.61 · v1 · ◉ panel · n 9") |
| Win rate | paired wins vs. champion, always with n ("7/9"); an **"insufficient trials"** state below the minimum, never a premature rank |
| Factors | per-factor mini-bars with source glyphs; floor breaches as a red underline with count |
| Δ cost | vs. champion, cache-aware USD ("−38%") |
| Prediction | for generated variants: predicted vs. observed ("predicted −35–45% · observed −38% ✓") — the proposer's and sweeps' closed loop |

A **tag-slice control** re-computes the board per task tag (`trivial`, `gnarly`…) — where the solo baseline wins its slice, that fact is one click deep, not buried. Retired variants collapse below the fold with their retirement reason ("floor breach ×2: correctness").

**Lineage tree** — the second chart. Variants as nodes (colored by composite, champion path bold, current champion ringed), edges labeled with their mutation ("−triager", "be→sonnet"). Pruned branches gray but present. Click-through to variant pages. This view *is* the "list of structures and their scores after 100 iterations" — shaped as ancestry, because that is what makes it navigable.

**Trial feed** — append-only: scored trials with one-line outcomes, voids with reasons, promotions, retirements, envelope edits, rubric bumps — every entry an actor and a timestamp. The experiment's receipts.

## 2. The trial page — one comparison, fully honest

- **Exhibits side by side** — both deliverables rendered (markdown, diffs), labeled by variant *for the operator*, with an **"as judges saw it"** toggle that re-anonymizes and re-shuffles — the operator can verify the blindfold.
- **Scorecard** — per factor: both values, source badge, and for judged factors the panel's grades with spread. Floor checks rendered as pass/fail lines, not numbers.
- **Judge cards** — per panel member: preference, grades, rationale (expandable), and what the judging cost. Split panels flagged. Every judge card links to the full judging assignment in the standard inspector — judge reasoning is inspectable work, not an oracle.
- **Run drill-down** — each run links to the stock intent detail: living plan, steps, gates, meter history. The trial page adds *comparison*; it never re-implements inspection.
- **Metrics panel** — cost breakdown (four token components, per F1), timeline with gate-wait and capacity-hold shading (the visual form of the active-vs-elapsed rule), rework and operator-load counts.
- **The human verdict control** — "Record your verdict": preference and/or per-factor grades plus a note. Recording one supersedes the panel verdict (tier rule, `02` §1), recomputes the leaderboard, updates the calibration stat, and **preserves the superseded verdict struck-through in place** — overruling is a recorded act, never an erasure.

## 3. The variant page

Chart snapshot with the parent-diff overlay (`04` §5's shared language) · mutation and provenance line ("proposed by sweep:model-downgrade · predicted −35–45%") · score history sparkline across trials · per-tag strengths · trial list · guardrail findings if any. Actions: **retire**, **clone to compose**, and **promote**.

**Promote** is the series' one production door (`03` §7): the flow previews exactly what changes on the target production team (the same diff overlay, now against the *production* chart), states what carries (blueprint, bindings, salaries) and what does not (variant memory — production keeps its own), then opens the ApprovalGate. Ratification stamps the variant `graduated`, applies the blueprint (deactuate → apply → re-actuate, v1 semantics), and drops a receipt in the org feed: *"B1 promoted to canopy-maintenance: −38% cost, quality held, 12 trials · rubric v1."* Reinstating a former champion is the same flow from its variant page.

## 4. Attention and notifications

Severity discipline per the house rule — the badge never cries wolf, and F4/F5's lessons (the org's one urgent thing must be unmissable; internal wiring must not read as operator work) apply verbatim:

| Kind | Severity | When |
|---|---|---|
| `champion-suggested` | **attention** | promotion predicate + holdout confirmed — an action card with the one-click path to the promote flow |
| `panel-split` / audit due | **attention** | judgment needs a human — the audit queue surfaces on the experiment page |
| `experiment-budget` | warning → attention | ceiling approach / crossed (admission stops) |
| `floor-breach` retirement, trial `void` | info | governance already acted; the feed records it |
| `trial-scored`, sweep frontier found | info | progress, not interrupts |

Trials' *internal* gates (a variant's own clarifications, dependency waits) never surface in the operator's org inbox — they are the variant team's affairs, visible on drill-down only. The experiment's asks of the operator are exactly: audits, out-of-envelope approvals, promotions, budget. Nothing else pages.

## 5. Portfolio integration

The org page's Lab section (`04` §1) rolls up: running experiments with champion chips and attention state. The org section on the portfolio home gains at most **one** lab line ("`ex-maint` · champion B1 ↑ · 1 needs you") — the home stays a glance, per the portfolio rules. Variant teams stay out of the Teams grid (they carry `experimentId`; a "show lab teams" toggle exists for the operator who wants to watch one work — it opens the standard team operate surface, read-only conventions unchanged). Promotions and concluded-experiment results land in the org's receipts feed — the lab's output is receipts, in the org-roadmap's sense.

## 6. Honesty rules

The capacity console's discipline, applied to scores:

1. **No naked numbers.** Every composite, win rate, and grade wears its rubric version, its source tier glyph, and its n. A score that lost its provenance is not rendered.
2. **Insufficient beats premature.** Below minimum n: "insufficient trials (3/5)", never a rank. `consistency` suppressed below its n. A leaderboard with one scored trial says so.
3. **Blind means verifiable.** The "as judges saw it" toggle exists so blinding is a checkable claim, and the known limits of anonymization (`02` §5.1) are stated in the UI ("content may carry stylistic tells"), not hidden.
4. **Voids are visible.** Voided trials render struck in the feed with reasons; a variant's record states scored / voided counts side by side.
5. **Superseded verdicts remain.** Human overrides strike through, never delete (§2).
6. **Predictions meet observations.** Wherever a generator claimed an effect, the observed effect renders beside it — the proposer earns trust the way knob chips do, or visibly fails to.
7. **The lab pays its way in public.** Evaluation overhead % on the header, judge costs on judge cards, the lab team on the org payroll. If judging costs more than the work it judges, the header says so before the operator's invoice does.

## 7. Components and data

`ExperimentPage` (`HeaderStrip`, `Leaderboard`, `LineageTree`, `TrialFeed`), `TrialPage` (`ExhibitPane` ×2, `Scorecard`, `JudgeCard`, `RunTimeline`, `HumanVerdictControl`), `VariantPage` (`ChartDiffOverlay`, `ScoreSparkline`, `PromoteFlow`), `AuditQueue`. Data: `GET /api/experiments/{id}` aggregate + `GET /api/experiments/{id}/leaderboard|lineage|trials` (`06` §3); no scoring math in the UI bundle — composites, win rates, and predicate states arrive computed, so the observatory and the harness cannot disagree (the `useCapacity` rule, applied here).
