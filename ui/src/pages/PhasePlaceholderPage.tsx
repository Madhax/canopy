import { LeafMark } from "../components/AppHeader";

interface Props {
  phase: number;
  title: string;
  tagline: string;
  intro: string;
  does: { heading: string; body: string }[];
  produces: string;
}

// Described-but-not-yet-available phase screen, backed by docs/phases.md.
export function PhasePlaceholderPage({ phase, title, tagline, intro, does, produces }: Props) {
  return (
    <div className="mx-auto max-w-3xl px-8 py-10">
      <div className="mb-8 flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-full bg-surface-2 text-lg font-semibold text-ink-muted">
          {phase}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-ink">{title}</h1>
            <span className="rounded-full border border-warn/40 bg-warn/10 px-2 py-0.5 text-[11px] font-medium text-warn">
              Coming soon
            </span>
          </div>
          <p className="text-sm text-ink-muted">{tagline}</p>
        </div>
      </div>

      <p className="mb-8 leading-relaxed text-ink">{intro}</p>

      <div className="grid gap-4 sm:grid-cols-2">
        {does.map((d) => (
          <div key={d.heading} className="rounded-xl border border-border bg-surface p-4">
            <h3 className="mb-1 text-sm font-semibold text-ink">{d.heading}</h3>
            <p className="text-sm leading-relaxed text-ink-muted">{d.body}</p>
          </div>
        ))}
      </div>

      <div className="mt-8 flex items-start gap-3 rounded-xl border border-accent/30 bg-accent/5 p-4">
        <LeafMark size={18} />
        <div className="text-sm">
          <span className="font-medium text-ink">Produces: </span>
          <span className="text-ink-muted">{produces}</span>
        </div>
      </div>

      <p className="mt-6 text-xs text-ink-subtle">
        See <code className="rounded bg-surface-2 px-1">docs/phases.md</code> for the full design of
        the Build → Actuate → Execute trajectory.
      </p>
    </div>
  );
}

export function ExecutePage() {
  return (
    <PhasePlaceholderPage
      phase={3}
      title="Execute"
      tagline="Give the organization a standing intent and drive the work through the chart."
      intro="The execution engine hands the root agent a goal and drives the work down the reporting lines until every responsibility ends in something checkable. It never edits the chart — only you, back in Build, make a permanent structural change."
      does={[
        {
          heading: "Seed the intent",
          body: "The operator gives the root a goal; it decomposes into assignments for its reports, and delegation flows down the reporting lines.",
        },
        {
          heading: "Honor the gates",
          body: "Dependency gates hold work until upstream artifacts are accepted; approval gates pause consequential actions; intervention gates surface stalls upward.",
        },
        {
          heading: "Meter the spend",
          body: "Every model and tool call is metered against each agent's budget between steps. Managers see burn rate, progress, and stalls in real time.",
        },
        {
          heading: "Collect deliverables",
          body: "Each discharged responsibility yields an artifact or attestation. Acceptance is contract-based and rolls up the tree.",
        },
      ]}
      produces="completed work — artifacts and attestations — plus a full provenance trail from each spend event up to the root intent."
    />
  );
}
