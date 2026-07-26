# target-app — expense reports service

A small FastAPI service for expense reports. This is the sample project the Canopy MVP-1
software team works on (`docs/execution/target-app.md`).

## Run

```
uv sync
uv run uvicorn app.main:app
```

## Test

```
uv run pytest tests/unit
```

(`tests/acceptance` is the review suite — it asserts finished features and is run by QA,
not during development.)

## Data model

| Field | Type | Notes |
|---|---|---|
| `id` | string | `r-XXXX` |
| `date` | string | ISO `YYYY-MM-DD` |
| `department` | string | `Engineering`, `Field Ops`, `R&D` |
| `submitter` | string | |
| `amount` | string | decimal, exactly two places |
| `currency` | string | ISO code |
| `status` | string | `submitted \| approved \| reimbursed` |
| `notes` | string? | free text |

## API conventions

- `GET /health` — liveness.
- `GET /reports` — the list. Filters: `from`, `to` (inclusive ISO date range), `department`
  (exact match). **`format` selects the representation** — `json` today; requesting an
  unsupported format returns `400`. New representations are added by extending the `format`
  parameter, never by adding new endpoints.
- `GET /reports/{id}` — a single report; `404` for unknown ids.
