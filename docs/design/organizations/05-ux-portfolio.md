# 05 · UX — The Portfolio Home

> **Status:** Adopted 2026-08-09 (operator decision) — proposed by the portfolio-and-capacity working group, 2026-08-08
> **Reads with:** `01-team-and-organization.md`, `06-ux-capacity.md` (the sibling surface), `../../execution/operator-experience.md` (the team-level Operate surface, which survives intact one level down), `../../phases.md`

## 1. Information architecture, reworked

Today the app's top level *is* one team: a list page, an editor, `/actuate`, `/execute` with an org picker bolted on. After this proposal the top level is the **portfolio**, and everything that exists today becomes the *team scope*, reached by drilling in:

```
Portfolio home  (/)                    — all organizations, all teams, capacity strip
└── Organization page  (/orgs/:orgId)  — one organization: its teams, budget, inbox
    └── Team scope  (/teams/:teamId)   — today's product, re-rooted:
        ├── /teams/:id/edit            — the chart editor (Build)
        ├── /teams/:id/operate         — Execute views: work | pulse | costs (unchanged inside)
        └── actuation controls         — on the team header, as today
Capacity console  (/capacity)          — operator-level, cross-org by necessity (06)
```

Three IA rules do the heavy lifting:

- **Scope is a place, not a filter.** You are always *somewhere*: in the portfolio, in one organization, or in one team. Every list, inbox, notification bell, and SSE stream binds to the current scope. There is no "all organizations" work view below the home page — that is what the home page is.
- **The org context is worn, not remembered.** A persistent scope bar (org theme color + name) sits under the app header everywhere inside an organization. `personal` is indigo everywhere it appears; `canopy-inc` sage. Deep links carry scope in the URL; nothing depends on session state.
- **Build/Actuate/Execute become team verbs.** `phases.md`'s trio stops being global navigation and becomes the team header's mode switch — which is what it always really was (you build *a team*, actuate *a team*, work *a team*).

## 2. Portfolio home — anatomy

The operator's one-glance answer to "what is my world doing?"

```
┌────────────────────────────────────────────────────────────────────────┐
│ Canopy                                                    ⚙  🔔(3)     │
├────────────────────────────────────────────────────────────────────────┤
│ CAPACITY   Claude Max   5h ████████░░ 82% ↻17:40   7d ███░░ 31%        │
│            Google AI    day ██░░░░░░░ ~19% (counted)      → console ↗  │
├────────────────────────────────────────────────────────────────────────┤
│ ▌canopy-inc — Serves Canopy's own development.        $12.40/$40 wk    │
│ ┌──────────────────────────┐  ┌──────────────────────────┐             │
│ │ canopy-docs         ● 2/2│  │ canopy-maintenance  ● 3/3│             │
│ │ 1 intent · 0 need you    │  │ 2 intents · 1 NEEDS YOU  │             │
│ │ ▸ PR #14 delivered 14:02 │  │ ⏸ holding 5h → ~17:40    │             │
│ │ 0.6 pp/hr · 96% accept   │  │ 4.1 pp/hr · 88% accept   │             │
│ │ [Operate] [⏸] [Edit]     │  │ [Operate] [▶ knobs]      │             │
│ └──────────────────────────┘  └──────────────────────────┘             │
├────────────────────────────────────────────────────────────────────────┤
│ ▌personal — Serves your life.                          $1.10/$8 wk     │
│ ┌──────────────────────────┐                                           │
│ │ household           ● 1/1│   priority: interactive · reserve 15%     │
│ │ idle · next cadence 18:00│                                           │
│ └──────────────────────────┘                                           │
└────────────────────────────────────────────────────────────────────────┘
```

Components, top to bottom:

- **Capacity strip** (`CapacityStrip`) — one row per ProviderAccount: headline window gauges with reset countdowns, each number wearing its source badge (`06` §6). Click-through to the console. This strip is the *only* cross-org element on the page besides the org sections themselves — capacity is operator-level truth and pretending otherwise would be a lie of layout.
- **Organization sections** (`OrgSection`) — one per org, in operator-set order. The section header carries the identity (theme bar, name, purpose sentence), the week's budget position (`$spent/$ceiling`, estimates-styled), and an org-scoped attention count. Sections are visually heavy on purpose: the separation requirement is satisfied first by *layout* — two worlds, two bands, no shared rows.
- **Team cards** (`TeamCard`) — §3.

An empty portfolio (first boot) shows the existing new-org wizard reframed: "Create your first organization" → name/purpose/theme → "now add its first team" → the current type/seed wizard unchanged.

## 3. The team card

The card answers, in order: is it alive, does it need me, what is it doing, what is it costing, and is it any good — without a click.

