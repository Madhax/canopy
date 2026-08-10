// Helpers for reading/updating a nested team within the top-level document.
// The store keeps ONE top-level document (docs §7.5); a drill-in path is a list of child-team ids.
import type { TeamDoc } from "../schema/team";

/** Resolve the team at `path` (child-team ids from the top). `[]` -> the top document. */
export function getOrgAtPath(doc: TeamDoc, path: string[]): TeamDoc {
  let cur = doc;
  for (const teamId of path) {
    const child = cur.childTeams.find((c) => c.team.id === teamId);
    if (!child) return cur; // stale path — fall back to the deepest valid team
    cur = child.team;
  }
  return cur;
}

/** Return a new top-level document with the team at `path` transformed by `updater`. Immutable. */
export function updateOrgAtPath(
  doc: TeamDoc,
  path: string[],
  updater: (team: TeamDoc) => void,
): TeamDoc {
  const clone: TeamDoc = structuredClone(doc);
  const target = getOrgAtPath(clone, path);
  updater(target);
  return clone;
}

/** Breadcrumb trail: [{id, name}] from the top document down to `path`. */
export function breadcrumbs(
  doc: TeamDoc,
  path: string[],
): { id: string; name: string; path: string[] }[] {
  const trail = [{ id: doc.id, name: doc.name, path: [] as string[] }];
  let cur = doc;
  const acc: string[] = [];
  for (const teamId of path) {
    const child = cur.childTeams.find((c) => c.team.id === teamId);
    if (!child) break;
    cur = child.team;
    acc.push(teamId);
    trail.push({ id: cur.id, name: cur.name, path: [...acc] });
  }
  return trail;
}
