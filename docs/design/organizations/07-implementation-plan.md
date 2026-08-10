# 07 · Implementation Plan — migration, milestones, and the hand-off

> **Status:** Adopted 2026-08-09 (operator decision) — proposed by the portfolio-and-capacity working group, 2026-08-08
> **Reads with:** the whole series; `../../execution/mvp.md` (milestone style this follows), `../../testing.md` (pillars every stage must honor), `../../actuation/phase3-debts.md` (the ledger that will track what this opens)
> **Audience:** this document is written to be handed to Claude Code. Each milestone is independently green, demoable, and CI-covered on the `mock` spine.

## 0. Sequencing mandate — this precedes the full MVP

**Operator decision, 2026-08-08:** this plan is not post-MVP polish; the C-series is part of the MVP implementation plan itself. The full Canopy MVP — the E-series capstones plus the first live O-ladder rungs — is **not declared delivered until C1–C7 land**. Two reasons make this ordering load-bearing rather than preferential: the C1 rename only gets more expensive with every day of accumulated state, exports, and habit (CAP-D4), so it must precede any broader release; and no standing-intent org may run unattended before capacity governance exists (C2–C4) — an ungoverned fleet drawing on a shared subscription is precisely the failure mode the MVP must not ship. `../../execution/mvp.md` and `../../org-roadmap.md` gain pointers to this section on adoption (§7).

## 1. Milestones (C-series)

| # | Name | Ships | Done means |
|---|---|---|---|
| **C1** | The rename + Organization entity | Team vocabulary end-to-end (docs kind `canopy.team` v2, code identifiers, API routes §3, UI copy); `organization` table + membership; filesystem regrouping §2.5; portfolio home (read-only cards) + org pages + scope bar; move-team flow | fresh clone runs the MVP demo with two organizations × two teams concurrently; v1 documents import; e2e passes renamed |
| **C2** | Capacity substrate | `provider_account`, `capacity_window/reading/event` tables; QuotaAdapter registry with `mock` + `anthropic-max` tier-2 (S1/S2 parsing in the cli adapter and fake-CLI); profile→account migration §2.3; attribution + burn rates + runway math | fake-CLI limit script drives window `exhausted`→`ok` through readings; attribution splits two mock teams correctly under test clock |
| **C3** | Capacity read UX | `GET /api/capacity` aggregate; capacity strip + console (gauges, badges, attribution, feed); capacity notifications §`06` §5; S3 statusline tap (opt-in) | console demonstrable on `mock`; every number carries source+age; zero capacity math in the UI bundle |
| **C4** | The governor | `team_schedule` + scheduler admission at the three boundaries; capacity gate (`opened_by='trigger:capacity'`, timer auto-resolution); K1–K6 knobs + knob panel with prediction chips + closed loop; fallback rungs `hold-resume`, `degrade-model` | kill a mock window mid-run: sessions hold at turn boundary, gate renders as scheduled-waiting, auto-resume on scripted reset; pause/resume a team from the card |
| **C5** | Org economics + fairness | org budgets (ceiling at intent admission), shares K7 + reserves K8, contention ordering `04` §6; what-if strip; `/orgs/:id/capacity` | SC-5 scenario as a scheduler test: two orgs, contended mock pool, shares honored, reserve admits interactive team at high utilization |
| **C6** | Provider breadth | `switch-account` + `extra-usage` rungs (account cap, `claude-extra` cost tag); S4 usage-endpoint source (off-default, config-gated, compliance doc §`03` §2); `google-consumer` classification + `cli_daily` counting schema; api-key header windows | fallback chain demo on mock accounts; S4 behind explicit config with the documented posture |
| **C7** | Hardening + fold-in | restart/redelivery sweeps for capacity gates; reading retention; live smoke (one marked test against a real Max login, `testing.md` §6 style); doc-edit impact map §7 executed; debts registered | E6-style audit: control-plane restart mid-hold resumes correctly; `phase3-debts.md` gains this series' open items |

