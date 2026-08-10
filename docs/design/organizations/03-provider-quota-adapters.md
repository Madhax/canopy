# 03 · Provider Quota Adapters — reading the source of truth

> **Status:** Adopted 2026-08-09 (operator decision) — proposed by the portfolio-and-capacity working group, 2026-08-08
> **Reads with:** `02-capacity-model.md` (the ledger these feed), `04-scheduling-and-throttles.md` (the consumer), `../../execution/cli-runtime.md` (session machinery), `../../actuation/agent-profile.md`
> **Provenance discipline:** every surface below is labeled **[Official]** (provider-documented), **[Community]** (reverse-engineered, widely used, undocumented), or **[Uncertain]**. Facts current as of 2026-08-08; §7 records the citations. Adapters must treat [Community] surfaces as breakable and degrade to the next tier without operator action.

## 1. The adapter interface

```python
class QuotaAdapter(ABC):                       # registry-selected per ProviderAccount
    def expected_windows(self, account) -> list[WindowSpec]: ...
    async def poll(self, account) -> list[WindowReading]:        # tier-1 pull, may be a no-op
    def on_session_event(self, account, ev) -> list[WindowReading]:   # tier-2, in-band
    def classify_error(self, account, err) -> ErrorClass: ...
        # → quota-exhausted(window_key, resets_at?) | capacity-transient | auth | other
```

`poll` is optional (Google consumer has nothing to poll). `on_session_event` is mandatory and free: it is fed from streams Canopy already parses — the `cli-claude` observer thread (`cli-runtime.md` §5) and gateway responses. `classify_error` is what keeps F11's lesson (`erroring ≠ stalled`) intact one level up: a quota 429, a transient capacity 429, and an auth failure demand three different reactions (`04` §8).

## 2. `anthropic-max` (subscription-cli accounts)

The account under which `cli-claude` sessions run. Window set: `five_hour`, `seven_day`, `seven_day_opus`, `seven_day_sonnet` (each `{utilization, resets_at}`), plus `extra_usage` (credit-pool) when enabled.

**[Official] Limit mechanics being modeled.** The 5-hour rolling session window opens at first message and resets 5 h later; weekly windows (added Aug 2025) cap total and per-model (Opus) usage on a 7-day cycle; limits are unified across claude.ai, desktop, Cowork, and Claude Code — one pool, which is why `external` attribution (`02` §5) exists. Three distinct user-facing ceilings: session, weekly, per-model weekly ("Opus limit"); the per-model ceiling blocks only that model. "Extra usage" pay-per-token overage can be enabled past plan limits (with a documented prompt-cache-TTL downgrade side effect worth knowing when comparing costs).

**Sources, in tier order:**

| # | Surface | Tier | Availability | What it yields |
|---|---|---|---|---|
| S1 | Session limit signals in `stream-json` | provider-event | always, in-band | exhaustion + reset time |
| S2 | `system/api_retry` events | provider-event | always, in-band | rate-limit pressure signal |
| S3 | Statusline `rate_limits` stdin JSON | provider-read | interactive sessions only — **not** `-p` headless | `five_hour`/`seven_day` used % + resets |
| S4 | OAuth usage endpoint | provider-read | opt-in, [Community], ToS-gray | all four windows + extra-usage, full fidelity |

- **S1 [Community, stable in practice].** When a subscription limit hits in `-p`/stream-json mode, the final `result` message has historically carried the machine-parseable `"Claude AI usage limit reached|<epoch-seconds>"` (pipe-delimited reset), with newer builds emitting the interactive phrasing `"You've hit your session limit · resets 3:45pm"` / weekly / Opus variants. The adapter parses **both** shapes, maps session→`five_hour`, weekly→`seven_day`, Opus→`seven_day_opus`, records `utilization=100` + `resets_at`, and treats unparseable limit text as `five_hour` exhausted with unknown reset (conservative). This is the load-bearing source: it requires nothing but sessions we already run and parse.
- **S2 [Official].** Headless mode emits `system/api_retry` events (`attempt`, `max_retries`, `retry_delay_ms`, `error_status`, `error` ∈ {`rate_limit`, `overloaded`, …}) before each retry. `rate_limit` entries feed a pressure counter (not a level); sustained pressure at moderate inferred utilization is itself displayed ("provider throttling before window exhaustion") rather than mislabeled a stall — F11's rule.
- **S3 [Official].** Claude Code passes `rate_limits.five_hour.used_percentage` / `.resets_at` (epoch) and `rate_limits.seven_day.*` to custom statusline commands via stdin JSON — an *officially documented* provider-read of exactly the two headline windows. It does not run under `-p`. The adapter ships a tiny statusline hook (`canopy-statusline-tap`: append the JSON to a file the control plane tails) so that **any** interactive Claude Code use of the same login — including the operator's own coding sessions — feeds tier-1 readings for free. Honest limitation: if the operator never opens an interactive session, S3 contributes nothing; per-model windows never appear here.
- **S4 [Community, ToS-gray, opt-in only].** `GET https://api.anthropic.com/api/oauth/usage` with the login's OAuth bearer token (from `CLAUDE_CONFIG_DIR` credentials / platform keychain) returns the full picture: `five_hour`, `seven_day`, `seven_day_opus`, `seven_day_sonnet` each `{utilization, resets_at}`, plus `extra_usage {is_enabled, monthly_limit, used_credits, utilization}`. It is undocumented, aggressively rate-limited (poll ≥180 s), requires Claude-Code-shaped request headers, and — decisively — Anthropic's 2026 consumer-terms clarification prohibits using subscription OAuth tokens *outside Claude Code itself*. Widely-used monitors consume it without incident to date, and enforcement has targeted third-party *inference*, but the compliance posture is the operator's call, not ours to default. Therefore: `[capacity.anthropic] source = "usage-endpoint"` is **off by default**, documented with exactly this paragraph, and the entire design *works without it* — S1/S2/S3 + calibration deliver every feature at reduced fidelity (levels are inferred between anchors instead of provider-read every 5 minutes). This is the one place the "source of truth first" requirement bends to a provider's terms, and it bends transparently.

