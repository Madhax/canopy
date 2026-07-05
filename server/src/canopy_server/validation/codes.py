"""Validation issue codes and messages (docs/org-chart-editor.md §4.1).

Codes and human-readable messages are shared with the TypeScript side via the golden vectors
in ``testdata/validation`` — keep wording aligned when it changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["error", "warning"]
Mode = Literal["draft", "export"]

# Canonical messages. Kept short and identical across both validators.
CODE_MESSAGES: dict[str, str] = {
    "DUPLICATE_ID": "Duplicate id within this organization.",
    "REPORTS_CYCLE": "Reporting chain forms a cycle — every agent must roll up to a single root.",
    "NO_ROOT": "This organization has no root agent (one agent must have no manager).",
    "MULTIPLE_ROOTS": (
        "This organization has more than one root agent (only one may have no manager)."
    ),
    "MANAGER_DANGLING": "Manager refers to an agent that does not exist in this organization.",
    "DEP_DANGLING": "Dependency endpoint refers to an agent or child org that does not exist here.",
    "DEP_SELF": "An agent cannot depend on itself.",
    "DEP_DUPLICATE": "Duplicate dependency between the same pair.",
    "DEP_NOT_SIBLINGS": (
        "Dependencies connect siblings only — sequence these one level up, "
        "between their managers."
    ),
    "DEP_CYCLE": "Dependencies within this team form a cycle.",
    "ROLE_UNKNOWN": "Role is not in the catalog or this document's custom roles.",
    "ROLE_VERSION_UNKNOWN": "Role exists but this version is not known to the catalog.",
    "MOUNT_DANGLING": "Child organization is mounted on an agent that does not exist.",
    "CHILD_INVALID": "A nested child organization has validation issues.",
    "SALARY_INVALID": "Salary allowance must be a positive integer and warn threshold in (0, 100].",
    "AGENT_ORPHAN": "Agent is not wired into any dependency and has no reports.",
}


@dataclass
class ValidationIssue:
    severity: Severity
    code: str
    message: str
    agentIds: list[str] = field(default_factory=list)
    dependencyIds: list[str] = field(default_factory=list)
    orgPath: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        out: dict = {"severity": self.severity, "code": self.code, "message": self.message}
        if self.agentIds:
            out["agentIds"] = self.agentIds
        if self.dependencyIds:
            out["dependencyIds"] = self.dependencyIds
        if self.orgPath:
            out["orgPath"] = self.orgPath
        return out


def issue(
    code: str,
    severity: Severity,
    *,
    agentIds: list[str] | None = None,
    dependencyIds: list[str] | None = None,
    orgPath: list[str] | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        severity=severity,
        code=code,
        message=CODE_MESSAGES[code],
        agentIds=agentIds or [],
        dependencyIds=dependencyIds or [],
        orgPath=orgPath or [],
    )
