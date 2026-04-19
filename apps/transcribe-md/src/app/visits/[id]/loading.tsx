// Visit page loading state — chip row + large content placeholder
// while the server does auth() + visit lookup.

import { PageWrapper } from '@/components/page-wrapper';
import { Skeleton } from '@/components/skeleton';

export default function VisitLoading() {
  return (
    <PageWrapper>
      <div className="h-14 border-b border-border-subtle" />
      <main className="mx-auto max-w-4xl px-4 pb-24 pt-8 sm:px-6 lg:px-8 lg:pt-12">
        <Skeleton className="mb-8 h-4 w-36" />
        <div className="flex flex-wrap gap-2">
          <Skeleton className="h-6 w-24 rounded-full" />
          <Skeleton className="h-6 w-32 rounded-full" />
          <Skeleton className="h-6 w-28 rounded-full" />
        </div>
        <div className="mt-10 space-y-3">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      </main>
    </PageWrapper>
  );
}
