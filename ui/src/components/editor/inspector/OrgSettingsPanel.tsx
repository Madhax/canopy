import type { OrganizationDoc } from "../../../schema/organization";
import type { ValidationIssue } from "../../../validation/codes";
import { useDocumentStore } from "../../../store/documentStore";
import { useSelectionStore } from "../../../store/selectionStore";
import { IssuesPanel } from "./IssuesPanel";

interface Props {
  org: OrganizationDoc;
  issues: ValidationIssue[];
  onFocusIssue: (issue: ValidationIssue) => void;
}

export function OrgSettingsPanel({ org, issues, onFocusIssue }: Props) {
  const store = useDocumentStore();
  const path = useSelectionStore((s) => s.path);

  return (
    <div className="flex flex-col gap-5 p-4">
      <label className="flex flex-col gap-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
          Organization name
        </span>
        <input
          value={org.name}
          onChange={(e) => store.renameOrg(path, e.target.value)}
          className="rounded-md border border-border bg-canvas px-2 py-1.5 text-sm outline-none focus:border-accent"
        />
      </label>

      <div className="flex flex-col gap-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Type</span>
        <span className="text-sm text-ink-muted">{org.organizationType}</span>
      </div>

      <div className="border-t border-border pt-4">
        <IssuesPanel issues={issues} onFocus={onFocusIssue} />
      </div>
    </div>
  );
}
