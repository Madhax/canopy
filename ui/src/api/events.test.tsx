// The SSE hook (events.ts): stream events become targeted query invalidations; the live flag
// flips the work.ts polling fallback (testing.md §4 E5 row — "plan outline updates on SSE").
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useLiveStore, useOrgEvents } from "./events";

type Listener = (e: MessageEvent) => void;

class MockEventSource {
  static instances: MockEventSource[] = [];
  listeners = new Map<string, Listener[]>();
  onerror: (() => void) | null = null;
  closed = false;

  constructor(public url: string) {
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, fn: Listener) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), fn]);
  }

  emit(type: string, data: unknown = {}) {
    for (const fn of this.listeners.get(type) ?? []) {
      fn({ data: JSON.stringify(data) } as MessageEvent);
    }
  }

  close() {
    this.closed = true;
  }
}

function setup(orgId: string | null = "or_1") {
  const qc = new QueryClient();
  const invalidated = vi.spyOn(qc, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  const hook = renderHook(() => useOrgEvents(orgId), { wrapper });
  const keys = () => invalidated.mock.calls.map((c) => (c[0]!.queryKey as string[])[0]);
  return { hook, invalidated, keys, es: () => MockEventSource.instances.at(-1)! };
}

describe("useOrgEvents", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
    useLiveStore.setState({ live: false });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("connects per org and goes live on hello with a catch-up invalidation", () => {
    const { hook, es, keys } = setup();
    expect(es().url).toBe("/api/organizations/or_1/events");
    expect(hook.result.current).toBe(false);

    act(() => es().emit("hello", { seq: 7 }));
    expect(hook.result.current).toBe(true);
    expect(keys()).toContain("intents");
    expect(keys()).toContain("gates");
    expect(keys()).toContain("spend");
  });

  it("maps activity kinds to targeted invalidations", () => {
    const { es, invalidated, keys } = setup();
    act(() => es().emit("activity", { seq: 1, kind: "gate.opened", subjectIds: [] }));
    expect(keys()).toContain("gates");
    expect(keys()).toContain("notifications");
    expect(keys()).not.toContain("spend");

    invalidated.mockClear();
    act(() => es().emit("activity", { seq: 2, kind: "meter.topped-up", subjectIds: [] }));
    expect(keys()).toContain("spend");
    expect(keys()).not.toContain("gates");
  });

  it("coalesced family events invalidate their views; steps are throttled", () => {
    vi.useFakeTimers();
    try {
      const { es, invalidated, keys } = setup();
      act(() => es().emit("notes"));
      expect(keys()).toEqual(["intent-plan"]);

      invalidated.mockClear();
      act(() => es().emit("steps"));
      expect(keys()).toContain("assignment-detail"); // first one passes straight through

      invalidated.mockClear();
      act(() => es().emit("steps")); // inside the throttle window — deferred
      expect(invalidated).not.toHaveBeenCalled();
      act(() => vi.advanceTimersByTime(2100));
      expect(keys()).toContain("assignment-detail");
    } finally {
      vi.useRealTimers();
    }
  });

  it("falls back to polling on error and closes on unmount", () => {
    const { hook, es } = setup();
    act(() => es().emit("hello", { seq: 0 }));
    expect(hook.result.current).toBe(true);

    act(() => es().onerror?.());
    expect(hook.result.current).toBe(false); // work.ts intervals take over

    hook.unmount();
    expect(es().closed).toBe(true);
  });

  it("opens nothing without an org", () => {
    setup(null);
    expect(MockEventSource.instances).toHaveLength(0);
  });
});
