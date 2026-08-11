# Glossary — every Canopy term, in plain English

*Merged from the three analyst glossaries (actuation; team & operator;
execution & safety), deduplicated and alphabetized. One or two lay sentences each.
Cross-references in italics.*

- **A2A (Agent2Agent)** — a published open protocol for sending tasks between AI
  agents. Canopy's original design used it as the message format; the protocol layer
  was never adopted (a simpler mailbox shipped instead), so the term is historical.

- **Acceptance / Rejection** — the manager's final verdict on submitted work.
  Acceptance closes the assignment, its budget, and writes the worker's memory;
  rejection sends the work back under the *rework funding rule*.

- **Acceptance tests** — see *Unit tests vs. acceptance tests*.

- **ActionAttestation** — a signed "I did X, here is the evidence" claim, for
  real-world actions that produce no file (a sales call, a cooked order). Only
  accepted if the required approval was granted first: consented, then evidenced.

- **Activity Log** — the append-only (records can be added, never erased) audit
  journal of everything that happens in the system.

- **Actuation** — bringing a drawn org chart to life: provisioning one running agent
  per box, budgeted and readiness-checked, until the team is live. **Deactuate** is
  the clean teardown: drain mail, revoke tokens, stop agents, destroy sandboxes.

- **Actuator** — the head-office service that performs actuation and teardown, and
  continuously repairs the gap between "what should be running" and "what is."

- **Agent** — one AI worker occupying one box on the org chart: a running program
  driven by an AI model, with a job, a manager, a budget, a private workspace, and
  durable memory. Works one assignment at a time, like a person.

- **Agent Directory** — the attendance register: which agents are alive, at what
  address, in what state, based on their heartbeats.

- **Agent Envelope** — the complete sealed package assembled for one node: charter
  (who am I) + grant set (what may I touch) + runtime kind (how do I execute) +
  sandbox tier (how strong a wall) + profile (which brain). The contract every
  agent honors regardless of how it's implemented.

- **Agent Inspector** — the designed deep-dive screen for one worker: instructions,
  current assignment and the chain of "why," plan, spending, gates, memory, session
  log, and files. Part of the not-yet-built Operate cockpit.

- **Agent Profile** — the "which brain" record: AI provider, model, and settings,
  with a reference (never the value) to the account key. Kept out of the portable
  chart; attached to nodes by an **AgentBinding**.

- **Allowance** — the token budget attached to one assignment's meter; funded from
  the role's *salary*.

- **API key** — the kind of account credential that lets a program bill AI usage
  per individual request. Canopy's current setup has none — the operator's machine
  is logged in under a personal subscription instead, which is why real work runs
  as wrapped CLI sessions (see *Session*).

- **Approval gate** — the pause for consent before a consequential action (merge
  code, contact a customer, spend extra). Denial is a prohibition to plan around,
  never a request to redo.

- **Archetype (team type)** — a ready-made kind of company (software
  company, newsroom, medical clinic) that determines which roles and formations you
  build with. The catalog ships 26.

- **Artifact** — a permanent, versioned, addressable work product (document, code
  change, report). Fingerprinted, with recorded provenance; the only way work
  leaves a workspace. Revisions create new versions; old ones never vanish.

- **ArtifactSpace** — a team's shared shelf of artifacts. Sharing beyond the team is
  explicit, temporary, and logged (a *cross-team grant*).

- **Artifact Store** — the permission-checked filing cabinet holding all artifacts;
  workers exchange `org://` references into it, never raw files.

- **Assignment** — one unit of delegated work binding a worker, a brief, a
  definition of done, and a budget. Assignments form a family tree under the intent.

- **Blueprint** — a deferred future feature: saving a whole team as a
  reusable template for cloning.

- **Branch** — in *git*, a worker's separate line of changes to a shared codebase,
  kept apart from the official copy (the *main line*) until reviewed and merged.
  Every Canopy coding agent works on its own private branch.

- **Brief** — the written instructions inside an assignment. Versioned: rewriting it
  creates version 2, and which version was in force decides who pays for rework.

- **Budget warn** — the tripwire at (default) 80% of an allowance: a warning and an
  amber glow; work continues.

- **BudgetMeter** — see *Meter*.

- **Bus** — the postal system beneath the message router: one durable inbox queue
  per agent; messages are never lost and are delivered in order when the recipient
  is free.

