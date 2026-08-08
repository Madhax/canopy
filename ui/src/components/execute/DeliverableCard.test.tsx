// The deliverable viewer: content where the verdict happens — you can't accept what you
// can't see.
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ArtifactPreview, Deliverable } from "../../api/work";
import { DeliverableView } from "./DeliverableCard";

function deliverable(over: Partial<Deliverable> = {}): Deliverable {
  return {
    id: "dv_1", kind: "artifact", artifactRefs: ["org://acme/a_lead/deliverable@1"],
    summary: "Completed: hello world", accepted: null, reviewNote: null,
    createdAt: "2026-08-03T00:00:00Z", ...over,
  };
}

const preview: ArtifactPreview = {
  meta: { ref: "org://acme/a_lead/deliverable@1", name: "deliverable", type: "Deliverable",
          size: 20, version: 1, nodeId: "a_lead", createdAt: "" },
  content: "print('hello world')",
  reason: null,
};

describe("DeliverableView", () => {
  it("shows summary, refs, and the artifact content when open", () => {
    render(
      <DeliverableView deliverable={deliverable()} reviewable={false}
                       openRef="org://acme/a_lead/deliverable@1" preview={preview}
                       onToggleRef={() => {}} />,
    );
    expect(screen.getByText(/Completed: hello world/)).toBeTruthy();
    // F7: resolved/non-reviewable work starts collapsed — expand to see the body.
    fireEvent.click(screen.getByText(/Completed: hello world/));
    expect(screen.getByText("deliverable@1")).toBeTruthy();
    expect(screen.getByText("print('hello world')")).toBeTruthy();
  });

  it("awaiting review: accept always enabled, reject requires a note", () => {
    const onAccept = vi.fn();
    const onReject = vi.fn();
    render(
      <DeliverableView deliverable={deliverable()} reviewable openRef={null}
                       onToggleRef={() => {}} onAccept={onAccept} onReject={onReject} />,
    );
    expect(screen.getByText("awaiting your review")).toBeTruthy();
    const reject = screen.getByText("Reject") as HTMLButtonElement;
    expect(reject.disabled).toBe(true);
    fireEvent.change(screen.getByPlaceholderText(/Review note/), {
      target: { value: "not hello enough" },
    });
    expect(reject.disabled).toBe(false);
    fireEvent.click(reject);
    expect(onReject).toHaveBeenCalledWith("not hello enough");
    fireEvent.click(screen.getByText("Accept"));
    expect(onAccept).toHaveBeenCalled();
  });

  it("binary preview refuses inline content with a reason; verdict chips render", () => {
    render(
      <DeliverableView
        deliverable={deliverable({ accepted: true, reviewNote: "ship it" })}
        reviewable={false} openRef="org://acme/a_lead/deliverable@1"
        preview={{ ...preview, content: null, reason: "binary" }}
        onToggleRef={() => {}} />,
    );
    expect(screen.getByText("accepted")).toBeTruthy();
    fireEvent.click(screen.getByText("accepted")); // F7: recedes collapsed once resolved
    expect(screen.getByText(/Binary content/)).toBeTruthy();
    expect(screen.getByText(/review note: ship it/)).toBeTruthy();
  });

  it("F7: markdown-typed artifacts render as markdown, not monospace", () => {
    render(
      <DeliverableView
        deliverable={deliverable()} reviewable
        openRef="org://acme/a_lead/deliverable@1"
        preview={{ ...preview, meta: { ...preview.meta, name: "report.md" },
                   content: "# Findings\n\n- one\n- two" }}
        onToggleRef={() => {}} />,
    );
    expect(screen.getByText("Findings")).toBeTruthy();
    expect(screen.getByText("one")).toBeTruthy(); // a list item, not raw "- one"
    expect(screen.queryByText(/^- one/)).toBeNull();
  });
});
