# Agent Envelope — Encapsulating One Agent Across Every Use Case

**Status:** Design draft · **Date:** 2026-07-06
**Upstream:** `../domain-model.md` (invariants), `sandbox.md` (isolation), `agent-runtime.md` (the v1 loop), `agent-profile.md` (the brain), `../roles.md` (the catalog this must serve).

## 1. The problem this doc solves

Two pressures collide in Canopy's central claim — *"roles are data, not code"*:

1. **Scope creep is the default failure mode of LLM agents.** A software engineer that decides to "also just quickly verify the fix end-to-end" is now doing the QA tester's job — badly, unmetered against QA's baselines, and invisibly to the manager who structured the work as two Assignments. Prompt instructions ("stay in your lane") do not fix this; an LLM's compliance with its own scope is advisory.
2. **One runtime shape cannot serve every role.** The v1 step loop (`agent-runtime.md`) is right for a manager decomposing briefs, wrong for a backend engineer who needs a real coding session against a repository, and absurd for a cold caller whose entire job is a telephony API. Roles as different as `line-cook` and `cloud-architect` cannot share one hardcoded tool table.

The resolution is the same for both: **what an agent can do is determined by what it possesses, not by what it is told.** Scope is enforced by construction — the tool surface handed to the agent, the sandbox it runs in, and the server-side checks behind every call — never by the LLM's judgment. And the thing that packages all of this per node is the **Agent Envelope**.

This keeps "roles are data" honest by drawing the line precisely:

- **Data plane (open, extensible by anyone):** roles, archetypes, formations, *tool grants referenced by key*, runtime-kind selection, salary defaults. Authoring a new role — even a whole new industry — touches no code.
- **Code plane (closed, small, platform-owned):** the set of runtime kinds (§4), the set of tool executors behind grant keys (§3), the set of sandbox providers (`sandbox.md`). Like `SandboxProvider` and `ModelProvider`, these are registries of implementations: adding one is code, *using* one is data. One executor is generic by design — the `mcp` executor (§3.6) — which is how third parties extend capability without touching the code plane.

A role can only reference capabilities the platform actually implements. That is not a weakness of the model — it is the model. The catalog is a vocabulary of guarantees; the code plane is what makes the guarantees real.

## 2. The envelope

An envelope is everything the Actuator assembles to turn one chart node into one running agent. Five parts, deliberately separable because they change for different reasons:

