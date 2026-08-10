# 03 — How work flows

*From one typed sentence to reviewed, costed results: intents, assignments, plans,
budgets, gates, and the engine that keeps the whole thing honest.*

Our running example continues. The pod from [doc 02](02-the-team.md) is now
live (how that happens is [doc 04](04-how-agents-run.md)). The operator types:
*"Add CSV export to the report endpoints of target-app; all tests must pass."* — that
is, add a download-as-CSV option to the reporting part of the practice web service.

## The engine: one office manager, one whiteboard

Before the nouns, the referee. The **execution engine** is the central coordinator
inside Canopy's server. Think of it as the office manager who owns the master
whiteboard: workers never change official records themselves. They *report* ("I
finished planning," "here's my deliverable") or *request* ("give this subtask to my
report"), and the engine validates each message and updates the single source of
truth. Every request arrives signed with the worker's own **run token** (its
revocable pass-card — see [doc 04](04-how-agents-run.md)), so a worker can
only act on its own task. No worker can promote its own work to "done," skip the
funding step, or touch another's records — the moves simply don't exist for it.

## Intents: what you actually asked for

An **intent** is the operator's request, addressed to one agent (usually the root).
It is the anchor of the whole paper trail: every task and every spend event traces
back to exactly one intent. Intents come in two kinds: **episodic** (a bounded ask,
like our CSV export — it finishes) and **standing** (an open-ended goal that *is* the
team's mission, like "keep the docs accurate").

There are also **cadences** — schedules ("every Monday, compile a status report")
that automatically fire a fresh intent at each occurrence, skipping a beat if the
previous run is still open.

## Assignments and briefs

An **assignment** is one unit of delegated work binding four things: a worker, a
**brief** (the written instructions), a deliverable contract (what "done" looks
like), and a budget. Assignments form a family tree under the intent: the root
assignment goes to the lead; the lead's delegations create child assignments; and so
on down. That tree is how the system answers, for any worker at any moment, "why is
this agent doing this?" — you walk up the chain to your original sentence.

Briefs are **versioned**. If a manager rewrites the instructions after work started,
that's brief version 2 — and the version history decides who pays for redone work
(see "Who pays for rework," below).

The **deliverable contract** declares the *type* of output that will be accepted — "a
PullRequest" (a **pull request** is a packaged, proposed code change a reviewer can
examine and accept), "a TestReport" — and nothing else counts as done. Contracts are
per role: in our pod, the engineer's contract is a code change, QA's is a test report.
A QA agent that "helpfully" fixes the code instead of reporting on it has not
delivered — its output is literally not acceptable under its contract.

## Delegation — and why nothing is funded until you look

The lead receives the root assignment, checks the brief is feasible, and decomposes:
one child assignment per engineer ("implement CSV export," contract: PullRequest),
and one for QA ("verify it," contract: TestReport) that *depends on* the engineers'
work via a verify link ([doc 02](02-the-team.md)).

The engine checks every delegation against the org chart — a manager may delegate
only to its own direct reports; anything else is refused.

Then the design's most operator-protective idea, **staged delegation**: when a
plan-review checkpoint is on (the default for top-level work), the lead's delegations
are not dispatched. They are buffered as unfunded **drafts** — real subtasks with
real proposed briefs, contracts, dependencies, and budgets, holding no money. The
operator reviews the actual batch, may edit it, and approves or denies. Approval
funds and dispatches everything atomically (all together, or not at all); denial
cancels it outright. An AI middle
manager can therefore mis-scope or over-budget all it likes — nothing moves until a
human has seen the real plan. (An earlier version of this design would have had you
approve a prose summary while the real subtasks dispatched unreviewed; a pre-build
review caught it, and the fix — approve the actual drafts — is recorded in the
amendments log.)

**Our running example:** the operator sees two drafts — engineer (200,000-token
allowance), QA (120,000, born waiting on the engineer) — and approves. Money moves;
the engineer starts; QA's task opens directly into a waiting state, a padlock on the
chart, burning nothing.

## Plans and steps: visible work, metered work

A worker doesn't just silently toil. It declares a **plan** — an observable to-do
list for its assignment, broken into **stages** with completion signals, with a
cursor showing where it is. Plan revisions are versioned, not silent.

As it executes, every atomic action is recorded as a **step**: one AI exchange or
tool action, with its token counts, duration, and a "what changed" label — the
**delta taxonomy**: *produced a file / used a tool / advanced the plan / sent a
message / nothing*. That last label, "nothing," is the mechanical early-warning sign
of a worker spinning its wheels. Cost and progress drill down cleanly: intent →
assignment → plan → stage → step.

## Budgets: the meter, the warning, the hard stop

