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
