// The portfolio home (design/organizations/05-ux-portfolio §2, milestone C1): the operator's
// landing surface. Organizations render as hard-walled sections — identity, theme, purpose —
// with their teams as read-only cards inside; the only cross-organization act on this page is
// the operator's own custody transfer (Move…).
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useCatalog, indexCatalog } from "../api/catalog";
import { useDeleteTeam, useImportTeam } from "../api/teams";
import { useCreateOrg, useMoveTeam, usePortfolio, type PortfolioOrg } from "../api/orgs";
import { useCapacity } from "../api/capacity";
import { WindowGauge } from "../components/capacity/CapacityConsole";
import { apiGet, ApiError } from "../api/client";
import type { OrgSummary } from "../api/types";
import { LeafMark } from "../components/AppHeader";
import { TeamCard } from "../components/list/TeamCard";
import {
  Button,
  CenteredSpinner,
  ConfirmDialog,
  EmptyState,
  useToast,
} from "../components/common";
import { downloadJson, pickJsonFile } from "../lib/download";
import { slugify } from "../lib/format";

const ORG_COLORS: Record<string, string> = {
  sage: "#5B7F52",
  indigo: "#4F46E5",
  amber: "#B45309",
  rose: "#BE123C",
  slate: "#475569",
};

function orgColor(org: PortfolioOrg): string {
  return ORG_COLORS[String(org.theme?.color ?? "")] ?? "#6b7280";
}

