'use client';

// ============================================================================
// TrashedVisitCard — card variant for the /patients/[id]?tab=trash tab
// (T-M17.3 Phase 4 Commit 8)
// ----------------------------------------------------------------------------
// Shows a dimmed visit card with a countdown chip + inline actions:
//   [Restore]              — instant, no confirm.
//   [Delete permanently]   — confirm modal; hits the Phase 2 delete
//                            endpoint with `?permanent=1` which
//                            transactionally drops AiCall rows +
//                            the visit row + best-effort MinIO sweep.
//
// The avatar + name + dates area is a <Link> to /visits/[id] (which
// renders its own Commit 6 trash banner + Restore/Delete buttons).
// The action row below is outside the Link so button clicks don't
// bubble into a navigation.
// ============================================================================

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import * as Dialog from '@radix-ui/react-dialog';
import { AlertTriangle, Loader2, RotateCcw, Trash2, X } from 'lucide-react';
import { toast } from 'sonner';

import { formatRelativeTime } from '@/lib/format-time';

const SOFT_DELETE_WINDOW_DAYS = 15;

export interface TrashedVisitCardData {
  id: string;
  patientName: string | null;
  specialty: string;
  /** Ignored for display (every row on this tab is trashed), but
   *  kept on the type so the server can forward the raw Prisma
   *  shape without reshaping. */
  status: string;
  createdAt: Date;
  deletedAt: Date;
}

interface Props {
  visit: TrashedVisitCardData;
}

// Thin wrapper around the shared formatter so the "Apr 14" fallback
// resolves in the viewer's local timezone.
function formatAgo(d: Date): string {
  return formatRelativeTime(d);
}

function daysUntilPurge(deletedAt: Date): number {
  const purge =
    deletedAt.getTime() + SOFT_DELETE_WINDOW_DAYS * 24 * 60 * 60 * 1000;
  const ms = purge - Date.now();
  return Math.max(0, Math.ceil(ms / (24 * 60 * 60 * 1000)));
}

export function TrashedVisitCard({ visit }: Props) {
  const router = useRouter();
  const [restoring, setRestoring] = useState(false);
  const displayName = visit.patientName?.trim() || 'Anonymous';
  const initial = displayName.charAt(0).toUpperCase();
  const daysLeft = daysUntilPurge(visit.deletedAt);

  async function onRestore() {
    setRestoring(true);
    try {
      const res = await fetch(`/api/visits/${visit.id}/restore`, {
        method: 'POST',
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        toast.error(body.error ?? 'Could not restore visit.');
        return;
      }
      toast.success('Visit restored');
      router.refresh();
    } catch {
      toast.error('Network error. Please try again.');
    } finally {
      setRestoring(false);
    }
  }

  return (
    <div className="group flex h-full flex-col gap-3 rounded-xl border border-border-subtle bg-bg-surface-1/40 p-5 opacity-75 transition-opacity hover:opacity-100">
      <Link
        href={`/visits/${visit.id}`}
        className="flex items-start gap-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base rounded-md"
      >
        <div
          aria-hidden
          className="flex h-10 w-10 flex-none items-center justify-center rounded-full bg-[linear-gradient(135deg,#4C1D95_0%,#7C3AED_50%,#A855F7_100%)] text-[14px] font-semibold text-white shadow-[0_0_0_1px_rgba(167,139,250,0.3)] grayscale-[25%]"
        >
          {initial}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[14px] font-medium text-text-primary">
            {displayName}
          </div>
          <div className="mt-0.5 text-[12px] text-text-muted">
            Deleted {formatAgo(visit.deletedAt)}
          </div>
        </div>
      </Link>

      <div className="flex items-center justify-between gap-3">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-border-subtle bg-bg-surface-2 px-2.5 py-0.5 text-[11px] font-medium tracking-tight text-text-tertiary">
          {visit.specialty}
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-warning/15 px-2.5 py-0.5 text-[11px] font-medium text-warning">
          Auto-deletes in {daysLeft} {daysLeft === 1 ? 'day' : 'days'}
        </span>
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-border-subtle pt-3">
        <button
          type="button"
          onClick={onRestore}
          disabled={restoring}
          className="inline-flex items-center gap-1.5 rounded-full border border-border-default bg-bg-surface-1/60 px-3 py-1.5 text-[12px] font-medium text-text-secondary transition-colors hover:border-violet-500/60 hover:text-text-primary disabled:opacity-50"
        >
          {restoring ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <RotateCcw className="h-3 w-3" aria-hidden />
          )}
          Restore
        </button>
        <DeletePermanentlyDialog
          visitId={visit.id}
          patientName={displayName}
        />
      </div>
    </div>
  );
}

function DeletePermanentlyDialog({
  visitId,
  patientName,
}: {
  visitId: string;
  patientName: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onConfirm() {
    setError(null);
    setPending(true);
    try {
      const res = await fetch(`/api/visits/${visitId}/delete?permanent=1`, {
        method: 'POST',
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        setError(body.error ?? 'Could not delete permanently.');
        return;
      }
      toast.success('Visit permanently deleted');
      setOpen(false);
      router.refresh();
    } catch {
      setError('Network error. Please try again.');
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) {
          setError(null);
          setPending(false);
        }
      }}
    >
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1.5 rounded-full border border-danger/60 bg-danger/10 px-3 py-1.5 text-[12px] font-medium text-danger transition-colors hover:bg-danger/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger"
        >
          <Trash2 className="h-3 w-3" aria-hidden />
          Delete permanently
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
                Delete this visit permanently?
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-[13px] leading-relaxed text-text-tertiary">
                This cannot be undone. All audio, transcripts, and
                AI-generated outputs for {patientName}&apos;s visit will
                be deleted.
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

          {error && <p className="mb-3 text-[12px] text-danger">{error}</p>}

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
              disabled={pending}
              className="inline-flex items-center gap-1.5 rounded-full bg-danger px-4 py-2 text-[13px] font-medium text-white shadow-[0_0_0_1px_rgba(239,68,68,0.3)] transition-all hover:shadow-[0_0_0_1px_rgba(239,68,68,0.5)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {pending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Delete permanently
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
