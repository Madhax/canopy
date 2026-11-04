// Node-inspector control: which Agent Profile powers this node (agent-profile.md §3).
// Profiles/bindings live in the control plane, not the Team document — so this reads and
// writes them via the API, keyed by the TOP-LEVEL team id + this node's drill-in path (teamPath).
// A node with no binding of its own inherits the team-default profile (UX-35).
import { useState } from "react";
import {
  useBindingMutations,
  useBindings,
  useProfiles,
  useTeamDefaultProfile,
  validateProfile,
} from "../../../api/actuation";
import type { ValidationResult } from "../../../schema/actuation";
import { modelInvalid, resolveNodeModel } from "../../../lib/nodeModel";
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
  const teamDefault = useTeamDefaultProfile(teamId);
  const { set, remove } = useBindingMutations(teamId);
  const [check, setCheck] = useState<ValidationResult | null>(null);
  const [checking, setChecking] = useState(false);

  const current = bindings.data?.find(
    (b) => b.agentNodeId === agentNodeId && samePath(b.teamPath, teamPath),
  );
  const list = profiles.data ?? [];
  const loaded = !!profiles.data && !!bindings.data && !!teamDefault.data;
  const defaultId = teamDefault.data?.profileId ?? null;
  const defaultProfile = list.find((p) => p.id === defaultId);
  const info = loaded
    ? resolveNodeModel(agentNodeId, teamPath, bindings.data!, list, defaultId)
    : undefined;
  const invalid = modelInvalid(info);
  const danglingId = info?.source === "dangling" ? current?.profileId : undefined;

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
    if (!info?.profile) return;
    setChecking(true);
    try {
      setCheck(await validateProfile(teamId, info.profile.id));
    } catch (e) {
      setCheck({ ok: false, error: e instanceof Error ? e.message : "check failed" });
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <span
        className={`flex items-center justify-between text-xs font-semibold uppercase tracking-wide ${
          invalid ? "text-danger" : "text-ink-muted"
        }`}
      >
        Agent profile
        {info?.profile ? (
          <span className="font-mono font-normal normal-case text-ink-muted">
            {info.profile.provider} · {info.profile.model}
          </span>
        ) : invalid ? (
          <span className="font-mono font-normal normal-case text-danger">
            {info?.source === "dangling" ? "profile missing" : "unspecified"}
          </span>
        ) : null}
      </span>
      {loaded && list.length === 0 ? (
        <p className="rounded-md border border-danger bg-danger/5 px-2 py-1.5 text-xs text-danger">
          No profiles yet, so no model feeds this node. Add one in Team settings (deselect this
          node) and make it the team default.
        </p>
      ) : (
        <>
          <select
            value={danglingId ?? current?.profileId ?? ""}
            onChange={(e) => onSelect(e.target.value)}
            aria-invalid={invalid || undefined}
            className={`rounded-md border bg-canvas px-2 py-1.5 text-sm outline-none ${
              invalid
                ? "border-danger text-danger ring-1 ring-danger/40 focus:border-danger"
                : "border-border focus:border-accent"
            }`}
          >
            <option value="">
              {defaultProfile
                ? `Team default — ${defaultProfile.name} · ${defaultProfile.provider}/${defaultProfile.model}`
                : "— unspecified (no team default) —"}
            </option>
            {danglingId && <option value={danglingId}>⚠ missing profile ({danglingId})</option>}
            {list.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · {p.provider}/{p.model}
              </option>
            ))}
          </select>
          {info && (
            <span className={`text-xs ${invalid ? "font-medium text-danger" : "text-ink-muted"}`}>
              {info.source === "node" && "Set on this node — overrides the team default."}
              {info.source === "team-default" && "Inherited from the team default profile."}
              {info.source === "unspecified" &&
                "⚠ No model specified — pick a profile here, or set a team default in Team settings."}
              {info.source === "dangling" &&
                "⚠ This node's profile was deleted — pick another, or fall back to the team default."}
            </span>
          )}
          {info?.profile && (
            <div className="mt-1 flex items-center gap-2">
              <Button variant="ghost" onClick={runValidate}>
                {checking ? "Checking…" : "Validate"}
              </Button>
              {current && sameRoleNodeIds.length > 1 && (
                <Button variant="ghost" onClick={applyToRole}>
                  Apply to all {sameRoleNodeIds.length} with this role
                </Button>
              )}
            </div>
          )}
          {check && (
            <span className={`text-xs ${check.ok ? "text-ok" : "text-danger"}`}>
              {check.ok ? "✓ profile reachable" : `⚠ ${check.error ?? "unreachable"}`}
            </span>
          )}
        </>
      )}
    </div>
  );
}
