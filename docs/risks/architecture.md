# Risk Context: Architecture — Where the Structure Itself Can Fail

The actuation architecture is deliberately conservative: modular monolith, two mediation chokepoints, interface-first seams. Its risks are the flip side of its virtues — centralization, double-implementation, and seams designed but never exercised.

## AR-1 — Chokepoint centralization and the distributed-monolith trap *(Manageable · Medium)*

**The risk.** Every LLM call and every agent message round-trips through one FastAPI process backed by one SQLite file (single-writer, WAL or not). This is correct for invariants and fine for dozens of agents — but three pressures converge on the same process: gateway traffic (large payloads, long provider latencies), router/bus delivery loops, and the phase-1 editor API. Async FastAPI mitigates I/O blocking, but SQLite write contention (steps + spend events + queue state on every step of every agent) arrives earlier than the roadmap's "extraction when scale demands" implies. The trap: performance pain gets patched *inside* the monolith with threads and caches until the clean seams no longer describe reality — a distributed monolith before any distribution.

**Derisking modifications.**
- **Load-test the fabric with the mock provider before A4:** 50 fake agents × 20 steps each is an afternoon's test that reveals the real write-contention ceiling with zero API spend. Set a measured budget ("v1 comfortably supports N concurrent agents") and publish it rather than discovering it in a user's demo.
- Batch the hot writes (spend events + steps can be buffered per-task and flushed per-step-boundary transactionally with the meter check — the meter check itself must stay transactional).
- Keep the **extraction test** in CI-culture: gateway and router must remain importable/runnable standalone (a smoke test that boots each against the ABCs alone). Seams that are never exercised rot.

## AR-2 — Dual implementation drift (this time it's worse) *(Manageable · Medium)*

**The risk.** Phase 1 accepted Python+TS dual validators with golden vectors — sound. Phase 2 quietly multiplies the duplicated surface: the charter contract, tool schemas (neutral → Claude-format → Gemini-format), envelope shapes, and status enums all exist in ≥2 places (control plane, agent runtime, UI). Each is small; the sum is a drift field where a renamed status or an added tool parameter breaks agents at runtime rather than at build time.

**Derisking modifications.** One schema source of truth *per contract* with generation or vectors: pydantic models exported to JSON Schema, consumed by the UI's Zod layer (generation) and by contract tests in the runtime (vectors). Add "contract fixtures" (a canned charter, a canned envelope, a canned tool-call round-trip) that both server and runtime test suites must parse identically — same trick as the validators, applied to the new seams.

## AR-3 — At-least-once delivery vs. money *(Major · Medium)*

**The risk.** The bus is at-least-once; the runtime's crash-recovery restarts tasks "from intake." But steps cost real dollars: a task that crashes at step 18 of 20 and redelivers re-buys 18 steps. Worse, a *delivery duplicate* (visibility-timeout race) could run the same task twice concurrently against two meters, or double-complete toward a manager. "Idempotent: workspace/out re-derived; artifact versions dedupe by hash" (agent-runtime §6) handles artifacts but not spend or task identity.

**Derisking modifications.**
- **Delivery dedupe keys:** router assigns an idempotency key per (task, delivery-generation); the runtime records the active key; the gateway rejects steps bearing a stale generation. Concurrent duplicates become impossible at the money layer even if the bus misbehaves.
- **Meter continuity on redelivery:** a restarted task resumes its *existing* meter (spent tokens stay spent) — this is also the honest accounting; make it explicit in the ledger design rather than implied.
- Consider (Phase 2.5) checkpointing the loop's message history to the workspace per step, so restart resumes at step N+1 instead of step 1 — cheap insurance once transcripts are recorded anyway (DE-6).

## AR-4 — A2A as a hub-mediated protocol: cost without (yet) benefit *(Manageable · Medium)*

**The risk.** A2A's payoff is *interoperability with agents you don't control* — but v1 mediates everything through the router, agents are all Canopy's own runtime, and external agents are out of scope. Meanwhile the protocol brings real ceremony (cards, task-state mapping, JSON-RPC framing, SDK churn at v1.0) into the innermost loop. If the SDK's server model fights the single-flight runtime or the router's forward-auth, the project pays integration tax on its hottest path for a benefit that only materializes at federation time.

**Derisking modifications.**
- Keep A2A but **confine it**: the runtime should touch A2A only in one adapter module (server + client wrappers); the loop and tools speak internal types. If the SDK misbehaves, the adapter swaps for plain HTTP without touching agent logic — the reverse migration (internal RPC → A2A at the edges) stays open.
- Bank the interop win early and visibly: an A6+ demo where one node of the org is an *external* A2A agent (someone else's) would justify the protocol choice publicly and validate the card/auth path — put it on the roadmap explicitly.

## AR-5 — Phase-3 rework debt is being taken on knowingly *(Manageable · High)*

**The risk.** Several Phase-2 simplifications are placeholders the domain model will force back open: meter-per-routed-task (vs. per-Assignment), status enum without gates, "rejected + reason" standing in for ClarificationGates, workspace-persists-across-tasks (vs. per-Assignment + durable memory). Each is individually flagged in the docs — the risk is *interaction*: UI, ledger rollups, and operator habits will calcify around the simplified semantics, making Phase 3 a breaking migration of live orgs rather than an extension.

**Derisking modifications.** Name the placeholder objects with their final names now (the ledger interface already does this — extend the discipline to task/assignment naming in tables and APIs); keep a short `actuation/phase3-debts.md` ledger of every knowingly-simplified semantic with its target end-state; version the operator-facing API so gate-era responses can extend rather than mutate shapes.

## AR-6 — Secrets posture vs. future positioning *(Manageable · Low)*

**The risk.** Master key on disk beside the DB is right for trusted-local v1 and wrong for every future the roadmap names (teams, hosted, multi-tenant). The risk is not the design — it's the *drift of positioning* ahead of the hardening: the first "deploy Canopy for your team on a VPS" blog post inherits a single-operator threat model silently.

**Derisking modifications.** Write the threat model down (one page: what v1 defends against, what it explicitly does not); gate any multi-user/hosted messaging on the SecretStore roadmap items (keychain/Vault/IAM); keep run-token revocation and loopback binding tested so the parts that *do* claim security stay true.
