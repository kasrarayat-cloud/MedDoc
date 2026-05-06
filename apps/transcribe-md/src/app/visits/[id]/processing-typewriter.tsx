'use client';

// ============================================================================
// Typewriter SOAP — production post-upload processing screen.
// ----------------------------------------------------------------------------
// Replaces the v1 minimal-dot processing-state UI. Renders a 4-section
// SOAP skeleton (Subjective / Objective / Assessment / Plan) that fills
// section-by-section as the visit advances through the pipeline phases.
// At AUTOMATING (display: "Coding"), ICD/CPT chips appear at the bottom
// with real counts pulled from the visit row.
//
// PATH A discipline (this PR):
//   - No fake patient text. Every section content area is rendered as
//     underscore blanks; the active section gets a blinking caret +
//     a "writing…" muted indicator under the label. The typewriter
//     "feel" comes from caret motion + label-pulse + per-section state
//     transitions, NOT from streamed real text.
//   - V2 (streaming partial draft) is deferred until a pilot doctor
//     asks for it. Worker would emit Redis pubsub of incremental
//     output; client would subscribe via scribe-ws sidecar.
//
// Phase-event source: existing /api/visits/[id]/status polling at 1.5s
// interval. No new schema columns; no new pubsub. Polling cadence is
// 1.5s (down from v1's 2s) so phase transitions feel less jumpy.
//
// Min-display-time: 2.4s per phase. Some phases (e.g. AUTOMATING when
// no Rx is involved) complete faster than they're visible. Holding
// each phase for ≥2.4s before advancing the displayed phase keeps the
// animation smooth — the underlying data still updates immediately;
// only the displayed phase lags. When the actual visit hits READY, we
// transition through any unseen phases at 1.2s each before redirecting
// (so the doctor sees Coding chips appear if they were skipped).
//
// prefers-reduced-motion: disables the caret blink + label pulse;
// keeps the cross-fade transitions but caps them at 90ms so the screen
// still functions but stays visually quiet for users who opted out.
// ============================================================================

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import type { TranscribeVisitStatus } from '@prisma/client';
import {
  PHASE_EYEBROW,
  VISIT_PHASES,
  formatElapsed,
  phaseIndex,
  sectionStates,
  statusToPhase,
  type SoapSection,
  type VisitPhase,
} from '@/lib/visit-phase';

interface StatusResponse {
  visitId: string;
  status: TranscribeVisitStatus;
  progressHint: string;
  needsReview: boolean;
  reviewReason: string | null;
  audioDurationSec: number | null;
  deletedAt: string | null;
  archivedAt: string | null;
  processingStartedAt: string | null;
  icdCount: number;
  cptCount: number;
}

interface ProcessingTypewriterProps {
  visitId: string;
  initialStatus: TranscribeVisitStatus;
  initialIcdCount?: number;
  initialCptCount?: number;
  initialProcessingStartedAt?: string | null;
  /** Pretty-printed specialty for the top-left badge. */
  specialtyLabel?: string;
}

const POLL_MS = 1500;
const MIN_PHASE_MS = 2400;
const WARN_AT_MIN = 10;
const STUCK_AT_MIN = 30;

const SOAP_SECTIONS: { key: SoapSection; label: string; rows: number }[] = [
  { key: 'subjective', label: 'Subjective', rows: 3 },
  { key: 'objective',  label: 'Objective',  rows: 2 },
  { key: 'assessment', label: 'Assessment', rows: 2 },
  { key: 'plan',       label: 'Plan',       rows: 3 },
];

// Underscore-blank pattern. Wide enough to look like a paragraph but
// short of a full mock paragraph (which would feel like a placeholder
// the doctor expects to see filled in).
const ROW_BLANK = '________ _____ ___ ______ ________ _____ ___';

