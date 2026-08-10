# Standing Organizations — UX

**Status:** Implemented (2026-08-08) · **Date:** 2026-08-08 · *Vocabulary + supersession note: see the banner on [standing-orgs.md](standing-orgs.md) — "org" = Team post-C1; complements, not superseded by, `organizations/`. The surfaces below re-root under the portfolio home at C1 (`organizations/05` §1); source health joins the team card's vitals.*
**Reads with:** [standing-orgs.md](standing-orgs.md) (the technical design), `execution/engine.md` §4 (cadences, shipped in E7), [builder-connectors-ux.md](builder-connectors-ux.md) (triggers consume connector instances), `org-roadmap.md` §O3 (the bug-close org this enables).

---

## 1. The one-sentence story

Some work you hand an org once; some work *arrives* — on a schedule, or because something happened outside — and a standing organization is one the operator has wired to receive it: same team, same gates, same meters, no operator in the loop at the moment work begins.

Two sources of arriving work, one mental model:

- **Cadence** — *time* fires it. "Every hour, read the AI feeds and distill what's new." Shipped in E7; this document gives it a home.
- **Trigger** — *an event* fires it. "A bug report labeled `bug` lands in the repo → the maintenance team starts on it." New.

Both produce ordinary intents. Everything downstream — plan review, budgets, deliverables, acceptance — is the machinery the operator already knows. The UX job is to make the *sources* as legible and governable as the work they generate.

## 2. Where it lives: the Standing work section

`/execute` gains a **Standing work** section (replacing the bare Cadences block), two lists under one header:

**Cadences** — as shipped: name, cron (with plain-English echo: "every weekday at 09:00"), target node, last fired, next fire, enable toggle.

**Triggers** — one row per trigger:

- **Source**: the connector instance + filter, stated as a sentence — "New issues labeled `bug` in **canopy repo** (GitHub)". The instance name links to its pill in the builder.
- **Target**: which node receives the intent (default: the org root — the lead triages, exactly as if the operator had typed it).
- **Status**: enabled toggle · last checked · last fired · a small "3 intents this week" count.
- **Actions**: edit · check now (one manual poll, for confidence) · disable.

### 2.1 Creating a trigger

"New trigger" opens a three-step card, deliberately in the operator's language:

1. **When** — pick the event source: a dropdown of the org's connector instances that can emit events (v1: GitHub instances with `issues.read` enabled). Then the filter: labels (chips), state (open), and "issues created after…" (defaults to now — a new trigger never replays history unless asked).
2. **Then** — the intent template, a textarea with placeholders and a live preview rendered against the most recent matching issue: `Fix the bug reported in {{url}}: {{title}}\n\n{{body}}`. Placeholders: `{{title}} {{number}} {{url}} {{body}} {{labels}} {{author}}`.
3. **Guardrails** — target node; per-fire budget note (the intent inherits role salaries as always — restated so nobody wonders); flood control, stated honestly: "at most N new intents per check (default 3); the rest wait their turn."

A **dry run** button lists the issues that *would* fire right now, with the rendered intent for the first — the operator sees exactly what the org would receive before enabling anything.

### 2.2 Provenance on the work itself

Intent chips already mark cadence-fired work with ↻. Trigger-fired intents get ⚡ plus the external key: "⚡ #142". The chip's hover names the trigger and links the source issue URL. In the living plan, the intent header carries the same line. Cost rolls up per source: the Costs view's by-intent table groups cadence- and trigger-born intents under their source's name, so "what does the bug pipeline cost me per week" is a glance, not a query.

### 2.3 Notifications

`trigger-fired` (info): "Trigger 'bug intake' opened intent for issue #142." `trigger-error` (warning, deduped): the poll failed (credential revoked, rate-limited) — surfaced once per failure streak, with the reason, not once per poll. Both ride the existing notification feed and SSE.

## 3. Worked examples

### 3.1 The bug-fix team (event-driven)

The org from [builder-connectors-ux.md](builder-connectors-ux.md) §3 — pod + GitHub instance linked org-wide. The operator adds one trigger: *when* new issues labeled `bug` in `canopy repo` → *then* "Reproduce and fix the bug in {{url}}: {{title}}…" → target: the lead. A bug lands at 03:00; by morning the inbox holds a plan-review gate: the lead has triaged, proposed a fix assignment for the engineer and a verify assignment for QA. The operator approves the batch, later accepts the fix, approves the governed PR — every human touch a gate they already know. The team is "long-running" without a single long-running session: it is *summoned per bug*, remembers via agent memory, and costs nothing between bugs.

### 3.2 The research team (cadence-driven)

A two-node org: an analyst and an editor. One cadence: `0 * * * *`, target the analyst — "Review the AI feeds listed in your instructions; follow links worth following; deliver a distilled note of genuinely novel ideas since the last run, or finish with 'nothing new' if there are none." The analyst's memory carries what it has already seen (dedupe lives in judgment, not machinery); the editor's verify edge gates what reaches the operator; the operator reads a morning digest of accepted notes. No trigger needed — time is the event. This works today on E7 machinery; the UX contribution is the Standing work section making the cadence visible, pausable, and accountable next to its costs.

## 4. Principles this UX commits to

1. **Sources are governable objects, not settings.** They render beside the work they create, carry provenance onto every intent, show costs, and disable in one click.
2. **The moment of autonomy is intake only.** A trigger replaces the operator *typing* the intent — never the plan review, never acceptance, never a governed action. Standing orgs widen when work arrives, not what the org may do.
3. **No replay surprises.** New triggers start from "now"; flood control caps a burst; a paused trigger accumulates nothing it will later dump (events missed while disabled are gone unless the operator lowers the "created after" mark on purpose).
4. **Failures are quiet but visible.** A broken credential is one warning with a cause, not a hundred, and never a silent stop — the row shows "last checked" going stale.

## 5. Out of scope for v1

Webhook ingestion (polling first — `connectors/05` names webhooks as the later step); trigger kinds beyond GitHub issues (PR comments, Slack messages, RSS — the trigger row's *When* dropdown is where they will appear); never-closing **standing intents** with milestone views (`work-model.md` reserves `intent.kind: "standing"`; O3 pulls it — v1 triggers open episodic intents per event, which is the honest shape for per-bug work); cross-org triggers (frontdesk → maintenance handoff, the O7→O3 rehearsal).
