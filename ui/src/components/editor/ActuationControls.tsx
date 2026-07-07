// Actuate / Deactuate control + readiness dialog (phases.md Phase 2, control-plane.md §10).
// Self-contained: it polls the current actuation (shared query cache with EditorPage's node pills).
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { actuate, deactuate, useActuationCurrent } from "../../api/actuation";
import { ApiError } from "../../api/client";
import type { ValidationIssue } from "../../validation/codes";
import { Button, Dialog, useToast } from "../common";

const STATE_TONE: Record<string, string> = {
  provisioning: "bg-warn/15 text-warn",
  live: "bg-ok/15 text-ok",
  degraded: "bg-warn/15 text-warn",
  draining: "bg-warn/15 text-warn",
};

export function ActuationControls({ orgId }: { orgId: string }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const { data: actuation } = useActuationCurrent(orgId);
  const [busy, setBusy] = useState(false);
  const [issues, setIssues] = useState<ValidationIssue[] | null>(null);

  const refresh = () => qc.invalidateQueries({ queryKey: ["actuation", orgId] });
  const active = !!actuation && actuation.state !== "stopped" && actuation.state !== "failed";

  const onActuate = async () => {
    setBusy(true);
    try {
      await actuate(orgId);
      refresh();
    } catch (e) {
      if (e instanceof ApiError && e.code === "ACTUATION_BLOCKED") setIssues(e.issues ?? []);
      else toast(e instanceof Error ? e.message : "Actuate failed.", "error");
    } finally {
      setBusy(false);
    }
  };

  const onDeactuate = async () => {
    setBusy(true);
    try {
      await deactuate(orgId);
      refresh();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Deactuate failed.", "error");
    } finally {
      setBusy(false);
    }
  };

  const ready = actuation?.nodes.filter((n) => n.subState === "ready").length ?? 0;
  const total = actuation?.nodes.length ?? 0;

  return (
    <div className="flex items-center gap-2">
      {active ? (
        <>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${
              STATE_TONE[actuation!.state] ?? "bg-surface-2 text-ink-muted"
            }`}
            title="Actuation status"
          >
            <span className="size-1.5 rounded-full bg-current" />
            {actuation!.state} · {ready}/{total} ready
          </span>
          <Button size="sm" variant="danger" onClick={onDeactuate} disabled={busy}>
            {busy ? "Stopping…" : "Deactuate"}
          </Button>
        </>
      ) : (
        <Button size="sm" variant="primary" onClick={onActuate} disabled={busy}>
          {busy ? "Actuating…" : "▶ Actuate"}
        </Button>
      )}

      <Dialog
        open={issues !== null}
        onClose={() => setIssues(null)}
        title="Cannot actuate yet"
        footer={
          <Button variant="secondary" onClick={() => setIssues(null)}>
            Close
          </Button>
        }
      >
        <p className="mb-3 text-ink-muted">
          Every node needs a valid Agent Profile binding before the org can be actuated. Fix these,
          then try again:
        </p>
        <ul className="flex flex-col gap-2">
          {(issues ?? []).map((i, idx) => (
            <li key={idx} className="rounded-md border border-border bg-canvas px-2 py-1.5">
              <div className="font-mono text-xs text-danger">{i.code}</div>
              <div className="text-sm">{i.message}</div>
              {i.agentIds && i.agentIds.length > 0 && (
                <div className="mt-0.5 text-xs text-ink-muted">node: {i.agentIds.join(", ")}</div>
              )}
            </li>
          ))}
        </ul>
      </Dialog>
    </div>
  );
}
