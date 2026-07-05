import { useMemo, useState } from "react";
import type { Catalog } from "../../../schema/catalog";
import type { Agent, OrganizationDoc } from "../../../schema/organization";
import { newChildOrgDoc, defaultRootRole, type ChildSeed } from "../../../lib/newOrg";
import { Button, Dialog } from "../../common";

interface Props {
  open: boolean;
  catalog: Catalog;
  agents: Agent[];
  defaultMountId?: string;
  onClose: () => void;
  onCreate: (mountAgentId: string, child: OrganizationDoc) => void;
}

// The "＋ Child organization" mini-wizard: a full nested Organization mounted under a parent agent.
export function ChildOrgDialog({ open, catalog, agents, defaultMountId, onClose, onCreate }: Props) {
  const [typeKey, setTypeKey] = useState("customer-support-center");
  const [name, setName] = useState("");
  const [mountId, setMountId] = useState(defaultMountId ?? agents[0]?.id ?? "");
  const [seedKind, setSeedKind] = useState<ChildSeed["kind"]>("formation");
  const [formationKey, setFormationKey] = useState<string>("");

  const orgType = useMemo(
    () => catalog.organizationTypes.find((o) => o.key === typeKey),
    [catalog, typeKey],
  );
  const formations = orgType?.formations ?? [];
  const effFormation = formationKey || formations[0] || "";

  const canCreate = mountId && (seedKind !== "formation" || effFormation);

  function create() {
    const seed: ChildSeed =
      seedKind === "blank"
        ? { kind: "blank" }
        : seedKind === "root"
          ? { kind: "root", roleKey: defaultRootRole(catalog, orgType) }
          : { kind: "formation", formationKey: effFormation };
    const child = newChildOrgDoc(catalog, name.trim() || (orgType?.title ?? "Child org"), typeKey, seed);
    onCreate(mountId, child);
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Add child organization"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" disabled={!canCreate} onClick={create}>
            Mount organization
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <Field label="Name">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={orgType?.title}
            className="w-full rounded-md border border-border bg-canvas px-2 py-1.5 text-sm outline-none focus:border-accent"
          />
        </Field>
        <Field label="Type">
          <select
            value={typeKey}
            onChange={(e) => {
              setTypeKey(e.target.value);
              setFormationKey("");
            }}
            className="w-full rounded-md border border-border bg-canvas px-2 py-1.5 text-sm"
          >
            {catalog.organizationTypes.map((o) => (
              <option key={o.key} value={o.key}>
                {o.title}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Reports to">
          <select
            value={mountId}
            onChange={(e) => setMountId(e.target.value)}
            className="w-full rounded-md border border-border bg-canvas px-2 py-1.5 text-sm"
          >
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Seed">
          <div className="flex flex-col gap-1.5 text-sm">
            {formations.length > 0 && (
              <label className="flex items-center gap-2">
                <input type="radio" checked={seedKind === "formation"} onChange={() => setSeedKind("formation")} />
                <span>Formation</span>
                <select
                  value={effFormation}
                  disabled={seedKind !== "formation"}
                  onChange={(e) => setFormationKey(e.target.value)}
                  className="ml-1 rounded border border-border bg-canvas px-1.5 py-1 text-xs disabled:opacity-50"
                >
                  {formations.map((f) => (
                    <option key={f} value={f}>
                      {catalog.formations.find((x) => x.key === f)?.title ?? f}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="flex items-center gap-2">
              <input type="radio" checked={seedKind === "root"} onChange={() => setSeedKind("root")} />
              Root agent only
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" checked={seedKind === "blank"} onChange={() => setSeedKind("blank")} />
              Blank
            </label>
          </div>
        </Field>
      </div>
    </Dialog>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{label}</span>
      {children}
    </label>
  );
}
