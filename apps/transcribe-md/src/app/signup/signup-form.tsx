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
import { signupAction, type AuthActionState } from '@/actions/auth';
import { MARKETING_URL } from '@/lib/constants';
import { isSkinRounds } from '@/config/skin-rounds';

const initialState: AuthActionState = null;

// Phase 5 — Linear V1 Faithful signup form. AuthShell owns the page
// chrome; this component owns fields + submit + terms checkbox.
// signupAction signature unchanged per PROTECTED_CONTRACTS.

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

export function SignupForm() {
  // Build-time, so flag-OFF folds to a constant and this component renders
  // exactly as it does today.
  const rounds = isSkinRounds();
  const [state, formAction, pending] = useActionState(signupAction, initialState);
  const router = useRouter();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  useEffect(() => {
    if (state && state.ok) {
      if (state.warning) {
        toast.warning('Account created', { description: state.warning });
      } else {
        toast.success('Welcome to QuillMD', {
          description: "You're in. Start your first visit whenever you're ready.",
        });
      }
      router.push(state.redirect);
      router.refresh();
    } else if (state && !state.ok && state.errors._form) {
      toast.error('Signup failed', { description: state.errors._form });
    }
  }, [state, router]);

  const errors = state && !state.ok ? state.errors : {};
  const values = state && !state.ok ? state.values ?? {} : {};

  // Client-side confirm-password check. The server schema doesn't
  // validate confirmPassword, so we MUST block submission here —
  // otherwise a user with mismatched inputs would unknowingly create
  // an account using the first password field.
  const mismatchMessage =
    confirmPassword.length > 0 && confirmPassword !== password
      ? 'Passwords do not match'
      : undefined;

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    if (confirmPassword !== password) {
      e.preventDefault();
      toast.error('Passwords do not match', {
        description: 'Retype your password in the Confirm field.',
      });
      document.getElementById('confirmPassword')?.focus();
    }
  };

  return (
    <form action={formAction} onSubmit={handleSubmit}>
      {/* Invite-only pilot (2026-07-28). First field, because it decides
          whether the rest is worth filling in — and the server refuses before
          it ever looks the email up, so a wrong code reveals nothing. */}
      <div style={{ marginTop: 18 }}>
        <AuthFieldLabel htmlFor="inviteCode">Invite code</AuthFieldLabel>
        <input
          id="inviteCode"
          name="inviteCode"
          type="text"
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          defaultValue={values.inviteCode ?? ''}
          required
          maxLength={64}
          className={rounds ? 'qm-rounds-input' : undefined}
          style={{ ...inputStyle, marginTop: 6, letterSpacing: '0.04em' }}
        />
        <p
          style={{
            marginTop: 6,
            fontSize: 12,
            color: 'var(--color-linear-text-3, #8a8f98)',
          }}
        >
          QuillMD is invite-only during the pilot.{' '}
          {/* Underlined, not just tinted — the reciprocal of the /waitlist →
              /signup link, and the same recorded axe fix. A link inside a text
              block distinguished ONLY by colour fails `link-in-text-block` at
              SERIOUS. The comment was on the waitlist half only; carried across
              so the next reader does not tidy this one away as an
              inconsistency with the file's own `linkStyle` default. */}
          <a
            href="/waitlist"
            className={rounds ? 'qm-rounds-link' : undefined}
            style={{ textDecoration: 'underline' }}
          >
            Join the waitlist
          </a>{' '}
          if you don&rsquo;t have a code.
        </p>
        <AuthFieldError message={errors.inviteCode} />
      </div>

      <div style={{ marginTop: 14 }}>
        <AuthFieldLabel htmlFor="name">Full name</AuthFieldLabel>
        <input
          id="name"
          name="name"
          type="text"
          autoComplete="name"
          defaultValue={values.name ?? ''}
          required
          className={rounds ? 'qm-rounds-input' : undefined}
          style={{ ...inputStyle, marginTop: 6 }}
        />
        <AuthFieldError message={errors.name} />
      </div>

      <div style={{ marginTop: 14 }}>
        <AuthFieldLabel htmlFor="email">Email</AuthFieldLabel>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          defaultValue={values.email ?? ''}
          required
          maxLength={254}
          className={rounds ? 'qm-rounds-input' : undefined}
          style={{ ...inputStyle, marginTop: 6 }}
        />
        <AuthFieldError message={errors.email} />
      </div>

      <div style={{ marginTop: 14 }}>
        <AuthFieldLabel htmlFor="password">Password</AuthFieldLabel>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={rounds ? 'qm-rounds-input' : undefined}
          style={{ ...inputStyle, marginTop: 6 }}
        />
        <p
          style={{
            marginTop: 6,
            fontFamily: 'var(--font-sans)',
            fontSize: 11.5,
            color: 'var(--color-linear-text-3)',
            lineHeight: 1.4,
          }}
        >
          At least 10 characters, with upper + lowercase letters and a digit.
        </p>
        <AuthFieldError message={errors.password} />
      </div>

      <div style={{ marginTop: 14 }}>
        <AuthFieldLabel htmlFor="confirmPassword">Confirm password</AuthFieldLabel>
        <input
          id="confirmPassword"
          name="confirmPassword"
          type="password"
          autoComplete="new-password"
          required
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          className={rounds ? 'qm-rounds-input' : undefined}
          style={{ ...inputStyle, marginTop: 6 }}
        />
        <AuthFieldError message={mismatchMessage} />
      </div>

      <label
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 10,
          marginTop: 18,
          fontFamily: 'var(--font-sans)',
          fontSize: 12.5,
          color: 'var(--color-linear-text-2)',
          lineHeight: 1.5,
        }}
      >
        {/* ⚠️ NO id, NO htmlFor, and that is deliberate: the wrapping <label>
            gives it an implicit association, and its accessible name is the
            whole label's prose. That is why 38 spec files reach it as the
            single unqualified `getByRole('checkbox')` on /signup. Do not give
            it an id and an external label, and never add a second checkbox to
            this page — either throws Playwright strict mode across the suite.
            A className is safe; the accessible name does not change. */}
        <input
          type="checkbox"
          name="acceptTerms"
          required
          className={rounds ? 'qm-rounds-check' : undefined}
          style={{
            marginTop: 3,
            width: 14,
            height: 14,
            accentColor: 'var(--color-linear-sage)',
          }}
        />
        <span>
          I agree to the{' '}
          <a
            href={`${MARKETING_URL}/terms`}
            target="_blank"
            rel="noopener noreferrer"
            className={rounds ? 'qm-rounds-link' : undefined} style={linkStyle}
          >
            terms of service
          </a>{' '}
          and{' '}
          <a
            href={`${MARKETING_URL}/privacy`}
            target="_blank"
            rel="noopener noreferrer"
            className={rounds ? 'qm-rounds-link' : undefined} style={linkStyle}
          >
            privacy policy
          </a>
          .
        </span>
      </label>
      <AuthFieldError message={errors.acceptTerms} />
      <AuthFieldError message={errors._form} />

      <button
        type="submit"
        disabled={pending}
        aria-disabled={pending || Boolean(mismatchMessage)}
        className={rounds ? 'qm-lin-btn-primary qm-rounds-btn-primary' : 'qm-lin-btn-primary'}
        style={{
          width: '100%',
          marginTop: 22,
          height: 36,
          fontSize: 13,
          opacity: pending ? 0.6 : 1,
          cursor: pending ? 'not-allowed' : 'pointer',
        }}
      >
        {pending ? 'Creating account…' : 'Create account'}
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
        Have an account?{' '}
        <Link href="/login" className={rounds ? 'qm-rounds-link' : undefined} style={linkStyle}>
          Sign in →
        </Link>
      </div>
    </form>
  );
}
