<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { robotState, connectWebSocket, sendWSMessage, addLocalLog, sendJog } from '$lib/store.svelte';

	import Header from '$lib/components/Header.svelte';
	import TelemetryCard from '$lib/components/TelemetryCard.svelte';
	import ManualOverridesCard from '$lib/components/ManualOverridesCard.svelte';
	import TerminalCard from '$lib/components/TerminalCard.svelte';
	import MasterControlCard from '$lib/components/MasterControlCard.svelte';
	import CamerasCard from '$lib/components/CamerasCard.svelte';
	import DiagramsCard from '$lib/components/DiagramsCard.svelte';
	import DatasetManager from '$lib/components/DatasetManager.svelte';

	let controlInterval: any = null;
	
	let keysPressed = {
		w: false, s: false,
		a: false, d: false,
		q: false, e: false
	};

	function handleKeyDown(event: KeyboardEvent) {
		const activeElement = document.activeElement;
		const isTyping = activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA');
		if (isTyping || !robotState.keyboardEnabled || robotState.activeTab !== 'live') return;
		
		const key = event.key.toLowerCase();
		const controlKeys = ['w', 's', 'a', 'd', 'q', 'e'];
		if (controlKeys.includes(key)) {
			event.preventDefault();
		}
		if (event.repeat) return;
		if (key === 'a') keysPressed.a = true;
		if (key === 'd') keysPressed.d = true;
		if (key === 'w') keysPressed.w = true;
		if (key === 's') keysPressed.s = true;
		if (key === 'q') keysPressed.q = true;
		if (key === 'e') keysPressed.e = true;
	}

	function handleKeyUp(event: KeyboardEvent) {
		const activeElement = document.activeElement;
		const isTyping = activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA');
		if (isTyping || !robotState.keyboardEnabled || robotState.activeTab !== 'live') return;

		const key = event.key.toLowerCase();
		const controlKeys = ['w', 's', 'a', 'd', 'q', 'e'];
		if (controlKeys.includes(key)) {
			event.preventDefault();
		}
		if (key === 'a') keysPressed.a = false;
		if (key === 'd') keysPressed.d = false;
		if (key === 'w') keysPressed.w = false;
		if (key === 's') keysPressed.s = false;
		if (key === 'q') keysPressed.q = false;
		if (key === 'e') keysPressed.e = false;
	}

	function handleBlur() {
		keysPressed.w = false;
		keysPressed.s = false;
		keysPressed.a = false;
		keysPressed.d = false;
		keysPressed.q = false;
		keysPressed.e = false;
	}

	let lastJogAmplitude = { A: 0.0, B: 0.0, C: 0.0 };
	let smoothedJog = { A: 0.0, B: 0.0, C: 0.0 };
	let lastSendTime: Record<string, number> = { A: 0, B: 0, C: 0 };
	let lastGamepadButtons = {
		leftBumper: false,
		north: false,
		east: false,
		rightBumper: false
	};

	function shapeAxis(value: number) {
		const deadzone = 0.15;
		if (Math.abs(value) <= deadzone) return 0.0;
		const sign = value > 0 ? 1 : -1;
		const scaled = (Math.abs(value) - deadzone) / (1.0 - deadzone);
		return sign * Math.pow(Math.min(1.0, scaled), 3);
	}

	function processGamepadButtons(gp: Gamepad) {
		const current = {
			east: Boolean(gp.buttons[1]?.pressed),
			north: Boolean(gp.buttons[3]?.pressed),
			leftBumper: Boolean(gp.buttons[4]?.pressed),
			rightBumper: Boolean(gp.buttons[5]?.pressed)
		};

		if (
			(current.leftBumper && !lastGamepadButtons.leftBumper) ||
			(current.rightBumper && !lastGamepadButtons.rightBumper)
		) {
			sendWSMessage({ type: "console", value: "stop", silent: false });
		}
		if (current.north && !lastGamepadButtons.north) {
			sendWSMessage({ type: "console", value: "home", silent: false });
		}
		if (current.east && !lastGamepadButtons.east) {
			sendWSMessage({ type: "console", value: "capture", silent: false });
		}

		lastGamepadButtons = current;
	}

	function startControlInterval() {
		controlInterval = setInterval(() => {
			if (robotState.wsStatus === 'connected') {
				let jogA = 0.0;
				let jogB = 0.0;
				let jogC = 0.0;

				const activeElement = document.activeElement;
				const isTyping = activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA');

				if (robotState.keyboardEnabled && !isTyping && robotState.activeTab === 'live') {
					jogA += keysPressed.e ? 1 : keysPressed.q ? -1 : 0;
					jogB += keysPressed.s ? 1 : keysPressed.w ? -1 : 0;
					jogC += keysPressed.a ? 1 : keysPressed.d ? -1 : 0;
				}

				if (robotState.controllerEnabled) {
					const gamepads = navigator.getGamepads();
					let gp = null;
					for (let i = 0; i < gamepads.length; i++) {
						if (gamepads[i]) {
							gp = gamepads[i];
							break;
						}
					}

					if (gp) {
						robotState.gamepadConnected = true;
						processGamepadButtons(gp);

						let axisC = gp.axes[0] || 0.0;
						let axisB = gp.axes[1] || 0.0;
						let axisA = gp.axes[3] || 0.0;

						jogC += shapeAxis(axisC);
						jogB += shapeAxis(axisB);
						jogA += shapeAxis(axisA);
					} else {
						robotState.gamepadConnected = false;
						lastGamepadButtons = {
							leftBumper: false,
							north: false,
							east: false,
							rightBumper: false,
						};
					}
				}

				const alpha = 0.8;
				smoothedJog.A = (1 - alpha) * smoothedJog.A + alpha * jogA;
				smoothedJog.B = (1 - alpha) * smoothedJog.B + alpha * jogB;
				smoothedJog.C = (1 - alpha) * smoothedJog.C + alpha * jogC;
				if (Math.abs(smoothedJog.A) < 0.001) smoothedJog.A = 0.0;
				if (Math.abs(smoothedJog.B) < 0.001) smoothedJog.B = 0.0;
				if (Math.abs(smoothedJog.C) < 0.001) smoothedJog.C = 0.0;

				const now = Date.now();
				const processJog = (joint: 'A' | 'B' | 'C', amplitude: number) => {
					const quantized = Math.abs(amplitude) < 0.001 ? 0.0 : Math.round(amplitude * 100) / 100;
					const prev = lastJogAmplitude[joint];
					const timeSinceLast = now - (lastSendTime[joint] || 0);

					if (quantized !== prev || (quantized !== 0.0 && timeSinceLast > 500)) {
						lastJogAmplitude[joint] = quantized;
						lastSendTime[joint] = now;
						sendJog(joint, quantized, robotState.pwmScale);
					}
				};

				processJog('A', Math.max(-1, Math.min(1, smoothedJog.A)));
				processJog('B', Math.max(-1, Math.min(1, smoothedJog.B)));
				processJog('C', Math.max(-1, Math.min(1, smoothedJog.C)));
			}
		}, 50); // 20Hz
	}

	onMount(() => {

		robotState.unifiedFeed = [
			{ type: 'log', text: "Robot Control Interface Refactoring complete.", time: new Date().toLocaleTimeString() },
			{ type: 'log', text: "Ready for telemetry.", time: new Date().toLocaleTimeString() }
		];

		connectWebSocket();
		startControlInterval();
		
		// Check for already connected gamepads on mount
		if (typeof navigator !== 'undefined' && navigator.getGamepads) {
			const gamepads = navigator.getGamepads();
			for (let i = 0; i < gamepads.length; i++) {
				if (gamepads[i]) {
					robotState.gamepadConnected = true;
					break;
				}
			}
		}
		
		window.addEventListener('keydown', handleKeyDown);
		window.addEventListener('keyup', handleKeyUp);
		window.addEventListener('blur', handleBlur);
		window.addEventListener("gamepadconnected", handleGamepadConnected);
		window.addEventListener("gamepaddisconnected", handleGamepadDisconnected);
	});

	onDestroy(() => {
		if (controlInterval) clearInterval(controlInterval);
		
		if (typeof window !== 'undefined') {
			window.removeEventListener('keydown', handleKeyDown);
			window.removeEventListener('keyup', handleKeyUp);
			window.removeEventListener('blur', handleBlur);
			window.removeEventListener("gamepadconnected", handleGamepadConnected);
			window.removeEventListener("gamepaddisconnected", handleGamepadDisconnected);
		}
	});

	function handleGamepadConnected(e: GamepadEvent) {
		addLocalLog(`Xbox Controller linked: ${e.gamepad.id.substring(0, 15)}...`);
		robotState.gamepadConnected = true;
	}

	function handleGamepadDisconnected(e: GamepadEvent) {
		addLocalLog("Xbox Controller disconnected.");
		robotState.gamepadConnected = false;
	}
