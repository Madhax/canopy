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

      <fieldset className="flex flex-col gap-1">
        <legend className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
          Starts when
        </legend>
        <div className="flex gap-2" role="radiogroup" aria-label="Starts when">
          {(
            [
              { value: "accepted", label: "work is accepted", hint: "consume — waits for sign-off" },
              { value: "delivered", label: "work is submitted", hint: "verify — reviews the submission" },
            ] as const
          ).map((opt) => (
            <button
              key={opt.value}
              type="button"
              role="radio"
              aria-checked={(dependency.resolveOn ?? "accepted") === opt.value}
              title={opt.hint}
              onClick={() => store.setDependencyResolveOn(path, dependency.id, opt.value)}
              className={`flex-1 rounded-md border px-2 py-1.5 text-sm ${
                (dependency.resolveOn ?? "accepted") === opt.value
                  ? "border-accent bg-surface-2 font-semibold text-ink"
                  : "border-border bg-canvas text-ink-muted hover:border-accent"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </fieldset>

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
