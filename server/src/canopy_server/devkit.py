"""Dev-only helper to exercise the Model Gateway before the Actuator exists (A2).

The A1 demo is "curl the gateway as a fake agent": a metered completion, then exhaust a meter and
watch the 402. That needs a bound profile + a funded meter + a run token — all of which the
Actuator will mint in A2. Until then this CLI mints a throwaway "session" so the *real* gateway
resolution path (token → binding → profile → secret → meter) is exercised end to end, not stubbed.

    uv run --project server python -m canopy_server.devkit mint-session --org <ORG_ID>
    uv run --project server python -m canopy_server.devkit mint-session --org <ORG_ID> \
        --provider anthropic --model claude-sonnet-5 --secret-value sk-ant-...

Not wired into the app; it is not an HTTP surface.
"""

from __future__ import annotations

import argparse
import json
import sys

from .deps import get_ledger, get_profile_store, get_runtokens, get_secret_store
from .ids import new_actuation_id, new_agent_id


def _mint_session(args: argparse.Namespace) -> int:
    profiles = get_profile_store()
    secrets = get_secret_store()
    ledger = get_ledger()
    runtokens = get_runtokens()

    secret_id = None
    if args.secret_value:
        secret_id = secrets.create(args.org, args.secret_name, args.secret_value).id

    profile = profiles.create_profile(
        args.org,
        name=args.profile_name,
        provider=args.provider,
        model=args.model,
        api_key_secret_id=secret_id,
    )
    node_id = args.node or new_agent_id()
    profiles.set_binding(args.org, node_id, profile.id)

    actuation_id = new_actuation_id()
    meter = ledger.open_meter(
        actuation_id, node_id, args.allowance, warn_threshold_pct=args.warn, hard_stop=True
    )
    token, _ = runtokens.issue(
        actuation_id, node_id, args.org, default_meter_id=meter.id
    )

    curl = (
        f'curl -s http://localhost:8700/api/dp/llm/complete '
        f'-H "Authorization: Bearer {token}" -H "Content-Type: application/json" '
        f'-d \'{{"messages":[{{"role":"user","content":"hello"}}],"kind":"production"}}\''
    )
    print(json.dumps({
        "organizationId": args.org,
        "actuationId": actuation_id,
        "nodeId": node_id,
        "profileId": profile.id,
        "provider": args.provider,
        "model": args.model,
        "meterId": meter.id,
        "allowance": meter.allowance,
        "runToken": token,
    }, indent=2))
    print("\n# Try it:\n" + curl, file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="canopy-devkit")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ms = sub.add_parser("mint-session", help="mint a run token + meter for gateway curl testing")
    ms.add_argument("--org", required=True, help="organization id")
    ms.add_argument("--node", default=None, help="agent node id (default: a fresh synthetic id)")
    ms.add_argument("--provider", default="mock", choices=["mock", "anthropic", "gemini"])
    ms.add_argument("--model", default="mock-1")
    ms.add_argument("--allowance", type=int, default=2000, help="meter allowance in tokens")
    ms.add_argument("--warn", type=float, default=80.0)
    ms.add_argument("--profile-name", default="devkit profile")
    ms.add_argument("--secret-value", default=None, help="API key plaintext (real providers)")
    ms.add_argument("--secret-name", default="devkit key")
    ms.set_defaults(func=_mint_session)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
