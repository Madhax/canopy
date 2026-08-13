// Regression for the 2026-08-10 overwrite incident: undo restored a pre-save snapshot
// INCLUDING its stale `updatedAt`, so the next autosave 409'd into the conflict dialog.
// safeUndo/safeRedo time-travel the content but re-apply the last server-issued token.
import { beforeEach, describe, expect, it } from "vitest";
import {
  noteServerUpdatedAt,
  safeRedo,
  safeUndo,
  useDocumentStore,
  useTemporalStore,
} from "./documentStore";
import type { TeamDoc } from "../schema/team";

const doc = (name: string, updatedAt: string): TeamDoc =>
  ({
    kind: "canopy.team",
    schemaVersion: 2,
    id: "t1",
    name,
    organizationType: "product-engineering",
    updatedAt,
    agents: [],
    dependencies: [],
    customRoles: [],
    childTeams: [],
    meta: {},
  }) as TeamDoc;

describe("safeUndo/safeRedo", () => {
  beforeEach(() => {
    useTemporalStore.getState().clear();
    useDocumentStore.getState().load(doc("Original", "T1"));
    useTemporalStore.getState().clear();
  });

  it("undo restores content but keeps the latest server token", () => {
    noteServerUpdatedAt("T1");
    // An edit (the accidental stamp), then a successful autosave bumping the token.
    useDocumentStore.setState((s) => ({ doc: { ...s.doc!, name: "Accident" } }));
    useTemporalStore.getState().pause();
    useDocumentStore.getState().setUpdatedAt("T2");
    useTemporalStore.getState().resume();
    noteServerUpdatedAt("T2");

    safeUndo();

    const d = useDocumentStore.getState().doc!;
    expect(d.name).toBe("Original"); // the content came back…
    expect(d.updatedAt).toBe("T2"); // …but the concurrency token stayed current
  });

  it("redo re-applies the token too", () => {
    noteServerUpdatedAt("T1");
    useDocumentStore.setState((s) => ({ doc: { ...s.doc!, name: "Edit" } }));
    useTemporalStore.getState().pause();
    useDocumentStore.getState().setUpdatedAt("T2");
    useTemporalStore.getState().resume();
    noteServerUpdatedAt("T2");

    safeUndo();
    safeRedo();

    const d = useDocumentStore.getState().doc!;
    expect(d.name).toBe("Edit");
    expect(d.updatedAt).toBe("T2");
  });
});
