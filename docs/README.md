# Canopy Docs

Design documentation for Canopy: a framework for building AI-agent organizations as literal org charts — roles, reporting chains, and typed artifacts that route along the structure.

## The documents

| File | What it is | Domain concept it feeds |
|---|---|---|
| `mission.md` | The mission, the one-operator decision record, the standing commitments, and what Canopy is not. The root of the tree — every other document is downstream of it. | doctrine (`design/doctrine.md`) |
| `domain-model.md` | The core abstractions, lifecycles, and invariants. Read this first for the *how*; `mission.md` is the *why*. | everything below hangs off it |
| `archetypes.md` | Team types: the palette of chart kinds a user can build, each with its role set and dynamics | `TeamType` |
| `roles.md` | The role catalog: every role's purpose and responsibilities, written as duty → deliverable contract | `RoleTemplate` |
| `formations.md` | Formations: reusable manager+members subtrees with pre-wired artifact flow and dependencies | blueprint fragments for the chart |
| `use-cases.md` | The out-of-the-box acceptance suite: what a user can ask for on day one and what comes back | `Intent` recipes |
| `manager-responsibilities.md` | Taxonomy of manager responsibilities across all archetypes, coverage verdicts against the domain model, and proposed extensions for the gaps (mid-flight intervention, scope-divergence detection, checkpoints, standing directives) | proposal feeding `domain-model.md` |
| `phases.md` | The three phases — Build → Actuate → Execute — and the artifact each hands the next | product navigation |
| `org-chart-editor.md` | Design spec for the phase-1 WYSIWYG org-chart editor: catalog/document schemas, validation rules, thin FastAPI server, React Flow UI, build milestones | the editor + the serialized `Team` document (`canopy.team` v2; see the 2026-08 amendment) |
| `actuation/` | Phase-2 design suite: control/data plane topology, agent profiles (Claude/Gemini), sandboxes, agent runtime, workspaces/artifacts, A2A + bus fabric, roadmap. Start at `actuation/README.md`. | actuating the chart into running agents |
| `execution/` | Phase-3 design suite: the work layer made executable (Assignments, five Gates, Plans/Steps, assignment-bound meters, memory, cadences), the Claude-CLI-wrapped agent runtime (no API key), the ongoing operator experience (mission control, agent inspector, cost explorer, inbox), and the MVP-1 software-team plan. Start at `execution/README.md`. | executing work through the chart |
| `risks/` | Risk register and derisking strategy across seven contexts (problem-fit, usefulness, marketing, design, architecture, implementation, scalability). Start at `risks/README.md`. | keeping the project alive |
| `testing.md` | The consolidated testing strategy: four pillars, the current test estate, standing coverage rules, the milestone-by-milestone gap plan, CI topology, and the manual live path | keeping every other row true |
| `org-roadmap.md` | The milestone sequence in organizations, not features: the self-hosting ladder (docs → bug-close → feature → catalog → voice → frontdesk → Canopy Inc.), the trust/recursion rules, and the capabilities each rung pulls | what should be *running* on all of the above |
| `canopy-inc.md` | **Proposed:** the staff org design — the standing-team roster the ladder grows into (frontier, foundry, intake, maintenance, docs, release, receipts, forge, voice, frontdesk), the repo-as-coordination-medium principles, the self-extension loop, and the founding order | the `canopy-inc` Organization at cruise |
| `design/connectors/` + `design/builder-connectors*.md` + `design/standing-orgs*.md` | Adopted + implemented: connector packs/instances/scoping/security, the builder UX (palette → pill → scope edge), and triggers (work arrives on its own) | `ConnectorInstance`, `WorkTrigger` |
| `design/organizations/` | **Adopted, pre-MVP (C-series):** the Team/Organization/Pod vocabulary correction, the Organization entity (invariant 12), provider-truthful capacity, the portfolio scheduler, and the portfolio/capacity UX | `Organization`, `ProviderAccount`, `CapacityPool` |
| `design/experiments/` | **Adopted, post-MVP (L-series):** A/B testing for team structures — experiments, variants, trials, rubrics, blinded panels, search under an envelope, governed promotion; plus the proposed selection layer (`07`, 2026-08-16): factors, campaigns, the evidence store, advisory formation selection | `Experiment`, `Variant`, `Trial`, `Rubric`, `experiment_effect` |
| `design/doctrine.md` | **Proposed:** the doctrine cascade — mission-level purpose attached to the Organization and structurally present in every compiled agent context (doctrine → purpose → duty → task) | the Organization's voice |
| `design/unattended/` | **Proposed (H-series):** hands-off operation — the operations envelope (bounded standing consent), the daily brief + closed page set, platform continuity (supervision, credential health, backups), flow policies (trigger admission/refire, rebase, salary calibration), threat posture + docker T2, and the readiness checklist / fleet soak / posture ladder | `team_ops_envelope`, the brief, postures P0–P2 |
| `design/ux/` | **Proposed (UX-series):** the operator experience reorganized around questions, not machinery — altitudes and navigation, products-first team views (the artifact feed), the fleet-glance health model, and setup-as-product (`canopy up`, doctor, wizard) | the five surfaces; the health taxonomy; receipt cards |
| `plain-english/` | The companion series for non-engineers: what Canopy is, how work flows, how agents run, what keeps it safe — with a glossary | onboarding |

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
