"""The capacity read surface (design/organizations/06, milestone C3).

One aggregate — ``GET /api/capacity`` — serves the console and the portfolio strip:
accounts with their windows (each level wearing source tier + age), per-window burn
stacks with the ``external`` band, runway for the headline window, and the event feed.
**Zero capacity math lives in the UI**; everything here comes computed so the console
and the scheduler can never disagree.

Also here: ProviderAccount CRUD (accounts involve logins and secrets, so they are
operator data behind the API, never TOML), and the S3 statusline tap — an officially
documented tier-1 surface: point Claude Code's statusline command at
``POST /api/capacity/statusline`` (e.g. ``curl -s -X POST .../api/capacity/statusline
-d @-``) and every interactive session of the same login feeds provider-read levels
for free (03 §2 S3; opt-in by installing the hook, reversible by removing it).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from ..capacity.adapters import WindowReading, adapter_for
from ..config import get_capacity_enabled
from ..deps import (
    get_capacity_ledger,
    get_org_store,
    get_provider_accounts,
    get_store,
)

router = APIRouter()

_HEADLINE = {"anthropic": "five_hour", "google": "cli_daily"}


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _window_json(w: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": w["key"],
        "kind": w["kind"],
        "displayName": w["display_name"],
        "modelScope": w["model_scope"],
        "state": w["state"],
        "utilizationPct": w["utilization_pct"],
        "resetsAt": w["resets_at"],
        # The honesty rule (06 §6): every level wears its source tier and its age.
        "source": w["source"],
        "observedAt": w["observed_at"],
        "ageS": w["age_s"],
    }


@router.get("/capacity")
def capacity_aggregate(
    accounts=Depends(get_provider_accounts),
    ledger=Depends(get_capacity_ledger),
    store=Depends(get_store),
    orgs=Depends(get_org_store),
) -> dict:
    """The console's single source (02 §7): stored facts + derived math, computed here."""
    team_names: dict[str, str] = {}
    team_orgs: dict[str, str] = {}
    org_meta: dict[str, dict] = {o.id: {"key": o.key, "name": o.name} for o in orgs.list()}
    for team in store.read_all():
        team_names[team.id] = team.name
        membership = getattr(store, "organization_of", None)
        if membership is not None:
            try:
                team_orgs[team.id] = membership(team.id)
            except Exception:  # noqa: BLE001 - membership is decoration here
                pass

    def band(team_id: str, pp_hr: float) -> dict:
        org_id = team_orgs.get(team_id)
        meta = org_meta.get(org_id or "", {})
        return {
            "teamId": team_id,
            "teamName": team_names.get(team_id, team_id),
            "orgId": org_id,
            "orgKey": meta.get("key"),
            "orgName": meta.get("name"),
            "ppHr": round(pp_hr, 2),
        }

    out_accounts = []
    for acct in accounts.list():
        adapter = adapter_for(acct)
        windows = ledger.windows(acct.id)
        known = {w["key"] for w in windows}
        # Windows discovered from readings carry their key as display name; the
        # adapter's vocabulary is nicer — presentation only, storage untouched.
        if adapter is not None:
            names = {sp.key: sp.display_name for sp in adapter.expected_windows(acct)}
            for w in windows:
                if w["display_name"] == w["key"] and w["key"] in names:
                    w["display_name"] = names[w["key"]]
        # planHint seeds gauges before first contact (02 §3) — expected windows render
        # as "no reading yet", never as a number.
        if adapter is not None:
            for spec in adapter.expected_windows(acct):
                if spec.key not in known:
                    windows.append({
                        "key": spec.key, "kind": spec.kind, "display_name": spec.display_name,
                        "model_scope": spec.model_scope, "state": "unknown",
                        "utilization_pct": None, "resets_at": None, "source": None,
                        "observed_at": None, "age_s": None,
                    })
        headline = _HEADLINE.get(acct.provider)
        burn: dict[str, Any] = {}
        runway: dict[str, Any] | None = None
        for w in windows:
            if w["source"] is None:
                continue
            rates = ledger.burn_rates(acct.id, w["key"])
            external = rates.pop("external", 0.0)
            burn[w["key"]] = {
                "teams": sorted(
                    (band(t, r) for t, r in rates.items()),
                    key=lambda b: -b["ppHr"],
                ),
                "externalPpHr": round(external, 2),
            }
            if w["key"] == headline or (headline not in known and runway is None):
                runway = {**ledger.runway(acct.id, w["key"]), "windowKey": w["key"]}
        events = []
        for ev in ledger.events(acct.id, limit=30):
            events.append({
                "id": ev["id"], "kind": ev["kind"], "windowKey": ev["window_key"],
                "teamId": ev["team_id"],
                "teamName": team_names.get(ev["team_id"] or "", ev["team_id"]),
                "payload": ev["payload"], "createdAt": ev["created_at"],
            })
        out_accounts.append({
            "id": acct.id, "provider": acct.provider, "authMode": acct.authMode,
            "label": acct.label, "planHint": acct.planHint,
            "maxConcurrentSessions": acct.maxConcurrentSessions,
            "windows": [_window_json(w) for w in sorted(windows, key=lambda x: x["key"])],
            "headlineWindow": headline,
            "burn": burn,
            "runway": runway,
            "events": events,
        })
    return {"enabled": get_capacity_enabled(), "accounts": out_accounts}


