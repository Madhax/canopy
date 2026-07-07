// Org-settings section: manage Agent Profiles and Secrets (control-plane.md §10).
// These are control-plane records, kept OUT of the Organization document (agent-profile.md) — the
// chart stays portable structure; this panel carries the machine-local, secret-adjacent config.
import { useState } from "react";
import {
  useProfileMutations,
  useProfiles,
  useSecretMutations,
  useSecrets,
} from "../../../api/actuation";
import type { Provider } from "../../../schema/actuation";
import { Button } from "../../common";

const KNOWN_MODELS: Record<Provider, string[]> = {
  anthropic: ["claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5"],
  gemini: ["gemini-2.5-pro", "gemini-2.5-flash"],
  mock: ["mock-1"],
};

export function ProfilesSecretsPanel({ orgId }: { orgId: string }) {
  const profiles = useProfiles(orgId);
  const secrets = useSecrets(orgId);
  const profileM = useProfileMutations(orgId);
  const secretM = useSecretMutations(orgId);

  const [name, setName] = useState("");
  const [provider, setProvider] = useState<Provider>("mock");
  const [model, setModel] = useState("mock-1");
  const [secretId, setSecretId] = useState<string>("");

  const [secretName, setSecretName] = useState("");
  const [secretValue, setSecretValue] = useState("");

  const addProfile = () => {
    if (!name.trim() || !model.trim()) return;
    profileM.create.mutate(
      {
        name: name.trim(),
        provider,
        model: model.trim(),
        apiKeySecretId: provider === "mock" || !secretId ? null : secretId,
      },
      {
        onSuccess: () => {
          setName("");
          setSecretId("");
        },
      },
    );
  };

  const addSecret = () => {
    if (!secretName.trim() || !secretValue) return;
    secretM.create.mutate(
      { name: secretName.trim(), value: secretValue },
      { onSuccess: () => { setSecretName(""); setSecretValue(""); } },
    );
  };

  const inputCls =
    "rounded-md border border-border bg-canvas px-2 py-1.5 text-sm outline-none focus:border-accent";

  return (
    <div className="flex flex-col gap-4 border-t border-border pt-4">
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
          Profiles &amp; Secrets
        </h3>
        <p className="mt-1 text-xs text-ink-muted">
          Which model powers each node. Kept out of the exported chart; keys are encrypted at rest.
        </p>
      </div>

      {/* Profiles */}
      <div className="flex flex-col gap-2">
        {(profiles.data ?? []).map((p) => (
          <div
            key={p.id}
            className="flex items-center justify-between rounded-md border border-border bg-canvas px-2 py-1.5"
          >
            <div className="min-w-0">
              <div className="truncate text-sm">{p.name}</div>
              <div className="text-xs text-ink-muted">
                {p.provider} · {p.model}
              </div>
            </div>
            <button
              onClick={() => profileM.remove.mutate(p.id)}
              className="text-xs text-ink-muted hover:text-danger"
              aria-label={`Delete profile ${p.name}`}
            >
              ✕
            </button>
          </div>
        ))}
        {profiles.data?.length === 0 && (
          <p className="text-xs text-ink-muted">No profiles yet.</p>
        )}
      </div>

      <div className="flex flex-col gap-2 rounded-md border border-dashed border-border p-2">
        <span className="text-xs font-semibold text-ink-muted">New profile</span>
        <input
          className={inputCls}
          placeholder="Name (e.g. Sonnet — default)"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <div className="flex gap-2">
          <select
            className={inputCls}
            value={provider}
            onChange={(e) => {
              const p = e.target.value as Provider;
              setProvider(p);
              setModel(KNOWN_MODELS[p][0]);
            }}
          >
            <option value="mock">mock</option>
            <option value="anthropic">anthropic</option>
            <option value="gemini">gemini</option>
          </select>
          <input
            className={`${inputCls} flex-1`}
            placeholder="model id"
            value={model}
            list="canopy-known-models"
            onChange={(e) => setModel(e.target.value)}
          />
          <datalist id="canopy-known-models">
            {KNOWN_MODELS[provider].map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </div>
        {provider !== "mock" && (
          <select className={inputCls} value={secretId} onChange={(e) => setSecretId(e.target.value)}>
            <option value="">— API key secret —</option>
            {(secrets.data ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        )}
        <Button onClick={addProfile} disabled={profileM.create.isPending}>
          Add profile
        </Button>
      </div>

      {/* Secrets */}
      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold text-ink-muted">Secrets (write-only)</span>
        {(secrets.data ?? []).map((s) => (
          <div
            key={s.id}
            className="flex items-center justify-between rounded-md border border-border bg-canvas px-2 py-1.5"
          >
            <span className="truncate text-sm">{s.name}</span>
            <button
              onClick={() => secretM.remove.mutate(s.id)}
              className="text-xs text-ink-muted hover:text-danger"
              aria-label={`Delete secret ${s.name}`}
            >
              ✕
            </button>
          </div>
        ))}
        <div className="flex flex-col gap-2 rounded-md border border-dashed border-border p-2">
          <input
            className={inputCls}
            placeholder="Secret name (e.g. anthropic-key)"
            value={secretName}
            onChange={(e) => setSecretName(e.target.value)}
          />
          <input
            className={inputCls}
            type="password"
            placeholder="Paste API key (stored encrypted, never shown again)"
            value={secretValue}
            onChange={(e) => setSecretValue(e.target.value)}
          />
          <Button onClick={addSecret} disabled={secretM.create.isPending}>
            Add secret
          </Button>
        </div>
      </div>
    </div>
  );
}
