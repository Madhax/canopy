# Actuation (Phase 2) — Design Suite

**Status:** Implementation-ready draft · **Date:** 2026-07-05
**Phase:** Build → **Actuate** → Execute. Phase 1 (`../org-chart-editor.md`) produces a serialized Organization document. Phase 2 consumes it: for every agent node, provision a running agent — configured LLM, sandbox, workspace, communication endpoint — until the organization is *live and ready to receive an Intent*. Full work-layer semantics (Assignments, Gates, Plans, rework funding) are Phase 3; Phase 2 proves the fabric with one end-to-end intent smoke path.
**Authoritative upstream:** `../domain-model.md` — every design here is constrained by its invariants. `../org-chart-editor.md` defines the input document. Paperclip (`D:\workspace\paperclip`) is the DX/pattern reference (wakeup queues, execution workspaces, secret bindings, budgets, activity log) — reference only, no shared code.

## The documents

Read in this order:

| Doc | What it designs |
|---|---|
| `topology.md` | Control plane vs data plane, the component inventory, microservice abstraction rules, the self-hosted v1 deployment shape |
| `agent-profile.md` | The AI configuration assignable to each node: provider (Claude, Gemini), model, endpoint, key references, params — and how bindings attach to chart nodes |
| `control-plane.md` | The services: actuator, agent directory, model gateway, message router, budget ledger, artifact store, secrets, activity — plus REST API and SQLite schema |
| `data-plane.md` | How agents talk: A2A protocol usage, platform-mediated routing, the distribution-bus abstraction and its scalability story |
| `sandbox.md` | The sandbox abstraction encapsulating everything one agent needs to run; the v1 subprocess provider; future container/microVM providers |
| `agent-runtime.md` | The agent itself: boot, A2A server, the step loop, how it thinks (via the gateway), how it delegates and delivers |
| `workspace.md` | The agent's working directory and the artifact path from local file to addressable `org://` ref |
| `roadmap.md` | Future implementations per abstraction (Docker sandboxes, managed pub/sub, Postgres, packaged microservice agents) and the major actuation-phase milestones |

## Phase-2 definition of done

1. In the editor, assign an Agent Profile (Claude or Gemini) to every node of an org chart; click **Actuate**.
2. Every node becomes a running subprocess agent in its own sandbox with a private workspace; the chart shows live status per node.
3. Submit an intent to the root agent. The root decomposes it (real LLM call through the gateway), delegates sub-tasks to its reports over A2A (through the router), reports produce real artifacts into the artifact store, the root aggregates and returns a final artifact ref.
4. Every model call is a metered Step with a SpendEvent; exhausting a node's budget halts it *before the next model call*, visibly.
5. **Deactuate** tears everything down cleanly; re-actuation works.
6. No agent process ever holds an API key, sees another agent's workspace, or exchanges a message the chart doesn't allow — by construction, not by convention.

## Non-goals (Phase 2)

Full Assignment lifecycle, ClarificationGates/EscalationGates/plans/rework-funding (Phase 3); durable agent memory (stub only); catalog tool grants beyond artifact + delegation primitives; multi-host deployment; auth/multi-user; Blueprints; incremental re-actuation on chart edit (v1: deactuate → edit → re-actuate).
