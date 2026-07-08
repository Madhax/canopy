// Phase 2 · Actuate — the organizations you can spin up. Each row reuses the editor's
// ActuationControls (▶ Actuate / live status / Deactuate + readiness dialog), so you can actuate
// straight from the list. Invalid orgs point back to the editor to fix first.
import { useNavigate } from "react-router-dom";
import { indexCatalog, useCatalog } from "../api/catalog";
import { useOrganizations } from "../api/organizations";
import type { OrgSummary } from "../api/types";
import { LeafMark } from "../components/AppHeader";
import { ActuationControls } from "../components/editor/ActuationControls";
import { Button, CenteredSpinner, EmptyState } from "../components/common";

export function ActuatePage() {
  const navigate = useNavigate();
  const orgs = useOrganizations();
  const catalog = useCatalog();
  const index = catalog.data ? indexCatalog(catalog.data) : null;

  return (
    <div className="min-h-full">
      <header className="flex items-center justify-between border-b border-border bg-surface px-6 py-3">
        <div>
          <h1 className="text-base font-semibold text-ink">Actuate</h1>
          <p className="text-xs text-ink-muted">
            Phase 2 · Actuate — spin up an organization's agents and make it ready for work
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-8">
        {orgs.isLoading ? (
          <CenteredSpinner label="Loading organizations…" />
        ) : orgs.data && orgs.data.length > 0 ? (
          <div className="flex flex-col gap-3">
            {orgs.data.map((s) => (
              <ActuateRow
                key={s.id}
                summary={s}
                typeTitle={index?.orgTypes.get(s.organizationType)?.title}
                onOpen={() => navigate(`/organizations/${s.id}`)}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<LeafMark size={48} />}
            title="No organizations to actuate yet."
            action={
              <Button variant="primary" onClick={() => navigate("/organizations/new")}>
                Create an organization
              </Button>
            }
          >
            Build an organization first — then come back here to spin up its agents.
          </EmptyState>
        )}
      </main>
    </div>
  );
}

function ActuateRow({
  summary,
  typeTitle,
  onOpen,
}: {
  summary: OrgSummary;
  typeTitle?: string;
  onOpen: () => void;
}) {
  const nodes = `${summary.agentCount} ${summary.agentCount === 1 ? "node" : "nodes"}`;
  const subs = summary.childOrgCount > 0 ? ` · ${summary.childOrgCount} sub-orgs` : "";

  return (
    <div className="flex items-center justify-between gap-4 rounded-xl border border-border bg-surface px-4 py-3">
      <button onClick={onOpen} className="min-w-0 flex-1 text-left" title="Open in the editor">
        <div className="flex items-center gap-2">
          <span className="truncate font-medium text-ink">{summary.name}</span>
          {!summary.valid && (
            <span className="rounded-full border border-warn/40 bg-warn/10 px-2 py-0.5 text-[11px] font-medium text-warn">
              needs fixes
            </span>
          )}
        </div>
        <div className="mt-0.5 truncate text-xs text-ink-muted">
          {typeTitle ?? summary.organizationType} · {nodes}
          {subs}
        </div>
      </button>

      <div className="shrink-0">
        {summary.valid ? (
          <ActuationControls orgId={summary.id} />
        ) : (
          <Button size="sm" variant="secondary" onClick={onOpen}>
            Fix in editor
          </Button>
        )}
      </div>
    </div>
  );
}
