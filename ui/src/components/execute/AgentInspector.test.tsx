// The inspector panel renders the aggregate across its eight tabs and gates the
// destructive action (operator-experience.md §3; testing.md §4 E5 row).
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AgentState } from "../../api/inspector";
import { AgentInspector } from "./AgentInspector";

const names: Record<string, string> = { a_lead: "Engineering Lead", a_be: "Backend Engineer" };
const nodeName = (id: string) => names[id] ?? id;

function fixture(): AgentState {
  return {
    nodeId: "a_be",
    charter: {
      displayName: "Backend Engineer", roleKey: "backend-engineer", isManager: false,
      instructions: "You are the backend engineer.", managerNodeId: "a_lead",
      reportNodeIds: [], toolGrants: ["repo.read", "repo.write"], defaultRuntime: "cli-claude",
    },
    binding: { profileId: "pf_1", name: "default", provider: "mock", model: "mock-1" },
    envelope: { toolGrants: ["repo.read", "repo.write"], runtimeKind: "loop" },
    salary: { perAssignmentAllowance: 200000, warnThresholdPct: 80, hardStop: true },
    directory: {
      status: "engaged", lastHeartbeatAt: "2026-07-28T00:00:00Z",
      heartbeatAgeSeconds: 4, endpointUrl: "http://127.0.0.1:9001",
    },
    actuation: { id: "act_1", state: "live" },
    stats: {
      assignmentsTotal: 3, assignmentsDone: 2, accepted: 1, acceptanceRate: 0.5,
      avgCostTokens: 4200, escalations: 1,
    },
    current: {
      assignment: {
        id: "as_cur", intentId: "in_1", nodeId: "a_be", parentId: "as_root",
        issuedBy: "a_lead", state: "executing", briefVersion: 2, contractKind: "artifact",
        contractType: "PullRequest", meterId: "mt_1", priority: 0, sessionRef: "sess-42",
        createdAt: "2026-07-28T00:00:00Z",
      },
      briefs: [
        { version: 1, text: "implement CSV export", createdAt: "t1" },
        { version: 2, text: "implement CSV export with quoting", createdAt: "t2" },
      ],
      plan: {
        stages: [
          { idx: 0, title: "read the code", state: "done", envelopeTokens: null },
          { idx: 1, title: "write the endpoint", state: "active", envelopeTokens: 50000 },
        ],
      },
      steps: [{
        id: "st_1", assignmentId: "as_cur", stageIdx: 1, kind: "production",
        inputTokens: 1200, outputTokens: 300, durationMs: 900, deltaKind: "progress",
        deltaRef: null, createdAt: "2026-07-28T10:00:00Z",
      }],
      meter: { id: "mt_1", allowance: 200000, spent: 150000, reserved: 0, state: "open", warned: false },
      gates: [],
    },
    queue: [{
      id: "as_q1", intentId: "in_2", nodeId: "a_be", parentId: null, issuedBy: "operator",
      state: "briefed", briefVersion: 1, contractKind: "artifact", contractType: "Deliverable",
      meterId: "mt_2", priority: 5, sessionRef: null, createdAt: "2026-07-28T01:00:00Z",
    }],
    history: [{
      id: "as_old", intentId: "in_0", nodeId: "a_be", parentId: null, issuedBy: "operator",
      state: "closed", briefVersion: 1, contractKind: "artifact", contractType: "Deliverable",
      meterId: "mt_0", priority: 0, sessionRef: null, createdAt: "2026-07-27T00:00:00Z",
      spentTokens: 8400,
    }],
    gates: {
      open: [{
        id: "gt_1", assignmentId: "as_cur", kind: "escalation", openedBy: "a_be",
        owner: "operator", reason: "which auth scheme?", payload: {}, state: "open",
        resolution: null, createdAt: "2026-07-28T09:00:00Z",
      }],
      recent: [],
    },
    spend: { nodeTokens: 9900, orgTokens: 33000, sharePct: 30.0 },
    memory: [
      { seq: 1, entry: { outcome: "accepted", summary: "did the thing" }, createdAt: "2026-07-27T00:00:00Z" },
    ],
    session: {
      sessionRef: "sess-42",
      toolEvents: [{
        id: "te_1", tool: "repo_pr", outcome: "denied", detail: "GRANT_DENIED",
        assignment_id: "as_cur", created_at: "2026-07-28T10:05:00Z",
      }],
      logTail: ["booting", "registered"],
    },
    workspace: {
      root: "D:/sb/act_1/a_be/workspace",
      files: [{ path: "out/result.csv", size: 128, modifiedAt: "2026-07-28T10:00:00Z" }],
      truncated: false,
    },
  };
}

