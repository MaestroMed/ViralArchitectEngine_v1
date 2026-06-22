"""WebSocket endpoints for real-time updates."""

import asyncio
import json
import logging
from dataclasses import dataclass, field

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from forge_engine.core.auth import authorize_websocket
from forge_engine.core.jobs import Job, JobManager

logger = logging.getLogger(__name__)
router = APIRouter()


# WebSocket message types
class WSMessageType:
    # Outbound (server -> client)
    JOB_UPDATE = "JOB_UPDATE"
    PROJECT_UPDATE = "PROJECT_UPDATE"
    ANALYSIS_PROGRESS = "ANALYSIS_PROGRESS"
    EXPORT_PROGRESS = "EXPORT_PROGRESS"
    SEGMENT_DISCOVERED = "SEGMENT_DISCOVERED"
    TRANSCRIPT_CHUNK = "TRANSCRIPT_CHUNK"
    ERROR = "ERROR"
    PONG = "PONG"
    SUBSCRIBED = "SUBSCRIBED"

    # Inbound (client -> server)
    PING = "ping"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"


@dataclass
class WSClient:
    """Represents a connected WebSocket client."""
    websocket: WebSocket
    subscriptions: set[str] = field(default_factory=set)  # Channels subscribed to
    project_id: str | None = None  # Current project context


class ConnectionManager:
    """Enhanced WebSocket connection manager with channels."""

    def __init__(self):
        self.clients: dict[WebSocket, WSClient] = {}
        self.job_manager = JobManager.get_instance()
        self._listening = False

    @property
    def active_connections(self) -> list[WebSocket]:
        """Backwards compatibility."""
        return list(self.clients.keys())

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.clients[websocket] = WSClient(websocket=websocket)
        logger.info(f"Client connected. Total: {len(self.clients)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.clients:
            del self.clients[websocket]
            logger.info(f"Client disconnected. Total: {len(self.clients)}")

    async def subscribe(self, websocket: WebSocket, channel: str):
        """Subscribe a client to a channel."""
        if websocket in self.clients:
            self.clients[websocket].subscriptions.add(channel)
            await websocket.send_json({
                "type": WSMessageType.SUBSCRIBED,
                "channel": channel
            })
            logger.debug(f"Client subscribed to {channel}")

    async def unsubscribe(self, websocket: WebSocket, channel: str):
        """Unsubscribe a client from a channel."""
        if websocket in self.clients:
            self.clients[websocket].subscriptions.discard(channel)

    async def set_project_context(self, websocket: WebSocket, project_id: str):
        """Set the project context for a client."""
        if websocket in self.clients:
            self.clients[websocket].project_id = project_id
            # Auto-subscribe to project channel
            await self.subscribe(websocket, f"project:{project_id}")

    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        if not self.clients:
            return

        disconnected = []
        for ws in self.clients:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)

        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_to_channel(self, channel: str, message: dict):
        """Send message only to clients subscribed to a channel."""
        if not self.clients:
            return

        disconnected = []
        for ws, client in self.clients.items():
            if channel in client.subscriptions:
                try:
                    await ws.send_json(message)
                except Exception:
                    disconnected.append(ws)

        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_to_project(self, project_id: str, message: dict):
        """Send message to clients watching a specific project."""
        channel = f"project:{project_id}"
        await self.broadcast_to_channel(channel, message)

    async def send_analysis_progress(
        self,
        project_id: str,
        stage: str,
        progress: float,
        message: str,
        data: dict | None = None
    ):
        """Send analysis progress update."""
        payload = {
            "type": WSMessageType.ANALYSIS_PROGRESS,
            "payload": {
                "project_id": project_id,
                "stage": stage,
                "progress": progress,
                "message": message,
                "data": data or {}
            }
        }
        await self.broadcast_to_project(project_id, payload)

    async def send_transcript_chunk(
        self,
        project_id: str,
        text: str,
        start_time: float,
        end_time: float,
        is_final: bool = False
    ):
        """Send transcript chunk as it's being generated."""
        payload = {
            "type": WSMessageType.TRANSCRIPT_CHUNK,
            "payload": {
                "project_id": project_id,
                "text": text,
                "start_time": start_time,
                "end_time": end_time,
                "is_final": is_final
            }
        }
        await self.broadcast_to_project(project_id, payload)

    async def send_segment_discovered(
        self,
        project_id: str,
        segment_data: dict
    ):
        """Send notification when a new segment is discovered."""
        payload = {
            "type": WSMessageType.SEGMENT_DISCOVERED,
            "payload": {
                "project_id": project_id,
                "segment": segment_data
            }
        }
        await self.broadcast_to_project(project_id, payload)

    async def handle_message(self, websocket: WebSocket, data: str):
        """Handle incoming WebSocket message."""
        try:
            message = json.loads(data)
            msg_type = message.get("type", "").lower()

            if msg_type == WSMessageType.PING:
                await websocket.send_json({"type": WSMessageType.PONG})

            elif msg_type == WSMessageType.SUBSCRIBE:
                channel = message.get("channel")
                if channel:
                    await self.subscribe(websocket, channel)

            elif msg_type == WSMessageType.UNSUBSCRIBE:
                channel = message.get("channel")
                if channel:
                    await self.unsubscribe(websocket, channel)

            else:
                logger.debug(f"Unknown message type: {msg_type}")

        except json.JSONDecodeError:
            # Simple text message, treat as ping
            if data.lower() == "ping":
                await websocket.send_text("pong")


