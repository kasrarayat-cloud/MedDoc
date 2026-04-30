'use client';

// ============================================================================
// Edit Draft dialog — /visits/[id] (T-M17.3 Phase 4 Commit 7)
// ----------------------------------------------------------------------------
// Radix Dialog that hits PATCH /api/visits/[id]. Four fields:
//
//   Patient       — PatientPickerCore from /visits/new, wrapped in a
//                   "current patient pill + Change" pattern so the
//                   full search/create UI only takes screen real estate
//                   when the doctor actually wants to swap patients.
//   Specialty     — SpecialtyDropdown (shared with the new-visit form).
//   Chief complaint — single-line text input.
//   Input mode    — three compact radio-style tiles. Not the new-visit
//                   TiltCard/GlowCard tiles — those are styled to be
//                   the page's CTA; inside a dialog a lighter
//                   treatment reads right.
//
// Save button is gated on (form valid AND something actually changed
// from initial values) — matches the T-M17.2 Edit Patient dialog
// pattern so a no-op Save doesn't bump updatedAt.
//
// Server error codes map to user-facing copy per the Commit 5 contract:
//   VISIT_NOT_DRAFT → "This visit is no longer a draft. Refresh."
//   VISIT_DELETED   → "This visit is in trash. Restore it first."
//   INVALID_PATIENT → "That patient no longer exists."
//   everything else → generic retry.
// ============================================================================

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import * as Dialog from '@radix-ui/react-dialog';
import { Loader2, Mic, PenLine, Pencil, Radio, X, ArrowLeftRight } from 'lucide-react';
import { toast } from 'sonner';

import { SpecialtyDropdown } from '@/components/specialty-dropdown';
import { SPECIALTIES } from '@/lib/specialties';
import { cn } from '@/lib/cn';
import { PatientPickerCore } from '@/app/visits/new/patient-picker';
import type { SelectedPatient } from '@/app/visits/new/patient-types';

type InputMode = 'audio_upload' | 'voice_dictation' | 'text_notes';

type EditDraftDialogTheme = 'legacy' | 'clinician';

interface Props {
  visitId: string;
  initialPatient: SelectedPatient;
  initialSpecialty: string;
  initialChiefComplaint: string | null;
  initialInputMode: InputMode;
  /** Phase 2 (Clinician remodel) — additive theme prop. Default
   *  `'legacy'` keeps the dark dialog with violet ring + gradient
   *  Save button. `'clinician'` swaps to the .qm-cl-card chrome on
   *  cream + sage focus rings + sage-deep Save CTA. */
  theme?: EditDraftDialogTheme;
}

interface PatchResponse {
  visit?: { id: string };
  error?: string;
  code?: string;
  field?: string;
}

const MODES: ReadonlyArray<{
  value: InputMode;
  title: string;
  description: string;
  icon: 'mic' | 'radio' | 'pen-line';
}> = [
  {
    value: 'audio_upload',
    title: 'Upload audio',
    description: 'Record the visit elsewhere, upload the file.',
    icon: 'mic',
  },
  {
    value: 'voice_dictation',
    title: 'Dictate live',
    description: 'Speak a summary into your mic.',
    icon: 'radio',
  },
  {
    value: 'text_notes',
    title: 'Text to SOAP',
    description: 'Type bullets, AI expands them.',
    icon: 'pen-line',
  },
];

const ICON_MAP = { mic: Mic, radio: Radio, 'pen-line': PenLine } as const;

function formatDob(iso: string | null): string {
  return iso ? `b. ${iso.slice(0, 10)}` : 'No DOB on file';
}

function mapErrorCode(code: string | undefined, fallback: string): string {
  switch (code) {
    case 'VISIT_NOT_DRAFT':
      return 'This visit is no longer a draft. Refresh the page.';
    case 'VISIT_DELETED':
      return 'This visit is in trash. Restore it first.';
    case 'INVALID_PATIENT':
      return 'That patient no longer exists.';
    default:
      return fallback || 'Could not save changes. Try again.';
  }
}

