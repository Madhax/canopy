import { useEffect, useMemo, useState } from "react";
import type { Catalog } from "../schema/catalog";
import type { TeamDoc } from "../schema/team";
import type { ValidationIssue } from "../validation/codes";
import { validateTeam } from "../validation/rules";

const arraysEqual = (a: string[], b: string[]) =>
  a.length === b.length && a.every((v, i) => v === b[i]);

/** Debounced full-tree validation (docs §7.4). Also derives issue sets for the current level. */
export function useValidation(
  doc: TeamDoc | null,
  catalog: Catalog | undefined,
  path: string[],
) {
  const [issues, setIssues] = useState<ValidationIssue[]>([]);

  useEffect(() => {
    if (!doc || !catalog) return;
    const handle = setTimeout(() => {
      setIssues(validateTeam(doc, "draft", catalog));
    }, 300);
    return () => clearTimeout(handle);
  }, [doc, catalog]);

  const currentIssues = useMemo(
    () => issues.filter((i) => arraysEqual(i.teamPath ?? [], path)),
    [issues, path],
  );

  const { issueAgentIds, issueDepIds, errorAgentIds } = useMemo(() => {
    const agents = new Set<string>();
    const deps = new Set<string>();
    // Nodes holding an invalid setting — rendered red on the canvas. Errors, plus an unknown
    // role or role version (warnings in draft mode, but still a wrong setting on this node).
    const errors = new Set<string>();
    for (const i of currentIssues) {
      for (const a of i.agentIds ?? []) agents.add(a);
      for (const d of i.dependencyIds ?? []) deps.add(d);
      if (
        i.severity === "error" ||
        i.code === "ROLE_UNKNOWN" ||
        i.code === "ROLE_VERSION_UNKNOWN"
      ) {
        for (const a of i.agentIds ?? []) errors.add(a);
      }
    }
    // A child team on the current canvas with internal errors emits CHILD_INVALID at
    // [...path, child.team.id] — mark the child team card itself as holding an error.
    for (const i of issues) {
      if (
        i.code === "CHILD_INVALID" &&
        i.teamPath &&
        i.teamPath.length === path.length + 1 &&
        arraysEqual(i.teamPath.slice(0, -1), path)
      ) {
        const childId = i.teamPath[i.teamPath.length - 1];
        agents.add(childId);
        errors.add(childId);
      }
    }
    return { issueAgentIds: agents, issueDepIds: deps, errorAgentIds: errors };
  }, [currentIssues, issues, path]);

  const errorCount = issues.filter((i) => i.severity === "error").length;
  const warningCount = issues.filter((i) => i.severity === "warning").length;

  return {
    issues, currentIssues, issueAgentIds, issueDepIds, errorAgentIds, errorCount, warningCount,
  };
}
