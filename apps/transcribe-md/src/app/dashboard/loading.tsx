// Dashboard loading state — matches the shape of the real dashboard
// so the transition feels instant. Fires while /dashboard's top-level
// awaits (auth() + user lookup) are in flight. Inner Suspense in the
// page file still governs the streamed visit grid.

import { PageWrapper } from '@/components/page-wrapper';
import { Skeleton, SkeletonVisitGrid } from '@/components/skeleton';

export default function DashboardLoading() {
  return (
    <PageWrapper>
      <div className="h-14 border-b border-border-subtle" />
      <main className="mx-auto max-w-7xl px-4 pb-24 pt-8 sm:px-6 lg:px-8 lg:pt-12">
        <div className="mb-6 space-y-2">
          <Skeleton className="h-8 w-44" />
          <Skeleton className="h-3 w-32" />
        </div>
        <SkeletonVisitGrid count={6} />
      </main>
    </PageWrapper>
  );
}
