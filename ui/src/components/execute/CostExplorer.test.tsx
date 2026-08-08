// The cost explorer renders the spend feed honestly: the SC-1 split, quality context by node,
// and the intent → assignments → steps drill (operator-experience.md §6; testing.md §4 E5 row).
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Assignment, Intent, SpendRow, Step } from "../../api/work";
import { CostExplorer } from "./CostExplorer";

const names: Record<string, string> = { a_lead: "Lead", a_be: "Backend Engineer" };
const nodeName = (id: string) => names[id] ?? id;

const intents: Intent[] = [
  { id: "in_1", text: "Add CSV export; all tests must pass", state: "executing",
    targetNode: "a_lead", createdAt: "", rootAssignmentId: "as_root", cadenceId: null },
];

const byIntent: SpendRow[] = [
  { key: "in_1", input_tokens: 600, output_tokens: 400, est_cost_micros: 12_345, steps: 5,
    coordination_tokens: 250, production_tokens: 750 },
];

const byNode: SpendRow[] = [
  { key: "a_be", input_tokens: 500, output_tokens: 300, est_cost_micros: 9_000, steps: 3,
    coordination_tokens: 0, production_tokens: 800 },
  { key: "a_lead", input_tokens: 100, output_tokens: 100, est_cost_micros: 3_345, steps: 2,
    coordination_tokens: 200, production_tokens: 0 },
];

const byAssignment: SpendRow[] = [
  { key: "as_be", input_tokens: 500, output_tokens: 300, est_cost_micros: 9_000, steps: 3,
    coordination_tokens: 0, production_tokens: 800 },
];

function assignment(over: Partial<Assignment>): Assignment {
  return {
    id: "as_be", intentId: "in_1", nodeId: "a_be", parentId: "as_root", issuedBy: "a_lead",
    state: "closed", briefVersion: 1, contractKind: "artifact", contractType: "PullRequest",
    meterId: "mt_1", priority: 0, sessionRef: null, createdAt: "", ...over,
  };
}

const assignments: Assignment[] = [
  assignment({ id: "as_root", nodeId: "a_lead", parentId: null, contractType: "Deliverable",
               state: "executing" }),
  assignment({ id: "as_be", briefVersion: 2 }), // one rework round, accepted
  assignment({ id: "as_be2", state: "cancelled" }),
];

function renderExplorer(over: Partial<Parameters<typeof CostExplorer>[0]> = {}) {
  return render(
    <CostExplorer
      byIntent={byIntent}
      byNode={byNode}
      byAssignment={byAssignment}
      intents={intents}
      assignments={assignments}
      nodeName={nodeName}
      openAssignmentId={null}
      openAssignmentSteps={null}
      onToggleSteps={() => {}}
      {...over}
    />,
  );
}

describe("CostExplorer", () => {
  it("headline totals: cost, tokens, steps, and the SC-1 overhead share", () => {
    renderExplorer();
    expect(screen.getAllByText("$0.0123").length).toBeGreaterThan(0); // 12_345 micros
    expect(screen.getAllByText("1,000").length).toBeGreaterThan(0);
    // F2: the split bar names its metric — the bare % read as share-of-total spend.
    expect(screen.getAllByText("25% coord").length).toBeGreaterThan(0); // 250 / 1000
    expect(screen.getByText(/Costs are estimates/)).toBeTruthy(); // IM-5, always labeled
  });

  it("F2: an unpriced model shows — with a no-price caption, never $0.0000", () => {
    renderExplorer({
      byIntent: [{ key: "in_1", input_tokens: 600, output_tokens: 400, est_cost_micros: 0,
                   steps: 5, coordination_tokens: 250, production_tokens: 750 }],
      byNode: [{ key: "a_lead", input_tokens: 600, output_tokens: 400, est_cost_micros: 0,
                 steps: 5 }],
      byAssignment: [],
    });
    expect(screen.queryByText("$0.0000")).toBeNull();
    expect(screen.getByText(/no price for this model/)).toBeTruthy();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("F1: cached context totals surface next to the token headline and per step", () => {
    renderExplorer({
      byIntent: [{ key: "in_1", input_tokens: 600, output_tokens: 400, est_cost_micros: 12_345,
                   steps: 5, cache_read_tokens: 1_200, cache_creation_tokens: 300 }],
      openAssignmentId: "as_be",
      openAssignmentSteps: [
        { id: "st_00000001", assignmentId: "as_be", stageIdx: 0, kind: "production",
          inputTokens: 5, outputTokens: 3, cacheReadTokens: 901, cacheCreationTokens: 100,
          durationMs: 10, deltaKind: "artifact", deltaRef: null, createdAt: "" },
      ],
    });
    expect(screen.getByText("+ 1,500 cached context")).toBeTruthy();
    fireEvent.click(screen.getByText(/Add CSV export/));
    expect(screen.getByText("1,001", { selector: "td" })).toBeTruthy(); // 901 + 100 cached
  });

  it("by-intent rows carry the intent text and drill down to assignments with spend + rework", () => {
    renderExplorer();
    const row = screen.getByText(/Add CSV export/);
    fireEvent.click(row);
    // both of the node's assignments appear as drill rows (plus the by-node ranking cell)
    expect(screen.getAllByText("Backend Engineer", { selector: "button" }).length).toBe(2);
    expect(screen.getByText(/rework · brief v2/)).toBeTruthy();
    // the assignment's own spend appears in the drill row (and in the by-node ranking)
    expect(screen.getAllByText("$0.0090").length).toBe(2);
  });

  it("by-node rows show acceptance and rework context alongside cost", () => {
    renderExplorer();
    // a_be: as_be accepted (closed), as_be2 cancelled → 1/2; one rework round
    expect(screen.getByText("1/2")).toBeTruthy();
    const beRow = screen.getByText("Backend Engineer", { selector: "td" }).closest("tr")!;
    expect(beRow.textContent).toContain("$0.0090");
  });

  it("the steps drill toggles per assignment and renders the loaded steps", () => {
    const onToggleSteps = vi.fn();
    const steps: Step[] = [
      { id: "st_00000001", assignmentId: "as_be", stageIdx: 0, kind: "production",
        inputTokens: 500, outputTokens: 300, durationMs: 10, deltaKind: "artifact",
        deltaRef: null, createdAt: "" },
    ];
    renderExplorer({ onToggleSteps, openAssignmentId: "as_be", openAssignmentSteps: steps });
    fireEvent.click(screen.getByText(/Add CSV export/));
    fireEvent.click(screen.getAllByText("Backend Engineer", { selector: "button" })[0]); // as_be
    expect(onToggleSteps).toHaveBeenCalledWith("as_be");
    expect(screen.getByText("artifact")).toBeTruthy();
    expect(screen.getByText("500")).toBeTruthy();
  });
});
