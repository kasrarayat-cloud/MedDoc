'use client';

// HANDOFF §2.3 LiveOrb — SVG circular waveform + core orb driven by a
// mock amplitude signal (§3.5). RAF loop guarded against StrictMode
// double-mount per §8.3; reduced-motion short-circuits to a static
// frame per §8.9.

import { useEffect, useRef, useState } from 'react';

export function LiveOrb({
  paused = false,
  reducedMotion = false,
}: {
  paused?: boolean;
  reducedMotion?: boolean;
}) {
  const [amp, setAmp] = useState(0.5);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (reducedMotion || paused) {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      // Amp is intentionally NOT reset here — the render just below
      // handles the static frame, and writing setAmp would trigger a
      // cascading render. The component re-mounts clean on state
      // changes that matter (paused flip → new effect run).
      return;
    }
    let cancelled = false;
    let t = 0;
    const tick = () => {
      if (cancelled) return;
      t += 0.04;
      const base = 0.35 + 0.15 * Math.sin(t * 2);
      const burst =
        Math.max(0, Math.sin(t * 5.3)) *
        0.4 *
        (Math.random() > 0.6 ? 1 : 0.3);
      setAmp(Math.min(1, base + burst + Math.random() * 0.08));
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      cancelled = true;
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [paused, reducedMotion]);

  const scale = 1 + amp * 0.12;
  const rings = [0, 1, 2];

  return (
    <div
      style={{
        position: 'relative',
        width: 360,
        height: 360,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {rings.map((i) => (
        <div
          key={i}
          aria-hidden
          style={{
            position: 'absolute',
            width: 220 + i * 60,
            height: 220 + i * 60,
            borderRadius: '50%',
            border: `1px solid rgba(139,92,255,${0.2 - i * 0.04})`,
            transform: `scale(${1 + amp * 0.05})`,
            transition: 'transform .08s linear',
          }}
        />
      ))}
      <svg
        viewBox="0 0 360 360"
        width={360}
        height={360}
        style={{ position: 'absolute' }}
        aria-hidden
      >
        <defs>
          <linearGradient id="qm-orb-g" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#D1B5FF" />
            <stop offset="0.5" stopColor="#A87CFF" />
            <stop offset="1" stopColor="#6B3FD9" />
          </linearGradient>
          <radialGradient id="qm-orb-core" cx="0.5" cy="0.45" r="0.55">
            <stop offset="0" stopColor="#E8D9FF" stopOpacity="0.9" />
            <stop offset="0.45" stopColor="#8B5CFF" stopOpacity="0.5" />
            <stop offset="1" stopColor="#2A1560" stopOpacity="0.95" />
          </radialGradient>
          <radialGradient id="qm-orb-glow" cx="0.5" cy="0.5" r="0.7">
            <stop offset="0" stopColor="#8B5CFF" stopOpacity="0.55" />
            <stop offset="1" stopColor="#8B5CFF" stopOpacity="0" />
          </radialGradient>
        </defs>
        <circle
          cx={180}
          cy={180}
          r={170}
          fill="url(#qm-orb-glow)"
          opacity={0.6 + amp * 0.3}
        />
        {Array.from({ length: 64 }).map((_, i) => {
          const a = (i / 64) * Math.PI * 2;
          const seed = Math.sin(i * 0.7) * 0.5 + Math.sin(i * 1.3) * 0.5;
          const mag = 6 + (amp + 0.2) * (12 + Math.abs(seed) * 18);
          const r0 = 130;
          const r1 = r0 + mag;
          const x0 = 180 + Math.cos(a) * r0;
          const y0 = 180 + Math.sin(a) * r0;
          const x1 = 180 + Math.cos(a) * r1;
          const y1 = 180 + Math.sin(a) * r1;
          return (
            <line
              key={i}
              x1={x0}
              y1={y0}
              x2={x1}
              y2={y1}
              stroke="url(#qm-orb-g)"
              strokeWidth={2}
              strokeLinecap="round"
              opacity={paused ? 0.3 : 0.9}
            />
          );
        })}
        <circle cx={180} cy={180} r={118 * scale} fill="url(#qm-orb-core)" />
        <circle
          cx={180}
          cy={180}
          r={118 * scale}
          fill="none"
          stroke="rgba(255,255,255,0.35)"
          strokeWidth={0.6}
        />
        <ellipse
          cx={155}
          cy={148}
          rx={42}
          ry={24}
          fill="rgba(255,255,255,0.22)"
          transform="rotate(-18 155 148)"
        />
        {!paused && (
          <circle
            cx={180}
            cy={180}
            r={8 + amp * 6}
            fill="#FB7185"
            opacity={0.85}
          />
        )}
      </svg>
    </div>
  );
}
