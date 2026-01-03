"""WebSocket endpoints for real-time updates."""

import logging
import json
import asyncio
from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from forge_engine.core.jobs import Job, JobManager

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.job_manager = JobManager.get_instance()
        self._listening = False

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total: {len(self.active_connections)}")
        
        # Start listening to job updates if not already
        if not self._listening:
            self._listening = True
            # Register global listener
            # Note: JobManager implementation needs to support a global listener or we iterate
            # For now, let's assume we can hook into _notify_listeners
            # But since JobManager is singleton, we can just patch/add a listener
            pass # We'll handle this by polling or hooking in JobManager

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        if not self.active_connections:
            return
            
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)


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
    await manager.connect(websocket)
    
    # Register listener if first connection (idempotent)
    # Ideally this should be done once at startup, but here works too
    job_mgr = JobManager.get_instance()
    # We need a way to add a 'global' listener to JobManager
    # Currently it supports listener by job_id. 
    # Let's modify JobManager to support global listeners.
    
    try:
        while True:
            # Keep connection alive / handle incoming messages if needed
            data = await websocket.receive_text()
            # We can handle ping/pong here
    except WebSocketDisconnect:
        manager.disconnect(websocket)




