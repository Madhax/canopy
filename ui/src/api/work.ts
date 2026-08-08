// The operator work surface (E5) over the E2 engine APIs. Live data rides the SSE channel
// (events.ts) — while it is connected the intervals below switch off and the stream
// invalidates these query keys instead; polling is the fallback when the stream drops.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiSend } from "./client";
import { useLiveStore } from "./events";

export interface Assignment {
  id: string;
  intentId: string;
  nodeId: string;
  parentId: string | null;
  issuedBy: string;
  state: string;
  briefVersion: number;
  contractKind: string;
  contractType: string;
  meterId: string | null;
  priority: number;
  sessionRef: string | null;
  createdAt: string;
}

export interface Meter {
  id: string;
  allowance: number;
  spent: number;
  reserved: number;
  state: string;
  warned: boolean;
}

export interface Gate {
  id: string;
  assignmentId: string;
  kind: string;
  openedBy: string;
  owner: string;
  reason: string;
  payload: Record<string, unknown>;
  state: string;
  resolution: Record<string, unknown> | null;
  createdAt: string;
}

export interface WorkNote {
  id: string;
  assignmentId: string | null;
  stageIdx: number | null;
  author: string;
  text: string;
  createdAt: string;
  deliveredAt: string | null;
}

export interface Deliverable {
  id: string;
  kind: string;
  artifactRefs: string[];
  summary: string;
  accepted: boolean | null; // null = awaiting the verdict
  reviewNote: string | null;
  createdAt: string;
}

export interface PlanNode {
  assignment: Assignment;
  brief: { text: string; artifactRefs: string[]; version: number } | null;
  plan: {
    stages: {
      idx: number;
      title: string;
      state: string;
      startedAt: string | null;
      completedAt: string | null;
    }[];
  } | null;
  gates: Gate[];
  meter: Meter | null;
  deliverable: Deliverable | null;
  notes: WorkNote[];
  children: PlanNode[];
}

export interface Intent {
  id: string;
  text: string;
  state: string;
  targetNode: string;
  createdAt: string;
  rootAssignmentId: string | null;
  cadenceId: string | null;
  // Trigger provenance (standing-orgs.md §3): the ⚡ chip and its external key.
  triggerId?: string | null;
  externalKey?: string | null;
}

// A standing schedule (E7, engine.md §4): each due occurrence fires an ordinary intent.
export interface Cadence {
  id: string;
  nodeId: string | null; // null ⇒ the org root at fire time
  name: string;
  cron: string; // five UTC fields: minute hour day-of-month month day-of-week
  intentText: string;
  enabled: boolean;
  lastFiredAt: string | null;
  nextFireAt: string | null; // server-computed; null when disabled
  createdAt: string;
}

