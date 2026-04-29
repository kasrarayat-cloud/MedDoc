'use client';

// ============================================================================
// Processing state — app-redesign-v1 cinematic (HANDOFF §2.3 Gate 10).
// ----------------------------------------------------------------------------
// Keeps the T-M16.4 polling + retry semantics (2s interval, 10min warn,
// 30min stuck) and swaps the visual for the handoff's 7-step pipeline
// ladder + LiveOrb. Status → hint text streams in under the orb; the
// ladder highlights the active stage with a moving violet rail.
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the dark LiveOrb cinematic
// rendering. Visit-detail (Clinician) drops the LiveOrb (per CL-5)
// and renders the .qm-cl-ai-status crossfade band + soft pipeline
// ladder on cream — same polling + status-text streaming, restrained
// motion idiom.
// ============================================================================

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import type { TranscribeVisitStatus } from '@prisma/client';
import { Ic } from '@/components/ui/icon';
import { LiveOrb } from '@/components/recording/live-orb';

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

export function ProcessingState({
  visitId,
  initialStatus,
  initialHint,
  theme = 'legacy',
}: ProcessingStateProps) {
  const router = useRouter();
  const [status, setStatus] = useState<TranscribeVisitStatus>(initialStatus);
  const [hint, setHint] = useState<string>(initialHint);
  const [elapsedMin, setElapsedMin] = useState(0);
  const [retrying, setRetrying] = useState(false);
  const [reducedMotion, setReducedMotion] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });
  const isClinician = theme === 'clinician';
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedAtRef = useRef<number>(0);

  // Capture the processing start time on mount (refs aren't allowed
  // to be initialised with impure expressions per the react-hooks
  // lint rule). Zero sentinel means "not yet initialised".
  useEffect(() => {
    if (startedAtRef.current === 0) startedAtRef.current = Date.now();
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = () => setReducedMotion(mq.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
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

  if (isClinician) {
    return (
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 380px',
          minHeight: 'calc(100vh - 120px)',
          gap: 0,
        }}
      >
        {/* Centre stage — restrained "drafting" moment with sage halo
            + breathing mic dot. Per CL-5: no LiveOrb in Clinician. */}
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
          <div className="qm-cl-eyebrow">Drafting · in flight</div>
          <div style={{ position: 'relative', width: 96, height: 96 }}>
            <div
              className="qm-cl-halo"
              style={{ position: 'absolute', inset: -32 }}
              aria-hidden
            />
            <div
              className="qm-cl-halo qm-cl-halo-delayed"
              style={{ position: 'absolute', inset: -32 }}
              aria-hidden
            />
            <div
              className="qm-cl-mic-dot"
              style={{
                position: 'relative',
                width: 96,
                height: 96,
                borderRadius: 999,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'var(--cream-card, #FFFCF5)',
                border: '1px solid var(--sage, #7AA68C)',
              }}
            >
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: 999,
                  background: 'var(--sage, #7AA68C)',
                }}
              />
            </div>
          </div>
          <div style={{ textAlign: 'center', maxWidth: 460 }}>
            <h1
              className="qm-cl-serif"
              style={{
                margin: 0,
                fontSize: 32,
                fontWeight: 500,
                letterSpacing: '-0.015em',
                color: 'var(--ink, #2B2620)',
              }}
            >
              Working on your{' '}
              <em
                style={{
                  color: 'var(--sage-deep, #2F5040)',
                  fontStyle: 'italic',
                }}
              >
                note
              </em>
            </h1>
            <p
              style={{
                margin: '12px 0 0',
                fontSize: 14,
                color: 'var(--ink-2, #5C544A)',
                lineHeight: 1.55,
              }}
            >
              {hint || 'Hold tight — Quill is moving through the pipeline.'}
            </p>
            <p
              style={{
                marginTop: 14,
                fontSize: 11.5,
                fontFamily: 'var(--mono, ui-monospace)',
                color: 'var(--ink-4, #B5AE9F)',
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
              }}
            >
              Elapsed {elapsedMin} min · leave the page and we&rsquo;ll finish in the background
            </p>
          </div>

          {showWarn && (
            <StatusBanner
              tone="amber"
              title="Taking longer than usual"
              theme={theme}
            >
              Most notes finish in 3-5 minutes. We&apos;ll keep checking — you can
              also leave this page and come back later.
            </StatusBanner>
          )}
          {showStuck && (
            <StatusBanner
              tone="coral"
              title="Something may be wrong"
              theme={theme}
            >
              Processing for {elapsedMin} minutes. You can retry, or contact
              support with visit{' '}
              <span style={{ fontFamily: 'var(--mono, ui-monospace)' }}>
                {visitId}
              </span>
              .
              <div style={{ marginTop: 10 }}>
                <button
                  type="button"
                  onClick={onRetry}
                  disabled={retrying}
                  className="qm-cl-btn qm-cl-btn-soft"
                  style={{
                    fontSize: 12.5,
                    padding: '7px 14px',
                  }}
                >
                  <Ic.sparkle width={12} height={12} />
                  {retrying ? 'Retrying…' : 'Retry upload'}
                </button>
              </div>
            </StatusBanner>
          )}
        </div>

        {/* Right rail — pipeline ladder, cream-2 surface */}
        <aside
          style={{
            borderLeft: '1px solid var(--line, rgba(43, 38, 32, 0.08))',
            background: 'var(--cream-2, #F2EDE3)',
            padding: 24,
            overflow: 'auto',
          }}
        >
          <div className="qm-cl-eyebrow" style={{ marginBottom: 18 }}>
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
                  theme={theme}
                />
              );
            })}
          </ol>
        </aside>
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 380px',
        minHeight: 'calc(100vh - 120px)',
        gap: 0,
      }}
    >
      {/* Centre stage — orb + status text */}
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
        <div className="qm-sectlabel">§ Drafting · in flight</div>
        <LiveOrb paused={false} reducedMotion={reducedMotion} />
        <div
          style={{
            textAlign: 'center',
            maxWidth: 460,
          }}
        >
          <h1
            className="qm-serif"
            style={{
              margin: 0,
              fontSize: 32,
              fontWeight: 400,
              letterSpacing: '-0.02em',
              color: 'var(--fg)',
            }}
          >
            Working on your <em style={{ color: 'var(--accent-bright)' }}>note</em>
          </h1>
          <p
            style={{
              margin: '12px 0 0',
              fontSize: 14,
              color: 'var(--fg-3)',
              lineHeight: 1.55,
            }}
          >
            {hint || 'Hold tight — the worker is routing through the pipeline.'}
          </p>
          <p
            style={{
              marginTop: 12,
              fontSize: 11.5,
              fontFamily: 'var(--mono)',
              color: 'var(--fg-4)',
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
            }}
          >
            Elapsed {elapsedMin} min · leave the page and we\u2019ll finish in the background
          </p>
        </div>

        {showWarn && (
          <StatusBanner tone="amber" title="Taking longer than usual" theme={theme}>
            Most notes finish in 3-5 minutes. We&apos;ll keep checking — you can
            also leave this page and come back later.
          </StatusBanner>
        )}
        {showStuck && (
          <StatusBanner tone="coral" title="Something may be wrong" theme={theme}>
            Processing for {elapsedMin} minutes. You can retry, or contact
            support with visit{' '}
            <span style={{ fontFamily: 'var(--mono)' }}>{visitId}</span>.
            <div style={{ marginTop: 10 }}>
              <button
                type="button"
                onClick={onRetry}
                disabled={retrying}
                className="qm-btn qm-btn-ghost qm-btn-sm"
                style={{ color: 'var(--coral)' }}
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
          borderLeft: '1px solid var(--line)',
          background: 'rgba(12,10,22,0.4)',
          padding: 24,
          overflow: 'auto',
        }}
      >
        <div className="qm-sectlabel" style={{ marginBottom: 18 }}>
          § Pipeline
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
                theme={theme}
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
  theme,
}: {
  index: number;
  title: string;
  blurb: string;
  state: 'done' | 'active' | 'pending';
  theme: ProcessingStateTheme;
}) {
  const isClinician = theme === 'clinician';

  if (isClinician) {
    // Clinician palette: sage = active, sage-deep ink for done with
    // sage-tint pill, ink-4 for pending. No gradients; soft pill chips.
    const fg =
      state === 'active'
        ? 'var(--ink, #2B2620)'
        : state === 'done'
          ? 'var(--ink-2, #5C544A)'
          : 'var(--ink-4, #B5AE9F)';
    const badgeBg =
      state === 'active'
        ? 'var(--sage, #7AA68C)'
        : state === 'done'
          ? 'var(--sage-tint, rgba(122, 166, 140, 0.14))'
          : 'var(--cream-card, #FFFCF5)';
    const badgeColor =
      state === 'active'
        ? '#FFFCF5'
        : state === 'done'
          ? 'var(--sage-deep, #2F5040)'
          : 'var(--ink-4, #B5AE9F)';
    return (
      <li
        style={{
          display: 'grid',
          gridTemplateColumns: '28px 1fr',
          gap: 12,
          padding: '10px 4px',
          borderRadius: 8,
          background:
            state === 'active'
              ? 'var(--sage-tint, rgba(122, 166, 140, 0.14))'
              : 'transparent',
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
                ? 'var(--sage-deep, #2F5040)'
                : state === 'done'
                  ? 'rgba(122, 166, 140, 0.34)'
                  : 'var(--line, rgba(43, 38, 32, 0.08))'
            }`,
            color: badgeColor,
            fontFamily: 'var(--mono, ui-monospace)',
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
                  background: 'var(--sage-deep, #2F5040)',
                  verticalAlign: 'middle',
                }}
              />
            )}
          </div>
          <div
            style={{
              marginTop: 3,
              fontSize: 11.5,
              color: 'var(--ink-3, #8A8278)',
              fontFamily: 'var(--mono, ui-monospace)',
              letterSpacing: '0.02em',
            }}
          >
            {blurb}
          </div>
        </div>
      </li>
    );
  }

  const fg =
    state === 'active'
      ? 'var(--fg)'
      : state === 'done'
        ? 'var(--fg-2)'
        : 'var(--fg-4)';
  const badgeBg =
    state === 'active'
      ? 'linear-gradient(135deg, #A87CFF, #6B3FD9)'
      : state === 'done'
        ? 'rgba(110, 231, 183, 0.18)'
        : 'rgba(255,255,255,0.03)';
  const badgeColor =
    state === 'active'
      ? '#fff'
      : state === 'done'
        ? 'var(--mint)'
        : 'var(--fg-4)';
  return (
    <li
      style={{
        display: 'grid',
        gridTemplateColumns: '28px 1fr',
        gap: 12,
        padding: '10px 4px',
        borderRadius: 8,
        background:
          state === 'active' ? 'rgba(139,92,255,0.05)' : 'transparent',
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
              ? 'rgba(139,92,255,0.4)'
              : state === 'done'
                ? 'rgba(110,231,183,0.3)'
                : 'var(--line)'
          }`,
          color: badgeColor,
          fontFamily: 'var(--mono)',
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
              className="qm-pulse"
              style={{
                display: 'inline-block',
                marginLeft: 8,
                width: 6,
                height: 6,
                borderRadius: 999,
                background: 'var(--accent-bright)',
                verticalAlign: 'middle',
              }}
            />
          )}
        </div>
        <div
          style={{
            marginTop: 3,
            fontSize: 11.5,
            color: 'var(--fg-4)',
            fontFamily: 'var(--mono)',
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
  theme,
}: {
  tone: 'amber' | 'coral';
  title: string;
  children: React.ReactNode;
  theme: ProcessingStateTheme;
}) {
  const isClinician = theme === 'clinician';
  if (isClinician) {
    // Soft tinted card on cream — same role="status" semantics, soft
    // palette. amber for "taking longer", coral for "may be wrong".
    const tintBg =
      tone === 'amber'
        ? 'var(--amber-tint, rgba(212, 165, 116, 0.18))'
        : 'var(--coral-tint, rgba(201, 123, 110, 0.16))';
    const tintBorder =
      tone === 'amber'
        ? 'rgba(212, 165, 116, 0.34)'
        : 'rgba(201, 123, 110, 0.34)';
    const headColor =
      tone === 'amber'
        ? 'var(--amber-deep, #7A4F1F)'
        : 'var(--coral-deep, #7A3329)';
    return (
      <div
        role="status"
        style={{
          width: '100%',
          maxWidth: 460,
          padding: 14,
          borderRadius: 12,
          border: `1px solid ${tintBorder}`,
          background: tintBg,
          color: headColor,
          fontSize: 12.5,
          lineHeight: 1.55,
          textAlign: 'left',
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: 6 }}>{title}</div>
        <div style={{ color: 'var(--ink-2, #5C544A)' }}>{children}</div>
      </div>
    );
  }

  return (
    <div
      role="status"
      style={{
        width: '100%',
        maxWidth: 460,
        padding: 14,
        borderRadius: 12,
        border: `1px solid var(--${tone})55`,
        background: `var(--${tone})0a`,
        color: `var(--${tone})`,
        fontSize: 12.5,
        lineHeight: 1.55,
        textAlign: 'left',
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 6 }}>{title}</div>
      <div style={{ color: 'var(--fg-2)' }}>{children}</div>
    </div>
  );
}
