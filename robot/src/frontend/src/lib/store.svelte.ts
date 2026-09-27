// Svelte 5 Centralized State & WebSocket Manager
function getCookie(name: string): string | null {
	if (typeof document === 'undefined') return null;
	const nameLenPlus = (name.length + 1);
	return document.cookie
		.split(';')
		.map(c => c.trim())
		.filter(cookie => cookie.substring(0, nameLenPlus) === `${name}=`)
		.map(cookie => decodeURIComponent(cookie.substring(nameLenPlus)))[0] || null;
}

const savedTheme = getCookie("theme");
let initialTheme = "dark";
if (savedTheme === "dark" || savedTheme === "light") {
	initialTheme = savedTheme;
} else if (typeof window !== 'undefined') {
	const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
	initialTheme = prefersDark ? "dark" : "light";
}

export const robotState = $state({
	wsStatus: "disconnected", // "disconnected" | "connecting" | "connected"
	hasReceivedTelemetry: false,
	angles: { A: 0.0, B: 0.0, C: 0.0 },
	speeds: { A: 0.0, B: 0.0, C: 0.0 },
	eePosition: { x: 0.144, y: 0.088, z: 0.888 },
	keyboardEnabled: false,
	controllerEnabled: false,
	isHomed: false,
	isHoming: false,
	isCalibrating: false,
	homeAngles: { A: 0.0, B: 0.0, C: 0.0 },
	zeroTriggerCount: 0,
	captureCount: 0,
	isCapturing: false,
	clientCount: 1,
	limits: {
		A: [-45.0, 45.0],
		B: [-50.0, 20.0],
		C: [-45.0, 45.0]
	},
	offsets: {
		A: 75.0,
		B: -24.0,
		C: 0.0
	},

	// Dynamic robot status pill
	robotStatus: "IDLE" as "IDLE" | "RUNNING" | "ESTOPPED" | "HOMING",
	cam1Frame: "",

	// Terminal feed combining chat commands and server logs
	unifiedFeed: [] as Array<{ type: 'chat' | 'log'; sender?: string; text: string; time: string; command?: string }>,
	lastLogId: 0,
	lastServerLogId: 0,

	// Gamepad tracking
	gamepadConnected: false,

	// Theme tracking
	currentTheme: initialTheme,
	activeTab: "live",
	pwmScale: 0.8,

	// Lease & VLA status
	leaseHolder: "None",
	vlaMode: "block",
	hasPendingVla: false,
	pendingVlaAction: null as any,

	// Dataset Manager state
	datasetList: [] as Array<{ id: string; goal_text: string; start_time: string; task_id: string; step_count?: number }>,
	selectedDatasetId: null as string | null,
	selectedDatasetDetails: null as any,
	currentPlaybackStep: 0,
	datasetStepTelemetry: null as any,
});

let socket: WebSocket | null = null;
let lastSocketUrl: string = "";
let heartbeatInterval: any = null;

// Resolve API host dynamically
export function getApiBaseUrl(): string {
	if (typeof window === 'undefined') return "";
	return `${window.location.protocol}//${window.location.host}`;
}

// Resolve WebSocket URL dynamically
export function getWsUrl(): string {
	if (typeof window === 'undefined') return "";
	const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
	return `${protocol}//${window.location.host}/ws`;
}

// Resolve Video Feed URL dynamically
export function getVideoFeedUrl(slotIdx: number): string {
	if (typeof window === 'undefined') return "";
	const base = getApiBaseUrl();
	return `${base}/video_feed/${slotIdx}`;
}

// Resolve Dataset Step Image URL dynamically
export function getDatasetStepImageUrl(episodeId: string, stepId: number, cameraId: number): string {
	if (typeof window === 'undefined') return "";
	const base = getApiBaseUrl();
	return `${base}/api/dataset/${episodeId}/step/${stepId}/image/${cameraId}`;
}

function appendFeed(entry: any) {
	robotState.unifiedFeed = [...robotState.unifiedFeed, entry].slice(-150);
	scrollTerminal();
}

