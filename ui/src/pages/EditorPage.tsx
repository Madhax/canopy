import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useCatalog } from "../api/catalog";
import { importOrganization, useOrganization } from "../api/organizations";
import { useActuationCurrent } from "../api/actuation";
import { apiGet } from "../api/client";
import type { OrganizationDoc } from "../schema/organization";
import type { ValidationIssue } from "../validation/codes";
import { useDocumentStore, useTemporalStore } from "../store/documentStore";
import { useSelectionStore } from "../store/selectionStore";
import { useSettingsStore } from "../store/settingsStore";
import { ResetDialog } from "../components/editor/ResetDialog";
import { getOrgAtPath } from "../store/orgTree";
import { useValidation } from "../hooks/useValidation";
import { useAutosave } from "../hooks/useAutosave";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { layoutReportingTree } from "../lib/autoLayout";
import { downloadJson, pickJsonFile } from "../lib/download";
import { slugify } from "../lib/format";
import { CenteredSpinner, useToast } from "../components/common";
import { Breadcrumbs } from "../components/editor/Breadcrumbs";
import { Toolbar } from "../components/editor/Toolbar";
import { ActuationControls } from "../components/editor/ActuationControls";
import { ConflictDialog } from "../components/editor/ConflictDialog";
import { OrgCanvas } from "../components/editor/canvas/OrgCanvas";
import { Palette } from "../components/editor/palette/Palette";
import { Inspector } from "../components/editor/inspector/Inspector";
import { JsonDrawer } from "../components/editor/JsonDrawer";
import { ChildOrgDialog } from "../components/editor/palette/ChildOrgDialog";
import { CustomRoleForm } from "../components/editor/palette/CustomRoleForm";

