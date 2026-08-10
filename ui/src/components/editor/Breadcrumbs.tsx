import type { TeamDoc } from "../../schema/team";
import { breadcrumbs } from "../../store/orgTree";

interface Props {
  doc: TeamDoc;
  path: string[];
  onNavigate: (path: string[]) => void;
}

// Breadcrumbs are the nesting UI: each segment is one team (docs §7.4).
export function Breadcrumbs({ doc, path, onNavigate }: Props) {
  const trail = breadcrumbs(doc, path);
  return (
    <nav className="flex items-center gap-1 text-sm">
      {trail.map((seg, i) => (
        <span key={seg.id} className="flex items-center gap-1">
          {i > 0 && <span className="text-ink-subtle">/</span>}
          <button
            onClick={() => onNavigate(seg.path)}
            className={
              i === trail.length - 1
                ? "font-semibold text-ink"
                : "text-ink-muted hover:text-ink hover:underline"
            }
          >
            {seg.name}
          </button>
        </span>
      ))}
    </nav>
  );
}
