// Helpers for reading/updating a nested organization within the top-level document.
// The store keeps ONE top-level document (docs §7.5); a drill-in path is a list of child-org ids.
import type { OrganizationDoc } from "../schema/organization";

/** Resolve the organization at `path` (child-org ids from the top). `[]` -> the top document. */
export function getOrgAtPath(doc: OrganizationDoc, path: string[]): OrganizationDoc {
  let cur = doc;
  for (const orgId of path) {
    const child = cur.childOrganizations.find((c) => c.organization.id === orgId);
    if (!child) return cur; // stale path — fall back to the deepest valid org
    cur = child.organization;
  }
  return cur;
}

/** Return a new top-level document with the org at `path` transformed by `updater`. Immutable. */
export function updateOrgAtPath(
  doc: OrganizationDoc,
  path: string[],
  updater: (org: OrganizationDoc) => void,
): OrganizationDoc {
  const clone: OrganizationDoc = structuredClone(doc);
  const target = getOrgAtPath(clone, path);
  updater(target);
  return clone;
}

/** Breadcrumb trail: [{id, name}] from the top document down to `path`. */
export function breadcrumbs(
  doc: OrganizationDoc,
  path: string[],
): { id: string; name: string; path: string[] }[] {
  const trail = [{ id: doc.id, name: doc.name, path: [] as string[] }];
  let cur = doc;
  const acc: string[] = [];
  for (const orgId of path) {
    const child = cur.childOrganizations.find((c) => c.organization.id === orgId);
    if (!child) break;
    cur = child.organization;
    acc.push(orgId);
    trail.push({ id: cur.id, name: cur.name, path: [...acc] });
  }
  return trail;
}
