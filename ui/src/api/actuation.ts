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
export function useProfiles(teamId: string | undefined) {
  return useQuery({
    queryKey: ["profiles", teamId],
    queryFn: () => apiGet<AgentProfile[]>(`/teams/${teamId}/profiles`),
    enabled: !!teamId,
  });
}

export function useBindings(teamId: string | undefined) {
  return useQuery({
    queryKey: ["bindings", teamId],
    queryFn: () => apiGet<AgentBinding[]>(`/teams/${teamId}/bindings`),
    enabled: !!teamId,
  });
}

export function useSecrets(teamId: string | undefined) {
  return useQuery({
    queryKey: ["secrets", teamId],
    queryFn: () => apiGet<SecretMeta[]>(`/teams/${teamId}/secrets`),
    enabled: !!teamId,
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

export function useProfileMutations(teamId: string | undefined) {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["profiles", teamId] });
  return {
    create: useMutation({
      mutationFn: (body: ProfileInput) =>
        apiSend<AgentProfile>("POST", `/teams/${teamId}/profiles`, body),
      onSuccess: invalidate,
    }),
    update: useMutation({
      mutationFn: ({ id, patch }: { id: string; patch: Partial<ProfileInput> }) =>
        apiSend<AgentProfile>("PUT", `/teams/${teamId}/profiles/${id}`, patch),
      onSuccess: invalidate,
    }),
    remove: useMutation({
      mutationFn: (id: string) =>
        apiSend<void>("DELETE", `/teams/${teamId}/profiles/${id}`),
      onSuccess: invalidate,
    }),
  };
}

export function validateProfile(teamId: string, profileId: string) {
  return apiSend<ValidationResult>(
    "POST",
    `/teams/${teamId}/profiles/${profileId}/validate`,
  );
}

// -- binding mutations ------------------------------------------------------ //
export function useBindingMutations(teamId: string | undefined) {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["bindings", teamId] });
  return {
    set: useMutation({
      mutationFn: (body: { agentNodeId: string; profileId: string; teamPath: string[] }) =>
        apiSend<AgentBinding>("PUT", `/teams/${teamId}/bindings`, body),
      onSuccess: invalidate,
    }),
    remove: useMutation({
      mutationFn: ({ agentNodeId, teamPath }: { agentNodeId: string; teamPath: string[] }) => {
        const q = teamPath.length ? `?teamPath=${teamPath.join(",")}` : "";
        return apiSend<void>(
          "DELETE",
          `/teams/${teamId}/bindings/${agentNodeId}${q}`,
        );
      },
      onSuccess: invalidate,
    }),
  };
}

// -- secret mutations ------------------------------------------------------- //
export function useSecretMutations(teamId: string | undefined) {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["secrets", teamId] });
  return {
    create: useMutation({
      mutationFn: (body: { name: string; value: string }) =>
        apiSend<SecretMeta>("POST", `/teams/${teamId}/secrets`, body),
      onSuccess: invalidate,
    }),
    remove: useMutation({
      mutationFn: (id: string) =>
        apiSend<void>("DELETE", `/teams/${teamId}/secrets/${id}`),
      onSuccess: invalidate,
    }),
  };
}

// -- actuation -------------------------------------------------------------- //
export interface ActuationNodeView {
  nodeId: string;
  teamPath: string[];
  subState: string;
  status: string | null;
  endpointUrl: string | null;
  error: string | null;
}

export interface ActuationView {
  id: string;
  teamId: string;
  state: string;
  error: string | null;
  createdAt: string;
  updatedAt: string;
  nodes: ActuationNodeView[];
}

export function useActuationCurrent(teamId: string | undefined) {
  return useQuery({
    queryKey: ["actuation", teamId],
    queryFn: () => apiGet<ActuationView | null>(`/teams/${teamId}/actuations/current`),
    enabled: !!teamId,
    // Poll on a steady cadence so per-node status stays fresh through provisioning → live →
    // teardown. A conditional interval doesn't reliably re-arm across the null→active transition,
    // and one small GET every 2 s on the open editor is negligible. Paused when the tab is hidden.
    refetchInterval: 2000,
    refetchIntervalInBackground: false,
  });
}

export function actuate(teamId: string) {
  return apiSend<{ actuationId: string; state: string }>(
    "POST",
    `/teams/${teamId}/actuations`,
  );
}

export function deactuate(teamId: string) {
  return apiSend<{ actuationId: string; state: string }>(
    "DELETE",
    `/teams/${teamId}/actuations/current`,
  );
}
