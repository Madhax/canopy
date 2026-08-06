// The live channel (E5, operator-experience.md §1): one SSE stream per org
// (`GET /organizations/{id}/events`) replaces the 2.5s polling. Events map to targeted
// react-query invalidations; when the stream drops, `useLiveStore.live` flips false and the
// work.ts hooks fall back to their intervals while EventSource reconnects on its own.
import { useEffect } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { create } from "zustand";

// Module-level so work.ts can subscribe (`usePollInterval`) without prop-drilling.
export const useLiveStore = create<{ live: boolean }>(() => ({ live: false }));

const ALL_WORK_KEYS = [
  "intents", "intent-plan", "assignments", "assignment-detail", "gates",
  "notifications", "spend", "agent-state", "pulse", "cadences",
];

// Activity events carry engine transitions by kind (`intent.submitted`, `gate.opened`,
// `meter.topped-up`, …); first matching row wins.
const ACTIVITY_KEYS: [RegExp, string[]][] = [
  [/^gate\./, ["gates", "intent-plan", "intents", "notifications", "agent-state", "pulse"]],
  [/^meter\./, ["intent-plan", "spend", "assignment-detail", "agent-state", "pulse"]],
  [/^(intent|assignment)\./, ["intents", "intent-plan", "assignments", "assignment-detail", "gates", "agent-state", "pulse"]],
  [/^memory\./, ["agent-state"]],
  [/^actuation\./, ["pulse"]],
  [/^cadence\./, ["cadences", "intents", "notifications"]],
];

// Coalesced per-family events (the server emits at most one per tick).
const FAMILY_KEYS: Record<string, string[]> = {
  steps: ["assignment-detail", "spend", "intent-plan", "agent-state", "pulse"],
  plan: ["intent-plan", "agent-state", "pulse"],
  notes: ["intent-plan"],
  notifications: ["notifications"],
};

// Steps are already coalesced server-side per ~1s tick; throttle further client-side
// (operator-experience.md §7's live-update discipline).
const STEP_THROTTLE_MS = 2000;

function invalidate(qc: QueryClient, keys: string[]) {
  for (const key of keys) qc.invalidateQueries({ queryKey: [key] });
}

/** Subscribe the org's SSE stream to the query cache. Returns whether the channel is live. */
export function useOrgEvents(orgId: string | null): boolean {
  const qc = useQueryClient();

  useEffect(() => {
    if (!orgId) return;
    const es = new EventSource(`/api/organizations/${orgId}/events`);
    let lastStepAt = 0;
    let stepTimer: ReturnType<typeof setTimeout> | null = null;

    es.addEventListener("hello", () => {
      useLiveStore.setState({ live: true });
      // Catch anything that happened while we weren't listening (first connect or reconnect).
      invalidate(qc, ALL_WORK_KEYS);
    });
    es.addEventListener("activity", (e) => {
      const { kind } = JSON.parse((e as MessageEvent).data) as { kind: string };
      for (const [pattern, keys] of ACTIVITY_KEYS) {
        if (pattern.test(kind)) {
          invalidate(qc, keys);
          break;
        }
      }
    });
    for (const [family, keys] of Object.entries(FAMILY_KEYS)) {
      es.addEventListener(family, () => {
        if (family !== "steps") {
          invalidate(qc, keys);
          return;
        }
        const wait = lastStepAt + STEP_THROTTLE_MS - Date.now();
        if (wait <= 0) {
          lastStepAt = Date.now();
          invalidate(qc, keys);
        } else if (stepTimer === null) {
          stepTimer = setTimeout(() => {
            stepTimer = null;
            lastStepAt = Date.now();
            invalidate(qc, keys);
          }, wait);
        }
      });
    }
    // EventSource retries on its own; we just flip the polling fallback on meanwhile.
    es.onerror = () => useLiveStore.setState({ live: false });

    return () => {
      es.close();
      if (stepTimer !== null) clearTimeout(stepTimer);
      useLiveStore.setState({ live: false });
    };
  }, [orgId, qc]);

  return useLiveStore((s) => s.live);
}
