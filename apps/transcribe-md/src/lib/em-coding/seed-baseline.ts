// ============================================================================
// Seed the E/M baseline from the note as it stood BEFORE a mutation.
// ----------------------------------------------------------------------------
// `emScoredCode` is what a re-score measures movement against. Seeding it on
// page view covers the common path, but not a doctor whose first action on a
// visit is an edit — a chat instruction, a tap-to-edit, an adopt from a list
// they were shown before the page finished settling. For them the first
// re-score would find no baseline, conclude nothing had moved, and clear the
// gate.
//
// THE NOTE MUST BE THE PRE-MUTATION ONE. Seeding from the post-mutation note
// would record the level the edit produced and call it the level before the
// edit — the same "no before" bug in a new place, and harder to see. Every
// caller reads the visit before it writes, so the prior note is in hand.
//
// Cost: `computeDisplayedEmCode` is cached on a hash of the note body, so this
// is usually a cache hit from the page render. When it is not, it is one call,
// once per visit, ever.
//
// Best effort by design: a failure leaves the baseline unset, the next re-score
// establishes it, and nothing is blocked. It logs, so a persistent failure is
// visible rather than a gate that quietly never fires.
// ============================================================================

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';

import { computeDisplayedEmCode } from '@/lib/em-coding/displayed-level';
import { log } from '@/lib/log';

export interface SeedEmBaselineInput {
  visitId: string;
  /** The note as it stood BEFORE this mutation. */
  priorSoap: string | null;
  /** Already known? Then this is a no-op — it only ever seeds once. */
  currentScoredCode: string | null;
  signals: { icdCodes: unknown; rxDrafts: unknown; cptCodes: unknown };
  ctx: { practiceId?: string | null; userId?: string | null };
  /** Skip entirely where there is no E/M to baseline (imaging reports). */
  applies: boolean;
  /** When the caller already computed the pre-mutation level — adopt does —
   *  pass it and no scoring call is made at all. */
  knownPriorCode?: string | null;
}

/** A CPT E/M code, and nothing else.
 *
 *  The scorers return SENTINELS on failure — `computeEmLevelDelta` yields
 *  `{ from: 'unknown' }` — and one of those reaching this column made every
 *  later re-score report a movement FROM 'unknown' that never happened: a
 *  fabricated confirm dialog for the doctor and a fabricated EM_RESCORED row.
 *  Callers are fixed, but this is the column's last line of defence and a
 *  future caller will make the same mistake. */
function isCptCode(value: string | null | undefined): value is string {
  return typeof value === 'string' && /^\d{5}$/.test(value);
}

export async function seedEmBaselineIfUnset(input: SeedEmBaselineInput): Promise<void> {
  if (!input.applies) return;
  if (input.currentScoredCode) return; // already seeded; never overwrite
  if (!input.priorSoap && !input.knownPriorCode) return;

  try {
    const code =
      input.knownPriorCode ||
      (await computeDisplayedEmCode(input.priorSoap as string, input.signals, {
        practiceId: input.ctx.practiceId ?? undefined,
        visitId: input.visitId,
        userId: input.ctx.userId ?? null,
      }));
    if (!isCptCode(code)) {
      // A sentinel or an empty answer is not a baseline. Leaving it unset is
      // correct: the next re-score establishes it, and nothing is blocked.
      if (code) {
        log.warn('em-baseline', 'refusing to seed a non-code baseline', {
          visitId: input.visitId,
        });
      }
      return;
    }

    await prisma.transcribeVisit.updateMany({
      // `emScoredCode: null` makes this idempotent under concurrency — two
      // mutations racing to seed cannot produce two answers — and READY keeps
      // it off a row that was signed while we were scoring.
      where: {
        id: input.visitId,
        // ⚠️ T5-W — `ctx.practiceId` arrived here from the first version and
        // was used ONLY for the audit row; the WRITE went unscoped beside it.
        // A tenant known to the code and not applied to the statement is
        // exactly the shape this unit retires.
        ...(input.ctx.practiceId ? { practiceId: input.ctx.practiceId } : {}),
        emScoredCode: null,
        status: TranscribeVisitStatus.READY,
      },
      data: { emScoredCode: code },
    });
  } catch (err) {
    // Not fatal: the next re-score establishes the baseline instead. Logged so
    // a persistent failure shows up as something other than a quiet gate.
    log.warn('em-baseline', 'could not seed the baseline before a mutation', {
      visitId: input.visitId,
      error: err instanceof Error ? err.message : String(err),
    });
  }
}
