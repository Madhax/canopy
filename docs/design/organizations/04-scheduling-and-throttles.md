# 04 · Scheduling and Throttles — the governor

> **Status:** Adopted 2026-08-09 (operator decision) — proposed by the portfolio-and-capacity working group, 2026-08-08
> **Reads with:** `02-capacity-model.md` (state it consumes), `03-provider-quota-adapters.md` (signals), `../../execution/engine.md` §3 (gates), `../../execution/cli-runtime.md` §5–6 (turn boundary, kill+resume), `../../risks/scalability.md` (SC-4, SC-5), `../../actuation/phase3-debts.md` (F13)

## 1. What exists today (and what is genuinely missing)

Concurrency already *happens*: the delivery, trigger, and cadence loops iterate every live actuation, so two actuated teams run side by side now. Three governance pieces exist in embryo: per-provider gateway semaphores (`[gateway.concurrency]`) cap api-key parallelism; the assignment meter gates every turn on *budget*; and the kill-at-turn-boundary + `claude --resume` machinery (F13) means any session can be suspended cheaply and continued later. What is missing is everything above that: nothing decides *whether a team should be running right now*, nothing paces a hot team, nothing knows a provider window exists, and when a limit hits, the session dies into a retry loop that reads as a stall (F11's cousin at the fleet level). The governor closes exactly that gap — as *admission and pacing* control at boundaries Canopy already owns, never as mid-turn interference.

## 2. The scheduler

A new control-plane module (`scheduler.py`) with one row per team:

```jsonc
// table: team_schedule
{
  "teamId": "t_…",
  "runState": "running",          // running | paused | drain
  "maxConcurrentSessions": 3,      // K2 — admission cap across the team's nodes
  "paceChunkTurns": null,          // K3 — chunk size; null = unpaced
  "paceInterChunkDelayS": null,    // K3 — cool-down between chunks
  "modelTierCap": null,            // K4 — e.g. "sonnet": profiles above the cap are downshifted
  "priority": "batch",             // K5 — interactive | batch  (default from org.priorityClass)
  "activeHours": null,             // K6 — cron-style windows, e.g. "22:00-06:00 daily"
  "fallbackPolicy": ["hold-resume", "degrade-model"],   // §5, ordered
  "updatedAt": "…"
}
```

**Run states.** `running` — normal. `paused` — no new sessions admitted, live sessions suspended at the next turn boundary (their assignments hold behind a capacity gate, §4; work state is preserved; resume is instant). `drain` — live sessions finish their current assignment; nothing new starts. Pausing is always safe by construction because suspension reuses the gate + `--resume` machinery: **a paused team is a set of suspended conversations, not lost work.**

**Admission points** — the scheduler is consulted at exactly three boundaries, all already server-owned:

1. **Session spawn** — `GET /dp/assignment/current` returns `hold` (with reason) instead of work when: team not `running`, team at `maxConcurrentSessions`, outside `activeHours`, watermark/share says no (§7), or the profile's pool window is `exhausted` with no fallback rung available.
2. **Turn/chunk boundary** — the existing per-turn meter check grows a capacity check; the cli adapter ends the chunk (kill at event boundary, F13-style) instead of starting a turn the pool cannot afford.
3. **Intent admission** — org weekly ceiling (`01` §6) and a courtesy runway check ("this window exhausts in 20 min; queue anyway?") at `POST /api/teams/{id}/intents`.

## 3. The knob inventory

Every knob states its mechanism, where it acts, how fast it takes effect, and how its predicted effect is computed (all predictions in pp/hr per window, from the attribution model, `02` §5). This table is the contract the capacity console renders (`06` §3).

| # | Knob | Scope | Mechanism | Effect latency | Predicted effect |
|---|---|---|---|---|---|
| K1 | Run state (`running`/`paused`/`drain`) | team | admission + suspend at turn boundary | ≤ 1 turn | −(team's whole burn): the attribution stack's own number |
| K2 | `maxConcurrentSessions` | team | spawn admission | next spawn/finish | −burn × (removed sessions ÷ active sessions), shown as a range |
| K3 | Pacing (`paceChunkTurns` + `paceInterChunkDelayS`) | team | session runs in `--max-turns`-sized chunks; adapter sleeps between chunk and `--resume` | ≤ 1 chunk | −burn × (delay ÷ (chunk-duration + delay)); duty-cycle math, honest error bars |
| K4 | `modelTierCap` | team | profile downshift at next session/chunk start | next chunk | moves burn *between* windows (Opus→overall): shown per-window, e.g. "−1.9 pp/hr `seven_day_opus`, +0.4 `five_hour`-equivalent" |
| K5 | `priority` (`interactive`/`batch`) | team | watermark eligibility (§7) | immediate | qualitative: admission above/below the reserve line |
| K6 | `activeHours` | team | spawn admission by clock | next boundary | burn moved in time, shown on the runway timeline |
| K7 | `capacityShares` | org | contention weights (§7) | under contention only | reallocation, not reduction — console says so |
| K8 | `reserveWatermarkPct` | org × pool | hard admission floor for `interactive` | immediate | guarantees, not savings: "15% of the window held for interactive" |
| K9 | Fallback policy order | team | §5 ladder | on exhaustion | which degraded mode engages, and its cost note |
| K10 | Extra-usage opt-in + cap | account | allows overflow past plan limits into paid credits | on exhaustion | converts a hold into estimated $ at API list rates — displayed as money, never silently |

Notes. K3 is the honest version of "rate limit a team": a headless `claude -p` run cannot be paced mid-flight, so pacing = chunking — run `paceChunkTurns` turns, suspend, cool down, `--resume`. The chunk boundary is the same mechanism budget enforcement already uses, so K3 costs no new machinery, only policy. K2's per-*team* cap composes with the existing per-*provider* gateway semaphores (api-key paths) and with a new per-*account* session cap (`provider_account.maxConcurrentSessions`, default 4) that respects Anthropic's documented multi-session soft ceilings — three layers, each named for what it protects: team fairness, provider etiquette, account etiquette.

## 4. The capacity gate

When a session must stop for capacity (window exhausted, pause, watermark), the assignment suspends behind an **InterventionGate** with `opened_by='trigger:capacity'` — the gate taxonomy stays at five kinds, exactly as X1 kept it. Payload:

```jsonc
{ "pool": "pa_claudemax", "window": "five_hour", "reason": "exhausted",
  "resetsAt": "2026-08-08T17:40:00Z", "policy": "hold-resume", "sessionRef": "…" }
```

Three properties make it cheap and legible:

- **Timer auto-resolution.** The trigger sweep resolves the gate when `resetsAt` passes (plus jitter) and the admission checks pass — the first timer-resolved gate in the system, a deliberate, bounded extension of SC-4's "bounded auto-resolution" precedent (which shipped as the hard-stop top-up policy). If `resetsAt` was unknown (unparseable limit text), the gate resolves on the next successful probe instead.
- **It is not a stall and not an error.** The inspector, pulse, and plan views render capacity gates as *scheduled waiting* ("holding for 5 h window · resumes ~17:40"), a third visual state distinct from blocked-on-operator and erroring — F11's classification discipline extended to the fleet level. Capacity gates are `info`-severity by default; they page nobody (`06` §5).
- **Resumption is a `--resume`.** The suspended conversation continues where it stopped; nothing re-briefs, nothing re-spends intake.

Budget gates and capacity gates compose without special cases: a hard-stopped assignment (budget) behind an exhausted window (capacity) shows both, and resolving the money one still leaves the capacity hold until reset — two different questions, two different answers, per `02` §1.

## 5. The fallback ladder

Per-team, ordered, from `fallbackPolicy`; each rung is attempted at the moment work would otherwise hold:

1. **`hold-resume`** (default, always last implicitly) — capacity gate until `resetsAt`. Cost: latency only. The correct default for `batch`.
2. **`degrade-model`** — restart the next chunk on the team's configured fallback tier (K4 semantics), e.g. Opus→Sonnet when only `seven_day_opus` is exhausted, staying inside the same account. Cost: quality note on the assignment (a Directive records the downshift so the transcript explains itself).
3. **`switch-account`** — next ProviderAccount in the team's profile chain (e.g. Max → Gemini plan, or Max → api-key). Requires a fresh session (context does not cross providers); the adapter closes the chunk cleanly, re-briefs from the assignment record, and notes the switch. Cost: re-intake tokens + provider consistency; only sensible for roles whose work is provider-portable — the profile chain is per-team opt-in, never global.
4. **`extra-usage`** (K10, opt-in) — continue on the same account past plan limits into metered credits, within the account's hard cap. Cost: real dollars at API list rates, surfaced in the cost explorer as `provider='claude-extra'`, never blended into subscription "$0" rows.
5. **`park`** — `drain`, notify `attention`. The explicit "wake the human" rung for teams whose work should not degrade silently.

The worked scenario, replayed mechanically: `canopy-maintenance` (batch, `[hold-resume]`) exhausts `five_hour` at 16:55 → its three sessions close at turn boundaries into capacity gates (resume ~17:40); `household` (interactive) stays admissible against the 15% reserve (K8) — the second team's capacity was *pre-provisioned by policy*, and introducing it required no emergency knob-turning at all. Had the operator instead needed room *before* exhaustion, the console's what-if strip (`06` §3) answers "which knob frees how much": K1 on maintenance frees 4.1 pp/hr, K2 3→1 frees ~2.6, K3 at 50% duty frees ~2.0 — provider-anchored numbers, each labeled with its confidence.

## 6. Fairness across organizations

Under contention (demand for spawns > admissible spawns), ordering is: reserve eligibility (K8) → org shares (K7, weighted round-robin over organizations by unconsumed share this window) → team priority (K5) → FIFO by wait time. Starvation is bounded because shares are weights over a rolling window, not static partitions: an org with 30% share and pent-up demand accumulates claim while idle. SC-5's noisy neighbor gets its concrete mechanism here; the load-test scenario it prescribed becomes a scheduler test (`07` §6).

## 7. Failure and recovery semantics

- **Mid-turn limit hit** (the provider says no while a turn is in flight): the CLI's own retry emits `api_retry`; if the turn ultimately fails with a limit result, the chunk closes, the step ledger keeps whatever the session reported (idempotent step ids, unchanged), and the assignment gates. No double-charge, no lost work — the same crash-consistency spine E6 hardened.
- **Scheduler restart**: `team_schedule` and gates are SQLite truth; on boot the sweep re-evaluates every open capacity gate against current window state (a reset that passed during downtime resolves immediately). Predictions and burn rates are derived state and rebuild from readings.
- **Adapter darkness** (no readings for > TTL): windows go `unknown`; admission *does not block* on unknown (running blind is the status quo ante, and blocking on ignorance would make the capacity layer a regression); the console shows the staleness loudly; tier-2 events still pin exhaustions.
- **Clock skew**: `resetsAt` comparisons use server time with ±120 s jitter on auto-resolution to avoid thundering-herd resumes racing the provider's clock.

## 8. Config and defaults

```toml
[scheduler]
enabled = true
default_priority = "batch"
account_max_concurrent_sessions = 4   # per ProviderAccount, etiquette cap (K2 note)
resume_jitter_s = 120

[scheduler.watermarks]                # window-state thresholds for the pool state machine
warning_pct = 75                      # window → warning; console amber; batch spawns get runway check
```

Per-team knobs are UI/API-managed rows (`PUT /api/teams/{id}/schedule`), not TOML — they are operational state, adjusted from the console, audited like every other operator action.

## 9. Open questions

1. **Should `drain` be the default reaction to org-ceiling crossings** instead of refuse-new-intents? Current answer: no — ceilings gate *admission*, drain is an operator verb; revisit after a month of real budgets.
2. **Per-node scheduling.** Everything here is per-team; a team whose lead should stay responsive while its ICs batch is expressible only via priority at team granularity. Wait for a real case before adding a node axis.
3. **Preemption.** True preemption (suspending a *turn* in flight) is deliberately absent — turns are atomic by design (metering, F13). If a genuinely urgent interactive need can't wait one turn, that is what K8 reserves are for; revisit only with evidence.
4. **Cadence interaction.** ~~Cadence-fired intents currently submit unconditionally; they should consult runway (skip-with-note when the window can't fit the median run — `cadence.skipped reason=capacity`). Small, but needs a decision on whether a skipped occurrence coalesces (leaning yes, matching existing misfire policy).~~ **Decided at C7 (2026-08-15):** cadences consult the governor before they submit — `Scheduler.admit_cadence` (boundary 3 for standing intents) refuses on the org weekly ceiling (`cadence.skipped reason=budget`), a paused or drained team (`reason=paused|drain`), or an exhausted binding window for which the fallback ladder finds no rung that admits (`reason=capacity`, with `resetsAt` in the note); rungs that admit (degrade / switch-account / extra-usage) let it fire. Spawn-time *waits* — active hours, the K2 cap, reserve/contention ordering — do not skip: those are queues, not doors, and the intent waits at admission like any other. A skipped occurrence **coalesces** (consumed, matching the misfire policy). What remains open is the finer test the question named — "the median run fits the remaining runway" — which needs per-cadence run-size history (`phase3-debts.md` CAP-D10); trigger-fired intents are likewise not yet governed at this boundary.