manager = ConnectionManager()


# Store reference to main event loop for thread-safe access
_main_loop: asyncio.AbstractEventLoop = None

def set_main_loop(loop: asyncio.AbstractEventLoop):
    """Set the main event loop for thread-safe callbacks."""
    global _main_loop
    _main_loop = loop
    logger.info("WebSocket main loop registered")


# Hook into JobManager to broadcast updates
def job_update_listener(job: Job):
    """Callback triggered by JobManager when a job updates."""
    message = {
        "type": "JOB_UPDATE",
        "payload": job.to_dict()
    }

    # Try to get the running loop first (if we're in main thread)
    try:
        loop = asyncio.get_running_loop()
        logger.debug("Broadcasting job update (main thread): %s - %.1f%%", job.id[:8], job.progress)
        loop.create_task(manager.broadcast(message))
        return
    except RuntimeError:
        pass

    # We're in a worker thread - use the stored main loop
    if _main_loop and _main_loop.is_running():
        logger.debug("Broadcasting job update (from thread): %s - %.1f%%", job.id[:8], job.progress)
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), _main_loop)
    else:
        logger.warning("Cannot broadcast job update: no main loop available")


def broadcast_project_update(project_data: dict):
    """Broadcast project status change to all connected clients."""
    message = {
        "type": "PROJECT_UPDATE",
        "payload": project_data
    }

    # Try to get the running loop first (if we're in main thread)
    try:
        loop = asyncio.get_running_loop()
        logger.info("Broadcasting project update: %s -> %s", project_data.get("id", "?")[:8], project_data.get("status", "?"))
        loop.create_task(manager.broadcast(message))
        return
    except RuntimeError:
        pass

    # We're in a worker thread - use the stored main loop
    if _main_loop and _main_loop.is_running():
        logger.info("Broadcasting project update (from thread): %s -> %s", project_data.get("id", "?")[:8], project_data.get("status", "?"))
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), _main_loop)
    else:
        logger.warning("Cannot broadcast project update: no main loop available")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Gate the handshake before accepting (no-op when auth is off). Closing
    # pre-accept rejects the upgrade; the iOS/web clients pass the key as
    # `?key=` (and the X-API-Key header as a fallback). See core/auth.py.
    if not await authorize_websocket(websocket):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            await manager.handle_message(websocket, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.websocket("/ws/project/{project_id}")
async def project_websocket(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for project-specific updates."""
    if not await authorize_websocket(websocket):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await manager.connect(websocket)
    await manager.set_project_context(websocket, project_id)

    try:
        while True:
            data = await websocket.receive_text()
            await manager.handle_message(websocket, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.websocket("/ws/job/{job_id}")
async def job_websocket(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for job-specific updates."""
    if not await authorize_websocket(websocket):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await manager.connect(websocket)
    await manager.subscribe(websocket, f"job:{job_id}")

    try:
        while True:
            data = await websocket.receive_text()
            await manager.handle_message(websocket, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Helper functions for broadcasting from services
async def broadcast_analysis_progress(
    project_id: str,
    stage: str,
    progress: float,
    message: str,
    data: dict | None = None
):
    """Broadcast analysis progress from services."""
    await manager.send_analysis_progress(project_id, stage, progress, message, data)


async def broadcast_transcript_chunk(
    project_id: str,
    text: str,
    start_time: float,
    end_time: float,
    is_final: bool = False
):
    """Broadcast transcript chunk from transcription service."""
    await manager.send_transcript_chunk(project_id, text, start_time, end_time, is_final)


async def broadcast_segment_discovered(project_id: str, segment_data: dict):
    """Broadcast new segment discovery."""
    await manager.send_segment_discovered(project_id, segment_data)




