<script lang="ts">
	import { robotState } from '$lib/store.svelte';
</script>

<section class="glass-card telemetry-card">
	<div class="cell-header">
		<h2>TELEMETRY MATRICES</h2>
		<span class="hud-meta">ACTIVE STATE</span>
	</div>
	<div class="telemetry-bento-grid">
		<div class="tele-item">
			<span class="label">Joint (C)</span>
			<span class="value">{robotState.angles.C.toFixed(1)}°</span>
		</div>
		<div class="tele-item">
			<span class="label">Joint (B)</span>
			<span class="value">{robotState.angles.B.toFixed(1)}°</span>
		</div>
		<div class="tele-item">
			<span class="label">Joint (A)</span>
			<span class="value">{robotState.angles.A.toFixed(1)}°</span>
		</div>
		<div class="tele-item x">
			<span class="label">X-POS</span>
			<span class="value coordinate">{robotState.eePosition.x.toFixed(3)}m</span>
		</div>
		<div class="tele-item y">
			<span class="label">Y-POS</span>
			<span class="value coordinate">{robotState.eePosition.y.toFixed(3)}m</span>
		</div>
		<div class="tele-item z">
			<span class="label">Z-POS</span>
			<span class="value coordinate">{robotState.eePosition.z.toFixed(3)}m</span>
		</div>
	</div>
</section>

<style>
	.telemetry-card {
		flex: 0 0 auto;
		height: 17%;
	}
	@media (max-width: 1024px) {
		.telemetry-card {
			height: auto;
			min-height: 120px;
		}
	}
	
	.telemetry-bento-grid {
		display: grid;
		grid-template-columns: repeat(6, 1fr);
		gap: 0.4rem;
		flex: 1;
		min-height: 0;
		align-items: center;
	}

	@media (max-width: 768px) {
		.telemetry-bento-grid {
			grid-template-columns: repeat(3, 1fr);
			grid-template-rows: repeat(2, 1fr);
		}
	}

	.tele-item {
		background: var(--card-sub-bg);
		border: 1px solid var(--border-soft);
		border-radius: 6px;
		padding: 0.35rem;
		text-align: center;
		display: flex;
		flex-direction: column;
		justify-content: center;
		height: 100%;
	}

	.tele-item .label {
		font-size: 0.72rem;
		font-weight: 700;
		color: var(--text-muted);
		margin-bottom: 0.1rem;
	}

	.tele-item .value {
		font-size: 1.15rem;
		font-weight: 750;
		font-family: 'Fira Code', monospace;
		color: var(--text-main);
	}

	.tele-item .value.coordinate {
		color: var(--brand-blue-ice);
	}
</style>
