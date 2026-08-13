// Version history — the operator-facing face of the revision log (server revisions.py).
// Every destructive write snapshots the version it replaced; restoring is itself
// snapshotted, so nothing done here can lose work either.
import { useRevisions, restoreRevision, type TeamRevision } from "../../api/teams";
import type { TeamDoc } from "../../schema/team";
import { ApiError } from "../../api/client";
import { Button, Dialog, CenteredSpinner, useToast } from "../common";
import { relativeTime } from "../../lib/format";

interface Props {
  open: boolean;
  teamId: string;
  onClose: () => void;
  /** Called with the restored document — the editor reloads it as the saved baseline. */
  onRestored: (doc: TeamDoc) => void;
}

const REASON_LABELS: Record<TeamRevision["reason"], string> = {
  save: "replaced by a save",
  overwrite: "replaced by an overwrite",
  restore: "replaced by a restore",
  delete: "deleted",
};

export function HistoryDialog({ open, teamId, onClose, onRestored }: Props) {
  const { toast } = useToast();
  const revisions = useRevisions(teamId, open);

  return (
    <Dialog open={open} onClose={onClose} title="Version history">
      <p className="mb-3 text-xs text-ink-muted">
        Every time a save replaces this team, the replaced version lands here (last 20 kept).
        Restoring snapshots the current version first — nothing you do here can lose work.
      </p>
      {revisions.isLoading ? (
        <CenteredSpinner label="Loading history…" />
      ) : revisions.data && revisions.data.revisions.length > 0 ? (
        <ul className="flex max-h-80 flex-col gap-1 overflow-y-auto">
          {revisions.data.revisions.map((rev) => (
            <li
              key={rev.id}
              className="flex items-center gap-3 rounded-md border border-border px-3 py-2 text-sm"
            >
              <div className="min-w-0 flex-1">
                <div className="truncate text-ink">{rev.name}</div>
                <div className="text-[11px] text-ink-subtle">
                  {rev.agentCount} agent{rev.agentCount === 1 ? "" : "s"} ·{" "}
                  {REASON_LABELS[rev.reason] ?? rev.reason} · {relativeTime(rev.savedAt)}
                </div>
              </div>
              <Button
                size="sm"
                variant="secondary"
                onClick={async () => {
                  try {
                    const result = await restoreRevision(teamId, rev.id);
                    onRestored(result.document as TeamDoc);
                    toast("Restored. The replaced version is now in history.", "success");
                    onClose();
                  } catch (err) {
                    toast(
                      err instanceof ApiError ? err.message : "Restore failed.",
                      "error",
                    );
                  }
                }}
              >
                Restore
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-ink-subtle">
          No revisions yet — they appear the first time a save replaces this team.
        </p>
      )}
    </Dialog>
  );
}
