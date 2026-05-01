'use client';

// Phase 5 — Linear V1 Faithful LiveOrb.
// Reference: docs/design-directions-v8-linear/recording.html
//
// The legacy violet 64-spoke SVG orb is replaced with a calm sage halo
// + sage-bright mic dot + 40-bar waveform driven by a clamped random
// walk (matching the recording.html mockup). The component still
// exposes the original `paused` + `reducedMotion` props so existing
// call sites (visits/[id]/processing-state.tsx) keep working.
// reduced-motion short-circuits to a static frame.

import { useEffect, useRef, useState } from 'react';

const BARS = 40;

export function LiveOrb({
  paused = false,
  reducedMotion = false,
}: {
  paused?: boolean;
  reducedMotion?: boolean;
}) {
  const [heights, setHeights] = useState<number[]>(() =>
    Array.from({ length: BARS }, (_, i) =>
      6 + Math.round(Math.abs(Math.sin(i * 1.7)) * 22)
    )
  );
  const rafRef = useRef<number | null>(null);
  const lastTickRef = useRef<number>(0);

  useEffect(() => {
    if (reducedMotion || paused) {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      return;
    }
    let cancelled = false;
    const loop = (now: number) => {
      if (cancelled) return;
      // 80ms tick cadence per the mockup — matches the
      // qm-lin-wave-bar transition timing.
      if (now - lastTickRef.current >= 80) {
        lastTickRef.current = now;
        setHeights((prev) =>
          prev.map((h) => {
            let next = h + (Math.floor(Math.random() * 13) - 6);
            if (next < 4) next = 4;
            if (next > 32) next = 32;
            return next;
          })
        );
      }
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return () => {
      cancelled = true;
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [paused, reducedMotion]);

  const isActive = !paused && !reducedMotion;

  return (
    <div
      style={{
        position: 'relative',
        width: 280,
        height: 280,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {/* Halo + mic centerpiece */}
      <div
        style={{
          position: 'relative',
          width: 200,
          height: 200,
          display: 'grid',
          placeItems: 'center',
        }}
      >
        {/* concentric sage rings */}
        <span
          aria-hidden
          style={{
            position: 'absolute',
            inset: 0,
            borderRadius: '50%',
            border: '1px solid rgba(122,166,140,0.18)',
          }}
        />
        <span
          aria-hidden
          style={{
            position: 'absolute',
            inset: 24,
            borderRadius: '50%',
            border: '1px solid rgba(122,166,140,0.26)',
          }}
        />
        <span
          aria-hidden
          style={{
            position: 'absolute',
            inset: 48,
            borderRadius: '50%',
            border: '1px solid rgba(122,166,140,0.36)',
          }}
        />
        {/* Pulsing sage glow halo */}
        {isActive && (
          <span
            aria-hidden
            className="qm-lin-mic-halo"
            style={{
              position: 'absolute',
              inset: 36,
              borderRadius: '50%',
              background:
                'radial-gradient(closest-side, rgba(155,196,168,0.32), rgba(122,166,140,0) 70%)',
            }}
          />
        )}
        {/* Mic dot */}
        <span
          aria-hidden
          className={isActive ? 'qm-lin-mic-dot' : undefined}
          style={{
            position: 'relative',
            width: 16,
            height: 16,
            borderRadius: '50%',
            background: 'var(--color-linear-sage-bright)',
            boxShadow:
              '0 0 18px rgba(155,196,168,0.65), 0 0 0 4px rgba(155,196,168,0.10)',
          }}
        />
      </div>

      {/* 40-bar waveform */}
      <div
        aria-hidden
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 3,
          height: 40,
          marginTop: 18,
          width: '100%',
          maxWidth: 340,
        }}
      >
        {heights.map((h, i) => (
          <span
            key={i}
            style={{
              width: 4,
              height: h,
              borderRadius: 2,
              background: 'var(--color-linear-sage)',
              opacity: paused ? 0.3 : 0.85,
              transition: 'height 80ms linear, opacity 200ms ease-out',
            }}
          />
        ))}
      </div>
    </div>
  );
}
