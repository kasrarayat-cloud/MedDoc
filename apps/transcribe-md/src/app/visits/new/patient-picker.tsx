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
// Selecting an existing patient (either from the search list or from
// the duplicate modal) calls onSelect(patient); the parent component
// hands the patient off to Step 2.
// ============================================================================

import { useCallback, useEffect, useState } from 'react';
import { Loader2, Search, Plus, UserPlus, X } from 'lucide-react';

import { MIN_DOB_YEAR, validateDob } from '@/lib/dob';
import { DuplicateModal } from './duplicate-modal';
import type { FuzzyMatch, SelectedPatient } from './patient-types';

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

interface Props {
  onSelect: (p: SelectedPatient) => void;
}

function formatDob(iso: string | null): string {
  return iso ? iso.slice(0, 10) : 'No DOB';
}

export function PatientPicker({ onSelect }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PatientListApiRow[]>([]);
  const [searching, setSearching] = useState(false);

  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDob, setNewDob] = useState('');
  const [newExternalId, setNewExternalId] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Duplicate-modal state — opened when fuzzy-match returns candidates
  // with score > 0.6 for the just-typed name. Carries the unsaved
  // inline form values so "Create new anyway" can proceed without the
  // user re-typing.
  const [duplicates, setDuplicates] = useState<{
    matches: FuzzyMatch[];
    pendingName: string;
    pendingDob: string;
    pendingExternalId: string | null;
  } | null>(null);

  // --- debounced search ---
  useEffect(() => {
    const term = query.trim();
    if (term === '') {
      setResults([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    const controller = new AbortController();
    const timer = setTimeout(async () => {
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
  }, [query]);

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
      // Check for fuzzy duplicates before creating. If any match has
      // score > 0.6 we show the duplicate modal; the doctor picks
      // "Use existing" or "Create new anyway".
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
      // No strong matches → create immediately.
      await actuallyCreate(name, dob.iso, externalId);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-2xl border border-border-default bg-bg-surface-1/60 p-5">
      <div className="mb-4 flex items-center gap-2">
        <UserPlus className="h-4 w-4 text-violet-400" aria-hidden />
        <h2 className="text-[15px] font-semibold tracking-tight text-text-primary">
          Who&apos;s this visit for?
        </h2>
      </div>

      {/* --- Search --- */}
      <label className="relative block">
        <span className="sr-only">Search patients</span>
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted"
          aria-hidden
        />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name or external ID…"
          className="block w-full rounded-lg border border-border-default bg-bg-surface-1/60 py-2.5 pl-10 pr-10 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30"
        />
        {query.length > 0 && (
          <button
            type="button"
            onClick={() => setQuery('')}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-text-muted hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
            aria-label="Clear search"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </label>

      {/* --- Results --- */}
      {query.trim().length > 0 && (
        <div className="mt-3 overflow-hidden rounded-lg border border-border-subtle bg-bg-surface-1/40">
          {searching && results.length === 0 && (
            <div className="flex items-center gap-2 px-4 py-3 text-[13px] text-text-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Searching…
            </div>
          )}
          {!searching && results.length === 0 && (
            <div className="px-4 py-3 text-[13px] text-text-muted">
              No matches. Create a new patient below.
            </div>
          )}
          {results.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => selectExisting(p)}
              className="flex w-full items-center gap-3 border-t border-border-subtle px-4 py-3 text-left transition-colors first:border-t-0 hover:bg-bg-surface-2/50 focus-visible:outline-none focus-visible:bg-bg-surface-2/70"
            >
              <div
                aria-hidden
                className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-[linear-gradient(135deg,#4C1D95_0%,#7C3AED_100%)] text-[12px] font-semibold text-white"
              >
                {p.name.charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[14px] text-text-primary">
                  {p.name}
                </div>
                <div className="text-[12px] text-text-muted">
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
            className="inline-flex items-center gap-1.5 rounded-full border border-border-subtle bg-bg-surface-1/40 px-4 py-2 text-[13px] font-medium text-text-secondary transition-colors hover:border-violet-500/60 hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
          >
            <Plus className="h-3.5 w-3.5" />
            Create new patient
          </button>
        ) : (
          <form
            onSubmit={onSubmitCreate}
            className="space-y-3 rounded-xl border border-border-subtle bg-bg-surface-1/40 p-4"
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-[12px] font-medium tracking-tight text-text-tertiary">
                  Name
                </label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  maxLength={200}
                  autoFocus
                  placeholder="Jane Doe"
                  className="block w-full rounded-lg border border-border-default bg-bg-surface-1/80 px-3 py-2 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30"
                />
              </div>
              <div>
                <label className="mb-1 block text-[12px] font-medium tracking-tight text-text-tertiary">
                  Date of birth
                </label>
                <input
                  type="date"
                  value={newDob}
                  onChange={(e) => setNewDob(e.target.value)}
                  min={`${MIN_DOB_YEAR}-01-01`}
                  max={new Date().toISOString().slice(0, 10)}
                  className="block w-full rounded-lg border border-border-default bg-bg-surface-1/80 px-3 py-2 text-[14px] text-text-primary outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block text-[12px] font-medium tracking-tight text-text-tertiary">
                  External ID{' '}
                  <span className="font-normal text-text-muted">(optional)</span>
                </label>
                <input
                  type="text"
                  value={newExternalId}
                  onChange={(e) => setNewExternalId(e.target.value)}
                  maxLength={100}
                  placeholder="EMR chart number or MRN"
                  className="block w-full rounded-lg border border-border-default bg-bg-surface-1/80 px-3 py-2 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30"
                />
              </div>
            </div>

            {createError && (
              <p className="text-[12px] text-danger">{createError}</p>
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
                className="rounded-full px-3 py-1.5 text-[13px] text-text-tertiary hover:text-text-secondary"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center gap-1.5 rounded-full bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)] px-4 py-2 text-[13px] font-medium text-white shadow-[0_0_0_1px_rgba(167,139,250,0.3)] transition-all hover:shadow-[0_0_0_1px_rgba(167,139,250,0.5)] disabled:opacity-50"
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
