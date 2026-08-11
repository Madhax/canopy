# 04 — How agents run

*What an AI worker physically is: the head office and the workshop floor, the sealed
work order each agent receives, the locked room it works in, and the three doors all
its activity must pass through.*

[Doc 03](03-how-work-flows.md) described work as if workers simply existed. This doc
opens the hood. Our running example continues: we follow the backend engineer from
the moment the operator clicks **Actuate** to the moment it edits real code.

## Head office and workshop floor

The deepest line in Canopy's architecture splits the system in two.

The **control plane** is the head office: one central program that holds all the
records — org charts, AI configurations, budgets, finished work, the audit journal,
and every secret key. It is "small and authoritative."

The **data plane** is the workshop floor: the running agents themselves, one running
program (a "process") per chart node, each locked in its own sandbox. The floor is
deliberately "dumb and
replaceable": any agent can be killed and rebuilt from head-office records alone.
Nothing precious ever lives only in a workshop — sandboxes are cattle, not pets:
replaceable without sentiment, as the design's borrowed idiom puts it.

Everything an agent does that touches the world passes through a head-office
chokepoint. There are three — the topology doc names the first two; the capability
model (agent-envelope) adds the third:

- **Thinking** → the **Model Gateway**. The only route to the AI providers. The
  gateway looks up which AI model this agent is configured to use, attaches the
  secret account key (which the agent never sees), checks the budget *before*
  forwarding, and records the spend — like a switchboard that bills every
  long-distance call to the right department. (One honest caveat, unpacked below:
  today's wrapped CLI sessions reach the provider through the subscription login,
  not this gateway — so for them, budget checks land between turns and costs are the
  provider's own numbers.)
- **Talking** → the **Message Router**. The only way agents communicate. Every
  message is checked against the org chart (managers with their own reports; the
  operator with anyone; everything else refused — siblings route via their manager),
  logged, and queued. Under it sits the **bus**: one durable inbox per agent,
  messages never lost, delivered in order when the recipient is free. Agents don't
  even know each other's addresses — only names.
- **Acting** → the **Tool Proxy**. The single execution path for tool use with
  real-world reach (see "Grants," below): authorize, pause for approval if the
  action is governed, inject the credential, execute, log.

An agent that cannot think, talk, or act except through a checkpoint is an agent
whose every consequential move is authorized, metered, and written down.

*(A historical note: the original design had agents speak a published agent-to-agent
protocol called A2A, each running its own little protocol server. That layer was
never adopted — a simpler mailbox shipped instead, and the design record says so.
The router-and-bus model above is what stands.)*

## The brain is chosen at head office

Which AI model powers an agent — Claude or Gemini, and which version — is set by an
**agent profile**, a record kept deliberately *outside* the org chart. The chart
stays a portable description of structure; the profile carries machine-local,
secret-adjacent detail. A small record called a **binding** attaches a profile to a
chart node; many nodes can share one profile.

Secret keys get the strictest handling in the system. A profile never contains an
account key — only a *reference* into the **Secret Store**, a vault inside the
control plane where keys live encrypted. The vault is **write-only from the
outside**: you can add, rotate, or delete a key, but no screen or API ever displays
one back. Only the Model Gateway, deep inside the head-office process, decrypts a key
at the moment of use.

The punchline is what the agent itself sees of all this: *nothing*. At startup an
agent receives only its identity, its instructions, its manager's and reports' names,
the head-office address, and its **run token** — a revocable pass-card it presents on
every call, the *only* credential it will ever hold. It cannot name a model, a
provider, or a key. A confused or compromised agent has nothing to steal and no way
to upgrade its own brain.

## Actuate: bringing the chart to life

When the operator clicks **Actuate**, the head office's **Actuator** runs a
checklist. First, readiness: every node has a binding, every profile's key exists and
answers a cheap test call, every granted capability is available, and the isolation
on offer is strong enough for the tools being granted (more below) — if not, the
launch *refuses* rather than start with weakened walls.

Then it walks the chart top-down (managers first, because a report must be told who
its manager is). For each node it mints an identity and a run token; compiles the
**charter** — the agent's complete briefing pack: role instructions, manager and
report names, salary, and (in the current capability model) its resolved tool grants
and runtime kind; asks the sandbox provider to build the workshop and start the
process; and waits for the newborn agent to call home and register.

The new agent boots, fetches its charter, lays out its desk, registers, and starts
**heartbeating** — a ten-second "I'm alive" pulse into the **Agent Directory**, the
head office's attendance register. The node turns green in the editor. When every
node is green, the team is **live**. A **reconciler** loop then patrols every fifteen
seconds, comparing what *should* be running against what *is*, restarting anything
dead — a supervisor doing rounds.

**Deactuate** is the reverse, in careful order: drain the mail, revoke the tokens,
stop the processes, destroy the sandboxes. (Open work now survives a deactuate →
re-actuate cycle; editing the chart *while* live is still not supported — tear down,
edit, bring it back up.)

## The sandbox: a locked workshop

A **sandbox** wraps everything one agent needs — its process, its private folder, its
network identity, its resource limits — and walls it off from every other agent.

Today's walls are honest but soft. The v1 sandbox is an ordinary operating-system
process, isolated by careful construction: it starts with a scrubbed environment of
half a dozen variables (address, token, identity — *no keys, because none exist
anywhere on the workshop floor*); its folder is private and it is never told any
other agent's path; its network endpoint accepts connections only from the control
plane, so even two agents on the same machine cannot dial each other. The design's
own words: this "trusts the agent runtime code, not OS enforcement" — a policed
honor system, with real walls (containers and micro-VMs — technologies that seal a
program inside its own miniature computer) planned as pluggable upgrades.

The intended ladder — set out in the capability model (agent-envelope), not the
sandbox doc itself — is four **sandbox tiers**, T0–T3, from bare process to
micro-virtual-machine with default-deny networking. The strength an agent gets is
**derived, never chosen**: the riskiest tool it holds dictates the minimum tier, and
actuation refuses to launch an agent behind weaker walls than its tools demand. No
tier has general internet access. (Where things actually stand: per the runtime
doc's own words, MVP runs CLI sessions as ordinary subprocesses under the
trusted-local waiver — `execution.allow_trusted_local = true` in the config —
so containers remain future work; the build may have moved since. See
[doc 06](06-status-and-direction.md).)

## The workspace: the desk

Inside its sandbox, an agent's **workspace** is a desk with three zones:

- `brief/` — the in-tray: the task instructions and any input files, fetched at
  intake;
- `work/` — the workbench: free scratch space the platform never inspects;
- `out/` — the out-tray: staging for deliverables.

Work leaves the desk exactly one way: the agent stages a file in `out/` and publishes
it. The platform fingerprints the exact contents (a cryptographic hash — a unique
digital fingerprint), stores it immutably with a version and provenance, and hands
back a permanent `org://` address. From then on, agents exchange those short
references — never the files, and never a peek into each other's rooms. Fetching a
reference is permission-checked: a manager can grant a report only references the
manager itself is entitled to read.

For coding roles there is one more piece of furniture: the **worktree** — a real
working copy of a code repository, materialized *into* the workspace by the
platform's **git** machinery (git is the standard system programmers use to track
versions of code), on the agent's own private **branch** — a worker's separate line
of changes, kept apart from the official shared copy until reviewed and merged. Repo
access is "a
credentialed capability, not a filesystem fact": the agent never holds the
repository credential; it simply finds a working copy on its desk because its role
was granted one. One worktree per assignment; no worker ever touches another's copy
or the protected main line.

