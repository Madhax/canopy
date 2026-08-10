# E8 runbook — the first self-PR

**Status:** operator script (live milestone) · **Reads with:** `mvp.md` §4 E8, `../org-roadmap.md` O2, `../formations.md` §`docs-pod`

E8 is Canopy working on Canopy, one rung early: the MVP pod re-roled as a **docs pod**
(`tech-writer` / `editor` under an `engineering-lead`), the E4 git executor pointed at a
**local clone** of the Canopy repository, and **one operator-curated documentation issue** run
through the full machinery — staged plan review, worktree edit, verify-dep review, acceptance.
It is a **live** milestone, never a CI job: CI's fixture remains `target-app`, and everything
below happens on the operator's machine with a logged-in `claude`. No new integrations exist
yet — the operator pastes the issue text in and pushes the accepted branch out by hand. What
this run proves, O2 (`canopy-docs`) then automates.

The machinery behind this runbook lands with E8: the `docs-pod` formation, the tier-1
`docs.repo.write` grant (docs are never executed downstream, so the pod actuates on the
subprocess tier **without** the trusted-local waiver), and the `[repo] source` work-target
override.

## 0. Prerequisites

- A logged-in `claude` CLI on PATH (`claude -p "hi"` answers without prompting).
- The server runnable from source (`uv sync` done) and the UI built (`pnpm build`) — the
  control plane serves `ui/dist` on :8700.
- A **dedicated clone** of the Canopy repo, separate from the checkout the server runs from
  (the recursion boundary in `../org-roadmap.md` §2 — the org must never touch the running
  instance):

  ```bash
  git clone https://github.com/Madhax/canopy.git ../canopy-work
  ```

## 1. Configure

In `canopy.toml`:

```toml
[repo]
source = "D:/workspace/canopy-work"   # the dedicated clone, absolute path

[execution]
allow_trusted_local = false   # the docs pod needs no waiver — prove it
runtime_override = ""         # let the roles' cli-claude runtime run for real
```

Restart the server after editing (config is read once at boot). With `source` set, every
org's work target is a *clone* of `canopy-work` under `data/repos/<orgId>/canopy-work` —
the source is only ever read.

## 2. Build and staff the org

1. In the editor, create an organization `canopy-docs` and drop the **Docs Pod** formation
   (suggested under the product-engineering type): lead / writer / editor, with the
   editor→writer verify edge pre-wired.
2. In org settings, bind all three nodes to an Anthropic profile (the CLI runtime meters per
   session turn; the gateway profile is still the billing identity).
3. Actuate. Expect `live · 3/3 ready` — and **no** `execution.trusted-local-waiver` entry in
   the activity feed: nothing in this pod holds a grant above tier 1.

## 3. Curate the issue

Pick one real documentation issue — small, self-contained, verifiable by reading (a stale
doc, a missing section, a quickstart gap). Copy its text. Resist scope: one issue, one run.

## 4. Run it

1. **Intent** (Execute page → the lead): paste the issue text, e.g. *"Docs issue #NN:
   ‹pasted body›. Propose a documentation change on a branch; docs only, no code."*
2. **Plan review** (X3): the lead's staged fan-out appears as unfunded drafts — write→writer
   (contract `PullRequest`), review→editor (`dependsOn` the writer, `resolveOn: delivered`).
   Approve; the batch funds and dispatches atomically. The editor is born `gated(dependency)`.
3. **The writer works**: its session takes the rw worktree (`docs.repo.write` →
   `canopy/<assignmentId>` branch in the org's clone), edits, assembles the PR artifact,
   finishes. The verify dependency resolves at *submission* — the editor wakes with the refs
   pinned.
4. **The editor reviews** read-only (`repo.read` checkout at the submitted head), delivers
   its review; the lead wakes.
5. **Acceptance**: the lead accepts both (rejection funds rework on the same meter — let it,
   if the review says no). Optionally let the lead request the **governed merge**: approve
   the gate and `main` advances *inside the org's clone only*.
6. Watch mid-flight with the living plan, drop an anchored note if steering is needed, and
   open the inspector for per-turn Steps and the meter arc.

## 5. Push by hand (the deliberate manual mile)

The accepted branch exists only in the org's work target. Publish it yourself:

```bash
cd data/repos/<orgId>/canopy-work
git push https://github.com/Madhax/canopy.git canopy/<assignmentId>
```

Open the PR on GitHub yourself, citing the issue. In the PR body, paste the receipt (below).
Merge it like any human PR — review first; the org proposed, the human ratifies.

## 6. The receipt

From the cost explorer (Execute → Costs): the intent's total cost, tokens, the
coordination/production split, and rework rounds if any. That number goes in the PR
description — *"authored by a Canopy org for $X.XX"* — the first entry in the receipts feed
(`../org-roadmap.md` §1: the ledger is the product).

## 7. Reset

Deactuate the org. To return the machine to fixture work, empty `[repo] source` and restore
`allow_trusted_local` / `runtime_override` to taste, then restart. The dedicated clone stays
for next time — O2 turns "next time" into a cadence.

## What E8 leaves seeded for O2

The GitHub grant pack (issue ingestion, remote push, PR-create as a governed action) is
exactly the plumbing this runbook does by hand in §3 and §5. When O2 lands it, the same
formation, grants, and repo source carry over unchanged.
