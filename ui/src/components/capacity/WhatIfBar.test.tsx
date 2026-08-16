// The what-if strip (06 §3, C5): the goal goes in, suggestions come back computed —
// the strip renders them with their freed pp and applies a suggestion only on the
// explicit click, via the same schedule PUT the knob panel uses.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CapacityAccount, WhatIfResult } from "../../api/capacity";
import { ToastProvider } from "../common";
import { WhatIfBar } from "./WhatIfBar";

const account = { id: "pa_mock", label: "Mock", provider: "mock" } as CapacityAccount;

const result: WhatIfResult = {
  accountId: "pa_mock",
  windowKey: "mock_window",
  horizonH: 2,
  horizonBasis: "until-reset",
  neededPp: 6,
  basis: "ewma-attribution",
  suggestions: [
    {
      actions: [
        {
          teamId: "t_maint", teamName: "canopy-maintenance", knob: "runState",
          value: "paused", label: "pause", freesPpHr: 4.1,
        },
      ],
      freesPpHr: 4.1, freesPp: 8.2, satisfies: true,
    },
    {
      actions: [
        {
          teamId: "t_maint", teamName: "canopy-maintenance",
          knob: "maxConcurrentSessions", value: 1, label: "sessions 3→1", freesPpHr: 2.6,
        },
      ],
      freesPpHr: 2.6, freesPp: 5.2, satisfies: false,
    },
  ],
};

function mockFetch() {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({
        url: String(url),
        method: init?.method ?? "GET",
        body: init?.body ? JSON.parse(String(init.body)) : undefined,
      });
      const payload = String(url).includes("/capacity/whatif")
        ? result
        : { schedule: {}, predictions: {} };
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  return calls;
}

function renderBar() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <WhatIfBar account={account} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("WhatIfBar", () => {
  it("computes suggestions for a stated goal and labels sufficiency", async () => {
    const calls = mockFetch();
    renderBar();
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "6" } });
    fireEvent.click(screen.getByText("Show my options"));

    await waitFor(() =>
      expect(screen.getByText(/pause canopy-maintenance/)).toBeInTheDocument(),
    );
    const whatif = calls.find((c) => c.url.includes("/capacity/whatif"));
    expect(whatif?.body).toMatchObject({ accountId: "pa_mock", neededPp: 6 });
    // Both options render with their freed points; only the sufficient one gets ✓.
    expect(screen.getByText(/−4.1 pp\/hr · 8.2 pp/)).toBeInTheDocument();
    expect(screen.getByText("✓")).toBeInTheDocument();
    expect(screen.getByText("not enough")).toBeInTheDocument();
  });

  it("applies a suggestion only on the explicit click, via the schedule PUT", async () => {
    const calls = mockFetch();
    renderBar();
    fireEvent.click(screen.getByText("Show my options"));
    await waitFor(() =>
      expect(screen.getByText(/pause canopy-maintenance/)).toBeInTheDocument(),
    );
    // Nothing auto-applies: no schedule PUT yet.
    expect(calls.some((c) => c.url.includes("/schedule"))).toBe(false);

    fireEvent.click(screen.getAllByText("Apply")[0]);
    await waitFor(() =>
      expect(
        calls.find((c) => c.url.includes("/teams/t_maint/schedule") && c.method === "PUT"),
      ).toBeTruthy(),
    );
    const put = calls.find((c) => c.url.includes("/teams/t_maint/schedule"));
    expect(put?.body).toMatchObject({ runState: "paused" });
  });
});
