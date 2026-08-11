# Standing Organizations — Design

**Status:** Implemented (2026-08-08, with `builder-connectors.md`) · **Date:** 2026-08-08

> **Vocabulary note (2026-08-09).** "Org" below means the actuatable chart — a **Team** after the `organizations/` series' rename (C1); a "standing organization" is a *Team with work sources*, unrelated to the new Organization entity. **Not superseded** by `organizations/`: that series governs *capacity and grouping*, this one governs *work arrival* — they compose. The composition is load-bearing in one direction: trigger-fed teams run unattended, and unattended operation requires the C-series' capacity governance before it is allowed on a cadence (`../../org-roadmap.md` §2 rule 5; scheduler admission applies to trigger-born intents like any other).
**Reads with:** [standing-orgs-ux.md](standing-orgs-ux.md) (the UX), `engine/cadence.py` + `execution/engine.md` §4 (the E7 machinery this mirrors), [builder-connectors.md](builder-connectors.md) (the event source), `work-model.md` (intents), `org-roadmap.md` §O2–O3 (the consumers).

---

## 1. Position: a standing org is sources + a team, not a new runtime

The long-running organization needs no new execution model. Agents are already summoned per assignment, remember via `agent_memory`, and cost nothing idle. What "long-running" adds is **work sources** — control-plane objects that open intents without the operator typing them:

| Source | Fires on | Shipped | v1 work |
|---|---|---|---|
| **Cadence** | cron time (UTC) | E7 (`work_cadence`, 30 s loop, consume-on-due misfire policy) | UX home only |
| **Trigger** | external event, observed by polling a connector | — | this document |

Both open **episodic** intents — one per firing, one per event. `IntentKind` already reserves `"standing"` (never-closing intents with milestone projections); that stays reserved for O3, and nothing below forecloses it. Per-event episodic intents are the *correct* shape for the bug pipeline: each bug gets its own meter, plan, acceptance, and receipt.

## 2. The trigger model

```sql
CREATE TABLE work_trigger (
    id               TEXT PRIMARY KEY,      -- tr_…
    org_id           TEXT NOT NULL,
    name             TEXT NOT NULL,
    kind             TEXT NOT NULL,         -- 'github-issues' (v1's only kind)
    node_id          TEXT NOT NULL,         -- intent target (default: root)
    instance_id      TEXT NOT NULL,         -- the connector instance polled
    config           TEXT NOT NULL,         -- JSON {labels: [], state: 'open', createdAfter: iso}
    intent_template  TEXT NOT NULL,         -- {{title}} {{number}} {{url}} {{body}} {{labels}} {{author}}
    enabled          INTEGER NOT NULL DEFAULT 1,
    cursor           TEXT,                  -- JSON {since: iso}: advances only on successful pass
    last_checked_at  TEXT, last_fired_at TEXT, last_error TEXT,
    created_at       TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE work_trigger_fire (            -- exactly-once per external event
    trigger_id   TEXT NOT NULL,
    external_key TEXT NOT NULL,             -- 'issue:142'
    intent_id    TEXT NOT NULL,
    fired_at     TEXT NOT NULL,
    PRIMARY KEY (trigger_id, external_key)
);
```

`work_trigger_fire` is the idempotency ledger — the Paperclip pattern the bus already uses. The cursor is an *optimization* (narrow the poll window); the fire table is the *guarantee* (an issue fires at most one intent per trigger, ever, regardless of cursor resets, restarts, or overlapping polls).

## 3. The poll loop

`TriggerScheduler.run_once()` on a 60 s lifespan loop (`work.trigger_poll_seconds`, same pattern as `_cadence_loop`, per-trigger try so one broken trigger never starves the rest):

1. Skip unless trigger enabled **and** org actuation is `live`/`degraded` (an event arriving while down is *not consumed* — unlike cadence occurrences, events are durable upstream; the next successful poll picks the issue up because the cursor only advances on success).
2. Resolve the instance; list issues via the connector client: `state`, `labels`, `since = cursor.since − overlap` (5 min overlap; dedupe absorbs it), newest-first, capped.
3. For each candidate not in `work_trigger_fire`, oldest-first, up to `maxPerPass` (default 3): render the template (straight substitution, no expression language), `submit_intent(created_by="trigger", trigger_id=…, external_key=…)` — creator maps to `issued_by="operator"` exactly as cadence does, so every downstream gate routes to the operator inbox. Insert the fire row **in the same transaction** as the intent. Notify `trigger-fired`.
4. On full success: cursor ← newest `updated_at` seen, `last_error` cleared. On connector failure: `last_error` set, `trigger-error` notification (deduped on the error string), cursor untouched.

