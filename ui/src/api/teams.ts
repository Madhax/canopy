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
