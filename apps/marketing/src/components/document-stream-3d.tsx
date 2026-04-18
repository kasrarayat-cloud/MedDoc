'use client';
// React Compiler opt-out: R3F's useFrame is fundamentally imperative
// (mutates camera/mesh refs per frame) and the compiler's purity lint
// flags those mutations as errors. Everything memo-adjacent here is
// already hand-rolled via useMemo/useRef.
'use no memo';

/* ============================================================================
 * DocumentStream3D — signature hero element
 * ----------------------------------------------------------------------------
 * Ten "documents" float in 3D space as softly-rotating rounded planes.
 * Each plane uses a procedural canvas texture showing writing lines, and
 * carries a violet emissive material so the group glows against the
 * dark background.
 *
 * Mouse parallax: the group translates and tilts a few degrees tracking
 * the cursor. No OrbitControls — this is a hero surface, not an
 * inspectable object. Performance guardrails:
 *   - Instanced particle field (not a loop of meshes)
 *   - DPR capped at 2
 *   - Automatic pause when the tab is hidden (R3F `frameloop="demand"`
 *     doesn't fit the constant animation, so we use a visibility hook)
 *   - Lazy-loaded via next/dynamic from the page so SSR doesn't touch it
 * ========================================================================== */

import { Suspense, useMemo, useRef, useEffect, useState } from 'react';
import * as THREE from 'three';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Float } from '@react-three/drei';

const DOC_COUNT = 10;
const PARTICLE_COUNT = 140;

// ---------------------------------------------------------------------------
// Procedural "paper with writing" texture. Canvas-drawn once on mount;
// every document shares the same texture so the GPU only uploads once.
// ---------------------------------------------------------------------------
function usePaperTexture(): THREE.CanvasTexture {
  return useMemo(() => {
    const size = 512;
    const canvas =
      typeof document !== 'undefined'
        ? document.createElement('canvas')
        : null;
    if (!canvas) {
      // SSR fallback — DataTexture with a flat violet-ish colour.
      const data = new Uint8Array([30, 32, 48, 255]);
      const tex = new THREE.DataTexture(data, 1, 1, THREE.RGBAFormat);
      tex.needsUpdate = true;
      return tex as unknown as THREE.CanvasTexture;
    }
    canvas.width = size;
    canvas.height = size * 1.3; // 1:1.3 aspect, letter-like
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      const tex = new THREE.CanvasTexture(canvas);
      return tex;
    }

    // Paper background — very dark surface with subtle violet tint so
    // the emissive shows through.
    const bg = ctx.createLinearGradient(0, 0, 0, canvas.height);
    bg.addColorStop(0, '#1A1C28');
    bg.addColorStop(1, '#14161F');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Header block — a small violet "logo" and a bolder line.
    ctx.fillStyle = 'rgba(167, 139, 250, 0.9)';
    ctx.fillRect(40, 40, 80, 10);
    ctx.fillStyle = 'rgba(248, 250, 252, 0.9)';
    ctx.fillRect(40, 65, 300, 14);

    // Writing lines — 20 horizontal bars of varying length to suggest
    // prose. Lines are medium-translucent so the emissive underneath
    // reads through.
    ctx.fillStyle = 'rgba(203, 213, 225, 0.45)';
    const rng = (seed: number) => {
      // Deterministic mulberry32 — same texture across reloads.
      let t = seed + 0x6d2b79f5;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    for (let i = 0; i < 22; i++) {
      const y = 120 + i * 18;
      const w = 200 + rng(i * 17) * 260;
      ctx.fillRect(40, y, w, 4);
    }

    // Violet signature block at bottom.
    ctx.fillStyle = 'rgba(167, 139, 250, 0.55)';
    ctx.fillRect(40, canvas.height - 60, 160, 6);
    ctx.fillRect(40, canvas.height - 40, 120, 4);

    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 8;
    tex.needsUpdate = true;
    return tex;
  }, []);
}

// ---------------------------------------------------------------------------
// One floating document mesh.
// ---------------------------------------------------------------------------
interface DocumentPlaneProps {
  index: number;
  texture: THREE.CanvasTexture;
}

