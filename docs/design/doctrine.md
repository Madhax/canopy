# Doctrine — How Purpose Cascades Through the Chart

**Status:** Requirements draft (proposed for adoption) · **Date:** 2026-08-16
**Upstream:** `../mission.md` (the content this mechanism carries), `../domain-model.md` (Organization / Team / Agent / Assignment; invariants 3, 11, 12, 13), `organizations/01-team-and-organization.md` (the administrative Organization this gives a voice), `../execution/cli-runtime.md` §2–§3 (the compiled session context this extends).
**Scope note:** requirements only. This document names the seams it touches but deliberately specifies no schemas, tables, or endpoints.

---

## 0. The problem

In Canopy, everything structural cascades. Reporting lines cascade delegation (`domain-model.md` invariant 4). Budgets cascade from organization ceiling to salary to assignment meter. Grants narrow downward and never widen. But **intent above the team level does not cascade at all.**

The Organization is deliberately administrative — never actuated, no chart, cannot receive an Intent (`organizations/01` §3). That design was right, and the O8 amendment (`../org-roadmap.md` §3) rightly realized the "org of orgs" administratively rather than as a chart nobody needed. But the trade silently dropped the one thing the chart version would have provided: **a shared root context.** Today there is no mechanism by which every team under an Organization knows anything in common. An agent's compiled context contains its role, its assignment, its memory — everything below and beside it, nothing above its team. A fleet of teams standing up under `canopy-inc` would share a budget, a capacity pool, and a portfolio page, and would not share a purpose.

For a mission whose success is defined as one operator governing a fleet (`../mission.md` §3), that gap is not cosmetic. Shared doctrine is what lets the operator's direction be approved *once* and inherited *everywhere*, instead of re-stated per team and drifting per restatement.

## 1. The model

Four levels, one reading order. Each level answers a different question, and an agent's compiled context opens with the chain above it — top first:

| Level | Answers | Carried by | Attached to | Exists today? |
|---|---|---|---|---|
| **Doctrine** | *why does this fleet exist; what binds all of us* | mission + standing commitments | Organization | ❌ — this proposal |
| **Purpose** | *what is this team for, standing* | team charter / standing purpose | Team | partial (standing intent text, team description) |
| **Duty** | *what does this seat do* | role instructions, duty → deliverable | RoleTemplate | ✅ catalog |
| **Task** | *what is asked of me now* | brief (versioned) | Assignment | ✅ |

This mirrors how real organizations propagate direction — mission → mandate → job description → task — and it is "the chart is the system" applied to purpose: the same hierarchy that already routes messages, budgets, and grants routes *why*.

## 2. Requirements

**DR-1 — Doctrine attaches to the Organization.** A single operator-authored prose document (markdown), org-scoped, with no per-team or per-agent variants. For `canopy-inc`, its content is `docs/mission.md` §1–§5 — the mission and the standing commitments. Doctrine is the Organization's only voice: attaching it does not make the Organization actuatable, addressable, or chart-bearing, and it must not erode `organizations/01` §3's restraint.

**DR-2 — Injection is structural, not optional.** Every compiled agent context in every team of the Organization opens with the doctrine, before team purpose, before role instructions, before the brief. No role, formation, or team setting can opt out. Both runtimes see it identically — the charter compilation step is the single shared seam — so a `loop` fixture and a `cli-claude` session inherit the same chain.

**DR-3 — Versioned and stamped.** Doctrine is versioned like a brief (`doctrine@N`); every session records the version it was compiled under, and the record is inspectable wherever briefs are (inspector, engagement audit). "Which doctrine was in force when this decision was made" must be answerable — nothing is done by vibes, including by us.

**DR-4 — Advisory, never enforcement.** Doctrine shapes judgment; grants and gates shape action. No security or governance property may depend on doctrine text: it never widens or narrows a grant, never substitutes for an ApprovalGate, never satisfies a readiness check. The capability surface stays legible from the chart alone (invariant 13) with the doctrine unread. A commitment stated in doctrine (e.g. "agents propose; humans ratify") is *enforced* elsewhere or not at all.

