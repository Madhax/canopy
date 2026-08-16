// The capacity console route (/capacity) — the operations room for the shared pools
// (design/organizations/06 §1). Operator-level and cross-org by necessity: this is the
// one deliberately mixed surface, so every team-tagged element carries its org chip.
// Mounted at /orgs/:id/capacity too (C5): the same console filtered to the org's teams
// with shared pools still visible — filtered, not falsified.
import { Link, useParams } from "react-router-dom";
import { useCapacity, type CapacityOrgRow, type OrgEconomics } from "../api/capacity";
import { usePortfolio } from "../api/orgs";
import { KnobRow } from "../components/capacity/KnobPanel";
import { CapacityFeed, PoolCard } from "../components/capacity/CapacityConsole";
import { WhatIfBar } from "../components/capacity/WhatIfBar";
import { CenteredSpinner } from "../components/common";

// K7/K8 shown read-only here: the operations room displays governance, it doesn't
// rewrite it — edits live on the org page's budget editor (06 §3).
function OrgEconomicsRow({ org }: { org: CapacityOrgRow }) {
  const eco = org.economics as Partial<OrgEconomics>;
  const shares = Object.entries(eco.capacityShares ?? {});
  const reserves = Object.entries(eco.reserveWatermarkPct ?? {});
  const ceiling = eco.weeklyCostCeilingUsd;
  if (ceiling == null && shares.length === 0 && reserves.length === 0) return null;
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2 text-xs">
      <div className="flex items-center gap-2">
        <span className="truncate font-medium text-ink">{org.name}</span>
        <Link className="ml-auto shrink-0 text-[10px] text-ink-subtle underline" to={`/orgs/${org.id}`}>
          edit budget
        </Link>
      </div>
      {ceiling != null && (
        <div className="mt-1 text-ink-muted">
          week est. ${eco.weekSpendUsd?.toFixed(2)} of ${ceiling.toFixed(2)} ceiling
        </div>
      )}
      {shares.length > 0 && (
        <div className="mt-0.5 text-ink-muted">
          shares: {shares.map(([, w]) => `${w}`).join(" / ")}{" "}
          <span className="text-ink-subtle">(bind under contention only)</span>
        </div>
      )}
      {reserves.length > 0 && (
        <div className="mt-0.5 text-ink-muted">
          {reserves.map(([, pct]) => `${pct}% held for interactive`).join(" · ")}
        </div>
      )}
    </div>
  );
}

export function CapacityPage() {
  const { id: orgId } = useParams<{ id: string }>();
  const capacity = useCapacity(orgId);
  const portfolio = usePortfolio();

  const orgName = capacity.data?.organizations.find((o) => o.id === orgId)?.name;
  const knobTeams = (portfolio.data?.organizations ?? [])
    .filter((org) => !orgId || org.id === orgId)
    .flatMap((org) => org.teams.map((t) => ({ team: t, orgKey: org.key })));

  return (
    <div className="min-h-full">
      <header className="border-b border-border bg-surface px-6 py-3">
        <h1 className="text-base font-semibold text-ink">
          Capacity{orgName ? ` · ${orgName}` : ""}
        </h1>
        <p className="text-xs text-ink-muted">
          {orgId
            ? "This organization's burn on the shared pools — pool levels stay pool truth"
            : "Provider windows, per-team burn, and what the system did about it — every number carries its source and age"}
        </p>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        {capacity.isLoading ? (
          <CenteredSpinner label="Reading the pools…" />
        ) : !capacity.data?.enabled ? (
          <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-xs text-ink-subtle">
            Capacity tracking is off — set <code>[capacity] enabled = true</code> in
            canopy.toml to start recording window readings from the sessions Canopy already
            runs.
          </p>
        ) : capacity.data.accounts.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-xs text-ink-subtle">
            No provider accounts yet — they appear when profiles migrate or the first
            session reports a window signal.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_280px]">
            <div className="flex flex-col gap-4">
              <WhatIfBar account={capacity.data.accounts[0]} />
              {capacity.data.accounts.map((acct) => (
                <PoolCard key={acct.id} account={acct} />
              ))}
            </div>
            <aside>
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                Knobs
              </h2>
              <div className="mb-6 flex flex-col gap-2">
                {knobTeams.map(({ team, orgKey }) => (
                  <KnobRow key={team.id} teamId={team.id} teamName={team.name} orgKey={orgKey} />
                ))}
              </div>
              {capacity.data.organizations.some((o) => Object.keys(o.economics).length > 0) && (
                <>
                  <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                    Org budgets
                  </h2>
                  <div className="mb-6 flex flex-col gap-2">
                    {capacity.data.organizations.map((o) => (
                      <OrgEconomicsRow key={o.id} org={o} />
                    ))}
                  </div>
                </>
              )}
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                Event feed
              </h2>
              <CapacityFeed
                events={capacity.data.accounts.flatMap((a) => a.events).sort((x, y) =>
                  y.createdAt.localeCompare(x.createdAt),
                )}
              />
            </aside>
          </div>
        )}
      </main>
    </div>
  );
}
