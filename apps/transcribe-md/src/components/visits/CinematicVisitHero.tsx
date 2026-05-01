'use client';

// ============================================================================
// CinematicVisitHero — Phase 4 Apple Cinematic hero band for /visits/[id].
// ----------------------------------------------------------------------------
// Renders a 280px-tall photo band above the existing visit body (SOAP
// editor, processing state, etc). Mirrors visit-detail-04.html:
//
//   ┌─────────────────────────────────────────────────────────────┐
//   │   [parallax photo + cream gradient overlay]                 │
//   │   DASHBOARD › MEI-LING PARK › VISIT · READY                 │  <- breadcrumb
//   │   [Family Medicine] [Ready · J20.9] [99214 · 22 min]        │  <- pills
//   │   Mei-Ling /Park/                                           │  <- headline
//   │   42F · MRN-77324 · drafted 0:38                            │  <- meta
//   └─────────────────────────────────────────────────────────────┘
//
// Animation orchestration:
//   - Patient name renders word-by-word via .av1-word; the LAST token
//     gets `.em.glow` (italic sage glow). Non-reduced-motion only.
//   - Breadcrumb + pills + meta fade in via .av1-fade after the headline.
//   - Parallax + DOF blur handler is identical to landing-11-anim-1.html.
//
// 🟢 SAFE: This component renders ONLY the cinematic band. It does not
// touch the SOAP editor, the Sign & Send flow, the lifecycle actions,
// the processing-state pipeline rail, or anything below the band.
// ============================================================================

import { useEffect, useRef } from 'react';
import { runCinematicEntry, scheduleParallaxScroll } from './cinematic-anim';

export type CinematicVisitHeroStatus =
  | 'QUEUED'
  | 'PROCESSING'
  | 'READY'
  | 'SIGNED'
  | 'FAILED';

export interface CinematicVisitHeroProps {
  /** Full patient display name. Last whitespace-separated token is the
   *  italic sage-glow token. Falls back to "Patient" if empty. */
  patientName: string;
  /** Specialty label (e.g. "Family Medicine"). Renders into the first pill. */
  specialty: string;
  /** Status pill label. Drives the second pill text + dot color. */
  status: CinematicVisitHeroStatus;
  /** Optional chief complaint / primary ICD code shown after the status pill. */
  chiefComplaint?: string | null;
  /** Optional E/M code + duration (e.g. "99214 · 22 min"). */
  emCodeMeta?: string | null;
  /** Optional one-line meta strip below the headline (age/sex, MRN, drafted). */
  metaLine?: string | null;
  /** When `true`, the breadcrumb chunk renders. Disable when no patient
   *  is associated with the visit (e.g. orphaned drafts). */
  showBreadcrumb?: boolean;
  /** Optional override of the breadcrumb string. Defaults to a sensible
   *  `DASHBOARD › {NAME} › VISIT · {STATUS}` derived form. */
  breadcrumbOverride?: string | null;
}

const STATUS_LABEL: Record<CinematicVisitHeroStatus, string> = {
  QUEUED: 'Queued',
  PROCESSING: 'Processing',
  READY: 'Ready',
  SIGNED: 'Signed',
  FAILED: 'Failed',
};

/**
 * Splits the display name on the last whitespace so the trailing token
 * gets the italic sage-glow treatment. Returns the head + tail in two
 * pieces; tail may be empty (single-name patients).
 */
function splitNameForGlow(raw: string): { head: string; tail: string } {
  const trimmed = raw.trim();
  if (!trimmed) return { head: 'Patient', tail: '' };
  const idx = trimmed.lastIndexOf(' ');
  if (idx < 0) return { head: trimmed, tail: '' };
  return {
    head: trimmed.slice(0, idx),
    tail: trimmed.slice(idx + 1),
  };
}

export function CinematicVisitHero({
  patientName,
  specialty,
  status,
  chiefComplaint,
  emCodeMeta,
  metaLine,
  showBreadcrumb = true,
  breadcrumbOverride = null,
}: CinematicVisitHeroProps) {
  const bgRef = useRef<HTMLDivElement | null>(null);
  const rootRef = useRef<HTMLElement | null>(null);

  // Drive the av1-* word/fade entrance + the parallax/DOF scroll handler.
  // The helper functions in ./cinematic-anim are idempotent + reduced-
  // motion-aware — they no-op when matchMedia('(prefers-reduced-motion:
  // reduce)') matches.
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const cancelEntry = runCinematicEntry(root);
    const cancelScroll = scheduleParallaxScroll(bgRef.current);
    return () => {
      cancelEntry?.();
      cancelScroll?.();
    };
  }, []);

  const { head, tail } = splitNameForGlow(patientName || 'Patient');
  const breadcrumb =
    breadcrumbOverride ??
    `DASHBOARD${
      patientName ? ` › ${patientName.toUpperCase()}` : ''
    } › VISIT · ${STATUS_LABEL[status].toUpperCase()}`;

  // Word stagger: head splits on whitespace; each word gets its own
  // .av1-word with a stepped delay. The final tail token always carries
  // .em.glow regardless of word count so the doctor's surname always
  // reads as the focal point.
  const headWords = head.split(/\s+/).filter(Boolean);
  const baseDelayStep = 120;
  const tailDelay = headWords.length * baseDelayStep;

  return (
    <section
      ref={rootRef}
      className="qm-cin-band qm-cin-band-tall"
      aria-label="Visit hero"
    >
      <div ref={bgRef} className="qm-cin-bg qm-cin-bg-visit" aria-hidden />
      <div className="qm-cin-inner">
        {showBreadcrumb && (
          <div className="qm-cin-breadcrumb av1-fade" data-d="0">
            {breadcrumb}
          </div>
        )}
        <div className="qm-cin-pills av1-fade" data-d="100">
          <span className="qm-cin-pill">
            <span className="qm-cin-pill-dot" />
            {specialty}
          </span>
          <span className="qm-cin-pill">
            <span className="qm-cin-pill-dot" />
            {STATUS_LABEL[status]}
            {chiefComplaint ? ` · ${chiefComplaint}` : ''}
          </span>
          {emCodeMeta ? <span className="qm-cin-pill">{emCodeMeta}</span> : null}
        </div>
        <h1 className="qm-cin-headline" aria-label={patientName}>
          {headWords.map((word, i) => (
            <span
              key={`head-${i}`}
              className="av1-word"
              data-d={i * baseDelayStep}
            >
              {word}
              {i < headWords.length - 1 || tail ? ' ' : ''}
            </span>
          ))}
          {tail ? (
            <span className="av1-word em glow" data-d={tailDelay}>
              {tail}
            </span>
          ) : null}
        </h1>
        {metaLine ? (
          <div className="qm-cin-meta av1-fade" data-d="200">
            {metaLine}
          </div>
        ) : null}
      </div>
    </section>
  );
}