// An event-driven work source (standing-orgs.md §2): polls a connector instance, opens one
// episodic intent per new external event, deduped by the server's fire ledger.
export interface Trigger {
  id: string;
  orgId: string;
  name: string;
  kind: string; // 'github-issues' (v1)
  nodeId: string | null;
  instanceId: string;
  config: { labels?: string[]; state?: string; createdAfter?: string };
  intentTemplate: string;
  enabled: boolean;
  cursor: { since?: string } | null;
  lastCheckedAt: string | null;
  lastFiredAt: string | null;
  lastError: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface TriggerDryRun {
  candidates: { key: string; title: string; url: string }[];
  renderedFirst: string | null;
}

export interface Step {
  id: string;
  assignmentId: string;
  stageIdx: number | null;
  kind: "coordination" | "production";
  inputTokens: number;
  outputTokens: number;
  /** F1: cached context settled per step (older rows omit them). */
  cacheReadTokens?: number;
  cacheCreationTokens?: number;
  durationMs: number;
  deltaKind: string;
  deltaRef: string | null;
  createdAt: string;
}

// One row of the spend rollup (operations.py); split columns present when split=true.
export interface SpendRow {
  key: string;
  input_tokens: number;
  output_tokens: number;
  /** F1: the cached context window, settled separately and priced cache-aware. */
  cache_read_tokens?: number;
  cache_creation_tokens?: number;
  est_cost_micros: number;
  steps: number;
  coordination_tokens?: number;
  production_tokens?: number;
}

export interface Notification {
  id: string;
  severity: "attention" | "warning" | "info";
  kind: string;
  subjectIds: string[];
  text: string;
  createdAt: string;
  readAt: string | null;
}

const POLL = 2500;

// SSE connected ⇒ no interval (the stream invalidates); dropped ⇒ poll.
export function usePollInterval(): number | false {
  return useLiveStore((s) => s.live) ? false : POLL;
}

export function useIntents(orgId: string | null) {
  return useQuery({
    queryKey: ["intents", orgId],
    queryFn: () => apiGet<{ intents: Intent[] }>(`/organizations/${orgId}/intents`),
    enabled: !!orgId,
    refetchInterval: usePollInterval(),
    select: (d) => d.intents,
  });
}

export function useIntentPlan(intentId: string | null) {
  return useQuery({
    queryKey: ["intent-plan", intentId],
    queryFn: () =>
      apiGet<{ intent: Intent; tree: PlanNode[]; intentNotes: WorkNote[] }>(
        `/intents/${intentId}/plan`,
      ),
    enabled: !!intentId,
    refetchInterval: usePollInterval(),
  });
}

export function useSpend(
  orgId: string | null,
  groupBy: "node" | "intent" | "assignment",
  split = true,
) {
  return useQuery({
    queryKey: ["spend", orgId, groupBy, split],
    queryFn: () =>
      apiGet<{ rows: SpendRow[]; costsAreEstimates: boolean }>(
        `/organizations/${orgId}/spend?groupBy=${groupBy}&split=${split}`,
      ),
    enabled: !!orgId,
    refetchInterval: usePollInterval(),
    select: (d) => d.rows,
  });
}

export function useAssignments(orgId: string | null) {
  return useQuery({
    queryKey: ["assignments", orgId],
    queryFn: () =>
      apiGet<{ assignments: Assignment[] }>(`/organizations/${orgId}/assignments`),
    enabled: !!orgId,
    refetchInterval: usePollInterval(),
    select: (d) => d.assignments,
  });
}

// The money-end drill-down (operator-experience.md §6): one assignment's steps + meter.
export function useAssignmentDetail(assignmentId: string | null) {
  return useQuery({
    queryKey: ["assignment-detail", assignmentId],
    queryFn: () =>
      apiGet<{ assignment: Assignment; steps: Step[]; meter: Meter | null }>(
        `/assignments/${assignmentId}`,
      ),
    enabled: !!assignmentId,
    refetchInterval: usePollInterval(),
  });
}

export function useOperatorGates(orgId: string | null) {
  return useQuery({
    queryKey: ["gates", orgId],
    queryFn: () =>
      apiGet<{ gates: Gate[] }>(`/organizations/${orgId}/gates?state=open&owner=operator`),
    enabled: !!orgId,
    refetchInterval: usePollInterval(),
    select: (d) => d.gates,
  });
}

export function useNotifications(orgId: string | null) {
  return useQuery({
    queryKey: ["notifications", orgId],
    queryFn: () =>
      apiGet<{ notifications: Notification[] }>(
        `/organizations/${orgId}/notifications?unread=true`,
      ),
    enabled: !!orgId,
    refetchInterval: usePollInterval(),
    select: (d) => d.notifications,
  });
}

function useInvalidateWork(orgId: string | null) {
  const qc = useQueryClient();
  return () => {
    for (const key of ["intents", "intent-plan", "gates", "notifications", "assignments",
                       "spend", "assignment-detail", "cadences", "triggers"]) {
      qc.invalidateQueries({ queryKey: [key] });
    }
    void orgId;
  };
}

// Operator artifact preview (the deliverable viewer). Refs are immutable versions, so the
// result never goes stale.
export interface ArtifactPreview {
  meta: {
    ref: string;
    name: string;
    type: string;
    size: number;
    version: number;
    nodeId: string;
    createdAt: string;
  };
  content: string | null;
  reason: "too-large" | "binary" | "missing-blob" | null;
}

export function useArtifact(orgId: string | null, ref: string | null) {
  return useQuery({
    queryKey: ["artifact", orgId, ref],
    queryFn: () =>
      apiGet<ArtifactPreview>(
        `/organizations/${orgId}/artifacts?ref=${encodeURIComponent(ref!)}`,
      ),
    enabled: !!orgId && !!ref,
    staleTime: Infinity,
  });
}

export function useCadences(orgId: string | null) {
  return useQuery({
    queryKey: ["cadences", orgId],
    queryFn: () => apiGet<{ cadences: Cadence[] }>(`/organizations/${orgId}/cadences`),
    enabled: !!orgId,
    refetchInterval: usePollInterval(),
    select: (d) => d.cadences,
  });
}

export function useCreateCadence(orgId: string | null) {
  const invalidate = useInvalidateWork(orgId);
  return useMutation({
    mutationFn: (body: {
      name: string;
      cron: string;
      intentText: string;
      nodeId?: string | null;
    }) => apiSend("POST", `/organizations/${orgId}/cadences`, body),
    onSuccess: invalidate,
  });
}

export function useUpdateCadence(orgId: string | null) {
  const invalidate = useInvalidateWork(orgId);
  return useMutation({
    mutationFn: ({ cadenceId, body }: { cadenceId: string; body: { enabled?: boolean } }) =>
      apiSend("PUT", `/organizations/${orgId}/cadences/${cadenceId}`, body),
    onSuccess: invalidate,
  });
}

export function useDeleteCadence(orgId: string | null) {
  const invalidate = useInvalidateWork(orgId);
  return useMutation({
    mutationFn: (cadenceId: string) =>
      apiSend("DELETE", `/organizations/${orgId}/cadences/${cadenceId}`),
    onSuccess: invalidate,
  });
}

// ---- triggers (standing-orgs.md §4) ----
export function useTriggers(orgId: string | null) {
  return useQuery({
    queryKey: ["triggers", orgId],
    queryFn: () => apiGet<{ triggers: Trigger[] }>(`/organizations/${orgId}/triggers`),
    enabled: !!orgId,
    refetchInterval: usePollInterval(),
    select: (d) => d.triggers,
  });
}

export interface TriggerBody {
  name: string;
  instanceId: string;
  intentTemplate: string;
  nodeId?: string | null;
  config?: Trigger["config"];
}

export function useCreateTrigger(orgId: string | null) {
  const invalidate = useInvalidateWork(orgId);
  return useMutation({
    mutationFn: (body: TriggerBody) =>
      apiSend<Trigger>("POST", `/organizations/${orgId}/triggers`, body),
    onSuccess: invalidate,
  });
}

export function useUpdateTrigger(orgId: string | null) {
  const invalidate = useInvalidateWork(orgId);
  return useMutation({
    mutationFn: ({ triggerId, body }: { triggerId: string; body: Partial<TriggerBody> & { enabled?: boolean } }) =>
      apiSend<Trigger>("PUT", `/organizations/${orgId}/triggers/${triggerId}`, body),
    onSuccess: invalidate,
  });
}

export function useDeleteTrigger(orgId: string | null) {
  const invalidate = useInvalidateWork(orgId);
  return useMutation({
    mutationFn: (triggerId: string) =>
      apiSend("DELETE", `/organizations/${orgId}/triggers/${triggerId}`),
    onSuccess: invalidate,
  });
}

export function useCheckTrigger(orgId: string | null) {
  const invalidate = useInvalidateWork(orgId);
  return useMutation({
    mutationFn: (triggerId: string) =>
      apiSend<{ fired: string[]; candidates: number }>(
        "POST", `/organizations/${orgId}/triggers/${triggerId}/check`,
      ),
    onSuccess: invalidate,
  });
}

export function useDryRunTrigger(orgId: string | null) {
  return useMutation({
    mutationFn: (triggerId: string) =>
      apiSend<TriggerDryRun>("POST", `/organizations/${orgId}/triggers/${triggerId}/dry-run`),
  });
}

export function useSubmitIntent(orgId: string | null) {
  const invalidate = useInvalidateWork(orgId);
  return useMutation({
    mutationFn: (body: { text: string; targetNodeId?: string }) =>
      apiSend("POST", `/organizations/${orgId}/intents`, body),
    onSuccess: invalidate,
  });
}

export interface ResolveBody {
  action: string;
  note?: string;
  amount?: number;
  toNodeId?: string;
  answer?: string;
  brief?: string;
  assignmentId?: string;
}

export function useResolveGate(orgId: string | null) {
  const invalidate = useInvalidateWork(orgId);
  return useMutation({
    mutationFn: ({ gateId, body }: { gateId: string; body: ResolveBody }) =>
      apiSend("POST", `/gates/${gateId}/resolve`, body),
    onSuccess: invalidate,
  });
}

export function useAssignmentAction(orgId: string | null) {
  const invalidate = useInvalidateWork(orgId);
  return useMutation({
    mutationFn: ({
      assignmentId,
      action,
      body,
    }: {
      assignmentId: string;
      action: "accept" | "reject" | "intervene";
      body: { note: string; revisedBrief?: string };
    }) => apiSend("POST", `/assignments/${assignmentId}/${action}`, body),
    onSuccess: invalidate,
  });
}

export function useLeaveNote(orgId: string | null) {
  const invalidate = useInvalidateWork(orgId);
  return useMutation({
    mutationFn: ({
      intentId,
      body,
    }: {
      intentId: string;
      body: { text: string; assignmentId?: string; stageIdx?: number };
    }) => apiSend("POST", `/intents/${intentId}/notes`, body),
    onSuccess: invalidate,
  });
}

export function useMarkNotificationsRead(orgId: string | null) {
  const invalidate = useInvalidateWork(orgId);
  return useMutation({
    mutationFn: (ids?: string[]) =>
      apiSend("POST", `/organizations/${orgId}/notifications/read`, { ids: ids ?? null }),
    onSuccess: invalidate,
  });
}
