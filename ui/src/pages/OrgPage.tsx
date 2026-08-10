// One organization's page (design/organizations/05-ux-portfolio, C1 slice): identity,
// purpose, priority class, budget-at-a-glance, and the teams behind this org's wall.
// Editing is deliberately light at C1 — name/purpose; budgets get their console at C5.
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCatalog, indexCatalog } from "../api/catalog";
import { usePortfolio, type PortfolioOrg } from "../api/orgs";
import { apiSend, ApiError } from "../api/client";
import { TeamCard } from "../components/list/TeamCard";
import { Button, CenteredSpinner, useToast } from "../components/common";

const ORG_COLORS: Record<string, string> = {
  sage: "#5B7F52",
  indigo: "#4F46E5",
  amber: "#B45309",
  rose: "#BE123C",
  slate: "#475569",
};

export function OrgPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const qc = useQueryClient();
  const portfolio = usePortfolio();
  const catalog = useCatalog();
  const index = catalog.data ? indexCatalog(catalog.data) : null;

  const org: PortfolioOrg | undefined = portfolio.data?.organizations.find((o) => o.id === id);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState("");
  useEffect(() => {
    if (org) {
      setName(org.name);
      setPurpose(org.purpose);
    }
  }, [org?.id, org?.name, org?.purpose]);

  const save = useMutation({
    mutationFn: () => apiSend("PUT", `/orgs/${id}`, { name, purpose }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["portfolio"] });
      qc.invalidateQueries({ queryKey: ["orgs"] });
      setEditing(false);
      toast("Saved.", "success");
    },
    onError: (err) =>
      toast(err instanceof ApiError ? err.message : "Save failed.", "error"),
  });

  if (portfolio.isLoading) return <CenteredSpinner label="Loading…" />;
  if (!org) {
    return (
      <div className="p-8 text-sm text-ink-muted">
        No such organization. <Link className="underline" to="/">Back to the portfolio.</Link>
      </div>
    );
  }
  const color = ORG_COLORS[String(org.theme?.color ?? "")] ?? "#6b7280";
  const budget = org.budget ?? {};
  const ceiling = budget["weeklyCostCeilingUsd"];

  return (
    <div className="min-h-full">
      <header
        className="border-b border-border bg-surface px-6 py-4"
        style={{ borderTop: `3px solid ${color}` }}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-baseline gap-3">
              {editing ? (
                <input
                  className="rounded-md border border-border bg-surface px-2 py-1 text-base font-semibold text-ink"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              ) : (
                <h1 className="text-base font-semibold text-ink">{org.name}</h1>
              )}
              <span className="text-xs text-ink-subtle">{org.key}</span>
              <span className="rounded-full border border-border px-2 py-0.5 text-[11px] text-ink-muted">
                {org.priorityClass}
              </span>
            </div>
            {editing ? (
              <input
                className="mt-1 w-full max-w-xl rounded-md border border-border bg-surface px-2 py-1 text-xs text-ink"
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
                placeholder="One sentence, shown on the card"
              />
            ) : (
              <p className="mt-1 text-xs text-ink-muted">{org.purpose || "No purpose set."}</p>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {typeof ceiling === "number" && (
              <span className="text-xs text-ink-muted" title="Weekly cost ceiling (estimates)">
                ceiling ~${ceiling}/wk
              </span>
            )}
            {editing ? (
              <>
                <Button variant="secondary" onClick={() => setEditing(false)}>
                  Cancel
                </Button>
                <Button variant="primary" onClick={() => save.mutate()}>
                  Save
                </Button>
              </>
            ) : (
              <Button variant="secondary" onClick={() => setEditing(true)}>
                Edit
              </Button>
            )}
            <Button variant="secondary" onClick={() => navigate("/")}>
              Portfolio
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
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
                />
              );
            })}
          </div>
        ) : (
          <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-xs text-ink-subtle">
            No teams in this organization yet — move one here from the portfolio.
          </p>
        )}
      </main>
    </div>
  );
}
