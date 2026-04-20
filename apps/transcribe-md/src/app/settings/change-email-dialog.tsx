'use client';

import { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Loader2, Mail, X } from 'lucide-react';
import { toast } from 'sonner';

interface ApiError {
  error?: string;
  field?: string;
}

interface Props {
  currentEmail: string;
}

export function ChangeEmailDialog({ currentEmail }: Props) {
  const [open, setOpen] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [done, setDone] = useState(false);

  function reset() {
    setNewEmail('');
    setPassword('');
    setError(null);
    setPending(false);
    setDone(false);
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const res = await fetch('/api/settings/change-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ newEmail: newEmail.trim(), password }),
      });
      const body = (await res.json().catch(() => ({}))) as ApiError & {
        ok?: boolean;
      };
      if (!res.ok || !body.ok) {
        setError({
          error: body.error ?? 'Could not start email change.',
          field: body.field,
        });
        return;
      }
      setDone(true);
      toast.success('Confirmation email sent', {
        description: 'Click the link in your new inbox to complete the change.',
      });
    } catch {
      setError({ error: 'Network error. Please try again.' });
    } finally {
      setPending(false);
    }
  }

  const fieldError = error?.field;
  const formError = error && !fieldError ? error.error : null;

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
          className="inline-flex items-center gap-2 rounded-lg border border-border-default bg-bg-surface-1/60 px-3 py-1.5 text-[12px] font-medium text-text-secondary hover:bg-bg-surface-2/70 hover:border-border-emphasis transition-colors"
        >
          <Mail className="h-3.5 w-3.5" />
          Change
        </button>
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(480px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border-default bg-bg-surface-1 p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-[16px] font-semibold text-text-primary">
                Change email
              </Dialog.Title>
              <Dialog.Description className="mt-1.5 text-[13px] leading-relaxed text-text-tertiary">
                We&apos;ll send a confirmation link to the new address.
                Your current email stays active until you click that link.
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

          {done ? (
            <div className="mt-6 space-y-4">
              <p className="text-[14px] text-text-secondary">
                Confirmation link sent to{' '}
                <strong className="text-text-primary">{newEmail}</strong>.
                Open the link from that inbox — once you do, future
                sign-ins use the new address.
              </p>
              <div className="flex justify-end">
                <Dialog.Close asChild>
                  <button
                    type="button"
                    className="rounded-lg border border-border-default bg-bg-surface-1/60 px-4 py-2 text-[13px] font-medium text-text-secondary hover:bg-bg-surface-1 transition-colors"
                  >
                    Close
                  </button>
                </Dialog.Close>
              </div>
            </div>
          ) : (
            <form onSubmit={onSubmit} className="mt-6 space-y-4" noValidate>
              <div>
                <label className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary">
                  Current email
                </label>
                <div className="rounded-lg border border-border-subtle bg-bg-surface-1/40 px-3.5 py-2.5 text-[13px] text-text-muted break-all">
                  {currentEmail}
                </div>
              </div>

              <div>
                <label
                  htmlFor="newEmail"
                  className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary"
                >
                  New email
                </label>
                <input
                  id="newEmail"
                  type="email"
                  autoComplete="email"
                  required
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  disabled={pending}
                  className={inputClass}
                />
                {fieldError === 'newEmail' && (
                  <p role="alert" className="mt-1.5 text-[12px] text-danger">
                    {error?.error}
                  </p>
                )}
              </div>

              <div>
                <label
                  htmlFor="password-for-change"
                  className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary"
                >
                  Confirm with password
                </label>
                <input
                  id="password-for-change"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={pending}
                  className={inputClass}
                />
                {fieldError === 'password' && (
                  <p role="alert" className="mt-1.5 text-[12px] text-danger">
                    {error?.error}
                  </p>
                )}
              </div>

              {formError && (
                <p role="alert" className="text-[12px] text-danger">
                  {formError}
                </p>
              )}

              <div className="flex items-center justify-end gap-2 pt-2">
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
                  type="submit"
                  disabled={pending || !newEmail.trim() || !password}
                  className="inline-flex items-center gap-2 rounded-lg bg-violet-500 px-4 py-2 text-[13px] font-medium text-white hover:bg-violet-600 transition-colors disabled:opacity-50 disabled:pointer-events-none"
                >
                  {pending && <Loader2 className="h-4 w-4 animate-spin" />}
                  {pending ? 'Sending…' : 'Send confirmation'}
                </button>
              </div>
            </form>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

const inputClass =
  'block w-full rounded-lg border border-border-default bg-bg-surface-1/60 px-3.5 py-2.5 text-[14px] text-text-primary outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30';
