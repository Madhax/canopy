// Artifact Browser: browse, filter, inspect lineage, and preview content for artifacts
// produced across a team (Execute page view) or by a single agent (Agent Inspector tab).
import { useEffect, useMemo, useState } from "react";
import {
  useArtifact,
  useTeamArtifacts,
  type ArtifactMeta,
  type ArtifactPreview,
} from "../../api/work";
import { CenteredSpinner, EmptyState, Markdown } from "../common";

const REASON_TEXT: Record<string, string> = {
  "too-large": "Too large to preview inline (> 256 KB).",
  binary: "Binary content — no inline preview.",
  "missing-blob": "The artifact blob is missing from the store.",
};

function isMarkdownArtifact(meta: { name: string; type: string }): boolean {
  return (
    /\.(md|markdown)$/i.test(meta.name) ||
    /deliverable|plan|doc|report|readme|markdown|summary|spec|guideline/i.test(meta.type)
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export interface ArtifactBrowserViewProps {
  artifacts: ArtifactMeta[];
  nodeName: (id: string) => string;
  selectedRef: string | null;
  onSelectRef: (ref: string | null) => void;
  preview: ArtifactPreview | null;
  previewLoading?: boolean;
  onInspectNode?: (nodeId: string) => void;
  compact?: boolean;
}

export function ArtifactBrowserView({
  artifacts,
  nodeName,
  selectedRef,
  onSelectRef,
  preview,
  previewLoading = false,
  onInspectNode,
  compact = false,
}: ArtifactBrowserViewProps) {
  const [query, setQuery] = useState("");
  const [nodeFilter, setNodeFilter] = useState<string>("all");
  const [rawMode, setRawMode] = useState(false);

  const uniqueNodes = useMemo(
    () => Array.from(new Set(artifacts.map((a) => a.nodeId))),
    [artifacts],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return artifacts.filter((a) => {
      if (!compact && nodeFilter !== "all" && a.nodeId !== nodeFilter) return false;
      if (!q) return true;
      return (
        a.name.toLowerCase().includes(q) ||
        a.type.toLowerCase().includes(q) ||
        a.ref.toLowerCase().includes(q) ||
        (a.taskId ?? "").toLowerCase().includes(q) ||
        nodeName(a.nodeId).toLowerCase().includes(q)
      );
    });
  }, [artifacts, compact, nodeFilter, query, nodeName]);

  useEffect(() => {
    if (!selectedRef && filtered.length > 0) {
      onSelectRef(filtered[0].ref);
    }
  }, [filtered, selectedRef, onSelectRef]);

  if (artifacts.length === 0) {
    return (
      <EmptyState title="No artifacts yet">
        Artifacts produced by assignments will appear here as agents complete their work.
      </EmptyState>
    );
  }

  const selectedMeta =
    preview?.meta ?? artifacts.find((a) => a.ref === selectedRef) ?? null;
  const canRenderMarkdown = selectedMeta ? isMarkdownArtifact(selectedMeta) : false;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter by name, type, ref, or assignment…"
          aria-label="Filter artifacts"
          className="min-w-[180px] flex-1 rounded-md border border-border bg-canvas px-2.5 py-1 text-xs outline-none focus:border-accent"
        />
        {!compact && uniqueNodes.length > 1 && (
          <select
            value={nodeFilter}
            onChange={(e) => setNodeFilter(e.target.value)}
            aria-label="Filter by agent"
            className="rounded-md border border-border bg-canvas px-2 py-1 text-xs outline-none focus:border-accent"
          >
            <option value="all">All agents ({artifacts.length})</option>
            {uniqueNodes.map((nid) => (
              <option key={nid} value={nid}>
                {nodeName(nid)}
              </option>
            ))}
          </select>
        )}
        <span className="text-[11px] text-ink-muted">
          {filtered.length} artifact{filtered.length === 1 ? "" : "s"}
        </span>
      </div>

      <div
        className={
          compact
            ? "flex flex-col gap-3"
            : "grid grid-cols-1 gap-4 lg:grid-cols-[340px_minmax(0,1fr)]"
        }
      >
        {/* Artifact list */}
        <div
          className={`flex flex-col gap-1.5 overflow-y-auto ${
            compact ? "max-h-56" : "max-h-[540px]"
          }`}
        >
          {filtered.map((a) => {
            const active = a.ref === selectedRef;
            return (
              <button
                key={a.ref}
                type="button"
                onClick={() => onSelectRef(a.ref)}
                className={`flex flex-col gap-0.5 rounded-md border px-3 py-2 text-left text-xs transition-colors ${
                  active
                    ? "border-accent bg-accent/10 text-ink"
                    : "border-border bg-surface text-ink hover:border-accent/60"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-medium text-ink">
                    {a.name}
                    <span className="ml-1 font-mono text-[10px] text-ink-muted">
                      @v{a.version}
                    </span>
                  </span>
                  <span className="shrink-0 rounded bg-surface-2 px-1.5 py-0.5 text-[10px] text-ink-muted">
                    {a.type}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-x-2 text-[10px] text-ink-muted">
                  {!compact && <span>{nodeName(a.nodeId)}</span>}
                  {a.taskId && <span className="font-mono">{a.taskId}</span>}
                  <span>{formatBytes(a.size)}</span>
                  <span className="ml-auto">
                    {a.createdAt.slice(0, 19).replace("T", " ")}
                  </span>
                </div>
              </button>
            );
          })}
          {filtered.length === 0 && (
            <p className="py-4 text-center text-xs text-ink-muted">
              No artifacts match your filter.
            </p>
          )}
        </div>

        {/* Artifact detail & content preview */}
        <div className="flex min-w-0 flex-col rounded-md border border-border bg-surface p-3">
          {!selectedRef ? (
            <p className="py-8 text-center text-xs text-ink-muted">
              Select an artifact to preview its contents.
            </p>
          ) : (
            <>
              {selectedMeta && (
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-semibold text-ink">
                        {selectedMeta.name}@v{selectedMeta.version}
                      </span>
                      <span className="rounded bg-accent/10 px-1.5 py-0.5 text-[10px] font-medium text-accent">
                        {selectedMeta.type}
                      </span>
                      <span className="text-[11px] text-ink-muted">
                        {formatBytes(selectedMeta.size)}
                      </span>
                    </div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[10px] text-ink-muted">
                      <span className="font-mono">{selectedMeta.ref}</span>
                      <span>·</span>
                      {onInspectNode ? (
                        <button
                          type="button"
                          onClick={() => onInspectNode(selectedMeta.nodeId)}
                          className="text-accent hover:underline"
                        >
                          {nodeName(selectedMeta.nodeId)}
                        </button>
                      ) : (
                        <span>{nodeName(selectedMeta.nodeId)}</span>
                      )}
                      {selectedMeta.taskId && (
                        <>
                          <span>·</span>
                          <span className="font-mono">{selectedMeta.taskId}</span>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {preview?.lineage && preview.lineage.length > 1 && (
                      <div className="flex items-center gap-1 mr-1">
                        {preview.lineage.map((v) => (
                          <button
                            key={v.ref}
                            type="button"
                            onClick={() => onSelectRef(v.ref)}
                            className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${
                              v.ref === selectedRef
                                ? "bg-accent text-white"
                                : "bg-surface-2 text-ink-muted hover:text-ink"
                            }`}
                          >
                            v{v.version}
                          </button>
                        ))}
                      </div>
                    )}
                    {canRenderMarkdown && preview?.content != null && (
                      <button
                        type="button"
                        onClick={() => setRawMode((r) => !r)}
                        className="rounded border border-border bg-canvas px-2 py-0.5 text-[10px] text-ink-muted hover:text-ink"
                      >
                        {rawMode ? "Rendered" : "Raw"}
                      </button>
                    )}
                  </div>
                </div>
              )}

              {previewLoading ? (
                <CenteredSpinner label="Loading artifact…" />
              ) : preview ? (
                preview.content !== null ? (
                  canRenderMarkdown && !rawMode ? (
                    <div
                      className={`overflow-y-auto rounded bg-canvas p-3 text-xs text-ink ${
                        compact ? "max-h-72" : "max-h-[460px]"
                      }`}
                    >
                      <Markdown text={preview.content} />
                    </div>
                  ) : (
                    <pre
                      className={`overflow-y-auto whitespace-pre-wrap rounded bg-canvas p-3 font-mono text-[11px] text-ink ${
                        compact ? "max-h-72" : "max-h-[460px]"
                      }`}
                    >
                      {preview.content}
                    </pre>
                  )
                ) : (
                  <p className="py-6 text-center text-xs text-ink-muted">
                    {REASON_TEXT[preview.reason ?? ""] ?? "No preview available."}
                  </p>
                )
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export function ArtifactBrowserSection({
  teamId,
  nodeName,
  onInspectNode,
}: {
  teamId: string;
  nodeName: (id: string) => string;
  onInspectNode?: (nodeId: string) => void;
}) {
  const artifacts = useTeamArtifacts(teamId);
  const [selectedRef, setSelectedRef] = useState<string | null>(null);
  const preview = useArtifact(teamId, selectedRef);

  if (artifacts.isLoading) {
    return <CenteredSpinner label="Loading artifacts…" />;
  }

  return (
    <section className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-ink">Artifacts</h2>
          <p className="text-xs text-ink-muted">
            Versioned deliverables and work outputs produced across this team
          </p>
        </div>
      </div>
      <ArtifactBrowserView
        artifacts={artifacts.data ?? []}
        nodeName={nodeName}
        selectedRef={selectedRef}
        onSelectRef={setSelectedRef}
        preview={preview.data ?? null}
        previewLoading={preview.isLoading}
        onInspectNode={onInspectNode}
      />
    </section>
  );
}

