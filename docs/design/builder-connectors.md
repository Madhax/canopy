# Connectors in the Builder — Design

**Status:** Implemented (2026-08-08) · **Date:** 2026-08-08 · *Scope amendment (2026-08-09): "org" here = **Team** post-C1; instances stay team-scoped, packs importable at Organization level — see the amendment on [`connectors/README.md`](connectors/README.md).*
**Reads with:** [builder-connectors-ux.md](builder-connectors-ux.md) (the UX), the `connectors/` governance series (this document implements its step-1 slice), `actuation/agent-envelope.md` §3, §5 (grants, readiness), `execution/cli-runtime.md` §2, §4 (compiled surface, MCP tool plane).

---

## 1. Scope: which slice of the proposal this builds

The governance series (`connectors/01–05`) is the design authority for packs, instances, scoping, and security; nothing here amends it. This document commits the **v1 implementation slice** — the adoption plan's step 0 remainder + step 1 (`connectors/05` §1–2) — and the builder surfaces over it:

| In v1 | Deferred (named in 05-adoption.md) |
|---|---|
| `connectorPacks[]` catalog section; `github` + `local-git` packs | pack registration UX, third-party packs, signing |
| `ConnectorInstance` store + CRUD + verify endpoint | instance lifecycle vs running actuations beyond next-intake semantics |
| org-wide and node link scoping | child-org path scoping; assignment-level temporary additions |
| capability mask (`enabledGrants`), param overrides | glob-subset *verification* (patterns are operator-trusted in v1 — the blocking open question stands) |
| GitHub: issues read (MCP tools), repo read/write (materialized), PR create (governed) | merge via connector; Slack pack; http-api kind; webhooks |
| readiness: `CONNECTOR_UNBOUND`, `CONNECTOR_SECRET_UNBOUND`, `CONNECTOR_GRANT_DISABLED` | `GRANT_SCHEMA_DRIFT` / `PACK_TOOL_DRIFT` (no live MCP servers in v1) |

**One deliberate narrowing, stated loudly:** the v1 GitHub pack is `kind: "native"` — a platform-side GitHub REST executor (httpx against `api.github.com`), not a spawned `github-mcp-server` (`connectors/01` §2 sketches `mcp-server`). Rationale: zero external binaries, an injectable transport making the whole path testable offline (the mock-provider doctrine, risk IM-2), and byte-identical governance semantics — the grant/instance/gate machinery cannot tell which kind serves a call. The `mcp-server` kind is step 3's generalization; the pack schema already carries `kind` so the migration is a pack edit, not a schema change.

## 2. Catalog: the `connectorPacks[]` section

New top-level section beside `roles[]` / `toolGrants[]`, exactly the `connectors/01` §2 shape minus `server` (native kind):

```jsonc
{
  "key": "github", "version": 1, "title": "GitHub", "kind": "native",
  "secrets": [{ "credentialKind": "scm-token", "required": true,
                "scopesHint": ["contents:rw", "pull_requests:rw", "issues:ro"] }],
  "configSchema": {
    "owner":         { "type": "string", "required": true },
    "repo":          { "type": "string", "required": true },
    "branchPattern": { "type": "string", "default": "canopy/*", "narrowable": true },
    "targetBranch":  { "type": "string", "default": "main" }
  },
  "grants": [
    { "key": "connector.github.issues.read", "riskClass": "read", "minSandboxTier": 1,
      "executor": "connector", "tools": ["github_list_issues", "github_get_issue"],
      "credentialKind": "scm-token", "provides": ["issues.read"] },
    { "key": "connector.github.repo.read", "riskClass": "read", "minSandboxTier": 1,
      "executor": "git-mediated", "credentialKind": "scm-token", "provides": ["repo.read"] },
    { "key": "connector.github.repo.write", "riskClass": "write", "minSandboxTier": 1,
      "executor": "git-mediated", "credentialKind": "scm-token",
      "provides": ["docs.repo.write", "code.repo.write"], "params": { "branchPattern": "canopy/*" } },
    { "key": "connector.github.pr.create", "riskClass": "write", "minSandboxTier": 1,
      "executor": "connector", "tools": ["github_create_pr"],
      "credentialKind": "scm-token", "governedActions": ["create_pull_request"] }
  ]
}
```

