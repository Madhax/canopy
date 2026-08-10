# Target App — The Work Object for MVP-1 (`examples/target-app`)

**Status:** Implementation-ready draft · **Date:** 2026-07-26
**Upstream:** `mvp.md` §2 (summarizes this doc; §3's demo runs against it), `../use-cases.md` #1 (the CSV-export recipe, verbatim), `amendments-2026-07-26.md` D-1 (the verify-dependency this app's suite split exists to exercise), `../testing.md` (the suite rules this app inherits).
**What this doc is:** the full design of the sample application the MVP-1 software team operates on — the app, the split test suite, the seeded acceptance contract, the grant-to-command mapping, the extra feature seams, the salary-calibration procedure, and the PF-1 benchmark twin. Built in **E4**.

---

## 1. What this app is for

`target-app` is a fixture: a deliberately small, deliberately boring product that ships inside the Canopy repo so the demo org has real software to work on — the driving school's car. It is load-bearing for four different things, and every design choice below traces to one of them:

1. **The rework beat.** The demo's centerpiece (mvp §3.8) needs a first implementation attempt that fails QA *structurally* — so the app ships a split suite whose acceptance half the engineer cannot execute.
2. **The isolation story made physical.** Engineer/QA non-overlap is enforced by grants mapped to concrete paths and commands in *this* repo layout (§5).
3. **Rerun and cadence seams.** One feature is not a product demo; the app carries two more small, verifiable seams (§7) for reruns, E7's cadence, and variety.
4. **The PF-1 benchmark target.** The same intent runs through a bare headless session on the same repo (§10) — the economics experiment the risk register ranks first.

## 2. Design decisions

- **Language: Python 3.11 + FastAPI + pytest**, uv-managed. Rationale: it reuses the exact toolchain CI already proves on both OSes (uv, pytest, Windows-safe), the engineer's grant compiles to a single scoped command, and worktrees stay light (no `node_modules` materialized per assignment). The counterargument — a TypeScript app would prove the framework isn't Python-shaped — is real and deliberately banked for MVP-2; the demo should not pay for that proof.
- **Domain: expense reports.** Universally legible, naturally tabular (CSV export is a *plausible* ask, not a contrived one), and rich in edge-case-bearing text fields.
- **Size cap: ~300 lines of app code.** A session must grok the whole app in one read; the demo's tokens should go to the feature, not to archaeology.
- **The CSV seam is open but pinned.** The shipped app supports `GET /reports?format=json` via an explicit `format` query parameter and rejects unknown formats. The convention is documented in the README, so "add CSV export" has exactly one discoverable surface: `?format=csv`. The acceptance suite may fairly pin it.

## 3. The application

**Data model** — `Report`: `id` (string), `date` (ISO `YYYY-MM-DD`), `department` (string), `submitter` (string), `amount` (decimal, two places), `currency` (ISO code), `status` (`submitted | approved | reimbursed`), `notes` (optional free text).

**Endpoints:**

| Route | Behavior |
|---|---|
| `GET /health` | liveness |
| `GET /reports` | list; filters `from`, `to` (date range), `department`; `format` param (`json` today; unknown values → `400 unsupported format`) |
| `GET /reports/{id}` | single report; 404 unknown |

**Seed data** (`app/data.py`, committed, deterministic): ~30 reports across three departments (`Engineering`, `Field Ops`, `R&D`), spanning three months. The adversarial rows are *in the visible dataset*, not hidden: notes containing commas (`"lunch, client on-site"`), double quotes (`saw the "good" vendor`), embedded newlines, and non-ASCII (`naïve`, `café`); amounts including `0.00` and four-digit values; one department name that itself needs no quoting so column-boundary bugs surface elsewhere.

**README** documents: how to run (`uv run uvicorn app.main:app`), how to test (`uv run pytest tests/unit`), the data model table, and the API conventions *including the `format` parameter*. It deliberately does **not** specify a CSV contract — defining and meeting that contract is the work, and verifying it is QA's job (§6 fairness note).

