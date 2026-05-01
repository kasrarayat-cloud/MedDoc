'use client';

// ============================================================================
// Step 1 of /visits/new — patient picker (T-M17.2 Phase 3 Commit 9)
// ----------------------------------------------------------------------------
// Three behaviours surfaced in one panel:
//   1. Debounced search of existing patients via GET /api/patients?search=
//   2. Inline "Create new patient" form (name + DOB + optional externalId)
//   3. On submit-create, first POST /api/patients/fuzzy-match; if matches
//      with score > 0.6 are found, render the DuplicateModal so the
//      doctor can confirm. Otherwise POST /api/patients directly.
//
// Phase 5 — Linear V1 Faithful. The picker renders on a hairline-
// bordered surface-1 surface; results rows use `.qm-lin-row` hover
// styling. The `theme` prop is preserved as a no-op.
// ============================================================================

import { useCallback, useEffect, useState } from 'react';
import { Loader2, Search, Plus, UserPlus, X } from 'lucide-react';

import { cn } from '@/lib/cn';
import { MIN_DOB_YEAR, validateDob } from '@/lib/dob';
import { DuplicateModal } from './duplicate-modal';
import type { FuzzyMatch, SelectedPatient } from './patient-types';

type PatientPickerTheme = 'legacy' | 'clinician';

interface PatientListApiRow {
  id: string;
  name: string;
  dateOfBirth: string | null;
  externalId: string | null;
}

interface PatientListApiResponse {
  patients: PatientListApiRow[];
}

interface CreateApiResponse {
  patient?: {
    id: string;
    name: string;
    dateOfBirth: string | null;
    externalId: string | null;
  };
  error?: string;
  field?: string;
}

interface FuzzyApiResponse {
  matches: FuzzyMatch[];
}

interface CoreProps {
  onSelect: (p: SelectedPatient) => void;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: PatientPickerTheme;
}

const FIELD_LABEL =
  'mb-1.5 block font-mono text-[10.5px] font-medium uppercase tracking-[0.07em] text-linear-text-3';

const INPUT_CLS =
  'block w-full rounded-md border border-linear-border bg-linear-surface-1 px-3 py-2 text-[14px] text-linear-text placeholder:text-linear-text-3 outline-none transition-colors focus:border-linear-sage focus:ring-2 focus:ring-linear-sage/30';

/** Full picker with the `/visits/new` "Who's this visit for?" card
 *  wrapper. Used as Step 1 of the new-visit flow. For callers that
 *  want the picker inside their own container, use PatientPickerCore. */
export function PatientPicker(props: CoreProps) {
  return (
    <div>
      <div className="mb-4 flex items-center gap-2">
        <UserPlus
          className="h-4 w-4 text-linear-sage-bright"
          aria-hidden
        />
        <h2
          style={{
            margin: 0,
            fontFamily: 'var(--font-sans)',
            fontSize: 17,
            fontWeight: 500,
            letterSpacing: '-0.012em',
            color: 'var(--color-linear-text)',
          }}
        >
          Who&apos;s this visit for?
        </h2>
      </div>
      <PatientPickerCore {...props} />
    </div>
  );
}

function formatDob(iso: string | null): string {
  return iso ? iso.slice(0, 10) : 'No DOB';
}

/** Headless picker — search + results + inline create + duplicate
 *  modal. */
