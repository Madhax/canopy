// Connector packs + instances (docs/design/builder-connectors.md §3, §7): the builder's
// palette rows, canvas pills, and instance panel all read/write through here. Instances are
// server truth (react-query), never part of the chart document or its undo history.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiSend } from "./client";

export interface ConnectorSecretDecl {
  credentialKind: string;
  required: boolean;
  scopesHint: string[];
}

export interface ConnectorConfigField {
  type: "string";
  required?: boolean;
  default?: string | null;
  narrowable?: boolean;
}

export interface ConnectorGrant {
  key: string;
  title: string;
  riskClass: "inert" | "read" | "write" | "execute" | "consequential";
  minSandboxTier: number;
  executor: string;
  credentialKind?: string | null;
  governedActions: string[];
  tools: string[];
  provides: string[];
  params: Record<string, unknown>;
}

export interface ConnectorPack {
  key: string;
  version: number;
  title: string;
  kind: "native" | "mcp-server" | "http-api";
  secrets: ConnectorSecretDecl[];
  configSchema: Record<string, ConnectorConfigField>;
  grants: ConnectorGrant[];
}

export interface ConnectorInstance {
  id: string;
  teamId: string;
  packKey: string;
  name: string;
  config: Record<string, string>;
  secretBindings: Record<string, string>; // kind -> secretId (never a value)
  enabledGrants: string[];
  nodeLinks: string[] | null; // null = team-wide; [] = unlinked/inert
  enabled: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface VerifyResult {
  ok: boolean;
  checks: { name: string; ok: boolean; detail: string }[];
}

export function useConnectorPacks(teamId: string | undefined) {
  return useQuery({
    queryKey: ["connector-packs", teamId],
    queryFn: () =>
      apiGet<{ packs: ConnectorPack[] }>(`/teams/${teamId}/connector-packs`),
    enabled: !!teamId,
    staleTime: Infinity, // catalog data — changes only with a server restart
    select: (d) => d.packs,
  });
}

export function useConnectorInstances(teamId: string | undefined) {
  return useQuery({
    queryKey: ["connectors", teamId],
    queryFn: () =>
      apiGet<{ instances: ConnectorInstance[] }>(`/teams/${teamId}/connectors`),
    enabled: !!teamId,
    select: (d) => d.instances,
  });
}

export interface InstanceBody {
  packKey: string;
  name: string;
  config?: Record<string, string>;
  secrets?: Record<string, string>; // plaintext, write-only — stored, returned as ids
  enabledGrants?: string[];
  nodeLinks?: string[] | null;
}

export interface InstancePatch {
  name?: string;
  config?: Record<string, string>;
  secrets?: Record<string, string>;
  enabledGrants?: string[];
  nodeLinks?: string[];
  linkScope?: "team" | "nodes";
  enabled?: boolean;
}

function useInvalidate(teamId: string | undefined) {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: ["connectors", teamId] });
  };
}

export function useCreateInstance(teamId: string | undefined) {
  const invalidate = useInvalidate(teamId);
  return useMutation({
    mutationFn: (body: InstanceBody) =>
      apiSend<ConnectorInstance>("POST", `/teams/${teamId}/connectors`, body),
    onSuccess: invalidate,
  });
}

export function useUpdateInstance(teamId: string | undefined) {
  const invalidate = useInvalidate(teamId);
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: InstancePatch }) =>
      apiSend<ConnectorInstance>("PUT", `/teams/${teamId}/connectors/${id}`, patch),
    onSuccess: invalidate,
  });
}

export function useDeleteInstance(teamId: string | undefined) {
  const invalidate = useInvalidate(teamId);
  return useMutation({
    mutationFn: (id: string) =>
      apiSend<void>("DELETE", `/teams/${teamId}/connectors/${id}`),
    onSuccess: invalidate,
  });
}

export function useVerifyInstance(teamId: string | undefined) {
  return useMutation({
    mutationFn: (id: string) =>
      apiSend<VerifyResult>("POST", `/teams/${teamId}/connectors/${id}/verify`),
  });
}
