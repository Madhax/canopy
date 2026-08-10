# Organizations, Teams, and Capacity — Design Suite

> **Status:** Proposal — portfolio-and-capacity working group, 2026-08-08
> **Sequencing:** Pre-MVP prerequisite (operator decision, 2026-08-08) — the C-series in `07-implementation-plan.md` is part of the MVP implementation plan itself and lands **before** the full Canopy MVP is declared delivered. See `07` §0.
> **Reads with:** `../../domain-model.md` (authoritative for chart-level invariants), `../../org-roadmap.md` (O8 is realized here), `../../risks/scalability.md` (SC-5), `../../actuation/phase3-debts.md` (F1, F11, F13), `../connectors/` (sibling proposal series; same conventions)
> **Supersedes on adoption:** the *vocabulary* of `domain-model.md` §Organization / §Team, `phases.md` navigation, and the org-picker information architecture of `../../execution/operator-experience.md` §1. Nothing in the chart-level work model changes.

## The question

Canopy today has one load-bearing noun, **Organization**, doing three jobs at once: it is the actuatable chart, it is the unit of budgeting, and it is the top of the operator's world. That worked while there was exactly one of them. It stops working the moment the operator runs several charts at once for genuinely different purposes — a fleet serving Canopy's own development next to a fleet serving the operator's personal life — under **one shared pool of provider capacity** (a Claude Max subscription with 5-hour and weekly windows, a Google AI plan with its own windows).

Three questions, precisely:

1. **What is the missing abstraction?** Is today's Organization really a *Team*, with a true Organization — a named, budgeted group of teams — missing above it?
2. **How does the operator manage many teams at once?** Not from one giant chart: from a portfolio view where independent teams run concurrently, each legible at a glance, with hard separation between organizations that serve different purposes.
3. **How does Canopy treat provider capacity as a first-class, provider-truthful resource?** The 5-hour window is real infrastructure. Which team is consuming it, what knob frees capacity, how much does turning the knob free, and what happens when the window exhausts anyway — across more than one provider.

## The answer, in one paragraph

Today's Organization is renamed **Team**: the actuatable chart, unchanged internally, still nestable, still governed by all eleven invariants. A new **Organization** entity sits above it: a flat, named group of teams with its own identity, its own budget, and hard isolation walls — nothing crosses organizations except the operator. (The old derived manager-plus-reports grouping that `domain-model.md` called *Team* is renamed **Pod**, a word the catalog already uses.) Beside the org tree, a new **capacity layer** models each provider login as a **ProviderAccount** owning a **CapacityPool** of provider-defined **QuotaWindows** (Anthropic: `five_hour`, `seven_day`, `seven_day_opus`, `seven_day_sonnet`; Google: daily CLI requests, app windows). Window *levels* come from the provider — session-observed limit signals always, provider usage reads where available — never from silent arithmetic; window *attribution* (which team burned it) comes from Canopy's own per-step metering proportioned against provider-measured deltas, and is labeled as such. A **portfolio scheduler** turns that state into governance: per-team run states, concurrency caps, pacing, model-tier caps, priority classes, org-level capacity shares, and watermarks — each knob with a predicted effect in window percentage points — plus a **fallback ladder** (hold-and-resume at reset → degrade model → switch account → opt-in extra usage → park) that fires mechanically when a window exhausts. Two new operator surfaces make it navigable: a **portfolio home** (organizations and their teams, performance at a glance, separation made visual) and a **capacity console** (window gauges, per-team burn attribution, knobs with predicted effects, the limit-event feed).

## Reading order

| Doc | What it answers |
|---|---|
| `01-team-and-organization.md` | The rename, the new Organization entity, membership and isolation rules, org budgets, migration of the domain vocabulary |
| `02-capacity-model.md` | ProviderAccount, CapacityPool, QuotaWindow, readings and confidence tiers, attribution math, org capacity shares, prediction model |
| `03-provider-quota-adapters.md` | The concrete adapters: `anthropic-max`, `google-consumer`, api-key variants, `mock` — exact endpoints, fields, error shapes, and the compliance posture of each source |
| `04-scheduling-and-throttles.md` | The governor: the scheduler, the full knob inventory with predicted effects, capacity gates, the fallback ladder, fairness across orgs |
| `05-ux-portfolio.md` | UX: the portfolio home, organization pages, team cards, separation design, navigation rework |
| `06-ux-capacity.md` | UX: the capacity console — gauges, attribution, knob panel, what-if planner, limit-event feed, honesty rules |
| `07-implementation-plan.md` | Migration mechanics, API change map, schema sketches, C1–C7 milestones for Claude Code, test plan, doc-edit impact map |

