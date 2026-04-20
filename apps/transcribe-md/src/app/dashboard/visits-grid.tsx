'use client';

// ============================================================================
// Client-side dashboard grid with "Load more" pagination (T-M16.4 M5).
// ----------------------------------------------------------------------------
// Server renders the first page directly (fast SSR paint). Subsequent
// pages come from loadMoreVisitsAction. Page size = 20.
// ============================================================================

import { useState, useTransition } from 'react';
import { Loader2 } from 'lucide-react';

import { VisitCard, type VisitCardData } from '@/components/visit-card';
import { loadMoreVisitsAction } from '@/actions/visits';
import type { DashboardCursor } from '@/lib/dashboard-pagination';

interface Props {
  initialVisits: VisitCardData[];
  initialCursor: DashboardCursor | null;
}

export function VisitsGrid({ initialVisits, initialCursor }: Props) {
  const [visits, setVisits] = useState<VisitCardData[]>(initialVisits);
  const [cursor, setCursor] = useState<DashboardCursor | null>(initialCursor);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function onLoadMore() {
    if (!cursor) return;
    setError(null);
    const c = cursor;
    startTransition(async () => {
      try {
        const result = await loadMoreVisitsAction(c);
        setVisits((prev) => [...prev, ...(result.visits as VisitCardData[])]);
        setCursor(result.nextCursor);
      } catch {
        setError('Could not load more visits. Please try again.');
      }
    });
  }

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {visits.map((v) => (
          <VisitCard key={v.id} visit={v} />
        ))}
      </div>

      {cursor && (
        <div className="mt-8 flex flex-col items-center gap-2">
          <button
            type="button"
            onClick={onLoadMore}
            disabled={pending}
            className="inline-flex items-center gap-2 rounded-full border border-border-default bg-bg-surface-1/60 px-5 py-2 text-[13px] font-medium text-text-secondary hover:bg-bg-surface-2/70 hover:border-border-emphasis disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {pending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {pending ? 'Loading…' : 'Load more visits'}
          </button>
          {error && (
            <p className="text-[12px] text-danger">{error}</p>
          )}
        </div>
      )}

      {!cursor && visits.length > 0 && (
        <p className="mt-8 text-center text-[12px] text-text-muted">
          That&apos;s every visit on this account.
        </p>
      )}
    </>
  );
}
