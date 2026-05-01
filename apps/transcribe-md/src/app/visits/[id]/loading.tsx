// Visit page loading state — chip row + large content placeholder
// while the server does auth() + visit lookup. Phase 5 (Linear V1) —
// renders on the dark canvas; loading.tsx is outside the AppFrame
// boundary so the wrapper sets linear-bg directly. Skeleton is owned
// by Subagent 2 and will retire its `theme` prop in their pass.

import { PageWrapper } from '@/components/page-wrapper';
import { Skeleton } from '@/components/skeleton';

export default function VisitLoading() {
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