## The envelope: the sealed work order

How does one system safely run a manager, a coding engineer, and (someday) a
phone-calling sales agent? The design's answer is the **agent envelope** — the
complete sealed package assembled per node, with five separable parts:

1. the **charter** — who am I;
2. the **grant set** — what may I touch;
3. the **runtime kind** — how do I execute;
4. the **sandbox tier** — how strong a wall (derived from the grants);
5. the **profile** — which brain.

Its governing principle: **what an agent can do is determined by what it possesses,
not by what it is told.** Everything outside the grant set isn't "forbidden" — it
simply *does not exist* in the agent's world.

### Grants

A **tool grant** is a catalog entry describing one grantable capability — say,
`code.repo.write` — carrying a **risk class** on a five-rung ladder (inert → read →
write → execute → consequential, that last meaning irreversible real-world effects
like payments or phone calls), the minimum sandbox tier it demands, the head-office
machinery that actually performs it, the credential injected at call time, and any
**governed actions** — the subset requiring explicit approval before execution
("push to a protected branch").

Grants attach at the role, may be *narrowed* per node (never widened), and may be
temporarily extended for one assignment from the delegating manager's own set — with
a one-way rule guaranteeing an agent's effective powers never silently exceed what
the chart shows.

Enforcement is five layers, "none of them a prompt": the model never sees ungranted
tools; the server re-checks every call anyway; the sandbox physically lacks routes to
ungranted systems; the deliverable contract only accepts role-shaped output; and the
chart controls who can delegate what. Asking the AI nicely appears nowhere on that
list.

External tools plug in through **MCP** (Model Context Protocol, a standard connector
protocol) — but always *behind the Tool Proxy*, never wired to an agent directly, and
only after a human hand-curates each exposed tool into a grant with an assigned risk
class. Deliberate friction: a tool's technical description won't tell you whether
calling it emails a customer.