export function EditDraftDialog({
  visitId,
  initialPatient,
  initialSpecialty,
  initialChiefComplaint,
  initialInputMode,
  theme = 'legacy',
}: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const isClinician = theme === 'clinician';

  const [patient, setPatient] = useState<SelectedPatient>(initialPatient);
  const [changingPatient, setChangingPatient] = useState(false);
  const [specialty, setSpecialty] = useState(initialSpecialty);
  const [chiefComplaint, setChiefComplaint] = useState(
    initialChiefComplaint ?? ''
  );
  const [inputMode, setInputMode] = useState<InputMode>(initialInputMode);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const normalizedCC =
    chiefComplaint.trim() === '' ? null : chiefComplaint.trim();

  const nameOk = true; // patient is always set (can't unselect; just swap)
  const specialtyOk = specialty.trim().length > 0;

  const hasChanged =
    patient.id !== initialPatient.id ||
    specialty.trim() !== initialSpecialty ||
    normalizedCC !== initialChiefComplaint ||
    inputMode !== initialInputMode;

  const canSubmit =
    !submitting && nameOk && specialtyOk && hasChanged;

  function resetToInitial() {
    setPatient(initialPatient);
    setChangingPatient(false);
    setSpecialty(initialSpecialty);
    setChiefComplaint(initialChiefComplaint ?? '');
    setInputMode(initialInputMode);
    setSubmitting(false);
    setError(null);
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    const body: {
      patientId?: string;
      specialty?: string;
      chiefComplaint?: string | null;
      inputMode?: InputMode;
    } = {};
    if (patient.id !== initialPatient.id) body.patientId = patient.id;
    if (specialty.trim() !== initialSpecialty) body.specialty = specialty.trim();
    if (normalizedCC !== initialChiefComplaint) {
      body.chiefComplaint = normalizedCC;
    }
    if (inputMode !== initialInputMode) body.inputMode = inputMode;

    setSubmitting(true);
    try {
      const res = await fetch(`/api/visits/${visitId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = (await res.json().catch(() => ({}))) as PatchResponse;
      if (!res.ok || !data.visit) {
        setError(mapErrorCode(data.code, data.error ?? ''));
        return;
      }
      toast.success('Draft updated');
      setOpen(false);
      router.refresh();
    } catch {
      setError('Network error. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) resetToInitial();
      }}
    >
      <Dialog.Trigger asChild>
        <button
          type="button"
          className={cn(
            'inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-[13px] font-medium transition-colors',
            isClinician
              ? 'border border-clinician-line bg-clinician-cream-card text-clinician-ink-2 hover:bg-clinician-cream-2 hover:border-clinician-line-strong hover:text-clinician-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-clinician-sage focus-visible:ring-offset-2 focus-visible:ring-offset-clinician-cream'
              : 'border border-border-default bg-bg-surface-1/60 text-text-secondary hover:bg-bg-surface-2/70 hover:border-border-emphasis focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500'
          )}
        >
          <Pencil className="h-3.5 w-3.5" aria-hidden />
          Edit draft
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay
          className={cn(
            'fixed inset-0 z-40 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in',
            isClinician
              ? 'bg-[rgba(43,38,32,0.32)]'
              : 'bg-black/70'
          )}
        />
        <Dialog.Content
          className={cn(
            'fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-full max-w-xl -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-2xl p-6 outline-none',
            // Radix portals into <body> outside .qm-cl-app, so wrap
            // here when theme="clinician" so the inner clinician-*
            // utilities resolve.
            isClinician
              ? 'qm-cl-app border border-clinician-line bg-clinician-cream-card shadow-[0_32px_96px_-24px_rgba(43,38,32,0.18)]'
              : 'border border-border-default bg-bg-surface-1 shadow-2xl'
          )}
        >
          <div className="mb-5 flex items-start justify-between gap-3">
            <div>
              <Dialog.Title
                className={cn(
                  'text-[16px] font-semibold tracking-tight',
                  isClinician
                    ? 'qm-cl-serif text-clinician-ink'
                    : 'text-text-primary'
                )}
                style={
                  isClinician
                    ? { fontWeight: 500, letterSpacing: '-0.01em' }
                    : undefined
                }
              >
                Edit draft
              </Dialog.Title>
              <Dialog.Description
                className={cn(
                  'mt-1 text-[13px]',
                  isClinician ? 'text-clinician-ink-3' : 'text-text-tertiary'
                )}
              >
                Adjust the patient, specialty, chief complaint, or
                capture mode before any input is uploaded.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close"
                className={cn(
                  'flex-none rounded-md p-1',
                  isClinician
                    ? 'text-clinician-ink-3 hover:text-clinician-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-clinician-sage'
                    : 'text-text-muted hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500'
                )}
              >
                <X className="h-4 w-4" />
              </button>
            </Dialog.Close>
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
            {/* Patient */}
            <div>
              <label
                className={cn(
                  'mb-1 block text-[12px] font-medium tracking-tight',
                  isClinician ? 'text-clinician-ink-3' : 'text-text-tertiary'
                )}
              >
                Patient
              </label>
              {!changingPatient ? (
                <div
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2',
                    isClinician
                      ? 'border border-clinician-line bg-clinician-cream-card'
                      : 'border border-border-default bg-bg-surface-1/80'
                  )}
                >
                  <div
                    aria-hidden
                    className={cn(
                      'flex h-7 w-7 flex-none items-center justify-center rounded-full text-[11px] font-semibold',
                      isClinician
                        ? // Sage-tint avatar with sage-deep serif initial,
                          // mirroring the .qm-cl-avatar-sage idiom from
                          // the dashboard PatientCard.
                          'qm-cl-serif text-clinician-sage-deep'
                        : 'bg-[linear-gradient(135deg,#4C1D95_0%,#7C3AED_100%)] text-white'
                    )}
                    style={
                      isClinician
                        ? {
                            background:
                              'var(--sage-tint-strong, rgba(122, 166, 140, 0.22))',
                          }
                        : undefined
                    }
                  >
                    {patient.name.charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div
                      className={cn(
                        'truncate text-[14px]',
                        isClinician ? 'text-clinician-ink' : 'text-text-primary'
                      )}
                    >
                      {patient.name}
                    </div>
                    <div
                      className={cn(
                        'text-[11px]',
                        isClinician
                          ? 'text-clinician-ink-3'
                          : 'text-text-muted'
                      )}
                    >
                      {formatDob(patient.dateOfBirth)}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setChangingPatient(true)}
                    className={cn(
                      'inline-flex items-center gap-1 rounded-full px-3 py-1 text-[12px] transition-colors',
                      isClinician
                        ? 'text-clinician-ink-3 hover:bg-clinician-cream-2 hover:text-clinician-ink'
                        : 'text-text-tertiary hover:text-text-primary'
                    )}
                  >
                    <ArrowLeftRight className="h-3 w-3" aria-hidden />
                    Change
                  </button>
                </div>
              ) : (
                <div
                  className={cn(
                    'rounded-lg p-3',
                    isClinician
                      ? 'border border-clinician-line bg-clinician-cream-card'
                      : 'border border-border-subtle bg-bg-surface-1/40'
                  )}
                >
                  <PatientPickerCore
                    onSelect={(p) => {
                      setPatient(p);
                      setChangingPatient(false);
                    }}
                  />
                </div>
              )}
            </div>

            {/* Specialty */}
            <div>
              <label
                className={cn(
                  'mb-1 block text-[12px] font-medium tracking-tight',
                  isClinician ? 'text-clinician-ink-3' : 'text-text-tertiary'
                )}
              >
                Specialty
              </label>
              <SpecialtyDropdown
                options={SPECIALTIES}
                name="specialty"
                defaultValue={specialty}
                onChange={setSpecialty}
              />
            </div>

            {/* Chief complaint */}
            <div>
              <label
                htmlFor="edit-draft-cc"
                className={cn(
                  'mb-1 block text-[12px] font-medium tracking-tight',
                  isClinician ? 'text-clinician-ink-3' : 'text-text-tertiary'
                )}
              >
                Chief complaint{' '}
                <span
                  className={cn(
                    'font-normal',
                    isClinician
                      ? 'text-clinician-ink-4'
                      : 'text-text-muted'
                  )}
                >
                  (optional)
                </span>
              </label>
              <input
                id="edit-draft-cc"
                type="text"
                value={chiefComplaint}
                onChange={(e) => setChiefComplaint(e.target.value)}
                maxLength={500}
                placeholder="e.g. Headache for 3 days"
                className={cn(
                  'block w-full rounded-lg px-3 py-2 text-[14px] outline-none transition-colors',
                  isClinician
                    ? 'border border-clinician-line bg-clinician-cream-card text-clinician-ink placeholder:text-clinician-ink-4 focus:border-clinician-sage focus:ring-2 focus:ring-clinician-sage/30'
                    : 'border border-border-default bg-bg-surface-1/80 text-text-primary placeholder:text-text-muted focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30'
                )}
              />
            </div>

            {/* Input mode */}
            <div>
              <div
                className={cn(
                  'mb-2 text-[12px] font-medium tracking-tight',
                  isClinician ? 'text-clinician-ink-3' : 'text-text-tertiary'
                )}
              >
                Capture mode
              </div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                {MODES.map((m) => {
                  const Icon = ICON_MAP[m.icon];
                  const active = inputMode === m.value;
                  return (
                    <button
                      key={m.value}
                      type="button"
                      onClick={() => setInputMode(m.value)}
                      aria-pressed={active}
                      className={cn(
                        'flex flex-col gap-2 rounded-lg border p-3 text-left transition-colors',
                        isClinician
                          ? 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-clinician-sage focus-visible:ring-offset-2 focus-visible:ring-offset-clinician-cream'
                          : 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500',
                        active
                          ? isClinician
                            ? 'border-clinician-sage'
                            : 'border-violet-500 bg-violet-500/10'
                          : isClinician
                            ? 'border-clinician-line bg-clinician-cream-card hover:border-clinician-line-strong'
                            : 'border-border-default bg-bg-surface-1/40 hover:border-border-emphasis'
                      )}
                      style={
                        isClinician && active
                          ? {
                              background:
                                'var(--sage-tint, rgba(122, 166, 140, 0.14))',
                            }
                          : undefined
                      }
                    >
                      <Icon
                        className={cn(
                          'h-4 w-4',
                          active
                            ? isClinician
                              ? 'text-clinician-sage-deep'
                              : 'text-violet-300'
                            : isClinician
                              ? 'text-clinician-ink-3'
                              : 'text-text-tertiary'
                        )}
                        aria-hidden
                      />
                      <div>
                        <div
                          className={cn(
                            'text-[13px] font-medium',
                            isClinician
                              ? 'text-clinician-ink'
                              : 'text-text-primary'
                          )}
                        >
                          {m.title}
                        </div>
                        <div
                          className={cn(
                            'mt-0.5 text-[11px] leading-relaxed',
                            isClinician
                              ? 'text-clinician-ink-3'
                              : 'text-text-muted'
                          )}
                        >
                          {m.description}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {error && (
              <p
                className={cn(
                  'text-[12px]',
                  isClinician ? 'text-clinician-coral-deep' : 'text-danger'
                )}
              >
                {error}
              </p>
            )}

            <div
              className={cn(
                'flex items-center justify-end gap-2 border-t pt-4',
                isClinician ? 'border-clinician-line' : 'border-border-subtle'
              )}
            >
              <Dialog.Close asChild>
                <button
                  type="button"
                  className={cn(
                    'rounded-full px-3 py-2 text-[13px]',
                    isClinician
                      ? 'text-clinician-ink-3 hover:bg-clinician-cream-2 hover:text-clinician-ink'
                      : 'text-text-tertiary hover:text-text-secondary'
                  )}
                >
                  Cancel
                </button>
              </Dialog.Close>
              <button
                type="submit"
                disabled={!canSubmit}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-[13px] font-medium transition-all disabled:cursor-not-allowed disabled:opacity-50',
                  isClinician
                    ? // Sage-deep CTA on cream — mirrors .qm-cl-btn-primary
                      // chrome (sage solid bg + cream-card text + paper
                      // shadow). No gradient.
                      'qm-cl-btn qm-cl-btn-primary'
                    : 'bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)] text-white shadow-[0_0_0_1px_rgba(167,139,250,0.3)] hover:shadow-[0_0_0_1px_rgba(167,139,250,0.5)] disabled:hover:shadow-[0_0_0_1px_rgba(167,139,250,0.3)]'
                )}
              >
                {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Save changes
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
