'use client';

import dynamic from 'next/dynamic';

const VioletOrb = dynamic(
  () => import('@/components/violet-orb').then((m) => m.VioletOrb),
  { ssr: false, loading: () => <div className="h-full w-full" /> }
);

/** Wraps VioletOrb in a client-side dynamic import so server pages can
 *  place it without tripping Next.js's "ssr:false in server component"
 *  rule. The halo behind the orb is rendered here too to keep the
 *  visual composition in one place. */
export function VisitOrb() {
  return (
    <div className="relative mb-10 h-64 w-64">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 rounded-full"
        style={{
          background:
            'radial-gradient(ellipse at center, rgba(139,92,246,0.4) 0%, rgba(139,92,246,0.1) 40%, transparent 70%)',
          filter: 'blur(32px)',
        }}
      />
      <VioletOrb radius={1.55} quiet />
    </div>
  );
}
