import { useMemo, useState } from "react";
import type { Catalog, OrgType } from "../../api/types";
import { Badge } from "../common";
import { SECTION_LABELS, SECTION_ORDER, sectionColor } from "../../lib/theme";

interface Props {
  catalog: Catalog;
  selectedKey: string | null;
  onSelect: (type: OrgType) => void;
}

export function TypeStep({ catalog, selectedKey, onSelect }: Props) {
  const [query, setQuery] = useState("");

  const grouped = useMemo(() => {
    const q = query.trim().toLowerCase();
    const match = (o: OrgType) =>
      !q ||
      o.title.toLowerCase().includes(q) ||
      o.description.toLowerCase().includes(q) ||
      o.key.includes(q);
    const bySection = new Map<string, OrgType[]>();
    for (const o of catalog.organizationTypes) {
      if (!match(o)) continue;
      if (!bySection.has(o.section)) bySection.set(o.section, []);
      bySection.get(o.section)!.push(o);
    }
    return bySection;
  }, [catalog, query]);

  return (
    <div className="flex flex-col gap-5">
      <input
        autoFocus
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search organization types…"
        className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
      />
      {SECTION_ORDER.filter((s) => grouped.has(s)).map((section) => (
        <section key={section} className="flex flex-col gap-2">
          <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">
            <span className="size-2 rounded-full" style={{ background: sectionColor(section) }} />
            {SECTION_LABELS[section]}
          </h3>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {grouped.get(section)!.map((o) => (
              <button
                key={o.key}
                onClick={() => onSelect(o)}
                className={`flex flex-col gap-2 rounded-xl border p-3.5 text-left transition-colors ${
                  selectedKey === o.key
                    ? "border-accent bg-accent/5"
                    : "border-border bg-surface hover:border-border-strong"
                }`}
              >
                <div className="font-medium text-ink">{o.title}</div>
                <p className="text-xs leading-relaxed text-ink-muted">{o.description}</p>
                {o.exampleIntent && (
                  <p className="text-xs italic text-ink-subtle">“{o.exampleIntent}”</p>
                )}
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {o.rolePalette.slice(0, 4).map((r) => (
                    <Badge key={r} dot={false} className="text-[10px]">
                      {r}
                    </Badge>
                  ))}
                  {o.formations.map((f) => (
                    <Badge key={f} color={sectionColor(section)} className="text-[10px]">
                      {f}
                    </Badge>
                  ))}
                </div>
              </button>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
