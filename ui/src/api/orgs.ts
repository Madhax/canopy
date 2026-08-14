// Organizations — the umbrella above Teams (design/organizations/01; C1) — and the
// portfolio home aggregate. Never actuated, never a chart: identity, theme, budget,
// and the teams grouped behind its isolation wall.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiSend } from "./client";
import type { OrgEconomics } from "./capacity";
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
  /** Scheduler run state (C4): running | paused | drain. */
  runState?: "running" | "paused" | "drain";
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

/** One org with live economics (C5): budget claims + derived week spend. */
export function useOrg(orgId: string | undefined) {
  return useQuery({
    queryKey: ["org", orgId],
    queryFn: () =>
      apiGet<Organization & { teamIds: string[]; economics: OrgEconomics | Record<string, never> }>(
        `/orgs/${orgId}`,
      ),
    enabled: !!orgId,
  });
}

/** The org-level knobs (K7 shares, K8 reserves, weekly ceiling) — audited server-side. */
export function useUpdateOrgBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ orgId, budget }: { orgId: string; budget: Record<string, unknown> }) =>
      apiSend<Organization>("PUT", `/orgs/${orgId}/budget`, budget),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["org", vars.orgId] });
      qc.invalidateQueries({ queryKey: ["orgs"] });
      qc.invalidateQueries({ queryKey: ["portfolio"] });
      qc.invalidateQueries({ queryKey: ["capacity"] });
    },
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
