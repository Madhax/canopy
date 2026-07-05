import { Button, Dialog } from "../common";

interface Props {
  open: boolean;
  onReloadTheirs: () => void;
  onOverwriteMine: () => void;
}

// 409 conflict resolution: reload the server copy, or force-overwrite with local edits (docs §7.4).
export function ConflictDialog({ open, onReloadTheirs, onOverwriteMine }: Props) {
  return (
    <Dialog
      open={open}
      onClose={onReloadTheirs}
      title="This organization changed elsewhere"
      footer={
        <>
          <Button variant="secondary" onClick={onReloadTheirs}>
            Reload theirs
          </Button>
          <Button variant="danger" onClick={onOverwriteMine}>
            Overwrite with mine
          </Button>
        </>
      }
    >
      <p className="text-ink-muted">
        The stored document was updated since you loaded it — most likely from another tab. Reload
        the latest version (discarding your unsaved edits), or overwrite it with your current
        changes.
      </p>
    </Dialog>
  );
}
