'use client';

// ============================================================================
// Edit Draft dialog — /visits/[id] (T-M17.3 Phase 4 Commit 7)
// ----------------------------------------------------------------------------
// Phase 5 — Linear V1 Faithful. Renders inside `.qm-lin-spotlight`
// chrome with hairline-bordered surface-1 form fields. Specialty
// dropdown, patient picker, chief complaint, and capture-mode tiles
// all migrate to the dark canvas. Server PATCH semantics are
// unchanged. The `theme` prop is preserved as a no-op.
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
import {
  Loader2,
  Mic,
  PenLine,
  Pencil,
  Radio,
  X,
  ArrowLeftRight,
} from 'lucide-react';
import { toast } from 'sonner';

import { SpecialtyDropdown } from '@/components/specialty-dropdown';
import { SPECIALTIES_FOR_VISIT_CREATE, findSpecialty } from '@meddoc/shared/specialties';
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
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
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

const FIELD_LABEL =
  'mb-1.5 block font-mono text-[10.5px] font-medium uppercase tracking-[0.07em] text-linear-text-3';

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
  // Normalize initialSpecialty to a canonical id so the dropdown
  // displays the right option even when the visit row still holds
  // a legacy display name ('Cardiology') or short id ('pain').
  // Typed as `string` (not SpecialtyId) so the SpecialtyDropdown's
  // generic onChange signature matches without an unsafe cast.
  const initialSpecialtyId: string = findSpecialty(initialSpecialty).id;
  const [specialty, setSpecialty] = useState<string>(initialSpecialtyId);
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
    specialty.trim() !== initialSpecialtyId ||
    normalizedCC !== initialChiefComplaint ||
    inputMode !== initialInputMode;

  const canSubmit = !submitting && nameOk && specialtyOk && hasChanged;

  function resetToInitial() {
    setPatient(initialPatient);
    setChangingPatient(false);
    setSpecialty(initialSpecialtyId);
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
    if (specialty.trim() !== initialSpecialtyId) body.specialty = specialty.trim();
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
        <button type="button" className="qm-lin-btn">
          <Pencil className="h-3.5 w-3.5" aria-hidden />
          Edit draft
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay
          className={cn(
            'qm-lin-spotlight',
            'data-[state=open]:animate-in data-[state=open]:fade-in'
          )}
        />
        <Dialog.Content
          className={cn(
            'qm-lin-spotlight-panel qm-lin-blur-in',
            'fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-full max-w-xl -translate-x-1/2 -translate-y-1/2 overflow-y-auto outline-none'
          )}
          style={{ padding: 0 }}
        >
          <div
            className="flex items-start justify-between gap-3"
            style={{ padding: '20px 24px 8px' }}
          >
            <div>
              <Dialog.Title
                style={{
                  margin: 0,
                  fontFamily: 'var(--font-sans)',
                  fontSize: 16,
                  fontWeight: 500,
                  letterSpacing: '-0.01em',
                  color: 'var(--color-linear-text)',
                }}
              >
                Edit draft
              </Dialog.Title>
              <Dialog.Description
                style={{
                  marginTop: 6,
                  marginBottom: 0,
                  fontSize: 13,
                  color: 'var(--color-linear-text-2)',
                }}
              >
                Adjust the patient, specialty, chief complaint, or
                capture mode before any input is uploaded.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close"
                className="flex-none rounded-md p-1 text-linear-text-3 hover:text-linear-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage"
              >
                <X className="h-4 w-4" />
              </button>
            </Dialog.Close>
          </div>

          <form
            onSubmit={onSubmit}
            className="space-y-4"
            style={{ padding: '4px 24px 16px' }}
          >
            {/* Patient */}
            <div>
              <label className={FIELD_LABEL}>Patient</label>
              {!changingPatient ? (
                <div className="flex items-center gap-3 rounded-lg border border-linear-border bg-linear-surface-1 px-3 py-2">
                  <div
                    aria-hidden
                    className="flex h-7 w-7 flex-none items-center justify-center rounded-full text-[11px] font-semibold"
                    style={{
                      background: 'var(--color-linear-sage-tint)',
                      color: 'var(--color-linear-sage-bright)',
                    }}
                  >
                    {patient.name.charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[14px] text-linear-text">
                      {patient.name}
                    </div>
                    <div className="text-[11px] text-linear-text-3">
                      {formatDob(patient.dateOfBirth)}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setChangingPatient(true)}
                    className="qm-lin-btn"
                  >
                    <ArrowLeftRight className="h-3 w-3" aria-hidden />
                    Change
                  </button>
                </div>
              ) : (
                <div className="rounded-lg border border-linear-border bg-linear-surface-1 p-3">
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
              <label className={FIELD_LABEL}>Specialty</label>
              <SpecialtyDropdown
                options={SPECIALTIES_FOR_VISIT_CREATE}
                name="specialty"
                defaultValue={specialty}
                onChange={setSpecialty}
              />
            </div>

            {/* Chief complaint */}
            <div>
              <label htmlFor="edit-draft-cc" className={FIELD_LABEL}>
                Chief complaint{' '}
                <span style={{ color: 'var(--color-linear-text-3)', fontWeight: 400, textTransform: 'none', letterSpacing: '-0.005em' }}>
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
                className="block w-full rounded-md border border-linear-border bg-linear-surface-1 px-3 py-2 text-[14px] text-linear-text placeholder:text-linear-text-3 outline-none transition-colors focus:border-linear-sage focus:ring-2 focus:ring-linear-sage/30"
              />
            </div>

            {/* Input mode */}
            <div>
              <div className={FIELD_LABEL}>Capture mode</div>
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
                        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage focus-visible:ring-offset-2 focus-visible:ring-offset-linear-bg',
                        active
                          ? 'border-[rgba(122,166,140,0.45)] bg-linear-sage-tint'
                          : 'border-linear-border bg-linear-surface-1 hover:border-linear-border-strong'
                      )}
                    >
                      <Icon
                        className={cn(
                          'h-4 w-4',
                          active ? 'text-linear-sage-bright' : 'text-linear-text-3'
                        )}
                        aria-hidden
                      />
                      <div>
                        <div className="text-[13px] font-medium text-linear-text">
                          {m.title}
                        </div>
                        <div className="mt-0.5 text-[11px] leading-relaxed text-linear-text-3">
                          {m.description}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {error && (
              <p className="text-[12px] text-linear-danger">{error}</p>
            )}

            <div
              className="flex items-center justify-end gap-2"
              style={{
                marginLeft: -24,
                marginRight: -24,
                marginBottom: -16,
                borderTop: '1px solid var(--color-linear-hairline)',
                background: 'var(--color-linear-surface-2)',
                padding: '12px 24px',
              }}
            >
              <Dialog.Close asChild>
                <button type="button" className="qm-lin-btn">
                  Cancel
                </button>
              </Dialog.Close>
              <button
                type="submit"
                disabled={!canSubmit}
                className="qm-lin-btn-primary"
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
