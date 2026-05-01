'use client';

// ============================================================================
// VisitFailedView — terminal-state UI for a FAILED visit row.
// ----------------------------------------------------------------------------
// Phase 5 — Linear V1 Faithful. Drops the VioletOrb cinematic and the
// clinician dual-theme branch. Renders a quiet danger-tinted icon
// block with a sage primary CTA for transient/provider/unknown
// retries and a `.qm-lin-btn` ghost "Back to dashboard". The retry
// semantics + failure categorization are unchanged.
// ============================================================================

import { useState, useTransition, type ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Cloud,
  FileX,
  Loader2,
  RefreshCw,
  Upload,
  WifiOff,
} from 'lucide-react';
import { toast } from 'sonner';

type VisitFailedViewTheme = 'legacy' | 'clinician';

interface Props {
  visitId: string;
  reason: string | null;
  /** One of 'transient' | 'permanent' | 'provider_down' (or null on
   *  pre-categorization rows). Drives icon + headline + CTA. */
  failureCategory?: string | null;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: VisitFailedViewTheme;
}

interface CategoryCopy {
  Icon: typeof WifiOff;
  headline: string;
  body: string;
  /** When set, the primary CTA is a navigation rather than the
   *  in-place /retry POST. Permanent failures point to /visits/new
   *  because the same audio will fail the same way. */
  ctaHref?: string;
  ctaLabel: string;
  /** Render an extra hint above the button (e.g. "wait 5 minutes"). */
  hint?: ReactNode;
}

function copyForCategory(failureCategory: string | null | undefined): CategoryCopy {
  switch (failureCategory) {
    case 'permanent':
      return {
        Icon: FileX,
        headline: "Couldn't process this audio",
        body:
          'The audio file may be corrupted or in an unsupported format. Please re-upload using MP3, WAV, M4A, or WebM.',
        ctaHref: '/visits/new',
        ctaLabel: 'Upload new audio',
      };
    case 'provider_down':
      return {
        Icon: Cloud,
        headline: 'Service temporarily unavailable',
        body:
          "Our transcription service is having an outage. We're aware and working on it. Please try again in 5–10 minutes.",
        ctaLabel: 'Try again',
        hint: 'Best to wait a few minutes before retrying.',
      };
    case 'transient':
      return {
        Icon: WifiOff,
        headline: 'Connection issue',
        body:
          "We had trouble reaching our transcription service. Try again — this usually works on the second attempt.",
        ctaLabel: 'Try again',
      };
    default:
      // Null / 'unknown' / pre-categorization — keep the original
      // generic copy so existing FAILED rows don't suddenly look
      // misclassified.
      return {
        Icon: RefreshCw,
        headline: 'Processing failed',
        body:
          'Something went wrong while generating your note. You can re-upload the audio to try again.',
        ctaLabel: 'Try again',
      };
  }
}

export function VisitFailedView({
  visitId,
  reason,
  failureCategory,
}: Props) {
  const router = useRouter();
  const [submitting, startTransition] = useTransition();
  const [pending, setPending] = useState(false);

  const copy = copyForCategory(failureCategory);
  const isPermanent = failureCategory === 'permanent';

  const onRetry = () => {
    setPending(true);
    startTransition(async () => {
      try {
        const r = await fetch(`/api/visits/${visitId}/retry`, {
          method: 'POST',
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
