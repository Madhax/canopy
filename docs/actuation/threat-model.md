# Actuation Threat Model (v1)

**Status:** v1 — trusted-local · **Purpose:** write down, on one page, exactly what the Phase-2
v1 posture defends against and what it explicitly does **not** (risk AR-6). The design is right for
a single operator on a trusted machine; the risk is *positioning drift* — the first "deploy Canopy
for your team on a VPS" inheriting a single-operator threat model silently. Gate any multi-user or
hosted messaging on the SecretStore roadmap items (keychain / Vault / IAM).

## Posture: single trusted operator, single trusted host

One person runs `pnpm dev` on their own machine (Paperclip's "trusted local" mode, topology.md §5).
Everything binds loopback. There is no auth on the operator API and no multi-tenant isolation.

## What v1 **does** defend against

- **An agent acting as anything other than itself.** Each agent holds a per-node **run token**
  (256-bit, stored only as a SHA-256 hash), minted at provision and revoked at teardown. A leaked
  agent environment leaks a *revocable token*, never a credential.
- **Credentials reaching an agent.** API keys live only in the encrypted Secret Store; plaintext is
  revealed only inside the control-plane process, only by the Model Gateway, at call time
  (invariant 10). No agent env, workspace, or A2A message ever carries a key.
- **Agents talking off-chart.** Every A2A message is mediated by the router, which enforces the
  chart topology; agents never learn peer addresses (invariant 3). *(Enforcement point exists from
  A3; A1 has no inter-agent messaging yet.)*
- **Budget runaway.** The gateway checks the meter before every dispatch and halts before the
  breaching call (invariant 7) — mechanical, not advisory.
- **Secrets at rest.** Fernet (AES-128-CBC + HMAC); the operator API is write-only for secrets
  (create / rotate / delete return metadata only).

## What v1 explicitly does **not** defend against

- **A hostile host user.** `data/master.key` sits beside the DB (0600 where the OS honors it). Any
  process that can read the operator's disk can decrypt the secrets. This is acceptable *only*
  because the host is trusted.
- **Network exposure.** Binds are loopback-only. There is no TLS, no operator authentication, no
  rate limiting for a public interface. Do not port-forward the control plane.
- **Multi-tenant isolation between orgs.** v1 shares one process, one DB, one gateway across all
  actuated orgs (a noisy org degrades its neighbors — risk SC-5). Per-org fairness caps are config,
  not a security boundary.
- **Untrusted agent code / tools.** The subprocess sandbox is *soft* isolation (cwd-jailed by
  convention, no OS enforcement). Executable tool grants (shell, browser) are deliberately withheld
  until hard sandboxes (docker/microVM) land — `write_file` + shell in soft isolation would break
  the model.

## Preconditions to relax before hosting

Do **not** publish "run Canopy for your team" messaging until, at minimum: secrets move off
plaintext-on-disk (keychain / Vault / IAM); the operator API gains authentication; per-org
isolation is a real boundary; and the sandbox provider is a hard one. Until then the run-token
revocation and loopback binding are the parts that genuinely claim security — keep them tested.
