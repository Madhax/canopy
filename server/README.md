# canopy-server

FastAPI thin control plane for the Canopy org-chart editor (Phase 1). Persists and validates
serialized Organization documents. See [`../docs/org-chart-editor.md`](../docs/org-chart-editor.md)
§5–§6 for the contract this implements.

## Dev

From the repo root:

```sh
uv sync --project server        # install deps
pnpm dev                        # runs this + the UI (uvicorn :8700, vite :5173)
```

Standalone:

```sh
uv run --project server uvicorn canopy_server.main:app --reload --port 8700
uv run --project server pytest server/tests -q
```

## Layout

- `models.py` — Pydantic v2 schema for Organization documents and the catalog.
- `validation/` — the authoritative rule set (`codes.py`, `rules.py`).
- `catalog.py` — loads `../catalog/catalog.json`, integrity-checked at import.
- `store.py` — JSON file store with atomic writes (`CANOPY_DATA_DIR`, default `./data`).
- `routes/` — `health`, `catalog`, `organizations`.
- `main.py` — app factory; serves the built UI (`ui/dist`) in production.
