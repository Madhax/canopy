# Testing Strategy — How Canopy Stays Correct

**Status:** Living document · **Date:** 2026-07-26
**Purpose:** the testing strategy in one place. Until now it lived across four documents — `risks/implementation.md` (IM-2, IM-3, IM-5), `risks/architecture.md` (AR-1, AR-2, AR-3), `org-chart-editor.md` §5.4/§8, and `execution/mvp.md` §4–5 — and partially in the test suites themselves. This doc consolidates the pillars, inventories the estate, states the standing rules, and holds the gap plan. Those documents remain authoritative for *why* each risk matters; this one is authoritative for *what we test and when*.
**Reads with:** `.github/workflows/ci.yml` (the enforcement point), `execution/amendments-2026-07-26.md` §3.5 (the E2-era test additions).

---

## 1. The four pillars

1. **Deterministic core, zero-spend CI** (IM-2). Every meaningful behavior — loop, delegation, gates, budget-stop — must be testable with no API key and no spend. The `mock` ModelProvider is the spine; the fake-CLI shim (E3) extends it to the `cli-claude` runtime. Exactly **one** live smoke test exists (marked, skipped in CI, run manually — §6). Determinism is non-negotiable: golden assertions rot against live models, so live models never sit under golden assertions.
2. **Dual-implementation honesty** (AR-2, editor §5.4). Every contract that exists in two languages is kept honest by shared fixtures, not discipline: golden validation vectors (`testdata/validation/`) force the Python and TypeScript validators to produce identical issue lists; contract fixtures (`testdata/contracts/`) are parsed by both Pydantic and Zod suites. A field drifting on one side fails one suite loudly. Adding a rule or a field *means* adding a vector — the vector is the spec.
3. **Money-path paranoia** (IM-5, AR-3). Bugs elsewhere waste time; bugs in reserve/record/settle waste user money and the product's core claim. The money path therefore gets the strongest test forms in the repo: real-thread contention (the hard-stop must hold when 50 workers race one meter), step-id idempotency (redelivery never double-charges), warn-edge single-firing, and seeded fuzz over interleavings asserting `spent + reserved ≤ allowance` always. Anything that touches the ledger inherits this bar.
4. **Two OSes, always** (IM-3). Development happens on Windows; deployment targets are Linux; the product orchestrates processes — so "works on my machine" is architectural. The full suite runs on `ubuntu-latest` and `windows-latest` on every PR and every push to main. Process-lifecycle tests (sandbox spawn/kill/restart, and E3's interrupt-at-turn-boundary) are the core matrix content, not an afterthought.

## 2. The estate today (what exists and where)

| Layer | Tooling | Location | Notable coverage |
|---|---|---|---|
| Shared validators | golden vectors, both runners | `testdata/validation/` ← pytest + vitest | ≥2 vectors per rule code incl. nested-org `orgPath` cases |
| Cross-language contracts | shared JSON fixtures | `testdata/contracts/` ← `test_contracts.py` + `ui/src/schema/actuation.contract.test.ts` | profile, binding, secret-meta (asserts *no* field could carry plaintext), completion request/result |
| Money path | pytest, threads + seeded fuzz | `test_ledger.py` | contention (50 threads, exactly 10 of 50 reserves may win a 1000-token meter), idempotent record, warn-crossing edge, top-up reopen, invariant fuzz |
| Bus | pytest | `test_bus.py` | FIFO, visibility timeout + attempt bump, idempotency-key dedupe, coalescing (`coalescedCount`), nack → dead-letter |
| Router / topology | pytest | `test_router.py` | channel derivation, sibling-call 403 (`CHANNEL_FORBIDDEN`), operator↔any |
| Sandbox / actuator / directory | pytest | `test_sandbox.py`, `test_actuator.py`, `test_directory.py`, `test_actuation_api.py` | provision/teardown state machine, reconciler restart, heartbeat status |
| Gateway / providers | pytest | `test_gateway.py` | budget check before dispatch (402 path), step + spend attribution, mock provider |
| Work layer (E1) | pytest, real app harness | `test_engine.py`, `test_work_store.py`, `test_work_api.py` | intent → funded root assignment (D1 both directions), full happy path to closed + memory write, reject → planning with brief v2 |
| Loop runtime | pytest, in-process ASGI | `test_loop_runtime.py` | drives a real assignment end-to-end through the dp API; asserts `work_step.id == SpendEvent.step_id` (one Step, two views) |
| Editor UI | vitest + Testing Library | `ui/src` | projection both directions, store actions (re-parent, formation stamp as one undo unit), incremental-check parity vs vectors |
| Server misc | pytest | `test_persistence.py`, `test_store.py`, `test_catalog.py`, `test_seeds.py`, `test_nested.py`, `test_secretstore.py`, `test_routes.py`, `test_profiles_api.py` | atomic writes, catalog integrity (unique keys, resolvable refs), import re-iding, 409 stale write |

**CI:** `.github/workflows/ci.yml` — `server` job (ruff + pytest) and `ui` job (tsc + vitest + build), each × {ubuntu, windows}, on every PR and push to main. ~1 minute wall-clock.

## 3. Standing rules (the coverage doctrine)

Not a percentage target. The bar is structural:

1. **Every state transition has a golden vector.** The work-model §2.1 state machine (including `proposed`, both dependency thresholds, cancel cascades) ships with a vector per legal transition and per notable illegal one. The vector list is written *before* the code — it doubles as the build spec.
2. **Every invariant has at least one adversarial test** that actively tries to break it: a forbidden channel call, an ungranted artifact fetch, an over-budget dispatch, a workspace escape. Invariants that are only tested by well-behaved callers are not tested.
3. **Every closed debt keeps its regression test forever.** D1's assignment-bound-meter test, D2's status enum, … — closing a debt row (per `actuation/phase3-debts.md`) adds the test in the same PR, and it never leaves.
4. **Contract changes update fixture + both suites + doc in the same PR** (the existing repo rule, IM-6, restated as a test rule).
5. **No test requires a credential or spends money.** Anything that would is either mocked, faked (fake-CLI), or lives in the marked manual live path (§6).
6. **Both OSes or it doesn't count** — a test skipped on Windows needs a written reason in the skip marker.
7. **Flaky tests are quarantined loudly** (skip + issue + owner), never deleted and never silently retried. A flaky test in the money path blocks releases.

## 4. Gap plan (what gets added, when)

Consolidated from the pre-E2 plan review and `amendments-2026-07-26.md` §3.5. Ordered by when the work lands.

### Now (with the Phase-1 `resolveOn` schema commit)

- Golden vectors: a document with `resolveOn: "delivered"` round-trips both validators; an invalid value fails schema parse on both; catalog integrity covers formation `resolveOn` values.
- **The failing isolation test** (write it red, on purpose): any agent can currently fetch any org artifact via `GET /dp/artifacts` — org-scope is checked, grants are not. Land a test asserting an agent *cannot* fetch a ref outside its brief's granted set, `xfail` until E3's grant check turns it green. It documents a real hole and hands E3 a ready acceptance test.

### E2 (work layer)

- **State-machine vectors** per rule 1: `proposed → briefed` funds a meter atomically; `proposed → cancelled` on deny holds no meter and published nothing; verify-dep resolves at `finish` / consume-dep only at `accept` (both idempotent under redelivery); rework on unchanged brief burns the same meter; revised-brief rework transfers from the parent meter and **transfers net to zero**; operator cancel cascades (children cancelled, meters closed, no orphan gates); reassignment carries `reassigned_from` and remaining balance; WIP cap holds delivery.
- **Manager-await**: two children, staggered delivery ⇒ two wakes; items pending at a wake are reviewed in one batch; re-arm until the child set drains.
- **The demo ordering as a fixture**: submit → verify-dep resolves → QA fails → reject on the *still-open* assignment → rework → re-verify → accept; assert acceptance never precedes the green report (mvp §5's criterion, executable).
- **Notes**: created → in plan aggregate → `delivered_at` stamped exactly once → next session input contains it → the assignment never left `executing`.
- **Money invariant replay**: replay a run's SpendEvents against final meter states; `sum(SpendEvents) == sum(meter.spent)` as an end-of-run assertion in every integration test, not just the demo.
- **Meter continuity under redelivery** (pull forward from E6): kill a mock-loop agent mid-assignment, redeliver, assert spent tokens stay spent and no step double-charges — the AR-3 scenario at system level (the ledger unit already proves the primitive).

### E3 (cli runtime)

- Fake-CLI integration suite: staged fan-out approved / denied; wake with partial batch; note injection mid-session; interrupt-at-turn-boundary and `--resume` — **on both OSes** (the Windows process-group kill is the single riskiest integration in MVP-1; it does not wait for E6).
- Grant enforcement: the §"Now" isolation test turns green; hallucinated MCP tool → 403 + ToolEvent; QA session attempting `Edit` on source refused at every layer; lead attempting `Bash` likewise (the mvp §5 adversarial suite, all three nodes, both directions).
- **Fake-CLI ↔ real CLI drift check**: a marked local test diffing the pinned CLI version's `stream-json` shapes (init/turn/result, `--resume` behavior) against the shim's assumptions. Cannot run in GitHub CI (no login); it is a release-checklist item (§6).

### E4–E5 (executors + UI)

- Repo executors: worktree materialization respects branch pattern; read-only checkout is read-only; merge executor refuses without a resolved ApprovalGate; attestation links the gate.
- Operate UI component tests: plan-review card renders the proposed batch and dispatches on approve; plan outline updates on SSE events; inbox inline resolutions hit the right endpoints.

### E6 (hardening)

- Playwright e2e: the full mvp §3 scenario headless on fake-CLI + mock (a third CI job; browser setup, longer timeout).
- Control-plane restart mid-intent; deactuate/re-actuate with open work (gated assignments survive with gates intact); memory write/inspect/reset audited.

### Scheduled (not per-PR)

- **Load/soak** (AR-1): 50 mock agents × 20 steps on one host; measure SQLite write contention and delivery latency; publish "v1 comfortably runs N agents" and fail the job if N regresses. Include the SC-5 org-fairness scenario (one noisy org, one quiet org). Weekly `on: schedule`, plus manually before any demo.

### Post-MVP

- **Role-content evals** (PF-2): golden-task evals per hero role — "given this brief, does the lead produce a sane decomposition?" LLM-judged, spend-capped, nightly-at-most. This is the one genuinely new *kind* of testing Canopy will need; everything above is conventional. Design it when the first transcripts exist to grade against.

## 5. CI topology (current and planned)

| Job | Runs | Trigger | Status |
|---|---|---|---|
| `server` × {ubuntu, windows} | ruff + full pytest | every PR, push to main | live |
| `ui` × {ubuntu, windows} | tsc + vitest + build | every PR, push to main | live |
| `e2e` | Playwright demo on fake-CLI + mock | every PR (or main-only if slow) | lands E6 |
| `load` | mock-provider soak, ceiling regression | weekly schedule + manual | lands with AR-1 work |

Docs-only PRs run the full matrix by design: the golden vectors and catalog integrity tests exist precisely to catch docs and code drifting apart, and the run costs a minute. Add a `concurrency` block (cancel superseded runs) whenever push frequency makes it worth it.

## 6. The live path (what CI cannot cover)

There is no API key and CI has no logged-in CLI, so the following are **manual, local, and on the release checklist** — never GitHub checks:

1. The one marked live smoke test: a real `claude` session drives a 2-node org through delegate → work → finish → accept. Spend-capped by the org's own salaries.
2. The fake-CLI drift check against the **pinned** CLI version (§4/E3). Upgrading the pinned CLI version requires re-running it — treat a CLI upgrade like a dependency major bump.
3. The full mvp §3 demo, once per release, on the Windows dev machine — because that is the machine the first users' experience is being built on.

Everything else in this document runs green with zero external calls, which is the point: the day CI is red is the day something real broke, not the day a provider hiccupped.
