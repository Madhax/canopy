# 06 · UX — The Capacity Console

> **Status:** Proposal — portfolio-and-capacity working group, 2026-08-08
> **Reads with:** `02-capacity-model.md` (every number here is defined there), `03-provider-quota-adapters.md` (source tiers), `04-scheduling-and-throttles.md` (every control here is a knob there), `05-ux-portfolio.md`, `../../execution/operator-experience.md` §6 (cost explorer — the sibling money view)

## 1. Where capacity lives in the UI

Three altitudes, one discipline (numbers always wear source + age):

1. **Portfolio capacity strip** (`05` §2) — headline gauges, always visible at home.
2. **The capacity console** (`/capacity`) — this document: the operations room for the shared pools. Operator-level and therefore cross-org *by necessity*; every team-tagged element carries its org chip so the one deliberately mixed surface stays legible (`05` §5.5).
3. **Team-scope chips** (`05` §6) — burn and hold state where the team's own work is displayed.

The console answers, in order: *how much is left and when does it come back* (§2), *who is eating it* (§2), *what can I turn and what will turning it buy me* (§3), *what has the system already done about it* (§4), and *what should interrupt me* (§5).

## 2. Console anatomy — pools, windows, attribution

```
┌──────────────────────────────────────────────────────────────────────────┐
│ CAPACITY                                                    ⚙ accounts   │
├──────────────────────────────────────────────────────────────────────────┤
│ ▌Claude Max (patrick) · subscription                                     │
│                                                                          │
│  5-hour      ████████████░░░  82%   resets 17:40 (1h 28m)                │
│              provider-reported · 3 min ago                               │
│              runway ▸ exhausts ~16:55 at current burn  ⚠ before reset    │
│                                                                          │
│  7-day       █████░░░░░░░░░░  31%   resets Mon 09:00      3d 17h         │
│  7-day Opus  ████████░░░░░░░  56%   resets Mon 09:00                     │
│  extra usage off                                                         │
│                                                                          │
│  burn, this window (pp/hr)                                               │
│  canopy-maintenance ▉▉▉▉▉▉▉▉ 4.1   [canopy-inc]                          │
│  canopy-docs        ▉ 0.6           [canopy-inc]                         │
│  household          ▏0.2            [personal]                           │
│  external (you)     ▉▉ 1.0          outside Canopy                       │
├──────────────────────────────────────────────────────────────────────────┤
│ ▌Google AI (patrick) · subscription                                      │
│  CLI daily   ███░░░░░░░░░░░░  ~19% (287/1500) · counted locally          │
│              resets ~00:00 PT        app windows: no reading yet         │
└──────────────────────────────────────────────────────────────────────────┘
```

- **Pool cards** (`PoolCard`), one per ProviderAccount. Window rows show: gauge, utilization, `resets_at` absolute + countdown, source badge + age (§6), and — for the headline window — the **runway line**: exhaustion ETA at current total burn, with an explicit ⚠ when ETA precedes reset (the only situation where the window will actually bite). Warning watermark (`04` §8) turns the gauge amber; `exhausted` renders the reset countdown as the primary fact, because "when does it come back" is the operative question once the level is 100.
- **Attribution stack** (`BurnStack`) per pool: horizontal bars, pp/hr per team, org chips, and the **`external` band** — the operator's own non-Canopy usage, rendered in neutral gray with the label "outside Canopy". Toggle: rate (pp/hr) ↔ share-of-window-so-far (pp consumed). Clicking a team focuses its knob row (§3).
- **History drawer** (fast-follow): utilization vs. time for the window with reading markers (dots = tier-1 reads, diamonds = exhaustion events, shading = inferred spans) — the picture that teaches the operator what their day actually looks like against a 5-hour clock.

## 3. The knob panel and the what-if strip

One row per team (grouped by org, org chips throughout), directly manipulating `team_schedule` (`04` §2):

```
│ canopy-maintenance   [canopy-inc]          burn 4.1 pp/hr                │
│  state [▶ running ▾]   sessions [3 ▾]   pace [off ▾]   model [opus ▾]    │
│  priority [batch]      fallback: hold-resume → degrade                   │
│  predicted if paused: −4.1 pp/hr → runway 17:55 (past reset ✓)           │
```

- Every control renders its **predicted effect chip** before commit — the K-table's math (`04` §3) verbatim: `sessions 3→1 · −2.6 pp/hr → runway 17:31`. Predictions are labeled with confidence (derived from attribution's tier — provider-anchored vs inferred) and the console **closes the loop**: for two intervals after a knob commit, the affected row shows `predicted −2.6 · observed −2.4 ✓`, building exactly the trust the prediction model needs to be useful (and exposing it when calibration drifts).
- **The what-if strip** (`WhatIfBar`) answers the scenario question directly. The operator states a goal — "fit `household` (~6 pp) before 18:00" or picks a team to introduce — and the strip enumerates the cheapest knob combinations that satisfy it, from the same math: `pause maintenance (−4.1·2h = 8.2 pp) ✓` / `sessions 3→1 + pace 50% (−4.6·2h ≈ 9.2 pp) ✓`. Apply is one click per suggestion; nothing auto-applies. This is the "how do I know what a knob frees" requirement made into a control, not a calculation the operator performs in their head.
- Org-level knobs (shares K7, reserves K8) are *shown* here read-only with links to the org page's budget editor (`05` §4) — operations room displays governance, doesn't rewrite it.

