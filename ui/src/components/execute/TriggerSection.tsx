// Triggers (docs/design/standing-teams-ux.md §2): the event-driven half of Standing work.
// Each row states its source as a sentence, its target, its health, and its controls; the
// create card is When → Then → Guardrails with a dry-run before anything is enabled.
import { useState } from "react";
import { useConnectorInstances, type ConnectorInstance } from "../../api/connectors";
import {
  useCheckTrigger,
  useCreateTrigger,
  useDeleteTrigger,
  useDryRunTrigger,
  useTriggers,
  useUpdateTrigger,
  type Trigger,
  type TriggerDryRun,
} from "../../api/work";
import { Button } from "../common";

const DEFAULT_TEMPLATE =
  "Fix the bug reported in {{url}}: {{title}}\n\n{{body}}";

function fmtWhen(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

// ---------------------------------------------------------------- presentational
export function TriggerPanel({
  triggers,
  instances,
  nodeName,
  nodes,
  busy,
  error,
  dryRun,
  onCreate,
  onToggle,
  onDelete,
  onCheck,
  onDryRun,
}: {
  triggers: Trigger[];
  instances: ConnectorInstance[];
  nodeName: (id: string) => string;
  nodes: { id: string; name: string }[];
  busy?: boolean;
  error?: string | null;
  dryRun?: TriggerDryRun | null;
  onCreate: (body: {
    name: string; instanceId: string; intentTemplate: string;
    nodeId: string | null; config: { labels?: string[] };
  }) => void;
  onToggle: (t: Trigger) => void;
  onDelete: (id: string) => void;
  onCheck: (id: string) => void;
  onDryRun?: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [instanceId, setInstanceId] = useState("");
  const [labels, setLabels] = useState("bug");
  const [template, setTemplate] = useState(DEFAULT_TEMPLATE);
  const [nodeId, setNodeId] = useState<string | null>(null);

  const sources = instances.filter((i) => i.enabled && i.packKey === "github");

  return (
    <section className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink">Triggers</h3>
        <Button size="sm" onClick={() => setOpen((v) => !v)} disabled={sources.length === 0}
                title={sources.length === 0 ? "Add a GitHub connector with issue-read first" : undefined}>
          New trigger
        </Button>
      </div>

      {open && (
        <form
          className="mt-3 flex flex-col gap-2 rounded-md border border-border bg-canvas p-3"
          onSubmit={(e) => {
            e.preventDefault();
            onCreate({
              name: name.trim(), instanceId, intentTemplate: template,
              nodeId,
              config: { labels: labels.split(",").map((s) => s.trim()).filter(Boolean) },
            });
            setOpen(false);
            setName("");
          }}
        >
          {/* When */}
          <p className="text-xs font-medium text-ink">When</p>
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
            new issues labeled
            <input value={labels} onChange={(e) => setLabels(e.target.value)}
                   placeholder="bug, docs" aria-label="labels"
                   className="w-28 rounded-md border border-border bg-surface px-2 py-1 outline-none focus:border-accent" />
            in
            <select value={instanceId} onChange={(e) => setInstanceId(e.target.value)} required
                    aria-label="source instance"
                    className="rounded-md border border-border bg-surface px-2 py-1 outline-none focus:border-accent">
              <option value="">— pick a connector —</option>
              {sources.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.name} ({i.config.owner}/{i.config.repo})
                </option>
              ))}
            </select>
          </div>
          {/* Then */}
          <p className="mt-1 text-xs font-medium text-ink">Then submit</p>
          <textarea value={template} onChange={(e) => setTemplate(e.target.value)} rows={3}
                    aria-label="intent template"
                    className="rounded-md border border-border bg-surface px-2 py-1.5 text-xs outline-none focus:border-accent" />
          <p className="text-[10px] text-ink-subtle">
            {"placeholders: {{title}} {{number}} {{url}} {{body}} {{labels}} {{author}}"}
          </p>
          {/* Guardrails */}
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
            to
            <select value={nodeId ?? ""} onChange={(e) => setNodeId(e.target.value || null)}
                    aria-label="target node"
                    className="rounded-md border border-border bg-surface px-2 py-1 outline-none focus:border-accent">
              <option value="">the team root</option>
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>{n.name}</option>
              ))}
            </select>
            <span className="text-ink-subtle">· at most 3 new intents per check; older issues wait their turn</span>
          </div>
          <div className="flex items-center gap-2">
            <input value={name} onChange={(e) => setName(e.target.value)} required
                   placeholder="trigger name — e.g. bug intake" aria-label="trigger name"
                   className="flex-1 rounded-md border border-border bg-surface px-2 py-1 text-xs outline-none focus:border-accent" />
            <Button size="sm" type="submit" variant="primary" disabled={busy || !instanceId}>
              Create
            </Button>
          </div>
        </form>
      )}
      {error && <p className="mt-2 text-xs text-danger">{error}</p>}

      <ul className="mt-2 flex flex-col gap-1.5">
        {triggers.map((t) => {
          const inst = instances.find((i) => i.id === t.instanceId);
          return (
            <li key={t.id} className="rounded-md border border-border bg-canvas px-3 py-2 text-xs">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-ink">⚡ {t.name}</span>
                <span className="text-ink-muted">
                  new issues{(t.config.labels?.length ?? 0) > 0 && ` labeled ${t.config.labels!.join(", ")}`} in{" "}
                  <span className="text-ink">{inst?.name ?? t.instanceId}</span>
                </span>
                <span className="text-ink-subtle">→ {t.nodeId ? nodeName(t.nodeId) : "team root"}</span>
                {t.lastError && (
                  <span className="rounded-full bg-danger/15 px-1.5 text-[10px] text-danger"
                        title={t.lastError}>
                    failing
                  </span>
                )}
                <span className="ml-auto flex items-center gap-1.5 text-[10px] text-ink-subtle">
                  checked {fmtWhen(t.lastCheckedAt)} · fired {fmtWhen(t.lastFiredAt)}
                </span>
              </div>
              <div className="mt-1 flex items-center gap-2">
                <label className="flex items-center gap-1 text-[11px] text-ink-muted">
                  <input type="checkbox" checked={t.enabled} onChange={() => onToggle(t)} />
                  enabled
                </label>
                {onDryRun && (
                  <button type="button" className="text-[11px] text-accent hover:underline"
                          onClick={() => onDryRun(t.id)}>
                    dry run
                  </button>
                )}
                <button type="button" className="text-[11px] text-accent hover:underline"
                        onClick={() => onCheck(t.id)}>
                  check now
                </button>
                <button type="button" className="ml-auto text-[11px] text-danger hover:underline"
                        onClick={() => onDelete(t.id)}
                        title="Intents it fired stay; re-creating it later may re-fire old issues.">
                  delete
                </button>
              </div>
            </li>
          );
        })}
        {triggers.length === 0 && (
          <p className="mt-1 text-xs text-ink-muted">
            No triggers — wire external events (a bug report, an issue) to start work without you.
          </p>
        )}
      </ul>

      {dryRun && (
        <div className="mt-2 rounded-md border border-border bg-canvas p-2 text-xs">
          <p className="font-medium text-ink">
            Dry run — {dryRun.candidates.length} issue{dryRun.candidates.length === 1 ? "" : "s"} would fire
          </p>
          {dryRun.candidates.slice(0, 5).map((c) => (
            <p key={c.key} className="text-ink-muted">
              {c.key} — {c.title}
            </p>
          ))}
          {dryRun.renderedFirst && (
            <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-surface-2 p-2 text-[11px] text-ink-muted">
              {dryRun.renderedFirst}
            </pre>
          )}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- wired
export function TriggerSection({
  teamId,
  nodeName,
  nodes,
}: {
  teamId: string;
  nodeName: (id: string) => string;
  nodes: { id: string; name: string }[];
}) {
  const triggers = useTriggers(teamId);
  const instances = useConnectorInstances(teamId);
  const create = useCreateTrigger(teamId);
  const update = useUpdateTrigger(teamId);
  const remove = useDeleteTrigger(teamId);
  const check = useCheckTrigger(teamId);
  const dryRun = useDryRunTrigger(teamId);

  return (
    <TriggerPanel
      triggers={triggers.data ?? []}
      instances={instances.data ?? []}
      nodeName={nodeName}
      nodes={nodes}
      busy={create.isPending}
      error={create.isError ? (create.error as Error).message : null}
      dryRun={dryRun.data ?? null}
      onCreate={(body) => create.mutate(body)}
      onToggle={(t) => update.mutate({ triggerId: t.id, body: { enabled: !t.enabled } })}
      onDelete={(id) => remove.mutate(id)}
      onCheck={(id) => check.mutate(id)}
      onDryRun={(id) => dryRun.mutate(id)}
    />
  );
}
