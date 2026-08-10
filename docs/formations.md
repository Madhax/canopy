# Canopy Formations

*(This file was `teams.md` until the 2026-08 vocabulary correction — `design/organizations/01` — renamed the derived manager-plus-reports grouping to **Pod** and freed "Team" for the chart unit.)*

A **formation** is a reusable subtree — a manager role plus member roles, pre-wired with the artifact flow and dependency shape that makes the pod work. Formations are the middle layer between roles and archetypes: an archetype (see `archetypes.md`) composes one or more formations under its root; a formation composes roles (see `roles.md`).

In domain-model terms, a formation is a blueprint fragment: dropping one into the editor creates the manager node, its report nodes, and the standing dependency/artifact-routing pattern between them — a formation *stamps a pod*. Pods at runtime are still *derived* (a manager plus its reports, `domain-model.md` §Pod); the formation is just the recipe.

Each formation has a stable `key`, the roles it wires (by role key), the canonical artifact flow, and the intents it's built to absorb.

Dependency edges carry a **resolution policy** (`resolveOn`, per `domain-model.md` §Dependency): **verify** edges (`delivered`) unlock the moment the upstream work is *submitted* — the downstream role *is* the review (QA, fact-check, inspection, eval) — while **consume** edges (`accepted`, the default) wait for the manager's sign-off before the downstream role builds on the output. The policy is part of the formation's wiring, like the edge itself; the annotations below mark the non-default (verify) edges.

---

## `product-engineering-pod`

**Manager:** `engineering-lead` · **Members:** `backend-engineer`, `frontend-engineer`, `qa-engineer`
**Purpose:** Ship product features end-to-end with built-in verification.
**Artifact flow:** brief → engineers produce `PullRequest` → DependencyGate opens QA → `TestReport` → lead accepts both → publishes upward.
**Built-in dependencies:** QA assignments always depend on the implementing engineer's PR (**verify** — unlocks at submission; the lead's acceptance waits for the `TestReport`).
**Absorbs intents like:** "Add multi-tenant billing," "Fix the checkout race condition."

## `docs-pod`