## The worked example, carried end to end

One operator ("you"), one machine, one Canopy instance. Two organizations:

- **`canopy-inc`** — serves Canopy itself. Teams: `canopy-docs` (the O2 docs pod) and `canopy-maintenance` (the O3 bug-close org). Theme: sage. Budget: 70% share of the Anthropic pool, weekly cost ceiling published in the receipts feed.
- **`personal`** — serves your life. Teams: `household` (a coordinator + research-analyst pod handling errands, trip planning, purchase research). Theme: indigo. Budget: 30% share, small weekly ceiling, `interactive` priority — when you ask for something, it goes now.

Both organizations draw on the same two ProviderAccounts: your **Claude Max** login (windows: `five_hour`, `seven_day`, `seven_day_opus`) and your **Google AI plan** (windows: `cli_daily`, app windows observed-only). `canopy-maintenance` is configured `priority=batch, fallback=[hold-resume, degrade-model]` and runs as fast as admission allows. On a heavy afternoon it drives the `five_hour` window to 82%. The capacity console shows: the gauge at 82% with *resets 17:40* (provider-reported, 3 min ago), the attribution stack showing maintenance at 4.1 pp/hr, docs at 0.6, household at 0.2, and a runway line — *exhausts ~16:55 at current burn, 45 min before reset*. You want `household` responsive tonight, so you turn one knob: maintenance `maxConcurrentSessions 3 → 1`. The knob's chip predicted *−2.6 pp/hr*; the stack confirms it within the next two intervals. At 100% anyway, maintenance sessions hold at the turn boundary (an InterventionGate, `opened_by='trigger:capacity'`), auto-resume when the provider's `resets_at` passes; `household`, priority `interactive`, is admitted against the reserve you configured (a 15% watermark held back from batch work). Nothing about this was estimated in the dark: exhaustion came from the provider's own signal, the reset time from the provider's own timestamp, and every displayed number carries its source and staleness.

## The four pillars

- **Separation.** Organizations are hard walls: no shared artifacts, refs, secrets, repos, notifications, or views. The operator is the only bridge. The separation is visible (identity, theme, scoped surfaces) and structural (scoped tables, scoped filesystem, scoped budgets) — obvious in the view *and* in the design, per the requirement.
- **Provider truth.** Capacity numbers are the provider's numbers wherever a provider surface exists, event-anchored observations where one does not, and *labeled* estimates in the gaps. No silently synthesized quota. (This extends the "estimates, not invoices" and `fmtCostHonest` ethos, and closes the spirit of F1.)
- **Governable concurrency.** Teams run concurrently by default; the scheduler makes concurrency *governed* — every knob has a stated mechanism, a stated effect latency, and a predicted effect the console can show before you commit it. SC-5's noisy-neighbor risk gets its answer here.
- **Handoff-ready.** Every entity has a schema, every surface has a route, every milestone has acceptance criteria. `07-implementation-plan.md` is written to be handed to Claude Code as-is.

## Scope

**In scope:** the Team/Organization/Pod renaming and the new Organization entity; org budgets; the capacity domain (accounts, pools, windows, readings, attribution, prediction); provider quota adapters for Anthropic Max, Google consumer plans, api-key providers, and CI mock; the portfolio scheduler, knobs, capacity gates, and fallback ladder; the portfolio home and capacity console UX; migration and milestones.

**Non-goals (this series):** inter-team communication or delegation across teams (organizations are administrative groupings, not communication topology — the operator is the bridge; org-level coordination teams are an open item, not a design); multi-operator/multi-user; billing-grade cost accounting (costs stay estimates); cross-provider capacity *unit conversion* (pools are independent; dollars-estimated remains the only cross-provider lens); any change to chart-level semantics — assignments, gates, meters, memory, and the eleven invariants are untouched below the Team boundary.

## Relationship to the existing corpus

This series *realizes* `org-roadmap.md` §O8 ("Canopy Inc. — the org of orgs") administratively rather than topologically: O8 imagined mounting O2–O7 under one root chart; this design gives them a shared Organization with budgets and a portfolio view instead, and leaves chart-level mounting for the day inter-team work actually needs an edge. It *answers* SC-5 (multi-org noisy neighbor) with org shares and fair scheduling. It *extends* the F1 close-out (cache-token accounting) with a capacity ledger that finally distinguishes "what I spent" from "what I'm allowed." And it deliberately mirrors the `../connectors/` series in method: schema-first, enforcement named per mitigation, worked example carried end to end.
