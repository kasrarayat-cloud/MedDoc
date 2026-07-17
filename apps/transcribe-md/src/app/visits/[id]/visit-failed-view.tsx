'use client';

// ============================================================================
// VisitFailedView — terminal-state UI for a FAILED visit row.
// ----------------------------------------------------------------------------
// 2026-05-12 prod-fix (post-deep-audit follow-up): the failure UI now
// branches on (failureCategory × failed-layer × inputMode) instead of
// failureCategory alone, so an L6 polish blip + a Deepgram outage + a
// 1-second dictation don't all collapse to "Connection issue" + WiFi-off.
// Copy + icon derivation lives in `./visit-failed-copy.ts` so the table
// is unit-testable. The WiFi-off icon is gone from this surface — true
// client-side network failures are surfaced via the retry-handler's
// sonner toast, not the visit-row UI.
// ============================================================================

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Loader2, RefreshCw, Upload } from 'lucide-react';
import { toast } from 'sonner';

import { failureCopyFor } from './visit-failed-copy';

type VisitFailedViewTheme = 'legacy' | 'clinician';

interface Props {
  visitId: string;
  syntheticQaAttempt?: number | null;
  reason: string | null;
  /** One of 'transient' | 'permanent' | 'provider_down' (or null on
   *  pre-categorization rows). Drives icon + headline + CTA. */
  failureCategory?: string | null;
  /** Visit inputMode — drives text_notes vs audio-corrupt copy split
   *  (deep-audit G11). 'audio_upload' | 'voice_dictation' | 'text_notes'. */
  inputMode?: string | null;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: VisitFailedViewTheme;
}

export function VisitFailedView({
  visitId,
  syntheticQaAttempt = null,
  reason,
  failureCategory,
  inputMode,
}: Props) {
  const router = useRouter();
  const [submitting, startTransition] = useTransition();
  const [pending, setPending] = useState(false);

  const copy = failureCopyFor({
    failureCategory: (failureCategory ?? null) as
      | 'transient'
      | 'permanent'
      | 'provider_down'
      | null,
    reviewReason: reason,
    inputMode: inputMode ?? null,
  });
  const isPermanent = failureCategory === 'permanent';

  const onRetry = () => {
    setPending(true);
    startTransition(async () => {
      try {
        const r = await fetch(`/api/visits/${visitId}/retry`, {
          method: 'POST',
          ...(syntheticQaAttempt === null
            ? {}
            : {
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ expectedAttempt: syntheticQaAttempt }),
              }),
        });
        if (r.ok) {
          router.refresh();
          return;
        }
        let detail = `Retry failed (${r.status}).`;
        let code: string | undefined;
        try {
          const body = (await r.json()) as { error?: string; code?: string };
          if (body.error) detail = body.error;
          code = body.code;
        } catch {
          /* response wasn't JSON */
        }
        if (code === 'RETRY_BUDGET_EXHAUSTED') {
          toast.error('Retry limit reached', { description: detail });
        } else {
          toast.error('Could not retry', { description: detail });
        }
        setPending(false);
      } catch {
        toast.error('Network error', {
          description: 'Check your connection and try again.',
        });
        setPending(false);
      }
    });
  };

  const isRetrying = pending || submitting;
  const PrimaryIcon = copy.Icon;

  return (
    <div className="mx-auto flex max-w-xl flex-col items-center py-16 text-center sm:py-24">
      <div
        aria-hidden
        className="mb-8 inline-flex h-14 w-14 items-center justify-center rounded-2xl"
        style={{
          background: 'rgba(212,87,74,0.10)',
          border: '1px solid rgba(212,87,74,0.32)',
          color: 'var(--color-linear-danger)',
        }}
      >
        <PrimaryIcon className="h-6 w-6" aria-hidden />
      </div>

      <h2
        style={{
          margin: 0,
          fontFamily: 'var(--font-sans)',
          fontSize: 24,
          fontWeight: 500,
          letterSpacing: '-0.012em',
          color: 'var(--color-linear-text)',
        }}
      >
        {copy.headline}
      </h2>

      <p
        className="mt-3 max-w-md text-[14px] leading-relaxed"
        style={{ color: 'var(--color-linear-text-2)' }}
      >
        {reason ?? copy.body}
      </p>

      {copy.hint && (
        <p
          className="mt-2 max-w-md text-[12px] leading-relaxed"
          style={{ color: 'var(--color-linear-text-3)' }}
        >
          {copy.hint}
        </p>
      )}

      <div className="mt-10 flex items-center justify-center gap-3">
        {isPermanent && copy.ctaHref ? (
          <Link
            href={copy.ctaHref}
            className="qm-lin-btn-primary"
            style={{ textDecoration: 'none' }}
          >
            <Upload className="h-3.5 w-3.5" aria-hidden />
            {copy.ctaLabel}
          </Link>
        ) : (
          <button
            type="button"
            className="qm-lin-btn-primary"
            onClick={onRetry}
            disabled={isRetrying}
          >
            {isRetrying ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                Retrying…
              </>
            ) : (
              <>
                <RefreshCw className="h-3.5 w-3.5" aria-hidden />
                {copy.ctaLabel}
              </>
            )}
          </button>
        )}
        <Link
          href="/dashboard"
          className="qm-lin-btn"
          style={{ textDecoration: 'none' }}
        >
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
