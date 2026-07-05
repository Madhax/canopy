# Org Chart Editor — Front-End Design Spec (Phase 1: Build & Serialize)

**Status:** Implementation-ready draft
**Date:** 2026-07-05
**Scope:** The WYSIWYG org-chart editor and its thin persistence server — the *build* phase of Canopy's build → actuate → execute trajectory. No runtime, no agents executing, no actuation.
**Supersedes:** the earlier `DESIGN-frontend-org-chart.md` draft (written before the domain docs existed in this repo; its structural-archetype and free-form-dependency model conflicted with `domain-model.md` and is dropped).
**Reads with:** `domain-model.md` (authoritative for all invariants), `archetypes.md`, `roles.md`, `teams.md`, `use-cases.md`, `docs/README.md` (catalog conventions and serialization path).
**DX reference:** [Paperclip](https://github.com/paperclipai/paperclip) — one-command dev server, embedded storage, monorepo contract discipline. Reference for ergonomics only; Canopy shares no code with it.

---

## 1. What this phase builds

A user opens the editor, picks an **organization type** (an archetype from the catalog — `product-engineering`, `franchise-operation`, `research-lab`, …), and gets a canvas plus a palette of that archetype's roles and suggested formations. They drag roles and formations onto the canvas, wire reporting lines and sibling dependencies, mount child organizations, set salaries, and save. The output is a **serialized Organization document** — the structure-layer serialization `domain-model.md` already commits to: *chart + role bindings + salaries, explicitly excluding memory, secrets, and in-flight work*.

That document is what the future FastAPI control plane will actuate. The editor is the tool; the document is the product.

Two boundaries from the domain docs shape everything below:

- **This is not Blueprints.** `domain-model.md` explicitly defers org templates/cloning/marketplace. What we serialize here is the persistence format of a *specific organization being edited* — not a template artifact. Duplicate/import exist as operator conveniences, nothing more.
- **The editor draws only what the domain model can run.** Every wiring the canvas permits must correspond to a legal runtime structure. Anything the invariants forbid (a second manager, a cross-team dependency) must be *unrepresentable or rejected at draw time*, not caught later.

### Non-goals (phase 1)

No actuation or execution; no Intents, Assignments, Gates, or live status on nodes; no auth/multi-user; no real-time collaboration; no Blueprints/marketplace; no catalog *authoring* UI (the catalog ships as data; extending it is a repo contribution, though custom roles per document are supported — §3.4); no mobile editor (the org list should merely not break on small screens).

---

## 2. Domain alignment (what the editor must honor)

These are restatements of `domain-model.md` decisions as editor behavior — the source of truth remains that document.

| Domain rule | Editor consequence |
| --- | --- |
| **The chart is a tree** (inv. 1): every Agent has exactly one manager; only the org root has none. No matrix structure. | Reporting is stored as `managerId` on the agent — a second manager is *unrepresentable*. Connecting a report to a new manager **re-parents** (undoable), never adds a second edge. |
| **Dependencies connect siblings only** (inv. 4), declared by the manager, never crossing team boundaries. | `depends_on` edges can only be drawn between agents sharing the same `managerId`. Cross-team sequencing is expressed one level up — the editor rejects the shortcut with a message saying exactly that. |
| **Organizations are typed and nestable**; the parent sees only the child org's root (sub-org opacity). | Child organizations are first-class: an opaque mount node in the parent canvas, a full canvas of its own when drilled into. The parent canvas never renders the child's internals. |
| **Roles are data** (inv. 11); RoleTemplates are versioned; archetypes *offer* palettes but roles are catalog-wide (`code-reviewer` "under any lead" — `use-cases.md`). | The palette defaults to the archetype's offered set with a search across the full catalog. Placing an off-palette role is legal and produces no warning. Role bindings serialize as `key` + `version`. |
| **Salary is a core object**: per-assignment allowance, warn threshold (default 80%), hard-stop policy (default on); RoleTemplates ship defaults, the user overrides per node *in the editor*. | Salary is an editable inspector section on every agent and serializes with the chart. |
| **Directives are Assignment-scoped; only the user, through the editor, permanently changes an Agent.** | Per-agent `extensions` (instruction overrides, added responsibilities) are editable and serialized — this *is* that permanent-change surface. |
| **Formations are blueprint fragments**: "dropping one into the editor creates the manager node, its report nodes, and the standing dependency/artifact-routing pattern between them" (`teams.md`). | Formations are draggable palette items that stamp a pre-wired subtree, including its dependency edges. |
| **Projects and pipelines are non-goals.** | No cross-cutting grouping surface of any kind. The only structures are the tree, sibling dependencies, and nesting. |

---

## 3. Data model

### 3.1 Catalog

The catalog is the machine-readable form of `archetypes.md` (26 organization types), `roles.md` (~75 roles), and `teams.md` (16 formations). Per the serialization path in `docs/README.md`, the markdown files are the human-authored source of truth and the eventual pipeline is frontmatter → catalog directory → generated `catalog.json`. **Phase 1 takes a pragmatic first step:** a hand-transcribed `catalog/catalog.json`, faithful to the docs' keys and cross-references, with CI checks for integrity (unique keys, every role/formation reference resolves, every formation's roles exist). When the frontmatter pass lands, generation replaces transcription and the file's schema stays put.

