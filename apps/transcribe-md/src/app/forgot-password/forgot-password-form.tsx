'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

import { SpecularButton } from '@/components/specular-button';

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
      <div className="space-y-4 text-center">
        <p className="text-[14px] text-text-secondary">
          If an account exists for <strong>{email}</strong>, we&apos;ve
          sent a reset link. It expires in 1 hour.
        </p>
        <p className="text-[13px] text-text-muted">
          Check your inbox — and your spam folder too.
        </p>
        <p className="pt-2 text-[13px] text-text-muted">
          <Link
            href="/login"
            className="text-violet-400 hover:text-violet-300 transition-colors"
          >
            ← Back to sign in
          </Link>
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      <div>
        <label
          htmlFor="email"
          className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary"
        >
          Email
        </label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="block w-full rounded-lg border border-border-default bg-bg-surface-1/60 px-3.5 py-2.5 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors duration-200 focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30"
        />
      </div>

      {error && (
        <p role="alert" className="text-[12px] text-danger">
          {error}
        </p>
      )}

      <SpecularButton
        type="submit"
        variant="primary"
        size="lg"
        className="w-full"
        disabled={pending || !email.trim()}
      >
        {pending ? 'Sending…' : 'Send reset link'}
        {!pending && <ArrowRight className="h-4 w-4" />}
      </SpecularButton>

      <p className="text-center text-[13px] text-text-muted">
        Remembered it?{' '}
        <Link
          href="/login"
          className="text-violet-400 hover:text-violet-300 transition-colors"
        >
          Back to sign in →
        </Link>
      </p>
    </form>
  );
}
