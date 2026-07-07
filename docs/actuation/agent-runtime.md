# Agent Runtime — The Process Behind Every Node

`canopy-agent` is one Python package, identical for every role — roles are data (invariant 11), so the runtime is a generic shell that loads a charter and behaves accordingly. It is deliberately thin: **all** intelligence goes through the Model Gateway, **all** communication through the Router, **all** outputs through the Artifact Store. What remains here is the loop.

> **Scope note:** this doc specifies the `loop` runtime kind — the first of several agent implementations behind one envelope contract. `agent-envelope.md` defines the full encapsulation model (tool grants, runtime kinds `loop`/`cli`/`actor`, sandbox tiers); under it, the §3 tool table below is the **baseline grant set** every envelope receives, extended per role by catalog tool grants.

## 1. Boot sequence

1. Read env (`CANOPY_CP_URL`, run token, ids, A2A host/port).
2. `GET /api/dp/charter` → the compiled charter: `{ nodeId, orgId, displayName, roleKey, instructions (compiled: role base + extensions + profile preamble), managerNodeId, reportNodeIds[], salary, workspaceLayout }`. The runtime never reads the org document.
3. Prepare workspace subdirs (`workspace.md`), start the A2A server (`a2a-sdk`, JSON-RPC binding) on the assigned port, publish its **Agent Card** (name = node display name; skills = role responsibilities summarized; provider/model deliberately absent).
4. `POST /api/dp/register` with the endpoint; begin 10 s heartbeats (status + queue hints); status `idle`.

Boot is charter-driven and stateless — restart = same sequence; any in-flight task redelivers from the bus.

## 2. Execution model

Single-flight, matching the domain: **one task executing at a time**. Delivered A2A tasks beyond the current one are answered `working`-queued locally? No — the runtime *rejects* concurrent delivery (`503 + Retry-After`); queueing lives in the bus (single source of queue truth, visible to operators). The delivery worker only sends when the directory shows `idle`, so rejections are a race fallback, not a path.

Per task, the runtime runs a **step loop** (phase-2 simplified assignment lifecycle):

```
receive task ─▶ INTAKE: parse brief, resolve cited artifact refs into workspace/brief/
            ─▶ LOOP (bounded, default max 20 steps):
                 build messages (charter instructions + brief + working context + tool results)
                 POST /api/dp/llm/complete            ◀── every model call = one metered Step
                 dispatch returned tool calls (below), append results
                 until finish tool called or step cap ⇒ fail(step-cap)
            ─▶ DISCHARGE: upload outputs from workspace/out/ ⇒ org:// refs,
                 complete the A2A task with refs as A2A artifact parts
402 BUDGET_EXHAUSTED at any step ⇒ status paused, task → failed(budget), note to manager
```

## 3. The tool surface (v1, closed set)

Tools are the runtime's capabilities, executed locally or via control-plane APIs — the LLM never gets raw network access. Provider-formatted for Claude/Gemini by the gateway from one neutral schema:

| Tool | Effect | Notes |
|---|---|---|
| `write_file(path, content)` / `read_file(path)` / `list_files()` | workspace I/O | paths jailed to the workspace (canonicalize + prefix check — defense in depth against escapes) |
| `produce_artifact(path, type, name)` | upload from `workspace/out/` → returns `org://` ref | the only way work leaves the sandbox |
| `fetch_artifact(ref)` | download into `workspace/brief/` | control plane checks the ref is in the task's granted set |
| `delegate(reportNodeId, brief, artifactRefs[], deliverableContract)` | **managers only** (charter has reports) — router creates an A2A task on the report | returns child task id; polls/receives completion via router callbacks |
| `await_reports(taskIds[])` | block on child task completions, receive their artifact refs | the fan-out/fan-in primitive for the smoke path |
| `message_manager(text)` / `reply_report(taskId, text)` | mediated messages on existing tasks | escalation-shaped questions surface as A2A `input-required` |
| `finish(summary, artifactRefs[])` | ends the loop, triggers discharge | |

No shell, no web, no pip in phase 2 — the artifact workflow is file-based (documents, code-as-text, data files). Executable tool grants (run tests, browse) are a roadmap item tied to hard sandboxes, because `write_file` + shell inside soft isolation would break the trust model.

## 4. Manager behavior vs IC behavior

Same binary, charter-differentiated. A charter with `reportNodeIds` gains the delegation tools and an instruction block teaching the delegate → await → synthesize pattern (decompose the brief, one child task per report as appropriate, cite artifact refs, aggregate results into its own deliverable). A leaf charter gets the maker instruction block (do the work in `workspace/work/`, deliver via `produce_artifact` + `finish`). Child-org roots are just managers whose "manager" is their mount agent — nesting needs no special code.

## 5. Memory (stub) and observability

`workspace/memory.json` — a scratch note the runtime persists per node across tasks in phase 2 (task summaries only). Explicitly *not* the domain's durable memory design; replaced in phase 3 (`roadmap.md`). Observability: every step already lands in the gateway's tables; the runtime adds structured stderr logs (`ts, nodeId, taskId, event`) captured by the sandbox provider — a stuck agent is diagnosable from control-plane data alone (steps show token burn; logs show the loop).

## 6. Failure semantics (phase 2)

| Failure | Behavior |
|---|---|
| Provider 4xx/5xx via gateway | retry ×2 with backoff, then task `failed(provider)`, message upward |
| Budget exhausted | halt before dispatch (gateway-enforced), task `failed(budget)`, node `paused` until operator raises the meter (ledger API) or deactuates |
| Step cap | task `failed(step-cap)` — the phase-2 stand-in for stall detection |
| Malformed brief | task `rejected` with reason (ClarificationGate proper is phase 3) |
| Crash | sandbox restarts, bus redelivers, task restarts from intake (idempotent: workspace/out is re-derived; artifact versions dedupe by content hash) |

## 7. Packaging seam

The runtime ships as an installable package with a pinned lockfile and a single entrypoint honoring only the env contract in `sandbox.md` — which *is* the microservice packaging story: a Dockerfile around `pip install canopy-agent` + that env contract produces the standalone agent image for the docker/remote sandbox providers, with zero runtime code changes.
