<script lang="ts">
	import { 
		robotState, 
		loadDatasets, 
		loadDatasetDetails, 
		loadStepTelemetry, 
		deleteDataset,
		getDatasetStepImageUrl 
	} from '$lib/store.svelte';
	import { onMount } from 'svelte';

	let isPlaying = $state(false);
	let playInterval = $state<any>(null);
	let isRefreshing = $state(false);

	// Heatmap modal state
	let showHeatmap = $state(false);
	let heatmapSrc = $state('');

	function openHeatmap() {
		// Global heatmap showing all episodes' switch positions
		heatmapSrc = `/api/heatmap_output/switch_position_kde.png`;
		showHeatmap = true;
	}

	function closeHeatmap() {
		showHeatmap = false;
	}

	function handleHeatmapError(e: Event) {
		console.warn('Failed to load heatmap image', e);
		// keep modal open but replace image with a small message or close
		showHeatmap = false;
	}

	async function handleRefresh() {
		isRefreshing = true;
		await loadDatasets();
		setTimeout(() => {
			isRefreshing = false;
		}, 600);
	}

	let filteredDatasets = $derived(robotState.datasetList);

	onMount(() => {
		loadDatasets();
	});

	function selectDataset(id: string) {
		if (robotState.selectedDatasetId === id) return;
		if (isPlaying) togglePlay();
		loadDatasetDetails(id);
	}

	function handleSliderChange(e: Event) {
		const slider = e.target as HTMLInputElement;
		const val = parseInt(slider.value, 10);
		if (robotState.selectedDatasetId !== null) {
			loadStepTelemetry(robotState.selectedDatasetId, val);
		}
	}

	function togglePlay() {
		isPlaying = !isPlaying;
		if (isPlaying) {
			playInterval = setInterval(() => {
				if (robotState.selectedDatasetDetails) {
					const maxSteps = robotState.selectedDatasetDetails.step_count;
					if (maxSteps > 0) {
						let nextStep = robotState.currentPlaybackStep + 1;
						if (nextStep >= maxSteps) {
							nextStep = 0;
						}
						if (robotState.selectedDatasetId) {
							loadStepTelemetry(robotState.selectedDatasetId, nextStep);
						}
					}
				}
			}, 200); // 5Hz playback speed
		} else {
			clearInterval(playInterval);
		}
	}

	function stepForward() {
		if (robotState.selectedDatasetDetails && robotState.selectedDatasetId) {
			const maxSteps = robotState.selectedDatasetDetails.step_count;
			const nextStep = Math.min(maxSteps - 1, robotState.currentPlaybackStep + 1);
			loadStepTelemetry(robotState.selectedDatasetId, nextStep);
		}
	}

	function stepBackward() {
		if (robotState.selectedDatasetDetails && robotState.selectedDatasetId) {
			const nextStep = Math.max(0, robotState.currentPlaybackStep - 1);
			loadStepTelemetry(robotState.selectedDatasetId, nextStep);
		}
	}

	let pendingDeleteId = $state<string | null>(null);

	function handleStartDelete(id: string, e: Event) {
		e.stopPropagation();
		pendingDeleteId = id;
	}

	function handleConfirmDelete(id: string, e: Event) {
		e.stopPropagation();
		if (isPlaying && robotState.selectedDatasetId === id) {
			togglePlay();
		}
		deleteDataset(id);
		pendingDeleteId = null;
	}

	function handleCancelDelete(e: Event) {
		e.stopPropagation();
		pendingDeleteId = null;
	}

	function handleDownloadEpisode(id: string, e?: Event) {
		if (e) e.stopPropagation();
		const link = document.createElement('a');
		link.href = `/api/dataset/${id}/download`;
		link.download = `${id}.tar.gz`;
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
	}

	function downloadAll() {
		const link = document.createElement('a');
		link.href = `/api/datasets/download`;
		link.download = `all_episodes.tar.gz`;
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
	}

	function navigateList(direction: number) {
		if (filteredDatasets.length === 0) return;
		const currentIndex = filteredDatasets.findIndex(ds => ds.id === robotState.selectedDatasetId);
		let nextIndex = currentIndex + direction;
		if (currentIndex === -1) {
			nextIndex = direction > 0 ? 0 : filteredDatasets.length - 1;
		} else {
			nextIndex = (nextIndex + filteredDatasets.length) % filteredDatasets.length;
		}
		const nextDataset = filteredDatasets[nextIndex];
		if (nextDataset) {
			selectDataset(nextDataset.id);
		}
	}

	function handleGlobalKeyDown(e: KeyboardEvent) {
		// allow Escape to close modal
		if (showHeatmap && e.key === 'Escape') {
			closeHeatmap();
			return;
		}
		if (robotState.activeTab !== 'datasets') return;
		
		const activeElement = document.activeElement;
		const isTyping = activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA');
		if (isTyping) return;

		if (e.key === 'ArrowDown') {
			e.preventDefault();
			navigateList(1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			navigateList(-1);
		} else if (e.key === 'ArrowLeft') {
			e.preventDefault();
			stepBackward();
		} else if (e.key === 'ArrowRight') {
			e.preventDefault();
			stepForward();
		}
	}
</script>

<svelte:window onkeydown={handleGlobalKeyDown} />

<section class="glass-card dataset-manager-card">
	<div class="cell-header">
		<div class="label-group">
			<h2>Dataset Manager</h2>
		</div>
		<div class="header-controls">
			<button class="download-all-btn" onclick={downloadAll}>Download All</button>
			<!-- New Show Heatmap button -->
			<button class="download-all-btn heatmap-btn" onclick={() => openHeatmap()} title="Show Heatmap">Show Heatmap</button>
			<button class="refresh-btn" disabled={isRefreshing} onclick={handleRefresh}>
				{isRefreshing ? "Refreshing..." : "Refresh"}
			</button>
		</div>
	</div>

	<div class="dataset-split-layout">
		<!-- Left Panel: File Explorer List -->
		<div class="file-explorer-panel">
			<div class="explorer-table-header">
				<div class="col-name">Episode ID</div>
				<div class="col-goal">Goal Prompt</div>
				<div class="col-time">Start Time</div>
				<div class="col-steps text-center">Steps</div>
				<div class="col-actions"></div>
			</div>
			
			<div class="explorer-list">
				{#if filteredDatasets.length === 0}
					<div class="empty-list-message">
						<span class="empty-list-icon">📂</span>
						<p>No recorded episodes found.</p>
					</div>
				{:else}
					{#each filteredDatasets as ds}
						<div 
							class="explorer-row" 
							class:selected={robotState.selectedDatasetId === ds.id}
							onclick={() => selectDataset(ds.id)}
							role="button"
							tabindex="0"
							onkeydown={(e) => e.key === 'Enter' && selectDataset(ds.id)}
						>
							<div class="col-name">
								<span class="file-icon">📁</span>
								<span class="file-name code-font" title={ds.id}>{ds.id}</span>
							</div>
							<div class="col-goal text-truncate" title={ds.goal_text}>
								"{ds.goal_text}"
							</div>
							<div class="col-time">
								{ds.start_time}
							</div>
							<div class="col-steps text-center">
								{ds.step_count !== undefined ? ds.step_count : '-'}
							</div>
							<div class="col-actions">
								{#if pendingDeleteId === ds.id}
									<button 
										class="btn-confirm-delete" 
										onclick={(e) => handleConfirmDelete(ds.id, e)}
										title="Confirm Deletion"
									>
										CONFIRM
									</button>
									<button 
										class="btn-cancel-delete" 
										onclick={(e) => handleCancelDelete(e)}
										title="Cancel"
									>
										✕
									</button>
								{:else}
									<button 
										class="btn-download" 
										onclick={(e) => handleDownloadEpisode(ds.id, e)}
										title="Download Episode"
									>
										<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
											<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
											<polyline points="7 10 12 15 17 10"></polyline>
											<line x1="12" y1="15" x2="12" y2="3"></line>
										</svg>
									</button>
									<button 
										class="btn-delete" 
										onclick={(e) => handleStartDelete(ds.id, e)}
										title="Delete Episode"
									>
										<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
											<polyline points="3 6 5 6 21 6"></polyline>
											<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
											<line x1="10" y1="11" x2="10" y2="17"></line>
											<line x1="14" y1="11" x2="14" y2="17"></line>
										</svg>
									</button>
								{/if}
							</div>
						</div>
					{/each}
				{/if}
			</div>
		</div>

		<!-- Heatmap Modal (outside loop) -->
		{#if showHeatmap}
			<div class="heatmap-modal" role="dialog" aria-modal="true" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && closeHeatmap()}>
				<div class="heatmap-card" role="group">
					<button type="button" class="modal-close" onclick={() => closeHeatmap()} title="Close">✕</button>
					<img src={heatmapSrc} alt="Switch position heatmap" onerror={handleHeatmapError} />
				</div>
			</div>
		{/if}

		<!-- Right Panel: Inspector Pane -->
		<div class="inspector-panel">
			{#if robotState.selectedDatasetId && robotState.selectedDatasetDetails}
				<div class="inspector-content">
					<div class="inspector-section-header">
						<h3>Episode Inspector</h3>
						<button 
							class="download-episode-btn-inspector" 
							onclick={() => handleDownloadEpisode(robotState.selectedDatasetDetails.id)}
							title="Download tar.gz"
						>
							Download Tarball
						</button>
					</div>
					
					<div class="inspector-meta-grid">
						<div class="meta-card">
							<span class="meta-label">Episode ID</span>
							<span class="meta-value code-font">{robotState.selectedDatasetDetails.id}</span>
						</div>
						<div class="meta-card">
							<span class="meta-label">Goal Prompt</span>
							<span class="meta-value highlight">"{robotState.selectedDatasetDetails.metadata?.goal_text || 'None'}"</span>
						</div>
						<div class="meta-card">
							<span class="meta-label">Total Steps</span>
							<span class="meta-value">{robotState.selectedDatasetDetails.step_count}</span>
						</div>
						<div class="meta-card">
							<span class="meta-label">Start Time</span>
							<span class="meta-value">{robotState.selectedDatasetDetails.metadata?.start_time || 'Unknown'}</span>
						</div>
					</div>

					<!-- Media player area -->
					<div class="player-panel">
						<div class="step-frames-grid">
							<div class="step-frame-box">
								<img 
									src={getDatasetStepImageUrl(robotState.selectedDatasetId, robotState.currentPlaybackStep, 0)} 
									alt="Step Top View"
								/>
								<span class="frame-tag">STEP {robotState.currentPlaybackStep} // CAM 01</span>
							</div>
							<div class="step-frame-box">
								<img 
									src={getDatasetStepImageUrl(robotState.selectedDatasetId, robotState.currentPlaybackStep, 1)} 
									alt="Step Wrist View"
								/>
								<span class="frame-tag">STEP {robotState.currentPlaybackStep} // CAM 02</span>
							</div>
						</div>

						<!-- Telemetry overlay of step -->
						{#if robotState.datasetStepTelemetry}
							<div class="step-telemetry-strip">
								<div class="telemetry-item">
									<div class="t-val code-font">
										A: {robotState.datasetStepTelemetry.calibrated_joint_angles?.[0]?.toFixed(1) || '0.0'}° | 
										B: {robotState.datasetStepTelemetry.calibrated_joint_angles?.[1]?.toFixed(1) || '0.0'}° | 
										C: {robotState.datasetStepTelemetry.calibrated_joint_angles?.[2]?.toFixed(1) || '0.0'}°
									</div>
									<div class="t-lbl">Joint Angles</div>
								</div>
								<div class="telemetry-item">
									<div class="t-val code-font">
										X: {robotState.datasetStepTelemetry.ee_position?.[0]?.toFixed(3) || '0.000'}m | 
										Y: {robotState.datasetStepTelemetry.ee_position?.[1]?.toFixed(3) || '0.000'}m | 
										Z: {robotState.datasetStepTelemetry.ee_position?.[2]?.toFixed(3) || '0.000'}m
									</div>
									<div class="t-lbl">End-Effector XYZ</div>
								</div>
								<div class="telemetry-item">
									<div class="t-val code-font">
										{robotState.datasetStepTelemetry.language_instruction || 'None'}
									</div>
									<div class="t-lbl">Instruction</div>
								</div>
							</div>
						{/if}

						<!-- Timeline scrubber -->
						<div class="timeline-controls-container">
							<div class="timeline-slider-group">
								<span class="time-code">STEP {robotState.currentPlaybackStep}</span>
								<input 
									type="range" 
									min="0" 
									max={robotState.selectedDatasetDetails.step_count - 1} 
									value={robotState.currentPlaybackStep}
									oninput={handleSliderChange}
									class="timeline-slider"
								/>
								<span class="time-code">{robotState.selectedDatasetDetails.step_count - 1}</span>
							</div>

							<div class="playback-buttons">
								<button class="playback-btn secondary" onclick={stepBackward} title="Previous Step">◀</button>
								<button 
									class="playback-btn primary" 
									class:playing={isPlaying}
									onclick={togglePlay}
								>
									{isPlaying ? 'PAUSE' : 'PLAY'}
								</button>
								<button class="playback-btn secondary" onclick={stepForward} title="Next Step">▶</button>
							</div>
						</div>
					</div>
				</div>
			{:else}
				<div class="empty-inspector-state">
					<div class="empty-icon">🔍</div>
					<h3>No Episode Selected</h3>
					<p>Select a recorded episode from the explorer pane to inspect the images, telemetry data, and playback.</p>
				</div>
			{/if}
		</div>
	</div>
</section>

<style>
	.dataset-manager-card {
		flex: 1 1 auto;
		display: flex;
		flex-direction: column;
		min-width: 0;
		height: 100%;
	}


	.refresh-btn {
		margin-left: 0.5rem;
		background: var(--btn-bg);
		border: 1px solid var(--border-soft);
		color: var(--text-muted);
		border-radius: 6px;
		font-family: 'Outfit', sans-serif;
		font-size: 0.75rem;
		font-weight: 700;
		cursor: pointer;
		padding: 0.3rem 0.75rem;
		transition: all 0.15s ease;
		outline: none;
	}

	.refresh-btn:hover {
		background: var(--btn-hover);
		color: var(--text-main);
		border-color: var(--brand-blue);
		box-shadow: 0 0 10px rgba(42, 117, 243, 0.2);
	}

	.refresh-btn:active {
		background: var(--btn-active);
	}

	.dataset-split-layout {
		display: grid;
		grid-template-columns: 1.15fr 0.85fr;
		gap: 1.25rem;
		margin-top: 0.75rem;
		flex: 1;
		min-height: 0;
		height: calc(100vh - 160px); /* Fill screen space nicely */
	}

	/* File Explorer Panel */
	.file-explorer-panel {
		background: var(--card-sub-bg);
		border: 1px solid var(--border-soft);
		border-radius: 8px;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		height: 100%;
	}

	.explorer-table-header {
		display: grid;
		grid-template-columns: 1.6fr 1.6fr 1.2fr 0.6fr 100px;
		gap: 0.5rem;
		padding: 0.65rem 0.85rem;
		background: var(--card-sub-bg);
		border-bottom: 1px solid var(--border-soft);
		font-size: 0.68rem;
		text-transform: uppercase;
		font-weight: 700;
		color: var(--text-muted);
		letter-spacing: 0.05em;
	}

	.explorer-list {
		flex: 1;
		overflow-y: auto;
	}

	.explorer-row {
		display: grid;
		grid-template-columns: 1.6fr 1.6fr 1.2fr 0.6fr 100px;
		gap: 0.5rem;
		padding: 0.7rem 0.85rem;
		border-bottom: 1px solid var(--border-soft);
		font-size: 0.78rem;
		align-items: center;
		cursor: pointer;
		color: var(--text-main);
		background: transparent;
		transition: background-color 0.15s ease;
	}

	.explorer-row:hover {
		background: var(--btn-hover);
	}

	.explorer-row.selected {
		background: rgba(42, 117, 243, 0.15) !important;
		border-left: 3px solid var(--brand-blue);
		padding-left: calc(0.85rem - 3px);
	}

	.col-name {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		min-width: 0;
	}

	.file-icon {
		font-size: 0.85rem;
		flex-shrink: 0;
	}

	.file-name {
		font-size: 0.72rem;
		color: var(--text-main);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.col-goal {
		color: var(--brand-blue-ice);
		font-style: italic;
	}

	.text-truncate {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.col-time {
		color: var(--text-muted);
		font-size: 0.72rem;
	}

	.text-center {
		text-align: center;
	}

	.col-actions {
		display: flex;
		justify-content: center;
		align-items: center;
	}

	.btn-delete {
		background: transparent;
		border: none;
		color: var(--text-muted);
		padding: 4px;
		cursor: pointer;
		border-radius: 4px;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.15s ease;
	}

	.btn-delete:hover {
		color: #ef4444;
		background: rgba(239, 68, 68, 0.15);
	}

	.btn-confirm-delete {
		background: #ef4444;
		border: 1px solid #dc2626;
		color: #fff;
		border-radius: 4px;
		font-family: 'Outfit', sans-serif;
		font-size: 0.68rem;
		font-weight: 800;
		cursor: pointer;
		padding: 0.2rem 0.4rem;
		transition: all 0.15s ease;
		outline: none;
	}

	.btn-confirm-delete:hover {
		background: #dc2626;
		box-shadow: 0 0 8px rgba(239, 68, 68, 0.45);
	}

	.btn-cancel-delete {
		background: transparent;
		border: 1px solid var(--border-soft);
		color: var(--text-muted);
		border-radius: 4px;
		font-family: 'Outfit', sans-serif;
		font-size: 0.68rem;
		font-weight: 800;
		cursor: pointer;
		padding: 0.2rem 0.35rem;
		margin-left: 0.25rem;
		transition: all 0.15s ease;
		outline: none;
	}

	.btn-cancel-delete:hover {
		color: var(--text-main);
		border-color: var(--text-muted);
		background: rgba(255, 255, 255, 0.05);
	}

	.empty-list-message {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 4rem 2rem;
		color: var(--text-muted);
		text-align: center;
	}

	.empty-list-icon {
		font-size: 2.2rem;
		margin-bottom: 0.5rem;
	}

	.empty-list-message p {
		margin: 0;
		font-size: 0.85rem;
	}

	/* Inspector Panel */
	.inspector-panel {
		background: var(--card-sub-bg);
		border: 1px solid var(--border-soft);
		border-radius: 8px;
		padding: 1rem;
		display: flex;
		flex-direction: column;
		height: 100%;
		overflow-y: auto;
	}

	.inspector-content {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		height: 100%;
	}

	.inspector-section-header {
		border-bottom: 1px solid var(--border-soft);
		padding-bottom: 0.5rem;
		flex-shrink: 0;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.inspector-section-header h3 {
		margin: 0;
		font-size: 0.85rem;
		font-weight: 800;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.8px;
	}

	.inspector-meta-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.5rem;
		flex-shrink: 0;
	}

	.meta-card {
		background: var(--card-sub-bg);
		border: 1px solid var(--border-soft);
		border-radius: 6px;
		padding: 0.5rem 0.6rem;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.meta-label {
		color: var(--text-muted);
		font-size: 0.62rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.meta-value {
		color: var(--text-main);
		font-size: 0.75rem;
		font-weight: 500;
		word-break: break-all;
	}

	.meta-value.highlight {
		color: var(--brand-blue-neon);
		font-style: italic;
	}

	.player-panel {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		flex: 1;
		min-height: 0;
	}

	.step-frames-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.5rem;
	}

	.step-frame-box {
		background: #08090d;
		border: 1px solid var(--border-soft);
		border-radius: 6px;
		overflow: hidden;
		position: relative;
		aspect-ratio: 4 / 3;
	}

	.step-frame-box img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}

	.frame-tag {
		position: absolute;
		bottom: 6px;
		left: 6px;
		font-family: 'Fira Code', monospace;
		font-size: 7.5px;
		font-weight: 700;
		color: rgba(255, 255, 255, 0.85);
		background: rgba(0, 0, 0, 0.75);
		padding: 2px 5px;
		border-radius: 3px;
		border: 1px solid rgba(255, 255, 255, 0.1);
	}

	.step-telemetry-strip {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
		gap: 0.4rem;
		background: var(--card-sub-bg);
		border: 1px solid var(--border-soft);
		border-radius: 6px;
		padding: 0.4rem;
	}

	.telemetry-item {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
	}

	.t-lbl {
		color: var(--text-muted);
		font-size: 0.6rem;
		text-transform: uppercase;
	}

	.t-val {
		color: var(--text-main);
		font-size: 0.7rem;
		text-align: center;
	}

	.timeline-controls-container {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		background: var(--card-sub-bg);
		border: 1px solid var(--border-soft);
		border-radius: 6px;
		padding: 0.6rem;
		margin-top: auto; /* Push to bottom of player panel */
	}

	.timeline-slider-group {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.time-code {
		font-family: 'Fira Code', monospace;
		font-size: 0.7rem;
		color: var(--text-muted);
		min-width: 50px;
	}

	.timeline-slider {
		flex: 1;
		accent-color: var(--brand-blue);
		height: 4px;
		border-radius: 2px;
		outline: none;
		cursor: pointer;
	}

	.playback-buttons {
		display: flex;
		justify-content: center;
		gap: 0.4rem;
	}

	.playback-btn {
		background: var(--btn-bg);
		border: 1px solid var(--border-soft);
		color: var(--text-muted);
		border-radius: 6px;
		font-family: 'Outfit', sans-serif;
		font-size: 0.78rem;
		font-weight: 700;
		cursor: pointer;
		padding: 0.45rem 0.8rem;
		transition: all 0.15s ease;
		outline: none;
		display: flex;
		align-items: center;
		justify-content: center;
		min-width: 44px;
	}

	.playback-btn:hover {
		background: var(--btn-hover);
		color: var(--text-main);
		border-color: var(--brand-blue);
		box-shadow: 0 0 10px rgba(42, 117, 243, 0.2);
	}

	.playback-btn:active {
		background: var(--btn-active);
	}

	.playback-btn.primary {
		background: var(--btn-active);
		color: var(--brand-blue-neon);
		border-color: var(--brand-blue);
		width: 76px;
	}

	.playback-btn.primary:hover {
		background: var(--btn-hover);
		color: var(--text-main);
		box-shadow: 0 0 12px rgba(42, 117, 243, 0.25);
	}

	.playback-btn.primary.playing {
		color: var(--brand-blue-neon);
		border-color: var(--brand-blue);
		animation: pulse-blue-rec 1.2s infinite alternate;
	}

	@keyframes pulse-blue-rec {
		from { box-shadow: 0 0 4px rgba(42, 117, 243, 0.35); }
		to { box-shadow: 0 0 12px rgba(42, 117, 243, 0.75); }
	}

	.empty-inspector-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		flex: 1;
		text-align: center;
		padding: 3rem 1rem;
		color: var(--text-muted);
	}

	.empty-icon {
		font-size: 2.2rem;
		margin-bottom: 0.5rem;
	}

	.empty-inspector-state h3 {
		margin: 0.5rem 0 0.25rem 0;
		font-size: 0.95rem;
		color: var(--text-main);
	}

	.empty-inspector-state p {
		font-size: 0.78rem;
		max-width: 250px;
		margin: 0;
	}

	.download-all-btn {
		margin-left: 0.5rem;
		background: rgba(42, 117, 243, 0.15);
		border: 1px solid rgba(42, 117, 243, 0.4);
		color: var(--brand-blue-ice);
		border-radius: 6px;
		font-family: 'Outfit', sans-serif;
		font-size: 0.75rem;
		font-weight: 700;
		cursor: pointer;
		padding: 0.3rem 0.75rem;
		transition: all 0.15s ease;
		outline: none;
	}

	.download-all-btn:hover {
		background: rgba(42, 117, 243, 0.25);
		color: var(--text-main);
		border-color: var(--brand-blue);
		box-shadow: 0 0 10px rgba(42, 117, 243, 0.3);
	}

	.download-all-btn:active {
		background: rgba(42, 117, 243, 0.35);
	}

	.btn-download {
		background: transparent;
		border: none;
		color: var(--text-muted);
		padding: 4px;
		cursor: pointer;
		border-radius: 4px;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.15s ease;
		margin-right: 0.25rem;
	}

	.btn-download:hover {
		color: var(--brand-blue-ice);
		background: rgba(42, 117, 243, 0.15);
	}

	.download-episode-btn-inspector {
		background: var(--btn-bg);
		border: 1px solid var(--border-soft);
		color: var(--text-muted);
		border-radius: 4px;
		font-family: 'Outfit', sans-serif;
		font-size: 0.68rem;
		font-weight: 700;
		cursor: pointer;
		padding: 0.25rem 0.5rem;
		transition: all 0.15s ease;
		outline: none;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.download-episode-btn-inspector:hover {
		background: var(--btn-hover);
		color: var(--text-main);
		border-color: var(--brand-blue);
		box-shadow: 0 0 10px rgba(42, 117, 243, 0.2);
	}

	.download-episode-btn-inspector:active {
		background: var(--btn-active);
	}

	.refresh-btn {
		margin-left: 0.5rem;
		background: rgba(16, 185, 129, 0.15);
		border: 1px solid rgba(16, 185, 129, 0.4);
		color: #10b981;
		border-radius: 6px;
		font-family: 'Outfit', sans-serif;
		font-size: 0.75rem;
		font-weight: 700;
		cursor: pointer;
		padding: 0.3rem 0.75rem;
		transition: all 0.15s ease;
		outline: none;
		width: 96px;
	}

	.refresh-btn:hover:not(:disabled) {
		background: rgba(16, 185, 129, 0.25);
		color: var(--text-main);
		border-color: #10b981;
		box-shadow: 0 0 10px rgba(16, 185, 129, 0.3);
	}

	.refresh-btn:active:not(:disabled) {
		background: rgba(16, 185, 129, 0.35);
	}

	.refresh-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	/* Heatmap button (purple) */
	.heatmap-btn {
		margin-left: 0.5rem;
		background: rgba(128, 90, 200, 0.12);
		border: 1px solid rgba(128, 90, 200, 0.35);
		color: #7c3aed;
		border-radius: 6px;
		font-family: 'Outfit', sans-serif;
		font-size: 0.75rem;
		font-weight: 700;
		cursor: pointer;
		padding: 0.3rem 0.75rem;
		transition: all 0.15s ease;
		outline: none;
	}

	.heatmap-btn:hover {
		background: rgba(124, 58, 237, 0.18);
		color: var(--text-main);
		border-color: rgba(124, 58, 237, 0.5);
		box-shadow: 0 0 10px rgba(124, 58, 237, 0.25);
	}

	/* Modal styles */
	.heatmap-modal {
		position: fixed;
		inset: 0;
		background: rgba(0,0,0,0.45);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1200;
	}

	.heatmap-card {
		background: var(--card-bg);
		border: 1px solid var(--border-soft);
		padding: 0.6rem;
		border-radius: 8px;
		max-width: 85vw;
		max-height: 85vh;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.heatmap-card img {
		max-width: calc(85vw - 48px);
		max-height: calc(85vh - 48px);
		display: block;
		object-fit: contain;
	}

	.modal-close {
		position: absolute;
		top: 16px;
		right: 18px;
		background: rgba(177, 39, 39, 0.95);
		border: 1px solid rgba(224, 197, 197, 0.9);
		color: rgba(224, 197, 197, 0.9);
		border-radius: 6px;
		width: 34px;
		height: 34px;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		font-weight: 700;
	}

	@media (max-width: 1024px) {
		.dataset-split-layout {
			grid-template-columns: 1fr;
			height: auto;
		}
		.file-explorer-panel, .inspector-panel {
			height: 500px;
		}
	}
</style>
