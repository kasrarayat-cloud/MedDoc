/**
 * Phase 5 — Linear V1 Faithful page wrapper.
 *
 * Subtle page-enter animation. Wraps a page's content so navigating to
 * it fades in from 2px below. We swap framer-motion for the
 * `.qm-lin-fade-in` utility from globals.css — Linear V1 keeps motion
 * snappy (120 ms ease-out, 2px translate) and we don't need a separate
 * JS-driven animator.
 *
 * Server-component-friendly: no 'use client' directive needed; the
 * animation is pure CSS. Pages can wrap server-rendered children
 * without forcing a client island.
 */
export function PageWrapper({ children }: { children: React.ReactNode }) {
  return (
    <div className="qm-lin-fade-in" style={{ minHeight: '100vh' }}>
      {children}
    </div>
  );
}
