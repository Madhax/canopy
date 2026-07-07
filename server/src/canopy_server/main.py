"""FastAPI application factory.

Dev: the UI runs on Vite (:5173) and proxies ``/api`` here (:8700).
Prod: ``pnpm build`` emits ``ui/dist`` and this app serves it as static files + SPA fallback.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__

# Import the schema-owning modules whose tables no route pulls in yet (the Execution Engine's
# routes arrive in E1 item 3). Schemas register at import (see db.py), and the gateway now depends
# on the work store, so these must be registered before the first Db is built.
from . import artifacts as _artifacts  # noqa: F401
from .catalog import get_catalog
from .config import get_ui_dist
from .engine import store as _engine_store  # noqa: F401
from .routes import actuations as actuation_routes
from .routes import catalog as catalog_routes
from .routes import dp as dp_routes
from .routes import health as health_routes
from .routes import operations as operations_routes
from .routes import organizations as organization_routes
from .routes import profiles as profiles_routes


async def _reconciler_loop() -> None:
    """Every 15 s, restart nodes whose heartbeat went stale (control-plane.md §2)."""
    while True:
        try:
            from .deps import get_actuator

            actuator = get_actuator()
            for actuation_id in actuator.list_active_actuation_ids():
                await actuator.reconcile_once(actuation_id)
        except Exception:  # noqa: BLE001 - the reconciler must survive any single bad pass
            pass
        await asyncio.sleep(15)


async def _forward_to_agent(endpoint_url: str, envelope) -> bool:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(endpoint_url.rstrip("/") + "/inbox", json=envelope.model_dump())
            return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False


async def _delivery_loop() -> None:
    """Forward queued messages to idle agents (data-plane.md §3: delivery workers).

    Only delivers to a node the directory shows ``idle`` — an engaged/paused node simply isn't
    delivered to until it heartbeats idle, which gives the domain's "one executing assignment at a
    time; a growing queue is a visible bottleneck" for free.
    """
    while True:
        try:
            from .deps import get_activity, get_actuator, get_bus, get_directory
            from .router import inbox_topic

            actuator, directory, bus, activity = (
                get_actuator(), get_directory(), get_bus(), get_activity()
            )
            for actuation_id in actuator.list_active_actuation_ids():
                for agent in directory.list(actuation_id):
                    if agent.status != "idle" or not agent.endpointUrl:
                        continue
                    topic = inbox_topic(actuation_id, agent.nodeId)
                    for delivery in bus.poll(topic, "delivery-worker", 5, 30):
                        if await _forward_to_agent(agent.endpointUrl, delivery.envelope):
                            bus.ack(delivery.id)
                        else:
                            dead, _env = bus.nack(delivery.id, requeue=True)
                            if dead:
                                activity.log(
                                    "system", "router.dead_letter", org_id=None,
                                    subject_ids=[actuation_id, agent.nodeId, delivery.id],
                                )
        except Exception:  # noqa: BLE001 - a delivery hiccup must not kill the worker
            pass
        await asyncio.sleep(1)


@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    tasks = [asyncio.create_task(_reconciler_loop()), asyncio.create_task(_delivery_loop())]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task


def create_app() -> FastAPI:
    app = FastAPI(title="Canopy Control Plane", version=__version__, lifespan=_lifespan)

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
    api.include_router(profiles_routes.router)  # profiles / bindings / secrets (A1)
    api.include_router(operations_routes.router)  # spend rollups + activity feed (A1)
    api.include_router(actuation_routes.router)  # actuate / deactuate / current (A2)
    api.include_router(dp_routes.router)  # data plane /api/dp/* (gateway + charter/register/hb)
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