```jsonc
{
  "kind": "canopy.catalog",
  "catalogVersion": 1,
  "organizationTypes": [
    {
      "key": "product-engineering",
      "title": "Core Product Engineering",
      "section": "tech-enterprise",        // grouping from archetypes.md §1–5:
                                            // tech-enterprise | physical-world |
                                            // knowledge-community | professional-services |
                                            // corporate-chassis
      "description": "Translating ambiguous market requirements into shipped, stable code.",
      "exampleIntent": "Release the new multi-tenant billing microservice by Q3.",
      "rolePalette": ["program-manager", "engineering-lead", "backend-engineer", "qa-engineer", "..."],
      "formations": ["product-engineering-pod", "design-studio-cell"]
    }
  ],
  "roles": [
    {
      "key": "backend-engineer",
      "version": 1,
      "title": "Backend Engineer",
      "group": "software-engineering",     // section heading from roles.md
      "purpose": "Server-side implementation",
      "responsibilities": [
        { "duty": "Implement features", "deliverable": { "kind": "artifact", "type": "PullRequest" } },
        { "duty": "Write unit tests",   "deliverable": { "kind": "artifact", "type": "TestSuite" } }
      ],
      "isManager": false,                   // true for Leadership & Coordination + lead roles;
                                            // drives node styling and formation slots
      "defaultSalary": { "perAssignmentAllowance": 150000, "warnThresholdPct": 80, "hardStop": true }
    }
  ],
  "formations": [
    {
      "key": "product-engineering-pod",
      "title": "Product Engineering Pod",
      "purpose": "Ship product features end-to-end with built-in verification.",
      "manager": { "slot": "lead", "roleKey": "engineering-lead" },
      "members": [
        { "slot": "backend",  "roleKey": "backend-engineer" },
        { "slot": "frontend", "roleKey": "frontend-engineer" },
        { "slot": "qa",       "roleKey": "qa-engineer" }
      ],
      "dependencies": [
        { "from": "qa", "to": "backend" },   // slot refs: QA depends on backend's output
        { "from": "qa", "to": "frontend" }
      ],
      "artifactFlow": "brief → engineers produce PullRequest → QA TestReport → lead accepts → publishes upward"
    }
  ]
}
```

Notes: **slots** exist because a formation may wire two agents of the same role (`franchise-shift` has two `line-cook`s — grill and fry); dependency wiring refers to slots, not role keys. `defaultSalary` values are **placeholder envelopes** authored in M1 and flagged as calibration-pending — the Economics layer's calibration story replaces them at runtime, but the editor needs sane numbers to show. All keys are kebab-case per catalog conventions.

### 3.2 Organization document (the serialized org chart)

One JSON document per top-level organization. Pydantic models (server) and Zod schemas (UI) both implement this shape; §5.4 explains how they're kept honest against each other.

