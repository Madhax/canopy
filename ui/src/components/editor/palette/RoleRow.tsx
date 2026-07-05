import type { CatalogRole } from "../../../schema/catalog";
import { roleGroupColor } from "../../../lib/theme";

interface Props {
  role: CatalogRole;
  onPlace: () => void;
}

export function RoleRow({ role, onPlace }: Props) {
  const color = roleGroupColor(role.group);
  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("application/canopy-role", role.key);
        e.dataTransfer.effectAllowed = "copy";
      }}
      onDoubleClick={onPlace}
      title={role.purpose}
      className="flex cursor-grab items-center gap-2 rounded-md border border-transparent px-2 py-1.5 text-sm hover:border-border hover:bg-surface-2 active:cursor-grabbing"
    >
      <span className="w-3 shrink-0 text-center text-[10px] text-ink-muted" aria-hidden>
        {role.isManager ? "♛" : "•"}
      </span>
      <span className="size-2 shrink-0 rounded-full" style={{ background: color }} />
      <span className="truncate text-ink">{role.title}</span>
    </div>
  );
}
