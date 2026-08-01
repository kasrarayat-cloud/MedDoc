'use client';

import { useState } from 'react';
import { toast } from 'sonner';

// Phase 5 — Linear V1 Faithful change-password form. /api/settings/
// change-password contract is unchanged per PROTECTED_CONTRACTS.

interface ApiError {
  error?: string;
  field?: string;
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  height: 32,
  padding: '0 10px',
  background: 'var(--color-linear-surface-2)',
  border: '1px solid var(--color-linear-border)',
  borderRadius: 6,
  color: 'var(--color-linear-text)',
  fontFamily: 'var(--font-sans)',
  fontSize: 13,
  outline: 'none',
  transition: 'border-color 100ms ease',
};

const labelStyle: React.CSSProperties = {
  display: 'block',
  marginBottom: 6,
  fontFamily: 'var(--font-mono)',
  fontSize: 10.5,
  color: 'var(--color-linear-text-3)',
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  fontWeight: 500,
};

const errorStyle: React.CSSProperties = {
  marginTop: 6,
  fontFamily: 'var(--font-sans)',
  fontSize: 12,
  color: 'var(--color-linear-coral)',
};

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
    <form
      onSubmit={onSubmit}
      style={{ display: 'flex', flexDirection: 'column', gap: 14 }}
      noValidate
    >
      <div>
        <label
          htmlFor="currentPassword"
          className="qm-rounds-label"
          style={labelStyle}
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
          className="qm-tap-44-input qm-rounds-input" style={inputStyle}
        />
        {fieldError === 'currentPassword' && (
          <p role="alert" className="qm-rounds-error" style={errorStyle}>
            {error?.error}
          </p>
        )}
      </div>

      <div>
        <label
          htmlFor="newPassword"
          className="qm-rounds-label"
          style={labelStyle}
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
          className="qm-tap-44-input qm-rounds-input" style={inputStyle}
        />
        <p
          style={{
            marginTop: 6,
            fontFamily: 'var(--font-sans)',
            fontSize: 11.5,
            color: 'var(--color-linear-text-3)',
          }}
        >
          At least 10 characters, with upper + lowercase letters and a digit.
        </p>
        {fieldError === 'newPassword' && (
          <p role="alert" className="qm-rounds-error" style={errorStyle}>
            {error?.error}
          </p>
        )}
      </div>

      <div>
        <label
          htmlFor="confirmPassword"
          className="qm-rounds-label"
          style={labelStyle}
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
          className="qm-tap-44-input qm-rounds-input" style={inputStyle}
        />
        {fieldError === 'confirmPassword' && (
          <p role="alert" className="qm-rounds-error" style={errorStyle}>
            {error?.error}
          </p>
        )}
      </div>

      {formError && (
        <p role="alert" className="qm-rounds-error" style={errorStyle}>
          {formError}
        </p>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
        <button
          type="submit"
          disabled={
            pending || !currentPassword || !newPassword || !confirmPassword
          }
          className="qm-lin-btn-primary"
          style={{
            height: 30,
            padding: '0 14px',
            fontSize: 12.5,
            opacity:
              pending || !currentPassword || !newPassword || !confirmPassword
                ? 0.55
                : 1,
            cursor:
              pending || !currentPassword || !newPassword || !confirmPassword
                ? 'not-allowed'
                : 'pointer',
          }}
        >
          {pending ? 'Updating…' : 'Update password'}
        </button>
      </div>
    </form>
  );
}
