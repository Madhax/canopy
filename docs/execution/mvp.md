# MVP-1 — The Software Team

**Status:** Implementation-ready plan · **Date:** 2026-07-06
**Upstream:** every doc in this suite; `../roles.md` / `../teams.md` (the pod comes from the catalog, not bespoke); `../use-cases.md` #1/#3/#29 (what this MVP proves).
**The ask, verbatim:** a simple software team that can build and test a piece of code; distinct roles with isolated, non-overlapping responsibilities; using the framework's tooling — including salary; full introspection of any agent; the operator aware of costs, state, and anything an owner should be alerted to; agents backed by wrapped Claude CLI sessions (no API key).

---

## 1. The organization

`product-engineering` archetype, seeded from the catalog's `product-engineering-pod` formation, trimmed to three nodes (SC-1: ship the shallowest org that satisfies the use case):

```
            a_lead  (engineering-lead)          cli-claude · manager
             │                    │
   a_be  (backend-engineer)   a_qa  (qa-engineer)     cli-claude · ICs
             ◀────── dependency: a_qa depends on a_be ──────
```

| Node | Salary (per-assignment allowance) | Deliverable contracts | Effective grants (envelope terms) | Generated session permissions |
|---|---|---|---|---|
| `a_lead` | 60k tokens · warn 80% · hard-stop | TaskBreakdown (implicit via delegation), ReviewDecision (via accept/reject) | baseline + `repo.read` | MCP canopy tools only; **no** Bash/Edit/Write; read-only checkout for reviewing diffs |
| `a_be` | 200k tokens · warn 80% · hard-stop | `PullRequest` (branch + diff artifact), `TestSuite` | baseline + `code.repo.write` (branch pattern `canopy/*`) + `test.unit.run` | Edit/Write/Glob/Grep in its worktree; `Bash(git *)`, `Bash(<test-cmd> *)` scoped to the worktree; no e2e, no web |
| `a_qa` | 120k tokens · warn 80% · hard-stop | `TestPlan`, `TestReport`, `BugReport` | baseline + `repo.read` + `test.run` (full suite) | read-only checkout; `Bash(<test-cmd> *)`; **no Edit/Write on source** — "a QA agent that just fixes it" is unrepresentable |

Non-overlap is enforced the envelope way, all five layers: the tools don't exist in each other's sessions (surface), the MCP server 403s ungranted calls (authorization), separate workspaces/worktrees with no channel between the ICs (physics + topology), and contracts of different types (an engineer burning tokens on self-QA can still only discharge a `PullRequest`, visibly over-budget against engineer expectations). Salary is not decorative: every assignment's meter is funded from these numbers, the demo script exhausts one on purpose, and the cost explorer's by-node view renders utilization against them.

## 2. The work target — a real repository

A sample project ships in-repo at `examples/target-app/`: a small TypeScript (or Python — implementer's choice, one language) service with an existing test suite, a `README`, and two or three plausible feature seams (e.g. a CSV-export endpoint — use-case #1's literal example). At actuation the repo is initialized as a **git repository under platform control** (`data/repos/<orgId>/target-app`, `main` protected by convention):

- The **engineer's** intake materializes a worktree on a fresh `canopy/<assignmentId>` branch (the `code.repo.write` executor in its v1, git-mediated form: local worktree + branch, no remotes). Its `PullRequest` artifact = `{branch, baseSha, diff, testOutput}` produced by the adapter from the worktree state at `finish`.
- The **QA** intake materializes a read-only checkout at the PR's head and runs the suite; its `TestReport` artifact = structured pass/fail + log excerpts + verdict.
- **Merge is a governed action**: on accepting both deliverables the lead's `repo_merge_request` MCP tool opens an **ApprovalGate owned by the operator** — consent before the consequential act, the demo's clearest domain moment. Approval → platform executes the merge (fast-forward or merge commit) and records the ActionAttestation.

## 3. The demo scenario (doubles as the e2e acceptance script)

