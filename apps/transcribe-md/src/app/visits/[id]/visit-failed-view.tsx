'use client';

import { useState, useTransition, type ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import {
  Cloud,
  FileX,
  Loader2,
  RefreshCw,
  Upload,
  WifiOff,
} from 'lucide-react';
import dynamic from 'next/dynamic';
import { toast } from 'sonner';

import { SpecularButton } from '@/components/specular-button';
import { cn } from '@/lib/cn';

const VioletOrb = dynamic(
  () => import('@/components/violet-orb').then((m) => m.VioletOrb),
  { ssr: false, loading: () => <div className="h-48 w-48" /> }
);

interface Props {
  visitId: string;
  reason: string | null;
  /** One of 'transient' | 'permanent' | 'provider_down' (or null on
   *  pre-categorization rows). Drives icon + headline + CTA. */
  failureCategory?: string | null;
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

export function VisitFailedView({ visitId, reason, failureCategory }: Props) {
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
      <div className="relative mb-10 h-56 w-56">
        <div
          aria-hidden
          className={cn(
            'pointer-events-none absolute inset-0 -z-10 rounded-full',
            "bg-[radial-gradient(ellipse_at_center,rgba(245,158,11,0.35)_0%,rgba(245,158,11,0.08)_40%,transparent_72%)]",
            'orb-pulse'
          )}
          style={{ filter: 'blur(28px)' }}
        />
        <VioletOrb radius={1.1} state="processing" quiet reactive={0} />
      </div>

      <div className="mb-3 flex items-center gap-2">
        <PrimaryIcon className="h-5 w-5 text-amber-400" aria-hidden />
        <h2 className="type-h1 text-text-primary">{copy.headline}</h2>
      </div>

      <p className="mt-3 max-w-md text-[14px] leading-relaxed text-text-tertiary">
        {reason ?? copy.body}
      </p>

      {copy.hint && (
        <p className="mt-2 max-w-md text-[12px] leading-relaxed text-text-muted">
          {copy.hint}
        </p>
      )}

      <div className="mt-10 flex items-center justify-center gap-3">
        {isPermanent && copy.ctaHref ? (
          <SpecularButton href={copy.ctaHref} variant="primary" size="md">
            <Upload className="h-3.5 w-3.5" aria-hidden />
            {copy.ctaLabel}
          </SpecularButton>
        ) : (
          <SpecularButton
            variant="primary"
            size="md"
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
          </SpecularButton>
        )}
        <SpecularButton
          href="/dashboard"
          variant="secondary"
          size="md"
          sweep={false}
        >
          Back to dashboard
        </SpecularButton>
      </div>
    </div>
  );
}
