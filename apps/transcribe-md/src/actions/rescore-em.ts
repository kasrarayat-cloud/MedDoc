'use server';

// ============================================================================
// rescoreEmAction — resolve a stale E/M level.
// ----------------------------------------------------------------------------
// Every content mutation sets `emStale`, and the sign route refuses while it is
// set. That is the point: a note that changed has an unvalidated billing level,
// and "unvalidated" is not a state a note may be signed in.
//
// This is how the flag comes off, and it has a REAL BEFORE to compare against.
// The displayed level is recomputed on read and never persisted, so the first
// version of this scored the current note, called that the baseline, and
// concluded nothing had moved — every single time. The gate cleared itself and
// looked exactly like a gate that had checked. `emScoredCode` is the level we
// last validated at; movement is measured against it.
//
// Outcomes, all ordinary:
//   no baseline yet   -> record what we scored. We cannot assert a movement we
//                        have no evidence for.
//   the level moved   -> the EXISTING confirm card asks for acknowledgement,
//                        exactly as it does after adopting a suggestion.
//   it did not move   -> the flag clears and nothing is asked of them.
//
// It never clears the flag without having scored, never writes over a note it
// did not score (optimistic on soapVersion), and never destroys a pending
// change it could not parse.
// ============================================================================

import prisma from '@meddoc/db';
import { Prisma, TranscribeVisitStatus } from '@prisma/client';

import {
  emAppliesToSpecialty,
  isImagingReportSpecialty,
  ultrasoundSpecialtyEnabled,
} from '@meddoc/shared/specialties';

import { requireSession } from '@/lib/auth';
import { visitByIdScope } from '@/lib/practice-scope';
import { logAudit } from '@/lib/audit';
import { computeDisplayedEmCode } from '@/lib/em-coding/displayed-level';
import { unacknowledgedEmChange, type EmChangeCause } from '@/lib/em-pending-change';
import { log } from '@/lib/log';

export interface RescoreEmResult {
  ok: boolean;
  /** False once the level has been validated against the current note. */
  stale: boolean;
  /** Set when the level moved and the doctor must acknowledge it. */
  pending: { from: string; to: string } | null;
  /** The level this re-score validated — the displayed code, override projected
   *  (`computeDisplayedEmCode`), which is what the gate and the signature use.
   *
   *  SEPARATE FROM `pending` ON PURPOSE. `pending` answers "did it move", and
   *  null there means "it did not" — not "there is no level". A caller that
   *  reads the level out of `pending.to` blanks its own display on the ordinary
   *  no-movement outcome, which is exactly how the documentation-level row (and
   *  with it the only place a doctor can disagree with the level) vanished from
   *  the review page. Null here means the re-score did not score: it bailed
   *  early, or the visit is an imaging report with no office level at all. */
  code: string | null;
  /** The cause carried on the pending record, so a consumer can say WHY the
   *  level moved without guessing. The sign route used to hardcode
   *  'note_edited', which told a doctor their own override was an edit. */
  cause: EmChangeCause | null;
  error?: string;
}

