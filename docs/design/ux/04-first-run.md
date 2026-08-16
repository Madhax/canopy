# 04 · First Run — setup as product

> **Status:** Proposed 2026-08-16 · **Reads with:** `README.md` P8, `../../execution/cli-runtime.md` (probe/readiness this surfaces), `../unattended/03-continuity.md` (the service posture this hands off to), root `README.md` (whose quickstart this simplifies), `../../canopy-inc.md` §7

## 0. The problem

Today's real-session path: install node+pnpm+uv, `pnpm install`, `uv sync`, install the Claude CLI, log in, hand-edit four `canopy.toml` flags, restart, create profiles, **bind a profile to every node individually**, actuate, and know that config is boot-time. Each step is documented somewhere; none of it is *product*. The bar: **demo mode in one command; real mode in one command plus one login; everything else is the app's job to check, explain, and fix.**

## 1. `canopy up` — one command (UX-30)

A launcher script (`pnpm canopy up` / `scripts/up`): verifies prerequisites (node, uv; installs workspace deps if missing), builds the UI if stale, boots the **production single-port** server (dev mode stays `pnpm dev`, for hacking on Canopy itself), opens the browser, prints one line per check. Flags: `--dev`, `--port`, `--data-dir`. It is the README's new first line, and it composes with the H3 service install ("run always" is `canopy up`'s standing form). **UX-31** `canopy doctor` — the same checks headless, with fix-it text per failure (missing uv → the install command; port busy → who holds it; no `claude` → the install link; logged out → the login command). Doctor output is the first thing support asks for; design it as the artifact to paste.

## 2. The System panel (UX-32)

Doctor, resident in-app: a header status chip (green/amber) opening a panel of the same checks live — CLI present/version, login state per provider account (from CN-4/5's classification), config posture (the four flags, current values), scheduler/capacity enabled, disk, backup age. **Each row states its fix**; where the fix is a config change, the panel shows the exact `canopy.toml` snippet — and once the H3 supervisor exists, offers *apply + restart* (config stays boot-time; the panel automates the boot, debt UXD-3). No more discovering `runtime_override` by reading a design doc.

## 3. The first-run wizard (UX-33)

On empty state, the app runs the sequence instead of documenting it:

1. **Mode**: *Demo* (keyless — `mock` + `loop`, everything free and deterministic) or *Real sessions* (runs the CLI checks inline; Demo is one click and never blocked).
2. **Organization + team**: name the org (or accept `default`), pick a team type → **start from a formation** (the existing stamp).
3. **Bindings, once**: create one Agent Profile and set it as the **team default binding — every node inherits it; per-node overrides are the exception** (kills today's worst step: per-node binding N times). Readiness re-checks live as bindings land.
4. **Readiness as checklist**: the existing actuation-readiness issues rendered as checkboxes with fix buttons, then **Actuate**.
5. **First intent**: a pre-filled template appropriate to the formation (the target-app CSV intent for the demo pod), submitted from the wizard's last screen.

**UX-34** Empty states across the app teach the same path piecemeal ("No teams yet — stamp one from a formation"); the wizard is the paved road, never a gate — every step skippable for the operator who knows the machinery.

## 4. Platform pulls

**UX-35** Team-level `defaultProfileBinding` with node-level override (document + store + editor support — the one schema change this series asks for). **UX-36** CLI login detection surfaced via the existing probe + CN-4 classification; no new auth machinery — presentation of what H3 already knows. **UX-37** Root README quickstart rewritten around `canopy up` when UX4 lands; **applied now** (truth-preserving, this change-set): the real-CLI path documented as one numbered section instead of a scattered paragraph — see root `README.md` §"Running with real Claude sessions".

## 5. Open questions

1. Should Demo mode auto-seed the tour team *actuated with a completed engagement* so the fleet/products views are alive at first paint? Leaning yes — an empty fleet view teaches nothing (`README` P8); one flag to skip.
2. Windows-first or parity-first for `canopy up` (the dev machine is Windows; CI is both)? Parity-first, per the two-OS testing rule.
3. Does the wizard offer the ops envelope at creation (mode `always` pre-selected) or defer to the team page? Defer — first-run is not the moment to explain autonomy policy; the readiness checklist (`../unattended/06`) catches it before any hands-off posture.
