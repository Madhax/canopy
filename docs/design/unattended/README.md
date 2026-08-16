# Unattended Operations — Design Suite (the H-series)

> **Status:** Proposed 2026-08-16 (drafted in operator session) — adoption is the operator's call
> **Sequencing:** post-C-series; pre-requisite for `canopy-inc.md` §6's W2+ running hands-off. Milestones are **H1–H6** ("H" for *hands-off*; "U" was declined to avoid colliding with the usefulness-risk ids U-1/U-2).
> **Reads with:** `../../mission.md` §3–§4 (the operating state this series makes real), `../../canopy-inc.md` (the fleet this operates), `../organizations/04-scheduling-and-throttles.md` (the governor this extends), `../experiments/03-search-and-iteration.md` §5 (the envelope pattern this generalizes), `../standing-orgs.md` (the intake this hardens), `../../risks/usefulness.md` U-2 (the daily-return surface this finally builds), `../../execution/cli-runtime.md` §8 (the waiver this series schedules for retirement)

## The question

The mission defines success as an operator with exactly two duties — approve direction, approve consequences — checking in **once a day**. The corpus as it stands cannot deliver that day. Its governance stack is complete: everything suspends correctly, meters hard-stop race-free, every consequence gates. But **everything is designed to stop safely; almost nothing is designed to proceed safely.** A triggered intent blocks on plan review within minutes and waits for tomorrow. A hard-stop parks an assignment until a human tops it up. A credential expiring at midnight takes the fleet down until morning, silently. The platform runs as a dev process on a desktop. There is no designed answer to "what does the operator actually look at each morning," and no defined bar for "safe to leave running."

This series closes those gaps as six designs:

| Doc | Gap it closes |
|---|---|
| `01-operations-envelope.md` | No autonomy-policy layer: plan review, budget top-ups, and known clarifications all block on the operator. The envelope automates the operator's *predictable answers* under bounded standing consent — never the operator's *authority*. |
| `02-daily-brief.md` | No designed check-in: the daily brief (batched ratification, parked work, anomalies, receipts delta), and the closed set of events allowed to page the operator between briefs. |
| `03-continuity.md` | Nobody keeps the platform itself alive: service supervision, credential health and re-auth, backups, disk/log hygiene — boring infrastructure as a design deliverable. |
| `04-flow-policies.md` | Failure flow: trigger-fired intents finally consult the governor (CAP-D10), failed trigger work can re-fire boundedly, long-lived branches get a rebase policy, and salaries get calibrated from receipts instead of placeholders. |
| `05-threat-posture.md` | Unattended external input: injection posture for reader teams, audit tripwires, and the docker tier promoted from "eventually" to the gate on Wave 3. |
| `06-readiness-and-soak.md` | Proof: the per-team unattended-readiness checklist, the fleet soak standard, and the three-posture graduation ladder that gives "leave it running" a defined entry bar. |
| `07-implementation-plan.md` | H1–H6, prerequisites, config, API map, debts (OPS-D1..D5), doc-edit impact map. |

## The five pillars

1. **Automate answers, never authority.** The envelope may spend bounded tokens inside the walls; it may never accept outcomes, authorize consequences, or widen a capability. Ratification remains human, always (`mission.md` §4.1, §5 — the two approvals are the product, not scaffolding).
2. **Park, don't page.** The default response to anything unresolvable is to park it with a reason and surface it in the brief. Paging is reserved for a closed, tiny set of events (`02` §4) — a fleet that pages is a fleet the operator will turn off (SC-4).
3. **The brief is the fleet's deliverable about itself.** One surface, once a day, ordered ratify → parked → anomalies → receipts, with an honest "nothing needs you" when true. If the brief can't be read in fifteen minutes, that is a forge signal, not a reading assignment.
4. **Boring infrastructure is a design deliverable.** Supervision, backups, credential health, and disk hygiene are specified and tested like features, because at 3am they *are* the product.
5. **Readiness is checked, not vibed.** No team runs a hands-off posture until its checklist passes — the actuation-readiness pattern applied to autonomy — and no posture is entered until the previous one is boring (the trust ladder, applied to the operator's own absence).

## Relationship to the existing corpus

The envelope generalizes the experiment lab's envelope (`../experiments/03` §5) from search space to operations, and its graduation mechanism reuses the promotion pattern (`champion-suggested` → `graduation-suggested`; the envelope never loosens itself, it nominates itself for loosening). The brief is the standing answer to U-2's second-session problem and absorbs the C-series' honesty rules (every number with source and age). `04` closes CAP-D10 in place and retires the F1 salary residual with a mechanism instead of a warning. `05` is the threat-model refresh `06-status-and-direction` said was overdue, and pulls A6/T2 with a named customer and acceptance tests. `06` mechanizes `org-roadmap.md` §5's "run unattended for a month" bar, which until now was a definition without an instrument.
