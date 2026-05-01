// ============================================================================
// Phase 5 — Linear V1 Faithful delete-account dialog (T-M16.2)
// ----------------------------------------------------------------------------
// Two safeguards on top of the "this is irreversible" copy:
//   1. Type the literal word DELETE to unlock the submit button.
//   2. Re-enter the current password — proves it's actually the account
//      owner and not someone who sat down at an unlocked laptop.
//
// On success: NextAuth signOut (clears the JWT cookie) with a callback
// URL pointing at the marketing site's `?deleted=1` banner. Server-side
// /api/settings/delete-account contract is unchanged.
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

const inputStyle: React.CSSProperties = {
  width: '100%',
  height: 32,
  padding: '0 10px',
  background: 'var(--color-linear-surface-2)',
  border: '1px solid var(--color-linear-border)',
  borderRadius: 6,
  color: 'var(--color-linear-text)',
  fontFamily: 'var(--font-sans)',
  fontSize: 13,
  outline: 'none',
};

const labelStyle: React.CSSProperties = {
  display: 'block',
  marginBottom: 6,
  fontFamily: 'var(--font-mono)',
  fontSize: 10.5,
  color: 'var(--color-linear-text-3)',
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  fontWeight: 500,
};

const errorStyle: React.CSSProperties = {
  marginTop: 6,
  fontFamily: 'var(--font-sans)',
  fontSize: 12,
  color: 'var(--color-linear-coral)',
};

export function DeleteAccountDialog() {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<{ message: string; field?: string } | null>(
    null,
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
          className="qm-lin-btn"
          style={{
            borderColor: 'rgba(212, 87, 74, 0.40)',
            color: 'var(--color-linear-coral)',
            background: 'rgba(212, 87, 74, 0.05)',
          }}
        >
          <AlertTriangle className="h-3.5 w-3.5" />
          Delete my account
        </button>
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Overlay
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 50,
            background: 'rgba(0, 0, 0, 0.55)',
            backdropFilter: 'blur(2px)',
          }}
          className="data-[state=open]:animate-in data-[state=open]:fade-in-0"
        />
        <Dialog.Content
          aria-describedby={undefined}
          style={{
            position: 'fixed',
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 50,
            width: 'min(500px, calc(100vw - 32px))',
            background: 'var(--color-linear-surface-1)',
            border: '1px solid var(--color-linear-border-strong)',
            borderRadius: 10,
            padding: 24,
            boxShadow:
              '0 30px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.03)',
            color: 'var(--color-linear-text)',
          }}
          className="data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <Dialog.Title
                style={{
                  margin: 0,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  fontFamily: 'var(--font-sans)',
                  fontSize: 16,
                  fontWeight: 500,
                  color: 'var(--color-linear-text)',
                  letterSpacing: '-0.01em',
                }}
              >
                <AlertTriangle
                  className="h-4 w-4"
                  style={{ color: 'var(--color-linear-coral)' }}
                />
                Delete your account?
              </Dialog.Title>
              <Dialog.Description
                style={{
                  margin: '6px 0 0',
                  fontFamily: 'var(--font-sans)',
                  fontSize: 12.5,
                  color: 'var(--color-linear-text-2)',
                  lineHeight: 1.5,
                }}
              >
                This is{' '}
                <strong style={{ color: 'var(--color-linear-text)' }}>
                  permanent
                </strong>
                . Every visit, transcript, SOAP note, and exported file will be
                erased. We keep a compliance record (email, deletion date,
                visit count) for 90 days, then that goes too.
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--color-linear-text-3)',
                  cursor: 'pointer',
                  padding: 4,
                }}
              >
                <X className="h-4 w-4" />
              </button>
            </Dialog.Close>
          </div>

          <div
            style={{
              marginTop: 22,
              display: 'flex',
              flexDirection: 'column',
              gap: 14,
            }}
          >
            <div>
              <label htmlFor="delete-password" style={labelStyle}>
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
                style={inputStyle}
              />
              {error?.field === 'password' && (
                <p role="alert" style={errorStyle}>
                  {error.message}
                </p>
              )}
            </div>

            <div>
              <label htmlFor="delete-confirmation" style={labelStyle}>
                Type{' '}
                <strong style={{ color: 'var(--color-linear-text)' }}>
                  DELETE
                </strong>{' '}
                to confirm
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
                style={inputStyle}
              />
              {error?.field === 'confirmation' && (
                <p role="alert" style={errorStyle}>
                  {error.message}
                </p>
              )}
            </div>

            {error && !error.field && (
              <p role="alert" style={errorStyle}>
                {error.message}
              </p>
            )}
          </div>

          <div
            style={{
              marginTop: 22,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: 8,
            }}
          >
            <Dialog.Close asChild>
              <button type="button" disabled={pending} className="qm-lin-btn">
                Cancel
              </button>
            </Dialog.Close>
            <button
              type="button"
              disabled={!canSubmit}
              onClick={onConfirm}
              className="qm-lin-btn-primary"
              style={{
                background: 'var(--color-linear-danger)',
                boxShadow: '0 0 0 1px rgba(212, 87, 74, 0.45)',
                opacity: canSubmit ? 1 : 0.5,
                cursor: canSubmit ? 'pointer' : 'not-allowed',
              }}
            >
              {pending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
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
