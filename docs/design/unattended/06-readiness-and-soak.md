# 06 · Readiness and Soak — proving "safe to leave" before leaving

> **Status:** Proposed 2026-08-16 · **Reads with:** `README.md`, docs 01–05 (the machinery this checks), `../../org-roadmap.md` §5 (the bar this mechanizes), `../../testing.md` (pillars; the soak joins its estate), `../../canopy-inc.md` §6 (the waves these gates guard), `../standing-orgs.md` (dry-run/check-now precedents)

## 0. The problem

The corpus defines existence as "run unattended on a cadence for a month with published numbers" — a bar with no instrument. Nothing tells the operator *before* a hands-off night that a team is ready for one, and nothing rehearses the fleet's bad days except production. Two instruments close this: a **checklist** (readiness, per team, checked like actuation readiness) and a **soak** (the fleet's month, compressed, with the bad days injected). Plus the ladder that names the postures between "watching" and "gone."

## 1. The unattended-readiness checklist (RD-1..3)

**RD-1** `POST /api/teams/{id}/unattended-check` returns issues in the actuation-readiness mold — codes, severities, fixes — and the standing-orgs create-card and team page render them. The checks, each mechanical:

| Code | Verifies |
|---|---|
| `UN_ENVELOPE_MODE` | ops envelope exists at the wave-required mode (`01` §2 OE-8), version ratified by the operator |
| `UN_SALARY_EVIDENCE` | every role has calibration evidence `n ≥ 5` — or the envelope compensates (`always` mode or auto-top-up armed) per FL-13 |
| `UN_PAGE_TESTED` | the notify seam's test fire was delivered and acknowledged within the last 30 days (`02` BR-9) |
| `UN_INTAKE_DRYRUN` | every enabled trigger has a green dry-run; every cadence a satisfiable schedule; refire policy set (`04` §2) |
| `UN_READER_GRANTS` | the reader rule holds — no unconfirmed-external-intake role carries write/execute grants (`05` TP-3) |
| `UN_TIER` | the team's grant tiers are satisfiable on its sandbox tier *without* the waiver, or the waiver posture is explicitly acknowledged for this team (W1/W2), or T2 required-and-present (W3 — `05` TP-9) |
| `UN_SUNSET` | the team's sunset/kill criteria are recorded (`canopy-inc.md` §4.8's rule, checked, not just written) |
| `UN_LATENCY_BUDGET` | `reviewLatencyBudgetH` set; brief nudge configured |
| `UN_CONTINUITY` | fleet-level, checked once: supervisor installed, last backup < 48h, credential probe green (`03`) — surfaced on every team's check because every team shares the fate |

**RD-2** Checks are advisory the way actuation readiness is — the operator can override, and the override is recorded on the team (eyes-open is a legitimate posture; silent unreadiness is not). **RD-3** The brief's anomaly section re-runs the fleet's checks daily and reports *regressions* (a team that was ready and no longer is — a lapsed page test, a stale backup — is exactly the drift that erodes hands-off safety silently).

## 2. The fleet soak (RD-4..6)

**RD-4** A compressed-clock soak in the test estate (FakeClock, `mock` + fake-CLI, the C-series/L6 pattern scaled to the fleet): the W1+W2 roster actuated together, **30 simulated days** of cadences, triggers, and engagements, with the bad days injected on schedule — adapter crash mid-turn, control-plane restart mid-everything, provider limit script exhausting a window, an `auth`-class failure day, a poisoned issue (two strikes then park), org-budget contention between two orgs, a conflicted rebase. **RD-5** Pass bar, asserted not narrated: zero un-receipted skips or silent drops; zero double-charges (`sum(SpendEvents) == sum(meter.spent)` fleet-wide); zero consequences without gates; every park carries a reason and every page class fires exactly when scripted; the brief renders every simulated morning with correct queues and honest all-clears; recovery from every injected failure without operator input except where the design says park. **RD-6** The soak is CI-runnable (nightly/slow tier) and is a *release gate for the H-series itself* — plus a one-week **live pilot** protocol: W1 teams, envelopes `always`, operator present daily, graduating postures only after the pilot's receipts are boring (`testing.md` §6's live-path discipline).

## 3. The posture ladder (RD-7)

Three named operator postures, each entered by checklist and exited by boredom — the trust ladder applied to the operator's own absence:

| Posture | What it means | Entry bar |
|---|---|---|
| **P0 — attended** | today: operator present, envelopes `always`, every gate hand-resolved | none (current state) |
| **P1 — office-hours** | fleet runs the workday unattended; operator does the daily brief; envelopes `graduated`; pages armed | per-team readiness green (RD-1); pilot week complete; page channel proven |
| **P2 — unattended-month** | the org-roadmap §5 bar: a month on cadence, numbers published, operator = brief + ratification only | P1 boring for ≥2 weeks (no page-class events except drills, latency budgets held, receipts steady); soak green on the current build |

"Check in once a day" is **P1** — a defined, checkable state, not an aspiration. **P2** is where a rung earns "exists" in the roadmap's sense, and the receipts team publishes the month as evidence. Regression is always available and cheap: any breach of the entry conditions drops the posture (auto-tighten precedent, `01` §4), receipted in the brief.

## 4. Open questions

1. Does posture live per-team or per-org? Leaning per-team with an org rollup (the weakest team defines the org's honest posture) — matches the wave structure.
2. Should the soak include a chaos-monkey mode (randomized injection order) beyond the scripted days? Scripted first — determinism is the C-series' rule; randomized soaks as a later hardening tier.
3. How much of the pilot week can the receipts team itself observe and publish (dogfooding the compass on the fleet's own bring-up)? Attractive from day one; decide at W1 founding.
