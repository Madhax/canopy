import { useNavigate } from "react-router-dom";
import type { OrgSummary } from "../../api/types";
import { Badge } from "../common";
import { relativeTime } from "../../lib/format";
import { SECTION_LABELS, sectionColor } from "../../lib/theme";

interface Props {
  summary: OrgSummary;
  section?: string;
  typeTitle?: string;
  /** Actuation state chip for portfolio cards (null/undefined = not actuated). */
  actuation?: string | null;
  onExport: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
  /** Custody transfer to another Organization (design/organizations/01 §3). */
  onMove?: () => void;
}

export function TeamCard({
  summary,
  section,
  typeTitle,
  actuation,
  onExport,
  onDuplicate,
  onDelete,
  onMove,
}: Props) {
  const navigate = useNavigate();
  const color = section ? sectionColor(section) : "#6b7280";
  return (
    <div
      className="group flex cursor-pointer flex-col gap-3 rounded-xl border border-border bg-surface p-4 transition-colors hover:border-border-strong"
      onClick={() => navigate(`/teams/${summary.id}`)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate font-semibold text-ink">{summary.name}</h3>
          <Badge color={color} className="mt-1.5">
            {typeTitle ?? summary.organizationType}
          </Badge>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {actuation && (
            <Badge color="var(--color-ok)">{actuation === "live" ? "live" : actuation}</Badge>
          )}
          <span
            title={summary.valid ? "Valid for export" : "Has validation errors"}
            className="mt-1 size-2.5 shrink-0 rounded-full"
            style={{ background: summary.valid ? "var(--color-ok)" : "var(--color-warn)" }}
          />
        </div>
      </div>

      <div className="flex items-center gap-3 text-xs text-ink-muted">
        <span>
          {summary.agentCount} agent{summary.agentCount === 1 ? "" : "s"}
        </span>
        {summary.childTeamCount > 0 && <span>· {summary.childTeamCount} sub-team</span>}
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
        {onMove && (
          <button className="text-ink-muted hover:text-ink" onClick={onMove}>
            Move…
          </button>
        )}
        <button className="ml-auto text-ink-muted hover:text-danger" onClick={onDelete}>
          Delete
        </button>
      </div>
    </div>
  );
}
