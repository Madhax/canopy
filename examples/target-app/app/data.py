"""Committed, deterministic seed data (target-app.md §3).

The adversarial rows are IN the visible dataset, not hidden: notes with commas, embedded
double quotes, a real newline, and non-ASCII; amounts including 0.00 and four-digit values.
The acceptance suite pins its RFC 4180 assertions against these exact rows byte-for-byte.
"""

from __future__ import annotations

from .models import Report

_ROWS: list[dict] = [
    # -- Engineering, month 1 -------------------------------------------------
    {"id": "r-0001", "date": "2026-04-03", "department": "Engineering",
     "submitter": "ada", "amount": "42.50", "currency": "USD", "status": "approved",
     "notes": "team offsite supplies"},
    {"id": "r-0002", "date": "2026-04-07", "department": "Engineering",
     "submitter": "grace", "amount": "18.00", "currency": "USD", "status": "reimbursed",
     "notes": "lunch, client on-site"},  # the comma row
    {"id": "r-0003", "date": "2026-04-11", "department": "Engineering",
     "submitter": "linus", "amount": "0.00", "currency": "USD", "status": "submitted",
     "notes": "voided duplicate"},
    {"id": "r-0004", "date": "2026-04-19", "department": "Engineering",
     "submitter": "ada", "amount": "1250.00", "currency": "USD", "status": "approved",
     "notes": 'saw the "good" vendor'},  # the quote row
    # -- Field Ops, month 1 ---------------------------------------------------
    {"id": "r-0005", "date": "2026-04-05", "department": "Field Ops",
     "submitter": "mira", "amount": "63.20", "currency": "USD", "status": "reimbursed",
     "notes": "site visit\nsecond day"},  # the newline row
    {"id": "r-0006", "date": "2026-04-12", "department": "Field Ops",
     "submitter": "kai", "amount": "7.75", "currency": "USD", "status": "submitted",
     "notes": None},
    {"id": "r-0007", "date": "2026-04-21", "department": "Field Ops",
     "submitter": "mira", "amount": "310.00", "currency": "USD", "status": "approved",
     "notes": "equipment rental"},
    # -- R&D, month 1 ---------------------------------------------------------
    {"id": "r-0008", "date": "2026-04-09", "department": "R&D",
     "submitter": "noor", "amount": "95.10", "currency": "EUR", "status": "approved",
     "notes": "naïve bayes workshop at the café"},  # the non-ASCII row
    {"id": "r-0009", "date": "2026-04-27", "department": "R&D",
     "submitter": "sam", "amount": "12.99", "currency": "USD", "status": "submitted",
     "notes": "journal access"},
    # -- month 2 --------------------------------------------------------------
    {"id": "r-0010", "date": "2026-05-02", "department": "Engineering",
     "submitter": "grace", "amount": "220.40", "currency": "USD", "status": "approved",
     "notes": "conference travel"},
    {"id": "r-0011", "date": "2026-05-06", "department": "Engineering",
     "submitter": "linus", "amount": "35.00", "currency": "USD", "status": "reimbursed",
     "notes": "keyboard"},
    {"id": "r-0012", "date": "2026-05-09", "department": "Field Ops",
     "submitter": "kai", "amount": "88.88", "currency": "USD", "status": "approved",
     "notes": "fuel"},
    {"id": "r-0013", "date": "2026-05-13", "department": "Field Ops",
     "submitter": "mira", "amount": "150.00", "currency": "USD", "status": "submitted",
     "notes": "safety gear"},
    {"id": "r-0014", "date": "2026-05-17", "department": "R&D",
     "submitter": "noor", "amount": "410.60", "currency": "EUR", "status": "approved",
     "notes": "lab consumables"},
    {"id": "r-0015", "date": "2026-05-21", "department": "R&D",
     "submitter": "sam", "amount": "5.25", "currency": "USD", "status": "reimbursed",
     "notes": "postage"},
    {"id": "r-0016", "date": "2026-05-25", "department": "Engineering",
     "submitter": "ada", "amount": "999.99", "currency": "USD", "status": "submitted",
     "notes": "workstation deposit"},
    # -- month 3 --------------------------------------------------------------
    {"id": "r-0017", "date": "2026-06-01", "department": "Engineering",
     "submitter": "grace", "amount": "27.30", "currency": "USD", "status": "approved",
     "notes": "team lunch"},
    {"id": "r-0018", "date": "2026-06-04", "department": "Engineering",
     "submitter": "linus", "amount": "64.00", "currency": "USD", "status": "submitted",
     "notes": "docking station"},
    {"id": "r-0019", "date": "2026-06-08", "department": "Field Ops",
     "submitter": "kai", "amount": "19.60", "currency": "USD", "status": "reimbursed",
     "notes": "parking"},
    {"id": "r-0020", "date": "2026-06-11", "department": "Field Ops",
     "submitter": "mira", "amount": "530.00", "currency": "USD", "status": "approved",
     "notes": "subcontractor day rate"},
    {"id": "r-0021", "date": "2026-06-14", "department": "R&D",
     "submitter": "noor", "amount": "75.00", "currency": "EUR", "status": "submitted",
     "notes": "dataset license"},
    {"id": "r-0022", "date": "2026-06-17", "department": "R&D",
     "submitter": "sam", "amount": "8.40", "currency": "USD", "status": "approved",
     "notes": "cables"},
    {"id": "r-0023", "date": "2026-06-20", "department": "Engineering",
     "submitter": "ada", "amount": "301.10", "currency": "USD", "status": "reimbursed",
     "notes": "cloud credits overage"},
    {"id": "r-0024", "date": "2026-06-23", "department": "Field Ops",
     "submitter": "kai", "amount": "45.45", "currency": "USD", "status": "submitted",
     "notes": "tolls, both directions"},
    {"id": "r-0025", "date": "2026-06-26", "department": "R&D",
     "submitter": "noor", "amount": "2200.00", "currency": "EUR", "status": "approved",
     "notes": "microscope service contract"},
]

REPORTS: list[Report] = [Report(**r) for r in _ROWS]
