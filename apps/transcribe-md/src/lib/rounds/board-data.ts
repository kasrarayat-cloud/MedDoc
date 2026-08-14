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
//   stage / failure stage                    → lib/rounds/stages.ts
//
// What is NOT available, and is parked rather than faked:
//   the stage a FAILED visit died in. The row records the terminal status only,
//   so `failureStageOf` takes whatever last-known status the caller can supply
//   and otherwise stops at stage 1 — see its header. The board draws the stub
//   to that stage and no further.
// ============================================================================

import { stageOf, failureStageOf, type RoundsStage } from './stages';

export interface BoardLaneInput {
  id: string;
  patientName: string | null;
  patientFallback: string | null;
  specialty: string;
  status: string;
  createdAt: string;
  signedAt: string | null;
  audioDurationSec: number | null;
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
  // ⚠️ `criticalCount` and `topInteraction` were REMOVED here with the
  // prescription-safety surface (owner ruling #109). They drove the board's red
  // border, its row tint, the `critical` filter arm, the critical-first sort and
  // the header tally — every one of which pointed the doctor at a gate that no
  // longer exists.
  createdAt: string;
  signedAt: string | null;
  audioDurationSec: number | null;
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
    createdAt: v.createdAt,
    signedAt: v.signedAt,
    audioDurationSec: v.audioDurationSec,
  };
}

export type BoardFilter =
  | 'active'
  // R1: the legacy dashboard's "drafts ready" quick-list — up to three
  // READY-but-unsigned visits — folded in here as a first-class rail rather
  // than reproduced as a second widget. The board already carried these as
  // `ready` lanes inside `active`; what the quick-list added was the ability
  // to look at ONLY them, which is a filter, not a list.
  | 'ready'
  | 'signed'
  | 'soap'
  | 'ultrasound'
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
    case 'ready':
      return lane.kind === 'ready';
    case 'signed':
      return lane.kind === 'signed';
    case 'failed':
      return lane.kind === 'failed';
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
 * Board order: most recent first.
 *
 * ⚠️ CRITICAL-FIRST WAS REMOVED HERE with the prescription-safety surface
 * (owner ruling #109). The note that stood here argued the ordering was "not
 * decoration" — that burying a red lane under twelve routine ones is how an
 * interaction gets missed — and that argument was sound about a board whose red
 * lanes led somewhere. They no longer do, so ordering by them would sort the
 * board on a signal the doctor can no longer act on.
 */
export function sortLanes(lanes: BoardLane[]): BoardLane[] {
  return [...lanes].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
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
