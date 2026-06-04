'use client';

// ============================================================================
// Phase 5 — Linear V1 Faithful error boundary fallback.
// ----------------------------------------------------------------------------
// Reference: dashboard-v1.html chrome (linear-bg + hairline border).
//
// Each app/**/error.tsx mounts this with a scope label. Behavior is
// unchanged — friendly recovery UI, sendBeacon to /api/client-errors,
// reset() retry, link back to dashboard. Visual: dark canvas, hairline
// border, sage retry CTA.
// ============================================================================

import { useEffect, useMemo } from 'react';
import Link from 'next/link';
import { ArrowLeft, RefreshCw } from 'lucide-react';

import { SpecularButton } from '@/components/specular-button';
import { isStaleDeploymentError } from '@/lib/stale-deployment';

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
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
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
}: ErrorFallbackProps) {
  const errorId = useMemo(() => makeErrorId(error.digest), [error.digest]);
  // Next.js "deployment skew": this tab loaded before a deploy, so an action it
  // posted no longer exists on the server. reset() re-mounts the SAME stale
  // bundle and fails again — only a full reload fixes it. Show an accurate
  // "updated, reload" message + a real Reload button instead of a crash.
  const isStale = useMemo(() => isStaleDeploymentError(error), [error]);

  useEffect(() => {
    // Fire-and-forget: sendBeacon if available (survives page unload),
    // fallback to fetch with keepalive. Never throw into the render
    // cycle — that would turn a recoverable error into an infinite
    // boundary loop.
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

  return (
    <main
      style={{
        minHeight: '60vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '64px 24px',
        background: 'var(--color-linear-bg)',
        color: 'var(--color-linear-text)',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 480,
          background: 'var(--color-linear-surface-1)',
          border: '1px solid var(--color-linear-border)',
          borderRadius: 10,
          padding: '40px 32px',
          textAlign: 'center',
        }}
      >
        <div
          aria-hidden
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 44,
            height: 44,
            borderRadius: '50%',
            background: 'rgba(212, 87, 74, 0.10)',
            border: '1px solid rgba(212, 87, 74, 0.35)',
            color: 'var(--color-linear-danger)',
            marginBottom: 18,
            fontSize: 18,
          }}
        >
          !
        </div>

        <h1
          style={{
            margin: 0,
            fontFamily: 'var(--font-sans)',
            fontSize: 22,
            fontWeight: 500,
            letterSpacing: '-0.012em',
            color: 'var(--color-linear-text)',
          }}
        >
          {isStale ? 'QuillMD was just updated' : 'Something went wrong'}
        </h1>

        <p
          style={{
            margin: '10px auto 0',
            maxWidth: 380,
            fontFamily: 'var(--font-sans)',
            fontSize: 13.5,
            lineHeight: 1.55,
            color: 'var(--color-linear-text-2)',
          }}
        >
          {isStale
            ? 'This page was open before our latest update, so that action isn’t available anymore. Reload to get the current version.'
            : 'We hit an unexpected error. The issue has been logged. Try again in a moment — if it keeps happening, send the error ID below to support.'}
        </p>

        <div
          style={{
            display: 'inline-block',
            marginTop: 18,
            padding: '6px 12px',
            borderRadius: 6,
            border: '1px solid var(--color-linear-border)',
            background: 'var(--color-linear-surface-2)',
            fontFamily: 'var(--font-mono)',
            fontSize: 11.5,
            color: 'var(--color-linear-text-3)',
          }}
        >
          Error ID:{' '}
          <span style={{ color: 'var(--color-linear-text)' }}>{errorId}</span>
        </div>

        <div
          style={{
            marginTop: 28,
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 12,
          }}
        >
          {isStale ? (
            <SpecularButton variant="primary" size="md" onClick={() => window.location.reload()}>
              <RefreshCw className="h-3.5 w-3.5" aria-hidden />
              Reload
            </SpecularButton>
          ) : (
            <SpecularButton variant="primary" size="md" onClick={reset}>
              <RefreshCw className="h-3.5 w-3.5" aria-hidden />
              Try again
            </SpecularButton>
          )}
          <Link
            href="/dashboard"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 12px',
              fontFamily: 'var(--font-sans)',
              fontSize: 12.5,
              color: 'var(--color-linear-text-3)',
              textDecoration: 'none',
              transition: 'color 120ms ease',
            }}
            className="hover:!text-linear-text-2"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
            Back to dashboard
          </Link>
        </div>
      </div>
    </main>
  );
}