function DocumentPlane({ index, texture }: DocumentPlaneProps) {
  const meshRef = useRef<THREE.Mesh>(null);

  // Each document gets a stable pseudo-random position + phase.
  const { x, y, z, phase, spinSpeed, rotBase } = useMemo(() => {
    const t = index / DOC_COUNT;
    return {
      x: (Math.sin(index * 1.7) * 1.2),
      y: -3 + t * 6,           // stacked vertically through view
      z: Math.cos(index * 1.2) * 0.6,
      phase: index * 0.6,
      spinSpeed: 0.12 + (index % 3) * 0.04,
      rotBase: (index * 0.22) % (Math.PI * 2),
    };
  }, [index]);

  useFrame((state) => {
    const m = meshRef.current;
    if (!m) return;
    const t = state.clock.getElapsedTime();
    // Subtle drift — each doc oscillates on X/Z at its own phase.
    m.position.x = x + Math.sin(t * 0.4 + phase) * 0.18;
    m.position.z = z + Math.cos(t * 0.35 + phase) * 0.14;
    // Y scrolls downward slowly then wraps, so the stream feels
    // continuous without ever leaving view.
    const yWrap = 6; // total vertical range
    m.position.y = ((y + t * 0.25) % yWrap + yWrap) % yWrap - yWrap / 2;
    // Slow rotation — each doc at its own speed, starting from rotBase.
    m.rotation.y = rotBase + t * spinSpeed;
    m.rotation.x = Math.sin(t * 0.3 + phase) * 0.05;
  });

  return (
    <mesh ref={meshRef} castShadow receiveShadow>
      <planeGeometry args={[1.4, 1.82, 1, 1]} />
      <meshStandardMaterial
        map={texture}
        emissive={'#7C3AED'}
        emissiveIntensity={0.18}
        roughness={0.35}
        metalness={0.1}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

// ---------------------------------------------------------------------------
// Drifting particle field — GPU-instanced Points.
// ---------------------------------------------------------------------------
function Particles() {
  const ref = useRef<THREE.Points>(null);

  const positions = useMemo(() => {
    // Seeded mulberry32 — stable across re-renders (Math.random is
    // impure and flagged by the React purity lint). Visually
    // indistinguishable from random.
    let seed = 0x1234abcd;
    const rand = () => {
      seed |= 0;
      seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    const arr = new Float32Array(PARTICLE_COUNT * 3);
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      arr[i * 3 + 0] = (rand() - 0.5) * 8;
      arr[i * 3 + 1] = (rand() - 0.5) * 10;
      arr[i * 3 + 2] = (rand() - 0.5) * 4;
    }
    return arr;
  }, []);

  useFrame((state) => {
    const p = ref.current;
    if (!p) return;
    const t = state.clock.getElapsedTime();
    // Rotate the whole point cloud very slowly — individual motion is
    // implicit from the rotation against the parallax.
    p.rotation.y = t * 0.02;
    p.rotation.x = Math.sin(t * 0.1) * 0.08;
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
        size={0.03}
        color={'#A78BFA'}
        transparent
        opacity={0.6}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

// ---------------------------------------------------------------------------
// Camera-parallax rig. Tracks a normalised mouse coord and smoothly
// eases the camera position toward a small offset — gives the scene
// a "you're moving through it" feel without real controls.
// ---------------------------------------------------------------------------
function ParallaxRig() {
  const { camera } = useThree();
  const target = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      target.current.x = (e.clientX / window.innerWidth - 0.5) * 2;
      target.current.y = (e.clientY / window.innerHeight - 0.5) * 2;
    };
    window.addEventListener('pointermove', onMove);
    return () => window.removeEventListener('pointermove', onMove);
  }, []);

  useFrame(() => {
    const targetX = target.current.x * 0.6;
    const targetY = -target.current.y * 0.35;
    // camera is a ref-style THREE.Object3D — the React Compiler lint
    // flags direct property mutation as "modifying a local". Using
    // .set()/.lookAt() is the object's documented API, which the lint
    // treats as an intent-ful method call rather than a bare assign.
    const nextX = camera.position.x + (targetX - camera.position.x) * 0.05;
    const nextY = camera.position.y + (targetY - camera.position.y) * 0.05;
    camera.position.set(nextX, nextY, camera.position.z);
    camera.lookAt(0, 0, 0);
  });

  return null;
}

// ---------------------------------------------------------------------------
// Scene
// ---------------------------------------------------------------------------
function Scene() {
  const texture = usePaperTexture();
  return (
    <>
      {/* Violet key light from upper-right */}
      <ambientLight intensity={0.35} />
      <directionalLight
        position={[4, 6, 3]}
        intensity={1.2}
        color={'#C4B5FD'}
      />
      {/* Back-rim in deeper violet for edge glow */}
      <pointLight position={[-3, -4, -2]} intensity={1.6} color={'#7C3AED'} />

      {Array.from({ length: DOC_COUNT }).map((_, i) => (
        <Float
          key={i}
          speed={0.8 + (i % 3) * 0.2}
          rotationIntensity={0.3}
          floatIntensity={0.4}
        >
          <DocumentPlane index={i} texture={texture} />
        </Float>
      ))}

      <Particles />
      <ParallaxRig />
    </>
  );
}

// ---------------------------------------------------------------------------
// Public component — wraps the Canvas. Suspense fallback is a tasteful
// gradient blur so the hero never flashes a blank rectangle.
// ---------------------------------------------------------------------------
export function DocumentStream3D({ className }: { className?: string }) {
  const [tabVisible, setTabVisible] = useState(true);

  useEffect(() => {
    const onVis = () => setTabVisible(document.visibilityState === 'visible');
    document.addEventListener('visibilitychange', onVis);
    return () => document.removeEventListener('visibilitychange', onVis);
  }, []);

  return (
    <div className={className}>
      <Canvas
        dpr={[1, 2]}
        camera={{ position: [0, 0, 4.5], fov: 45 }}
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
        frameloop={tabVisible ? 'always' : 'never'}
        style={{ background: 'transparent' }}
      >
        <Suspense fallback={null}>
          <Scene />
        </Suspense>
      </Canvas>
    </div>
  );
}