```
┌───────────────────────────── AGENT ENVELOPE (one per node) ─────────────────────────────┐
│                                                                                          │
│  CHARTER          who am I: identity, org position, manager/reports, compiled            │
│  (from chart)     instructions, responsibilities, deliverable contracts                  │
│                                                                                          │
│  GRANT SET        what may I touch: resolved ToolGrants (§3) — the ONLY capabilities     │
│  (from role       that exist for this agent; everything else is not "forbidden,"         │
│   + node          it is absent                                                           │
│   + assignment)                                                                          │
│                                                                                          │
│  RUNTIME KIND     how do I execute: loop | cli | actor (§4) — the implementation         │
│  (from role,      that drives the model against the grant set                            │
│   node override)                                                                         │
│                                                                                          │
│  SANDBOX TIER     where do I run: T0–T3 (§5) — derived from the riskiest grant,          │
│  (derived)        never chosen directly                                                  │
│                                                                                          │
│  PROFILE          which brain: provider/model/params (agent-profile.md, unchanged)       │
│  (binding)                                                                               │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

Every envelope, regardless of runtime kind, honors one external contract — this is the encapsulation boundary the rest of the platform sees:

1. Boots from a charter fetched with a run token; holds no secrets (invariant 10).
2. Thinks only through the Model Gateway; every model call is a metered Step (invariant 7).
3. Communicates only through the Message Router on chart-derived channels (invariant 3).
4. Ships work out only as Artifacts or Attestations via the control plane (invariant 2).
5. Exposes health (register + heartbeat) and is disposable (cattle, per `sandbox.md` §3).

The sandbox and the agent are coupled — every agent runs inside exactly one sandbox — but conceptually distinct: the **sandbox is the wall** (isolation, resources, lifecycle) and the **envelope is the contents and the contract** (what runs inside the wall and what it is permitted to reach through it). §5 makes the coupling rule explicit: grants determine the minimum wall.

## 3. Tool grants — capability as possession

### 3.1 The vocabulary

A **ToolGrant** is a catalog entry (new top-level catalog section, alongside `roles` and `organizationTypes`) describing one capability the platform can hand to an agent:

```jsonc
// catalog: toolGrants[]
{
  "key": "code.repo.write",              // stable kebab/dot key, referenced by RoleTemplates
  "title": "Repository write access",
  "riskClass": "write",                   // inert | read | write | execute | consequential
  "minSandboxTier": 2,                    // hard floor — actuation refuses below this (§5)
  "executor": "git-mediated",             // which platform-side implementation serves it (code plane)
  "credentialKind": "scm-token",          // what the control plane injects AT CALL TIME, never into the agent
  "governedActions": ["push-to-protected"],// subset requiring an ApprovalGate before execution
  "params": { "branchPattern": "canopy/*" } // grant-level defaults; narrowable per role/node, never widenable
}
```

Risk classes order the vocabulary and drive tier derivation:

| Class | Meaning | Examples |
|---|---|---|
| `inert` | pure computation over inputs already in the workspace | `workspace.rw`, `artifact.produce`, `artifact.fetch` |
| `read` | observes the world beyond the workspace | `web.read` (allowlisted), `crm.read`, `repo.read` |
| `write` | mutates platform-external state that is still reversible/reviewable | `code.repo.write` (branch-scoped), `ticket.update`, `kb.publish-draft` |
| `execute` | runs agent-authored code or drives real software | `shell.run`, `test.unit.run`, `test.e2e.run`, `browser.drive`, `python.notebook` |
| `consequential` | irreversible real-world effect on people or money | `telephony.call`, `email.send-external`, `payment.execute`, `content.publish` |

Every `consequential` grant's actions are governed by definition — ApprovalGate before, ActionAttestation after (invariant 9). `execute` grants carry the hard sandbox-tier floors, because agent-authored code must be assumed hostile to its own cage.

### 3.2 Where grants attach, and the narrowing rule

- **RoleTemplate** declares the default grant set — this makes the existing "tool grants" bullet in `domain-model.md` §RoleTemplate concrete: it is a list of grant keys + param narrowings.
- **Agent node** (user, in the editor) may *remove* grants or *narrow* params. Widening beyond the role requires explicitly changing the node's role or adding a catalog-visible extension — a loud act, rendered on the chart.
- **Assignment** may carry temporary additions only from the delegating manager's own transferable set (mirrors the artifact grant-set rule in `workspace.md` §2), and they expire with the Assignment.

The composition rule is **monotone narrowing**: `effective = (role grants ∪ assignment additions) − node removals, params = most restrictive wins`. There is no path by which an agent's effective set silently exceeds what the chart shows.

### 3.3 Enforcement — five layers, none of them a prompt

This is the direct answer to "the engineer starts doing QA's work":

1. **Surface filtering.** The tool schema compiled into every model call contains only the effective grant set. The engineer's model never *sees* a `test.e2e.run` or `browser.drive` tool. You cannot call what does not exist in your world.
2. **Server-side authorization.** Every tool invocation is executed (or brokered) by the control plane's **Tool Proxy** (§3.4), which re-checks the run token's grant set per call. A hallucinated or injected call to an ungranted tool is a 403, logged. Layer 1 is UX; layer 2 is the guarantee.
3. **Sandbox physics.** Even a jailbroken runtime cannot improvise capability: no network egress except the control plane (per tier, §5), no credentials in the environment, no peer addresses. The engineer's sandbox has no path to the staging environment QA tests against.
4. **Contract acceptance.** The Assignment's deliverable contract is role-shaped (`PullRequest`, not `TestReport`). An engineer that burns tokens self-QA-ing still can only discharge a PullRequest, and the spend shows up as an envelope overrun against *engineer* baselines — visible, attributable waste rather than silent scope drift.
5. **Topology.** Delegation follows the chart (invariant 4). The engineer cannot assign QA work to itself or anyone else; only the shared manager can, which is exactly where the domain wants that decision.

Layers 1–3 make out-of-scope action *impossible*; layers 4–5 make residual in-scope wandering *expensive and visible*. Nothing anywhere asks the LLM to restrain itself.

### 3.4 The Tool Proxy

A new control-plane component (same ABC/registry pattern as the others, `topology.md` §3): the single execution path for every grant whose executor is platform-side — third-party APIs (CRM, telephony, ticketing), mediated git, allowlisted web fetch. It is the third mediation chokepoint, symmetric with the Model Gateway (thinking) and Message Router (talking): **acting**.

Per call: resolve run token → check grant + params → open ApprovalGate if the action is governed and unapproved → inject credential from the Secret Store → execute → record a `SpendEvent`-adjacent `ToolEvent` (agent, assignment, grant key, params hash, outcome, cost where meterable) → return the result. Credentials for external tools thus follow the exact rule model keys already follow (invariant 10): referenced by grant, held by the platform, injected at call time, never resident in a sandbox.

Workspace-local grants (`workspace.rw`) and in-sandbox execution grants (`shell.run` inside a T2/T3 sandbox) don't route through the proxy — the sandbox *is* their enforcement — but they still emit ToolEvents through the runtime for observability.

### 3.5 The standard grant library — Claude Code parity

Claude Code demonstrates that a general development agent needs roughly one screenful of built-in tools: file I/O, search, shell, web, LSP, subagents, task tracking, scheduling, MCP. Canopy can provide the same working surface, but each capability is re-homed to whichever mechanism *owns* it in an organization — because Claude Code's set assumes one trusted operator supervising one session, and several of its tools are, in org terms, acts of self-granted authority. The mapping is the seed `toolGrants[]` catalog:

| Claude Code built-in | Canopy home | Why there |
|---|---|---|
| `Read`/`Write`/`Edit`/`Glob`/`Grep`/`NotebookEdit` | `workspace.rw` — baseline, inert, T1+ | private scratch is every agent's birthright (invariant 2 makes it harmless) |
| `Bash`/`PowerShell` | `shell.run` — grant, execute, minTier 2, param-scoped (command patterns) | agent-authored execution needs a hard wall, never soft isolation |
| `LSP` | `code.lsp` — grant, inert, bundled into `cli` worktree sessions | pure computation over the worktree |
| `WebFetch`/`WebSearch` | `web.read` / `web.search` — grants, read, **proxy-brokered + allowlisted** | no sandbox has general egress (§5); the proxy is where allowlists and logging live |
| `EnterWorktree` | `code.repo.*` — the git-mediated executor materializes the worktree | repo access is a credentialed capability, not a filesystem fact |
| MCP servers | the Tool Proxy mount itself (agent-side); executor extensions (platform-side, §3.6) | MCP is Canopy's *delivery* mechanism for platform-brokered grants — never a sandbox-configurable addition — and, on the platform side, the extension seam for new capabilities |
| `Agent` (subagents) | **split.** *Internal* subagents (parallel exploration inside one session) are allowed as a `cli` runtime param (`session.subagents: true`) — they never leave the sandbox and every underlying call is still gateway-metered against the same BudgetMeter. *Work-splitting* delegation is NOT a tool: it is the `delegate` primitive, manager-only, chart-topological (invariant 4) | an IC parallelizing its own thinking is fine; an IC spawning workers is an org-structure decision it doesn't own |
| `TodoWrite`/`Task*` | Plan / PlanStage — first-class domain objects | an agent's task list is *observable state the manager can read* (`domain-model.md` §Plan), not private scratch |
| `Cron*`/`ScheduleWakeup` | **not a grant, ever.** Recurring work is a Cadence, defined at the chart level | an agent must not self-schedule standing work outside any Assignment — that is the purest form of scope creep |
| `AskUserQuestion` | `message_manager` → EscalationGate | questions route up the chart, not to "the user"; only the root's manager is the user |
| `Skill` / skills | RoleTemplate-attached procedures (catalog data) | skills are prompt-shaped workflow data — they slot into "roles are data" natively, as role/responsibility attachments compiled into the charter |
| `ToolSearch` | unnecessary | grant sets are small by design; the schema *is* discovery |
| Permission rules (`allow`/`deny`/`ask`) | the grant system itself; `ask` ≈ governed actions → ApprovalGate | Canopy's `ask` is answered by the chart (manager/user gate owner), not an interactive terminal |

### 3.6 Extension via MCP — opening the executor registry

§1 draws the data/code boundary: new roles are data, new *capabilities* are code. MCP softens that boundary in the one place it should soften: the Tool Proxy grows a generic **`mcp` executor** that adapts any external MCP server into grant-servable capabilities, so extending Canopy with a new tool family (GitHub, a CRM, a telephony provider, an internal API) means *configuring* a server, not writing an executor class.

```jsonc
// control plane: registered MCP executor backend (operator-configured, org-scoped)
{
  "id": "mcpx_gh01",
  "transport": "stdio | http",             // launched/held by the control plane — NEVER inside a sandbox
  "endpoint": "…",                          // or command, for stdio
  "credentialSecretId": "sec_…",            // Secret Store, same rules as model keys (invariant 10)
  "toolAllowlist": ["create_pull_request", "get_issue", "…"]   // subset actually exposed
}

