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

// Phase 5 — Linear V1 Faithful login form. The AuthShell wraps the
// page chrome; this component owns the form fields, submit CTA, and
// inline cross-app + verification banners. Server-action contract
// (loginAction signature, redirect handling, errors map) is unchanged
// per PROTECTED_CONTRACTS.

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
          maxLength={254}
          style={{ ...inputStyle, marginTop: 6 }}
        />
        <AuthFieldError message={errors.email} />
      </div>

      <div style={{ marginTop: 14 }}>
        <AuthFieldLabel
          htmlFor="password"
          hint={
            <Link
              href="/forgot-password"
              style={{ ...linkStyle, fontSize: 11.5 }}
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
          style={{ ...inputStyle, marginTop: 6 }}
        />
        <AuthFieldError message={errors.password} />
      </div>

      {!crossAppRedirect && <AuthFieldError message={errors._form} />}

      {crossAppRedirect && (
        <div
          style={{
            marginTop: 14,
            padding: 12,
            borderRadius: 8,
            border: '1px solid rgba(116, 168, 201, 0.30)',
            background: 'rgba(116, 168, 201, 0.06)',
            color: 'var(--color-linear-text-2)',
            fontFamily: 'var(--font-sans)',
            fontSize: 12.5,
            lineHeight: 1.5,
          }}
        >
          <p style={{ margin: 0, color: 'var(--color-linear-text)' }}>
            {crossAppRedirect.message}
          </p>
          <a
            href={crossAppRedirect.url}
            className="qm-lin-btn"
            style={{
              marginTop: 10,
              fontSize: 12,
              padding: '6px 12px',
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
            borderRadius: 8,
            border: '1px solid rgba(212, 165, 116, 0.30)',
            background: 'rgba(212, 165, 116, 0.06)',
            color: 'var(--color-linear-text-2)',
            fontFamily: 'var(--font-sans)',
            fontSize: 12.5,
            lineHeight: 1.5,
          }}
        >
          <p style={{ margin: 0 }}>
            We sent a verification link to{' '}
            <strong style={{ color: 'var(--color-linear-text)' }}>
              {needsVerificationFor}
            </strong>
            . Click it, then sign in again.
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
              color: 'var(--color-linear-amber)',
              fontFamily: 'var(--font-sans)',
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
        className="qm-lin-btn-primary"
        style={{
          width: '100%',
          marginTop: 22,
          height: 36,
          fontSize: 13,
          opacity: pending ? 0.75 : 1,
        }}
      >
        {pending ? 'Signing in…' : 'Sign in'}
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
        No account?{' '}
        <Link href="/signup" style={linkStyle}>
          Sign up →
        </Link>
      </div>
    </form>
  );
}
