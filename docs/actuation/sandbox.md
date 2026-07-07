# Sandbox — The Isolation Boundary Around One Agent

A **sandbox** encapsulates everything one agent needs to run: its process, its workspace, its network identity, its resource envelope, its lifecycle. Sandboxes are isolated from one another — invariant 2 (workspace isolation is absolute) is *this component's* job, together with the mediation chokepoints (agents have nothing worth stealing: no keys, no peer addresses).

## 1. Provider abstraction

```python
class SandboxProvider(ABC):
    key: str                                                    # "subprocess" | "docker" | ...
    async def create(self, spec: SandboxSpec) -> SandboxHandle: ...
    async def start(self, h: SandboxHandle) -> None: ...
    async def stop(self, h: SandboxHandle, grace_s: int = 10) -> None: ...
    async def destroy(self, h: SandboxHandle) -> None: ...      # includes workspace disposal per spec
    async def status(self, h: SandboxHandle) -> SandboxStatus:  # running | exited(code) | unknown
    async def logs(self, h: SandboxHandle, tail: int) -> str: ...

class SandboxSpec(BaseModel):
    actuation_id: str; node_id: str; org_id: str
    runtime: str = "canopy-agent"            # entrypoint identity; later: image ref for containers
    workspace_root: Path                      # provider-created, private to this sandbox
    env: dict[str, str]                       # STRICT WHITELIST — see below
    a2a_port: int | None                      # None ⇒ provider/agent picks and reports at register
    limits: Limits                            # best-effort in v1: max_rss_mb, cpu_nice, wall_clock only
    keep_workspace_on_destroy: bool = True    # forensics-friendly default; GC policy separate
```

The Actuator consumes only this interface. Provider selected by `canopy.toml` → registry, per the topology rules; **per-organization override** allowed (one org on docker, another on subprocess) since the spec is self-contained.

## 2. v1 provider: `SubprocessSandbox`

Each agent = one OS subprocess of the host's Python environment:

- **Spawn:** `python -m canopy_agent` with `cwd = workspace_root` and a **clean environment** — `env` is constructed from scratch (never inherited): `CANOPY_CP_URL`, `CANOPY_RUN_TOKEN`, `CANOPY_NODE_ID`, `CANOPY_ACTUATION_ID`, `CANOPY_A2A_HOST=127.0.0.1`, `CANOPY_A2A_PORT`, `PATH`/`PYTHONHOME` minimums, nothing else. No provider API keys exist anywhere in the data plane, so a leaked env leaks only a revocable run token.
- **Filesystem:** `workspace_root = data/sandboxes/<actuationId>/<nodeId>/` created `0700`. Isolation from sibling workspaces is by construction (agent code never receives another sandbox's path, cwd-jailed by convention) — *soft* isolation, honestly labeled: v1 trusts the agent runtime code, not OS enforcement. The runtime additionally refuses paths outside its workspace (defense in depth in `agent-runtime.md`).
- **Network:** A2A server binds loopback on the assigned port. Agents accept inbound connections **only from the control plane** (run-token-signed forward header) — direct peer dials are rejected even on localhost.
- **Supervision:** provider tracks pid + start time; `status()` via pid liveness; stdout/stderr teed to `workspace_root/../logs/<nodeId>.log` (rotating). Crash → Actuator reconciler restarts with backoff.
- **Stop:** SIGTERM → grace → SIGKILL. `destroy()` also revokes nothing itself — token revocation is the Actuator's job (ordering: revoke, stop, destroy).
- **Limits (best-effort):** RSS watchdog (poll, kill over `max_rss_mb`), `nice` for CPU, wall-clock cap per actuation. Real enforcement arrives with container providers.

Windows note (the dev machine is Windows): use `CREATE_NEW_PROCESS_GROUP` + `taskkill /T` for tree termination; paths via `pathlib` throughout; no POSIX-only calls in the provider.

## 3. Lifecycle within actuation

```
Actuator.provision(node) ─▶ create(spec) ─▶ start() ─▶ agent boots ─▶ registers (directory)
                                                          │ boot timeout ⇒ failed(node)
live: status() polled by reconciler; agent heartbeats independently (both signals feed health)
deactuate: router drains ─▶ stop() ─▶ destroy() ─▶ token revoked ─▶ directory row closed
```

One sandbox == one agent == one A2A endpoint. Sandboxes are cattle: any sandbox can be destroyed and re-created from control-plane state alone (charter + queue + artifacts all live upstream); an agent that dies mid-task loses only its in-flight step — the task redelivers from the bus (at-least-once) on restart.

## 4. Future providers (details in `roadmap.md`)

| Provider | Isolation gained | Notes |
|---|---|---|
| `docker` | real fs/net/resource isolation, packaged runtime image | first hard-isolation step; image = `canopy-agent` + pinned deps; limits become cgroups; port mapping replaces loopback ports |
| `microvm` (Firecracker/Cloud Hypervisor) | kernel-level isolation | for untrusted-code workloads (agents running arbitrary tools) |
| `remote` (e2b / Cloud Run / k8s Job) | off-host scale-out | agents dial the control plane over the network; A2A push notifications replace local forwards; this provider is also the "agent as standalone microservice" packaging path |

The `SandboxSpec.runtime` string becoming an OCI image reference is the only planned interface change, reserved now — plus the additions in `agent-envelope.md` §7: `tier` and `egress_policy` fields on the spec, and a `max_tier` declaration per provider. The provider ladder above maps onto the **sandbox tiers** (T0–T3) defined in `agent-envelope.md` §5, where the tier for each agent is *derived from its tool grants*, never chosen directly.
