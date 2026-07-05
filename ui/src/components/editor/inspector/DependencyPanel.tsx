import type { Dependency, OrganizationDoc } from "../../../schema/organization";
import { useDocumentStore } from "../../../store/documentStore";
import { useSelectionStore } from "../../../store/selectionStore";
import { Button } from "../../common";

interface Props {
  dependency: Dependency;
  org: OrganizationDoc;
}

export function DependencyPanel({ dependency, org }: Props) {
  const store = useDocumentStore();
  const path = useSelectionStore((s) => s.path);
  const clear = useSelectionStore((s) => s.clear);

  const label = (id: string) =>
    org.agents.find((a) => a.id === id)?.name ??
    org.childOrganizations.find((c) => c.organization.id === id)?.organization.name ??
    id;

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="rounded-md border border-border bg-surface-2 p-3 text-sm">
        <span className="font-semibold text-ink">{label(dependency.from)}</span>
        <span className="text-ink-muted"> depends on </span>
        <span className="font-semibold text-ink">{label(dependency.to)}</span>
      </div>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Note</span>
        <textarea
          value={dependency.note ?? ""}
          onChange={(e) => store.updateDependencyNote(path, dependency.id, e.target.value)}
          rows={2}
          placeholder="Optional annotation…"
          className="resize-y rounded-md border border-border bg-canvas px-2 py-1.5 text-sm outline-none focus:border-accent"
        />
      </label>

      <Button
        variant="danger"
        onClick={() => {
          store.removeDependency(path, dependency.id);
          clear();
        }}
      >
        Delete dependency
      </Button>
    </div>
  );
}