1. **Build** (exists): create the org from the formation, set the salaries above, bind a `claude-cli` profile to all nodes.
2. **Actuate** (exists + E3): three sandboxes boot adapters; chart shows three `idle` nodes. Readiness includes the CLI probe and the `allow_trusted_local` acknowledgment.
3. **Intent**: *"Add CSV export to the report endpoints of target-app; all tests must pass."*
4. **Plan review** (X3/U-3): the lead's decomposition appears — implement→`a_be` (contract `PullRequest`), verify→`a_qa` (contract `TestReport`, `dependsOn` the engineer's assignment). Operator approves. QA's assignment is born `gated(dependency)` — a padlock on the chart, burning nothing.
5. **Implementation**: the engineer's session plans (visible stages), edits its worktree, runs unit tests, produces the PR artifact. Operator opens the **inspector** mid-flight and sees the live plan cursor, per-turn Steps with token counts, and the meter arc filling.
6. **Budget theater, on purpose**: the engineer's allowance is set low enough that the first implementation attempt crosses **warn** (amber glow, notification) and may **hard-stop**; the operator resolves the InterventionGate from the inbox with a top-up; the session resumes from where it stopped.
7. **Dependency resolution**: lead accepts the PR → QA's gate auto-resolves, refs injected; QA runs the suite.
8. **The rework loop** (the formation's whole point): the seeded feature seam is designed so a naive implementation fails one edge-case test. QA's `TestReport` says fail → lead **rejects** the engineer's deliverable with the report cited, brief unchanged → rework burns the engineer's meter (visible), engineer fixes, QA re-verifies green.
9. **Governed merge**: lead accepts both, requests merge → ApprovalGate → operator approves → merge + attestation.
10. **Completion**: intent closes; deliverable card (branch, diff, test report, cost split coordination/production); digest entry waits in the inbox.
11. **Introspection audit** (the checklist for requirement "introspect any agent"): for each node, the inspector shows charter, envelope, status, assignment + brief versions, plan + steps + deltas, meter + spend history, gates, queue, memory (now containing one entry each), session log, workspace listing.

## 4. Build milestones (for Claude Code)

Each ends green (`pnpm test` = pytest + vitest + fake-CLI integration) and independently demoable. E1–E2 run on `loop`+`mock` (no CLI needed); E3 onward add the fake-CLI path; the live demo needs a logged-in `claude`.

| # | Milestone | Delivers | Demo |
|---|---|---|---|
| **E1** | Artifact store + work substrate | Artifact Store exactly per `workspace.md`/`control-plane.md` §7 (A4 scope). Engine tables (`work-model.md`), intent→root-assignment intake, assignment-bound meters (D1), brief versioning, status enum incl. `gated` (D2). Dp endpoints: `assignment/current`, `assignment/events`, `finish`, `artifacts`. `loop` runtime upgraded to drive one assignment end-to-end on `mock`. | intent → root assignment → mock-loop produces an artifact → deliverable row, spend attributed per step |
| **E2** | Delegation, gates, acceptance | `delegate` + `dependsOn` (dependency gates, auto-resolve on acceptance), clarification + escalation + approval gates, accept/reject with rework-funding rule, X1 operator intervene, R2 reassign, R3 priority, plan store + X3 root plan-review checkpoint, trigger sweep (warn/hard-stop/stall), notifications table. Golden state-machine tests (every transition in `work-model.md` §2.1 has a vector). | scripted mock org: 3-node fan-out with dependency, a rejection funding rework on the right meter, a hard-stop resolved by top-up — all via API |
| **E3** | The `cli-claude` runtime | Runtime-kind registry in `canopy-agent`; the adapter (`cli-runtime.md` §1–3): session config generation from the envelope, stream-json parsing → Steps/ToolEvents, per-turn meter checks, interrupt-at-boundary, `--resume` on gate resolution. **Minimal `toolGrants[]` catalog section** (envelope §3.1 shape, just the keys §1's table needs: `workspace.rw`, `repo.read`, `code.repo.write`, `test.unit.run`, `test.run`, `repo.merge`) + `toolGrants`/`defaultRuntime` on the three roles, with catalog integrity tests. Canopy MCP server on the control plane with grant filtering. Fake-CLI shim + its test suite. Actuation readiness: CLI probe, `GRANT_UNKNOWN`, `allow_trusted_local` gate. | a 2-node org on fake-CLI runs delegate→work→finish→accept; the same org with real `claude` (manual smoke) does it for real |
| **E4** | The repo executors | Git-mediated worktree materialization (engineer), read-only checkout (QA), PR-artifact assembly at finish, `repo_merge_request` governed action + merge executor + attestation. `examples/target-app` with the seeded failing-edge-case seam. | engineer branch → PR artifact → QA runs suite → red then green across a rework round → governed merge |
| **E5** | Operate UI | Mission control overlay + org pulse, agent inspector (all eight tabs), intent console with plan review and tree, inbox (needs-you + digest, inline resolutions), cost explorer (by-intent/by-node), SSE channel. | the full §3 scenario driven from the UI, no curl |
| **E6** | MVP hardening | Crash/redelivery tests (adapter dies mid-turn; control plane restarts mid-intent), deactuate/re-actuate with open work, memory write/inspect/reset, Windows path/process-group audit, the §3 scenario as a Playwright + fake-CLI e2e, README quickstart ("clone → pnpm dev → run the software team"). | CI runs the whole demo headless; the debt ledger rows D1–D6/D9 marked closed in the same PR(s) |
| **E7** | *Stretch:* cadence | Scheduler + cadence CRUD/UI; a "daily standup" cadence on the lead (`reports_status` → StatusReport artifact). | use-case #30 live: the digest contains this morning's standup |

## 5. Acceptance criteria (MVP-1 done)

- The §3 scenario runs end-to-end from the UI on a clean machine with only `pnpm install`, `uv sync`, and a logged-in `claude`.
- Role isolation holds under test: an engineer session instructed (via test fixture) to run the e2e suite or edit outside its worktree is refused at every layer we control (permissions, MCP 403, absent tools), and the attempt is visible in ToolEvents.
- Every token spent anywhere is attributable: `sum(SpendEvents) == sum(meter.spent)` across the run, and the intent's cost splits cleanly into coordination vs production.
- Kill any agent process mid-assignment → reconciler restarts it → the assignment resumes (session resume or clean restart) → the intent still completes; no double-charged steps.
- The introspection audit (§3.11) passes for all three nodes; memory survives deactuate → re-actuate; memory reset works and is audited.
- All of it runs in CI on fake-CLI + mock with zero external calls; the live path is one marked smoke test.

## 6. What MVP-1 explicitly does not include

Frontend-engineer node (the pod formation's fourth slot — add later by editing the chart, which is the product working as intended); envelope-overrun and scope-divergence triggers (X2); standing directives (X4); manager-agent-initiated interventions; milestones; work pools; docker tier (tracked as the first post-MVP hardening item, per `cli-runtime.md` §8); any second archetype. The catalog's other 25 archetypes remain expressible on this engine per `README.md` §"Use-case coverage" — MVP-1 proves the machinery on the one that exercises the most of it (dependencies, rework economics, governed actions, and verification-as-structure in a single formation).
