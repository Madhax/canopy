import { useState } from "react";
import type { CustomRole, Responsibility } from "../../../schema/organization";
import { slugify } from "../../../lib/format";
import { Button, Dialog } from "../../common";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreate: (role: CustomRole) => void;
}

// Document-local role definition (docs §3.4). Every responsibility must carry a deliverable.
export function CustomRoleForm({ open, onClose, onCreate }: Props) {
  const [title, setTitle] = useState("");
  const [purpose, setPurpose] = useState("");
  const [isManager, setIsManager] = useState(false);
  const [allowance, setAllowance] = useState(120000);
  const [resp, setResp] = useState<Responsibility[]>([
    { duty: "", deliverable: { kind: "artifact", type: "" } },
  ]);

  const validResp = resp.filter((r) => r.duty.trim() && r.deliverable.type.trim());
  const canCreate = title.trim() && validResp.length > 0 && validResp.length === resp.length;

  function create() {
    const key = `custom-${slugify(title)}`;
    onCreate({
      key,
      version: 1,
      title: title.trim(),
      group: "custom",
      purpose: purpose.trim(),
      responsibilities: resp,
      isManager,
      defaultSalary: { perAssignmentAllowance: allowance, warnThresholdPct: 80, hardStop: true },
    });
  }

  const update = (i: number, patch: Partial<Responsibility>) =>
    setResp((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  const updateDeliv = (i: number, patch: Partial<Responsibility["deliverable"]>) =>
    update(i, { deliverable: { ...resp[i].deliverable, ...patch } });

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Define custom role"
      width="max-w-lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={!canCreate} onClick={create}>
            Create role
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <label className="flex flex-col gap-1">
          <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Title</span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Release Captain"
            className="rounded-md border border-border bg-canvas px-2 py-1.5 text-sm outline-none focus:border-accent"
          />
          {title.trim() && (
            <span className="text-[11px] text-ink-subtle">key: custom-{slugify(title)}</span>
          )}
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Purpose</span>
          <input
            value={purpose}
            onChange={(e) => setPurpose(e.target.value)}
            className="rounded-md border border-border bg-canvas px-2 py-1.5 text-sm outline-none focus:border-accent"
          />
        </label>

        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={isManager} onChange={(e) => setIsManager(e.target.checked)} />
            Manager role
          </label>
          <label className="flex items-center gap-2 text-sm">
            <span className="text-ink-muted">Allowance</span>
            <input
              type="number"
              value={allowance}
              onChange={(e) => setAllowance(Math.max(1, Math.round(+e.target.value)))}
              className="w-28 rounded-md border border-border bg-canvas px-2 py-1 text-sm"
            />
          </label>
        </div>

        <div className="flex flex-col gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
            Responsibilities <span className="font-normal normal-case text-ink-subtle">(duty → deliverable, required)</span>
          </span>
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
                  onChange={(e) => updateDeliv(i, { kind: e.target.value as "artifact" | "attestation" })}
                  className="rounded border border-border bg-canvas px-1 py-1 text-xs"
                >
                  <option value="artifact">Artifact</option>
                  <option value="attestation">Attestation</option>
                </select>
                <input
                  value={r.deliverable.type}
                  onChange={(e) => updateDeliv(i, { type: e.target.value })}
                  placeholder="Deliverable type (required)…"
                  className="min-w-0 flex-1 rounded border border-border bg-canvas px-1.5 py-1 text-xs outline-none focus:border-accent"
                />
                {resp.length > 1 && (
                  <button
                    className="px-1 text-ink-muted hover:text-danger"
                    onClick={() => setResp((rs) => rs.filter((_, idx) => idx !== i))}
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>
          ))}
          <button
            onClick={() => setResp((rs) => [...rs, { duty: "", deliverable: { kind: "artifact", type: "" } }])}
            className="rounded-md border border-dashed border-border px-2 py-1 text-xs text-ink-muted hover:border-accent hover:text-ink"
          >
            ＋ Add responsibility
          </button>
        </div>
      </div>
    </Dialog>
  );
}
