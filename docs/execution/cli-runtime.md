# CLI Runtime — Wrapping Headless Claude Code Sessions (No API Key)

**Status:** Implementation-ready draft · **Date:** 2026-07-06
**Upstream:** `../actuation/agent-envelope.md` §4.2 (the `cli` kind this implements), `../actuation/agent-runtime.md` (the adapter shell reuses its boot/register/heartbeat), `work-model.md` + `engine.md` (what the adapter reports to).
**The constraint:** the operator has **no Anthropic API key** — only a machine with the Claude Code CLI logged in under a subscription. So the envelope doc's original `cli` plan (CLI pointed at the Model Gateway via `ANTHROPIC_BASE_URL`, gateway injects the key) is not available: there is no key to inject, and subscription OAuth is pinned to the CLI's own auth flow. This doc adapts the design: **the CLI session is the agent's brain and loop; the adapter around it observes, meters, gates, and reports.** Every invariant is preserved except per-model-call budget enforcement, which coarsens to per-turn (§7, debt E-D1).

---

## 1. Shape

`canopy-agent` gains a runtime-kind registry (envelope §4); `cli-claude` is the second kind after `loop`. One adapter process per node (same sandbox contract, same env, same boot: charter → register → heartbeat). Per assignment, the adapter runs one **headless Claude Code session**:

```
adapter (python, the sandboxed process)
  ├─ boot: fetch charter, register, heartbeat (unchanged from A2)
  ├─ inbox: receives assignment deliveries / gate resumes from the bus (A3 delivery, unchanged)
  └─ per assignment:
       1. INTAKE   materialize assignments/<id>/brief/ (fetch refs via dp API)
       2. CONFIG   generate the session sandbox: settings.json (permissions ⟵ grant set),
                   .mcp.json (exactly one server: canopy → control plane, run-token auth),
                   CLAUDE.md (charter instructions + assignment protocol)
       3. RUN      claude -p "<intake prompt>" --output-format stream-json --verbose
                     --max-turns <cap> --permission-mode default
                     --mcp-config <generated> --strict-mcp-config
                     --allowedTools <from grants> --disallowedTools <denials>
                     (cwd = assignments/<id>/work/, or the materialized worktree for repo roles)
       4. OBSERVE  parse stream-json events → Steps, ToolEvents, plan updates → dp reports
       5. GATE     meter check between turns; engine halt flags honored at turn boundaries
       6. DISCHARGE session called MCP finish → adapter confirms deliverable submitted, closes out
       resume:     gate resolution / children-complete → claude --resume <sessionId> -p "<payload>"
```

The session id from the stream-json `init` event is stored as the assignment's `session_ref` — the resume handle that makes gates cheap: a gated assignment is a *suspended conversation*, not lost context.

## 2. Session configuration is compiled, never authored

Everything Claude Code is allowed to do is **generated from the envelope** at intake — the operator and the catalog decide; the session cannot vote:

| Session surface | Compiled from |
|---|---|
| `settings.json` `permissions.allow` / `deny` | the node's effective grant set (envelope §3.2). Examples: engineer gets `Edit`, `Write`, `Bash(git *)`, `Bash(npm test *)` scoped to its worktree; QA gets `Bash(npm test *)`, `Bash(npx playwright *)`, read-only checkout, **no** `Edit/Write` on source; the lead gets **no** `Bash`, no `Edit` — only MCP canopy tools. `deny` always includes `WebFetch`, `WebSearch` unless a `web.read` grant exists. |
| `.mcp.json` | exactly one server: the control plane's canopy MCP endpoint with the node's run token. `--strict-mcp-config` guarantees no user/host MCP servers leak in. |
| `CLAUDE.md` | charter instructions (role + extensions + directives) + the assignment protocol (§3) + the memory block. |
| `--max-turns` | from salary/envelope defaults — the step-cap stall guard. |
| model | profile's `model` → `--model` (subscription decides what's actually available; `PROFILE_UNREACHABLE` check becomes a `claude --version`/ping probe at actuation). |

This is defense-in-depth, honestly labeled for v1: generated permissions + server-side grant checks on every MCP call are the real walls; on the subprocess sandbox tier, `Bash` scoping is best-effort (§8). The engineer/QA separation additionally holds **structurally**: separate workspaces, separate worktrees, deliverable contracts of different types, and no channel between them (invariants 2–4).

## 3. The assignment protocol (what the session is taught)

The generated `CLAUDE.md` teaches a fixed protocol, role-flavored:

- **Every agent:** you have exactly one assignment; its brief is in `brief/`; declare a plan with `canopy.declare_plan` before working; keep the stage cursor honest with `canopy.update_stage`; ship results only via `canopy.produce_artifact` from `out/` (or your worktree branch, for repo roles) and end with `canopy.finish`. If the brief is defective, `canopy.open_clarification` — do not guess. If you need a decision above your pay grade, `canopy.escalate` — asking is cheaper than guessing.
- **Managers additionally:** decompose the brief; one `canopy.delegate` per child with a self-contained brief, cited refs, an explicit deliverable contract, and `dependsOn` for sequencing; then `canopy.finish_turn` to await. When resumed with completed child work, review against the contract and `canopy.accept`/`canopy.reject` with a note; synthesize accepted refs into your own deliverable. You may check `canopy.reports_status` (R1) at any time. You never do your reports' work — you have no tools for it (envelope §6.5: austerity is the design).
- **ICs additionally:** the deliverable contract is exactly what you discharge — nothing else is accepted (envelope enforcement layer 4).

## 4. The Canopy MCP server (control-plane side)

