# 02 — Scoping and Grants: Org, Role, Node

**Series:** [Connector Governance](README.md) · **Prev:** [01-connector-model.md](01-connector-model.md) · **Next:** [03-security.md](03-security.md)

## 1. The baseline this extends

Today grants attach at role → node → assignment with **monotone narrowing** (`agent-envelope.md` §3.2): `effective = (role grants ∪ assignment additions) − node removals; params = most restrictive wins`. The effective set is stamped into the envelope's GRANT SET, which becomes the compiled charter and the CLI session's permission surface (`cli-runtime.md` §2). The connector model adds one level *above* role — the organization — and leaves §3.2 untouched below it.

## 2. Level 1 — organization: enablement is instantiation

An org may use a connector only if the operator has created a **ConnectorInstance** for it. This is envelope §3.6's registered backend (`mcpx_gh01`, already "operator-configured, org-scoped") promoted to a named domain object — control-plane data behind the operator API, **not** catalog data:

```jsonc
// control plane, per actuated org — the worked example's instance
{
  "id": "ci_gh_canopy",
  "orgId": "org_canopydocs",
  "packKey": "github", "packVersion": 1,
  "config": { "owner": "Madhax", "repo": "canopy", "targetBranch": "main" },
  "secretBindings": { "scm-token": "sec_7f2…" },   // Secret Store refs — plaintext never
                                                   //   leaves the control plane (03 §2)
  "enabledGrants": [                               // org-level mask: the subset of pack grants
    "connector.github.repo.read",                  //   this org may use at all
    "connector.github.pr.create"
    // connector.github.repo.merge NOT enabled — merges stay human
    //   (org-roadmap.md §2 rule 1, the recursion boundary)
  ],
  "servesFamilies": ["repo"],                      // this instance serves repo.* abstract keys
                                                   //   (01 §4 `provides`) for this org
  "paramOverrides": { "branchPattern": "canopy/*" },  // org-level narrowing of pack defaults
  "extraGovernedActions": []                       // an org may ADD governance, never remove it
}
```

Properties: an org can hold **multiple instances of one pack** (two repos → two instances). Each abstract family (`repo.*`) has exactly one *default* instance per org; nodes select among enabled instances by pinning (§3). No instance ⇒ every connector-backed grant in the org fails readiness (§5) — enablement is a hard mask, not advice.

## 3. Levels 2 and 3 — role and node: unchanged, plus pinning

**Role.** `roles[].toolGrants` keeps its exact current shape — flat keys, optional `{key, params}` narrowings (envelope §3.2). A role references abstract keys (`repo.read`) or namespaced pack keys (`connector.github.pr.create`). Nothing about a role says *which* GitHub — that is the org's binding. Existing catalog roles work against connector-served capability without edits: `tech-writer`'s `repo.read` resolves to whatever instance serves `repo` in the actuated org.

