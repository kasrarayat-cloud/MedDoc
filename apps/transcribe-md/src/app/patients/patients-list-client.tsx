'use client';

// Client-side search-by-name for the /patients list. The server sends
// the full page (<=100 rows); filtering runs in memory on every input
// tick. If this page grows past ~200 patients, move to a debounced
// server search via /api/patients or the ⌘K palette.

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
    <div style={{ padding: '0 32px 48px' }}>
      <div
        style={{
          position: 'relative',
          maxWidth: 420,
          marginBottom: 20,
        }}
      >
        <Ic.search
          width={14}
          height={14}
          style={{
            position: 'absolute',
            top: 13,
            left: 14,
            color: 'var(--fg-3)',
            pointerEvents: 'none',
          }}
        />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter by name…"
          className="qm-input"
          style={{ paddingLeft: 38, fontSize: 13 }}
          autoComplete="off"
          aria-label="Filter patients by name"
        />
      </div>

      {filtered.length === 0 ? (
        <div
          style={{
            margin: '40px auto',
            maxWidth: 420,
            textAlign: 'center',
            fontSize: 13,
            color: 'var(--fg-3)',
          }}
        >
          No patients match <strong style={{ color: 'var(--fg-2)' }}>{query}</strong>.
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
            gap: 14,
          }}
        >
          {filtered.map((p) => (
            <PatientCard key={p.id} patient={p} />
          ))}
        </div>
      )}
    </div>
  );
}
