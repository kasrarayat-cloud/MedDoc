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
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop on both PatientPicker and PatientPickerCore. Default
// `'legacy'` keeps the dark surface + violet ring chrome verbatim.
// `theme="clinician"` swaps to a `.qm-cl-card` surface with sage
// focus rings, `.qm-cl-avatar-sage` initial chips, and Source Serif 4
// patient names — matching the visit-detail mockup's quiet card idiom.
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
  /** Phase 2 (Clinician remodel) — additive theme prop. */
  theme?: PatientPickerTheme;
}

/** Full picker with the `/visits/new` "Who's this visit for?" card
 *  wrapper. Used as Step 1 of the new-visit flow. For callers that
 *  want the picker inside their own container (Edit-draft dialog,
 *  future command-palette entry), use PatientPickerCore instead. */
export function PatientPicker(props: CoreProps) {
  const isClinician = props.theme === 'clinician';
  return (
    <div
      className={cn(
        'p-5',
        isClinician
          ? 'qm-cl-card'
          : 'rounded-2xl border border-border-default bg-bg-surface-1/60'
      )}
      style={isClinician ? { padding: 24 } : undefined}
    >
      <div className="mb-4 flex items-center gap-2">
        <UserPlus
          className={cn(
            'h-4 w-4',
            isClinician ? 'text-clinician-sage' : 'text-violet-400'
          )}
          aria-hidden
        />
        <h2
          className={cn(
            'tracking-tight',
            isClinician
              ? 'qm-cl-serif text-clinician-ink'
              : 'text-[15px] font-semibold text-text-primary'
          )}
          style={
            isClinician
              ? { fontSize: 18, fontWeight: 500, letterSpacing: '-0.005em' }
              : undefined
          }
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
 *  modal. No outer card/header; callers supply their own framing.
 *  Contract: call onSelect with the chosen patient. */
export function PatientPickerCore({ onSelect, theme = 'legacy' }: CoreProps) {
  const isClinician = theme === 'clinician';
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
  // When the term is empty we skip the fetch entirely; the results
  // container below is gated on `query.trim().length > 0` so stale
  // state doesn't render. Clearing state synchronously inside the
  // effect triggered react-hooks/set-state-in-effect.
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
    <div>
      {/* --- Search --- */}
      <label className="relative block">
        <span className="sr-only">Search patients</span>
        <Search
          className={cn(
            'pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2',
            isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
          )}
          aria-hidden
        />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name or external ID…"
          className={
            isClinician
              ? 'qm-cl-input block w-full pl-10 pr-10'
              : 'block w-full rounded-lg border border-border-default bg-bg-surface-1/60 py-2.5 pl-10 pr-10 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30'
          }
        />
        {query.length > 0 && (
          <button
            type="button"
            onClick={() => setQuery('')}
            className={cn(
              'absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 focus-visible:outline-none focus-visible:ring-2',
              isClinician
                ? 'text-clinician-ink-3 hover:text-clinician-ink-2 focus-visible:ring-clinician-sage'
                : 'text-text-muted hover:text-text-secondary focus-visible:ring-violet-500'
            )}
            aria-label="Clear search"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </label>

      {/* --- Results --- */}
      {query.trim().length > 0 && (
        <div
          className={cn(
            'mt-3 overflow-hidden rounded-lg',
            isClinician
              ? 'border border-clinician-line bg-clinician-cream'
              : 'border border-border-subtle bg-bg-surface-1/40'
          )}
        >
          {searching && results.length === 0 && (
            <div
              className={cn(
                'flex items-center gap-2 px-4 py-3 text-[13px]',
                isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
              )}
            >
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Searching…
            </div>
          )}
          {!searching && results.length === 0 && (
            <div
              className={cn(
                'px-4 py-3 text-[13px]',
                isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
              )}
            >
              No matches. Create a new patient below.
            </div>
          )}
          {results.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => selectExisting(p)}
              className={cn(
                'flex w-full items-center gap-3 px-4 py-3 text-left transition-colors first:border-t-0 focus-visible:outline-none',
                isClinician
                  ? 'border-t border-clinician-line hover:bg-clinician-cream-2/60 focus-visible:bg-clinician-cream-2'
                  : 'border-t border-border-subtle hover:bg-bg-surface-2/50 focus-visible:bg-bg-surface-2/70'
              )}
            >
              {isClinician ? (
                <div
                  aria-hidden
                  className="qm-cl-avatar qm-cl-avatar-sage flex-none"
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 10,
                    fontSize: 13,
                  }}
                >
                  {p.name.charAt(0).toUpperCase()}
                </div>
              ) : (
                <div
                  aria-hidden
                  className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-[linear-gradient(135deg,#4C1D95_0%,#7C3AED_100%)] text-[12px] font-semibold text-white"
                >
                  {p.name.charAt(0).toUpperCase()}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <div
                  className={cn(
                    'truncate',
                    isClinician
                      ? 'qm-cl-serif text-clinician-ink'
                      : 'text-[14px] text-text-primary'
                  )}
                  style={isClinician ? { fontSize: 15 } : undefined}
                >
                  {p.name}
                </div>
                <div
                  className={cn(
                    'text-[12px]',
                    isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
                  )}
                >
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
            className={
              isClinician
                ? 'qm-cl-btn qm-cl-btn-soft'
                : 'inline-flex items-center gap-1.5 rounded-full border border-border-subtle bg-bg-surface-1/40 px-4 py-2 text-[13px] font-medium text-text-secondary transition-colors hover:border-violet-500/60 hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500'
            }
            style={
              isClinician
                ? { padding: '10px 18px', fontSize: 13.5 }
                : undefined
            }
          >
            <Plus className="h-3.5 w-3.5" />
            Create new patient
          </button>
        ) : (
          <form
            onSubmit={onSubmitCreate}
            className={cn(
              'space-y-3 rounded-xl p-4',
              isClinician
                ? 'border border-clinician-line bg-clinician-cream'
                : 'border border-border-subtle bg-bg-surface-1/40'
            )}
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label
                  className={cn(
                    'mb-1 block text-[12px] font-medium tracking-tight',
                    isClinician
                      ? 'text-clinician-ink-2'
                      : 'text-text-tertiary'
                  )}
                >
                  Name
                </label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  maxLength={200}
                  autoFocus
                  placeholder="Jane Doe"
                  className={
                    isClinician
                      ? 'qm-cl-input block w-full'
                      : 'block w-full rounded-lg border border-border-default bg-bg-surface-1/80 px-3 py-2 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30'
                  }
                />
              </div>
              <div>
                <label
                  className={cn(
                    'mb-1 block text-[12px] font-medium tracking-tight',
                    isClinician
                      ? 'text-clinician-ink-2'
                      : 'text-text-tertiary'
                  )}
                >
                  Date of birth
                </label>
                <input
                  type="date"
                  value={newDob}
                  onChange={(e) => setNewDob(e.target.value)}
                  min={`${MIN_DOB_YEAR}-01-01`}
                  max={new Date().toISOString().slice(0, 10)}
                  className={
                    isClinician
                      ? 'qm-cl-input block w-full'
                      : 'block w-full rounded-lg border border-border-default bg-bg-surface-1/80 px-3 py-2 text-[14px] text-text-primary outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30'
                  }
                />
              </div>
              <div className="sm:col-span-2">
                <label
                  className={cn(
                    'mb-1 block text-[12px] font-medium tracking-tight',
                    isClinician
                      ? 'text-clinician-ink-2'
                      : 'text-text-tertiary'
                  )}
                >
                  External ID{' '}
                  <span
                    className={cn(
                      'font-normal',
                      isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
                    )}
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
                  className={
                    isClinician
                      ? 'qm-cl-input block w-full'
                      : 'block w-full rounded-lg border border-border-default bg-bg-surface-1/80 px-3 py-2 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30'
                  }
                />
              </div>
            </div>

            {createError && (
              <p
                className={cn(
                  'text-[12px]',
                  isClinician ? 'text-clinician-coral-deep' : 'text-danger'
                )}
                style={
                  isClinician ? { color: 'var(--coral-deep)' } : undefined
                }
              >
                {createError}
              </p>
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
                className={
                  isClinician
                    ? 'qm-cl-btn qm-cl-btn-ghost'
                    : 'rounded-full px-3 py-1.5 text-[13px] text-text-tertiary hover:text-text-secondary'
                }
                style={
                  isClinician
                    ? { padding: '8px 16px', fontSize: 13 }
                    : undefined
                }
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className={
                  isClinician
                    ? 'qm-cl-btn qm-cl-btn-primary'
                    : 'inline-flex items-center gap-1.5 rounded-full bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)] px-4 py-2 text-[13px] font-medium text-white shadow-[0_0_0_1px_rgba(167,139,250,0.3)] transition-all hover:shadow-[0_0_0_1px_rgba(167,139,250,0.5)] disabled:opacity-50'
                }
                style={
                  isClinician
                    ? {
                        padding: '10px 18px',
                        fontSize: 13.5,
                        opacity: submitting ? 0.6 : 1,
                      }
                    : undefined
                }
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
          theme={theme}
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
