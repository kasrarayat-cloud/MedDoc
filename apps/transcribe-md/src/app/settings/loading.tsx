// Phase 5 — Linear V1 Faithful settings loading state.

import { Skeleton, SkeletonSettingsRow } from '@/components/skeleton';

export default function SettingsLoading() {
  return (
    <div
      className="qm-lin-fade-in"
      style={{
        padding: '18px 24px 64px',
        maxWidth: 1200,
      }}
    >
      <Skeleton className="mb-3 h-3 w-16" />
      <Skeleton className="mb-2 h-7 w-32" />
      <Skeleton className="mb-8 h-3 w-72" />
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
          maxWidth: 720,
        }}
      >
        <SkeletonSettingsRow />
        <SkeletonSettingsRow />
        <SkeletonSettingsRow />
        <SkeletonSettingsRow />
      </div>
    </div>
  );
}