**Node.** Envelope §3.2 verbatim — a node may **remove** grants or **narrow** params; widening requires changing the role or a chart-visible extension — plus one addition: a node may **pin** a connector-backed grant to a specific enabled instance (`instanceRef: "ci_gh_canopy2"`). Pinning selects among what the org already enabled, so it is selection, not widening. Assignment-level temporary additions (from the delegating manager's transferable set, expiring with the assignment) carry over unchanged.

## 4. Precedence and narrowing rules (normative)

Evaluation order, outermost first — each level can only shrink what the previous level produced:

1. **Pack** defines the universe: grants, tools, risk classes, param defaults, governed actions.
2. **Org instance** masks grants (`enabledGrants` subset), narrows params (`paramOverrides`), may add governed actions.
3. **Role** selects from surviving keys; may narrow params further.
4. **Node** removes / narrows / pins; **assignment** may add only manager-transferable keys, temporarily.
5. **Params:** most-restrictive-wins along schema-`narrowable` axes only. A non-narrowable field (`owner`, `repo`) is instance-fixed; no lower level can touch it. Pattern-valued params (branch/path globs) must be textual subsets — verifying glob-subset relations is real work, restated as a blocking open question in [05-adoption.md](05-adoption.md) §4 (it is envelope §9's "grant params vocabulary" question, now load-bearing).
6. **Governance is monotone the other way:** any level may add `governedActions`; none may remove one. A child scope can make an action *more* gated, never less.
7. **Risk class and tier are pack-fixed:** `riskClass` / `minSandboxTier` are set at curation and untouchable downstream; tier derivation stays `tier = max(minSandboxTier over effective grants)` (envelope §5).

The invariant the whole series rests on: **no path exists by which an agent's effective connector surface exceeds what the chart and the org's instance list show** — envelope §3.2's "no silent widening," extended one level up.

## 5. Actuation-time resolution: bindings in the envelope

Today the Actuator resolves each node's effective grant set into the envelope, and readiness checks (`GRANT_UNKNOWN`, `GRANT_EXECUTOR_MISSING`, `GRANT_CREDENTIAL_UNBOUND`, `TIER_UNSATISFIABLE` — envelope §5) gate actuation. But the *target* of the repo grants is the global boot-time `[repo] source` in `canopy.toml` — one repo for every org. The connector model closes that gap: at actuation, after computing the effective set per §4, the Actuator resolves every connector-backed grant to a **GrantBinding**:

```
grant key  →  instance (node pin → org family default → error)
           →  effective params (pack ⊓ instance ⊓ role ⊓ node)
           →  credential PRESENCE check (secretBindings covers credentialKind — presence, never value)
           →  governed-action set (union over levels)
```

The envelope's GRANT SET (and the compiled charter, envelope §7) gains `instanceRef` + effective params per grant. **Credentials are never part of the binding** — the binding names the instance; the Tool Proxy resolves instance → Secret Store ref → plaintext only at call time inside the control-plane process (invariant 10; 03 §2). A leaked envelope leaks a revocable run token and an instance *name*.

New readiness checks, extending envelope §5's list (same `ValidationIssue` shape):

| Check | Fires when |
|---|---|
| `CONNECTOR_UNBOUND` | an effective grant is connector-backed but no org instance serves its pack/family (subsumes `GRANT_EXECUTOR_MISSING` for `mcp` grants) |
| `CONNECTOR_GRANT_DISABLED` | role/node grants a key the org instance's `enabledGrants` mask excludes — the operator either enables it or strips it from the node; actuation never silently drops it |
| `CONNECTOR_SECRET_UNBOUND` | instance exists but a required `credentialKind` has no secret bound (specializes `GRANT_CREDENTIAL_UNBOUND`) |
| `GRANT_SCHEMA_DRIFT` / `PACK_TOOL_DRIFT` | live tool surface diverges from the curation pin — fail-closed vs. warning per the split in [01-connector-model.md](01-connector-model.md) §5 |

## 6. The worked example, resolved

The operator wants the `canopy-docs` pod (O2 shape: lead + `tech-writer` + `editor`) to draft a design proposal and submit it as a PR to the real Canopy repository.

**Roles (untouched, from `catalog.json`):** `tech-writer` = `["workspace.rw", "repo.read", "docs.repo.write"]`; `editor` = `["workspace.rw", "repo.read"]`; `engineering-lead` = `["workspace.rw", "repo.read", "repo.merge"]`. Both repo keys resolve via `provides` to `ci_gh_canopy`. The `editor` can read the repo and review the draft but possesses no write or PR capability — the QA-mirror pattern (envelope §6.2) at docs scale.

**The PR grant sits on the lead.** `connector.github.pr.create` is attached to the org's `engineering-lead` node as a chart-visible extension: the outward action belongs to the accepting manager, matching how `repo.merge` already sits on `engineering-lead` and how QA's verify sits opposite the engineer's write. The working group's alternative — an assignment-level temporary addition to the writer from the lead's transferable set (envelope §3.2) — remains legal and is the right shape for one-off direct submission; the tradeoff is one extra hop (lead accepts, then submits) against keeping outward authority where acceptance authority already lives. The pack's default role mappings encode the lead-side placement so the operator never faces the question (04 §2).

**The lead's `repo.merge` fails loud, on purpose.** `ci_gh_canopy` does not enable `connector.github.repo.merge`, so the lead's role-default `repo.merge` trips `CONNECTOR_GRANT_DISABLED` at actuation. The operator strips it from the node (the recursion boundary says merge is a human act on GitHub itself) — an explicit decision, recorded on the chart, not a silent drop.

**Node narrowing.** Writer node `a_tw01` narrows `pathPattern` to `docs/**`; the lead's PR grant narrows `branchPattern` to `canopy/docs/*`. Readiness passes: instance bound, secret present, no drift; derived tier stays **T1** — every grant here is read/write class with `minSandboxTier: 1`, no execute grants (envelope §5). Envelope stamped with bindings:

```
repo.read                   → ci_gh_canopy   params {pathPattern: docs/**}
docs.repo.write             → ci_gh_canopy   params {branchPattern: canopy/*, pathPattern: docs/**}
connector.github.pr.create  → ci_gh_canopy   params {branchPattern: canopy/docs/*}   [lead node]
                              governed: [create_pull_request], gate owner: operator
```

## 7. What the session receives

Connector grants ride the compiled-config path (`cli-runtime.md` §2 — session config is generated from the envelope, never authored) in two materialization modes:

**Mode A — brokered (default).** The grant's tools appear as namespaced tools on the *canopy* MCP server (`cli-runtime.md` §4, "granted tools via Tool Proxy executors as they land") — e.g. `github_create_pull_request` in the lead's session. Surface filtering (envelope layer 1) exposes them only to sessions whose run token carries the binding; the proxy re-checks per call (layer 2): run token → grant + binding → params check → **ApprovalGate if governed and unapproved** → credential injected from the Secret Store → proxy-as-MCP-client calls the pack's server → ToolEvent. The agent's `.mcp.json` still names exactly one server — the control plane, `--strict-mcp-config` — so the §3.6 boundary (*agents never mount external MCP servers directly*) is preserved verbatim.

**Mode B — materialized (repo-family grants).** `repo.read` / `*.repo.write` are served by the git-mediated executor *materializing a worktree* in the session cwd, cloned from the **bound instance's** source rather than `[repo] source` — the only delta is where the clone URL comes from. The writer's compiled `settings.json` then allows `Edit` / `Write` / `Bash(git *)` scoped to the worktree (`cli-runtime.md` §2's engineer example), while push, PR, and merge remain Mode-A brokered calls — the write that *leaves* the machine still passes the proxy, its gate, and its audit line.

The gate machinery is what makes governed connector actions cheap: gates suspend, `claude --resume <sessionId>` resumes (`cli-runtime.md` §1) — a PR awaiting operator approval is a suspended conversation, not a lost session. Instance edits take effect at next assignment intake, not mid-session, mirroring the `runtime_override` re-actuation rule (`cli-runtime.md` §1); the security consequences of stale session surfaces are handled by live per-call checks (03 §4).
