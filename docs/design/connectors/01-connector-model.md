# 01 — The Connector Model: Declaration

**Series:** [Connector Governance](README.md) · **Next:** [02-scoping-and-grants.md](02-scoping-and-grants.md)

## 1. What exists today, and what is missing

Three pieces of the connector story are already designed and shipping:

- `catalog/catalog.json` `toolGrants[]` is a first-class capability vocabulary: `{key, riskClass, minSandboxTier, executor, credentialKind?, governedActions?, params}` (`agent-envelope.md` §3.1).
- Roles grant by key: `tech-writer` holds `["workspace.rw", "repo.read", "docs.repo.write"]`, `editor` holds `["workspace.rw", "repo.read"]`, `engineering-lead` holds `["workspace.rw", "repo.read", "repo.merge"]` (`catalog.json` `roles[]`).
- The extension seam is open: the Tool Proxy's generic `mcp` executor adapts any external MCP server into grant-servable capabilities, behind the curation rule — registering a server auto-creates nothing; every exposed tool must be human-wrapped in a ToolGrant (`agent-envelope.md` §3.6).

What is missing is the noun. Envelope §3.6 ends with "grant packs distribute like the rest of the catalog" but gives that sentence no schema; the registered backend (`mcpx_gh01`) carries config and a credential but is not a named domain object an operator can list, bind, or kill; and the one connector-shaped thing in production — the repo — is a single global boot-time `[repo] source` in `canopy.toml`, one repo for every org, changeable only by restart. This document supplies the noun.

## 2. The connector pack

A connector is **declared** as a **connector pack**: a new top-level catalog section beside `roles[]` and `toolGrants[]`, versioned and distributable, bundling four things — (a) how the platform reaches the external system, (b) what secrets an instance must bind, (c) a per-instance config schema, and (d) the curated ToolGrants the pack contributes to the grant vocabulary. Pack grants are merged into the same vocabulary at catalog load, so every existing integrity check (`GRANT_UNKNOWN`, role-key resolution — envelope §5, §7) works unchanged.

The worked example's pack — the O2 GitHub pack, in full:

```jsonc
// catalog: connectorPacks[] — the O2 GitHub pack
{
  "key": "github",
  "version": 1,
  "title": "GitHub",
  "kind": "mcp-server",                       // executor family — see §3
  "server": {                                 // kind=mcp-server: launched/held by the CONTROL
    "transport": "stdio",                     //   PLANE, never a sandbox (envelope §3.6: the
    "command": ["github-mcp-server"],         //   proxy is the MCP client; agents never mount it)
    "toolSurface": [                          // the PINNED tool surface — §5
      "get_issue", "list_issues", "get_file_contents",
      "create_pull_request", "push_files", "merge_pull_request"
    ]
  },
  "secrets": [                                // credentialKinds an INSTANCE must bind (Secret
    { "credentialKind": "scm-token",          //   Store, invariant 10); scm-token matches the
      "required": true,                       //   kind catalog.json already uses for the
      "scopesHint": ["contents:rw", "pull_requests:rw"] }  // git-mediated write grants
  ],
  "configSchema": {                           // per-instance config; `narrowable` marks the axes
    "type": "object",                         //   roles and nodes may tighten (02 §4)
    "properties": {
      "owner":         { "type": "string" },
      "repo":          { "type": "string" },
      "branchPattern": { "type": "string", "default": "canopy/*", "narrowable": true },
      "targetBranch":  { "type": "string", "default": "main" },
      "pathPattern":   { "type": "string", "default": "**", "narrowable": true }
    },
    "required": ["owner", "repo"]
  },
  "grants": [                                 // curated ToolGrants — exact envelope §3.1 shape,
    {                                         //   plus `tools` (§5) and `provides` (§4)
      "key": "connector.github.repo.read",
      "riskClass": "read", "minSandboxTier": 1,
      "executor": "mcp",
      "tools": ["get_issue", "list_issues", "get_file_contents"],
      "credentialKind": "scm-token",
      "provides": ["repo.read"]
    },
    {
      "key": "connector.github.pr.create",
      "riskClass": "write", "minSandboxTier": 1,
      "executor": "mcp",
      "tools": ["create_pull_request", "push_files"],
      "credentialKind": "scm-token",
      "governedActions": ["create_pull_request"],   // O2: every public PR is an ApprovalGate
      "params": { "branchPattern": "canopy/*" }
    },
    {
      "key": "connector.github.repo.merge",
      "riskClass": "write", "minSandboxTier": 1,
      "executor": "mcp",
      "tools": ["merge_pull_request"],
      "credentialKind": "scm-token",
      "governedActions": ["merge_pull_request"],
      "provides": ["repo.merge"]
    }
  ]
}
```

Naming note, resolved for the series: envelope §3.6's illustrative grant `scm.github.pr` predates the namespace rule below and is superseded by `connector.github.pr.create`. The pack's credential kind is `scm-token`, not a new `github-token` — the catalog already defines `scm-token` on `code.repo.write` / `docs.repo.write`, and one kind means one secret can serve both the git-mediated executor and the MCP-brokered grants for the same repository.

