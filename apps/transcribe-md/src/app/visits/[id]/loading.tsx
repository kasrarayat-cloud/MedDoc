// ============================================================================
// Visit page loading state.
// ----------------------------------------------------------------------------
// The skeleton mirrors the SHAPE of the resolved page, not just its colour:
// an 820px paper on a spotlit stage with a pipeline strip above it. A skeleton
// that promises a different column width than the content delivers moves the
// doctor's eye to where the content is not — worse than showing nothing, and
// not something a colour bridge can fix.
// ============================================================================

import { Skeleton } from '@/components/skeleton';

export default function VisitLoading() {
  return (
    <div
      className="qm-rounds-host qm-rounds-loading"
      data-testid="rounds-loading-visit"
      style={{ minHeight: '100vh', padding: '32px 24px' }}
    >
      {/* The pipeline strip: five nodes on a rule, which is what resolves. */}
      <div
        aria-hidden
        style={{
          maxWidth: 820,
          margin: '0 auto 28px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-2.5 w-2.5 rounded-full" />
        ))}
      </div>
      {/* The sheet. 820px, because that is the paper the spec pins. */}
      <div className="qm-rounds-skel-sheet" aria-hidden>
        <Skeleton className="mb-6 h-5 w-52 rounded" />
        <Skeleton className="mb-3 h-3 w-full rounded" />
        <Skeleton className="mb-3 h-3 w-11/12 rounded" />
        <Skeleton className="mb-8 h-3 w-4/5 rounded" />
        <Skeleton className="h-64 w-full rounded" />
      </div>
    </div>
  );
}
