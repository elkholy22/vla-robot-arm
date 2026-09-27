<script lang="ts">
	import { robotState, getVideoFeedUrl } from '$lib/store.svelte';

	let timestamp = $state(Date.now());
	let feedsDisabled = $state(false);

	function reloadFeeds() {
		timestamp = Date.now();
		robotState.unifiedFeed = [...robotState.unifiedFeed, {
			type: 'log',
			text: '[Client] Reloading browser camera feed streams...',
			time: new Date().toLocaleTimeString()
		}];
	}
</script>

<section class="glass-card cameras-card">
	<div class="cell-header">
		<div class="label-group">
			<h2>Camera Streams</h2>
		</div>
		<div class="header-controls">
			<button class="btn-disable-feeds" onclick={() => feedsDisabled = !feedsDisabled}>
				{feedsDisabled ? "Enable Feeds" : "Disable Feeds"}
			</button>
			<button class="btn-reload-feeds" onclick={reloadFeeds}>Reload Feeds</button>
			{#if robotState.isCapturing}
				<span class="capture-alert-badge-blue">REC ACTIVE</span>
			{/if}
		</div>
	</div>
	
	<div class="cam-streams-container">
		{#if !feedsDisabled}
			<div class="cam-box">
				<img 
					class="camera-stream-img" 
					src={`${getVideoFeedUrl(0)}?t=${timestamp}`} 
					alt="Camera 1 Stream" 
				/>
				<div class="cam-label">CAM 01 // TOP VIEW</div>
			</div>
			<div class="cam-box">
				<img 
					class="camera-stream-img" 
					src={`${getVideoFeedUrl(1)}?t=${timestamp}`} 
					alt="Camera 2 Stream" 
				/>
				<div class="cam-label">CAM 02 // WRIST VIEW</div>
			</div>
		{:else}
			<div class="cam-box">
				<div class="camera-placeholder">
					<span>FEED DISABLED</span>
				</div>
				<div class="cam-label">CAM 01 // TOP VIEW</div>
			</div>
			<div class="cam-box">
				<div class="camera-placeholder">
					<span>FEED DISABLED</span>
				</div>
				<div class="cam-label">CAM 02 // WRIST VIEW</div>
			</div>
		{/if}
	</div>
</section>

<style>
	.cameras-card {
		flex: 0 0 auto;
		min-width: 0;
	}

	.cam-streams-container {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
		margin-top: 0.5rem;
	}

	.cam-box {
		background: #08090d;
		border: 1px solid var(--border-soft);
		border-radius: 6px;
		overflow: hidden;
		display: flex;
		justify-content: center;
		align-items: center;
		position: relative;
		aspect-ratio: 4 / 3;
		width: 100%;
	}

	.label-group {
		display: flex;
		align-items: center;
		gap: 0.45rem;
	}

	.cameras-card :global(.cell-header h2) {
		font-size: 0.8rem;
	}

	.cameras-card :global(.cell-header) {
		margin-bottom: 0.4rem;
		padding-bottom: 0.25rem;
	}

	.capture-alert-badge-blue {
		font-family: 'Fira Code', monospace;
		font-size: 0.6rem;
		font-weight: 700;
		background: rgba(42,117,243,0.15);
		color: var(--brand-blue);
		border: 1px solid rgba(42,117,243,0.3);
		padding: 0.1rem 0.4rem;
		border-radius: 4px;
	}

	.camera-stream-img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}

	.camera-placeholder {
		display: flex;
		justify-content: center;
		align-items: center;
		width: 100%;
		height: 100%;
		color: var(--text-muted);
		font-family: 'Fira Code', monospace;
		font-size: 0.65rem;
		font-weight: 700;
		opacity: 0.6;
	}

	.header-controls {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}

	.cam-label {
		position: absolute;
		bottom: 8px;
		left: 8px;
		font-family: 'Fira Code', monospace;
		font-size: 7.5px;
		font-weight: 700;
		color: rgba(255, 255, 255, 0.85);
		background: rgba(0, 0, 0, 0.75);
		padding: 1.5px 5px;
		border-radius: 3px;
		border: 1px solid rgba(255, 255, 255, 0.1);
		max-width: calc(100% - 16px);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.btn-reload-feeds, .btn-disable-feeds {
		background: rgba(120, 120, 120, 0.03);
		border: 1px solid var(--border-soft);
		color: var(--text-muted);
		font-family: 'Outfit', sans-serif;
		font-size: 0.65rem;
		font-weight: 700;
		padding: 0.2rem 0.5rem;
		border-radius: 4px;
		cursor: pointer;
		transition: all 0.15s ease;
		outline: none;
	}

	.btn-reload-feeds:hover {
		background: rgba(42, 117, 243, 0.08);
		color: var(--text-main);
		border-color: var(--brand-blue);
		box-shadow: 0 0 8px rgba(42, 117, 243, 0.15);
	}

	.btn-disable-feeds:hover {
		background: rgba(220, 50, 50, 0.08);
		color: var(--text-main);
		border-color: rgba(220, 50, 50, 0.4);
		box-shadow: 0 0 8px rgba(220, 50, 50, 0.15);
	}
</style>
