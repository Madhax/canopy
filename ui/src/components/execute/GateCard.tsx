// One open gate, with its inline resolution actions (engine.md §6 — the single resolution
// endpoint behind every button). The plan-review card shows the REAL batch (amendment D-2).
import { useState } from "react";
import type { Gate, ResolveBody } from "../../api/work";
import { Button } from "../common";

interface Props {
  gate: Gate;
  nodeName: (id: string) => string;
  onResolve: (gateId: string, body: ResolveBody) => void;
  busy?: boolean;
}

interface BatchEntry {
  assignmentId: string;
  nodeId: string;
  brief: string;
  contract: { kind: string; type: string };
  dependsOn: { upstreamId: string; resolveOn: string }[];
  allowance: number;
}

const KIND_LABEL: Record<string, string> = {
  approval: "Approval",
  intervention: "Intervention",
  clarification: "Clarification",
  escalation: "Escalation",
  dependency: "Dependency",
};

export function GateCard({ gate, nodeName, onResolve, busy }: Props) {
  const [note, setNote] = useState("");
  const [amount, setAmount] = useState("");
  const batch = (gate.payload.batch as BatchEntry[] | undefined) ?? null;
  const governed = gate.payload.governedAction as string | undefined;
  const resolve = (body: ResolveBody) => onResolve(gate.id, { ...body, note: note || undefined });

  return (
    <div className="rounded-lg border border-warn/40 bg-surface p-4">
      <div className="mb-2 flex items-center gap-2">
        <span className="rounded-full bg-warn/15 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-warn">
          {KIND_LABEL[gate.kind] ?? gate.kind}
        </span>
        <span className="text-xs text-ink-muted">
          opened by {gate.openedBy} · {new Date(gate.createdAt).toLocaleTimeString()}
        </span>
      </div>

      {batch ? (
        <div className="mb-3">
          <p className="mb-2 text-sm font-medium text-ink">
            Plan review — {batch.length} proposed delegation{batch.length === 1 ? "" : "s"}
          </p>
          <ul className="flex flex-col gap-2">
            {batch.map((b) => (
              <li key={b.assignmentId} className="rounded-md border border-border bg-surface-2 p-2 text-sm">
                <div className="font-medium text-ink">
                  {nodeName(b.nodeId)}
                  <span className="ml-2 text-xs font-normal text-ink-muted">
                    {b.contract.type} · {b.allowance.toLocaleString()} tokens
                  </span>
                </div>
                <div className="text-xs text-ink-muted">{b.brief}</div>
                {b.dependsOn.length > 0 && (
                  <div className="mt-1 text-[11px] text-accent">
                    depends on {b.dependsOn.map((d) => `${d.upstreamId} (${d.resolveOn})`).join(", ")}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : governed ? (
        <p className="mb-3 text-sm text-ink">
          Governed action <span className="font-semibold">{governed}</span>
          {typeof gate.payload.branch === "string" && (
            <span className="text-ink-muted"> — branch {gate.payload.branch}</span>
          )}
        </p>
      ) : (
        <p className="mb-3 text-sm text-ink">
          {(gate.payload.question as string) ?? (gate.payload.note as string) ??
            (gate.payload.detail as string) ?? gate.reason}
        </p>
      )}

      <input
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Note (rides the resolution)…"
        className="mb-2 w-full rounded-md border border-border bg-canvas px-2 py-1 text-sm outline-none focus:border-accent"
      />

      <div className="flex flex-wrap items-center gap-2">
        {(batch || governed) && (
          <>
            <Button onClick={() => resolve({ action: "approve" })} disabled={busy}>
              Approve
            </Button>
            <Button variant="danger" onClick={() => resolve({ action: "deny" })} disabled={busy}>
              Deny
            </Button>
          </>
        )}
        {gate.kind === "intervention" && !governed && (
          <>
            <Button onClick={() => resolve({ action: "resume" })} disabled={busy}>
              Resume
            </Button>
            <input
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="tokens"
              className="w-24 rounded-md border border-border bg-canvas px-2 py-1 text-sm outline-none focus:border-accent"
            />
            <Button
              onClick={() => resolve({ action: "top-up", amount: parseInt(amount, 10) || 0 })}
              disabled={busy || !amount}
            >
              Top up
            </Button>
            <Button variant="danger" onClick={() => resolve({ action: "cancel" })} disabled={busy}>
              Cancel work
            </Button>
          </>
        )}
        {gate.kind === "clarification" && (
          <Button
            onClick={() => resolve({ action: "revise-brief", brief: note })}
            disabled={busy || !note}
          >
            Answer with revised brief
          </Button>
        )}
        {gate.kind === "escalation" && (
          <Button onClick={() => resolve({ action: "answer", answer: note })} disabled={busy || !note}>
            Answer
          </Button>
        )}
      </div>
    </div>
  );
}