**Our running example:** the engineer's envelope holds repo-write and unit-test
grants (unit tests — small, quick checks of individual pieces of the code — are
execute-class, so its derived tier calls for a container); QA
holds read-only checkout and full-test-suite grants; the lead holds the *fewest*
grants of anyone — delegation and review need no dangerous tools. "Authority in
Canopy is topological, not capability-based": rank gives you reports, not weapons.

## Runtime kinds: three ways to be an agent

The **runtime kind** says what program actually drives a node:

- **`loop`** — the native step loop: fetch the brief, then repeat "compose the
  situation, think once via the gateway, carry out the requested actions" up to a
  bounded number of rounds, then submit. Right for managers and document-shaped work.
- **`cli`** — wraps a full coding agent (Claude Code, running headless — no visible
  window) as the worker's brain. This is how real building work runs today (see next
  section).
- **`actor`** — a minimal decision loop over head-office-brokered calls, for roles
  like a cold-caller that need no filesystem at all. *(Designed, not built.)*

Two more are reserved on paper: `workflow` (fixed no-AI procedures) and
`human-proxy` (a person behind the same contract as an agent).

The design evolved here, and the docs show their age honestly: the oldest runtime doc
presents the step loop as *the* agent; the envelope doc demotes it to one kind among
several; and the execution suite's decision record (2026-07-26) settles the current
division: **real work runs as `cli` sessions**, with the step loop as the simpler
native runtime.

## The `cli` runtime and the subscription constraint

One practical constraint shapes today's system more than any architectural diagram:
**there is no pay-per-use API key** — an API key being the kind of account
credential that lets a program bill AI usage per individual request. The operator's
machine has the Claude Code
program logged in under a personal subscription. So each working agent is actually a
**wrapped, supervised Claude Code conversation** — in the runtime doc's words, "the
CLI session is the agent's brain and loop; the adapter around it observes, meters,
gates, and reports."

Per assignment, the adapter: fetches the brief into the workspace; **generates** the
session's entire configuration from the envelope — which tools it may use, which
files it may touch, and the one communication channel back to Canopy ("compiled,
never authored": the worker cannot vote on its own permissions); starts the session;
records every **turn** (one back-and-forth exchange) as a metered step; checks the
budget between turns; and confirms the deliverable was submitted when the session
declares itself done. A paused assignment is a *suspended conversation*, not lost
work — resuming injects the answer and continues where it left off.

The honest trade-offs of the subscription route: Canopy cannot approve each
individual AI request *before* it happens — it meters and brakes at turn boundaries,
so one turn can overshoot a budget (known debt E-D1); costs are provider-reported
rather than independently measured; and the session's login credential lives on this
machine in a settings ("config") folder a hostile local process could read —
mitigated today by a
dedicated revocable login and full audit, properly fixed only by the future container
tier. [Doc 05](05-keeping-it-safe-and-on-track.md) takes up all three.

**Our running example, closed:** the engineer's node is `cli`. At dispatch, the
adapter generates a session whose permitted commands are exactly the engineer's
grants — edit its own worktree, run *unit* tests only, nothing else — and whose only
outside line is Canopy's own channel. The engineer codes inside its locked workshop;
every turn is metered; the acceptance tests it cannot run are waiting for QA.

---

**Where this comes from:**
[actuation/topology.md](../actuation/topology.md) (control/data plane, the first two
chokepoints) ·
[actuation/agent-profile.md](../actuation/agent-profile.md) (profiles, Secret Store) ·
[actuation/control-plane.md](../actuation/control-plane.md) (actuator, directory,
gateway, reconciler) ·
[actuation/data-plane.md](../actuation/data-plane.md) (router, bus; the A2A layer —
historical) ·
[actuation/sandbox.md](../actuation/sandbox.md) (the locked workshop, soft isolation) ·
[actuation/workspace.md](../actuation/workspace.md) (the desk, artifacts) ·
[actuation/agent-runtime.md](../actuation/agent-runtime.md) (the `loop` runtime) ·
[actuation/agent-envelope.md](../actuation/agent-envelope.md) (envelope, grants, risk
classes, the tier ladder and no-internet rule, runtime kinds, worktrees — with
[actuation/phase3-debts.md](../actuation/phase3-debts.md) D5) ·
[execution/cli-runtime.md](../execution/cli-runtime.md) (the wrapped session, turns,
the subscription constraint, the trusted-local waiver) ·
[execution/README.md](../execution/README.md) (the no-API-key constraint) ·
[actuation/phase3-debts.md](../actuation/phase3-debts.md) (what shipped vs. what the
older docs describe).
