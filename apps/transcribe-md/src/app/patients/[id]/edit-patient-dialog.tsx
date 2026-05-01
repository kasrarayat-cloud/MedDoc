'use client';

// ============================================================================
// Edit Patient dialog
// ----------------------------------------------------------------------------
// Radix Dialog fronting PATCH /api/patients/[id]. Editable fields:
//   name          required, trimmed, 1-200 chars
//   dateOfBirth   optional — empty input means "unset", otherwise the
//                 shared validateDob() helper catches typos (future,
//                 pre-1900, calendar-impossible)
//   mrn           optional, 0-50 chars
//   insurance     optional, 0-200 chars
//   externalId    optional, 0-100 chars
//
// Submit is gated on (form-valid AND something actually changed from
// the initial values) so clicking Save on an untouched form doesn't
// fire a no-op PATCH + spuriously bump updatedAt.
//
// On success: router.refresh() so the server component re-fetches and
// the header's name/DOB/externalId re-render with the new values.
//
// Phase 5 (Linear V1 Faithful) — spotlight overlay on the dark canvas.
// Form fields render against linear-surface-1 with sage focus ring; the
// previous violet gradient CTA becomes the standard sage primary.
// ============================================================================

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import * as Dialog from '@radix-ui/react-dialog';
import { Loader2, X, Pencil } from 'lucide-react';
import { toast } from 'sonner';

import { MIN_DOB_YEAR, validateDob } from '@/lib/dob';

interface Props {
  patientId: string;
  initialName: string;
  /** YYYY-MM-DD or null. Server formats the Prisma DATE on its side
   *  before passing this in so the client doesn't juggle Date objects. */
  initialDob: string | null;
  initialExternalId: string | null;
  initialMrn: string | null;
  initialInsurance: string | null;
}

interface UpdateResponse {
  patient?: {
    id: string;
    name: string;
    dateOfBirth: string | null;
    externalId: string | null;
    mrn: string | null;
    insurance: string | null;
    updatedAt: string;
  };
  error?: string;
  field?: string;
}

const FIELD_INPUT_CLS =
  'block w-full rounded-md border border-linear-border bg-linear-surface-1 px-3 py-2 text-[14px] text-linear-text placeholder:text-linear-text-3 outline-none transition-colors focus:border-linear-border-strong focus:ring-2 focus:ring-linear-sage/40';