Every assignment carries a **meter**: an allowance (funded from the role's salary), a
running spent figure, a warning threshold (default 80%), and a hard stop at 100%.
The enforcement is mechanical, and it belongs to the platform, not the worker:

- At 80%: an amber warning. Work continues.
- At 100%: the work is halted — the worker's session is stopped at the next safe
  boundary — and an **intervention gate** opens for a decision: top up, redirect,
  reassign, or cancel. A halted worker's conversation is suspended, not lost;
  resuming continues exactly where it stopped.
- One bounded automation: a manager may top up a report's exhausted meter by 20%,
  once per assignment, without waking you. Anything beyond routes upward.

One honest caveat: in the current runtime design, budget checks land *between*
conversational turns, so a single turn can overshoot the line before the brake
engages — a slightly coarse brake pedal, recorded as a known debt (E-D1). See
[doc 05](05-keeping-it-safe-and-on-track.md).

## Gates: the one way work ever pauses

Anything that legitimately pauses work is a **gate** — one uniform mechanism, no
special cases. A gated assignment is suspended: the worker is genuinely idle (no
session, no spend) and free to work other queued tasks. Exactly five kinds:

1. **Clarification** — "these instructions are defective." Raised by the worker at
   intake *instead of guessing*; resolved by a revised brief (or cancellation).
2. **Dependency** — "waiting on someone else's output." Resolves mechanically by the
   link's policy: *consume* links wait for acceptance; *verify* links resolve at
   submission, because the checker's report is what acceptance should be informed by.
3. **Approval** — "this action has real-world consequences; I need consent first"
   (merge to the main line, contact a customer, spend beyond an allowance). Denial is
   a prohibition to plan around, never a request to redo.
4. **Escalation** — "this decision is above my pay grade." The manager (or someone
   higher) answers; the answer is injected into the resumed work. Asking is designed
   to be cheaper than guessing.
5. **Intervention** — the brake. Opened automatically by tripwires (budget exhausted;
   a **stall** — no step for ten minutes, or five consecutive "nothing changed"
   steps) or by human judgment.

Waiting managers are not a special case either: while reports work, the manager sits
behind an ordinary dependency gate — and wakes whenever *any* report submits, so a
bad deliverable gets rejected promptly while its siblings keep working. (This, too,
was a pre-build fix: as first written, managers waited for children to "close," but
children can only close when the manager accepts — deadlock by documentation.)

## Steering without stopping: notes and directives

Mid-flight, an authority (you, or a manager) has two tools. A **note** is anchored,
non-blocking advice — "prefer the streaming writer" — injected into the worker's next
turn; it pauses nothing, and the worker may act on it or explain why not. A
**directive** is binding: a real instruction added to the assignment, taking effect
at the next turn boundary. (Team-wide *standing* directives — rules that auto-attach
to future assignments — are a proposal, not yet part of the rulebook.)

**Our running example:** watching the living plan, the operator drops a note about
output format. The engineer picks it up next turn without breaking stride.

## Submission, review, and who pays for rework

The engineer finishes: its work is bundled as a deliverable and submitted. Because
QA's dependency is a *verify* link, submission (not acceptance) wakes QA, with
references pinned to exactly the submitted version — the checker never reviews a
moving target. The lead also wakes, but does not accept yet: acceptance is the final
verdict, *informed by* the verification.

QA runs the full test suite — which the engineer, by construction, could not run —
and files a failing report: an edge case the practice project's data plants
deliberately — text fields containing commas and quotes — breaks the CSV.
The lead **rejects** the engineer's deliverable, citing the report. The brief was
unchanged, so the assignment returns to planning **on the same meter**.

That sentence is the **rework funding rule**, and it is one of the design's sharpest
ideas: *if the instructions stood, redoing the work burns the worker's own budget* —
a quality failure stays visibly that worker's cost. *If the manager had to rewrite
the brief, the top-up is charged to the manager's budget* — a scoping failure
surfaces one level up. Blame, in token form, lands where the failure was.

The engineer fixes the edge case and resubmits; QA re-verifies; green. The lead
accepts both deliverables. Acceptance is terminal: it closes the assignment and its
meter, and the platform writes each worker's **memory** — a durable "recent work"
record the worker will see at its next intake, surviving restarts, inspectable and
resettable by you, never writable by the worker itself.

## Artifacts: how finished work is filed

Work products leave a worker only as **artifacts**: permanent, versioned files in a
shared, permission-checked store. Each artifact gets an address like
`org://acme/a_qa01/test-report@1`; workers exchange these short references, never
raw files. Revising an artifact creates version 2 — version 1 never vanishes. Each
team has its own shelf (**ArtifactSpace**); sharing beyond the team is explicit,
temporary, and logged. Provenance is recorded throughout: who made it, on which
assignment, at what cost.

Real-world actions that produce no file are delivered as **action attestations** —
signed claims with evidence attached — and are only accepted if the required approval
gate was resolved *first*: consented, then evidenced.

**Our running example, closing:** merging the accepted code into the protected main
line ([doc 01](01-what-is-canopy.md) glossed this: adding it to the official shared
copy of the program) is a governed action. An approval gate owned by the operator
opens; on consent,
the *platform* performs the merge and records the attestation linking consent to
evidence. The intent completes with a deliverable card: the artifacts, the total
cost — split into *coordination* (management overhead) versus *production* (actual
work) — and the full chain from the typed sentence to every spend event.

## When things crash

State lives in a database, not in anyone's head. Crashed workers are restarted and
resume their suspended conversations; open work survives shutting the whole team down
and restarting it; redelivered messages never double-charge the ledger. The paper
trail is append-only (records can be added, never erased).

---

**Where this comes from:**
[execution/work-model.md](../execution/work-model.md) (intents, assignments, briefs,
gates, plans, steps, rework funding, memory) ·
[execution/engine.md](../execution/engine.md) (the engine, staged delegation,
manager-await, top-ups, cadences, recovery) ·
[domain-model.md](../domain-model.md) (the underlying rulebook and invariants) ·
[execution/mvp.md](../execution/mvp.md) and
[execution/target-app.md](../execution/target-app.md) (the CSV-export walkthrough,
the split test suite) ·
[execution/amendments-2026-07-26.md](../execution/amendments-2026-07-26.md) (the five
pre-build fixes: verify/consume, staged delegation, wake-on-delivery, the living
plan, notes) ·
[actuation/workspace.md](../actuation/workspace.md) (artifacts, `org://` references) ·
[execution/operator-experience.md](../execution/operator-experience.md) (the
operator's screens — designed, not built).
