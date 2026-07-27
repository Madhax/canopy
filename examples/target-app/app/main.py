"""Expense-reports service (docs/execution/target-app.md §3).

API conventions: list endpoints take a ``format`` query parameter. ``json`` is the shipped
format; unknown values are a 400 — the convention is the extension seam.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from .data import REPORTS
from .models import Report

app = FastAPI(title="target-app", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _filtered(
    from_: str | None, to: str | None, department: str | None,
) -> list[Report]:
    rows = REPORTS
    if from_ is not None:
        rows = [r for r in rows if r.date >= from_]
    if to is not None:
        rows = [r for r in rows if r.date <= to]
    if department is not None:
        rows = [r for r in rows if r.department == department]
    return rows


@app.get("/reports")
def list_reports(
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    department: str | None = None,
    format: str = "json",
):
    rows = _filtered(from_, to, department)
    if format == "json":
        return [r.model_dump() for r in rows]
    raise HTTPException(status_code=400, detail=f"unsupported format: {format!r}")


@app.get("/reports/{report_id}")
def get_report(report_id: str) -> dict:
    for r in REPORTS:
        if r.id == report_id:
            return r.model_dump()
    raise HTTPException(status_code=404, detail=f"no report {report_id!r}")
