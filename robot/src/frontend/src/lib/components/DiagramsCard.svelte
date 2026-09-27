<script lang="ts">
	import { robotState } from '$lib/store.svelte';

	const PX_PER_M = 720;
	const URDF_ORIGINS = {
		joint1: { x: 0, z: 0.066 },
		joint2: { x: 0.048, z: 0.130 },
		joint3: { x: 0.120, z: 0 },
		endEffector: { x: 0.160, z: 0 }
	};
	const FIXED_SHOULDER_LINK = Math.hypot(URDF_ORIGINS.joint2.x, URDF_ORIGINS.joint2.z);
	const FIXED_SHOULDER_ANGLE = Math.atan2(URDF_ORIGINS.joint2.z, URDF_ORIGINS.joint2.x);
	const MAX_HORIZONTAL_REACH =
		URDF_ORIGINS.joint2.x + URDF_ORIGINS.joint3.x + URDF_ORIGINS.endEffector.x;
	const ORIGIN_X = 78;
	const ORIGIN_Z = 206;
	const TOP_CENTER = 100;
	const TOP_PX_PER_M = 260;

	type SideVector = { x: number; z: number };

	function sidePoint(x: number, z: number) {
		return {
			x: ORIGIN_X + x * PX_PER_M,
			y: ORIGIN_Z - z * PX_PER_M
		};
	}

	function degToRad(degrees: number) {
		return degrees * Math.PI / 180;
	}

	function addSideVector(a: SideVector, b: SideVector) {
		return { x: a.x + b.x, z: a.z + b.z };
	}

	function rotatePitch(vector: SideVector, angleRad: number) {
		return {
			x: vector.x * Math.cos(angleRad) + vector.z * Math.sin(angleRad),
			z: -vector.x * Math.sin(angleRad) + vector.z * Math.cos(angleRad)
		};
	}

	function topPoint(radius: number, yawRad: number) {
		return {
			x: TOP_CENTER + radius * TOP_PX_PER_M * Math.cos(yawRad),
			y: TOP_CENTER - radius * TOP_PX_PER_M * Math.sin(yawRad)
		};
	}

	let geometry = $derived.by(() => {
		const angleA = robotState.angles.A + robotState.offsets.A;
		const angleB = robotState.angles.B + robotState.offsets.B;
		const angleC = robotState.angles.C + robotState.offsets.C;
		const joint2Pitch = degToRad(angleB);
		const joint3Pitch = degToRad(angleA);
		const yaw = degToRad(angleC);

		const base = sidePoint(0, 0);
		const yawJointWorld = URDF_ORIGINS.joint1;
		const shoulderWorld = addSideVector(yawJointWorld, {
			x: FIXED_SHOULDER_LINK * Math.cos(FIXED_SHOULDER_ANGLE),
			z: FIXED_SHOULDER_LINK * Math.sin(FIXED_SHOULDER_ANGLE)
		});
		const elbowWorld = addSideVector(
			shoulderWorld,
			rotatePitch(URDF_ORIGINS.joint3, joint2Pitch)
		);
		const eeWorld = addSideVector(
			elbowWorld,
			rotatePitch(URDF_ORIGINS.endEffector, joint2Pitch + joint3Pitch)
		);
		const yawJoint = sidePoint(yawJointWorld.x, yawJointWorld.z);
		const shoulder = sidePoint(shoulderWorld.x, shoulderWorld.z);
		const elbow = sidePoint(elbowWorld.x, elbowWorld.z);
		const ee = sidePoint(eeWorld.x, eeWorld.z);

		const shoulderRadius = shoulderWorld.x;
		const elbowRadius = elbowWorld.x;
		const eeRadius = eeWorld.x;
		const topShoulder = topPoint(shoulderRadius, yaw);
		const topElbow = topPoint(elbowRadius, yaw);
		const topEe = topPoint(eeRadius, yaw);

		return { base, yawJoint, shoulder, elbow, ee, topShoulder, topElbow, topEe, eeWorld };
	});
</script>

