// Which model feeds a node (UX-35): its own binding wins, else the team-default profile, else
// nothing. Mirrors ProfileStore.resolve_binding on the server — the canvas, the inspector and
// actuation readiness must all give the same answer.
import type { AgentBinding, AgentProfile } from "../schema/actuation";

export type NodeModelSource = "node" | "team-default" | "unspecified" | "dangling";

export interface NodeModelInfo {
  source: NodeModelSource;
  /** The profile powering the node — absent when unspecified or dangling. */
  profile?: AgentProfile;
}

/** True when the node cannot actuate for want of a model. */
export function modelInvalid(info: NodeModelInfo | undefined): boolean {
  return !!info && (info.source === "unspecified" || info.source === "dangling");
}

function samePath(a: string[], b: string[]) {
  return a.length === b.length && a.every((x, i) => x === b[i]);
}

export function resolveNodeModel(
  nodeId: string,
  teamPath: string[],
  bindings: AgentBinding[],
  profiles: AgentProfile[],
  teamDefaultId: string | null,
): NodeModelInfo {
  const byId = new Map(profiles.map((p) => [p.id, p]));
  const own = bindings.find((b) => b.agentNodeId === nodeId && samePath(b.teamPath, teamPath));
  if (own) {
    const profile = byId.get(own.profileId);
    return profile ? { source: "node", profile } : { source: "dangling" };
  }
  const def = teamDefaultId ? byId.get(teamDefaultId) : undefined;
  return def ? { source: "team-default", profile: def } : { source: "unspecified" };
}

/** Short label for a node's model: "mock-1", "claude-sonnet-5", … */
export function modelLabel(info: NodeModelInfo): string {
  if (info.profile) return `${info.profile.provider} · ${info.profile.model}`;
  return info.source === "dangling" ? "profile missing" : "model unspecified";
}
