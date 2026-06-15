'use client';

// ============================================================================
// Typewriter SOAP — production post-upload processing screen.
// ----------------------------------------------------------------------------
// Renders a 4-section SOAP skeleton (Subjective / Objective / Assessment
// / Plan) that fills section-by-section as the AI pipeline runs. At
// AUTOMATING (display: "Coding"), ICD/CPT chips appear with real counts.
//
// SCOPE (this PR — fix-typewriter-typography-and-scope):
// Sections stay empty (underscored blanks + caret on the active label
// per phase mapping) through TRANSCRIBING / EXTRACTING / DRAFTING. When
// soapDraft lands (post-DRAFTING / re-written by POLISHING), the four
// sections type in their real bodies. Markdown bold (`**text**`) is
// rendered as `<strong>` inline; partial mid-typing markers display
// the asterisks until the closing pair arrives.
//
// Earlier iteration typed the raw Deepgram transcript on the Subjective
// slot during TRANSCRIBING, then cross-faded to soap.subjective when
// DRAFTING completed. Doctors saw their own dictation artifacts
// ("comma", "period", "Sorry for number two") play back at 150 cps for
// ~50 seconds — anti-trust experience. Dropped the transcript phase
// entirely; sections sit idle until SOAP is ready.
//
// Phase-event mechanism: /api/visits/[id]/status polling at 1.5s. The
// endpoint surfaces { soap: {S,O,A,P} } as preview-clipped strings
// (3200 chars per section). No worker streaming changes.
//
// Min-display-time: 2.4s per phase so fast phases stay legible. Typing
// is independent of the display-phase advance — once SOAP content
// lands it types at 300 cps until done.
//
// prefers-reduced-motion: caret blink + label pulse OFF; typing speed
// 300 → 800 chars/sec so content appears nearly-instantly. The typing
// itself stays on (it's information, not decoration).
//
// Reading width: section body is capped at 70ch (~63ch usable after
// font metrics) to keep eye-travel inside the typography sweet spot;
// outer container is centered at 1100px max-width.
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
  statusToPhase,
  type SoapSection,
  type VisitPhase,
} from '@/lib/visit-phase';
import { isSkinBeta } from '@/config/skin-beta';

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
  preview: {
    soap: {
      subjective: string | null;
      objective: string | null;
      assessment: string | null;
      plan: string | null;
    } | null;
  };
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

// Typing speed (characters per second). 300 cps suits real SOAP
// sections (1500-3200 chars per the live distribution analysis); 150
// cps would drag a 3200-char Subjective out for >20s, longer than the
// AUDITING phase itself. Reduced-motion floods content nearly-instantly
// so the page stays quiet for users who opted out of animation.
const TYPE_CHARS_PER_SEC_SOAP = 300;
const TYPE_CHARS_PER_SEC_REDUCED = 800;

const SOAP_SECTIONS: { key: SoapSection; label: string; rows: number }[] = [
  { key: 'subjective', label: 'Subjective', rows: 3 },
  { key: 'objective',  label: 'Objective',  rows: 2 },
  { key: 'assessment', label: 'Assessment', rows: 2 },
  { key: 'plan',       label: 'Plan',       rows: 3 },
];
const SOAP_KEYS: SoapSection[] = ['subjective', 'objective', 'assessment', 'plan'];

// Underscore-blank pattern used for idle sections.
const ROW_BLANK = '________ _____ ___ ______ ________ _____ ___';

// Per-section content state. A section travels: idle → typing → done.
// Earlier iteration had a transcript-source + swap-out cross-fade; both
// dropped because typing the raw transcript was an anti-trust user
// experience for doctors (Deepgram artifacts visible mid-typing).
type SectionMode = 'idle' | 'typing' | 'done';
interface SectionTarget {
  /** Full content the typewriter is animating toward. null = nothing yet. */
  text: string | null;
  /** Float so the RAF loop can advance fractional chars; rendered via
   *  Math.floor so identical integer slices skip the React DOM diff. */
  revealed: number;
  mode: SectionMode;
}

