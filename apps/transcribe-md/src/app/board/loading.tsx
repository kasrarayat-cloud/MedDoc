// ============================================================================
// /board loading state — NEW. The route had `page.tsx` and nothing else.
// ----------------------------------------------------------------------------
// Without a `loading.tsx`, Next shows the PREVIOUS route until the board's
// server component finishes its queue query. On a cold navigation that is a
// blank stage; on a warm one it is the page the doctor just left, still
// interactive-looking. Neither says "this is loading".
//
// ⚠️ NO FLAG FORK HERE, and that is deliberate rather than an omission:
// `/board` itself fails closed. `app/board/page.tsx:76` runs
// `if (!isSkinRounds()) notFound();` before `auth()`, so with the flag off
// this route does not exist and this file cannot render. A fork would be dead
// code that reads as a supported state.
// ============================================================================

import { SkeletonRoundsLane } from '@/components/skeleton';

export default function BoardLoading() {
  return (
    <div
      className="qm-rounds-host qm-rounds-loading"
      data-testid="rounds-loading-board"
      style={{ minHeight: '100vh', padding: '28px 24px' }}
    >
      <div style={{ maxWidth: 1280, margin: '0 auto' }}>
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonRoundsLane key={i} />
        ))}
      </div>
    </div>
  );
}
