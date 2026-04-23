'use client';

import { useActionState, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { toast } from 'sonner';

import { Ic } from '@/components/ui/icon';
import {
  AuthFieldError,
  AuthFieldLabel,
} from '@/components/ui/auth-shell';
import { loginAction, type AuthActionState } from '@/actions/auth';

const initialState: AuthActionState = null;

export function LoginForm() {
  const [state, formAction, pending] = useActionState(loginAction, initialState);
  const router = useRouter();
  const [resendPending, setResendPending] = useState(false);

  useEffect(() => {
    if (state && state.ok) {
      router.push(state.redirect);
      router.refresh();
    } else if (
      state &&
      !state.ok &&
      state.errors._form &&
      !state.needsVerificationFor
    ) {
      toast.error('Sign-in failed', { description: state.errors._form });
    }
  }, [state, router]);

  const errors = state && !state.ok ? state.errors : {};
  const values = state && !state.ok ? state.values ?? {} : {};
  const needsVerificationFor =
    state && !state.ok ? state.needsVerificationFor : undefined;

  async function resendVerification() {
    if (!needsVerificationFor) return;
    setResendPending(true);
    try {
      const res = await fetch('/api/auth/resend-verification', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: needsVerificationFor }),
      });
      if (res.status === 429) {
        toast.error('Too many requests', {
          description: 'Wait a few minutes before trying again.',
        });
      } else if (res.ok) {
        toast.success('Verification email sent', {
          description: 'Check your inbox.',
        });
      } else {
        toast.error('Could not resend', { description: 'Please try again later.' });
      }
    } catch {
      toast.error('Network error', { description: 'Please try again.' });
    } finally {
      setResendPending(false);
    }
  }

  return (
    <form action={formAction}>
      <div style={{ marginTop: 14 }}>
        <AuthFieldLabel htmlFor="email">Email</AuthFieldLabel>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          defaultValue={values.email ?? ''}
          required
          className="qm-input"
          style={{ marginTop: 6 }}
        />
        <AuthFieldError message={errors.email} />
      </div>

      <div style={{ marginTop: 14 }}>
        <AuthFieldLabel
          htmlFor="password"
          hint={
            <Link
              href="/forgot-password"
              style={{ fontSize: 11.5, color: 'var(--accent-bright)' }}
            >
              Forgot?
            </Link>
          }
        >
          Password
        </AuthFieldLabel>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          className="qm-input"
          style={{ marginTop: 6 }}
        />
        <AuthFieldError message={errors.password} />
      </div>

      <AuthFieldError message={errors._form} />

      {needsVerificationFor && (
        <div
          style={{
            marginTop: 14,
            padding: 12,
            borderRadius: 10,
            border: '1px solid rgba(251, 191, 36, 0.35)',
            background: 'rgba(251, 191, 36, 0.06)',
            color: 'var(--amber)',
            fontSize: 12,
            lineHeight: 1.5,
          }}
        >
          <p style={{ margin: 0 }}>
            We sent a verification link to{' '}
            <strong style={{ color: '#FDE68A' }}>{needsVerificationFor}</strong>.
            Click it, then sign in again.
          </p>
          <button
            type="button"
            onClick={resendVerification}
            disabled={resendPending}
            style={{
              marginTop: 8,
              background: 'none',
              border: 'none',
              padding: 0,
              color: '#FDE68A',
              fontSize: 12,
              fontWeight: 500,
              textDecoration: 'underline',
              textUnderlineOffset: 2,
              cursor: resendPending ? 'default' : 'pointer',
              opacity: resendPending ? 0.6 : 1,
            }}
          >
            {resendPending ? 'Sending…' : 'Resend the verification email'}
          </button>
        </div>
      )}

      <button
        type="submit"
        disabled={pending}
        className="qm-btn qm-btn-primary"
        style={{
          width: '100%',
          justifyContent: 'center',
          padding: 12,
          marginTop: 22,
          opacity: pending ? 0.75 : 1,
        }}
      >
        {pending ? 'Signing in…' : 'Sign in'}
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
        No account?{' '}
        <Link href="/signup" style={{ color: 'var(--accent-bright)' }}>
          Sign up →
        </Link>
      </div>
    </form>
  );
}
