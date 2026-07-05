# Canopy Catalog

`catalog.json` is the machine-readable form of the domain docs:

- [`../docs/archetypes.md`](../docs/archetypes.md) — 26 organization types (`organizationTypes`)
- [`../docs/roles.md`](../docs/roles.md) — 87 roles (`roles`)
- [`../docs/teams.md`](../docs/teams.md) — 16 formations (`formations`)

## Provenance (Phase 1)

Per the serialization path in [`../docs/README.md`](../docs/README.md), the markdown files are the
human-authored source of truth. The eventual pipeline is **frontmatter → catalog directory →
generated `catalog.json`**. Phase 1 takes the pragmatic first step described in
[`../docs/org-chart-editor.md`](../docs/org-chart-editor.md) §3.1: a hand-transcribed `catalog.json`
faithful to the docs' keys and cross-references, with CI checks for integrity.

When the frontmatter pass lands, generation replaces transcription and this file's **schema stays
put** — consumers (`server/src/canopy_server/catalog.py`, `ui/src/schema/catalog.ts`) do not change.

## Integrity guarantees (enforced by tests)

`server/tests/test_catalog.py` and `ui` catalog tests assert:

- All keys (`organizationTypes[].key`, `roles[].key`, `formations[].key`) are unique and kebab-case.
- Every `organizationTypes[].rolePalette` entry resolves to a known role key.
- Every `organizationTypes[].formations` entry resolves to a known formation key.
- Every `formations[].manager.roleKey` and `formations[].members[].roleKey` resolves to a known role.
- Every `formations[].dependencies[].from`/`.to` refers to a declared slot within that formation.
- `roles[].defaultSalary` values are structurally valid (positive allowance, warn threshold in (0, 100]).

## Notes

- `defaultSalary` values are **placeholder envelopes** flagged as calibration-pending. The Economics
  layer replaces them at runtime; the editor only needs sane numbers to show.
- **Slots** exist because a formation may wire two agents of the same role (e.g. `franchise-shift`
  has grill and fry `line-cook`s). Dependency wiring refers to slots, not role keys.
- `isManager` is `true` for the Leadership & Coordination group and for every role that heads a
  formation or archetype (leads/directors/chiefs). It drives node styling and formation slots only.
