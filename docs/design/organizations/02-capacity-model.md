# 02 · The Capacity Model — provider quota as a first-class resource

> **Status:** Adopted 2026-08-09 (operator decision) — proposed by the portfolio-and-capacity working group, 2026-08-08
> **Reads with:** `01-team-and-organization.md`, `03-provider-quota-adapters.md` (the concrete sources), `04-scheduling-and-throttles.md` (the consumer), `../../actuation/control-plane.md` §5 (BudgetLedger), `../../actuation/phase3-debts.md` (F1, F11), `../../execution/cli-runtime.md` §5–6

## 1. Capacity is not budget

Canopy already has one money-shaped subsystem, and it must not be overloaded. The **BudgetLedger** answers *"how much did we choose to spend on this assignment?"* — allowances the operator sets, denominated in tokens, enforced mechanically between Steps. It is a statement about *demand*.

Capacity is the other side: *"how much are we allowed to consume, by the provider, right now?"* — windows the provider defines, denominated however the provider pleases (percent of an opaque compute pool, requests per day), resetting on the provider's clock, shared across everything the operator runs *including their own interactive Claude usage outside Canopy*. It is a statement about *supply*.

The two differ in every dimension that matters:

| | BudgetLedger (exists) | CapacityLedger (this doc) |
|---|---|---|
| Question | did this assignment overspend its allowance? | is there provider headroom to run at all? |
| Unit | tokens (meter), estimated USD (reporting) | provider-defined: utilization % + reset timestamp; requests/day |
| Source of truth | Canopy's own metering | **the provider**, wherever a surface exists |
| Reset | never (meters are per-assignment) | provider clock: rolling 5 h, weekly, daily |
| Enforcement | hard-stop between Steps | admission + hold at turn boundary (`04` §4) |
| Scope | one assignment | the whole operator — every org, every team, *and non-Canopy usage* |

That last row is the deep one: Canopy is not the only tenant of the operator's Max subscription. An afternoon of interactive claude.ai chat moves the same `five_hour` window. This is precisely why capacity levels **cannot** be reconstructed from Canopy's internal metering alone, and why the requirement — *metrics from the source of truth, not from calculations* — is architecturally correct, not merely preferable.

## 2. ProviderAccount

A **ProviderAccount** is one authenticated identity at one provider. Operator-level (`01` §2, decision 5).

```jsonc
// table: provider_account   (owner-module: capacity/accounts.py)
{
  "id": "pa_claudemax",              // prefix pa_
  "provider": "anthropic",           // anthropic | google | …
  "authMode": "subscription-cli",    // subscription-cli | api-key
  "label": "Claude Max (patrick)",
  // subscription-cli: the CLI login this account rides on
  "cliConfigDir": "~/.claude-canopy",   // CLAUDE_CONFIG_DIR / dedicated profile (cli-runtime.md §8)
  "cliCmd": null,                        // override, else CANOPY_CLI_CMD / default probe
  // api-key: the credential ref (never the credential)
  "apiKeySecretId": null,
  "planHint": "max-20x",             // display + default window set; never used for math
  "createdAt": "…"
}
```

- **AgentProfile gains `providerAccountId`.** A profile today is `{provider, model, apiKeySecretId, params}`; it becomes `{providerAccountId, model, params, systemPreamble}` — the account carries auth, the profile carries model choice. Existing profiles migrate by synthesizing one account per distinct `(provider, apiKeySecretId)` pair, plus one `subscription-cli` account if any team runs `cli-claude` (`07` §2.3).
- The `cli-claude` runtime inherits the account's `cliConfigDir` — so two ProviderAccounts *can* be two different Max logins with separate windows, and the pools stay honest.
- `mock` remains a provider with a trivially infinite account for CI.

## 3. CapacityPool and QuotaWindow

Each ProviderAccount owns exactly one **CapacityPool**; a pool is a set of provider-defined **QuotaWindows**.

