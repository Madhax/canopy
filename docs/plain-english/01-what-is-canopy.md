# 01 — What is Canopy?

*The whole system in one story. Two pages. Everything here is unpacked in the rest of
the series.*

## A company you draw

Imagine you could hire a whole company by drawing it.

You open a drawing tool and sketch an org chart: a box for a team lead, boxes for an
engineer and a QA (quality-assurance) tester underneath, lines showing who reports to
whom. For each box you pick a job description from a catalog — real ones, with duties
and expected outputs. You give each position a salary. Then you press a button, and
every box on the chart becomes a live AI worker, sitting at its own desk, waiting for
work.

That is Canopy. One person — called the **operator** — owns and supervises this
company. The workers are **agents**: computer programs driven by an AI model, one per
box on the chart.

Canopy works in three acts, and the boundaries are strict:

1. **Build.** You draw the chart. Nothing runs. The output is a saved document
   describing the company — structure, jobs, salaries.
2. **Actuate.** Canopy reads that document and brings it to life: one running agent
   per box, each with its own budget, its own private workspace, and its own mailbox.
   The company is hired and waiting. Still, no work happens.
3. **Execute.** You type a request, and the machine starts moving.

## One request, end to end

You type a single sentence to the top box — say, *"Add CSV export to the report
endpoints of target-app; all tests must pass."* In ordinary words: add a
download-as-CSV option (CSV is a simple spreadsheet-style file) to the report
endpoints — the part of a small practice web service that serves up reports. In
Canopy this request is called an **intent**, and it is the root of everything that
follows: every task and every cent of spending will trace back to it.

The lead doesn't just start typing code. Like a real manager, it breaks your request
into subtasks: one for the engineer ("implement this; deliver a code change"), one for
the QA tester ("verify it; deliver a test report"), with the QA task explicitly
waiting on the engineer's. Each subtask — called an **assignment** — carries written
instructions, a definition of done, and its own budget.

Before any of that is funded, the proposed breakdown lands in front of *you*. You see
the actual subtasks — instructions, budgets, dependencies — and approve, edit, or
reject them. Only on your approval does money move and work start.

## Locked workshops

Each agent works alone, inside walls.

An agent's workspace is private — no agent can ever read another's files. Its tools
are exactly the ones its job grants, and nothing else: the QA tester can run the full
test suite but cannot edit code; the engineer can edit code but cannot run the
deciding acceptance tests — the final pass/fail checks that decide whether the whole
feature is done; the lead has no coding tools at all. An agent never holds a
password or an account key — those live encrypted at head office and are attached to
requests on the agent's behalf, out of its sight. And agents cannot chat freely:
every message passes through a central router that only allows conversations the org
chart draws — managers with their own reports, and you with anyone.

The point of all this is a phrase from the design: safety **"by construction, not by
convention."** The system is physically built so that an agent *cannot* overstep,
rather than politely asked not to.

## Budgets with teeth

Every agent's salary is a spending allowance, measured in **tokens** — the unit AI
computation is billed in, the company's currency. Every assignment gets a funded
meter. As the agent works, every step is metered. At 80% spent, you see an amber
warning. At 100%, the work is mechanically halted — the agent cannot keep spending,
because the platform, not the agent, holds the brake. You (or the agent's manager,
within a small bounded allowance) decide: top it up, redirect it, or cancel it.

## Work comes back for review

The engineer finishes and submits its code change. That wakes the QA tester, who runs
the full test suite and submits a report. The lead reviews both and — this is the
heart of the system — **accepts or rejects** against the written definition of done.
Rejected work goes back, and the redo burns the *worker's* budget if the instructions
were unchanged, or the *manager's* if the instructions had to be rewritten. Quality
failures and scoping failures each land on the right desk.

Finished work is filed as **artifacts**: permanent, versioned work products with a
recorded history of who made what, for which task, at what cost. Anything with
real-world consequences — merging code into the main line (adding it to the official
shared copy of the program), contacting a customer — pauses for your explicit consent
first, and records the consent alongside the evidence.

At the end you get a deliverable card: the results, the total cost, and the full
paper trail from your one typed sentence down to every individual spend. You can ask,
of any token spent anywhere: *who spent this, on what, and why?* — and get an answer.

## Where things stand

Not all of this runs today. The drawing tool (act one) is built. The machinery behind
acts two and three has been landing milestone by milestone, and some of the operator
screens described above are still designs on paper. [Doc 06](06-status-and-direction.md)
gives the honest inventory of built versus designed.

That's Canopy: a company you draw, workers in locked workshops, budgets with teeth,
and a boss — you — who reviews everything that matters.

---

**Where this comes from:** [phases.md](../phases.md) (the three acts) ·
[README.md](../README.md) (the core idea) ·
[domain-model.md](../domain-model.md) (intents, assignments, budgets, review) ·
[actuation/README.md](../actuation/README.md) and
[actuation/topology.md](../actuation/topology.md) ("by construction", the chokepoints) ·
[execution/mvp.md](../execution/mvp.md) (the CSV-export story) ·
[execution/engine.md](../execution/engine.md) (plan review, acceptance).