```jsonc
{
  "kind": "canopy.organization",
  "schemaVersion": 1,
  "id": "6b9f2c1e-...",                     // uuid, server-assigned at creation
  "name": "Acme Software",
  "organizationType": "product-engineering", // catalog organizationTypes key
  "createdAt": "2026-07-05T18:00:00Z",
  "updatedAt": "2026-07-05T18:12:34Z",

  "agents": [
    {
      "id": "a_k7mp2x9q",                   // "a_" + nanoid(8), client-generated
      "name": "Engineering Lead",            // display name; defaults to role title
      "role": { "key": "engineering-lead", "version": 1 },
      "managerId": null,                     // null ⇒ this is the org root. THE tree encoding.
      "extensions": {
        "instructions": "",                  // permanent instruction overrides (the editor's
                                             // "only the user permanently changes an Agent" surface)
        "responsibilities": [                // added on top of the RoleTemplate's
          { "duty": "Run the weekly demo", "deliverable": { "kind": "attestation", "type": "DemoAttestation" } }
        ]
      },
      "salary": {                            // populated from role default at placement; user-editable
        "perAssignmentAllowance": 150000,
        "warnThresholdPct": 80,
        "hardStop": true
      },
      "position": { "x": 400, "y": 80 }      // canvas coordinates
    }
  ],

  "dependencies": [                          // design-time standing dependencies — the formation-
    {                                        // shaped "B consumes A's output" wiring, siblings only
      "id": "d_p3vq8n2m",
      "from": "a_qa000001",                  // the dependent (QA)
      "to": "a_be000001",                    // the dependency (backend) — "from depends on to"
      "note": "tests what engineering ships" // optional operator annotation
    }
    // Endpoints are agent ids — or a child-organization id, meaning that child org as an
    // opaque unit (semantically its root). A mounted child "looks like any other report"
    // (domain-model), so it participates in sibling dependencies like one.
  ],

  "customRoles": [                           // document-local RoleTemplates (see §3.4)
    {
      "key": "custom-release-captain",       // kebab-case, "custom-" prefix enforced
      "version": 1,
      "title": "Release Captain",
      "group": "custom",
      "purpose": "Owns release trains end to end.",
      "responsibilities": [
        { "duty": "Cut and verify releases", "deliverable": { "kind": "artifact", "type": "ReleaseCandidate" } }
      ],
      "isManager": false,
      "defaultSalary": { "perAssignmentAllowance": 120000, "warnThresholdPct": 80, "hardStop": true }
    }
  ],

  "childOrganizations": [                    // nesting — recursive, sub-org-opaque
    {
      "mountAgentId": "a_k7mp2x9q",          // the PARENT agent the child org's root reports to
      "organization": {                       // a complete canopy.organization document
        "kind": "canopy.organization",
        "schemaVersion": 1,
        "id": "c4d81f0a-...",
        "name": "Acme Support",
        "organizationType": "customer-support-center",
        "agents": [ /* its own root has managerId: null WITHIN this child document */ ],
        "dependencies": [],
        "customRoles": [],
        "childOrganizations": [],             // nesting recurses
        "meta": {}
      }
    }
  ],

  "meta": {}                                  // passthrough; operator notes / forward-compat
}
```

**Deliberate encoding choices:**

- **`managerId` instead of a reporting-edge list.** The tree invariant is structural: a second manager cannot be expressed, only replaced. The canvas *renders* reporting edges from `managerId`; it never stores them separately. A `managerId` chain that loops (a→b→a) is still checkable and is an error (`REPORTS_CYCLE`).
- **Dependencies are a separate edge list**, because they genuinely are edges — but constrained to siblings (§5). Direction: `from` depends on `to` (`to`'s deliverable feeds `from`'s brief), matching the manager's-eye reading in `teams.md`.
- **Child orgs nest the full document recursively** under a mount point, mirroring "a nested Organization is a full Organization … attached at a mount point: its root Agent reports to a designated Agent in the parent." The parent document knows only the mount; everything about the child lives inside the child's own subtree of JSON. Timestamps and ids exist at every level; persistence, export, and validation always operate on the **top-level** document as one unit.
- **Excluded on purpose** (per the structure-layer serialization note in `domain-model.md`): memory, secrets/credentials, and any in-flight work objects. There is nowhere in this schema to put them, which is the point.
- **Forward-compat:** unknown keys rejected everywhere except `meta` (all levels) — the single escape hatch. `schemaVersion` gates loading; `migrateOrganization()` (identity in v1, hard error above 1) runs before parse on both sides.
- **Canonical export:** keys in schema order, agents/dependencies sorted by id, 2-space indent — exports diff cleanly.

### 3.3 IDs and naming

Document ids: server-assigned UUIDs. Agent/dependency ids: client-generated `a_`/`d_` + nanoid(8) so editing never blocks on the server. All catalog keys kebab-case (catalog convention); display names free-form.

### 3.4 Custom roles