- **Cadence** — a schedule ("every Monday…") that automatically fires a fresh intent
  at each occurrence; skipped if the previous run is still open.

- **Catalog** — the shipped library of archetypes, roles, formations, tool grants,
  and use-case recipes. Data, not code.

- **Charter** — an agent's compiled briefing pack: identity, role instructions,
  manager and reports, salary — and, in the current model, its resolved grants and
  runtime kind. Fetched at boot; the agent never reads the team document itself.

- **Clarification gate** — "these instructions are defective." Raised by the worker
  at intake instead of guessing; resolved by a revised brief or cancellation.

- **CLI (command-line interface)** — a program driven by typed commands rather than
  windows and buttons. In this series it almost always means the Claude Code
  program, which Canopy runs headless (no visible window) as a worker's brain.

- **Consume edge (consume link)** — see *Dependency*.

- **Contract (deliverable contract)** — the declared *type* of output an assignment
  will accept ("a PullRequest," "a TestReport"). Nothing else counts as done.

- **Control plane** — the head office: the one authoritative program holding all
  records and all secrets. It coordinates everything but never does an agent's
  thinking for it.

- **Coordination vs. production split** — the ledger's division of spend into
  management overhead (delegating, reviewing) versus actual work — the number that
  answers "what did the bureaucracy cost?"

- **Cost Explorer** — the designed money screen: spend by request, node, and model,
  drillable to individual steps. Part of the not-yet-built Operate cockpit.

- **Cross-team grant** — temporary, read-only, logged access to one artifact for one
  assignment in another team.

- **Data plane** — the workshop floor: the running agents themselves, deliberately
  kept dumb and replaceable; anything can be rebuilt from head-office records.

- **Deactuate** — see *Actuation*.

- **Delegation** — a manager creating a child assignment for a direct report. Only
  manager → own report is legal, checked against the chart on every attempt.

- **Deliverable** — the finished output submitted for review: an *artifact* or an
  *ActionAttestation*.

- **Delta (delta taxonomy)** — the closed set of "what changed this step" labels:
  produced a file, used a tool, advanced the plan, sent a message, or *nothing* —
  the last being the early-warning sign of a worker spinning.

- **Dependency** — a declared "B waits for A" link between sibling assignments. Its
  **resolution policy** says what B waits for: a **verify edge** (verify link)
  starts B at A's *submission* (B's job is to check A); a **consume edge** (consume
  link) waits for the manager's *acceptance* (B builds on A).

- **Dependency gate** — the waiting state of an assignment blocked on someone else's
  output; resolves mechanically per the edge's policy, costing nothing while it
  waits.

- **Directive** — a binding mid-flight instruction added to an assignment, taking
  effect at the next turn. A **standing directive** (team-wide, auto-attaching to
  future assignments) is a proposal, not yet in the rulebook.

- **Engine (Execution Engine)** — the central coordinator that owns all official
  work records. Workers only report or request; the engine validates and updates
  state — the office manager with the master whiteboard.

- **Escalation gate** — "this decision is above my pay grade." Someone higher
  answers, and the answer is injected into the resumed work. An **introduction**
  (brokered channel) is one resolution: a temporary, logged direct line between two
  agents in different teams.

- **Executor** — the platform-side machinery that actually performs a granted
  capability (e.g. the git machinery behind repository access). Building a new kind
  of executor requires programming; once it exists, granting and using it is just
  catalog data — the design's shorthand is "adding one is code; using one is data."

- **Formation** — a reusable team blueprint: one manager role plus member roles,
  pre-wired with the flow of work and waiting rules. Stamped into a chart in one
  action; "pod" is the informal name for the small delivery-team formations.

- **Fuzzing** — automated testing by randomized bombardment: throw large volumes of
  random or malformed input at a system to shake out failures no one thought to
  test for. Canopy's money-path tests use it.

- **Gate** — the one mechanism for anything that pauses work. Five kinds:
  clarification, dependency, approval, escalation, intervention. A gated assignment
  is suspended, spends nothing, and frees its worker for other queued work.

- **Git** — the standard system programmers use to track versions of code: it keeps
  the official shared copy, everyone's separate *branches*, and the history of
  every change. Canopy's platform operates git on the agents' behalf; agents never
  hold the repository credential.

