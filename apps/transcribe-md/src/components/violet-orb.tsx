/**
 * Phase 5 — Linear V1 Faithful (legacy violet-orb stripped).
 *
 * The Phase 4 R3F violet 3D orb is gone. Linear V1 has no spinning
 * spheres or volumetric glows; the chrome is flat hairlines on the dark
 * canvas. We keep this file (Stage 5 cleanup will check usage and
 * decide) and replace its content with a subtle sage-glow div so any
 * caller that still imports `<VioletOrb />` renders something visually
 * coherent rather than a broken WebGL canvas.
 *
 * Callers in scope of this migration:
 *   - components/visit-orb.tsx — wrapper that previously dynamic-imported
 *     this orb. Now renders a static sage glow halo through this stub.
 *
 * The `OrbState` enum and props remain in the signature so unmigrated
 * callers (visit-failed-view, voice-dictator) compile without changes.
 */
export type OrbState = 'idle' | 'listening' | 'processing';

interface VioletOrbProps {
  className?: string;
  /** @deprecated Linear V1 has no 3D orb; sized via parent container. */
  radius?: number;
  /** @deprecated kept for back-compat; no animation in Linear V1 stub. */
  quiet?: boolean;
  /** @deprecated kept for back-compat; no audio reactivity in stub. */
  reactive?: number;
  /** @deprecated kept for back-compat; no per-state hue shift. */
  state?: OrbState;
}

export function VioletOrb({ className }: VioletOrbProps) {
  return (
    <div
      aria-hidden
      className={className}
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        display: 'grid',
        placeItems: 'center',
      }}
    >
      <div
        style={{
          width: '70%',
          aspectRatio: '1 / 1',
          borderRadius: '50%',
          background:
            'radial-gradient(circle at 50% 50%, var(--color-linear-sage-glow) 0%, transparent 70%)',
          opacity: 0.85,
        }}
      />
    </div>
  );
}
