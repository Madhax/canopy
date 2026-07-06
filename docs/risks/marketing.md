# Risk Context: Marketing — Being Found, Understood, and Chosen

Canopy will launch into the most crowded category in software: agent orchestration, 2026. The marketing risks are not about ad budgets; they are about *position* — whether the project can state, in one breath, why it exists when Paperclip, CrewAI-descendants, and the platforms' own multi-agent features already exist.

## MK-1 — Category crowding and the Paperclip shadow *(Major · High)*

**The risk.** Canopy's own docs cite Paperclip as the reference architecture — an established, open-source, MIT-licensed "control plane for AI-agent companies" with community, plugins, and traction. To an outside observer, Canopy is "Paperclip minus maturity." Simultaneously, the platform vendors (Anthropic, Google, OpenAI) keep absorbing orchestration into their products and SDKs; every absorption shrinks the independent layer's oxygen. The worst position is *undifferentiated middle*: heavier than a library, less proven than Paperclip, less integrated than the platforms.

**Derisking modifications.**
- **State the differentiation in domain terms, loudly.** Canopy's actual differences from Paperclip are real and principled: the chart is *executable structure* (topology enforced at runtime), communication/delegation are *mediated invariants* (not conventions), economics are *mechanical* (metered between steps, not reported), and deliverables are *contracts* (artifact/attestation, not status updates). Paperclip is a task manager that agents use; Canopy is a machine whose shape is the program. Write this comparison page early, respectfully, and keep it current — the docs' own "If OpenClaw is an employee, Paperclip is the company" framing suggests Canopy's line: **"Paperclip manages the company. Canopy *is* the company."** (Sharpen with care.)
- **Treat platform-native orchestration as a substrate, not a rival:** Canopy's adapters can *hire* platform agent runtimes as workers (the roadmap's CLI-agent adapters). The pitch then survives platform absorption: whatever agents exist, Canopy gives them an org, a budget, and an audit trail.
- **Don't launch until one hero use case demonstrably works** (see `usefulness.md`); category-crowded launches get one look.

## MK-2 — The name *(Manageable · High)*

**The risk.** "Canopy" is heavily collided: an accounting-practice suite, a security company, parenting software, real-estate tools, and more share the name. SEO will be brutal; trademark in software classes is plausibly contested. This is boring and fixable now, expensive later.

**Derisking modifications.** Reserve a distinctive handle everywhere now (e.g. `canopy-org`, `canopyhq`, or a qualified brand like "Canopy Org"); check USPTO/EUIPO classes before printing the name into APIs (`org://` refs, `canopy.organization` kinds are internal enough to survive a rename, but rename cost grows weekly); decide by end of Phase 2.

## MK-3 — Demo appeal vs. retention ("SimCity for agents") *(Major · Medium)*

**The risk.** A glowing org chart with agents lighting up is *extremely* shareable — expect a strong HN/X spike — and spikes convert badly when the second session disappoints (`usefulness.md` U-2). A viral toy reputation is sticky and hard to relaunch out of.

**Derisking modifications.**
- Sequence the public moments: quiet alpha with 5–10 design partners on the hero use case → publish the **benchmark results** (`problem-fit.md` PF-1) as the launch artifact → *then* the pretty demo. Numbers first, spectacle second, so the spectacle has a spine.
- Build the demo around **money**: the burn-down of a real intent, the hard-stop firing, the approval gate catching a publish. Governance theater is differentiating; activity theater is commodity.
- The mock provider (register move #4) doubles as a **zero-key playground**: a hosted or `docker run` demo org anyone can poke without spending — top-of-funnel without API-key friction.

## MK-4 — Open-source GTM without a community plan *(Manageable · Medium)*

**The risk.** "Open source it and they will come" fails silently. Paperclip's visible machinery (Discord, contribution paths, plugin marketplace, PR discipline) is a community *product* that took deliberate work. Canopy has a catalog designed for community extension (roles/archetypes as data) but no stated path for contributions, and a solo maintainer is a bus-factor-one review bottleneck.

**Derisking modifications.**
- The **catalog is the community wedge** — contributing a role or formation is markdown + frontmatter, reviewable by non-engineers, exactly the low-friction contribution ladder young projects need. Publish contribution templates the day the frontmatter pass lands.
- Adopt Paperclip-grade contribution hygiene early (PR templates, roadmap-coordination norms) — it is copyable process, and the docs already admire it.
- Pick one channel and own it (probably X + a monthly build-log); breadth is a full-time job the project can't fund.

## MK-5 — The pitch is abstract *(Manageable · Medium)*

**The risk.** "A framework for building AI-agent organizations as literal org charts" describes mechanism, not outcome. Mechanism pitches select for hobbyists (see PF-3). Every existing doc leads with the model, not the moment of value.

**Derisking modifications.** Rewrite the README top around one concrete narrative ("You told your org 'hold first-response under 2 hours.' Here's the night shift it ran, what it cost, and the three things it asked permission for.") and keep "the chart is the system" as the second beat — the *how* behind a *what* people want. Test five one-liners on strangers; keep the one they can repeat back.
