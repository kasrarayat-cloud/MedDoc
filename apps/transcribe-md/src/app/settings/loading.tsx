// Settings page loading state — label + rows while the server fetches
// user + session info.

import { PageWrapper } from '@/components/page-wrapper';
import { Skeleton, SkeletonSettingsRow } from '@/components/skeleton';

export default function SettingsLoading() {
  return (
    <PageWrapper>
      <div className="h-14 border-b border-border-subtle" />
      <main className="mx-auto max-w-3xl px-4 pb-24 pt-8 sm:px-6 lg:px-8 lg:pt-12">
        <Skeleton className="mb-10 h-8 w-32" />
        <div className="space-y-4">
          <SkeletonSettingsRow />
          <SkeletonSettingsRow />
          <SkeletonSettingsRow />
          <SkeletonSettingsRow />
        </div>
      </main>
    </PageWrapper>
  );
}
