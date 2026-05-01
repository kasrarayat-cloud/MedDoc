'use client';

// ============================================================================
// Processing state — Phase 5 (Linear V1).
// ----------------------------------------------------------------------------
// Keeps the T-M16.4 polling + retry semantics (2s interval, 10min warn,
// 30min stuck) and renders the visit's in-flight pipeline on the dark
// canvas. Centre stage shows a pulsing sage halo + breathing dot with
// a status sentence that crossfades through ("Listening" → "Drafting"
// → "Reviewing" → "Ready"). Right rail shows the 7-step pipeline
// ladder with a sage-tinted active row. The `theme` prop is preserved
// as a no-op for caller back-compat.
// ============================================================================

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import type { TranscribeVisitStatus } from '@prisma/client';
import { Ic } from '@/components/ui/icon';

type ProcessingStateTheme = 'legacy' | 'clinician';

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
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: ProcessingStateTheme;
}

const POLL_MS = 2000;
const WARN_AT_MIN = 10;
const STUCK_AT_MIN = 30;

type StageId =
  | 'TRANSCRIBING'
  | 'EXTRACTING'
  | 'DRAFTING'
  | 'CRITIQUING'
  | 'POLISHING'
  | 'AUTOMATING'
  | 'READY';

const STAGES: { id: StageId; title: string; blurb: string }[] = [
  { id: 'TRANSCRIBING', title: 'Transcribe', blurb: 'Deepgram Nova-3 · diarised turns' },
  { id: 'EXTRACTING', title: 'Understand', blurb: 'Structured entities + evidence quotes' },
  { id: 'DRAFTING', title: 'SOAP draft', blurb: 'Section-by-section composition' },
  { id: 'CRITIQUING', title: 'Review', blurb: 'Low-confidence + safety flags' },
  { id: 'POLISHING', title: 'Polish', blurb: 'Doctor-style conformance' },
  { id: 'AUTOMATING', title: 'Codes + Rx', blurb: 'ICD-10 / CPT / prescriptions' },
  { id: 'READY', title: 'Ready', blurb: 'Your draft is signable' },
];

const HEADLINE_FOR: Record<TranscribeVisitStatus, string> = {
  QUEUED: 'Queued',
  TRANSCRIBING: 'Listening',
  EXTRACTING: 'Understanding',
  DRAFTING: 'Drafting',
  CRITIQUING: 'Reviewing',
  POLISHING: 'Polishing',
  AUTOMATING: 'Coding',
  READY: 'Ready',
  FAILED: 'Failed',
  SIGNED: 'Signed',
};

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
  const startedAtRef = useRef<number>(0);

  // Capture the processing start time on mount (refs aren't allowed
  // to be initialised with impure expressions per the react-hooks
  // lint rule). Zero sentinel means "not yet initialised".
  useEffect(() => {
    if (startedAtRef.current === 0) startedAtRef.current = Date.now();
  }, []);

  useEffect(() => {
    pollingRef.current = setInterval(async () => {
      const elapsed = Math.floor((Date.now() - startedAtRef.current) / 60_000);
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
          router.refresh();
        }
      } catch {
        /* transient — next tick retries */
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
        toast.info(
          body.code === 'STILL_PROCESSING'
            ? 'Still processing'
            : 'Cannot retry this visit',
          {
            description:
              body.error ?? 'The worker is making progress — hold on a bit.',
          }
        );
        return;
      }
      if (!res.ok) {
        toast.error('Retry failed', {
          description: 'Please try again in a moment, or contact support.',
        });
        return;
      }
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

  const currentIdx = STAGES.findIndex((s) => s.id === (status as StageId));
  const showWarn = elapsedMin >= WARN_AT_MIN && elapsedMin < STUCK_AT_MIN;
  const showStuck = elapsedMin >= STUCK_AT_MIN;
  const headline = HEADLINE_FOR[status] ?? 'Processing';

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 380px',
        minHeight: 'calc(100vh - 120px)',
        gap: 0,
      }}
    >
      {/* Centre stage — pulsing sage halo + status sentence */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 40,
          gap: 28,
        }}
      >
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10.5,
            fontWeight: 500,
            letterSpacing: '0.07em',
            textTransform: 'uppercase',
            color: 'var(--color-linear-text-3)',
          }}
        >
          Drafting · in flight
        </div>
        <div style={{ position: 'relative', width: 96, height: 96 }}>
          <div
            className="qm-lin-mic-halo"
            aria-hidden
            style={{
              position: 'absolute',
              inset: -32,
              borderRadius: 999,
              background: 'var(--color-linear-sage-glow)',
            }}
          />
          <div
            className="qm-lin-mic-dot"
            style={{
              position: 'relative',
              width: 96,
              height: 96,
              borderRadius: 999,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'var(--color-linear-surface-1)',
              border: '1px solid var(--color-linear-sage)',
              boxShadow: '0 0 0 1px rgba(122,166,140,0.18)',
            }}
          >
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 999,
                background: 'var(--color-linear-sage)',
              }}
            />
          </div>
        </div>
        <div style={{ textAlign: 'center', maxWidth: 460 }}>
          <h1
            key={headline}
            style={{
              margin: 0,
              fontFamily: 'var(--font-sans)',
              fontSize: 28,
              fontWeight: 500,
              letterSpacing: '-0.015em',
              color: 'var(--color-linear-text)',
            }}
            className="qm-lin-fade-in"
          >
            {headline}
          </h1>
          <p
            style={{
              margin: '12px 0 0',
              fontSize: 14,
              color: 'var(--color-linear-text-2)',
              lineHeight: 1.55,
            }}
          >
            {hint || 'Hold tight — Quill is moving through the pipeline.'}
          </p>
          <p
            style={{
              marginTop: 14,
              fontSize: 11,
              fontFamily: 'var(--font-mono)',
              color: 'var(--color-linear-text-3)',
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
            }}
          >
            Elapsed {elapsedMin} min · leave the page and we&rsquo;ll finish in the background
          </p>
        </div>

        {showWarn && (
          <StatusBanner tone="warning" title="Taking longer than usual">
            Most notes finish in 3-5 minutes. We&apos;ll keep checking — you can
            also leave this page and come back later.
          </StatusBanner>
        )}
        {showStuck && (
          <StatusBanner tone="danger" title="Something may be wrong">
            Processing for {elapsedMin} minutes. You can retry, or contact
            support with visit{' '}
            <span style={{ fontFamily: 'var(--font-mono)' }}>{visitId}</span>.
            <div style={{ marginTop: 10 }}>
              <button
                type="button"
                onClick={onRetry}
                disabled={retrying}
                className="qm-lin-btn"
              >
                <Ic.sparkle width={12} height={12} />
                {retrying ? 'Retrying…' : 'Retry upload'}
              </button>
            </div>
          </StatusBanner>
        )}
      </div>

      {/* Right rail — pipeline ladder */}
      <aside
        style={{
          borderLeft: '1px solid var(--color-linear-hairline)',
          background: 'var(--color-linear-surface-1)',
          padding: 24,
          overflow: 'auto',
        }}
      >
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10.5,
            fontWeight: 500,
            letterSpacing: '0.07em',
            textTransform: 'uppercase',
            color: 'var(--color-linear-text-3)',
            marginBottom: 18,
          }}
        >
          Pipeline
        </div>
        <ol
          style={{
            listStyle: 'none',
            margin: 0,
            padding: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          {STAGES.map((stage, i) => {
            const state =
              currentIdx === -1
                ? 'pending'
                : i < currentIdx
                  ? 'done'
                  : i === currentIdx
                    ? 'active'
                    : 'pending';
            return (
              <StageRow
                key={stage.id}
                index={i + 1}
                title={stage.title}
                blurb={stage.blurb}
                state={state}
              />
            );
          })}
        </ol>
      </aside>
    </div>
  );
}

