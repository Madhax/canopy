// The cadence management list (E7, operator-experience.md §4): name/cron/target/last/next,
// enable toggle + delete, and the create form that "make this recurring" prefills.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Cadence } from "../../api/work";
import { CadencePanel } from "./CadenceSection";

const names: Record<string, string> = { a_lead: "Engineering Lead" };
const nodeName = (id: string) => names[id] ?? id;

function standup(over: Partial<Cadence> = {}): Cadence {
  return {
    id: "cd_1", nodeId: "a_lead", name: "daily standup", cron: "0 9 * * 1-5",
    intentText: "Report status of all current work", enabled: true,
    lastFiredAt: "2026-08-03T09:00:00Z", nextFireAt: "2026-08-04T09:00:00Z",
    createdAt: "2026-08-01T00:00:00Z", ...over,
  };
}

describe("CadencePanel", () => {
  it("lists cadences with cron, target, and last/next fire", () => {
    render(
      <CadencePanel cadences={[standup()]} nodeName={nodeName}
                    onCreate={() => {}} onToggle={() => {}} onDelete={() => {}} />,
    );
    expect(screen.getByText("daily standup")).toBeTruthy();
    expect(screen.getByText("0 9 * * 1-5")).toBeTruthy();
    expect(screen.getByText(/Engineering Lead/)).toBeTruthy();
    expect(screen.getByText(/last .+ · next /)).toBeTruthy();
  });

  it("toggle and delete dispatch; a disabled cadence shows next = off", () => {
    const onToggle = vi.fn();
    const onDelete = vi.fn();
    render(
      <CadencePanel cadences={[standup({ enabled: false, nextFireAt: null })]}
                    nodeName={nodeName}
                    onCreate={() => {}} onToggle={onToggle} onDelete={onDelete} />,
    );
    expect(screen.getByText(/next off/)).toBeTruthy();
    fireEvent.click(screen.getByText("off"));
    expect(onToggle).toHaveBeenCalledWith(expect.objectContaining({ id: "cd_1" }));
    fireEvent.click(screen.getByTitle("Delete this cadence"));
    expect(onDelete).toHaveBeenCalledWith("cd_1");
  });

  it("creates from the form with the default weekday cron", () => {
    const onCreate = vi.fn();
    render(
      <CadencePanel cadences={[]} nodeName={nodeName}
                    onCreate={onCreate} onToggle={() => {}} onDelete={() => {}} />,
    );
    fireEvent.click(screen.getByText("New cadence"));
    fireEvent.change(screen.getByPlaceholderText(/Name/), {
      target: { value: "weekly digest" },
    });
    fireEvent.change(screen.getByPlaceholderText(/Intent to fire/), {
      target: { value: "Summarize the week" },
    });
    fireEvent.click(screen.getByText("Schedule"));
    expect(onCreate).toHaveBeenCalledWith({
      name: "weekly digest", cron: "0 9 * * 1-5",
      intentText: "Summarize the week", nodeId: null,
    });
  });

  it("a make-this-recurring seed opens the form prefilled with the intent", () => {
    const onSeedConsumed = vi.fn();
    render(
      <CadencePanel cadences={[]} nodeName={nodeName}
                    seed={{ intentText: "Add CSV export", nodeId: "a_lead" }}
                    onCreate={() => {}} onToggle={() => {}} onDelete={() => {}}
                    onSeedConsumed={onSeedConsumed} />,
    );
    expect(
      (screen.getByPlaceholderText(/Intent to fire/) as HTMLInputElement).value,
    ).toBe("Add CSV export");
    expect(screen.getByText(/Target: Engineering Lead/)).toBeTruthy();
    expect(onSeedConsumed).toHaveBeenCalled();
  });
});
