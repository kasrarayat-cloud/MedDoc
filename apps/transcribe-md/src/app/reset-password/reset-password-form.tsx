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
        style={{
          marginTop: 20,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 12,
          textAlign: 'center',
        }}
      >
        <p style={{ margin: 0, fontSize: 13.5, color: 'var(--fg-2)' }}>
          This reset link is missing its token. Open the link from the email we
          sent — or request a fresh one.
        </p>
        <Link
          href="/forgot-password"
          style={{ fontSize: 12.5, color: 'var(--accent-bright)' }}
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

  if (done) {
    return (
      <p
        style={{
          marginTop: 20,
          textAlign: 'center',
          fontSize: 13.5,
          color: 'var(--fg-2)',
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
      <div style={{ marginTop: 14 }}>
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
          className="qm-input"
          style={{ marginTop: 6 }}
        />
        <p
          style={{
            marginTop: 6,
            fontSize: 11,
            color: 'var(--fg-4)',
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
          className="qm-input"
          style={{ marginTop: 6 }}
        />
        {fieldError === 'confirmPassword' && (
          <AuthFieldError message={error?.error} />
        )}
      </div>

      <AuthFieldError message={formError ?? undefined} />

      <button
        type="submit"
        disabled={pending || !password || !confirmPassword}
        className="qm-btn qm-btn-primary"
        style={{
          width: '100%',
          justifyContent: 'center',
          padding: 12,
          marginTop: 22,
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
          color: 'var(--fg-3)',
          fontSize: 12.5,
          marginTop: 18,
        }}
      >
        <Link href="/login" style={{ color: 'var(--accent-bright)' }}>
          Back to sign in →
        </Link>
      </div>
    </form>
  );
}
