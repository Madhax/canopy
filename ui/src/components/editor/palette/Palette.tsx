import { useMemo, useState } from "react";
import type { Catalog, OrgType } from "../../../schema/catalog";
import { ROLE_GROUP_LABELS, roleGroupColor } from "../../../lib/theme";
import { RoleRow } from "./RoleRow";
import { FormationRow } from "./FormationRow";

interface Props {
  catalog: Catalog;
  orgType: OrgType | undefined;
  onPlaceRole: (roleKey: string) => void;
  onStampFormation: (formationKey: string) => void;
  onAddCustomRole: () => void;
  onAddChildOrg: () => void;
}

export function Palette({
  catalog,
  orgType,
  onPlaceRole,
  onStampFormation,
  onAddCustomRole,
  onAddChildOrg,
}: Props) {
  const [query, setQuery] = useState("");
  const [wholeCatalog, setWholeCatalog] = useState(false);

  const paletteKeys = useMemo(() => new Set(orgType?.rolePalette ?? []), [orgType]);
  const q = query.trim().toLowerCase();
  const searching = q.length > 0;

  // Search always spans the whole catalog and auto-flips the toggle on match (docs §7.4).
  const roles = useMemo(() => {
    const all = catalog.roles;
    const filtered = all.filter((r) => {
      const inScope = wholeCatalog || searching || paletteKeys.has(r.key);
      const matches = !q || r.title.toLowerCase().includes(q) || r.key.includes(q);
      return inScope && matches;
    });
    const byGroup = new Map<string, typeof filtered>();
    for (const r of filtered) {
      if (!byGroup.has(r.group)) byGroup.set(r.group, []);
      byGroup.get(r.group)!.push(r);
    }
    return byGroup;
  }, [catalog.roles, wholeCatalog, searching, paletteKeys, q]);

  const formations = useMemo(() => {
    const suggested = new Set(orgType?.formations ?? []);
    const list = catalog.formations.filter(
      (f) => !q || f.title.toLowerCase().includes(q) || f.key.includes(q),
    );
    return {
      suggested: list.filter((f) => suggested.has(f.key)),
      rest: list.filter((f) => !suggested.has(f.key)),
    };
  }, [catalog.formations, orgType, q]);

  return (
    <aside className="flex w-[260px] shrink-0 flex-col border-r border-border bg-surface">
      <div className="border-b border-border p-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search roles & formations…"
          className="w-full rounded-md border border-border bg-canvas px-2.5 py-1.5 text-sm outline-none focus:border-accent"
        />
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Roles */}
        <div className="p-3">
          <div className="mb-1.5 flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Roles</h3>
            {!searching && (
              <button
                onClick={() => setWholeCatalog((v) => !v)}
                className="text-[11px] text-accent hover:underline"
              >
                {wholeCatalog ? "archetype only" : "whole catalog"}
              </button>
            )}
          </div>
          {[...roles.entries()].map(([group, rs]) => (
            <div key={group} className="mb-2">
              <div className="mb-0.5 flex items-center gap-1.5 px-1 text-[10px] uppercase tracking-wide text-ink-subtle">
                <span className="size-1.5 rounded-full" style={{ background: roleGroupColor(group) }} />
                {ROLE_GROUP_LABELS[group] ?? group}
              </div>
              {rs.map((r) => (
                <RoleRow key={r.key} role={r} onPlace={() => onPlaceRole(r.key)} />
              ))}
            </div>
          ))}
          {roles.size === 0 && <p className="px-1 text-xs text-ink-subtle">No matching roles.</p>}
        </div>

        {/* Formations */}
        <div className="border-t border-border p-3">
          <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
            Formations
          </h3>
          {formations.suggested.map((f) => (
            <FormationRow key={f.key} formation={f} catalog={catalog} onStamp={() => onStampFormation(f.key)} />
          ))}
          {formations.rest.length > 0 && (
            <details className="mt-1">
              <summary className="cursor-pointer px-1 text-[11px] text-ink-muted hover:text-ink">
                All formations ({formations.rest.length})
              </summary>
              {formations.rest.map((f) => (
                <FormationRow key={f.key} formation={f} catalog={catalog} onStamp={() => onStampFormation(f.key)} />
              ))}
            </details>
          )}
        </div>

        {/* Special */}
        <div className="border-t border-border p-3">
          <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
            Special
          </h3>
          <button
            onClick={onAddCustomRole}
            className="w-full rounded-md px-2 py-1.5 text-left text-sm text-ink hover:bg-surface-2"
          >
            ＋ Custom role
          </button>
          <button
            onClick={onAddChildOrg}
            className="w-full rounded-md px-2 py-1.5 text-left text-sm text-ink hover:bg-surface-2"
          >
            ＋ Child organization
          </button>
        </div>
      </div>
    </aside>
  );
}