</script>

<Header />

{#if robotState.activeTab === 'live'}
	<div class="workspace-layout-split">
		<div class="workspace-column left">
			<TelemetryCard />
			<ManualOverridesCard />
			<TerminalCard />
		</div>

		<div class="workspace-column right">
			<MasterControlCard />
			<CamerasCard />
			<DiagramsCard />
		</div>
	</div>
{:else}
	<div class="workspace-layout-full">
		<DatasetManager />
	</div>
{/if}

<style>
	/* Global Component styles for glass cards */
	:global(.glass-card) {
		background: var(--glass-bg);
		backdrop-filter: var(--glass-blur);
		border: 1px solid var(--border-soft);
		border-radius: 10px;
		padding: 0.75rem 1rem;
		box-shadow: var(--glass-shadow);
		display: flex;
		flex-direction: column;
		overflow: hidden; 
		transition: border-color 0.2s cubic-bezier(0.4, 0, 0.2, 1), background-color 0.2s cubic-bezier(0.4, 0, 0.2, 1);
	}

	:global(.glass-card:hover) {
		border-color: rgba(42, 117, 243, 0.25);
		box-shadow: 0 0 15px var(--glass-card-hover-glow);
	}

	:global(.cell-header) {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.6rem;
		border-bottom: 1px solid var(--border-soft);
		padding-bottom: 0.35rem;
		flex-shrink: 0;
	}

	:global(.cell-header h2) {
		margin: 0;
		font-size: 0.88rem;
		font-weight: 800;
		letter-spacing: 0.8px;
		color: var(--text-muted);
		text-transform: uppercase;
	}

	:global(.hud-meta) {
		font-family: 'Fira Code', monospace;
		font-size: 0.72rem;
		color: var(--text-muted);
		opacity: 0.7;
	}

	.workspace-layout-split {
		height: calc(100vh - 68px);
		display: grid;
		grid-template-columns: 1.15fr 1.25fr;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		overflow: hidden;
	}

	.workspace-layout-full {
		height: calc(100vh - 68px);
		padding: 0.75rem 1rem;
		overflow-y: auto;
	}

	.workspace-column {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		height: 100%;
		min-height: 0;
	}

	/* Mobile Responsiveness Rules! */
	@media (max-width: 1024px) {
		.workspace-layout-split {
			display: flex;
			flex-direction: column;
			height: auto;
			overflow-y: visible;
		}

		.workspace-column {
			display: contents; /* Flattens columns into the parent flex container! */
		}
		
		/* Explicitly reorder components for mobile */
		:global(.telemetry-card) { order: 1; }
		:global(.overrides-card) { order: 2; }
		:global(.master-actions-card) { order: 3; }
		:global(.unified-terminal-card) { order: 4; }
		:global(.cameras-card) { order: 5; }
		:global(.vectors-card) { order: 6; }
	}
</style>
