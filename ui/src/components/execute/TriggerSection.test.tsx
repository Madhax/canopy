// TriggerPanel (standing-teams-ux.md §2): the row reads as a sentence, the create card
// requires a source, dry-run renders, and failure shows one honest chip.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ConnectorInstance } from "../../api/connectors";
import type { Trigger } from "../../api/work";
import { TriggerPanel } from "./TriggerSection";

const inst: ConnectorInstance = {
  id: "ci_1", teamId: "o1", packKey: "github", name: "canopy repo",
  config: { owner: "acme", repo: "canopy" }, secretBindings: { "scm-token": "sec_1" },
  enabledGrants: ["connector.github.issues.read"], nodeLinks: null, enabled: true,
  createdAt: "2026-08-08T00:00:00Z", updatedAt: "2026-08-08T00:00:00Z",
};

const trigger: Trigger = {
  id: "tr_1", teamId: "o1", name: "bug intake", kind: "github-issues", nodeId: null,
  instanceId: "ci_1", config: { labels: ["bug"] },
  intentTemplate: "Fix {{url}}", enabled: true, cursor: null,
  lastCheckedAt: "2026-08-08T01:00:00Z", lastFiredAt: null,
  lastError: "github: 401 bad credentials",
  createdAt: "2026-08-08T00:00:00Z", updatedAt: "2026-08-08T00:00:00Z",
};

function renderPanel(overrides: Partial<Parameters<typeof TriggerPanel>[0]> = {}) {
  const props = {
    triggers: [trigger], instances: [inst],
    nodeName: (id: string) => id, nodes: [{ id: "a_1", name: "Lead" }],
    onCreate: vi.fn(), onToggle: vi.fn(), onDelete: vi.fn(), onCheck: vi.fn(),
    ...overrides,
  };
  render(<TriggerPanel {...props} />);
  return props;
}

describe("TriggerPanel", () => {
  it("states the source as a sentence and surfaces failure once", () => {
    renderPanel();
    expect(screen.getByText(/bug intake/)).toBeInTheDocument();
    expect(screen.getByText(/new issues labeled bug in/)).toBeInTheDocument();
    expect(screen.getByText("canopy repo")).toBeInTheDocument();
    expect(screen.getByText(/team root/)).toBeInTheDocument();
    const failing = screen.getByText("failing");
    expect(failing).toHaveAttribute("title", "github: 401 bad credentials");
  });

  it("creates a trigger from the When → Then card", () => {
    const props = renderPanel();
    fireEvent.click(screen.getByText("New trigger"));
    fireEvent.change(screen.getByLabelText("source instance"), { target: { value: "ci_1" } });
    fireEvent.change(screen.getByLabelText("trigger name"), { target: { value: "docs intake" } });
    fireEvent.change(screen.getByLabelText("labels"), { target: { value: "docs" } });
    fireEvent.click(screen.getByText("Create"));
    expect(props.onCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "docs intake", instanceId: "ci_1", nodeId: null,
        config: { labels: ["docs"] },
      }),
    );
  });

  it("check-now and toggle hit their handlers; dry run renders candidates", () => {
    const props = renderPanel({
      dryRun: {
        candidates: [{ key: "issue:7", title: "dry me", url: "u" }],
        renderedFirst: "Fix u: dry me",
      },
    });
    fireEvent.click(screen.getByText("check now"));
    expect(props.onCheck).toHaveBeenCalledWith("tr_1");
    fireEvent.click(screen.getByLabelText(/enabled/i));
    expect(props.onToggle).toHaveBeenCalled();
    expect(screen.getByText(/1 issue would fire/)).toBeInTheDocument();
    expect(screen.getByText(/issue:7/)).toBeInTheDocument();
  });

  it("disables creation when no instance can serve events", () => {
    renderPanel({ instances: [], triggers: [] });
    expect(screen.getByText("New trigger")).toBeDisabled();
    expect(screen.getByText(/No triggers/)).toBeInTheDocument();
  });
});
