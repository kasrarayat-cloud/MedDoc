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
        description: "If your account is unverified, you'll see a new link shortly.",
      });
    } catch {
      toast.error('Network error', {
        description: 'Please try again.',
      });
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-4 text-center">
      <p className="text-[13px] text-text-tertiary">
        Didn&apos;t get the email? Check your spam folder, or resend the link.
      </p>

      <button
        type="button"
        disabled={!email || pending || sent}
        onClick={onResend}
        className="w-full rounded-lg border border-border-default bg-bg-surface-1/60 px-4 py-2 text-[13px] font-medium text-text-secondary hover:bg-bg-surface-2/70 hover:border-border-emphasis transition-colors disabled:opacity-50"
      >
        {pending ? 'Sending…' : sent ? 'Sent — check your inbox' : 'Resend verification link'}
      </button>

      <p className="pt-2 text-[13px] text-text-muted">
        <Link
          href="/login"
          className="text-violet-400 hover:text-violet-300 transition-colors"
        >
          Back to sign in →
        </Link>
      </p>
    </div>
  );
}
