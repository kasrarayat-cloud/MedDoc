// ============================================================================
// FREEZE THE PAIR AT SIGNING — the note and its native document become ONE
// object, by construction rather than by refusal.
// ----------------------------------------------------------------------------
// ⚠️ WHY. `native-export` declines a manifest that does not match the visit's
// current note, which stops a stale document being SERVED. But a visit signed
// while stale is frozen stale: after signing the compute path refuses to
// recompute (`visit_not_eligible`), so the doctor's own letterhead is
// unavailable on their own signed record, forever, and they get the styled
// layout with no idea why.
//
// So the refresh happens BEFORE the signature is written. Fresh manifest ->
// signed record and stored bytes correspond by construction.
//
// ⚠️ AND A FORMATTING SUBSYSTEM MUST NEVER BLOCK A SIGNATURE. Every failure
// path here returns and lets the sign proceed. What is forbidden is SILENCE:
// the caller records the reason in the audit row and surfaces a line in the
// response, so the doctor learns at SIGN time rather than at download time.
// The same shape the E/M signedCode freeze twenty lines above already uses.
import prisma from '@meddoc/db';
import { manifestMatchesNote } from './note-identity';

/** Bounded FILL-sized, not sweep-sized. A doctor is waiting on this request. */
export const SIGN_FREEZE_BUDGET_MS = 20_000;

export type NativeFreezeOutcome =
  /** No native document is involved — nothing to freeze, nothing to say. */
  | { state: 'not_applicable' }
  /** The manifest already matches the note. ⚠️ THE COMMON PATH PAYS NOTHING.
   *  `manifestId` is the document the signature must FREEZE BY POINTER. */
  | { state: 'already_fresh'; manifestId: string }
  /** Re-filled against the current note; the pair is frozen. */
  | { state: 'regenerated'; manifestId: string }
  /** Could not refresh. Signing proceeds STYLED, and the reason is recorded. */
  | { state: 'failed'; reason: string };

/**
 * Bring the visit's native manifest up to date with its current note, if there
 * is one and it is stale.
 *
 * ⚠️ ONE CHEAP READ ON THE COMMON PATH. A visit with no manifest, or with a
 * matching one, costs a single indexed lookup and returns. No fill, no MinIO,
 * no model. `gate-sign-freeze` asserts that.
 */
export async function freezeNativeManifestForSigning(input: {
  visitId: string;
  practiceId: string;
}): Promise<NativeFreezeOutcome> {
  const { visitId, practiceId } = input;

  const manifest = await prisma.templateTwinFillManifest.findFirst({
    where: {
      visitId,
      visit: { practiceId, deletedAt: null },
      status: 'VERIFIED',
      roundTripVerified: true,
      outputObjectKey: { not: null },
    },
    select: {
      id: true,
      noteSha256: true,
      visit: {
        select: {
          soapFinal: true,
          userId: true,
          createdAt: true,
          noteTemplateId: true,
          noteTemplateVersion: true,
          inputMode: true,
          transcriptText: true,
          entities: true,
        },
      },
    },
  });

  // No native document on this record. Nothing to freeze and nothing to report:
  // a styled signature was always this visit's outcome.
  if (!manifest?.visit) return { state: 'not_applicable' };

  if (manifestMatchesNote(manifest.noteSha256, manifest.visit.soapFinal).ok) {
    return { state: 'already_fresh', manifestId: manifest.id };
  }

  const v = manifest.visit;
  if (!v.soapFinal || !v.noteTemplateId || v.noteTemplateVersion == null) {
    return { state: 'failed', reason: 'visit_incomplete' };
  }

  // ⚠️ THE FILL ENGINE LOADS ONLY WHEN A RE-FILL IS ACTUALLY NEEDED.
  //
  // Everything above is one indexed read plus a hash compare. Importing the
  // engine at module scope would pull it — and its model/AI surface — into the
  // sign route's graph for EVERY signature, including the overwhelming majority
  // that need no refresh at all. It also broke an unrelated sign test whose
  // `@meddoc/ai` mock is deliberately narrow, which is how the cost announced
  // itself.
  //
  // So the rare path pays for the rare path.
  const [{ processTemplateTwinVisit }, { mapInputMode }] = await Promise.all([
    import('./fill-engine'),
    import('./native-export'),
  ]);

  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    await Promise.race([
      processTemplateTwinVisit({
        visitId,
        practiceId,
        // ⚠️ THE VISIT'S OWN DOCTOR, never the signer. They are usually the same
        // person and must not be assumed to be.
        doctorId: v.userId,
        noteTemplateId: v.noteTemplateId,
        noteTemplateVersion: v.noteTemplateVersion,
        inputMode: mapInputMode(v.inputMode),
        contextText: v.transcriptText ?? '',
        entities: v.entities,
        generatedNote: v.soapFinal,
        // ⚠️ visitDate IS LOAD-BEARING AND THE FIRST DRAFT DROPPED IT.
        // `withProcedureDateFact` injects DATE OF PROCEDURE from it; omitting it
        // made the sign-time re-fill BLANK a field the original fill had
        // populated — a signature that silently erased a date. Found by the
        // refutation pass; the export path has always passed it.
        visitDate: v.createdAt,
        // Same values the export path's compute uses — one behaviour, not a
        // second configuration of the same engine.
        validationNow: new Date(),
        resolverModelVersion: null,
      }),
      new Promise((_, reject) => {
        timer = setTimeout(
          () => reject(new Error('sign_freeze_timeout')),
          SIGN_FREEZE_BUDGET_MS,
        );
      }),
    ]);
  } catch (err) {
    return {
      state: 'failed',
      reason: err instanceof Error ? err.message : 'refill_failed',
    };
  } finally {
    if (timer) clearTimeout(timer);
  }

  // ⚠️ VERIFY, DON'T ASSUME. A fill that returned without throwing has not
  // necessarily produced a manifest matching this note — the engine can decline
  // for its own reasons. Re-read and prove it before claiming the pair is
  // frozen; the whole point of this function is that the claim is checkable.
  // ⚠️ THE SAME PREDICATE THE SERVE PATH USES, NOT A WEAKER ONE.
  //
  // The first draft re-read without `status: 'VERIFIED'`,
  // `roundTripVerified` or `outputObjectKey`, so it could claim `regenerated`
  // for a manifest `loadNativeTemplateDocxForVisit` would still decline — the
  // freeze reporting success for a document the doctor cannot receive. Found by
  // the refutation pass.
  const after = await prisma.templateTwinFillManifest.findFirst({
    where: {
      visitId,
      visit: { practiceId, deletedAt: null },
      status: 'VERIFIED',
      roundTripVerified: true,
      outputObjectKey: { not: null },
    },
    select: { id: true, noteSha256: true, visit: { select: { soapFinal: true } } },
  });
  if (!after || !manifestMatchesNote(after.noteSha256, after.visit?.soapFinal).ok) {
    return { state: 'failed', reason: 'refill_did_not_match' };
  }
  return { state: 'regenerated', manifestId: after.id };
}
