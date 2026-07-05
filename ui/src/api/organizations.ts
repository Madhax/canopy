import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiSend } from "./client";
import type { OrganizationDoc, OrgSummary, SeedSpec, ValidationIssue } from "./types";

interface SaveResult {
  document: OrganizationDoc;
  issues: ValidationIssue[];
}

export function useOrganizations() {
  return useQuery({ queryKey: ["organizations"], queryFn: () => apiGet<OrgSummary[]>("/organizations") });
}

export function useOrganization(id: string | undefined) {
  return useQuery({
    queryKey: ["organization", id],
    queryFn: () => apiGet<OrganizationDoc>(`/organizations/${id}`),
    enabled: !!id,
  });
}

export function createOrganization(body: {
  name: string;
  organizationType: string;
  seed: SeedSpec;
}) {
  return apiSend<OrganizationDoc>("POST", "/organizations", body);
}

export function saveOrganization(doc: OrganizationDoc) {
  return apiSend<SaveResult>("PUT", `/organizations/${doc.id}`, doc);
}

export function deleteOrganization(id: string) {
  return apiSend<void>("DELETE", `/organizations/${id}`);
}

export function importOrganization(doc: unknown) {
  return apiSend<SaveResult>("POST", "/organizations/import", doc);
}

export function validateStored(id: string, mode: "draft" | "export") {
  return apiSend<{ issues: ValidationIssue[] }>("POST", `/organizations/${id}/validate?mode=${mode}`);
}

export function useDeleteOrganization() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteOrganization,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["organizations"] }),
  });
}

export function useImportOrganization() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: importOrganization,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["organizations"] }),
  });
}