- **Governed action** — an action with real-world consequences (merge, publish,
  contact a customer, pay) that requires consent *before* execution and evidence
  after.

- **Grant (ToolGrant)** — a catalog entry for one grantable capability, carrying a
  risk class, a minimum sandbox tier, its executor, its credential kind, and any
  governed actions. An agent's powers are exactly its resolved grants —
  "capability as possession."

- **Grant pack** — a distributable bundle of curated grants for one tool family
  (e.g. a GitHub pack). Designed, not confirmed built.

- **Hard stop** — the mechanical halt when an allowance is exhausted: the session
  stops at the turn boundary and an intervention gate opens — top up, redirect,
  reassign, or cancel.

- **Heartbeat** — the periodic "I'm alive, here's my status" ping every agent sends
  the directory (about every ten seconds).

- **Inbox (operator's)** — the designed screen listing only items genuinely blocked
  on the human. Part of the not-yet-built Operate cockpit.

- **Intent** — what the operator actually asked for, addressed to one agent (usually
  the root); the record every task and every cent traces back to. **Episodic**
  intents finish; a **standing** intent is open-ended and *is* the team's goal.

- **Intent Console** — the designed screen where you give the team work: type a
  request, see a projected-cost hint, approve the proposed breakdown before money
  moves, then watch the living outline of the engagement. Part of the not-yet-built
  Operate cockpit.

- **Intervention gate** — the brake: opened automatically by tripwires (hard stop,
  stall) or by human judgment. Resolutions: resume, redirect, constrain, reassign,
  top up, cancel.

- **Invariant** — a rule that must always hold, no matter what — like "spend never
  exceeds allowance." Canopy's tests attack every invariant deliberately:
  "invariants only tested by well-behaved callers are not tested."

- **Ledger** — the append-only money book: every step lands exactly one spend
  record — a duplicate delivery never charges twice — and costs roll up
  step → assignment → intent → team.

- **Living plan view** — the designed single evolving outline of a whole engagement
  (every assignment, plan, cursor, budget, gate), where each line can receive a
  note or an intervention.

- **Manager** — any agent with reports: it decomposes work, issues briefs, declares
  dependencies, accepts or rejects deliverables, and unblocks. It cannot do its
  reports' work (it holds no tools for it) and cannot restructure the team.

- **Manager-await** — the ordinary dependency gate a manager sits behind while its
  reports work; it wakes the manager whenever *any* report submits and re-arms
  until all are done.

- **MCP (Model Context Protocol)** — a standard connector protocol for external
  tools. In Canopy's design, MCP servers hang off the Tool Proxy (never off an
  agent), and each exposed tool must be hand-curated into a grant. A Canopy MCP
  server is also how wrapped CLI sessions talk back to the platform.

