# 05 — Keeping it safe and on track

*What could go wrong, what actually stops it, and what the design honestly admits it
does not stop. Plus the project's own list of what could kill it.*

Safety in Canopy is not one feature. It is a posture repeated at every layer: assume
the worker will err or overreach, and make the dangerous move impossible, expensive,
or loudly visible — never merely discouraged. This doc collects the whole picture:
the threat model, the walls, the money brakes, the review gates, the paper trail, and
the known risks.

## The threat model: one page, deliberately modest

A **threat model** is a security document that states plainly who might attack a
system, how, which defenses hold — and which attacks the system does *not* defend
against. Canopy's is one page, and its stated purpose is preventing *positioning
drift*: the danger that someone later markets "run Canopy for your team on a server"
while silently inheriting assumptions made for one person on one laptop.

**Version 1 assumes: one trusted person, on their own trusted computer, nothing
exposed to the network.** No login screen, no separation between customers.

What v1 **does** defend against, in lay terms:

- **A worker impersonating another.** Each agent holds a unique, revocable
  **run token**, stored server-side only as a fingerprint. A leak burns a cancelable
  token, never a real credential.
- **Workers seeing the operator's account keys.** Keys live encrypted in the Secret
  Store and are revealed only deep inside the server at the moment of use. Even the
  operator's own interface is write-only for secrets: you can store or rotate a key,
  never read one back.
- **Off-chart communication.** All messages pass through the router, which enforces
  the org chart; workers never learn each other's addresses.
- **Runaway spending.** The budget check is mechanical and halts work — the platform
  holds the brake, not the agent. (With one honest coarsening in the current
  runtime; see "Budget hard stops" below.)

What v1 explicitly does **not** defend against:

- **A hostile user on the same machine.** The master encryption key sits on disk
  next to the database; anyone who can read the disk can decrypt the secrets.
- **Network exposure.** Traffic is unencrypted and there is no login check — the
  design says flatly: do not expose the control plane to the network.
- **One team degrading another.** All teams share one process and one database.
- **Untrusted code.** The sandbox is soft (below) — which is exactly why dangerous
  tool grants are withheld until hard sandboxes exist.

The threat model lists preconditions before any hosted or multi-user version is
allowed. Treat the exclusions as promises about what must change first.

**A staleness flag the reader deserves:** the threat model has not been updated for
the current CLI runtime. It still asserts "no agent environment ever carries a key"
and "the budget check halts before the breaching call" — both weakened by the
wrapped-session design: the Claude Code login credential sits in a settings
("config") folder
*inside* the (soft) sandbox, readable in principle by a hostile process on this
machine, and budget enforcement moved to turn boundaries. The runtime doc discloses
both honestly and calls itself an extension of the threat model; the threat model
itself hasn't absorbed the changes. A reader of the threat model alone gets a
stronger guarantee than the system currently provides.

## Sandboxing: real walls, honestly described

[Doc 04](04-how-agents-run.md) described the locked workshop; here is its safety
summary. Each agent runs in its own sandbox: private folder, scrubbed environment,
no credentials, network access only to the control plane. Isolation between workers
is layered — in our running example the engineer *cannot* run the acceptance tests,
edit outside its own worktree, or reach QA's files, because: (1) those tools are
absent from its generated session, (2) the server re-checks and refuses ungranted
calls anyway, (3) the workspaces are physically separate folders, and (4) its
deliverable contract wouldn't accept out-of-role output. "A QA agent that just fixes
the code is unrepresentable."

The honest part: today's walls are **soft** — ordinary processes, careful
construction, "trusts the agent runtime code, not OS enforcement." Real walls
(containers, micro-VMs) are designed as the tier ladder but are future work. The
design's compensating rule: risky capabilities are simply not granted until walls
strong enough for them exist, and running risky grants on the soft sandbox requires
an explicit, logged acknowledgment called the **trusted-local waiver**. Notably,
Canopy's first real self-hosted run (the E8 documentation task) was deliberately
configured with the waiver *off* — proving a docs-only team needs no special-risk
acknowledgment at all.

## Budget hard stops

The money story in one paragraph: every assignment has a meter; every step lands a
spend record; at 80% you get an amber warning; at 100% the platform halts the
session at the turn boundary and opens an intervention gate — top up, redirect,
reassign, or cancel. A manager may auto-top-up a report once, by 20%, and no further.
The worker cannot opt out: the state moves are the engine's, not the worker's.

Two honest limits. First, **E-D1**, the known debt: with a wrapped subscription
session there is no way to pre-approve each individual AI request, so the brake
engages *between* turns — one turn can overshoot the line before the check lands.
Second, costs are the provider's own reported numbers, not independently measured.
Both are recorded in the design as debts with intended fixes, not glossed over.

Alongside the hard stop run the other tripwires: the **stall** detector (no recorded
step for ten minutes, or five consecutive "nothing changed" steps — the mechanical
signature of a worker spinning) opens an intervention gate; a scope-drift alarm
("on budget but off brief") is designed but explicitly deferred until after the
first working version (the "MVP" — minimum viable product).

## Review gates: consent before consequence

The gate system ([doc 03](03-how-work-flows.md)) is as much a safety mechanism as a
workflow one:

- **Staged delegation** means an AI manager's plan spends nothing until a human has
  seen the real subtasks, budgets and all. Denial cancels outright.
- **Approval gates** put a human between the team and anything irreversible. In the
  running example, the merge to the protected main line only *opens a gate*; the
  platform executes the merge after consent and records consent plus evidence
  together. An agent cannot perform the governed act itself — the tool it holds
  literally only requests permission.
