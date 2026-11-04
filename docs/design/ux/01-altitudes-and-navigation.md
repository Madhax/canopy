# 01 · Altitudes and Navigation — one question per surface

> **Status:** Proposed 2026-08-16 · **Reads with:** `README.md` (the altitude model), `../../execution/operator-experience.md`, `../unattended/02-daily-brief.md` (the Ratify altitude), `../organizations/05-ux-portfolio.md`

## 1. The surface map

Five top-level destinations, one per altitude, replacing the current page-per-machinery navigation:

| Nav | Altitude | Absorbs today's | Never shows |
|---|---|---|---|
| **Home** (fleet) | Fleet | portfolio home + org pages | steps, gates taxonomy, raw tokens |
| **Brief** | Ratify | inbox needs-you + digest (H2's page) | anything with no action or no news |
| **Team** (per team) | Team + Products | Execute page, mission control, plan view, cadence/trigger sections | per-step economics, envelope internals |
| **Bench** | the lab (L-series, when built) | experiment surfaces | — |
| **Capacity** | governance | capacity console (unchanged — already altitude-clean) | — |

Build, Actuate, and team settings become *modes of the Team surface* (tabs/edit states), not sibling destinations — the operator thinks "this team," not "which of five pages about this team." The inspector remains the universal forensic layer, reachable from any entity chip, never a nav destination.

**UX-1** One route per altitude; every other view is reached *through* an object, not the nav. **UX-2** The brief and the fleet cross-link per `README.md` principle 10 — same cards, two entry postures.

## 2. Object-centric pages

**UX-3** Every entity — Organization, Team, Engagement (intent), Artifact, Gate, Seat (agent) — has one canonical page/panel with a consistent header: name, status word + reason, age, and its 1–3 legal actions. **UX-4** Universal breadcrumb `Org › Team › Engagement › Artifact`; every id rendered anywhere is a link to its object; no dead-end ids. **UX-5** Cross-surface hops are one click: PR card → engagement → newest artifact → producing seat's transcript. If a hop needs the URL bar, the graph is broken.

## 3. The demotion audit

The systematic fix for "details leaking." **UX-6** Every datum currently rendered is classified **ratify / glance / forensic** and re-homed to its altitude. The audit table lives beside the code (a checklist PR at UX3); the classification rule: *would the operator act on it? → ratify. Does it change what they check next? → glance. Otherwise → forensic.* Seed classifications:

| Datum | Today | Class → home |
|---|---|---|
| step deltas, per-step tokens, tool events | plan/inspector surfaces | forensic → inspector only |
| gate kind names (`clarification`, `escalation`…) | cards | forensic → cards say what's needed in plain words ("needs an answer", "waiting on QA"), kind visible on expand |
| node/team/assignment ids | throughout | forensic → names + avatars (`README` P7); ids on hover/expand |
| meter raw tokens | cards | glance as **% of allowance + trend**; raw in forensic |
| brief/plan version numbers, schema ids | cards | forensic |
| verify verdicts, rework count, cost line | buried in tabs | **ratify** → onto the receipt card (`02` §2) |
| stall flag, capacity hold reason | engine/activity | **glance** → the status word's reason (`03` §1) |
| cadence cron strings | settings | glance as human phrase ("weekday mornings"); cron on edit |

**UX-7** Demotion never deletes: forensic surfaces keep everything, one click deep, permalink-able (audit and trust depend on it — placement changes, access doesn't).

## 4. The card grammar (every ask, everywhere)

**UX-8** Anything requesting operator action — plan review, PR, governed action, graduation, gate — renders as **claim → evidence → action**: one sentence of claim ("`canopy-docs` wants to dispatch 2 assignments, Σ 180k"), evidence inline and specific (proposed briefs one-line each; for PRs: verify verdicts, diffstat, cost, rework count; for governed actions: exactly what will leave the walls), then the actions (approve / edit / deny — never more than three). **UX-9** Evidence is *the same receipt objects* everywhere (`02` §2) — the brief batches these cards; team pages show them singly; no surface invents its own ask format.

## 5. Since you looked

**UX-10** The notification read-cursor generalizes to a per-surface *seen* marker: fleet and team surfaces subtly mark what changed since the operator last looked (new products, status changes) and offer "catch me up" — the brief's delta semantics, ambient. No unread-count anxiety mechanics: markers fade on view, nothing nags.

## 6. Open questions

1. Do Build/Actuate deserve nav presence during early setup (when they *are* the workflow) with automatic demotion once teams run? Leaning yes — nav can be posture-aware.
2. Keyboard-first operation (j/k through brief cards, a to approve) — cheap to add at UX3, worth specifying then.
3. Naming: keep domain verbs (Actuate) with plain subtitles, or rename in-UI? Leaning keep — the operator learned the vocabulary; subtitles serve newcomers. Revisit at first external user.
