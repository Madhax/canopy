"""The expense report — deliberately small, naturally tabular (target-app.md §3)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Status = Literal["submitted", "approved", "reimbursed"]


class Report(BaseModel):
    id: str
    date: str  # ISO YYYY-MM-DD
    department: str
    submitter: str
    amount: str  # decimal, two places, serialized as a string to keep cents exact
    currency: str  # ISO code
    status: Status
    notes: str | None = None
