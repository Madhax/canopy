// The plan-review card renders the REAL proposed batch and dispatches resolutions
// (amendment D-2; testing.md §4 E5 row).
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Gate, PlanNode } from "../../api/work";
import { GateCard } from "./GateCard";
import { PlanOutline } from "./PlanOutline";

const names: Record<string, string> = { a_be: "Backend Engineer", a_qa: "QA Engineer" };
const nodeName = (id: string) => names[id] ?? id;

function batchGate(): Gate {
  return {
    id: "gt_1", assignmentId: "as_root", kind: "approval", openedBy: "system",
    owner: "operator", reason: "plan-review", state: "open", resolution: null,
    createdAt: "2026-07-26T00:00:00Z",
    payload: {
      batch: [
        { assignmentId: "as_be", nodeId: "a_be", brief: "implement CSV export",
          contract: { kind: "artifact", type: "PullRequest" }, dependsOn: [],
          allowance: 200000 },
        { assignmentId: "as_qa", nodeId: "a_qa", brief: "verify the export",
          contract: { kind: "artifact", type: "TestReport" },
          dependsOn: [{ upstreamId: "as_be", resolveOn: "delivered" }],
          allowance: 120000 },
      ],
    },
  };
}

describe("GateCard plan review", () => {
  it("shows the real delegations — briefs, contracts, deps with thresholds, allowances", () => {
    render(<GateCard gate={batchGate()} nodeName={nodeName} onResolve={() => {}} />);
    expect(screen.getByText(/2 proposed delegations/)).toBeTruthy();
    expect(screen.getByText("implement CSV export")).toBeTruthy();
    expect(screen.getByText(/PullRequest · 200,000 tokens/)).toBeTruthy();
    expect(screen.getByText(/depends on as_be \(delivered\)/)).toBeTruthy();
  });

  it("approve and deny hit the resolution endpoint", () => {
    const onResolve = vi.fn();
    render(<GateCard gate={batchGate()} nodeName={nodeName} onResolve={onResolve} />);
    fireEvent.click(screen.getByText("Approve"));
    expect(onResolve).toHaveBeenCalledWith("gt_1", expect.objectContaining({ action: "approve" }));
    fireEvent.click(screen.getByText("Deny"));
    expect(onResolve).toHaveBeenCalledWith("gt_1", expect.objectContaining({ action: "deny" }));
  });

  it("intervention gates offer resume and a top-up with an amount", () => {
    const onResolve = vi.fn();
    const gate: Gate = { ...batchGate(), kind: "intervention",
                         payload: { note: "hard stop" } };
    render(<GateCard gate={gate} nodeName={nodeName} onResolve={onResolve} />);
    fireEvent.change(screen.getByPlaceholderText("tokens"), { target: { value: "5000" } });
    fireEvent.click(screen.getByText("Top up"));
    expect(onResolve).toHaveBeenCalledWith(
      "gt_1", expect.objectContaining({ action: "top-up", amount: 5000 }),
    );
  });
});

describe("PlanOutline", () => {
  it("renders the tree with states, padlocks, cursors, and notes", () => {
    const node: PlanNode = {
      assignment: { id: "as_root", intentId: "in_1", nodeId: "a_lead", parentId: null,
                    issuedBy: "operator", state: "gated",
                    briefVersion: 1, contractKind: "artifact", contractType: "Deliverable",
                    meterId: "mt_1", priority: 0, sessionRef: null, createdAt: "" },
      brief: { text: "ship CSV", artifactRefs: [], version: 1 },
      plan: { stages: [{ idx: 0, title: "decompose", state: "done", startedAt: "t",
                         completedAt: "t" },
                       { idx: 1, title: "review", state: "active", startedAt: "t",
                         completedAt: null }] },
      gates: [{ id: "g1", assignmentId: "as_root", kind: "dependency", openedBy: "system",
                owner: "system", reason: "await", payload: { await: true }, state: "open",
                resolution: null, createdAt: "" }],
      meter: { id: "mt_1", allowance: 1000, spent: 850, reserved: 0, state: "open",
               warned: true },
      deliverable: null,
      notes: [{ id: "no_1", assignmentId: "as_root", stageIdx: null, author: "operator",
                text: "prefer the streaming writer", createdAt: "", deliveredAt: "t" }],
      children: [],
    };
    render(<PlanOutline node={node} nodeName={() => "Engineering Lead"} onNote={() => {}}
                        onIntervene={() => {}} onAccept={() => {}} onReject={() => {}} />);
    expect(screen.getByText("Engineering Lead")).toBeTruthy();
    expect(screen.getByText("gated")).toBeTruthy();
    expect(screen.getByText(/🔒 dependency/)).toBeTruthy();
    expect(screen.getByText("85%")).toBeTruthy();
    expect(screen.getByText(/prefer the streaming writer/)).toBeTruthy();
    expect(screen.getByText("← cursor")).toBeTruthy();
  });
});
