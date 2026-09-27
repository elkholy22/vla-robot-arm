import os
import glob
import asyncio
import pickle
import logging
import json
import shutil

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Response, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
import tarfile
from datetime import datetime

from core.config_loader import load_config
from hardware.camera_manager import camera_manager
import control.ws_manager as ws_m

logger = logging.getLogger("api")
router = APIRouter()

# -------------------------------------------------------------
# WebSocket Control Endpoint
# -------------------------------------------------------------
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_m.manager.connect(websocket)
    client_id = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "Unknown"
    
    # Push initial connection status and cache list of logs
    for log_entry in ws_m.ui_callbacks.logs:
        try:
            await websocket.send_text(json.dumps({
                "type": "chat_response",
                "text": log_entry["text"],
                "sender": "system",
                "command": "CONSOLE"
            }))
        except Exception:
            pass

    try:
        while True:
            data = await websocket.receive_text()
            data = data.strip()
            if not data:
                continue

            # Check if JSON payload or simple command string
            try:
                msg = json.loads(data)
                msg_type = msg.get("type")
                if msg_type == "console":
                    command_text = msg.get("value", "").strip()
                    silent = msg.get("silent", False)
                    if ws_m.console_executor:
                        ws_m.console_executor.exec_cmd(command_text, client_id, silent=silent)
                elif msg_type == "vla_register":
                    agent_id = msg.get("agent_id", "vla_agent_1")
                    agent_name = msg.get("name", "VLA Client")
                    options = msg.get("options", {})
                    if ws_m.controller:
                        ws_m.controller.vla.register_agent(agent_id, agent_name, options)
                elif msg_type == "vla_action":
                    agent_id = msg.get("agent_id", "vla_agent_1")
                    target_pos = msg.get("target_positions", [])
                    target_vels = msg.get("target_velocities", [])
                    if ws_m.controller:
                        success, message = ws_m.controller.vla.handle_inference_action(agent_id, target_pos, target_vels)
                        await websocket.send_text(json.dumps({
                            "type": "vla_action_ack",
                            "success": success,
                            "message": message
                        }))
            except json.JSONDecodeError:
                if ws_m.console_executor:
                    ws_m.console_executor.exec_cmd(data, client_id)
                    
    except WebSocketDisconnect:
        ws_m.manager.disconnect(websocket)

# -------------------------------------------------------------
# Camera Feed Endpoint
# -------------------------------------------------------------
async def gen_video_frames(slot_idx: int):
    try:
        while not ws_m.is_shutting_down:
            frame_bytes = camera_manager.get_frame(slot_idx)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            await asyncio.sleep(0.033)
    except asyncio.CancelledError:
        pass
    except Exception:
        pass

class GracefulStreamingResponse(StreamingResponse):
    async def __call__(self, scope, receive, send) -> None:
        try:
            await super().__call__(scope, receive, send)
        except (asyncio.CancelledError, Exception):
            pass

@router.get("/video_feed/{slot_idx}")
def video_feed(slot_idx: int):
    return GracefulStreamingResponse(
        gen_video_frames(slot_idx),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# -------------------------------------------------------------
# Dataset Manager APIs
# -------------------------------------------------------------
def validate_episode_id(episode_id: str):
    if episode_id == "tmp_downloads" or not all(c.isalnum() or c in ('-', '_') for c in episode_id):
        raise HTTPException(status_code=400, detail="Invalid episode ID")

@router.get("/api/datasets")
def list_datasets():
    """Retrieve list of all recorded dataset folders."""
    config = load_config()
    save_dir = config["recording"]["save_directory"]
    if not os.path.exists(save_dir):
        return []
    
    datasets = []
    for d in sorted(os.listdir(save_dir)):
        if d == "tmp_downloads" or d.startswith("."):
            continue
        d_path = os.path.join(save_dir, d)
        if os.path.isdir(d_path):
            meta_path = os.path.join(d_path, "metadata.json")
            meta = {}
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r") as f:
                        meta = json.load(f)
                except Exception:
                    pass
            
            step_files = glob.glob(os.path.join(d_path, "step_*.pkl"))
            step_count = len(step_files)
            
            datasets.append({
                "id": d,
                "goal_text": meta.get("goal_text", "No prompt"),
                "start_time": meta.get("start_time", "Unknown"),
                "task_id": meta.get("task_id", ""),
                "step_count": step_count
            })
    return sorted(datasets, key=lambda x: x["start_time"], reverse=True)

@router.get("/api/dataset/{episode_id}")
def get_dataset_details(episode_id: str):
    """Retrieve details and total step counts of a specific dataset episode."""
    validate_episode_id(episode_id)
    config = load_config()
    save_dir = config["recording"]["save_directory"]
    ep_path = os.path.join(save_dir, episode_id)
    
    if not os.path.exists(ep_path) or not os.path.isdir(ep_path):
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    meta_path = os.path.join(ep_path, "metadata.json")
    meta = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)
        except Exception:
            pass
            
    step_files = glob.glob(os.path.join(ep_path, "step_*.pkl"))
    step_count = len(step_files)
    
    return {
        "id": episode_id,
        "metadata": meta,
        "step_count": step_count
    }

