import type { Catalog, Formation } from "../../api/types";
import { roleGroupColor } from "../../lib/theme";

interface Props {
  formation: Formation;
  catalog: Catalog;
  selected: boolean;
  onSelect: () => void;
}

/** A seed choice card: shows the formation's manager, members, and its artifact-flow line. */
export function FormationCard({ formation, catalog, selected, onSelect }: Props) {
  const roleTitle = (key: string) =>
    catalog.roles.find((r) => r.key === key)?.title ?? key;
  const roleColor = (key: string) =>
    roleGroupColor(catalog.roles.find((r) => r.key === key)?.group ?? "custom");

  return (
    <button
      onClick={onSelect}
      className={`flex flex-col gap-2 rounded-xl border p-3.5 text-left transition-colors ${
        selected ? "border-accent bg-accent/5" : "border-border bg-surface hover:border-border-strong"
      }`}
    >
      <div className="font-medium text-ink">{formation.title}</div>
      <p className="text-xs leading-relaxed text-ink-muted">{formation.purpose}</p>
      <div className="flex flex-col gap-1 pt-1">
        <Chip color={roleColor(formation.manager.roleKey)} label={roleTitle(formation.manager.roleKey)} lead />
        <div className="flex flex-wrap gap-1 pl-3">
          {formation.members.map((m, i) => (
            <Chip key={`${m.slot}-${i}`} color={roleColor(m.roleKey)} label={roleTitle(m.roleKey)} />
          ))}
        </div>
      </div>
      {formation.artifactFlow && (
        <p className="pt-1 text-[11px] italic text-ink-subtle">{formation.artifactFlow}</p>
      )}
    </button>
  );
}

function Chip({ color, label, lead }: { color: string; label: string; lead?: boolean }) {
  return (
    <span
      className="inline-flex w-fit items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px]"
      style={{ background: `${color}18`, color }}
    >
      {lead && <span aria-hidden>♛</span>}
      {label}
    </span>
  );
}