The **`local-git` pack** (`kind: "native"`, no secrets) reframes today's fixture/clone flow per step 0: config `{source}`, grants providing `repo.read` / `*.repo.write` via the existing git-mediated executor. `org_repo_source` (F8) becomes the migration fallback: at resolution, an org with no instance serving the `repo` family gets an implicit `local-git` instance from the F8 binding, then the boot `[repo] source`, then the fixture — exactly today's semantics, now expressed as instance resolution. No existing install re-answers anything.

Load-time integrity (extends the pinned checks in `test_catalog.py`): pack keys unique; every pack grant key starts `connector.<packKey>.`; `provides` targets must exist in `toolGrants[]`; grants merge into the one vocabulary so `GRANT_UNKNOWN` and role-key resolution work unchanged (`connectors/01` §6).

## 3. Control plane: the instance store

`connectors.py`, the `profiles.py` pattern (org-scoped operator data, Pydantic boundary, own table):

```sql
CREATE TABLE connector_instance (
    id              TEXT PRIMARY KEY,       -- ci_…
    organization_id TEXT NOT NULL,
    pack_key        TEXT NOT NULL,
    name            TEXT NOT NULL,
    config          TEXT NOT NULL,          -- JSON, non-secret
    secret_bindings TEXT NOT NULL,          -- JSON {credentialKind: secretId} — refs only
    enabled_grants  TEXT NOT NULL,          -- JSON [grantKey] — the org-level mask
    node_links      TEXT,                   -- JSON [nodeId] | NULL = org-wide
    enabled         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL, updated_at TEXT NOT NULL
);
```

`node_links NULL` = linked to the org root (org-wide); a non-empty list = node-scoped; an empty list = unlinked/inert (the dimmed pill). Plaintext credentials never touch this table — paste goes to the Secret Store, the row stores ids (invariant 10; `connectors/03` §2).

**Routes** (`routes/connectors.py`, operator API):

- `GET /teams/{id}/connector-packs` — catalog packs, for the palette.
- `GET|POST /teams/{id}/connectors`, `PUT|DELETE /teams/{id}/connectors/{cid}` — CRUD. POST/PUT validate: pack exists, required config present, `enabledGrants ⊆ pack grants`, node links exist in the chart. Secret values arrive in a write-only `secrets: {kind: value}` field, are stored, and are replaced by ids in the response.
- `POST /teams/{id}/connectors/{cid}/verify` — credential presence + a `GET /repos/{owner}/{repo}` probe through the executor; returns pass/fail + reason. Activity-logged.

All mutations log to the activity feed (`connector.created|updated|deleted|verify`) and take effect at **next assignment intake** (`connectors/02` §7) — running sessions keep their compiled surface; the per-call check below is what fails closed immediately on disable.

## 4. Resolution: instance → effective capability

One function, one place — `connectors.resolve(org_id, node_id, grant_key) -> Binding | None`:

1. Collect the org's enabled instances whose pack contributes `grant_key` directly, or whose `provides` covers it (abstract keys like `repo.read`).
2. Scope-filter: instance is org-wide, or `node_id ∈ node_links`.
3. Mask-filter: the serving pack grant ∈ `enabledGrants`.
4. Precedence: a node-linked instance outranks an org-wide one (the pin, `connectors/02` §3); two candidates at the same rank → the older instance wins deterministically and readiness carries a warning.
5. Params: pack defaults ⊓ instance `config` (v1 narrowing beyond that stays at the node inspector, unchanged).

Consumers:

