# 03 · Continuity — keeping the platform itself alive

> **Status:** Proposed 2026-08-16 · **Reads with:** `README.md`, `../../actuation/control-plane.md`, `../../execution/cli-runtime.md` §8 (the credential posture), `../organizations/03-provider-quota-adapters.md` (error classification this extends), `../../testing.md` §6 (the live path this joins)

## 0. The problem

E6 proved the *engine* survives a crash; nothing ensures the crash is noticed, the process restarted, the database backed up, or the login still valid at 3am. The corpus's operational posture is a dev loop (`pnpm dev`, launch.json) — correct for building, disqualifying for leaving. Continuity is four small designs and one runbook, specified and tested like features, because at 3am they are the product.

## 1. Service supervision

**CN-1** The control plane runs under a supervisor with restart-on-failure and start-on-boot, serving the built UI on one port (the existing production posture). Deliverables: `scripts/service/` with a Windows service wrapper (`install-service.ps1`, NSSM or Task Scheduler equivalent) and a `systemd` unit example; both poll **`/healthz`** (exists) with a failure threshold before restart. **CN-2** Restart-loop detection: ≥3 restarts in 10 minutes → supervisor stops retrying and fires `supervisor-restart-loop` through the page channel — a crash-looping control plane must not silently burn the night. **CN-3** Every supervised restart lands an activity row on next boot ("recovered at …, downtime …s"), so the brief's anomaly section reports downtime the operator never saw. The agent adapters need no supervisor of their own — the actuator's reconciler already restarts dead adapters; supervision of the reconciler's host is the missing link this closes.

## 2. Credential health

The fleet's sharpest single point of failure: every `cli-claude` session authenticates from operator-provisioned `CLAUDE_CONFIG_DIR` copies whose OAuth material can expire or be revoked — first symptom today: every session fails, silently, until morning.

- **CN-4 — Passive classification (mandatory).** The adapters' error classification gains an `auth` class (distinct from `limit` and `transient`): auth-shaped session failures immediately (a) mark the provider account `credential-suspect`, (b) park that account's teams' new sessions (hold-resume machinery, `opened_by: trigger:credential`), (c) fire `credential-failure` on the page channel — once, deduped per account. Parking beats thrashing: retry storms against a dead login burn nothing but look like an outage.
- **CN-5 — Active probe (optional, default weekly).** A scheduled cheap CLI probe per account (`claude --version`-class, no tokens; a 1-turn no-op on `mock` pricing where a real call is unavoidable) verifying the config dir still authenticates — catching expiry *before* a work session does. Config: `[continuity] credential_probe = "weekly"` (off/daily/weekly).
- **CN-6 — Re-auth runbook + sync.** One canonical login per provider; `scripts/accounts-sync` copies refreshed material to each account's config dir (the accounts already record `cliConfigDir`); teams parked under `trigger:credential` auto-resume on the next healthy probe or session. Expiry *foresight* from token metadata is best-effort where the provider exposes it, and never promised (debt OPS-D2).

## 3. Data continuity

**CN-7** A nightly maintenance loop in the control plane (a platform loop beside the cadence/trigger loops, not a team): SQLite online backup (`.backup`) to `data/backups/` with rotation (`[continuity] backup_keep = 14`), receipted in activity. **CN-8** `data/master.key` is named in the runbook as the item to back up *separately and securely* — with it, the secret store; without it, nothing recoverable; it never enters `data/backups/`. **CN-9** Off-machine copy is the operator's mechanism (cloud folder, rsync target) pointed at `data/backups/` — the runbook says so plainly rather than half-building sync. **CN-10** Restore is documented and *rehearsed by test*: a CI job restores a backup into a fresh data dir and boots green (`testing.md` gains the vector).

## 4. Disk and log hygiene

**CN-11** The maintenance loop enforces retention: session transcripts and stderr archives beyond `[retention] transcript_days = 30` are pruned with a receipt (counts, bytes); artifacts and the ledger are never auto-pruned (they are the record). **CN-12** Disk watermarks on the data volume: below 10% free → `attention` anomaly + pause-new-sessions (drain semantics, resumable); below 3% → `disk-critical` page. A fleet that fills the disk must degrade to waiting, not to corruption.

## 5. The runbook

**CN-13** `docs/runbooks/unattended.md` (deliverable of H3): first-boot supervision install; the four config flips (runtime, repo source, capacity, scheduler — with the C5–C7-merged prerequisite stated); credential provisioning and the re-auth drill; backup/restore drill; the page-channel test; "what to do when paged," one section per page class, each ending in a resolution the brief can verify. Runbooks are tested prose: each drill has a CI-or-manual marker, same discipline as `testing.md` §6's live path.

## 6. Open questions

1. Should the maintenance loop live in-process or as a second supervised job? Leaning in-process (one thing to supervise) with the backup step crash-isolated.
2. Windows service wrapper: NSSM vendored vs. Task Scheduler native. Decide in H3 by trying both on the real host.
3. Is a weekly credential probe too coarse for OAuth lifetimes actually observed? Collect the first month's `auth`-class data, then set the default honestly.
