// ============================================================================
// Delete-account confirmation dialog (T-M16.2)
// ----------------------------------------------------------------------------
// Two safeguards on top of the "this is irreversible" copy:
//   1. Type the literal word DELETE to unlock the submit button.
//   2. Re-enter the current password — proves it's actually the account
//      owner and not someone who sat down at an unlocked laptop.
//
// On success: NextAuth signOut (clears the JWT cookie) with a callback
// URL pointing at the marketing site's `?deleted=1` banner. The sign-out
// call still works even though the User row is already gone — we're
// just blowing away the cookie + navigating away.
// ============================================================================

'use client';

import { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { AlertTriangle, Loader2, X } from 'lucide-react';
import { signOut } from 'next-auth/react';
import { toast } from 'sonner';

interface DeleteResponse {
  ok?: boolean;
  redirectTo?: string;
  error?: string;
  field?: string;
}

export function DeleteAccountDialog() {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<{ message: string; field?: string } | null>(
    null
  );

  const canSubmit =
    !pending && password.length > 0 && confirmation === 'DELETE';

  async function onConfirm() {
    setError(null);
    setPending(true);
    try {
      const res = await fetch('/api/settings/delete-account', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password, confirmation }),
      });
      const body = (await res.json().catch(() => ({}))) as DeleteResponse;
      if (!res.ok || !body.ok) {
        setError({
          message: body.error ?? 'Could not delete your account.',
          field: body.field,
        });
        return;
      }
      // Transaction committed + audit row written. Time to burn the
      // session cookie and navigate away.
      toast.success('Account deleted');
      const fallback =
        body.redirectTo ?? `${window.location.origin}/?deleted=1`;
      await signOut({ callbackUrl: fallback, redirect: true });
    } catch {
      setError({ message: 'Network error. Please try again.' });
    } finally {
      setPending(false);
    }
  }

  function reset() {
    setPassword('');
    setConfirmation('');
    setError(null);
    setPending(false);
  }

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-lg border border-red-500/50 bg-red-500/5 px-4 py-2 text-[13px] font-medium text-red-300 hover:bg-red-500/10 hover:border-red-500/70 transition-colors"
        >
          <AlertTriangle className="h-4 w-4" />
          Delete my account
        </button>
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(500px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border-default bg-bg-surface-1 p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-[16px] font-semibold text-text-primary flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-red-400" />
                Delete your account?
              </Dialog.Title>
              <Dialog.Description className="mt-1.5 text-[13px] leading-relaxed text-text-tertiary">
                This is <strong className="text-text-secondary">permanent</strong>.
                Every visit, transcript, SOAP note, and exported file will be
                erased. We keep a compliance record (email, deletion date,
                visit count) for 90 days, then that goes too.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close"
                className="text-text-muted hover:text-text-primary transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </Dialog.Close>
          </div>

          <div className="mt-6 space-y-4">
            <div>
              <label
                htmlFor="delete-password"
                className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary"
              >
                Current password
              </label>
              <input
                id="delete-password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={pending}
                className="block w-full rounded-lg border border-border-default bg-bg-surface-1/60 px-3.5 py-2.5 text-[14px] text-text-primary outline-none transition-colors focus:border-red-500/70 focus:ring-2 focus:ring-red-500/30"
              />
              {error?.field === 'password' && (
                <p role="alert" className="mt-1.5 text-[12px] text-danger">
                  {error.message}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="delete-confirmation"
                className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary"
              >
                Type <strong className="text-text-primary">DELETE</strong> to confirm
              </label>
              <input
                id="delete-confirmation"
                name="confirmation"
                type="text"
                autoComplete="off"
                autoCorrect="off"
                autoCapitalize="off"
                spellCheck={false}
                required
                value={confirmation}
                onChange={(e) => setConfirmation(e.target.value)}
                disabled={pending}
                className="block w-full rounded-lg border border-border-default bg-bg-surface-1/60 px-3.5 py-2.5 text-[14px] text-text-primary outline-none transition-colors focus:border-red-500/70 focus:ring-2 focus:ring-red-500/30"
              />
              {error?.field === 'confirmation' && (
                <p role="alert" className="mt-1.5 text-[12px] text-danger">
                  {error.message}
                </p>
              )}
            </div>

            {error && !error.field && (
              <p role="alert" className="text-[12px] text-danger">
                {error.message}
              </p>
            )}
          </div>

          <div className="mt-6 flex items-center justify-end gap-2">
            <Dialog.Close asChild>
              <button
                type="button"
                disabled={pending}
                className="rounded-lg border border-border-default bg-bg-surface-1/60 px-4 py-2 text-[13px] font-medium text-text-secondary hover:bg-bg-surface-1 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
            </Dialog.Close>
            <button
              type="button"
              disabled={!canSubmit}
              onClick={onConfirm}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-red-500 px-4 py-2 text-[13px] font-medium text-white shadow-[0_0_0_1px_rgba(239,68,68,0.4),0_8px_24px_-8px_rgba(239,68,68,0.5)] transition-all hover:bg-red-600 disabled:opacity-50 disabled:pointer-events-none"
            >
              {pending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Deleting…
                </>
              ) : (
                'Delete account'
              )}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
