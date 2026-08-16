# 03 · Fleet Glance — health, status, and burn for many teams at once

> **Status:** Proposed 2026-08-16 · **Reads with:** `README.md` P3, `../organizations/05-ux-portfolio.md` (the home this sharpens) + `02-capacity-model.md` §5 (attribution — the burn numbers), `../unattended/01-operations-envelope.md` (park states) + `06-readiness-and-soak.md` (postures), `../../canopy-inc.md` §2 P2

## 0. The problem

Managing many teams currently means assembling health by eye from lists, pulses, and the capacity console. The fleet altitude needs an **opinionated health model**: the platform commits to one status word per team, derived from signals it already has — because an operator who must derive health themselves will either over-check (attention burn) or under-check (silent rot).

## 1. The health model

**UX-20** A closed status taxonomy, derived server-side, precedence-ordered (first match wins):

| Status | Meaning (derived from) | Color class |
|---|---|---|
| `needs-you (n)` | operator-owned gates open (count) | attention |
| `stuck` | stall trigger fired, or parked past its latency budget, or refire-strikes | attention |
| `working` | ≥1 assignment executing; steps flowing | ok |
| `waiting — capacity` | held by the governor (window/reset shown) | info — *scheduled waiting, pages nobody* |
| `waiting — dependency` | gated on verify/consume edges | info |
| `scheduled` | idle now, next cadence/trigger window shown | info |
| `idle` | actuated, nothing queued, nothing scheduled | neutral |
| `off` | not actuated | neutral |

**UX-21** Every status carries its **reason phrase** ("waiting — 5h window resets 14:20") — the word is never shown without its why. **UX-22** `stuck` is the load-bearing distinction: *quiet-because-waiting* vs *quiet-because-broken* must never share a rendering (the single most trust-destroying confusion a fleet view can commit).

## 2. The team card

**UX-23** One card per team, the glance grammar exactly (`README` P3):

> **avatar+name** · status word + reason · current engagement one-liner (or standing purpose when idle) · **last product** (receipt-card smallest form: kind + age) · **burn chip** · needs-you badge (only when > 0)

**UX-24 — The burn chip answers "should I see tokens per team": yes, as share and trend, not as raw tokens.** The chip renders: % of the org's current window attributable to this team (the C-series attribution, live) + a 24h sparkline + est. cost/day in USD. Raw token counts are forensic. Rationale: raw tokens are unactionable at a glance; *share* tells the operator who is eating the subscription, *trend* tells them whether it's new, *cost/day* prices it — three actionable readings in one chip, all already computed by the capacity ledger.

## 3. The org rollup (Home header)

**UX-25** Per organization: status counts ("6 working · 2 waiting · 1 needs-you"), the weekly budget bar (spend vs ceiling, warn at 80% — admission semantics annotated), runway (source-tiered + age, per honesty rules), posture chip (P0/P1/P2, `../unattended/06`), and the needs-you total that links straight into the brief. **UX-26** Sort order *is* the priority order: needs-you → stuck → working → waiting → scheduled → idle → off; within a class, oldest-untouched first. The board reads top-left = worst. **UX-27** Fleet surfaces run on SSE, not polling — the 5s-poll console (CAP-D7) upgrades in the same milestone; a fleet view that lags its fleet teaches the operator to distrust it.

## 4. Health integrity

**UX-28** The status word is computed from the same records the brief and receipts read — never a second opinion. A team `working` on Home is `working` in the brief's context lines and in the receipts' day narrative; disagreement is a bug with a test. **UX-29** Health *regressions* (ready→unready, working→stuck, posture drops) emit the standard anomaly into the brief (RD-3) — the fleet view and the brief are two renderings of one truth.

## 5. Open questions

1. Card grid vs. dense rows for >10 teams? Both, a toggle — rows for scanning, cards for the wall-display posture. Decide with real fleet size at W2.
2. Does the seat-level (per-agent) row belong on Home at all, or only inside the team page? Leaning team-page-only — Home's unit is the team; the screenshot's flat session list is exactly what we're not doing.
3. Org-of-orgs (multiple Organizations) rollup ordering — by worst status or by budget share? Worst-first, consistent with UX-26.