export function PortfolioPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const portfolio = usePortfolio();
  const catalog = useCatalog();
  const del = useDeleteTeam();
  const importTeam = useImportTeam();
  const createOrg = useCreateOrg();
  const moveTeam = useMoveTeam();

  const [toDelete, setToDelete] = useState<OrgSummary | null>(null);
  const [toMove, setToMove] = useState<OrgSummary | null>(null);
  const [showNewOrg, setShowNewOrg] = useState(false);
  const [orgName, setOrgName] = useState("");
  const [orgKey, setOrgKey] = useState("");
  const [orgPurpose, setOrgPurpose] = useState("");

  const capacity = useCapacity();
  const index = catalog.data ? indexCatalog(catalog.data) : null;
  const orgs = portfolio.data?.organizations ?? [];
  const teamCount = orgs.reduce((n, o) => n + o.teams.length, 0);

  async function handleExport(summary: OrgSummary) {
    try {
      const res = await fetch(`/api/teams/${summary.id}/export`);
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        toast(body?.error?.message ?? "Export blocked by validation errors.", "error");
        return;
      }
      const text = await res.text();
      downloadJson(`${slugify(summary.name)}.team.json`, text);
      toast("Exported.", "success");
    } catch {
      toast("Export failed.", "error");
    }
  }

  async function handleDuplicate(summary: OrgSummary) {
    try {
      const doc = await apiGet(`/teams/${summary.id}`);
      await importTeam.mutateAsync(doc);
      toast("Duplicated.", "success");
    } catch {
      toast("Duplicate failed.", "error");
    }
  }

  async function handleImport() {
    try {
      const doc = await pickJsonFile();
      if (!doc) return;
      const result = await importTeam.mutateAsync(doc);
      toast("Imported.", "success");
      navigate(`/teams/${result.document.id}`);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Could not read that file.";
      toast(msg, "error");
    }
  }

  async function handleCreateOrg() {
    try {
      await createOrg.mutateAsync({
        key: orgKey || slugify(orgName),
        name: orgName,
        purpose: orgPurpose,
      });
      toast("Organization created.", "success");
      setShowNewOrg(false);
      setOrgName("");
      setOrgKey("");
      setOrgPurpose("");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not create it.", "error");
    }
  }

  return (
    <div className="min-h-full">
      <header className="flex items-center justify-between border-b border-border bg-surface px-6 py-3">
        <div>
          <h1 className="text-base font-semibold text-ink">Portfolio</h1>
          <p className="text-xs text-ink-muted">
            Organizations and their teams — create an organization, add a team
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={handleImport}>
            Import team
          </Button>
          <Button variant="secondary" onClick={() => setShowNewOrg(true)}>
            New organization
          </Button>
          <Button variant="primary" onClick={() => navigate("/teams/new")}>
            New team
          </Button>
        </div>
      </header>

      {/* The capacity strip (06 §1.1): headline gauges, always visible at home. */}
      {capacity.data?.enabled && capacity.data.accounts.length > 0 && (
        <div className="border-b border-border bg-surface-2/40 px-6 py-2">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-1">
            {capacity.data.accounts.map((acct) => {
              const headline = acct.windows.find((w) => w.key === acct.headlineWindow)
                ?? acct.windows.find((w) => w.source != null);
              if (!headline) return null;
              return (
                <div key={acct.id} className="flex items-center gap-2">
                  <span className="text-[11px] text-ink-muted">{acct.label}</span>
                  <WindowGauge w={headline} />
                </div>
              );
            })}
            <a href="/capacity" className="ml-auto text-[11px] text-ink-muted hover:text-ink hover:underline">
              capacity console →
            </a>
          </div>
        </div>
      )}

      <main className="mx-auto max-w-6xl px-6 py-8">
        {portfolio.isLoading ? (
          <CenteredSpinner label="Loading the portfolio…" />
        ) : teamCount > 0 || orgs.length > 1 ? (
          <div className="flex flex-col gap-10">
            {orgs.map((org) => (
              <section key={org.id}>
                <div
                  className="mb-3 flex items-baseline gap-3 border-l-4 pl-3"
                  style={{ borderColor: orgColor(org) }}
                >
                  <Link to={`/orgs/${org.id}`} className="text-sm font-semibold text-ink hover:underline">
                    {org.name}
                  </Link>
                  <span className="text-xs text-ink-subtle">{org.key}</span>
                  {org.purpose && (
                    <span className="truncate text-xs text-ink-muted">{org.purpose}</span>
                  )}
                  <span className="ml-auto text-xs text-ink-subtle">
                    {org.teams.length} team{org.teams.length === 1 ? "" : "s"}
                  </span>
                </div>
                {org.teams.length > 0 ? (
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {org.teams.map((s) => {
                      const type = index?.orgTypes.get(s.organizationType);
                      return (
                        <TeamCard
                          key={s.id}
                          summary={s}
                          section={type?.section}
                          typeTitle={type?.title}
                          actuation={s.actuation}
                          onExport={() => handleExport(s)}
                          onDuplicate={() => handleDuplicate(s)}
                          onDelete={() => setToDelete(s)}
                          onMove={orgs.length > 1 ? () => setToMove(s) : undefined}
                        />
                      );
                    })}
                  </div>
                ) : (
                  <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-xs text-ink-subtle">
                    No teams yet — move one here, or create a new team.
                  </p>
                )}
              </section>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<LeafMark size={48} />}
            title="The chart isn't a diagram of the system — it is the system."
            action={
              <Button variant="primary" onClick={() => navigate("/teams/new")}>
                Create your first team
              </Button>
            }
          >
            Define a team — roles, a reporting chain, the dependencies between pods — and
            Canopy serializes it into a single document you can hand off, version, and run.
          </EmptyState>
        )}
      </main>

      {/* New organization */}
      <ConfirmDialog
        open={showNewOrg}
        title="New organization"
        confirmLabel="Create"
        onCancel={() => setShowNewOrg(false)}
        onConfirm={handleCreateOrg}
      >
        <div className="flex flex-col gap-2 text-left">
          <label className="text-xs text-ink-muted">
            Name
            <input
              className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-ink"
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              placeholder="Canopy Inc."
            />
          </label>
          <label className="text-xs text-ink-muted">
            Key (kebab-case, permanent)
            <input
              className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-ink"
              value={orgKey}
              onChange={(e) => setOrgKey(e.target.value)}
              placeholder={slugify(orgName) || "canopy-inc"}
            />
          </label>
          <label className="text-xs text-ink-muted">
            Purpose
            <input
              className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-ink"
              value={orgPurpose}
              onChange={(e) => setOrgPurpose(e.target.value)}
              placeholder="One sentence, shown on the card"
            />
          </label>
        </div>
      </ConfirmDialog>

      {/* Move team (custody transfer) */}
      <ConfirmDialog
        open={!!toMove}
        title={`Move “${toMove?.name}”?`}
        confirmLabel="Close"
        onCancel={() => setToMove(null)}
        onConfirm={() => setToMove(null)}
      >
        <div className="flex flex-col gap-2 text-left">
          <p className="text-xs text-ink-muted">
            A move is a custody transfer: blocked while the team is actuated, audited, and its
            on-disk home moves with it.
          </p>
          {orgs
            .filter((o) => !o.teams.some((t) => t.id === toMove?.id))
            .map((o) => (
              <Button
                key={o.id}
                variant="secondary"
                onClick={async () => {
                  if (!toMove) return;
                  try {
                    await moveTeam.mutateAsync({ teamId: toMove.id, organizationId: o.id });
                    toast(`Moved to ${o.name}.`, "success");
                    setToMove(null);
                  } catch (err) {
                    toast(err instanceof ApiError ? err.message : "Move failed.", "error");
                  }
                }}
              >
                → {o.name} ({o.key})
              </Button>
            ))}
        </div>
      </ConfirmDialog>

      <ConfirmDialog
        open={!!toDelete}
        title="Delete team?"
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
        “{toDelete?.name}” and its nested teams will be permanently removed.
      </ConfirmDialog>
    </div>
  );
}