export function addLocalLog(msg: string) {
	const timeStr = new Date().toLocaleTimeString();
	appendFeed({
		type: 'log',
		text: `[Local Client] ${msg}`,
		time: timeStr
	});
}

export function addSystemLog(msg: string) {
	const timeStr = new Date().toLocaleTimeString();
	appendFeed({
		type: 'log',
		text: msg,
		time: timeStr
	});
}

function scrollTerminal() {
	if (typeof window !== 'undefined') {
		setTimeout(() => {
			const el = document.getElementById("terminal-scroll-area");
			if (el) el.scrollTop = el.scrollHeight;
		}, 30);
	}
}

export function connectWebSocket() {
	if (typeof window === 'undefined') return;

	robotState.wsStatus = "connecting";
	robotState.hasReceivedTelemetry = false;
	const wsUrl = getWsUrl();
	lastSocketUrl = wsUrl;

	try {
		socket = new WebSocket(wsUrl);

		socket.onopen = () => {
			robotState.wsStatus = "connected";
			addLocalLog("WebSocket channel successfully opened.");
			if (robotState.keyboardEnabled || robotState.controllerEnabled) {
				sendWSMessage({ type: "console", value: "lease acquire", silent: true });
			}
			if (!heartbeatInterval && typeof window !== 'undefined') {
				heartbeatInterval = setInterval(() => {
					if ((robotState.keyboardEnabled || robotState.controllerEnabled) && robotState.wsStatus === 'connected') {
						sendWSMessage({ type: "console", value: "lease acquire", silent: true });
					}
				}, 10000);
			}
		};

		socket.onmessage = (event) => {
			try {
				const data = JSON.parse(event.data);
				if (data.type === "telemetry") {
					const isFirstTelemetry = !robotState.hasReceivedTelemetry;
					if (data.angles !== undefined) {
						robotState.angles = data.angles;
						robotState.hasReceivedTelemetry = true;
					}
					if (data.speeds !== undefined) {
						robotState.speeds = data.speeds;
					}
					if (data.ee_position !== undefined) {
						robotState.eePosition = data.ee_position;
					}
					if (data.is_homed !== undefined) {
						robotState.isHomed = data.is_homed;
					}
					if (data.is_homing !== undefined) {
						robotState.isHoming = data.is_homing;
					}
					if (data.is_calibrating !== undefined) {
						const wasCalibrating = robotState.isCalibrating;
						robotState.isCalibrating = data.is_calibrating;
						if (!isFirstTelemetry && wasCalibrating !== data.is_calibrating) {
							addSystemLog(data.is_calibrating ? "Calibration mode started. limits bypassed" : "Calibration mode stopped. zero positions locked");
						}
					}
					if (data.home_angles !== undefined) {
						robotState.homeAngles = data.home_angles;
					}
					if (data.is_capturing !== undefined) {
						const wasCapturing = robotState.isCapturing;
						robotState.isCapturing = data.is_capturing;
						if (wasCapturing !== data.is_capturing) {
							if (!isFirstTelemetry) {
								addSystemLog(data.is_capturing ? "Capturing started" : "Capturing stopped");
							}
							loadDatasets();
							setTimeout(loadDatasets, 500);
							setTimeout(loadDatasets, 1500);
						}
					}
					if (data.capture_count !== undefined) {
						robotState.captureCount = data.capture_count;
					}
					if (data.client_count !== undefined) {
						robotState.clientCount = data.client_count;
					}
					if (data.limits !== undefined) {
						robotState.limits = data.limits;
					}
					if (data.offsets !== undefined) {
						robotState.offsets = data.offsets;
					}
					if (data.lease_holder !== undefined) {
						robotState.leaseHolder = data.lease_holder;
					}
					if (data.vla_mode !== undefined) {
						const oldMode = robotState.vlaMode;
						robotState.vlaMode = data.vla_mode;
						if (!isFirstTelemetry && oldMode !== data.vla_mode) {
							addSystemLog(`VLA safety mode updated: ${data.vla_mode.toUpperCase()}`);
						}
					}
					if (data.has_pending_vla !== undefined) {
						robotState.hasPendingVla = data.has_pending_vla;
					}

					// Update status
					if (data.pwm_blocked !== undefined) {
						const isMoving = Object.values(robotState.speeds).some(s => Math.abs(s) > 0.05);
						const oldStatus = robotState.robotStatus;
						if (data.pwm_blocked === true) {
							robotState.robotStatus = "ESTOPPED";
							if (!isFirstTelemetry && oldStatus !== "ESTOPPED") {
								addSystemLog("Emergency stop activated. All motors coasting.");
							}
						} else {
							robotState.robotStatus = robotState.isHoming ? "HOMING" : (isMoving ? "RUNNING" : "IDLE");
							if (!isFirstTelemetry && oldStatus === "ESTOPPED") {
								addSystemLog("PWM unblocked. Robot arm is operational again.");
							}
						}
					}

					// Secure log parsing with incremental server IDs
					if (data.logs && Array.isArray(data.logs)) {
						if (data.logs.length > 0) {
							robotState.lastServerLogId = data.logs[data.logs.length - 1].id;
						}

						const newLogs = data.logs.filter((log: any) => log.id > robotState.lastLogId);
						newLogs.forEach((log: any) => {
							appendFeed({
								type: 'log',
								text: log.text,
								time: new Date().toLocaleTimeString()
							});
							robotState.lastLogId = log.id;
						});
					}
				} else if (data.type === "video_frame") {
					robotState.cam1Frame = data.image;
				} else if (data.type === "vla_pending") {
					robotState.hasPendingVla = true;
					robotState.pendingVlaAction = data.action;
					addSystemLog(`VLA Action Pending Approval: ${JSON.stringify(data.action)}`);
				} else if (data.type === "vla_resolved") {
					robotState.hasPendingVla = false;
					robotState.pendingVlaAction = null;
					addSystemLog(`VLA Pending Action Resolved: ${data.status}`);
				} else if (data.type === "chat_response") {
					const timeStr = new Date().toLocaleTimeString();
					appendFeed({
						type: 'chat',
						sender: data.sender || "system",
						text: data.text,
						time: timeStr,
						command: data.command
					});

					if (data.text.includes("Emergency stop")) {
						robotState.robotStatus = "ESTOPPED";
					}
				}
			} catch (e) {
				console.error("Error reading socket frame", e);
			}
		};

		socket.onclose = () => {
			robotState.wsStatus = "disconnected";
			setTimeout(connectWebSocket, 2000);
		};

		socket.onerror = () => {
			robotState.wsStatus = "disconnected";
			socket?.close();
		};
	} catch (e) {
		robotState.wsStatus = "disconnected";
		setTimeout(connectWebSocket, 2000);
	}
}

