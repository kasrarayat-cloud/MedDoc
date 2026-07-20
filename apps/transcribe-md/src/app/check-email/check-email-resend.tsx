'use client';

import { useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';

import { AuthFieldLabel } from '@/components/ui/auth-shell';

// Phase 5 — Linear V1 Faithful check-email resend block.
// /api/auth/resend-verification contract is unchanged: 200 on success,
// 429 on rate limit, anti-enumeration on unknown emails.

const linkStyle: React.CSSProperties = {
  color: 'var(--color-linear-sage-bright)',
  fontFamily: 'var(--font-sans)',
  fontWeight: 500,
  textDecoration: 'none',
};

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
};

export function CheckEmailResend() {
  const [email, setEmail] = useState('');
  const [pending, setPending] = useState(false);
  const [sent, setSent] = useState(false);

  async function onResend(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail) return;
    setPending(true);
    try {
      const res = await fetch('/api/auth/resend-verification', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: normalizedEmail }),
      });
      if (res.status === 429) {
        toast.error('Too many requests', {
          description: 'Wait a few minutes before trying again.',
        });
        return;
      }
      if (!res.ok) {
        toast.error('Could not resend', {
          description: 'Please try again, or contact support.',
        });
        return;
      }
      setSent(true);
      toast.success('Sent', {
        description:
          "If your account is unverified, you'll see a new link shortly.",
      });
    } catch {
      toast.error('Network error', { description: 'Please try again.' });
    } finally {
      setPending(false);
    }
  }

  const canSend = Boolean(email.trim()) && !pending && !sent;

  return (
    <form style={{ marginTop: 18 }} onSubmit={onResend}>
      {/* Linear V1 envelope mark — outline glyph in linear-sage-bright. */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          marginBottom: 18,
        }}
      >
        <svg
          width="64"
          height="48"
          viewBox="0 0 64 48"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden
        >
          <rect
            x="4"
            y="9"
            width="56"
            height="34"
            rx="4"
            stroke="var(--color-linear-sage-bright)"
            strokeWidth="1.4"
          />
          <path
            d="M4 12 L32 30 L60 12"
            stroke="var(--color-linear-sage-bright)"
            strokeWidth="1.4"
          />
          <path
            d="M44 5 l4 4 -4 4"
            stroke="var(--color-linear-sage-bright)"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M32 9 l16 0"
            stroke="var(--color-linear-sage-bright)"
            strokeWidth="1.4"
            opacity="0.6"
          />
        </svg>
      </div>

      <p
        style={{
          margin: '0 0 18px',
          fontFamily: 'var(--font-sans)',
          fontSize: 13.5,
          color: 'var(--color-linear-text-2)',
          textAlign: 'center',
          lineHeight: 1.55,
        }}
      >
        Didn&apos;t get it? Check your spam folder — or resend below.
      </p>

      <div style={{ marginBottom: 14 }}>
        <AuthFieldLabel htmlFor="verification-email">Email</AuthFieldLabel>
        <input
          id="verification-email"
          name="email"
          type="email"
          inputMode="email"
          autoComplete="email"
          spellCheck={false}
          maxLength={254}
          required
          value={email}
          onChange={(event) => {
            setEmail(event.target.value);
            setSent(false);
          }}
          style={{ ...inputStyle, marginTop: 6 }}
        />
      </div>

      <button
        type="submit"
        disabled={!canSend}
        className="qm-lin-btn"
        style={{
          width: '100%',
          height: 36,
          fontSize: 13,
          opacity: canSend ? 1 : 0.55,
          cursor: canSend ? 'pointer' : 'not-allowed',
        }}
      >
        {pending
          ? 'Sending…'
          : sent
            ? 'Sent — check your inbox'
            : 'Resend verification link'}
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
        <Link href="/login" style={linkStyle}>
          Back to sign in →
        </Link>
      </div>
    </form>
  );
}
