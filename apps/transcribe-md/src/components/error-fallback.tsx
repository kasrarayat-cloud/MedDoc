'use client';

// ============================================================================
// ErrorFallback — shared body for every app/**/error.tsx (T-M11)
// ----------------------------------------------------------------------------
// Next 16 requires each error boundary to be its own file. Rather than
// re-author the same JSX five times, each boundary is a one-liner that
// renders this component with a surface-specific `scope` label.
//
// Behavior:
//   • Shows a friendly "something went wrong" page — NEVER exposes the
//     raw error.message to the user. Supports can ask for the errorId.
//   • "Try again" calls reset(), which re-mounts the boundary's child
//     subtree. If the underlying issue was transient (network hiccup)
//     the user recovers without a full page reload.
//   • "Back to dashboard" link for when reset() isn't enough.
//   • Fires one sendBeacon (or fetch fallback) to /api/client-errors
//     the first time the boundary mounts so ops can correlate support
//     reports with server logs. errorId is a short slug the user can
//     read over the phone.
// ============================================================================

import { useEffect, useMemo } from 'react';
import Link from 'next/link';
import { ArrowLeft, RefreshCw } from 'lucide-react';

import { SpecularButton } from '@/components/specular-button';

type ErrorFallbackTheme = 'legacy' | 'clinician';

interface ErrorFallbackProps {
  /** The Error that Next's boundary passed in. Kept out of the UI. */
  error: Error & { digest?: string };
  /** Re-mounts the child subtree of this boundary. */
  reset: () => void;
  /** Human label identifying which boundary fired. Included in the
   *  client-errors POST body so ops can see *where* something broke. */
  scope:
    | 'root'
    | 'dashboard'
    | 'visits:new'
    | 'visits:id'
    | 'settings';
  /** Visual theme — `'legacy'` (dark surface, danger ring), or
   *  `'clinician'` (warm cream `.qm-cl-card` + soft retry CTA). */
  theme?: ErrorFallbackTheme;
}

function makeErrorId(digest: string | undefined): string {
  if (digest && digest.length > 0) return digest;
  // Short readable ID; the user only needs to read it aloud to support.
  const rand = Math.random().toString(36).slice(2, 8);
  return `c-${Date.now().toString(36)}-${rand}`;
}

export function ErrorFallback({
  error,
  reset,
  scope,
  theme = 'legacy',
}: ErrorFallbackProps) {
  const errorId = useMemo(() => makeErrorId(error.digest), [error.digest]);

  useEffect(() => {
    // Fire-and-forget: sendBeacon if available (survives page unload),
    // fallback to fetch with keepalive. Either way, this call must
    // NEVER throw into the render cycle — it would turn a recoverable
    // error into an infinite boundary loop.
    try {
      const payload = JSON.stringify({
        errorId,
        scope,
        message: error.message,
        stack: error.stack,
        digest: error.digest,
        url: typeof window !== 'undefined' ? window.location.href : '',
        userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : '',
      });
      const blob = new Blob([payload], { type: 'application/json' });
      if (
        typeof navigator !== 'undefined' &&
        typeof navigator.sendBeacon === 'function'
      ) {
        navigator.sendBeacon('/api/client-errors', blob);
      } else {
        void fetch('/api/client-errors', {
          method: 'POST',
          body: payload,
          headers: { 'content-type': 'application/json' },
          keepalive: true,
        }).catch(() => {
          /* swallow — the user sees the boundary UI regardless */
        });
      }
    } catch {
      /* swallow — never let telemetry failure propagate */
    }
  }, [error.digest, error.message, error.stack, errorId, scope]);

  if (theme === 'clinician') {
    return (
      <main className="mx-auto flex min-h-[60vh] max-w-xl flex-col items-center justify-center px-4 py-16 text-center sm:py-24">
        <div className="qm-cl-card flex w-full flex-col items-center px-6 py-10 sm:px-10 sm:py-12">
          <div
            aria-hidden
            className="mb-6 inline-flex h-12 w-12 items-center justify-center rounded-full"
            style={{
              background: 'var(--coral-tint, rgba(201, 123, 110, 0.14))',
              color: 'var(--coral-deep, #7A3329)',
              border: '1px solid var(--coral-tint-strong, rgba(201, 123, 110, 0.22))',
            }}
          >
            <span className="text-[20px]">!</span>
          </div>

          <h1
            className="text-clinician-ink"
            style={{
              fontFamily: 'var(--serif, "Source Serif 4", Georgia, serif)',
              fontSize: 28,
              fontWeight: 400,
              letterSpacing: '-0.015em',
              margin: 0,
            }}
          >
            Something went wrong
          </h1>

          <div className="qm-cl-prose mt-3" style={{ maxWidth: 420 }}>
            <p>
              We hit an unexpected error. The issue has been logged. Try again
              in a moment — if it keeps happening, send the error ID below to
              support.
            </p>
          </div>

          <div
            className="mt-6 rounded-lg px-4 py-2 font-mono text-[12px]"
            style={{
              border: '1px solid var(--line, rgba(43, 38, 32, 0.08))',
              background: 'var(--cream-2, #F2EDE3)',
              color: 'var(--ink-3, #8A8278)',
            }}
          >
            Error ID:{' '}
            <span className="text-clinician-ink">{errorId}</span>
          </div>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <SpecularButton
              theme="clinician"
              variant="secondary"
              size="md"
              onClick={reset}
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden />
              Try again
            </SpecularButton>
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-1.5 rounded-md text-[13px] text-clinician-ink-3 transition-colors hover:text-clinician-ink-2"
            >
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
              Back to dashboard
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-[60vh] max-w-xl flex-col items-center justify-center px-4 py-16 text-center sm:py-24">
      <div className="mb-6 inline-flex h-12 w-12 items-center justify-center rounded-full border border-danger/30 bg-danger/10">
        <span aria-hidden className="text-[20px]">!</span>
      </div>

      <h1 className="type-h1 text-text-primary">Something went wrong</h1>

      <p className="mt-3 max-w-md text-[14px] leading-relaxed text-text-tertiary">
        We hit an unexpected error. The issue has been logged. Try again in a
        moment — if it keeps happening, send the error ID below to support.
      </p>

      <div className="mt-6 rounded-lg border border-border-subtle bg-bg-surface-1/60 px-4 py-2 font-mono text-[12px] text-text-tertiary">
        Error ID: <span className="text-text-primary">{errorId}</span>
      </div>

      <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
        <SpecularButton variant="primary" size="md" onClick={reset}>
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
          Try again
        </SpecularButton>
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1.5 rounded-md text-[13px] text-text-tertiary transition-colors hover:text-text-secondary"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
          Back to dashboard
        </Link>
      </div>
    </main>
  );
}
