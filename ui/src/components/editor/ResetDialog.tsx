import { useState } from "react";
import type { Catalog } from "../../schema/catalog";
import type { Agent, Dependency, OrganizationDoc } from "../../schema/organization";
import { buildSeedContent, defaultRootRole, type ChildSeed } from "../../lib/newOrg";
import { Button, Dialog } from "../common";
import { roleGroupColor } from "../../lib/theme";

type Choice =
  | { kind: "original" }
  | { kind: "formation"; formationKey: string }
  | { kind: "root" }
  | { kind: "blank" };

interface Props {
  open: boolean;
  catalog: Catalog;
  org: OrganizationDoc;
  onClose: () => void;
  onApply: (agents: Agent[], dependencies: Dependency[]) => void;
}

// Reset the current chart to its original seed, or to a template derived from the archetype.
export function ResetDialog({ open, catalog, org, onClose, onApply }: Props) {
  const orgType = catalog.organizationTypes.find((o) => o.key === org.organizationType);
  const seed = (org.meta as Record<string, unknown> | undefined)?.seed as ChildSeed | undefined;
  const [choice, setChoice] = useState<Choice | null>(seed ? { kind: "original" } : null);

  const formations = (orgType?.formations ?? [])
    .map((k) => catalog.formations.find((f) => f.key === k))
    .filter((f): f is NonNullable<typeof f> => !!f);

  function apply() {
    if (!choice) return;
    let content: { agents: Agent[]; dependencies: Dependency[] };
    if (choice.kind === "original") {
      content = buildSeedContent(catalog, seed ?? { kind: "blank" });
    } else if (choice.kind === "formation") {
      content = buildSeedContent(catalog, {
        kind: "formation",
        formationKey: choice.formationKey,
      });
    } else if (choice.kind === "root") {
      content = buildSeedContent(catalog, {
        kind: "root",
        roleKey: defaultRootRole(catalog, orgType),
      });
    } else {
      content = { agents: [], dependencies: [] };
    }
    onApply(content.agents, content.dependencies);
  }

  const eq = (c: Choice) => choice && JSON.stringify(choice) === JSON.stringify(c);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Reset chart"
      width="max-w-lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="danger" disabled={!choice} onClick={apply}>
            Reset chart
          </Button>
        </>
      }
    >
      <p className="mb-4 text-ink-muted">
        This replaces the current chart — agents, dependencies, and any nested organizations. It can
        be undone with <kbd className="rounded bg-surface-2 px-1">⌘Z</kbd>.
      </p>

      <div className="flex flex-col gap-3">
        {seed && (
          <Card selected={!!eq({ kind: "original" })} onClick={() => setChoice({ kind: "original" })}>
            <div className="font-medium text-ink">Original</div>
            <div className="text-xs text-ink-muted">The chart as it was first created.</div>
          </Card>
        )}

        {formations.length > 0 && (
          <div>
            <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
              Templates
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {formations.map((f) => (
                <Card
                  key={f.key}
                  selected={!!eq({ kind: "formation", formationKey: f.key })}
                  onClick={() => setChoice({ kind: "formation", formationKey: f.key })}
                >
                  <div className="flex items-center gap-1.5 font-medium text-ink">
                    <span style={{ color: roleGroupColor(managerGroup(catalog, f.manager.roleKey)) }}>♛</span>
                    {f.title}
                  </div>
                  <div className="text-xs text-ink-muted">{f.members.length + 1} agents</div>
                </Card>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-2">
          <Card selected={!!eq({ kind: "root" })} onClick={() => setChoice({ kind: "root" })}>
            <div className="font-medium text-ink">Root agent only</div>
            <div className="text-xs text-ink-muted">Just the leadership role.</div>
          </Card>
          <Card selected={!!eq({ kind: "blank" })} onClick={() => setChoice({ kind: "blank" })}>
            <div className="font-medium text-ink">Blank</div>
            <div className="text-xs text-ink-muted">Empty canvas.</div>
          </Card>
        </div>
      </div>
    </Dialog>
  );
}

function managerGroup(catalog: Catalog, roleKey: string): string {
  return catalog.roles.find((r) => r.key === roleKey)?.group ?? "custom";
}

function Card({
  selected,
  onClick,
  children,
}: {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex flex-col gap-0.5 rounded-lg border p-3 text-left transition-colors ${
        selected ? "border-accent bg-accent/5" : "border-border bg-surface hover:border-border-strong"
      }`}
    >
      {children}
    </button>
  );
}
