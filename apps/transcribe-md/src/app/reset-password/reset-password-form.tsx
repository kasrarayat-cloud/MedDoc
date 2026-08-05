'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import { Ic } from '@/components/ui/icon';
import {
  AuthFieldError,
  AuthFieldLabel,
} from '@/components/ui/auth-shell';

interface Props {
  token: string;
}

interface ApiError {
  error?: string;
  field?: string;
}

// Phase 5 — Linear V1 Faithful reset-password form.
// /api/auth/reset-password contract is unchanged.

const inputStyle: React.CSSProperties = {
  width: '100%',
  height: 36,
  padding: '0 12px',
  background: 'var(--color-linear-surface-2)',
  border: '1px solid var(--color-linear-border)',
  borderRadius: 6,
  color: 'var(--color-linear-text)',
  fontFamily: 'var(--font-sans)',
  fontSize: 13.5,
  outline: 'none',
  transition: 'border-color 100ms ease, background-color 100ms ease',
};

const linkStyle: React.CSSProperties = {
  color: 'var(--color-linear-sage-bright)',
  fontFamily: 'var(--font-sans)',
  fontWeight: 500,
  textDecoration: 'none',
};

export function ResetPasswordForm({ token }: Props) {
  const router = useRouter();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [done, setDone] = useState(false);

  if (!token) {
    return (
      <div
        className="qm-rounds-panel"
        style={{
          marginTop: 22,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 12,
          textAlign: 'center',
        }}
      >
        <p
          style={{
            margin: 0,
            fontFamily: 'var(--font-sans)',
            fontSize: 13.5,
            color: 'var(--color-linear-text-2)',
            lineHeight: 1.55,
          }}
        >
          This reset link is missing its token. Open the link from the email we
          sent — or request a fresh one.
        </p>
        <Link
          href="/forgot-password"
          style={{ ...linkStyle, fontSize: 12.5 }}
        >
          Send a new reset link →
        </Link>
      </div>
    );
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const res = await fetch('/api/auth/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password, confirmPassword }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as ApiError;
        setError({
          error: body.error ?? 'Something went wrong. Please try again.',
          field: body.field,
        });
        return;
      }
      setDone(true);
      toast.success('Password updated', {
        description: 'Sign in with your new password.',
      });
      setTimeout(() => router.push('/login'), 1500);
    } catch {
      setError({ error: 'Network error. Please try again.' });
    } finally {
      setPending(false);
    }
  }

  // ⚠️ TRANSIENT, AND NOT COVERED BY THE ROUNDS PACK — stated plainly rather
  // than implied. `onSubmit` sets `done` and schedules `router.push('/login')`
  // 1.5s later, so anything photographing this state is racing a timer.
  // `rounds-c1` stops at the reset FORM and never submits it, so this panel is
  // the SECOND state the pack does not cover (the first is login's
  // needs-verification banner). It matters a little more than it looks: the
  // panel just gained `.qm-rounds-panel`, which changes its ground from the
  // card to surface-2 — exactly the move that demoted a paragraph from 4.91:1
  // to 4.18:1 on /forgot-password. The panel class re-bridges the faint tiers
  // for that reason, and `gate-c1d-auth` asserts the pairing by arithmetic, so
  // this text is covered by a unit even though no walk photographs it.
  // `17-password-reset.spec.ts` (the required chromium gate) does drive it,
  // now always in the Rounds skin.
  if (done) {
    return (
      <p
        className="qm-rounds-panel"
        style={{
          marginTop: 22,
          textAlign: 'center',
          fontFamily: 'var(--font-sans)',
          fontSize: 13.5,
          color: 'var(--color-linear-text-2)',
          lineHeight: 1.6,
        }}
      >
        Password updated. Redirecting to sign in…
      </p>
    );
  }

  const fieldError = error?.field;
  const formError = !fieldError ? error?.error : null;

  return (
    <form onSubmit={onSubmit} noValidate>
      <div style={{ marginTop: 18 }}>
        <AuthFieldLabel htmlFor="password">New password</AuthFieldLabel>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={10}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="qm-rounds-input"
          style={{ ...inputStyle, marginTop: 6 }}
        />
        <p
          style={{
            marginTop: 6,
            fontFamily: 'var(--font-sans)',
            fontSize: 11.5,
            color: 'var(--color-linear-text-3)',
            lineHeight: 1.4,
          }}
        >
          At least 10 characters, with upper + lowercase letters and a digit.
        </p>
        {fieldError === 'password' && (
          <AuthFieldError message={error?.error} />
        )}
      </div>

      <div style={{ marginTop: 14 }}>
        <AuthFieldLabel htmlFor="confirmPassword">Confirm password</AuthFieldLabel>
        <input
          id="confirmPassword"
          name="confirmPassword"
          type="password"
          autoComplete="new-password"
          required
          minLength={10}
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          className="qm-rounds-input"
          style={{ ...inputStyle, marginTop: 6 }}
        />
        {fieldError === 'confirmPassword' && (
          <AuthFieldError message={error?.error} />
        )}
      </div>

      <AuthFieldError message={formError ?? undefined} />

      <button
        type="submit"
        disabled={pending || !password || !confirmPassword}
        className="qm-lin-btn-primary qm-rounds-btn-primary"
        style={{
          width: '100%',
          marginTop: 22,
          height: 36,
          fontSize: 13,
          opacity: pending || !password || !confirmPassword ? 0.6 : 1,
          cursor:
            pending || !password || !confirmPassword ? 'not-allowed' : 'pointer',
        }}
      >
        {pending ? 'Saving…' : 'Set new password'}
        {!pending && <Ic.arrowRight width={14} height={14} />}
      </button>

      <div
        style={{
          textAlign: 'center',
          color: 'var(--color-linear-text-3)',
          fontFamily: 'var(--font-sans)',
          fontSize: 12.5,
          marginTop: 18,
        }}
      >
        <Link href="/login" className="qm-rounds-link" style={linkStyle}>
          Back to sign in →
        </Link>
      </div>
    </form>
  );
}
