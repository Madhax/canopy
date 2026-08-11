import type { Catalog, Formation } from "../../../schema/catalog";

interface Props {
  formation: Formation;
  catalog: Catalog;
}

// Stamping is drag-only, deliberately. A double-click used to stamp the whole subtree
// instantly at a fixed position — over an existing chart, with autosave persisting the
// accident within a second (the 2026-08-10 incident). Dragging is the one gesture that
// cannot happen by accident and that carries its own placement.
export function FormationRow({ formation, catalog }: Props) {
  const memberCount = formation.members.length + 1;
  const flow = formation.artifactFlow;
  const managerTitle =
    catalog.roles.find((r) => r.key === formation.manager.roleKey)?.title ?? formation.manager.roleKey;

  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("application/canopy-formation", formation.key);
        e.dataTransfer.effectAllowed = "copy";
      }}
      title={`${managerTitle} + ${formation.members.length} members — drag onto the canvas to stamp${flow ? `\n\n${flow}` : ""}`}
      className="flex cursor-grab items-center justify-between rounded-md border border-transparent px-2 py-1.5 text-sm hover:border-border hover:bg-surface-2 active:cursor-grabbing"
    >
      <span className="truncate text-ink">{formation.title}</span>
      <span className="shrink-0 text-[10px] text-ink-muted">{memberCount}</span>
    </div>
  );
}