**What the adapter does *not* do:** call the Agent SDK with subscription OAuth (explicitly disallowed by Anthropic — Canopy spawns the `claude` binary itself, which is the sanctioned automation path), spoof interactive surfaces, or read another instance's credentials.

**Api-key Anthropic accounts** (if the operator adds one as a fallback rung): [Official] every response carries `anthropic-ratelimit-{requests,input-tokens,output-tokens}-{limit,remaining,reset}` headers plus `retry-after` on 429 — genuine tier-1 token-bucket windows, read for free by the existing gateway path. The Admin Usage & Cost API is org/API-scoped and irrelevant to Max; noted only so nobody goes looking.

## 3. `google-consumer` (Google AI plan accounts)

**The honest headline: no server-side "remaining quota" read exists for consumer Google AI plans.** This adapter is tiers 2–3 by construction, and the design says so out loud rather than laundering estimates into gauges.

**[Official] Limit shapes being modeled.** The Gemini app moved to *relative* limits in 2026 — plan-tier multipliers over unstated "standard limits," refreshing on a **5-hour window capped by a weekly limit**, explicitly compute-weighted and mutable without notice → windows `app_five_hour`, `app_weekly`, kind `rolling-window`, level unknown-until-evented. Gemini CLI / Code Assist under the plans has a **daily model-request quota** (published: 1,500/day AI Pro, 2,000/day AI Ultra; per-minute limits exist but exact RPM is no longer published), aggregated across models and across CLI+agent surfaces → window `cli_daily`, kind `fixed-daily`, with a *known denominator* — the one place this adapter can count meaningfully client-side.
**[Official, 2026-03]** Consumer-OAuth reuse by third-party software is a policy violation — identical posture to Anthropic: Canopy may automate the official `gemini` binary (headless mode is a documented feature), never its OAuth backend directly.

**Sources:**

