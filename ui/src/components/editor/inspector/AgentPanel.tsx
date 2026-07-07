import type { Catalog } from "../../../schema/catalog";
import type { Agent, OrganizationDoc } from "../../../schema/organization";
import { useDocumentStore } from "../../../store/documentStore";
import { useSelectionStore } from "../../../store/selectionStore";
import { roleGroupColor } from "../../../lib/theme";
import { Button } from "../../common";
import { BindingPicker } from "./BindingPicker";
import { SalaryEditor } from "./SalaryEditor";
import { ExtensionsEditor } from "./ExtensionsEditor";

interface Props {
  agent: Agent;
  org: OrganizationDoc;
  catalog: Catalog;
}

export function AgentPanel({ agent, org, catalog }: Props) {
  const store = useDocumentStore();
  const path = useSelectionStore((s) => s.path);
  const clear = useSelectionStore((s) => s.clear);
  const topOrgId = useDocumentStore((s) => s.doc?.id);
  const sameRoleNodeIds = org.agents
    .filter((a) => a.role.key === agent.role.key)
    .map((a) => a.id);

  const role =
    catalog.roles.find((r) => r.key === agent.role.key) ??
    org.customRoles.find((r) => r.key === agent.role.key);
  const roleUnknown = !role;
  const color = roleGroupColor(role?.group ?? "custom");

  return (
    <div className="flex flex-col gap-5 p-4">
      <label className="flex flex-col gap-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Name</span>
        <input
          value={agent.name}
          onChange={(e) => store.renameAgent(path, agent.id, e.target.value)}
          className="rounded-md border border-border bg-canvas px-2 py-1.5 text-sm outline-none focus:border-accent"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-ink-muted">
          Role
          <span className="font-normal normal-case" style={{ color }}>
            {agent.role.key}@{agent.role.version}
          </span>
        </span>
        <select
          value={agent.role.key}
          onChange={(e) => {
            const r =
              catalog.roles.find((x) => x.key === e.target.value) ??
              org.customRoles.find((x) => x.key === e.target.value);
            store.reassignRole(path, agent.id, e.target.value, r?.version ?? 1);
          }}
          className={`rounded-md border bg-canvas px-2 py-1.5 text-sm outline-none focus:border-accent ${
            roleUnknown ? "border-warn" : "border-border"
          }`}
        >
          {roleUnknown && <option value={agent.role.key}>⚠ {agent.role.key} (unknown)</option>}
          <optgroup label="Catalog">
            {catalog.roles.map((r) => (
              <option key={r.key} value={r.key}>
                {r.title}
              </option>
            ))}
          </optgroup>
          {org.customRoles.length > 0 && (
            <optgroup label="Custom roles">
              {org.customRoles.map((r) => (
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
          orgId={topOrgId}
          agentNodeId={agent.id}
          orgPath={path}
          sameRoleNodeIds={sameRoleNodeIds}
        />
      )}

      <SalaryEditor
        salary={agent.salary}
        defaultSalary={role?.defaultSalary}
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
