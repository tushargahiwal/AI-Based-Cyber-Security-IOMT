import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from config import settings
from database import engine
from database import SessionLocal
from services import safety_service
from services.broadcast import broadcaster
from services.security import decode_access_token
from routers import (
    alerts,
    attack_types,
    audit_logs,
    auth,
    blocklist,
    datasets,
    detections,
    devices,
    enforcement,
    ml_models,
    patients,
    protocols,
    stats,
    system_config,
    thresholds,
    notifications,
    reports,
    simulation,
    users,
    vitals,
)

async def _safety_sweep() -> None:
    """Lifts quarantines and blocks that have reached their deadline.

    Runs for the life of the process. A failure here must never take the API
    down with it, so the loop logs and carries on — but a device staying
    quarantined is the failure that matters, hence the log is a warning.
    """
    while True:
        await asyncio.sleep(safety_service.SWEEP_SECONDS)
        try:
            db = SessionLocal()
            try:
                await asyncio.to_thread(safety_service.release_expired, db)
            finally:
                db.close()
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.getLogger(__name__).warning("safety sweep failed", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Detections are scored in FastAPI's sync threadpool, so the broadcaster
    # needs a handle on the loop to schedule sends from off-thread.
    broadcaster.bind_loop(asyncio.get_running_loop())
    sweep = asyncio.create_task(_safety_sweep())
    try:
        yield
    finally:
        sweep.cancel()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Same-origin in development (Vite proxies /api/v1) and in the Docker setup
# (nginx proxies it), so this only matters for a split deployment — the
# frontend on one host, this API on another. Origins are listed rather than
# wildcarded: an API that answers any origin is one any page can call with
# a token it has stolen from somewhere else.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,  # auth is a Bearer header, not a cookie
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],  # the Excel export's filename
)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(devices.router)
app.include_router(patients.router)
app.include_router(attack_types.router)
app.include_router(protocols.router)
app.include_router(system_config.router)
app.include_router(thresholds.router)
app.include_router(blocklist.router)
app.include_router(datasets.router)
app.include_router(audit_logs.router)
app.include_router(ml_models.router)
app.include_router(detections.router)
app.include_router(stats.router)
app.include_router(alerts.router)
app.include_router(vitals.router)
app.include_router(notifications.router)
app.include_router(reports.router)
app.include_router(simulation.router)
app.include_router(enforcement.router)


@app.websocket("/api/v1/ws")
async def live_feed(websocket: WebSocket, token: str = ""):
    """Live detection and alert feed.

    The token arrives as a query parameter because browsers cannot set an
    Authorization header on a WebSocket handshake. It is verified before the
    connection is accepted, so an unauthenticated client never joins the
    fan-out set.
    """
    try:
        decode_access_token(token)
    except ValueError:
        await websocket.close(code=1008)  # policy violation
        return

    await websocket.accept()
    await broadcaster.register(websocket)
    try:
        while True:
            # Nothing is expected from the client; this read is how a
            # disconnect surfaces.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await broadcaster.unregister(websocket)


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "env": settings.env}


@app.get("/api/v1/health/db")
def health_db():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
