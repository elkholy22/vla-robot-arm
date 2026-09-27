# Robot System Protocol Specification

## 1. Purpose

This document specifies the communication interfaces between the Svelte web UI, the VLA client, and the FastAPI robot server. It defines the transport protocols, message formats, API endpoints, and communication semantics required for controlling the robot and exchanging telemetry and dataset information.

The FastAPI server acts as the central communication hub, receiving commands from clients and distributing robot state, telemetry, and system events.

---

| Interface | Protocol | Purpose |
|-----------|----------|---------|
| Web UI – FastAPI Server | WebSocket (JSON) | Robot control and real-time telemetry |
| Web UI – FastAPI Server | HTTP REST | Dataset management and file transfer |
| Browser – FastAPI Server | HTTP MJPEG | Live camera streaming |
| VLA Client – FastAPI Server | WebSocket (JSON) | Action inference and execution |

The server listens on `http://<robot-ip>:9000`. The frontend derives both HTTP and WebSocket URLs from the current browser host, using `ws` for HTTP deployments and `wss` when deployed behind HTTPS.

---

## 3. Data Conventions

| Data | Convention |
|------|------------|
| Joint names | `A`: end effector, `B`: vertical joint, `C`: base |
| Joint angles | Degrees |
| Joint limits | Degrees |
| End-effector position | Metres (`{x, y, z}`) |
| PWM values | Normalized to `[-1.0, 1.0]` |
| Absolute encoder values | Wrapped to `[-180°, 180°]` |
| Timestamps | Unix time (seconds) |

---

# 4. WebSocket Protocol

Clients connect to

```text
ws://<robot-ip>:9000/ws
```

After establishing a connection, the server sends the current robot state, the number of connected clients, and cached log messages. Robot telemetry is broadcast whenever relevant values change.

Structured protocol messages are UTF-8 encoded JSON objects identified by the `type` field. Non-JSON text messages are accepted as legacy console commands.

---

## 4.1 Client Messages

### Console Command

```json
{"type":"console","value":"move A 10","silent":false}
```

`value` contains the console command to execute. The optional `silent` field suppresses terminal output.

---

### VLA Registration

```json
{"type":"vla_register","agent_id":"octo_1","name":"Octo Client","options":{"model":"octo-small"}}
```

Registers a VLA client with the server.

---

### VLA Action

```json
{"type":"vla_action","agent_id":"octo_1","target_positions":[[1.5,-0.8,2.0]],"target_velocities":[0.2,0.2,0.2]}
```

`target_positions` contains one or more joint-space actions ordered as `[A, B, C]`. Incoming actions are validated before execution.

---

## 4.2 Server Messages

### Telemetry

```json
{
  "type":"telemetry",
  "angles":{"A":0.0,"B":0.0,"C":0.0},
  "speeds":{"A":0.0,"B":0.0,"C":0.0},
  "measured_velocities":{"A":0.0,"B":0.0,"C":0.0},
  "ee_position":{"x":0.14,"y":0.09,"z":0.89},
  "limits":{"A":[-45,45],"B":[-50,20],"C":[-45,45]},
  "physical_limits":{"A":[-45,45],"B":[-50,20],"C":[-45,45]},
  "is_homed":true,
  "offsets":{"A":74.2,"B":-25.8,"C":0.0},
  "pwm_blocked":false,
  "is_homing":false,
  "is_calibrating":false,
  "is_capturing":false,
  "capture_count":0,
  "client_count":1,
  "lease_holder":"None",
  "vla_mode":"block",
  "has_pending_vla":false
}
```

Regular telemetry broadcasts contain the full robot state. Connection events may send partial telemetry containing only fields such as `client_count`, clients therefore update only fields present in each message.

---

### Command Responses

```json
{"type":"chat_response","text":"Command completed.","sender":"system","command":"CONSOLE"}
```

---

### VLA Events

```json
{"type":"vla_action_ack","success":true,"message":"Action queued for approval."}
```

```json
{"type":"vla_pending","action":{"agent_id":"octo_1","target_positions":[[1.5,-0.8,2.0]],"target_velocities":[0.2,0.2,0.2],"timestamp":1783700000.0}}
```

```json
{"type":"vla_resolved","status":"approved"}
```

```json
{"type":"vla_inference_trigger"}
```

`vla_resolved.status` is either `approved` or `rejected`.

---

## 4.3 Console Commands

| Command | Description |
|----------|-------------|
| `stop` | Emergency stop |
| `unblock` | Re-enable PWM output |
| `home` | Move to the calibrated home position |
| `zero` | Apply a temporary software zero |
| `calibrate_mode <start\|stop>` | Start or stop calibration |
| `calibrate <joint> <offset>` | Update a kinematic offset |
| `move <joint> <angle>` | Joint-space movement |
| `moveee <x> <y> <z>` | Cartesian movement |
| `jog <joint> <direction> [scale]` | Continuous joint movement |
| `capture` | Start or stop dataset recording |
| `goal <text>` | Set the language instruction for a recording |
| `lease <acquire\|release>` | Acquire or release manual control |
| `vla_mode <block\|moderated\|auto>` | Select the VLA execution mode |
| `vla_approve` | Approve a pending VLA action |
| `vla_reject` | Reject a pending VLA action |
| `vla_trigger_inference` | Request the next VLA action |

Commands are case-insensitive and support quoted arguments.

---

# 5. HTTP API

| Method | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/datasets` | List all recorded episodes |
| `GET` | `/api/dataset/{id}` | Episode metadata |
| `GET` | `/api/dataset/{id}/step/{step}/telemetry` | Recorded telemetry |
| `GET` | `/api/dataset/{id}/step/{step}/image/{camera}` | Recorded image |
| `DELETE` | `/api/dataset/{id}` | Delete an episode |
| `GET` | `/api/dataset/{id}/download` | Download one episode |
| `GET` | `/api/datasets/download` | Download all episodes |
| `GET` | `/api/heatmap_output/switch_position_kde.png` | Generated heatmap |
| `GET` | `/video_feed/{slot}` | Live MJPEG camera stream |

Example dataset entry:

```json
{"id":"ep_20260712_120000","goal_text":"flip the lever","start_time":"2026-07-12T12:00:00","task_id":"ep_20260712_120000","step_count":125}
```

Camera streams use `multipart/x-mixed-replace` with JPEG frames. Error responses follow the format

```json
{ "detail":"message"}
```

using standard HTTP status codes such as `400`, `404`, and `500`.

---

# 6. Safety and Error Handling

- Manual robot control is protected by a lease mechanism to prevent conflicting commands from multiple clients.
- While another client owns the control lease, the server rejects `move`, `moveee`, `jog`, `home`, `zero`, and `calibrate_mode` commands from other clients.
- Emergency stop is always available, regardless of lease ownership.
- Motion requests are validated against the configured joint limits before execution.
- Invalid commands return a `chat_response` message describing the error.
- Every VLA action receives a corresponding acknowledgement (`vla_action_ack`).
- VLA execution supports three modes:
  - `block`
  - `moderated`
  - `auto`
- The server currently assumes deployment within a trusted local network and does not provide authentication or TLS directly.