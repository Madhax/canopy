# Manager Responsibilities — Coverage Analysis and Proposed Extensions

**Status:** Proposal (gap analysis + design) · **Date:** 2026-07-06
**Reads with:** `domain-model.md` (authoritative for all current abstractions and invariants), `archetypes.md`, `roles.md`, `teams.md`, `actuation/phase3-debts.md` (extend-don't-mutate discipline), `risks/usefulness.md` U-3, `risks/scalability.md` SC-2/SC-4, `risks/problem-fit.md` PF-2.
**What this doc is:** an enumeration of every responsibility a manager holds across the catalog's archetypes, a verdict on whether the current domain model supports each, and — for the gaps — a deliberately small set of proposed extensions. Nothing here changes `domain-model.md`; accepted proposals should be folded into it and this section of the doc retired.

---

## 1. Method

A "manager" in Canopy is any Agent with reports: the `chief-executive` at an org root, an `engineering-lead` over a pod, a `store-manager` over a shift, a `managing-editor` over a newsdesk. Management is not a separate mechanism — it is what the work layer looks like from the node above: creating Assignments, declaring Dependencies, issuing Directives, resolving Gates, accepting Deliverables.

The taxonomy below consolidates what managers do across all 26 archetypes into six families of responsibilities. Consolidation is deliberate: "prevent scope creep" is the same duty whether the report is a `backend-engineer` drifting into platform work, an agency creative absorbing unpaid client scope, or a `data-scientist` drifting off-hypothesis — so it appears once, with archetype manifestations, rather than 26 times.

Verdicts:

- ✅ **Supported** — expressible today with the mechanisms in `domain-model.md`.
- ⚠️ **Partial** — the ingredients exist but a triggering, access, or policy piece is missing or unspecified.
- ❌ **Gap** — not expressible; needs an extension.
- ⛔ **Excluded by design** — deliberately not a manager power; noted so the boundary is explicit rather than accidental.

---

## 2. The taxonomy

### Family A — Direct: decompose and delegate

| # | Responsibility | Archetype manifestations | Verdict | Mechanism / gap |
|---|---|---|---|---|
| A1 | Decompose an Intent into child Assignments with briefs | `management-consultancy`: the issue tree *is* the assignment tree; `curriculum-studio`: the `CourseOutline` becomes the delegation plan; every archetype root | ✅ | Assignment creation along reporting edges (inv. 4); brief carries cited Artifact refs |
| A2 | Sequence the work | `build-crew`: electrician after carpenter (physics); `ml-delivery-pod`: eval before deploy; `design-studio-cell`: research gates design | ✅ | Dependency, declared by the manager at delegation time, siblings only |
| A3 | Define what "done" looks like per delegation | `newsroom`: a story that survives fact-check; `law-practice`: acceptance *is* the product | ✅ | Deliverable contract on every Assignment; acceptance is contract-based |
| A4 | Shape how a report operates for one engagement | `creative-agency`: "use the client's brand system"; `general-contracting`: "to code, permit attached" | ✅ | Directive, Assignment-scoped (see §4 R4 for a mid-flight clarification) |
| A5 | Set standing team norms | `product-engineering`: engineering standards; `medical-clinic`: care protocols; `content-machine`: voice and style rules | ❌ | Directives die with the Assignment; a manager cannot express "always, for this team." → **X4** |
| A6 | Route work to the right role | `support-tier`: cheapest competent level first; any lead choosing implementer vs. reviewer | ✅ | Manager judgment over RoleTemplate responsibilities (catalog data); delegation is addressed, not pooled |

### Family B — Control: scope and trajectory

The family motivating this document. A manager delegates a problem; in executing it the report may drift into work suited to another role, another team, or work that shouldn't be done at all.

| # | Responsibility | Archetype manifestations | Verdict | Mechanism / gap |
|---|---|---|---|---|
| B1 | Review a report's plan before it burns budget | `applied-ml`: a training run that eats triple its envelope should have been reviewed *before* launch; `general-contracting`: the GC signs off the `WorkSchedule` before trades mobilize | ❌ | The lifecycle runs `planning → executing` with no consent point. The Plan is observable, but observation is not a checkpoint. → **X3** |
| B2 | Detect scope creep | `product-engineering`: engineer building CI tooling that belongs to `platform-pod`; `creative-agency`: creatives silently absorbing client re-scopes; `research-cell`: hypothesis drift | ⚠️ | The raw material exists — Plans are versioned, Steps record deltas, artifact types are visible — but all four intervention triggers are economic (budget, envelope, stall). Work that is *on budget but off brief* fires nothing. → **X2** |
| B3 | Interrupt and correct in-flight work | Any archetype: "stop — that's not what I asked for"; `newsroom`: managing editor pulls a reporter off an angle mid-investigation | ❌ | Every Gate today is opened by the report (clarification, escalation), the structure (dependency), or the platform (intervention). The manager — the one node whose job is judgment — cannot open one. → **X1** |
| B4 | Kill work that should not happen | `newsroom`: the story doesn't hold — killing it is success; `legal-compliance-desk`: halt on regulatory exposure | ⚠️ | `cancelled` exists as a terminal state, but the manager can only reach it at a gate or at acceptance — not mid-execution on their own judgment. → **X1** |
| B5 | Re-scope mid-flight when the world changes | `creative-agency`: client changed their mind mid-round; `enterprise-sales`: deal terms shifted | ⚠️ | Brief revision exists only as a ClarificationGate resolution (report-initiated) or a rework round (post-rejection). No manager-initiated path while `executing`. → **X1** (redirect), funded by the existing brief-version rework rule |
| B6 | Keep reports inside their capability lane | `medical-clinic`: only physicians make care decisions; `franchise-operation`: stations don't improvise the menu | ✅ | Tool grants are role-bound and platform-held (inv. 10); governed actions require consent (inv. 9); workspace isolation (inv. 2). Capability is fenced — X2 fences *effort* the same way |

### Family C — Monitor: progress and reporting

| # | Responsibility | Archetype manifestations | Verdict | Mechanism / gap |
|---|---|---|---|---|
| C1 | Observe the current work trajectory of all reports | Every archetype — the user's "look at the current work trajectory for all reports" | ⚠️ | The derived progress view (stage cursors, actuals-vs-envelope, Assignment → Plan → Stage → Step → SpendEvent drill-down) is designed as "the manager's-eye view" — but the docs only ever hand it to the *user* in the editor. Whether a manager *Agent* can programmatically read it is unstated. → **R1** |
| C2 | Detect stuck or overrunning work | `franchise-shift`: fry vat down → stall; `applied-ml`: runaway training | ✅ | Intervention triggers 1–4 (warn, hard-stop, envelope overrun, stall), routed manager-first with bounded auto-resolution |
| C3 | Proactively review, not just react | `site-reliability`: daily load review; `finance-back-office`: the close rhythm | ✅ | Cadence at any node; RoleTemplates ship defaults (manager weekly sync). A "review my reports' trajectories" cadence composes from Cadence + R1 — no new mechanism |
| C4 | Compile status upward | Use-case #30: daily StatusReport; `chief-of-staff` role | ✅ | Cadence-generated episodic Intents; rollup is derived, not stored |
| C5 | Track milestones and risk | `event-production`: `at_risk` derived backward from an immovable date; `management-consultancy`: the six-week clock | ✅ | Milestones derived from Deliverable acceptance and in-flight estimates |
| C6 | Spot structural problems in the org itself | `platform-engineering`: every pod keeps getting introduced → grow the pod (Conway's law); `support-tier`: queue depth behind a node | ✅ | Queue depth, long-open Gates, channel telemetry surfaced as re-org suggestions |

### Family D — Quality: acceptance and standards

| # | Responsibility | Archetype manifestations | Verdict | Mechanism / gap |
|---|---|---|---|---|
| D1 | Accept or reject deliverables against the contract | `law-practice`: counsel reviews everything; every acceptance edge | ✅ | Manager-granted `accepted`; rejection returns to `planning` |
| D2 | Fund rework fairly | `product-engineering`: failed E2E burns the engineer's meter; re-scope burns the manager's | ✅ | Rework funding follows brief versions — quality failure stays the report's cost, re-scoping surfaces as the manager's, one level up |
| D3 | Wire verification into the structure | `newsdesk`: fact-check cannot be waived silently; `ml-delivery-pod`: eval gates deploy; `build-crew`: inspection before acceptance | ✅ | Formation-shaped Dependencies; "we skipped research" is a visible manager act, not a quiet default |
| D4 | Calibrate review depth to stakes | `ecommerce-fulfillment`: spot-check high-volume attestations; `law-practice`: full review always | ⚠️ | Acceptance today is implicitly full-review. `risks/scalability.md` SC-2 already proposes the fix — an acceptance-policy knob (full / spot-check / contract-shape-only) per formation. A policy parameter, not a new abstraction; adopt it |
| D5 | Enforce standards of *how* work is done | `product-engineering`: design-system compliance; `medical-clinic`: protocol adherence | ⚠️ | Per-engagement: ✅ Directives. Standing: ❌ same gap as A5. → **X4** |

### Family E — Unblock: gates and coordination

The best-covered family — the current model was visibly designed around it.

| # | Responsibility | Archetype manifestations | Verdict | Mechanism / gap |
|---|---|---|---|---|
| E1 | Fix defective briefs | Any archetype; catching it at intake costs a sliver, at rejection the whole attempt | ✅ | ClarificationGate; versioned briefs drive rework funding |
| E2 | Answer questions above a report's pay grade | `research-cell`: anomaly contradicts hypothesis → PI; `enterprise-sales`: discount authority | ✅ | EscalationGate; resolution is an answer, refs, a grant, or an introduction |
| E3 | Consent to consequential actions | `growth-marketing`: publishing; `recruiting-loop`: offer extension; `medical-clinic`: consequential orders | ✅ | Governed actions → ApprovalGate before, ActionAttestation after (inv. 9) |
| E4 | Grant budget top-ups | `site-reliability`: cloud spend; any hard-stop | ✅ | ApprovalGate within granted limits, else user; bounded auto-resolution (SC-4 makes this the attention-scaling mechanism) |
| E5 | Broker cross-team access | `enterprise-sales`: AE introduced to a cloud architect; `platform-engineering`: requests arrive as escalations | ✅ | Cross-team grants + brokered channels — manager-granted, Assignment-scoped, expiring, audited |
| E6 | Escalate beyond own authority | All: intervention routes manager-first, then user | ✅ | Gate ownership chains upward |

### Family F — Resource: budget, load, and people

| # | Responsibility | Archetype manifestations | Verdict | Mechanism / gap |
|---|---|---|---|---|
| F1 | Fund work and adjust allowances | Everywhere | ✅ | Salary → BudgetMeter per Assignment; visible manager overrides for known-large tasks |
| F2 | Prioritize a report's queue | `franchise-shift`: the rush order jumps the queue; `support-tier`: SEV-1 before backlog | ⚠️ | Queue policy is an acknowledged open item in `domain-model.md`. → **R3** resolves it |
| F3 | Rebalance load across reports | `support-tier`: agent swamped, peer idle; any bottleneck where a *report*, not the structure, is the constraint | ⚠️ | "Reassign" is named in the user's gate-resolution set but has no defined semantics — an Assignment binds one Agent at creation. → **R2** defines it, **X1** provides the entry point |
| F4 | Evaluate report performance over time | Any archetype: chronic rejection, chronic overrun | ⚠️ | Fully *derivable* — acceptance rate, envelope adherence, rework count, escalation frequency are all in existing objects. Needs only a derived scorecard view (presentation, not domain). The *remedy* is correctly user-only: memory reset / replacement is "backfilling the position" |
| F5 | Change the team — hire, restructure, re-role | `talent-acquisition` gestures at future self-hiring | ⛔ | Deliberate boundary: only the user, through the editor, changes the chart. Managers *surface evidence* (queue depth, repeat introductions, F4 scorecards); the user acts. Keep it that way — an org that rewires itself under a standing Intent is a different, riskier product |

**Coverage summary:** 30 responsibilities — 18 ✅, 8 ⚠️, 3 ❌, 1 ⛔. The supported set clusters in delegation, gates, and economics; every gap clusters in one theme: **the manager's authority during a report's execution**. The current model gives managers complete authority at the *edges* of an Assignment (briefing, gating, acceptance) and none in the *middle*.

---

## 3. The gaps, consolidated

| Gap | What's missing | Blocks | Resolved by |
|---|---|---|---|
| **G1** | Manager-initiated suspension and correction of in-flight work | B3, B4, B5, F3 | X1 |
| **G2** | A scope/drift intervention trigger — all four current triggers are economic | B2 | X2 |
| **G3** | A consent point between planning and spending | B1 | X3 |
| **G4** | Standing, team-scoped behavioral rules | A5, D5 | X4 |
| **G5** | Unspecified mechanics: manager-agent telemetry access, reassignment semantics, queue priority | C1, F3, F2 | R1, R2, R3 |

---

## 4. Proposed extensions

**Design rule:** extend existing abstractions; add no new object kinds where an existing one generalizes. This follows the `phase3-debts.md` discipline (extend shapes, never mutate them) and keeps the abstraction count where `domain-model.md` left it: the Gate taxonomy stays at five kinds, the intervention-trigger list grows by one entry, the "governed" marker generalizes, and one small new record type (the standing directive) is added because nothing existing can carry it.

### X1 — Judgment-opened InterventionGate

**Change:** an InterventionGate may be opened not only by the platform (triggers) but **by an authority's judgment**: the Assignment's issuing manager, any transitive manager above it, or the user, on any Assignment in their subtree, at any time.

**Mechanics.** The halt request is honored at the next Step boundary — exactly where the meter check already sits, so interruption is mechanical, not a request politely made to an LLM (the same argument as invariant 7). Standard gate semantics apply unchanged: workspace preserved, the Agent releases to work its queue, resolution resumes at front-of-queue.

**Resolution set** (formalizing and extending the set `domain-model.md` already sketches for the user — "raise the meter, narrow the brief, reassign, answer, or cancel"):

- **Resume** — optionally with an answer or note; the false-alarm path must be cheap.
- **Redirect** — a revised brief. Briefs are already versioned, so the existing rework-funding rule applies with no modification: if the manager narrows a brief because *they* re-scoped, the delta funds from the parent's meter; if the brief stands and the report drifted, everything already burned stays visibly on the original meter — drift is expensive and attributed, which is the point.
- **Constrain** — inject or amend a Directive mid-flight (see R4).
- **Reassign** — cancel-with-continuation to another report (R2).
- **Top up** — raise the meter, within the manager's granted limits, else ApprovalGate to the user (unchanged rules).
- **Cancel** — terminal, the B4 case.

**Why not a sixth Gate kind.** The gate's meaning is identical — "an authority decided this work needs a remedy before it continues" — only the *detector* differs (a threshold vs. a judgment). Same owner chain, same observability, same resolution set. The kind taxonomy stays at five; the gate record gains an `opened_by` (trigger | manager | user).

### X2 — Scope-divergence trigger (intervention trigger #5)

**Change:** add a fifth intervention trigger alongside budget-warn, hard-stop, envelope-overrun, and stall:

5. **Scope divergence** — the work is on budget but off brief. Framework-observed signals, in escalating order of confidence:
   - **Plan expansion** — a Plan revision adds stages or grows advisory sizing past a calibrated tolerance. Plan revisions are already versioned and visible; this makes the scope-creep tell a tripwire instead of something a human might notice.
   - **Contract-foreign deltas** — Steps producing or revising artifacts whose type appears nowhere in the Assignment's Deliverable contract or brief. The engineer whose steps start emitting `ToolingRelease`-shaped output against a `PullRequest` contract trips this mechanically.
   - **Advisory drift check** (optional, platform-run) — a cheap periodic comparison of recent Step deltas against the brief, producing a flag, never an automatic halt. Labeled advisory because it is a model judgment, unlike the two mechanical signals above.

The trigger opens an ordinary InterventionGate routed manager-first with bounded auto-resolution, like every other trigger. Goodhart-proofing is inherited: all signals come from framework-recorded facts (plan versions, step deltas, artifact types) — an agent cannot pad or hide its own tripwire, for the same reason it cannot set its own envelopes.

**Division of labor with B6:** tool grants fence what a report *can do*; scope divergence fences what it *spends effort on*. Both are needed — no tool grant stops an agent from writing the wrong documents with the tools it legitimately holds.

### X3 — Checkpoints: governed transitions

**Change:** generalize the **governed** marker. Today a Responsibility may mark *actions* as governed (consent before consequence). Additionally allow a brief or Directive to mark *lifecycle transitions* as governed — most importantly `planning → executing` (**plan review**), and optionally named PlanStage boundaries.

Reaching a governed transition opens an ordinary **ApprovalGate** owned by the issuing manager (the user, for a root Assignment). Approval semantics are exactly the existing ones: consent resumes; **denial is a prohibition, not a rework request** — the agent must re-plan around the denied plan or the Assignment is cancelled. No new gate kind, no new lifecycle state: `gated` at the boundary, like any other approval.

**Defaults.** A RoleTemplate or Salary may declare "plan review required when the meter exceeds N" — so expensive work gets reviewed by construction and cheap work flows uninterrupted. Two existing designs slot in as instances of this one mechanism: `risks/usefulness.md` U-3's "human-approved delegation" (a plan-review checkpoint on the root Assignment — the proposed decomposition *is* the root's plan) and the review patterns archetypes already reach for structurally (`build-crew`'s inspection, `newsdesk`'s publication approval).

**The three controls compose:** X3 is consent *before* spend (proactive), X2 is a tripwire *during* spend (automatic), X1 is judgment *at any time* (reactive). All three discharge through existing gate machinery.

### X4 — Standing Directives

**Change:** a manager may register a **standing Directive**: a Directive template scoped to its team (all reports, or a subset by role or by node) that auto-attaches to every future Assignment the manager creates within scope. Each attachment is an ordinary Assignment-scoped Directive; the standing record itself is a small new object owned by the manager node.

**What this is not.** It does not mutate any Agent — the Agent object, its RoleTemplate binding, and its extensions are untouched, so "only the user, through the editor, permanently changes an Agent" survives intact. It is not chart structure either: standing directives are work-layer state, excluded from the Organization document like all in-flight work, but **rendered in the operations view** so the running org never has invisible rules.

**Lifecycle:** created and revoked by the manager (or user); optionally expiring; every attachment audited. **Promotion path:** a standing Directive that persists is a signal — the user may promote it into the Agent's permanent `extensions` (an editor act) or upstream into the RoleTemplate (a catalog contribution). This gives `risks/problem-fit.md` PF-2's transcript→instruction feedback loop its concrete mechanism: corrections start as X1 *constrain* resolutions, harden into standing Directives, and graduate into role content.

### R1 — Manager telemetry read (clarification, no new mechanism)

Make explicit what "the manager's-eye view" implies: **a manager holds read access to the observability surface of its subtree** — assignment states, plan versions, stage cursors, step actuals-vs-envelope, meter state, and open gates of its reports (recursively, respecting sub-org opacity: a mounted child org exposes only its root's surface). Never workspace contents, never other teams' assignments, never message bodies between other agents — telemetry, not surveillance, and identical to what the operations UI renders for the human.

Exposed to manager agents as runtime read tools (e.g. `inspect_report(assignmentId)`, `subtree_status()`). With R1 in place, **proactive trajectory review is pure composition**: a manager RoleTemplate ships a Cadence ("review in-flight work across my reports") whose execution reads R1 telemetry and whose resolution is either nothing or an X1 intervention. No new abstraction — the user's "look at the current work trajectory for all reports and interrupt" is Cadence + R1 + X1.

### R2 — Reassignment semantics (resolves an undefined term)

Reassignment is **cancel-with-continuation**: the original Assignment is cancelled; a new Assignment is created on the new report carrying the latest brief version, citations to any already-accepted or partial Artifacts (which live in the team's ArtifactSpace, not the old workspace — nothing is lost to isolation), the remaining meter balance, and a provenance link `reassigned_from`. The Intent trace stays unbroken (invariant 6), the one-agent-per-Assignment rule stays simple, and spent tokens stay attributed to the node that spent them (honest accounting, per the ledger's meter-continuity principle).

### R3 — Queue priority (resolves the open queue-policy item)

Default FIFO; the issuing manager may set and revise a priority on Assignments queued behind its reports. Gate resolutions retain their existing front-of-queue resumption. This keeps the policy small and swappable as `domain-model.md` asked, while giving `franchise-shift` and `support-tier` the rush-order semantics they structurally need.

### R4 — Directive timing (clarification)

`domain-model.md` states Directives are Assignment-scoped but not *when* they may be issued. Clarify: a Directive may be issued or amended at any point in the Assignment's life; mid-flight issuance takes effect at the next Step boundary and is versioned alongside the brief. (Without this, X1's *constrain* resolution has no footing.)

---

## 5. Worked example — the scope-creep scenario

`product-engineering-pod`. The `engineering-lead` delegates "implement the multi-tenant billing endpoints" to a `backend-engineer`, Deliverable contract `PullRequest`, meter funded from salary. Mid-execution the engineer decides the deploy pipeline is inadequate and starts building CI tooling — work that belongs to `platform-pod`, in another team.

1. **Detection, three redundant paths.** (a) The engineer revises its Plan to add two stages ("build pipeline", "migrate configs") — *plan expansion* trips trigger #5 (X2). (b) Its steps start emitting tooling-shaped artifacts against a `PullRequest` contract — *contract-foreign deltas*, same trigger. (c) Independently, the lead's weekly trajectory-review Cadence (R1) would have surfaced the divergence even if no tripwire fired.
2. **Suspension.** An InterventionGate opens on the Assignment, owner: `engineering-lead`. The halt lands at the next Step boundary; the workspace freezes; the engineer node picks up its next queued Assignment.
3. **Correction.** The lead resolves with *constrain* (X1 + R4): "stay within the PullRequest contract; drop stages 4–5; the pipeline problem is out of scope." The brief is unchanged, so every token burned on the drift stays visibly on the engineer's meter — drift is priced, attributed, and rolls up the Intent tree.
4. **The legitimate need routes correctly.** The pipeline gap is real, so the lead handles it *structurally*, one level up: an escalation to the common manager, resolved as cross-team sequencing between the lead's and platform-pod's own Assignments — exactly where `domain-model.md` says cross-team work belongs. If it keeps happening, channel telemetry surfaces the Conway signal.
5. **Prevention next time.** The lead registers a standing Directive (X4) on its engineers: "infrastructure and CI work is out of scope for feature Assignments; escalate instead." If the rule proves permanent, the user promotes it into the role's extensions or the catalog.

Every step lands in existing machinery: gates, briefs versions, meters, escalation, telemetry.

---

## 6. Invariant compatibility

| Invariant | Effect of X1–X4, R1–R4 |
|---|---|
| 1 — chart is a tree | Untouched. All new authority flows along existing reporting edges. |
| 2 — workspace isolation | Untouched. R1 reads telemetry the platform already records; never workspace contents. |
| 3 — communication follows the chart | Untouched. No new channels; interventions ride the existing manager↔report relationship. |
| 4 — delegation follows the chart | Untouched. R2's reassignment creates the new Assignment via the same manager, on its own report. |
| 5 — artifacts immutable | Untouched. |
| 6 — every Deliverable traces to an Intent | Preserved explicitly by R2's `reassigned_from` provenance link. |
| 7 — mechanical metering | Strengthened: X1's halt and R4's directive injection are enforced at the same between-Steps boundary as the meter, by the same argument. |
| 8 — all suspension is a Gate | Preserved and relied on: X1, X2, and X3 all discharge through the existing five gate kinds; the taxonomy does not grow. |
| 9 — consented, then evidenced | Generalized by X3 from governed *actions* to governed *transitions*; semantics (denial = prohibition) unchanged. |
| 10 — credentials never enter an Agent | Untouched. |
| 11 — roles are data | Preserved: checkpoint defaults and trajectory-review cadences ship as RoleTemplate data; standing directives are runtime data. |

"Only the user permanently changes an Agent" also survives: X4 attaches per-Assignment directives and never edits the Agent; permanence requires the user, via the promotion path.

---

## 7. Phasing

All four extensions are Phase-3 work-layer semantics — they presuppose Assignments, Plans, and Gates, none of which exist in Phase 2. Per the `phase3-debts.md` discipline, the cheap reservations worth making early:

- **The halt check** belongs beside the meter check in the gateway/step loop (one flag read per step boundary) — reserving it in Phase 2 costs nothing and makes X1 a policy change rather than a runtime change. It also generalizes the existing `paused` node state.
- **Step delta taxonomy** (already an open item) should include the artifact-type facet X2's contract-foreign-delta signal needs — one more reason to close that enum at the SDK layer.
- **U-3's human-approved delegation** (Phase 2.5 candidate) should be built as a plan-review checkpoint on the root Assignment, so it *is* X3's first instance rather than a throwaway training wheel.
- **D4's acceptance-policy knob** (SC-2) and **manager auto-resolution bounds** (SC-4) are adjacent policy work in the same manager surface; design them together.

## 8. Open items

- **Intervention etiquette.** How often may a manager agent interrupt before it becomes the bottleneck it exists to prevent? Likely a calibrated cost: interventions burn the *manager's* meter (they are manager work), which self-limits micromanagement the same way rework funding self-limits re-scoping.
- **Scope-divergence tolerances.** Plan-expansion thresholds should come from calibration like envelopes do; cold-start defaults are a catalog-authoring concern (same as cold-start envelopes).
- **Standing-directive conflicts.** Precedence when a standing Directive, an engagement Directive, and role instructions disagree — proposal: most-specific wins (engagement > standing > role), all three visible in the compiled charter.
- **Cross-level intervention.** X1 grants transitive managers the power to intervene below their direct reports. Skip-level intervention is real management behavior but undermines the middle manager; consider requiring it to route *through* the intermediate manager (open the gate, assign them as owner) rather than resolving directly.
