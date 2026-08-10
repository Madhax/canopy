# Canopy in Plain English — a companion series

This series explains how Canopy works, in ordinary language, for a reader with no
software background. It does not replace the design documents in `docs/`. It sits
beside them, untouched, and translates them.

## Who this is for

You — the operator. The person who owns a Canopy organization, gives it work, approves
its plans, and pays its bills. If you have ever found the design docs precise but
impenetrable, this series is the readable path through the same material.

No document here assumes you can read code. Every technical term is defined the first
time it appears, and again in the [glossary](glossary.md).

## What Canopy is, in one sentence

Canopy lets one person draw a company org chart — boxes for employees, lines for who
reports to whom — and then brings that chart to life, with an AI worker in every box,
so that typing one request to the top box makes real work flow down the chart and
finished, reviewed, fully-costed results flow back up.

## How to read this series

Read [01 — What is Canopy?](01-what-is-canopy.md) first. It is the whole system in two
pages. If you read nothing else, read that.

Then the series follows the life of a piece of work:

| Doc | Question it answers |
|---|---|
| [01 — What is Canopy?](01-what-is-canopy.md) | The whole system in one story. |
| [02 — The organization](02-the-organization.md) | Who works here? Orgs, roles, teams, managers, and the chart editor. |
| [03 — How work flows](03-how-work-flows.md) | How a request becomes tasks, and how results come back for review. |
| [04 — How agents run](04-how-agents-run.md) | What an AI worker physically is, and what walls it lives inside. |
| [05 — Keeping it safe and on track](05-keeping-it-safe-and-on-track.md) | What could go wrong, and what actually stops it. |
| [06 — Status and direction](06-status-and-direction.md) | What is built today vs. designed on paper, and where the roadmap points. |
| [Glossary](glossary.md) | Every Canopy term, alphabetized, in one or two plain sentences. |

## The running example

Documents 02–05 carry one example all the way through: **the operator asks the org to
"add CSV export to the report endpoints of target-app; all tests must pass."** In
ordinary words: add a download-as-CSV option (CSV is a simple spreadsheet-style file)
to the report endpoints — the part of a small practice web service that serves up
reports. A small software team — a lead, an engineer, and a QA (quality-assurance)
tester — plans it, builds it, tests it, fails it once, fixes it, and merges it with
the operator's consent.

We use this example rather than inventing a new one because it is the design's own
canonical demo: the original documents (`execution/mvp.md`, `execution/target-app.md`
and others) walk this exact story step by step, so every beat of our version can be
traced to a source rather than imagined.

## The honesty rules this series follows

The design docs describe a mix of running software, near-term plans, and long-range
vision — and they don't always say which is which. This series does. Three rules:

1. **Roadmap is never presented as reality.** Where a feature is designed but not
   confirmed built, the text says so in-line: "the design calls for X; today the
   system does Y."
2. **Contradictions are named, not smoothed over.** Where two design docs disagree
   (and in a few places they do), we say what each one says and which is likely
   current. [Doc 06](06-status-and-direction.md) collects these.
3. **Nothing is invented.** Every claim traces to the design docs, read through three
   detailed analyses of them (actuation; organization & operator; execution engine &
   safety). Each companion doc ends with a "Where this comes from" list.

Two vocabulary choices, made once, used everywhere: the human in charge is the
**operator** (some docs say "the user" — same person), and one back-and-forth exchange
with the AI is a **turn** (an older doc says "tick" — we standardize on turn).

## Source map: every design doc → where this series explains it

**Top-level docs (`docs/`)**

| Original document | Explained in |
|---|---|
| [README.md](../README.md) — map of the docs, catalog layering rule | [02](02-the-organization.md) §"The catalog" |
| [domain-model.md](../domain-model.md) — the rulebook of concepts and invariants | [02](02-the-organization.md), [03](03-how-work-flows.md) |
| [archetypes.md](../archetypes.md) — the 26 ready-made company types | [02](02-the-organization.md) §"Archetypes" |
| [roles.md](../roles.md) — the job descriptions (about 87 by actual count; several design docs say ~75 — another counting drift) | [02](02-the-organization.md) §"Roles" |
| [formations.md](../formations.md) — the 17 pre-wired team blueprints ("formations") | [02](02-the-organization.md) §"Teams and formations" |
| [manager-responsibilities.md](../manager-responsibilities.md) — what managers can and can't do (proposal) | [02](02-the-organization.md) §"Managers", [03](03-how-work-flows.md) §"Steering", [06](06-status-and-direction.md) |
| [use-cases.md](../use-cases.md) — 31 things you can ask for on day one | [02](02-the-organization.md) §"What you can ask for" |
| [org-chart-editor.md](../org-chart-editor.md) — the drawing tool (built) | [02](02-the-organization.md) §"The org chart editor" |
| [phases.md](../phases.md) — Build → Actuate → Execute | [01](01-what-is-canopy.md), [06](06-status-and-direction.md) |
| [org-roadmap.md](../org-roadmap.md) — the self-hosting ladder (aspirational) | [06](06-status-and-direction.md) §"Where the roadmap points" |
| [testing.md](../testing.md) — how the system stays correct without spending money | [05](05-keeping-it-safe-and-on-track.md) §"Tested like money depends on it" |

