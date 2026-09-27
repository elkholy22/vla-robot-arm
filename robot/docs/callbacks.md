# Server UI Callbacks Architecture

The robot server uses an asynchronous, thread-safe callback system to bridge the gap between real-time background threads (hardware loops, monitoring, and command parsing) and the FastAPI WebSocket connection pool.

---

## The Thread-Safety Challenge

The FastAPI web server runs on an asynchronous event loop (`asyncio`). However, the robot driver runs its own background threads:
1. **Hardware Loop (`BaseRobotArm._hardware_loop`)**: Runs at 100Hz to calculate positions, check stalls, and write PWM values to motors.
2. **Monitoring Loop (`ArmController._monitor_loop`)**: Runs at 10Hz to sample telemetry, manage recording state, and broadcast updates.
3. **Command Execution Threads**: Spanned by `ConsoleCmdExecutor` to execute safety and movement commands in parallel, preventing UI lags.

Because synchronous background threads cannot directly call asynchronous methods (`await websocket.send_text(...)`), a bridge is required to safely schedule async coroutines on the main thread's event loop.

---

## Architecture Flow

```mermaid
sequenceDiagram
    participant HW as "Hardware Thread"
    participant Callback as "ServerUICallbacks (Sync)"
    participant Loop as "FastAPI Event Loop"
    participant WS as "WebSocket Clients"

    HW->>Callback: update_telemetry(data)
    Note over Callback: Prepare JSON payload
    Callback->>Loop: asyncio.run_coroutine_threadsafe()
    Note over Loop: Execute coroutine in main loop
    Loop->>WS: manager.broadcast(message)
```

---

## Implementation Details

### Event Loop Capturing
During FastAPI startup (in `main.py`), the running event loop is registered inside the `ws_manager` module:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Capture the main ASGI running event loop
    ws_m.main_loop = asyncio.get_event_loop()
    ...
```

### Thread-Safe Dispatching: Why `run_coroutine_threadsafe`?
In Python's `asyncio` architecture, event loops are not thread-safe. Attempting to call `asyncio.create_task()` or directly invoking coroutines from an external thread (like the 100Hz hardware loop or the 10Hz monitor loop) will raise a fatal exception:
`RuntimeError: Task attached to a different loop` or result in silent corruption of socket frames.

The `safe_broadcast` helper solves this by using `asyncio.run_coroutine_threadsafe`, which thread-safely queues the coroutine into the main ASGI event loop's wakeup queue:

```python
def safe_broadcast(message: Dict[str, Any]):
    if main_loop and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), main_loop)
```

---

## Connection Pool Resiliency & Pruning

When broadcasting high-frequency data ($10\text{Hz}$ telemetry and logs), client network connections can abruptly drop due to closed tabs, network timeouts, or wireless packet loss. 

If a broken socket raises an `OSError` or `WebSocketDisconnect` during broadcast, an unhandled exception would crash the callback and potentially propagate back to the calling hardware loop. To prevent this, `ConnectionManager.broadcast` uses an **exception-resilient pruning pattern**:

```python
class ConnectionManager:
    async def broadcast(self, message: Dict[str, Any]):
        if not connected_clients:
            return
        payload = json.dumps(message)
        disconnected = []
        for connection in connected_clients:
            try:
                await connection.send_text(payload)
            except Exception:
                # Catch closed or broken pipes without interrupting the loop
                disconnected.append(connection)
        
        # Prune dead connections after the iteration completes
        for conn in disconnected:
            self.disconnect(conn)
```

By collecting dead sockets during the iteration and pruning them afterwards, the server ensures zero packet loss for healthy clients and prevents memory leaks from ghost sockets.

---

## Log Caching & Deduplication Architecture

To maintain a clean terminal feed in the Svelte UI without flooding client memory or losing logs during reconnects, `ServerUICallbacks` implements an indexed rolling buffer:

```python
class ServerUICallbacks:
    def __init__(self):
        self.logs = []
        self.log_counter = 0
        self.is_silent = False
```

### 1. Rolling Cache Limit
When a system log is generated via `log(text)`, an incremental ID is assigned (`log_counter += 1`), and the entry is appended to `self.logs`. The list is strictly bounded to the most recent **50 entries** (`self.logs.pop(0)`), ensuring fixed RAM consumption even during extended multi-day runs.

### 2. Client Reconnection Synchronization
When a Svelte frontend client opens or refreshes its browser tab:
1. The WebSocket connection handler immediately pushes the cached `self.logs` array to the newly connected client.
2. The Svelte state store (`store.svelte.ts`) tracks the highest log ID it has processed in `robotState.lastLogId` and `lastServerLogId`.
3. Incoming telemetry packets include server log payloads. The frontend compares the incoming log IDs against `lastLogId` and only renders items with `log.id > lastLogId`.
4. **Result**: The user never sees duplicate terminal messages when reconnecting, and terminal chat history is instantly restored upon tab refresh.

---

## ServerUICallbacks Interface

Located in [ws_manager.py](../src/control/ws_manager.py), the `ServerUICallbacks` class exposes several callbacks:

### 1. `update_telemetry(telemetry_data)`
Broadcasts real-time parameters from the monitoring loop to all connected UI clients.
* **Payload Format:**
  ```json
  {
    "type": "telemetry",
    "client_count": 2,
    "angles": {"A": 10.5, "B": -5.0, "C": 0.0},
    "speeds": {"A": 0.0, "B": 0.0, "C": 0.0},
    "ee_position": {"x": 0.12, "y": 0.05, "z": 0.76},
    "limits": {"A": [-45.0, 45.0], "B": [-50.0, 20.0], "C": [-45.0, 45.0]},
    "is_homed": true,
    "pwm_blocked": false,
    "is_homing": false,
    "is_calibrating": false,
    "is_capturing": false,
    "capture_count": 0,
    "lease_holder": "192.168.1.50",
    "vla_mode": "moderated",
    "has_pending_vla": false,
    "offsets": {"A": 75.0, "B": -24.0, "C": 0.0}
  }
  ```

### 2. `log(text, category)`
Logs messages to the standard python logger, retains a rolling cache of the last 50 console entries on the server, and broadcasts a chat-formatted response to all UI consoles.
* **Payload Format:**
  ```json
  {
    "type": "chat_response",
    "text": "Starting absolute zero calibration recovery...",
    "sender": "system",
    "command": "CONSOLE"
  }
  ```

### 3. `notify_vla_pending(action)`
Informs the user via the frontend that a VLA (Vision-Language-Action) agent has requested a movement step, prompting approval.
* **Payload Format:**
  ```json
  {
    "type": "vla_pending",
    "action": {
      "agent_id": "vla_agent_1",
      "target_positions": [[5.0, -2.5, 0.0]],
      "target_velocities": [0.2, 0.2, 0.2],
      "timestamp": 1720268500.25
    }
  }
  ```

### 4. `notify_vla_resolved(status)`
Notifies the frontend that the pending action has been accepted or rejected.
* **Payload Format:**
  ```json
  {
    "type": "vla_resolved",
    "status": "approved" // or "rejected"
  }
  ```

### 5. `trigger_vla_inference()`
Triggers VLA clients (who are listening to the socket) to capture the current cameras and run another inference cycle.
* **Payload Format:**
  ```json
  {
    "type": "vla_inference_trigger"
  }
  ```
