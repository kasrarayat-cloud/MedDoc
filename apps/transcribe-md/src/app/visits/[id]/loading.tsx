// ============================================================================
// Visit page loading state.
// ----------------------------------------------------------------------------
// ⚠️ THE ROUNDS BRANCH IS A DIFFERENT SHAPE, NOT A DIFFERENT COLOUR, and that
// is why it is forked rather than bridged.
//
// The flag-OFF skeleton below draws a 56px header bar, a chip row and two
// content blocks inside `max-w-4xl`. Under Rounds the same route resolves to
// an 820px paper on a spotlit stage with a pipeline strip above it. A skeleton
// that promises a 4xl column and delivers an 820px sheet moves the doctor's
// eye to where the content is not — worse than showing nothing, and not
// something a colour bridge can fix.
//
// (The flag-OFF branch is UNCHANGED, deliberately. And it is not "the old
// tabbed layout" — it never drew tabs; that 56px bar is empty. Recorded
// because an earlier plan described it that way, and a false before-state
// outlives whoever wrote it.)
// ============================================================================

import { PageWrapper } from '@/components/page-wrapper';
import { Skeleton } from '@/components/skeleton';
import { isSkinRounds } from '@/config/skin-rounds';

export default function VisitLoading() {
  if (isSkinRounds()) {
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

  return (
    <PageWrapper>
      <div
        style={{
          minHeight: '100vh',
          background: 'var(--color-linear-bg)',
        }}
      >
        <div
          style={{
            height: 56,
            borderBottom: '1px solid var(--color-linear-hairline)',
          }}
        />
        <main className="mx-auto max-w-4xl px-4 pb-24 pt-8 sm:px-6 lg:px-8 lg:pt-12">
          <Skeleton className="mb-8 h-4 w-36" />
          <div className="flex flex-wrap gap-2">
            <Skeleton className="h-6 w-24 rounded-md" />
            <Skeleton className="h-6 w-32 rounded-md" />
            <Skeleton className="h-6 w-28 rounded-md" />
          </div>
          <div className="mt-10 space-y-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-96 w-full" />
          </div>
        </main>
      </div>
    </PageWrapper>
  );
}
