import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { OrgSummary } from "../../api/types";
import type { Pulse } from "../../api/pulse";
import { OrgPicker } from "./OrgPicker";

const teamsFixture: OrgSummary[] = [
  {
    id: "t_live",
    name: "Live Team",
    organizationType: "product-engineering",
    agentCount: 3,
    childTeamCount: 0,
    updatedAt: "2026-08-01T10:00:00Z",
    valid: true,
  },
  {
    id: "t_degraded",
    name: "Degraded Team",
    organizationType: "product-engineering",
    agentCount: 2,
    childTeamCount: 0,
    updatedAt: "2026-08-01T11:00:00Z",
    valid: true,
  },
  {
    id: "t_idle",
    name: "Idle Unactuated Team",
    organizationType: "product-engineering",
    agentCount: 4,
    childTeamCount: 0,
    updatedAt: "2026-08-01T12:00:00Z",
    valid: true,
  },
];

function makePulse(teamId: string, state: string | null): Pulse {
  return {
    actuation: state ? { id: `act_${teamId}`, state } : null,
    nodes: [],
    intents: { open: 1, total: 1 },
    gates: { open: 0, byKind: {}, attention: 0 },
    burn: {
      windowMinutes: 10,
      tokensPerMinute: 0,
      estCostMicrosPerHour: 0,
      costsAreEstimates: true,
    },
  };
}

function renderPicker(teams: OrgSummary[], states: Record<string, string | null>, onPick = vi.fn()) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const match = url.match(/\/teams\/([^/]+)\/pulse/);
    const id = match?.[1] ?? "";
    return new Response(JSON.stringify(makePulse(id, states[id] ?? null)), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });

  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <OrgPicker teams={teams} onPick={onPick} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { onPick };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("OrgPicker (running-only teams on Execute page)", () => {
  it("only shows teams that are up and running (live or degraded)", async () => {
    const { onPick } = renderPicker(teamsFixture, {
      t_live: "live",
      t_degraded: "degraded",
      t_idle: null,
    });

    await waitFor(() => expect(screen.getByText("Live Team")).toBeTruthy());
    expect(screen.getByText("Degraded Team")).toBeTruthy();
    expect(screen.queryByText("Idle Unactuated Team")).toBeNull();
    expect(screen.getByText(/1 other team isn't running/)).toBeTruthy();

    fireEvent.click(screen.getByText("Live Team"));
    expect(onPick).toHaveBeenCalledWith("t_live");
  });

  it("shows empty state with link to Actuate when no teams are running", async () => {
    renderPicker(teamsFixture, {
      t_live: null,
      t_degraded: "stopped",
      t_idle: null,
    });

    await waitFor(() => expect(screen.getByText("No teams are running")).toBeTruthy());
    expect(screen.getByText("Go to Actuate")).toBeTruthy();
    expect(screen.queryByText("Live Team")).toBeNull();
    expect(screen.queryByText("Degraded Team")).toBeNull();
    expect(screen.queryByText("Idle Unactuated Team")).toBeNull();
  });
});
