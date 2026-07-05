import type { Catalog } from "../../../schema/catalog";
import type { ChildOrganizationDoc, OrganizationDoc } from "../../../schema/organization";
import { useDocumentStore } from "../../../store/documentStore";
import { useSelectionStore } from "../../../store/selectionStore";
import { Button } from "../../common";

interface Props {
  child: ChildOrganizationDoc;
  org: OrganizationDoc;
  catalog: Catalog;
  onOpen: () => void;
}

export function ChildOrgPanel({ child, org, catalog, onOpen }: Props) {
  const store = useDocumentStore();
  const path = useSelectionStore((s) => s.path);
  const clear = useSelectionStore((s) => s.clear);

  const type = catalog.organizationTypes.find((o) => o.key === child.organization.organizationType);
  const mountAgent = org.agents.find((a) => a.id === child.mountAgentId);

  return (
    <div className="flex flex-col gap-4 p-4">
      <div>
        <h3 className="text-sm font-semibold text-ink">{child.organization.name}</h3>
        <p className="text-xs text-ink-muted">{type?.title ?? child.organization.organizationType}</p>
      </div>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
          Reports to
        </span>
        <select
          value={child.mountAgentId}
          onChange={(e) =>
            store.applyBatch(path, (o) => {
              const c = o.childOrganizations.find(
                (x) => x.organization.id === child.organization.id,
              );
              if (c) c.mountAgentId = e.target.value;
            })
          }
          className="rounded-md border border-border bg-canvas px-2 py-1.5 text-sm outline-none focus:border-accent"
        >
          {org.agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
        {!mountAgent && <span className="text-xs text-warn">Mount agent no longer exists.</span>}
      </label>

      <Button variant="primary" onClick={onOpen}>
        Open ⤢
      </Button>

      <div className="border-t border-border pt-3">
        <Button
          variant="danger"
          onClick={() => {
            store.applyBatch(path, (o) => {
              o.childOrganizations = o.childOrganizations.filter(
                (x) => x.organization.id !== child.organization.id,
              );
            });
            clear();
          }}
        >
          Delete child organization
        </Button>
      </div>
    </div>
  );
}
