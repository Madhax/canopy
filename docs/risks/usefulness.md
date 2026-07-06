# Risk Context: Usefulness — Value Before the Vision Completes

Canopy's plan is three phases, and its *value* is unevenly distributed across them: Build produces a drawing, Actuate produces a standing (idle) org, and only Execute produces work. That backloading is the central usefulness risk.

## U-1 — Value gated behind Phase 3 *(Existential · High)*

**The risk.** Phase 1 (implemented) is a pleasant editor whose output nothing consumes yet. Phase 2's definition of done is one intent smoke path. The things that make Canopy *daily-useful* — gates, plans, cadences, dependable delegation, memory — are all Phase 3. The realistic failure mode is not a crash; it is a user who actuates an org, runs two intents, gets artifacts slightly worse than their chat workflow, and never returns. Meanwhile the build effort ahead (Phase 3 is the largest phase) is funded by exactly that user's enthusiasm.

**Derisking modifications.**
- **Re-slice phases by *user value*, not by architectural layer.** Phase 2.5 should be "one hero use case, end-to-end, genuinely good": e.g. `support-tier` with real ticket ingestion via a webhook, or `content-machine` with a weekly cadence — including the thin ApprovalGate (publish requires consent) and the KB/dependency pattern that makes the formation's promise real. One vertical slice of Phase 3 semantics beats a horizontal layer of them.
- **Make Actuate itself useful:** the live chart with burn rates, queue depths, and status is an *observability product* even before execution matures — position it as "finally see what your agents cost," and let it monitor intents however shallow.
- **Cadences early.** A recurring intent ("every Thursday, draft the newsletter") converts Canopy from a tool you remember to open into a system that runs without you — the retention mechanism the domain model already designed (`Cadence`). It is small to implement on the Phase-2 fabric (a scheduler publishing intents to the bus) and disproportionately valuable.

## U-2 — The second-session problem *(Major · High)*

**The risk.** First session: wow (live chart, glowing nodes). Second session requires a *reason to return*: either standing work (cadences, queues) or artifacts whose quality beat alternatives. Canopy's demo assets are strong; its return-visit hooks are, today, absent from the design docs entirely — there is no notification story, no digest, no "here's what your org did while you were gone."

**Derisking modifications.**
- Add an **"while you were away" surface** to the Phase-2 UI backlog: intent completions, budget warns, approvals waiting. Even email-less (a badge and a feed) it reframes Canopy as an ongoing operation.
- Approvals-waiting is the natural pull mechanism: a paused governed action *needs* the human. This is another reason to pull ApprovalGate forward (register move #3).
- Instrument return-rate honestly from the first self-hosted telemetry decision (opt-in, Paperclip-style), or at least in your own usage: if *the founder* doesn't return daily to their own org, users won't.

## U-3 — Output quality is hostage to delegation quality *(Major · Medium)*

**The risk.** In the smoke-path design, the root decomposes an intent with a single LLM call over a charter. Decomposition is the hardest cognitive act in the system, performed at the point of least context. A bad split (overlapping briefs, missing constraints, wrong sequencing) wastes the entire subtree's tokens — the user pays for the org's confusion. The domain model's remedies (ClarificationGate, plan review, brief versioning) are Phase 3.

**Derisking modifications.**
- **Human-approved delegation option in Phase 2:** before the root's child tasks dispatch, show the proposed decomposition in the intent panel for one-click approve/edit. It is a temporary training wheel that doubles as the future plan-review UI, and it protects early users' wallets from the worst failure mode.
- Invest hero-role instruction effort disproportionately in **manager roles** (leads, editors-in-chief, directors) — decomposition quality is where role-content dollars pay most (`problem-fit.md` PF-2).
- Cap subtree fan-out and budget per intent by default (already partly in salary design); make "this intent may cost up to ~X" visible before dispatch.

## U-4 — Usefulness for the builder-user is real but bounded *(Manageable · Medium)*

**The risk.** The editor alone (Phase 1) has genuine but niche standalone value — thinking tool, documentation of intended agent processes, org-design sandbox. If the runtime slips, the editor's value plateau becomes the product's ceiling, and "beautiful org charts for agents you can't run" invites mockery.

**Derisking modifications.**
- Keep editor-only value honest but real: the serialized document is already versionable/diffable — lean into "org-as-code" (PR-review your org changes) as a legitimate practice that pays off the moment actuation lands.
- Resist further editor polish investment until the A4 smoke path exists; every week of canvas refinement before an artifact exists deepens U-1.
