// Organizations — the umbrella above Teams (design/organizations/01; C1) — and the
// portfolio home aggregate. Never actuated, never a chart: identity, theme, budget,
// and the teams grouped behind its isolation wall.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiSend } from "./client";
import type { OrgSummary } from "./types";

export interface Organization {
  id: string;
  key: string;
  name: string;
  purpose: string;
  theme: { color?: string; icon?: string } & Record<string, unknown>;
  priorityClass: string;
  budget: Record<string, unknown>;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface PortfolioTeam extends OrgSummary {
  /** Actuation state for the read-only card (null = not actuated). */
  actuation: string | null;
}

export interface PortfolioOrg extends Organization {
  teams: PortfolioTeam[];
}

export function useOrgs() {
  return useQuery({
    queryKey: ["orgs"],
    queryFn: () => apiGet<(Organization & { teamIds: string[] })[]>("/orgs"),
  });
}

export function usePortfolio() {
  return useQuery({
    queryKey: ["portfolio"],
    queryFn: () => apiGet<{ organizations: PortfolioOrg[] }>("/portfolio"),
  });
}

export function useCreateOrg() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { key: string; name: string; purpose?: string; theme?: object }) =>
      apiSend<Organization>("POST", "/orgs", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orgs"] });
      qc.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });
}

export function useMoveTeam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ teamId, organizationId }: { teamId: string; organizationId: string }) =>
      apiSend<{ teamId: string; organizationId: string }>("POST", `/teams/${teamId}/move`, {
        organizationId,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orgs"] });
      qc.invalidateQueries({ queryKey: ["portfolio"] });
      qc.invalidateQueries({ queryKey: ["teams"] });
    },
  });
}