## 4. The event feed

`CapacityFeed`, right rail: the append-only `capacity_event` stream (`02` §7) rendered as a timeline — exhaustions (`five_hour exhausted · provider signal · 3 sessions held`), holds and resumes (`canopy-maintenance resumed · window reset confirmed`), fallback engagements (`degrade-model: opus→sonnet on as_x1y2 · directive recorded`), knob commits (with actor: operator), adapter health (`usage-endpoint 429 · backing off`, `no reading 22m · levels inferred`). This is the audit trail that makes the governor's automatic actions trustworthy: nothing the ladder (`04` §5) does is invisible or unexplained. Filterable by pool, org, kind.

## 5. Alerts and thresholds

Extends the existing notification vocabulary (`engine.md` §7) with capacity kinds, honoring the house severity discipline (`attention` = blocked on *you*):

| Kind | Severity | When |
|---|---|---|
| `capacity-warning` | `warning` | window crosses warning watermark with non-trivial burn |
| `capacity-runway` | `warning` | exhaustion ETA precedes reset (the ⚠ state) |
| `capacity-exhausted` | `info` by default | window hit; holds engaged; auto-resume scheduled — the system is handling it |
| `capacity-parked` | `attention` | fallback ladder reached `park`: a team is drained awaiting you |
| `capacity-budget` | `attention` | org weekly ceiling crossed: new intents refused |
| `capacity-etiquette` | `info` | provider soft-cap advisories (session-count ceilings; sustained throttling) |

Deliberate choice: **exhaustion is not an emergency.** The default posture treats window exhaustion as scheduled weather the governor already dressed for; only *parked work* and *refused intents* claim `attention`. Operators who want louder behavior flip per-kind severity in settings — the discipline (`04` §4, F4's lesson about gate prominence) is the default, not a cage.

## 6. Honesty rules (the capacity analog of `fmtCostHonest`)

1. Every displayed level carries **source badge + age**: `provider-reported · 3 min`, `event-anchored · 41 min`, `~ counted locally`, `~ inferred since 16:05`. Tier vocabulary from `02` §4; badges are the same component everywhere (strip, console, team chips).
2. **Inferred numbers wear `~` and never render in the confident weight.** A gauge with only tier-3 backing draws hollow.
3. **Unknown beats fabricated.** A window with no reading renders `no reading yet` — never 0%, never a guess. Google app windows will spend their life here until an event arrives; that is correct (`03` §3).
4. **Predictions show their error afterwards** (§3's closed loop). A prediction that missed by >30% twice demotes its confidence label until recalibrated.
5. **Money is money.** Extra-usage burn renders as dollars in cost surfaces, never as "free subscription tokens"; the `claude-extra` provider tag keeps it separable forever.
6. **The provider's clock wins.** All resets display provider timestamps (with local conversion), never Canopy's arithmetic — when we don't know, we say `reset unknown · resolves on next successful call` (`04` §4).

## 7. Degraded states

- **Observed-only mode** (default Anthropic posture, `03` §2 S4 off): gauges show event-anchored/inferred levels with prominent anchor age; a passive banner on the pool card — `levels inferred between provider signals · enable richer reads in settings` — links to the account settings where S3 (statusline tap) and S4 (usage endpoint, with its compliance paragraph) are offered. The console must be *useful, not nagging*, in this mode: runway, attribution shares, knobs, and holds all function identically; only level precision differs.
- **Adapter dark** (nothing for > TTL): gauge grays, `no signal 34m`; admission unaffected (`04` §7); feed entry records the gap.
- **Mock pools** (CI/demo): rendered identically with a `mock` badge — the console is fully demonstrable keyless, per pillar and per the e2e plan (`07` §6).

## 8. Component inventory and routes

Route `/capacity` (portfolio-level; `/orgs/:id/capacity` renders the same console filtered to the org's teams with shared pools still visible — filtered, not falsified). Components: `CapacityConsole`, `PoolCard`, `WindowGauge` (+`SourceBadge`, `RunwayLine`), `BurnStack`, `KnobPanel`/`KnobRow` (+`PredictionChip`), `WhatIfBar`, `CapacityFeed`, `AccountSettings` (ProviderAccount CRUD + source opt-ins), `useCapacity` (one aggregate: `GET /api/capacity`), `useCapacityEvents` (SSE tag). Data contract is exactly `02` §7's derived aggregate; the console holds no math of its own — predictions come computed, so UI and scheduler can never disagree about what a knob will do.

## 9. MVP cut

C3 ships: pool cards with window gauges, source badges, runway, attribution stack with `external`, event feed, alerts. C4 ships: knob panel with predictions and the closed loop. C5 ships: what-if strip, history drawer, `/orgs/:id/capacity` filter. Explicitly later: multi-account comparison views, calendar/heatmap of window usage patterns, and any automation that *applies* knobs without a click — the governor acts on exhaustion (that's policy the operator wrote), but proactive optimization stays human-in-the-loop until the prediction loop has earned trust.
