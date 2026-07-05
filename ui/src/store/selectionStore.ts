// Non-temporal UI state: which nested org is open (drill-in path) and what's selected.
import { create } from "zustand";

export type Selection =
  | { kind: "none" }
  | { kind: "agent"; id: string }
  | { kind: "dependency"; id: string }
  | { kind: "childOrg"; id: string };

interface SelectionStore {
  path: string[];
  selection: Selection;
  setPath: (path: string[]) => void;
  select: (selection: Selection) => void;
  clear: () => void;
}

export const useSelectionStore = create<SelectionStore>((set) => ({
  path: [],
  selection: { kind: "none" },
  setPath: (path) => set({ path, selection: { kind: "none" } }),
  select: (selection) => set({ selection }),
  clear: () => set({ selection: { kind: "none" } }),
}));