function StageRow({
  index,
  title,
  blurb,
  state,
}: {
  index: number;
  title: string;
  blurb: string;
  state: 'done' | 'active' | 'pending';
}) {
  // Linear V1: sage = active, sage-tint pill for done, neutral for
  // pending. No gradients; soft hairline borders.
  const fg =
    state === 'active'
      ? 'var(--color-linear-text)'
      : state === 'done'
        ? 'var(--color-linear-text-2)'
        : 'var(--color-linear-text-3)';
  const badgeBg =
    state === 'active'
      ? 'var(--color-linear-sage)'
      : state === 'done'
        ? 'var(--color-linear-sage-tint)'
        : 'var(--color-linear-surface-2)';
  const badgeColor =
    state === 'active'
      ? '#0d1611'
      : state === 'done'
        ? 'var(--color-linear-sage-bright)'
        : 'var(--color-linear-text-3)';
  return (
    <li
      style={{
        display: 'grid',
        gridTemplateColumns: '28px 1fr',
        gap: 12,
        padding: '10px 4px',
        borderRadius: 6,
        background:
          state === 'active' ? 'var(--color-linear-sage-tint)' : 'transparent',
      }}
    >
      <div
        style={{
          width: 26,
          height: 26,
          borderRadius: 999,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: badgeBg,
          border: `1px solid ${
            state === 'active'
              ? 'rgba(122,166,140,0.6)'
              : state === 'done'
                ? 'rgba(122,166,140,0.34)'
                : 'var(--color-linear-border)'
          }`,
          color: badgeColor,
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          fontWeight: 600,
        }}
      >
        {state === 'done' ? <Ic.check width={12} height={12} /> : index}
      </div>
      <div>
        <div
          style={{
            fontSize: 13.5,
            color: fg,
            fontWeight: state === 'active' ? 600 : 500,
          }}
        >
          {title}
          {state === 'active' && (
            <span
              style={{
                display: 'inline-block',
                marginLeft: 8,
                width: 6,
                height: 6,
                borderRadius: 999,
                background: 'var(--color-linear-sage)',
                verticalAlign: 'middle',
              }}
            />
          )}
        </div>
        <div
          style={{
            marginTop: 3,
            fontSize: 11.5,
            color: 'var(--color-linear-text-3)',
            fontFamily: 'var(--font-mono)',
            letterSpacing: '0.02em',
          }}
        >
          {blurb}
        </div>
      </div>
    </li>
  );
}

function StatusBanner({
  tone,
  title,
  children,
}: {
  tone: 'warning' | 'danger';
  title: string;
  children: React.ReactNode;
}) {
  const bgColor =
    tone === 'warning'
      ? 'rgba(212,164,55,0.10)'
      : 'rgba(212,87,74,0.10)';
  const borderColor =
    tone === 'warning'
      ? 'rgba(212,164,55,0.32)'
      : 'rgba(212,87,74,0.32)';
  const headColor =
    tone === 'warning'
      ? 'var(--color-linear-warning)'
      : 'var(--color-linear-danger)';

  return (
    <div
      role="status"
      style={{
        width: '100%',
        maxWidth: 460,
        padding: 14,
        borderRadius: 8,
        border: `1px solid ${borderColor}`,
        background: bgColor,
        color: headColor,
        fontSize: 12.5,
        lineHeight: 1.55,
        textAlign: 'left',
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 6 }}>{title}</div>
      <div style={{ color: 'var(--color-linear-text-2)' }}>{children}</div>
    </div>
  );
}