const INITIAL_SECTION_TARGET: SectionTarget = {
  text: null,
  revealed: 0,
  mode: 'idle',
};

// ── Inline markdown renderer (bold + line-breaks only) ──────────────
// SOAP drafts use `**Header:**` style for clinical sub-headings. The
// existing project pattern (apps/transcribe-md/src/app/visits/[id]/
// soap/SoapSection.tsx) has a 30-line minimal renderer; we reuse the
// inline-bold pattern here so the typewriter doesn't pull in a heavy
// markdown lib. Partial mid-typing markers display asterisks until the
// closing pair arrives — the regex requires a complete `**...**` pair
// to substitute, so unfinished bold renders verbatim for ≤300ms (one
// frame at 300 cps × ~3-4 char marker length).
const BOLD_SPLIT_RE = /(\*\*[^*]+\*\*)/g;
function renderInlineMd(text: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  const lines = text.split('\n');
  lines.forEach((line, li) => {
    if (li > 0) out.push(<br key={`br-${li}`} />);
    const parts = line.split(BOLD_SPLIT_RE);
    parts.forEach((p, pi) => {
      if (p.startsWith('**') && p.endsWith('**') && p.length >= 5) {
        out.push(<strong key={`b-${li}-${pi}`}>{p.slice(2, -2)}</strong>);
      } else if (p) {
        out.push(<span key={`t-${li}-${pi}`}>{p}</span>);
      }
    });
  });
  return out;
}

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
  const [displayPhase, setDisplayPhase] = useState<VisitPhase | null>(() =>
    statusToPhase(initialStatus)
  );
  const lastDisplayChangeRef = useRef<number>(Date.now());

  // ── per-section typewriter state ────────────────────────────────────
  const [sectionTargets, setSectionTargets] = useState<
    Record<SoapSection, SectionTarget>
  >(() => ({
    subjective: { ...INITIAL_SECTION_TARGET },
    objective:  { ...INITIAL_SECTION_TARGET },
    assessment: { ...INITIAL_SECTION_TARGET },
    plan:       { ...INITIAL_SECTION_TARGET },
  }));

  // Detect prefers-reduced-motion (live, not just on mount, so a user
  // toggling the OS setting mid-session takes effect).
  const [reducedMotion, setReducedMotion] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

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
          ingestPreview(body.preview);
          if (body.status === 'FAILED') {
            router.refresh();
            return;
          }
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

    /** Fold a poll's preview block into per-section state.
     *
     *   - First time `soap.{S,O,A,P}` arrives for a section: set
     *     target + start typing. Server returns the full clipped
     *     content; the RAF loop animates `revealed` up to it.
     *   - Server may keep returning the same content on subsequent
     *     polls — only act on changes (text differs from current
     *     target). Done sections never re-arm.
     *
     *   Done-state is a function of revealed === text.length and is
     *   computed in the RAF loop, not here.
     */
    function ingestPreview(preview: StatusResponse['preview']) {
      setSectionTargets((prev) => {
        const next = { ...prev };
        let changed = false;
        for (const k of SOAP_KEYS) {
          const incoming = preview.soap?.[k] ?? null;
          if (incoming && prev[k].text !== incoming) {
            next[k] = { text: incoming, revealed: 0, mode: 'typing' };
            changed = true;
          }
        }
        return changed ? next : prev;
      });
    }

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
      const nextIdx = Math.min(VISIT_PHASES.length - 1, dispIdx + 1);
      setDisplayPhase(VISIT_PHASES[nextIdx]);
      lastDisplayChangeRef.current = Date.now();
    }, remaining);
    return () => clearTimeout(id);
  }, [status, displayPhase]);

  // ── RAF typing loop ─────────────────────────────────────────────────
  // Animates `revealed` toward `text.length` for any section in
  // 'typing' mode. Frame-rate-independent (uses dt from rAF). Settles
  // into 'done' when fully revealed; respects swap-out (no advance
  // during fade-out).
  //
  // Earlier version had a "render throttle" else-branch that wrote the
  // float to `next[k]` but DIDN'T set `changed = true` — the reducer
  // returned `prev`, the partial increment was discarded, and on
  // high-refresh displays (120–240 Hz, common on clinical iPads /
  // modern MacBooks) where `speed * dt < 1 char/frame`, the float
  // never accumulated. `revealed` froze one integer below
  // `text.length`, mode never flipped to 'done', and all sections
  // stayed in "writing…" forever. Fix: always commit + flag changed.
  // The render-throttle is unnecessary anyway because the rendered
  // string slice uses Math.floor(target.revealed), so identical
  // integer slices produce identical text-node strings — React's DOM
  // diff bails out at the cheap level.
  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    const speed = reducedMotion
      ? TYPE_CHARS_PER_SEC_REDUCED
      : TYPE_CHARS_PER_SEC_SOAP;
    const loop = (t: number) => {
      const dt = Math.min(0.1, (t - last) / 1000); // clamp for tab-switch
      last = t;
      setSectionTargets((prev) => {
        let changed = false;
        const next = { ...prev };
        for (const k of SOAP_KEYS) {
          const cur = prev[k];
          if (cur.mode !== 'typing' || !cur.text) continue;
          const target = cur.text.length;
          if (cur.revealed >= target) {
            next[k] = { ...cur, mode: 'done' };
            changed = true;
            continue;
          }
          const incremented = Math.min(target, cur.revealed + speed * dt);
          next[k] = { ...cur, revealed: incremented };
          changed = true;
        }
        return changed ? next : prev;
      });
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [reducedMotion]);

  // ── derived ─────────────────────────────────────────────────────────
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

  const elapsedMin = elapsedSec / 60;
  const stuckLevel: 'ok' | 'warn' | 'stuck' =
    elapsedMin >= STUCK_AT_MIN ? 'stuck' : elapsedMin >= WARN_AT_MIN ? 'warn' : 'ok';

  const showCodingChips = displayPhase === 'Coding';

  // Caret-section selection: prefer the section currently being typed
  // (so the cursor sits at the end of the active text). If no section
  // is typing, fall back to the phase-mapping caret position.
  const activeTypingSection = useMemo<SoapSection | null>(() => {
    for (const k of SOAP_KEYS) {
      if (sectionTargets[k].mode === 'typing') return k;
    }
    return null;
  }, [sectionTargets]);

  // ── C3 calm-skin processing (Stage-1 capture-finish, flag-gated) ───────────
  // SKIN-ONLY: the polling loop, StatusResponse handling, phase governor, and
  // typewriter engine above are all untouched. This branch re-skins the
  // presentation into the calm C3 capture language — an honest checklist driven
  // by the SAME real displayPhase / phaseIndex(displayPhase), the SAME
  // elapsedFmt + stuckLevel, and the SAME RetryButton recovery — matching the
  // record screen's processing state. The load-bearing "You can leave this
  // page" reassurance is preserved verbatim. Flag OFF → the typewriter below
  // renders verbatim.
  if (isSkinBeta()) {
    const di = phaseIndex(displayPhase);
    const allDone = di >= VISIT_PHASES.length - 1 && displayPhase === 'Coding';
    return (
      <div style={{ maxWidth: 520, margin: '40px auto 64px', padding: '0 20px' }}>
        <div className="qm-c3-rec-card" style={{ margin: '0 auto' }}>
          <div
            className={allDone ? 'qm-c3-rec-spin done' : 'qm-c3-rec-spin'}
            aria-hidden
          />
          <h1 className="qm-c3-rec-h" aria-live="polite" data-testid="qm-tw-phase">
            Writing the note…
          </h1>
          <p className="qm-c3-rec-p">
            {eyebrow?.primary ?? 'Queued'} ·{' '}
            <span style={{ color: 'var(--color-linear-text-3)' }}>
              {eyebrow?.sub ?? 'Waiting for a worker'}
            </span>
          </p>
          <ol
            className="qm-c3-rec-steps"
            aria-label={`SOAP processing — step ${Math.max(0, di + 1)} of ${VISIT_PHASES.length}: ${eyebrow?.primary ?? 'Queued'}`}
          >
            {VISIT_PHASES.map((p, i) => {
              const state = i < di ? 'done' : i === di ? 'now' : 'pending';
              return (
                <li key={p} className={state === 'now' ? 'now' : ''}>
                  <span className="qm-c3-rec-mark" aria-hidden>
                    {state === 'done' ? '✓' : state === 'now' ? '◴' : '○'}
                  </span>{' '}
                  {PHASE_EYEBROW[p].primary}
                  {state === 'now' && (
                    <span style={{ color: 'var(--color-linear-text-3)' }}>
                      {' '}— {PHASE_EYEBROW[p].sub.toLowerCase()}
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
          {showCodingChips && icdCount + cptCount > 0 && (
            <p className="qm-c3-rec-hint">
              {icdCount} ICD-10 · {cptCount} CPT selected
            </p>
          )}
          <p className="qm-c3-rec-hint" aria-live="polite">
            <strong style={{ color: 'var(--color-linear-text-2)' }}>
              You can leave this page.
            </strong>{' '}
            We&apos;ll keep working in the background and notify you when the note
            is ready to sign. · elapsed{' '}
            <span data-testid="qm-tw-elapsed">{elapsedFmt}</span>
          </p>
          {stuckLevel !== 'ok' && (
            <div
              className="qm-c3-rec-honest"
              style={{
                color:
                  stuckLevel === 'stuck'
                    ? 'var(--color-linear-danger)'
                    : 'var(--color-linear-warning)',
              }}
            >
              {stuckLevel === 'warn'
                ? `Taking longer than usual · elapsed ${elapsedFmt}`
                : `This visit appears stuck · elapsed ${elapsedFmt}`}
              {stuckLevel === 'stuck' && (
                <div style={{ marginTop: 12 }}>
                  <RetryButton visitId={visitId} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="qm-typewriter">
      {/* ── Top bar: specialty badge + elapsed ───────────────────── */}
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
        <div
          className="qm-tw-segments"
          role="progressbar"
          aria-label="SOAP processing progress"
          aria-valuemin={0}
          aria-valuemax={VISIT_PHASES.length}
          aria-valuenow={Math.max(0, phaseIndex(displayPhase) + 1)}
          aria-valuetext={`Phase ${Math.max(0, phaseIndex(displayPhase) + 1)} of ${VISIT_PHASES.length}: ${eyebrow?.primary ?? 'Queued'}`}
        >
          {VISIT_PHASES.map((p, i) => {
            const di = phaseIndex(displayPhase);
            const cls = i < di ? 'done' : i === di ? 'active' : 'queued';
            return <div key={p} className={`qm-tw-seg qm-tw-seg-${cls}`} />;
          })}
        </div>
      </div>

      {/* ── SOAP skeleton + typewriter ────────────────────────────── */}
      <div className="qm-tw-soap" role="region" aria-label="SOAP draft preview">
        {SOAP_SECTIONS.map((sec) => {
          const target = sectionTargets[sec.key];
          const isActiveTyping = activeTypingSection === sec.key;
          const sectionDone = target.mode === 'done';
          const hasContent = target.text !== null;
          const revealedCount = Math.floor(target.revealed);
          const revealed = target.text ? target.text.slice(0, revealedCount) : '';
          const labelState: 'idle' | 'writing' | 'done' =
            sectionDone
              ? 'done'
              : hasContent
              ? 'writing'
              : 'idle';
          return (
            <div
              key={sec.key}
              className={`qm-tw-section qm-tw-state-${labelState}`}
              data-testid={`qm-tw-section-${sec.key}`}
            >
              <div className="qm-tw-section-label-row">
                <div className="qm-tw-section-label">{sec.label}</div>
                <div className="qm-tw-section-badge">
                  {labelState === 'done' && (
                    <span className="qm-tw-check" role="img" aria-label="drafted">
                      ✓
                    </span>
                  )}
                  {labelState === 'writing' && (
                    <span className="qm-tw-writing">writing…</span>
                  )}
                </div>
              </div>
              <div
                className="qm-tw-section-body"
                aria-live={hasContent ? 'polite' : 'off'}
                aria-atomic="false"
              >
                {!hasContent ? (
                  Array.from({ length: sec.rows }).map((_, ri) => (
                    <div key={ri} className="qm-tw-row">
                      <span className="qm-tw-blank">
                        {ROW_BLANK.slice(
                          0,
                          ri === sec.rows - 1
                            ? Math.floor(ROW_BLANK.length * 0.62)
                            : ROW_BLANK.length
                        )}
                      </span>
                      {isActiveTyping && ri === 0 ? (
                        <span className="qm-tw-cursor" aria-hidden="true" />
                      ) : null}
                    </div>
                  ))
                ) : (
                  <div className="qm-tw-typed-wrap">
                    <span className="qm-tw-typed">{renderInlineMd(revealed)}</span>
                    {isActiveTyping && !sectionDone ? (
                      <span className="qm-tw-cursor qm-tw-cursor-inline" aria-hidden="true" />
                    ) : null}
                  </div>
                )}
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

      <style jsx>{`
        .qm-typewriter {
          position: relative;
          width: 100%;
          max-width: 1100px;
          margin: 0 auto;
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
          word-break: break-word;
          overflow-wrap: anywhere;
          /* 70ch keeps line-length inside the typography sweet spot
             (60-80ch) where eye-travel + saccade re-acquisition stay
             comfortable. Without this, real SOAP content stretches
             1500+ px on wide screens and reads like a wall. */
          max-width: 70ch;
        }
        .qm-tw-typed strong {
          font-weight: 600;
          color: #fff;
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
        .qm-tw-typed-wrap {
          position: relative;
          color: #fff;
        }
        .qm-tw-typed {
          color: #fff;
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
        .qm-tw-cursor-inline {
          width: 8px;
          margin-left: 2px;
        }
        @keyframes qm-tw-blink {
          0%, 49% { opacity: 1; }
          50%, 100% { opacity: 0; }
        }
        @keyframes qm-tw-label-pulse {
          0%, 100% { opacity: 0.7; }
          50% { opacity: 1; }
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
        .qm-tw-codes-visible { opacity: 1; }
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
        .qm-tw-reassurance-strong { color: #c4c8c5; }
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
        .qm-tw-stuck-warn { border-color: rgba(255, 200, 100, 0.16); }
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
        @media (max-width: 720px) {
          .qm-typewriter {
            padding: 24px 20px 24px 20px;
          }
          .qm-tw-soap {
            grid-template-columns: 96px 1fr;
            gap: 20px 16px;
          }
          .qm-tw-section-body {
            font-size: 15px;
          }
          .qm-tw-codes {
            grid-template-columns: 96px 1fr;
            gap: 16px;
          }
          .qm-tw-eyebrow-row {
            flex-direction: column;
            align-items: flex-start;
            gap: 14px;
          }
          .qm-tw-bottom {
            flex-direction: column;
            align-items: flex-start;
            gap: 14px;
          }
        }
        @media (prefers-reduced-motion: reduce) {
          .qm-tw-cursor,
          .qm-tw-state-writing .qm-tw-section-label,
          .qm-tw-seg-active::after {
            animation: none;
          }
          .qm-tw-cursor { opacity: 0.65; }
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