## 4. Repo layout

```
examples/target-app/
├── README.md
├── pyproject.toml            # app deps + pytest, uv-managed, standalone
├── app/
│   ├── main.py               # FastAPI app + endpoints
│   ├── models.py             # Report model
│   └── data.py               # seed dataset
└── tests/
    ├── unit/                 # engineer-runnable (grant-scoped to this path)
    │   ├── test_reports_json.py    # list/detail/404, format=json, unknown format → 400 (probes with format=xml — NOT csv, so the seam stays open)
    │   └── test_filters.py         # date-range + department filters
    └── acceptance/           # QA-only — the engineer's session cannot execute this directory
        └── test_csv_export.py      # §6, written in E4, red against the shipped app by definition
```

At actuation the tree is copied to `data/repos/<orgId>/target-app` and `git init`-ed with one initial commit on `main` (protected by convention). The engineer's intake materializes a worktree on `canopy/<assignmentId>`; QA's intake materializes a read-only checkout at the PR's head (mvp §2, unchanged).

## 5. Grant → command mapping (the isolation, concretely)

| Node | Test capability | Compiled session permission |
|---|---|---|
| `a_be` (engineer) | unit suite only | `Bash(uv run pytest tests/unit*)` — scoped to its worktree; `tests/acceptance` is outside the permitted command pattern, the MCP server 403s any granted-tool detour, and no other execution path exists in its session |
| `a_qa` | full suite | `Bash(uv run pytest tests*)` on the read-only checkout; no `Edit`/`Write` on source |
| `a_lead` | none | MCP canopy tools only; reviews diffs as artifacts |

This table is the mvp §1 grant column made path-concrete. The structural claim the demo makes — *first-attempt failure is structural* — rests on the engineer's inability to run `tests/acceptance`, which rests on these three rows. The adversarial tests in `testing.md` §4 (engineer attempts the acceptance suite; QA attempts `Edit`) assert each row from the hostile side.

## 6. The seeded acceptance suite (the contract, verbatim)

`tests/acceptance/test_csv_export.py` pins the CSV contract:

1. **Surface:** `GET /reports?format=csv` → `200`, `Content-Type: text/csv; charset=utf-8`.
2. **Header row, exact:** `id,date,department,submitter,amount,currency,status,notes` — the model's field order.
3. **RFC 4180 quoting:** fields containing commas, double quotes, or newlines are double-quoted; embedded quotes doubled. Asserted against the specific seed rows (exact expected byte strings for the three adversarial notes).
4. **Empty result is not an empty body:** a filter matching nothing → `200` with the header row only (never `204`, never zero bytes).
5. **Formats:** `amount` with exactly two decimals; `date` as ISO `YYYY-MM-DD`; UTF-8, no BOM.
6. **Round-trip:** parsing the body with Python's `csv.reader` yields exactly the rows the JSON endpoint returns for the same filter — the two representations never disagree.
7. **Regression:** QA runs the *full* suite, so every shipped unit test must still pass alongside the new contract.

**Fairness note (design stance, stated once):** the intent's own words — *"all tests must pass"* — make this suite the deliverable contract, so rejecting a first attempt that misses it is a quality failure under the rework-funding rule, not a rigged trap. The assertions pin choices a reasonable first implementation must guess (empty-set behavior, exact quoting, two-decimal rendering); with the suite unrunnable from the engineer's seat, a full first-try sweep is unlikely — but not impossible. **The scripted fake-CLI demo guarantees the rework beat in CI; a live run where the engineer nails it first try simply skips to the governed merge, which is still a good demo.** Honest theater or no theater.

## 7. The other seams (reruns, cadence, variety)