- **Verify dependencies** wire independent checking into team structure: QA wakes on
  the engineer's *submission*, and the lead's acceptance comes after the checker's
  report — a property proven by automated tests, not just described in prose (the
  design's phrase: "by test, not narrated").
- **Rejection has a price tag** — the rework funding rule bills redone work to
  whoever caused it (worker if the brief stood, manager if it changed), so quality
  failures can't hide.

## The audit trail

Everything consequential is written down, append-only (records can be added, never
erased), and attributable:

- every AI exchange → a metered **step** with token counts and a "what changed" label;
- every cost → a **spend event** in the ledger, idempotent (a redelivered message
  never double-charges), rolling up step → assignment → intent → team;
- every tool call through the proxy → a logged event; every message through the
  router → logged; every gate, consent, and denial → recorded;
- every artifact → fingerprinted, versioned, with provenance (who, which task, when);
- the whole team → inspectable live: any agent can be opened to show its charter,
  plan, steps, meter, gates, memory, session log, and files.

The designed end product of all this is the **receipt**: a published cost summary of
a piece of team-authored work — total cost, tokens, and the split of coordination
overhead versus production work. "Authored by a Canopy team for $X.XX."

## Tested like money depends on it

The design treats its own correctness as a safety feature. Four commitments stand
out: every meaningful behavior must be testable with *zero* AI spend (fake provider,
fake CLI; exactly one manually-run test touches the real AI); the same checking
rules are written twice, in two different programming languages — and shared test
data forces both copies to give identical answers, so any drift between them fails a
test immediately; the **money path gets the strongest tests in the repo** — fifty
simultaneous streams of activity ("threads") racing one meter to prove the hard stop
holds, proofs that redelivery never
double-charges, randomized bombardment ("fuzzing") asserting that spend — including
holds — never exceeds allowance; and
every **invariant** (a rule that must always hold, like "spend never exceeds
allowance") gets at least one *adversarial* test that actively tries to break it
— "invariants only tested by well-behaved callers are not tested."

One disclosure the design makes itself, and this series repeats: at the time the
docs were written, per-agent permission checks on artifact fetching were **not yet
implemented** — any agent could fetch any team artifact — and the test plan parks a
deliberately failing test on the gap until the fix (scheduled at milestone E3)
lands. The isolation story elsewhere in the docs describes the *target* state.
Whether the gap has since closed is a build-status question; see
[doc 06](06-status-and-direction.md).

## The top known risks

Canopy keeps a candid risk register — "what could kill this" — ranked by severity.
The headline entries, in lay terms:

- **The economic null hypothesis** (existential). Maybe one strong AI agent with
  good context simply beats a simulated team on cost *and* quality for most tasks.
  The declared counter-move: build the head-to-head benchmark early (the same task,
  one unsupervised agent vs. the team), publish the numbers honestly either way — and
  if the team loses on raw cost, the pitch becomes what the ledger already proves:
  teams make AI work *governable, auditable, and costed*.
- **Value gated behind Phase 3; the second-session problem** (existential/major).
  Early phases demo beautifully but give no reason to return tomorrow; recurring
  cadences and real usefulness are the retention answer.
- **A crowded market; "SimCity for agents"** (major). Orchestration is a crowded
  field, and the product risks being spectacular to watch but weakly retained —
  bookmarked admiringly, never adopted.
- **Cold start** (major). You must design a team before any output exists. Planned
  counter: intent-first onboarding — type the request first, Canopy proposes the team.
- **Coordination cost and manager bottlenecks** (major). Management overhead tokens
  can dwarf production tokens as trees deepen, and every manager is a spot where
  work queues up single-file. The coordination-vs-production split in the ledger
  exists partly to keep
  this measurable and honest.
- **Build capacity and money-path correctness** (major/manageable). A huge surface
  area against mostly one builder; and bugs in the ledger burn real money — answered
  by the testing bar above.
- **Architecture watch-items** (mostly manageable): central mediation as a
  bottleneck, dual-language drift, at-least-once delivery colliding with money
  (hence idempotent charging), the secrets posture versus future hosted ambitions,
  noisy-neighbor teams, and operator attention itself as the scarce resource at scale.

---

**Where this comes from:**
[actuation/threat-model.md](../actuation/threat-model.md) (the threat model) ·
[execution/cli-runtime.md](../execution/cli-runtime.md) (turn-boundary enforcement,
E-D1, the credential caveat, the trust statement) ·
[actuation/sandbox.md](../actuation/sandbox.md) and
[actuation/agent-envelope.md](../actuation/agent-envelope.md) (soft walls, tiers,
enforcement layers) ·
[execution/mvp.md](../execution/mvp.md) and
[execution/target-app.md](../execution/target-app.md) (layered isolation, the
structural rework beat, the benchmark twin) ·
[execution/work-model.md](../execution/work-model.md) and
[execution/engine.md](../execution/engine.md) (meters, stalls, gates, bounded
top-ups) ·
[execution/e8-runbook.md](../execution/e8-runbook.md) (no-waiver run, the receipt) ·
[testing.md](../testing.md) (zero-spend testing, money-path paranoia, the artifact
grant gap) ·
[risks/README.md](../risks/README.md) and the seven themed risk files
([problem-fit](../risks/problem-fit.md), [usefulness](../risks/usefulness.md),
[marketing](../risks/marketing.md), [design](../risks/design.md),
[architecture](../risks/architecture.md),
[implementation](../risks/implementation.md),
[scalability](../risks/scalability.md)).
