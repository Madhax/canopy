// The deliverable viewer (operator-experience.md §4's deliverable card, pulled forward):
// what the node actually produced — summary, artifact refs, and the content itself —
// rendered where the verdict happens. You can't accept what you can't see.
import { useState } from "react";
import {
  useArtifact,
  type ArtifactPreview,
  type Deliverable,
} from "../../api/work";
import { Button } from "../common";

const REASON_TEXT: Record<string, string> = {
  "too-large": "Too large to preview inline (> 256 KB).",
  binary: "Binary content — no inline preview.",
  "missing-blob": "The artifact blob is missing from the store.",
};

// ---------------------------------------------------------------- presentational
export function DeliverableView({
  deliverable,
  reviewable,
  busy,
  openRef,
  preview,
  previewLoading,
  onToggleRef,
  onAccept,
  onReject,
}: {
  deliverable: Deliverable;
  reviewable: boolean; // the assignment is 'delivering' — the verdict is the operator's
  busy?: boolean;
  openRef: string | null;
  preview?: ArtifactPreview | null;
  previewLoading?: boolean;
  onToggleRef: (ref: string) => void;
  onAccept?: () => void;
  onReject?: (note: string) => void;
}) {
  const d = deliverable;
  const [note, setNote] = useState("");
  const verdict =
    d.accepted === true ? (
      <span className="rounded bg-ok/15 px-1.5 text-[10px] text-ok">accepted</span>
    ) : d.accepted === false ? (
      <span className="rounded bg-danger/15 px-1.5 text-[10px] text-danger">rejected</span>
    ) : (
      <span className="rounded bg-warn/15 px-1.5 text-[10px] text-warn">awaiting your review</span>
    );

  return (
    <div
      className={`mb-1 rounded-md border px-3 py-2 text-xs ${
        reviewable ? "border-warn/50 bg-warn/5" : "border-border bg-canvas"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span>📦</span>
        <span className="font-medium text-ink">{d.kind}</span>
        {verdict}
        {d.summary && <span className="text-ink-muted">{d.summary}</span>}
      </div>

      <div className="mt-1 flex flex-wrap gap-1.5">
        {d.artifactRefs.map((ref) => (
          <button
            key={ref}
            onClick={() => onToggleRef(ref)}
            title={ref}
            className={`rounded border px-1.5 py-0.5 font-mono text-[10px] ${
              openRef === ref
                ? "border-accent bg-accent/10 text-ink"
                : "border-border bg-surface text-ink-muted hover:border-accent"
            }`}
          >
            {ref.split("/").pop()}
          </button>
        ))}
        {d.artifactRefs.length === 0 && (
          <span className="text-[10px] text-ink-muted">no artifacts attached</span>
        )}
      </div>

      {openRef &&
        (previewLoading ? (
          <p className="mt-1 text-[11px] text-ink-muted">Loading artifact…</p>
        ) : preview ? (
          preview.content !== null ? (
            <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap rounded bg-surface-2 p-2 font-mono text-[11px] text-ink">
              {preview.content}
            </pre>
          ) : (
            <p className="mt-1 text-[11px] text-ink-muted">
              {REASON_TEXT[preview.reason ?? ""] ?? "No preview available."}
            </p>
          )
        ) : null)}

      {d.reviewNote && (
        <p className="mt-1 text-[11px] text-ink-muted">review note: {d.reviewNote}</p>
      )}

      {reviewable && onAccept && onReject && (
        <div className="mt-2 flex items-center gap-2">
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Review note (optional; required to reject)…"
            className="flex-1 rounded-md border border-border bg-surface px-2 py-1 text-[11px] outline-none focus:border-accent"
          />
          <Button size="sm" variant="primary" disabled={busy} onClick={onAccept}>
            Accept
          </Button>
          <Button
            size="sm"
            disabled={busy || !note.trim()}
            className="text-danger"
            onClick={() => onReject(note.trim())}
          >
            Reject
          </Button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------- wired
export function DeliverableCard({
  orgId,
  deliverable,
  reviewable,
  busy,
  onAccept,
  onReject,
}: {
  orgId: string | null;
  deliverable: Deliverable;
  reviewable: boolean;
  busy?: boolean;
  onAccept?: () => void;
  onReject?: (note: string) => void;
}) {
  const [openRef, setOpenRef] = useState<string | null>(
    // The review moment defaults to eyes-on: a single-artifact deliverable opens itself.
    reviewable && deliverable.artifactRefs.length === 1 ? deliverable.artifactRefs[0] : null,
  );
  const preview = useArtifact(orgId, openRef);

  return (
    <DeliverableView
      deliverable={deliverable}
      reviewable={reviewable}
      busy={busy}
      openRef={openRef}
      preview={preview.data ?? null}
      previewLoading={preview.isLoading}
      onToggleRef={(ref) => setOpenRef(openRef === ref ? null : ref)}
      onAccept={onAccept}
      onReject={onReject}
    />
  );
}
