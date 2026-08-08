# Connector Governance — Proposal Series

**Status:** Proposal · **Date:** 2026-08-06
**Produced by:** the connector-governance working group (synthesis of the technical-model, usefulness, and security analyses)
**Upstream:** `../../actuation/agent-envelope.md` (grants §3, Tool Proxy §3.4, MCP executor §3.6, tiers §5), `../../execution/cli-runtime.md` (compiled session config §2, canopy MCP server §4), `../../org-roadmap.md` (O2 — the immediate consumer), `../../actuation/threat-model.md`, `../../../catalog/catalog.json` (`toolGrants[]`, `roles[].toolGrants`).

## The question

How is an external connector — GitHub, Slack, a cloud service, an arbitrary MCP server — **declared**, how is access to it **scoped** per organization, per role, and per node, and how does an operator safely put it in a team's hands?

## The answer, in one paragraph

A connector is not a new mechanism. It is a **connector pack** — a distributable bundle of curated ToolGrants (envelope §3.6's "grant packs distribute like the rest of the catalog," given a schema) — plus a per-org **ConnectorInstance** that carries config and credential bindings (the §3.6 registered backend, promoted to a named domain object). Roles keep granting capabilities by key exactly as today; orgs bind keys to instances; nodes narrow; and the Tool Proxy plus the compiled CLI session config remain the only enforcement paths. Nothing in this series bypasses an existing wall; every new object is an extension of one already designed.

## Reading order

| Doc | Answers |
|---|---|
| [01-connector-model.md](01-connector-model.md) | How a connector is **declared**: the pack manifest, connector kinds, capability namespaces, and the relation to `catalog.json` `toolGrants[]` |
| [02-scoping-and-grants.md](02-scoping-and-grants.md) | How access is **scoped**: the org / role / node three-level model, precedence and narrowing rules, and actuation-time resolution to instance + credential + config |
| [03-security.md](03-security.md) | Why it is **safe**: the threat-model delta, write-only secret custody, least-privilege credential mappings, revocation semantics, and the audit trail |
| [04-operations.md](04-operations.md) | How an operator **runs** it: configure → grant → verify → monitor → revoke, approval workflows, enterprise controls, tenancy isolation, defaults |
| [05-adoption.md](05-adoption.md) | How we **get there**: migration from the global `[repo] source`, the O2 GitHub pack as the first increment, the sequence for Slack / MCP / cloud, and open questions |

## The worked example, carried end to end

Every document walks the same scenario through its own slice: **an operator gives the `canopy-docs` team access to the Canopy GitHub repository so the team can draft a design proposal and submit it as a pull request.** This is O2's exact shape (`org-roadmap.md` §O2): `tech-writer` + `editor` under an `engineering-lead`, drafting on `canopy/*` branches, with every public PR an ApprovalGate owned by the operator. Doc 01 shows the pack that declares the capability; doc 02 shows the instance, the role grants, and the resolved bindings; doc 03 shows the credential's path and the audit trail of one PR; doc 04 shows the operator's ten minutes of actual work; doc 05 shows why this is the first shippable increment.

## The four pillars

- **Safe.** Threat-modeled as a delta against `threat-model.md` (03 §1); credentials write-only and proxy-held, never sandbox-side (03 §2); least-privilege upstream credentials that double-enforce every grant ceiling (03 §3); revocation from next-call to upstream-independent (03 §4); every invocation a ToolEvent (03 §5).
- **Enterprise-ready.** Approval-gated instance registration and pack import with rendered risk diffs, per-invocation gates on governed actions, org-scoped tenancy for instances and credentials, append-only exportable audit, deny-by-default policy (04 §3–§4).
- **Scalable.** Packs are versioned catalog data — a new MCP-served system costs zero platform code; instances are per-org operator data, editable at runtime; the abstract-capability layer keeps the role catalog connector-agnostic, so catalog growth and connector growth are independent axes (01 §4, 02 §5).
- **Useful.** The common case is a pack, not a form: one install, one secret, one verify click, one gate approval (04 §2); verify-at-grant surfaces misconfiguration in minutes, not mid-assignment; adoption never makes an existing install re-answer a settled question (05 §1).

## Scope

Docs-only design proposal. It specifies catalog schema extensions, one new control-plane object, new readiness checks, and operator workflows — it changes no code and commits no implementation sequencing beyond what `org-roadmap.md` already orders. Deploy-class cloud verbs are a named non-goal (05 §3).
