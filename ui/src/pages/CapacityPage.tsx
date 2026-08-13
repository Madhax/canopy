// The capacity console route (/capacity) — the operations room for the shared pools
// (design/organizations/06 §1). Operator-level and cross-org by necessity: this is the
// one deliberately mixed surface, so every team-tagged element carries its org chip.
import { useCapacity } from "../api/capacity";
import { CapacityFeed, PoolCard } from "../components/capacity/CapacityConsole";
import { CenteredSpinner } from "../components/common";

export function CapacityPage() {
  const capacity = useCapacity();

  return (
    <div className="min-h-full">
      <header className="border-b border-border bg-surface px-6 py-3">
        <h1 className="text-base font-semibold text-ink">Capacity</h1>
        <p className="text-xs text-ink-muted">
          Provider windows, per-team burn, and what the system did about it — every number
          carries its source and age
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
              {capacity.data.accounts.map((acct) => (
                <PoolCard key={acct.id} account={acct} />
              ))}
            </div>
            <aside>
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
