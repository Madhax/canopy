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
from . import capacity as _capacity  # noqa: F401  (schema registration at import)
from .catalog import get_catalog
from .config import get_ui_dist
from .routes import actuations as actuation_routes
from .routes import capacity as capacity_routes
from .routes import catalog as catalog_routes
from .routes import connectors as connector_routes
from .routes import dp as dp_routes
from .routes import health as health_routes
from .routes import inspector as inspector_routes
from .routes import mcp as mcp_routes
from .routes import operations as operations_routes
from .routes import orgs as org_routes
from .routes import profiles as profiles_routes
from .routes import teams as team_routes
from .routes import work as work_routes


async def _reconciler_loop() -> None:
    """Every 15 s, restart nodes whose heartbeat went stale (control-plane.md §2).

    The try sits INSIDE the for (E6): one broken actuation must not starve the rest of the
    fleet's reconciliation — that failure mode kept every agent dead after a control-plane
    restart over a DB with a single orphaned actuation."""
    while True:
        try:
            from .deps import get_actuator

            actuator = get_actuator()
            actuation_ids = actuator.list_active_actuation_ids()
        except Exception:  # noqa: BLE001 - the reconciler must survive any single bad pass
            actuation_ids, actuator = [], None
        for actuation_id in actuation_ids:
            try:
                await actuator.reconcile_once(actuation_id)
            except Exception:  # noqa: BLE001 - isolate per actuation
                pass
        await asyncio.sleep(15)


def sweep_once() -> dict[str, int]:
    """One pass of the two sweeps the trigger loop runs — the stall triggers over executing
    assignments (work-model.md §6) and the capacity-gate timer resolution (04 §4). Each in
    its OWN try (E6's lesson, applied here at C7): a bad stall pass must never starve the
    capacity sweep, or a reset that passed while the control plane was down would sit
    unresolved until the next pass that happened not to throw. The first call happens at
    boot, before the loop's first sleep — that IS the restart sweep 04 §7 promises.
    Returns per-sweep counts (``-1`` marks a pass that raised) for tests and callers."""
    from .deps import get_engine, get_scheduler

    out = {"triggers": -1, "capacity": -1}
    try:
        out["triggers"] = len(get_engine().sweep_triggers())
    except Exception:  # noqa: BLE001 - the sweep must survive any single bad pass
        pass
    try:
        out["capacity"] = get_scheduler().sweep()
    except Exception:  # noqa: BLE001 - isolate the two sweeps from each other
        pass
    return out


async def _trigger_sweep_loop() -> None:
    """Every 30 s, ``sweep_once``. Budget warn/hard-stop ride each step report; this loop
    catches the quiet failures and resolves scheduled waits."""
    while True:
        try:
            sweep_once()
        except Exception:  # noqa: BLE001 - even the import must not kill the loop
            pass
        await asyncio.sleep(30)


async def _capacity_retention_loop() -> None:
    """Hourly compaction of the capacity ledger's append-only tables (02 §9.3, decided at
    C7): readings older than ``[capacity] reading_retention_days`` (30) go — except each
    window's newest, which is the state's provenance — and feed events older than
    ``event_retention_days`` (90). Runs once at boot, then hourly; ``0`` keeps forever."""
    while True:
        try:
            from .config import (
                get_capacity_event_retention_days,
                get_capacity_reading_retention_days,
            )
            from .deps import get_capacity_ledger

            get_capacity_ledger().prune(
                reading_retention_days=get_capacity_reading_retention_days(),
                event_retention_days=get_capacity_event_retention_days(),
            )
        except Exception:  # noqa: BLE001 - hygiene must survive any single bad pass
            pass
        await asyncio.sleep(3600)


async def _cadence_loop() -> None:
    """Every 30 s, fire due cadences as ordinary episodic intents (engine.md §4). Stateless:
    ``work_cadence.last_fired_at`` is the only cursor, so restarts just resume."""
    while True:
        try:
            from .deps import get_cadence_scheduler

            get_cadence_scheduler().run_once()
        except Exception:  # noqa: BLE001 - the scheduler must survive any single bad pass
            pass
        await asyncio.sleep(30)


