// The knob panel (design/organizations/06 §3, C4 slice): one row per team, directly
// manipulating team_schedule. Every control shows its predicted effect BEFORE commit —
// the predictions arrive computed from the server's attribution model; the panel holds
// no math of its own.
import { useState } from "react";
import {
  useSchedule,
  useUpdateSchedule,
  type TeamSchedule,
} from "../../api/capacity";
import { ApiError } from "../../api/client";
import { Button, useToast } from "../common";

interface RowProps {
  teamId: string;
  teamName: string;
  orgKey?: string | null;
}

export function KnobRow({ teamId, teamName, orgKey }: RowProps) {
  const { toast } = useToast();
  const q = useSchedule(teamId);
  const update = useUpdateSchedule();
  const [open, setOpen] = useState(false);

  const sched = q.data?.schedule;
  const pred = q.data?.predictions;

  async function commit(patch: Partial<TeamSchedule>) {
    try {
      await update.mutateAsync({ teamId, ...patch });
      toast("Schedule updated.", "success");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Update failed.", "error");
    }
  }

  if (!sched) return null;
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2">
      <div className="flex items-center gap-2">
        <button
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
          onClick={() => setOpen((v) => !v)}
        >
          <span className="truncate text-sm text-ink">{teamName}</span>
          {orgKey && (
            <span className="rounded-full border border-border px-1.5 text-[10px] text-ink-subtle">
              {orgKey}
            </span>
          )}
          <span className="text-[11px] text-ink-subtle">{sched.priority}</span>
        </button>
        {pred && pred.pauseFreesPpHr > 0 && (
          <span
            className="text-[11px] text-ink-muted"
            title={`predicted from ${pred.basis} on ${pred.windowKey ?? "?"}`}
          >
            pause frees −{pred.pauseFreesPpHr} pp/hr
          </span>
        )}
        <Button
          size="sm"
          variant={sched.runState === "paused" ? "primary" : "secondary"}
          onClick={() =>
            commit({ runState: sched.runState === "paused" ? "running" : "paused" })
          }
        >
          {sched.runState === "paused" ? "▶ Resume" : "⏸ Pause"}
        </Button>
      </div>

      {open && (
        <div className="mt-2 flex flex-wrap items-end gap-3 border-t border-border pt-2 text-xs">
          <label className="flex flex-col gap-0.5 text-ink-muted">
            state
            <select
              className="rounded-md border border-border bg-surface px-1.5 py-1 text-ink"
              value={sched.runState}
              onChange={(e) => commit({ runState: e.target.value as TeamSchedule["runState"] })}
            >
              <option value="running">running</option>
              <option value="paused">paused</option>
              <option value="drain">drain</option>
            </select>
          </label>
          <label className="flex flex-col gap-0.5 text-ink-muted">
            sessions{" "}
            {pred?.sessionCapFreesPpHr != null && (
              <span className="text-[10px]">−{pred.sessionCapFreesPpHr} pp/hr</span>
            )}
            <input
              type="number"
              min={-1}
              className="w-16 rounded-md border border-border bg-surface px-1.5 py-1 text-ink"
              defaultValue={sched.maxConcurrentSessions ?? ""}
              placeholder="∞"
              onBlur={(e) =>
                commit({
                  maxConcurrentSessions:
                    e.target.value === "" ? -1 : parseInt(e.target.value, 10),
                })
              }
            />
          </label>
          <label className="flex flex-col gap-0.5 text-ink-muted">
            pace (turns / delay s)
            {pred?.paceFreesPpHr != null && (
              <span className="text-[10px]" title={pred.paceBasis}>
                −{pred.paceFreesPpHr} pp/hr
              </span>
            )}
            <span className="flex gap-1">
              <input
                type="number"
                className="w-14 rounded-md border border-border bg-surface px-1.5 py-1 text-ink"
                defaultValue={sched.paceChunkTurns ?? ""}
                placeholder="off"
                onBlur={(e) =>
                  commit({ paceChunkTurns: parseInt(e.target.value, 10) || 0 })
                }
              />
              <input
                type="number"
                className="w-14 rounded-md border border-border bg-surface px-1.5 py-1 text-ink"
                defaultValue={sched.paceDelayS ?? ""}
                placeholder="0"
                onBlur={(e) => commit({ paceDelayS: parseInt(e.target.value, 10) || 0 })}
              />
            </span>
          </label>
          <label className="flex flex-col gap-0.5 text-ink-muted">
            model cap
            <input
              className="w-20 rounded-md border border-border bg-surface px-1.5 py-1 text-ink"
              defaultValue={sched.modelTierCap ?? ""}
              placeholder="none"
              onBlur={(e) => commit({ modelTierCap: e.target.value })}
            />
          </label>
          <label className="flex flex-col gap-0.5 text-ink-muted">
            priority
            <select
              className="rounded-md border border-border bg-surface px-1.5 py-1 text-ink"
              value={sched.priority}
              onChange={(e) => commit({ priority: e.target.value as TeamSchedule["priority"] })}
            >
              <option value="batch">batch</option>
              <option value="interactive">interactive</option>
            </select>
          </label>
          <span className="text-[10px] text-ink-subtle">
            fallback: {sched.fallbackPolicy.join(" → ")}
          </span>
        </div>
      )}
    </div>
  );
}
