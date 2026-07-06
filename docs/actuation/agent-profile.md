# Agent Profiles — AI Configuration per Node

An **Agent Profile** is the answer to "which brain does this node get": provider, model, endpoint, key, parameters. Profiles are deployment configuration, deliberately kept **out of the Organization document** — the chart stays portable structure (roles, salaries, wiring) while profiles carry machine-local, secret-adjacent detail. This honors the phase-1 spec's rule that the document carries no model/adapter/cost fields (`../org-chart-editor.md` §10): bindings live in the control plane as their own records. (Rationale: exporting a chart must never drag provider config or secret refs with it; the same chart actuates with different profiles on different machines.)

## 1. Data model

```jsonc
// AgentProfile — reusable, org-scoped config; many nodes may share one profile
{
  "id": "ap_9f2k1x7c",
  "organizationId": "6b9f2c1e-...",        // profiles are org-scoped in v1
  "name": "Sonnet — default engineer",
  "provider": "anthropic",                  // "anthropic" | "gemini"  (v1 closed enum)
  "model": "claude-sonnet-4-5",             // provider-native model id, free string
  "endpoint": null,                         // base-URL override (proxies, regional endpoints); null = provider default
  "apiKeySecretId": "sec_k2m8p1qz",         // reference into the Secret Store — NEVER the key itself
  "params": {                               // provider-agnostic core + passthrough
    "maxOutputTokens": 8192,
    "temperature": 0.7,
    "providerOptions": {}                   // passthrough object, provider-specific (e.g. thinking budget)
  },
  "systemPreamble": "",                     // optional operator text prepended to every system prompt
  "createdAt": "...", "updatedAt": "..."
}

// AgentBinding — attaches a profile to a chart node
{
  "organizationId": "6b9f2c1e-...",
  "agentNodeId": "a_k7mp2x9q",              // agent id in the Organization document (nested orgs:
                                             // node ids are unique per document; binding also stores
                                             // "orgPath": [] to disambiguate nested duplicates)
  "orgPath": [],
  "profileId": "ap_9f2k1x7c"
}
```

Secrets: the Secret Store holds `{ id, organizationId, name, ciphertext, createdAt }`, encrypted at rest (Fernet/AES-GCM; master key in `data/master.key`, 0600, generated on first run — documented as "protect this file"). Plaintext is retrievable **only** by the Model Gateway inside the control-plane process; no API returns it (write-only from the UI: create, rotate, delete; reads return metadata only). Paperclip's agent-secret-bindings is the pattern reference.

## 2. Provider adapters (v1: Claude + Gemini)

Adapters live in the **Model Gateway** (`control-plane.md`), not in agents. Interface:

```python
class ModelProvider(ABC):
    key: str                                     # "anthropic" | "gemini"
    async def complete(self, req: CompletionRequest, cred: str) -> CompletionResult: ...
    async def validate(self, profile: AgentProfile, cred: str) -> ValidationResult: ...  # cheap ping
    def list_known_models(self) -> list[ModelInfo]: ...                                  # static hints for UI

# CompletionRequest: system, messages[{role, content}], tools?[], maxOutputTokens, temperature, providerOptions
# CompletionResult:  text, toolCalls?, inputTokens, outputTokens, stopReason, providerRaw (truncated, for debugging)
```

- **anthropic** — official `anthropic` Python SDK; Messages API; `endpoint` → `base_url`.
- **gemini** — official `google-genai` Python SDK; `generateContent`; `endpoint` → API endpoint override.

Both normalize to the same `CompletionRequest/Result` shapes — the agent runtime is provider-blind. Token counts come from provider usage metadata (authoritative for SpendEvents). Adding a provider later = one adapter class + registry entry (`roadmap.md`).

## 3. Actuation readiness rules

An organization may actuate only when, for every agent node at every nesting level:

1. A binding exists → resolves to an existing profile → whose secret exists. (`BINDING_MISSING`, `PROFILE_DANGLING`, `SECRET_DANGLING` — actuation-time errors, same ValidationIssue shape as phase 1.)
2. The profile passes `validate()` — one cheap live call per distinct (provider, secretId, endpoint) tuple at actuate time, surfaced as `PROFILE_UNREACHABLE` warnings with the provider's error text.

The editor gains a **Profiles** section (org settings) for CRUD + key entry, and a **Binding picker** in the node inspector (with an "apply to all nodes with this role" bulk action — the common case is one profile for many nodes). Chart export remains profile-free; a separate *bindings export* (profiles + bindings, secrets **excluded**, secret names only) exists for migrating machines.

## 4. What the agent runtime sees

None of the above. At boot an agent receives: its identity, org id, role instructions (compiled from RoleTemplate + extensions), its manager/report ids, the control-plane URL, and its run token. When it wants to think, it POSTs to the gateway; the gateway looks up the binding server-side. An agent cannot name a model, a provider, or a key — so a compromised or confused agent cannot exfiltrate credentials or bypass its configuration. Profile changes while actuated take effect on the next gateway call (no agent restart needed).
