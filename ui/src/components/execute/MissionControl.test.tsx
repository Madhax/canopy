// Mission control renders the pulse header numbers and the live node tree with the
// operations overlay (operator-experience.md §2); every card is an inspect handle.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Pulse } from "../../api/pulse";
import { MissionControl, OrgPulse } from "./MissionControl";

function pulse(): Pulse {
  return {
    actuation: { id: "act_1", state: "live" },
    intents: { open: 2, total: 5 },
    gates: { open: 3, byKind: { escalation: 1, intervention: 2 }, attention: 2 },
    burn: {
      windowMinutes: 10,
      tokensPerMinute: 1234,
      estCostMicrosPerHour: 42_000_000,
      costsAreEstimates: true,
    },
    nodes: [
      {
        nodeId: "a_lead", name: "Engineering Lead", managerId: null, roleKey: "engineering-lead",
        status: "engaged", runtimeKind: "loop",
        current: { assignmentId: "as_root", state: "executing", briefPreview: "Add CSV export",
                   stageProgress: { done: 1, total: 2 } },
        queueDepth: 0, wip: 1,
        meter: { spent: 150_000, allowance: 200_000, warned: false, state: "open" },
        openGateKinds: [],
      },
      {
        nodeId: "a_be", name: "Backend Engineer", managerId: "a_lead", roleKey: "backend-engineer",
        status: "gated", runtimeKind: "cli-claude",
        current: { assignmentId: "as_be", state: "gated", briefPreview: "implement the endpoint" },
        queueDepth: 2, wip: 3,
        meter: { spent: 190_000, allowance: 200_000, warned: true, state: "open" },
        openGateKinds: ["escalation"],
      },
      {
        nodeId: "a_qa", name: "QA Engineer", managerId: "a_lead", roleKey: "qa-engineer",
        status: "idle", runtimeKind: "loop", current: null,
        queueDepth: 0, wip: 0, meter: null, openGateKinds: [],
      },
    ],
  };
}

describe("OrgPulse", () => {
  it("shows actuation, intents, burn, the narrative, and the attention badge", () => {
    render(<OrgPulse pulse={pulse()} />);
    expect(screen.getByText("live")).toBeTruthy();
    expect(
      screen.getByText((_, el) => el?.textContent === "2 open intents"),
    ).toBeTruthy();
    expect(screen.getByText(/1,234/)).toBeTruthy();
    expect(screen.getByText(/\$42\.00\/hr/)).toBeTruthy();
    // F5: internal wiring is a quiet count; operator work is the loud badge (F4).
    expect(
      screen.getByText((_, el) => el?.textContent === "1 internal gate (wiring)"),
    ).toBeTruthy();
    expect(screen.getByText("2 gates need you")).toBeTruthy();
    expect(screen.getByText(/1 working/)).toBeTruthy(); // the F5 narrative line
  });
});

describe("MissionControl", () => {
  it("renders the tree with statuses, current work, badges, and padlocks", () => {
    render(<MissionControl pulse={pulse()} onInspect={() => {}} />);
    expect(screen.getByText("Engineering Lead")).toBeTruthy();
    expect(screen.getByText("engaged")).toBeTruthy();
    expect(screen.getByText(/Add CSV export/)).toBeTruthy();
    expect(screen.getByText("queue 2")).toBeTruthy();
    expect(screen.getByText("wip 3")).toBeTruthy();
    expect(screen.getByText("🔒 escalation")).toBeTruthy();
    expect(screen.getByText("no active work")).toBeTruthy(); // the idle QA card
    // F15: the budget number is labeled as budget, never a bare "progress" arc.
    expect(screen.getByText(/budget 95%/)).toBeTruthy();
    // F15: stage progress is the headline when a plan exists.
    expect(screen.getByText("1/2 stages")).toBeTruthy();
  });

  it("cards deep-link into the inspector", () => {
    const onInspect = vi.fn();
    render(<MissionControl pulse={pulse()} onInspect={onInspect} />);
    fireEvent.click(screen.getByText("Backend Engineer"));
    expect(onInspect).toHaveBeenCalledWith("a_be");
  });
});