async def _capacity_poll_loop() -> None:
    """Tier-1 pull for adapters with something to poll (03 §1; C6). Inert by
    default: the only polling adapter today is anthropic-max's S4 delegate, and it
    returns nothing unless ``[capacity.anthropic] source = "usage-endpoint"`` was
    explicitly set — the loop's cadence honors the 180 s etiquette floor either way.
    Sleeps first: no boot-time dial-out, ever."""
    while True:
        try:
            from .config import get_capacity_anthropic_poll_s

            delay = float(get_capacity_anthropic_poll_s())
        except Exception:  # noqa: BLE001
            delay = 300.0
        await asyncio.sleep(delay)
        try:
            from .capacity.adapters import adapter_for
            from .config import get_capacity_enabled
            from .deps import get_capacity_ledger, get_provider_accounts

            if not get_capacity_enabled():
                continue
            ledger = get_capacity_ledger()
            for acct in get_provider_accounts().list():
                adapter = adapter_for(acct)
                if adapter is None:
                    continue
                for reading in await asyncio.to_thread(adapter.poll, acct):
                    ledger.record_reading(acct.id, reading)
        except Exception:  # noqa: BLE001 - polling must survive any single bad pass
            pass


async def _trigger_poll_loop() -> None:
    """Every 60 s, poll enabled event triggers and open intents for new external events
    (standing-orgs.md §3). Stateless: the fire ledger + per-trigger cursor are the only
    state, so restarts resume with zero replays and zero drops."""
    while True:
        try:
            from .config import get_trigger_poll_seconds
            from .deps import get_trigger_scheduler

            await asyncio.to_thread(get_trigger_scheduler().run_once)
            delay = get_trigger_poll_seconds()
        except Exception:  # noqa: BLE001 - the scheduler must survive any single bad pass
            delay = 60.0
        await asyncio.sleep(delay)


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
            actuation_ids = actuator.list_active_actuation_ids()
        except Exception:  # noqa: BLE001 - a delivery hiccup must not kill the worker
            actuation_ids = []
        for actuation_id in actuation_ids:
            try:  # isolate per actuation (E6): one bad fleet member must not block deliveries
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
                                    "system", "router.dead_letter", team_id=None,
                                    subject_ids=[actuation_id, agent.nodeId, delivery.id],
                                )
            except Exception:  # noqa: BLE001
                pass
        await asyncio.sleep(1)


@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    # C1 boot migrations: store construction renames tables / assigns the default
    # Organization; the filesystem pass then regroups data/work + data/repos under
    # data/orgs/<orgKey>/teams/<teamId>/ (design/organizations/07 §2.3–2.5).
    from .config import get_data_dir
    from .deps import get_db, get_store
    from .orgs import migrate_c1_filesystem

    get_store()
    migrate_c1_filesystem(get_data_dir(), get_db())

    tasks = [
        asyncio.create_task(_reconciler_loop()),
        asyncio.create_task(_delivery_loop()),
        asyncio.create_task(_trigger_sweep_loop()),
        asyncio.create_task(_cadence_loop()),
        asyncio.create_task(_trigger_poll_loop()),
        asyncio.create_task(_capacity_poll_loop()),
        asyncio.create_task(_capacity_retention_loop()),
    ]
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
    api.include_router(team_routes.router)
    api.include_router(org_routes.router)  # organizations + portfolio + move (C1)
    api.include_router(capacity_routes.router)  # capacity aggregate + accounts + S3 tap (C3)
    api.include_router(profiles_routes.router)  # profiles / bindings / secrets (A1)
    api.include_router(connector_routes.router)  # connector instances (builder-connectors.md)
    api.include_router(operations_routes.router)  # spend rollups + activity feed (A1)
    api.include_router(actuation_routes.router)  # actuate / deactuate / current (A2)
    api.include_router(dp_routes.router)  # data plane /api/dp/* (gateway + charter/register/hb)
    api.include_router(mcp_routes.router)  # Canopy MCP server /api/dp/mcp (E3, cli-runtime §4)
    api.include_router(work_routes.router)  # operator work API: intents + assignments (E1)
    api.include_router(inspector_routes.router)  # agent inspector aggregate + memory (E5)
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
