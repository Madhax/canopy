# Risk Context: Implementation — Can This Actually Get Built and Stay Correct?

Phase 1 shipping is real evidence of velocity. The implementation risks concern what changes at Phase 2: two languages become two *runtimes*, tests start costing money, and the surface area crosses the line where one person holds it all in their head.

## IM-1 — Surface area vs. build capacity *(Major · Medium)*

**The risk.** The Phase-2 inventory: ~10 control-plane modules behind ABCs, a separate agent-runtime package, a sandbox provider with Windows-specific process handling, two provider adapters, a bus, an artifact store, six UI surfaces, plus the 26-archetype/75-role/16-formation catalog transcription — maintained by (mostly) one person orchestrating AI coding agents. AI leverage is real but skewed: it multiplies code production, not *integration debugging* — and this design's hard parts are exactly integration (process lifecycle, delivery races, provider quirks, Windows). The likely failure is not "can't build it" but a long tail of 80%-done modules and a slipping A4 demo, which is the U-1 clock running out.

**Derisking modifications.**
- **A4 is the only milestone that matters; trade everything else for it.** Cut A2's reconciler to "restart on next actuate," defer A5's rollup UI, ship 3 archetypes not 26 (register move #5) — anything to reach intent→artifacts→spend earliest, because it de-risks PF-1/U-1 with *evidence* while the rest is still opinion.
- Exploit the ABC seams for **parallel agent-codeable workstreams** with contract fixtures as the interlock (`architecture.md` AR-2): gateway, sandbox, and runtime can be built by separate AI sessions against shared fixtures without merge collisions.
- Timebox catalog transcription by generating the frontmatter/JSON *from the existing markdown with an LLM pass + human spot-check* — it is exactly the kind of structured extraction AI does well, and CI integrity checks (already specced) catch the errors that matter.

## IM-2 — Testing with real LLMs: the eroding CI *(Manageable · High)*

**The risk.** Every meaningful Phase-2 behavior (loop, tools, delegation, budget-stop) involves a model. Real-API tests are slow, flaky (provider hiccups), and cost money per CI run — the standard outcome is engineers skipping them, then trusting them less, then a broken smoke path discovered during a demo. Determinism is also unreachable with live models, so "golden" e2e assertions rot.

**Derisking modifications.**
- The **mock provider** (register move #4) is the spine: scripted completions keyed by matcher (role + step), enabling deterministic full-fabric e2e — actuate, intent, delegation, budget-stop — with zero spend. Bus races and sandbox lifecycle get *more* coverage this way, not less, because tests can run hundreds of orgs.
- Add a **replay mode** (record one real run's completions to fixtures; replay in CI) for realism without flakiness; refresh fixtures deliberately, not per-commit.
- Keep exactly **one** real-API smoke job (nightly, both providers, one 3-node intent, spend-capped) as the canary for provider drift — isolated so its flakiness never blocks merges.

## IM-3 — Windows as the primary dev target *(Manageable · High)*

**The risk.** Development happens on Windows (D:\workspace, PowerShell history); the design notes Windows-specific process handling, but the ecosystem reality is broader: `asyncio` subprocess quirks on Windows event loops, uvicorn reload + child-process interactions, path/локale edge cases, NTFS slowness the Paperclip fork docs already complain about, and the fact that most deployment targets will be Linux. Single-platform development of a *process-orchestration* product is where "works on my machine" becomes architectural.

**Derisking modifications.** CI matrix (Windows + Linux) from A2 onward, with the sandbox-provider lifecycle tests as the core matrix content; make WSL2 the documented dev fast-path if native Windows friction mounts; treat the `docker` sandbox provider (A6) as the Windows escape hatch too, not just an isolation upgrade.

## IM-4 — Dependency-frontier churn *(Manageable · Medium)*

**The risk.** The stack pins itself to fast-moving edges: `a2a-sdk` (v1.0-era), `google-genai` (recently unified, still shifting), Anthropic SDK (stable but model names/pricing churn), React Flow v12/Tailwind v4. Any one breakage is trivial; the compound effect on a thin team is a recurring tax paid at the worst times.

**Derisking modifications.** Lock everything (uv lock + pnpm lockfile committed — already the norm); wrap each frontier dep behind the already-planned adapters (A2A adapter module per AR-4, ModelProvider per design) so upgrades are localized; keep the model-name/pricing table as *data* (config) not code, since it churns fastest of all.

## IM-5 — Correctness of the money path *(Major · Low-Medium)*

**The risk.** Most bugs in this system waste time; bugs in the meter/ledger/gateway path waste *user money* and destroy exactly the trust the product sells ("mechanical budgets"). Race conditions around reserve/spend/settle, double-dispatch on redelivery (AR-3), or a mispriced model table produce quiet overspend — the one bug class Canopy can't shrug off.

**Derisking modifications.** Property-based tests on the ledger (interleaved reserve/spend/settle sequences never go negative, never double-settle); the AR-3 idempotency keys; an invariant checker that replays a day's SpendEvents against meter states in CI; conservative defaults (hard-stop on, low allowances) so early bugs fail *cheap*; and a visible "estimates, not invoices" label on cost displays until pricing-table maintenance has a process.

## IM-6 — Design-doc drift *(Manageable · Medium)*

**The risk.** This corpus is now large and interlocking (domain model, phase specs, actuation suite, risks). Implementation will diverge — it always does — and un-updated design docs curdle from asset into liability, especially in an AI-agent-driven workflow where future coding sessions *read the docs as ground truth*.

**Derisking modifications.** Adopt Paperclip's rule that fits this repo already: contract changes update all affected layers *including the doc*, checked in PR review; add a lightweight `STATUS` header per doc (implemented / partial / design) — `phases.md` already models this; and prefer *amending* specs over piling correction docs (this risks suite deliberately references decisions rather than restating them).
