'use client';

import { useRef, useState, useCallback } from 'react';
import { cn } from '@/lib/cn';

/**
 * 3D-tilt card — tracks pointer position relative to the card and
 * applies a subtle rotateX/rotateY transform. Max 6° per axis per the
 * design spec; the light-specular highlight follows the cursor too.
 *
 * Reduced-motion preference is honoured via CSS (transitions collapse
 * in globals.css), and pointer-coarse devices (touch) skip the tilt
 * entirely to keep scroll performance clean.
 */
const MAX_TILT_DEG = 6;

export function TiltCard({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [transform, setTransform] = useState<string>('');
  const [spotlight, setSpotlight] = useState<{ x: number; y: number } | null>(
    null
  );

  const onMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (!el) return;
    if (e.pointerType === 'touch') return;
    const rect = el.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width; // 0-1
    const py = (e.clientY - rect.top) / rect.height; // 0-1
    const tiltY = (px - 0.5) * 2 * MAX_TILT_DEG; // left → right
    const tiltX = (0.5 - py) * 2 * MAX_TILT_DEG; // top → bottom (inverted)
    setTransform(
      `perspective(1200px) rotateX(${tiltX.toFixed(2)}deg) rotateY(${tiltY.toFixed(2)}deg)`
    );
    setSpotlight({ x: px * 100, y: py * 100 });
  }, []);

  const onLeave = useCallback(() => {
    setTransform('');
    setSpotlight(null);
  }, []);

  return (
    <div
      ref={ref}
      onPointerMove={onMove}
      onPointerLeave={onLeave}
      style={{
        transform,
        transition: transform
          ? 'transform 150ms cubic-bezier(0.4,0,0.2,1)'
          : 'transform 400ms cubic-bezier(0.4,0,0.2,1)',
        transformStyle: 'preserve-3d',
      }}
      className={cn('relative will-change-transform', className)}
    >
      {spotlight && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-40"
          style={{
            background: `radial-gradient(circle at ${spotlight.x}% ${spotlight.y}%, rgba(167,139,250,0.25), transparent 55%)`,
            mixBlendMode: 'screen',
          }}
        />
      )}
      {children}
    </div>
  );
}
