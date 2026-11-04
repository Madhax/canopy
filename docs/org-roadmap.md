# Organization Roadmap — What Canopy Should Be Running

**Status:** Aspirational roadmap (living) · **Date:** 2026-07-26
**Purpose:** the milestone sequence expressed in *organizations*, not features. The A/E-milestones (`actuation/roadmap.md`, `execution/mvp.md` §4) sequence what the platform can do; this document sequences what should be **existing and running** on it — each rung an organization that pulls exactly the capabilities it needs behind a legible outcome. Feature work that no rung pulls is, by definition, not on the critical path.
**Reads with:** `mission.md` (the mission this ladder is the standing acceptance test of — and, since 2026-08-16, the canonical home of this document's standing rules), `archetypes.md` (the palette these orgs draw from), `use-cases.md` (the recipes they instantiate), `risks/` (PF-1, PF-2, U-2, MK-3 — this doc is their standing answer), `execution/target-app.md` §10 (the benchmark discipline every rung inherits).

---

## 1. The principle: Canopy grows by Canopy working on Canopy

The organizations we most want existing are the ones that sustain the project's own organic growth. Not demo orgs — **staff**. The north star: the Canopy repository's bug backlog, feature pipeline, catalog content, documentation, and public voice are each worked by a standing Canopy organization, with the operator (the founder, then maintainers) governing through the same gates, meters, and plan views every user gets.

This principle is the mission run reflexively (`mission.md` §3): the operator approves direction and approves consequences — the fleet produces everything in between. The ladder below is that claim's standing acceptance test, and §5's metrics are its measurement.

Why this ordering beats a market-facing hero-archetype sequence:

- **U-2 (second-session problem) dissolves.** The founder returns daily to the org that is closing their bugs. Retention is not designed; it is structural.
- **PF-1 (economic null hypothesis) gets a living answer.** Every closed issue is a benchmarkable unit — ledger-attributed cost, verified outcome, public PR. The benchmark stops being an event and becomes a feed.
- **PF-2 (catalog quality ceiling) gets a forge.** Role instructions for engineer/QA/triage/writer roles are iterated against real transcripts from real work on a real codebase — then those hardened roles *are* the launch catalog.
- **MK-3 (demo vs retention) inverts.** The public story is not a glowing chart; it is a commit history: *"this PR was produced by a Canopy org for $2.10, reproduced the bug first, passed QA, and a human approved the merge."* Receipts, not theater.

## 2. Standing rules of the ladder

> **Amendment (2026-08-16):** these rules are promoted to mission-level standing commitments — `mission.md` §4 is now their canonical statement, binding every organization Canopy runs, not just this ladder. They remain below in their ladder-specific form; where the two diverge, the mission wins.

1. **The recursion boundary.** Self-hosted orgs edit the codebase **as artifacts** — branches, diffs, proposed PRs. They never touch the running instance they execute on: merge is a governed action resolved by a human, deploy/self-update is not a grant that exists, and the control plane is never in any org's tool surface. The org proposes; the human ratifies; the platform the org runs on only changes when a human ships it.
2. **The trust ladder.** Rungs escalate authority slowly: artifact-only work → PR-proposing work → (much later, if ever) consequential external actions. A rung never starts until the previous rung's acceptance rate makes the escalation boring.
3. **Benchmark discipline.** Every rung publishes its numbers per `target-app.md` §10: cost per closed unit, acceptance rate, rework rounds, human minutes per merged PR. Wins and losses both — the ledger is the product.
4. **Real code runs in real walls.** Reproducing bugs and running Canopy's own test suite is `execute`-class work on effectively untrusted input; O3 onward requires the docker tier (T2) — which deliberately drags A6 forward, exactly where `cli-runtime.md` §8 already wanted it.
5. **Capacity governance precedes unattended operation** (adopted 2026-08-09). No standing-intent org runs unattended on a cadence before the C-series' scheduler and capacity gates exist — an ungoverned fleet drawing on a shared subscription is the failure mode the ladder must not normalize. The C-series is a pre-MVP prerequisite: `design/organizations/07-implementation-plan.md` §0.

## 3. The rungs

| # | Organization | Standing purpose | Status |
|---|---|---|---|
| **O1** | `mvp-pod` — the fixture software team | prove the machinery on `target-app` (MVP-1, as planned — unchanged) | E-series |
| **O2** | `canopy-docs` — the groundskeeper | close documentation issues with proposed PRs | first real-repo org |
| **O3** | `canopy-maintenance` — the bug-close org | read bug reports → reproduce → fix → verify → propose PR | the user-story rung |
| **O4** | `canopy-product` — the feature org | feature requests → spec → implement → verify → propose PR | scope + judgment rung |
| **O5** | `canopy-catalog` — the roles forge | author/refine role instructions; evals as QA | PF-2 as an org |
| **O6** | `canopy-voice` — the build log | devlog/content on a weekly cadence, governed publish | `content-machine`, dogfooded |
| **O7** | `canopy-frontdesk` — community support | triage discussions/questions; KB growth | `support-tier`, dogfooded |
| **O8** | **Canopy Inc.** — the org of orgs | O2–O7 grouped, budgeted, and governed as one portfolio | **realized administratively** — `design/organizations/` |
| **O9+** | the frontier | external customers on the same rungs; physical-world via `human-proxy`; Blueprints/cloning | vision, not promise |

### O2 — `canopy-docs` (the lowest-risk real work)

The same pod shape as MVP-1, re-roled: `tech-writer` + `editor` under a lead, reading GitHub issues labeled `docs`, proposing documentation PRs. No test suite to run, no compute beyond the workspace — but it forces the **entire external plumbing** the bigger rungs need, at minimum stakes: the GitHub grant pack via the `mcp` executor (`agent-envelope.md` §3.6, used exactly as designed — curated grants, proxy-brokered, credentials in the Secret Store), the remote-git extension of E4's executor (push branch, open PR — a **governed action**: every public PR is an ApprovalGate owned by the operator), and issue ingestion via a Cadence ("every morning, review new docs issues") — polling first, webhooks later. A wrong docs PR costs nothing; the plumbing it proves carries everything after it.

**Seeded by `execution/mvp.md` E8** — the MVP capstone runs this org's first unit by hand (operator-curated issue in, human-pushed PR out) before any plumbing exists, so O2 proper starts from a proven flow and only adds the machinery: the GitHub pack, the remote-git executor, and the ingestion cadence.

**Pulls:** GitHub MCP grant pack · remote git + PR-create executor (governed) · ingestion cadence. **Done when:** five docs PRs merged; cost per PR published.

### O3 — `canopy-maintenance` (the bug-close org — the rung this roadmap exists for)

Formation (all catalog roles): `engineering-lead` managing a **triager** (`support-engineer`: reads the issue, attempts reproduction, discharges a `ReproReport` — reproducible with failing test, or needs-info, or invalid), a `backend-engineer` (fix on a `canopy/*` branch behind a verify-dep on the repro), and a `qa-engineer` (full suite + the new regression test; `TestReport`). The lead's acceptance triggers the governed PR proposal; a human merges. Issues where reproduction fails become `needs-info` comments — also governed, also attested.

The standing intent — *"drive the open bug backlog toward zero"* — makes this the first real **standing-intent** org, with the derived Milestone view finally earning its keep (backlog burn-down is the milestone axis). Reproduction means running Canopy's own test suite against attacker-shaped input: **T2 docker is the floor**, no `allow_trusted_local` waiver on this rung.

**Pulls:** docker tier (A6, promoted) · repro-executor pattern (run suite, capture failing test) · standing intents + milestones in anger · issue→intent ingestion. **Done when:** ten bug PRs merged; median cost per closed bug and rework rate published; the triage verdict distribution (fixed / needs-info / invalid) looks like a real maintainer's.

### O4 — `canopy-product` (the feature org)

Same skeleton, bigger cognition: feature requests arrive, a **spec stage** precedes code (a design-doc artifact the operator plan-reviews — the staged-delegation card doing its highest-value work), then implement → verify → proposed PR. This rung is where the judgment machinery gets exercised for real: scope-divergence (X2) finds its first honest tripwires, budgets meet genuinely variable task sizes, and the ClarificationGate earns its keep on underspecified requests ("what should the flag default to?" routes back as a comment on the issue — governed, like all outward speech).

**Pulls:** X2 calibration data · larger envelope/salary tuning · spec-artifact conventions. **Done when:** three merged features that began as external-shaped requests; cost-per-feature vs. a bare-session baseline published (PF-1's harder test).

### O5 — `canopy-catalog` (the roles forge)

Roles are data — so improving them is *authoring work an org can do*. Input: transcripts and rejection notes from O2–O4 (the platform already records everything needed); output: proposed catalog PRs refining role instructions, salary defaults, and effort envelopes. QA here is a **rubric-scored experiment** (`design/experiments/`, adopted 2026-08-09): "a candidate role revision must beat the incumbent before the lead proposes it" is exactly a champion–challenger comparison under a versioned rubric with floors — so O5's eval bar is the experiment bench's API (L1 substrate, L2 rubric engine + promotion predicate, L3 judged panel), not a bespoke tool. This is `risks/problem-fit.md` PF-2's transcript→instruction feedback loop, staffed — and it is the named customer that pulls the L-series onto the critical path (`design/experiments/06` §0).

**Pulls:** experiments L1–L3 (the eval harness as product surface) · catalog-PR conventions. **Done when:** a role revision authored by this org measurably improves O3's acceptance rate — proven on the leaderboard before the lead proposes it.

### O6 — `canopy-voice` and O7 — `canopy-frontdesk`

The original hero archetypes return — as Canopy's own departments. `canopy-voice` is `content-machine` on a weekly cadence: build-log drafts from the week's merged PRs and ledger stats (the receipts write the marketing), editor gate, governed publish (MK-4's one-channel plan, run by an org). `canopy-frontdesk` is `support-tier` on GitHub Discussions: triage, answer with KB citations, escalate real bugs *into O3's intake* — the first org-to-org handoff, and the deliberate rehearsal for O8. Both are attestation-heavy, low-blast-radius, and pull work pools when volume justifies (`sc-2`'s fungible-role answer, arriving when a rung actually needs it).

### O8 — Canopy Inc. (the org of orgs)

> **Amendment (2026-08-09): realized administratively by `design/organizations/`.** This rung imagined mounting O2–O7 under one root chart. The adopted organizations series delivers the substance another way: the teams share one **Organization** (`canopy-inc`) with an org budget, capacity shares, and a portfolio home that makes their collective health legible — without manufacturing a coordination chart nobody needs yet. Chart-level mounting remains available for the day inter-team work actually needs an edge (`design/organizations/01` §8.2); the O7→O3 escalation handoff stays the rehearsal for that door. The rungs O2–O7 themselves are unaffected.

The original vision, for the record: O2–O7 mounted as child teams under one root with the standing intent *"grow Canopy"* — the operator governing a company rather than a single team. The chart on the README stops being an illustration: it is the actual, running structure of the project, inspectable by anyone, its costs public. That acceptance test of the whole thesis — *the chart is the system*, demonstrated by the system that builds it — now runs through the portfolio surfaces.

### O9+ — the frontier (vision, not promise)

External customers running the hardened rungs on their own repos and backlogs; the consequential-action orgs (`sales-pod`-class) once the trust ladder reaches them; physical-world archetypes via the `human-proxy` runtime; Blueprints making O3 cloneable as a product ("a maintenance org for *your* repo" — use-case #31, finally). Kept per PF-3's framing: labeled vision, priced as marketing imagery, promised to no one.

## 4. Capability pull matrix (what each rung drags onto the critical path)

| Capability | Pulled by | Feeds existing milestone |
|---|---|---|
| GitHub MCP grant pack (curated, proxy-brokered) | O2 | envelope §3.6's first real executor |
| Remote git + PR-create as governed action | O2 | extends E4's local git executor |
| Ingestion cadence (issues → intents; webhooks later) | O2/O3 | engine §4 cadences + a small poll executor |
| Docker tier T2, no trusted-local waiver | O3 | A6, promoted ahead of polish (per cli-runtime §8) |
| Standing intents + derived Milestones | O3 | post-MVP milestone view, now with a customer |
| X2 scope-divergence calibration | O4 | manager-responsibilities X2, with real data |
| Experiment bench L1–L3 (substrate, rubric engine, judged panel) | O5 | `design/experiments/` — the post-MVP series, pulled by this rung |
| Work pools | O6/O7 (volume-dependent) | roadmap's pools row, pulled only when needed |
| Org-to-org handoff, nested-org operations | O7/O8 | domain's nesting, exercised for real |

## 5. What "existing and running" means (the metrics per rung)

A rung is not "supported" when it is expressible — that bar is already met by 30 of 31 use cases. A rung exists when its org has **run unattended on a cadence for a month** with: acceptance rate the operator stopped watching nervously, cost-per-unit published, human minutes per merged PR trending down, and zero recursion-boundary violations (nothing merged, published, or executed without its gate). The ledger computes all of it; this document just commits us to reading it out loud.

*Amendment (2026-08-16):* this bar now has an instrument — `design/unattended/06-readiness-and-soak.md`: the per-team readiness checklist, the compressed-clock fleet soak, and the posture ladder whose **P2 (unattended-month)** is exactly this paragraph, entered by checklist and boredom rather than by hope.
