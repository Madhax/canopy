# Workspace & Artifacts — Where Work Happens and How It Leaves

The workspace is the agent's private working directory — the only filesystem it can touch. Artifacts are the only way work exits it (invariant 2: exchange is artifacts and messages, platform-mediated, or nothing). This doc defines the layout, the artifact path, and the store.

## 1. Workspace layout

Created by the sandbox provider at `data/sandboxes/<actuationId>/<nodeId>/workspace/`:

```
workspace/
├── brief/        # read-mostly: task brief text + fetched input artifacts (materialized by intake)
├── work/         # scratch — the agent's free area; never inspected by the platform
├── out/          # staging for deliverables; produce_artifact() uploads from here
└── memory.json   # phase-2 memory stub (see agent-runtime.md)
```

Phase-2 policy: the workspace persists across tasks within one actuation (`brief/` and `out/` are cleared at each task intake; `work/` and `memory.json` persist). This approximates the domain's "workspace per Assignment, memory durable" split without a second storage system; phase 3 sharpens it (fresh workspace per assignment, platform-managed memory). Deactuation keeps workspaces on disk (`keep_workspace_on_destroy`) for inspection; a GC command (`canopy sandbox gc`) prunes old actuations.

## 2. The artifact path

```
agent writes workspace/out/report.md
  └─ tool: produce_artifact("out/report.md", type="document", name="q3-report")
       └─ runtime: sha256, POST /api/dp/artifacts (multipart, run token)
            └─ control plane: dedupe by hash, assign version (name exists ⇒ @n+1, linked to @n),
                              record provenance {nodeId, taskId, actuationId},
                              return ref  org://acme-software/a_qa01/q3-report@1
                 └─ agent finishes task citing the ref; A2A artifact parts carry refs, never blobs
```

Consumption is the mirror image: a manager delegates citing refs → intake calls `fetch_artifact(ref)` → control plane authorizes (the ref must be in the delegating task's grant set — the manager can grant only refs it can itself read) → blob materializes under `brief/`. Access checks follow the domain's team-visibility rule reduced to phase-2 scope: a node may read artifacts produced within its own team (its manager + siblings' published outputs routed through the manager) plus anything explicitly granted on a task. Cross-team grants proper are phase 3; the grant-set mechanism built here is what they'll use.

## 3. Store properties

Content-addressed blobs (`data/artifacts/<sha2>/<sha256>`), metadata in SQLite (`control-plane.md` §7). Immutable versions with lineage; refs never dangle (deletes are tombstones in v1 — blob GC only when no live org references the hash). Size cap per artifact (default 50 MB) and per-actuation quota, enforced at upload. Types are an open vocabulary (`document`, `code-patch`, `dataset`, `report`, …) — a string, not an enum, per the domain.

The `ArtifactStore` interface (`put/get/resolve/list/lineage`) is object-store-shaped; the v1 local-disk backend swaps for S3/GCS/MinIO in the roadmap without touching provenance or refs (metadata stays in the control plane's DB either way).

## 4. Operator surface

The UI's intent panel and node inspector list produced artifacts (name, type, version chain, producer, task, size) with download links via `GET /api/artifacts/{ref}?content=1`. The activity feed logs every publish. This is also the phase-2 answer to "the artifact the user asked the org for": the intent's completing artifact refs render as the deliverable card.
