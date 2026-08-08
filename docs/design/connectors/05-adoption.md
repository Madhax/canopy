# 05 — Adoption: From One Global Repo to a Connector Ecosystem

**Series:** [Connector Governance](README.md) · **Prev:** [04-operations.md](04-operations.md)

The migration constraint: an existing install must never re-answer a question it already answered. Today the repo target is a single global `[repo] source` in `canopy.toml`, read at boot; every `git-mediated` grant implicitly points at it, and changing it means a restart. That is the gap this sequence closes first — and each step has a named consumer already on the roadmap, with risk rising one notch per step.

## 1. Step 0 — reframe, don't move (zero disruption)

Model the current local-clone flow as a built-in **`local-git` connector pack** (`kind: native`, 01 §3): executor the existing `git-mediated` one, `configSchema` `{source: path, branchPattern, targetBranch}`, `provides: ["repo.read", "code.repo.write", "docs.repo.write", "repo.merge"]`. Then:

- Each actuated org gets its own `local-git` (or `github`) instance — **the repo target becomes per-org operator data, mutable without restart**, created and edited through the operator API like secrets are today.
- `canopy.toml [repo] source` degrades to a *migration fallback*: at actuation, an org with no instance serving `repo.*` gets an implicit instance from the toml value (empty ⇒ the `examples/target-app` fixture — exactly today's semantics). No config change, no behavior change; the connector model is at first only a new name for the current truth. One release later the fallback warns; eventually it dies.
- E4's local git executor and O2's remote-git extension become two packs sharing the `repo.*` family — the org decides whether "the repo" is a local clone or a GitHub remote, and *nothing in any role changes* (01 §4).

**Worked example at this step:** the docs pod still points at a local clone; the operator's only visible change is that the repo binding now lives on the org, next to its secrets.

## 2. The increments

**Step 1 — the O2 GitHub pack (smallest shippable increment).** The pack of 01 §2, one instance, three capabilities: issue read (feeding the ingestion cadence), branch push on `canopy/*`, PR-create as a governed action. Consumed immediately by `canopy-docs`; acceptance test is O2's done-bar (five merged docs PRs, cost per PR published — `org-roadmap.md` §O2). This increment forces the real plumbing everything later needs — Secret Store credential path, proxy-as-MCP-client, ApprovalGate on an outward action — at docs-PR stakes, where a wrong PR costs nothing. E8 proved the flow by hand (operator pastes the issue in, pushes the branch out); the pack's whole job is to delete those two manual steps. **Worked example:** this is the step where the docs pod's scenario, run by hand in E8, becomes the machinery of 02 §6 and 04 §2.

**Step 1.5 — repo source per actuated org, claimed explicitly.** Once "the repo" is a connector rather than a boot flag, binding it per actuated org (no server restart) is the natural next move — one Canopy instance running `canopy-docs` against the Canopy repo and a second org against a customer repo. Already an operator-requested direction and cheap once step 0 lands; the proposal claims it rather than leaving the global binding fossilized.

**Step 2 — Slack notify pack.** Outbound-only, one webhook secret, default-on digest for gate-opened / budget-warn / intent-complete. Highest leverage per unit of risk: notify-only is read-class risk with consequential optics — a wrong message is embarrassing, not destructive — and it multiplies the value of every other connector, because governance latency is the real tax on all of them (04 §4). Exercises the first non-git MCP backend. **Worked example:** Jordan's PR-create gate now arrives in Slack with a deep link; median gate-age drops.

**Step 3 — generic MCP registration UX.** Promote what steps 1–2 used internally into the operator-facing advanced flow: register backend → map tools to grant keys → assign risk class and tier → publishable pack. This is where the community extension story starts — a third-party `telephony-twilio` pack installs like a role: data, versioned, signed (03 §1, C-5). **Worked example:** unchanged — which is the point; the docs pod never notices the mechanism generalizing under it.

**Step 4 — cloud observe; deploy explicitly deferred.** Read-only log/metric grants (`http-api` packs) for `platform-pod` / `incident-response-squad` formations, feeding TriageNotes and postmortems — an incident squad diagnosing from real telemetry without anyone pasting logs into a brief. Consequential cloud verbs wait for the trust ladder (`org-roadmap.md` §2, rule 2: consequential external actions come *after* PR-proposing work is boring), and self-deploy is explicitly "not a grant that exists" for self-hosted orgs — the recursion boundary. **Deploy verbs do not appear in this proposal except as this named non-goal.**

Sequencing rationale: each step has a committed consumer (O2 → operator attention → community/O5 → O3's observe needs), and risk class rises one notch per step — read/write-gated → notify → long-tail read → observe — with deploy beyond the horizon.

## 3. Failure modes this design is built to avoid

- **Over-configuration.** Ten decisions per connector means operators stop at one connector or none. Countered by packs as the unit of adoption (decisions made once, by the pack author), role-level defaults so granting is "attach" not "design," exactly one secret in the common case, and verify-at-grant so misconfiguration surfaces in minutes (04 §1–§2).
- **Grant sprawl.** Six months in, nobody knows why a node can touch what. Countered structurally: monotone narrowing guarantees effective ≤ visible; widening is a loud act rendered on the chart; assignment additions expire. Kept *legible* by the Inspector envelope tab and the by-connector cost rollup; kept *bounded* by the one-action kill switch. The property to defend: no grant that doesn't render somewhere an operator already looks (04 §1).
- **Operators bypassing the system.** The E8 lesson (04 §0): the governed path must beat the side-channel on both cost and output quality. The 5-minute bar, reused surfaces, and the automatic provenance/receipt on pack-proposed PRs are what kill the bypass.
- **Teams blocked on approvals.** 04 §4's controls: gate only outward actions, suspend cheaply, deliver gates to Slack, measure gate-age.
- **Silently weakened walls.** A grant's tier floor exceeding what the host provides must refuse loudly, not degrade. Already answered by `TIER_UNSATISFIABLE` (envelope §5); connector grants declare `minSandboxTier` like native ones, and the check surfaces at grant time (04 §1, station 4), not at actuation.

## 4. Open questions (blocking items named, not papered over)

1. **Glob-subset verification.** Precedence rule 5 (02 §4) requires pattern-valued params to narrow to textual subsets; verifying glob-subset relations is real work. This is envelope §9's "grant params vocabulary" question, now load-bearing — it needs a closed param-schema discipline before step 1 ships governed branch patterns.
2. **Is `provides` open or closed?** Should packs only be able to provide abstract families the catalog pre-declares (closed vocabulary, curated), or may a pack introduce a new family? Leaning closed — an uncurated abstract vocabulary re-opens the collision and semantics problems the two-layer rule (01 §4) exists to solve — at the cost of a catalog PR per new family.
3. **Instance lifecycle vs. running actuations.** An edited instance takes effect at next assignment intake, not mid-session (02 §7), mirroring the `runtime_override` re-actuation rule (`cli-runtime.md` §1). The residual question is whether *disable* (the kill switch) should also halt in-flight sessions by default or leave them to finish workspace-local work (03 §4 says: kill switch fails calls closed immediately; session halt is a separate, deliberate lever).
4. **Pack versioning and risk-class migration.** When a pack update changes a grant's `riskClass` or tool surface: version-pin per instance, explicit operator upgrade with a rendered diff (04 §3), re-run readiness. The open part is fleet-scale ergonomics — many orgs pinned across many versions of many packs.

## 5. Where this leaves the pillars

**Safe:** every mitigation double-enforced — once at the proxy, once in the upstream credential's own scope — with credentials write-only and never sandbox-side (03). **Enterprise-ready:** approvals, org-scoped tenancy, append-only audit, deny-by-default policy, honest v1 caveats (04 §3). **Scalable:** packs are data (a new MCP-served system costs zero platform code); instances are per-org rows; the abstract-family layer keeps role catalog and connector ecosystem growing on independent axes (01, 02). **Useful:** the common case is one install, one secret, one verify click, one gate approval — and the migration never makes an install re-answer a settled question (04 §2, 05 §1).
