import asyncio
import json
import sys
import os
import websockets
import time
import urllib.request

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.classes import RobotState, GoalMessage, ModelMode
from model.wrapper import OctoWrapper

WEBUI_IP = os.environ.get("WEBUI_IP", "localhost")   # web UI host
WS_PORT = 9000
CHECKPOINT = "/home/lego-team-1/finetune_output/20260711_1733_base_aug_full_w1"
STEP = 44999
GOAL = "flip the switch from green to red"
AGENT_ID = "vla_agent_1"
URDF_PATH = os.path.join(os.path.dirname(__file__), "..", "pi", "zeroshot_prototype.xml")
JOINT_ORDER = ["A", "B", "C",]
#RHC (Receding Horizon Control) parameters
EXEC_HORIZON = 8       # steps to execute per inference (try 5, 8, 15). Higher=smoother but less correction; lower=more correction but riskier replanning noise.
STEP_DELAY = 0.3       # seconds to wait between moveee commands (arm+camera catch-up). Increase if arm can't keep up.
MAX_TOTAL_STEPS = 200  # safety abort: stop continuous RHC after this many total steps (prevents infinite loop)


def fetch_frame(url, timeout=2.0):
    """Grab one raw JPEG frame (bytes) from an MJPEG HTTP stream.
    Returns JPEG bytes (what _preprocess expects) or None.
    The web UI streams multipart/x-mixed-replace with JPEG frames separated by
    boundaries; we read until we find one complete JPEG (FFD8...FFD9)."""
    try:
        stream = urllib.request.urlopen(url, timeout=timeout)
        buf = b""
        while True:
            chunk = stream.read(1024)
            if not chunk:
                break
            buf += chunk
            start = buf.find(b'\xff\xd8')   # JPEG start marker
            end = buf.find(b'\xff\xd9')     # JPEG end marker
            if start != -1 and end != -1 and end > start:
                jpeg = buf[start:end + 2]   # one complete JPEG
                stream.close()
                return jpeg                  # raw JPEG bytes
        stream.close()
        return None
    except Exception as e:
        print(f"fetch_frame error: {e}")
        return None

def ee_position_to_list(ee: dict):
    """Convert telemetry ee_position {"x":.., "y":.., "z":..} to [x, y, z] float
    list. This is the CARTESIAN end-effector position (meters) that the model's
    proprio was trained on - NOT the joint angles."""
    return [float(ee["x"]), float(ee["y"]), float(ee["z"])]


def angles_list(angles: dict):
    
    return [float(angles[j]) for j in JOINT_ORDER]


def load_policy(octo_mode, step, checkpoint, action_gain, task_type, use_wrist, goal, window_size, action_horizon):
    """Load model + URDF + goal SYNCHRONOUSLY (outside asyncio). Orbax checkpoint
    loading calls asyncio.run() internally, which conflicts with a running loop."""
    print(f"Loading OctoWrapper from {checkpoint} (mode={octo_mode}, step={step}, "
          f"gain={action_gain}, task={task_type}, wrist={use_wrist}, window_size={window_size})...")
    policy = OctoWrapper(
        checkpoint, octo_mode,
        action_gain=action_gain, tasktype=task_type, usewrist=use_wrist, step=step,
        window_size=window_size, action_horizon=action_horizon,
    )
    policy.initialize()

    try:
        with open(URDF_PATH, "r") as f:
            urdf_content = f.read()
        policy.ik_solver.load_urdf_from_string(urdf_content)
        print(f"Loaded URDF from {URDF_PATH}")
    except FileNotFoundError:
        print(f"WARNING: URDF not found at {URDF_PATH} - IK will not work.")

    policy.set_goal(GoalMessage(
        text_prompt=goal, goal_image=None, task_id="manual", is_update=True))
    return policy


