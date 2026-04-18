'use client';
// React Compiler opt-out — the R3F scene mutates mesh refs imperatively
// per frame, which the compiler's purity rules reject.
'use no memo';

import { useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface VioletOrbProps {
  className?: string;
  /** Diameter hint (Three.js world units). Kept small — EmptyState uses 1.2,
   *  the /visits/[id] page uses 1.6. */
  radius?: number;
  /** Slow down the "breathe" animation — useful when the orb sits inside a
   *  larger motion-staggered layout and shouldn't be the eye-catch. */
  quiet?: boolean;
}

/**
 * Lightweight brand-violet sphere with a soft emissive glow. Prep for the
 * T-M3 "big orb" hero; here it's the decoration for EmptyState and the
 * /visits/[id] placeholder.
 *
 * Performance: DPR capped at 1.5 so low-power screens don't chug; frame
 * loop only runs when the tab is visible (Canvas default).
 */
export function VioletOrb({
  className,
  radius = 1.2,
  quiet = false,
}: VioletOrbProps) {
  return (
    <div className={className}>
      <Canvas
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 3.5], fov: 45 }}
        gl={{
          antialias: true,
          alpha: true,
          powerPreference: 'high-performance',
        }}
        style={{ background: 'transparent' }}
      >
        <ambientLight intensity={0.4} />
        <pointLight position={[2, 2, 3]} intensity={1.8} color={'#C4B5FD'} />
        <pointLight position={[-3, -2, -1]} intensity={2.0} color={'#7C3AED'} />
        <OrbMesh radius={radius} quiet={quiet} />
      </Canvas>
    </div>
  );
}

function OrbMesh({ radius, quiet }: { radius: number; quiet: boolean }) {
  const ref = useRef<THREE.Mesh>(null);
  const geometry = useMemo(() => new THREE.SphereGeometry(radius, 48, 48), [radius]);

  useFrame((state) => {
    const m = ref.current;
    if (!m) return;
    const t = state.clock.getElapsedTime();
    // "Breathe" — radius pulses ~2% at 0.5 Hz (1 Hz when quiet=false).
    const speed = quiet ? 0.35 : 0.7;
    const amount = quiet ? 0.015 : 0.025;
    const scale = 1 + Math.sin(t * speed) * amount;
    m.scale.set(scale, scale, scale);
    // Gentle y-axis rotation keeps the highlight moving so the sphere
    // reads as living geometry rather than a flat disc.
    m.rotation.y = t * 0.15;
  });

  return (
    <mesh ref={ref} geometry={geometry}>
      <meshStandardMaterial
        color={'#1E1B4B'}
        emissive={'#7C3AED'}
        emissiveIntensity={0.45}
        roughness={0.25}
        metalness={0.15}
      />
    </mesh>
  );
}
