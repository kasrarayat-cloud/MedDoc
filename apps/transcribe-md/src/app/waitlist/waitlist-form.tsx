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
        className="qm-rounds-panel"
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
          className="qm-rounds-input"
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
          className="qm-rounds-input"
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
          className="qm-rounds-input"
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

      {/* ⚠️ THE LABEL COLOUR IS A TOKEN, AND IT IS A CONTRAST FIX, NOT A TASTE
          CHANGE. `--color-linear-sage` bridges to `--rounds-accent`, a mid
          indigo. A hardcoded `#08090a` measures 7.27:1 on sage but only
          **3.71:1 on the accent — an AA failure**, on the submit button of the
          most-visited unauthenticated page in the product. The bridge retints
          the fill and cannot touch a literal sitting on it, so the label must
          come from `--rounds-on-accent`. Do not re-hardcode it.
          Gate C could not have caught this: axe ownership climbs to the
          nearest classed ancestor-or-self, and a classed button answers for
          itself — so the violation would be logged "inherited" and never
          block. `gate-c1d-auth` computes the ratio instead. */}
      <button
        type="submit"
        disabled={pending}
        className="qm-rounds-btn-primary"
        style={{
          marginTop: 20,
          width: '100%',
          height: 38,
          borderRadius: 6,
          border: 'none',
          background: 'var(--color-linear-sage)',
          color: 'var(--rounds-on-accent)',
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
        {/* Underlined, not just tinted. A link inside a text block that is
            distinguished ONLY by colour fails axe's link-in-text-block at
            SERIOUS — anyone who cannot separate the two hues sees prose. */}
        <a
          href="/signup"
          className="qm-rounds-link"
          style={{
            color: 'var(--color-linear-sage-bright)',
            textDecoration: 'underline',
          }}
        >
          Create your account
        </a>
      </p>
    </form>
  );
}
