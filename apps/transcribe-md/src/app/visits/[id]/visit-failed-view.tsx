'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2, RefreshCw } from 'lucide-react';
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
}

/** Terminal failure screen. The "Try again" CTA POSTs to
 *  /api/visits/[id]/retry, which re-enqueues the worker against the
 *  already-uploaded audio (no re-record needed) and resets status to
 *  QUEUED. router.refresh() then swaps the server-rendered view to
 *  ProcessingState because the fresh server read sees QUEUED again. */
export function VisitFailedView({ visitId, reason }: Props) {
  const router = useRouter();
  const [submitting, startTransition] = useTransition();
  const [pending, setPending] = useState(false);

  const onRetry = () => {
    setPending(true);
    startTransition(async () => {
      try {
        const r = await fetch(`/api/visits/${visitId}/retry`, {
          method: 'POST',
        });
        if (r.ok) {
          // Server-component refresh — visit row now reads QUEUED, so
          // page.tsx swaps VisitFailedView for ProcessingState.
          router.refresh();
          return;
        }
        // Surface the API's structured error to the user.
        let detail = `Retry failed (${r.status}).`;
        try {
          const body = (await r.json()) as { error?: string; code?: string };
          if (body.error) detail = body.error;
        } catch {
          /* response wasn't JSON; keep the generic detail */
        }
        toast.error('Could not retry', { description: detail });
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

  return (
    <div className="mx-auto flex max-w-xl flex-col items-center py-16 text-center sm:py-24">
      <div className="relative mb-10 h-56 w-56">
        <div
          aria-hidden
          className={cn(
            'pointer-events-none absolute inset-0 -z-10 rounded-full',
            // Amber halo instead of violet to signal failure without
            // swapping the whole orb palette.
            "bg-[radial-gradient(ellipse_at_center,rgba(245,158,11,0.35)_0%,rgba(245,158,11,0.08)_40%,transparent_72%)]",
            'orb-pulse'
          )}
          style={{ filter: 'blur(28px)' }}
        />
        <VioletOrb radius={1.1} state="processing" quiet reactive={0} />
      </div>

      <h2 className="type-h1 text-text-primary">Processing failed</h2>

      <p className="mt-3 max-w-md text-[14px] leading-relaxed text-text-tertiary">
        {reason ??
          'Something went wrong while generating your note. You can re-upload the audio to try again.'}
      </p>

      <div className="mt-10 flex items-center justify-center gap-3">
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
              Try again
            </>
          )}
        </SpecularButton>
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
