<script lang="ts">
	import { robotState, sendJog } from '$lib/store.svelte';

	const joints = [
		{
			id: 'C',
			name: 'Shoulder',
			left: { label: 'A', dir: 'LEFT', val: 1, type: 'pos' },
			right: { label: 'D', dir: 'RIGHT', val: -1, type: 'neg' }
		},
		{
			id: 'B',
			name: 'Elbow',
			left: { label: 'W', dir: 'UP', val: -1, type: 'neg' },
			right: { label: 'S', dir: 'DOWN', val: 1, type: 'pos' }
		},
		{
			id: 'A',
			name: 'Wrist',
			left: { label: 'Q', dir: 'UP', val: -1, type: 'neg' },
			right: { label: 'E', dir: 'DOWN', val: 1, type: 'pos' }
		}
	] as const;

	function jog(joint: 'A' | 'B' | 'C', direction: number) {
		sendJog(joint, direction, robotState.pwmScale);
	}
</script>

<section class="glass-card overrides-card">
	<div class="cell-header">
		<h2>Manual Jog Controls</h2>
	</div>
	
	<div class="power-row">
		<label for="jog-power">Jog Speed Scale</label>
		<div class="slider-and-label">
			<input 
				id="jog-power" 
				type="range" 
				min="0.01" 
				max="1" 
				step="0.01" 
				bind:value={robotState.pwmScale} 
			/>
			<span class="power-percentage">{Math.round(robotState.pwmScale * 100)}%</span>
		</div>
	</div>

	<div class="controls-grid">
		{#each joints as joint}
			<div class="joint-control-row">
				<div class="joint-info-label">
					<span class="joint-id">{joint.id}</span>
					<span class="joint-name">{joint.name}</span>
				</div>
				<div class="jog-buttons-pair">
					<button
						class="btn-jog {joint.left.type}"
						onpointerdown={() => jog(joint.id, joint.left.val)}
						onpointerup={() => jog(joint.id, 0)}
						onpointerleave={() => jog(joint.id, 0)}
					>
						<span class="key-letter">{joint.left.label}</span>
						<span class="key-direction">[{joint.left.dir}]</span>
					</button>
					<button
						class="btn-jog {joint.right.type}"
						onpointerdown={() => jog(joint.id, joint.right.val)}
						onpointerup={() => jog(joint.id, 0)}
						onpointerleave={() => jog(joint.id, 0)}
					>
						<span class="key-letter">{joint.right.label}</span>
						<span class="key-direction">[{joint.right.dir}]</span>
					</button>
				</div>
			</div>
		{/each}
	</div>
</section>

<style>
	.overrides-card {
		flex: 0 0 auto;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		min-height: 230px;
	}

	.power-row {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		margin-bottom: 0.25rem;
	}

	.power-row label {
		font-size: 0.76rem;
		font-weight: 700;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.slider-and-label {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.slider-and-label input[type="range"] {
		flex: 1;
		-webkit-appearance: none;
		background: var(--bg-tertiary);
		height: 4px;
		border-radius: 2px;
		outline: none;
	}

	.slider-and-label input[type="range"]::-webkit-slider-thumb {
		-webkit-appearance: none;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: var(--brand-blue-neon);
		cursor: pointer;
		border: 2px solid var(--bg-primary);
		box-shadow: 0 0 6px var(--brand-blue-neon);
		transition: transform 0.1s ease;
	}

	.slider-and-label input[type="range"]::-webkit-slider-thumb:hover {
		transform: scale(1.2);
	}

	.power-percentage {
		font-family: 'Fira Code', monospace;
		font-size: 0.85rem;
		font-weight: 700;
		color: var(--brand-blue-ice);
		min-width: 2.5rem;
		text-align: right;
	}

	.controls-grid {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		flex: 1;
		justify-content: center;
	}

	.joint-control-row {
		display: grid;
		grid-template-columns: 1fr 220px;
		align-items: center;
		gap: 0.75rem;
	}

	.joint-info-label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.joint-id {
		font-family: 'Fira Code', monospace;
		font-size: 0.95rem;
		font-weight: 800;
		color: var(--text-main);
		background: var(--card-sub-bg);
		padding: 0.15rem 0.4rem;
		border-radius: 4px;
		border: 1px solid var(--border-soft);
	}

	.joint-name {
		font-size: 0.8rem;
		font-weight: 700;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.jog-buttons-pair {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.35rem;
	}

	.btn-jog {
		background: var(--btn-bg);
		border: 1px solid var(--border-soft);
		color: var(--text-main);
		border-radius: 6px;
		font-family: 'Outfit', sans-serif;
		font-size: 0.82rem;
		font-weight: 800;
		height: 32px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.25rem;
		transition: all 0.1s ease;
		outline: none;
	}

	.key-letter {
		color: var(--text-main);
	}

	.key-direction {
		font-family: 'Fira Code', monospace;
		font-size: 0.68rem;
		color: var(--text-muted);
		font-weight: 600;
	}

	.btn-jog:hover {
		background: var(--btn-hover);
		border-color: rgba(42, 117, 243, 0.4);
	}

	.btn-jog:active {
		background: var(--btn-active);
		border-color: var(--brand-blue);
		color: var(--brand-blue-neon);
		box-shadow: 0 0 10px rgba(42, 117, 243, 0.25);
		transform: scale(0.95);
	}
</style>
