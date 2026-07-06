# Canopy Risk Register — What Could Kill This, and How We Derisk It

**Status:** Living document · **Date:** 2026-07-05
**Purpose:** An honest inventory of the greatest risks to Canopy becoming real, used, and genuinely useful — with strategic modifications that reduce each one. Written against the current corpus: `domain-model.md`, the catalog docs, `org-chart-editor.md` (Phase 1, implemented), `phases.md`, and the `actuation/` suite (Phase 2, designed).
**How to read severity:** *Existential* = if unaddressed, the project fails even if everything else goes right. *Major* = costs the project its window or its users. *Manageable* = real but absorbable with ordinary discipline.

## The documents

| Doc | Context | Core question |
|---|---|---|
| `problem-fit.md` | Genuine problem | Is the pain real, whose pain is it, and is *structure* actually the cure? |
| `usefulness.md` | Usefulness | Will anyone get value before the full vision lands — and keep getting it after the demo glow fades? |
| `marketing.md` | Marketing | Can Canopy be found, understood, and chosen in a crowded 2026 agent-orchestration market? |
| `design.md` | Design (product/UX + domain) | Does the product's shape — editor-first, strict invariants — help or fight the user? |
| `architecture.md` | Architecture | Do the chokepoints, buses, and seams hold up — technically and economically? |
| `implementation.md` | Implementation | Can this surface area actually get built and kept correct with the resources at hand? |
| `scalability.md` | Scalability | What breaks first as orgs get deeper, busier, and more numerous — and is it code or cost? |

## Top-10 ranked register

| # | ID | Risk (one line) | Severity | Likelihood | Doc |
|---|---|---|---|---|---|
| 1 | PF-1 | The economic null hypothesis: one strong agent with good context beats a simulated org on cost *and* quality for most tasks | Existential | High | `problem-fit.md` |
| 2 | U-1 | Daily usefulness is gated behind Phase 3 — Phases 1–2 demo well but don't earn a second session | Existential | High | `usefulness.md` |
| 3 | MK-1 | Category crowding: Paperclip (our own reference!) plus platform-native orchestration commoditize the layer before Canopy ships | Major | High | `marketing.md` |
| 4 | DE-1 | Cold start: users must design an org, author bindings, and paste API keys before any output exists | Major | High | `design.md` |
| 5 | SC-1 | Cost scales with tree depth: coordination tokens (decompose/await/synthesize) can dwarf work tokens | Major | High | `scalability.md` |
| 6 | PF-2 | Roles-as-data quality ceiling: placeholder role instructions produce mediocre agents, and mediocrity compounds down the tree | Major | Medium | `problem-fit.md` |
| 7 | IM-1 | Surface area vs. velocity: ~10 control-plane modules, dual validators, 75-role content debt against (mostly) one builder | Major | Medium | `implementation.md` |
| 8 | AR-1 | Central mediation (gateway + router + SQLite single-writer) becomes a distributed monolith that bottlenecks before its extraction seams are exercised | Manageable | Medium | `architecture.md` |
| 9 | IM-2 | LLM-in-the-loop testing: e2e is flaky, slow, and costs real money — CI erodes or gets skipped | Manageable | High | `implementation.md` |
| 10 | MK-3 | "SimCity for agents": spectacular demo, weak retention — watched, starred, not used | Major | Medium | `marketing.md` |

## The five derisking moves that matter most

Each context doc details its own modifications; these five recur across contexts and should shape the roadmap directly:

1. **Prove the economics or pivot the pitch (answers PF-1, SC-1).** Build a benchmark harness early (Phase 2.5): the same three hero intents run (a) through a Canopy org and (b) through a single strong agent, with the ledger attributing every token. Publish results honestly. If the org wins on quality-per-dollar for even one class of work (long-horizon, parallelizable, verification-heavy), that class becomes the wedge. If it doesn't, the pitch pivots from "orgs do better work" to what the ledger already proves: **orgs make agent work governable, auditable, and costed** — which no single-agent loop offers.
2. **Invert the cold start: intent-first onboarding (answers DE-1, U-1).** Let a new user type an intent *first*; Canopy proposes the org (archetype + formation + roles) as a draft chart they approve — the org chart becomes the *explanation* of how their work will be done, not homework before it. This converts the editor from an entry barrier into the trust surface.
3. **Pull one gate forward (answers U-1, MK-1).** The domain model's soul is governance — approval before consequence, evidence after. A thin ApprovalGate (publish/spend actions pause for operator consent in the UI) belongs in Phase 2.5, not Phase 3. It is the single most differentiating *visible* behavior and it makes the smoke path feel like a product.
4. **Ship a mock/replay ModelProvider (answers IM-2, DE-1, MK-3).** A deterministic provider adapter (canned or recorded completions) makes CI cheap and green, demos free and reproducible, and "try Canopy without an API key" possible on day one.
5. **Narrow the launch catalog (answers IM-1, PF-2).** Keep all 26 archetypes in the docs as the vision; ship **3 hero archetypes** (suggested: `product-engineering`, `content-machine`-backed `growth-marketing`, `customer-support-center`) with genuinely excellent role instructions, presets, and benchmark results. Twenty-three thin archetypes hurt more than three deep ones help.

## What is *not* on this list

Things sometimes flagged that we judge low-risk here: the tree-only topology (a deliberate, defensible constraint — see `design.md` DE-3 for the escape valves), SQLite as v1 persistence (right-sized; see AR-2), A2A protocol churn (v1.0 is stable enough and it's confined behind the router), and open-source licensing strategy (Apache-2.0 intent is fine; revisit only at commercial-layer time).