**DR-5 — Changes land at boundaries.** A doctrine edit reaches running sessions the way notes do: at the next turn or session boundary, without suspending anything. No mid-turn injection, no fleet-wide restart. Teams actuated at the time of an edit converge on the new version as their sessions naturally cycle; the stamp (DR-3) makes the convergence observable.

**DR-6 — Exports stay portable.** Team documents deliberately do not carry organization membership (`organizations/01` §8, decision 4); doctrine likewise remains server-side organization state joined at compile time. A exported `canopy.team` document contains no doctrine text; an imported team acquires the doctrine of whatever Organization it lands in. Doctrine describes the *house*, not the *team*.

**DR-7 — The team-level slot is purpose, not policy.** The cascade's second level is the team's standing purpose — one operator-authored paragraph ("close the documentation backlog of the Canopy repo, PR by PR"), distinct from any standing intent's operational text and from the team description's display role. Formalizing this slot is in scope for the cascade; loading it with per-team rule-books is not — rules that bind everyone belong in doctrine, rules that bind conduct belong in role instructions, and anything enforcement-shaped belongs in grants and gates (DR-4).

**DR-8 — Legible to the operator.** The Organization's page shows its doctrine and version history; the agent inspector shows the doctrine version a session ran under; plan review and acceptance surfaces can cite doctrine deltas ("planned under doctrine@3; current is @4") so stale-doctrine work is visible at the moments the operator is already judging it.

**DR-9 — Sized for the context it rides in.** Doctrine is a stable prefix in every session of every agent in the fleet — cache-friendly by construction, but paid for in context window by everyone. The requirement is a discipline, not a limit: doctrine carries what binds *everyone* (mission, standing commitments) and nothing that binds only some (role conduct, team procedure, task detail). As a working bar: if a paragraph would change any specific agent's next action, it belongs at a lower level.

## 3. Non-goals

- **Per-agent doctrine overrides.** Agent extensions and standing directives (X4) already exist for narrower scopes; doctrine is what does *not* vary.
- **Cross-organization doctrine.** Invariant 12 stands; two Organizations share nothing, including purpose. An operator who wants shared doctrine across orgs copies it — deliberately.
- **A policy engine.** Doctrine is prose for judgment, not a rules DSL, not evaluable conditions, not configuration. The moment doctrine text is parsed by machinery rather than read by a model, DR-4 has been violated somewhere.
- **Enforcement.** Stated throughout; restated here because it is the failure mode most likely to creep.

## 4. Open questions

1. **Does doctrine bind the operator's own intents?** Proposed: yes as display (the intent console shows the doctrine the receiving team runs under), no as constraint — the operator outranks the document they authored.
2. **Doctrine for the doctrine.** Editing doctrine is itself direction-approval (`../mission.md` §3, duty 1). Should a doctrine edit require an explicit self-owned ApprovalGate so the ratification is on the record, or is the edit itself the record? Leaning: the edit is the record (DR-3 stamps it); an approval ceremony of one is theater.
3. **Convergence pressure on long-lived sessions.** DR-5's next-boundary rule is clearly right for ordinary work; is it sufficient for a team mid-way through a large engagement when a *commitment* (not just emphasis) changes? Possible answer: a doctrine edit may optionally open an advisory note to all active teams — reusing the existing note machinery, no new mechanism.
4. **Where the purpose slot (DR-7) lives in the document model** — team document field vs. server-side state like membership. Portability (DR-6) argues server-side; "the chart is legible alone" argues in-document. Undecided; the cascade works either way.

## 5. Adoption shape (informative)

Smallest honest increment: (1) doctrine text + version on the Organization, surfaced on its page; (2) charter compilation prepends it; (3) session stamp in the inspector. DR-7's purpose slot and DR-8's delta citations can follow. Nothing here blocks or reorders the existing roadmap; the named customer is `canopy-inc` standing up its first teams under a shared mission (`../org-roadmap.md`).
