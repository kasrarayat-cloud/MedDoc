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
//
// Phase 5 — Linear V1 Faithful. Banners use surface-1 chrome with
// hairline borders; trash banner uses warning-tinted accents and
// trash button uses danger-tinted hover. Confirm dialogs render in
// `.qm-lin-spotlight` panels. The `theme` prop is preserved as a
// no-op on the public API.
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
import { cn } from '@/lib/cn';
import { recoveryHref } from '@/lib/recovery-href';

type LifecycleTheme = 'legacy' | 'clinician';

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
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: LifecycleTheme;
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
    return <TrashedBanner visitId={visitId} deletedAtIso={deletedAt} />;
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
    <div
      className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-lg px-4 py-3 text-[13px]"
      style={{
        background: 'rgba(212,164,55,0.07)',
        border: '1px solid rgba(212,164,55,0.32)',
        color: 'var(--color-linear-text-2)',
      }}
    >
      <div className="flex items-center gap-2">
        <Trash2
          className="h-4 w-4 flex-none"
          style={{ color: 'var(--color-linear-warning)' }}
          aria-hidden
        />
        <span>
          This visit is in trash. Auto-deletes in{' '}
          <strong style={{ color: 'var(--color-linear-text)' }}>
            {daysLeft} {daysLeft === 1 ? 'day' : 'days'}
          </strong>
          .
        </span>
      </div>
      <div className="flex items-center gap-2">
        <RestoreButton visitId={visitId} busy={busy} setBusy={setBusy} />
        <DeletePermanentlyButton
          visitId={visitId}
          busy={busy}
          setBusy={setBusy}
        />
      </div>
    </div>
  );
}

function ArchivedBanner({ visitId }: { visitId: string }) {
  return (
    <div
      className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-lg px-4 py-3 text-[13px]"
      style={{
        background: 'var(--color-linear-surface-1)',
        border: '1px solid var(--color-linear-border)',
        color: 'var(--color-linear-text-2)',
      }}
    >
      <div className="flex items-center gap-2">
        <Archive
          className="h-4 w-4 flex-none"
          style={{ color: 'var(--color-linear-text-3)' }}
          aria-hidden
        />
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
      className="qm-lin-btn"
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
      className="qm-lin-btn"
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
      router.push(recoveryHref());
    } catch {
      toast.error('Network error. Please try again.');
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button type="button" className="qm-lin-btn">
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
      router.push(recoveryHref());
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
          className="qm-lin-btn"
          style={{
            // Coral hover wash on the hairline-bordered ghost — same
            // semantic as before, restyled for the dark canvas.
          }}
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
      router.push(recoveryHref());
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
          className="qm-lin-btn"
          style={{
            background: 'rgba(212,87,74,0.10)',
            borderColor: 'rgba(212,87,74,0.45)',
            color: 'var(--color-linear-danger)',
          }}
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
  return (
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
          'fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 outline-none'
        )}
        style={{ padding: 0 }}
      >
        <div className="flex items-start gap-3" style={{ padding: '20px 24px 4px' }}>
          <div
            aria-hidden
            className="flex h-9 w-9 flex-none items-center justify-center rounded-md"
            style={{
              background:
                tone === 'danger'
                  ? 'rgba(212,87,74,0.10)'
                  : 'var(--color-linear-sage-tint)',
              color:
                tone === 'danger'
                  ? 'var(--color-linear-danger)'
                  : 'var(--color-linear-sage-bright)',
              border:
                tone === 'danger'
                  ? '1px solid rgba(212,87,74,0.32)'
                  : '1px solid rgba(122,166,140,0.32)',
            }}
          >
            {tone === 'danger' ? (
              <AlertTriangle className="h-4 w-4" />
            ) : (
              <Archive className="h-4 w-4" />
            )}
          </div>
          <div className="min-w-0 flex-1">
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
              {title}
            </Dialog.Title>
            <Dialog.Description
              style={{
                marginTop: 6,
                marginBottom: 0,
                fontSize: 13,
                lineHeight: 1.55,
                color: 'var(--color-linear-text-2)',
              }}
            >
              {description}
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
        <div
          className="flex items-center justify-end gap-2"
          style={{
            borderTop: '1px solid var(--color-linear-hairline)',
            background: 'var(--color-linear-surface-2)',
            padding: '12px 24px',
            marginTop: 16,
          }}
        >
          <Dialog.Close asChild>
            <button type="button" className="qm-lin-btn">
              Cancel
            </button>
          </Dialog.Close>
          <button
            type="button"
            onClick={onConfirm}
            disabled={pending}
            className={cn(
              tone === 'danger' ? 'qm-lin-btn' : 'qm-lin-btn-primary'
            )}
            style={
              tone === 'danger'
                ? {
                    background: 'rgba(212,87,74,0.16)',
                    borderColor: 'rgba(212,87,74,0.45)',
                    color: 'var(--color-linear-danger)',
                  }
                : undefined
            }
          >
            {pending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </Dialog.Content>
    </Dialog.Portal>
  );
}