```jsonc
// table: capacity_window    (owner-module: capacity/ledger.py)
{
  "id": "qw_5h_claudemax",
  "accountId": "pa_claudemax",
  "key": "five_hour",            // provider-namespaced vocabulary, below
  "kind": "rolling-window",      // rolling-window | fixed-daily | token-bucket | credit-pool
  "modelScope": null,            // null = all models; "opus" | "sonnet" for per-model windows
  "displayName": "Session (5 h)",
  // current state (denormalized from latest reading):
  "utilizationPct": 82.0,
  "resetsAt": "2026-08-08T17:40:00Z",
  "state": "ok",                 // ok | warning | exhausted | unknown
  "source": "provider-read",     // provenance of the current level, §4
  "observedAt": "2026-08-08T16:12:00Z"
}
```

Window vocabulary shipped by the adapters (`03` defines each precisely):

| Provider | Window keys | Kind |
|---|---|---|
| `anthropic` / subscription | `five_hour`, `seven_day`, `seven_day_opus`, `seven_day_sonnet`, `extra_usage` | rolling-window ×4, credit-pool |
| `google` / subscription | `cli_daily`, `app_five_hour`, `app_weekly` | fixed-daily, rolling-window ×2 |
| `anthropic` / api-key | `requests_min`, `input_tokens_min`, `output_tokens_min` | token-bucket (from headers) |
| `google` / api-key | `rpm`, `tpm`, `rpd`, `spend_10min` | token-bucket / fixed-daily |
| `mock` | scriptable | any |

Windows are *discovered and updated by adapters*, not hand-configured: the first authoritative reading (or exhaustion event) for an unknown key creates the window row. `planHint` seeds the expected set so the console can render gauges before first contact.

## 4. Readings, and the three tiers of truth

Every piece of capacity knowledge enters as an append-only **WindowReading**:

```jsonc
// table: capacity_reading
{
  "id": "qr_…", "windowId": "qw_5h_claudemax",
  "utilizationPct": 82.0,            // nullable — an exhaustion event may carry only resetsAt
  "resetsAt": "2026-08-08T17:40:00Z",
  "source": "provider-read",         // tier, below
  "detail": "oauth-usage-endpoint",  // adapter-specific: which surface produced it
  "observedAt": "…"
}
```

Three source tiers, strictly ordered by authority; the window's current state is the **most authoritative recent** reading, never merely the newest:

1. **`provider-read`** — the provider stated the level. Anthropic's usage surface (utilization + `resets_at` per window), a statusline `rate_limits` payload, api-key rate-limit headers. Trust fully; stale after `capacity.reading_ttl_s` (default 900), then decay to tier 3 display.
2. **`provider-event`** — the provider stated a *fact* but not a level: a 429 classified as quota (window → `exhausted`, `resetsAt` from the payload when present), a limit-reached result string with reset epoch, a successful call after reset (window → `ok`, utilization unknown). Events *pin* state transitions and *calibrate* tier 3.
3. **`inferred`** — Canopy's own arithmetic: internal step metering scaled by calibration (§5), used only to *interpolate between* tier-1/2 anchors. Never displayed as fact — the console renders inferred levels with an explicit `~` and the anchor's age (`06-ux-capacity.md` §6).

The invariant of the whole layer: **a displayed capacity number always carries its tier and its age.** "82% · provider-reported · 3 min ago" and "~64% · inferred from 16:05 reading" are different claims, and the UI never lets them look the same. This is the design answer to the requirement that metrics come from the source of truth: tier 1 whenever the provider offers a surface, tier 2 always (it costs nothing — the signals arrive in-band on our own sessions), tier 3 clearly demoted to connective tissue.

## 5. Attribution — who is burning the window

The provider reports *level*, never *split*: no Anthropic surface says "canopy-maintenance did this." Attribution is therefore a stated, honest hybrid:

- **Level deltas** come from consecutive tier-1 readings: the pool burned `Δutil` percentage points over `Δt`.
- **The split** of `Δutil` across consumers comes from Canopy's own per-step metering (`work_step` tokens by team, cache-aware, over the same interval) — the one thing Canopy *does* know authoritatively.
- The residual — provider-measured burn not matched by any Canopy step — is attributed to **`external`**: the operator's own interactive usage outside Canopy. It is displayed as its own band, not smeared across teams. (This falls out of the math for free and is genuinely useful: *you* are a visible tenant of your own pool.)

