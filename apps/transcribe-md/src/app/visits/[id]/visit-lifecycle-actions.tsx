'use client';

// ============================================================================
// Visit lifecycle UI — banner + action buttons + confirm dialogs
// (T-M17.3 Phase 4 Commit 6)
// ----------------------------------------------------------------------------
// Renders the context-aware action UI above the visit body:
//
//   Trashed          banner "in trash, auto-deletes in N days"
//                    + [Restore] + [Delete permanently]
//   Archived         banner "archived"
//                    + [Unarchive]
//   SIGNED           [Archive]  (neutral chip-style)
//   Other non-trashed [Delete]  (destructive)
//
// On success:
//   - Restore / Unarchive / Archive → router.refresh() so the page
//     re-renders with the new state
//   - Soft Delete                   → router.push('/dashboard') + toast
//   - Hard Delete (QUEUED+no input or from-trash) → same
// ============================================================================

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import * as Dialog from '@radix-ui/react-dialog';
import {
  AlertTriangle,
  Archive,
  ArchiveRestore,
  Loader2,
  RotateCcw,
  Trash2,
  X,
} from 'lucide-react';
import { toast } from 'sonner';

import { TranscribeVisitStatus } from '@prisma/client';

const SOFT_DELETE_WINDOW_DAYS = 15;

interface Props {
  visitId: string;
  status: TranscribeVisitStatus;
  deletedAt: string | null;
  archivedAt: string | null;
  /** Null when the visit is a QUEUED draft with no input uploaded yet
   *  — the doctor can Delete it, which goes through the HARD path
   *  on the server. Non-null otherwise (server still does the final
   *  routing; this just drives the confirm copy). */
  hasInput: boolean;
  /** T-M17.3 Commit 7: Edit-draft dialog slotted in next to the
   *  Delete button for QUEUED+no-input visits. Null for every other
   *  lifecycle state. */
  editSlot?: React.ReactNode;
}

function daysUntilAutoPurge(deletedAtIso: string): number {
  const deletedAt = new Date(deletedAtIso).getTime();
  const purgeAt = deletedAt + SOFT_DELETE_WINDOW_DAYS * 24 * 60 * 60 * 1000;
  const msLeft = purgeAt - Date.now();
  return Math.max(0, Math.ceil(msLeft / (24 * 60 * 60 * 1000)));
}

