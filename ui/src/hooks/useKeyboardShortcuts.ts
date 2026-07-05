import { useEffect } from "react";
import { useDocumentStore, useTemporalStore } from "../store/documentStore";
import { useSelectionStore } from "../store/selectionStore";

function isTypingTarget(el: EventTarget | null): boolean {
  const node = el as HTMLElement | null;
  if (!node) return false;
  const tag = node.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || node.isContentEditable;
}

/** ⌘Z / ⌘⇧Z undo-redo, ⌘S save, Delete removes the current selection (docs §7.4). */
export function useKeyboardShortcuts(onSave: () => void) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      const store = useDocumentStore.getState();
      const { selection, path, clear } = useSelectionStore.getState();

      if (mod && e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (e.shiftKey) useTemporalStore.getState().redo();
        else useTemporalStore.getState().undo();
        return;
      }
      if (mod && e.key.toLowerCase() === "s") {
        e.preventDefault();
        onSave();
        return;
      }
      if ((e.key === "Delete" || e.key === "Backspace") && !isTypingTarget(e.target)) {
        if (selection.kind === "agent") {
          store.deleteAgent(path, selection.id);
          clear();
        } else if (selection.kind === "dependency") {
          store.removeDependency(path, selection.id);
          clear();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onSave]);
}
