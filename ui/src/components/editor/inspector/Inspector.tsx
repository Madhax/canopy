import type { Catalog } from "../../../schema/catalog";
import type { TeamDoc } from "../../../schema/team";
import type { ValidationIssue } from "../../../validation/codes";
import { useSelectionStore } from "../../../store/selectionStore";
import { AgentPanel } from "./AgentPanel";
import { DependencyPanel } from "./DependencyPanel";
import { ChildOrgPanel } from "./ChildOrgPanel";
import { OrgSettingsPanel } from "./OrgSettingsPanel";

interface Props {
  team: TeamDoc;
  catalog: Catalog;
  issues: ValidationIssue[];
  onFocusIssue: (issue: ValidationIssue) => void;
  onOpenChild: (childTeamId: string) => void;
}

export function Inspector({ team, catalog, issues, onFocusIssue, onOpenChild }: Props) {
  const selection = useSelectionStore((s) => s.selection);

  const agent =
    selection.kind === "agent" ? team.agents.find((a) => a.id === selection.id) : undefined;
  const dependency =
    selection.kind === "dependency"
      ? team.dependencies.find((d) => d.id === selection.id)
      : undefined;
  const child =
    selection.kind === "childTeam"
      ? team.childTeams.find((c) => c.team.id === selection.id)
      : undefined;

  return (
    <aside className="w-[340px] shrink-0 overflow-y-auto border-l border-border bg-surface">
      {agent ? (
        <AgentPanel agent={agent} team={team} catalog={catalog} />
      ) : dependency ? (
        <DependencyPanel dependency={dependency} team={team} />
      ) : child ? (
        <ChildOrgPanel child={child} team={team} catalog={catalog} onOpen={() => onOpenChild(child.team.id)} />
      ) : (
        <OrgSettingsPanel team={team} issues={issues} onFocusIssue={onFocusIssue} />
      )}
    </aside>
  );
}
