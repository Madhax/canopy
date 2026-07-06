# Risk Context: Scalability — What Breaks First as Orgs Grow

Scalability for Canopy is unusual: the *technical* ceilings (SQLite, one host) are known, seamed, and honestly documented. The binding constraint is more likely **economic and structural** — how cost and latency scale with org *shape*, which no bus swap fixes.

## SC-1 — Token economics scale with depth and ceremony *(Major · High)*

**The risk.** Every level of hierarchy adds coordination calls: intake, decomposition, per-child brief authoring, await/synthesize, acceptance. A 3-level org handling one intent pays the coordination tax at two management layers before any leaf does work; charters, briefs, and artifact summaries ride along as context in *every* call, so cost grows roughly with (nodes × steps × context-per-step) — and context-per-step grows with org complexity too. The product's own headline features (metering, ledgers) will make this overhead *visible*, which is honest and also means users will see exactly how much the org costs versus the work. If coordination is 60% of spend, the ledger indicts the architecture.

**Derisking modifications.**
- **Measure coordination share explicitly** — tag steps as coordination vs. production in the gateway (the loop knows which it's doing); make "overhead %" a first-class ledger stat. What's measured can be optimized; what's hidden becomes a scandal later.
- **Route cheap models to coordination:** decomposition/synthesis on fast-cheap models (Haiku-class, Flash-class), production on frontier models, per-role profiles — the two-provider design already supports this; make it the *default* template configuration, and the benchmark (PF-1) will quantify the savings.
- **Flatten by default:** presets should ship the shallowest org that satisfies the use case (manager + leaves); depth is an opt-in for scale, not a starting aesthetic. The tree constraint is a cap on wiring complexity, not a mandate for middle management.
- Compact briefs/charters aggressively (summaries + refs rather than full texts; artifacts fetched on demand already — extend the discipline to org context).

## SC-2 — Manager nodes are structural serialization points *(Major · Medium)*

**The risk.** Single-flight agents + tree topology = every subtree's throughput caps at its manager's task rate. Fan-out is parallel, but *acceptance* is serial: ten completed child tasks queue behind one manager doing one synthesis at a time. The domain model embraces this ("a growing queue is a bottleneck made visible; the fix is structural — add another node") — but adding a node means *redesigning the org*, a heavyweight response to a throughput problem, and deactuate-edit-reactuate (v1) makes it heavier.

**Derisking modifications.**
- Make queue-depth-driven advice concrete in the operations UI: "`support-lead` has averaged 7 queued tasks for 2 days → consider splitting the tier" — the Conway-telemetry idea from the domain model, applied to load.
- Prioritize **incremental re-actuation** (add/remove nodes without teardown) earlier than the roadmap implies — it's the difference between "tune your org" and "reboot your company," and it unblocks the structural fix the philosophy prescribes.
- **Work pools** (roadmap item) are the real answer for fungible-role hot spots (support tiers, pipeline stations, franchise shifts — the catalog's highest-volume archetypes all match); pull the design forward even if implementation waits.
- Cheap acceptance: managers can accept-with-spot-check (validate contract shape + sample) rather than full-review every deliverable — an acceptance-policy knob per formation, priced accordingly.

## SC-3 — The known single-host ceilings *(Manageable · Medium)*

**The risk.** One machine bounds everything: agent count (a subprocess each — Python interpreter memory × N), SQLite write throughput across gateway/ledger/bus/router (all hot on the same file), loopback port pool, and provider **rate limits pooled through one gateway and typically one API key** — thirty agents share one org's Anthropic tier, so bursts hit 429s that serialize the whole org regardless of local capacity.

**Derisking modifications.** The seams already exist (bus swap, sandbox `remote`, Postgres, gateway extraction) — the additions are: measure the actual ceilings with the mock-provider load test (AR-1) and publish "v1 comfortably runs N agents"; implement gateway-level **rate-limit-aware queuing with per-provider concurrency caps** in v1 (cheap, prevents the 429 cascade); support multiple keys per provider per org (key pools) as a v1.5 item since it's pure gateway logic; and lazy-start sandboxes (spawn on first delivery, reap after idle) so *actuated* size can exceed *resident* size.

## SC-4 — Scale multiplies operator attention *(Manageable · Medium)*

**The risk.** The governance design routes exceptions upward — approvals, interventions, budget top-ups — and in v1 the top of every escalation path is one human. At 5 agents this is engagement; at 50 it's a pager. The domain model anticipates this (managers get bounded auto-resolution authority) but that's Phase 3; meanwhile "scalable service" quietly assumes a scalable *supervisor*.

**Derisking modifications.** Batch and rank the approval surface from its first version (one queue, grouped by kind, bulk-approve for low-stakes classes); implement manager auto-resolution bounds ("approve up to +20% once") as *the first* Phase-3 gate feature rather than the last, since it's the attention-scaling mechanism; and default Cadence-generated work to tighter budgets so the recurring background load rarely escalates at all.

## SC-5 — Multi-org and the noisy neighbor *(Manageable · Low, until it isn't)*

**The risk.** The design is multi-org (company-scoped everything, per Paperclip's lesson), but v1 shares one process, one DB, one gateway, one bus across all actuated orgs on the host. One runaway org (or one 200-task franchise shift) degrades every other org's latency — invisible in single-org development, guaranteed in the first serious self-hosted deployment.

**Derisking modifications.** Per-org concurrency caps at the gateway and delivery workers (config, not architecture); per-org spend/queue dashboards so degradation is attributable; and fold "org fairness" scenarios into the mock-provider load test suite so the behavior is at least *known* before it's *reported*.
