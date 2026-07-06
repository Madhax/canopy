# Actuation Topology — Control Plane, Data Plane, and the Microservice Seams

## 1. The split

**Control plane** — knows about *organizations*: charts, profiles, budgets, artifacts, routing rules, provisioning state. It is the source of truth and the only holder of secrets. Nothing in the control plane executes an LLM loop on behalf of a role.

**Data plane** — the running agents: one process per agent node, each inside a sandbox, each speaking A2A. Agents hold no secrets, no global state, and no knowledge of the org beyond what the control plane tells them (their own identity, their manager, their reports).

The deliberate asymmetry: the data plane is **dumb and replaceable** (any agent can be killed and re-provisioned from control-plane state), while the control plane is **small and authoritative**. This is what makes "package the agent as a standalone microservice" a future deployment detail rather than a redesign: an agent already only needs its identity, a run token, and the control-plane URL.

```
┌─────────────────────────── CONTROL PLANE (FastAPI, one process in v1) ───────────────────────────┐
│                                                                                                   │
│  Org Registry / Catalog   Agent Profiles    Secret Store     Budget Ledger      Artifact Store    │
│  (phase-1 documents)      (LLM configs)     (encrypted)      (meters+spend)     (org:// refs)     │
│                                                                                                   │
│  Actuator                 Agent Directory   Model Gateway    Message Router     Activity Log      │
│  (provision state         (node → endpoint, (ONLY path to    (ONLY path         (audit events)    │
│   machine)                 card, health)     LLM APIs)        between agents)                     │
└────────┬──────────────────────────┬───────────────┬───────────────┬──────────────────────────────┘
         │ provisions               │ registers     │ LLM calls     │ A2A messages (mediated)
┌────────▼──────────┐   ┌───────────▼───────┐   ┌───▼───────────────▼───┐
│ Sandbox: root     │   │ Sandbox: report A │   │ Sandbox: report B     │        DATA PLANE
│ ┌───────────────┐ │   │ ┌───────────────┐ │   │ ┌───────────────┐     │  (one subprocess per
│ │ Agent runtime │ │   │ │ Agent runtime │ │   │ │ Agent runtime │     │   node in v1; one
│ │  A2A server   │ │   │ │  A2A server   │ │   │ │  A2A server   │     │   container/service
│ │  step loop    │ │   │ │  step loop    │ │   │ │  step loop    │     │   per node later)
│ │  workspace/   │ │   │ │  workspace/   │ │   │ │  workspace/   │     │
│ └───────────────┘ │   │ └───────────────┘ │   │ └───────────────┘     │
└───────────────────┘   └───────────────────┘   └───────────────────────┘
```

Two mediation chokepoints define the security and observability model:

- **Model Gateway** — agents never call Anthropic/Gemini directly; they call the gateway with a run token. The gateway resolves the node's Agent Profile, injects the credential, meters the call as a Step, and enforces the budget *before dispatch*. This mechanically satisfies domain invariants 7 (no work without a meter; the LLM is never asked to limit itself) and 10 (credentials never enter an agent).
- **Message Router** — agents never address each other directly; every A2A message goes through the router, which enforces the chart topology (manager↔report only — invariant 3), queues when the target is busy, and logs everything. The router *is* the pub/sub seam: v1 delivers over local HTTP, future backends swap in NATS/GCP Pub/Sub without agents changing.

## 2. Component inventory

| Component | Plane | v1 form | Owns | Detailed in |
|---|---|---|---|---|
| Org Registry & Catalog | control | phase-1 module | Organization documents, catalog | phase 1 |
| Agent Profile service | control | module | LLM configs, node bindings | `agent-profile.md` |
| Secret Store | control | module | encrypted API keys | `agent-profile.md` |
| Actuator | control | module | provision/teardown state machine | `control-plane.md` |
| Agent Directory | control | module | node → endpoint/card/health/status | `control-plane.md` |
| Model Gateway | control | module | provider adapters, Steps, SpendEvents | `control-plane.md` |
| Message Router | control | module | mediated A2A, queues, topology enforcement | `data-plane.md` |
| Budget Ledger | control | module | Salaries → meters → spend, hard-stops | `control-plane.md` |
| Artifact Store | control | module | immutable versioned artifacts, `org://` refs | `workspace.md` |
| Activity Log | control | module | append-only audit events | `control-plane.md` |
| Sandbox Provider | data | subprocess impl | agent process lifecycle + isolation | `sandbox.md` |
| Agent Runtime | data | `canopy-agent` pkg | A2A server, step loop, workspace use | `agent-runtime.md` |
| Workspace | data | local dir | brief/work/out layout | `workspace.md` |

## 3. Microservice abstraction rules

Every control-plane component must be **extractable** later without touching the others. Concretely, and enforceable in review:

1. **Interface first.** Each component is a Python class behind a small ABC (`ModelGateway`, `MessageRouter`, `SandboxProvider`, `ArtifactStore`, `SecretStore`, `BudgetLedger`, `AgentDirectory`, `Bus`). Callers depend on the ABC, never the implementation module.
2. **No shared tables.** Each component owns its SQLite tables; cross-component reads go through the owning component's interface. (This is the rule that makes the later split to per-service databases mechanical.)
3. **Serializable boundaries.** Every interface method's arguments and returns are Pydantic models — already wire-shaped. Extracting a component = wrapping the same models in HTTP/gRPC.
4. **IDs, not object references,** across component boundaries.
5. **Config-selected implementations.** `canopy.toml` picks implementations by key (`sandbox.provider = "subprocess"`, `bus.backend = "sqlite"`, `db.url = "sqlite:///..."`), Paperclip-adapter-registry style: implementations self-register in a registry keyed by name.
6. **The data plane already speaks network.** Agents interact with the control plane only over HTTP (gateway, router, artifacts, heartbeat) using their run token — an agent moved to another machine or packaged as a container needs a URL change, nothing else.

## 4. Self-hosted v1 deployment shape

One machine, two kinds of processes:

- `canopy-server` — the FastAPI modular monolith (phase-1 editor + all phase-2 control-plane modules) on port **8700**. SQLite at `data/canopy.db`; artifacts under `data/artifacts/`; sandboxes under `data/sandboxes/`.
- N agent subprocesses — spawned/supervised by the Sandbox Provider, each bound to `127.0.0.1:<ephemeral>` for its A2A server, registered in the Agent Directory.

`pnpm dev` (phase 1) still runs everything; actuation adds no new commands. A machine reboot mid-actuation is recoverable: actuation state is in SQLite, and the Actuator reconciles desired-vs-actual on startup (re-spawning dead agents), Paperclip-recovery-style.

## 5. Trust model (v1)

Single trusted operator on a trusted machine (Paperclip's "trusted local" mode). The run token (per-agent, minted at provision, revoked at teardown) exists so that *agents* are least-privilege — an agent can act only as itself — not to defend against a hostile host user. Network binds are loopback-only. Hardening beyond this is a sandbox-provider concern (`roadmap.md`).
