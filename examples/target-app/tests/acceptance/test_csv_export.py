"""The seeded acceptance contract (target-app.md §6) — QA's suite, RED against the shipped app
BY DEFINITION: it pins the finished CSV-export feature. The fixture's own CI excludes this
directory (`pytest tests/unit`); it exists for QA's runtime use during the MVP demo.

The intent's words — "all tests must pass" — make this suite the deliverable contract, so a
first attempt that misses it is a quality failure under the rework-funding rule, not a trap.
"""

import csv
import io

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.acceptance

client = TestClient(app)

HEADER = "id,date,department,submitter,amount,currency,status,notes"


def _get_csv(query: str = "") -> "csv_response":  # noqa: F821 - doc alias
    return client.get(f"/reports?format=csv{query}")


def test_surface_and_content_type():
    r = _get_csv()
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "charset=utf-8" in r.headers["content-type"].replace(" ", "")


def test_header_row_exact():
    body = _get_csv().text
    assert body.splitlines()[0] == HEADER  # the model's field order, verbatim


def test_rfc4180_quoting_of_the_seed_rows():
    body = _get_csv().text
    # The comma row: the notes field is double-quoted.
    assert '"lunch, client on-site"' in body
    # The quote row: embedded quotes doubled, field quoted.
    assert '"saw the ""good"" vendor"' in body
    # The newline row: the embedded newline survives inside a quoted field.
    assert '"site visit\nsecond day"' in body or '"site visit\r\nsecond day"' in body


def test_empty_result_is_header_only():
    r = _get_csv("&department=Marketing")
    assert r.status_code == 200  # never 204, never zero bytes
    lines = [ln for ln in r.text.splitlines() if ln]
    assert lines == [HEADER]


def test_formats_and_encoding():
    body = _get_csv().text
    rows = list(csv.reader(io.StringIO(body)))
    amounts = [row[4] for row in rows[1:]]
    assert all(len(a.split(".")[-1]) == 2 for a in amounts)  # exactly two decimals
    dates = [row[1] for row in rows[1:]]
    assert all(len(d) == 10 and d[4] == "-" and d[7] == "-" for d in dates)  # ISO dates
    raw = _get_csv().content
    assert not raw.startswith(b"\xef\xbb\xbf")  # UTF-8, no BOM
    assert "naïve" in body and "café" in body  # non-ASCII survives


def test_csv_round_trips_against_json():
    for query in ("", "&department=Engineering", "&from=2026-05-01&to=2026-05-31"):
        json_rows = client.get(f"/reports?format=json{query}").json()
        body = _get_csv(query).text
        parsed = list(csv.reader(io.StringIO(body)))
        assert len(parsed) - 1 == len(json_rows)  # header + one row per report
        for csv_row, jr in zip(parsed[1:], json_rows):
            assert csv_row[0] == jr["id"]
            assert csv_row[7] == (jr["notes"] or "")
