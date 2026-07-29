// ============================================================================
// ROUNDS — the Board's row model.
// ----------------------------------------------------------------------------
// DATA HONESTY IS THE RULE HERE. Every field on a lane derives from something
// the queue actually stores. Where the design asks for a datum the system does
// not have, the lane PARKS it visibly rather than inventing a plausible value —
// a board that shows a confident wrong number is worse than one that admits a
// gap, because a clinician will believe it.
//
// What is real, and where it comes from:
//   patientName, status, specialty, createdAt, signedAt, audioDurationSec
//                                            → transcribe_visits columns
//   criticalCount, topInteraction            → rxDrafts.warnings[] (Json)
//   stage / failure stage                    → lib/rounds/stages.ts
//
// What is NOT available, and is parked rather than faked:
//   the stage a FAILED visit died in. The row records the terminal status only,
//   so `failureStageOf` takes whatever last-known status the caller can supply
//   and otherwise stops at stage 1 — see its header. The board draws the stub
//   to that stage and no further.
// ============================================================================

import { stageOf, failureStageOf, type RoundsStage } from './stages';

/** Worker severity band. Only 'critical' gates signing — see lib/rx-warnings. */
type WorkerSeverity = 'critical' | 'moderate' | 'info' | string;

interface RxWarningShape {
  severity?: WorkerSeverity;
  message?: string;
  drugA?: string;
  drugB?: string;
}

export interface BoardLaneInput {
  id: string;
  patientName: string | null;
  patientFallback: string | null;
  specialty: string;
  status: string;
  createdAt: string;
  signedAt: string | null;
  audioDurationSec: number | null;
  /** The raw `rxDrafts` Json column, whatever shape it is in. */
  rxDrafts?: unknown;
  /** Last status before FAILED, when the caller can supply it. */
  lastKnownStatus?: string | null;
}

export type LaneKind =
  | 'ready'
  | 'processing'
  | 'recording'
  | 'signed'
  | 'failed';

export interface BoardLane {
  id: string;
  /** Display name. Falls back to the stored fallback, then to a plain
   *  "Unnamed patient" — never to a generated identity. */
  patientLabel: string;
  specialty: string;
  status: string;
  kind: LaneKind;
  /** Where the lane currently sits, or null for an outcome status. */
  stage: RoundsStage | null;
  /** How far the solid run is drawn, 0..5. */
  runTo: number;
  /** For a failed lane: where the red stub stops. */
  failedAt: RoundsStage | null;
  /** Critical Rx warnings outstanding on this visit. Drives the red border,
   *  the ⚠, and the tinted lane row. */
  criticalCount: number;
  /** ONE line, the top interaction, for the critical card. Null when there is
   *  no critical warning or the payload carries no readable message — a blank
   *  is honest, an invented summary is not. */
  topInteraction: string | null;
  createdAt: string;
  signedAt: string | null;
  audioDurationSec: number | null;
}

/** Pull critical warnings out of the rxDrafts Json, tolerantly. It is model
 *  output persisted as Json, so a malformed payload must yield "no criticals"
 *  rather than throw and take the whole board down. */
export function criticalWarningsOf(rxDrafts: unknown): RxWarningShape[] {
  if (!rxDrafts || typeof rxDrafts !== 'object') return [];
  const w = (rxDrafts as { warnings?: unknown }).warnings;
  if (!Array.isArray(w)) return [];
  return w.filter(
    (x): x is RxWarningShape =>
      !!x && typeof x === 'object' && (x as RxWarningShape).severity === 'critical',
  );
}

/** The one-line interaction shown on a critical card. Prefers the drug pair,
 *  because that is what a clinician recognises fastest; falls back to the
 *  message; returns null rather than composing something from nothing. */
export function topInteractionLine(warnings: RxWarningShape[]): string | null {
  const first = warnings[0];
  if (!first) return null;
  const a = first.drugA?.trim();
  const b = first.drugB?.trim();
  if (a && b) return `${a} + ${b}`;
  const m = first.message?.trim();
  return m || null;
}

function kindOf(status: string, signedAt: string | null): LaneKind {
  if (status === 'SIGNED' || signedAt) return 'signed';
  if (status === 'FAILED') return 'failed';
  if (status === 'READY') return 'ready';
  // QUEUED is the pre-pipeline state: audio is being captured or has just
  // landed. It reads as "recording" on the board because that is what the
  // clinician was doing; everything downstream is the system working.
  if (status === 'QUEUED') return 'recording';
  return 'processing';
}

export function toBoardLane(v: BoardLaneInput): BoardLane {
  const criticals = criticalWarningsOf(v.rxDrafts);
  const kind = kindOf(v.status, v.signedAt);
  const stage = stageOf(v.status);

  return {
    id: v.id,
    patientLabel:
      v.patientName?.trim() || v.patientFallback?.trim() || 'Unnamed patient',
    specialty: v.specialty,
    status: v.status,
    kind,
    stage,
    // A signed lane draws its line the whole way; a failed one stops at the
    // stage it died in; everything else runs to where it currently is.
    runTo:
      kind === 'signed'
        ? 5
        : kind === 'failed'
          ? failureStageOf(v.lastKnownStatus).n
          : (stage?.n ?? 0),
    failedAt: kind === 'failed' ? failureStageOf(v.lastKnownStatus) : null,
    criticalCount: criticals.length,
    topInteraction: topInteractionLine(criticals),
    createdAt: v.createdAt,
    signedAt: v.signedAt,
    audioDurationSec: v.audioDurationSec,
  };
}

export type BoardFilter =
  | 'active'
  | 'signed'
  | 'soap'
  | 'ultrasound'
  | 'critical'
  | 'failed';

/** Filter predicate. Kept pure and exported so the unit tests exercise the same
 *  function the page does, rather than a re-implementation of it. */
export function laneMatchesFilter(
  lane: BoardLane,
  filter: BoardFilter,
  isImaging: (specialty: string) => boolean,
): boolean {
  switch (filter) {
    case 'active':
      return lane.kind !== 'signed' && lane.kind !== 'failed';
    case 'signed':
      return lane.kind === 'signed';
    case 'failed':
      return lane.kind === 'failed';
    case 'critical':
      return lane.criticalCount > 0;
    case 'ultrasound':
      return isImaging(lane.specialty);
    case 'soap':
      // "SOAP" means everything that is not an imaging report — the note shape,
      // not a specialty list, so a new non-imaging specialty is included for
      // free rather than silently dropping off the board.
      return !isImaging(lane.specialty);
  }
}

/**
 * Board order. Critical first, then the rest by recency.
 *
 * Critical-first is not decoration: it is the one ordering rule a clinician
 * would ask for, and burying a red lane under twelve routine ones on a busy day
 * is how an interaction gets missed.
 */
export function sortLanes(lanes: BoardLane[]): BoardLane[] {
  return [...lanes].sort((a, b) => {
    if (a.criticalCount > 0 !== b.criticalCount > 0) {
      return a.criticalCount > 0 ? -1 : 1;
    }
    return b.createdAt.localeCompare(a.createdAt);
  });
}

/** Day-progress meter: signed · to review · live. Derived, never stored. */
export function dayProgress(lanes: BoardLane[]): {
  signed: number;
  toReview: number;
  live: number;
  total: number;
} {
  const signed = lanes.filter((l) => l.kind === 'signed').length;
  const toReview = lanes.filter((l) => l.kind === 'ready').length;
  const live = lanes.filter(
    (l) => l.kind === 'processing' || l.kind === 'recording',
  ).length;
  return { signed, toReview, live, total: lanes.length };
}