export function EditPatientDialog({
  patientId,
  initialName,
  initialDob,
  initialExternalId,
  initialMrn,
  initialInsurance,
}: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  const [name, setName] = useState(initialName);
  const [dob, setDob] = useState(initialDob ?? '');
  const [externalId, setExternalId] = useState(initialExternalId ?? '');
  const [mrn, setMrn] = useState(initialMrn ?? '');
  const [insurance, setInsurance] = useState(initialInsurance ?? '');

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);

  // Did anything actually change? Controls the Save-button enabled state.
  const normalizedCurrentDob = dob.trim() === '' ? null : dob.trim();
  const normalizedCurrentExternalId =
    externalId.trim() === '' ? null : externalId.trim();
  const normalizedCurrentMrn = mrn.trim() === '' ? null : mrn.trim();
  const normalizedCurrentInsurance =
    insurance.trim() === '' ? null : insurance.trim();
  const hasChanged =
    name.trim() !== initialName ||
    normalizedCurrentDob !== initialDob ||
    normalizedCurrentExternalId !== initialExternalId ||
    normalizedCurrentMrn !== initialMrn ||
    normalizedCurrentInsurance !== initialInsurance;

  const nameOk = name.trim().length > 0 && name.trim().length <= 200;
  const dobIsEmptyOrValid =
    dob.trim() === '' || validateDob(dob).ok;
  const canSubmit =
    !submitting && hasChanged && nameOk && dobIsEmptyOrValid;

  function resetToInitial() {
    setName(initialName);
    setDob(initialDob ?? '');
    setExternalId(initialExternalId ?? '');
    setMrn(initialMrn ?? '');
    setInsurance(initialInsurance ?? '');
    setError(null);
    setSubmitting(false);
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    // Final validation guard. canSubmit already enforces this, but an
    // attacker could keyboard-trigger submit outside the form state.
    const trimmedName = name.trim();
    if (trimmedName.length === 0 || trimmedName.length > 200) {
      setError('Name is required (1-200 chars).');
      return;
    }

    // Build a patch containing ONLY the fields that actually changed —
    // the API PATCH treats `undefined` as "leave unchanged" and `null`
    // as "clear this field".
    const body: {
      name?: string;
      dateOfBirth?: string | null;
      externalId?: string | null;
      mrn?: string | null;
      insurance?: string | null;
    } = {};
    if (trimmedName !== initialName) body.name = trimmedName;
    if (normalizedCurrentDob !== initialDob) {
      if (normalizedCurrentDob === null) {
        body.dateOfBirth = null;
      } else {
        const v = validateDob(normalizedCurrentDob);
        if (!v.ok) {
          setError(v.error);
          return;
        }
        body.dateOfBirth = v.iso;
      }
    }
    if (normalizedCurrentExternalId !== initialExternalId) {
      body.externalId = normalizedCurrentExternalId;
    }
    if (normalizedCurrentMrn !== initialMrn) {
      body.mrn = normalizedCurrentMrn;
    }
    if (normalizedCurrentInsurance !== initialInsurance) {
      body.insurance = normalizedCurrentInsurance;
    }

    setSubmitting(true);
    try {
      const res = await fetch(`/api/patients/${patientId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = (await res.json().catch(() => ({}))) as UpdateResponse;
      if (!res.ok || !data.patient) {
        setError(data.error ?? 'Could not save changes.');
        return;
      }
      toast.success('Patient updated');
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
          className="inline-flex items-center gap-1.5 rounded-md border border-linear-border bg-transparent px-3 py-1.5 text-[12px] font-medium text-linear-text-2 transition-colors hover:border-linear-border-strong hover:text-linear-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage/40"
        >
          <Pencil className="h-3.5 w-3.5" aria-hidden />
          Edit
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-lg border border-linear-border-strong bg-linear-surface-2 p-6 shadow-[0_30px_80px_rgba(0,0,0,0.6)] outline-none">
          <div className="mb-5 flex items-start justify-between gap-3">
            <div>
              <Dialog.Title className="text-[16px] font-semibold tracking-tight text-linear-text">
                Edit patient
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-[13px] text-linear-text-3">
                Changes apply only to this patient record. Visit history
                stays intact.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close"
                className="flex-none rounded-md p-1 text-linear-text-3 hover:text-linear-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage/40"
              >
                <X className="h-4 w-4" />
              </button>
            </Dialog.Close>
          </div>

          <form onSubmit={onSubmit} className="space-y-3">
            <div>
              <label
                htmlFor="edit-patient-name"
                className="mb-1 block font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-linear-text-3"
              >
                Name
              </label>
              <input
                id="edit-patient-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={200}
                autoFocus
                className={FIELD_INPUT_CLS}
              />
            </div>

            <div>
              <label
                htmlFor="edit-patient-dob"
                className="mb-1 flex items-center justify-between font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-linear-text-3"
              >
                <span>
                  Date of birth{' '}
                  <span className="font-normal lowercase tracking-normal text-linear-text-3">
                    (clear to remove)
                  </span>
                </span>
              </label>
              <input
                id="edit-patient-dob"
                type="date"
                value={dob}
                onChange={(e) => setDob(e.target.value)}
                min={`${MIN_DOB_YEAR}-01-01`}
                max={today}
                className={FIELD_INPUT_CLS}
              />
            </div>

            <div>
              <label
                htmlFor="edit-patient-mrn"
                className="mb-1 block font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-linear-text-3"
              >
                MRN{' '}
                <span className="font-normal lowercase tracking-normal text-linear-text-3">
                  (optional)
                </span>
              </label>
              <input
                id="edit-patient-mrn"
                type="text"
                value={mrn}
                onChange={(e) => setMrn(e.target.value)}
                maxLength={50}
                placeholder="Medical record number"
                className={FIELD_INPUT_CLS}
              />
            </div>

            <div>
              <label
                htmlFor="edit-patient-ins"
                className="mb-1 block font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-linear-text-3"
              >
                Insurance{' '}
                <span className="font-normal lowercase tracking-normal text-linear-text-3">
                  (optional)
                </span>
              </label>
              <input
                id="edit-patient-ins"
                type="text"
                value={insurance}
                onChange={(e) => setInsurance(e.target.value)}
                maxLength={200}
                placeholder="Aetna PPO, Medicare, Self-pay…"
                className={FIELD_INPUT_CLS}
              />
            </div>

            <div>
              <label
                htmlFor="edit-patient-ext"
                className="mb-1 block font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-linear-text-3"
              >
                External ID{' '}
                <span className="font-normal lowercase tracking-normal text-linear-text-3">
                  (optional; separate from MRN)
                </span>
              </label>
              <input
                id="edit-patient-ext"
                type="text"
                value={externalId}
                onChange={(e) => setExternalId(e.target.value)}
                maxLength={100}
                placeholder="EMR chart number"
                className={FIELD_INPUT_CLS}
              />
            </div>

            {error && <p className="text-[12px] text-linear-danger">{error}</p>}

            <div className="flex items-center justify-end gap-2 border-t border-linear-border pt-4">
              <Dialog.Close asChild>
                <button type="button" className="qm-lin-btn">
                  Cancel
                </button>
              </Dialog.Close>
              <button
                type="submit"
                disabled={!canSubmit}
                className="qm-lin-btn-primary disabled:cursor-not-allowed disabled:opacity-50"
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