Sequencing notes: C1 is the big-bang rename and lands alone (one PR train, nothing else moving). C2–C3 are safe to build behind `[capacity] enabled=false`. C4 is the first behavior change to running work; its default posture (no schedules configured = today's behavior) keeps it non-breaking. The worked example (`README`) is fully demoable at C5 on mock, and live at C7.

## 2. Migration mechanics (C1)

1. **Vocabulary/code.** Mechanical rename with a table-driven sweep: `Organization→Team` (chart sense), `org→team` in identifiers keyed to charts (`orgId→teamId`, `org_path→team_path`, `OrgStore→TeamStore`…), `Team→Pod` in the derived-grouping sense (`team broadcast` channel kind → `pod broadcast`), `childOrganizations→childTeams`. The new-sense Organization takes the freed name. One commit per layer (server, agent, ui), grep-clean gates (`rg -i 'organization'` findings must be new-sense or citation).
2. **Documents.** `migrate.py`/`migrate.ts` v1→v2: `kind` rewrite, `childOrganizations` rename, export filename `<slug>.team.json`. v1 import accepted indefinitely; export always v2. Golden vectors duplicated to v2 (v1 vectors kept — the migrator is contract-tested against both).
3. **DB.** New tables `organization`, `team_membership`-free design (`team.organization_id` column on the renamed team store row), `provider_account`, capacity tables (C2), `team_schedule` (C4). Existing rows: one-shot boot migration creates `default` Organization (`key: "default"`, theme sage) and assigns every existing team; profile rows split into `provider_account` (one per distinct provider+secret, plus one `subscription-cli` account if any binding uses `cli-claude`) + slimmed profiles referencing them. Non-destructive, same pattern as `sqlite_store` A1 migration.
4. **Refs.** Writers emit `team://`; readers accept `org://` forever (one regex, both schemes); stored refs migrate lazily on touch, plus a one-shot rewrite pass in the boot migration for `work_*` and artifact metadata rows.
5. **Filesystem.** Boot migration moves `data/work/<teamId>` → `data/orgs/default/teams/<teamKey>/work`, `data/repos/<teamId>` → `…/repos`, sandbox/log homes likewise; `CANOPY_WORK_ROOT` derivation updated (the F13 property — actuation-independence — is preserved; the *path* changes once, and `--resume` continuity is why this must land in C1 while sessions are few, not later).
6. **Config.** `canopy.toml` gains `[capacity]`/`[scheduler]` (defaults off/inert); no existing key changes meaning.

## 3. API change map

| Today | After | Notes |
|---|---|---|
| `GET/POST /api/organizations…` (chart CRUD, validate, export, import) | `GET/POST /api/teams…` | verbatim move; old paths return `410` with the new path in the body for two releases |
| `/api/organizations/{id}/profiles·bindings·secrets·repo-source` | `/api/teams/{id}/…` | unchanged semantics; profiles reference `providerAccountId` |
| `/api/organizations/{id}/actuations·intents·assignments·gates·cadences·events·pulse·spend·activity·agents/*` | `/api/teams/{id}/…` | the whole operate surface re-roots |
| — | `GET /api/portfolio` | home aggregate: orgs, teams, vitals, capacity headline |
| — | `/api/orgs` CRUD; `PUT /api/orgs/{id}/budget`; `POST /api/teams/{id}/move` | new entity |
| — | `GET /api/capacity`; `/api/capacity/accounts` CRUD; `/api/capacity/events` (SSE tag) | console aggregate; accounts UI |
| — | `GET/PUT /api/teams/{id}/schedule` | knobs K1–K6, audited |
| `GET /api/organizations/{id}/events` (SSE) | `GET /api/teams/{id}/events` + `GET /api/events` (portfolio, org-tagged) | portfolio stream multiplexes team events + capacity events |
| dp surface (`/api/dp/*`) | unchanged paths; `assignment/current` may return `{"hold": {...}}` | run-token contract untouched otherwise — agents don't know the upper world exists (invariant 12) |

## 4. Schema sketches (DDL-level, engine style)

```sql
CREATE TABLE organization (id TEXT PRIMARY KEY, key TEXT UNIQUE NOT NULL, name TEXT, purpose TEXT,
  theme_json TEXT, priority_class TEXT DEFAULT 'batch', budget_json TEXT, created_at TEXT, updated_at TEXT);
-- team store row (renamed) gains: organization_id TEXT NOT NULL REFERENCES organization(id)
CREATE TABLE provider_account (id TEXT PRIMARY KEY, provider TEXT, auth_mode TEXT, label TEXT,
  cli_config_dir TEXT, cli_cmd TEXT, api_key_secret_id TEXT, plan_hint TEXT,
  max_concurrent_sessions INTEGER DEFAULT 4, extra_usage_cap_usd REAL, created_at TEXT);
CREATE TABLE capacity_window (id TEXT PRIMARY KEY, account_id TEXT, key TEXT, kind TEXT,
  model_scope TEXT, display_name TEXT, utilization_pct REAL, resets_at TEXT, state TEXT,
  source TEXT, observed_at TEXT, UNIQUE(account_id, key));
CREATE TABLE capacity_reading (id TEXT PRIMARY KEY, window_id TEXT, utilization_pct REAL,
  resets_at TEXT, source TEXT, detail TEXT, observed_at TEXT);
CREATE TABLE capacity_event (id TEXT PRIMARY KEY, account_id TEXT, window_key TEXT, org_id TEXT,
  team_id TEXT, kind TEXT, payload_json TEXT, created_at TEXT);   -- feed + audit
CREATE TABLE team_schedule (team_id TEXT PRIMARY KEY, run_state TEXT DEFAULT 'running',
  max_concurrent_sessions INTEGER, pace_chunk_turns INTEGER, pace_delay_s INTEGER,
  model_tier_cap TEXT, priority TEXT, active_hours TEXT, fallback_json TEXT, updated_at TEXT);
```

ID prefixes: `org_`, `pa_`, `qw_`, `qr_`, `ce_` join `ids.py`. Owner modules: `orgs.py`, `capacity/{accounts,ledger,adapters/}.py`, `scheduler.py` — each registering its schema, per the house pattern.

## 5. Code impact map

- **server:** new modules above; `deps.py` wires adapters + scheduler; `engine.py` gains the capacity check beside the budget check and the timer sweep case in `sweep_triggers`; `gates.py` learns `trigger:capacity` payload + timer resolution; `routes/` re-roots per §3 (mechanical) + new `routes/{portfolio,orgs,capacity,schedule}.py`; `actuator.py` derives the new work-root path; `charter.py` untouched (agents stay ignorant); `cadence.py` gains the runway skip (`04` §9.4 decision).
- **agent:** `cli_runtime.py` — chunked execution (`paceChunkTurns` → `--max-turns` per chunk + delay + `--resume`), `hold` handling on `assignment/current`, limit-signal forwarding (it already parses stream-json; it now *reports* S1/S2 as session events), account `cli_config_dir` → `CLAUDE_CONFIG_DIR`. `runtime.py` (loop): `hold` handling only.
- **ui:** rename sweep; new components per `05` §8 / `06` §8; router per `05` §1; SSE multiplexing; retire org-picker and `PhasePlaceholderPage` (already dead).
- **catalog/docs:** no catalog changes (roles/formations are org-model-agnostic — the layer boundary held).

## 6. Test plan

Per pillar (`testing.md` §1): **deterministic core** — everything below runs on `mock` + fake-CLI; the fake CLI grows `--limit-script` vocabulary (emit `api_retry`, limit-result strings with scripted epochs) so S1/S2 parsing is CI-truth; a `FakeClock` threads the capacity ledger and scheduler (runway/reset math must be clock-injected, never `now()`-scattered). **Golden vectors** — new families: v2 document migration (v1→v2 pairs), capacity-gate transitions (open on exhaustion / timer resolve / restart resume), scheduler admission tables (state × priority × watermark × share → admit/hold + reason). **Money-path paranoia extends to capacity:** property tests — attribution shares sum to provider delta ± ε with `external` absorbing the residual; no admission path bypasses both meter and window checks; `extra-usage` never engages without opt-in + cap headroom (adversarial test per invariant, house rule 2). **Two OSes** — chunked kill/resume on Windows (`taskkill /T`) joins the existing riskiest-integration suite. E2E: the C5 demo (two orgs, contended mock pool, knob turn, hold, scripted reset, resume) joins Playwright; exactly one live smoke (real Max login, one tiny session, asserts a tier-2 reading lands) marked manual per `testing.md` §6.

## 7. Doc-edit impact map (on adoption — not before)

| Doc | Edit |
|---|---|
| `domain-model.md` | Organization→Team, Team→Pod renames; add Organization entity + invariant 12; ProviderAccount cross-ref |
| `docs/teams.md` | retitle `formations.md`; text sweep (formations "stamp a pod") |
| `phases.md` | Build/Actuate/Execute become team-scope verbs; portfolio home noted above them |
| `operator-experience.md` | §1 IA superseded by `05` §1 (amendment note, not rewrite) |
| `org-chart-editor.md` | document kind/schemaVersion, `childTeams`, export filename |
| `org-roadmap.md` | O8 marked "realized administratively by `design/organizations/`"; rungs unaffected |
| `risks/scalability.md` SC-5 | answer pointer to `04` §6 |
| `actuation/agent-profile.md` | profiles reference ProviderAccounts |
| `phase3-debts.md` | F1 sub-item pointer to `02` §9.1; new debt rows from §8 |
| root `README.md` | terminology, quickstart ("create an organization, add a team"), architecture list |
| connectors series | ConnectorInstance scope: org-level vs team-level — one decision to record (leaning: instances stay team-scoped, packs importable at org level; needs its own amendment) |

## 8. Risks and debts this series knowingly opens

- **CAP-D1 — S4 compliance exposure.** The usage-endpoint source is ToS-gray; mitigated by off-default + isolation to one module (`03` §6). Sunset the debt if Anthropic ships an official usage API.
- **CAP-D2 — inference drift in observed-only mode.** Between anchors, levels are estimates; mitigated by honesty UI + closed-loop calibration; accepted until S3/S4 adoption or provider openness improves.
- **CAP-D3 — chunking overhead.** Pacing via chunk+resume re-reads session context on each resume (cache-priced, but not free); measured and surfaced in the cost explorer before K3 defaults ever tighten.
- **CAP-D4 — rename long tail.** History (git, old exports, screenshots, the pitch) says "organization" in the old sense forever; mitigated by the migrator's permanence and a glossary note in `domain-model.md`.
- **CAP-D5 — google-consumer is schema-first.** Its load-bearing life awaits a `cli-gemini` runtime; the risk is designing unexercised code — mitigated by keeping it classification+counting only until then.

## 9. Definition of done for the series

Two organizations with disjoint purposes run concurrently on one machine and one Max subscription; the portfolio home makes their separation and their health legible in one glance; the capacity console shows provider-anchored window state with per-team attribution including the operator's own external usage; every knob shows a prediction before commit and its observed effect after; window exhaustion holds work reversibly and resumes itself at the provider's reset; nothing anywhere displays a capacity or cost number without its source; and the whole story demos keyless on `mock` in CI, exactly once live in the release checklist.
