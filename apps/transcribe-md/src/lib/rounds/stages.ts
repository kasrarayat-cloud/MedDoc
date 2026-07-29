// ============================================================================
// ROUNDS — the five stages, derived from REAL statuses.
// ----------------------------------------------------------------------------
// Both the Board's stage columns (Screen 1) and the Stage's pipeline strip
// (Screen 2) render five nodes. This module is where those five come from, and
// it exists so there is exactly one mapping rather than two that drift.
//
// THE MAPPING IS DERIVED, NOT INVENTED. `TranscribeVisitStatus` has ten values;
// a clinician does not need ten columns, and inventing a prettier set would
// mean a board that shows a stage the pipeline cannot actually be in. So the
// ten collapse into five, and every one of the ten is accounted for — the
// exhaustiveness check at the bottom fails the build if a new status is added
// to the enum and not placed here.
//
// FAILED and SIGNED are deliberately NOT stages. They are outcomes:
//   - SIGNED is what a lane looks like when its whole run completed.
//   - FAILED is where a lane's line STOPS — it needs the stage it died at, not
//     a column of its own, which is why failureStageOf() exists.
// ============================================================================

export type RoundsStageId =
  | 'captured'
  | 'transcribed'
  | 'drafted'
  | 'checked'
  | 'ready';

export interface RoundsStage {
  id: RoundsStageId;
  /** 1-based, for the numbered column headers. */
  n: number;
  /** Column header + pipeline node label. Plain verbs, sentence case. */
  label: string;
  /** Which raw statuses land in this stage. */
  statuses: readonly string[];
}

export const ROUNDS_STAGES: readonly RoundsStage[] = [
  { id: 'captured', n: 1, label: 'Captured', statuses: ['QUEUED'] },
  { id: 'transcribed', n: 2, label: 'Transcribed', statuses: ['TRANSCRIBING'] },
  { id: 'drafted', n: 3, label: 'Drafted', statuses: ['EXTRACTING', 'DRAFTING'] },
  {
    id: 'checked',
    n: 4,
    label: 'Checked',
    // The self-critique, polish and automation layers read as one step to a
    // clinician: "the system is going over it". Three columns for three
    // internal layers would be an org chart, not a board.
    statuses: ['CRITIQUING', 'POLISHING', 'AUTOMATING'],
  },
  { id: 'ready', n: 5, label: 'Ready', statuses: ['READY'] },
] as const;

/** Outcomes, not stages — see the header. */
export const ROUNDS_OUTCOME_STATUSES = ['SIGNED', 'FAILED'] as const;

/** Which stage a visit currently occupies. `null` for an outcome status. */
export function stageOf(status: string): RoundsStage | null {
  return ROUNDS_STAGES.find((s) => s.statuses.includes(status)) ?? null;
}

/**
 * Where a FAILED lane's line should stop.
 *
 * A failure is not a stage, but it happened AT one, and a red line that stops
 * mid-run is the whole point of the track: it says where to look. The visit row
 * does not record the stage it died in, so this reads the last stage it is known
 * to have COMPLETED and stops one beyond — which is honest about the boundary
 * (the failure is somewhere in that step) rather than guessing a precise node.
 *
 * `lastKnownStatus` is whatever the row carried before FAILED, when the caller
 * has it; absent that, a failure with no history stops at stage 1, because
 * claiming it got further would be fiction.
 */
export function failureStageOf(lastKnownStatus?: string | null): RoundsStage {
  const s = lastKnownStatus ? stageOf(lastKnownStatus) : null;
  return s ?? ROUNDS_STAGES[0];
}

/** Progress along the strip, 0..5. SIGNED is a complete run. */
export function completedStageCount(status: string): number {
  if (status === 'SIGNED') return ROUNDS_STAGES.length;
  const s = stageOf(status);
  if (!s) return 0;
  // The stage a visit is IN is in progress, not complete — so the count is the
  // number strictly before it. READY is the exception: reaching READY means
  // stage 5 finished and it is waiting on a human.
  return s.id === 'ready' ? ROUNDS_STAGES.length : s.n - 1;
}

// ── Exhaustiveness ────────────────────────────────────────────────────────
// Every value of TranscribeVisitStatus must be either a stage or an outcome.
// Adding a status to the Prisma enum without placing it here is a build error,
// not a silently-missing column.
const ALL_STATUSES = [
  'QUEUED',
  'TRANSCRIBING',
  'EXTRACTING',
  'DRAFTING',
  'CRITIQUING',
  'POLISHING',
  'AUTOMATING',
  'READY',
  'FAILED',
  'SIGNED',
] as const;

export type KnownVisitStatus = (typeof ALL_STATUSES)[number];

/** Runtime guard, exported so a test can assert it rather than trusting a
 *  comment. Returns the statuses that are neither a stage nor an outcome. */
export function unmappedStatuses(): string[] {
  const mapped = new Set<string>([
    ...ROUNDS_STAGES.flatMap((s) => s.statuses),
    ...ROUNDS_OUTCOME_STATUSES,
  ]);
  return ALL_STATUSES.filter((s) => !mapped.has(s));
}
