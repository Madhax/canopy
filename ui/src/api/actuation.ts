// Phase-2 control-plane API: profiles, bindings, secrets, actuation (control-plane.md §9).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiSend } from "./client";
import type {
  AgentBinding,
  AgentProfile,
  Provider,
  SecretMeta,
  ValidationResult,
} from "../schema/actuation";

// -- queries ---------------------------------------------------------------- //
export function useProfiles(orgId: string | undefined) {
  return useQuery({
    queryKey: ["profiles", orgId],
    queryFn: () => apiGet<AgentProfile[]>(`/organizations/${orgId}/profiles`),
    enabled: !!orgId,
  });
}

export function useBindings(orgId: string | undefined) {
  return useQuery({
    queryKey: ["bindings", orgId],
    queryFn: () => apiGet<AgentBinding[]>(`/organizations/${orgId}/bindings`),
    enabled: !!orgId,
  });
}

export function useSecrets(orgId: string | undefined) {
  return useQuery({
    queryKey: ["secrets", orgId],
    queryFn: () => apiGet<SecretMeta[]>(`/organizations/${orgId}/secrets`),
    enabled: !!orgId,
  });
}

// -- profile mutations ------------------------------------------------------ //
export interface ProfileInput {
  name: string;
  provider: Provider;
  model: string;
  endpoint?: string | null;
  apiKeySecretId?: string | null;
  systemPreamble?: string;
  params?: { maxOutputTokens?: number; temperature?: number };
}

export function useProfileMutations(orgId: string | undefined) {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["profiles", orgId] });
  return {
    create: useMutation({
      mutationFn: (body: ProfileInput) =>
        apiSend<AgentProfile>("POST", `/organizations/${orgId}/profiles`, body),
      onSuccess: invalidate,
    }),
    update: useMutation({
      mutationFn: ({ id, patch }: { id: string; patch: Partial<ProfileInput> }) =>
        apiSend<AgentProfile>("PUT", `/organizations/${orgId}/profiles/${id}`, patch),
      onSuccess: invalidate,
    }),
    remove: useMutation({
      mutationFn: (id: string) =>
        apiSend<void>("DELETE", `/organizations/${orgId}/profiles/${id}`),
      onSuccess: invalidate,
    }),
  };
}

export function validateProfile(orgId: string, profileId: string) {
  return apiSend<ValidationResult>(
    "POST",
    `/organizations/${orgId}/profiles/${profileId}/validate`,
  );
}

// -- binding mutations ------------------------------------------------------ //
export function useBindingMutations(orgId: string | undefined) {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["bindings", orgId] });
  return {
    set: useMutation({
      mutationFn: (body: { agentNodeId: string; profileId: string; orgPath: string[] }) =>
        apiSend<AgentBinding>("PUT", `/organizations/${orgId}/bindings`, body),
      onSuccess: invalidate,
    }),
    remove: useMutation({
      mutationFn: ({ agentNodeId, orgPath }: { agentNodeId: string; orgPath: string[] }) => {
        const q = orgPath.length ? `?orgPath=${orgPath.join(",")}` : "";
        return apiSend<void>(
          "DELETE",
          `/organizations/${orgId}/bindings/${agentNodeId}${q}`,
        );
      },
      onSuccess: invalidate,
    }),
  };
}

// -- secret mutations ------------------------------------------------------- //
export function useSecretMutations(orgId: string | undefined) {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["secrets", orgId] });
  return {
    create: useMutation({
      mutationFn: (body: { name: string; value: string }) =>
        apiSend<SecretMeta>("POST", `/organizations/${orgId}/secrets`, body),
      onSuccess: invalidate,
    }),
    remove: useMutation({
      mutationFn: (id: string) =>
        apiSend<void>("DELETE", `/organizations/${orgId}/secrets/${id}`),
      onSuccess: invalidate,
    }),
  };
}

// -- actuation -------------------------------------------------------------- //
export interface ActuationNodeView {
  nodeId: string;
  orgPath: string[];
  subState: string;
  status: string | null;
  endpointUrl: string | null;
  error: string | null;
}

export interface ActuationView {
  id: string;
  orgId: string;
  state: string;
  error: string | null;
  createdAt: string;
  updatedAt: string;
  nodes: ActuationNodeView[];
}

export function useActuationCurrent(orgId: string | undefined) {
  return useQuery({
    queryKey: ["actuation", orgId],
    queryFn: () => apiGet<ActuationView | null>(`/organizations/${orgId}/actuations/current`),
    enabled: !!orgId,
    // Poll on a steady cadence so per-node status stays fresh through provisioning → live →
    // teardown. A conditional interval doesn't reliably re-arm across the null→active transition,
    // and one small GET every 2 s on the open editor is negligible. Paused when the tab is hidden.
    refetchInterval: 2000,
    refetchIntervalInBackground: false,
  });
}

export function actuate(orgId: string) {
  return apiSend<{ actuationId: string; state: string }>(
    "POST",
    `/organizations/${orgId}/actuations`,
  );
}

export function deactuate(orgId: string) {
  return apiSend<{ actuationId: string; state: string }>(
    "DELETE",
    `/organizations/${orgId}/actuations/current`,
  );
}
