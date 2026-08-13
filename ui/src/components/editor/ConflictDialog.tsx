import { Button, Dialog } from "../common";

interface Props {
  open: boolean;
  onReloadTheirs: () => void;
  onOverwriteMine: () => void;
}

// 409 conflict resolution. Neither choice can lose work anymore: every overwrite
// snapshots the version it replaces (revisions.py), and the dialog says so — the
// incident this redesign answers ended with an operator guessing between two
// destructive-sounding buttons.
export function ConflictDialog({ open, onReloadTheirs, onOverwriteMine }: Props) {
  return (
    <Dialog
      open={open}
      onClose={onReloadTheirs}
      title="This team changed since you loaded it"
      footer={
        <>
          <Button variant="secondary" onClick={onReloadTheirs}>
            Load the saved version
          </Button>
          <Button variant="danger" onClick={onOverwriteMine}>
            Keep mine (replaces saved)
          </Button>
        </>
      }
    >
      <p className="text-ink-muted">
        The stored copy was updated since this editor loaded it — usually another tab, or a
        save that landed while you were undoing. <strong>Load the saved version</strong> to
        see what's stored (your unsaved edits here are discarded), or{" "}
        <strong>keep mine</strong> to replace it with what you see here.
      </p>
      <p className="mt-2 text-xs text-ink-subtle">
        Every saved version this replaces is kept — Toolbar → History restores any of the
        last 20.
      </p>
    </Dialog>
  );
}
