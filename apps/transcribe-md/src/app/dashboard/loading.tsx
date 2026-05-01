// Phase 5 — Linear V1 Faithful dashboard loading state.
// Matches the shape of the dashboard page so the transition feels
// instant. Fires while the top-level awaits (auth() + user lookup) are
// in flight; inner Suspense in the page file still governs the streamed
// visit grid.

import { Skeleton } from '@/components/skeleton';

export default function DashboardLoading() {
  const tile: React.CSSProperties = {
    background: 'var(--color-linear-surface-2)',
    border: '1px solid var(--color-linear-border)',
    borderRadius: 8,
  };

  return (
    <div
      className="qm-lin-fade-in"
      style={{ padding: '18px 24px 80px', minHeight: '60vh' }}
    >
      {/* Greeting line */}
      <Skeleton className="mb-4 h-4 w-72" />

      {/* Stats row */}
      <div
        style={{
          display: 'flex',
          gap: 0,
          padding: '6px 0 14px',
          marginBottom: 8,
          borderBottom: '1px solid var(--color-linear-hairline)',
        }}
      >
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              padding: '0 18px',
              borderRight:
                i < 3
                  ? '1px solid var(--color-linear-hairline)'
                  : 'none',
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
            }}
          >
            <div style={{ height: 22, width: 60, ...tile, borderRadius: 4 }} />
            <div style={{ height: 10, width: 80, ...tile, borderRadius: 3 }} />
          </div>
        ))}
      </div>

      {/* Tab bar */}
      <Skeleton className="mt-5 h-7 w-44" />

      {/* Row list */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 0,
          marginTop: 18,
        }}
      >
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            style={{
              height: 36,
              borderBottom: '1px solid var(--color-linear-hairline)',
              opacity: 0.6,
            }}
          />
        ))}
      </div>
    </div>
  );
}