// catalog: a grant backed by it — same shape as §3.1, executor points at the adapter
{
  "key": "scm.github.pr",
  "riskClass": "write",                     // REQUIRED, human-assigned — see curation rule
  "minSandboxTier": 0,                      // proxy-brokered ⇒ no local compute implied
  "executor": "mcp:mcpx_gh01",
  "credentialKind": "via-executor",
  "governedActions": ["merge_pull_request"]
}
```

The flow is unchanged from §3.4 — run token → grant check → gate if governed → the proxy *as MCP client* invokes the external server → ToolEvent. All guarantees survive because the server hangs off the proxy, not the agent: the sandbox still reaches only the control plane, credentials still live in the Secret Store, every call is still authorized/gated/logged, and the agent cannot tell a native executor from an MCP-backed one.

**The curation rule — the deliberate friction.** MCP is self-describing about *function* (`tools/list`) but silent about *risk*: nothing in a tool's schema says whether calling it emails a customer. So registering a server does **not** auto-create grants. Every exposed tool must be wrapped in a ToolGrant by a human (or imported from a community-published grant pack) with `riskClass`, `governedActions`, and params explicitly assigned — and the actuation check `GRANT_EXECUTOR_MISSING` extends with `GRANT_UNCURATED` for MCP tools referenced without a curated wrapper. This keeps the §3.1 vocabulary a *vocabulary of guarantees*: the guarantee is exactly the curation.

Two boundaries stay firm: agents never mount external MCP servers directly (the only agent-side MCP endpoint remains the proxy — otherwise credentials, audit, and gates are bypassed in one move), and grant packs distribute like the rest of the catalog: data, versioned, community-extensible — a `telephony-twilio` pack is the same kind of artifact as a `role` entry, which is "roles are data" extended to capabilities.

Two conclusions worth stating. First, **parity is achievable with ~a dozen grant keys** (`workspace.rw`, `shell.run`, `code.lsp`, `code.repo.*`, `web.read`, `web.search`, `test.*.run`, `browser.drive`, `python.notebook`, plus the baseline primitives) — the standard library is small because Claude Code already proved the sufficient set. Second, the tools that *don't* carry over (self-scheduling, unscoped subagent spawning, asking the user directly) are precisely the ones that would let an agent act outside its Assignment — which is evidence the envelope model is cutting in the right place: what we removed from the tool table reappears, better-governed, as domain structure (Cadences, delegation, gates).

## 4. Runtime kinds — the agent implementations

Three kinds cover the catalog. Each is a data-plane implementation behind one registry (code plane, like sandbox providers); a RoleTemplate names its default kind and a node may override (e.g., trial a `loop` engineer before paying for `cli` sessions).

### 4.1 `loop` — the native step loop (exists today)

`agent-runtime.md` unchanged in spirit: charter → bounded step loop → gateway → tools → discharge. The v1 closed tool table is reinterpreted as the *baseline grant set* (`workspace.rw`, `artifact.produce/fetch`, `delegate`, `await_reports`, `message.*`, `finish`) that every envelope receives; role grants extend it. Right for **managers and coordinators** (their work *is* decompose/await/synthesize/accept — pure platform primitives) and for **document-shaped ICs** (analysts, writers, reviewers) whose work is thinking plus workspace I/O.

### 4.2 `cli` — a session-agent adapter

For roles whose real work is a long-horizon coding/creation session: wrap an existing CLI coding agent (Claude Code headless, Gemini CLI, antigravity-style) as the execution engine, while the canopy adapter around it holds the A2A server, intake/discharge, and heartbeats. This is the "preloaded configuration" pattern made platform-native — the adapter *generates* the session configuration from the envelope, per task:

```
intake (brief + fetched artifact refs materialized into workspace/brief/)
  └─ adapter writes session config derived from the ENVELOPE, not authored by hand:
       • allowed-tools whitelist  ⟵ effective grant set (e.g. Claude Code --allowedTools /
         settings.json permissions; antigravity's preloaded tool configuration)
       • MCP config: exactly one server — the canopy Tool Proxy endpoint scoped by run token
         (platform-brokered tools appear as MCP tools; nothing else is mounted)
       • model endpoint ⟵ the Model Gateway's provider-compatible proxy URL
         (e.g. ANTHROPIC_BASE_URL=<gateway>/proxy/anthropic, api key = run token) — the CLI
         thinks it's talking to the provider; the gateway resolves the real profile+key,
         meters every call as a Step, enforces the budget before dispatch
       • workspace = the sandbox workspace; repo roles get a git worktree materialized
         by the git-mediated executor (workspace.md roadmap item)
  └─ adapter drives the session headless against the brief; session transcript → structured logs
  └─ discharge: outputs staged in workspace/out/ → produce_artifact → refs → A2A completion
```

The invariants survive intact because the two chokepoints still sit under the CLI: the gateway proxy means every underlying model call is metered and budget-gated even though the loop belongs to a third-party binary, and the MCP-only tool mount means the session's capabilities are exactly the grant set. What the CLI adds is a *better loop* for code — planning, editing, self-testing within its grants — not new authority. **Requires tier ≥ 2** always (a coding session implies `execute`-class grants), which is consistent with `agent-runtime.md`'s existing rule that executable tools wait for hard sandboxes.

### 4.3 `actor` — the closed-API agent

For roles whose work is a sequence of domain API calls with judgment in between — and no general computation at all. The runtime is a thin decision loop: state in, one model call to choose the next action from the grant set, dispatch through the Tool Proxy, repeat. No filesystem beyond a scratch note, no shell, no code, no browser. The cold caller is the canonical case (§6.3): its entire tool surface is `telephony.*` + `crm.*` + attestation primitives.

`actor` is what makes low-risk roles *cheap and safe simultaneously*: because the agent possesses no compute grants, it can run at **T0** — no OS-level sandbox needed at all, since there is nothing to contain; every effect it can have already passes through the proxy's authorization, approval gates, and audit log. Hundreds of pooled actor agents (support tiers, SDR pods, pickers) are just decision loops multiplexed over the proxy.

### 4.4 Future kinds (reserved, not designed here)

- `workflow` — deterministic, LLM-free execution of a fixed procedure (an expeditor that only assembles and attests); worth having so cadence-driven rote work costs zero tokens.
- `human-proxy` — a human behind the same envelope: charter and assignments delivered to a UI/phone, deliverables and attestations entered by hand, same contract, same audit. This is how physical-world roles (`carpenter`, `nurse`) become real rather than simulated, without the org chart, router, or economics noticing any difference.

The registry pattern means these are additive: `runtime.kind` is already a string in the envelope.

## 5. Sandbox tiers — the wall matches the contents

`sandbox.md`'s provider ladder (subprocess → docker → microVM → remote) is re-expressed as **tiers**, and the envelope's tier is **derived, never chosen**: `tier = max(minSandboxTier over effective grants)`, with runtime-kind floors (`cli` ⇒ ≥2).

| Tier | Isolation | Egress | Serves | v1 provider |
|---|---|---|---|---|
| **T0** | none needed — no local compute capability exists | control plane only (gateway, router, proxy) | `actor`, `workflow`, `human-proxy` | subprocess (trivially safe: the process can only do RPC) |
| **T1** | soft (subprocess, cwd-jailed) | control plane only | `loop` with inert/read grants: managers, writers, analysts-without-compute | subprocess |
| **T2** | hard fs/net/resource (container) | control plane + proxy-brokered only; no direct internet | `cli` sessions; `loop` with `write`/bounded-`execute` grants (unit tests against the worktree) | docker (roadmap A6) |
| **T3** | kernel-level (microVM), default-deny network | control plane only; even proxy calls constrained | arbitrary/untrusted `execute`: e2e browsers, data-science notebooks, anything that runs fetched code | microvm (roadmap) |

Rules the Actuator enforces at actuation time (new readiness checks, same `ValidationIssue` shape as `agent-profile.md` §3):

- `TIER_UNSATISFIABLE` — a node's derived tier exceeds what the configured providers can supply (e.g., role grants demand T2, host only has subprocess). The org does not actuate with silently weakened walls; the operator either installs the provider or strips the grant. This check is what killed "shell in soft isolation" as a class of accidents.
- `GRANT_UNKNOWN` / `GRANT_EXECUTOR_MISSING` / `GRANT_CREDENTIAL_UNBOUND` — grant key not in catalog / executor not registered / `credentialKind` has no secret bound for this org.
- `RUNTIME_UNAVAILABLE` — role wants `cli` but no CLI adapter is installed/configured on this host.

Egress deserves emphasis because it is the sandbox behavior that changes most by tier: **no sandbox at any tier has general internet access.** T0/T1 processes can reach only the control plane by construction; T2 containers get a network namespace whose only route is the control plane (all web/API reach is proxy-brokered, allowlisted per grant); T3 is default-deny even inward. "The cold caller can only call the telephony API" is therefore not a property of the cold caller's prompt or even its runtime — it is a property of a network namespace plus a grant table, both of which the LLM cannot vote on.

## 6. Constructed use cases

Six envelopes spanning the catalog, showing how one chart yields heterogeneous agents. Notation: role keys and deliverables from `roles.md`.

### 6.1 Backend engineer — the coding session

```yaml
node: a_be01 (backend-engineer) → team: product-engineering-pod
charter:      implement features → PullRequest; unit tests → TestSuite
grants:       workspace.rw, artifact.*,                       # baseline
              code.repo.write   (branchPattern: canopy/*, git-mediated executor,
                                 governed: push-to-protected)
              test.unit.run     (execute, scoped to the worktree, minTier 2)
              docs.read         (read, allowlisted internal docs via proxy)
runtime:      cli   (Claude Code headless adapter; config generated per §4.2)
tier:         T2 (from test.unit.run / cli floor)
profile:      "Sonnet — default engineer"
NOT granted:  test.e2e.run, browser.drive, deploy.*, staging environment reach
```

The scope story end-to-end: the engineer *can* run unit tests (fast feedback belongs in the maker loop) but *cannot* run the e2e suite, drive a browser, or reach staging — those tools don't exist in its session config, the proxy would 403 them, and its container has no route to them. When its PullRequest is accepted, the sibling QA Assignment's DependencyGate opens. The engineer's "temptation" to self-verify is structurally reduced to what its worktree affords.

### 6.2 QA engineer — the mirror image

```yaml
node: a_qa01 (qa-engineer) → same pod
charter:      test plans → TestPlan; verification → TestReport; defects → BugReport
grants:       workspace.rw, artifact.*,
              repo.read          (read-only — can read the code, cannot change it)
              test.e2e.run       (execute, minTier 3 — runs the engineer's artifact)
              browser.drive      (execute, Playwright against the ephemeral env, minTier 3)
              env.ephemeral.provision (write, proxy-brokered: platform spins the env, agent never
                                       holds infra credentials)
runtime:      loop  (verification is plan → execute suites → interpret → report; the step loop
                     with execute grants suffices — no long-horizon code authoring needed)
tier:         T3 (browser + running fetched code = the riskiest workload in the pod)
NOT granted:  code.repo.write — a QA agent that "just fixes it" is structurally impossible;
              the fix is a BugReport artifact routed to the manager, who re-briefs the engineer
```

Engineer and QA are perfect complements by construction: each possesses exactly the capability the other lacks, and the only channel between them is the artifact flow their manager wired as a Dependency. This pair is the reference test for the whole design.

### 6.3 Cold caller (SDR) — the consequential actor

```yaml
node: a_sdr01..N (sales-development-rep) → sales-pod, pooled
charter:      prospect/qualify → QualifiedLead; log outreach → OutreachAttestation
grants:       artifact.*  (leads in, lead lists out),
              crm.read / crm.write        (write, proxy-brokered, org's CRM credential)
              telephony.call              (CONSEQUENTIAL: every dial to a new number is a
                                           governed action — ApprovalGate owned by the
                                           sales-director within a manager-approved call list;
                                           recording/transcript attached to the attestation)
              email.send-external         (consequential; templates narrowed at role level)
runtime:      actor (decision loop: pick next lead → call via proxy → live transcript turns
                     stream through the gateway as metered Steps → disposition → attest)
tier:         T0 — the agent has no compute grants; the sandbox is a bare process whose only
              reachable surface is the control plane
NOT granted:  workspace beyond scratch, web browsing, payment or contract tools —
              an SDR cannot "helpfully" send a proposal; that is the account-executive's grant
```

This is the envelope where the proxy earns its keep: consent-before (gate), evidence-after (attestation), credential never in the agent, full call audit — and the entire risk surface of a phone-wielding AI is reduced to one brokered grant. Pooling N of these behind a team topic (roadmap "work pools") needs no design change: identical envelopes are cattle.

### 6.4 Data analyst — bounded compute

```yaml
node: a_da01 (data-analyst) → data-insights-cell
charter:      answer data questions → AnalysisReport; dashboards → Dashboard
grants:       workspace.rw, artifact.*,
              warehouse.query    (read, proxy-brokered, read-only SQL role credential)
              python.notebook    (execute, minTier 3: runs agent-authored analysis code
                                  over fetched result sets, NO network inside)
              dashboard.publish  (write, governed at role level: publishing org-visible
                                  numbers gets a team-lead ApprovalGate)
runtime:      loop
tier:         T3 (python.notebook)
```

The interesting property: the *queries* leave the sandbox (proxy checks the credential is read-only) while the *computation* never does (the notebook microVM has no egress). Data can come in; code can run on it; nothing agent-authored can reach out.

### 6.5 Engineering lead — the manager needs almost nothing

```yaml
node: a_el01 (engineering-lead) → pod manager
charter:      TechPlan; ReviewDecision; standards → EngineeringGuideline
grants:       baseline only (workspace.rw, artifact.*, delegate, await_reports, message.*)
              + repo.read (to review diffs as artifacts/refs, not to touch the repo)
runtime:      loop
tier:         T1
```

Deliberately austere, and worth stating as a principle: **authority in Canopy is topological, not capability-based.** The most powerful node in the pod holds the fewest grants; its power is the `delegate` primitive plus acceptance. A compromised manager can mis-assign work — which the chart, budgets, and gates all surface — but it cannot push code, call customers, or touch production, because it never possessed the means. This inverts the usual privilege-escalation gradient and is the quiet payoff of separating capability from rank.

### 6.6 Line cook — the envelope at the physical edge

```yaml
node: a_lc01 (line-cook, grill) → franchise-shift
charter:      station items → StationAttestation; equipment faults → FaultReport
grants:       artifact.* (OrderTicket refs in), station.display (write: the kitchen screen),
              attest.* — and, per deployment, either device-level grants (IoT fryer/grill
              telemetry via proxy) or nothing but the display
runtime:      actor today (sequencing/timing decisions over tickets at tempo);
              human-proxy when the "agent" is actually a person holding a tablet
tier:         T0
```

Included to show the envelope's floor: a role can be *almost all charter and almost no capability* and still be a first-class node — metered, attesting, gate-raising (`FaultReport` → InterventionGate to the `store-manager`). The same chart position swaps between an AI actor and a human proxy without any other node knowing.

### 6.7 The chart view

One `product-engineering` org, actuated:

```
                    a_tpm (program-manager)          loop · T1
                       │
            a_el01 (engineering-lead)                loop · T1
             │              │              │
   a_be01 (backend)   a_fe01 (frontend)  a_qa01 (qa)
   cli · T2           cli · T2           loop · T3
```

Five nodes, three runtime kinds, three tiers, one contract. The editor renders kind and tier as node badges next to the existing salary/status pills; the actuation readiness panel explains any red badge (`TIER_UNSATISFIABLE` etc.). To the router, ledger, and artifact store, all five are indistinguishable.

## 7. Changes to existing abstractions

The design lands as extensions, not rewrites. In dependency order:

| Abstraction (doc) | Change |
|---|---|
| **Catalog schema** (`catalog/README.md`, `catalog.json`) | New top-level `toolGrants[]` section (§3.1 shape). `roles[]` gains `toolGrants: [{key, params?}]` and `defaultRuntime: "loop" \| "cli" \| "actor"`. New integrity tests: every role grant key resolves; role/param narrowings are subsets of grant params; `defaultRuntime` is a known kind. |
| **RoleTemplate** (`../domain-model.md` §Catalog) | The existing "tool grants — the default toolset…" bullet becomes a reference to the ToolGrant vocabulary; add the narrowing rule (§3.2). One-line addition; the concept was already reserved. Suggested invariant 12: *"Capability is possession. An agent's action surface is its effective grant set, enforced by the platform; scope is never delegated to model judgment."* |
| **Compiled charter** (`agent-runtime.md` §1) | Adds `runtimeKind`, `toolGrants[]` (resolved, effective, with params), and nothing else — the agent still learns no provider/model/keys. |
| **SandboxSpec** (`sandbox.md` §1) | Adds `tier: int` and `egress_policy` (derived, informational for the provider); `runtime` string already reserved for image refs covers per-kind images. Providers declare `max_tier` they can satisfy; the Actuator matches. |
| **Actuation readiness** (`agent-profile.md` §3) | Four new checks: `GRANT_UNKNOWN`, `GRANT_EXECUTOR_MISSING` / `GRANT_CREDENTIAL_UNBOUND`, `TIER_UNSATISFIABLE`, `RUNTIME_UNAVAILABLE` (§5). |
| **Control plane** (`control-plane.md`, `topology.md` §2) | New component: **Tool Proxy** (§3.4) — own ABC, own tables (`tool_events`, grant bindings), registry of executors. Secret Store generalizes from "provider API keys" to credential kinds bound to grants (same encryption, same write-only API). |
| **Agent Directory** | Registration/heartbeat carry `runtimeKind` + `tier` for the UI badges. |
| **Agent runtime** (`agent-runtime.md`) | The v1 package becomes the `loop` kind — first entry in a runtime-kind registry; its §3 closed tool table is re-labeled the baseline grant set. The roadmap's "pluggable execution backends" row is superseded by §4 of this doc (CLI adapters are now a designed kind, not a future note). |
| **Agent Profile** (`agent-profile.md`) | **Unchanged.** The brain stays orthogonal to the envelope — the same profile can drive a `loop` manager and a `cli` engineer. |
| **Editor** (`../org-chart-editor.md`) | Node inspector shows effective grants (with role-default vs node-narrowed provenance), runtime kind override, derived tier. Chart export includes grants/runtime (they are structure, not deployment); profiles remain excluded. |

## 8. Sequencing

Fits the existing roadmap without renumbering: **A4** ships grants as data (charter carries the effective set; surface filtering in the loop runtime; baseline + `repo.read`-style read grants via a minimal proxy). **A6**'s docker provider unlocks T2 and with it the first `cli` adapter (Claude Code headless behind the gateway proxy — also the first real test that third-party loops stay metered). The `actor` kind and consequential grants ride the phase-3 gate machinery, since governed actions without ApprovalGates would be theater. T3/microVM lands per the existing roadmap row it already owns.

## 9. Open questions

- **Gateway provider-proxy fidelity** — the `cli` kind assumes CLIs tolerate a base-URL override and opaque key (true for Claude Code via `ANTHROPIC_BASE_URL`; verify per adapter, including streaming and prompt caching passthrough).
- **Grant params vocabulary** — per-executor param schemas (branch patterns, allowlists, call lists) need the same closed-schema discipline as the step-delta taxonomy; resist stringly-typed params.
- **Session-agent Steps** — a CLI session makes many model calls per "step"; decide whether a Step = one underlying model call (preferred: keeps metering honest) with a `sessionSpanId` grouping them for the drill-down UI.
- **Cross-runtime memory** — durable memory (phase 3) must be readable by any runtime kind an agent might be switched to; that argues for platform-held structured memory, not runtime-native scratch files.
- **Human-proxy attestation trust** — when the envelope wraps a person, attestations are claims by that person; whether they need second-party countersignature is a domain question, not an actuation one.
