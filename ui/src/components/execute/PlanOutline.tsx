// The living plan, outline projection (amendment D-4): the whole engagement as one nested
// document — states, stage cursors, meters, padlocks, notes — with every line a handle:
// leave a note (D-5) or intervene (X1) inline. Read + act; the view stores nothing.
import { useState } from "react";
import type { PlanNode } from "../../api/work";
import { Button, Markdown } from "../common";
import { DeliverableCard } from "./DeliverableCard";
import { BudgetChip, StageProgress, stateLabel } from "./MissionControl";

interface Props {
  node: PlanNode;
  nodeName: (id: string) => string;
  onNote: (assignmentId: string, stageIdx: number | null, text: string) => void;
  onIntervene: (assignmentId: string, note: string) => void;
  onAccept: (assignmentId: string) => void;
  onReject: (assignmentId: string, note: string) => void;
  onInspect?: (nodeId: string) => void;
  orgId?: string | null; // enables artifact preview on deliverable cards
  depth?: number;
}

const STATE_TONE: Record<string, string> = {
  executing: "text-accent",
  delivering: "text-warn",
  gated: "text-warn",
  closed: "text-ink-muted",
  cancelled: "text-ink-muted line-through",
  proposed: "text-ink-muted italic",
};

export function PlanOutline(props: Props) {
  const { node, nodeName, depth = 0 } = props;
  const [composer, setComposer] = useState<null | { stageIdx: number | null }>(null);
  const [text, setText] = useState("");
  const a = node.assignment;
  const openGates = node.gates.filter((g) => g.state === "open");
  const cursor = node.plan?.stages.find((s) => s.state === "active");

  return (
    <div className={depth > 0 ? "ml-5 border-l border-border pl-4" : ""}>
      <div className="group flex flex-wrap items-center gap-2 py-1">
        {props.onInspect ? (
          <button
            className="text-sm font-medium text-ink hover:text-accent hover:underline"
            title="Inspect this agent"
            onClick={() => props.onInspect!(a.nodeId)}
          >
            {nodeName(a.nodeId)}
          </button>
        ) : (
          <span className="text-sm font-medium text-ink">{nodeName(a.nodeId)}</span>
        )}
        <span className={`text-xs font-semibold ${STATE_TONE[a.state] ?? "text-ink"}`}>
          {stateLabel(a.state)}
        </span>
        {/* F4/F5: gates awaiting the OPERATOR ring in danger; internal wiring stays quiet. */}
        {openGates.map((g) =>
          g.owner === "operator" ? (
            <span key={g.id}
                  className="rounded bg-danger/15 px-1.5 text-[11px] font-medium text-danger"
                  title={`${g.reason} — needs you`}>
              🔒 {g.kind}
            </span>
          ) : (
            <span key={g.id} className="rounded bg-surface-2 px-1.5 text-[11px] text-ink-muted"
                  title={`${g.reason} — internal (${g.owner}), not your action`}>
              🔗 {g.kind}
            </span>
          ),
        )}
        {/* F15: progress = plan stages; budget is its own labeled number. */}
        {node.plan && node.plan.stages.length > 0 && (
          <StageProgress
            progress={{
              done: node.plan.stages.filter((s) => s.state === "done").length,
              total: node.plan.stages.length,
            }}
          />
        )}
        {node.meter && (
          <BudgetChip
            meter={{ spent: node.meter.spent, allowance: node.meter.allowance,
                     warned: node.meter.warned, state: node.meter.state }}
          />
        )}
        {a.briefVersion > 1 && (
          <span className="text-[11px] text-ink-muted">brief v{a.briefVersion}</span>
        )}
        <span className="hidden gap-1 group-hover:inline-flex">
          <button
            className="text-[11px] text-accent hover:underline"
            onClick={() => setComposer(composer ? null : { stageIdx: null })}
          >
            note
          </button>
          {a.state === "delivering" && (
            <>
              <button className="text-[11px] text-accent hover:underline"
                      onClick={() => props.onAccept(a.id)}>
                accept
              </button>
              <button className="text-[11px] text-danger hover:underline"
                      onClick={() => props.onReject(a.id, "rejected from the plan view")}>
                reject
              </button>
            </>
          )}
          {["briefed", "planning", "executing"].includes(a.state) && (
            <button className="text-[11px] text-danger hover:underline"
                    onClick={() => props.onIntervene(a.id, "operator intervention")}>
              intervene
            </button>
          )}
        </span>
      </div>

      {node.brief && depth === 0 && (
        // F6: briefs are authored in markdown — render them that way.
        <Markdown text={node.brief.text} className="mb-1 text-xs text-ink-muted" />
      )}

      {node.plan && (
        <ol className="mb-1 flex flex-col">
          {node.plan.stages.map((s) => (
            <li key={s.idx} className="flex items-center gap-2 text-xs">
              <span className={s.state === "done" ? "text-ink-muted" : s.state === "active" ? "text-accent" : "text-ink-muted/60"}>
                {s.state === "done" ? "✓" : s.state === "active" ? "▶" : "○"}
              </span>
              <span className={s.state === "active" ? "font-medium text-ink" : "text-ink-muted"}>
                {s.title}
              </span>
              {s === cursor && <span className="text-[10px] text-accent">← cursor</span>}
            </li>
          ))}
        </ol>
      )}

      {node.deliverable && (
        <DeliverableCard
          orgId={props.orgId ?? null}
          deliverable={node.deliverable}
          reviewable={a.state === "delivering"}
          onAccept={() => props.onAccept(a.id)}
          onReject={(note) => props.onReject(a.id, note)}
        />
      )}

      {node.notes.map((n) => (
        <div key={n.id} className="mb-1 rounded bg-accent/10 px-2 py-1 text-xs text-ink">
          📝 {n.text}
          <span className="ml-2 text-[10px] text-ink-muted">
            {n.deliveredAt ? "delivered" : "pending injection"}
          </span>
        </div>
      ))}

      {composer && (
        <div className="mb-2 flex gap-2">
          <input
            autoFocus
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Anchored, non-blocking advice — reaches the session next turn…"
            className="flex-1 rounded-md border border-border bg-canvas px-2 py-1 text-xs outline-none focus:border-accent"
          />
          <Button
            onClick={() => {
              props.onNote(a.id, composer.stageIdx, text);
              setText("");
              setComposer(null);
            }}
            disabled={!text}
          >
            Leave note
          </Button>
        </div>
      )}

      {node.children.map((c) => (
        <PlanOutline key={c.assignment.id} {...props} node={c} depth={depth + 1} />
      ))}
    </div>
  );
}