Per-team **burn rate** is maintained as an exponentially-weighted rate in *percentage points per hour* (pp/hr) per window — the currency of every prediction in `04`:

```
burn_team(w) = EWMA over recent intervals of:  Δutil(w) × (team_step_tokens / Σ all_step_tokens)
runway(w)    = (100 − util(w)) / Σ burn(w)          → "exhausts ~16:55"
freed(knob)  = Σ burn attributable to the sessions the knob removes    → "−2.6 pp/hr"
```

When only tier-2/3 data exists (Google consumer, §`03`), the same math runs on event-calibrated inferred levels and is labeled as such. Calibration constants (tokens-per-utilization-point per window) are refit continuously from tier-1 deltas where available, and from exhaustion events (the window said 100%; we know what we sent since the last anchor) where not — F1's "meter currency" open item gets its principled home here rather than another ad-hoc constant.

## 6. Organization shares and reservations

Two org-level claims on each pool, both defined in `01` §3 and consumed by the scheduler (`04` §7):

- **`capacityShares[pool]`** — a *weight*, not a partition: when demand exceeds supply, admission is proportional to shares (70/30 in the worked example). Idle share flows to whoever has work; shares only bind under contention. Shares need not sum to 100 (they are normalized).
- **`reserveWatermarkPct[pool]`** — a *hard* claim: above `100 − reserve` utilization, only teams in this org's `interactive` priority class are admitted. This is how `personal` stays responsive at 9 pm even though `canopy-maintenance` would happily eat the window (`04` §6 walks the scenario).

`modelScope` windows (`seven_day_opus`) are governed by the same machinery — a team whose profile routes to Opus consumes the Opus window's headroom, and a model-tier-cap knob (`04` §3, K4) is the lever that trades between them. Shares stay per-pool in v1; a per-window axis is an acknowledged open item (`01` §9.4).

## 7. What the ledger stores vs. what it derives

Stored (append-only or slowly-changing): `provider_account`, `capacity_window`, `capacity_reading`, calibration constants, and **capacity events** (exhaustions, holds, resumes, fallbacks — the feed in `06` §4, table `capacity_event`).

Derived on read (never stored, so they cannot silently go stale): current window state (most-authoritative-recent reading), per-team burn rates, runway, attribution stacks, knob predictions. All served by one aggregate endpoint, `GET /api/capacity` (`07` §3), the capacity console's single source.

## 8. Config

```toml
[capacity]
enabled = true
reading_ttl_s = 900          # tier-1 reading considered fresh this long
attribution_window_s = 3600  # EWMA horizon for burn rates

[capacity.anthropic]
source = "observed"          # observed | usage-endpoint   (03 §2 — compliance posture differs)
poll_interval_s = 300        # usage-endpoint mode only; floor 180 (community-verified etiquette)

[capacity.google]
source = "observed"          # the only mode that exists (03 §3)
```

Accounts themselves are created in the UI (they involve logins and secrets), not in TOML; the TOML governs *how* adapters read, mirroring the house rule that `canopy.toml` selects mechanisms, not data.

## 9. Open questions

1. **Meter currency unification (F1's open sub-item).** Assignment meters charge raw input+output tokens; windows burn cache-weighted compute. Calibration (§5) absorbs the mismatch for capacity math, but salaries denominated in "tokens" and windows denominated in "percent" still meet nowhere. A future amendment may re-denominate salaries in window-share or estimated USD; explicitly out of scope here.
2. **How many accounts per provider?** The schema allows several Max logins (§2). The ToS posture of *operating* several is the operator's affair; `03` §6 states what we will and won't build around it.
3. **Reading retention.** `capacity_reading` grows forever; a 30-day compaction default seems right. Decide at C2.
4. **Cross-instance capacity.** Two Canopy instances (desktop + laptop) sharing one subscription see each other only as `external` burn. A shared capacity ledger is firmly out of scope; noted so nobody mistakes `external` for noise.