| Zone | Content | Source |
|---|---|---|
| Header | name · live dot + `ready/total` nodes (or `paused ⏸`, `drain ⏳`, `off ○`) | actuation + schedule |
| Needs-you | `N NEED YOU` chip (operator-owned gates, org-scoped styling, click → that team's inbox) | gates feed |
| Now | one line: current intent title, or capacity hold (`⏸ holding 5h → ~17:40`), or `idle · next cadence 18:00` | pulse + capacity gates |
| Last delivered | most recent deliverable, relative time | work store |
| Vitals | burn (`pp/hr` on its primary pool) · acceptance % (14 d) · rework rounds · est $/wk | attribution + rollups |
| Actions | `[Operate]` `[⏸/▶]` (run-state toggle, K1) · overflow: Edit chart, Knobs (→ console row), Move org (custody flow, `01` §3), Deactuate | — |

The card is the *management* unit the operator asked for: pause/resume without entering the team, performance without a dashboard dive. Anything deeper is one click — `Operate` lands in the team's existing Execute surface, which this series deliberately does not redesign.

## 4. Organization page

The org page is the home page's section, expanded, plus the org's own management surfaces:

- **Header:** identity, purpose (editable), budget editor (weekly ceiling, shares, reserve — the org-level knobs K7/K8 live here, *not* on the capacity console, because they are governance-of-mine rather than operations-of-now; the console links back).
- **Team grid:** the same `TeamCard`s, plus `+ New team` (wizard, pre-scoped) and import (`.team.json`, `01` §4).
- **Org inbox:** the union of member teams' needs-you feeds, org-scoped only, with team chips on each row. This is where "manage each team" and "don't manage from one giant chart" reconcile: escalation converges per-organization, never globally.
- **Org activity:** the receipts view — deliverables and costs across member teams, the natural home of the "$2.10 PR" story for `canopy-inc` and of "what did my life cost this week" for `personal`.

## 5. Separation design

The requirement: the two-worlds split must be *obvious in the view*. Mechanisms, in order of force:

1. **Scope-bound surfaces.** No list below the portfolio home ever mixes organizations. The inbox is org-scoped; notifications are org-scoped (the global bell shows per-org subtotals and routes to org inboxes); search (if/when it exists) scopes by default.
2. **Worn identity.** Org theme color on: the scope bar, section bands, team-card left border, gate cards, and notification rows. Two orgs never share a theme color (enforced at creation). Icons secondary; color is the carrier.
3. **URL honesty.** `/orgs/personal/...` vs `/orgs/canopy-inc/...` — scope readable in every address, bookmarkable, no ambient context.
4. **Structural walls behind the paint** — invariant 12 (`01` §5) guarantees the views aren't a veneer over a mixed substrate: the filesystem, the refs, the channels are equally separated. The UI claim and the system claim are the same claim.
5. **Deliberate exception, labeled:** the capacity strip/console shows all organizations *because the pools are genuinely shared*; every cross-org element there carries org chips so the mixing is explicit, bounded, and legible (`06` §2).

## 6. Team scope — what changes (little)

The Operate surface (`operator-experience.md` §§2–6: work/pulse/costs, inspector, living plan, inbox) survives intact, re-rooted at `/teams/:id/operate` with the org scope bar above it and the org-picker landing page **retired** (the portfolio home replaced it). Two additions inside the team scope:

- Capacity state appears wherever budget state already does: the pulse header gains the team's burn + primary-window chip; assignment rows show capacity holds as scheduled-waiting (`04` §4's third visual state); the inspector's Session tab shows chunk/pacing state (K3) when active.
- The editor is unchanged except vocabulary (Team, not Organization) and the header's org breadcrumb.

## 7. Flows worth specifying

- **Create second organization** (the moment this series exists for): Home → `+ New organization` → name/purpose/theme (theme picker excludes taken colors) → optional budget → empty org section appears → add team. Under five minutes to the worked example's `personal` org.
- **Move a team** (custody transfer): team card overflow → Move → pick destination org → confirmation states what changes (budget scope, filesystem home, theme) and what cannot follow (nothing — profiles/secrets are team-scoped; capacity shares are org properties, not team properties) → blocked if actuated → audited.
- **Pause an organization** (leaving town; conserve the pool): org header overflow → `Pause all teams` → K1 fan-out with one confirm; the org section renders dimmed with a single resume affordance.
- **Introduce a team into a hot pool** (the user's scenario): Home shows maintenance dominating the capacity strip → `[▶ knobs]` on its card deep-links to the console's what-if row for that team (`06` §3) → apply → return. Two screens, round trip.

## 8. Component inventory and routes

New: `PortfolioHome`, `CapacityStrip`, `OrgSection`, `TeamCard`, `OrgPage`, `OrgBudgetEditor`, `OrgInbox`, `OrgActivity`, `MoveTeamDialog`, `ScopeBar`, `useOrgScope`, `usePortfolio` (one aggregate query: `GET /api/portfolio`), plus SSE: portfolio-level stream multiplexing per-team events with org tags (`07` §3). Renamed/re-rooted: `OrganizationListPage` → retired; `ExecutePage`'s org picker → retired; editor/operate pages re-routed under `/teams/:id`. Retained wholesale: everything inside operate, the inspector, the editor internals.

## 9. MVP cut

Ships in C1/C3 (`07` §1): portfolio home with capacity strip (levels may be tier-2/3 early), org sections, team cards with vitals and K1 toggle, org page with budget editor and org inbox, scope bar, move-team flow, wizard reframe. Fast-follows: org activity/receipts view, pause-org fan-out, per-card sparklines. Explicitly not in this series: any cross-team chart visualization at org level (there is no such chart — that absence is the design), and notification digests beyond org scoping (existing digest machinery already suffices once scoped).
