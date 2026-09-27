<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';
	import { robotState } from '$lib/store.svelte';

	let { children } = $props();

	$effect(() => {
		if (robotState.currentTheme === "dark") {
			document.documentElement.classList.add("dark");
			document.documentElement.classList.remove("light");
		} else {
			document.documentElement.classList.add("light");
			document.documentElement.classList.remove("dark");
		}
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<!-- Google Fonts: Outfit (modern sans-serif) and Fira Code (monospaced telemetry) -->
	<link rel="preconnect" href="https://fonts.googleapis.com">
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous">
	<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Outfit:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
	<title>Robot-Team1 | Telemetry Control Center</title>
</svelte:head>

<div class="app-container">
	<main class="app-main">
		{@render children()}
	</main>
</div>

<style>
	/* Theme Definitions with High Contrast Tuning */
	:global(html.dark) {
		--bg-primary: #121212;      /* Dark gray background */
		--bg-secondary: #1e1e1e;    /* Lighter gray card tile */
		--bg-tertiary: #2a2a2a;     /* Accent gray boundaries */
		
		--brand-blue: #2a75f3;      /* Royal electric blue */
		--brand-blue-deep: #124ebd; /* Deep safety blue */
		--brand-blue-ice: #70a3f9;  /* Light ice blue */
		--brand-blue-neon: #4f8cfc; /* High contrast royal blue (formerly neon) */
		
		--text-main: #f3f4f6;       /* Clean silver white */
		--text-muted: #9e9e9e;      /* Neutral gray text */
		--border-soft: rgba(255, 255, 255, 0.1); /* Neutral border */
		--border-focus: rgba(255, 255, 255, 0.3);
		
		--glass-bg: rgba(30, 30, 30, 0.85); /* Solid gray glass base */
		--glass-blur: blur(24px);
		--glass-shadow: 0 12px 48px 0 rgba(0, 0, 0, 0.6);
		--glass-card-hover-glow: rgba(42, 117, 243, 0.25);
		
		--btn-bg: #222222;
		--btn-hover: #3d3d3d;
		--btn-active: #4a4a4a;
		--card-sub-bg: rgba(255, 255, 255, 0.03);
	}

	:global(html.light) {
		--bg-primary: #f4f6f9;      /* Clean soft light background */
		--bg-secondary: #ffffff;    /* Solid white card base */
		--bg-tertiary: #e2e8f0;     /* Light cool grey boundaries */
		
		--brand-blue: #1b63e0;      /* Electric royal blue */
		--brand-blue-deep: #0a40a8; /* Deep royal blue */
		--brand-blue-ice: #1b63e0;  /* High contrast blue in light mode for readability */
		--brand-blue-neon: #2a75f3; /* Matching royal blue */
		
		--text-main: #0f172a;       /* Slate 900 for extremely crisp main text */
		--text-muted: #475569;      /* Slate 600 for highly readable muted text */
		--border-soft: rgba(27, 99, 224, 0.12);
		--border-focus: rgba(27, 99, 224, 0.4);
		
		--glass-bg: #ffffff;        /* Solid white cards for perfect contrast */
		--glass-blur: blur(0px);    /* No blur needed on solid white */
		--glass-shadow: 0 4px 20px 0 rgba(0, 0, 0, 0.05);
		--glass-card-hover-glow: rgba(27, 99, 224, 0.08);
		
		--btn-bg: rgba(0, 0, 0, 0.04);
		--btn-hover: rgba(0, 0, 0, 0.08);
		--btn-active: rgba(27, 99, 224, 0.1);
		--card-sub-bg: rgba(0, 0, 0, 0.035);
	}

	:global(body) {
		margin: 0;
		padding: 0;
		background-color: var(--bg-primary);
		color: var(--text-main);
		font-family: 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
		height: 100vh;
		overflow: hidden; /* Lock viewport scrolling on desktop */
		transition: background-color 0.3s ease, color 0.3s ease;
	}
	
	@media (max-width: 1024px) {
		:global(html), :global(body) {
			height: auto !important;
			min-height: 100vh;
			overflow-y: auto !important;
			overflow-x: hidden;
		}
		.app-container, .app-main {
			height: auto !important;
			overflow: visible !important;
		}
	}

	:global(*) {
		box-sizing: border-box;
	}

	/* Elegant minimalist scrollbars */
	:global(::-webkit-scrollbar) {
		width: 4px;
		height: 4px;
	}
	:global(::-webkit-scrollbar-track) {
		background: var(--bg-primary);
	}
	:global(::-webkit-scrollbar-thumb) {
		background: rgba(42, 117, 243, 0.25);
		border-radius: 4px;
	}
	:global(::-webkit-scrollbar-thumb:hover) {
		background: var(--brand-blue-neon);
	}

	.app-container {
		position: relative;
		height: 100vh;
		display: flex;
		flex-direction: column;
		z-index: 1;
		overflow: hidden;
	}

	/* Gemini Soft Radial Glow Waves using purely Blue corner gradients */
	.app-container::before {
		content: "";
		position: fixed;
		top: -15%;
		right: -15%;
		width: 50%;
		height: 50%;
		background: radial-gradient(circle, rgba(42, 117, 243, 0.08) 0%, rgba(0, 240, 255, 0.02) 60%, transparent 100%);
		pointer-events: none;
		z-index: -1;
	}

	.app-container::after {
		content: "";
		position: fixed;
		bottom: -15%;
		left: -15%;
		width: 50%;
		height: 50%;
		background: radial-gradient(circle, rgba(18, 78, 189, 0.06) 0%, rgba(42, 117, 243, 0.01) 60%, transparent 100%);
		pointer-events: none;
		z-index: -1;
	}

	.app-main {
		flex: 1;
		width: 100%;
		height: 100%;
		overflow: hidden;
	}
</style>
