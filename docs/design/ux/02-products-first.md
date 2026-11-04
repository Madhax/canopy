# 02 · Products First — the team at work, answered by what it makes

> **Status:** Proposed 2026-08-16 · **Reads with:** `README.md` P1/P6, `01-altitudes-and-navigation.md` (card grammar), `../../domain-model.md` (artifacts/attestations — the objects this elevates), `../../execution/operator-experience.md` §4/§4a (the plan-centric view this inverts)

## 0. The problem

"I cannot easily see what artifacts a team in flight is producing" — because the UI is work-centric: plans, assignments, and gates are primary; artifacts hang *off* plan nodes. But the domain's own thesis is that work is only real as artifacts and attestations. The view inverts: **the product stream is the page; the plan is the explanation.**

## 1. The artifact feed

**UX-11** Per team and per org: a reverse-chronological feed of every Deliverable and ActionAttestation, each a **receipt card** (§2). Filters: engagement, seat, kind, verify-status. The org-level feed is "what did my organization make today" in one scroll — and it is the same corpus `canopy-receipts` reports on weekly, seen live. **UX-12** In-flight visibility: the feed also shows *expected next products* — the current engagement's undischarged contracts ("`TestReport` — expected from QA, in progress, stage 2/3") — so "what should exist soon" and "what exists" read as one list. This is the single strongest answer to "where do I look to know it's working": newest product age + next expected product, top of feed.

## 2. The receipt card

**UX-13** One card format for every product, reused verbatim by the brief, the feed, PR cards, and acceptance asks (`01` §4's evidence object):

- **What**: contract type + title ("`PullRequest` — CSV export for report endpoints"), artifact ref (versioned).
- **Who/where**: seat name + avatar, team color, engagement link.
- **Standing**: verify chips (each verify-dependency's verdict: green `TestReport ✓` / red with the cited failure), acceptance state, rework count if > 0.
- **Cost line**: this deliverable's attributed spend + the engagement running total — glance-class (% and USD), raw tokens forensic.
- **Open**: preview inline (markdown render, diff view with stat — the existing components), full content one click.

**UX-14** A card's verify chips are load-bearing: a deliverable with pending verification renders visually *unfinished* (muted until its verify edges resolve) — the structure of trust made visible, per formation wiring, not per operator memory.

## 3. The engagement page, reorganized

**UX-15** Header: the intent one-liner, status word + reason, **stage-based progress as the primary number** (the F15 lesson — budget is an affordance, not the headline), operator actions (note · intervene · cancel). **UX-16** Body: products rail (the feed, filtered to this engagement) is the widest column; the **plan outline collapses to milestones by default**, expanding to assignments on demand — the living plan remains one click away, not the landing view. **UX-17** Costs become one line with a sparkline (burn against allowance); the cost explorer stays as forensic drill. **UX-18** Liveness: a pulse line per active seat — current stage name + last-step age ("writing · 40s ago") — replacing any urge to stream logs; stall/hold states render in the pulse line's vocabulary (`03` §1), so *quiet-because-waiting* never reads as *working*.

## 4. Standing work, surfaced

**UX-19** The team page shows its standing shape above the feed: purpose line (the doctrine-cascade slot), cadences and triggers as human phrases with next-fire/last-fire ("docs sweep — weekday mornings · last: 2 PRs proposed"), envelope mode chip (`always/graduated/auto`), each editable in place (the screenshot's standing-routine page, in Canopy's grammar). What was settings-buried becomes the team's face — because for a standing org, *the routine is the identity*.

## 5. Open questions

1. Should attestations (merges, publishes, comments) interleave with artifacts in one feed or sit as a second lane? Leaning interleaved with kind filters — one timeline of "things that became real."
2. Artifact diffing across revisions (`@3` vs `@4`) inline — worth it at UX2 or forensic-only? Leaning inline for markdown, forensic for code diffs beyond stat.
3. Does the feed belong on the Home fleet cards too (last product, one line)? Yes per `03` §2 — the same card, smallest form.
