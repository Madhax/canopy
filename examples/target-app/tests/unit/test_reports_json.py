"""Engineer-runnable unit suite: list/detail/404, format=json, unknown format -> 400.

Deliberately probes the format seam with `xml`, NOT `csv` — the seam stays open for the
feature the acceptance suite will pin (target-app.md §4)."""

from fastapi.testclient import TestClient

from app.data import REPORTS
from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_list_returns_all_seed_rows():
    body = client.get("/reports").json()
    assert len(body) == len(REPORTS) == 25
    assert body[0]["id"] == "r-0001"


def test_detail_and_404():
    one = client.get("/reports/r-0004").json()
    assert one["submitter"] == "ada" and one["amount"] == "1250.00"
    assert client.get("/reports/r-9999").status_code == 404


def test_format_json_is_explicitly_supported():
    assert client.get("/reports?format=json").status_code == 200


def test_unknown_format_is_400():
    r = client.get("/reports?format=xml")
    assert r.status_code == 400
    assert "unsupported format" in r.json()["detail"]
