<script lang="ts">
	import { robotState, forceReconnect } from '$lib/store.svelte';

	function getCookie(name: string): string | null {
		const nameLenPlus = (name.length + 1);
		return document.cookie
			.split(';')
			.map(c => c.trim())
			.filter(cookie => cookie.substring(0, nameLenPlus) === `${name}=`)
			.map(cookie => decodeURIComponent(cookie.substring(nameLenPlus)))[0] || null;
	}

	function setCookie(name: string, val: string) {
		document.cookie = `${name}=${encodeURIComponent(val)};path=/;max-age=31536000`; // 1 year
	}

	function toggleTheme() {
		robotState.currentTheme = robotState.currentTheme === "dark" ? "light" : "dark";
		setCookie("theme", robotState.currentTheme);
	}
</script>

<header class="app-header">
	<div class="header-logo">
		<div class="gemini-wave">
			<div class="glow-dot d1"></div>
			<div class="glow-dot d2"></div>
		</div>
		<h1>Robot-<span class="highlight">Team1</span></h1>
	</div>

	<div class="header-nav-tabs">
		<button class="nav-tab-btn" class:active={robotState.activeTab === 'live'} onclick={() => robotState.activeTab = 'live'}>
			🔴 Live Control
		</button>
		<button class="nav-tab-btn" class:active={robotState.activeTab === 'datasets'} onclick={() => robotState.activeTab = 'datasets'}>
			📁 Dataset Manager
		</button>
	</div>
	
	<div class="header-status-controls">
		{#if robotState.wsStatus === 'connected'}
			<span class="devices-badge">DEVICES ONLINE: <strong class="badge-num">{robotState.clientCount}</strong></span>
		{/if}
		
		<button class="status-indicator-badge {robotState.wsStatus}" onclick={forceReconnect} title="WebSocket Connection: Click to force reconnect">
			<div class="indicator-orb"></div>
			<span class="indicator-label">{robotState.wsStatus.toUpperCase()}</span>
		</button>

		<button class="theme-toggle-btn" onclick={toggleTheme} title="Toggle between Dark and Light mode">
			{#if robotState.currentTheme === 'dark'}
				<svg viewBox="0 0 24 24" class="theme-icon">
					<path fill="currentColor" d="M12,18C11.11,18 10.26,17.8 9.5,17.45C11.56,16.5 13,14.42 13,12C13,9.58 11.56,7.5 9.5,6.55C10.26,6.2 11.11,6 12,6A6,6 0 0,1 18,12A6,6 0 0,1 12,18M20,8.69V4H15.31L12,0.69L8.69,4H4V8.69L0.69,12L4,15.31V20H8.69L12,23.31L15.31,20H20V15.31L23.31,12L20,8.69Z" />
				</svg>
			{:else}
				<svg viewBox="0 0 24 24" class="theme-icon">
					<path fill="currentColor" d="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4Z" />
				</svg>
			{/if}
		</button>
	</div>
</header>

<style>
	.app-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0 1.5rem;
		background: var(--glass-bg);
		border-bottom: 1px solid var(--border-soft);
		border-top: 3px solid var(--brand-blue);
		backdrop-filter: var(--glass-blur);
		height: 52px;
		box-sizing: border-box;
	}

	.header-logo {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex: 1 0 0%;
		justify-content: flex-start;
	}

	.gemini-wave {
		display: flex;
		align-items: center;
		justify-content: center;
		position: relative;
		width: 14px;
		height: 14px;
	}

	.glow-dot {
		position: absolute;
		border-radius: 50%;
		mix-blend-mode: screen;
		filter: blur(1.2px);
	}

	.glow-dot.d1 {
		width: 9px;
		height: 9px;
		background: var(--brand-blue);
		animation: drift-blue 4.5s infinite linear alternate;
	}

	.glow-dot.d2 {
		width: 9px;
		height: 9px;
		background: var(--brand-blue-neon);
		animation: drift-cyan 4.5s infinite linear alternate;
	}

	@keyframes drift-blue {
		0% { transform: translate(-3px, -2px) scale(1.1); box-shadow: 0 0 10px var(--brand-blue); }
		100% { transform: translate(3px, 2px) scale(0.9); box-shadow: 0 0 3px var(--brand-blue); }
	}

	@keyframes drift-cyan {
		0% { transform: translate(3px, 2px) scale(0.9); box-shadow: 0 0 3px var(--brand-blue-neon); }
		100% { transform: translate(-3px, -2px) scale(1.1); box-shadow: 0 0 10px var(--brand-blue-neon); }
	}

	.header-logo h1 {
		margin: 0;
		font-size: 1.3rem;
		font-weight: 800;
		letter-spacing: -0.5px;
		color: var(--text-main);
	}

	.header-logo h1 .highlight {
		color: #fff;
		background: linear-gradient(135deg, var(--brand-blue), var(--brand-blue-ice), var(--brand-blue-neon));
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
	}

	.header-status-controls {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex: 1 0 0%;
		justify-content: flex-end;
	}

	.devices-badge {
		font-family: 'Fira Code', monospace;
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--text-muted);
		background: rgba(42, 117, 243, 0.04);
		border: 1px solid var(--border-soft);
		padding: 0.25rem 0.6rem;
		border-radius: 6px;
	}

	.badge-num {
		color: var(--brand-blue);
	}

	.status-indicator-badge {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		background: rgba(120,120,120,0.03);
		border: 1px solid var(--border-soft);
		border-radius: 6px;
		padding: 0.25rem 0.65rem;
		cursor: pointer;
		outline: none;
		height: 30px;
	}

	.status-indicator-badge:hover {
		background: rgba(120,120,120,0.08);
		border-color: var(--text-muted);
	}

	.indicator-orb {
		width: 7.5px;
		height: 7.5px;
		border-radius: 50%;
	}

	.status-indicator-badge.connected .indicator-orb {
		background: var(--brand-blue);
		box-shadow: 0 0 6px var(--brand-blue);
	}
	.status-indicator-badge.connecting .indicator-orb {
		background: var(--brand-blue-ice);
		box-shadow: 0 0 6px var(--brand-blue-ice);
		animation: pulse-indicator-ping 0.8s infinite alternate;
	}
	.status-indicator-badge.disconnected .indicator-orb {
		background: var(--brand-blue-deep);
		box-shadow: 0 0 6px var(--brand-blue-deep);
		animation: pulse-indicator-ping 0.8s infinite alternate;
	}

	@keyframes pulse-indicator-ping {
		from { opacity: 0.4; }
		to { opacity: 1; }
	}

	.indicator-label {
		font-family: 'Fira Code', monospace;
		font-size: 0.75rem;
		font-weight: 700;
		color: var(--text-main);
	}

	.theme-toggle-btn {
		background: rgba(120,120,120,0.03);
		border: 1px solid var(--border-soft);
		border-radius: 6px;
		width: 30px;
		height: 30px;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		color: var(--text-muted);
		outline: none;
	}

	.theme-toggle-btn:hover {
		background: rgba(120,120,120,0.08);
		color: var(--brand-blue);
		border-color: var(--brand-blue);
	}

	.theme-icon {
		width: 15px;
		height: 15px;
	}

	.header-nav-tabs {
		display: flex;
		gap: 0.5rem;
		height: 100%;
		align-items: center;
	}

	.nav-tab-btn {
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid var(--border-soft);
		color: var(--text-muted);
		padding: 0.25rem 0.8rem;
		border-radius: 6px;
		font-family: 'Outfit', sans-serif;
		font-size: 0.78rem;
		font-weight: 700;
		cursor: pointer;
		display: flex;
		align-items: center;
		gap: 0.4rem;
		transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
		height: 30px;
	}

	.nav-tab-btn:hover {
		background: rgba(42, 117, 243, 0.08);
		color: var(--text-main);
		border-color: rgba(42, 117, 243, 0.3);
	}

	.nav-tab-btn.active {
		background: rgba(42, 117, 243, 0.12);
		color: var(--brand-blue-neon);
		border-color: var(--brand-blue);
		box-shadow: 0 0 10px rgba(42, 117, 243, 0.15);
	}
</style>
