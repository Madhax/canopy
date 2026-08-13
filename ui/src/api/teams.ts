import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiSend } from "./client";
import type { TeamDoc, OrgSummary, SeedSpec, ValidationIssue } from "./types";

interface SaveResult {
  document: TeamDoc;
  issues: ValidationIssue[];
}

export function useTeams() {
  return useQuery({ queryKey: ["teams"], queryFn: () => apiGet<OrgSummary[]>("/teams") });
}

export function useTeam(id: string | undefined) {
  return useQuery({
    queryKey: ["team", id],
    queryFn: () => apiGet<TeamDoc>(`/teams/${id}`),
    enabled: !!id,
  });
}

export function createTeam(body: {
  name: string;
  organizationType: string;
  seed: SeedSpec;
}) {
  return apiSend<TeamDoc>("POST", "/teams", body);
}

export function saveTeam(doc: TeamDoc) {
  return apiSend<SaveResult>("PUT", `/teams/${doc.id}`, doc);
}

export function deleteTeam(id: string) {
  return apiSend<void>("DELETE", `/teams/${id}`);
}

export function importTeam(doc: unknown) {
  return apiSend<SaveResult>("POST", "/teams/import", doc);
}

export function validateStored(id: string, mode: "draft" | "export") {
  return apiSend<{ issues: ValidationIssue[] }>("POST", `/teams/${id}/validate?mode=${mode}`);
}

export function useDeleteTeam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteTeam,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["teams"] }),
  });
}

export function useImportTeam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: importTeam,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["teams"] }),
  });
}

// --- Revisions: every overwrite is one restore away (server revisions.py) ----
export interface TeamRevision {
  id: string;
  reason: "save" | "overwrite" | "restore" | "delete";
  savedAt: string;
  name: string;
  agentCount: number;
  updatedAt: string | null;
}

export function useRevisions(id: string | undefined, open: boolean) {
  return useQuery({
    queryKey: ["team-revisions", id],
    queryFn: () => apiGet<{ revisions: TeamRevision[] }>(`/teams/${id}/revisions`),
    enabled: !!id && open,
  });
}

export function restoreRevision(teamId: string, revisionId: string) {
  return apiSend<SaveResult>("POST", `/teams/${teamId}/revisions/${revisionId}/restore`);
}
