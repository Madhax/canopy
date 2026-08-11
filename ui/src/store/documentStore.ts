// The single source of truth: ONE top-level Team document, with undo/redo (docs §7.5).
// All mutations are named actions; each operates on the team at a given drill-in `path`.
import { create } from "zustand";
import { temporal } from "zundo";
import type { Catalog } from "../schema/catalog";
import type {
  Agent,
  CustomRole,
  Dependency,
  TeamDoc,
  Salary,
} from "../schema/team";
import { newAgentId, newDependencyId } from "../lib/ids";
import { buildFormationSubtree } from "../lib/formation";
import { getOrgAtPath, updateOrgAtPath } from "./orgTree";

function agentFromRole(
  catalog: Catalog,
  roleKey: string,
  managerId: string | null,
  position: { x: number; y: number },
): Agent {
  const role = catalog.roles.find((r) => r.key === roleKey);
  const salary: Salary = role
    ? { ...role.defaultSalary }
    : { perAssignmentAllowance: 120000, warnThresholdPct: 80, hardStop: true };
  return {
    id: newAgentId(),
    name: role?.title ?? roleKey,
    role: { key: roleKey, version: role?.version ?? 1 },
    managerId,
    extensions: { instructions: "", responsibilities: [] },
    salary,
    position,
  };
}

export interface DocStore {
  doc: TeamDoc | null;

  load: (doc: TeamDoc) => void;
  renameOrg: (path: string[], name: string) => void;
  setUpdatedAt: (ts: string | null) => void;

  placeAgent: (
    path: string[],
    roleKey: string,
    position: { x: number; y: number },
    catalog: Catalog,
  ) => string;
  placeAgentNode: (path: string[], agent: Agent) => void;
  reparentAgent: (path: string[], agentId: string, managerId: string | null) => void;
  moveAgent: (path: string[], agentId: string, position: { x: number; y: number }) => void;
  renameAgent: (path: string[], agentId: string, name: string) => void;
  reassignRole: (path: string[], agentId: string, roleKey: string, version: number) => void;
  updateSalary: (path: string[], agentId: string, salary: Salary) => void;
  updateInstructions: (path: string[], agentId: string, instructions: string) => void;
  setAddedResponsibilities: (
    path: string[],
    agentId: string,
    responsibilities: Agent["extensions"]["responsibilities"],
  ) => void;
  deleteAgent: (path: string[], agentId: string) => void;

  addDependency: (path: string[], from: string, to: string, note?: string) => void;
  updateDependencyNote: (path: string[], depId: string, note: string) => void;
  setDependencyResolveOn: (path: string[], depId: string, resolveOn: Dependency["resolveOn"]) => void;
  removeDependency: (path: string[], depId: string) => void;

  stampFormation: (
    path: string[],
    formationKey: string,
    mountAgentId: string | null,
    origin: { x: number; y: number },
    catalog: Catalog,
  ) => void;

  mountChildTeam: (path: string[], mountAgentId: string, child: TeamDoc) => void;
  addCustomRole: (path: string[], role: CustomRole) => void;
  replaceChart: (path: string[], agents: Agent[], dependencies: Dependency[]) => void;

  applyBatch: (path: string[], mutate: (team: TeamDoc) => void) => void;
}

function patchAgent(
  set: (fn: (s: DocStore) => Partial<DocStore>) => void,
  path: string[],
  agentId: string,
  fn: (a: Agent) => void,
) {
  set((s) => {
    if (!s.doc) return {};
    return {
      doc: updateOrgAtPath(s.doc, path, (team) => {
        const a = team.agents.find((x) => x.id === agentId);
        if (a) fn(a);
      }),
    };
  });
}

