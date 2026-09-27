<script lang="ts">
	import { robotState, submitChatCommand, clearFeed } from '$lib/store.svelte';

	let chatInput = $state("");

	function handleSend() {
		submitChatCommand(chatInput);
		chatInput = "";
	}

	function getLogClass(entry: typeof robotState.unifiedFeed[0]): string {
		if (entry.type === 'chat') {
			return entry.sender === 'user' ? 'user' : 'system';
		}
		const text = entry.text;
		if (text.includes('warning') || text.includes('Safety')) {
			return 'warn';
		}
		if (text.includes('Stop') || text.includes('RECORD') || text.includes('EMERGENCY')) {
			return 'err';
		}
		return 'info';
	}
</script>

<section class="glass-card unified-terminal-card">
	<div class="cell-header">
		<h2>TERMINAL & LIVE DIAGNOSTICS</h2>
		<button class="btn-clear-logs" onclick={clearFeed}>CLEAR</button>
	</div>
	
	<div class="unified-terminal-container">
		<div class="terminal-flow-area" id="terminal-scroll-area">
			{#each robotState.unifiedFeed as entry}
				<div class="log-line-item {getLogClass(entry)}">
					
					{#if entry.type === 'chat'}
						<span class="arrow">{entry.sender === 'user' ? '>' : '#'}</span>
						<span class="text">
							{#if entry.command}<span class="command-highlight">[{entry.command}]</span> {/if}
							{entry.text}
						</span>
					{:else}
						<span class="arrow">></span>
						<span class="text">{entry.text}</span>
					{/if}
					<span class="time-stamp">{entry.time}</span>
				</div>
			{/each}
			{#if robotState.unifiedFeed.length === 0}
				<div class="no-logs-prompt">Waiting for developer input or WebSocket stream...</div>
			{/if}
		</div>
		
		<div class="chat-prompt-bar">
			<span class="terminal-prefix">></span>
			<input 
				type="text" 
				class="chat-textbox-prompt" 
				placeholder="type command"
				bind:value={chatInput}
				onkeydown={(e) => { if (e.key === 'Enter') handleSend(); }}
			/>
		</div>
	</div>
</section>

<style>
	.unified-terminal-card {
		flex: 1 1 auto;
		min-height: 0;
	}
	@media (max-width: 1024px) {
		.unified-terminal-card {
			height: 350px;
		}
	}

	.unified-terminal-container {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-height: 0;
	}

	.terminal-flow-area {
		flex: 1;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 0.15rem; /* Tighter gap for pure terminal look */
		padding-right: 0.4rem;
		margin-bottom: 0.6rem;
		min-height: 0; 
		background: rgba(0, 0, 0, 0.25);
		border: 1px solid var(--border-soft);
		border-radius: 6px;
		padding: 0.55rem;
	}

	:global(html.light) .terminal-flow-area {
		background: #ffffff;
	}

	/* Diagnostic entries inside terminal */
	.log-line-item {
		display: flex;
		gap: 0.5rem;
		font-family: 'Fira Code', monospace;
		font-size: 0.78rem;
		line-height: 1.4;
		align-items: flex-start;
		word-break: break-word;
	}

	.log-line-item .text {
		white-space: pre-wrap;
	}

	.log-line-item .arrow {
		color: var(--text-muted);
		font-weight: 700;
		flex-shrink: 0;
	}

	.log-line-item .time-stamp {
		font-size: 0.62rem;
		color: var(--text-muted);
		opacity: 0.5;
		margin-left: auto;
		padding-left: 0.5rem;
		white-space: nowrap;
	}

	/* Terminal coloring */
	.log-line-item.info .text { color: var(--text-muted); }
	.log-line-item.warn .text { color: var(--brand-blue-ice); }
	.log-line-item.err .text { color: var(--brand-blue); }
	
	.log-line-item.user .arrow { color: var(--brand-blue); }
	.log-line-item.user .text { color: var(--text-main); font-weight: 500; }
	
	.log-line-item.system .arrow { color: var(--text-muted); }
	.log-line-item.system .text { color: var(--text-muted); }

	.command-highlight {
		color: var(--brand-blue-ice);
		opacity: 0.8;
	}

	.no-logs-prompt {
		color: var(--text-muted);
		font-style: italic;
		text-align: center;
		margin-top: 3rem;
		font-size: 0.85rem;
	}

	.btn-clear-logs {
		background: transparent;
		border: 1px solid var(--border-soft);
		color: var(--text-muted);
		padding: 0.15rem 0.45rem;
		border-radius: 4px;
		font-size: 0.7rem;
		font-family: 'Outfit', sans-serif;
		cursor: pointer;
	}

	.btn-clear-logs:hover {
		border-color: var(--text-muted);
		color: var(--text-main);
	}

	.chat-prompt-bar {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		height: 32px;
		flex-shrink: 0;
		background: var(--bg-primary);
		border: 1px solid var(--border-soft);
		border-radius: 6px;
		padding: 0 0.6rem;
		transition: border-color 0.2s;
	}
	
	.chat-prompt-bar:focus-within {
		border-color: var(--brand-blue);
	}

	.terminal-prefix {
		font-family: 'Fira Code', monospace;
		color: var(--brand-blue);
		font-weight: 700;
	}

	.chat-textbox-prompt {
		flex: 1;
		background: transparent;
		border: none;
		color: var(--text-main);
		font-family: 'Fira Code', monospace;
		font-size: 0.82rem;
		outline: none;
	}
</style>
