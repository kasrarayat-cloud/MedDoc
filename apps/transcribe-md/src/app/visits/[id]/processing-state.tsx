'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

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

/** Elapsed-time thresholds for the T-M16.4 stuck-job UI (H13).
 *  Healthy pipeline completes in 3-5 min; 10 min is mildly unusual,
 *  30 min means something is genuinely off (the worker's own per-job
 *  timeout is 15 min × 3 attempts = 45 min worst-case — by 30 min we're
 *  either mid-retry-attempt-2 or the worker is wedged). */
const WARN_AT_MIN = 10;
const STUCK_AT_MIN = 30;

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
  const [elapsedMin, setElapsedMin] = useState(0);
  const [retrying, setRetrying] = useState(false);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Track elapsed time in a ref so the interval closure can read it
  // without adding it to useEffect's dep list (which would restart
  // the interval every tick).
  const startedAtRef = useRef<number>(Date.now());

  useEffect(() => {
    pollingRef.current = setInterval(async () => {
      // Update elapsed on every tick, regardless of fetch outcome.
      const elapsed = Math.floor(
        (Date.now() - startedAtRef.current) / 60_000
      );
      setElapsedMin(elapsed);

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

  async function onRetry() {
    setRetrying(true);
    try {
      const res = await fetch(`/api/visits/${visitId}/retry`, {
        method: 'POST',
      });
      if (res.status === 409) {
        const body = (await res.json().catch(() => ({}))) as {
          code?: string;
          error?: string;
        };
        if (body.code === 'STILL_PROCESSING') {
          toast.info('Still processing', {
            description:
              body.error ?? 'The worker is making progress — hold on a bit.',
          });
        } else {
          toast.error('Cannot retry this visit', {
            description: body.error ?? 'This visit is no longer retryable.',
          });
        }
        return;
      }
      if (!res.ok) {
        toast.error('Retry failed', {
          description: 'Please try again in a moment, or contact support.',
        });
        return;
      }
      // Successful retry — reset the timer so banners don't re-fire
      // instantly, and let the next poll tick pick up the new status.
      startedAtRef.current = Date.now();
      setElapsedMin(0);
      toast.success('Retry queued', {
        description: 'We sent the visit back through the pipeline.',
      });
    } catch {
      toast.error('Network error', { description: 'Please try again.' });
    } finally {
      setRetrying(false);
    }
  }

  const showWarn = elapsedMin >= WARN_AT_MIN && elapsedMin < STUCK_AT_MIN;
  const showStuck = elapsedMin >= STUCK_AT_MIN;

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

      {showWarn && (
        <div className="mt-8 w-full max-w-md rounded-lg border border-amber-500/40 bg-amber-500/5 p-4 text-left">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
            <div>
              <div className="text-[13px] font-medium text-amber-200">
                Taking longer than usual
              </div>
              <p className="mt-1 text-[12px] leading-relaxed text-amber-200/80">
                Most notes finish in 3-5 minutes. We&apos;ll keep
                checking — you can also leave this page and come back
                later.
              </p>
            </div>
          </div>
        </div>
      )}

      {showStuck && (
        <div className="mt-8 w-full max-w-md rounded-lg border border-red-500/50 bg-red-500/5 p-4 text-left">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
            <div className="flex-1">
              <div className="text-[13px] font-medium text-red-200">
                Something may be wrong
              </div>
              <p className="mt-1 text-[12px] leading-relaxed text-red-200/80">
                Your visit has been processing for {elapsedMin} minutes,
                which is well past normal. You can try re-running it,
                or contact support with the visit ID below.
              </p>
              <div className="mt-2 font-mono text-[11px] text-red-200/70 break-all">
                visit {visitId}
              </div>
              <button
                type="button"
                onClick={onRetry}
                disabled={retrying}
                className="mt-3 inline-flex items-center gap-2 rounded-lg border border-red-400/50 bg-red-500/10 px-3 py-1.5 text-[12px] font-medium text-red-100 hover:bg-red-500/15 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <RefreshCw
                  className={
                    retrying ? 'h-3.5 w-3.5 animate-spin' : 'h-3.5 w-3.5'
                  }
                />
                {retrying ? 'Retrying…' : 'Retry upload'}
              </button>
            </div>
          </div>
        </div>
      )}

      <p className="mt-10 text-[12px] text-text-muted">
        You can leave this page — your note will be waiting on the dashboard.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Visual strip showing which layer is active. 7 segments now that T-M6
// added AUTOMATING between POLISHING and READY.
// ---------------------------------------------------------------------------

const PIPELINE_ORDER: TranscribeVisitStatus[] = [
  'TRANSCRIBING',
  'EXTRACTING',
  'DRAFTING',
  'CRITIQUING',
  'POLISHING',
  'AUTOMATING',
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
