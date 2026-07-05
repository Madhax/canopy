import { useEffect, useMemo, useState } from "react";
import type { Catalog } from "../schema/catalog";
import type { OrganizationDoc } from "../schema/organization";
import type { ValidationIssue } from "../validation/codes";
import { validateOrganization } from "../validation/rules";

const arraysEqual = (a: string[], b: string[]) =>
  a.length === b.length && a.every((v, i) => v === b[i]);

/** Debounced full-tree validation (docs §7.4). Also derives issue sets for the current level. */
export function useValidation(
  doc: OrganizationDoc | null,
  catalog: Catalog | undefined,
  path: string[],
) {
  const [issues, setIssues] = useState<ValidationIssue[]>([]);

  useEffect(() => {
    if (!doc || !catalog) return;
    const handle = setTimeout(() => {
      setIssues(validateOrganization(doc, "draft", catalog));
    }, 300);
    return () => clearTimeout(handle);
  }, [doc, catalog]);

  const currentIssues = useMemo(
    () => issues.filter((i) => arraysEqual(i.orgPath ?? [], path)),
    [issues, path],
  );

  const { issueAgentIds, issueDepIds } = useMemo(() => {
    const agents = new Set<string>();
    const deps = new Set<string>();
    for (const i of currentIssues) {
      for (const a of i.agentIds ?? []) agents.add(a);
      for (const d of i.dependencyIds ?? []) deps.add(d);
    }
    return { issueAgentIds: agents, issueDepIds: deps };
  }, [currentIssues]);

  const errorCount = issues.filter((i) => i.severity === "error").length;
  const warningCount = issues.filter((i) => i.severity === "warning").length;

  return { issues, currentIssues, issueAgentIds, issueDepIds, errorCount, warningCount };
}