- **`_effective_grants` (dp.py)** — unchanged for native grants; connector-backed checks now also require a resolving instance, so a repo write in an org whose GitHub instance is disabled 403s per call (the kill switch).
- **RepoManager `_source_for`** — resolution order becomes: instance serving `repo` family → F8 `org_repo_source` → boot `[repo] source` → fixture. A GitHub instance materializes via authenticated clone URL (`https://x-access-token:<token>@github.com/{owner}/{repo}.git`) with the token injected **only inside the control-plane process** at clone/push time and never written to disk config; remotes are re-stripped after use (`git remote set-url` to the tokenless form).
- **MCP tool plane (dp.py `TOOLS`)** — `github_list_issues` / `github_get_issue` / `github_create_pr`, surface-filtered by the same resolution (a node without a resolving instance never sees the tools) and re-checked per call.
- **Actuator readiness** — per node, for every connector-backed effective grant: no resolving instance → `CONNECTOR_UNBOUND`; instance but missing secret → `CONNECTOR_SECRET_UNBOUND`; role grants a key the mask excludes → `CONNECTOR_GRANT_DISABLED`. Same `ValidationIssue` shape, surfaced in the builder Issues panel and at actuation.

## 5. The governed PR path

`github_create_pr(title, body, head_branch)` from a session does not call GitHub. It opens a **governed action** via the existing machinery (`engine.open_governed_action`, E4): an ApprovalGate owned by the operator, payload carrying repo, branch, base, title, and the diff stat from the org clone. On approve, the executor — registered in the deps `executors` dict beside `repo-merge` — pushes the branch to the instance's remote and creates the PR via REST, records the attestation (PR URL, head SHA) in the resolution, and notifies. On deny, prohibition; nothing left the machine. Branch names must match the effective `branchPattern` (textual prefix check in v1; glob-subset verification remains the named open question).

This deletes the two manual operator steps E8 proved by hand (push + PR-create), which is the entire point of step 1 (`connectors/05` §2).

## 6. The GitHub executor and its test double

`github_client.py`: a thin typed client over httpx — `get_repo`, `list_issues(since, labels, state)`, `get_issue`, `push` (delegated to git via RepoManager), `create_pr`. The constructor takes an httpx transport; deps wires the real one; **tests wire `MockGitHubTransport`** — an in-memory repo/issues/PR fixture speaking enough of the REST dialect (ETags, `since` filtering, pagination) to exercise every path offline. CI never touches the network; the golden vectors run against the double; one opt-in integration test (env-gated, skipped in CI) speaks to a real repo. The same doctrine that made the mock gateway the spine (IM-2) applies verbatim.

## 7. Builder integration (UI)

- **Palette**: `Connectors` section from `GET …/connector-packs`; drag payload `{packKey}`.
- **Canvas overlay**: instances render as `ConnectorPill` nodes and their links as dashed edges, projected into React Flow alongside chart nodes but sourced from the connectors API, not the org document — the ActuationControls precedent (runtime data on an editor page). Drop → POST instance → pill appears; drag pill handle → node/root → PUT `node_links`.
- **Inspector**: `ConnectorPanel` (identity/config/credentials/capabilities/verify per the UX doc), a sibling of ProfilesSecretsPanel.
- **Agent-node chips**: computed client-side from instances + links (org-wide ⇒ all nodes), 🔒 when a reachable grant carries `governedActions`.
- Editor state: instances live in react-query (server truth), not the Zustand chart store; undo/redo does not cover them (they are operator data with their own audit trail, like profile edits).

## 8. Invariants (normative, testable)

1. No plaintext credential in any table, response, envelope, or compiled session file — Secret Store ids only; injection happens in-process at call time.
2. An agent's reachable connector surface is exactly: role/node effective grants ∩ org mask ∩ scope links — no path widens it (extends envelope §3.2's no-silent-widening one level up).
3. Disable fails closed per call, immediately; instance edits apply at next intake.
4. Every governed connector action resolves through an ApprovalGate with an attested resolution; deny leaves no external side effect.
5. With no instances configured, every current install behaves byte-identically to today (F8 → toml → fixture fallback chain).
6. CI runs the full connector path with zero network, zero credentials.

## 9. Test plan

Store CRUD + mask/link validation vectors; resolution precedence (node pin > org-wide, mask excludes, disabled excludes, fallback chain); readiness triple (`CONNECTOR_UNBOUND` / `SECRET_UNBOUND` / `GRANT_DISABLED`) golden vectors; governed PR arc against the mock transport (open → approve → push+PR attested; open → deny → nothing left); MCP surface filtering per node scope; catalog integrity pins updated for the new section; UI component tests for palette row, pill/link rendering, panel mask editing, and issue chips.
