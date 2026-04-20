'use client';

import { useActionState, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { toast } from 'sonner';

import { SpecularButton } from '@/components/specular-button';
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
    } else if (state && !state.ok && state.errors._form && !state.needsVerificationFor) {
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
        toast.error('Could not resend', {
          description: 'Please try again later.',
        });
      }
    } catch {
      toast.error('Network error', { description: 'Please try again.' });
    } finally {
      setResendPending(false);
    }
  }

  return (
    <form action={formAction} className="space-y-4">
      <FieldLabel htmlFor="email" label="Email">
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          defaultValue={values.email ?? ''}
          required
          className={inputClass}
        />
        <FieldError message={errors.email} />
      </FieldLabel>

      <FieldLabel htmlFor="password" label="Password">
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          className={inputClass}
        />
        <FieldError message={errors.password} />
      </FieldLabel>

      <FieldError message={errors._form} />

      {needsVerificationFor && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-3 text-[12px] leading-relaxed text-amber-200">
          <p>
            We sent a verification link to{' '}
            <strong className="text-amber-100">{needsVerificationFor}</strong>.
            Click it, then sign in again.
          </p>
          <button
            type="button"
            onClick={resendVerification}
            disabled={resendPending}
            className="mt-2 inline-flex items-center gap-1.5 text-[12px] font-medium text-amber-100 underline-offset-2 hover:underline disabled:opacity-50"
          >
            {resendPending ? 'Sending…' : 'Resend the verification email'}
          </button>
        </div>
      )}

      <div className="flex justify-end -mt-2">
        <Link
          href="/forgot-password"
          className="text-[12px] text-text-muted hover:text-violet-300 transition-colors"
        >
          Forgot password?
        </Link>
      </div>

      <SpecularButton type="submit" variant="primary" size="lg" className="w-full">
        {pending ? 'Signing in…' : 'Sign in'}
        {!pending && <ArrowRight className="h-4 w-4" />}
      </SpecularButton>

      <p className="text-center text-[13px] text-text-muted">
        No account?{' '}
        <Link
          href="/signup"
          className="text-violet-400 hover:text-violet-300 transition-colors"
        >
          Sign up →
        </Link>
      </p>
    </form>
  );
}

const inputClass =
  'block w-full rounded-lg border border-border-default bg-bg-surface-1/60 px-3.5 py-2.5 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors duration-200 focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30';

function FieldLabel({
  htmlFor,
  label,
  children,
}: {
  htmlFor: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label
        htmlFor={htmlFor}
        className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary"
      >
        {label}
      </label>
      {children}
    </div>
  );
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="mt-1.5 text-[12px] text-danger">
      {message}
    </p>
  );
}
