'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowRight } from 'lucide-react';
import { toast } from 'sonner';

import { SpecularButton } from '@/components/specular-button';

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
      <div className="space-y-4 text-center">
        <p className="text-[14px] text-text-secondary">
          This reset link is missing its token. Open the link from the
          email we sent — or request a fresh one.
        </p>
        <p className="pt-2 text-[13px] text-text-muted">
          <Link
            href="/forgot-password"
            className="text-violet-400 hover:text-violet-300 transition-colors"
          >
            Send a new reset link →
          </Link>
        </p>
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
      // Brief pause so the success state is visible before bouncing.
      setTimeout(() => router.push('/login'), 1500);
    } catch {
      setError({ error: 'Network error. Please try again.' });
    } finally {
      setPending(false);
    }
  }

  if (done) {
    return (
      <div className="space-y-4 text-center">
        <p className="text-[14px] text-text-secondary">
          Password updated. Redirecting to sign in…
        </p>
      </div>
    );
  }

  const fieldError = error?.field;
  const formError = !fieldError ? error?.error : null;

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      <div>
        <label
          htmlFor="password"
          className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary"
        >
          New password
        </label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={10}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={inputClass}
        />
        <p className="mt-1.5 text-[11px] text-text-muted">
          At least 10 characters, with upper + lowercase letters and a
          digit.
        </p>
        {fieldError === 'password' && (
          <p role="alert" className="mt-1.5 text-[12px] text-danger">
            {error?.error}
          </p>
        )}
      </div>

      <div>
        <label
          htmlFor="confirmPassword"
          className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary"
        >
          Confirm password
        </label>
        <input
          id="confirmPassword"
          name="confirmPassword"
          type="password"
          autoComplete="new-password"
          required
          minLength={10}
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          className={inputClass}
        />
        {fieldError === 'confirmPassword' && (
          <p role="alert" className="mt-1.5 text-[12px] text-danger">
            {error?.error}
          </p>
        )}
      </div>

      {formError && (
        <p role="alert" className="text-[12px] text-danger">
          {formError}
        </p>
      )}

      <SpecularButton
        type="submit"
        variant="primary"
        size="lg"
        className="w-full"
        disabled={pending || !password || !confirmPassword}
      >
        {pending ? 'Saving…' : 'Set new password'}
        {!pending && <ArrowRight className="h-4 w-4" />}
      </SpecularButton>

      <p className="text-center text-[13px] text-text-muted">
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

const inputClass =
  'block w-full rounded-lg border border-border-default bg-bg-surface-1/60 px-3.5 py-2.5 text-[14px] text-text-primary placeholder:text-text-muted outline-none transition-colors duration-200 focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30';
