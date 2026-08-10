# 06 · Implementation Plan — the L-series, migration, and the hand-off

> **Status:** Adopted 2026-08-09 (operator decision) — proposed by the experiments working group
> **Reads with:** the whole series; `../organizations/07-implementation-plan.md` (style and sequencing precedent), `../../testing.md` (pillars every stage honors), `../../actuation/phase3-debts.md` (gains this series' debts on adoption)
> **Audience:** written to be handed to Claude Code. Each milestone independently green, demoable, and CI-covered on the `mock` + fake-CLI spine.

## 0. Sequencing

The L-series lands **after the C-series** (it speaks C1's vocabulary and reuses C4's scheduler and C5's org budgets) and is **not** an MVP prerequisite — it is the first post-MVP series, with `org-roadmap.md` O5 as its named customer: the roles forge cannot exist without L2's rubric engine and L3's judging, so O5's rung *pulls* L1–L3 onto the critical path exactly the way the O-ladder is designed to pull capabilities. L5 (search) is pulled by the model-downgrade question, which the first month of real Max-subscription burn will ask loudly on its own.

## 1. Milestones

| # | Name | Ships | Done means |
|---|---|---|---|
| **L1** | Substrate + manual A/B | `experiment/variant/task/trial/run` tables; snapshot-enroll from team/formation; solo-baseline auto-enroll; trial dispatch as stock intents into ephemeral teams (`experimentId` on the team row, portfolio-hidden); metrics harvest at close; measured factors + guardrails only; human preference verdicts; lab home + create flow (manual policy) + minimal trial page | two-variant experiment on `mock` runs three trials end to end in CI; harvested metrics match ledger/engine records exactly (property test); leaderboard renders win rate with n; voiding works and renders |
| **L2** | Rubric engine + probes | `experiment_rubric` versions; probe executor registry (`regression-suite` probe against target-app first); floors + non-inferiority; promotion predicate + holdout discipline; composite/win-rate math server-side; rubric editor UI; re-score semantics | rubric edit bumps version, past trials stable; golden vectors: scoring tables (factor values → composite → floors → predicate) and re-score parallel verdicts; promotion blocks without holdout confirmation |
| **L3** | Judged factors + the panel | exhibit materialization + sanitization; `evaluator` role + `experiment-lab` formation (evaluators only); VerdictCard contract; panel aggregation, tiers, split-flag; human override + audit queue; calibration probes + accuracy strip; judge-cost attribution to evaluation overhead | scripted fake judges (mock provider) drive deterministic panel outcomes in CI; tier precedence golden vectors (human > panel > solo); override strikes-through, never deletes; calibration stat computes from seeded probes |
| **L4** | Task sources | replay importer (closed-intent picker, `baseRef` pinning, reference metadata); `task-author` role + generated queue + review flow; tags + leaderboard slices; pool-health warnings; holdout masking + reveal audit | replayed task reproduces a closed bug trial in CI (fixture repo); generated tasks blocked from rotation until approved; holdout never appears in proposer-visible fixtures (adversarial test) |
| **L5** | Search | mutation vocabulary + lineage; `sweep:model-downgrade` (then `salary-trim`, `flatten`); envelope + auto-instantiate + out-of-envelope ApprovalGate; `structure-proposer` role + VariantProposal contract + predicted-vs-observed; lineage tree UI; variant composer + diff overlay | downgrade sweep on mock walks the tier ladder and stops at a scripted floor breach, frontier reported; out-of-envelope proposal opens a gate with the draft as payload; lineage renders 20 variants legibly |
| **L6** | Continuous + hardening | cadence-driven trials (runway-courteous, activeHours); restart/redelivery sweeps for in-flight trials; trial timeout/void policy; promotion flow end-to-end (deactuate→apply→re-actuate + receipt); retention for exhibits/verdicts; live smoke (one real trial, one real panel, marked manual) | control-plane restart mid-trial resumes collecting correctly (E6-style audit); a month-long mock soak (compressed clock) leaves a legible lineage; `phase3-debts.md` gains this series' rows |

Each milestone leaves the previous ones' surfaces working; nothing in L1–L4 depends on the proposer existing (the lab-free fallback is a standing requirement, `03` §6).

## 2. Migration

None destructive — the series is additive. New tables only; the team store row gains nullable `experiment_id` (absent = production team; portfolio queries filter on it); `ids.py` gains `ex_ vt_ tk_ tl_ vd_`; `canopy.toml` gains `[experiments]` (`enabled`, `trial_timeout_h = 24`, `exhibit_retention_days = 90`) — defaults inert. No document-schema change: variant blueprints *are* `canopy.team` v2 documents. No dp-surface change at all: **variant agents cannot tell they are in an experiment** — that is invariant-12 hygiene and Goodhart hygiene in one property, and a standing adversarial test.

## 3. API map

| Route | Purpose |
|---|---|
| `POST /api/orgs/{id}/experiments` · `GET /api/orgs/{id}/experiments` | create / list |
| `GET /api/experiments/{id}` | the aggregate (header, roster, policy, envelope, budget) |
| `PUT /api/experiments/{id}` · `POST …/pause·resume·conclude` | config + state |
| `PUT /api/experiments/{id}/rubric` · `GET …/rubric?version=` | new version / read |
| `POST /api/experiments/{id}/rescore` | explicit parallel re-score under a version |
| `POST /api/experiments/{id}/tasks` · `POST …/tasks/{tid}/review` | add / approve-reject |
| `POST /api/experiments/{id}/variants` · `POST …/variants/{vid}/retire·promote` | enroll / govern (promote opens the ApprovalGate) |
| `POST /api/experiments/{id}/trials` | schedule one/N (manual mode) |
| `GET /api/experiments/{id}/leaderboard·lineage·trials` | computed views — no scoring math client-side |
| `GET /api/trials/{id}` · `POST /api/trials/{id}/verdict` | comparison aggregate / human verdict |
| SSE | org streams gain `experiment` event family (trial states, verdicts, promotions) |

## 4. Schema sketches

```sql
CREATE TABLE experiment (id TEXT PRIMARY KEY, org_id TEXT NOT NULL, key TEXT NOT NULL, title TEXT,
  purpose TEXT, state TEXT DEFAULT 'draft', rubric_version INTEGER DEFAULT 1, task_source_json TEXT,
  policy_json TEXT, envelope_json TEXT, budget_json TEXT, baseline_json TEXT,
  memory_policy TEXT DEFAULT 'fresh', pairing TEXT DEFAULT 'concurrent',
  created_at TEXT, updated_at TEXT, UNIQUE(org_id, key));
CREATE TABLE experiment_rubric (experiment_id TEXT, version INTEGER, rubric_json TEXT,
  created_by TEXT, created_at TEXT, PRIMARY KEY (experiment_id, version));
CREATE TABLE experiment_variant (id TEXT PRIMARY KEY, experiment_id TEXT, key TEXT, label TEXT,
  parent_variant_id TEXT, mutation_json TEXT, blueprint_json TEXT, bindings_json TEXT,
  schedule_json TEXT, status TEXT DEFAULT 'candidate', team_id TEXT, created_by TEXT, created_at TEXT);
CREATE TABLE experiment_task (id TEXT PRIMARY KEY, experiment_id TEXT, origin TEXT, state TEXT,
  holdout INTEGER DEFAULT 0, tags_json TEXT, body_json TEXT, created_by TEXT, created_at TEXT);
CREATE TABLE experiment_trial (id TEXT PRIMARY KEY, experiment_id TEXT, task_id TEXT,
  rubric_version INTEGER, pairing TEXT, state TEXT DEFAULT 'pending', capacity_snapshot_json TEXT,
  void_reason TEXT, created_at TEXT, closed_at TEXT);
CREATE TABLE experiment_run (trial_id TEXT, variant_id TEXT, team_id TEXT, intent_id TEXT,
  state TEXT, metrics_json TEXT, PRIMARY KEY (trial_id, variant_id));
CREATE TABLE experiment_verdict (id TEXT PRIMARY KEY, trial_id TEXT, source TEXT, tier TEXT,
  rubric_version INTEGER, scores_json TEXT, preference TEXT, rationale_ref TEXT,
  superseded_by TEXT, created_by TEXT, created_at TEXT);
```

Owner modules per the house pattern: `experiments/{core,probes,judging,search}.py` registering their schemas; `routes/lab.py`.

## 5. Code impact

- **server:** the modules above; `deps.py` wires them; **engine: no semantic changes** — the harness calls existing surfaces (`submit_intent`, memory reset, gate resolution) and reads existing tables; `repos.py` gains `base_ref` on worktree materialization; actuator batch-actuates variant teams (stock actuation, N teams); scheduler treats variant teams as `batch` (forced at team-schedule creation).
- **agent:** none. Variant teams run stock runtimes — the whole point (`01` §9.2, `06` §2's invisibility test).
- **catalog:** `experiment-lab` formation; `evaluator`, `task-author`, `structure-proposer`, `lab-lead` roles with duty→deliverable contracts (VerdictCard, TaskDraft, VariantProposal — all artifacts); `rubricTemplates[]`.
- **ui:** components per `04` §7 / `05` §7; chart-editor read-annotate + diff-overlay mode (the one nontrivial UI lift, shared by composer and variant pages).

## 6. Test plan

Per the four pillars: **deterministic core** — everything through L5 runs on `mock` + fake-CLI; fake judges are scripted VerdictCards; a `FakeClock` threads trial timeouts and cadences (the C-series rule). **Golden vectors** — new families: scoring tables (`02` §4 math), tier precedence, promotion predicates incl. holdout, mutation/lineage integrity, re-score parallelism. **Money-path paranoia extends to scores:** property tests — harvested metrics ≡ ledger/engine ground truth; no verdict without pinned rubric version; supersede never deletes; holdout never reachable from proposer-visible queries (adversarial); variant-team charters/briefs contain no experiment traces (adversarial); guardrail-breached runs score 0 under every rubric. **Two OSes** as always. Exactly one live smoke (L6), manual, per `testing.md` §6.

## 7. Doc-edit impact map (on adoption — not before)

| Doc | Edit |
|---|---|
| `org-roadmap.md` §O5 | "eval harness as QA executor" → pointer here; O5 pulls L1–L3 |
| `execution/target-app.md` §10 | PF-1 twin marked "generalized: the solo baseline, `design/experiments/`" |
| `testing.md` | post-MVP eval row → pointer; new vector families registered |
| `manager-responsibilities.md` | note beside the ⛔: the sanctioned structural-change path (`03` §7) |
| `phases.md` | a fourth line under the three verbs: teams are Built, Actuated, Executed — and **Improved** in the lab; navigation gains the Lab section |
| `domain-model.md` | §Calibration cross-ref ("the active form"); candidate invariant: *experiment subordination — lab output is artifacts; production changes only through governed promotion* (numbering resolved behind invariant 12 and the connectors capability invariant at adoption) |
| `roles.md` / `teams.md` | lab roles + `experiment-lab` formation entries |
| `phase3-debts.md` | gains LAB-D1..D5 |
| root `README.md` | the lab in the feature list and architecture-at-a-glance |

## 8. Debts this series knowingly opens

- **LAB-D1 — imperfect blinding.** Exhibits carry stylistic tells; mitigated by panels, probes, audit, and the UI stating the limit. Sunset: never fully — measured honestly forever.
- **LAB-D2 — statistical crudeness.** Paired win rates + floors + minimum n, no sequential correction; a long-running experiment peeking at every trial inflates false promotion odds. Mitigated by holdout confirmation + human ratification; revisit with Elo/sequential methods when trial counts earn it.
- **LAB-D3 — generated-task validity.** A drifting task-author steers scores; walled by review + replay anchoring + tag balance surfacing. Sunset when generation has a month of accepted-rate history.
- **LAB-D4 — evaluation overhead unbounded a priori.** Judging cost scales with trials × panel; surfaced from L3 (header stat) so the operator prices it; a cap knob if reality demands.
- **LAB-D5 — promotion applies via deactuate→re-actuate.** Inherits D7/D8 (no live structural edits); a promotion mid-flight waits for the team to drain. Sunsets with D7/D8 themselves.

## 9. Definition of done for the series

An operator opens the lab on their maintenance org, seeds it from the production team, and accepts defaults; the solo baseline enrolls itself; twenty replayed-and-generated tasks fill the pool with five held out. The model-downgrade sweep finds that the backend role survives a tier drop and the leaderboard proves it — floors held, −38% cost, 7/9 wins, holdout confirmed — with every number wearing its rubric version, tier, and n. The operator reads two judge rationales, overrules one and watches the calibration stat move, then ratifies the promotion gate; the receipt lands in the org feed and the production team runs cheaper the same day. A hundred trials later the lineage tree still reads at a glance, the retired branches say why they died, evaluation overhead sits on the header where it can be judged, and PF-1's answer — where the org beats one strong session, and where it doesn't — is published continuously, whichever way it falls. All of it demos keyless on `mock` in CI, exactly once live in the release checklist.