async def vla_loop(policy, webui_ip=WEBUI_IP, use_wrist=True):
    ws_url = f"ws://{webui_ip}:{WS_PORT}/ws"
    video_primary = f"http://{webui_ip}:{WS_PORT}/video_feed/0"
    video_wrist   = f"http://{webui_ip}:{WS_PORT}/video_feed/1"

    print(f"Connecting to {ws_url}...")
    async with websockets.connect(ws_url) as ws:
        print("Connected. Registering VLA agent...")
        await ws.send(json.dumps({
            "type": "vla_register", "agent_id": AGENT_ID,
            "name": "Octo VLA", "options": {},
        }))
        # default mode is "block" all actions rejected. Set to auto.
        await ws.send(json.dumps({"type": "console", "value": "vla_mode auto"}))
        print("Sent vla_register + vla_mode auto. Waiting for telemetry/triggers...")
 
        latest_angles = None
        latest_ee = None
 
        while True:
            try:
                raw = await ws.recv()
            except websockets.ConnectionClosed:
                print("WebSocket closed.")
                break
 
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
 
            mtype = data.get("type")
 
            if mtype == "telemetry":
                a = data.get("angles")
                if a:
                    latest_angles = a          # [joint degrees]
                ee = data.get("ee_position")
                if ee:
                    latest_ee = ee             # Cartesian meters (PROPRIO)
                    print(f"[TELEM] angles={data.get('angles')} ee={data.get('ee_position')}")
 
            elif mtype == "vla_inference_trigger":
                if latest_ee is None:
                    print("Trigger received but no ee_position yet; skipping.")
                    continue

                # RHC: continuous receding-horizon control
                # One trigger starts a continuous loop: infer ,execute the
                # first EXEC_HORIZON steps (accumulating deltas as absolute
                # moveee targets) to re-infer with fresh camera + ee to repeat,
                # until MAX_TOTAL_STEPS or the connection drops.
                print(f"[RHC] Trigger received. Starting continuous control "
                      f"(exec_horizon={EXEC_HORIZON}, delay={STEP_DELAY}s, max={MAX_TOTAL_STEPS}).")
                total_steps = 0

                while total_steps < MAX_TOTAL_STEPS:
                    # ---- fetch fresh observation for this inference ----
                    frame_p = fetch_frame(video_primary)
                    frame_w = fetch_frame(video_wrist) if use_wrist else None
                    if frame_p is None:
                        print("Primary frame fetch failed; aborting RHC.")
                        break
                    cameras = [frame_p]
                    if use_wrist and frame_w is not None:
                        cameras.append(frame_w)

                    proprio = [float(latest_angles["C"]), float(latest_angles["B"]), float(latest_angles["A"])]
                    state = RobotState(
                        motor_positions=proprio,
                        camera_frames=cameras,
                        timestamp=time.time(),
                    )

                    print(f"[RHC] Inferencing at total_step={total_steps} "
                          f"(ee={latest_ee}, proprio={[round(p,3) for p in proprio]})...")
                    command = policy.predict_action(state)
                    deltas = command.target_positions   # list of [dx, dy, dz], len=action_horizon

                    # ---- execute the first EXEC_HORIZON steps, accumulating ----
                    # Start from the current (fresh) ee position; each delta moves
                    # relative to the previous target (Octo actions are per-step deltas).
                    cur_x = float(latest_ee["x"])
                    cur_y = float(latest_ee["y"])
                    cur_z = float(latest_ee["z"])

                    n_exec = min(EXEC_HORIZON, len(deltas))
                    for i in range(n_exec):
                        d = deltas[i]
                        cur_x += d[0]
                        cur_y += d[1]
                        cur_z += d[2]
                        await ws.send(f"moveee {cur_x:.4f} {cur_y:.4f} {cur_z:.4f} 0.5")
                        print(f"[RHC]  step {total_steps} moveee=[{cur_x:.4f},{cur_y:.4f},{cur_z:.4f}] "
                              f"delta={[round(v,4) for v in d]}")
                        total_steps += 1

                        # wait for arm+camera to catch up, while draining any
                        # incoming telemetry so latest_ee/latest_angles stay fresh
                        drain_until = time.time() + STEP_DELAY
                        while time.time() < drain_until:
                            try:
                                raw2 = await asyncio.wait_for(ws.recv(), timeout=0.05)
                                data2 = json.loads(raw2)
                                if data2.get("type") == "telemetry":
                                    a2 = data2.get("angles")
                                    if a2:
                                        latest_angles = a2
                                    ee2 = data2.get("ee_position")
                                    if ee2:
                                        latest_ee = ee2
                            except (asyncio.TimeoutError, json.JSONDecodeError):
                                pass
                            except websockets.ConnectionClosed:
                                print("WebSocket closed during RHC.")
                                return

                        if total_steps >= MAX_TOTAL_STEPS:
                            break

                print(f"[RHC] Finished continuous control after {total_steps} steps.")
                # ===== END RHC =====
 
            elif mtype == "vla_action_ack":
                print(f"Action ack: success={data.get('success')} msg={data.get('message')}")
 
 