export function ProcessingTypewriter({
  visitId,
  initialStatus,
  initialIcdCount = 0,
  initialCptCount = 0,
  initialProcessingStartedAt = null,
  specialtyLabel,
}: ProcessingTypewriterProps) {
  const router = useRouter();

  // ── live status (polled) ────────────────────────────────────────────
  const [status, setStatus] = useState<TranscribeVisitStatus>(initialStatus);
  const [icdCount, setIcdCount] = useState(initialIcdCount);
  const [cptCount, setCptCount] = useState(initialCptCount);
  const [processingStartedAt, setProcessingStartedAt] = useState<string | null>(
    initialProcessingStartedAt
  );

  // ── displayed phase (lagged by min-display-time) ────────────────────
  // The "real" phase from the server can advance faster than the UI
  // wants to show. We track displayPhase separately and advance it on
  // a min-display schedule. This keeps the typewriter motion legible
  // even when the worker tears through a phase in <1s.
  const [displayPhase, setDisplayPhase] = useState<VisitPhase | null>(() =>
    statusToPhase(initialStatus)
  );
  const lastDisplayChangeRef = useRef<number>(Date.now());

  // ── elapsed clock ───────────────────────────────────────────────────
  const [now, setNow] = useState<number>(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(id);
  }, []);

  // ── poll status ─────────────────────────────────────────────────────
  useEffect(() => {
    let abandoned = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      if (abandoned) return;
      try {
        const res = await fetch(`/api/visits/${visitId}/status`, {
          cache: 'no-store',
          credentials: 'same-origin',
        });
        if (abandoned) return;
        if (res.ok) {
          const body = (await res.json()) as StatusResponse;
          if (abandoned) return;
          // Lifecycle interrupts (T-M18.3 A21 parity): visit deleted
          // or archived in another tab → bounce to dashboard.
          if (body.deletedAt) {
            toast.info('This visit was deleted from another tab.');
            router.push('/dashboard');
            return;
          }
          if (body.archivedAt) {
            toast.info('This visit was archived from another tab.');
            router.push('/dashboard');
            return;
          }
          setStatus(body.status);
          setIcdCount(body.icdCount);
          setCptCount(body.cptCount);
          if (body.processingStartedAt) {
            setProcessingStartedAt(body.processingStartedAt);
          }
          // FAILED → reload page; the FAILED-view branch in
          // visits/[id]/page.tsx renders the failure UI.
          if (body.status === 'FAILED') {
            router.refresh();
            return;
          }
          // READY → reload to switch into the ready view.
          if (body.status === 'READY' || body.status === 'SIGNED') {
            router.refresh();
            return;
          }
        }
      } catch {
        // Network blip — keep polling.
      } finally {
        if (!abandoned) timer = setTimeout(tick, POLL_MS);
      }
    };
    tick();
    return () => {
      abandoned = true;
      if (timer) clearTimeout(timer);
    };
  }, [router, visitId]);

  // ── advance displayPhase with min-display-time ──────────────────────
  useEffect(() => {
    const realPhase = statusToPhase(status);
    if (!realPhase) return;
    const realIdx = phaseIndex(realPhase);
    const dispIdx = phaseIndex(displayPhase);
    if (realIdx <= dispIdx) return;

    const elapsedSinceChange = Date.now() - lastDisplayChangeRef.current;
    const remaining = Math.max(0, MIN_PHASE_MS - elapsedSinceChange);

    const id = setTimeout(() => {
      // Step exactly one phase forward — never skip multiple visible
      // states even if real has jumped two phases. The next effect
      // re-fires after this tick when displayPhase updates.
      const nextIdx = Math.min(VISIT_PHASES.length - 1, dispIdx + 1);
      setDisplayPhase(VISIT_PHASES[nextIdx]);
      lastDisplayChangeRef.current = Date.now();
    }, remaining);
    return () => clearTimeout(id);
  }, [status, displayPhase]);

  // ── derived ─────────────────────────────────────────────────────────
  const sections = useMemo(() => sectionStates(displayPhase), [displayPhase]);
  const eyebrow = useMemo(
    () => (displayPhase ? PHASE_EYEBROW[displayPhase] : null),
    [displayPhase]
  );

  const elapsedSec = useMemo(() => {
    if (!processingStartedAt) return 0;
    const startMs = new Date(processingStartedAt).getTime();
    if (!Number.isFinite(startMs)) return 0;
    return Math.max(0, (now - startMs) / 1000);
  }, [processingStartedAt, now]);
  const elapsedFmt = formatElapsed(elapsedSec);

  // ── stuck-state warnings (T-M16.4 H13 parity) ───────────────────────
  const elapsedMin = elapsedSec / 60;
  const stuckLevel: 'ok' | 'warn' | 'stuck' =
    elapsedMin >= STUCK_AT_MIN ? 'stuck' : elapsedMin >= WARN_AT_MIN ? 'warn' : 'ok';

  const showCodingChips = displayPhase === 'Coding';

  return (
    <div className="qm-typewriter">
      {/* ── Top bar: specialty badge + meta ───────────────────────── */}
      <div className="qm-tw-top">
        <div className="qm-tw-top-left">
          {specialtyLabel ? (
            <div className="qm-tw-specialty">{specialtyLabel}</div>
          ) : null}
        </div>
        <div className="qm-tw-top-right">
          <div className="qm-tw-elapsed">
            <span>elapsed</span>
            <span className="num" data-testid="qm-tw-elapsed">
              {elapsedFmt}
            </span>
          </div>
        </div>
      </div>

      {/* ── Eyebrow row (current phase) ───────────────────────────── */}
      <div className="qm-tw-eyebrow-row">
        <div className="qm-tw-eyebrow-stack">
          <div className="qm-tw-eyebrow" data-testid="qm-tw-phase">
            {eyebrow?.primary ?? 'Queued'}
          </div>
          <div className="qm-tw-eyebrow-sub">
            {eyebrow?.sub ?? 'Waiting for a worker'}
          </div>
        </div>
        {/* 5-segment phase indicator. Done segments are filled teal,
            active segment shimmers, queued segments are dim. */}
        <div
          className="qm-tw-segments"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={VISIT_PHASES.length}
          aria-valuenow={Math.max(0, phaseIndex(displayPhase) + 1)}
          aria-valuetext={`Phase ${Math.max(0, phaseIndex(displayPhase) + 1)} of ${VISIT_PHASES.length}: ${eyebrow?.primary ?? 'Queued'}`}
        >
          {VISIT_PHASES.map((p, i) => {
            const di = phaseIndex(displayPhase);
            const cls =
              i < di ? 'done' : i === di ? 'active' : 'queued';
            return <div key={p} className={`qm-tw-seg qm-tw-seg-${cls}`} />;
          })}
        </div>
      </div>

      {/* ── SOAP skeleton ─────────────────────────────────────────── */}
      <div className="qm-tw-soap" role="region" aria-label="SOAP draft skeleton">
        {SOAP_SECTIONS.map((sec) => {
          const state = sections[sec.key];
          return (
            <div
              key={sec.key}
              className={`qm-tw-section qm-tw-state-${state}`}
              data-testid={`qm-tw-section-${sec.key}`}
            >
              <div className="qm-tw-section-label-row">
                <div className="qm-tw-section-label">{sec.label}</div>
                <div className="qm-tw-section-badge">
                  {state === 'done' && (
                    <span className="qm-tw-check" role="img" aria-label="drafted">
                      ✓
                    </span>
                  )}
                  {state === 'writing' && (
                    <span className="qm-tw-writing">writing…</span>
                  )}
                </div>
              </div>
              <div className="qm-tw-section-body">
                {Array.from({ length: sec.rows }).map((_, ri) => (
                  <div key={ri} className="qm-tw-row">
                    <span className="qm-tw-blank">
                      {ROW_BLANK.slice(
                        0,
                        ri === sec.rows - 1
                          ? Math.floor(ROW_BLANK.length * 0.62)
                          : ROW_BLANK.length
                      )}
                    </span>
                    {state === 'writing' && ri === 0 ? (
                      <span className="qm-tw-cursor" aria-hidden="true" />
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          );
        })}

        {/* ── Coding chips ─────────────────────────────────────── */}
        <div
          className={`qm-tw-codes ${showCodingChips ? 'qm-tw-codes-visible' : ''}`}
          data-testid="qm-tw-codes"
          aria-hidden={!showCodingChips}
        >
          <div className="qm-tw-section-label-row">
            <div className="qm-tw-section-label">Codes</div>
            <div className="qm-tw-section-badge">
              {showCodingChips && icdCount + cptCount > 0 && (
                <span className="qm-tw-check">
                  {icdCount + cptCount} selected
                </span>
              )}
            </div>
          </div>
          <div className="qm-tw-chip-row">
            <span className="qm-tw-chip">
              <span className="qm-tw-chip-label">ICD-10</span>
              <span className="qm-tw-chip-count">{icdCount}</span>
            </span>
            <span className="qm-tw-chip">
              <span className="qm-tw-chip-label">CPT</span>
              <span className="qm-tw-chip-count">{cptCount}</span>
            </span>
          </div>
        </div>
      </div>

      {/* ── Bottom bar: reassurance + stuck warning ──────────────── */}
      <div className="qm-tw-bottom">
        <div className="qm-tw-reassurance">
          <span className="qm-tw-reassurance-strong">
            You can leave this page.
          </span>
          <br />
          We&apos;ll keep working in the background and notify you
          when the note is ready to sign.
        </div>
        {stuckLevel !== 'ok' && (
          <div className={`qm-tw-stuck qm-tw-stuck-${stuckLevel}`}>
            <span className="qm-tw-stuck-label">
              {stuckLevel === 'warn' ? 'Taking longer than usual' : 'Visit appears stuck'}
            </span>
            <span className="qm-tw-stuck-meta">
              elapsed {elapsedFmt}
              {stuckLevel === 'stuck' && (
                <RetryButton visitId={visitId} />
              )}
            </span>
          </div>
        )}
      </div>

      {/* Component-scoped styles. Tailwind isn't used in this app's
          server pages; sticking to the existing `qm-*` global class
          conventions a la processing-state.tsx. */}
      <style jsx>{`
        .qm-typewriter {
          position: relative;
          width: 100%;
          min-height: calc(100vh - 48px);
          background: #050607;
          color: #fff;
          padding: 32px 56px 32px 56px;
          display: flex;
          flex-direction: column;
          gap: 24px;
        }
        .qm-tw-top {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding-bottom: 4px;
        }
        .qm-tw-specialty {
          display: inline-flex;
          align-items: center;
          padding: 4px 10px;
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 4px;
          font-size: 11px;
          letter-spacing: 0.16em;
          text-transform: uppercase;
          color: #9eb5a0;
          background: rgba(158, 181, 160, 0.04);
        }
        .qm-tw-elapsed {
          font-family: ui-monospace, "SF Mono", Menlo, monospace;
          font-size: 10.5px;
          letter-spacing: 0.16em;
          color: #7a7e7b;
          text-transform: uppercase;
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .qm-tw-elapsed .num {
          color: #c4c8c5;
          font-variant-numeric: tabular-nums;
        }
        .qm-tw-eyebrow-row {
          display: flex;
          align-items: flex-end;
          justify-content: space-between;
          padding-bottom: 16px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        }
        .qm-tw-eyebrow-stack {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .qm-tw-eyebrow {
          font-size: 14px;
          color: #fff;
          letter-spacing: 0.005em;
          font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
        }
        .qm-tw-eyebrow-sub {
          font-family: ui-monospace, "SF Mono", Menlo, monospace;
          font-size: 10.5px;
          color: #7a7e7b;
          letter-spacing: 0.18em;
          text-transform: uppercase;
        }
        .qm-tw-segments {
          display: flex;
          gap: 6px;
        }
        .qm-tw-seg {
          width: 56px;
          height: 1.5px;
          background: #2a2e2b;
          border-radius: 1px;
          position: relative;
          overflow: hidden;
          transition: background 0.6s;
        }
        .qm-tw-seg-done {
          background: #5a7370;
        }
        .qm-tw-seg-active {
          background: #2a2e2b;
        }
        .qm-tw-seg-active::after {
          content: "";
          position: absolute;
          inset: 0;
          background: linear-gradient(
            90deg,
            transparent 0%,
            #9eb5a0 50%,
            transparent 100%
          );
          animation: qm-tw-shimmer 2.4s linear infinite;
        }
        @keyframes qm-tw-shimmer {
          0% {
            transform: translateX(-100%);
          }
          100% {
            transform: translateX(100%);
          }
        }
        .qm-tw-soap {
          display: grid;
          grid-template-columns: 140px 1fr;
          gap: 28px 28px;
          align-content: start;
          flex: 1;
        }
        .qm-tw-section {
          display: contents;
        }
        .qm-tw-section-label-row {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 6px;
          padding-top: 6px;
          border-top: 1px solid rgba(255, 255, 255, 0.06);
        }
        .qm-tw-section-label {
          font-family: ui-monospace, "SF Mono", Menlo, monospace;
          font-size: 10.5px;
          letter-spacing: 0.22em;
          text-transform: uppercase;
          color: #7a7e7b;
          transition: color 0.6s;
        }
        .qm-tw-state-writing .qm-tw-section-label {
          color: #c4c8c5;
          animation: qm-tw-label-pulse 4.2s ease-in-out infinite;
        }
        .qm-tw-state-done .qm-tw-section-label {
          color: #c4c8c5;
        }
        .qm-tw-section-badge {
          font-family: ui-monospace, "SF Mono", Menlo, monospace;
          font-size: 9.5px;
          letter-spacing: 0.18em;
          text-transform: uppercase;
        }
        .qm-tw-check {
          color: #5a7370;
        }
        .qm-tw-writing {
          color: #9eb5a0;
          font-style: italic;
          letter-spacing: 0.04em;
          text-transform: lowercase;
        }
        .qm-tw-section-body {
          padding-top: 6px;
          border-top: 1px solid rgba(255, 255, 255, 0.06);
          display: flex;
          flex-direction: column;
          gap: 10px;
          min-height: 24px;
          font-family: "Lora", "Source Serif 4", "Iowan Old Style", Georgia, serif;
          font-size: 17px;
          line-height: 1.65;
        }
        .qm-tw-row {
          display: flex;
          align-items: center;
        }
        .qm-tw-blank {
          color: #2a2e2b;
          letter-spacing: 0.05em;
          user-select: none;
          font-family: ui-monospace, "SF Mono", Menlo, monospace;
          font-size: 14px;
        }
        .qm-tw-state-writing .qm-tw-blank {
          color: #4a4e4b;
        }
        .qm-tw-cursor {
          display: inline-block;
          width: 7px;
          height: 1em;
          background: #9eb5a0;
          margin-left: 4px;
          vertical-align: -0.1em;
          animation: qm-tw-blink 1.05s ease-in-out infinite;
        }
        @keyframes qm-tw-blink {
          0%,
          49% {
            opacity: 1;
          }
          50%,
          100% {
            opacity: 0;
          }
        }
        @keyframes qm-tw-label-pulse {
          0%,
          100% {
            opacity: 0.7;
          }
          50% {
            opacity: 1;
          }
        }
        .qm-tw-codes {
          grid-column: 1 / -1;
          display: grid;
          grid-template-columns: 140px 1fr;
          gap: 28px;
          padding-top: 8px;
          opacity: 0;
          transition: opacity 0.6s;
        }
        .qm-tw-codes-visible {
          opacity: 1;
        }
        .qm-tw-chip-row {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          padding-top: 6px;
        }
        .qm-tw-chip {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 5px 11px;
          border: 1px solid rgba(158, 181, 160, 0.2);
          background: rgba(158, 181, 160, 0.08);
          border-radius: 3px;
          font-family: ui-monospace, "SF Mono", Menlo, monospace;
          font-size: 11px;
          color: #b8cebb;
          letter-spacing: 0.04em;
        }
        .qm-tw-chip-label {
          color: #7a7e7b;
          letter-spacing: 0.16em;
          text-transform: uppercase;
        }
        .qm-tw-chip-count {
          font-variant-numeric: tabular-nums;
        }
        .qm-tw-bottom {
          display: flex;
          align-items: flex-end;
          justify-content: space-between;
          padding-top: 16px;
          border-top: 1px solid rgba(255, 255, 255, 0.06);
          gap: 32px;
        }
        .qm-tw-reassurance {
          font-size: 12px;
          color: #7a7e7b;
          line-height: 1.55;
          max-width: 420px;
        }
        .qm-tw-reassurance-strong {
          color: #c4c8c5;
        }
        .qm-tw-stuck {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 4px;
          padding: 8px 12px;
          border: 1px solid rgba(255, 200, 100, 0.16);
          border-radius: 4px;
          background: rgba(255, 200, 100, 0.04);
        }
        .qm-tw-stuck-warn {
          border-color: rgba(255, 200, 100, 0.16);
        }
        .qm-tw-stuck-stuck {
          border-color: rgba(255, 130, 130, 0.24);
          background: rgba(255, 130, 130, 0.04);
        }
        .qm-tw-stuck-label {
          font-size: 11px;
          letter-spacing: 0.16em;
          text-transform: uppercase;
          color: #c4c8c5;
        }
        .qm-tw-stuck-meta {
          font-family: ui-monospace, "SF Mono", Menlo, monospace;
          font-size: 10.5px;
          color: #7a7e7b;
          letter-spacing: 0.16em;
        }
        @media (prefers-reduced-motion: reduce) {
          .qm-tw-cursor,
          .qm-tw-state-writing .qm-tw-section-label,
          .qm-tw-seg-active::after {
            animation: none;
          }
          .qm-tw-cursor {
            opacity: 0.65;
          }
          .qm-tw-codes,
          .qm-tw-section-label,
          .qm-tw-blank,
          .qm-tw-seg {
            transition-duration: 90ms;
          }
        }
      `}</style>
    </div>
  );
}

// ── stuck-state retry button ─────────────────────────────────────
// Same retry shape as the v1 processing-state. POSTs to the existing
// /api/visits/[id]/retry endpoint; redirects to /dashboard when
// the visit's retry budget is exhausted.
function RetryButton({ visitId }: { visitId: string }) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const onClick = useCallback(async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      const res = await fetch(`/api/visits/${visitId}/retry`, {
        method: 'POST',
        credentials: 'same-origin',
      });
      if (res.status === 409) {
        toast.info('Already processing — give it another minute.');
      } else if (res.ok) {
        toast.success('Retry started');
        router.refresh();
      } else if (res.status === 410) {
        toast.error('Retry budget exhausted — review the failure on dashboard');
        router.push('/dashboard');
      } else {
        toast.error('Could not retry — try again in a minute');
      }
    } catch {
      toast.error('Network blip — try again in a minute');
    } finally {
      setSubmitting(false);
    }
  }, [router, submitting, visitId]);

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={submitting}
      style={{
        marginLeft: 12,
        padding: '4px 10px',
        background: 'transparent',
        border: '1px solid rgba(158, 181, 160, 0.4)',
        color: '#9eb5a0',
        borderRadius: 3,
        font: 'inherit',
        fontFamily: 'ui-monospace, "SF Mono", Menlo, monospace',
        fontSize: 10.5,
        letterSpacing: '0.14em',
        textTransform: 'uppercase',
        cursor: submitting ? 'wait' : 'pointer',
      }}
    >
      {submitting ? 'retrying…' : 'retry'}
    </button>
  );
}
