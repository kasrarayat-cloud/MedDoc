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

interface Props {
  visitId: string;
  initialPatient: SelectedPatient;
  initialSpecialty: string;
  initialChiefComplaint: string | null;
  initialInputMode: InputMode;
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
}: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);

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
          className="inline-flex items-center gap-1.5 rounded-full border border-border-default bg-bg-surface-1/60 px-4 py-2 text-[13px] font-medium text-text-secondary transition-colors hover:bg-bg-surface-2/70 hover:border-border-emphasis focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
        >
          <Pencil className="h-3.5 w-3.5" aria-hidden />
          Edit draft
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-full max-w-xl -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-2xl border border-border-default bg-bg-surface-1 p-6 shadow-2xl outline-none">
          <div className="mb-5 flex items-start justify-between gap-3">
            <div>
              <Dialog.Title className="text-[16px] font-semibold tracking-tight text-text-primary">
                Edit draft
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-[13px] text-text-tertiary">
                Adjust the patient, specialty, chief complaint, or
                capture mode before any input is uploaded.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close"
                className="flex-none rounded-md p-1 text-text-muted hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
              >
                <X className="h-4 w-4" />
              </button>
            </Dialog.Close>
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
            {/* Patient */}
            <div>
              <label className="mb-1 block text-[12px] font-medium tracking-tight text-text-tertiary">
                Patient
              </label>
              {!changingPatient ? (
                <div className="flex items-center gap-3 rounded-lg border border-border-default bg-bg-surface-1/80 px-3 py-2">
                  <div
                    aria-hidden
                    className="flex h-7 w-7 flex-none items-center justify-center rounded-full bg-[linear-gradient(135deg,#4C1D95_0%,#7C3AED_100%)] text-[11px] font-semibold text-white"
                  >
                    {patient.name.charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[14px] text-text-primary">
                      {patient.name}
                    </div>
                    <div className="text-[11px] text-text-muted">
                      {formatDob(patient.dateOfBirth)}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setChangingPatient(true)}
                    className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-[12px] text-text-tertiary transition-colors hover:text-text-primary"
                  >
                    <ArrowLeftRight className="h-3 w-3" aria-hidden />
                    Change
                  </button>
                </div>
              ) : (
                <div className="rounded-lg border border-border-subtle bg-bg-surface-1/40 p-3">
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
              <label className="mb-1 block text-[12px] font-medium tracking-tight text-text-tertiary">
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
                className="mb-1 block text-[12px] font-medium tracking-tight text-text-tertiary"
              >
                Chief complaint{' '}
                <span className="font-normal text-text-muted">(optional)</span>
              </label>
              <input
                id="edit-draft-cc"
                type="text"
                value={chiefComplaint}
                onChange={(e) => setChiefComplaint(e.target.value)}
                maxLength={500}
                placeholder="e.g. Headache for 3 days"
                className="block w-full rounded-lg border border-border-default bg-bg-surface-1/80 px-3 py-2 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30"
              />
            </div>

            {/* Input mode */}
            <div>
              <div className="mb-2 text-[12px] font-medium tracking-tight text-text-tertiary">
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
                        'flex flex-col gap-2 rounded-lg border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500',
                        active
                          ? 'border-violet-500 bg-violet-500/10'
                          : 'border-border-default bg-bg-surface-1/40 hover:border-border-emphasis'
                      )}
                    >
                      <Icon
                        className={cn(
                          'h-4 w-4',
                          active ? 'text-violet-300' : 'text-text-tertiary'
                        )}
                        aria-hidden
                      />
                      <div>
                        <div className="text-[13px] font-medium text-text-primary">
                          {m.title}
                        </div>
                        <div className="mt-0.5 text-[11px] leading-relaxed text-text-muted">
                          {m.description}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {error && <p className="text-[12px] text-danger">{error}</p>}

            <div className="flex items-center justify-end gap-2 border-t border-border-subtle pt-4">
              <Dialog.Close asChild>
                <button
                  type="button"
                  className="rounded-full px-3 py-2 text-[13px] text-text-tertiary hover:text-text-secondary"
                >
                  Cancel
                </button>
              </Dialog.Close>
              <button
                type="submit"
                disabled={!canSubmit}
                className="inline-flex items-center gap-1.5 rounded-full bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)] px-4 py-2 text-[13px] font-medium text-white shadow-[0_0_0_1px_rgba(167,139,250,0.3)] transition-all hover:shadow-[0_0_0_1px_rgba(167,139,250,0.5)] disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:shadow-[0_0_0_1px_rgba(167,139,250,0.3)]"
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
