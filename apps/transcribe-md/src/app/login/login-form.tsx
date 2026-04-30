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
      !state.needsVerificationFor &&
      !state.crossAppRedirect
    ) {
      toast.error('Sign-in failed', { description: state.errors._form });
    }
  }, [state, router]);

  const errors = state && !state.ok ? state.errors : {};
  const values = state && !state.ok ? state.values ?? {} : {};
  const needsVerificationFor =
    state && !state.ok ? state.needsVerificationFor : undefined;
  const crossAppRedirect =
    state && !state.ok ? state.crossAppRedirect : undefined;

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
      <div style={{ marginTop: 18 }}>
        <AuthFieldLabel htmlFor="email">Email</AuthFieldLabel>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          defaultValue={values.email ?? ''}
          required
          className="qm-cl-input"
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
              style={{
                fontSize: 11.5,
                color: 'var(--sage-deep)',
                fontFamily: 'var(--sans)',
                fontWeight: 500,
              }}
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
          className="qm-cl-input"
          style={{ marginTop: 6 }}
        />
        <AuthFieldError message={errors.password} />
      </div>

      {!crossAppRedirect && <AuthFieldError message={errors._form} />}

      {crossAppRedirect && (
        <div
          style={{
            marginTop: 14,
            padding: 12,
            borderRadius: 12,
            border: '1px solid rgba(123, 168, 196, 0.35)',
            background: 'var(--sky-tint)',
            color: 'var(--sky-deep)',
            fontSize: 12.5,
            lineHeight: 1.5,
          }}
        >
          <p style={{ margin: 0, color: 'var(--ink)' }}>
            {crossAppRedirect.message}
          </p>
          <a
            href={crossAppRedirect.url}
            className="qm-cl-btn qm-cl-btn-soft"
            style={{
              marginTop: 10,
              fontSize: 12.5,
              padding: '8px 14px',
              textDecoration: 'none',
            }}
          >
            {crossAppRedirect.buttonLabel}
            <Ic.arrowRight width={12} height={12} />
          </a>
        </div>
      )}

      {needsVerificationFor && (
        <div
          style={{
            marginTop: 14,
            padding: 12,
            borderRadius: 12,
            border: '1px solid rgba(212, 165, 116, 0.4)',
            background: 'var(--amber-tint)',
            color: 'var(--amber-deep)',
            fontSize: 12.5,
            lineHeight: 1.5,
          }}
        >
          <p style={{ margin: 0 }}>
            We sent a verification link to{' '}
            <strong style={{ color: 'var(--ink)' }}>{needsVerificationFor}</strong>.
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
              color: 'var(--amber-deep)',
              fontSize: 12,
              fontWeight: 500,
              textDecoration: 'underline',
              textUnderlineOffset: 2,
              cursor: resendPending ? 'default' : 'pointer',
              opacity: resendPending ? 0.6 : 1,
              fontFamily: 'var(--sans)',
            }}
          >
            {resendPending ? 'Sending…' : 'Resend the verification email'}
          </button>
        </div>
      )}

      <button
        type="submit"
        disabled={pending}
        className="qm-cl-btn qm-cl-btn-primary qm-cl-btn-lg"
        style={{
          width: '100%',
          justifyContent: 'center',
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
          color: 'var(--ink-3)',
          fontSize: 12.5,
          marginTop: 18,
          fontFamily: 'var(--sans)',
        }}
      >
        No account?{' '}
        <Link
          href="/signup"
          style={{ color: 'var(--sage-deep)', fontWeight: 500 }}
        >
          Sign up →
        </Link>
      </div>
    </form>
  );
}
