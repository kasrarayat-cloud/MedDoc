'use client';

import { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Loader2, Mail, X } from 'lucide-react';
import { toast } from 'sonner';

// Phase 5 — Linear V1 Faithful change-email dialog. Server-side
// /api/settings/change-email contract is unchanged.

interface ApiError {
  error?: string;
  field?: string;
}

interface Props {
  currentEmail: string;
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
          className="qm-lin-btn"
          style={{
            height: 26,
            padding: '0 10px',
            fontSize: 11.5,
            gap: 6,
          }}
        >
          <Mail className="h-3 w-3" aria-hidden />
          Change
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
            width: 'min(480px, calc(100vw - 32px))',
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
                  fontFamily: 'var(--font-sans)',
                  fontSize: 16,
                  fontWeight: 500,
                  color: 'var(--color-linear-text)',
                  letterSpacing: '-0.01em',
                }}
              >
                Change email
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
                We&apos;ll send a confirmation link to the new address.
                Your current email stays active until you click that link.
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

          {done ? (
            <div
              style={{
                marginTop: 22,
                display: 'flex',
                flexDirection: 'column',
                gap: 16,
              }}
            >
              <p
                style={{
                  margin: 0,
                  fontFamily: 'var(--font-sans)',
                  fontSize: 13,
                  color: 'var(--color-linear-text-2)',
                }}
              >
                Confirmation link sent to{' '}
                <strong style={{ color: 'var(--color-linear-text)' }}>
                  {newEmail}
                </strong>
                . Open the link from that inbox — once you do, future sign-ins
                use the new address.
              </p>
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <Dialog.Close asChild>
                  <button type="button" className="qm-lin-btn">
                    Close
                  </button>
                </Dialog.Close>
              </div>
            </div>
          ) : (
            <form
              onSubmit={onSubmit}
              style={{
                marginTop: 22,
                display: 'flex',
                flexDirection: 'column',
                gap: 14,
              }}
              noValidate
            >
              <div>
                <label style={labelStyle}>Current email</label>
                <div
                  style={{
                    padding: '8px 12px',
                    border: '1px solid var(--color-linear-hairline)',
                    background: 'var(--color-linear-surface-2)',
                    borderRadius: 6,
                    fontFamily: 'var(--font-sans)',
                    fontSize: 12.5,
                    color: 'var(--color-linear-text-3)',
                    wordBreak: 'break-all',
                  }}
                >
                  {currentEmail}
                </div>
              </div>

              <div>
                <label htmlFor="newEmail" style={labelStyle}>
                  New email
                </label>
                <input
                  id="newEmail"
                  type="email"
                  autoComplete="email"
                  required
                  maxLength={254}
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  disabled={pending}
                  style={inputStyle}
                />
                {fieldError === 'newEmail' && (
                  <p role="alert" style={errorStyle}>
                    {error?.error}
                  </p>
                )}
              </div>

              <div>
                <label htmlFor="password-for-change" style={labelStyle}>
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
                  style={inputStyle}
                />
                {fieldError === 'password' && (
                  <p role="alert" style={errorStyle}>
                    {error?.error}
                  </p>
                )}
              </div>

              {formError && (
                <p role="alert" style={errorStyle}>
                  {formError}
                </p>
              )}

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'flex-end',
                  gap: 8,
                  paddingTop: 4,
                }}
              >
                <Dialog.Close asChild>
                  <button
                    type="button"
                    disabled={pending}
                    className="qm-lin-btn"
                  >
                    Cancel
                  </button>
                </Dialog.Close>
                <button
                  type="submit"
                  disabled={pending || !newEmail.trim() || !password}
                  className="qm-lin-btn-primary"
                  style={{
                    opacity: pending || !newEmail.trim() || !password ? 0.55 : 1,
                  }}
                >
                  {pending && <Loader2 className="h-3 w-3 animate-spin" />}
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
