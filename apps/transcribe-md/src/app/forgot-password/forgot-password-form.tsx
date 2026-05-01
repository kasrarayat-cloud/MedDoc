'use client';

import { useState } from 'react';
import Link from 'next/link';

import { Ic } from '@/components/ui/icon';
import {
  AuthFieldError,
  AuthFieldLabel,
} from '@/components/ui/auth-shell';

// Phase 5 — Linear V1 Faithful forgot-password form. Server-side
// /api/auth/forgot-password contract is unchanged: anti-enumeration,
// 200 regardless of address existence, 429 on rate limit.

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

export function ForgotPasswordForm() {
  const [email, setEmail] = useState('');
  const [pending, setPending] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const res = await fetch('/api/auth/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim() }),
      });
      if (res.status === 429) {
        setError('Too many requests. Try again in a few minutes.');
        return;
      }
      if (!res.ok) {
        setError('Something went wrong. Please try again.');
        return;
      }
      // Anti-enumeration: endpoint returns 200 whether or not the
      // address exists. The UI mirrors that.
      setSubmitted(true);
    } catch {
      setError('Network error. Please try again.');
    } finally {
      setPending(false);
    }
  }

  if (submitted) {
    return (
      <div
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
          If an account exists for{' '}
          <strong style={{ color: 'var(--color-linear-text)' }}>{email}</strong>,
          we&apos;ve sent a reset link. It expires in 1 hour.
        </p>
        <p
          style={{
            margin: 0,
            fontFamily: 'var(--font-sans)',
            fontSize: 12,
            color: 'var(--color-linear-text-3)',
          }}
        >
          Check your inbox — and your spam folder too.
        </p>
        <Link
          href="/login"
          style={{ ...linkStyle, marginTop: 6, fontSize: 12.5 }}
        >
          ← Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <div style={{ marginTop: 18 }}>
        <AuthFieldLabel htmlFor="email">Email</AuthFieldLabel>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={{ ...inputStyle, marginTop: 6 }}
        />
      </div>

      <AuthFieldError message={error ?? undefined} />

      <button
        type="submit"
        disabled={pending || !email.trim()}
        className="qm-lin-btn-primary"
        style={{
          width: '100%',
          marginTop: 22,
          height: 36,
          fontSize: 13,
          opacity: pending || !email.trim() ? 0.6 : 1,
          cursor: pending || !email.trim() ? 'not-allowed' : 'pointer',
        }}
      >
        {pending ? 'Sending…' : 'Send reset link'}
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
        Remembered it?{' '}
        <Link href="/login" style={linkStyle}>
          Back to sign in →
        </Link>
      </div>
    </form>
  );
}
