import type { Catalog, OrgType, SeedSpec } from "../../api/types";
import { FormationCard } from "./FormationCard";
import { roleGroupColor } from "../../lib/theme";

interface Props {
  catalog: Catalog;
  orgType: OrgType;
  name: string;
  onName: (v: string) => void;
  seed: SeedSpec;
  onSeed: (s: SeedSpec) => void;
}

export function SeedStep({ catalog, orgType, name, onName, seed, onSeed }: Props) {
  const formations = orgType.formations
    .map((k) => catalog.formations.find((f) => f.key === k))
    .filter((f): f is NonNullable<typeof f> => !!f);

  const managerRoles = catalog.roles.filter((r) => r.isManager);
  const defaultRoot =
    orgType.rolePalette.find((k) => managerRoles.some((m) => m.key === k)) ??
    orgType.rolePalette[0] ??
    "chief-executive";
  const rootRoleKey = seed.kind === "root" ? seed.roleKey : defaultRoot;

  return (
    <div className="flex flex-col gap-6">
      <label className="flex flex-col gap-1.5">
        <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Name</span>
        <input
          value={name}
          onChange={(e) => onName(e.target.value)}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
        />
      </label>

      {formations.length > 0 && (
        <Section title="Start from a formation" hint="Stamps a pre-wired team; its manager becomes the org root.">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {formations.map((f) => (
              <FormationCard
                key={f.key}
                formation={f}
                catalog={catalog}
                selected={seed.kind === "formation" && seed.formationKey === f.key}
                onSelect={() => onSeed({ kind: "formation", formationKey: f.key })}
              />
            ))}
          </div>
        </Section>
      )}

      <Section title="Root agent only" hint="A single leader; you build the rest by hand.">
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              checked={seed.kind === "root"}
              onChange={() => onSeed({ kind: "root", roleKey: rootRoleKey })}
            />
            Root role
          </label>
          <select
            value={rootRoleKey}
            disabled={seed.kind !== "root"}
            onChange={(e) => onSeed({ kind: "root", roleKey: e.target.value })}
            className="rounded-md border border-border bg-surface px-2 py-1.5 text-sm disabled:opacity-50"
          >
            {catalog.roles.map((r) => (
              <option key={r.key} value={r.key}>
                {r.title}
              </option>
            ))}
          </select>
          <span
            className="size-2.5 rounded-full"
            style={{
              background: roleGroupColor(
                catalog.roles.find((r) => r.key === rootRoleKey)?.group ?? "custom",
              ),
            }}
          />
        </div>
      </Section>

      <Section title="Blank canvas" hint="No agents yet — the first agent you place becomes the root.">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            checked={seed.kind === "blank"}
            onChange={() => onSeed({ kind: "blank" })}
          />
          Start empty
        </label>
      </Section>
    </div>
  );
}

function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-2">
      <div>
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        <p className="text-xs text-ink-muted">{hint}</p>
      </div>
      {children}
    </section>
  );
}