Flood behavior after downtime or a label backfill: candidates drain at `maxPerPass` per minute, oldest first — bounded intake, no drops, no thundering herd of fifty simultaneous plan reviews.

**Intent linkage:** `work_intent` gains nullable `trigger_id` + `external_key` (the ⚡ provenance; the migration is additive). The plan aggregate and intent list carry both; costs group by source name client-side.

## 4. API

`routes/work.py` additions, mirroring cadence CRUD:

- `GET|POST /teams/{id}/triggers`; `PUT|DELETE /teams/{id}/triggers/{tid}` — validation: kind known, node in chart, instance exists + enabled + serves `issues.read` (else `BAD_TRIGGER_SOURCE`), template placeholders ∈ vocabulary (`BAD_TEMPLATE`).
- `POST /teams/{id}/triggers/{tid}/check` — one synchronous pass for this trigger (the *check now* button); returns `{fired: [...], candidates: n}`.
- `POST /teams/{id}/triggers/{tid}/dry-run` — the poll without firing: candidate list + rendered template for the first. No cursor movement, no fire rows.

Events: `trigger.created|updated|deleted|fired|error` on the activity feed; SSE invalidation family `^trigger\.` (the events.ts pattern).

## 5. What cadence already answers (and this reuses verbatim)

Creator plumbing (`created_by` → operator-routed gates), the misfire *logging* discipline (`trigger.skipped` with reasons), the lifespan-loop shape, notification dedupe keys, the ↻/⚡ chip pattern, and the UI section scaffolding (`CadenceSection` generalizes to `StandingWorkSection` hosting both lists). The one deliberate divergence: cadences **consume** missed occurrences (time is not durable); triggers **never consume** unfired events (issues are durable) — stated in both docs because it is the design decision most likely to be "simplified" away later.

## 6. Failure modes, answered

- **Credential revoked mid-flight** → poll fails, one deduped warning, cursor frozen; re-verify on the instance panel; next poll resumes where it stopped.
- **Restart / crash between intent and fire-row?** Impossible by construction — same transaction.
- **Trigger deleted with intents open** → intents live on (they are ordinary intents); fire ledger rows cascade-delete with the trigger; re-creating the trigger with an earlier `createdAfter` may re-fire old issues — documented on the delete confirm.
- **Two triggers matching one issue** → two intents, by design (different templates/targets are different work); the UX shows both chips carrying the same #key so the operator sees the overlap.
- **Rate limits** → the client honors `Retry-After`/backoff headers as an ordinary poll failure; with the 60 s loop and conditional requests the steady-state budget is ~1 request/min/trigger.

## 7. Invariants (normative, testable)

1. At most one intent per (trigger, external event), across restarts, cursor edits, and concurrent passes.
2. No event is lost while a trigger is enabled: cursor advances only on success; the fire ledger, not the cursor, is the correctness boundary.
3. Trigger-born work is downstream-indistinguishable from operator work except for provenance fields — same gates, same owner routing, same meters.
4. A disabled trigger does nothing and accumulates nothing; enabling it resumes from its `createdAfter`/cursor marks, never from history, unless the operator moves the mark.
5. The loop is stateless between passes; a control-plane restart resumes with zero replays and zero drops.
6. CI exercises the full path (poll → dedupe → intent → provenance) against the mock GitHub transport with zero network.

## 8. Test plan

Golden vectors: first poll fires oldest-first capped; second poll no-ops on the same issues; cursor frozen on failure then resumes; not-actuated pass consumes nothing; same-transaction atomicity (crash injection between submit and insert must be unrepresentable — assert single-transaction shape); template rendering incl. missing-field degradation; `BAD_TRIGGER_SOURCE`/`BAD_TEMPLATE` rejections; check-now and dry-run semantics; SSE/notification emission; UI component tests for the section, creation card preview, and ⚡ chips.
