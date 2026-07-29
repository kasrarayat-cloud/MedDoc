'use client';

// ============================================================================
// ROUNDS — the in-lane RETRY affordance on a failed lane.
// ----------------------------------------------------------------------------
// WHY THIS IS A CLIENT COMPONENT AND NOT A <form action="...">.
//
// The board's first cut used a plain HTML form posting to
// /api/visits/[id]/retry. That route exists and accepts POST — but it is a
// JSON API route returning NextResponse. A native form POST would have
// NAVIGATED THE BROWSER to a page showing a JSON blob, which is not a bug that
// announces itself in a screenshot: the button appears to work, the board
// vanishes, and the doctor is looking at `{"ok":true}`.
//
// Caught by verifying the route rather than assuming the convention held.
//
// FAILED is genuinely retryable — the route's own eligibility notes say so
// ("FAILED is an explicit failure … doesn't need the staleness check"), which
// is why the board only renders this on failed lanes. SIGNED returns 409, and
// an in-flight visit with a fresh updatedAt returns 409 + STILL_PROCESSING so
// a live worker is never duplicated.
// ============================================================================

import { useRouter } from 'next/navigation';
import { useState } from 'react';

export function RoundsRetryButton({ visitId }: { visitId: string }) {
  const router = useRouter();
  const [state, setState] = useState<'idle' | 'working' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);

  async function retry() {
    setState('working');
    setMessage(null);
    try {
      const res = await fetch(`/api/visits/${visitId}/retry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) {
        // Surface the server's own refusal rather than a generic failure.
        // 409 here is usually STILL_PROCESSING, which is information the
        // doctor wants ("it is still going") not an error they should retry.
        const body = (await res.json().catch(() => null)) as
          | { error?: string; code?: string }
          | null;
        setState('error');
        setMessage(
          body?.code === 'STILL_PROCESSING'
            ? 'Still processing — give it a moment.'
            : (body?.error ?? 'Could not retry.'),
        );
        return;
      }
      setState('idle');
      // The lane's status changed server-side; refresh so the board redraws
      // the track rather than leaving a stale red stub on screen.
      router.refresh();
    } catch {
      setState('error');
      setMessage('Could not retry.');
    }
  }

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <button
        type="button"
        onClick={retry}
        disabled={state === 'working'}
        data-testid={`rounds-retry-${visitId}`}
        style={{
          fontFamily: 'var(--rounds-font-ui)',
          fontSize: 12,
          fontWeight: 600,
          color: 'var(--rounds-critical)',
          background: 'transparent',
          border: '1px solid var(--rounds-critical)',
          borderRadius: 'var(--rounds-radius-sm)',
          padding: '4px 10px',
          cursor: state === 'working' ? 'default' : 'pointer',
          opacity: state === 'working' ? 0.6 : 1,
        }}
      >
        {state === 'working' ? 'Retrying…' : 'Retry'}
      </button>
      {message ? (
        <span
          role="status"
          data-testid={`rounds-retry-message-${visitId}`}
          style={{
            fontFamily: 'var(--rounds-font-ui)',
            fontSize: 11.5,
            color: 'var(--rounds-text-2)',
          }}
        >
          {message}
        </span>
      ) : null}
    </span>
  );
}