The catalog is extensible by design ("users and the community define new ones without touching the core"), but catalog authoring is a repo/data contribution, not an editor feature. What the editor supports is **document-local roles**: define a role inline (title, purpose, responsibilities as duty → deliverable, manager flag, default salary), key auto-derived and `custom-`-prefixed, stored in `customRoles`, usable anywhere in that document. Responsibilities must carry a deliverable contract — the form doesn't allow a duty without one, enforcing "a responsibility with no checkable discharge doesn't belong."

---

## 4. Validation

One rule set, defined here, implemented twice (Python authoritative on save/export, TypeScript for live canvas UX), kept in lock-step by shared golden test vectors (§5.4).

```
ValidationIssue: { severity: "error" | "warning", code: string, message: string,
                   agentIds?: string[], dependencyIds?: string[], orgPath?: string[] }
```

`orgPath` locates issues inside nested orgs (list of org ids from root).

### 4.1 Rules

| Code | Severity | Rule |
| --- | --- | --- |
| `DUPLICATE_ID` | error | Agent/dependency ids unique within their organization document. |
| `REPORTS_CYCLE` | error | The `managerId` chain must be acyclic (a tree, given single-parent encoding). |
| `NO_ROOT` | draft: warning · export: error | Exactly one agent per organization (each nesting level) must have `managerId: null`. Zero roots ⇒ `NO_ROOT`. |
| `MULTIPLE_ROOTS` | draft: warning · export: error | More than one agent with `managerId: null`. |
| `MANAGER_DANGLING` | error | `managerId`, when set, must reference an existing agent in the *same* organization document. |
| `DEP_DANGLING` | error | Dependency endpoints must reference an existing agent — or a mounted child organization's id — in the same organization document. |
| `DEP_SELF` | error | No self-dependencies. |
| `DEP_DUPLICATE` | error | At most one dependency per ordered (from, to) pair. |
| `DEP_NOT_SIBLINGS` | error | Dependency endpoints must report to the same manager — an agent's `managerId`, a child org's `mountAgentId` (invariant 4: siblings only, one team). Never drawable in the UI; guards imports. |
| `DEP_CYCLE` | error | The dependency subgraph within each sibling group must be acyclic. |
| `ROLE_UNKNOWN` | warning | `role.key` not found in catalog or `customRoles` (import case; renders as missing-role node, re-assignable in inspector). |
| `ROLE_VERSION_UNKNOWN` | warning | Role key exists but the pinned version isn't known to this catalog. |
| `MOUNT_DANGLING` | error | `mountAgentId` must reference an existing agent in the parent document. |
| `CHILD_INVALID` | (bubbled) | Child organizations are validated recursively; their issues surface with `orgPath`. |
| `SALARY_INVALID` | error | `perAssignmentAllowance` must be a positive integer; `warnThresholdPct` in (0, 100]. |
| `AGENT_ORPHAN` | warning | Agent with a manager but no role in any dependency and no reports — drafting aid only. |

Notably absent: any "off-palette role" issue. Archetype palettes are defaults, not fences (`use-cases.md` puts `code-reviewer` and `tech-writer` "under any lead").

### 4.2 Modes

- **Draft** (autosave, live editing): `NO_ROOT`/`MULTIPLE_ROOTS` downgrade to warnings; documents with errors still persist. Operators never lose work to validation.
- **Export** (export & import endpoints): full severity; export refuses (HTTP 422 + issues) while any error exists anywhere in the tree of orgs.

### 4.3 Incremental checks (UI-side)

`checkReparent(doc, agentId, newManagerId)` and `checkDependency(doc, from, to)` — constant-time predicates behind React Flow's `isValidConnection`, evaluating only the rules a single new connection can break (`REPORTS_CYCLE` probe along ancestors, `DEP_NOT_SIBLINGS`, `DEP_DUPLICATE`, `DEP_SELF`, `DEP_CYCLE` probe). Rejections toast the exact rule message, e.g. *"Dependencies connect siblings only — sequence these one level up, between their managers."*

---

## 5. Repository layout, stack, and DX

The UI is React + Vite + TypeScript with React Flow (`@xyflow/react` v12). The thin server is **FastAPI** — chosen deliberately so this API grows into the planned control plane rather than being rewritten; the JSON-file store is the only throwaway part.