- **429 classification [Community-verified shapes].** API-style errors carry `status: RESOURCE_EXHAUSTED` with a `QuotaFailure` detail naming the violated quota (`quotaId`, `quotaMetric`, `quotaDimensions.model`) and a `RetryInfo.retryDelay`; the CLI's OAuth path can instead return bare capacity 429s ("no capacity for model …") with no structured details. `classify_error` maps: QuotaFailure with a daily `quotaId` → `cli_daily` exhausted, reset next midnight PT (RetryInfo is documented-unreliable for daily exhaustion — ignore it there, honor it for per-minute); bare 429 → `capacity-transient`, backoff without touching windows. Indistinguishable dimensions (capacity vs. account deprioritization) stay `capacity-transient` — we refuse to invent precision the payload doesn't carry.
- **Local counting against the known denominator [inferred, but well-anchored].** For `cli_daily` the adapter counts Canopy-issued model requests (the CLI's OTel/telemetry stream or session parsing, once a `cli-gemini` runtime exists) against the published per-plan denominator → an inferred level with an honest basis, displayed as `~n/1500 · counted locally`. External usage of the same Google login is invisible until a 429 corrects us — stated in the UI, not hidden.
- **`/stats` scraping [Community, fragile].** Recent Gemini CLI builds show per-model remaining-% with reset countdown in `/stats`; the backing endpoint is `v1internal` and unstable. Optional future source; never a dependency.

**A note on sequencing:** Canopy today has a Gemini *api-key* gateway provider and no Gemini CLI runtime. This adapter ships its schema and classification in C2 (it costs little and shapes the interface), but its full life begins when/if a `cli-gemini` runtime kind lands (`../../actuation/agent-envelope.md` §4 reserved the slot). The api-key Google account meanwhile is simpler: **[Official]** no rate-limit response headers exist (confirmed, long-standing); quota visibility is Cloud Console / Cloud Monitoring (`serviceruntime.googleapis.com/quota/*` metrics for `generativelanguage.googleapis.com`, e.g. `generate_content_free_tier_requests`) — an optional tier-1 pull for operators who wire a GCP project, otherwise 429-classification only, same code path.

## 4. `mock` (CI and demos)

Scriptable windows via profile/params: initial utilizations, burn-per-call, `resets_at` schedules, and injectable exhaustion/429 events — the capacity analog of the scriptable mock ModelProvider, keeping pillar 1 (zero-spend deterministic CI) intact. Every scheduler and console behavior in `04`/`06` must be demonstrable on `mock` alone; the fake-CLI shim (`server/tests/fake_claude.py`) grows limit-result and `api_retry` vocabulary so tier-2 parsing is CI-covered too (`07` §6).

## 5. Multi-provider arithmetic

Pools are **independent and incommensurable**: 82% of a Max 5-hour window and 1,240/1,500 Gemini CLI requests share no unit, and the design refuses to pretend otherwise. What is comparable, and how it is used:

- **Headroom-with-deadline** — every window reduces to "(100−util)%, resets at T" or "n remaining, resets at T". The scheduler consumes exactly this normalized pair per window; nothing needs a common unit (`04` §5's ladder just asks "is there a pool with headroom that this team's profile can use?").
- **Estimated dollars** — the only cross-provider lens, already established by the cost explorer, already labeled estimate. Org weekly ceilings (`01` §6) live here.
- Fallback across providers is therefore a *profile-chain* decision (this team may run on `pa_claudemax`, then `pa_googleai`, then an api-key account), not a unit conversion — `04` §5.

## 6. Compliance and risk register (adapter-scoped)

| Risk | Posture |
|---|---|
| S4 OAuth-endpoint use deemed ToS-violating | Off by default; opt-in behind config + doc warning; entire system functions without it; single module to delete. |
| S1 limit-string phrasing changes | Both known shapes parsed; unparseable limit text degrades to conservative exhaustion; fixture-covered so a phrasing change is a one-line fixture PR. |
| Statusline schema changes | [Official] surface, versioned by Claude Code; tap fails soft (absence = fewer tier-1 readings, nothing breaks). |
| Google publishes real quota API | Adapter grows a tier-1 `poll`; schema already fits (`utilization`/`resets_at`). We are structured to *benefit* from provider openness, not depend on reverse engineering. |
| Anthropic soft session/automation caps (documented ">50 sessions/month may be limited"; weekly limits exist to curb 24/7 automation) | Surfaced in `06` §5 as an advisory, and the scheduler's pacing knobs (`04` §3) are precisely the tool for staying a good citizen. Canopy's stance: govern within the subscription's spirit, don't race it. |
| Multiple Max accounts to multiply quota | The schema permits multiple accounts (they are real identities); Canopy will not add features whose only purpose is limit evasion (no account rotation, no automatic spillover between subscription accounts of the same provider without explicit per-team profile chains the operator configured). |

## 7. Source notes

Anthropic: code.claude.com/docs/en/{costs, statusline#rate-limit-usage, errors, headless}; support.anthropic.com article 11014257 (Max usage); support.claude.com articles 11145838 (Pro/Max in Claude Code), 12429409 (extra usage); platform.claude.com/docs/en/api/rate-limits (api-key headers). [Community]: the `api/oauth/usage` shape and etiquette as documented across Claude-Code-Usage-Monitor, claude-code-statusline, the `claude-usage` crate, and anthropics/claude-code issues (#5085, #11429 — limit result strings; #31637 et al. — endpoint 429s, "not planned"). ToS: Anthropic consumer terms §3.7 + Feb 2026 clarification (subscription OAuth outside Claude Code not permitted). Google: support.google.com/gemini/answer/16275805 (plan multipliers, 5 h/weekly refresh); gemini-cli quota-and-pricing doc + cloud.google.com/gemini/docs/quotas (daily quotas, aggregation); gemini-cli discussions #22970 (2026-03 policy, Pro-models-paid-only), #3096 (no quota API), issues #18960 (/stats remaining %), #13112/#24188 (429 shapes), ai.google.dev/gemini-api/docs/rate-limits (api-key tiers, spend-based limits); cloud monitoring quota-metrics docs. Full URLs live in the working-group notes; each claim above carries its tier so implementers know what to re-verify at build time.

## 8. Open questions

1. **Should the statusline tap ship enabled?** It touches the operator's Claude Code settings (a visible, reversible one-liner). Leaning yes-with-consent during account creation ("let Canopy read window state from your interactive sessions?").
2. **`seven_day_sonnet`** appears in the community endpoint schema but not in official ceilings copy; treat as discovered-if-seen (the unknown-window path already handles it).
3. **Extra-usage as a fallback rung** (`04` §5) needs a spend cap of its own — where does that cap live, org budget or account? Proposed: account-level hard cap, org ceilings still apply. Decide at C4.
4. **Gemini CLI runtime** — this series deliberately does not design `cli-gemini`; when it lands, `google-consumer` upgrades from schema-only to load-bearing, and its OTel-based counting needs a design pass of its own.
