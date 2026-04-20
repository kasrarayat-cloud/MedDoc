'use client';

// ============================================================================
// Patients dashboard grid with "Load more" pagination (T-M17.2)
// ----------------------------------------------------------------------------
// Client mirror of the T-M16.4 VisitsGrid. Server renders the first 20
// patients directly for a fast SSR paint; subsequent pages come from
// loadMorePatientsAction.
// ============================================================================

import { useState, useTransition } from 'react';
import { Loader2 } from 'lucide-react';

import { PatientCard } from '@/components/patient-card';
import { loadMorePatientsAction } from '@/actions/patients';
import type {
  PatientsCursor,
  PatientListItem,
} from '@/lib/patients-pagination';

interface Props {
  initialPatients: PatientListItem[];
  initialCursor: PatientsCursor | null;
}

export function PatientsGrid({ initialPatients, initialCursor }: Props) {
  const [patients, setPatients] = useState<PatientListItem[]>(initialPatients);
  const [cursor, setCursor] = useState<PatientsCursor | null>(initialCursor);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function onLoadMore() {
    if (!cursor) return;
    setError(null);
    const c = cursor;
    startTransition(async () => {
      try {
        const result = await loadMorePatientsAction(c);
        setPatients((prev) => [...prev, ...result.patients]);
        setCursor(result.nextCursor);
      } catch {
        setError('Could not load more patients. Please try again.');
      }
    });
  }

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {patients.map((p) => (
          <PatientCard key={p.id} patient={p} />
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
            {pending ? 'Loading…' : 'Load more patients'}
          </button>
          {error && <p className="text-[12px] text-danger">{error}</p>}
        </div>
      )}

      {!cursor && patients.length > 0 && (
        <p className="mt-8 text-center text-[12px] text-text-muted">
          That&apos;s every patient on this account.
        </p>
      )}
    </>
  );
}
