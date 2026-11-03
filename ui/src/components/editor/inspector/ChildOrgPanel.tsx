import type { Catalog } from "../../../schema/catalog";
import type { ChildTeamDoc, TeamDoc } from "../../../schema/team";
import { useDocumentStore } from "../../../store/documentStore";
import { useSelectionStore } from "../../../store/selectionStore";
import { Button } from "../../common";

interface Props {
  child: ChildTeamDoc;
  team: TeamDoc;
  catalog: Catalog;
  onOpen: () => void;
}

export function ChildOrgPanel({ child, team, catalog, onOpen }: Props) {
  const store = useDocumentStore();
  const path = useSelectionStore((s) => s.path);
  const clear = useSelectionStore((s) => s.clear);

  const type = catalog.organizationTypes.find((o) => o.key === child.team.organizationType);
  const mountAgent = team.agents.find((a) => a.id === child.mountAgentId);
  const mountInvalid = !mountAgent;

  return (
    <div className="flex flex-col gap-4 p-4">
      <div>
        <h3 className="text-sm font-semibold text-ink">{child.team.name}</h3>
        <p className="text-xs text-ink-muted">{type?.title ?? child.team.organizationType}</p>
      </div>

      <label className="flex flex-col gap-1">
        <span
          className={`text-xs font-semibold uppercase tracking-wide ${
            mountInvalid ? "text-danger" : "text-ink-muted"
          }`}
        >
          Reports to
        </span>
        <select
          value={child.mountAgentId}
          aria-invalid={mountInvalid || undefined}
          onChange={(e) =>
            store.applyBatch(path, (o) => {
              const c = o.childTeams.find(
                (x) => x.team.id === child.team.id,
              );
              if (c) c.mountAgentId = e.target.value;
            })
          }
          className={`rounded-md border bg-canvas px-2 py-1.5 text-sm outline-none ${
            mountInvalid
              ? "border-danger text-danger ring-1 ring-danger/40 focus:border-danger"
              : "border-border focus:border-accent"
          }`}
        >
          {mountInvalid && (
            <option value={child.mountAgentId}>⚠ {child.mountAgentId} (missing)</option>
          )}
          {team.agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
        {mountInvalid && (
          <span className="text-xs text-danger">Mount agent no longer exists.</span>
        )}
      </label>

      <Button variant="primary" onClick={onOpen}>
        Open ⤢
      </Button>

      <div className="border-t border-border pt-3">
        <Button
          variant="danger"
          onClick={() => {
            store.applyBatch(path, (o) => {
              o.childTeams = o.childTeams.filter(
                (x) => x.team.id !== child.team.id,
              );
            });
            clear();
          }}
        >
          Delete child team
        </Button>
      </div>
    </div>
  );
}