export async function rescoreEmAction(visitId: string): Promise<RescoreEmResult> {
  const session = await requireSession();

  const visit = await prisma.transcribeVisit.findFirst({
    where: {
      ...visitByIdScope(visitId, session.user.practiceId),
      deletedAt: null,
      archivedAt: null,
    },
    select: {
      id: true,
      status: true,
      emStale: true,
      emScoredCode: true,
      specialty: true,
      soapFinal: true,
      soapVersion: true,
      emPendingChange: true,
      icdCodes: true,
      rxDrafts: true,
      cptCodes: true,
      user: { select: { practiceId: true } },
    },
  });
  if (!visit) {
    return { ok: false, stale: true, pending: null, code: null, cause: null, error: 'Visit not found.' };
  }
  if (visit.status !== TranscribeVisitStatus.READY || !visit.emStale || !visit.soapFinal) {
    // Nothing was scored, so there is no level to report. `code: null` means
    // "no new information" and the caller must keep what it is showing — it
    // must never be read as "this visit has no level".
    return { ok: true, stale: visit.emStale, pending: null, code: null, cause: null };
  }

  // Imaging reports have no office-visit E/M level — the pipeline skips scoring
  // them entirely. Gating on a level that does not exist would make an
  // ultrasound report unsignable after any edit, and "resolving" it would mean
  // inventing a clinic code.
  if (!emAppliesToSpecialty(visit.specialty)) {
    const cleared = await prisma.transcribeVisit.updateMany({
      where: {
        // T6 §4.1c — was `userId: session.user.id`. These two updateManys carry
        // their OWN predicate and never had a practice one, so simply deleting
        // the author filter would leave an id-only write. Scoped instead.
        ...visitByIdScope(visitId, session.user.practiceId),
        status: TranscribeVisitStatus.READY,
        soapVersion: visit.soapVersion,
      },
      data: { emStale: false },
    });
    // Same rule as the scoring path: if the write missed, we changed nothing
    // and must not report that we did.
    if (cleared.count === 0) {
      return {
        ok: false,
        stale: true,
        pending: null,
        code: null,
        cause: null,
        error: 'The note changed while we were checking — try again.',
      };
    }
    // An imaging report genuinely has no office level. `code: null` is right
    // here for the same reason it is right above — and harmless, because the
    // level row never mounted on an imaging visit in the first place.
    return { ok: true, stale: false, pending: null, code: null, cause: null };
  }

  let scored: string;
  try {
    scored = await computeDisplayedEmCode(
      visit.soapFinal,
      { icdCodes: visit.icdCodes, rxDrafts: visit.rxDrafts, cptCodes: visit.cptCodes },
      { practiceId: visit.user?.practiceId, visitId: visit.id, userId: session.user.id },
    );
  } catch (err) {
    // Leave it stale. A level we could not check must not become signable
    // because the check failed.
    log.warn('rescore-em', 'scoring failed — visit stays stale', {
      visitId,
      error: err instanceof Error ? err.message : String(err),
    });
    return {
      ok: false,
      stale: true,
      pending: null,
      code: null,
      cause: null,
      error: "We couldn't re-check the billing level just now. Try again from the codes row.",
    };
  }

  // THE ONE COERCION. `unacknowledgedEmChange` fails closed on a malformed
  // record; reading the JSON directly meant a corrupt record that used to block
  // signing was read as "nothing to confirm" and then deleted.
  const existing = unacknowledgedEmChange(visit.emPendingChange);

  // The baseline is the level the doctor last had validated: an unacknowledged
  // change carries the reviewed level, otherwise it is the last scored code.
  const baseline = existing?.from ?? visit.emScoredCode ?? null;
  const moved = baseline !== null && baseline !== scored;

  const written = await prisma.transcribeVisit.updateMany({
    // Optimistic: the note must still be the one we scored. An LLM round-trip
    // sits between the read and this write, and an adopt landing in that window
    // would otherwise have its fresh pending change erased by our stale view.
    where: {
      // T6 §4.1c — see the sibling above. Scoped, not merely de-authored.
      ...visitByIdScope(visitId, session.user.practiceId),
      status: TranscribeVisitStatus.READY,
      soapVersion: visit.soapVersion,
    },
    data: {
      emStale: false,
      emScoredCode: scored,
      ...(moved
        ? {
            emPendingChange: {
              // Preserve the ORIGINAL cause and timestamp when a record already
              // exists — relabelling an AI-caused upcode as "note_edited" would
              // put the wrong cause in the sign-blocked audit row.
              cause: existing?.cause ?? 'note_edited',
              at: existing?.at || new Date().toISOString(),
              from: baseline,
              to: scored,
            } as unknown as Prisma.InputJsonValue,
          }
        : existing
          ? // Back at the reviewed level: nothing left to confirm.
            { emPendingChange: Prisma.DbNull }
          : {}),
    },
  });

  if (written.count === 0) {
    // The note moved under us, or the visit was signed. We validated nothing,
    // so we must not report that we did.
    return {
      ok: false,
      stale: true,
      pending: null,
      code: null,
      cause: null,
      error: 'The note changed while we were checking — open the codes row again.',
    };
  }

  void logAudit({
    action: 'EM_RESCORED',
    targetType: 'TranscribeVisit',
    targetId: visitId,
    // CPT codes and a cause class — never note text.
    metadata: { from: baseline, to: scored, moved, baselineKnown: baseline !== null },
  });

  return {
    ok: true,
    stale: false,
    pending: moved && baseline ? { from: baseline, to: scored } : null,
    // THE LEVEL WE JUST VALIDATED, reported whether or not it moved. This is
    // the field a display reads; `pending` is only for the confirm gate.
    code: scored,
    cause: moved && baseline ? (existing?.cause ?? 'note_edited') : null,
  };
}