| Seam | Intent it absorbs | Why it's here |
|---|---|---|
| Department filter on the export | "CSV export should respect the department filter" | the natural *second* intent: small, touches the fresh code, exercises rerun + a second rework opportunity |
| `GET /reports/summary` (totals by department and month) | "Add a summary endpoint; finance wants monthly totals" | a from-scratch endpoint for benchmark variety; verifiable arithmetic |
| Weekly summary cadence | E7: "every Monday, last week's expense summary as a report artifact" | the retention-mechanism demo (use-case #30's shape) against real data |

## 8. Artifact shapes (produced by the E4 executors)

- **`PullRequest`** — `{branch, baseSha, headSha, diff, testOutput}` where `testOutput` is the engineer's *unit* run (the only one it can produce).
- **`TestReport`** — `{verdict: pass|fail, prRef, suites: {unit, acceptance}, failures: [{test, message, excerpt}], logExcerpt}` — structured enough that the lead's rejection can cite specific failures into the rework brief, and the deliverable card can render red/green per suite.

## 9. Salary calibration (making budget theater honest)

The mvp §1 allowances (60k / 200k / 120k) are placeholders until real sessions run. Procedure, after E4 lands:

1. Run the live smoke on the hero intent three times; record the engineer's median tokens-to-first-submission, **M**.
2. Set the engineer's allowance ≈ **1.2 × M**: warn (80% = 0.96 M) fires near the end of attempt one — the amber glow lands mid-implementation, unforced — and the rework round then walks into the hard-stop naturally, which is exactly where the demo wants its InterventionGate + top-up beat.
3. Scale the lead/QA allowances from their observed medians with ~1.5× headroom (their beats don't include budget theater).
4. Write the observed medians into the catalog roles' `effortEnvelope` placeholders — the first honest numbers the calibration story will later refine.

## 10. The benchmark twin (PF-1's experiment, on this repo)

Same repo snapshot, same intent, two runs:

- **Org run:** the MVP-1 demo as scripted — full ledger, coordination/production split.
- **Baseline run:** one bare headless `claude` session in a clone, with *full* test access (unit + acceptance — the baseline gets to self-verify; handicapping it would cook the result) and the same "all tests must pass" instruction. Record tokens-to-all-green from the CLI's reported usage, wall clock, and any human interventions.

Compare: total tokens, tokens-to-green, wall clock, intervention count — plus the column the baseline cannot fill at any price: provenance, per-step attribution, budget enforcement, consented merge, and an audit trail. Publish both numbers whichever way they fall (register move #1). If the org loses on raw cost — likely at this task size — the honest headline is the governance column, and the follow-up experiment is a task shaped for structure's win conditions (parallel, verification-heavy, longer-horizon).

> **Generalized (2026-08-09).** This one-shot experiment is now standing machinery: the experiments series (`design/experiments/`) makes the bare-session baseline a first-class, default-on **solo baseline variant** in every experiment, scored per trial and published continuously on the leaderboard — including the per-tag slices ("solo wins `trivial`, loses `gnarly`") this section's follow-up experiment gestures at. This benchmark twin is Experiment #1; run it once by hand as written here, then let the lab keep the answer current.

## 11. E4 build checklist (this doc's acceptance)

- App boots and both suites run green standalone (`uv run pytest tests`) on ubuntu + windows — added to CI as a third step of the server job so the fixture can't rot.
- The shipped app has **no CSV code**: `format=csv` → `400` like any unknown format (and no unit test pins `csv` specifically — the seam stays open without a trap).
- `tests/acceptance/test_csv_export.py` is red against the shipped app by definition and is **excluded** from the fixture's own CI run (it asserts the *finished* feature; it exists for QA's runtime use), marked accordingly.
- Seed data contains the §3 adversarial rows byte-for-byte as the acceptance assertions expect.
- README documents run/test/API conventions including `format`, and nothing about a CSV contract.
- The §5 permission table compiles from the three roles' grants (E3 machinery) with the paths above, and the `testing.md` §4 adversarial cases pass (engineer refused on `tests/acceptance`, QA refused on `Edit`).
