// Phase 5 — Linear V1 Faithful visit-orb wrapper.
//
// The Phase 4 dynamic-imported R3F orb is gone. Linear V1 renders a
// static sage glow disk so the visit empty-state still has a visual
// anchor without spinning a WebGL canvas. The dynamic import is no
// longer needed — VioletOrb is now a pure CSS stub that's safe to
// import directly from a server component.

import { VioletOrb } from '@/components/violet-orb';

/** Wraps VioletOrb in the same 256px square the legacy orb consumed
 *  so caller layouts (visit-detail empty state, voice dictator) don't
 *  need to change. Behind the orb sits a wider sage-glow halo to
 *  match the Linear V1 AuthShell right pane. */
export function VisitOrb() {
  return (
    <div
      style={{
        position: 'relative',
        marginBottom: 40,
        width: 256,
        height: 256,
      }}
    >
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          zIndex: -1,
          borderRadius: '50%',
          background:
            'radial-gradient(ellipse at center, var(--color-linear-sage-glow) 0%, transparent 70%)',
          filter: 'blur(32px)',
          pointerEvents: 'none',
        }}
      />
      <VioletOrb />
    </div>
  );
}
