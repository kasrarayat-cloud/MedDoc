'use client';

import { useState } from 'react';
import { toast } from 'sonner';

interface ApiError {
  error?: string;
  field?: string;
}

export function ChangePasswordForm() {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const res = await fetch('/api/settings/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          currentPassword,
          newPassword,
          confirmPassword,
        }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as ApiError;
        setError(body);
        return;
      }
      toast.success('Password updated', {
        description:
          'Other devices were signed out. You can keep using this one.',
      });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch {
      setError({ error: 'Network error. Please try again.' });
    } finally {
      setPending(false);
    }
  }

  const fieldError = error?.field;
  const formError = error && !fieldError ? error.error : null;

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      <div>
        <label
          htmlFor="currentPassword"
          className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary"
        >
          Current password
        </label>
        <input
          id="currentPassword"
          type="password"
          autoComplete="current-password"
          required
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          disabled={pending}
          className={inputClass}
        />
        {fieldError === 'currentPassword' && (
          <p role="alert" className="mt-1.5 text-[12px] text-danger">
            {error?.error}
          </p>
        )}
      </div>

      <div>
        <label
          htmlFor="newPassword"
          className="mb-1.5 block text-[12px] font-medium tracking-tight text-text-tertiary"
        >
          New password
        </label>
        <input
          id="newPassword"
          type="password"
          autoComplete="new-password"
          required
          minLength={10}
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          disabled={pending}
          className={inputClass}
        />
        <p className="mt-1.5 text-[11px] text-text-muted">
          At least 10 characters, with upper + lowercase letters and a digit.
        </p>
        {fieldError === 'newPassword' && (
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
          Confirm new password
        </label>
        <input
          id="confirmPassword"
          type="password"
          autoComplete="new-password"
          required
          minLength={10}
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          disabled={pending}
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

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={
            pending || !currentPassword || !newPassword || !confirmPassword
          }
          className="inline-flex items-center gap-2 rounded-lg bg-violet-500 px-4 py-2 text-[13px] font-medium text-white shadow-[0_0_0_1px_rgba(139,92,246,0.3),0_8px_24px_-8px_rgba(124,58,237,0.5)] hover:bg-violet-600 transition-all disabled:opacity-50 disabled:pointer-events-none"
        >
          {pending ? 'Updating…' : 'Update password'}
        </button>
      </div>
    </form>
  );
}

const inputClass =
  'block w-full rounded-lg border border-border-default bg-bg-surface-1/60 px-3.5 py-2.5 text-[14px] text-text-primary outline-none transition-colors focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30';
