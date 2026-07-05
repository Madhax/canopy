import type { Extensions, Responsibility } from "../../../schema/organization";

interface Props {
  extensions: Extensions;
  onInstructions: (value: string) => void;
  onResponsibilities: (value: Responsibility[]) => void;
}

// The editor's "only the user permanently changes an Agent" surface (docs §3.2).
export function ExtensionsEditor({ extensions, onInstructions, onResponsibilities }: Props) {
  const resp = extensions.responsibilities;

  const update = (i: number, patch: Partial<Responsibility>) => {
    const next = resp.map((r, idx) => (idx === i ? { ...r, ...patch } : r));
    onResponsibilities(next);
  };
  const updateDeliverable = (i: number, patch: Partial<Responsibility["deliverable"]>) =>
    update(i, { deliverable: { ...resp[i].deliverable, ...patch } });

  const add = () =>
    onResponsibilities([
      ...resp,
      { duty: "", deliverable: { kind: "artifact", type: "" } },
    ]);
  const remove = (i: number) => onResponsibilities(resp.filter((_, idx) => idx !== i));

  return (
    <div className="flex flex-col gap-3">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Extensions</h4>

      <label className="flex flex-col gap-1">
        <span className="text-xs text-ink-muted">Instruction overrides</span>
        <textarea
          value={extensions.instructions}
          onChange={(e) => onInstructions(e.target.value)}
          rows={3}
          placeholder="Permanent instructions layered onto the role…"
          className="resize-y rounded-md border border-border bg-canvas px-2 py-1.5 text-sm outline-none focus:border-accent"
        />
      </label>

      <div className="flex flex-col gap-2">
        <span className="text-xs text-ink-muted">Added responsibilities</span>
        {resp.map((r, i) => (
          <div key={i} className="flex flex-col gap-1 rounded-md border border-border p-2">
            <input
              value={r.duty}
              onChange={(e) => update(i, { duty: e.target.value })}
              placeholder="Duty…"
              className="rounded border border-border bg-canvas px-1.5 py-1 text-sm outline-none focus:border-accent"
            />
            <div className="flex items-center gap-1">
              <select
                value={r.deliverable.kind}
                onChange={(e) => updateDeliverable(i, { kind: e.target.value as "artifact" | "attestation" })}
                className="rounded border border-border bg-canvas px-1 py-1 text-xs"
              >
                <option value="artifact">Artifact</option>
                <option value="attestation">Attestation</option>
              </select>
              <input
                value={r.deliverable.type}
                onChange={(e) => updateDeliverable(i, { type: e.target.value })}
                placeholder="Deliverable type (required)…"
                className="min-w-0 flex-1 rounded border border-border bg-canvas px-1.5 py-1 text-xs outline-none focus:border-accent"
              />
              <button className="px-1 text-ink-muted hover:text-danger" onClick={() => remove(i)}>
                ✕
              </button>
            </div>
          </div>
        ))}
        <button
          onClick={add}
          className="rounded-md border border-dashed border-border px-2 py-1 text-xs text-ink-muted hover:border-accent hover:text-ink"
        >
          ＋ Add responsibility
        </button>
      </div>
    </div>
  );
}
