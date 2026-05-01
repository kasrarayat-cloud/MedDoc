'use client';

// ============================================================================
// CinematicRecordingHero — Phase 4 Apple Cinematic hero band for
// /visits/[id]/record. Renders a 200px-tall photo band ABOVE the live
// recording widget. Mirrors recording-04.html:
//
//   ┌─────────────────────────────────────────────────────────────┐
//   │   [parallax mic-photo + cream gradient overlay]             │
//   │   ● RECORDING · MEI-LING PARK · 02:14                       │  <- mono pill
//   │   Working on your /note./                                   │  <- headline
//   └─────────────────────────────────────────────────────────────┘
//
// Animation orchestration:
//   - Headline word-by-word via .av1-word; "note" gets `.em.glow`.
//   - "RECORDING · …" pill fades in via .av1-fade.
//   - Parallax + DOF blur scroll handler (smaller blurStart factor for
//     the shorter band).
//
// 🟢 SAFE: This component renders ONLY the band. It does not touch the
// MediaRecorder, AudioContext, scribe-ws WebSocket, BullMQ submission,
// the mic dot, the halo, the waveform visualizer, the transcript
// bubbles, or the 7-step pipeline rail. All those live in the existing
// recording-client.tsx + components/recording/* modules and are
// rendered SIDE-BY-SIDE / BELOW the band by the parent.
// ============================================================================

import { useEffect, useRef } from 'react';
import { runCinematicEntry, scheduleParallaxScroll } from './cinematic-anim';

export interface CinematicRecordingHeroProps {
  /** Full patient display name. Rendered upper-cased into the eyebrow pill. */
  patientName: string;
  /** Elapsed timer string in MM:SS form. The parent (recording-client.tsx)
   *  formats this since it owns the MediaRecorder timer. Empty string
   *  hides the elapsed segment of the pill. */
  elapsed: string;
  /** Optional phase descriptor for the pill ("RECORDING", "UPLOADING",
   *  etc). Defaults to "RECORDING". */
  phaseLabel?: string;
}

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

/** Convenience: format a raw seconds count into MM:SS. Exported so
 *  recording-client.tsx can stay in lockstep with the hero component
 *  formatting choice. */
export function formatHeroElapsed(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${pad(m)}:${pad(s)}`;
}

export function CinematicRecordingHero({
  patientName,
  elapsed,
  phaseLabel = 'RECORDING',
}: CinematicRecordingHeroProps) {
  const bgRef = useRef<HTMLDivElement | null>(null);
  const rootRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const cancelEntry = runCinematicEntry(root);
    // Shorter band → start the DOF blur sooner (smaller factor) so the
    // photo softens before the recording widget below scrolls into the
    // viewport.
    const cancelScroll = scheduleParallaxScroll(bgRef.current, 0.5);
    return () => {
      cancelEntry?.();
      cancelScroll?.();
    };
  }, []);

  // Headline: "Working on your note." — split into 4 .av1-word tokens
  // with stepped delays. The final "note" token carries .em.glow.
  const headWords = ['Working', 'on', 'your'];
  const baseDelayStep = 120;
  const tailDelay = headWords.length * baseDelayStep;

  const pillBody = [
    phaseLabel,
    patientName ? patientName.toUpperCase() : null,
    elapsed,
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <section
      ref={rootRef}
      className="qm-cin-band qm-cin-band-short"
      aria-label="Recording hero"
    >
      <div ref={bgRef} className="qm-cin-bg qm-cin-bg-recording" aria-hidden />
      <div className="qm-cin-inner">
        <span className="qm-cin-rec-eyebrow av1-fade" data-d="0">
          <span className="qm-cin-rec-dot" aria-hidden />
          {pillBody}
        </span>
        <h1
          className="qm-cin-headline qm-cin-headline-rec"
          aria-label="Working on your note."
        >
          {headWords.map((word, i) => (
            <span
              key={`head-${i}`}
              className="av1-word"
              data-d={i * baseDelayStep}
            >
              {word}{' '}
            </span>
          ))}
          <span className="av1-word em glow" data-d={tailDelay}>
            note.
          </span>
        </h1>
      </div>
    </section>
  );
}
