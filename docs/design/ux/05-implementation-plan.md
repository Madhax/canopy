# 05 · Implementation Plan — the UX-series

> **Status:** Proposed 2026-08-16 · **Reads with:** the suite; `../organizations/07-implementation-plan.md` (style precedent), `../../testing.md`, `../unattended/07-implementation-plan.md` (the H-series these milestones interleave with)

## 0. Sequencing

UX-milestones are UI-heavy and mostly independent of the H-series' engine work; the two interleave rather than queue. Natural pairings: **UX1 lands with or before H2** (the brief deserves a fleet worth linking from; both ride the same SSE upgrade), **UX4 before any external user touches the repo**, UX2/UX3 whenever — every milestone is independently shippable. Nothing here blocks W1 founding; everything here makes W1 *governable at a glance*.

## 1. Milestones

| # | Name | Ships | Done means |
|---|---|---|---|
| **UX1** | Fleet glance | health-model computation server-side (status word + reason, precedence rules); `GET /api/fleet` rollup; Home rebuilt on team cards (glance grammar, burn chips from capacity attribution, last-product line); org rollup header (counts, budget bar, runway, posture chip); priority sort; SSE for fleet + capacity surfaces (closes CAP-D7) | golden vectors: signal-state → status word (every precedence rule); `stuck` vs `waiting` never share a rendering (snapshot test); burn chip matches capacity ledger attribution (property test); fleet updates without reload on scripted events |
| **UX2** | Products first | `GET /api/teams/{id}/artifacts` + org feed (deliverables + attestations interleaved, filters); receipt-card component (what/who/standing/cost/preview) reused by feed, brief, PR and acceptance cards; engagement page reorganized (header + products rail + collapsed plan + cost line + pulse lines); expected-next-products from open contracts; standing-work section on the team page (purpose, cadences/triggers as phrases, envelope chip) | feed matches engine records exactly (property test); verify chips render pending/green/red from fixture verdicts; a scripted engagement's page answers "working?" from products + pulse alone with the plan collapsed (Playwright); receipt card is one component, imported everywhere it renders (no forks) |
| **UX3** | Altitudes + navigation | five-destination nav; Build/Actuate folded into Team surface modes; object pages + universal breadcrumbs + id-chips-link-everywhere; the demotion audit applied (the §3 table as a checklist PR — every datum classified and re-homed); since-you-looked markers; card grammar normalized across all asks | demotion checklist merged with each row's new home noted; no dead-end ids (crawler test over rendered fixtures); every ask-card renders claim/evidence/action from one component; forensic surfaces reachable in ≤1 click from every chip |
| **UX4** | First run | `canopy up` + `canopy doctor` (both OSes); System panel (checks live, fixes shown, apply+restart when supervised); first-run wizard (mode → org/team → **team-default binding** → readiness checklist → first intent); empty states; demo-seed flag; root README quickstart rewritten around `canopy up` | clean-machine CI job: `canopy up` to a working demo engagement with zero manual edits (both OSes); doctor exit codes + fix texts under test; team-default binding round-trips the document schema and passes shared validators; wizard skippable at every step |
| **UX5** | Identity + warmth | seat display names + generated avatars (deterministic from seat id); team colors; empty-state illustrations; terminology subtitle pass (domain verbs keep, plain subtitles); read-cursor fade polish | avatars deterministic (same seat, same face, both OSes); a11y pass on color/status pairs (status never color-only); no id-as-label remains at glance altitude (audit re-run) |

## 2. Debts this series knowingly opens

- **UXD-1 — an opinionated health word can be wrong.** A team shown `working` that is semantically wasting effort erodes trust faster than no summary. Mitigations: the reason phrase always beside the word; forensic one click; UX-28's one-truth rule so wrongness is at least *consistent* and testable. Permanent honesty item.
- **UXD-2 — warmth vs. sobriety.** Avatars and colors read delightful to one operator and unserious to another; both readings affect daily-return behavior (U-2). Config: `[ui] warmth = "full" | "minimal"`. Revisit at first external user.
- **UXD-3 — apply+restart writes config.** The System panel editing `canopy.toml` + bouncing the supervised service is a footgun surface; bounded by showing the diff first and refusing outside the four known flags. Sunset if config ever becomes runtime-reloadable.

## 3. API and schema pulls

`GET /api/fleet` (rollup) · `GET /api/teams/{id}/artifacts` + `GET /api/orgs/{id}/artifacts` (feeds) · health/status SSE family · team `defaultProfileBinding` (document schema + validators + editor) · seat `displayName` (server-assigned default, operator-editable) · launcher/doctor scripts. No dp-surface changes; agents see none of this (the invisibility rule holds — a team must behave identically however it is rendered).

## 4. Doc-edit impact map (on adoption — not before)

| Doc | Edit |
|---|---|
| root `README.md` | quickstart rewritten around `canopy up` (UX4); *applied now:* the real-CLI section (§"Running with real Claude sessions") and this series in the docs table |
| `../../execution/operator-experience.md` | amended to point here as the current IA; its §2–§6 become the forensic-layer spec |
| `../organizations/05-ux-portfolio.md` / `06-ux-capacity.md` | portfolio home superseded by UX1's fleet glance (honesty rules unchanged); capacity console noted SSE at UX1 |
| `../unattended/02-daily-brief.md` | brief cards adopt the receipt/card components (BR-5's batch UX rides UX2's card) |
| `../../org-chart-editor.md` | team-default binding amendment (UX4) |
| `../../phases.md` | navigation note: five destinations, Build/Actuate as Team modes |
