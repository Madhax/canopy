# 04 — Operations: The Operator's Chair

**Series:** [Connector Governance](README.md) · **Prev:** [03-security.md](03-security.md) · **Next:** [05-adoption.md](05-adoption.md)

The governing test for everything in this document: **the common case is a pack, not a form.** If registering a connector is harder than doing the side-channel manually, the side-channel wins forever and audit silently loses coverage — E8 is the cautionary tale in our own repo (`docs/execution/e8-runbook.md`: the operator hand-pasting issues in and hand-pushing branches out). The governed path must be both cheaper *and* produce the better artifact: a PR proposed through the pack carries its provenance chain and cost receipt automatically; the hand-pushed branch never will.

## 1. The operator journey — six stations

Each station names its 5-minute/advanced line. The journey reuses Operate surfaces the operator has already accepted (Secret Store, Inbox gates, ToolEvents, Inspector) — connectors grow no console of their own.

1. **Discover.** Packs are catalog content, browsed where organizationTypes and roles already are — and packs declare which roles they extend, so discovery is *"the docs pod suggests the GitHub pack,"* surfaced on the role, not a directory search. *5-minute.*
2. **Configure.** Two things only: a connection (repo slug or backend endpoint) and a credential, into the Secret Store under invariant 10 — never into the chart, never into `canopy.toml`. The pack ships pre-scoped params (`branchPattern: canopy/*`, `targetBranch: main` governed), so the operator supplies exactly one secret and zero scoping decisions. *5-minute for one repo + one token; multi-instance, org-scoped credential separation, and custom MCP registration are advanced.*
3. **Grant.** Attach in the editor at the role (default), narrow per node, or add per assignment (expires with it). The monotone-narrowing rule (02 §4) is the ergonomic load-bearer: attaching a pack can never silently widen a node beyond what the chart shows, so the operator doesn't need to audit before granting. *5-minute: accept the pack's role-level defaults; per-node narrowing is the advanced path.*
4. **Verify.** The missing station in the current docs, and the one genuinely new UX surface this series requires. One click, "test this grant": the proxy makes a real read-class call (list branches, post to a test channel) and shows the ToolEvent. This is also where `TIER_UNSATISFIABLE` and the connector readiness checks (02 §5) surface — at grant time, with "install the provider or strip the grant" as the two buttons — not at actuation, and never mid-assignment. *Must be 5-minute; today it is nothing.*
5. **Monitor.** Already designed: Inspector Overview shows the envelope's grants; the Session tab shows tool calls; every proxy call emits a ToolEvent; governed actions land in the Inbox. Cost explorer learns a by-connector rollup. *Free, provided connectors reuse these surfaces.* The design property to defend: **there is no grant that doesn't render somewhere an operator already looks.**
6. **Revoke.** Two speeds: remove a grant from role/node (chart edit, next call at the proxy, next intake for the session surface), and **disable the instance** — the kill switch; every dependent grant 403s immediately (03 §4). Credential rotation is a Secret Store swap; grants reference the secret id, so nothing else changes. *The kill switch must be 5-minute and panic-proof.*

## 2. Defaults — the worked example from the operator's chair

Jordan operates a Canopy install and wants the `canopy-docs` team to read the Canopy repository, draft a proposal, and submit it as a PR. Today, post-E8, Jordan does the GitHub half by hand. With the O2 pack:

