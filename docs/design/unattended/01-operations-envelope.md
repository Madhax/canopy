# 01 · The Operations Envelope — bounded standing consent for a running team

> **Status:** Proposed 2026-08-16 · **Reads with:** `README.md`, `../../domain-model.md` (gates, meters, invariants 7–9), `../../manager-responsibilities.md` (X3 governed transitions, X4 standing directives), `../experiments/03-search-and-iteration.md` §5 (the pattern generalized), `../../canopy-inc.md` §2 P2/P4

## 0. The problem

Every suspension in Canopy is a gate, and every gate an agent cannot resolve routes to the operator. That is correct governance and a fatal flow model for a daily-check-in fleet: staged plan review (X3, default-on for root assignments) blocks each new engagement within minutes of intake; a budget hard-stop parks an assignment until a human tops it up; a clarification the operator has answered ten times waits to be answered an eleventh. The lab already solved this shape for experiments — the **envelope**: a pre-approved space inside which the machinery proceeds without asking, with prospective gates only at its edges. Production teams need the same instrument, pointed at operations instead of search.

**The rule that keeps it honest: the envelope automates the operator's predictable *answers*, never the operator's *authority*.** It may dispatch bounded plans and fund bounded top-ups — spending tokens inside the walls is pre-consequence work. It may never accept a deliverable, resolve a governed action, widen a grant, change a chart, or speak outward. The two approvals (`mission.md` §3) are untouched by construction.

## 1. The object

One envelope per team, operator-authored, versioned append-only (the rubric pattern), displayed on the team page, consulted by the engine at gate-opening time:

```jsonc
// table: team_ops_envelope   (team_id, version) — versions append-only
{
  "teamId": "tm_…", "version": 3,
  "planReview": {
    "mode": "graduated",                  // always | graduated | auto
    "autoApprove": {                      // consulted only in graduated/auto modes
      "provenance": ["cadence:*", "trigger:tr_docs1"],   // operator intents NEVER auto-dispatch by default
      "maxChildren": 5,
      "maxBatchAllowanceTokens": 300000,  // Σ proposed allowances per batch
      "requireDeclaredContracts": true    // every draft names a contract type the role declares
    }
  },
  "budget": {
    "autoTopUp": { "maxPerAssignment": 1, "factorCap": 1.5 },
    "onRefused": "park"                   // park | fail
  },
  "clarifications": {
    "directives": ["dir_a1", "dir_b2"],   // X4 standing directives consulted as auto-answers
    "unmatched": "park"                   // park | fail — the envelope never guesses
  },
  "escalations": { "unmatched": "park" },
  "reviewLatencyBudgetH": 24,             // parked longer than this ⇒ anomaly in the brief
  "graduation": {                         // §4 — nomination criteria, mechanical only
    "window": "30d",
    "criteria": { "batchesApprovedUnedited": 20, "rejectionRate": 0.1, "guardrailBreaches": 0 },
    "proposes": { "planReview.mode": "auto", "budget.autoTopUp.maxPerAssignment": 2 }
  },
  "createdBy": "operator", "createdAt": "…"
}
```

## 2. Requirements

**OE-1 — Consultation, not construction.** The engine consults the envelope at exactly the moments it would otherwise open an operator-owned gate: staged-batch approval, budget intervention (warn/hard-stop), clarification/escalation targeting the operator. The envelope returns one of `resolve(payload)` / `park` / `route` (normal needs-you). It introduces no new gate kinds and no new work semantics.

**OE-2 — Every predicate is mechanical.** Auto-approval conditions are framework facts only — provenance class, child count, allowance sums, declared contract types, directive key matches. No LLM evaluates an envelope condition (the X2 rule: Goodhart-proof by construction). Anything a predicate cannot decide routes or parks.

**OE-3 — Auto-dispatch is scoped to machine-born intents.** Default `provenance` never includes `operator` — an intent you typed is one you expect to steer, and its plan review stays yours unless you explicitly opt it in. Cadence- and trigger-born intents are where auto-dispatch earns its keep.

**OE-4 — Auto-top-up is bounded and funded honestly.** At most `maxPerAssignment` top-ups, each capped so total funding ≤ `factorCap` × original allowance; funded only if the org's weekly ceiling admits it (the admission check runs as if this were new work); recorded as the standard meter-transfer SpendEvent with `resolved_by: envelope@v3`. Refusal follows `onRefused` — default parks the gate, releasing the node.

**OE-5 — Every envelope action is a first-class, attributed resolution.** `resolved_by: envelope@vN` on the gate resolution, an activity row, and a line in the brief's digest. The envelope is a policy the operator can audit, diff across versions, and revert — never an invisible hand.

**OE-6 — The envelope never touches consequence or acceptance.** Governed actions (merge, PR-create, publish, outward speech) and root-deliverable acceptance are excluded *by class*, not by configuration — there is no envelope field that could express them. Manager-level acceptance inside the team is untouched (that is D4's knob, a different instrument).

**OE-7 — Park is a designed state.** A parked gate stays open, tagged `parked` with a reason code, releases the node's WIP slot (existing `gated` semantics), surfaces in the brief's Parked section, and flags as an anomaly when older than `reviewLatencyBudgetH`. Nothing parked pages.

**OE-8 — Modes are a ladder.** `always` (every batch reviewed — the founding posture), `graduated` (auto within `autoApprove`, review outside it), `auto` (review only outside bounds). New teams are born `always`; `canopy-inc.md` §6's wave gates require specific modes (`06-readiness-and-soak.md`).

## 3. Interaction with standing directives (X4)

Directives are the envelope's answer bank: a clarification whose subject matches a registered directive's scope resolves with the directive's text as the answer, attributed to `envelope@vN → dir_a1`, brief-logged. Unmatched clarifications park (never guess — a wrong guess costs more than a day's latency). This finally gives X4 its unattended payoff: the operator teaches an answer once, in a directive, instead of re-answering at every check-in.

## 4. Graduation — the envelope nominates, the operator ratifies

When the mechanical criteria hold over the window, the platform raises a **`graduation-suggested`** card in the brief: the proposed envelope vN+1 as a diff, with the evidence attached (batches, edit rate, breaches — receipts-store queries). Ratifying creates the new version; declining records why. **The envelope never loosens itself** — the promotion pattern (`../experiments/05` §3), applied to autonomy. Tightening, by contrast, is instant and unilateral: the operator (or a `canopy-forge` proposal) can drop a team to `always` at any moment, and guardrail breaches auto-tighten — any `clean-hands` violation or recursion-boundary attempt drops the team's envelope to `always` immediately, receipted, page-classed (`02` §4).

## 5. Non-goals

Per-agent envelopes (team-level only; roles and salaries already differentiate agents); envelope-editable capacity knobs (the schedule owns those, `../organizations/04`); LLM-judged conditions (OE-2); auto-acceptance of any deliverable at any level above the manager's existing D4 policy; cross-team or org-level envelopes (each team earns its own trust; an org-wide loosening is exactly the kind of decision that should hurt a little).

## 6. Open questions

1. Should `reviewLatencyBudgetH` differentiate gate kinds (clarifications age worse than top-ups)? Leaning yes, later — one number first.
2. Envelope templates in the catalog (a `docs-pod` ships with a suggested envelope)? Attractive; deferred until three teams' envelopes exist to generalize from.
3. Does a directive-resolved clarification count toward graduation evidence? Leaning yes — it is an operator answer, pre-recorded.
