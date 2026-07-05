"""FastAPI application factory.

Dev: the UI runs on Vite (:5173) and proxies ``/api`` here (:8700).
Prod: ``pnpm build`` emits ``ui/dist`` and this app serves it as static files + SPA fallback.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .catalog import get_catalog
from .config import get_ui_dist
from .routes import catalog as catalog_routes
from .routes import health as health_routes
from .routes import organizations as organization_routes


def create_app() -> FastAPI:
    app = FastAPI(title="Canopy Control Plane", version=__version__)

    # Fail fast if the catalog is broken — better at boot than on first request.
    get_catalog()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = FastAPI(title="Canopy API", version=__version__)
    api.include_router(health_routes.router)
    api.include_router(catalog_routes.router)
    api.include_router(organization_routes.router)
    app.mount("/api", api)

    _mount_ui(app)
    return app


def _mount_ui(app: FastAPI) -> None:
    dist = get_ui_dist()
    if not dist.is_dir():
        # No built UI (dev mode): a friendly note at the root instead of a 404.
        @app.get("/")
        def _dev_root() -> JSONResponse:
            return JSONResponse(
                {
                    "status": "ok",
                    "message": "Canopy API is running. Start the UI with `pnpm dev` "
                    "and open http://localhost:5173.",
                }
            )

        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    index = dist / "index.html"

    @app.get("/{full_path:path}")
    def _spa(full_path: str, request: Request) -> FileResponse:
        # Serve real files when present; otherwise fall back to index.html for client routing.
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
