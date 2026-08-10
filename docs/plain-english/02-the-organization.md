# 02 — The organization

*Who works here: orgs, roles, teams, managers — and the tool you draw them with.*

Throughout this doc we build the company that will handle our running example: the
operator wants to ask for CSV export on the report endpoints of the practice project
(the reports feature, in plain words). By the end, a three-worker software team
exists on paper, ready to be brought to life.

## The operator

The **operator** is the human who owns and supervises a Canopy organization. You
create it, give it work, approve its plans, resolve its alarms, and pay its bills.
You are also the only one who can permanently change its structure — no agent,
however senior its box on the chart, may reorganize the company. (Some design docs
call this person "the user." Same person; this series says operator.)

## Organizations and nodes

An **organization** is one company instance: a named org chart of AI workers — say,
"Acme Software." The chart is a tree: every worker has exactly one manager, all the
way up to a single root box (the "CEO" position, where your requests usually enter).

A box on the chart is called a **node**. When the org is live, each node is occupied
by an **agent** — one AI worker with a job, a manager, a budget, a private workspace,
and a durable memory of its past work.

Organizations can nest. A child organization can be mounted inside a parent — like a
department, or a franchise location — and the parent sees only the child's top box,
not its internals. The design calls this "sub-org opacity," and it is the intended
mechanism for scale: a big company is a parent org with child orgs mounted into its
chart.

## Roles: jobs as data, not code

A **role** is a prebuilt job description: instructions, duties, permitted tools, an
expected kind of output, and a default salary. The catalog ships about 87 of them by
actual count (several design docs say ~75 — another counting drift, of the kind
[doc 06](06-status-and-direction.md) catalogs), grouped into domains — engineering,
sales, healthcare, physical operations, and so on.
A role is pure data. Nothing about an agent's job is programmed; an agent is "hired
from" a role the way a person is hired into a job description.

The organizing discipline behind every role is **duty → deliverable**: no
responsibility counts unless doing it produces something checkable. A QA engineer's
duties read "write test plans → TestPlan; execute verification → TestReport." A line
cook's read "prepare station items → attested." Deliverables come in two kinds:

- an **artifact** — a produced work product: a document, a code change, a report;
- an **action attestation** — a signed "I did it, here's the evidence" claim, for
  jobs whose output is a real-world action rather than a file (a sales call, a
  cooked order, wired outlets).

This is what makes AI work reviewable: every job has a contract, so progress can be
checked against the contract instead of taken on faith.

## Salaries

Each node has a **salary** — not money, but a token allowance policy (**tokens** are
the unit AI computation is billed in). A salary sets the default budget per piece of
work, a warning threshold, and a hard stop. [Doc 03](03-how-work-flows.md) shows the
enforcement; one honesty note now: the specific token numbers in today's catalog are
explicitly placeholders, not calibrated values.

## Teams and formations

A **team** is a manager plus its direct reports. Teams are never drawn separately —
they simply *are* the chart's shape. The team is also the communication boundary:
teammates may talk (through the central **Message Router** — see
[doc 04](04-how-agents-run.md)); strangers' messages route up through managers.

A **formation** is a reusable team blueprint: one manager role plus member roles,
pre-wired with how work flows between them. Dropping a formation onto the chart
stamps out the whole mini-team in one action. The catalog describes 17 of them —
product-engineering pod, incident-response squad, newsdesk, franchise shift, and so
on. (One doc says 16 — a counting drift between two documents; the newest formation
was added after the editor spec was written.)

Formations carry a quietly important idea: the **resolution policy** on the "B waits
for A" links between teammates (the design docs call these links **edges**). A
**verify** link starts the downstream worker the
moment upstream work is *submitted* — because the downstream job *is* the review (QA
testing code, a fact-checker checking a story). A **consume** link waits for the
manager's *acceptance* — because the downstream job *builds on* the output and
shouldn't start from something that might be rejected. Quality control is thus wired
into the team's structure, not left to memory.

**Our running example:** the operator stamps the **product-engineering pod** formation
onto a new chart: an engineering lead managing a backend engineer, a frontend
engineer, and a QA engineer, with QA's work pre-wired as a *verify* link on the
engineers' — QA starts the moment code is submitted, and the lead won't accept
anything before the review is in. (In the design's minimal demo the pod is trimmed to
three: lead, one engineer, QA.)

## Archetypes: the menu of company types

An **archetype** is a ready-made *kind* of company, defining which roles are on the
palette and which formations it suggests. The catalog lists 26, in five families:
tech enterprise (product engineering, security operations, data & analytics…),
physical world (franchise operations, construction, a medical clinic…), knowledge &
community (research lab, newsroom, curriculum studio…), professional services
(agency, consultancy, law practice), and corporate chassis (recruiting, finance,
legal — support departments designed to mount inside any parent company).

## The catalog, and its layering rule

The **catalog** is the shipped library of all of the above — archetypes, roles,
formations, and use-case recipes. Data, not code. It obeys a strict layering rule:
**use cases** (things you can ask for) are satisfied by **archetypes**, which are
built from **formations**, which are built from **roles**, which all obey the
**domain model** — the rulebook underneath everything. If something you should be
able to ask for can't be expressed with shipped parts, that is a gap in the catalog,
"not a user error."