New control-plane surface: an MCP server (streamable HTTP) mounted at `/api/dp/mcp`, authenticated by run token, exposing **only** the tools the caller's grant set + charter allow (surface filtering, envelope layer 1) and re-checking server-side per call (layer 2 — a hallucinated tool call is a 403, logged). It is a thin veneer over the `engine.md` §5 endpoints — one authorization path for both runtimes.

Baseline tools (every agent): `get_assignment`, `declare_plan`, `update_stage`, `produce_artifact`, `fetch_artifact`, `open_clarification`, `escalate`, `attest_action`, `finish`, `message_manager`.
Manager tools (charter has reports): `delegate`, `finish_turn`, `reports_status`, `inspect_report`, `accept`, `reject`, `reply_report`.
Granted tools (per role, via Tool Proxy executors as they land): e.g. `repo_merge_request` for governed merges.

## 5. Metering — session-observed Steps

The adapter consumes `stream-json` events:

| stream-json event | Canopy record |
|---|---|
| `init` | `session_span_id` minted; `session_ref` stored on the assignment |
| assistant message (with `usage`) | **Step**: input/output tokens, duration; `kind` = coordination for manager sessions' delegate/accept turns, production otherwise; delta classified from the turn's content (tool_use → `tool-effect`/`message`/`artifact` per tool; text-only → `none` unless a stage advanced) |
| tool_use / tool_result | ToolEvent (observability); MCP-tool calls are *also* independently recorded server-side — the server-side record is authoritative |
| `result` (final, with total usage & cost) | reconciliation: any usage not yet attributed lands as a closing Step; `total_cost_usd` recorded as the SpendEvent cost basis (`provider='claude-cli'`, model from init) |

Every Step posts to `POST /dp/assignment/events` and settles in the **existing ledger** (`record` with step-id idempotency — redelivered reports never double-charge). Rollups, warn thresholds, and hard-stop state all work unchanged; the ledger cannot tell a gateway Step from a session Step, which is the point.

## 6. Budget and halt enforcement — the turn boundary

The between-Steps enforcement point (invariant 7) maps to the **turn boundary**:

- Before starting/resuming a session: `GET /dp/meter` — if exhausted, don't start; report; the engine opens the hard-stop InterventionGate.
- During a session: the adapter tracks cumulative usage live from stream events. When spend crosses the allowance (or the engine's SSE-pushed halt flag for this assignment — X1's mechanism — is set), the adapter **interrupts the CLI process at the current turn's end** (kill process group; Windows: `CREATE_NEW_PROCESS_GROUP` + `taskkill /T`, per sandbox.md). The session id survives — resume after resolution loses nothing but the interrupted turn.
- `--max-turns` bounds runaway sessions independently (the step-cap stall guard).

The residual gap — one turn can overshoot the allowance before the boundary check lands — is debt **E-D1** (§7).

## 7. Debts opened by the no-key constraint

| # | Debt | End-state | Honest seam |
|---|---|---|---|
| E-D1 | Hard-stop granularity is one session turn (a single turn can overshoot) | Per-model-call enforcement via a metering proxy (`ANTHROPIC_BASE_URL` → gateway passthrough that observes usage and can refuse dispatch) if/when subscription auth tolerates a base-URL override, or an API key arrives | Ledger semantics unchanged; only the enforcement point moves |
| E-D2 | Token/cost figures are CLI-reported, not gateway-measured | Same proxy as E-D1 makes them first-party | SpendEvent shape unchanged; `provider='claude-cli'` labels the provenance |
| E-D3 | Model routing is per-session (`--model`), not per-call; SC-1's cheap-coordination routing is coarse | Profile-per-node already gives role-level routing (lead on a cheaper model); per-call routing waits on E-D1's proxy | AgentProfile shape unchanged |
| E-D4 | Session-internal subagents (`session.subagents`) burn metered tokens but their internal structure is opaque | Fine-grained attribution via proxy; until then they are simply turns | Steps still capture all usage |

## 8. Trust statement (extends `../actuation/threat-model.md`, v1 posture)

Trusted-local, stated plainly: the CLI authenticates via an **operator-provisioned config dir** (`CLAUDE_CONFIG_DIR` pointed into the sandbox env at a copy provisioned by the actuator; revoke = log out that profile). A hostile agent process on the subprocess tier could read that OAuth material — the same class of exposure as phase-2's "v1 trusts the agent runtime code, not OS enforcement" (sandbox.md §2), now with a real credential in scope. Mitigations now: dedicated Claude profile for Canopy (blast radius = that login, revocable), generated permission denials, no general egress expectations in generated settings, full ToolEvent audit. Mitigation later: the docker provider (T2) makes the config dir a bind-mounted secret with real fs isolation — this is *the* reason to prioritize A6's docker provider after MVP. `TIER_UNSATISFIABLE` is **waived by explicit config** for MVP (`canopy.toml: execution.allow_trusted_local = true`) so the org actuates on subprocess with `execute`-class grants — loudly, once, logged at actuation.

## 9. Testing without a login (risk IM-2)

A **fake-CLI shim** (`tests/fake_claude.py`, installed as the `claude` command in test PATH) speaks the same contract: reads `-p`/`--resume`/`--mcp-config`, emits canned stream-json (init → assistant turns with usage → result), and actually calls the MCP server for scripted tool sequences. Engine + adapter + MCP integration tests run entirely on it; the `loop` runtime over the `mock` gateway provider remains the second CI path exercising the same dp endpoints. One live smoke test (marked, skipped in CI) validates against a real logged-in CLI.
