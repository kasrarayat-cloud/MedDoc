// Visit page loading state — chip row + large content placeholder
// while the server does auth() + visit lookup.
//
// Phase 2 (Clinician remodel) — the visit-detail route opts into the
// Clinician chrome via `<AppFrame theme="clinician">`. This loading
// route falls outside that boundary (Next renders loading.tsx OUTSIDE
// the page that mounts AppFrame), so we wrap it directly in
// `.qm-cl-app` and pass `theme="clinician"` to Skeleton (already
// dual-theme aware from Batch A) so the placeholder rectangles
// resolve against the warm cream palette instead of the dark shimmer
// sweep.

import { PageWrapper } from '@/components/page-wrapper';
import { Skeleton } from '@/components/skeleton';

export default function VisitLoading() {
  return (
    <PageWrapper>
      <div className="qm-cl-app min-h-screen bg-clinician-cream">
        <div className="h-14 border-b border-clinician-line" />
        <main className="mx-auto max-w-4xl px-4 pb-24 pt-8 sm:px-6 lg:px-8 lg:pt-12">
          <Skeleton theme="clinician" className="mb-8 h-4 w-36" />
          <div className="flex flex-wrap gap-2">
            <Skeleton
              theme="clinician"
              className="h-6 w-24 rounded-full"
            />
            <Skeleton
              theme="clinician"
              className="h-6 w-32 rounded-full"
            />
            <Skeleton
              theme="clinician"
              className="h-6 w-28 rounded-full"
            />
          </div>
          <div className="mt-10 space-y-3">
            <Skeleton theme="clinician" className="h-10 w-full" />
            <Skeleton theme="clinician" className="h-96 w-full" />
          </div>
        </main>
      </div>
    </PageWrapper>
  );
}
