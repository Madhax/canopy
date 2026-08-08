// ConnectorPanel (builder-connectors-ux.md §2.3): the capability mask renders risk + the
// governed lock, credentials are write-only with a bound chip, scope is legible.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ConnectorInstance, ConnectorPack } from "../../../api/connectors";
import type { OrganizationDoc } from "../../../schema/organization";
import { ToastProvider } from "../../common";
import { ConnectorPanel } from "./ConnectorPanel";

const pack: ConnectorPack = {
  key: "github", version: 1, title: "GitHub", kind: "native",
  secrets: [{ credentialKind: "scm-token", required: true,
              scopesHint: ["contents:rw", "issues:ro"] }],
  configSchema: {
    owner: { type: "string", required: true },
    repo: { type: "string", required: true },
    branchPattern: { type: "string", default: "canopy/*", narrowable: true },
  },
  grants: [
    { key: "connector.github.issues.read", title: "Read GitHub issues", riskClass: "read",
      minSandboxTier: 1, executor: "connector", governedActions: [], tools: [],
      provides: ["issues.read"], params: {} },
    { key: "connector.github.pr.create", title: "Open a pull request (governed)",
      riskClass: "write", minSandboxTier: 1, executor: "connector",
      governedActions: ["create_pull_request"], tools: [], provides: [], params: {} },
  ],
};

const instance: ConnectorInstance = {
  id: "ci_1", organizationId: "o1", packKey: "github", name: "canopy repo",
  config: { owner: "acme", repo: "canopy" },
  secretBindings: { "scm-token": "sec_1" },
  enabledGrants: ["connector.github.issues.read"],
  nodeLinks: null, enabled: true,
  createdAt: "2026-08-08T00:00:00Z", updatedAt: "2026-08-08T00:00:00Z",
};

const org = {
  agents: [
    { id: "a_1", name: "Lead", managerId: null, role: { key: "engineering-lead" } },
    { id: "a_2", name: "Writer", managerId: "a_1", role: { key: "tech-writer" } },
  ],
} as unknown as OrganizationDoc;

function renderPanel(inst: ConnectorInstance = instance) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <ConnectorPanel orgId="o1" instance={inst} pack={pack} org={org} onClose={vi.fn()} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("ConnectorPanel", () => {
  it("renders the capability mask with risk badges and the governed lock", () => {
    renderPanel();
    expect(screen.getByText("Read GitHub issues")).toBeInTheDocument();
    expect(screen.getByText("read")).toBeInTheDocument();
    expect(screen.getByText("Open a pull request (governed)")).toBeInTheDocument();
    expect(screen.getByTitle(/approval gate/)).toBeInTheDocument();
    expect(screen.getByText(/serves: issues.read/)).toBeInTheDocument();
    // The mask state mirrors enabledGrants.
    const boxes = screen.getAllByRole("checkbox");
    // [enabled, issues.read, pr.create] — order of render
    expect((boxes[1] as HTMLInputElement).checked).toBe(true);
    expect((boxes[2] as HTMLInputElement).checked).toBe(false);
  });

  it("credentials are write-only: bound chip, password field, never a value", () => {
    renderPanel();
    expect(screen.getByText("bound")).toBeInTheDocument();
    const field = screen.getByPlaceholderText(/stored encrypted/);
    expect(field).toHaveAttribute("type", "password");
    expect((field as HTMLInputElement).value).toBe("");
    expect(screen.getByText(/contents:rw, issues:ro/)).toBeInTheDocument();
  });

  it("shows org-wide scope and the fixed-vs-narrowable config marks", () => {
    renderPanel();
    const radios = screen.getAllByRole("radio");
    expect((radios[0] as HTMLInputElement).checked).toBe(true); // org-wide
    expect(screen.getAllByText("fixed at instance").length).toBe(2);
    expect(screen.getByText("roles/nodes may tighten")).toBeInTheDocument();
  });

  it("node-scoped instances list the chart's nodes as link checkboxes", () => {
    renderPanel({ ...instance, nodeLinks: ["a_2"] });
    expect(screen.getByText("Lead")).toBeInTheDocument();
    const writer = screen.getByLabelText("Writer") as HTMLInputElement;
    expect(writer.checked).toBe(true);
  });
});
