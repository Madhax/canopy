# Contract fixtures (risk AR-2)

Phase 2 multiplies the surface that exists in ≥2 languages: the charter, tool schemas, envelope
shapes, profiles, and gateway wire types all live in the control plane (pydantic) *and* the UI
(Zod) — and, later, the agent runtime. Each is small; the sum is a drift field where a renamed
field breaks agents at runtime instead of at build time.

These fixtures are the antidote, and they reuse the exact trick Phase 1 used for its two
validators: **one canned instance per contract, parsed identically by every side.**

- `server/tests/test_contracts.py` validates each file with its pydantic model.
- `ui/src/schema/actuation.contract.test.ts` parses each file with its Zod schema.

If a field is renamed or retyped on one side only, one of those suites fails. Add a fixture when
you add a contract; keep field names identical across pydantic and Zod.

| Fixture | pydantic model | Zod schema |
|---|---|---|
| `agent_profile.json` | `profiles.AgentProfile` | `agentProfileSchema` |
| `agent_binding.json` | `profiles.AgentBinding` | `agentBindingSchema` |
| `secret_meta.json` | `secretstore.SecretMeta` | `secretMetaSchema` |
| `completion_request.json` | `gateway.base.CompletionRequest` | `completionRequestSchema` |
| `completion_result.json` | `gateway.base.CompletionResult` | `completionResultSchema` |
