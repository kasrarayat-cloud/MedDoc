'use client';

import { useActionState } from 'react';

import { AuthFieldError, AuthFieldLabel } from '@/components/ui/auth-shell';
import { joinWaitlistAction, type WaitlistState } from '@/actions/waitlist';

const initialState: WaitlistState = { ok: false };

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

export function WaitlistForm() {
  const [state, formAction, pending] = useActionState(
    joinWaitlistAction,
    initialState,
  );

  if (state.ok && state.message) {
    return (
      <div
        style={{
          marginTop: 20,
          padding: 16,
          borderRadius: 8,
          background: 'var(--color-linear-surface-2)',
          border: '1px solid var(--color-linear-border)',
          fontFamily: 'var(--font-sans)',
          fontSize: 13.5,
          color: 'var(--color-linear-text)',
        }}
      >
        {state.message}
      </div>
    );
  }

  return (
    <form action={formAction}>
      <input type="hidden" name="source" value="app-waitlist" />

      <div style={{ marginTop: 18 }}>
        <AuthFieldLabel htmlFor="wl-email">Email</AuthFieldLabel>
        <input
          id="wl-email"
          name="email"
          type="email"
          autoComplete="email"
          required
          maxLength={254}
          style={{ ...inputStyle, marginTop: 6 }}
        />
        <AuthFieldError message={state.errors?.email} />
      </div>

      <div style={{ marginTop: 14 }}>
        <AuthFieldLabel htmlFor="wl-name">Name</AuthFieldLabel>
        <input
          id="wl-name"
          name="name"
          type="text"
          autoComplete="name"
          maxLength={120}
          style={{ ...inputStyle, marginTop: 6 }}
        />
      </div>

      <div style={{ marginTop: 14 }}>
        <AuthFieldLabel htmlFor="wl-note">
          Specialty and practice size (optional)
        </AuthFieldLabel>
        <input
          id="wl-note"
          name="note"
          type="text"
          maxLength={500}
          placeholder="e.g. vascular ultrasound, solo practice"
          style={{ ...inputStyle, marginTop: 6 }}
        />
        {/* Said plainly, because this box is on a medical product and someone
            WILL be tempted to describe a case in it. */}
        <p
          style={{
            marginTop: 6,
            fontSize: 12,
            color: 'var(--color-linear-text-3, #8a8f98)',
            fontFamily: 'var(--font-sans)',
          }}
        >
          Please don&rsquo;t include any patient information.
        </p>
      </div>

      <button
        type="submit"
        disabled={pending}
        style={{
          marginTop: 20,
          width: '100%',
          height: 38,
          borderRadius: 6,
          border: 'none',
          background: 'var(--color-linear-sage)',
          color: '#08090a',
          fontFamily: 'var(--font-sans)',
          fontSize: 13.5,
          fontWeight: 600,
          cursor: pending ? 'default' : 'pointer',
          opacity: pending ? 0.7 : 1,
        }}
      >
        {pending ? 'Adding you…' : 'Join the waitlist'}
      </button>

      <p
        style={{
          marginTop: 14,
          fontSize: 12.5,
          color: 'var(--color-linear-text-3, #8a8f98)',
          fontFamily: 'var(--font-sans)',
          textAlign: 'center',
        }}
      >
        Already have an invite code?{' '}
        <a href="/signup" style={{ color: 'var(--color-linear-sage-bright)' }}>
          Create your account
        </a>
      </p>
    </form>
  );
}
