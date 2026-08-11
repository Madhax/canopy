// The capacity console (design/organizations/06, C3 cut §9): pool cards with window
// gauges, source badges, runway, the attribution stack with the `external` band, and
// the event feed. The honesty rules are structural here: every level wears its source
// tier + age, inferred numbers wear `~` and draw hollow, and a window with no reading
// says so — never 0%, never a guess.
import type {
  BurnBand,
  CapacityAccount,
  CapacityEventRow,
  CapacityWindow,
} from "../../api/capacity";
import { relativeTime } from "../../lib/format";

// ---------------------------------------------------------------- SourceBadge
const TIER_LABELS: Record<string, string> = {
  "provider-read": "provider-reported",
  "provider-event": "event-anchored",
  inferred: "~ inferred",
};

export function SourceBadge({ w }: { w: CapacityWindow }) {
  if (!w.source) return <span className="text-[10px] text-ink-subtle">no reading yet</span>;
  const label = TIER_LABELS[w.source] ?? w.source;
  const age = w.ageS != null ? ` · ${formatAge(w.ageS)}` : "";
  return (
    <span className="text-[10px] text-ink-subtle" title={`source: ${w.source}`}>
      {label}
      {age}
    </span>
  );
}

function formatAge(s: number): string {
  if (s < 90) return `${Math.max(1, Math.round(s / 60))} min ago`;
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  return `${Math.round(s / 3600)} h ago`;
}

// ---------------------------------------------------------------- WindowGauge
export function WindowGauge({ w }: { w: CapacityWindow }) {
  const pct = w.utilizationPct;
  const tone =
    w.state === "exhausted" ? "var(--color-danger, #dc2626)"
    : w.state === "warning" ? "var(--color-warn, #d97706)"
    : "var(--color-ok, #16a34a)";
  const inferred = w.source === "inferred";
  return (
    <div className="flex items-center gap-3">
      <span className="w-24 shrink-0 truncate text-xs text-ink" title={w.key}>
        {w.displayName}
      </span>
      <div className="h-2.5 w-40 shrink-0 overflow-hidden rounded-full border border-border bg-surface-2">
        {pct != null && (
          <div
            className="h-full rounded-full"
            style={{
              width: `${Math.min(100, pct)}%`,
              background: tone,
              // Inferred levels never render in the confident weight (06 §6.2).
              opacity: inferred ? 0.4 : 1,
            }}
          />
        )}
      </div>
      <span className="w-14 shrink-0 text-xs tabular-nums text-ink">
        {pct != null ? `${inferred ? "~" : ""}${Math.round(pct)}%` : "—"}
      </span>
      <span className="shrink-0 text-[11px] text-ink-muted">
        {w.state === "exhausted" && w.resetsAt
          ? `resets ${new Date(w.resetsAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
          : w.resetsAt
            ? `resets ${new Date(w.resetsAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
            : w.state === "exhausted"
              ? "reset unknown · resolves on next successful call"
              : ""}
      </span>
      <SourceBadge w={w} />
    </div>
  );
}

// ----------------------------------------------------------------- RunwayLine
export function RunwayLine({ account }: { account: CapacityAccount }) {
  const r = account.runway;
  if (!r || !r.exhaustsAt) return null;
  const headline = account.windows.find((w) => w.key === r.windowKey);
  const eta = new Date(r.exhaustsAt);
  const resets = headline?.resetsAt ? new Date(headline.resetsAt) : null;
  const bites = resets != null && eta < resets;
  return (
    <div className="mt-1 text-[11px] text-ink-muted">
      runway ▸ exhausts ~{eta.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} at
      current burn{" "}
      {bites && <span className="text-warn">⚠ before reset</span>}
    </div>
  );
}

// ------------------------------------------------------------------ BurnStack
function BurnRow({ band, max }: { band: BurnBand; max: number }) {
  const width = max > 0 ? Math.max(2, (band.ppHr / max) * 100) : 0;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-36 shrink-0 truncate text-ink">{band.teamName}</span>
      <div className="h-2 w-32 shrink-0 overflow-hidden rounded-sm bg-surface-2">
        <div className="h-full rounded-sm bg-accent" style={{ width: `${width}%` }} />
      </div>
      <span className="w-12 shrink-0 tabular-nums text-ink-muted">{band.ppHr}</span>
      {band.orgKey && (
        <span className="rounded-full border border-border px-1.5 text-[10px] text-ink-subtle">
          {band.orgKey}
        </span>
      )}
    </div>
  );
}

export function BurnStack({ account }: { account: CapacityAccount }) {
  const key = account.headlineWindow ?? account.windows[0]?.key;
  const burn = key ? account.burn[key] : undefined;
  if (!burn || (burn.teams.length === 0 && burn.externalPpHr === 0)) return null;
  const max = Math.max(...burn.teams.map((b) => b.ppHr), burn.externalPpHr, 0.001);
  return (
    <div className="mt-3">
      <div className="mb-1 text-[11px] font-medium text-ink-muted">burn, this window (pp/hr)</div>
      <div className="flex flex-col gap-1">
        {burn.teams.map((b) => (
          <BurnRow key={b.teamId} band={b} max={max} />
        ))}
        {burn.externalPpHr > 0 && (
          <div className="flex items-center gap-2 text-xs">
            <span className="w-36 shrink-0 truncate text-ink-muted">external (you)</span>
            <div className="h-2 w-32 shrink-0 overflow-hidden rounded-sm bg-surface-2">
              <div
                className="h-full rounded-sm bg-ink-subtle"
                style={{ width: `${Math.max(2, (burn.externalPpHr / max) * 100)}%` }}
              />
            </div>
            <span className="w-12 shrink-0 tabular-nums text-ink-muted">{burn.externalPpHr}</span>
            <span className="text-[10px] text-ink-subtle">outside Canopy</span>
          </div>
        )}
      </div>
    </div>
  );
}

// --------------------------------------------------------------- CapacityFeed
const EVENT_LABELS: Record<string, string> = {
  "window-exhausted": "window exhausted",
  "window-reading": "reading",
  "rate-limit-pressure": "provider throttling",
};

export function CapacityFeed({ events }: { events: CapacityEventRow[] }) {
  if (events.length === 0) {
    return <p className="text-xs text-ink-subtle">No capacity events yet.</p>;
  }
  return (
    <ul className="flex flex-col gap-1">
      {events.map((ev) => (
        <li key={ev.id} className="flex items-baseline gap-2 text-xs">
          <span className="shrink-0 text-ink-subtle">{relativeTime(ev.createdAt)}</span>
          <span className="text-ink">
            {ev.windowKey ? `${ev.windowKey} · ` : ""}
            {EVENT_LABELS[ev.kind] ?? ev.kind}
            {ev.teamName ? ` · ${ev.teamName}` : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}

// ------------------------------------------------------------------- PoolCard
export function PoolCard({ account }: { account: CapacityAccount }) {
  return (
    <section className="rounded-xl border border-border bg-surface p-4">
      <div className="mb-3 flex items-baseline gap-2">
        <h2 className="text-sm font-semibold text-ink">{account.label}</h2>
        <span className="text-xs text-ink-subtle">{account.authMode}</span>
        {account.provider === "mock" && (
          <span className="rounded-full border border-border px-1.5 text-[10px] text-ink-subtle">
            mock
          </span>
        )}
      </div>
      <div className="flex flex-col gap-1.5">
        {account.windows.map((w) => (
          <WindowGauge key={w.key} w={w} />
        ))}
      </div>
      <RunwayLine account={account} />
      <BurnStack account={account} />
    </section>
  );
}
