'use client';

import { useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import { isSkinRounds } from '@/config/skin-rounds';

interface Props {
  email: string;
}

// Phase 5 — Linear V1 Faithful check-email resend block.
// /api/auth/resend-verification contract is unchanged: 200 on success,
// 429 on rate limit, anti-enumeration on unknown emails.

const linkStyle: React.CSSProperties = {
  color: 'var(--color-linear-sage-bright)',
  fontFamily: 'var(--font-sans)',
  fontWeight: 500,
  textDecoration: 'none',
};

export function CheckEmailResend({ email }: Props) {
  // Build-time, so flag-OFF folds to a constant and this component renders
  // exactly as it does today.
  const rounds = isSkinRounds();
  const [pending, setPending] = useState(false);
  const [sent, setSent] = useState(false);

  async function onResend() {
    if (!email) return;
    setPending(true);
    try {
      const res = await fetch('/api/auth/resend-verification', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
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

  const canSend = Boolean(email) && !pending && !sent;

  return (
    <div style={{ marginTop: 18 }}>
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

      <button
        type="button"
        disabled={!canSend}
        onClick={onResend}
        className={rounds ? 'qm-lin-btn qm-rounds-btn-secondary' : 'qm-lin-btn'}
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
        <Link href="/login" className={rounds ? 'qm-rounds-link' : undefined} style={linkStyle}>
          Back to sign in →
        </Link>
      </div>
    </div>
  );
}