export function forceReconnect() {
	addLocalLog("Forcing manual WebSocket reconnection...");
	socket?.close();
}

export function sendWSMessage(payload: string | object) {
	if (socket && socket.readyState === WebSocket.OPEN) {
		if (typeof payload === 'object') {
			socket.send(JSON.stringify(payload));
		} else {
			socket.send(payload);
		}
	}
}

// Controller Actions
export function toggleKeyboard() {
	robotState.keyboardEnabled = !robotState.keyboardEnabled;
	addSystemLog(`Keyboard control ${robotState.keyboardEnabled ? 'enabled' : 'disabled'}`);
	// Sync keyboard input status to lease
	if (robotState.keyboardEnabled) {
		submitChatCommand("lease acquire", true);
	} else {
		submitChatCommand("lease release", true);
	}
}

export function toggleController() {
	robotState.controllerEnabled = !robotState.controllerEnabled;
	addSystemLog(`Controller control ${robotState.controllerEnabled ? 'enabled' : 'disabled'}`);
	if (robotState.controllerEnabled) {
		submitChatCommand("lease acquire", true);
	} else {
		submitChatCommand("lease release", true);
	}
}

export function triggerStop() {
	robotState.robotStatus = "ESTOPPED";
	submitChatCommand("stop", true);
}

