'use client';

// ============================================================================
// Edit Patient dialog (T-M17.2 Phase 3 Commit 10)
// ----------------------------------------------------------------------------
// Radix Dialog fronting PATCH /api/patients/[id]. Three editable fields:
//   name          required, trimmed, 1-200 chars
//   dateOfBirth   optional — empty input means "unset", otherwise the
//                 shared validateDob() helper catches typos (future,
//                 pre-1900, calendar-impossible)
//   externalId    optional, 0-100 chars
//
// Submit is gated on (form-valid AND something actually changed from
// the initial values) so clicking Save on an untouched form doesn't
// fire a no-op PATCH + spuriously bump updatedAt.
//
// On success: router.refresh() so the server component re-fetches and
// the header's name/DOB/externalId re-render with the new values.
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
}

interface UpdateResponse {
  patient?: {
    id: string;
    name: string;
    dateOfBirth: string | null;
    externalId: string | null;
    updatedAt: string;
  };
  error?: string;
  field?: string;
}

export function EditPatientDialog({
  patientId,
  initialName,
  initialDob,
  initialExternalId,
}: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  const [name, setName] = useState(initialName);
  const [dob, setDob] = useState(initialDob ?? '');
  const [externalId, setExternalId] = useState(initialExternalId ?? '');

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);

  // Did anything actually change? Controls the Save-button enabled state.
  const normalizedCurrentDob = dob.trim() === '' ? null : dob.trim();
  const normalizedCurrentExternalId =
    externalId.trim() === '' ? null : externalId.trim();
  const hasChanged =
    name.trim() !== initialName ||
    normalizedCurrentDob !== initialDob ||
    normalizedCurrentExternalId !== initialExternalId;

  const nameOk = name.trim().length > 0 && name.trim().length <= 200;
  const dobIsEmptyOrValid =
    dob.trim() === '' || validateDob(dob).ok;
  const canSubmit =
    !submitting && hasChanged && nameOk && dobIsEmptyOrValid;

  function resetToInitial() {
    setName(initialName);
    setDob(initialDob ?? '');
    setExternalId(initialExternalId ?? '');
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
          className="inline-flex items-center gap-1.5 rounded-full border border-border-default bg-bg-surface-1/60 px-4 py-2 text-[13px] font-medium text-text-secondary transition-colors hover:bg-bg-surface-2/70 hover:border-border-emphasis focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base"
        >
          <Pencil className="h-3.5 w-3.5" aria-hidden />
          Edit
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-border-default bg-bg-surface-1 p-6 shadow-2xl outline-none">
          <div className="mb-5 flex items-start justify-between gap-3">
            <div>
              <Dialog.Title className="text-[16px] font-semibold tracking-tight text-text-primary">
                Edit patient
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-[13px] text-text-tertiary">
                Changes apply only to this patient record. Visit history
                stays intact.
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

          <form onSubmit={onSubmit} className="space-y-3">
            <div>
              <label
                htmlFor="edit-patient-name"
                className="mb-1 block text-[12px] font-medium tracking-tight text-text-tertiary"
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
                className="block w-full rounded-lg border border-border-default bg-bg-surface-1/80 px-3 py-2 text-[14px] text-text-primary outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30"
              />
            </div>

            <div>
              <label
                htmlFor="edit-patient-dob"
                className="mb-1 flex items-center justify-between text-[12px] font-medium tracking-tight text-text-tertiary"
              >
                <span>
                  Date of birth{' '}
                  <span className="font-normal text-text-muted">
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
                className="block w-full rounded-lg border border-border-default bg-bg-surface-1/80 px-3 py-2 text-[14px] text-text-primary outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30"
              />
            </div>

            <div>
              <label
                htmlFor="edit-patient-ext"
                className="mb-1 block text-[12px] font-medium tracking-tight text-text-tertiary"
              >
                External ID{' '}
                <span className="font-normal text-text-muted">(optional)</span>
              </label>
              <input
                id="edit-patient-ext"
                type="text"
                value={externalId}
                onChange={(e) => setExternalId(e.target.value)}
                maxLength={100}
                placeholder="EMR chart number or MRN"
                className="block w-full rounded-lg border border-border-default bg-bg-surface-1/80 px-3 py-2 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30"
              />
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
