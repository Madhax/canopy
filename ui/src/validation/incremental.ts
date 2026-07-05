// Constant-ish incremental predicates for React Flow's isValidConnection (docs §4.3).
// Each evaluates only the rules a single new connection can break, so the canvas can reject a
// bad drag before it lands and toast the exact rule message.
import type { OrganizationDoc } from "../schema/organization";
import { CODE_MESSAGES } from "./codes";

export interface ConnectionCheck {
  ok: boolean;
  code?: string;
  message?: string;
}

const OK: ConnectionCheck = { ok: true };

function reject(code: string): ConnectionCheck {
  return { ok: false, code, message: CODE_MESSAGES[code] };
}

/** May `agentId` be re-parented under `newManagerId` without forming a reporting cycle? */
export function checkReparent(
  doc: OrganizationDoc,
  agentId: string,
  newManagerId: string,
): ConnectionCheck {
  if (agentId === newManagerId) return reject("REPORTS_CYCLE");
  const managerOf = new Map<string, string | null>();
  for (const a of doc.agents) managerOf.set(a.id, a.managerId ?? null);
  if (!managerOf.has(newManagerId)) return reject("MANAGER_DANGLING");

  // Walk up from the proposed manager; if we reach the agent, this closes a cycle.
  let cur: string | null | undefined = newManagerId;
  const seen = new Set<string>();
  while (cur != null) {
    if (cur === agentId) return reject("REPORTS_CYCLE");
    if (seen.has(cur)) break;
    seen.add(cur);
    cur = managerOf.get(cur) ?? null;
  }
  return OK;
}

/** May a dependency `from -> to` be drawn on the current canvas? */
export function checkDependency(
  doc: OrganizationDoc,
  from: string,
  to: string,
): ConnectionCheck {
  if (from === to) return reject("DEP_SELF");

  // endpoints and their sibling group (agent.managerId, or child org.mountAgentId)
  const parentOf = new Map<string, string | null>();
  for (const a of doc.agents) parentOf.set(a.id, a.managerId ?? null);
  for (const c of doc.childOrganizations) parentOf.set(c.organization.id, c.mountAgentId);

  if (!parentOf.has(from) || !parentOf.has(to)) return reject("DEP_DANGLING");
  if (parentOf.get(from) !== parentOf.get(to)) return reject("DEP_NOT_SIBLINGS");

  for (const d of doc.dependencies) {
    if (d.from === from && d.to === to) return reject("DEP_DUPLICATE");
  }

  // Would adding from->to close a cycle? True iff `to` already reaches `from`.
  const adj = new Map<string, string[]>();
  for (const d of doc.dependencies) {
    if (!adj.has(d.from)) adj.set(d.from, []);
    adj.get(d.from)!.push(d.to);
  }
  const stack = [to];
  const seen = new Set<string>();
  while (stack.length) {
    const node = stack.pop()!;
    if (node === from) return reject("DEP_CYCLE");
    if (seen.has(node)) continue;
    seen.add(node);
    for (const nxt of adj.get(node) ?? []) stack.push(nxt);
  }
  return OK;
}
