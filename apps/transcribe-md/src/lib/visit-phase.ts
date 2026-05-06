// ============================================================================
// Visit-phase mapping — internal Prisma `TranscribeVisitStatus` (7 active
// processing states) folded into the 5 display phases the typewriter-SOAP
// processing screen renders.
// ----------------------------------------------------------------------------
// Internal worker has 7 stages it sets sequentially as it runs:
//   QUEUED → TRANSCRIBING → EXTRACTING → DRAFTING → CRITIQUING → POLISHING
//          → AUTOMATING → READY    (or FAILED at any point)
// Doctor-facing view collapses those into 5 honest display phases:
//   Transcribing → Understanding → Drafting → Reviewing → Coding
// CRITIQUING + POLISHING fold under "Reviewing" because both are draft-
// review passes from the doctor's perspective; AUTOMATING is the
// codes-and-Rx pass which gets its own "Coding" tile because the chips
// at the bottom of the typewriter render against it.
// ============================================================================

import { TranscribeVisitStatus } from '@prisma/client';

/** Public 5-phase enum the typewriter screen renders. Order is the
 *  display order (caret travel L→R / top→bottom in the SOAP). */
export const VISIT_PHASES = [
  'Transcribing',
  'Understanding',
  'Drafting',
  'Reviewing',
  'Coding',
] as const;
export type VisitPhase = (typeof VISIT_PHASES)[number];

/** Map internal Prisma status → display phase, or null when no phase
 *  applies (QUEUED-but-no-input, READY, FAILED, SIGNED). */
export function statusToPhase(
  status: TranscribeVisitStatus
): VisitPhase | null {
  switch (status) {
    case TranscribeVisitStatus.QUEUED:
      // QUEUED with input is "about to transcribe" — show the
      // Transcribing phase as the first active state. The page-level
      // caller must verify input is present before mounting the
      // typewriter; QUEUED-without-input should render the uploader,
      // not this screen.
      return 'Transcribing';
    case TranscribeVisitStatus.TRANSCRIBING:
      return 'Transcribing';
    case TranscribeVisitStatus.EXTRACTING:
      return 'Understanding';
    case TranscribeVisitStatus.DRAFTING:
      return 'Drafting';
    case TranscribeVisitStatus.CRITIQUING:
    case TranscribeVisitStatus.POLISHING:
      return 'Reviewing';
    case TranscribeVisitStatus.AUTOMATING:
      return 'Coding';
    case TranscribeVisitStatus.READY:
    case TranscribeVisitStatus.FAILED:
    case TranscribeVisitStatus.SIGNED:
      return null;
    default:
      return null;
  }
}

/** 0-based index of a phase within VISIT_PHASES, or -1 when null. */
export function phaseIndex(phase: VisitPhase | null): number {
  if (!phase) return -1;
  return VISIT_PHASES.indexOf(phase);
}

/** Canonical eyebrow + sub-eyebrow per display phase. The eyebrow is
 *  the uppercase micro-label above the SOAP skeleton; the sub-eyebrow
 *  is the muted-grey clarifier underneath ("EXTRACTING ENTITIES"
 *  underneath "UNDERSTANDING"). Kept short — these run in JetBrains
 *  Mono with letter-spacing, longer copy looks crowded. */
export const PHASE_EYEBROW: Record<VisitPhase, { primary: string; sub: string }> = {
  Transcribing:  { primary: 'Transcribing',   sub: 'In flight'             },
  Understanding: { primary: 'Understanding',  sub: 'Extracting entities'   },
  Drafting:      { primary: 'Drafting',       sub: 'Composing SOAP'        },
  Reviewing:     { primary: 'Reviewing',      sub: 'Auditing draft'        },
  Coding:        { primary: 'Coding',         sub: 'ICD-10 + CPT'          },
};

/** SOAP section the active caret sits on for each display phase. */
export type SoapSection = 'subjective' | 'objective' | 'assessment' | 'plan';
export const PHASE_CARET_SECTION: Record<VisitPhase, SoapSection> = {
  Transcribing:  'subjective',
  Understanding: 'objective',
  Drafting:      'assessment',
  Reviewing:     'plan',
  Coding:        'plan', // chips appear; caret stays on plan
};

/** Per-section "drafted" state at each phase. `idle` = empty
 *  underscores. `writing` = active caret + "writing…" muted indicator
 *  under the label. `done` = section label gets a subtle ✓ glyph. */
export type SectionState = 'idle' | 'writing' | 'done';

const SECTIONS: SoapSection[] = ['subjective', 'objective', 'assessment', 'plan'];

/** Compute per-section state given the active phase. Sections "before"
 *  the caret are done; the caret-section is writing; sections after
 *  are idle. At Reviewing all sections are done (the caret label moves
 *  to a per-phase eyebrow, the underline pattern stays). At Coding
 *  every section is done; chips render at the bottom. */
export function sectionStates(
  phase: VisitPhase | null
): Record<SoapSection, SectionState> {
  const out = {
    subjective: 'idle',
    objective:  'idle',
    assessment: 'idle',
    plan:       'idle',
  } as Record<SoapSection, SectionState>;
  if (!phase) return out;
  if (phase === 'Reviewing') {
    out.subjective = 'done';
    out.objective  = 'done';
    out.assessment = 'done';
    out.plan       = 'writing';
    return out;
  }
  if (phase === 'Coding') {
    SECTIONS.forEach((s) => { out[s] = 'done'; });
    return out;
  }
  const caret = PHASE_CARET_SECTION[phase];
  for (const s of SECTIONS) {
    if (s === caret) { out[s] = 'writing'; break; }
    out[s] = 'done';
  }
  return out;
}

/** Format elapsed seconds as "M:SS". Tabular-numeric in the UI. */
export function formatElapsed(totalSec: number): string {
  if (!Number.isFinite(totalSec) || totalSec < 0) return '0:00';
  const s = Math.floor(totalSec);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}
