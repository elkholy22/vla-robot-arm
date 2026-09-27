import time
import json
import logging
import asyncio
from typing import Set, Dict, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger("ws_manager")

# WebSocket Connection pools and dynamic loops
connected_clients: Set[WebSocket] = set()
main_loop: Optional[asyncio.AbstractEventLoop] = None
is_shutting_down: bool = False

class ConnectionManager:
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        connected_clients.add(websocket)
        logger.info(f"Client connected: {websocket.client.host if websocket.client else 'Unknown'}")
        
        # Broadcast updated client count to other clients
        await self.broadcast({
            "type": "telemetry",
            "client_count": len(connected_clients)
        })

        # Send full initial telemetry state to the new client
        if controller:
            telemetry_data = controller.get_telemetry_data()
            try:
                await websocket.send_text(json.dumps({
                    "type": "telemetry",
                    "client_count": len(connected_clients),
                    **telemetry_data
                }))
            except Exception:
                pass

    def disconnect(self, websocket: WebSocket):
        if websocket in connected_clients:
            connected_clients.remove(websocket)
            logger.info("Client disconnected.")
            
            # Release lease if held by this client
            if controller and controller.lease:
                client_id = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "Unknown"
                controller.lease.release_lease(client_id)
                
            # Broadcast updated client count to remaining clients
            safe_broadcast({
                "type": "telemetry",
                "client_count": len(connected_clients)
            })

    async def broadcast(self, message: Dict[str, Any]):
        if not connected_clients:
            return
        payload = json.dumps(message)
        disconnected = []
        for connection in connected_clients:
            try:
                await connection.send_text(payload)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

def safe_broadcast(message: Dict[str, Any]):
    if main_loop and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), main_loop)

# -------------------------------------------------------------
# UI Callback Interfaces
# -------------------------------------------------------------
class ServerUICallbacks:
    def __init__(self):
        self.logs = []
        self.log_counter = 0
        self.is_silent = False
        self.last_telemetry = None

    def update_telemetry(self, telemetry_data: Dict[str, Any]):
        self.last_telemetry = telemetry_data
        safe_broadcast({
            "type": "telemetry",
            "client_count": len(connected_clients),
            **telemetry_data
        })

    def log(self, text: str, category: Optional[str] = None):
        if self.is_silent:
            return

        self.log_counter += 1
        log_entry = {"id": self.log_counter, "text": text, "timestamp": time.time()}
        
        self.logs.append(log_entry)
        if len(self.logs) > 50:
            self.logs.pop(0)
            
        logger.info(f"[LOG] {text}")
        
        safe_broadcast({
            "type": "chat_response",
            "text": text,
            "sender": "system",
            "command": "CONSOLE"
        })

    def notify_vla_pending(self, action: Dict[str, Any]):
        safe_broadcast({
            "type": "vla_pending",
            "action": action
        })

    def notify_vla_resolved(self, status: str):
        safe_broadcast({
            "type": "vla_resolved",
            "status": status
        })

    def trigger_vla_inference(self):
        safe_broadcast({
            "type": "vla_inference_trigger"
        })

ui_callbacks = ServerUICallbacks()

# Global Controller & Executor handles (instantiated in main.py)
controller = None
console_executor = None