export function PatientPickerCore({ onSelect }: CoreProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PatientListApiRow[]>([]);
  const [searching, setSearching] = useState(false);

  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDob, setNewDob] = useState('');
  const [newExternalId, setNewExternalId] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [duplicates, setDuplicates] = useState<{
    matches: FuzzyMatch[];
    pendingName: string;
    pendingDob: string;
    pendingExternalId: string | null;
  } | null>(null);

  const term = query.trim();
  useEffect(() => {
    if (term === '') return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await fetch(
          `/api/patients?search=${encodeURIComponent(term)}`,
          { signal: controller.signal }
        );
        if (!res.ok) throw new Error(`search ${res.status}`);
        const body = (await res.json()) as PatientListApiResponse;
        setResults(body.patients.slice(0, 10));
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [term]);

  const selectExisting = useCallback(
    (p: PatientListApiRow) => {
      onSelect({
        id: p.id,
        name: p.name,
        dateOfBirth: p.dateOfBirth,
        externalId: p.externalId,
      });
    },
    [onSelect]
  );

  const actuallyCreate = useCallback(
    async (
      name: string,
      dobIso: string,
      externalId: string | null
    ): Promise<void> => {
      const res = await fetch('/api/patients', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, dateOfBirth: dobIso, externalId }),
      });
      const body = (await res.json().catch(() => ({}))) as CreateApiResponse;
      if (!res.ok || !body.patient) {
        setCreateError(body.error ?? 'Could not create patient.');
        return;
      }
      onSelect({
        id: body.patient.id,
        name: body.patient.name,
        dateOfBirth: body.patient.dateOfBirth,
        externalId: body.patient.externalId,
      });
    },
    [onSelect]
  );

  async function onSubmitCreate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setCreateError(null);

    const name = newName.trim();
    if (name.length === 0) {
      setCreateError('Name is required.');
      return;
    }
    const dob = validateDob(newDob);
    if (!dob.ok) {
      setCreateError(dob.error);
      return;
    }
    const externalId =
      newExternalId.trim().length > 0 ? newExternalId.trim() : null;

    setSubmitting(true);
    try {
      const res = await fetch('/api/patients/fuzzy-match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, dateOfBirth: dob.iso }),
      });
      if (res.ok) {
        const body = (await res.json()) as FuzzyApiResponse;
        const strong = body.matches.filter((m) => m.score > 0.6);
        if (strong.length > 0) {
          setDuplicates({
            matches: strong,
            pendingName: name,
            pendingDob: dob.iso,
            pendingExternalId: externalId,
          });
          return;
        }
      }
      await actuallyCreate(name, dob.iso, externalId);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      {/* --- Search --- */}
      <label className="relative block">
        <span className="sr-only">Search patients</span>
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-linear-text-3"
          aria-hidden
        />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name or external ID…"
          className={cn(INPUT_CLS, 'pl-10 pr-10')}
        />
        {query.length > 0 && (
          <button
            type="button"
            onClick={() => setQuery('')}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-linear-text-3 hover:text-linear-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage"
            aria-label="Clear search"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </label>

      {/* --- Results --- */}
      {query.trim().length > 0 && (
        <div className="mt-3 overflow-hidden rounded-md border border-linear-border bg-linear-surface-2">
          {searching && results.length === 0 && (
            <div className="flex items-center gap-2 px-4 py-3 text-[13px] text-linear-text-3">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Searching…
            </div>
          )}
          {!searching && results.length === 0 && (
            <div className="px-4 py-3 text-[13px] text-linear-text-3">
              No matches. Create a new patient below.
            </div>
          )}
          {results.map((p, i) => (
            <button
              key={p.id}
              type="button"
              onClick={() => selectExisting(p)}
              className={cn(
                'flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-linear-row-hover focus-visible:outline-none focus-visible:bg-linear-row-active',
                i > 0 && 'border-t border-linear-hairline'
              )}
            >
              <div
                aria-hidden
                className="flex h-8 w-8 flex-none items-center justify-center rounded-md text-[12px] font-semibold"
                style={{
                  background: 'var(--color-linear-sage-tint)',
                  color: 'var(--color-linear-sage-bright)',
                }}
              >
                {p.name.charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[14px] font-medium text-linear-text">
                  {p.name}
                </div>
                <div className="text-[12px] text-linear-text-3">
                  {formatDob(p.dateOfBirth)}
                  {p.externalId ? ` · ID ${p.externalId}` : ''}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* --- Create-new toggle --- */}
      <div className="mt-4">
        {!creating ? (
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="qm-lin-btn"
          >
            <Plus className="h-3.5 w-3.5" />
            Create new patient
          </button>
        ) : (
          <form
            onSubmit={onSubmitCreate}
            className="space-y-3 rounded-lg border border-linear-border bg-linear-surface-2 p-4"
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className={FIELD_LABEL}>Name</label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  maxLength={200}
                  autoFocus
                  placeholder="Jane Doe"
                  className={INPUT_CLS}
                />
              </div>
              <div>
                <label className={FIELD_LABEL}>Date of birth</label>
                <input
                  type="date"
                  value={newDob}
                  onChange={(e) => setNewDob(e.target.value)}
                  min={`${MIN_DOB_YEAR}-01-01`}
                  max={new Date().toISOString().slice(0, 10)}
                  className={INPUT_CLS}
                />
              </div>
              <div className="sm:col-span-2">
                <label className={FIELD_LABEL}>
                  External ID{' '}
                  <span
                    style={{
                      color: 'var(--color-linear-text-3)',
                      fontWeight: 400,
                      textTransform: 'none',
                      letterSpacing: '-0.005em',
                    }}
                  >
                    (optional)
                  </span>
                </label>
                <input
                  type="text"
                  value={newExternalId}
                  onChange={(e) => setNewExternalId(e.target.value)}
                  maxLength={100}
                  placeholder="EMR chart number or MRN"
                  className={INPUT_CLS}
                />
              </div>
            </div>

            {createError && (
              <p className="text-[12px] text-linear-danger">{createError}</p>
            )}

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setCreating(false);
                  setNewName('');
                  setNewDob('');
                  setNewExternalId('');
                  setCreateError(null);
                }}
                className="qm-lin-btn"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="qm-lin-btn-primary"
              >
                {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Create &amp; continue
              </button>
            </div>
          </form>
        )}
      </div>

      {/* --- Duplicate modal --- */}
      {duplicates && (
        <DuplicateModal
          matches={duplicates.matches}
          onClose={() => setDuplicates(null)}
          onUseExisting={(p) => {
            setDuplicates(null);
            selectExisting(p);
          }}
          onCreateAnyway={async () => {
            const snap = duplicates;
            setDuplicates(null);
            setSubmitting(true);
            try {
              await actuallyCreate(
                snap.pendingName,
                snap.pendingDob,
                snap.pendingExternalId
              );
            } finally {
              setSubmitting(false);
            }
          }}
        />
      )}
    </div>
  );
}
