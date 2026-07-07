# canopy-agent

The generic per-node agent runtime (Phase 2). One package, identical for every role — roles are
data (invariant 11), so the runtime is a thin shell that loads a **charter** from the control plane
and behaves accordingly.

It never imports `canopy_server`; it talks to the control plane only over HTTP using its run token.
That is the microservice-packaging seam (`docs/actuation/agent-runtime.md` §7): the same code
becomes the standalone agent image for the `docker`/`remote` sandbox providers with zero changes.

## Env contract (set by the sandbox provider — `docs/actuation/sandbox.md` §2)

| Var | Meaning |
|---|---|
| `CANOPY_CP_URL` | control-plane base URL |
| `CANOPY_RUN_TOKEN` | this agent's run token (the only credential it holds) |
| `CANOPY_NODE_ID` / `CANOPY_ACTUATION_ID` | identity |
| `CANOPY_A2A_HOST` / `CANOPY_A2A_PORT` | bind address; port `0` ⇒ pick ephemeral, report at register |

## What A2 does

Boot → fetch charter → prepare workspace (`brief/ work/ out/`) → start the card server → register →
heartbeat. The step loop, tools, and the full A2A task server arrive in A3/A4; A2 proves the fabric
(process up, card served, registered, heartbeating, ready).

    python -m canopy_agent
