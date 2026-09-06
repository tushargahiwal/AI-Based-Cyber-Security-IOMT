import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from sqlalchemy import text

from config import settings
from database import engine
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Detections are scored in FastAPI's sync threadpool, so the broadcaster
    # needs a handle on the loop to schedule sends from off-thread.
    broadcaster.bind_loop(asyncio.get_running_loop())
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
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
