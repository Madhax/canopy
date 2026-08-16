# Operator Experience — Design Suite (the UX-series)

> **Status:** Proposed 2026-08-16 (drafted in operator session) — adoption is the operator's call
> **Reads with:** `../../mission.md` §2 (attention as the conserved currency — every principle here derives from it), `../../execution/operator-experience.md` (the surfaces this reorganizes), `../organizations/05-ux-portfolio.md` + `06-ux-capacity.md` (honesty rules inherited wholesale), `../unattended/02-daily-brief.md` (the ratification altitude, already designed), `../../canopy-inc.md` §2 P2 (the attention budget these views must fit)
> **Milestones:** UX1–UX5 (`05-implementation-plan.md`).

## The diagnosis

The current UI is **machinery-shaped**: every surface faithfully renders the domain model — assignments, gates, meters, plans, steps — because the UI was built to prove the machinery. That was right for building and is wrong for operating. An operator run is a small set of recurring **questions**, and the product should be shaped as their answers:

| Altitude | The question | Today | Target |
|---|---|---|---|
| **Fleet** | *Is everything okay? Who's running, who's stuck, who needs me?* | portfolio lists teams; health is assembled by eye | `03-fleet-glance.md` |
| **Ratify** | *What needs me, with what evidence?* | inbox + GitHub + plan cards, unordered | the daily brief (`../unattended/02`) + card grammar (`01` §4) |
| **Team** | *Is this team doing its job right now?* | Execute page: plan, gates, pulse, costs at once | `02-products-first.md` |
| **Products** | *What did it make? Is it good?* | artifacts linked from plan nodes — buried | the artifact feed (`02`) |
| **Forensics** | *Why did this happen?* | inspector (excellent, keep) | unchanged — one click away, never in the way |

The screenshot that prompted this series (a session-orchestrator app) gets three things right that we should steal: **per-row glanceability** (name + status + burn + cost, one line per worker), **the standing routine as a first-class editable page** (ours are cadences/purpose — currently buried in settings), and **warmth** (named, avatared workers make a fleet scannable and pleasant to check daily). What we deliberately do not copy: it is session-centric — a flat list of processes. Canopy's differentiator is that the *organization* is the object: structure, governance, and receipts. Our fleet view ranks by *what needs the operator*, not by what is merely running.

## The principles

1. **Products over process.** The domain model is artifact-centric ("every responsibility ends in something checkable"); the UI must be too. The primary answer to "is it working?" is the stream of deliverables with their verify status — the plan tree is the explanation, one level down.
2. **One question per surface.** Each view answers its altitude's question and demotes everything else. A datum on the wrong altitude is a leak (`01` §3's audit).
3. **Glance grammar.** Anything scanned in a list gets exactly: a status word, a reason, one number, one trend. More belongs behind the click.
4. **Card grammar for every ask.** Anything requesting operator action reads claim → evidence → action, evidence inline (verify verdicts, diffstat, cost line) — ratification must never require an expedition.
5. **Ratify / glance / forensic.** Every datum in the product is classified into one of three altitudes, and renders only at or below its class. Access is never removed — placement is.
6. **Liveness without noise.** A working team shows a pulse (current stage, last step age); *idle* and *stuck* are visually distinct states (the engine knows — surface it); logs stream only in forensics.
7. **Names before ids.** Seats get display names and generated avatars; teams get colors. `a_be01` and `tm_…` are forensic vocabulary. Warmth is a feature: a fleet the operator enjoys glancing at gets glanced at (U-2 by another road).
8. **First run is a surface, not a wiki.** Setup, auth, and readiness are product screens with fix-it actions (`04-first-run.md`); empty states teach the next step.
9. **Honesty everywhere.** Source tier, age, and n on every number — the capacity console's rules, inherited by every new surface. An all-clear is stated, never implied.
10. **The brief is the front door when away; the fleet is the front door when present.** The two compose: fleet glance links into the same cards the brief batches.

## Reading order

| Doc | What it answers |
|---|---|
| `01-altitudes-and-navigation.md` | Information architecture: surfaces per altitude, the demotion audit, object-centric pages, "since you looked" |
| `02-products-first.md` | The team-at-work view: artifact feed, receipt cards, the engagement page reorganized |
| `03-fleet-glance.md` | The health model and status taxonomy; team cards; the org rollup; how burn is shown |
| `04-first-run.md` | Setup as product: `canopy up`, the doctor, the wizard, bindings-by-default, CLI auth |
| `05-implementation-plan.md` | UX1–UX5, API pulls, debts, doc-edit impact |
