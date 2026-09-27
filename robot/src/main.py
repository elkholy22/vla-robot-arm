import os
import socket
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import custom modules
from core.config_loader import load_config
from hardware.camera_manager import camera_manager
from control.arm_controller import ArmController
from commands.console_cmd import ConsoleCmdExecutor

# Import connection manager and api router
import control.ws_manager as ws_m
from control.api import router as api_router

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

# Helper to retrieve local IP addresses
def print_local_ips(port: int):
    ips = []
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        if local_ip not in ips and not local_ip.startswith("127."):
            ips.append(local_ip)
    except Exception:
        pass

    logger.info("=" * 60)
    logger.info("Robot Server Interface active!")
    if ips:
        logger.info("Local network access url(s):")
        for ip in ips:
            logger.info(f"  http://{ip}:{port}/")
    else:
        logger.info(f"Local host url: http://localhost:{port}/")
    logger.info("=" * 60)

# -------------------------------------------------------------
# FastAPI Lifecycle
# -------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    ws_m.main_loop = asyncio.get_event_loop()
    
    import signal
    original_sigint = signal.getsignal(signal.SIGINT)
    original_sigterm = signal.getsignal(signal.SIGTERM)
    
    def exit_handler(signum, frame):
        if ws_m.is_shutting_down:
            logger.warning(f"Signal {signum} caught during shutdown. Forcing immediate termination.")
            os._exit(1)
        logger.info(f"Signal {signum} caught. Setting shutdown flag immediately.")
        ws_m.is_shutting_down = True
        
        # Instantly stop all motors upon receiving the shutdown signal
        if ws_m.controller and ws_m.controller.arm:
            try:
                logger.info("Signal caught: instantly stopping all motors before homing.")
                ws_m.controller.arm.stop_all()
            except Exception as e:
                logger.error(f"Failed to instantly stop motors in exit handler: {e}")

        if signum == signal.SIGINT and callable(original_sigint):
            original_sigint(signum, frame)
        elif signum == signal.SIGTERM and callable(original_sigterm):
            original_sigterm(signum, frame)
            
    try:
        signal.signal(signal.SIGINT, exit_handler)
        signal.signal(signal.SIGTERM, exit_handler)
    except ValueError:
        pass

    # Initialize controller and executor and register to ws_manager module
    ws_m.controller = ArmController(ui_callback=ws_m.ui_callbacks)
    ws_m.console_executor = ConsoleCmdExecutor(
        arm=ws_m.controller.arm,
        ui=ws_m.ui_callbacks,
        vla_manager=ws_m.controller.vla,
        lease_manager=ws_m.controller.lease,
        controller=ws_m.controller
    )
    
    config = load_config()
    print_local_ips(config["network"]["web_ui_port"])
    
    yield
    
    # Set the shutting down flag to exit video streams gracefully
    ws_m.is_shutting_down = True
    
    # Close all active WebSockets immediately
    if ws_m.connected_clients:
        logger.info(f"Closing {len(ws_m.connected_clients)} active WebSocket connection(s)...")
        for ws in list(ws_m.connected_clients):
            try:
                await ws.close(code=1001, reason="Server shutting down")
            except Exception:
                pass
        ws_m.connected_clients.clear()

    logger.info("Stopping all camera reader threads...")
    camera_manager.stop_all()
    if ws_m.controller:
        ws_m.controller.shutdown()

app = FastAPI(title="Robotic Arm UI Server Gateway", lifespan=lifespan)

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom static files loader to bypass browser caching
class NoCacheStaticFiles(StaticFiles):
    def is_not_modified(self, response_headers, request_headers) -> bool:
        return False
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

# Register APIRouter
app.include_router(api_router)

# -------------------------------------------------------------
# Static File Mounting
# -------------------------------------------------------------
frontend_build_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "build")
if os.path.exists(frontend_build_dir):
    logger.info(f"Mounting production frontend build from {frontend_build_dir}")
    app.mount("/", NoCacheStaticFiles(directory=frontend_build_dir, html=True), name="frontend")
else:
    logger.warning(f"Static files build not found at {frontend_build_dir}! Run buildHat UI build scripts first.")

def run_server():
    import uvicorn
    config = load_config()
    uvicorn.run(
        app,
        host=config["network"]["host"],
        port=config["network"]["web_ui_port"],
        log_level="info",
        timeout_graceful_shutdown=5,
        access_log=False
    )

if __name__ == "__main__":
    run_server()
