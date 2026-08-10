// The connector instance panel (builder-connectors-ux.md §2.3): identity, config,
// write-only credentials, the capability mask, scope links, and Verify. Secrets paste
// straight through to the Secret Store — this panel holds references, never values.
import { useEffect, useState } from "react";
import {
  useDeleteInstance,
  useUpdateInstance,
  useVerifyInstance,
  type ConnectorInstance,
  type ConnectorPack,
  type VerifyResult,
} from "../../../api/connectors";
import type { TeamDoc } from "../../../schema/team";
import { Button, useToast } from "../../common";

interface Props {
  teamId: string;
  instance: ConnectorInstance;
  pack: ConnectorPack | undefined;
  team: TeamDoc;
  onClose: () => void;
}

const RISK_TONES: Record<string, string> = {
  read: "bg-surface-2 text-ink-muted",
  write: "bg-warn/15 text-ink",
  execute: "bg-danger/15 text-danger",
  consequential: "bg-danger/15 text-danger",
};

export function ConnectorPanel({ teamId, instance, pack, team, onClose }: Props) {
  const { toast } = useToast();
  const update = useUpdateInstance(teamId);
  const remove = useDeleteInstance(teamId);
  const verify = useVerifyInstance(teamId);

  const [name, setName] = useState(instance.name);
  const [config, setConfig] = useState<Record<string, string>>(instance.config);
  const [secretDrafts, setSecretDrafts] = useState<Record<string, string>>({});
  const [verifyResult, setVerifyResult] = useState<VerifyResult | null>(null);

  // Re-seed the drafts when the selection moves to another instance.
  useEffect(() => {
    setName(instance.name);
    setConfig(instance.config);
    setSecretDrafts({});
    setVerifyResult(null);
  }, [instance.id, instance.name, instance.config]);

  const patch = (p: Parameters<typeof update.mutate>[0]["patch"]) =>
    update.mutate(
      { id: instance.id, patch: p },
      { onError: (e) => toast((e as Error).message, "error") },
    );

  const saveIdentity = () => {
    const secrets = Object.fromEntries(
      Object.entries(secretDrafts).filter(([, v]) => v.trim()),
    );
    patch({ name, config, ...(Object.keys(secrets).length ? { secrets } : {}) });
    setSecretDrafts({});
    toast("Connector saved.", "success");
  };

  const toggleGrant = (key: string) => {
    const has = instance.enabledGrants.includes(key);
    patch({
      enabledGrants: has
        ? instance.enabledGrants.filter((g) => g !== key)
        : [...instance.enabledGrants, key],
    });
  };

  const orgWide = instance.nodeLinks === null;

  return (
    <aside className="flex w-[320px] shrink-0 flex-col overflow-y-auto border-l border-border bg-surface p-4 text-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold text-ink">
          {pack?.title ?? instance.packKey} connector
        </h2>
        <button className="text-xs text-ink-muted hover:text-ink" onClick={onClose}>
          ✕
        </button>
      </div>

      {/* Identity */}
      <label className="mb-1 text-xs text-ink-muted">Name</label>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="mb-2 rounded-md border border-border bg-canvas px-2 py-1.5 text-sm outline-none focus:border-accent"
      />
      <label className="mb-2 flex items-center gap-2 text-xs text-ink">
        <input
          type="checkbox"
          checked={instance.enabled}
          onChange={(e) => patch({ enabled: e.target.checked })}
        />
        Enabled
        <span className="text-ink-subtle">— off fails every call closed, immediately</span>
      </label>

      {/* Configuration */}
      <h3 className="mb-1 mt-3 text-xs font-semibold uppercase tracking-wide text-ink-muted">
        Configuration
      </h3>
      {Object.entries(pack?.configSchema ?? {}).map(([field, decl]) => (
        <div key={field} className="mb-2">
          <label className="mb-0.5 flex items-center gap-1.5 text-xs text-ink-muted">
            {field}
            {decl.required && <span className="text-danger">*</span>}
            <span className="text-[10px] text-ink-subtle">
              {decl.narrowable ? "roles/nodes may tighten" : "fixed at instance"}
            </span>
          </label>
          <input
            value={config[field] ?? decl.default ?? ""}
            onChange={(e) => setConfig({ ...config, [field]: e.target.value })}
            className="w-full rounded-md border border-border bg-canvas px-2 py-1 text-sm outline-none focus:border-accent"
          />
        </div>
      ))}

      {/* Credentials — write-only */}
      {(pack?.secrets ?? []).length > 0 && (
        <>
          <h3 className="mb-1 mt-3 text-xs font-semibold uppercase tracking-wide text-ink-muted">
            Credentials
          </h3>
          {(pack?.secrets ?? []).map((s) => {
            const bound = !!instance.secretBindings[s.credentialKind];
            return (
              <div key={s.credentialKind} className="mb-2">
                <label className="mb-0.5 flex items-center gap-2 text-xs text-ink-muted">
                  {s.credentialKind}
                  <span
                    className={`rounded-full px-1.5 text-[10px] ${
                      bound ? "bg-ok/15 text-ok" : "bg-danger/15 text-danger"
                    }`}
                  >
                    {bound ? "bound" : "unbound"}
                  </span>
                </label>
                <input
                  type="password"
                  placeholder="paste token — stored encrypted, never shown again"
                  value={secretDrafts[s.credentialKind] ?? ""}
                  onChange={(e) =>
                    setSecretDrafts({ ...secretDrafts, [s.credentialKind]: e.target.value })
                  }
                  className="w-full rounded-md border border-border bg-canvas px-2 py-1 text-sm outline-none focus:border-accent"
                />
                {s.scopesHint.length > 0 && (
                  <p className="mt-0.5 text-[10px] text-ink-subtle">
                    token needs: {s.scopesHint.join(", ")}
                  </p>
                )}
              </div>
            );
          })}
        </>
      )}

      {/* Capabilities — the team-level mask */}
      <h3 className="mb-1 mt-3 text-xs font-semibold uppercase tracking-wide text-ink-muted">
        Capabilities
      </h3>
      {(pack?.grants ?? []).map((g) => (
        <label key={g.key} className="mb-1.5 flex items-start gap-2 text-xs">
          <input
            type="checkbox"
            checked={instance.enabledGrants.includes(g.key)}
            onChange={() => toggleGrant(g.key)}
            className="mt-0.5"
          />
          <span className="min-w-0">
            <span className="flex items-center gap-1.5">
              <span className="text-ink">{g.title}</span>
              <span className={`rounded-full px-1.5 text-[10px] ${RISK_TONES[g.riskClass] ?? ""}`}>
                {g.riskClass}
              </span>
              {g.governedActions.length > 0 && (
                <span title="every call opens an approval gate you resolve">🔒</span>
              )}
            </span>
            {g.provides.length > 0 && (
              <span className="text-[10px] text-ink-subtle">serves: {g.provides.join(", ")}</span>
            )}
          </span>
        </label>
      ))}

      {/* Scope */}
      <h3 className="mb-1 mt-3 text-xs font-semibold uppercase tracking-wide text-ink-muted">
        Scope
      </h3>
      <label className="mb-1 flex items-center gap-2 text-xs text-ink">
        <input
          type="radio"
          checked={orgWide}
          onChange={() => patch({ linkScope: "team" })}
        />
        Org-wide — every node this team runs can reach it
      </label>
      <label className="mb-1 flex items-center gap-2 text-xs text-ink">
        <input
          type="radio"
          checked={!orgWide}
          onChange={() => patch({ linkScope: "nodes", nodeLinks: instance.nodeLinks ?? [] })}
        />
        Specific nodes only
      </label>
      {!orgWide && (
        <div className="mb-2 ml-5">
          {team.agents.map((a) => (
            <label key={a.id} className="flex items-center gap-2 text-xs text-ink-muted">
              <input
                type="checkbox"
                checked={(instance.nodeLinks ?? []).includes(a.id)}
                onChange={(e) => {
                  const links = new Set(instance.nodeLinks ?? []);
                  if (e.target.checked) links.add(a.id);
                  else links.delete(a.id);
                  patch({ linkScope: "nodes", nodeLinks: [...links] });
                }}
              />
              {a.name || a.role.key}
            </label>
          ))}
          <p className="mt-1 text-[10px] text-ink-subtle">
            Tip: drag from the pill’s handle to a node on the canvas — same thing.
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="primary" onClick={saveIdentity} disabled={update.isPending}>
          Save
        </Button>
        <Button
          variant="secondary"
          onClick={() =>
            verify.mutate(instance.id, {
              onSuccess: setVerifyResult,
              onError: (e) => toast((e as Error).message, "error"),
            })
          }
          disabled={verify.isPending}
        >
          {verify.isPending ? "Verifying…" : "Verify"}
        </Button>
        <Button
          variant="danger"
          onClick={() => {
            remove.mutate(instance.id, {
              onSuccess: onClose,
              onError: (e) => toast((e as Error).message, "error"),
            });
          }}
        >
          Delete
        </Button>
      </div>
      {verifyResult && (
        <div className="mt-2 rounded-md border border-border bg-canvas p-2">
          <p className={`text-xs font-medium ${verifyResult.ok ? "text-ok" : "text-danger"}`}>
            {verifyResult.ok ? "✓ verified" : "✗ verification failed"}
          </p>
          {verifyResult.checks.map((c) => (
            <p key={c.name} className="text-[11px] text-ink-muted">
              {c.ok ? "✓" : "✗"} {c.name}
              {c.detail && ` — ${c.detail}`}
            </p>
          ))}
        </div>
      )}
    </aside>
  );
}