```
canopy/
├── README.md
├── docs/                          # this file and the domain docs
├── catalog/
│   ├── catalog.json               # phase-1 hand-transcribed catalog (see §3.1)
│   └── README.md                  # provenance + the generation plan
├── testdata/
│   └── validation/                # golden vectors: *.json fixtures {document, mode, expectedIssues}
├── server/                        # FastAPI thin control plane
│   ├── pyproject.toml             # managed with uv; fastapi, uvicorn, pydantic v2, pytest, ruff
│   ├── src/canopy_server/
│   │   ├── main.py                # app factory; serves ui/dist statically in prod
│   │   ├── config.py              # CANOPY_PORT (default 8700), CANOPY_DATA_DIR (default ./data)
│   │   ├── models.py              # pydantic: Organization, Agent, Dependency, Salary, Catalog…
│   │   ├── store.py               # JSON file store, atomic write (tmp + rename), per-doc files
│   │   ├── catalog.py             # loads catalog/catalog.json at startup, integrity-checked
│   │   ├── validation/            # rules.py, codes.py — authoritative implementation
│   │   └── routes/                # health.py, catalog.py, organizations.py
│   └── tests/                     # pytest: routes, store, validation vs golden vectors, catalog integrity
├── ui/                            # React 19 + Vite + TS (pnpm)
│   └── src/                       # full tree in §7
├── package.json                   # root: dev orchestration scripts (concurrently)
└── data/                          # runtime store (gitignored): data/organizations/<uuid>.json
```

**Dev experience (the Paperclip bar):**

```sh
pnpm install && uv sync --project server     # once
pnpm dev                                      # → open http://localhost:5173
```

`pnpm dev` runs both processes via `concurrently`: `uvicorn --reload` on **8700** and Vite on **5173** with `/api` proxied to 8700. One command, one URL to open. Production: `pnpm build` builds the UI; `uvicorn canopy_server.main:app` on 8700 serves API + static UI from one port. `pnpm test` runs pytest + vitest; `pnpm typecheck` runs tsc + basic pyright/ruff checks.

### 5.4 Keeping two validators honest

Python (authoritative) and TypeScript (live UX) implement the same §4 rule set. Drift is prevented by **golden test vectors**: `testdata/validation/*.json`, each a document + mode + the exact expected issue list (codes + target ids). Both pytest and vitest iterate the same directory and must produce identical results; adding a rule means adding vectors, and CI fails if either side disagrees. Issue codes and messages live in the vectors, so even message wording stays aligned.

---

## 6. Server — REST contract

Base `/api`, JSON bodies, errors as `{ "error": { "code", "message", "issues"? } }`. This contract is the seam the real control plane inherits; nothing in the UI may assume the JSON-file store.

| Method & path | Purpose | Notes |
| --- | --- | --- |
| `GET /api/health` | Liveness | `{ status: "ok", version }` |
| `GET /api/catalog` | Catalog | Full catalog.json, ETag-cacheable. |
| `GET /api/organizations` | List | Summaries: `{ id, name, organizationType, agentCount (recursive), childOrgCount, updatedAt, valid }`. |
| `POST /api/organizations` | Create | `{ name, organizationType, seed }` where `seed` = `{ kind: "blank" }` \| `{ kind: "root", roleKey }` \| `{ kind: "formation", formationKey }` (formation manager becomes the root). → `201` full document. |
| `GET /api/organizations/{id}` | Read | Full document (with nested children). |
| `PUT /api/organizations/{id}` | Save | Full replace. Schema parse (`400`), id match, optimistic concurrency: body `updatedAt` must equal stored (`409 STALE_WRITE`). Runs draft validation, persists even with errors, bumps `updatedAt`. → `{ document, issues }`. Server re-imposes immutable fields (`id`, `createdAt`, `kind`, `schemaVersion`). |
| `DELETE /api/organizations/{id}` | Delete | `204`. |
| `POST /api/organizations/{id}/validate?mode=draft\|export` | Validate stored doc | `{ issues }`. |
| `GET /api/organizations/{id}/export` | Canonical export | Export-mode validation; `422` + issues on errors, else canonical JSON, `Content-Disposition: attachment; filename="<slug>.organization.json"`. |
| `POST /api/organizations/import` | Import | Accepts any supported `schemaVersion`; migrates, parses (`400` with path-precise messages), assigns **new ids throughout** (document and all nested org ids — import never collides), runs draft validation. → `201 { document, issues }`. Also the mechanism behind list-page "Duplicate". |

