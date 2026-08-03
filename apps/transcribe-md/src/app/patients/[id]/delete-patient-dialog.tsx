'use client';

// ============================================================================
// Delete Patient confirmation dialog
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
//
// Phase 5 (Linear V1 Faithful) — spotlight overlay on the dark canvas
// with a danger-tinted icon plate and danger CTA.
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
          className="inline-flex items-center gap-1.5 rounded-md border border-linear-border bg-transparent px-3 py-1.5 text-[12px] font-medium text-linear-text-2 transition-colors hover:border-linear-danger/60 hover:bg-[rgba(212,87,74,0.10)] hover:text-linear-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-danger/40"
        >
          <Trash2 className="h-3.5 w-3.5" aria-hidden />
          Delete
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in" />
        <Dialog.Content className="qm-rounds-host qm-rounds-dialog fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg border border-linear-border-strong bg-linear-surface-2 p-6 shadow-[0_30px_80px_rgba(0,0,0,0.6)] outline-none">
          <div className="mb-5 flex items-start gap-3">
            <div
              aria-hidden
              className="flex h-9 w-9 flex-none items-center justify-center rounded-full"
              style={{
                background: 'rgba(212,87,74,0.18)',
                color: 'var(--color-linear-danger)',
              }}
            >
              <AlertTriangle className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <Dialog.Title className="text-[15px] font-semibold tracking-tight text-linear-text">
                Delete patient?
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-[13px] leading-relaxed text-linear-text-2">
                {copy}
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

          {error && (
            <p className="mb-3 text-[12px] text-linear-danger">{error}</p>
          )}

          <div className="flex items-center justify-end gap-2 border-t border-linear-border pt-4">
            <Dialog.Close asChild>
              <button
                type="button"
                className="qm-lin-btn qm-rounds-btn-secondary"
              >
                Cancel
              </button>
            </Dialog.Close>
            <button
              type="button"
              onClick={onConfirm}
              disabled={submitting}
              className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60"
              style={{
                background: 'var(--color-linear-danger)',
                color: '#fff',
              }}
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