1. **Discover.** In the editor, the docs pod's `tech-writer` node lists its grants (`workspace.rw`, `repo.read`, `docs.repo.write`) and — because the pack declares its target roles — suggests: *"GitHub pack available for this role."*
2. **Configure.** Install: two fields — repo (`Madhax/canopy`) and a token, stored to the Secret Store. The dialog states the exact fine-grained-PAT permissions required (Contents: read/write, Pull requests: read/write, Metadata: read; per 03 §3) and echoes which the supplied token actually has — token scoping is the single most likely abandonment point in the whole journey. It also answers the identity question up front: a bot identity opens PRs; Jordan's merge click is the human act.
3. **Grant.** The pack proposes defaults: `tech-writer` keeps its existing keys (now served by the instance); `engineering-lead` gains `connector.github.pr.create` (governed, gate owner: operator); `editor` unchanged — `repo.read` suffices to review. The outward action sits on the accepting manager (02 §6), so Jordan never faces the "does the writer need the PR grant?" question. Jordan accepts without editing.
4. **Verify.** One click: the proxy lists the repo's branches and open `docs`-labeled issues as a live test; ToolEvent shown. A wrong token fails *here*, attributably — not mid-assignment as a gated, stalled agent, the worst possible place to debug a credential.
5. **Work happens.** Jordan submits the intent ("draft the connector proposal and submit it as a PR"), plan-reviews the fan-out, and watches the tree. The writer drafts on a `canopy/docs/as_…` branch in its materialized worktree (02 §7 Mode B); the editor reviews behind the dependency gate; the lead accepts and calls `github_create_pull_request`.
6. **Gate.** Inbox, top section: *"PR-create: 'connector proposal' → Madhax/canopy — diff, cost-so-far, provenance."* Jordan approves inline; the proxy — as MCP client, holding the only credential — pushes the branch and opens the PR. Approval clearly means "open the PR," not "merge it": merge stays a separate human act on GitHub, per the recursion boundary.
7. **Aftermath.** The deliverable card carries the PR URL and the cost receipt; the ledger gets its benchmark row (cost per PR — O2's published metric). Rotating the token is a Secret Store swap; disabling the instance is the kill switch; the chart changes for neither.

Total operator touch: one install, one token, one verify click, one gate approval — under ten minutes of attention, and every outward effect passed a gate Jordan owns.

## 3. Approval workflows and enterprise controls

What a skeptical platform team signs off before enabling connectors — each item with its enforcement point (03's vocabulary):

- **Approval workflow.** Registering an instance is an operator/admin act behind an approval (**server**) showing endpoint, credential fingerprint, org binding, pinned tool surface. Pack imports are approval-gated with a rendered diff of every grant's `riskClass`, `governedActions`, executor, and params (03 §1, C-5) — imported risk assignments are advisory until confirmed. Grant-to-role attachment is catalog data: reviewable, diffable, versioned (**catalog**). Governed actions get per-invocation ApprovalGates (**server**; invariant 9).
- **Tenancy isolation.** One instance and one credential **per org**, no exceptions (03 §1, C-3): per-org Secret Store bindings; actuation refuses cross-org credential references; one upstream server process/connection per org, no shared warm state. Stated honestly: v1 shares one control-plane process and DB across orgs (`threat-model.md` non-defense) — per-org *credential* isolation is real now; per-org *process* isolation lands with the hosting preconditions (`threat-model.md` "preconditions to relax").
- **Audit logging.** Every invocation → ToolEvent with instance id, upstream request id, intent id (03 §5); server-side records authoritative (`cli-runtime.md` §5); append-only, exportable to the team's SIEM.
- **Policy constraints.** Deny-by-default everywhere: no sandbox has general egress at any tier (envelope §5); web/API reach is proxy-brokered and allowlisted per grant; `--strict-mcp-config` guarantees exactly one MCP mount (`cli-runtime.md` §2); org-level deny lists (repos, channels, methods) override any grant (**server**). A capability not granted is *absent*, not forbidden (envelope §2).
- **Compliance posture.** Who approved what, when: gate resolutions, actuation events, secret create/rotate metadata, pack-import approvals — timestamped, attributed, queryable (**server**). Readiness checks (envelope §5 plus 02 §5's connector set) refuse actuation rather than degrade silently — misconfiguration is loud, before any agent runs.
- **Blast-radius statement.** 03 §5's closing sentence, verbatim, as the sign-off criterion.

## 4. Approval latency — the adoption killer, managed

The failure mode: the org drafts a PR in 40 minutes and waits 9 hours for a human click, meter open the whole time. The controls, all grounded in existing machinery:

- **Granularity.** Gate the outward action (PR-create, message-send, merge) — never the read. The pack's risk assignments encode this; nothing read-class is governed.
- **Cheap suspension.** A gated assignment is a suspended conversation (`claude --resume`, `cli-runtime.md` §1), not a burning session — waiting costs nothing but latency.
- **Severity discipline.** `attention` strictly means "blocked on you"; the badge never cries wolf. Bulk-approve exists for low-stakes classes.
- **Delivery.** The Slack notify pack (05 §2, step 2) exists substantially to deliver the gate itself — the ask reaches the operator where they live, with a deep link to inline resolution. Governance latency is the real tax on every connector; this pack pays it down for all of them.
- **Measurement.** Gate-age is visible on the plan timeline — approval latency is a measured number the operator sees, not a vibe. Optional later: manager-bounded auto-resolution for the lowest-stakes classes, bounds shown in the digest.