## What you can ask for

The design keeps itself honest with a list of 31 concrete requests a user should be
able to make out of the box, each mapped to the formation or archetype that absorbs
it — from "ship a feature end-to-end" (our example) to "run a hiring pipeline,"
"close the monthly books," "staff Saturday's service shift." Thirty of the 31 are
expressible with today's catalog; the last ("clone a working organization") depends
on a deliberately deferred feature called Blueprints — saving a whole org as a
reusable template.

## Managers and reports

A **manager** is any agent with reports; a **report** is an agent someone manages.
Managers do exactly what good human managers do, and structurally *cannot* do their
reports' work — they are given no tools for it. As the manager-responsibilities
proposal puts it, a manager has complete authority at the *edges* of a task
(briefing, gating, acceptance) and none in the *middle*. A manager:

- **decomposes** incoming work into subtasks and issues written briefs;
- **declares dependencies** between its reports' tasks;
- **accepts or rejects** each deliverable against its contract;
- **unblocks**: answers questions, resolves waiting states, escalates what it can't
  answer.

Managerial authority runs down the chart only — a manager may delegate only to its
own reports. And one thing no manager may ever do: change the team. Restructuring is
reserved to you.

An honest flag: a design review found that managers have full authority at the
*edges* of a task (briefing, acceptance) but little in the *middle* — the ability to
interrupt, redirect, or kill a report's running work. A proposal document
(`manager-responsibilities.md`) adds these mid-flight powers (intervene, scope-drift
alarms, plan-review checkpoints, standing team rules). Parts of it — notably
plan-review checkpoints — appear to have been folded into the rulebook already;
other parts remain proposals. Where these features matter in this series, we flag
their status.

## The org chart editor

The **org chart editor** is the first shipped piece of Canopy: a drag-and-drop canvas
where you build all of the above before anything runs. Pick an archetype, drag roles
and formations from a palette, draw reporting lines and dependencies, mount child
orgs, set salaries, save.

Its central discipline: **the editor draws only what the rules can run.** Illegal
structures are unrepresentable or rejected as you draw — a second boss for one worker
cannot even be expressed; a dependency between different teams' members is refused
with an explanation (cross-team sequencing belongs one level up). Drafts always save,
even with errors — you never lose work to validation — but export refuses until the
document is fully legal.

"The editor is the tool; the document is the product": what you actually produce is
the **organization document** — a saved file capturing chart, role assignments, and
salaries (deliberately excluding memory, secrets, and in-flight work). That file is
what actuation ([doc 04](04-how-agents-run.md)) brings to life.

**Our running example:** the operator saves the pod as an organization document. On
paper: one lead, engineer(s), one QA, salaries set, QA's verify link wired. Nothing
is running yet.

## What the operator sees and does

Day to day, the design gives the operator a cockpit called **Operate mode**, built
around five questions:

- *What is my organization doing?* — **Mission Control**: the org chart lit up live;
  each box dim when idle, pulsing when working, amber when waiting, red when dead,
  with queue depth (how many tasks are waiting) and a budget arc on every node.
- *What exactly is one agent up to?* — the **Agent Inspector**: open any worker and
  see its instructions, current assignment (with the chain of "why" up to your
  original request), plan, spending, waiting states, memory (with a reset button —
  "backfilling the position"), live session log, and a read-only view of its files.
- *Give it work, watch it work* — the **Intent Console**: type a request, see a
  projected-cost hint, approve the proposed breakdown before money moves, then watch
  a living outline of the whole engagement, where any line can take a note or an
  intervention.
- *What needs me?* — the **Inbox**: only items genuinely blocked on you.
- *Where is the money going?* — the **Cost Explorer**: spend by request, by node, by
  model, over time, every number drillable to individual steps.

**Status, honestly:** this cockpit is a *design*, written in confident present tense
but belonging to Phase 3 — the third act, Execute ("designed," per the phases doc,
not built). The chart
editor is built; the Operate screens should be treated as the intended experience
unless the current build says otherwise. See [doc 06](06-status-and-direction.md).

---

**Where this comes from:**
[domain-model.md](../domain-model.md) (organizations, agents, teams, salaries, the
rulebook) · [README.md](../README.md) (catalog layering, duty → deliverable) ·
[archetypes.md](../archetypes.md) (the 26 company types) ·
[roles.md](../roles.md) (the 87 roles) ·
[formations.md](../formations.md) (formations, verify/consume) ·
[manager-responsibilities.md](../manager-responsibilities.md) (manager powers and
gaps — a proposal) · [use-cases.md](../use-cases.md) (the 31 requests) ·
[org-roadmap.md](../org-roadmap.md) (30-of-31 expressible today) ·
[org-chart-editor.md](../org-chart-editor.md) (the editor, the organization document) ·
[execution/operator-experience.md](../execution/operator-experience.md) (Operate
mode — designed, not built).