<section class="glass-card vectors-card">
	<div class="cell-header">
		<h2>JOINT DIAGRAMS</h2>
		<span class="hud-meta">3-DOF SCHEMATIC</span>
	</div>
	<div class="diagrams">
		<div class="diagram-panel">
			<div class="diagram-box">
				<svg viewBox="0 0 320 230" aria-label="Robot arm side view">
					<line class="axis" x1="34" y1={ORIGIN_Z} x2="292" y2={ORIGIN_Z} />
					<line class="axis" x1={ORIGIN_X} y1="18" x2={ORIGIN_X} y2={ORIGIN_Z + 10} />
					<line class="fixed" x1={geometry.base.x} y1={geometry.base.y} x2={geometry.yawJoint.x} y2={geometry.yawJoint.y} />
					<line class="fixed" x1={geometry.yawJoint.x} y1={geometry.yawJoint.y} x2={geometry.shoulder.x} y2={geometry.shoulder.y} />
					<line x1={geometry.shoulder.x} y1={geometry.shoulder.y} x2={geometry.elbow.x} y2={geometry.elbow.y} />
					<line x1={geometry.elbow.x} y1={geometry.elbow.y} x2={geometry.ee.x} y2={geometry.ee.y} />
					<circle cx={geometry.base.x} cy={geometry.base.y} r="5" />
					<circle cx={geometry.yawJoint.x} cy={geometry.yawJoint.y} r="5" />
					<circle cx={geometry.shoulder.x} cy={geometry.shoulder.y} r="6" />
					<circle cx={geometry.elbow.x} cy={geometry.elbow.y} r="6" />
					<circle class="ee" cx={geometry.ee.x} cy={geometry.ee.y} r="5" />
				</svg>
				<div class="diagram-label">SIDE VIEW</div>
			</div>
		</div>
		<div class="diagram-panel">
			<div class="diagram-box">
				<svg viewBox="0 0 200 200" aria-label="Robot arm top view">
					<circle cx={TOP_CENTER} cy={TOP_CENTER} r={MAX_HORIZONTAL_REACH * TOP_PX_PER_M} class="ring" />
					<circle cx={TOP_CENTER} cy={TOP_CENTER} r={(URDF_ORIGINS.joint2.x + URDF_ORIGINS.joint3.x) * TOP_PX_PER_M} class="ring muted" />
					<line class="axis" x1="18" y1={TOP_CENTER} x2="182" y2={TOP_CENTER} />
					<line class="axis" x1={TOP_CENTER} y1="18" x2={TOP_CENTER} y2="182" />
					<line class="fixed" x1={TOP_CENTER} y1={TOP_CENTER} x2={geometry.topShoulder.x} y2={geometry.topShoulder.y} />
					<line x1={geometry.topShoulder.x} y1={geometry.topShoulder.y} x2={geometry.topElbow.x} y2={geometry.topElbow.y} />
					<line x1={geometry.topElbow.x} y1={geometry.topElbow.y} x2={geometry.topEe.x} y2={geometry.topEe.y} />
					<circle cx={TOP_CENTER} cy={TOP_CENTER} r="5" />
					<circle cx={geometry.topShoulder.x} cy={geometry.topShoulder.y} r="5" />
					<circle cx={geometry.topElbow.x} cy={geometry.topElbow.y} r="5" />
					<circle class="ee" cx={geometry.topEe.x} cy={geometry.topEe.y} r="5" />
				</svg>
				<div class="diagram-label">TOP VIEW</div>
			</div>
		</div>
	</div>
</section>

<style>
	.vectors-card {
		flex: 1 1 auto;
		min-height: 0;
	}
	@media (max-width: 1024px) {
		.vectors-card {
			height: auto;
			min-height: 250px;
		}
	}

	.diagrams {
		display: grid;
		grid-template-columns: 1.65fr 1fr;
		gap: 0.5rem;
		width: 100%;
		flex: 1;
		min-height: 0;
	}
	.diagram-panel {
		display: flex;
		flex-direction: column;
		min-height: 0;
		justify-content: center;
		align-items: center;
		overflow: hidden;
		width: 100%;
		height: 100%;
	}
	.diagram-box {
		position: relative;
		width: 100%;
		height: 100%;
		display: flex;
		justify-content: center;
		align-items: center;
		min-height: 0;
	}
	.diagram-label {
		position: absolute;
		bottom: 8px;
		left: 8px;
		font-family: 'Fira Code', monospace;
		font-size: 8.5px;
		font-weight: 700;
		color: rgba(255, 255, 255, 0.85);
		background: rgba(0, 0, 0, 0.75);
		padding: 2px 6px;
		border-radius: 3px;
		border: 1px solid rgba(255, 255, 255, 0.1);
	}
	svg {
		width: 100%;
		height: auto;
		max-height: 100%;
		background: rgba(42, 117, 243, 0.04);
		border: 1px solid var(--border-soft);
		border-radius: 6px;
	}
	line { stroke: var(--brand-blue); stroke-width: 5; stroke-linecap: round; }
	line.fixed { stroke: var(--brand-blue-ice); stroke-width: 3; opacity: 0.75; }
	line.axis { stroke: var(--border-soft); stroke-width: 1; }
	circle { fill: var(--bg-secondary); stroke: var(--brand-blue); stroke-width: 2; }
	circle.ee { fill: var(--brand-blue); stroke: white; }
	.ring { fill: none; opacity: 0.4; stroke: var(--brand-blue); stroke-width: 1; }
	.ring.muted { opacity: 0.18; stroke: var(--brand-blue-ice); stroke-width: 1; }

	@media (max-width: 720px) {
		.diagrams { grid-template-columns: 1fr; }
	}
</style>
