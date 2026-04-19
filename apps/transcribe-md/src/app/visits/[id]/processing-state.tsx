'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { motion, AnimatePresence } from 'framer-motion';

import type { TranscribeVisitStatus } from '@prisma/client';

const VioletOrb = dynamic(
  () => import('@/components/violet-orb').then((m) => m.VioletOrb),
  { ssr: false, loading: () => <div className="h-64 w-64" /> }
);

interface StatusResponse {
  visitId: string;
  status: TranscribeVisitStatus;
  progressHint: string;
  needsReview: boolean;
  reviewReason: string | null;
}

interface ProcessingStateProps {
  visitId: string;
  initialStatus: TranscribeVisitStatus;
  initialHint: string;
}

const POLL_MS = 2000;

/** Processing screen while the worker walks through the pipeline.
 *  Polls /api/visits/[id]/status every 2s; when status flips to READY
 *  or FAILED (or SIGNED, unlikely here) the outer page re-reads on
 *  router.refresh() and renders the correct view. */
export function ProcessingState({
  visitId,
  initialStatus,
  initialHint,
}: ProcessingStateProps) {
  const router = useRouter();
  const [status, setStatus] = useState<TranscribeVisitStatus>(initialStatus);
  const [hint, setHint] = useState<string>(initialHint);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    pollingRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/visits/${visitId}/status`, {
          cache: 'no-store',
        });
        if (!res.ok) return;
        const data = (await res.json()) as StatusResponse;
        setStatus(data.status);
        setHint(data.progressHint);
        if (
          data.status === 'READY' ||
          data.status === 'FAILED' ||
          data.status === 'SIGNED'
        ) {
          if (pollingRef.current) clearInterval(pollingRef.current);
          // router.refresh re-runs the server page → dispatches on the
          // new status and renders the ready/failed view.
          router.refresh();
        }
      } catch {
        // Swallow transient network errors; the next tick will retry.
      }
    }, POLL_MS);
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [visitId, router]);

  return (
    <div className="mx-auto flex max-w-xl flex-col items-center py-16 text-center sm:py-24">
      <div className="relative mb-10 h-64 w-64 sm:h-72 sm:w-72">
        <div
          aria-hidden
          className="orb-pulse pointer-events-none absolute inset-0 -z-10 rounded-full"
          style={{
            background:
              'radial-gradient(ellipse at center, rgba(139,92,246,0.45) 0%, rgba(139,92,246,0.12) 40%, transparent 72%)',
            filter: 'blur(28px)',
          }}
        />
        <VioletOrb radius={1.35} state="processing" reactive={0.5} />
      </div>

      <motion.h2
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
        className="type-h1 text-text-primary"
      >
        Working on your note
      </motion.h2>

      <div className="mt-3 min-h-[1.5rem] max-w-md text-[15px] leading-relaxed text-text-tertiary">
        <AnimatePresence mode="wait">
          <motion.span
            key={status}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.25 }}
          >
            {hint}
          </motion.span>
        </AnimatePresence>
      </div>

      <div className="mt-10 w-full max-w-md">
        <PipelineStrip status={status} />
      </div>

      <p className="mt-10 text-[12px] text-text-muted">
        You can leave this page — your note will be waiting on the dashboard.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Visual strip showing which of the 6 layers is active.
// ---------------------------------------------------------------------------

const PIPELINE_ORDER: TranscribeVisitStatus[] = [
  'TRANSCRIBING',
  'EXTRACTING',
  'DRAFTING',
  'CRITIQUING',
  'POLISHING',
  'READY',
];

function PipelineStrip({ status }: { status: TranscribeVisitStatus }) {
  const currentIdx = PIPELINE_ORDER.indexOf(status);
  return (
    <div className="flex items-center gap-1.5">
      {PIPELINE_ORDER.map((s, i) => {
        const state =
          i < currentIdx ? 'done' : i === currentIdx ? 'active' : 'pending';
        return (
          <div
            key={s}
            className={
              state === 'done'
                ? 'h-1 flex-1 rounded-full bg-violet-500'
                : state === 'active'
                  ? 'h-1 flex-1 rounded-full bg-violet-400 animate-pulse'
                  : 'h-1 flex-1 rounded-full bg-bg-surface-3'
            }
            aria-label={s.toLowerCase()}
          />
        );
      })}
    </div>
  );
}
