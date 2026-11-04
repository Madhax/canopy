import type { Catalog } from "../../../schema/catalog";
import type { Agent, TeamDoc } from "../../../schema/team";
import type { ValidationIssue } from "../../../validation/codes";
import { useDocumentStore } from "../../../store/documentStore";
import { useSelectionStore } from "../../../store/selectionStore";
import { roleGroupColor } from "../../../lib/theme";
import { Button } from "../../common";
import { BindingPicker } from "./BindingPicker";
import { SalaryEditor } from "./SalaryEditor";
import { ExtensionsEditor } from "./ExtensionsEditor";

interface Props {
  agent: Agent;
  team: TeamDoc;
  catalog: Catalog;
  /** Validation issues implicating this node — invalid fields render red. */
  issues?: ValidationIssue[];
}

const FIELD_CLS =
  "rounded-md border bg-canvas px-2 py-1.5 text-sm outline-none";
const fieldTone = (bad: boolean) =>
  bad
    ? "border-danger text-danger ring-1 ring-danger/40 focus:border-danger"
    : "border-border focus:border-accent";

export function AgentPanel({ agent, team, catalog, issues = [] }: Props) {
  const store = useDocumentStore();
  const path = useSelectionStore((s) => s.path);
  const clear = useSelectionStore((s) => s.clear);
  const topOrgId = useDocumentStore((s) => s.doc?.id);
  const sameRoleNodeIds = team.agents
    .filter((a) => a.role.key === agent.role.key)
    .map((a) => a.id);

  const role =
    catalog.roles.find((r) => r.key === agent.role.key) ??
    team.customRoles.find((r) => r.key === agent.role.key);
  const roleUnknown = !role;
  const color = roleGroupColor(role?.group ?? "custom");
  const codes = new Set(issues.map((i) => i.code));
  const nameBad = agent.name.trim() === "";
  const roleBad = roleUnknown || codes.has("ROLE_UNKNOWN") || codes.has("ROLE_VERSION_UNKNOWN");
  const salaryBad =
    codes.has("SALARY_INVALID") ||
    !Number.isInteger(agent.salary.perAssignmentAllowance) ||
    agent.salary.perAssignmentAllowance <= 0 ||
    agent.salary.warnThresholdPct <= 0 ||
    agent.salary.warnThresholdPct > 100;
  // Problems not tied to a single field (reporting cycle, dangling manager, …) list up top.
  const nodeErrors = issues.filter((i) => i.severity === "error");
  const nodeWarnings = issues.filter((i) => i.severity === "warning");

  return (
    <div className="flex flex-col gap-5 p-4">
      {(nodeErrors.length > 0 || nodeWarnings.length > 0) && (
        <ul className="flex flex-col gap-1" aria-label="Problems with this node">
          {[...nodeErrors, ...nodeWarnings].map((i, idx) => (
            <li
              key={`${i.code}-${idx}`}
              className={`rounded-md border px-2 py-1.5 text-xs ${
                i.severity === "error"
                  ? "border-danger bg-danger/5 text-danger"
                  : "border-warn/40 bg-warn/5 text-warn"
              }`}
            >
              <span className="font-mono text-[10px]">{i.code}</span> — {i.message}
            </li>
          ))}
        </ul>
      )}

      <label className="flex flex-col gap-1">
        <span
          className={`text-xs font-semibold uppercase tracking-wide ${
            nameBad ? "text-danger" : "text-ink-muted"
          }`}
        >
          Name
        </span>
        <input
          value={agent.name}
          onChange={(e) => store.renameAgent(path, agent.id, e.target.value)}
          aria-invalid={nameBad || undefined}
          className={`${FIELD_CLS} ${fieldTone(nameBad)}`}
        />
      </label>

      <label className="flex flex-col gap-1">
        <span
          className={`flex items-center justify-between text-xs font-semibold uppercase tracking-wide ${
            roleBad ? "text-danger" : "text-ink-muted"
          }`}
        >
          Role
          <span
            className="font-normal normal-case"
            style={{ color: roleBad ? "var(--color-danger)" : color }}
          >
            {agent.role.key}@{agent.role.version}
          </span>
        </span>
        <select
          value={agent.role.key}
          onChange={(e) => {
            const r =
              catalog.roles.find((x) => x.key === e.target.value) ??
              team.customRoles.find((x) => x.key === e.target.value);
            store.reassignRole(path, agent.id, e.target.value, r?.version ?? 1);
          }}
          aria-invalid={roleBad || undefined}
          className={`${FIELD_CLS} ${fieldTone(roleBad)}`}
        >
          {roleUnknown && <option value={agent.role.key}>⚠ {agent.role.key} (unknown)</option>}
          <optgroup label="Catalog">
            {catalog.roles.map((r) => (
              <option key={r.key} value={r.key}>
                {r.title}
              </option>
            ))}
          </optgroup>
          {team.customRoles.length > 0 && (
            <optgroup label="Custom roles">
              {team.customRoles.map((r) => (
                <option key={r.key} value={r.key}>
                  {r.title}
                </option>
              ))}
            </optgroup>
          )}
        </select>
      </label>

      {topOrgId && (
        <BindingPicker
          teamId={topOrgId}
          agentNodeId={agent.id}
          teamPath={path}
          sameRoleNodeIds={sameRoleNodeIds}
        />
      )}

      <SalaryEditor
        salary={agent.salary}
        defaultSalary={role?.defaultSalary}
        invalid={salaryBad}
        onChange={(s) => store.updateSalary(path, agent.id, s)}
      />

      <ExtensionsEditor
        extensions={agent.extensions}
        onInstructions={(v) => store.updateInstructions(path, agent.id, v)}
        onResponsibilities={(v) => store.setAddedResponsibilities(path, agent.id, v)}
      />

      <div className="border-t border-border pt-3">
        <Button
          variant="danger"
          onClick={() => {
            store.deleteAgent(path, agent.id);
            clear();
          }}
        >
          Delete agent
        </Button>
      </div>
    </div>
  );
}
