import type { Catalog } from "../../../schema/catalog";
import type { OrganizationDoc } from "../../../schema/organization";
import type { ValidationIssue } from "../../../validation/codes";
import { useSelectionStore } from "../../../store/selectionStore";
import { AgentPanel } from "./AgentPanel";
import { DependencyPanel } from "./DependencyPanel";
import { ChildOrgPanel } from "./ChildOrgPanel";
import { OrgSettingsPanel } from "./OrgSettingsPanel";

interface Props {
  org: OrganizationDoc;
  catalog: Catalog;
  issues: ValidationIssue[];
  onFocusIssue: (issue: ValidationIssue) => void;
  onOpenChild: (childOrgId: string) => void;
}

export function Inspector({ org, catalog, issues, onFocusIssue, onOpenChild }: Props) {
  const selection = useSelectionStore((s) => s.selection);

  const agent =
    selection.kind === "agent" ? org.agents.find((a) => a.id === selection.id) : undefined;
  const dependency =
    selection.kind === "dependency"
      ? org.dependencies.find((d) => d.id === selection.id)
      : undefined;
  const child =
    selection.kind === "childOrg"
      ? org.childOrganizations.find((c) => c.organization.id === selection.id)
      : undefined;

  return (
    <aside className="w-[340px] shrink-0 overflow-y-auto border-l border-border bg-surface">
      {agent ? (
        <AgentPanel agent={agent} org={org} catalog={catalog} />
      ) : dependency ? (
        <DependencyPanel dependency={dependency} org={org} />
      ) : child ? (
        <ChildOrgPanel child={child} org={org} catalog={catalog} onOpen={() => onOpenChild(child.organization.id)} />
      ) : (
        <OrgSettingsPanel org={org} issues={issues} onFocusIssue={onFocusIssue} />
      )}
    </aside>
  );
}
