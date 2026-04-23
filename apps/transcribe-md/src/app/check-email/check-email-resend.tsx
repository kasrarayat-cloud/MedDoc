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
    <div style={{ marginTop: 14 }}>
      <p
        style={{
          margin: '0 0 14px',
          fontSize: 12.5,
          color: 'var(--fg-3)',
          textAlign: 'center',
        }}
      >
        Didn&apos;t get it? Check your spam folder — or resend below.
      </p>

      <button
        type="button"
        disabled={!canSend}
        onClick={onResend}
        className="qm-btn qm-btn-ghost"
        style={{
          width: '100%',
          justifyContent: 'center',
          padding: 10,
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
          color: 'var(--fg-3)',
          fontSize: 12.5,
          marginTop: 18,
        }}
      >
        <Link href="/login" style={{ color: 'var(--accent-bright)' }}>
          Back to sign in →
        </Link>
      </div>
    </div>
  );
}
