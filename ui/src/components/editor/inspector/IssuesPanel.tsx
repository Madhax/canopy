import type { ValidationIssue } from "../../../validation/codes";

interface Props {
  issues: ValidationIssue[];
  onFocus: (issue: ValidationIssue) => void;
}

export function IssuesPanel({ issues, onFocus }: Props) {
  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warning");

  if (issues.length === 0) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-ok/30 bg-ok/5 px-3 py-2 text-sm text-ok">
        <span>✓</span> No validation issues.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
        Issues
        <span className="ml-2 font-normal text-ink-subtle">
          {errors.length} error{errors.length === 1 ? "" : "s"} · {warnings.length} warning
          {warnings.length === 1 ? "" : "s"}
        </span>
      </h4>
      <div className="flex flex-col gap-1">
        {[...errors, ...warnings].map((issue, i) => (
          <button
            key={i}
            onClick={() => onFocus(issue)}
            className="flex items-start gap-2 rounded-md border border-border px-2 py-1.5 text-left text-xs hover:bg-surface-2"
          >
            <span
              className="mt-0.5 size-2 shrink-0 rounded-full"
              style={{ background: issue.severity === "error" ? "var(--color-danger)" : "var(--color-warn)" }}
            />
            <span>
              <span className="font-medium text-ink">{issue.code}</span>
              {issue.orgPath && issue.orgPath.length > 0 && (
                <span className="text-ink-subtle"> · nested</span>
              )}
              <div className="text-ink-muted">{issue.message}</div>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