export function VisitLifecycleActions({
  visitId,
  status,
  deletedAt,
  archivedAt,
  hasInput,
  editSlot,
}: Props) {
  if (deletedAt !== null) {
    return (
      <TrashedBanner
        visitId={visitId}
        deletedAtIso={deletedAt}
      />
    );
  }
  if (archivedAt !== null) {
    return <ArchivedBanner visitId={visitId} />;
  }
  if (status === TranscribeVisitStatus.SIGNED) {
    return (
      <div className="mb-6 flex flex-wrap justify-end gap-2">
        <ArchiveButton visitId={visitId} />
      </div>
    );
  }
  // QUEUED / PROCESSING / REVIEW / READY — Edit lives here (when the
  // visit is still a blank draft) alongside Delete.
  return (
    <div className="mb-6 flex flex-wrap justify-end gap-2">
      {editSlot}
      <DeleteButton visitId={visitId} status={status} hasInput={hasInput} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Banners
// ---------------------------------------------------------------------------

function TrashedBanner({
  visitId,
  deletedAtIso,
}: {
  visitId: string;
  deletedAtIso: string;
}) {
  const daysLeft = daysUntilAutoPurge(deletedAtIso);
  // T-M18.3 A27: shared banner-level busy flag. Either Restore or
  // Delete-permanently sets it true for the life of its fetch; the
  // sibling is `disabled` throughout. Prevents the narrow race where
  // a user escapes the Delete dialog mid-fetch and then clicks
  // Restore while the permanent-delete request is still in flight.
  const [busy, setBusy] = useState(false);
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warning/40 bg-warning/5 px-4 py-3 text-[13px]">
      <div className="flex items-center gap-2 text-text-secondary">
        <Trash2 className="h-4 w-4 flex-none text-warning" aria-hidden />
        <span>
          This visit is in trash. Auto-deletes in{' '}
          <strong className="text-text-primary">
            {daysLeft} {daysLeft === 1 ? 'day' : 'days'}
          </strong>
          .
        </span>
      </div>
      <div className="flex items-center gap-2">
        <RestoreButton visitId={visitId} busy={busy} setBusy={setBusy} />
        <DeletePermanentlyButton visitId={visitId} busy={busy} setBusy={setBusy} />
      </div>
    </div>
  );
}

function ArchivedBanner({ visitId }: { visitId: string }) {
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border-subtle bg-bg-surface-1/60 px-4 py-3 text-[13px]">
      <div className="flex items-center gap-2 text-text-secondary">
        <Archive className="h-4 w-4 flex-none text-text-muted" aria-hidden />
        <span>This visit is archived. Hidden from your dashboard.</span>
      </div>
      <UnarchiveButton visitId={visitId} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Buttons w/ built-in fetch wrappers
// ---------------------------------------------------------------------------

function RestoreButton({
  visitId,
  busy,
  setBusy,
}: {
  visitId: string;
  busy: boolean;
  setBusy: (b: boolean) => void;
}) {
  const router = useRouter();
  const [selfPending, setSelfPending] = useState(false);
  async function onClick() {
    setSelfPending(true);
    setBusy(true);
    try {
      const res = await fetch(`/api/visits/${visitId}/restore`, {
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
      setSelfPending(false);
      setBusy(false);
    }
  }
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      className="inline-flex items-center gap-1.5 rounded-full border border-border-default bg-bg-surface-1/60 px-3 py-1.5 text-[12px] font-medium text-text-secondary transition-colors hover:border-violet-500/60 hover:text-text-primary disabled:opacity-50"
    >
      {selfPending ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : (
        <RotateCcw className="h-3 w-3" aria-hidden />
      )}
      Restore
    </button>
  );
}

function UnarchiveButton({ visitId }: { visitId: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  async function onClick() {
    setPending(true);
    try {
      const res = await fetch(`/api/visits/${visitId}/unarchive`, {
        method: 'POST',
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        toast.error(body.error ?? 'Could not unarchive visit.');
        return;
      }
      toast.success('Visit unarchived');
      router.refresh();
    } catch {
      toast.error('Network error. Please try again.');
    } finally {
      setPending(false);
    }
  }
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={pending}
      className="inline-flex items-center gap-1.5 rounded-full border border-border-default bg-bg-surface-1/60 px-3 py-1.5 text-[12px] font-medium text-text-secondary transition-colors hover:border-violet-500/60 hover:text-text-primary disabled:opacity-50"
    >
      {pending ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : (
        <ArchiveRestore className="h-3 w-3" aria-hidden />
      )}
      Unarchive
    </button>
  );
}

// ---------------------------------------------------------------------------
// Archive (SIGNED visits)
// ---------------------------------------------------------------------------

function ArchiveButton({ visitId }: { visitId: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);

  async function onConfirm() {
    setPending(true);
    try {
      const res = await fetch(`/api/visits/${visitId}/archive`, {
        method: 'POST',
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        toast.error(body.error ?? 'Could not archive visit.');
        return;
      }
      toast.success('Visit archived');
      setOpen(false);
      router.push('/dashboard');
    } catch {
      toast.error('Network error. Please try again.');
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1.5 rounded-full border border-border-default bg-bg-surface-1/60 px-4 py-2 text-[13px] font-medium text-text-secondary transition-colors hover:bg-bg-surface-2/70 hover:border-border-emphasis focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
        >
          <Archive className="h-3.5 w-3.5" aria-hidden />
          Archive
        </button>
      </Dialog.Trigger>
      <ConfirmScaffold
        title="Archive this visit?"
        tone="neutral"
        description="Archived visits are hidden from your dashboard but kept permanently per HIPAA retention. You can unarchive later."
        onConfirm={onConfirm}
        confirmLabel="Archive"
        pending={pending}
      />
    </Dialog.Root>
  );
}

// ---------------------------------------------------------------------------
// Delete (non-SIGNED visits). Server routes to HARD vs SOFT based on
// (status === QUEUED && hasInput === false). Copy here matches what
// the server will actually do.
// ---------------------------------------------------------------------------

function DeleteButton({
  visitId,
  status,
  hasInput,
}: {
  visitId: string;
  status: TranscribeVisitStatus;
  hasInput: boolean;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);

  const willHardDelete =
    status === TranscribeVisitStatus.QUEUED && !hasInput;

  async function onConfirm() {
    setPending(true);
    try {
      const res = await fetch(`/api/visits/${visitId}/delete`, {
        method: 'POST',
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        toast.error(body.error ?? 'Could not delete visit.');
        return;
      }
      toast.success(willHardDelete ? 'Visit deleted' : 'Visit moved to trash');
      setOpen(false);
      router.push('/dashboard');
    } catch {
      toast.error('Network error. Please try again.');
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1.5 rounded-full border border-border-default bg-bg-surface-1/60 px-4 py-2 text-[13px] font-medium text-text-secondary transition-colors hover:border-danger/60 hover:bg-danger/10 hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger"
        >
          <Trash2 className="h-3.5 w-3.5" aria-hidden />
          Delete
        </button>
      </Dialog.Trigger>
      <ConfirmScaffold
        title={willHardDelete ? 'Delete this draft?' : 'Move to trash?'}
        tone="danger"
        description={
          willHardDelete
            ? 'This visit will be permanently deleted. It has no clinical data yet.'
            : `This visit will be moved to trash for ${SOFT_DELETE_WINDOW_DAYS} days before permanent deletion. You can restore it before then.`
        }
        onConfirm={onConfirm}
        confirmLabel={willHardDelete ? 'Delete permanently' : 'Move to trash'}
        pending={pending}
      />
    </Dialog.Root>
  );
}

// ---------------------------------------------------------------------------
// Delete permanently from trash — unconditional hard delete.
// ---------------------------------------------------------------------------

function DeletePermanentlyButton({
  visitId,
  busy,
  setBusy,
}: {
  visitId: string;
  busy: boolean;
  setBusy: (b: boolean) => void;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [selfPending, setSelfPending] = useState(false);

  async function onConfirm() {
    setSelfPending(true);
    setBusy(true);
    try {
      // ?permanent=1 flips the delete endpoint from the idempotent
      // "already trashed" short-circuit into a full hard-purge on
      // the already-soft-deleted row: tx-drop AiCall + visit, then
      // best-effort MinIO sweep. Same routine the 15-day cleanup
      // cron will use in Phase 5 Commit 9.
      const res = await fetch(`/api/visits/${visitId}/delete?permanent=1`, {
        method: 'POST',
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        toast.error(body.error ?? 'Could not delete permanently.');
        return;
      }
      toast.success('Visit permanently deleted');
      setOpen(false);
      router.push('/dashboard');
    } catch {
      toast.error('Network error. Please try again.');
    } finally {
      setSelfPending(false);
      setBusy(false);
    }
  }

  return (
    <Dialog.Root
      open={open}
      // T-M18.3 A27: swallow open-change events while the fetch is
      // in flight so Escape / outside-click can't close the dialog
      // and leave a zombie request racing against Restore.
      onOpenChange={selfPending ? undefined : setOpen}
    >
      <Dialog.Trigger asChild>
        <button
          type="button"
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-full border border-danger/60 bg-danger/10 px-3 py-1.5 text-[12px] font-medium text-danger transition-colors hover:bg-danger/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger disabled:opacity-50"
        >
          <Trash2 className="h-3 w-3" aria-hidden />
          Delete permanently
        </button>
      </Dialog.Trigger>
      <ConfirmScaffold
        title="Delete this visit permanently?"
        tone="danger"
        description="This cannot be undone. All audio, transcripts, and AI-generated outputs will be deleted."
        onConfirm={onConfirm}
        confirmLabel="Delete permanently"
        pending={selfPending}
      />
    </Dialog.Root>
  );
}

// ---------------------------------------------------------------------------
// Dialog scaffold — identical chrome across all four confirm flows.
// ---------------------------------------------------------------------------

function ConfirmScaffold({
  title,
  description,
  tone,
  onConfirm,
  confirmLabel,
  pending,
}: {
  title: string;
  description: string;
  tone: 'danger' | 'neutral';
  onConfirm: () => Promise<void>;
  confirmLabel: string;
  pending: boolean;
}) {
  const confirmClass =
    tone === 'danger'
      ? 'bg-danger text-white shadow-[0_0_0_1px_rgba(239,68,68,0.3)] hover:shadow-[0_0_0_1px_rgba(239,68,68,0.5)]'
      : 'bg-[linear-gradient(135deg,#7C3AED_0%,#A855F7_100%)] text-white shadow-[0_0_0_1px_rgba(167,139,250,0.3)] hover:shadow-[0_0_0_1px_rgba(167,139,250,0.5)]';
  return (
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in" />
      <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-border-default bg-bg-surface-1 p-6 shadow-2xl outline-none">
        <div className="mb-5 flex items-start gap-3">
          <div
            aria-hidden
            className={
              tone === 'danger'
                ? 'flex h-9 w-9 flex-none items-center justify-center rounded-full bg-danger/15 text-danger'
                : 'flex h-9 w-9 flex-none items-center justify-center rounded-full bg-violet-500/15 text-violet-300'
            }
          >
            {tone === 'danger' ? (
              <AlertTriangle className="h-4 w-4" />
            ) : (
              <Archive className="h-4 w-4" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <Dialog.Title className="text-[15px] font-semibold tracking-tight text-text-primary">
              {title}
            </Dialog.Title>
            <Dialog.Description className="mt-1 text-[13px] leading-relaxed text-text-tertiary">
              {description}
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
            className={`inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-[13px] font-medium transition-all disabled:cursor-not-allowed disabled:opacity-60 ${confirmClass}`}
          >
            {pending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </Dialog.Content>
    </Dialog.Portal>
  );
}