@router.get("/api/dataset/{episode_id}/step/{step_id}/image/{camera_id}")
def get_dataset_step_image(episode_id: str, step_id: int, camera_id: int):
    """Read a specific camera frame from the pickled step file and return it as a JPEG."""
    validate_episode_id(episode_id)
    config = load_config()
    save_dir = config["recording"]["save_directory"]
    step_file = os.path.join(save_dir, episode_id, f"step_{step_id:05d}.pkl")
    
    if not os.path.exists(step_file):
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found in episode {episode_id}")
        
    try:
        with open(step_file, "rb") as f:
            step_data = pickle.load(f)
            
        state = step_data.get("state", {})
        camera_frames = state.get("camera_frames", [])
        
        if camera_id >= len(camera_frames):
            from hardware.camera_manager import generate_placeholder_frame
            placeholder = generate_placeholder_frame(camera_id)
            return Response(content=placeholder, media_type="image/jpeg")
            
        frame = camera_frames[camera_id]
        
        if isinstance(frame, bytes):
            return Response(content=frame, media_type="image/jpeg")
            
        import cv2
        ret, jpeg = cv2.imencode('.jpg', frame)
        if not ret:
            raise HTTPException(status_code=500, detail="Failed to encode frame")
            
        return Response(content=jpeg.tobytes(), media_type="image/jpeg")
    except Exception as e:
        logger.exception("Failed to load step image")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/dataset/{episode_id}/step/{step_id}/telemetry")
def get_dataset_step_telemetry(episode_id: str, step_id: int):
    """Retrieve non-image telemetry data from a step pickle."""
    validate_episode_id(episode_id)
    config = load_config()
    save_dir = config["recording"]["save_directory"]
    step_file = os.path.join(save_dir, episode_id, f"step_{step_id:05d}.pkl")
    
    if not os.path.exists(step_file):
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found")
        
    try:
        with open(step_file, "rb") as f:
            step_data = pickle.load(f)
            
        if "state" in step_data and "camera_frames" in step_data["state"]:
            del step_data["state"]["camera_frames"]
            
        return step_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/dataset/{episode_id}")
def delete_dataset(episode_id: str):
    """Delete a recorded dataset episode folder."""
    validate_episode_id(episode_id)
    config = load_config()
    save_dir = config["recording"]["save_directory"]
    ep_path = os.path.join(save_dir, episode_id)
    
    if not os.path.exists(ep_path) or not os.path.isdir(ep_path):
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    try:
        shutil.rmtree(ep_path)
        logger.info(f"Deleted dataset episode: {episode_id}")
        return {"status": "success", "message": f"Episode {episode_id} deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def remove_file(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.error(f"Failed to remove temp file {path}: {e}")

@router.get("/api/dataset/{episode_id}/download")
def download_episode(episode_id: str, background_tasks: BackgroundTasks):
    """Tar and download a single dataset episode."""
    validate_episode_id(episode_id)
    config = load_config()
    save_dir = config["recording"]["save_directory"]
    ep_path = os.path.join(save_dir, episode_id)
    
    if not os.path.exists(ep_path) or not os.path.isdir(ep_path):
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    tmp_dir = os.path.join(save_dir, "tmp_downloads")
    os.makedirs(tmp_dir, exist_ok=True)
    tar_path = os.path.join(tmp_dir, f"{episode_id}.tar.gz")
    
    try:
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(ep_path, arcname=episode_id)
            
        background_tasks.add_task(remove_file, tar_path)
        return FileResponse(
            path=tar_path,
            filename=f"{episode_id}.tar.gz",
            media_type="application/gzip"
        )
    except Exception as e:
        logger.exception(f"Failed to package episode {episode_id}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/heatmap_output/switch_position_kde.png")
def get_heatmap():
    """Serve the global switch position KDE heatmap PNG."""
    # The heatmap is stored relative to the robot/src/ directory
    heatmap_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "heatmap_output", "switch_position_kde.png")
    
    if not os.path.exists(heatmap_path):
        raise HTTPException(status_code=404, detail="Heatmap not found. Run capturing first.")
    
    return FileResponse(
        path=heatmap_path,
        filename="switch_position_kde.png",
        media_type="image/png"
    )

@router.get("/api/datasets/download")
def download_all_episodes(background_tasks: BackgroundTasks):
    """Tar and download all dataset episodes combined."""
    config = load_config()
    save_dir = config["recording"]["save_directory"]
    
    if not os.path.exists(save_dir) or not os.path.isdir(save_dir):
        raise HTTPException(status_code=404, detail="No recorded data found")
        
    # Find all directories that aren't tmp_downloads
    dirs = [d for d in os.listdir(save_dir) if os.path.isdir(os.path.join(save_dir, d)) and d != "tmp_downloads"]
    if not dirs:
        raise HTTPException(status_code=404, detail="No episodes found to download")
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_dir = os.path.join(save_dir, "tmp_downloads")
    os.makedirs(tmp_dir, exist_ok=True)
    tar_filename = f"all_episodes_{timestamp}.tar.gz"
    tar_path = os.path.join(tmp_dir, tar_filename)
    
    try:
        with tarfile.open(tar_path, "w:gz") as tar:
            for d in dirs:
                tar.add(os.path.join(save_dir, d), arcname=d)
                
        background_tasks.add_task(remove_file, tar_path)
        return FileResponse(
            path=tar_path,
            filename=tar_filename,
            media_type="application/gzip"
        )
    except Exception as e:
        logger.exception("Failed to package all episodes")
        raise HTTPException(status_code=500, detail=str(e))