**Manager:** `engineering-lead` · **Members:** `tech-writer`, `editor`
**Purpose:** Close documentation issues with reviewed, verifiable doc changes.
**Artifact flow:** brief → writer `PullRequest` (docs-only branch) → editor `EditedDraft` review → lead accepts both → publishes upward.
**Built-in dependencies:** the editor's review always depends on the writer's submitted PR (**verify** — the review starts at submission; the lead's acceptance waits for the `EditedDraft`).
**Distinctive:** the writer's `docs.repo.write` grant is tier-1 — documentation artifacts are never executed downstream (unlike code, which feeds `test.run`), so the pod actuates on the subprocess tier with no trusted-local waiver. Seeded by `execution/mvp.md` E8 (Canopy working on Canopy); grows into `org-roadmap.md` O2's `canopy-docs`.
**Absorbs intents like:** "Document the actuation readiness codes," "Rewrite the quickstart for the new runtime."

## `incident-response-squad`

**Manager:** `sre-lead` · **Members:** `incident-responder`, `platform-engineer`, `tech-writer`
**Purpose:** Restore service fast, then convert the pain into prevention.
**Artifact flow:** alert → responder `TriageNote` → recovery `RecoveryAttestation` → postmortem `IncidentPostmortem` → tech-writer `RunbookDoc`.
**Distinctive:** driven by InterventionGates and escalations rather than planned intents; the runbook assignment depends on the accepted postmortem.
**Absorbs intents like:** "Production is down," "Harden the deploy pipeline after last week's outage."

## `platform-pod`

**Manager:** `engineering-lead` · **Members:** `platform-engineer`, `cloud-architect`, `security-engineer`
**Purpose:** Internal developer platform — CI/CD, infra, paved roads.
**Artifact flow:** `InfraSpec` → implementation `PullRequest` → security `SecurityReport` gate → release.
**Distinctive:** its "customers" are other pods; requests arrive as escalations from peer pods resolved via brokered channels.

## `design-studio-cell`

**Manager:** `design-lead` · **Members:** `product-designer`, `ux-researcher`, `content-designer`
**Purpose:** Turn product questions into validated, buildable designs.
**Artifact flow:** `ResearchPlan` → `ResearchReport` → DependencyGate → `DesignSpec` + `CopyDoc` → lead review → publish to engineering.
**Absorbs intents like:** "Design the onboarding flow," "Why are users dropping at step 3?"

## `data-insights-cell`

**Manager:** `team-lead` · **Members:** `data-engineer`, `data-analyst`, `data-scientist`
**Purpose:** Answer questions with data; keep the data trustworthy enough to ask.
**Artifact flow:** question brief → engineer `PullRequest` (pipeline) → analyst `Dashboard`/`AnalysisReport` → scientist `FindingsReport` for the hard questions.
**Absorbs intents like:** "Build the retention dashboard," "Did the pricing change work?"

## `ml-delivery-pod`

**Manager:** `engineering-lead` · **Members:** `ml-engineer`, `data-engineer`, `data-scientist`, `qa-engineer`
**Purpose:** Train, evaluate, and ship models with evidence.
**Artifact flow:** `ExperimentDesign` → `DataQualityReport` → `ModelCard` → `EvalReport` (QA-style gate) → deployment PR.
**Distinctive:** the eval's dependency on the model is **verify** (it starts on the submitted `ModelCard`), while deployment's dependency on the eval is consume — nothing deploys before the `EvalReport` is accepted. Verification is structural, not optional.

## `sales-pod`

**Manager:** `sales-director` · **Members:** `sales-development-rep`, `account-executive`, `solutions-engineer`
**Purpose:** Take a territory from cold to closed.
**Artifact flow:** SDR `QualifiedLead` → DependencyGate → AE `Proposal` → `SignedContract`; SE feeds `QuestionnaireResponse`/`DemoAttestation` into the AE's stages.
**Distinctive:** heaviest ActionAttestation usage in the catalog (calls, meetings, demos); discount decisions surface as ApprovalGates to the director.

## `support-tier`

**Manager:** `team-lead` · **Members:** `support-agent` ×N, `support-engineer`, `knowledge-base-writer`
**Purpose:** Resolve customer issues at the cheapest competent level, and never solve the same problem twice.
**Artifact flow:** ticket → agent `ResolutionAttestation`, or `EscalationPackage` → engineer `DiagnosisReport` → KB writer `KBArticle`.
**Distinctive:** the KB assignment depends on any accepted diagnosis — institutionalizing the fix is built into the formation, not left to memory.

## `content-machine`

**Manager:** `marketing-lead` · **Members:** `content-writer`, `editor`, `social-media-manager`, `growth-analyst`
**Purpose:** Produce, polish, distribute, and measure content on a cadence.
**Artifact flow:** `CampaignBrief` → writer `ContentPiece` → editor `EditedDraft` (quality gate) → `PublishAttestation` → analyst `EngagementReport`.
**Distinctive:** naturally cadence-driven (weekly newsletter, posting schedule) rather than intent-driven.

## `recruiting-loop`

**Manager:** `recruiter` · **Members:** `sourcer`, `interview-coordinator`
**Purpose:** Fill an open role from sourcing to signed offer.
**Artifact flow:** `CandidateList` → `ScreenNote` → coordinator `BookingConfirmation` + `FeedbackPacket` → recruiter `OfferPacket`.
**Distinctive:** offer extension is a governed action (ApprovalGate to the hiring manager/user) — consent before the consequential act.

## `research-cell`

**Manager:** `principal-investigator` · **Members:** `literature-analyst`, `data-scientist`, `research-assistant`, `manuscript-drafter`
**Purpose:** Produce publishable knowledge.
**Artifact flow:** `ResearchBrief` → parallel `LitReview` + `Dataset`/`DataModel` → DependencyGate → `Manuscript` → PI review.
**Distinctive:** the drafter is gated on *both* upstream artifacts (consume — the `Manuscript` builds only on accepted inputs); anomalous findings route back to the PI as escalations, not silent hypothesis drift.

## `franchise-shift`

**Manager:** `store-manager` · **Members:** `cashier`, `line-cook` (grill), `line-cook` (fry), `expeditor`
**Purpose:** High-throughput standardized physical service.
**Artifact flow:** `OrderTicket` fans out to stations in parallel → `StationAttestation`s → expeditor `OrderCompleteAttestation`.
**Distinctive:** hundreds of tiny Assignment trees per shift; equipment faults surface as stall interventions to the manager. Stress-tests queue policy and WIP caps more than any other formation.

## `build-crew`

**Manager:** `general-contractor` · **Members:** `carpenter`, `electrician`, `site-inspector`
**Purpose:** Sequence physical trades where dependencies are physics, not preference.
**Artifact flow:** `WorkSchedule` → carpenter `BuildAttestation` → DependencyGate (consume — trades build on signed-off work) → electrician `WiringAttestation` → inspector `InspectionReport` (**verify** — inspection starts at submission; ApprovalGate) → GC acceptance.

## `newsdesk`

**Manager:** `managing-editor` · **Members:** `reporter`, `fact-checker`, `editor`
**Purpose:** Investigate and publish stories that survive scrutiny.
**Artifact flow:** `StoryBrief` → reporter `StoryDraft` → parallel `FactCheckReport` + `EditedDraft` (both **verify** edges on the submitted draft) → editor-in-chief ApprovalGate → publish.
**Distinctive:** publication is a governed action; the fact-check dependency cannot be waived by the reporter — only by the managing editor, visibly.

## `event-crew`

**Manager:** `event-producer` · **Members:** `coordinator`, `stage-manager`, `av-technician`, `content-writer`
**Purpose:** Take an event from concept through day-of execution to follow-up.
**Artifact flow:** `EventRunSheet` → coordinator `BookingConfirmation`s (permits/venue behind ApprovalGates — real money) → day-of `ShowAttestation` + `RecordingFile` → writer post-event `ContentPiece`.

## `fundraising-office`

**Manager:** `development-director` · **Members:** `grant-writer`, `volunteer-coordinator`, `content-writer`
**Purpose:** Fund and staff a mission.
**Artifact flow:** `FundraisingPlan` → parallel `GrantProposal`s + donor `MeetingAttestation`s + `VolunteerRoster` → quarterly `StatusReport` rollup.

## `experiment-lab` *(lands with the L-series — `design/experiments/`)*

**Manager:** `lab-lead` · **Members:** `evaluator` ×N (from L3; `task-author` joins at L4, `structure-proposer` at L5)
**Purpose:** Staff the experiment bench — blinded pairwise verdicts on trial exhibits, reviewed task generation, and variant proposals for the search policy.
**Artifact flow:** anonymized exhibits → evaluator `VerdictCard`s (panel-aggregated) · task queue → `TaskDraft`s (operator-reviewed) · lineage + envelope → `VariantProposal`s.
**Distinctive:** every output is an artifact; the lab holds no authority over production teams — instantiating variants and promoting a champion are platform actions behind operator-ratified gates (`design/experiments/03` §7). Judges never see team identities or costs; the proposer never sees holdout tasks.
