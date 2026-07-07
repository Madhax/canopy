import pytest
from fastapi.testclient import TestClient

from canopy_server.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Point the store at an isolated temp dir for each test.
    monkeypatch.setenv("CANOPY_DATA_DIR", str(tmp_path))
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def make_org(client):
    """Factory: create an organization via the API and return its document."""

    def _make(otype="product-engineering", seed=None, name="Acme"):
        resp = client.post(
            "/api/organizations",
            json={"name": name, "organizationType": otype, "seed": seed or {"kind": "blank"}},
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _make


@pytest.fixture()
def mint_session(client):
    """Factory mirroring canopy_server.devkit: profile + binding + meter + run token.

    Exercises the real gateway resolution path (token → binding → profile → secret → meter) before
    the Actuator exists (A2). Depends on ``client`` so ``CANOPY_DATA_DIR`` is already pointed at the
    test's temp dir — the stores it builds share that database with the app's gateway.
    """

    def _mint(
        org_id, *, provider="mock", model="mock-1", allowance=5000, max_output=4096,
        secret_value=None, warn=80.0, node_id=None,
    ):
        from canopy_server.deps import (
            get_ledger,
            get_profile_store,
            get_runtokens,
            get_secret_store,
        )
        from canopy_server.ids import new_actuation_id, new_agent_id
        from canopy_server.profiles import ProfileParams

        profiles = get_profile_store()
        secret_id = None
        if secret_value is not None:
            secret_id = get_secret_store().create(org_id, "key", secret_value).id
        profile = profiles.create_profile(
            org_id, name="test profile", provider=provider, model=model,
            api_key_secret_id=secret_id, params=ProfileParams(maxOutputTokens=max_output),
        )
        node = node_id or new_agent_id()
        profiles.set_binding(org_id, node, profile.id)
        actuation_id = new_actuation_id()
        meter = get_ledger().open_meter(
            actuation_id, node, allowance, warn_threshold_pct=warn
        )
        token, _ = get_runtokens().issue(
            actuation_id, node, org_id, default_meter_id=meter.id
        )
        return {
            "token": token, "nodeId": node, "meterId": meter.id,
            "profileId": profile.id, "actuationId": actuation_id,
        }

    return _mint