export function triggerUnblock() {
	submitChatCommand("unblock", true);
}

export function triggerHoming() {
	addSystemLog("Homing sequence triggered");
	submitChatCommand("home", true);
}

export function triggerCalibrateHome() {
	addSystemLog("Software zero calibration applied");
	submitChatCommand("zero", true);
}

export function startCalibration() {
	submitChatCommand("calibrate_mode start", true);
}

export function stopCalibration() {
	submitChatCommand("calibrate_mode stop", true);
}

export function toggleDatasetCapture() {
	submitChatCommand("capture", true);
}

export function applyManualAngle(joint: string, valueStr: string) {
	const val = parseFloat(valueStr);
	if (isNaN(val)) return;

	submitChatCommand(`move ${joint} ${val}`, true);
	addLocalLog(`Manual Target sent: Joint ${joint} = ${val}°`);
}

export function submitChatCommand(cmd: string, silent = false) {
	cmd = cmd.trim();
	if (!cmd) return;

	const lowerCmd = cmd.toLowerCase();
	if (lowerCmd === "clear" || lowerCmd === "cls") {
		clearFeed();
		return;
	}

	sendWSMessage({ type: "console", value: cmd, silent });

	if (!silent) {
		const timeStr = new Date().toLocaleTimeString();
		appendFeed({
			type: 'chat',
			sender: "user",
			text: cmd,
			time: timeStr
		});
	}
}

export function clearFeed() {
	robotState.unifiedFeed = [];
	robotState.lastLogId = robotState.lastServerLogId;
}

// -------------------------------------------------------------
// Dataset REST API Handlers
// -------------------------------------------------------------
export async function loadDatasets() {
	try {
		const base = getApiBaseUrl();
		const res = await fetch(`${base}/api/datasets`);
		if (res.ok) {
			robotState.datasetList = await res.json();
		}
	} catch (e) {
		console.error("Failed to load datasets:", e);
	}
}

export async function loadDatasetDetails(episodeId: string) {
	try {
		const base = getApiBaseUrl();
		const res = await fetch(`${base}/api/dataset/${episodeId}`);
		if (res.ok) {
			robotState.selectedDatasetId = episodeId;
			robotState.selectedDatasetDetails = await res.json();
			robotState.currentPlaybackStep = 0;
			await loadStepTelemetry(episodeId, 0);
		}
	} catch (e) {
		console.error(`Failed to load details for dataset ${episodeId}:`, e);
	}
}

export async function loadStepTelemetry(episodeId: string, stepId: number) {
	try {
		const base = getApiBaseUrl();
		const res = await fetch(`${base}/api/dataset/${episodeId}/step/${stepId}/telemetry`);
		if (res.ok) {
			robotState.datasetStepTelemetry = await res.json();
			robotState.currentPlaybackStep = stepId;
		}
	} catch (e) {
		console.error(`Failed to load telemetry for step ${stepId}:`, e);
	}
}

export async function deleteDataset(episodeId: string) {
	try {
		const base = getApiBaseUrl();
		const res = await fetch(`${base}/api/dataset/${episodeId}`, {
			method: 'DELETE'
		});
		if (res.ok) {
			robotState.selectedDatasetId = null;
			robotState.selectedDatasetDetails = null;
			robotState.datasetStepTelemetry = null;
			await loadDatasets();
		}
	} catch (e) {
		console.error(`Failed to delete dataset ${episodeId}:`, e);
	}
}

export function sendJog(joint: 'A' | 'B' | 'C', amplitude: number, scale = 1.0) {
	const clamped = Math.max(-1, Math.min(1, amplitude));
	const clampedScale = Math.max(0, Math.min(1, scale));
	sendWSMessage({ type: "console", value: `jog ${joint} ${clamped.toFixed(3)} ${clampedScale.toFixed(3)}`, silent: true });
}

