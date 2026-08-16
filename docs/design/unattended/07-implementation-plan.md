# 07 · Implementation Plan — the H-series

> **Status:** Proposed 2026-08-16 · **Reads with:** the whole series; `../organizations/07-implementation-plan.md` (style precedent), `../../testing.md` (pillars), `../../actuation/phase3-debts.md` (gains OPS-D1..D5 on adoption)
> **Audience:** written to be handed to Claude Code — or, per `../../canopy-inc.md`, to become `canopy-frontier`'s first ratified series and `canopy-foundry`'s first standing engagement. Each milestone independently green and demoable on the `mock` + fake-CLI spine.

## 0. Sequencing and prerequisites

The H-series lands **after the C-series is merged** — H-work assumes the governor, org budgets, and fallback ladder of C2–C7 on `main` (the C5–C7 branch train merging is prerequisite #1, tracked in `canopy-inc.md` §7). Operational posture prerequisites, stated once: `[capacity] enabled = true`, `[scheduler] enabled = true`, `runtime_override = ""` for the live path (CI stays keyless). Relationship to the waves (`canopy-inc.md` §6): **H1–H2 gate W1 running at posture P1**; H3–H4 gate W2; **H5 (docker) gates W3**; H6 wraps the ladder and is the release gate for calling any posture claim real. CAP-D8's missing knob UI lands inside H2 (the brief's team cards get the schedule panel), closing that debt alongside.

## 1. Milestones

| # | Name | Ships | Done means |
|---|---|---|---|
| **H1** | Operations envelope | `team_ops_envelope` table (versioned); engine consult points (staged-batch, budget intervention, clarification/escalation) returning resolve/park/route; `resolved_by: envelope@vN` attribution; park state + reason codes + latency flags; X4 directive-as-answer wiring; graduation evidence queries + `graduation-suggested` card; auto-tighten on guardrail breach; envelope editor (team page) | golden vectors: every consult point × (resolve/park/route) × mode; auto-top-up funds ≤ factorCap and refuses over org ceiling; operator intents never auto-dispatch in default envelopes; breach ⇒ `always` + receipt; parked gates release WIP and surface with reasons |
| **H2** | Daily brief + notify | `GET /api/brief` aggregate; brief page (ratify/parked/anomalies/receipts/all-clear); batch plan-review approval (idempotent, partial-failure honest); notify seam (`console`/`email`/`webhook` providers) + `[notify]` config + test-fire path; the closed page set wired (five classes); `brief-ready` daily nudge; brief-summary email (opt-in); schedule knob panel on team cards (closes CAP-D8) | brief renders from fixtures with correct ordering and honest all-clear; batch approve of N dispatches atomically per item; page classes fire on scripted events and nothing else pages (adversarial: `info`/`attention` events cannot reach the pager); cursor semantics: two briefs in a row show disjoint deltas |
| **H3** | Continuity | service wrappers (`scripts/service/` Windows + systemd example) polling `/healthz`; restart-loop page; recovered-downtime activity rows; `auth` error class + `credential-suspect` account state + park/resume via `trigger:credential`; `accounts-sync` script; weekly credential probe (config-gated); nightly maintenance loop (SQLite backup + rotation, retention prune, disk watermarks); restore-drill CI vector; `docs/runbooks/unattended.md` | kill -9 the control plane under supervisor ⇒ auto-restart + downtime row; 3 crashes/10min ⇒ page + stop; scripted auth failure parks the account's teams once (deduped page) and healthy probe resumes them; backup restores green in CI; disk watermark drills fire at thresholds |
| **H4** | Flow policies | `Scheduler.admit_trigger` consulted pre-fire (no fire row on hold; cursor holds; deduped skip receipts) — closes CAP-D10; fire-ledger `outcome` + bounded refire chains + two-strikes park + operator re-arm; rebase freshness gate in PR assembly/pr-create (+ mechanical rebase, conflict-note-to-session, conditional re-verify); salary-calibration report + proposal diffs; FL-13 bootstrap lint | scheduler test: exhausted window holds trigger candidates unfired then fires them at reset (never-consume + at-most-once proven); refire chains cap at N with provenance; stale-base PR refuses, rebases, re-verifies on conflict (fixture repo); calibration report matches ledger ground truth (property test) |
| **H5** | Threat posture | external-content fencing in the trigger renderer (platform-authored banner, hash-pinned body); reader-rule lint (`UN_READER_GRANTS`); denial/403 counters + attempt tripwires + `boundary-violation` page + envelope auto-tighten hook; **docker sandbox provider (T2)**: per-account config mount, workspace/worktree mounts only, DNS-pinned egress allowlist, `TIER_UNSATISFIABLE` re-armed; threat-model.md refresh | adversarial: fenced body's instructions are treated as data in scripted fake-CLI runs; denial spike raises anomaly with ToolEvent trail; consequential-class attempt pages + tightens; T2 acceptance: container sees nothing of the host beyond its mounts, egress off-allowlist fails, waiver check refuses tier-2 outside containers (both OSes) |
| **H6** | Readiness + soak | `unattended-check` endpoint + codes + UI surfacing + override-with-record; daily regression re-check into the brief; the 30-simulated-day fleet soak (scripted bad days, FakeClock) in the nightly tier; pilot-week protocol doc; posture ladder state (per-team, org rollup) + entry/regression wiring | soak passes its RD-5 bar in CI; readiness codes fire on seeded misconfigurations and clear on fixes; posture transitions require green checks and record overrides; a P1 org with a scripted page-class event auto-drops posture with receipt |

## 2. Config additions

```toml
[notify]    provider = "console"          # console | email | webhook
[brief]     hour = 8                       # local; 0 disables the nudge
[continuity] backup_keep = 14
             credential_probe = "weekly"   # off | daily | weekly
[retention] transcript_days = 30
[flow]      refire_after_h = 24
            max_refires = 2
            max_base_age_days = 7
```

All defaults inert or safe-on; nothing changes existing behavior until the operator flips postures.

## 3. API map (new surfaces only)

| Route | Purpose |
|---|---|
| `GET/PUT /api/teams/{id}/envelope` · `GET …/envelope?version=` | envelope read/new-version |
| `POST /api/teams/{id}/unattended-check` | readiness issues |
| `GET /api/brief` · `POST /api/brief/batch-approve` | the daily surface |
| `POST /api/notify/test` | page-channel proof |
| `POST /api/triggers/{id}/rearm` | refire re-arm (audited) |
| `GET /api/reports/salary-calibration` | FL-11 |
| `GET/PUT /api/orgs/{id}/posture` | posture ladder state |

SSE gains `brief` and `posture` event families. No dp-surface changes: **agents cannot observe the envelope, the posture, or the brief** — a team must behave identically watched and unwatched (adversarial test, the experiments-invisibility rule applied here).

## 4. Test plan

Four pillars, per `testing.md`: deterministic core (everything through H6 on `mock` + fake-CLI + FakeClock; page providers mocked); golden vectors (envelope consult matrix, page-class routing, refire chains, freshness gate, readiness codes, posture transitions); money-path paranoia extended to autonomy — property tests: no envelope resolution without attribution; no auto-top-up past factorCap or past the org ceiling; no fire row on a held candidate; no page from a non-page class; posture never rises without green checks; two OSes throughout (the service wrapper and process-group behavior are exactly where Windows bites). One live smoke: a real page delivery + a real supervised restart, marked manual in the release checklist.

## 5. Debts this series knowingly opens

- **OPS-D1 — page deliverability is unprovable end-to-end.** The seam can prove it sent; only the drill proves it arrived. Mitigation: `UN_PAGE_TESTED` staleness (30 days) forces the drill into the routine.
- **OPS-D2 — credential expiry foresight is best-effort.** Passive classification + probe shrink the window; they cannot eliminate it. Accepted; measured by time-to-park on auth failures.
- **OPS-D3 — conservative re-verify after conflicted rebases costs tokens.** Correctness over economy until receipts argue otherwise; the calibration report will show the cost.
- **OPS-D4 — the brief is desktop-bound until a hosted posture exists.** The summary email and pager are crutches, named as such. Sunsets with network deployment + real authn/z (explicitly out of this series' scope).
- **OPS-D5 — injection posture is mitigation, not solution.** TP-1/2 are speed bumps; the walls are the grants, gates, and T2. Permanent; measured honestly via tripwire stats in the brief.

## 6. Doc-edit impact map (on adoption — not before)

| Doc | Edit |
|---|---|
| `../../canopy-inc.md` §6/§7 | wave gates reference H-milestones and postures; pull table rows land (done in the same change-set as this series' proposal) |
| `../../org-roadmap.md` §5 | pointer: the bar's instrument is `06-readiness-and-soak.md` (checklist, soak, P2) |
| `../../actuation/threat-model.md` | the TP-10 refresh: unattended attacker column; stale promises corrected |
| `../standing-orgs.md` | §6/§7: admit_trigger consult + refire semantics; banner's governance caveat resolved (CAP-D10) |
| `../organizations/04-scheduling-and-throttles.md` §9.4 | CAP-D10 closed; admit_trigger documented beside admit_cadence |
| `../../execution/operator-experience.md` | the brief joins the surface list; inbox described as the brief's needs-you feed |
| `../../actuation/phase3-debts.md` | CAP-D8/D10 closed at H2/H4; gains OPS-D1..D5 |
| `../../testing.md` | soak + restore drill + page drill join the estate; new vector families registered |