## 3. Connector kinds

`kind` names the **executor family** that serves the pack — not the brand. GitHub, Slack, and a CRM are all packs; the kinds are:

| Kind | Served by | Examples |
|---|---|---|
| `mcp-server` | the Tool Proxy's generic `mcp` executor as MCP client (envelope §3.6) | GitHub, Slack, telephony, any third-party MCP server |
| `native` | a platform-side executor class (code plane) | `local-git` (05 §1 — today's `git-mediated` executor, reframed as a built-in pack) |
| `http-api` | the proxy's allowlisted HTTP executor | cloud read APIs (logs, metrics) where no MCP server exists |

The brief's four connector categories map onto this cleanly: **github** and **slack** are `mcp-server` packs; **cloud services** are `http-api` (or `mcp-server`) packs; **mcp-server** is the kind itself — the long tail. Adding a pack of any kind is catalog data; adding a *kind* is code, exactly the data/code boundary of envelope §1.

## 4. Capability namespaces — the two-layer rule

Connector capabilities get a dedicated namespace — `connector.<packKey>.<capability>` — **but roles should usually not reference it directly.**

- **Abstract capability keys** (`repo.read`, `docs.repo.write`, `repo.merge` — the keys already in `catalog.json` roles) remain the vocabulary roles grant. Roles are portable catalog data ("roles are data," envelope §1); a `tech-writer` archetype must not hardcode GitHub. A pack grant's `provides: ["repo.read"]` declares that, when this pack's instance is bound in an org, it *serves* that abstract key. This generalizes how `repo.read` already works — abstract key, `git-mediated` executor, concrete repo resolved elsewhere — so that "elsewhere" becomes the org binding (02 §2) instead of `[repo] source`.
- **Namespaced keys** (`connector.github.pr.create`, `connector.slack.channel.post`) exist for capabilities with no meaningful abstract family. Roles may grant them directly when the role is intrinsically about that system — a `social-media-manager` granting `connector.slack.channel.post` is honest, not a portability loss.

Collision safety at scale is mechanical: pack keys are unique in the catalog; the `connector.` prefix cannot collide with platform-native grants; `provides` aliases are validated at catalog load. An abstract key may be provided by many packs, but an *org* binds exactly one default instance per abstract family (02 §2) — which pack serves `repo.*` is an org decision, invisible to every role.

In the worked example: `tech-writer`'s existing `repo.read` and `docs.repo.write` resolve via `provides` to the org's GitHub instance with **zero role edits**. Only the genuinely GitHub-shaped capability — PR creation — uses the namespaced key.

## 5. How an MCP server declares its tool surface: it doesn't

`tools/list` is self-describing about *function* and silent about *risk* — nothing in a schema says whether calling a tool emails a customer. The curation rule (envelope §3.6) therefore applies to packs verbatim, with three mechanical consequences:

1. The pack **pins** `server.toolSurface` — the only tools the proxy will ever forward, regardless of what the live server advertises (this extends `toolAllowlist` from the `mcpx_gh01` shape).
2. Every forwarded tool must appear in some pack grant's `tools[]` with human-assigned `riskClass` / `governedActions` — the curated wrapper. A pinned tool wrapped by no grant is dead config; a grant referencing an unpinned tool fails catalog integrity.
3. At instance registration and per call, the proxy diffs the live server against the pin. Drift handling is split by stakes, resolving a working-group disagreement: for tools referenced by a **granted** capability, name-or-schema drift **fails closed per call** (`GRANT_SCHEMA_DRIFT` — the proxy records a hash of name + schema + description at curation and refuses on mismatch until a human re-curates); for the rest of the pinned surface, drift raises a `PACK_TOOL_DRIFT` readiness warning (same `ValidationIssue` shape as envelope §5), surfaced but not blocking. The tradeoff is explicit: fail-closed on granted tools trades availability for rug-pull safety — a server update can stall an org until re-curation — and we take that trade, because a silently widened tool is exactly the attack the curation rule exists to stop (03 §1, C-4). Advisory-only drift warnings on the unused surface keep the noise proportionate.

Tool descriptions the agent sees come from the curated grant, not the server's raw text — the compiled session surface (`cli-runtime.md` §2) never carries an external server's prose into a sandbox.

## 6. Relation to `toolGrants[]`, stated precisely

`connectorPacks[]` does not replace `toolGrants[]`; it *contains* contributions to it. At catalog load, pack grants merge into the one grant vocabulary; platform-native grants (`workspace.rw`, `shell.run`, `test.unit.run`) stay where they are. One vocabulary means one enforcement story: surface filtering, per-call proxy checks, tier derivation (`tier = max(minSandboxTier)`), and governed-action gating treat a pack-contributed grant identically to a native one. `riskClass` and `minSandboxTier` are pack-fixed at curation and untouchable downstream (02 §4) — a pack author's risk assignment is advisory until the operator confirms it at import (04 §3), and immutable after.
