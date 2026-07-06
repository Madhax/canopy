# Actuation Roadmap — Build Order, Future Implementations, Future Milestones

## 1. Phase-2 build order (milestones for Claude Code)

Each ends green (pytest + vitest + golden vectors) and independently demoable.

| # | Milestone | Delivers | Demo |
|---|---|---|---|
| **A1** | Profiles, secrets, gateway | SQLite migration of phase-1 store; profile/binding/secret CRUD + UI; Secret Store encryption; Model Gateway with `anthropic` + `gemini` adapters, Steps, SpendEvents; Budget Ledger with reserve/hard-stop; `validate()` live-check | curl the gateway as a fake agent: metered completion from both providers; exhaust a meter and watch the 402 |
| **A2** | Sandbox + runtime boot | `SandboxProvider` ABC + `SubprocessSandbox` (Windows-safe); `canopy-agent` package: boot, charter fetch, A2A server + card, register, heartbeat; Agent Directory; Actuator provision/teardown state machine + reconciler; Actuate/Deactuate UI with per-node status | actuate a 4-node chart → four processes, four cards, all `ready`; kill one → auto-restart; deactuate → clean |
| **A3** | Router + bus | Channel derivation from the chart; `Bus` ABC + `SqliteBus` (FIFO, visibility timeout, DLQ); delivery workers; `/api/dp/a2a/*`; topology rejection; queue-depth surfacing | two agents exchange a mediated A2A task; a forbidden sibling call gets 403; queued delivery to a busy node |
| **A4** | Work: tools + artifacts + intent smoke path | Step loop with the closed tool set; workspace layout + jail; Artifact Store + `produce/fetch`; delegation/await tools; intent endpoint + task-tree tracking; Intent UI panel | **the DoD demo**: intent → root decomposes → delegates to reports → real Claude/Gemini work → artifacts → aggregated deliverable, spend attributed per node/step |
| **A5** | Economics + operations visible | Meter-per-task funding from chart salaries; warn events; paused-node flow + operator raise-meter; spend rollups + burn UI; activity feed; structured logs; crash-redelivery hardening (idempotent intake) | budget-warn glow on the live chart; hard-stop mid-intent; operator tops up; intent completes |
| **A6** | Packaging preview + hardening | `canopy-agent` published as installable package + reference Dockerfile; `docker` SandboxProvider behind the same ABC (opt-in); loopback/auth review; e2e Playwright: actuate → intent → artifact → deactuate | same org actuated with `sandbox.provider="docker"` per-org override, zero runtime changes |

## 2. Future implementations per abstraction

The seams are designed now; these are the planned swaps. None changes an interface — that's the acceptance test for every row.

| Abstraction (v1 impl) | Next implementations |
|---|---|
| **SandboxProvider** (`subprocess`) | `docker` (OCI image, cgroup limits, real fs/net isolation — A6 preview → hardened) → `microvm` (Firecracker; for executable tool grants) → `remote` (e2b / k8s Job / Cloud Run; off-host scale-out and the packaged **agent-as-microservice** deployment) |
| **Bus** (`sqlite`) | `redis` (Streams; multi-process workers) → `nats` (JetStream; self-hosted scale-out) → managed `gcp-pubsub` / `sqs`; adds **work pools** (competing consumers per team topic for fungible roles) and A2A **push notifications** for cross-host delivery |
| **ModelProvider** (`anthropic`, `gemini`) | `openai`, `bedrock`, `vertex` (Claude/Gemini via cloud IAM instead of raw keys), `ollama`/`vllm` (local models); gateway grows streaming, prompt caching, provider rate-limit pools, failover chains per profile |
| **Persistence** (SQLite repos) | Postgres (repo swap; unlocks multi-process control plane) → per-service databases at extraction time |
| **SecretStore** (local encrypted) | OS keychain, Vault, cloud secret managers; IAM-based providers remove stored keys entirely |
| **ArtifactStore** (local disk) | S3/GCS/MinIO backend; content-delivery URLs; retention policies |
| **Control plane** (modular monolith) | Extraction order when scale demands: Model Gateway first (stateless, hot path) → Message Router (stateless over shared bus) → Actuator/Directory → Ledger/Artifacts. Each is already interface-isolated with own tables |
| **Agent runtime** (thin loop) | Pluggable execution backends behind the same charter/tool contract — CrewAI (per the original README direction), LangGraph, or CLI-agent adapters (Claude Code as a worker, Paperclip-adapter-style) — all still metered through the gateway |
| **Workspace** (persistent dir) | Fresh-per-assignment provisioning, git-worktree workspaces for code roles, volume/object-backed workspaces for remote sandboxes |
| **UI** (status pills + panels) | Live execution theater: task-tree overlay on the chart, step drill-down, queue-depth heat, replayable activity timeline |

## 3. Major future milestones of the actuation phase (post-A6)

| Milestone | Content |
|---|---|
| **Hardened multi-tenancy on one host** | Docker default, per-sandbox resource quotas, OS-user fallback where Docker is unavailable, secrets never on disk unencrypted, audited loopback auth |
| **Distributed data plane** | Remote sandbox provider GA + managed bus + A2A push notifications: agents on many hosts, control plane still one deployment; agent registry becomes service discovery |
| **Agent as a product** | `canopy package <org> <node>` builds a standalone agent microservice image (charter baked, gateway/router URLs injected at deploy); k8s manifests; per-agent horizontal scaling for pooled roles |
| **Executable tool grants** | Shell/test-runner/browser tools gated on hard sandboxes (microVM), catalog tool-grant vocabulary from RoleTemplates enforced by the runtime |
| **Provider breadth & resilience** | OpenAI/Bedrock/Vertex/local adapters, failover chains, cost-optimizing model routing per role, prompt caching |
| **Control-plane decomposition** | Gateway and router extracted as horizontally scalable services; Postgres; OTel traces end-to-end (step → task → intent) |
| **Phase-3 handshake: Execution** | Full work layer on this fabric — Assignments, five Gate kinds, Plans/PlanStages with envelopes, rework funding, durable memory, cadences, calibration. The phase-2 objects that survive into it unchanged: Steps, SpendEvents, meters, artifacts, channels, charters |

## 4. Explicitly deferred

Multi-user/auth on the control plane (inherits phase-1 posture), Blueprints, cross-org visibility, marketplace distribution of profiles/charters, mobile operations UI. Each waits on real usage of the phase-2 fabric.
