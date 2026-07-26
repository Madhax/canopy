# Amendment Record — Work-Layer Semantics & the Living Plan View

**Status:** Adopted · **Date:** 2026-07-26
**What this is:** the record of five design decisions settled before the E2 build, the doc edits that encode them, and the code areas each one touches. Per the IM-6 discipline, the design docs were amended in place (this file is the changelog, not the spec — the amended docs are authoritative). All five decisions were forced by contradictions or gaps found in a pre-build review of the MVP-1 plan; none of them was reachable by reading any single doc alone.

---

## 1. The decisions

### D-1 · Dependencies carry a resolution policy: verify vs consume

**Problem found:** `work-model.md` §3 resolved every DependencyGate at *acceptance*, while the MVP demo (steps 7–8) required the lead to accept the engineer's PR to unblock QA — and then *reject* it when QA failed. `accept()` is terminal (closed, meter closed, memory written), so the rejection — and the entire brief-version rework-funding rule, the formation's centerpiece — was unreachable. The collision occurs in **every verification-shaped formation**.

**Decision:** each dependency edge declares `resolveOn: accepted | delivered`.
- **consume** (`accepted`, default) — downstream *builds on* the output; waits for sign-off.
- **verify** (`delivered`) — downstream *checks* the output; starts at submission, because the verifier's report is what acceptance is supposed to be informed by.

Acceptance stays terminal and moves to where it belongs: after verification, as the final verdict. The rework loop now runs on a still-open (`delivering`) assignment, same meter, funding rule verbatim. Policy is formation-declared, per edge; refs are pinned at the resolving artifact version.

### D-2 · Staged delegation: plan review approves real delegations

**Problem found:** `engine.md` §2.9 gated `planning → executing` with *the plan* as the ApprovalGate payload, but `operator-experience.md` §4 promised the plan-review card shows *per-child briefs, contracts, dependencies, allowances* — objects that did not exist yet at that transition (delegation happens later, in `executing`). As specced, the operator would approve a prose plan and the real delegations would dispatch unreviewed.

**Decision:** when a plan-review checkpoint applies (root assignments by default), `delegate` calls buffer as **`proposed`** — unfunded drafts (no meter, nothing published). `finish_turn` opens the ApprovalGate with the **proposed batch** as payload. Approval funds and dispatches atomically (`proposed → briefed`); edit amends the draft brief before versioning begins (v1 stamps at dispatch); denial is a prohibition — drafts cancelled, the manager re-plans. X3's first instance thereby becomes governed *dispatch* rather than a governed state transition.

### D-3 · Managers wake on each delivery

**Problem found:** `engine.md` §2 11a said the manager-await gate "auto-resolves as children *close*" — but children only close when the manager accepts, and the manager cannot accept while gated. The flow only worked via an undocumented side channel (the bus notify at `delivering`).

**Decision:** the await-gate is a `delivered`-threshold watcher over the child set. It resolves whenever **any** watched child reaches `delivering` or a terminal state; the resume payload carries everything pending at that moment plus the outstanding remainder; the manager reviews what arrived and re-enters the gate while children remain. A failing deliverable is reviewed while its siblings still work — fast rejects keep rework cheap; pending items batch opportunistically at each wake.

### D-4 · The living plan view: one aggregate, three projections

**Gap found:** the plan data (assignment tree, per-node plans, cursors, gates, meters) is fully modeled and versioned, but no surface renders it as the *one organic, evolving document* an operator wants to read and step into. The tree view came closest; nothing stitched the whole engagement together.

