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
import {
  manifestMatchesDocument,
  noteIdentity,
  overridesIdentity,
} from './note-identity';
// #314 v2 — the text L3 read, decided once for every caller. Pure, so the
// lazy-loading of the fill engine below is unaffected.
import { groundingContextFor } from './grounding-context';

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
      // F24-S5 — the override half of the bound identity.
      overridesSha256: true,
      // ⚠️ #247 — WHEN THIS MANIFEST WAS PRODUCED, against when the PATIENT
      // ROW was last written. The record became a fill input with family 3, so
      // a demographic correction between the fill and the signature otherwise
      // freezes a name the preview no longer shows. Two more columns on a read
      // that already happens — the common path stays one indexed lookup, which
      // is what `gate-sign-freeze` asserts.
      updatedAt: true,
      visit: {
        select: {
          soapFinal: true,
          userId: true,
          createdAt: true,
          noteTemplateId: true,
          noteTemplateVersion: true,
          inputMode: true,
          transcriptText: true,
          // #314 v2 — a text_notes visit's source. `transcriptText` is NULL for
          // every one of them; see grounding-context.ts.
          rawTextInput: true,
          entities: true,
          patient: { select: { updatedAt: true } },
        },
      },
    },
  });

  // No native document on this record. Nothing to freeze and nothing to report:
  // a styled signature was always this visit's outcome.
  if (!manifest?.visit) return { state: 'not_applicable' };

  // ⚠️ F24-S5 — THE PAIR, NOT THE NOTE, AND THIS LINE IS WHERE THE REFUTED
  // SLICE ACTUALLY DIED. Driven under a mocked prisma it returned
  // `already_fresh` with `processTemplateTwinVisit` called ZERO times, so a
  // clinician's correction was never re-applied and the signature pinned the
  // PRE-OVERRIDE manifest as the signed document, permanently.
  //
  // Reading the pair makes an override read STALE, which falls through to the
  // re-fill below — the freeze then CAPTURES the correction, which is the only
  // change to signing behaviour. Pointer semantics are untouched.
  const currentOverrides = await prisma.templateTwinFieldOverride.findMany({
    where: { visitId, practiceId },
    select: {
        fieldId: true,
        selectedOptionOrdinal: true,
        overrideKind: true,
        insertedText: true,
      },
  });
  if (
    manifestMatchesDocument({
      manifestNoteSha256: manifest.noteSha256,
      manifestOverridesSha256: manifest.overridesSha256,
      soapFinal: manifest.visit.soapFinal,
      currentOverrides,
      manifestUpdatedAt: manifest.updatedAt,
      patientUpdatedAt: manifest.visit.patient?.updatedAt ?? null,
    }).ok
  ) {
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
        tenantPracticeId: practiceId,
        // ⚠️ THE VISIT'S OWN DOCTOR, never the signer. They are usually the same
        // person and must not be assumed to be.
        authorUserId: v.userId,
        noteTemplateId: v.noteTemplateId,
        noteTemplateVersion: v.noteTemplateVersion,
        inputMode: mapInputMode(v.inputMode),
        // ⚠️ #314 v2 — was `v.transcriptText ?? ''`, which is '' for a typed
        // visit, so the sign-time re-fill blanked a total the worker filled.
        contextText: groundingContextFor(v),
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
    select: {
      id: true,
      noteSha256: true,
      overridesSha256: true,
      visit: { select: { soapFinal: true } },
    },
  });
  // ⚠️ THE SAME PAIR THE SERVE PATH USES, RE-READ AFTER THE FILL. The override
  // set is read AGAIN rather than reusing `currentOverrides` above: a correction
  // that landed during the re-fill must not be able to pass this check on the
  // strength of a list captured before it existed. If it did land, the pair
  // disagrees and the freeze honestly reports `refill_did_not_match` rather
  // than freezing a document that is already stale.
  const overridesAfter = await prisma.templateTwinFieldOverride.findMany({
    where: { visitId, practiceId },
    select: {
        fieldId: true,
        selectedOptionOrdinal: true,
        overrideKind: true,
        insertedText: true,
      },
  });
  if (
    !after ||
    !manifestMatchesDocument({
      manifestNoteSha256: after.noteSha256,
      manifestOverridesSha256: after.overridesSha256,
      soapFinal: after.visit?.soapFinal,
      currentOverrides: overridesAfter,
    }).ok
  ) {
    return { state: 'failed', reason: 'refill_did_not_match' };
  }
  return { state: 'regenerated', manifestId: after.id };
}

/**
 * Which manifest corresponds to the text about to be signed?
 *
 * ⚠️ ASKED AT WRITE TIME, OF THE DATABASE — not "what did my freeze produce".
 * A concurrent signer, or this request's own orphaned fill, may have produced
 * the correct document after the freeze returned. Trusting the freeze's
 * in-memory id stamps NULL in exactly those cases and strands the record on the
 * styled path forever.
 *
 * Returns null when no VERIFIED manifest matches the captured note — which is
 * the honest answer, and the one that makes `styled` a fact rather than a guess.
 */
export async function resolveFrozenPointer(
  visitId: string,
  practiceId: string,
  capturedNote: string | null,
): Promise<string | null> {
  const wanted = noteIdentity(capturedNote);
  if (!wanted) return null;
  // ⚠️ F24-S5 — THE FOURTH COMPARISON SITE, AND IT IS A SQL PREDICATE RATHER
  // THAN A CALL TO `manifestMatchesNote`. A sweep for the FUNCTION finds the
  // other three and silently misses this one; it was found by grepping the
  // COLUMN. If the pointer bound on the note alone, a manifest filled before a
  // correction would still satisfy it and the signature would pin the
  // pre-override document — the very outcome the widened identity exists to
  // stop, re-entering one layer down.
  const currentOverrides = await prisma.templateTwinFieldOverride.findMany({
    where: { visitId, practiceId },
    select: {
        fieldId: true,
        selectedOptionOrdinal: true,
        overrideKind: true,
        insertedText: true,
      },
  });
  const wantedOverrides = overridesIdentity(currentOverrides);
  const m = await prisma.templateTwinFillManifest.findFirst({
    where: {
      visitId,
      visit: { practiceId, deletedAt: null },
      status: 'VERIFIED',
      roundTripVerified: true,
      outputObjectKey: { not: null },
      // ⚠️ BOUND TO THE CAPTURE, not to whatever the visit's note says now.
      // The signature freezes the captured text; the pointer must agree with
      // THAT, or the pair is not one object.
      noteSha256: wanted,
      // ⚠️ NULL IS ACCEPTED ONLY WHEN THERE ARE NO OVERRIDES, and that is not a
      // convenience — it is the null-is-empty rule expressed in SQL. A legacy
      // manifest predates the override table, so "no overrides" is true of it by
      // construction; but once a correction EXISTS, a null-stamped manifest
      // provably did not run against it and must not be pinned.
      ...(currentOverrides.length === 0
        ? { OR: [{ overridesSha256: wantedOverrides }, { overridesSha256: null }] }
        : { overridesSha256: wantedOverrides }),
    },
    select: { id: true },
  });
  return m?.id ?? null;
}