# --------------------------------------------------------------------------- #
# ProviderAccount CRUD (07 §3) — operator data; logins and secrets, never TOML
# --------------------------------------------------------------------------- #
class CreateAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    authMode: str
    label: str
    cliConfigDir: str | None = None
    cliCmd: str | None = None
    apiKeySecretId: str | None = None
    planHint: str | None = None
    maxConcurrentSessions: int = 4


class UpdateAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str | None = None
    cliConfigDir: str | None = None
    planHint: str | None = None
    maxConcurrentSessions: int | None = None


@router.get("/capacity/accounts")
def list_accounts(accounts=Depends(get_provider_accounts)) -> list[dict]:
    return [a.model_dump(mode="json") for a in accounts.list()]


@router.post("/capacity/accounts", status_code=201)
def create_account(req: CreateAccountRequest, accounts=Depends(get_provider_accounts)):
    acct = accounts.create(
        provider=req.provider, auth_mode=req.authMode, label=req.label,
        cli_config_dir=req.cliConfigDir, cli_cmd=req.cliCmd,
        api_key_secret_id=req.apiKeySecretId, plan_hint=req.planHint,
        max_concurrent_sessions=req.maxConcurrentSessions,
    )
    return JSONResponse(status_code=201, content=acct.model_dump(mode="json"))


@router.put("/capacity/accounts/{account_id}")
def update_account(
    account_id: str, req: UpdateAccountRequest, accounts=Depends(get_provider_accounts)
):
    acct = accounts.get(account_id)
    if acct is None:
        return _error(404, "NOT_FOUND", f"No account {account_id!r}")
    with accounts.db.transaction() as conn:
        conn.execute(
            "UPDATE provider_account SET label=?, cli_config_dir=?, plan_hint=?,"
            " max_concurrent_sessions=? WHERE id=?",
            (req.label if req.label is not None else acct.label,
             req.cliConfigDir if req.cliConfigDir is not None else acct.cliConfigDir,
             req.planHint if req.planHint is not None else acct.planHint,
             req.maxConcurrentSessions if req.maxConcurrentSessions is not None
             else acct.maxConcurrentSessions,
             account_id),
        )
    return accounts.get(account_id).model_dump(mode="json")


# --------------------------------------------------------------------------- #
# S3 — the statusline tap (03 §2): an [Official] tier-1 surface, opt-in
# --------------------------------------------------------------------------- #
@router.post("/capacity/statusline")
def statusline_tap(
    body: dict,
    accounts=Depends(get_provider_accounts),
    ledger=Depends(get_capacity_ledger),
):
    """Accepts Claude Code's statusline stdin JSON. ``rate_limits.five_hour`` /
    ``.seven_day`` carry ``used_percentage`` + ``resets_at`` (epoch) — an officially
    documented provider-read of the two headline windows, fed by ANY interactive
    session of the same login, including the operator's own coding."""
    if not get_capacity_enabled():
        return _error(409, "CAPACITY_DISABLED", "[capacity] enabled is false.")
    rate_limits = body.get("rate_limits") or {}
    if not isinstance(rate_limits, dict) or not rate_limits:
        return {"readings": 0}
    acct = accounts.ensure_cli_account("anthropic")
    n = 0
    for key in ("five_hour", "seven_day"):
        entry = rate_limits.get(key)
        if not isinstance(entry, dict):
            continue
        used = entry.get("used_percentage")
        resets = entry.get("resets_at")
        if used is None:
            continue
        resets_iso = None
        if isinstance(resets, (int, float)):
            from datetime import UTC, datetime

            resets_iso = datetime.fromtimestamp(int(resets), tz=UTC).isoformat()\
                .replace("+00:00", "Z")
        elif isinstance(resets, str):
            resets_iso = resets
        ledger.record_reading(acct.id, WindowReading(
            window_key=key, source="provider-read", utilization_pct=float(used),
            resets_at=resets_iso, detail="s3-statusline",
        ))
        n += 1
    return {"readings": n}