function renderPanel(overrides: Partial<Parameters<typeof AgentInspector>[0]> = {}) {
  const props = {
    state: fixture(),
    nodeName,
    onClose: vi.fn(),
    onResetMemory: vi.fn(),
    onIntervene: vi.fn(),
    filePreview: null,
    onPreviewFile: vi.fn(),
    ...overrides,
  };
  render(<AgentInspector {...props} />);
  return props;
}

describe("AgentInspector", () => {
  it("overview: identity, envelope, salary, lifetime stats", () => {
    renderPanel();
    expect(screen.getByText("Backend Engineer")).toBeTruthy();
    expect(screen.getByText(/engaged · heartbeat 4s ago · actuation live/)).toBeTruthy();
    expect(screen.getByText("repo.write")).toBeTruthy();
    expect(screen.getByText(/200,000 tokens\/assignment · warn 80% · hard-stop/)).toBeTruthy();
    expect(screen.getByText("50%")).toBeTruthy(); // acceptance
    expect(screen.getByText("4,200")).toBeTruthy(); // avg cost
  });

  it("assignment tab: brief versions, issued-by chain, intervene", () => {
    const props = renderPanel();
    fireEvent.click(screen.getByText("Assignment"));
    expect(screen.getByText("implement CSV export")).toBeTruthy();
    expect(screen.getByText("implement CSV export with quoting")).toBeTruthy();
    expect(screen.getByText(/Engineering Lead · intent in_1/)).toBeTruthy();
    fireEvent.click(screen.getByText("Intervene"));
    expect(props.onIntervene).toHaveBeenCalledWith("as_cur", expect.any(String));
  });

  it("plan & steps and spend tabs show the drill-down and the money", () => {
    renderPanel();
    fireEvent.click(screen.getByText("Plan & Steps"));
    expect(screen.getByText("write the endpoint")).toBeTruthy();
    expect(screen.getByText("1,200")).toBeTruthy();
    fireEvent.click(screen.getByText("Spend"));
    expect(screen.getByText(/150,000 \/ 200,000 tokens/)).toBeTruthy();
    expect(screen.getByText("30.0%")).toBeTruthy();
    expect(screen.getByText("8,400 tk")).toBeTruthy();
  });

  it("gates & queue: open gates and queued work with priority", () => {
    renderPanel();
    fireEvent.click(screen.getByText("Gates & Queue"));
    expect(screen.getByText("escalation")).toBeTruthy();
    expect(screen.getByText("which auth scheme?")).toBeTruthy();
    expect(screen.getByText("priority 5")).toBeTruthy();
  });

  it("memory reset is confirm-gated", () => {
    const props = renderPanel();
    fireEvent.click(screen.getByText("Memory"));
    fireEvent.click(screen.getByText("Reset memory…"));
    expect(props.onResetMemory).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Yes, reset"));
    expect(props.onResetMemory).toHaveBeenCalledTimes(1);
  });

  it("session and workspace tabs: tool denial visible, file preview requested", () => {
    const props = renderPanel();
    fireEvent.click(screen.getByText("Session"));
    expect(screen.getByText("sess-42")).toBeTruthy();
    expect(screen.getByText("denied")).toBeTruthy();
    fireEvent.click(screen.getByText("Workspace"));
    fireEvent.click(screen.getByText("out/result.csv"));
    expect(props.onPreviewFile).toHaveBeenCalledWith("out/result.csv");
  });
});
