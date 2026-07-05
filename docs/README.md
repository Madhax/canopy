# Canopy Docs

Design documentation for Canopy: a framework for building AI-agent organizations as literal org charts — roles, reporting chains, and typed artifacts that route along the structure.

## The documents

| File | What it is | Domain concept it feeds |
|---|---|---|
| `domain-model.md` | The core abstractions, lifecycles, and invariants. Read this first. | everything below hangs off it |
| `archetypes.md` | Organization types: the palette of org kinds a user can build, each with its role set and dynamics | `OrganizationType` |
| `roles.md` | The role catalog: every role's purpose and responsibilities, written as duty → deliverable contract | `RoleTemplate` |
| `teams.md` | Formations: reusable manager+members subtrees with pre-wired artifact flow and dependencies | blueprint fragments for the chart |
| `use-cases.md` | The out-of-the-box acceptance suite: what a user can ask for on day one and what comes back | `Intent` recipes |
| `org-chart-editor.md` | Design spec for the phase-1 WYSIWYG org-chart editor: catalog/document schemas, validation rules, thin FastAPI server, React Flow UI, build milestones | the editor + the serialized `Organization` document |

The layering is strict: **use cases** are satisfied by **archetypes**, which compose **formations**, which compose **roles**, which are constrained by the **domain model**. Anything expressible in the lower layers but not deliverable through the upper ones is a catalog gap, not a user error.

## Catalog conventions

- Every entity (archetype, role, formation, use case) has a stable **kebab-case key**. Keys are the serialization identifiers; prose titles are display strings and may change freely.
- Responsibilities are always written as *duty → deliverable*, and deliverables are marked **(A)** Artifact or **(Att)** ActionAttestation. A responsibility with no checkable discharge doesn't belong in the catalog.
- Roles are data, never code (domain-model invariant 11). Nothing in these files implies implementation.
- Cross-references between files are by key, in backticks: `product-engineering-pod`, `qa-engineer`.

## Serialization path (planned, not yet built)

These markdown files are the human-authored source of truth for now. The intended evolution, in order:

1. **Frontmatter pass** — each entity gets YAML frontmatter carrying its structured fields (key, category, roles, formations, deliverables); prose stays as the human description. Markdown remains readable; software reads the frontmatter.
2. **Catalog directory** — entities split one-per-file into `catalog/<kind>/<key>/` (mirroring the proven layout of Paperclip's teams-catalog, our reference architecture), with the docs here becoming the narrative overview.
3. **Schema + validation** — a JSON Schema per entity kind, a validator in CI, and a generated `catalog.json` manifest the runtime and the org-chart editor both consume.

Blueprints (serialized org instances for cloning/marketplace) are deliberately deferred — see non-goals in `domain-model.md`.
