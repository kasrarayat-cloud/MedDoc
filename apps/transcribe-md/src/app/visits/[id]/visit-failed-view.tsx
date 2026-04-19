'use client';

import { RefreshCw } from 'lucide-react';
import dynamic from 'next/dynamic';

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

/** Terminal failure screen. The "Try again" CTA just refreshes the
 *  route — the server will render the uploader again because audioKey
 *  stays set BUT the next upload PUT replaces it and re-enqueues. For
 *  a "re-run without re-upload" recovery, we'd need a separate button
 *  + API route; deferred until T-M4.5. */
export function VisitFailedView({ visitId, reason }: Props) {
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
          href={`/visits/${visitId}`}
          variant="primary"
          size="md"
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
          Try again
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
