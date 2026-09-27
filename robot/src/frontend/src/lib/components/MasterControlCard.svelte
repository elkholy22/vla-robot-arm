<script lang="ts">
	import { 
		robotState, 
		toggleKeyboard, 
		toggleController, 
		triggerStop, 
		triggerUnblock,
		triggerHoming, 
		startCalibration, 
		stopCalibration, 
		toggleDatasetCapture,
		submitChatCommand
	} from '$lib/store.svelte';

	function approveVla() {
		submitChatCommand("vla_approve", true);
	}

	function rejectVla() {
		submitChatCommand("vla_reject", true);
	}

	function triggerInference() {
		submitChatCommand("vla_trigger_inference", true);
	}
</script>

<section class="glass-card master-actions-card">
	<div class="cell-header">
		<h2>Master Control</h2>
		<span class="hud-meta">LEASE: {robotState.leaseHolder}</span>
	</div>
	
	<div class="master-split-container">
		<!-- LEFT SIDE: Toggles and operations -->
		<div class="master-left-side">
			
			<div class="master-toggles-row">
				<button 
					class="master-pill-btn keyboard {robotState.keyboardEnabled ? 'active' : ''}" 
					onclick={toggleKeyboard}
					title="Toggle Keyboard Controls">
					<svg viewBox="0 0 24 24" class="master-pill-icon">
						<path fill="currentColor" d="M19,15H5V9H19M19,7H5A2,2 0 0,0 3,9V15A2,2 0 0,0 5,17H19A2,2 0 0,0 21,15V9A2,2 0 0,0 19,7M6,14H8V12H6V14M9,14H11V12H9V14M12,14H15V12H12V14M16,14H18V12H16V14M6,11H8V10H6V11M9,11H11V10H9V11M12,11H14V10H12V11M15,11H17V10H15V11" />
					</svg>
					<span>KEYBOARD</span>
				</button>
				
				<button 
					class="master-pill-btn controller {robotState.controllerEnabled ? 'active' : ''}" 
					onclick={toggleController}
					title="Toggle Xbox Gamepad Controller Input">
					<svg viewBox="0 0 24 24" class="master-pill-icon">
						<path fill="currentColor" d="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M7.5,6.5A1.5,1.5 0 0,1 9,8A1.5,1.5 0 0,1 7.5,9.5A1.5,1.5 0 0,1 6,8A1.5,1.5 0 0,1 7.5,6.5M16.5,6.5A1.5,1.5 0 0,1 18,8A1.5,1.5 0 0,1 16.5,9.5A1.5,1.5 0 0,1 15,8A1.5,1.5 0 0,1 16.5,6.5M12,10A2,2 0 0,1 14,12A2,2 0 0,1 12,14A2,2 0 0,1 10,12A2,2 0 0,1 12,10Z" />
					</svg>
					<span>CONTROLLER</span>
				</button>
			</div>

			<div class="master-actions-list">
				<div class="btn-row">
					<button 
						class="btn-master-action" 
						disabled={robotState.isHoming} 
						onclick={triggerHoming}>
						{robotState.isHoming ? "Homing..." : "Home"}
					</button>
					{#if robotState.isCalibrating}
						<button 
							class="btn-master-action active-calibrating" 
							onclick={stopCalibration}>
							Lock Zero
						</button>
					{:else}
						<button 
							class="btn-master-action" 
							onclick={startCalibration}>
							Calibrate
						</button>
					{/if}
					<button 
						class="btn-master-action" 
						class:active-recording={robotState.isCapturing} 
						onclick={toggleDatasetCapture}>
						{robotState.isCapturing ? "Stop Capture" : "Start Capture"}
					</button>
				</div>
				
				<div class="vla-mode-container">
					<span class="vla-label">VLA SAFETY GATE</span>
					<div class="vla-btn-group">
						<button 
							class="btn-vla-mode block" 
							class:active={robotState.vlaMode === 'block'} 
							onclick={() => submitChatCommand('vla_mode block', true)} 
							title="BLOCK: Disallow all VLA commands">
							Block
						</button>
						<button 
							class="btn-vla-mode moderated" 
							class:active={robotState.vlaMode === 'moderated'} 
							onclick={() => submitChatCommand('vla_mode moderated', true)} 
							title="MODERATE: Wait for manual user approval before running VLA commands">
							Moderate
						</button>
						<button 
							class="btn-vla-mode auto" 
							class:active={robotState.vlaMode === 'auto'} 
							onclick={() => submitChatCommand('vla_mode auto', true)} 
							title="AUTO: Execute VLA commands immediately">
							Auto
						</button>
					</div>
				</div>
			</div>

		</div>

		<!-- RIGHT SIDE: Emergency Stop & VLA Moderation Alert -->
		<div class="master-right-side">
			{#if !robotState.hasReceivedTelemetry}
				<button class="btn-emergency-halt-right-half btn-connecting" disabled>
					CONNECTING...
				</button>
			{:else if robotState.hasPendingVla}
				<div class="vla-alert-box">
					<div class="vla-alert-title">🤖 VLA ACTION PENDING</div>
					<div class="vla-alert-btns">
						<button class="btn-vla-approve" onclick={approveVla}>APPROVE</button>
						<button class="btn-vla-reject" onclick={rejectVla}>REJECT</button>
					</div>
				</div>
			{:else}
				{#if robotState.robotStatus === 'ESTOPPED'}
					<button class="btn-emergency-halt-right-half btn-unlock" onclick={triggerUnblock}>
						UNLOCK ARM
					</button>
				{:else}
					<button class="btn-emergency-halt-right-half" onclick={triggerStop}>
						EMERGENCY STOP
					</button>
				{/if}
			{/if}
		</div>
	</div>

	{#if robotState.vlaMode === 'moderated' && !robotState.hasPendingVla}
		<div class="vla-inference-trigger-strip">
			<button class="btn btn-primary btn-xs w-full" onclick={triggerInference}>Trigger Next VLA Agent Step</button>
		</div>
	{/if}
</section>

<style>
	.master-actions-card {
		flex: 0 0 auto;
	}

	.master-split-container {
		display: grid;
		grid-template-columns: 1.2fr 1fr;
		gap: 0.65rem;
		margin-top: 0.5rem;
	}

	.master-left-side {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.vla-mode-container {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		margin-top: 0.15rem;
	}

	.vla-label {
		font-size: 0.72rem;
		font-weight: 700;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.vla-btn-group {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
		gap: 0.35rem;
	}

	.btn-vla-mode {
		background: var(--btn-bg);
		border: 1px solid var(--border-soft);
		color: var(--text-muted);
		border-radius: 6px;
		font-family: 'Outfit', sans-serif;
		font-size: 0.78rem;
		font-weight: 700;
		cursor: pointer;
		padding: 0.45rem;
		transition: all 0.15s ease;
		outline: none;
		text-align: center;
	}

	.btn-vla-mode:hover {
		background: var(--btn-hover);
		color: var(--text-main);
		border-color: rgba(42, 117, 243, 0.4);
	}

	.btn-vla-mode.active {
		background: var(--btn-active);
		color: var(--brand-blue-neon);
		border-color: var(--brand-blue);
		box-shadow: 0 0 10px rgba(42, 117, 243, 0.25);
	}

	.master-toggles-row {
		display: flex;
		gap: 0.5rem;
	}

	.master-actions-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.btn-row {
		display: flex;
		gap: 0.5rem;
	}

	.master-pill-btn {
		flex: 1;
		background: var(--btn-bg);
		border: 1px solid var(--border-soft);
		color: var(--text-muted);
		border-radius: 6px;
		font-family: 'Outfit', sans-serif;
		font-size: 0.72rem;
		font-weight: 700;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.3rem;
		outline: none;
		padding: 0.45rem;
		transition: all 0.2s ease;
	}

	.master-pill-btn:hover {
		background: var(--btn-hover);
		color: var(--text-main);
		border-color: var(--brand-blue);
		box-shadow: 0 0 10px rgba(42, 117, 243, 0.2);
	}

	.master-pill-btn.active {
		background: var(--btn-active);
		color: var(--brand-blue);
		border-color: var(--brand-blue);
		box-shadow: 0 0 12px rgba(42, 117, 243, 0.25);
	}

	.master-pill-icon {
		width: 14px;
		height: 14px;
	}

	.btn-master-action {
		flex: 1;
		background: var(--btn-bg);
		border: 1px solid var(--border-soft);
		color: var(--text-muted);
		border-radius: 6px;
		font-family: 'Outfit', sans-serif;
		font-size: 0.8rem; 
		font-weight: 700;
		cursor: pointer;
		padding: 0.45rem;
		display: flex;
		justify-content: center;
		align-items: center;
		transition: all 0.15s ease;
	}

	.btn-master-action:hover:not(:disabled) {
		background: var(--btn-hover);
		color: var(--text-main);
		border-color: var(--brand-blue);
		box-shadow: 0 0 10px rgba(42, 117, 243, 0.2);
	}

	.btn-master-action:disabled {
		opacity: 0.6;
		cursor: not-allowed;
		background: rgba(120, 120, 120, 0.05);
		border-color: var(--border-soft);
		color: var(--text-muted);
	}

	.btn-master-action.active-recording {
		background: var(--btn-active);
		color: var(--brand-blue);
		border-color: var(--brand-blue);
		animation: pulse-blue-rec 1.2s infinite alternate;
	}

	@keyframes pulse-blue-rec {
		from { box-shadow: 0 0 4px rgba(42, 117, 243, 0.35); }
		to { box-shadow: 0 0 12px rgba(42, 117, 243, 0.75); }
	}

	.master-right-side {
		display: flex;
		flex-direction: column;
		height: 100%;
		justify-content: stretch;
	}

	.btn-emergency-halt-right-half {
		flex: 1;
		border-radius: 6px;
		background: linear-gradient(135deg, #d32f2f, #9a0007);
		color: #fff;
		border: 2px solid #ff5252;
		font-family: 'Outfit', sans-serif;
		font-size: 1rem;
		font-weight: 850;
		letter-spacing: 0.8px;
		cursor: pointer;
		box-shadow: 0 0 16px rgba(255, 82, 82, 0.25);
		transition: transform 0.08s ease, box-shadow 0.15s ease, background 0.2s ease;
		display: flex;
		justify-content: center;
		align-items: center;
	}

	.btn-emergency-halt-right-half:hover {
		background: linear-gradient(135deg, #ff5252, #d32f2f);
		box-shadow: 0 0 24px rgba(255, 82, 82, 0.45);
	}

	.btn-emergency-halt-right-half:active {
		transform: scale(0.97);
	}

	.btn-emergency-halt-right-half.btn-unlock {
		background: linear-gradient(135deg, #10b981, #059669);
		border-color: #34d399;
		box-shadow: 0 0 16px rgba(16, 185, 129, 0.25);
	}

	.btn-emergency-halt-right-half.btn-unlock:hover {
		background: linear-gradient(135deg, #34d399, #10b981);
		box-shadow: 0 0 24px rgba(16, 185, 129, 0.45);
	}

	.btn-emergency-halt-right-half.btn-connecting {
		background: rgba(255, 255, 255, 0.05);
		border-color: var(--border-soft);
		color: var(--text-muted);
		box-shadow: none;
		cursor: not-allowed;
	}

	/* VLA Alert Box */
	.vla-alert-box {
		flex: 1;
		background: rgba(245, 158, 11, 0.1);
		border: 2px dashed #f59e0b;
		border-radius: 6px;
		padding: 0.5rem;
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		align-items: center;
		gap: 0.4rem;
	}

	.vla-alert-title {
		font-family: 'Fira Code', monospace;
		font-size: 0.8rem;
		font-weight: 800;
		color: #f59e0b;
	}

	.vla-alert-btns {
		display: flex;
		gap: 0.4rem;
		width: 100%;
	}

	.btn-vla-approve {
		flex: 1;
		background: #10b981;
		color: #fff;
		border: none;
		border-radius: 4px;
		padding: 0.35rem;
		font-weight: 700;
		cursor: pointer;
		font-size: 0.75rem;
	}

	.btn-vla-reject {
		flex: 1;
		background: #ef4444;
		color: #fff;
		border: none;
		border-radius: 4px;
		padding: 0.35rem;
		font-weight: 700;
		cursor: pointer;
		font-size: 0.75rem;
	}

	.vla-inference-trigger-strip {
		margin-top: 0.5rem;
		width: 100%;
	}
	
	.w-full {
		width: 100%;
	}

	.btn-master-action.active-calibrating {
		background: var(--btn-active);
		color: var(--brand-blue);
		border-color: var(--brand-blue);
		animation: pulse-blue-rec 1.2s infinite alternate;
	}
</style>