- **Memory** — the durable per-position "recent work" record, written by the
  platform when an assignment closes and shown to the worker at its next intake.
  Survives restarts; inspectable and resettable by the operator ("backfilling the
  position"); never writable by the worker.

- **Merge / main line** — the **main line** is the official shared copy of a
  program's code; **merging** is adding a finished change into it, making the
  change part of the real product. In Canopy, merging to the protected main line is
  always a *governed action* — see *Merge request*.

- **Merge request (governed merge)** — the flagship governed action: merging
  accepted code into the protected main line requires an operator-owned approval
  gate; the platform then executes the merge and records the attestation.

- **Message Router** — the mailroom chokepoint: the only path between agents,
  enforcing org-chart channels, queueing, and logging every message.

- **Meter** — the spending account attached to one assignment: an allowance, a
  running spent figure, a warning threshold, and a hard stop. Enforced by the
  platform between steps — an agent cannot opt out of its budget.

- **Milestone** — two senses in the docs. (1) A named checkpoint on an intent with
  a date and acceptance criteria; its status (met / missed / at-risk) is computed
  from the work, never hand-toggled. (2) A lettered build checkpoint in the
  project's own history — A1–A3, E1–E8, O1–O9 and the like; see
  [doc 06](06-status-and-direction.md)'s key to the letter codes.

- **Mission Control** — the designed live org-chart view: boxes dim when idle,
  pulsing when working, amber when gated, red when dead, with budget arcs and queue
  depths. Part of the not-yet-built Operate cockpit.

- **Mock provider / fake-CLI shim** — test stand-ins for the AI provider and the
  CLI session, letting every behavior run in automated tests with zero spend and no
  login.

- **Model Gateway** — the switchboard chokepoint: the only path to AI providers. It
  injects credentials, meters every call, and checks budgets before dispatch.
  (Today's wrapped CLI sessions are the honest exception: they reach the provider
  via the subscription login — see [doc 04](04-how-agents-run.md).)

- **Mount point (child team)** — where a nested team attaches: its root agent
  reports to a designated agent in the parent, and the parent sees only that root
  ("sub-team opacity").

- **MVP (minimum viable product)** — the first working version of a product: the
  smallest build that does the whole job end to end, shipped before the polish.
  Design items marked "post-MVP" are deferred until after that first version.

- **Node** — a box on the org chart; an agent's position in the tree. A mounted
  child team also appears as a single node.

- **Note** — anchored, non-blocking advice on in-flight work ("consider the
  streaming writer"), injected at the worker's next turn. Opens no gate, changes no
  instructions; the worker may act on it or explain why not.

- **Notification severities** — the discipline for alerts: *attention* means "the
  team is blocked on you," *warning* means "degrading but running," *info* is the
  normal pulse.

- **Operator** — the human who owns and supervises a Canopy team: creates
  it, gives it work, approves plans, resolves alarms, pays the bills, and is the
  only one who can change its structure. (Called "the user" in some docs.)

- **`team://` ref** — an artifact's permanent address, like
  `team://acme/a_qa01/q3-report@1`. Agents exchange these short references instead
  of files. (Addresses written before the 2026-08 rename start with `org://`;
  those keep working forever.)

- **Organization** — the umbrella above teams: a named, budgeted group of teams
  with hard walls between organizations — your company's fleet next to your
  personal fleet, nothing shared but you. Never runs anything itself; work always
  goes to a team. (Before the 2026-08 rename, "Organization" meant what is now
  called a Team.)

- **Team** — one runnable chart: a named org chart of AI workers with a type.
  Teams can nest inside each other as departments or franchises, and every team
  belongs to exactly one Organization.

- **Team document** — the saved file the chart editor produces: chart, role
  bindings, and salaries — deliberately excluding memory, secrets, and in-flight
  work. The input to actuation; "the editor is the tool; the document is the
  product."

- **Plan / PlanStage** — the worker's declared, observable to-do list for an
  assignment, broken into stages with completion signals and a visible cursor.
  Revisions are versioned, not silent.

- **Pull request** — a packaged, proposed change to a codebase — the worker's
  *branch*, bundled up so a reviewer can examine exactly what would change and
  accept or reject it before it merges into the *main line*.

- **Receipt** — the published cost summary of a piece of team-authored work: total
  cost, tokens, and the coordination-vs-production split ("authored by a Canopy team
  for $X.XX").

- **Reconciler** — the actuator's repair loop: every fifteen seconds, compare
  desired against actual and restart what died.

- **Report** — an agent someone manages; the other half of *manager*.

- **Resolution policy** — see *Dependency*.

- **Responsibility** — a named duty with a completion contract ("review pull
  requests → ReviewReport"). No duty counts unless discharging it produces
  something checkable: "duty → deliverable."

- **Rework funding rule** — who pays for redone work: if the brief was unchanged,
  the redo burns the worker's own meter (a quality failure, visible on them); if
  the brief was rewritten, the top-up is charged to the manager's meter (a scoping
  failure, visible one level up).

- **Risk class** — a grant's rung on the five-step danger ladder: inert → read →
  write → execute → consequential (irreversible real-world effect).

- **Role (RoleTemplate)** — a prebuilt job description: instructions, duties,
  permitted tools, expected outputs, and a default salary. Pure data, never code;
  versioned, so catalog changes don't silently alter existing teams.

- **Run token** — an agent's unique, revocable identity pass, minted at
  provisioning and presented on every call to the control plane; stored server-side
  only as a fingerprint. The only credential an agent ever holds.

- **Runtime (adapter)** — the wrapper program that drives an agent: fetches
  instructions, generates the session's permissions, watches and meters the
  conversation, enforces the budget between turns, and reports to the engine.

- **Runtime kind** — which implementation drives a node: `loop` (the native step
  loop), `cli` (a wrapped headless coding-agent session — how real work runs
  today), `actor` (a minimal decision loop over brokered calls; designed).
  Reserved on paper: `workflow`, `human-proxy`.

- **Salary** — a role's token-allowance policy (default per-assignment budget,
  warning threshold, hard stop). Not money: tokens are the unit AI computation is
  billed in. Today's numbers are uncalibrated placeholders.

- **Sandbox** — the locked workshop around one agent: its process, private folder,
  network identity, resource limits, and lifecycle, isolated from every other
  agent. Today's isolation is soft (careful construction, not hard walls).

- **Sandbox tier (T0–T3)** — how strong the workshop's walls are, from bare process
  to micro-virtual-machine with default-deny networking. Always *derived* from the
  riskiest grant held, never chosen by hand; no tier has general internet access.

- **SandboxProvider** — the pluggable technology supplying sandboxes: subprocess
  today; containers, micro-VMs, and remote machines as planned upgrades.

- **Secret Store** — the write-only vault for account keys and credentials:
  encrypted at rest, plaintext readable only deep inside the server at the moment
  of use. You can store or rotate a key; nothing ever displays one back.

- **Session** — one headless (no visible window) Claude Code conversation, serving
  as a worker's brain for one assignment. Pausing work suspends the conversation —
  resumable, context intact — rather than losing it.

- **SpendEvent** — one accounting entry attributing the cost of one step to its
  team, node, and assignment; the atomic record in the ledger.

- **Staged delegation ("proposed")** — with a plan-review checkpoint on, a
  manager's delegations buffer as unfunded drafts; the operator reviews the real
  batch (briefs, budgets, dependencies) and approval funds and dispatches it
  atomically. Denial cancels outright.

- **Stall** — the tripwire for a worker burning tokens without progress: no step
  for (default) ten minutes, or five consecutive "nothing changed" steps. Opens an
  intervention gate.

- **Step** — the atomic recorded unit of activity: one AI exchange or tool action,
  with token counts, duration, and a delta label. Cost and progress drill down
  intent → assignment → plan → stage → step.

- **Step loop** — the `loop` runtime's work cycle: intake the brief, then a bounded
  think-and-act loop (about 20 rounds), then discharge the outputs.

- **Pod** — a manager plus its direct reports, derived from the chart (never drawn
  separately). Also the communication boundary: podmates may talk; strangers'
  messages route up through managers. (Called a "team" before the 2026-08 rename
  freed that word for the chart itself.)

- **Threat model** — the document stating plainly what attacks the system defends
  against, what it deliberately does not, and what must change before those
  exclusions become acceptable.

- **Tick** — the older `loop` runtime's heartbeat cycle (act, report, repeat). In
  the current CLI runtime its role is played by the *turn*; this series uses turn.

- **Token** — the unit AI computation is measured and billed in; Canopy's internal
  currency for salaries, budgets, and costs.

- **Tool Proxy** — the third chokepoint (after thinking and talking): *acting*. The
  single execution path for platform-brokered tool calls — authorize, gate if
  governed, inject credential, execute, log. Each call is logged as a
  **ToolEvent**.

- **Top-up** — adding funds to an exhausted meter so work resumes. A manager may
  auto-top-up a report by a bounded 20%, once per assignment, without waking the
  operator; anything more routes upward.

- **Trusted-local (waiver)** — v1's honest posture: one trusted person, one trusted
  machine, soft sandboxes. Running risky grants on the soft sandbox requires this
  explicit, logged acknowledgment.

- **Turn** — one back-and-forth exchange in a session. The turn boundary is where
  Canopy's brakes engage: budget checks, halt flags, and injected advice all land
  between turns.

- **Unit tests vs. acceptance tests** — **unit tests** are small, quick checks of
  individual pieces of a program; **acceptance tests** are the final pass/fail
  checks that decide whether the whole feature is done. In Canopy's running example
  the engineer may run only unit tests; the deciding acceptance tests belong to QA.

- **Verify edge (verify link)** — see *Dependency*.

- **WIP (work-in-progress) cap** — the limit (default 3) on how many suspended
  assignments may pile up on one worker.

- **Workspace** — an agent's private desk, the only part of the filesystem it can
  touch: `brief/` (in-tray), `work/` (workbench), `out/` (out-tray).

- **Worktree** — a real working copy of a code repository, materialized into a
  workspace on the agent's own branch by the platform's git machinery. Repo access
  is "a credentialed capability, not a filesystem fact"; one worktree per
  assignment.
