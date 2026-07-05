import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCatalog, indexCatalog } from "../api/catalog";
import {
  useOrganizations,
  useDeleteOrganization,
  useImportOrganization,
} from "../api/organizations";
import { apiGet, ApiError } from "../api/client";
import type { OrgSummary } from "../api/types";
import { LeafMark } from "../components/AppHeader";
import { OrganizationCard } from "../components/list/OrganizationCard";
import { Button, CenteredSpinner, ConfirmDialog, EmptyState, useToast } from "../components/common";
import { downloadJson, pickJsonFile } from "../lib/download";
import { slugify } from "../lib/format";

export function OrganizationListPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const orgs = useOrganizations();
  const catalog = useCatalog();
  const del = useDeleteOrganization();
  const importOrg = useImportOrganization();
  const [toDelete, setToDelete] = useState<OrgSummary | null>(null);

  const index = catalog.data ? indexCatalog(catalog.data) : null;

  async function handleExport(summary: OrgSummary) {
    try {
      const res = await fetch(`/api/organizations/${summary.id}/export`);
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        toast(body?.error?.message ?? "Export blocked by validation errors.", "error");
        return;
      }
      const text = await res.text();
      downloadJson(`${slugify(summary.name)}.organization.json`, text);
      toast("Exported.", "success");
    } catch {
      toast("Export failed.", "error");
    }
  }

  async function handleDuplicate(summary: OrgSummary) {
    try {
      const doc = await apiGet(`/organizations/${summary.id}`);
      await importOrg.mutateAsync(doc);
      toast("Duplicated.", "success");
    } catch {
      toast("Duplicate failed.", "error");
    }
  }

  async function handleImport() {
    try {
      const doc = await pickJsonFile();
      if (!doc) return;
      const result = await importOrg.mutateAsync(doc);
      toast("Imported.", "success");
      navigate(`/organizations/${result.document.id}`);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Could not read that file.";
      toast(msg, "error");
    }
  }

  return (
    <div className="min-h-full">
      <header className="flex items-center justify-between border-b border-border bg-surface px-6 py-3">
        <div>
          <h1 className="text-base font-semibold text-ink">Organizations</h1>
          <p className="text-xs text-ink-muted">Phase 1 · Build — shape an org and serialize it</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={handleImport}>
            Import
          </Button>
          <Button variant="primary" onClick={() => navigate("/organizations/new")}>
            New organization
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        {orgs.isLoading ? (
          <CenteredSpinner label="Loading organizations…" />
        ) : orgs.data && orgs.data.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {orgs.data.map((s) => {
              const type = index?.orgTypes.get(s.organizationType);
              return (
                <OrganizationCard
                  key={s.id}
                  summary={s}
                  section={type?.section}
                  typeTitle={type?.title}
                  onExport={() => handleExport(s)}
                  onDuplicate={() => handleDuplicate(s)}
                  onDelete={() => setToDelete(s)}
                />
              );
            })}
          </div>
        ) : (
          <EmptyState
            icon={<LeafMark size={48} />}
            title="The chart isn't a diagram of the system — it is the system."
            action={
              <Button variant="primary" onClick={() => navigate("/organizations/new")}>
                Create your first organization
              </Button>
            }
          >
            Define an organization — roles, a reporting chain, the dependencies between teams — and
            Canopy serializes it into a single document you can hand off, version, and one day run.
          </EmptyState>
        )}
      </main>

      <ConfirmDialog
        open={!!toDelete}
        title="Delete organization?"
        danger
        confirmLabel="Delete"
        onCancel={() => setToDelete(null)}
        onConfirm={async () => {
          if (toDelete) {
            await del.mutateAsync(toDelete.id);
            toast("Deleted.", "success");
          }
          setToDelete(null);
        }}
      >
        “{toDelete?.name}” and its nested organizations will be permanently removed.
      </ConfirmDialog>
    </div>
  );
}
