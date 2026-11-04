import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactFlowProvider } from "@xyflow/react";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Catalog } from "../../../schema/catalog";
import type { Agent, TeamDoc } from "../../../schema/team";
import { useDocumentStore } from "../../../store/documentStore";
import { useSelectionStore } from "../../../store/selectionStore";
import { AgentNode } from "../canvas/AgentNode";
import { AgentPanel } from "./AgentPanel";

const here = dirname(fileURLToPath(import.meta.url));
const catalog = JSON.parse(
  readFileSync(join(here, "..", "..", "..", "..", "..", "catalog", "catalog.json"), "utf-8"),
) as Catalog;

function makeDoc(agentOverrides: Partial<Agent> = {}): TeamDoc {
  return {
    kind: "canopy.team",
    schemaVersion: 1,
    id: "t1",
    name: "Pod",
    organizationType: "product-engineering",
    agents: [
      {
        id: "a_lead",
        name: "Lead",
        role: { key: "engineering-lead", version: 1 },
        managerId: null,
        extensions: { instructions: "", responsibilities: [] },
        salary: { perAssignmentAllowance: 160000, warnThresholdPct: 80, hardStop: true },
        position: { x: 0, y: 0 },
        ...agentOverrides,
      },
    ],
    dependencies: [],
    customRoles: [],
    childTeams: [],
    meta: {},
  };
}

function mockProfileApi(opts: {
  profiles?: unknown[];
  bindings?: unknown[];
  defaultProfileId?: string | null;
}) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/profiles")) {
      return new Response(JSON.stringify(opts.profiles ?? []), { status: 200 });
    }
    if (url.endsWith("/bindings")) {
      return new Response(JSON.stringify(opts.bindings ?? []), { status: 200 });
    }
    if (url.endsWith("/profile-default")) {
      return new Response(
        JSON.stringify({ teamId: "t1", profileId: opts.defaultProfileId ?? null }),
        { status: 200 },
      );
    }
    return new Response("{}", { status: 200 });
  });
}

beforeEach(() => {
  useSelectionStore.setState({ path: [] });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AgentNode & AgentPanel model display and red invalid highlighting", () => {
  it("AgentNode shows the model feeding the node and default badge when inherited", () => {
    const doc = makeDoc();
    const role = catalog.roles.find((r) => r.key === "engineering-lead");
    const { container } = render(
      <ReactFlowProvider>
        <AgentNode
          id="a_lead"
          type="agent"
          selected={false}
          dragging={false}
          draggable={true}
          selectable={true}
          deletable={true}
          zIndex={0}
          isConnectable={true}
          positionAbsoluteX={0}
          positionAbsoluteY={0}
          data={{
            agent: doc.agents[0],
            role,
            isManager: true,
            selected: false,
            hasIssue: false,
            hasError: false,
            direction: "BT",
            model: {
              source: "team-default",
              profile: {
                id: "p1",
                teamId: "t1",
                name: "Team default (mock-1)",
                provider: "mock",
                model: "mock-1",
                endpoint: null,
                apiKeySecretId: null,
                params: { maxOutputTokens: 4096, temperature: 0.7, providerOptions: {} },
                systemPreamble: "",
                createdAt: "",
                updatedAt: "",
              },
            },
          }}
        />
      </ReactFlowProvider>,
    );

    expect(screen.getByText("mock · mock-1")).toBeTruthy();
    expect(screen.getByText("default")).toBeTruthy();
    expect(container.querySelector("[data-invalid]")).toBeNull();
  });

  it("AgentNode indicates when model is unspecified and highlights card red", () => {
    const doc = makeDoc();
    const role = catalog.roles.find((r) => r.key === "engineering-lead");
    const { container } = render(
      <ReactFlowProvider>
        <AgentNode
          id="a_lead"
          type="agent"
          selected={false}
          dragging={false}
          draggable={true}
          selectable={true}
          deletable={true}
          zIndex={0}
          isConnectable={true}
          positionAbsoluteX={0}
          positionAbsoluteY={0}
          data={{
            agent: doc.agents[0],
            role,
            isManager: true,
            selected: false,
            hasIssue: false,
            hasError: false,
            direction: "BT",
            model: { source: "unspecified" },
          }}
        />
      </ReactFlowProvider>,
    );

    expect(screen.getByText("model unspecified")).toBeTruthy();
    const card = container.querySelector("[data-invalid='true']");
    expect(card).toBeTruthy();
    expect(card?.className).toContain("border-danger");
  });

  it("AgentPanel highlights invalid name, role, salary, and unspecified model in red", async () => {
    const doc = makeDoc({
      name: "   ",
      role: { key: "nonexistent-role", version: 1 },
      salary: { perAssignmentAllowance: 0, warnThresholdPct: 80, hardStop: true },
    });
    useDocumentStore.getState().load(doc);
    mockProfileApi({
      profiles: [
        {
          id: "p1",
          teamId: "t1",
          name: "Sonnet",
          provider: "anthropic",
          model: "claude-sonnet-5",
          endpoint: null,
          apiKeySecretId: null,
          params: {},
          systemPreamble: "",
          createdAt: "",
          updatedAt: "",
        },
      ],
      bindings: [],
      defaultProfileId: null,
    });

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <AgentPanel
          agent={doc.agents[0]}
          team={doc}
          catalog={catalog}
          issues={[
            {
              code: "SALARY_INVALID",
              severity: "error",
              message: "Salary allowance must be a positive integer.",
              agentIds: ["a_lead"],
            },
          ]}
        />
      </QueryClientProvider>,
    );

    // Name input is highlighted red
    const nameInput = screen.getByLabelText("Name");
    expect(nameInput.getAttribute("aria-invalid")).toBe("true");
    expect(nameInput.className).toContain("border-danger");

    // Role select is highlighted red
    const roleSelect = screen.getByDisplayValue(/nonexistent-role/);
    expect(roleSelect.getAttribute("aria-invalid")).toBe("true");
    expect(roleSelect.className).toContain("border-danger");

    // Salary allowance input is highlighted red
    const salaryInput = screen.getByLabelText("Per-assignment allowance");
    expect(salaryInput.getAttribute("aria-invalid")).toBe("true");
    expect(salaryInput.className).toContain("border-danger");

    // Unspecified model select is highlighted red once loaded
    await waitFor(() => expect(screen.getByText(/No model specified/)).toBeTruthy());
    const modelSelect = screen.getByDisplayValue("— unspecified (no team default) —");
    expect(modelSelect.getAttribute("aria-invalid")).toBe("true");
    expect(modelSelect.className).toContain("border-danger");
  });
});