if __name__ == "__main__":
    octo_mode = ModelMode.FINETUNED
    step = STEP
    webui_ip = WEBUI_IP
    checkpoint = CHECKPOINT
    action_gain = 2.0
    task_type = 1
    use_wrist = True
    window_size = 1
    action_horizon = 50 
 
    # model mode
    try:
        ui = input("Use Octo Small/Base/Finetuned? (s/b/enter=finetuned): ").strip().lower()
        if ui == 's':
            octo_mode = ModelMode.SMALL
        elif ui == 'b':
            octo_mode = ModelMode.BASE
    except EOFError:
        pass
 
    # checkpoint path + step only relevant for finetuned
    if octo_mode == ModelMode.FINETUNED:
        try:
            ui = input(f"Checkpoint path? (enter={CHECKPOINT}): ").strip()
            if ui:
                checkpoint = ui
        except EOFError:
            pass
        try:
            ui = input(f"Checkpoint step? (enter={STEP}): ").strip()
            if ui:
                step = int(ui)
        except (EOFError, ValueError):
            pass
 
    # action gain
    try:
        ui = input("Action gain factor? (enter=2.0): ").strip()
        if ui:
            action_gain = float(ui)
    except (EOFError, ValueError):
        pass
 
    # task type
    try:
        ui = input("Task type? (1=text/2=image/enter=1): ").strip()
        if ui in ("1", "2"):
            task_type = int(ui)
    except EOFError:
        pass
 
    # wrist cam
    try:
        ui = input("Use wrist cam? (y/n/enter=yes): ").strip().lower()
        if ui == 'n':
            use_wrist = False
        elif ui == 'y':
            use_wrist = True
    except EOFError:
        pass
# window size (MUST match the value the model was finetuned with)
    try:
        ui = input(f"Window size? (must match training; enter={window_size}): ").strip()
        if ui:
            window_size = int(ui)
    except (EOFError, ValueError):
        pass

    # action horizon (MUST match the value the model was finetuned with)
    try:
        ui = input(f"Action horizon? (must match training; enter={action_horizon}): ").strip()
        if ui:
            action_horizon = int(ui)
    except (EOFError, ValueError):
        pass
    # web UI IP
    try:
        ui = input(f"Web UI IP? (enter={WEBUI_IP}): ").strip()
        if ui:
            webui_ip = ui
    except EOFError:
        pass
 
    # goal / instruction (must match the dataset's training instruction!)
    goal = GOAL
    try:
        print(f"Current goal is: '{GOAL}'")
        ui = input("Use this goal? (y/n/enter=yes): ").strip().lower()
        if ui == 'n':
            new_goal = input("Enter new goal: ").strip()
            if new_goal:
                goal = new_goal
                print(f"Goal set to: '{goal}'")
            else:
                print(f"No input; keeping default: '{goal}'")
    except EOFError:
        pass
 
    policy = load_policy(octo_mode, step, checkpoint, action_gain,
                         task_type, use_wrist, goal, window_size, action_horizon)
    asyncio.run(vla_loop(policy, webui_ip=webui_ip, use_wrist=use_wrist))