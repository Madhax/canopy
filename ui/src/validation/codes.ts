// Validation issue codes + messages (docs/org-chart-editor.md §4.1).
// Must stay byte-identical to server/src/canopy_server/validation/codes.py — the golden
// vectors in testdata/validation enforce this.

export type Severity = "error" | "warning";
export type Mode = "draft" | "export";

export const CODE_MESSAGES: Record<string, string> = {
  DUPLICATE_ID: "Duplicate id within this team.",
  REPORTS_CYCLE:
    "Reporting chain forms a cycle — every agent must roll up to a single root.",
  NO_ROOT: "This team has no root agent (one agent must have no manager).",
  MULTIPLE_ROOTS:
    "This team has more than one root agent (only one may have no manager).",
  MANAGER_DANGLING: "Manager refers to an agent that does not exist in this team.",
  DEP_DANGLING: "Dependency endpoint refers to an agent or child team that does not exist here.",
  DEP_SELF: "An agent cannot depend on itself.",
  DEP_DUPLICATE: "Duplicate dependency between the same pair.",
  DEP_NOT_SIBLINGS:
    "Dependencies connect siblings only — sequence these one level up, between their managers.",
  DEP_CYCLE: "Dependencies within this team form a cycle.",
  ROLE_UNKNOWN: "Role is not in the catalog or this document's custom roles.",
  ROLE_VERSION_UNKNOWN: "Role exists but this version is not known to the catalog.",
  MOUNT_DANGLING: "Child team is mounted on an agent that does not exist.",
  CHILD_INVALID: "A nested child team has validation issues.",
  SALARY_INVALID:
    "Salary allowance must be a positive integer and warn threshold in (0, 100].",
  AGENT_ORPHAN: "Agent is not wired into any dependency and has no reports.",
};

export interface ValidationIssue {
  severity: Severity;
  code: string;
  message: string;
  agentIds?: string[];
  dependencyIds?: string[];
  teamPath?: string[];
}

export function makeIssue(
  code: string,
  severity: Severity,
  opts: { agentIds?: string[]; dependencyIds?: string[]; teamPath?: string[] } = {},
): ValidationIssue {
  const issue: ValidationIssue = { severity, code, message: CODE_MESSAGES[code] };
  if (opts.agentIds && opts.agentIds.length) issue.agentIds = opts.agentIds;
  if (opts.dependencyIds && opts.dependencyIds.length) issue.dependencyIds = opts.dependencyIds;
  if (opts.teamPath && opts.teamPath.length) issue.teamPath = opts.teamPath;
  return issue;
}
