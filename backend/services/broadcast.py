"""In-process fan-out of live events to connected WebSocket clients.

The detection pipeline runs in FastAPI's sync threadpool, but WebSocket sends
are async and must happen on the event loop. `publish()` is therefore callable
from any thread: it hands the work to the loop rather than touching a socket
directly. The loop reference is captured at app startup.

This is deliberately in-process and unbuffered — a client that connects late
sees only what happens from then on, and events are not replayed. Anything a
user must not miss is written to the database (alerts, notifications) and read
back over the REST API; the socket is only for the live view.
"""

import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class Broadcaster:
    def __init__(self) -> None:
        self._connections: set = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def listener_count(self) -> int:
        return len(self._connections)

    async def register(self, websocket) -> None:
        self._connections.add(websocket)

    async def unregister(self, websocket) -> None:
        self._connections.discard(websocket)

    async def _fanout(self, event: dict) -> None:
        if not self._connections:
            return
        message = json.dumps(event, default=str)
        dead = []
        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception:
                # A client that vanished mid-send is normal; drop it and move on
                # rather than letting one bad socket stall the whole fan-out.
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)

    def publish(self, event: dict) -> None:
        """Safe to call from a sync request handler or a worker thread."""
        if self._loop is None or not self._connections:
            return
        try:
            self._loop.call_soon_threadsafe(
                lambda: self._loop.create_task(self._fanout(event))
            )
        except RuntimeError:
            # Loop already closed (shutdown in progress) — a dropped live event
            # is never worth failing the request that produced it.
            logger.debug("broadcast dropped: event loop unavailable")


broadcaster = Broadcaster()