Child organizations are not separately addressable resources in phase 1 — they save/load/validate/export as part of their top-level document. (The control plane may promote them later; the editor doesn't care.)

---

## 7. UI — the WYSIWYG editor

### 7.1 Routes

| Route | Page |
| --- | --- |
| `/` | Organization list |
| `/organizations/new` | Creation wizard |
| `/organizations/:id` | Editor (top-level org) |
| `/organizations/:id/org/:childOrgId/*` | Editor drilled into a nested child org (path segments nest further) |

### 7.2 Organization list

Cards: name, organization-type badge (with section color from §3.1's five sections), recursive agent count, child-org count, relative `updatedAt`, validity dot. Actions: open, duplicate, export (issues dialog on 422), delete (confirm). Header: New organization, Import. Empty state pitches the product in one paragraph ("the chart isn't a diagram of the system — it *is* the system") with a prominent create button.

### 7.3 Creation wizard (2 steps)

1. **Organization type.** Searchable grid grouped by the five sections of `archetypes.md` (Tech Enterprise, Physical World, Knowledge & Community, Professional Services, Corporate Chassis). Each card: title, one-line problem statement, example intent (muted, italic), role-palette chips, suggested-formation chips.
2. **Name & seed.** Name (default "Untitled <Type>"). Seed choice: **Start from a formation** (cards for the archetype's suggested formations, showing manager + members + a mini flow line; the formation's manager becomes the org root) · **Root agent only** (role picker defaulted to the archetype's leadership role, falling back to `chief-executive`) · **Blank canvas** (first agent placed with no manager becomes the root; `NO_ROOT` warning shows until then).

### 7.4 Editor layout

```
┌────────────────────────────────────────────────────────────────┐
│ Breadcrumbs: Acme Software / Acme Support   ·  save status     │
│ Toolbar: name ✎ · validate ⚠︎2 · auto-layout · undo redo ·     │
│          zoom-fit · export · back                              │
├──────────┬────────────────────────────────────┬────────────────┤
│ Palette  │        React Flow canvas           │   Inspector    │
│ (260px)  │   minimap · controls · dot grid    │    (340px)     │
└──────────┴────────────────────────────────────┴────────────────┘
```

Breadcrumbs are the nesting UI: each segment is an organization; the current canvas always shows exactly one organization's internals.

#### Palette (left)

Three sections, searchable together:

- **Roles** — the current org's archetype palette by default, grouped by `roles.md` group; a "whole catalog" toggle reveals every role (search always spans the whole catalog and auto-flips the toggle on match). Row: manager/IC glyph, title, group color dot. Drag to canvas to place an agent (name defaults to role title; salary defaults from the role). Double-click places at viewport center.
- **Formations** — the archetype's suggested formations first, the rest collapsed below. Row: title + member count; hover card shows manager, members, and the artifact-flow line from the catalog. **Drop on an existing agent**: stamps the subtree with the formation's manager reporting to that agent. **Drop on empty canvas in a rootless chart**: the formation's manager becomes the root. Stamps include the formation's pre-wired dependency edges (slot-resolved) and are one undo unit.
- **Special** — "＋ Custom role" (opens the §3.4 form) and "＋ Child organization" (name + organization-type mini-wizard; requires dropping onto the parent agent it mounts under, or selecting one in the dialog).

#### Canvas (center)

- **Agent node** (`AgentNode`): rounded card; left border colored by role group; role title small and muted over the agent display name; a small crown glyph for `isManager` roles; salary shown compactly (e.g. "150k · 80% · hard-stop") when the node is selected; error badge when implicated in a current issue.
- **Child-org node** (`ChildOrgNode`): visually distinct — heavier border, organization-type badge, recursive agent count, and an "Open ⤢" affordance. Double-click (or Open) navigates into the child canvas. It exposes only a top reporting handle (it reports to its mount agent); its internals are invisible here — sub-org opacity, rendered literally. Child-org nodes can be dependency endpoints **as siblings** like any other report (the edge semantically targets the child org's root).
- **Handles & edges:** top/bottom handles carry reporting (drag child-top → manager-bottom); connecting an agent that already has a manager **re-parents it** after the incremental check passes (single undoable action). Left/right handles carry dependencies (dependent-left → dependency-right), drawn dashed with an arrowhead toward the dependency; reporting edges are solid. Handle pairing determines meaning — there is no edge-mode toggle.
- **Live validation:** `isValidConnection` runs the incremental checks; rejections toast the rule. Full validation re-runs debounced (300 ms) on any mutation, feeding the toolbar badge, node badges, and the issues panel.
- Selection (click / shift / drag-box), `Delete` (removing an agent orphans its reports — they lose their manager and surface as `NO_ROOT`-adjacent warnings rather than being cascade-deleted; removing a child-org node deletes the mount *and* prompts before discarding the child document), `⌘Z`/`⌘⇧Z`, `⌘S`, zoom-to-fit.

#### Inspector (right)

- **Agent selected:** display name; role (title, group, `key@version`; re-assign picker — also the repair path for `ROLE_UNKNOWN`); **Salary** (allowance stepper, warn-threshold slider, hard-stop toggle, "reset to role default"); **Extensions** — permanent instructions (textarea) and added responsibilities (duty + deliverable kind/type rows; deliverable required); danger-zone delete.
- **Dependency selected:** "‹from› depends on ‹to›" summary, optional note, delete.
- **Child org selected:** name, type, mount agent (re-mountable via picker), agent count, Open button, delete.
- **Nothing selected:** organization settings (name; type read-only after creation in v1) and the **issues panel** — errors first, each row focusing/panning to its targets on click; issues from nested orgs show their `orgPath` and clicking drills in.

#### Toolbar behaviors

Autosave: 1 s debounce, whole top-level document per save regardless of which nested canvas is open. Save states: Saved / Saving… / Unsaved / Failed-retry (exponential backoff); `409` conflict → dialog offering reload-theirs / overwrite-mine. Auto-layout: dagre, top→bottom on the reporting tree of the *current canvas*, dependency edges ignored for ranking; result is one undo unit. Export always exports the top-level document.

### 7.5 State architecture

- **Document store** (zustand + zundo temporal): holds the **top-level** Organization document — single source of truth, nested orgs included. All mutations are named actions (`placeAgent`, `reparentAgent`, `addDependency`, `stampFormation`, `mountChildOrg`, `updateSalary`, …); drag-move batches to one history entry on drag-end. Selection/viewport state lives outside the temporal scope.
- **Canvas projection:** pure functions derive React Flow nodes/edges *for the currently open org path* — reporting edges from `managerId`, dependency edges from the list, child orgs as single nodes. RF change events translate back into store actions. RF never owns document data.
- **Server sync:** TanStack Query for catalog/list/document reads; a debounced `PUT` mutation for autosave. `sessionStorage` mirror as crash rescue (offered on reload if newer than server copy). `beforeunload` guard while dirty.

### 7.6 Visual design

Tailwind CSS v4; light/dark via `prefers-color-scheme`. Role-group colors assigned once in the UI theme (leadership/coordination amber, engineering blue, infra/security cyan, data/AI violet, product/design pink, marketing green, sales/customer orange, people teal, finance/legal slate, physical-ops brown, healthcare red, research indigo, media/events fuchsia, professional-services stone, nonprofit lime — exact palette at implementation, AA-checked in both themes). Node ~220×72 px; smooth at 150+ agents per canvas (memoized nodes, no per-node store subscriptions). Tone: calm and product-grade — Linear/Paperclip, not a toy diagrammer.

### 7.7 UI file inventory (indicative)

```
ui/src/
├── main.tsx · App.tsx · index.css
├── api/            client.ts · organizations.ts · catalog.ts
├── schema/         organization.ts (Zod) · catalog.ts · migrate.ts   # mirrors server models
├── validation/     rules.ts · incremental.ts · codes.ts             # golden-vector tested
├── store/          document-store.ts · selection-store.ts · projection.ts
├── pages/          OrganizationListPage.tsx · NewOrganizationWizard.tsx · EditorPage.tsx
├── components/
│   ├── common/     Button · Dialog · Toast · Badge · EmptyState · ConfirmDialog
│   ├── list/       OrganizationCard · ImportButton
│   ├── wizard/     TypeStep · SeedStep · FormationCard
│   └── editor/
│       ├── EditorLayout · Toolbar · Breadcrumbs · SaveStatus
│       ├── palette/    Palette · RoleRow · FormationRow · CustomRoleForm · ChildOrgDialog
│       ├── canvas/     OrgCanvas · AgentNode · ChildOrgNode · ReportingEdge · DependencyEdge
│       └── inspector/  Inspector · AgentPanel · DependencyPanel · ChildOrgPanel
│                       · OrgSettingsPanel · IssuesPanel · SalaryEditor · ExtensionsEditor
├── hooks/          useAutosave · useOrgDocument · useKeyboardShortcuts
└── lib/            auto-layout.ts · download.ts · format.ts · ids.ts
```

---

## 8. Testing

| Layer | Tooling | Must cover |
| --- | --- | --- |
| Golden vectors | shared JSON | ≥2 vectors (pass + fail) per §4 rule code, incl. nested-org cases with `orgPath`; both validators consume identically. |
| server | pytest | CRUD; draft-save persists with errors; export 422 gating; import re-ids everything incl. nested orgs; `409` stale write; immutable fields; atomic write crash-safety; catalog integrity (unique keys, resolvable cross-refs, every formation slot/dependency valid); seed modes (blank/root/formation). |
| ui | vitest + Testing Library | projection both directions (managerId ⇄ edges, child-org nodes); store actions incl. re-parent, formation stamp as one undo unit, orphan-on-delete; incremental checks parity vs golden vectors; wizard gating; salary editor bounds. |
| e2e (M6) | Playwright | Wizard → formation seed → drag role → wire dependency → get sibling-rule rejection → mount child org → drill in, add agent, drill out → reload (persistence) → export → re-import. |

CI gate: `pnpm typecheck && pnpm test && pnpm build` green, golden vectors passing on both sides.

---

## 9. Build order (milestones for Claude Code)

Each milestone ends green and demoable.

1. **M1 — Catalog + schemas + validators.** Transcribe `catalog/catalog.json` from `archetypes.md`/`roles.md`/`teams.md` (all 26 types, ~75 roles, 16 formations, slot wiring; placeholder salaries). Pydantic + Zod schemas for catalog and organization documents. Both validators + the full golden-vector suite. Catalog integrity tests.
2. **M2 — Server.** FastAPI app, JSON store (atomic writes), all §6 routes with seeds, static-UI serving for prod, pytest suite. Root `pnpm dev` orchestration works with a placeholder UI.
3. **M3 — UI shell.** Routing, API client + React Query, organization list (import/export/duplicate/delete), creation wizard with all three seed modes. Created orgs open a stub editor rendering the raw document.
4. **M4 — Editor core.** Canvas with agent nodes, reporting via managerId (place, connect, re-parent), dependency edges with sibling enforcement, palette (roles + search + whole-catalog toggle), inspector (agent panel with salary + extensions), autosave with conflict dialog, undo/redo.
5. **M5 — Full model.** Formation stamps (palette drag, slot-wired dependencies, one undo unit), child organizations (mount, drill-in breadcrumbs, opaque nodes, recursive validation with `orgPath`), custom roles, issues panel with cross-org focus, auto-layout, export gating, keyboard shortcuts, sessionStorage rescue.
6. **M6 — Polish + E2E.** Dark theme, empty/error states, 150-agent performance pass, Playwright suite, README quickstart, and split §3.2 out into `docs/serialization.md` as the standalone format reference.

**Acceptance (phase 1 done):**

- Clean clone → `pnpm install && uv sync --project server && pnpm dev` → working editor, zero config.
- I can create a `product-engineering` org seeded from `product-engineering-pod`, watch QA's pre-wired dependencies arrive with the stamp, get rejected (with the "siblings only" message) when I try to wire a dependency across teams, mount a `customer-support-center` child org under the lead, drill in, build its tier, drill out, and export one valid document containing it all.
- Re-importing that export reproduces the structure with fresh ids; the export passes export-mode validation; every §4 code has passing golden vectors on both validators.
- A refresh mid-edit loses at most ~1 second of work.

---

## 10. Seams for actuate & execute (context only — do not build)

Where phase 2/3 will attach, recorded so phase-1 shapes stay honest: each **agent** becomes a provisioned runtime agent (role instructions + extensions seed its persona; salary funds its BudgetMeters); **`managerId`** becomes the delegation/escalation route; **dependencies** become the manager's default Dependency declarations when it fans out an Intent; **child orgs** mount as sub-org-opaque reporting edges; the **export document** is the actuation input, which is why export-mode validation is strict and versioned. The document deliberately contains no memory, credentials, or work state — those are runtime-owned. Phase 1 must not add fields for models, adapters, tools, or costs; those decisions belong to the control plane and the catalog's tool-grant story, not the chart.
