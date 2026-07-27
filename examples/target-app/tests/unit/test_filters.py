"""Date-range + department filters (inclusive bounds, exact department match)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_department_filter_exact():
    rows = client.get("/reports?department=R%26D").json()
    assert rows and all(r["department"] == "R&D" for r in rows)


def test_date_range_inclusive():
    rows = client.get("/reports?from=2026-05-01&to=2026-05-31").json()
    assert rows and all("2026-05-01" <= r["date"] <= "2026-05-31" for r in rows)
    # Boundary rows are included.
    ids = {r["id"] for r in client.get("/reports?from=2026-05-02&to=2026-05-02").json()}
    assert "r-0010" in ids


def test_combined_filters():
    rows = client.get("/reports?department=Engineering&from=2026-06-01").json()
    assert {r["id"] for r in rows} == {"r-0017", "r-0018", "r-0023"}


def test_empty_result_is_an_empty_list():
    assert client.get("/reports?department=Marketing").json() == []
