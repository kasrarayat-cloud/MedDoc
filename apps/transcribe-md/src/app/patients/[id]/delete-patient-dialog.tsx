'use client';

// ============================================================================
// Delete Patient confirmation dialog (T-M17.2 Phase 3 Commit 10)
// ----------------------------------------------------------------------------
// Radix Dialog fronting DELETE /api/patients/[id]. Soft-delete only —
// the backend sets deletedAt = now(); linked visits remain intact
// (RESTRICT on the FK makes sure of this). The UI makes this clear in
// the confirmation copy so the doctor doesn't think they're wiping
// clinical history.
//
// On success: toast + redirect to /dashboard. Sonner's toast store
// persists across the client navigation so the "X deleted" banner
// shows up on the landing page.
// ============================================================================

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import * as Dialog from '@radix-ui/react-dialog';
import { AlertTriangle, Loader2, Trash2, X } from 'lucide-react';
import { toast } from 'sonner';

interface Props {
  patientId: string;
  patientName: string;
  visitCount: number;
}

export function DeletePatientDialog({
  patientId,
  patientName,
  visitCount,
}: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onConfirm() {
    setError(null);
    setSubmitting(true);
    try {
      const res = await fetch(`/api/patients/${patientId}`, {
        method: 'DELETE',
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        setError(body.error ?? 'Could not delete patient.');
        return;
      }
      toast.success(`${patientName} deleted`);
      setOpen(false);
      router.push('/dashboard');
    } catch {
      setError('Network error. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }

  const copy =
    visitCount === 0
      ? `Delete ${patientName}? This patient has no visits on file.`
      : `Delete ${patientName}? Their ${visitCount} visit${
          visitCount === 1 ? '' : 's'
        } will be preserved but the patient is hidden from your dashboard.`;

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) {
          setSubmitting(false);
          setError(null);
        }
      }}
    >
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1.5 rounded-full border border-border-default bg-bg-surface-1/60 px-4 py-2 text-[13px] font-medium text-text-secondary transition-colors hover:border-danger/60 hover:bg-danger/10 hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base"
        >
          <Trash2 className="h-3.5 w-3.5" aria-hidden />
          Delete
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-border-default bg-bg-surface-1 p-6 shadow-2xl outline-none">
          <div className="mb-5 flex items-start gap-3">
            <div
              aria-hidden
              className="flex h-9 w-9 flex-none items-center justify-center rounded-full bg-danger/15 text-danger"
            >
              <AlertTriangle className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <Dialog.Title className="text-[15px] font-semibold tracking-tight text-text-primary">
                Delete patient?
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-[13px] leading-relaxed text-text-tertiary">
                {copy}
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

          {error && (
            <p className="mb-3 text-[12px] text-danger">{error}</p>
          )}

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
              type="button"
              onClick={onConfirm}
              disabled={submitting}
              className="inline-flex items-center gap-1.5 rounded-full bg-danger px-4 py-2 text-[13px] font-medium text-white shadow-[0_0_0_1px_rgba(239,68,68,0.3)] transition-all hover:shadow-[0_0_0_1px_rgba(239,68,68,0.5)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Delete patient
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
