'use client';

// Client-side search-by-name for the /patients list. The server sends
// the full page (<=100 rows); filtering runs in memory on every input
// tick. If this page grows past ~200 patients, move to a debounced
// server search via /api/patients or the ⌘K palette.
//
// Phase 5 (Linear V1 Faithful) — filter input + empty-filter copy
// rendered against the dark canvas. <PatientCard> still receives
// `theme="clinician"` so the existing card surface keeps working
// until Subagent 2/3's dashboard migration lands.

import { useMemo, useState } from 'react';

import { Ic } from '@/components/ui/icon';
import {
  PatientCard,
  type DashboardPatient,
} from '@/components/dashboard/patient-card';

export function PatientsListClient({
  patients,
}: {
  patients: DashboardPatient[];
}) {
  const [query, setQuery] = useState('');
  const normalized = query.trim().toLowerCase();

  const filtered = useMemo(() => {
    if (normalized.length === 0) return patients;
    return patients.filter((p) =>
      p.name.toLowerCase().includes(normalized)
    );
  }, [patients, normalized]);

  return (
    <div className="px-10 pb-12">
      <div className="relative mb-6 max-w-[420px]">
        <Ic.search
          width={14}
          height={14}
          className="pointer-events-none absolute left-3.5 top-3.5 text-linear-text-3"
        />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter by name…"
          className="block h-10 w-full rounded-md border border-linear-border bg-linear-surface-1 pl-10 pr-3 text-[13.5px] text-linear-text placeholder:text-linear-text-3 focus-visible:border-linear-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage/40"
          autoComplete="off"
          aria-label="Filter patients by name"
        />
      </div>

      {filtered.length === 0 ? (
        <div className="mx-auto my-10 max-w-[420px] text-center text-[13.5px] text-linear-text-3">
          No patients match{' '}
          <strong className="font-medium text-linear-text">{query}</strong>.
        </div>
      ) : (
        <div
          className="grid gap-3.5"
          style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))' }}
        >
          {filtered.map((p) => (
            <PatientCard key={p.id} patient={p} theme="clinician" />
          ))}
        </div>
      )}
    </div>
  );
}
