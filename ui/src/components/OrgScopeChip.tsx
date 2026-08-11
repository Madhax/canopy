// The organization scope chip (design/organizations/05 §1, C1 slice): every team-scoped
// surface names the organization it lives under, linking back to that org's page. The
// separation is visible, not just structural.
import { Link } from "react-router-dom";
import { useOrgs } from "../api/orgs";

const ORG_COLORS: Record<string, string> = {
  sage: "#5B7F52",
  indigo: "#4F46E5",
  amber: "#B45309",
  rose: "#BE123C",
  slate: "#475569",
};

export function OrgScopeChip({ teamId }: { teamId: string | undefined }) {
  const orgs = useOrgs();
  if (!teamId || !orgs.data) return null;
  const org = orgs.data.find((o) => o.teamIds.includes(teamId));
  if (!org) return null;
  const color = ORG_COLORS[String(org.theme?.color ?? "")] ?? "#6b7280";
  return (
    <Link
      to={`/orgs/${org.id}`}
      title={`Organization: ${org.name}`}
      className="flex items-center gap-1.5 rounded-full border border-border px-2 py-0.5 text-xs text-ink-muted hover:text-ink"
    >
      <span className="size-2 rounded-full" style={{ background: color }} />
      {org.name}
    </Link>
  );
}
