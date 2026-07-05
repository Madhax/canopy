import { useNavigate } from "react-router-dom";
import type { OrgSummary } from "../../api/types";
import { Badge } from "../common";
import { relativeTime } from "../../lib/format";
import { SECTION_LABELS, sectionColor } from "../../lib/theme";

interface Props {
  summary: OrgSummary;
  section?: string;
  typeTitle?: string;
  onExport: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}

export function OrganizationCard({
  summary,
  section,
  typeTitle,
  onExport,
  onDuplicate,
  onDelete,
}: Props) {
  const navigate = useNavigate();
  const color = section ? sectionColor(section) : "#6b7280";
  return (
    <div
      className="group flex cursor-pointer flex-col gap-3 rounded-xl border border-border bg-surface p-4 transition-colors hover:border-border-strong"
      onClick={() => navigate(`/organizations/${summary.id}`)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate font-semibold text-ink">{summary.name}</h3>
          <Badge color={color} className="mt-1.5">
            {typeTitle ?? summary.organizationType}
          </Badge>
        </div>
        <span
          title={summary.valid ? "Valid for export" : "Has validation errors"}
          className="mt-1 size-2.5 shrink-0 rounded-full"
          style={{ background: summary.valid ? "var(--color-ok)" : "var(--color-warn)" }}
        />
      </div>

      <div className="flex items-center gap-3 text-xs text-ink-muted">
        <span>
          {summary.agentCount} agent{summary.agentCount === 1 ? "" : "s"}
        </span>
        {summary.childOrgCount > 0 && <span>· {summary.childOrgCount} sub-org</span>}
        <span className="ml-auto">{relativeTime(summary.updatedAt)}</span>
      </div>

      {section && (
        <div className="text-[11px] text-ink-subtle">{SECTION_LABELS[section] ?? section}</div>
      )}

      <div
        className="flex gap-3 border-t border-border pt-2 text-xs opacity-0 transition-opacity group-hover:opacity-100"
        onClick={(e) => e.stopPropagation()}
      >
        <button className="text-ink-muted hover:text-ink" onClick={onExport}>
          Export
        </button>
        <button className="text-ink-muted hover:text-ink" onClick={onDuplicate}>
          Duplicate
        </button>
        <button className="ml-auto text-ink-muted hover:text-danger" onClick={onDelete}>
          Delete
        </button>
      </div>
    </div>
  );
}