**Actuation docs (`docs/actuation/`)**

| Original document | Explained in |
|---|---|
| [README.md](../actuation/README.md) — the actuation suite's map and goals | [04](04-how-agents-run.md) |
| [topology.md](../actuation/topology.md) — control plane vs. data plane, the chokepoints | [04](04-how-agents-run.md) §"Head office and workshop floor" |
| [agent-profile.md](../actuation/agent-profile.md) — which AI "brain" each node gets; secret keys | [04](04-how-agents-run.md) §"The brain is chosen at head office" |
| [control-plane.md](../actuation/control-plane.md) — the head office's departments | [04](04-how-agents-run.md) §"Bringing the chart to life" |
| [data-plane.md](../actuation/data-plane.md) — how agents talk (router, bus; A2A — now historical) | [04](04-how-agents-run.md) §"How agents talk" |
| [sandbox.md](../actuation/sandbox.md) — the locked workshop | [04](04-how-agents-run.md) §"The sandbox", [05](05-keeping-it-safe-and-on-track.md) |
| [agent-runtime.md](../actuation/agent-runtime.md) — the worker's day, step by step (`loop` runtime) | [04](04-how-agents-run.md) §"Runtime kinds" |
| [agent-envelope.md](../actuation/agent-envelope.md) — the capability model: grants, tiers, runtime kinds | [04](04-how-agents-run.md) §"The envelope", [05](05-keeping-it-safe-and-on-track.md) |
| [workspace.md](../actuation/workspace.md) — the desk, and how work leaves it | [04](04-how-agents-run.md) §"The workspace" |
| [threat-model.md](../actuation/threat-model.md) — what could go wrong, and what honestly stops it | [05](05-keeping-it-safe-and-on-track.md) §"The threat model" |
| [roadmap.md](../actuation/roadmap.md) — build order and planned swaps | [06](06-status-and-direction.md) |
| [phase3-debts.md](../actuation/phase3-debts.md) — the IOU ledger; best in-repo record of what shipped | [06](06-status-and-direction.md) §"How to check status yourself" |

**Execution docs (`docs/execution/`)**

| Original document | Explained in |
|---|---|
| [README.md](../execution/README.md) — Phase 3's map; the no-API-key constraint | [03](03-how-work-flows.md), [04](04-how-agents-run.md) §"The subscription constraint" |
| [work-model.md](../execution/work-model.md) — the nouns of work and their rules | [03](03-how-work-flows.md) |
| [engine.md](../execution/engine.md) — the office manager that routes all work | [03](03-how-work-flows.md) §"The engine" |
| [cli-runtime.md](../execution/cli-runtime.md) — how a chat session becomes a supervised employee | [04](04-how-agents-run.md) §"The `cli` runtime", [05](05-keeping-it-safe-and-on-track.md) |
| [mvp.md](../execution/mvp.md) — the first full demo (the CSV-export story) | [03](03-how-work-flows.md), [05](05-keeping-it-safe-and-on-track.md) |
| [target-app.md](../execution/target-app.md) — the practice project ("the driving school's car") | [03](03-how-work-flows.md) §"Review", [05](05-keeping-it-safe-and-on-track.md) |
| [operator-experience.md](../execution/operator-experience.md) — the operator's cockpit (designed, not built) | [02](02-the-organization.md) §"What the operator sees", [03](03-how-work-flows.md) |
| [e8-runbook.md](../execution/e8-runbook.md) — Canopy's first work on itself, by hand | [05](05-keeping-it-safe-and-on-track.md), [06](06-status-and-direction.md) |
| [amendments-2026-07-26.md](../execution/amendments-2026-07-26.md) — five design fixes found before building | [03](03-how-work-flows.md), [06](06-status-and-direction.md) |

**Risk docs (`docs/risks/`)**

| Original document | Explained in |
|---|---|
| [README.md](../risks/README.md) — the ranked register of "what could kill this" | [05](05-keeping-it-safe-and-on-track.md) §"The top known risks" |
| [problem-fit.md](../risks/problem-fit.md), [usefulness.md](../risks/usefulness.md), [marketing.md](../risks/marketing.md), [design.md](../risks/design.md), [architecture.md](../risks/architecture.md), [implementation.md](../risks/implementation.md), [scalability.md](../risks/scalability.md) | [05](05-keeping-it-safe-and-on-track.md) §"The top known risks", [06](06-status-and-direction.md) |

---

*This series was produced from three accepted plain-English analyses of the design
docs (actuation layer; organization & operator layer; execution engine & safety
layer), verified against the originals at repo commit `0777e9d` — a fixed snapshot of
the repository. It adds files only — no existing document was modified.*
