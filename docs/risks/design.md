# Risk Context: Design — Product Shape, UX, and Domain-Design Choices

The design corpus is unusually disciplined: invariants stated, decisions recorded, non-goals explicit. The design risks are therefore mostly *second-order* — places where a locally-correct choice creates a globally hostile experience.

## DE-1 — Cold start: the org before the output *(Major · High)*

**The risk.** The current golden path demands, before any value: pick an archetype (26 choices) → build/wire a chart → define profiles → paste API keys → bind every node → actuate → compose an intent. That is six sophisticated decisions and one security-sensitive act before the first artifact. Every step is individually justified; the sum is a funnel that sheds the majority of curious arrivals. Phase 1 presets and formations mitigate chart-building, but nothing yet mitigates the *sequence*.

**Derisking modifications.**
- **Intent-first onboarding** (register move #2): the first-run screen asks "what do you want done?"; Canopy drafts the org (archetype + formation + bindings-to-one-default-profile) and shows it *as the plan*. Approve → actuate → run. The editor remains the power surface; it stops being the front door.
- **One key, many nodes:** a single org-default profile ("use this Claude key for everything") applied automatically, with per-node overrides as refinement later. The binding-per-node ceremony (already softened by "apply to all with this role") should be invisible on the golden path.
- **Zero-key first run** via the mock provider — let the funnel reach "watched an org complete an intent" before asking for a credential.

## DE-2 — Two-persona editor tension *(Manageable · Medium)*

**The risk.** The editor serves org *designers* (canvas, formations, salaries) and will increasingly serve org *operators* (status, burn, approvals, intents). Phase 2 bolts operator surfaces onto the designer layout (status pills, panels). These are different jobs — design-time density is operator-time noise — and a single surface serving both poorly is the default outcome of accretion.

**Derisking modifications.** `phases.md` already frames Build/Actuate/Execute as top-level navigation — commit to that: the *same chart* rendered in two modes (design mode: palettes/inspectors; operations mode: status/queues/burn/approvals, structure locked). Cheap now, expensive to retrofit after Phase-3 surfaces pile on.

## DE-3 — Invariant walls without doors *(Manageable · Medium)*

**The risk.** Tree-only reporting, sibling-only dependencies, team-scoped visibility: correct, and users will hit them within the first hour of real use ("QA needs the designer's spec" across teams). The domain model's doors — grants, brokered channels, publishing up — are Phase 3. Until then the walls are real and the doors are drawings, and users experience principled design as arbitrary limitation (`problem-fit.md` PF-4).

**Derisking modifications.** Every rejection message names the door: "cross-team data flows via the common manager — ask `engineering-lead` to publish the spec ref into the parent brief." When Phase-3 grants land, the *same* messages become actions ("request a grant"). Design the error strings now as future buttons. Also: the manager-mediated workaround (manager fetches ref, includes it in the child brief) works *today* on the Phase-2 grant-set mechanism — document it as the pattern, so the wall has a path around it from day one.

## DE-4 — Salary UX: numbers without instincts *(Manageable · High)*

**The risk.** Users must set `perAssignmentAllowance` in tokens per role — a unit nobody has intuitions for. Set high, budgets are theater; set low, orgs stall on hard-stops and Canopy "feels broken." The domain model's calibration engine (envelopes from actuals) is far away; v1 defaults are admitted placeholders. A governance product whose core dial is unusable undermines its own pitch.

**Derisking modifications.**
- Denominate the UI in **currency, not tokens** (per the profile's model pricing table): "$0.60 per task" is judgeable; "150k tokens" is not. Store tokens, display dollars.
- Ship **role-tier defaults** (lead/IC/reviewer × cheap/frontier model) and a per-org multiplier slider instead of 75 hand-set numbers.
- Treat the first hard-stop as a UX moment: show what was spent, on what steps, with one-click "top up ×1.5 and resume" — the intervention flow *is* the product teaching budget literacy.

## DE-5 — The catalog's promise outruns the runtime *(Manageable · Medium)*

**The risk.** `use-cases.md` markets 31 day-one recipes; the Phase-2 runtime honestly supports a fraction (file-artifact digital work; no shell, no web, no external systems). A user who picks use case #23 ("200-car lunch rush") gets nonsense. The gap between catalog imagination and tool-surface reality is a credibility risk *inside the product*, not just in marketing.

**Derisking modifications.** Gate the catalog by capability: archetypes/formations declare required tool grants; the wizard shows "runnable now / needs tools coming in vN" states honestly. This also creates the natural roadmap page — capability-gated catalog entries light up as tool surfaces land (web, shell-in-hard-sandbox, integrations).

## DE-6 — No design for failure narration *(Manageable · Medium)*

**The risk.** Agent systems fail weirdly: half-right artifacts, confident nonsense, loops that burn quietly to the step-cap. The Phase-2 surfaces show *states* (failed(step-cap), paused) but no design exists for the operator's actual question: "what went wrong and what do I do?" Products in this category live or die on debuggability of runs (Paperclip's transcript views, tracing accordions exist for exactly this reason).

**Derisking modifications.** Add a **run transcript view** to the Phase-2 UI backlog (per task: steps, tool calls, deltas, spend — the gateway already records everything needed); pair every terminal failure state with a recommended action; and log briefs verbatim so "bad decomposition" is visible rather than inferred. The observability tables exist — this is a UI investment, and it should outrank canvas polish.
