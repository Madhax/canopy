# Connectors in the Builder — UX

**Status:** Design (v1 scope committed) · **Date:** 2026-08-08
**Reads with:** [builder-connectors.md](builder-connectors.md) (the technical design), `connectors/` (the governance series — declaration, scoping, security), `org-chart-editor.md` (the builder this extends), `actuation/agent-envelope.md` §3 (grants).

---

## 1. The one-sentence story

The operator drags a connector from the palette onto the chart, links it to the whole org or to a single node, fills in credentials and a capability mask once — and from then on, what an agent can reach in the outside world is exactly what the chart shows.

The governance series designed the nouns (packs, instances, grants, scoping). This document designs where the operator *touches* them: the builder. The principle it inherits is the series' own: **no grant that doesn't render somewhere an operator already looks** (`connectors/04-operations.md` §1). The builder canvas is the somewhere.

## 2. What the operator sees

### 2.1 The palette: a Connectors section

Below Roles and Formations, the palette gains **Connectors** — one row per catalog pack (`connectorPacks[]`): icon, title, kind badge (`native` / `mcp-server` / `http-api`), and a one-line "provides" summary ("repo read · branch push · PR create (gated)"). Rows are draggable like roles. Search spans them.

### 2.2 On the canvas: instances as pills, scope as edges

Dropping a pack onto the canvas creates a **connector instance** — rendered as a distinct pill (square-cornered, icon-led, visually *not* an agent node) parked at the drop point. Instances are **not chart structure**: the org document stays portable (org-chart-editor.md §10); the pill is an overlay object persisted in the control plane beside profiles and secrets, drawn on the same canvas because scope is a thing the operator must *see*.

Scope is an edge:

- **Instance → org root**: org-wide. Every node whose role grants a capability this instance serves can reach it. Rendered as a dashed edge to the root node.
- **Instance → specific node**: node-scoped. Only the linked node(s) resolve this instance; everyone else remains unconnected. One instance may link several nodes.

Linking is the same gesture as drawing a report edge: drag from the pill's handle to a node (or the root). Re-linking and unlinking are edge operations. An unlinked instance is inert — configured but serving nobody — and renders dimmed with an "unlinked" chip.

The rule the rendering enforces: **an agent's external reach is legible from the canvas alone.** If the GitHub pill has an edge to the org root, everyone can read the repo. If it points only at the lead, only the lead can. There is no fourth place to look.

### 2.3 The instance panel: configure once, plainly

Selecting a pill opens the inspector with the instance panel, four blocks top to bottom:

1. **Identity** — pack, name (editable; two instances of one pack need names: "canopy repo", "docs repo"), enabled toggle (the kill switch: disable fails every call closed, immediately).
2. **Configuration** — the pack's `configSchema` fields as a plain form (owner, repo, branch pattern, target branch…). Non-narrowable fields are marked "fixed at instance"; narrowable ones say "roles/nodes may tighten".
3. **Credentials** — one row per `credentialKind` the pack requires: a write-only secret field (`paste token — stored encrypted, never shown again`), a bound/unbound chip, and the pack's scopes hint rendered as guidance ("token needs: contents:rw, pull_requests:rw"). Paste goes straight to the Secret Store; the panel holds a reference, never a value — exactly the ProfilesSecretsPanel pattern.
4. **Capabilities** — the pack's grants as a checklist mask (`enabledGrants`): each row shows the grant key, risk-class badge (read / write / execute), a 🔒 marker on governed actions ("PR create — every call opens an approval gate you resolve"), and which abstract keys it provides ("serves: repo.read"). Unchecked = the org cannot use it at all, whatever any role says. The dangerous rows default off.

A **Verify** button per instance runs the connector's health check (credential present, endpoint reachable, repo visible) and reports pass/fail inline — misconfiguration surfaces in minutes at bind time, not mid-assignment (`connectors/04-operations.md` §1).

### 2.4 Feedback on the agent nodes

Agent nodes gain a small connector chip row: one icon per instance the node can reach (org-wide or by direct link), with a 🔒 variant when what it reaches includes governed actions. Hovering names the instance and the served grants. A role that grants a connector-backed capability *no instance serves* shows the existing issue treatment (amber) with `CONNECTOR_UNBOUND` in the Issues panel — the same loud-at-build-time posture as every readiness check.

## 3. Worked example: the bug-fix team

The operator builds the O3-shaped team that fixes bugs from GitHub issue reports:

1. Stamp the `product-engineering-pod` formation (lead, backend engineer, QA).
2. Drag **GitHub** from the palette; drop it beside the chart. The panel opens.
3. Name it `canopy repo`; set owner/repo; paste a fine-grained PAT scoped to that repo (`contents:rw`, `pull_requests:rw`, `issues:ro`). Verify → green.
4. Capability mask: enable `issues.read`, `repo.read`, `code.repo.write` (serves the engineer's existing role grant), `pr.create` (governed 🔒). Leave `repo.merge` off — merges stay human.
5. Link the pill to the **org root**: the whole team can read the repo and the bug reports.
6. The engineer's node already narrows `branchPattern` to `canopy/*` from the role default; nothing else to do. The lead's node carries `pr.create` — outward authority sits where acceptance authority already lives.

Six gestures, all on one screen, and the resulting chart *is* the security story: who can read bugs (everyone), who can push branches (the engineer), who can open a public PR (the lead, gated), who can merge (nobody).

## 4. What deliberately does not change

- **Roles stay portable.** No role edit mentions GitHub; abstract keys (`repo.read`) resolve through the org's instance (`connectors/01` §4). The palette drag never modifies a role.
- **The chart document stays pure.** Instances/links live in the control plane; exporting an org chart carries no tokens, no repo names, no machine-local detail. Importing a chart into a fresh install shows `CONNECTOR_UNBOUND` issues precisely where instances must be recreated — the checklist writes itself.
- **Execute-side surfaces stay authoritative for runtime.** Gate resolution (approving a PR) happens in the /execute inbox where all gates live; the builder shows *shape*, not queue state.

## 5. Out of scope for v1 (named, not implied)

Child-org (nested path) scoping of instances; per-node param *editing* from the pill (nodes narrow via the existing node inspector); pack import/registration UX (`connectors/05` step 3 — v1 packs ship in the catalog); Slack and http-api packs (the GitHub pack and the built-in local-git pack are v1); drift-diff visualizations (readiness issues carry the state).
