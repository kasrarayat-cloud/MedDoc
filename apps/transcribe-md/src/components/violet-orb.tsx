'use client';
// The R3F scene mutates mesh refs imperatively per frame, which trips
// React Compiler's purity lint — opt out locally.
'use no memo';

import { useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------
export type OrbState = 'idle' | 'listening' | 'processing';

interface VioletOrbProps {
  className?: string;
  /** Diameter hint (Three.js world units). EmptyState uses 1.35, the
   *  /visits/[id] placeholder uses 1.55. */
  radius?: number;
  /** When true, quiets the ambient 3D pulse so a surrounding CSS
   *  animation can dominate the motion story. */
  quiet?: boolean;
  /** 0-1 reactivity amount. 0 = pure auto-pulse, 1 = amplitude tied
   *  directly to voice level. T-M3 defaults to 0.3 (soft auto-pulse).
   *  T-M5 will wire this to the mic envelope during dictation. */
  reactive?: number;
  /** State hint → hue shift on the rim light.
   *    idle       → violet (base)
   *    listening  → cyan edge
   *    processing → amber edge
   *  Geometry and base material stay the same so transitions look like
   *  the orb is changing mood rather than morphing shape. */
  state?: OrbState;
}

const STATE_RIM_COLOR: Record<OrbState, string> = {
  idle: '#7C3AED', // violet-600
  listening: '#06B6D4', // cyan-500
  processing: '#F59E0B', // amber-500
};

const PARTICLE_COUNT = 18;

/** Seeded mulberry32 — stable particle positions across renders. */
function makeRng(seed: number) {
  let s = seed | 0;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------------------------------------------------------------------------
// Outer component — sets up the Canvas + lights. Everything else is
// inside the scene so useFrame works without leaking into parent renders.
// ---------------------------------------------------------------------------
export function VioletOrb({
  className,
  radius = 1.2,
  quiet = false,
  reactive = 0.3,
  state = 'idle',
}: VioletOrbProps) {
  const rimColor = STATE_RIM_COLOR[state];

  return (
    <div className={className}>
      <Canvas
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 3.8], fov: 45 }}
        gl={{
          antialias: true,
          alpha: true,
          powerPreference: 'high-performance',
        }}
        style={{ background: 'transparent' }}
      >
        {/* Ambient + key/rim lights. The rim colour follows `state` so
            idle/listening/processing read as different moods without
            swapping the whole material. */}
        <ambientLight intensity={0.35} />
        <pointLight position={[2.2, 2.2, 3]} intensity={2.0} color={'#C4B5FD'} />
        <pointLight position={[-3, -2, -1.5]} intensity={2.4} color={rimColor} />

        <OrbGroup
          radius={radius}
          quiet={quiet}
          reactive={reactive}
          rimColor={rimColor}
        />
      </Canvas>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Scene: rotating group containing the sphere + drifting particle cloud.
// ---------------------------------------------------------------------------
function OrbGroup({
  radius,
  quiet,
  reactive,
  rimColor,
}: {
  radius: number;
  quiet: boolean;
  reactive: number;
  rimColor: string;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const sphereRef = useRef<THREE.Mesh>(null);
  const innerGlowRef = useRef<THREE.Mesh>(null);

  // Sphere geometry — constructed once and shared between outer orb and
  // the emissive inner shell. 48x48 gives a smooth silhouette at screen
  // sizes we ship (~256px). Anything higher is wasted fidelity.
  const geometry = useMemo(
    () => new THREE.SphereGeometry(radius, 48, 48),
    [radius]
  );
  const innerGeometry = useMemo(
    () => new THREE.SphereGeometry(radius * 0.88, 32, 32),
    [radius]
  );

  // Per-frame rotation + pulse. Reactive clamps 0-1, scales pulse
  // amplitude; at 0 there's still a 1.5% auto-breathe so the sphere
  // never sits perfectly still.
  useFrame((s) => {
    const t = s.clock.getElapsedTime();
    if (groupRef.current) {
      groupRef.current.rotation.y = t * 0.1;
      groupRef.current.rotation.x = Math.sin(t * 0.13) * 0.05;
    }
    if (sphereRef.current) {
      const clampedReactive = Math.max(0, Math.min(1, reactive));
      const autoAmp = quiet ? 0.012 : 0.025;
      const reactiveAmp = clampedReactive * 0.06;
      const amp = autoAmp + reactiveAmp;
      const speed = quiet ? 0.35 : 0.7;
      const scale = 1 + Math.sin(t * speed) * amp;
      sphereRef.current.scale.set(scale, scale, scale);
    }
    if (innerGlowRef.current) {
      // Inner shell pulses on a slightly different period so the two
      // layers interact rather than lockstep.
      const scale = 1 + Math.sin(t * 0.55 + 1.3) * 0.02;
      innerGlowRef.current.scale.set(scale, scale, scale);
    }
  });

  return (
    <group ref={groupRef}>
      {/* Outer sphere — the readable silhouette. Emissive violet shows
          through from the rim light + its own emissiveIntensity. */}
      <mesh ref={sphereRef} geometry={geometry}>
        <meshStandardMaterial
          color={'#1E1B4B'}
          emissive={'#7C3AED'}
          emissiveIntensity={0.48}
          roughness={0.22}
          metalness={0.18}
        />
      </mesh>

      {/* Inner glow shell — slightly smaller additive-blended sphere so
          the core looks volumetric rather than hollow. BackSide keeps
          the outer orb occluding it naturally. */}
      <mesh ref={innerGlowRef} geometry={innerGeometry}>
        <meshBasicMaterial
          color={rimColor}
          transparent
          opacity={0.35}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          side={THREE.BackSide}
        />
      </mesh>

      <Particles radius={radius} />
    </group>
  );
}

// ---------------------------------------------------------------------------
// Particle cloud — 18 tiny points drifting around/inside the orb.
// Instanced Points: single draw call, GPU-friendly.
// ---------------------------------------------------------------------------
function Particles({ radius }: { radius: number }) {
  const ref = useRef<THREE.Points>(null);

  // Spherical shell distribution at ~1.1×–1.5× the orb radius so points
  // appear to orbit just around the surface.
  const positions = useMemo(() => {
    const rnd = makeRng(0xdeadbeef);
    const arr = new Float32Array(PARTICLE_COUNT * 3);
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const phi = Math.acos(2 * rnd() - 1); // polar
      const theta = rnd() * Math.PI * 2; // azimuth
      const r = radius * (1.1 + rnd() * 0.4);
      arr[i * 3 + 0] = r * Math.sin(phi) * Math.cos(theta);
      arr[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      arr[i * 3 + 2] = r * Math.cos(phi);
    }
    return arr;
  }, [radius]);

  useFrame((s) => {
    const p = ref.current;
    if (!p) return;
    const t = s.clock.getElapsedTime();
    // Counter-rotate against the parent group so the particles trace a
    // slight helix relative to the viewer.
    p.rotation.y = -t * 0.18;
    p.rotation.x = Math.sin(t * 0.23) * 0.1;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
          count={PARTICLE_COUNT}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.045}
        color={'#C4B5FD'}
        transparent
        opacity={0.85}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}
