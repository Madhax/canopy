// Node-inspector control: which Agent Profile powers this node (agent-profile.md §3).
// Profiles/bindings live in the control plane, not the Team document — so this reads and
// writes them via the API, keyed by the TOP-LEVEL team id + this node's drill-in path (teamPath).
import { useState } from "react";
import { useBindingMutations, useBindings, useProfiles, validateProfile } from "../../../api/actuation";
import type { ValidationResult } from "../../../schema/actuation";
import { Button } from "../../common";

interface Props {
  teamId: string;
  agentNodeId: string;
  teamPath: string[];
  sameRoleNodeIds: string[];
}

function samePath(a: string[], b: string[]) {
  return a.length === b.length && a.every((x, i) => x === b[i]);
}

export function BindingPicker({ teamId, agentNodeId, teamPath, sameRoleNodeIds }: Props) {
  const profiles = useProfiles(teamId);
  const bindings = useBindings(teamId);
  const { set, remove } = useBindingMutations(teamId);
  const [check, setCheck] = useState<ValidationResult | null>(null);
  const [checking, setChecking] = useState(false);

  const current = bindings.data?.find(
    (b) => b.agentNodeId === agentNodeId && samePath(b.teamPath, teamPath),
  );
  const list = profiles.data ?? [];

  const onSelect = (profileId: string) => {
    setCheck(null);
    if (profileId === "") remove.mutate({ agentNodeId, teamPath });
    else set.mutate({ agentNodeId, profileId, teamPath });
  };

  const applyToRole = () => {
    if (!current) return;
    for (const node of sameRoleNodeIds) {
      set.mutate({ agentNodeId: node, profileId: current.profileId, teamPath });
    }
  };

  const runValidate = async () => {
    if (!current) return;
    setChecking(true);
    try {
      setCheck(await validateProfile(teamId, current.profileId));
    } catch (e) {
      setCheck({ ok: false, error: e instanceof Error ? e.message : "check failed" });
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
        Agent profile
      </span>
      {list.length === 0 ? (
        <p className="text-xs text-ink-muted">
          No profiles yet. Add one in Team settings (deselect this node) to choose which
          model powers it.
        </p>
      ) : (
        <>
          <select
            value={current?.profileId ?? ""}
            onChange={(e) => onSelect(e.target.value)}
            className="rounded-md border border-border bg-canvas px-2 py-1.5 text-sm outline-none focus:border-accent"
          >
            <option value="">— unassigned —</option>
            {list.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · {p.provider}/{p.model}
              </option>
            ))}
          </select>
          {current && (
            <div className="mt-1 flex items-center gap-2">
              <Button variant="ghost" onClick={runValidate}>
                {checking ? "Checking…" : "Validate"}
              </Button>
              {sameRoleNodeIds.length > 1 && (
                <Button variant="ghost" onClick={applyToRole}>
                  Apply to all {sameRoleNodeIds.length} with this role
                </Button>
              )}
            </div>
          )}
          {check && (
            <span className={`text-xs ${check.ok ? "text-ok" : "text-warn"}`}>
              {check.ok ? "✓ profile reachable" : `⚠ ${check.error ?? "unreachable"}`}
            </span>
          )}
        </>
      )}
    </div>
  );
}
