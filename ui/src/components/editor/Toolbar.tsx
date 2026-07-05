import { useStore } from "zustand";
import { useTemporalStore } from "../../store/documentStore";
import type { LayoutDirection } from "../../store/settingsStore";
import type { SaveStatus as Status } from "../../hooks/useAutosave";
import { Button } from "../common";
import { ThemeSwitcher } from "../ThemeSwitcher";
import { SaveStatus } from "./SaveStatus";

interface Props {
  status: Status;
  errorCount: number;
  warningCount: number;
  onBack: () => void;
  onShowIssues: () => void;
  onAutoLayout: () => void;
  onInvert: () => void;
  direction: LayoutDirection;
  onReset: () => void;
  onExport: () => void;
  onDownload: () => void;
  onUpload: () => void;
  onToggleJson: () => void;
  jsonOpen: boolean;
}

export function Toolbar({
  status,
  errorCount,
  warningCount,
  onBack,
  onShowIssues,
  onAutoLayout,
  onInvert,
  direction,
  onReset,
  onExport,
  onDownload,
  onUpload,
  onToggleJson,
  jsonOpen,
}: Props) {
  const canUndo = useStore(useTemporalStore, (s) => s.pastStates.length > 0);
  const canRedo = useStore(useTemporalStore, (s) => s.futureStates.length > 0);

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={onShowIssues}
        title="Show validation issues"
        className="flex items-center gap-1.5 rounded-md border border-border px-2 py-1 text-xs"
      >
        {errorCount > 0 ? (
          <span className="flex items-center gap-1 text-danger">● {errorCount}</span>
        ) : (
          <span className="flex items-center gap-1 text-ok">✓</span>
        )}
        {warningCount > 0 && <span className="text-warn">▲ {warningCount}</span>}
      </button>

      <div className="mx-1 h-5 w-px bg-border" />

      <Button size="sm" variant="ghost" disabled={!canUndo} onClick={() => useTemporalStore.getState().undo()}>
        Undo
      </Button>
      <Button size="sm" variant="ghost" disabled={!canRedo} onClick={() => useTemporalStore.getState().redo()}>
        Redo
      </Button>
      <Button size="sm" variant="ghost" onClick={onAutoLayout}>
        Auto-layout
      </Button>
      <Button
        size="sm"
        variant="ghost"
        onClick={onInvert}
        title={direction === "BT" ? "Currently bottom-up — flip to top-down" : "Currently top-down — flip to bottom-up"}
      >
        {direction === "BT" ? "↑ Bottom-up" : "↓ Top-down"}
      </Button>
      <Button size="sm" variant="ghost" onClick={onReset}>
        Reset
      </Button>

      <div className="mx-1 h-5 w-px bg-border" />

      <Button
        size="sm"
        variant={jsonOpen ? "secondary" : "ghost"}
        onClick={onToggleJson}
        title="Toggle live JSON preview"
      >
        JSON
      </Button>
      <Button size="sm" variant="ghost" onClick={onUpload}>
        Upload JSON
      </Button>
      <Button size="sm" variant="ghost" onClick={onDownload}>
        Download JSON
      </Button>
      <Button size="sm" variant="primary" onClick={onExport}>
        Export
      </Button>

      <div className="mx-1 h-5 w-px bg-border" />
      <ThemeSwitcher compact />
      <SaveStatus status={status} />

      <Button size="sm" variant="ghost" onClick={onBack}>
        ← All orgs
      </Button>
    </div>
  );
}
