// Cadences (E7, operator-experience.md §4): the small management list — name, cron, target,
// last/next fire, enabled — plus the create form that "make this recurring" on a completed
// intent prefills (the U-1 retention hook placed where satisfaction is highest).
import { useEffect, useState } from "react";
import {
  useCadences,
  useCreateCadence,
  useDeleteCadence,
  useUpdateCadence,
  type Cadence,
} from "../../api/work";
import { Button } from "../common";

export interface CadenceSeed {
  intentText: string;
  nodeId: string | null;
}

const DEFAULT_CRON = "0 9 * * 1-5"; // weekdays 09:00 UTC — the daily-standup shape

function fmtWhen(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

// ---------------------------------------------------------------- presentational
export function CadencePanel({
  cadences,
  nodeName,
  seed,
  busy,
  error,
  onCreate,
  onToggle,
  onDelete,
  onSeedConsumed,
}: {
  cadences: Cadence[];
  nodeName: (id: string) => string;
  seed?: CadenceSeed | null;
  busy?: boolean;
  error?: string | null;
  onCreate: (body: { name: string; cron: string; intentText: string; nodeId: string | null }) => void;
  onToggle: (cadence: Cadence) => void;
  onDelete: (cadenceId: string) => void;
  onSeedConsumed?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [cron, setCron] = useState(DEFAULT_CRON);
  const [intentText, setIntentText] = useState("");
  const [nodeId, setNodeId] = useState<string | null>(null);

  // "Make this recurring" hands us the completed intent's text + target.
  useEffect(() => {
    if (!seed) return;
    setOpen(true);
    setIntentText(seed.intentText);
    setNodeId(seed.nodeId);
    setName(seed.intentText.slice(0, 40));
    setCron(DEFAULT_CRON);
    onSeedConsumed?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed]);

  return (
    <section className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink">
          Cadences
          {cadences.length > 0 && (
            <span className="ml-2 text-[11px] font-normal text-ink-muted">
              {cadences.length} scheduled
            </span>
          )}
        </h2>
        <Button size="sm" onClick={() => setOpen((v) => !v)}>
          {open ? "Close" : "New cadence"}
        </Button>
      </div>

      {open && (
        <form
          className="mt-3 flex flex-col gap-2 rounded-md border border-border bg-canvas p-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (!name.trim() || !intentText.trim()) return;
            onCreate({ name: name.trim(), cron: cron.trim(), intentText: intentText.trim(), nodeId });
          }}
        >
          <div className="flex gap-2">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Name — e.g. daily standup"
              className="flex-1 rounded-md border border-border bg-surface px-2 py-1.5 text-sm outline-none focus:border-accent"
            />
            <input
              value={cron}
              onChange={(e) => setCron(e.target.value)}
              placeholder="cron (UTC)"
              title="minute hour day-of-month month day-of-week, UTC"
              className="w-36 rounded-md border border-border bg-surface px-2 py-1.5 font-mono text-xs outline-none focus:border-accent"
            />
          </div>
          <input
            value={intentText}
            onChange={(e) => setIntentText(e.target.value)}
            placeholder='Intent to fire — e.g. "Report status of all current work"'
            className="rounded-md border border-border bg-surface px-2 py-1.5 text-sm outline-none focus:border-accent"
          />
          {error && <p className="text-xs text-danger">{error}</p>}
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-ink-muted">
              Target: {nodeId ? nodeName(nodeId) : "org root"}
            </span>
            <Button type="submit" size="sm" variant="primary"
                    disabled={busy || !name.trim() || !intentText.trim()}>
              Schedule
            </Button>
          </div>
        </form>
      )}

      {cadences.length === 0 && !open ? (
        <p className="mt-2 text-xs text-ink-muted">
          No cadences — put this org on a schedule, or make a completed intent recurring.
        </p>
      ) : (
        <ul className="mt-3 flex flex-col gap-2">
          {cadences.map((c) => (
            <li
              key={c.id}
              className={`flex items-center gap-3 rounded-md border border-border px-3 py-2 text-xs ${
                c.enabled ? "bg-canvas" : "bg-canvas opacity-60"
              }`}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2">
                  <span className="font-medium text-ink">{c.name}</span>
                  <code className="font-mono text-[10px] text-ink-muted">{c.cron}</code>
                  <span className="text-[10px] text-ink-muted">
                    → {c.nodeId ? nodeName(c.nodeId) : "org root"}
                  </span>
                </div>
                <div className="mt-0.5 truncate text-[11px] text-ink-muted" title={c.intentText}>
                  {c.intentText}
                </div>
                <div className="mt-0.5 text-[10px] text-ink-subtle">
                  last {fmtWhen(c.lastFiredAt)} · next {c.enabled ? fmtWhen(c.nextFireAt) : "off"}
                </div>
              </div>
              <button
                onClick={() => onToggle(c)}
                title={c.enabled ? "Pause this cadence" : "Resume this cadence"}
                className={`rounded-full border px-2 py-0.5 text-[10px] ${
                  c.enabled
                    ? "border-ok/40 bg-ok/10 text-ok"
                    : "border-border bg-surface text-ink-muted"
                }`}
              >
                {c.enabled ? "on" : "off"}
              </button>
              <button
                onClick={() => onDelete(c.id)}
                title="Delete this cadence"
                className="text-ink-subtle hover:text-danger"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------- wired
export function CadenceSection({
  orgId,
  nodeName,
  seed,
  onSeedConsumed,
}: {
  orgId: string | null;
  nodeName: (id: string) => string;
  seed?: CadenceSeed | null;
  onSeedConsumed?: () => void;
}) {
  const cadences = useCadences(orgId);
  const create = useCreateCadence(orgId);
  const update = useUpdateCadence(orgId);
  const remove = useDeleteCadence(orgId);

  return (
    <CadencePanel
      cadences={cadences.data ?? []}
      nodeName={nodeName}
      seed={seed}
      busy={create.isPending}
      error={create.isError ? (create.error as Error).message : null}
      onCreate={(body) => create.mutate(body)}
      onToggle={(c) => update.mutate({ cadenceId: c.id, body: { enabled: !c.enabled } })}
      onDelete={(cadenceId) => remove.mutate(cadenceId)}
      onSeedConsumed={onSeedConsumed}
    />
  );
}
