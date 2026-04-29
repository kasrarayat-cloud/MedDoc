'use client';

import { useState } from 'react';
import Link from 'next/link';

import { Ic } from '@/components/ui/icon';
import {
  AuthFieldError,
  AuthFieldLabel,
} from '@/components/ui/auth-shell';

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
          className="qm-cl-serif"
          style={{
            margin: 0,
            fontSize: 15,
            color: 'var(--ink-2)',
            lineHeight: 1.6,
            fontStyle: 'italic',
          }}
        >
          If an account exists for{' '}
          <strong style={{ color: 'var(--ink)', fontStyle: 'normal' }}>{email}</strong>,
          we&apos;ve sent a reset link. It expires in 1 hour.
        </p>
        <p
          style={{
            margin: 0,
            fontSize: 12.5,
            color: 'var(--ink-3)',
            fontFamily: 'var(--sans)',
          }}
        >
          Check your inbox — and your spam folder too.
        </p>
        <Link
          href="/login"
          style={{
            marginTop: 6,
            fontSize: 12.5,
            color: 'var(--sage-deep)',
            fontFamily: 'var(--sans)',
            fontWeight: 500,
          }}
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
          className="qm-cl-input"
          style={{ marginTop: 6 }}
        />
      </div>

      <AuthFieldError message={error ?? undefined} />

      <button
        type="submit"
        disabled={pending || !email.trim()}
        className="qm-cl-btn qm-cl-btn-primary qm-cl-btn-lg"
        style={{
          width: '100%',
          justifyContent: 'center',
          marginTop: 22,
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
          color: 'var(--ink-3)',
          fontSize: 12.5,
          marginTop: 18,
          fontFamily: 'var(--sans)',
        }}
      >
        Remembered it?{' '}
        <Link href="/login" style={{ color: 'var(--sage-deep)', fontWeight: 500 }}>
          Back to sign in →
        </Link>
      </div>
    </form>
  );
}
