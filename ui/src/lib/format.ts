/** Human-friendly formatting helpers. */

export function slugify(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || "organization";
}

/** Compact salary: 150000 -> "150k". */
export function formatMoney(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n % 1_000_000 ? 1 : 0)}m`;
  if (n >= 1000) return `${Math.round(n / 1000)}k`;
  return String(n);
}

/** "150k · 80% · hard-stop" summary of a salary envelope. */
export function formatSalary(s: {
  perAssignmentAllowance: number;
  warnThresholdPct: number;
  hardStop: boolean;
}): string {
  return `${formatMoney(s.perAssignmentAllowance)} · ${Math.round(s.warnThresholdPct)}%${
    s.hardStop ? " · hard-stop" : ""
  }`;
}

const RELATIVE = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

export function relativeTime(iso?: string | null): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const diff = then - Date.now();
  const abs = Math.abs(diff);
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["day", 86_400_000],
    ["hour", 3_600_000],
    ["minute", 60_000],
    ["second", 1000],
  ];
  for (const [unit, ms] of units) {
    if (abs >= ms || unit === "second") {
      return RELATIVE.format(Math.round(diff / ms), unit);
    }
  }
  return "just now";
}