**Decision:** a per-intent aggregate — `GET /intents/{id}/plan` — feeds three synchronized projections: **outline** (default; the engagement as one nested living document), **chart overlay** (extends mission control's assignment-flow overlay), and **timeline** (stage bars from new `started_at`/`completed_at` stamps). Every line is a handle: leave a note (D-5) or intervene (X1) inline. Read + act; the view stores nothing. Outline + notes ship in MVP-1; overlay and timeline are fast-follows on the same aggregate.

### D-5 · Notes: the non-blocking advice channel

**Gap found:** every mid-flight managerial touch rode an InterventionGate, which *suspends* work — right for redirection, far too heavy for "consider the streaming API." There was no way to advise without halting.

**Decision:** a **note** — an anchored, advisory message (`work_note`: intent / assignment / stage anchor, author, text) rendered in the plan view at its anchor and injected into the target session's context at the next turn boundary (the same boundary directives use, R4). It opens no gate, revises no brief, constrains nothing; `delivered_at` records injection. Binding change still travels as briefs, Directives, and Gates. Conceptually a Message with an anchor (domain §Message); operator-authored in MVP, manager-agent-authored post-MVP.

---

## 2. Doc edits (all applied in this change)

| Doc | Sections touched | Change |
|---|---|---|
| `domain-model.md` | §Dependency · §Gates (DependencyGate) · dependency/approval precision para · Assignment lifecycle · §Message · Resolved design decisions | D-1 policy definition; `proposed` line in the lifecycle; anchored notes; three new resolved-decision entries (D-1, D-2, D-3) |
| `execution/work-model.md` | header id list · §2 schema (`meter_id` nullable) · §2.1 lifecycle + staged-delegation rule · §3 dependency row + gate mechanics (two hooks, await-gate re-arm) · §4 stage timestamps · §5 `work_note` + notes prose | D-1, D-2, D-3, D-4 (timestamps), D-5 |
| `execution/engine.md` | §2 flow (steps 1–6, 9/9a, 11a, 12, 13) · §3 gate service (two hooks) · §5 dp table (`assignment/current` notes, `delegate` staging) · §6 operator API (`/intents/{id}/plan`, `/intents/{id}/notes`) | D-1, D-2, D-3, D-4, D-5 |
| `execution/mvp.md` | §1 diagram · demo steps 4, 5, 7, 8, 9 · E2 + E5 milestone rows · §5 acceptance criteria (+3) | demo now consistent with D-1/D-2/D-3; plan view + note beats added; structural failure seeding (edge-case test lives in QA-only suite) |
| `execution/operator-experience.md` | §4 plan-review bullet · new §4a (living plan) · §7 components · §8 MVP cut | D-2, D-4, D-5 |
| `teams.md` | intro (policy definition) + annotations on `product-engineering-pod`, `ml-delivery-pod`, `newsdesk`, `build-crew`, `research-cell` | D-1 formation classifications |
| `org-chart-editor.md` | §3.1 formation deps · §3.2 dependency object + encoding-choices bullet · §7.4 dependency inspector | D-1 in the Phase-1 document schema (see code impact — this doc describes *implemented* code) |

Not folded (deliberate): `manager-responsibilities.md` X3 still describes checkpoints as governed *transitions* — its proposals are scheduled to be retired into `domain-model.md`; fold D-2's governed-dispatch framing then. `execution/README.md` adopted-extensions table remains accurate in spirit (X3 = "plan review on root assignments, default-on").

---

## 3. Code impact map

Ordered by where the work lands. E1 is implemented; E2+ is not — most of this is *build-to-the-amended-spec*, not rework.

### 3.1 Phase-1 surface (implemented today — small, do as one commit)

| Area | Change |
|---|---|
| `server/src/canopy_server/models.py` | `Dependency` gains `resolveOn: Literal["accepted","delivered"] = "accepted"` |
| `ui/src/schema/organization.ts` | Zod mirror of the same field + default |
| `catalog/catalog.json` | formation `dependencies[]` entries gain `resolveOn` (verify edges per amended `teams.md`: product-engineering-pod QA edges, ml-delivery eval→model, newsdesk both edges, build-crew inspector edge) |
| `ui` formation stamp (`document-store.ts` / `projection.ts`) | stamped edges carry `resolveOn`; dependency edge rendering may badge verify edges (optional) |
| `ui` dependency inspector | resolve-on toggle ("starts when: work is submitted / work is accepted") — can trail the schema change |
| `testdata/validation/` | vectors: a document with `resolveOn: delivered` round-trips; an invalid value fails schema parse on both validators; catalog integrity test covers formation `resolveOn` values |
| Compatibility | field is optional with default ⇒ every existing document parses; exports carry it; no `schemaVersion` bump |

### 3.2 Engine / work layer (E2 — not yet built; build to amended spec)

| Area | Change |
|---|---|
| `work_assignment` schema | `meter_id` nullable (NULL only while `proposed`); `proposed` added to the state machine |
| Delegation path (`engine/engine.py` or new `engine/delegation.py`) | staged branch: checkpointed caller ⇒ `proposed` draft (no meter, no publish); direct branch unchanged; batch tracked per delegating assignment |
| Gate service (`engine/gates.py`, new) | dependency-gate payload snapshots `resolveOn` per edge; **two resolution hooks** — sweep at `finish` (delivered-watchers, refs pinned at submitted version) and at `accept` (accepted-watchers); idempotent per (assignment, kind, reason-hash) |
| Plan-review checkpoint | ApprovalGate opened at `finish_turn` with the proposed batch as payload; resolutions: approve (fund + dispatch atomically, continue into await gate without a wake), edit-draft (amend draft brief pre-versioning), deny (cancel drafts, prohibition) |
| Manager-await | await gate resolves on any child reaching `delivering`/terminal; resume payload = pending deliverables + outstanding list; `finish_turn` re-arms while children remain |
| `work_plan_stage` | `started_at` / `completed_at` columns; stamped in `set_stage_state` |
| `work_note` table + notes service | CRUD per §5; `delivered_at` stamped when served to the runtime |
| Existing E1 code touched | `engine.finish()` and `engine.accept()` call the new gate sweep (no-ops until gates exist); `routes/dp.py` `assignment/current` response gains `notes[]`; `routes/work.py` assignment detail exposes stage timestamps |
| Operator API | `GET /intents/{id}/plan` aggregate; `POST /intents/{id}/notes`; `/gates/{id}/resolve` handles the batch-approval resolution actions |

### 3.3 Runtimes (E3)

| Area | Change |
|---|---|
| `agent/src/canopy_agent/runtime.py` (`loop`) | manager tick logic understands `proposed` (delegate returns without delivery), partial-batch review resumes, and note blocks in `assignment/current` |
| `cli-claude` adapter (new in E3) | resume payload renders pending deliverables + notes into the next session input; generated `CLAUDE.md` protocol teaches: staged delegate → `finish_turn` → possible edit/deny outcomes; review-what-arrived-then-`finish_turn` wake loop; notes are advisory context, not instructions to renegotiate the brief |
| Fake-CLI shim | scripted sequences for: staged fan-out approved / denied; wake with one-of-two deliverables; note injection mid-session |

### 3.4 Operate UI (E5)

| Area | Change |
|---|---|
| `PlanReviewCard` | binds to the proposed-batch gate payload (real briefs/contracts/deps/allowances); Approve / Edit brief / Reject wired to the resolution endpoint |
| `PlanView` (+ `PlanOutline`, `PlanOverlay`, `PlanTimeline`, `NoteComposer`) | outline ships MVP-1; overlay/timeline fast-follow on the same `GET /intents/{id}/plan` aggregate; inline Note + Intervene on every row |
| SSE | plan/stage/note events invalidate the plan aggregate query |

### 3.5 Tests (across E2–E6)

- Golden state-machine vectors: `proposed → briefed` (approve), `proposed → cancelled` (deny), no-meter invariant while proposed.
- Dependency-threshold vectors: verify edge resolves at `finish`, consume edge only at `accept`; both under redelivery (idempotent sweep).
- The demo §3.7–3.9 ordering as a fixture: submit → verify-dep resolves → QA fails → reject on same open assignment/meter → rework → re-verify → accept; assert acceptance never precedes the green report and rework burned the original meter.
- Manager-await: two children, staggered delivery ⇒ two wakes; batch pending at wake reviewed together; re-arm until empty.
- Notes: created → rendered in aggregate → `delivered_at` stamped exactly once → session input contains it → assignment never left `executing`.

---

## 4. Follow-ups this amendment deliberately did not decide

- **E2 split (E2a delegation spine / E2b judgment gates + triggers):** recommended in the plan review; adopt when scheduling E2 — the amended E2 row is now even larger than before.
- **Re-verification cost attribution:** QA's second run after a rework is a new assignment on QA's salary; the defect's ripple cost shows in the intent rollup, not on the engineer's tab. Honest, but the cost explorer should surface "verification rounds per assignment" so ripple cost is visible.
- **Org-wide plan rollup** (all intents in one view): later; the per-intent aggregate is the building block.
- **Manager-agent notes and manager-initiated intervention:** post-MVP per the standing etiquette question (interventions burn the manager's meter).
- **`manager-responsibilities.md` X3 wording:** governed *dispatch* framing folds in when that doc's proposals retire into `domain-model.md`.
