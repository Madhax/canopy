"""S4 — the OAuth usage endpoint (03 §2 S4). [Community], ToS-gray, OFF BY DEFAULT.

The compliance posture, verbatim from the design (03 §2), because this module IS the
risk it describes: ``GET https://api.anthropic.com/api/oauth/usage`` with the login's
OAuth bearer token returns the full picture — ``five_hour``, ``seven_day``,
``seven_day_opus``, ``seven_day_sonnet`` each ``{utilization, resets_at}``, plus
``extra_usage {is_enabled, monthly_limit, used_credits, utilization}``. It is
undocumented, aggressively rate-limited (poll >= 180 s), requires Claude-Code-shaped
request headers, and — decisively — Anthropic's 2026 consumer-terms clarification
prohibits using subscription OAuth tokens outside Claude Code itself. Widely-used
monitors consume it without incident to date, and enforcement has targeted third-party
*inference*, but the compliance posture is the operator's call, not ours to default.
Therefore ``[capacity.anthropic] source = "usage-endpoint"`` is off by default,
documented with exactly this paragraph, and the entire design works without it —
S1/S2/S3 + calibration deliver every feature at reduced fidelity. This is the one
place the "source of truth first" requirement bends to a provider's terms, and it
bends transparently.

Isolation is the mitigation (CAP-D1): every S4 concern lives in this one module —
delete the file and the risk is gone. The adapter's ``poll`` delegates here behind
the config gate; nothing else imports it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..accounts import ProviderAccount
from . import WindowReading

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"

_WINDOW_KEYS = ("five_hour", "seven_day", "seven_day_opus", "seven_day_sonnet")


def read_oauth_token(cli_config_dir: str | None) -> str | None:
    """The login's bearer, from the account's own config dir ([Community] shape:
    ``.credentials.json`` → ``claudeAiOauth.accessToken``). Never another
    instance's credentials (03 §2 'what the adapter does not do'); fails soft —
    no token means no readings, never an error."""
    base = Path(cli_config_dir).expanduser() if cli_config_dir else Path.home() / ".claude"
    path = base / ".credentials.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        token = (payload.get("claudeAiOauth") or {}).get("accessToken")
        return str(token) if token else None
    except (OSError, ValueError):
        return None


def _resets_iso(value: Any) -> str | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(int(value), tz=UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, str) and value:
        return value
    return None


def parse_usage_payload(payload: dict[str, Any]) -> list[WindowReading]:
    """The endpoint's JSON → tier-1 readings. Unknown keys are ignored; a missing
    window simply yields no reading (unknown beats fabricated, 06 §6.3)."""
    readings: list[WindowReading] = []
    for key in _WINDOW_KEYS:
        entry = payload.get(key)
        if not isinstance(entry, dict):
            continue
        util = entry.get("utilization")
        if util is None:
            continue
        readings.append(WindowReading(
            window_key=key, source="provider-read", utilization_pct=float(util),
            resets_at=_resets_iso(entry.get("resets_at")), detail="s4-usage",
        ))
    extra = payload.get("extra_usage")
    if isinstance(extra, dict) and extra.get("is_enabled"):
        util = extra.get("utilization")
        used = extra.get("used_credits")
        limit = extra.get("monthly_limit")
        readings.append(WindowReading(
            window_key="extra_usage", source="provider-read",
            utilization_pct=float(util) if util is not None else None,
            kind="credit-pool",
            detail=f"s4-usage credits {used}/{limit}"
            if used is not None and limit is not None else "s4-usage",
        ))
    return readings


def _default_fetcher(url: str, headers: dict[str, str]) -> dict[str, Any]:
    import urllib.request

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 - fixed https URL
        return json.loads(resp.read().decode("utf-8"))


def fetch_usage(
    account: ProviderAccount,
    *,
    fetcher: Callable[[str, dict[str, str]], dict[str, Any]] | None = None,
) -> list[WindowReading]:
    """One poll. Every failure path returns [] — a [Community] surface must degrade
    to the next tier without operator action (03 provenance discipline); S1/S2/S3
    keep the lights on when this goes dark."""
    token = read_oauth_token(account.cliConfigDir)
    if token is None:
        return []
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        # Claude-Code-shaped headers: the endpoint serves the CLI's own telemetry.
        "User-Agent": "claude-code",
        "anthropic-beta": "oauth-2025-04-20",
    }
    try:
        payload = (fetcher or _default_fetcher)(USAGE_URL, headers)
    except Exception:  # noqa: BLE001 - rate-limits, network, schema drift: all degrade
        return []
    if not isinstance(payload, dict):
        return []
    return parse_usage_payload(payload)
