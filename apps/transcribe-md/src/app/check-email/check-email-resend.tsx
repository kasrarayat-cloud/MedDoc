'use client';

import { useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';

interface Props {
  email: string;
}

export function CheckEmailResend({ email }: Props) {
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
      {/* Soft sage line-art envelope — the warm illustration moment per
         the Clinician landing-and-recording mockup's empty-state
         vocabulary. Stroke 1.4 px, fill from --sage-tint-strong. */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          marginBottom: 18,
        }}
      >
        <svg
          width="96"
          height="72"
          viewBox="0 0 96 72"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden
        >
          <rect
            x="6"
            y="14"
            width="84"
            height="52"
            rx="6"
            className="qm-cl-illus-fill-cream qm-cl-illus-stroke"
            strokeWidth="1.4"
          />
          <path
            d="M6 18 L48 44 L90 18"
            className="qm-cl-illus-stroke"
            strokeWidth="1.4"
          />
          <path
            d="M64 8 l6 6 -6 6"
            className="qm-cl-illus-stroke"
            strokeWidth="1.4"
          />
          <path
            d="M48 14 l22 0"
            className="qm-cl-illus-stroke"
            strokeWidth="1.4"
            opacity="0.6"
          />
        </svg>
      </div>

      <p
        className="qm-cl-serif"
        style={{
          margin: '0 0 18px',
          fontSize: 14.5,
          color: 'var(--ink-2)',
          textAlign: 'center',
          fontStyle: 'italic',
          lineHeight: 1.55,
        }}
      >
        Didn&apos;t get it? Check your spam folder — or resend below.
      </p>

      <button
        type="button"
        disabled={!canSend}
        onClick={onResend}
        className="qm-cl-btn qm-cl-btn-soft"
        style={{
          width: '100%',
          justifyContent: 'center',
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
          color: 'var(--ink-3)',
          fontSize: 12.5,
          marginTop: 18,
          fontFamily: 'var(--sans)',
        }}
      >
        <Link href="/login" style={{ color: 'var(--sage-deep)', fontWeight: 500 }}>
          Back to sign in →
        </Link>
      </div>
    </div>
  );
}
