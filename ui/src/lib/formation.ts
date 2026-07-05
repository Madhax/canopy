// Materialize a formation subtree client-side (mirrors server/src/canopy_server/seeds.py).
// Used by palette formation stamps: manager + members with fresh ids and slot-resolved deps.
import type { Catalog } from "../schema/catalog";
import type { Agent, Dependency, Salary } from "../schema/organization";
import { newAgentId, newDependencyId } from "./ids";
import { useSettingsStore } from "../store/settingsStore";

const MEMBER_Y = 300;
const MEMBER_DX = 240;

export function buildFormationSubtree(
  catalog: Catalog,
  formationKey: string,
  managerManagerId: string | null,
  origin: { x: number; y: number },
): { agents: Agent[]; dependencies: Dependency[] } {
  const formation = catalog.formations.find((f) => f.key === formationKey);
  if (!formation) return { agents: [], dependencies: [] };

  const agentFromRole = (roleKey: string, managerId: string | null, pos: { x: number; y: number }): Agent => {
    const role = catalog.roles.find((r) => r.key === roleKey);
    const salary: Salary = role
      ? { ...role.defaultSalary }
      : { perAssignmentAllowance: 120000, warnThresholdPct: 80, hardStop: true };
    return {
      id: newAgentId(),
      name: role?.title ?? roleKey,
      role: { key: roleKey, version: role?.version ?? 1 },
      managerId,
      extensions: { instructions: "", responsibilities: [] },
      salary,
      position: pos,
    };
  };

  const manager = agentFromRole(formation.manager.roleKey, managerManagerId, origin);
  const slotToId: Record<string, string> = { [formation.manager.slot]: manager.id };
  const agents: Agent[] = [manager];

  // Bottom-up: reports sit above the manager (smaller y); top-down: below.
  const memberDy = useSettingsStore.getState().layoutDirection === "BT" ? -MEMBER_Y : MEMBER_Y;
  const n = formation.members.length;
  const totalW = (n - 1) * MEMBER_DX;
  const startX = origin.x - totalW / 2;
  formation.members.forEach((m, i) => {
    const a = agentFromRole(m.roleKey, manager.id, {
      x: startX + i * MEMBER_DX,
      y: origin.y + memberDy,
    });
    slotToId[m.slot] = a.id;
    agents.push(a);
  });

  const dependencies: Dependency[] = [];
  for (const d of formation.dependencies) {
    const from = slotToId[d.from];
    const to = slotToId[d.to];
    if (from && to) dependencies.push({ id: newDependencyId(), from, to, note: null });
  }

  return { agents, dependencies };
}
