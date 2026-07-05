import type { SaveStatus as Status } from "../../hooks/useAutosave";
import { Spinner } from "../common";

const LABELS: Record<Status, string> = {
  saved: "Saved",
  saving: "Saving…",
  unsaved: "Unsaved changes",
  failed: "Save failed — retrying",
  conflict: "Conflict",
};

export function SaveStatus({ status }: { status: Status }) {
  return (
    <span className="flex items-center gap-1.5 text-xs text-ink-muted">
      {status === "saving" && <Spinner className="size-3" />}
      {status === "saved" && <span className="size-2 rounded-full bg-ok" />}
      {(status === "unsaved" || status === "failed" || status === "conflict") && (
        <span className="size-2 rounded-full bg-warn" />
      )}
      {LABELS[status]}
    </span>
  );
}