export const useDocumentStore = create<DocStore>()(
  temporal(
    (set, get) => ({
      doc: null,

      load: (doc) => set({ doc }),

      renameOrg: (path, name) =>
        set((s) => (s.doc ? { doc: updateOrgAtPath(s.doc, path, (o) => void (o.name = name)) } : {})),

      setUpdatedAt: (ts) => set((s) => (s.doc ? { doc: { ...s.doc, updatedAt: ts } } : {})),

      placeAgent: (path, roleKey, position, catalog) => {
        const team = get().doc ? getOrgAtPath(get().doc!, path) : null;
        const hasRoot = !!team?.agents.some((a) => a.managerId === null);
        const agent = agentFromRole(catalog, roleKey, null, position);
        // First agent in a rootless chart becomes the root; otherwise it's unparented until wired.
        void hasRoot;
        set((s) =>
          s.doc ? { doc: updateOrgAtPath(s.doc, path, (o) => void o.agents.push(agent)) } : {},
        );
        return agent.id;
      },

      placeAgentNode: (path, agent) =>
        set((s) =>
          s.doc ? { doc: updateOrgAtPath(s.doc, path, (o) => void o.agents.push(agent)) } : {},
        ),

      reparentAgent: (path, agentId, managerId) =>
        patchAgent(set, path, agentId, (a) => void (a.managerId = managerId)),

      moveAgent: (path, agentId, position) =>
        patchAgent(set, path, agentId, (a) => void (a.position = position)),

      renameAgent: (path, agentId, name) =>
        patchAgent(set, path, agentId, (a) => void (a.name = name)),

      reassignRole: (path, agentId, roleKey, version) =>
        patchAgent(set, path, agentId, (a) => void (a.role = { key: roleKey, version })),

      updateSalary: (path, agentId, salary) =>
        patchAgent(set, path, agentId, (a) => void (a.salary = salary)),

      updateInstructions: (path, agentId, instructions) =>
        patchAgent(set, path, agentId, (a) => void (a.extensions.instructions = instructions)),

      setAddedResponsibilities: (path, agentId, responsibilities) =>
        patchAgent(set, path, agentId, (a) => void (a.extensions.responsibilities = responsibilities)),

      deleteAgent: (path, agentId) =>
        set((s) => {
          if (!s.doc) return {};
          return {
            doc: updateOrgAtPath(s.doc, path, (team) => {
              team.agents = team.agents.filter((a) => a.id !== agentId);
              // Orphan the reports (they lose their manager) rather than cascade-deleting.
              for (const a of team.agents) if (a.managerId === agentId) a.managerId = null;
              // Drop dependencies and child mounts referencing the removed agent.
              team.dependencies = team.dependencies.filter(
                (d) => d.from !== agentId && d.to !== agentId,
              );
            }),
          };
        }),

      addDependency: (path, from, to, note) =>
        set((s) => {
          if (!s.doc) return {};
          const dep: Dependency = {
            id: newDependencyId(),
            from,
            to,
            resolveOn: "accepted",
            note: note ?? null,
          };
          return { doc: updateOrgAtPath(s.doc, path, (o) => void o.dependencies.push(dep)) };
        }),

      updateDependencyNote: (path, depId, note) =>
        set((s) =>
          s.doc
            ? {
                doc: updateOrgAtPath(s.doc, path, (o) => {
                  const d = o.dependencies.find((x) => x.id === depId);
                  if (d) d.note = note;
                }),
              }
            : {},
        ),

      setDependencyResolveOn: (path, depId, resolveOn) =>
        set((s) =>
          s.doc
            ? {
                doc: updateOrgAtPath(s.doc, path, (o) => {
                  const d = o.dependencies.find((x) => x.id === depId);
                  if (d) d.resolveOn = resolveOn;
                }),
              }
            : {},
        ),

      removeDependency: (path, depId) =>
        set((s) =>
          s.doc
            ? {
                doc: updateOrgAtPath(
                  s.doc,
                  path,
                  (o) => void (o.dependencies = o.dependencies.filter((d) => d.id !== depId)),
                ),
              }
            : {},
        ),

      stampFormation: (path, formationKey, mountAgentId, origin, catalog) =>
        set((s) => {
          if (!s.doc) return {};
          const { agents, dependencies } = buildFormationSubtree(
            catalog,
            formationKey,
            mountAgentId,
            origin,
          );
          if (agents.length === 0) return {};
          // Drop-on-empty-rootless: the formation manager becomes the root (mountAgentId null).
          // Drop-on-agent: the manager reports to that agent. One undo unit (single set).
          return {
            doc: updateOrgAtPath(s.doc, path, (team) => {
              team.agents.push(...agents);
              team.dependencies.push(...dependencies);
            }),
          };
        }),

      mountChildTeam: (path, mountAgentId, child) =>
        set((s) =>
          s.doc
            ? {
                doc: updateOrgAtPath(
                  s.doc,
                  path,
                  (o) => void o.childTeams.push({ mountAgentId, team: child }),
                ),
              }
            : {},
        ),

      addCustomRole: (path, role) =>
        set((s) =>
          s.doc
            ? {
                doc: updateOrgAtPath(s.doc, path, (o) => {
                  const existing = o.customRoles.findIndex((r) => r.key === role.key);
                  if (existing >= 0) o.customRoles[existing] = role;
                  else o.customRoles.push(role);
                }),
              }
            : {},
        ),

      replaceChart: (path, agents, dependencies) =>
        set((s) =>
          s.doc
            ? {
                doc: updateOrgAtPath(s.doc, path, (o) => {
                  // Reset the chart to a template: swap agents + dependencies, drop child teams.
                  // Custom role definitions are kept (they're reusable, document-local).
                  o.agents = agents;
                  o.dependencies = dependencies;
                  o.childTeams = [];
                }),
              }
            : {},
        ),

      applyBatch: (path, mutate) =>
        set((s) => (s.doc ? { doc: updateOrgAtPath(s.doc, path, mutate) } : {})),
    }),
    {
      // Only the document is time-travelled; equality avoids no-op history entries.
      partialize: (state) => ({ doc: state.doc }),
      equality: (a, b) => a.doc === b.doc,
      limit: 100,
    },
  ),
);

/** Access the zundo temporal control store (undo/redo/pause). */
export const useTemporalStore = useDocumentStore.temporal;

// --------------------------------------------------------------------------- //
// Safe undo/redo — the concurrency token is not part of edit history.
//
// Incident (2026-08-10): undo restored a pre-save snapshot INCLUDING its stale
// `updatedAt`; the next autosave then 409'd into the conflict dialog, whose every
// option loses one side. The token names which server version this client last saw —
// undoing your edits never changes that fact, so undo/redo re-applies the last
// server-issued token after time-travelling the content.
// --------------------------------------------------------------------------- //
let lastServerUpdatedAt: string | null | undefined;

/** Record the server-issued updatedAt (on load, after every save, after conflict). */
export function noteServerUpdatedAt(ts: string | null | undefined): void {
  lastServerUpdatedAt = ts ?? null;
}

function reapplyServerToken(): void {
  if (lastServerUpdatedAt === undefined) return;
  const t = useTemporalStore.getState();
  t.pause();
  useDocumentStore.getState().setUpdatedAt(lastServerUpdatedAt);
  t.resume();
}

export function safeUndo(): void {
  useTemporalStore.getState().undo();
  reapplyServerToken();
}

export function safeRedo(): void {
  useTemporalStore.getState().redo();
  reapplyServerToken();
}
