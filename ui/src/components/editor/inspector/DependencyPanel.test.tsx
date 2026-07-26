// The resolve-on toggle writes through to the document (docs/org-chart-editor.md §7.4):
// "starts when: work is submitted (verify) / work is accepted (consume)".
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import type { OrganizationDoc } from "../../../schema/organization";
import { useDocumentStore } from "../../../store/documentStore";
import { useSelectionStore } from "../../../store/selectionStore";
import { DependencyPanel } from "./DependencyPanel";

function docWithDep(): OrganizationDoc {
  return {
    kind: "canopy.organization",
    schemaVersion: 1,
    id: "o1",
    name: "Test",
    organizationType: "product-engineering",
    agents: [
      { id: "a_qa", name: "QA", role: { key: "qa-engineer", version: 1 }, managerId: null, extensions: { instructions: "", responsibilities: [] }, salary: { perAssignmentAllowance: 1, warnThresholdPct: 80, hardStop: true }, position: { x: 0, y: 0 } },
      { id: "a_be", name: "BE", role: { key: "backend-engineer", version: 1 }, managerId: "a_qa", extensions: { instructions: "", responsibilities: [] }, salary: { perAssignmentAllowance: 1, warnThresholdPct: 80, hardStop: true }, position: { x: 0, y: 0 } },
    ],
    dependencies: [{ id: "d1", from: "a_qa", to: "a_be", resolveOn: "accepted", note: null }],
    customRoles: [],
    childOrganizations: [],
    meta: {},
  };
}

const dep = () => useDocumentStore.getState().doc!.dependencies[0];

beforeEach(() => {
  useDocumentStore.getState().load(docWithDep());
  useSelectionStore.setState({ path: [] });
});

describe("DependencyPanel resolve-on toggle", () => {
  it("renders both options with the document's value checked", () => {
    const doc = useDocumentStore.getState().doc!;
    render(<DependencyPanel dependency={doc.dependencies[0]} org={doc} />);
    const accepted = screen.getByRole("radio", { name: "work is accepted" });
    const submitted = screen.getByRole("radio", { name: "work is submitted" });
    expect(accepted.getAttribute("aria-checked")).toBe("true");
    expect(submitted.getAttribute("aria-checked")).toBe("false");
  });

  it("clicking 'work is submitted' flips the dependency to delivered", () => {
    const doc = useDocumentStore.getState().doc!;
    render(<DependencyPanel dependency={doc.dependencies[0]} org={doc} />);
    fireEvent.click(screen.getByRole("radio", { name: "work is submitted" }));
    expect(dep().resolveOn).toBe("delivered");
  });

  it("clicking 'work is accepted' flips it back", () => {
    useDocumentStore.getState().setDependencyResolveOn([], "d1", "delivered");
    const doc = useDocumentStore.getState().doc!;
    render(<DependencyPanel dependency={doc.dependencies[0]} org={doc} />);
    fireEvent.click(screen.getByRole("radio", { name: "work is accepted" }));
    expect(dep().resolveOn).toBe("accepted");
  });
});