export function EditorPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const query = useOrganization(id);
  const catalog = useCatalog();

  const doc = useDocumentStore((s) => s.doc);
  const load = useDocumentStore((s) => s.load);
  const store = useDocumentStore();
  const path = useSelectionStore((s) => s.path);
  const setPath = useSelectionStore((s) => s.setPath);
  const select = useSelectionStore((s) => s.select);
  const clear = useSelectionStore((s) => s.clear);

  const { status, saveNow, overwriteMine, markSavedSignature } = useAutosave(doc);
  const loadedId = useRef<string | null>(null);

  const direction = useSettingsStore((s) => s.layoutDirection);
  const setLayoutDirection = useSettingsStore((s) => s.setLayoutDirection);

  const [jsonOpen, setJsonOpen] = useState(false);
  const [childDialog, setChildDialog] = useState(false);
  const [customRoleDialog, setCustomRoleDialog] = useState(false);
  const [resetDialog, setResetDialog] = useState(false);
  const [rescueDoc, setRescueDoc] = useState<OrganizationDoc | null>(null);
  const [pendingLayout, setPendingLayout] = useState(false);

  // Load the fetched document into the store once, resetting history + selection.
  useEffect(() => {
    if (query.data && loadedId.current !== query.data.id) {
      load(query.data);
      useTemporalStore.getState().clear();
      setPath([]);
      markSavedSignature(query.data);
      loadedId.current = query.data.id;

      // Crash rescue: a sessionStorage mirror newer than the server copy means the last edits
      // never made it to a save. Offer to restore (docs §7.5).
      const raw = sessionStorage.getItem(`canopy:rescue:${query.data.id}`);
      if (raw) {
        try {
          const parsed = JSON.parse(raw) as OrganizationDoc;
          const server = query.data;
          const differs =
            JSON.stringify({ ...parsed, updatedAt: null }) !==
            JSON.stringify({ ...server, updatedAt: null });
          if (differs) setRescueDoc(parsed);
          else sessionStorage.removeItem(`canopy:rescue:${query.data.id}`);
        } catch {
          /* ignore malformed rescue */
        }
      }

      // Freshly created orgs are flagged for an initial auto-layout in the current direction.
      if ((query.data.meta as Record<string, unknown> | undefined)?.needsLayout) {
        setPendingLayout(true);
      }
    }
  }, [query.data, load, setPath, markSavedSignature]);

  const org = doc ? getOrgAtPath(doc, path) : null;
  const { currentIssues, issueAgentIds, issueDepIds, errorCount, warningCount } = useValidation(
    doc,
    catalog.data,
    path,
  );

  // Live actuation status (A2): map each node on the CURRENT canvas to its status pill.
  const { data: actuation } = useActuationCurrent(doc?.id);
  const nodeStatus = useMemo(() => {
    const m = new Map<string, string>();
    if (actuation) {
      const pathKey = JSON.stringify(path);
      for (const n of actuation.nodes) {
        if (JSON.stringify(n.orgPath) !== pathKey) continue;
        m.set(n.nodeId, n.subState === "ready" ? n.status ?? "idle" : n.subState);
      }
    }
    return m;
  }, [actuation, path]);

  useKeyboardShortcuts(saveNow);

  const focusIssue = useCallback(
    (issue: ValidationIssue) => {
      if (issue.orgPath && issue.orgPath.length > 0) setPath(issue.orgPath);
      if (issue.agentIds?.[0]) select({ kind: "agent", id: issue.agentIds[0] });
      else if (issue.dependencyIds?.[0]) select({ kind: "dependency", id: issue.dependencyIds[0] });
    },
    [setPath, select],
  );

  const runLayout = useCallback(
    (dir: typeof direction) => {
      store.applyBatch(path, (o) => {
        const positions = layoutReportingTree(o, dir);
        for (const a of o.agents) {
          const p = positions.get(a.id);
          if (p) a.position = p;
        }
        for (const c of o.childOrganizations) {
          const p = positions.get(c.organization.id);
          if (p) c.organization.meta = { ...c.organization.meta, position: p };
        }
      });
    },
    [path, store],
  );

  const onAutoLayout = useCallback(() => runLayout(direction), [runLayout, direction]);

  const onInvert = useCallback(() => {
    const next = direction === "BT" ? "TB" : "BT";
    setLayoutDirection(next);
    runLayout(next);
  }, [direction, setLayoutDirection, runLayout]);

  // Initial auto-layout for freshly created orgs (one history entry, then reset history).
  useEffect(() => {
    if (!pendingLayout || !doc || !org) return;
    store.applyBatch([], (o) => {
      const positions = layoutReportingTree(o, direction);
      for (const a of o.agents) {
        const p = positions.get(a.id);
        if (p) a.position = p;
      }
      if (o.meta) delete (o.meta as Record<string, unknown>).needsLayout;
    });
    useTemporalStore.getState().clear();
    setPendingLayout(false);
  }, [pendingLayout, doc, org, direction, store]);

  const onExport = useCallback(async () => {
    if (!doc) return;
    try {
      const res = await fetch(`/api/organizations/${doc.id}/export`);
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        toast(body?.error?.message ?? "Export blocked by validation errors.", "error");
        return;
      }
      downloadJson(`${slugify(doc.name)}.organization.json`, await res.text());
      toast("Exported canonical document.", "success");
    } catch {
      toast("Export failed.", "error");
    }
  }, [doc, toast]);

  const onDownload = useCallback(() => {
    if (!doc) return;
    downloadJson(`${slugify(doc.name)}.organization.json`, doc);
    toast("Downloaded current document.", "success");
  }, [doc, toast]);

  const onUpload = useCallback(async () => {
    try {
      const picked = await pickJsonFile();
      if (!picked) return;
      const imported = await importOrganization(picked);
      navigate(`/organizations/${imported.document.id}`);
    } catch {
      toast("Could not import that file.", "error");
    }
  }, [navigate, toast]);

  const reloadTheirs = useCallback(async () => {
    if (!id) return;
    const fresh = await apiGet<OrganizationDoc>(`/organizations/${id}`);
    load(fresh);
    useTemporalStore.getState().clear();
    markSavedSignature(fresh);
  }, [id, load, markSavedSignature]);

  const doOverwrite = useCallback(async () => {
    if (!id) return;
    const fresh = await apiGet<OrganizationDoc>(`/organizations/${id}`);
    await overwriteMine(fresh.updatedAt ?? null);
  }, [id, overwriteMine]);

  if (query.isLoading || catalog.isLoading || !doc || !catalog.data || !org) {
    return <CenteredSpinner label="Loading editor…" />;
  }

  const orgType = catalog.data.organizationTypes.find((o) => o.key === org.organizationType);

  return (
    <div className="flex h-screen flex-col">
      {rescueDoc && (
        <div className="flex items-center justify-between gap-3 border-b border-warn/40 bg-warn/10 px-4 py-2 text-sm text-ink">
          <span>Unsaved changes from a previous session were recovered.</span>
          <div className="flex gap-2">
            <button
              className="rounded-md border border-border px-2 py-1 text-xs hover:bg-surface-2"
              onClick={() => {
                if (id) sessionStorage.removeItem(`canopy:rescue:${id}`);
                setRescueDoc(null);
              }}
            >
              Discard
            </button>
            <button
              className="rounded-md bg-accent px-2 py-1 text-xs text-accent-fg hover:bg-accent-hover"
              onClick={() => {
                load(rescueDoc);
                useTemporalStore.getState().clear();
                setRescueDoc(null);
              }}
            >
              Restore
            </button>
          </div>
        </div>
      )}
      <div className="flex items-center justify-between gap-3 border-b border-border bg-surface px-4 py-2">
        <div className="flex items-center gap-3">
          <Breadcrumbs doc={doc} path={path} onNavigate={setPath} />
          <ActuationControls orgId={doc.id} />
        </div>
        <Toolbar
          status={status}
          errorCount={errorCount}
          warningCount={warningCount}
          onBack={() => navigate("/")}
          onShowIssues={clear}
          onAutoLayout={onAutoLayout}
          onInvert={onInvert}
          direction={direction}
          onReset={() => setResetDialog(true)}
          onExport={onExport}
          onDownload={onDownload}
          onUpload={onUpload}
          onToggleJson={() => setJsonOpen((v) => !v)}
          jsonOpen={jsonOpen}
        />
      </div>

      <div className="flex min-h-0 flex-1">
        <Palette
          catalog={catalog.data}
          orgType={orgType}
          onPlaceRole={(roleKey) =>
            select({ kind: "agent", id: store.placeAgent(path, roleKey, { x: 360, y: 200 }, catalog.data!) })
          }
          onStampFormation={(formationKey) => {
            const root = org.agents.find((a) => a.managerId === null);
            store.stampFormation(path, formationKey, root?.id ?? null, { x: 400, y: 140 }, catalog.data!);
          }}
          onAddCustomRole={() => setCustomRoleDialog(true)}
          onAddChildOrg={() => {
            if (org.agents.length === 0) {
              toast("Add an agent first — a child org mounts under one.", "info");
              return;
            }
            setChildDialog(true);
          }}
        />

        <div className="min-w-0 flex-1">
          <OrgCanvas
            org={org}
            catalog={catalog.data}
            issueAgentIds={issueAgentIds}
            issueDepIds={issueDepIds}
            onOpenChild={(childOrgId) => setPath([...path, childOrgId])}
            nodeStatus={nodeStatus}
          />
        </div>

        <Inspector
          org={org}
          catalog={catalog.data}
          issues={currentIssues}
          onFocusIssue={focusIssue}
          onOpenChild={(childOrgId) => setPath([...path, childOrgId])}
        />

        <JsonDrawer doc={doc} open={jsonOpen} onClose={() => setJsonOpen(false)} />
      </div>

      <ChildOrgDialog
        open={childDialog}
        catalog={catalog.data}
        agents={org.agents}
        defaultMountId={
          useSelectionStore.getState().selection.kind === "agent"
            ? (useSelectionStore.getState().selection as { id: string }).id
            : org.agents.find((a) => a.managerId === null)?.id
        }
        onClose={() => setChildDialog(false)}
        onCreate={(mountAgentId, child) => {
          store.mountChildOrg(path, mountAgentId, child);
          setChildDialog(false);
          select({ kind: "childOrg", id: child.id });
        }}
      />

      <CustomRoleForm
        open={customRoleDialog}
        onClose={() => setCustomRoleDialog(false)}
        onCreate={(role) => {
          store.addCustomRole(path, role);
          setCustomRoleDialog(false);
          toast(`Custom role “${role.title}” added.`, "success");
        }}
      />

      <ResetDialog
        open={resetDialog}
        catalog={catalog.data}
        org={org}
        onClose={() => setResetDialog(false)}
        onApply={(agents, deps) => {
          store.replaceChart(path, agents, deps);
          clear();
          setResetDialog(false);
          // Arrange the fresh template in the current direction.
          setTimeout(() => runLayout(direction), 0);
          toast("Chart reset.", "success");
        }}
      />

      <ConflictDialog
        open={status === "conflict"}
        onReloadTheirs={reloadTheirs}
        onOverwriteMine={doOverwrite}
      />
    </div>
  );
}
