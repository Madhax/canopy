# Risk Context: Does Canopy Solve a Genuine Problem?

The vision — "the chart isn't a diagram of the system, it **is** the system" — is coherent and differentiated. The risk is not incoherence; it is that the *specific cure* (organizational structure) may not match the *actual disease* (agent work that is unreliable, unaccountable, and expensive). This doc separates the real pains from the assumed ones.

## PF-1 — The economic null hypothesis *(Existential · High)*

**The risk.** For a large share of tasks users actually have, a single strong model with a good context window, tools, and a loop will produce equal or better output than a simulated multi-role organization — at a fraction of the tokens and wall-clock. Frontier context windows keep growing; frontier models keep getting better at self-decomposition. Every Canopy hop costs real tokens: the manager decomposes (LLM call), each report intakes and works (calls), the manager synthesizes (calls). If a 6-node org spends 5× the tokens of a single agent to produce 1.1× the quality, the product is a loss machine and no amount of architecture rescues it.

**Why it might be wrong (the bull case to test, not assume).** There are task classes where structure plausibly wins: work that exceeds one context window; work that parallelizes (12 course modules, 40 support tickets); work where *independent verification* is the value (fact-checker, QA, site-inspector patterns — the catalog is full of these deliberately); and work that runs for days where a single loop drifts. The domain model's checkable-deliverable contracts are a genuine anti-drift mechanism.

**Derisking modifications.**
- **Benchmark harness as a first-class deliverable (Phase 2.5).** Same intent, org vs. single-agent baseline, ledger-attributed cost, blind quality rubric. Run it on the three hero use cases. This is cheap relative to the information it buys — it is the project's most important experiment.
- **Position the ledger as the product even if quality ties.** "Know what every artifact cost, who made it, who approved it" is real value a monolithic agent cannot offer; Canopy's metering-between-steps is architecturally honest in a way competitors' self-reported costs are not.
- **Target the win conditions.** Bias the hero use cases toward parallel + verification-heavy work (support triage, content pipelines, test-gated engineering), not tasks a single agent does fine (write me a blog post).

## PF-2 — Roles-as-data quality ceiling *(Major · Medium)*

**The risk.** "Roles are data, not code" is the right architecture, but it moves the entire quality burden into catalog *content*: 75 roles whose `promptSummary`/instructions are currently placeholders. An org of agents is a pipeline of prompts; a mediocre `engineering-lead` charter produces bad decompositions that no excellent `backend-engineer` downstream can save. Worse, failures will read as "Canopy doesn't work," not "this role's instructions are thin."

**Derisking modifications.**
- Treat role instructions like code: versioned (already), *tested* (golden-task evals per hero role — "given this brief, does the lead produce a sane decomposition?"), and iterated against transcripts.
- Ship 3 deep archetypes rather than 26 shallow ones (register move #5); mark the rest "community-callable" honestly.
- Add a **transcript→instruction feedback loop** to the roadmap: when an operator corrects an agent (Phase 3 directives), offer to fold the correction into the role/extension — the "Automatic Organizational Learning" idea from the long-term vision, pulled toward the catalog.

## PF-3 — Whose pain, exactly? *(Major · Medium)*

**The risk.** The docs speak to two different users without choosing: the **operator** (wants outcomes: tickets resolved, features shipped, cost controlled) and the **org designer** (enjoys building the machine). The 26-archetype breadth — clinics, franchises, construction crews — reads as designed for the second persona. But the second persona is a hobbyist market; the first pays. Physical-world archetypes (line cooks, electricians) also depend on ActionAttestations by *humans executing what agents sequence* — a coordination claim that is untestable until real-world users exist, and which can make the whole catalog feel speculative.

**Derisking modifications.**
- Declare the launch persona: a technical solo founder / small team running **digital** work (code, content, support, research) who already burns money on agent subscriptions and has lost track of what runs where. Paperclip's own positioning validates this segment exists.
- Move physical-world and clinic archetypes to a clearly-labeled "frontier catalog" section — vision, not promise. They are great marketing imagery and weak first products.
- Write the three hero use cases as *outcome* stories ("first response under 2 hours, and you can audit every resolution") rather than *structure* stories ("build a support org").

## PF-4 — The strictness bet *(Manageable · Medium)*

**The risk.** Canopy's invariants (tree-only, mediated comms, single-flight agents, contracts for everything) are its identity — and every one of them is friction a rival can undercut with a looser, faster tool. If users experience the invariants as bureaucracy before they experience them as safety, they leave before the payoff.

**Derisking modifications.**
- Make every rejection *teach*: the "siblings only — sequence one level up" style of error (already specced) should be universal; each wall the user hits must explain the org-design principle behind it and offer the sanctioned alternative in one click.
- Keep the strictness in the runtime but soften it in the authoring flow (drafts save with errors — already the Phase-1 stance; keep that spirit in Phases 2–3).
- Publish a short "why so strict" manifesto doc; strictness sells to the governance-minded buyer *if narrated*, and reads as arbitrary if not.
