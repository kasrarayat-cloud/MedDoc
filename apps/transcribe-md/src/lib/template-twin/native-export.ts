// ============================================================================
// Native Template Twin DOCX export — serve the doctor's OWN document.
// ----------------------------------------------------------------------------
// When a visit was filled against a Template Twin native template, the fill
// engine has already rendered the ORIGINAL .docx with the resolved field values
// and roundtrip-VERIFIED it, storing the bytes under the tenant's private prefix
// (fill manifest outputObjectKey). Export just serves those verified bytes — the
// doctor gets their exact template back, formatting preserved.
//
// Returns null when the visit is not a twin visit or has no verified native
// output; the caller falls back to the QuillMD-styled generateVisitDocx. The
// sign route is NOT involved. Ownership is enforced here (the manifest's visit
// must belong to userId) on top of the route's own ownership gate.
// ============================================================================

import { manifestMatchesNote } from './note-identity';
import prisma from '@meddoc/db';

import { processTemplateTwinVisit } from './fill-engine';
import type { EncounterInputMode } from './encounter-facts';
import {
  createTemplateTwinArtifactStore,
  type TemplateTwinArtifactStore,
} from './storage';

export interface NativeTemplateExport {
  bytes: Buffer;
  outputSha256: string;
  roundTripVerified: boolean;
}

/** Shared with `sign-freeze.ts`: the sign path re-fills through the SAME
 *  mapping the export path uses. A second copy would drift. */
export function mapInputMode(inputMode: string): EncounterInputMode {
  if (inputMode === 'voice_dictation') return 'dictation';
  if (inputMode === 'text_notes') return 'text';
  return 'conversation';
}

export async function loadNativeTemplateDocxForVisit(
  visitId: string,
  practiceId: string,
  deps?: { storage?: TemplateTwinArtifactStore },
): Promise<NativeTemplateExport | null> {
  // ⚠️ A SIGNED RECORD RESOLVES BY POINTER, NEVER BY LOOKUP — ruling 2(b).
  //
  // The signature stamped `frozenFillManifestId` in the same write that set
  // SIGNED. Reading it — rather than searching for "a VERIFIED manifest for
  // this visit" — makes a manifest that landed AFTERWARDS unreachable by
  // construction. Layer (a) makes that write impossible; this makes a write
  // that slipped through inert.
  //
  // NULL on a signed visit is not "look it up instead": it records that the
  // signature froze NO native document, and the answer is styled, forever.
  const signedVisit = await prisma.transcribeVisit.findFirst({
    // Scoped inline, matching this file's own manifest query below rather than
    // importing the accessor — which would drag next-auth into every consumer's
    // module graph and add a declared system read for no tenancy gain.
    where: { id: visitId, practiceId, deletedAt: null },
    select: { status: true, frozenFillManifestId: true },
  });
  const isSigned = signedVisit?.status === 'SIGNED';
  if (isSigned && !signedVisit?.frozenFillManifestId) {
    console.info(
      `[template-twin:native] signed visit=${visitId} froze no native document — styled`,
    );
    return null;
  }

  const manifest = await prisma.templateTwinFillManifest.findFirst({
    where: {
      visitId,
      // ⚠️ THE POINTER IS THE WHOLE PREDICATE FOR A SIGNED RECORD.
      ...(isSigned ? { id: signedVisit!.frozenFillManifestId! } : {}),
      // ⚠️ TENANCY IS PER-PRACTICE, NOT PER-USER — F5-f ruling 2.
      //
      // This read `visit: { userId }`, so a colleague with access to the same
      // chart received a DIFFERENT document for the same record: the author
      // saw their letterhead, everyone else saw the generic layout. The
      // archive route already states the product's law — the patient's chart
      // is the PRACTICE's — and this predicate contradicted it.
      //
      // A record has ONE current document. The practice is the tenancy
      // boundary; the caller's identity is not.
      visit: { practiceId, deletedAt: null },
      status: 'VERIFIED',
      roundTripVerified: true,
      outputObjectKey: { not: null },
    },
    select: {
      practiceId: true,
      outputObjectKey: true,
      outputSha256: true,
      outputSizeBytes: true,
      // The note this fill ran against, so the caller can prove the artifact
      // still corresponds to the visit's CURRENT note before serving it.
      noteSha256: true,
      visit: { select: { soapFinal: true } },
    },
  });
  if (
    !manifest ||
    !manifest.outputObjectKey ||
    !manifest.outputSha256 ||
    manifest.outputSizeBytes == null
  ) {
    return null;
  }

  // ⚠️ A MANIFEST IS SERVABLE ONLY WHEN IT PROVABLY MATCHES THE CURRENT NOTE.
  //
  // Without this the artifact was served forever: the worker filled from note
  // v1, the doctor edited to v2, and the download stayed v1 — and after signing
  // the compute path refuses to recompute, so the stored bytes and `soapFinal`
  // could disagree PERMANENTLY with nothing on any surface saying so.
  //
  // Fail-closed on all three unprovable cases, including a manifest written
  // before `noteSha256` existed. An artifact that cannot prove which note it
  // came from is not evidence of anything.
  // ⚠️ FRESHNESS GOVERNS THE UNSIGNED RECORD; THE POINTER GOVERNS THE SIGNED ONE.
  //
  // A signed record's pair was frozen AT the signature, under the CAS that
  // guarantees `signedSoap` is the text the manifest was bound to. Re-deriving
  // freshness from `soapFinal` afterwards would let a post-signature edit to
  // that column DECLINE the very document the signature froze — the record
  // would stop being able to produce itself.
  //
  // So for a signed visit the pointer is authoritative and this check is
  // skipped, deliberately. For an unsigned one the note can still move and the
  // check is the only thing standing between a doctor and a stale download.
  const freshness = isSigned
    ? ({ ok: true, reason: 'match' } as const)
    : manifestMatchesNote(manifest.noteSha256, manifest.visit?.soapFinal);
  if (!freshness.ok) {
    console.info(
      `[template-twin:native] manifest declined visit=${visitId} reason=${freshness.reason}`,
    );
    return null;
  }

  const storage = deps?.storage ?? createTemplateTwinArtifactStore();
  const bytes = await storage.readOutputArtifact({
    practiceId: manifest.practiceId,
    objectKey: manifest.outputObjectKey,
    expectedSha256: manifest.outputSha256,
    expectedSizeBytes: manifest.outputSizeBytes,
  });
  return { bytes, outputSha256: manifest.outputSha256, roundTripVerified: true };
}

/**
 * Serve the cached native document, computing it ON DEMAND once if the manifest
 * is absent. The worker fill step is the PRIMARY producer (compute-once at note
 * generation); this fallback only fires for a visit whose manifest never
 * materialised (e.g. the template was certified after generation). The compute
 * is deterministic (resolver + bridge + render — NO AI), idempotent, and gated:
 * it runs ONLY for an UNSIGNED certified-twin visit that has a generated note.
 * Any failure returns null so the caller degrades to the styled export — the
 * fill never blocks the download.
 *
 * DESIGN NOTE (BOUND-002 spirit): the on-demand compute is heavy work on the GET
 * export request thread, which we normally keep off the web tier. It is bounded +
 * safe here: DETERMINISTIC (resolver + bridge + render, NO AI), gated to an
 * UNSIGNED certified-twin visit with a generated note, idempotent (compute-once —
 * the worker fill step is the PRIMARY producer; this only fires when the manifest
 * never materialised), and fail-safe (any error → null → styled export). It is a
 * resilience fallback, not the hot path.
 */
/**
 * Why a native export did NOT happen. Every fallback path names itself.
 *
 * Silence was the defect: this function returned bare `null` from four
 * different places and the caller degraded to the styled export without a
 * word, so "my own form did not come back" was indistinguishable from "the
 * feature is off" — for the doctor AND for anyone reading the logs. The PDF
 * path already records nativePdfApplied/nativePdfReason on its audit row; this
 * mirrors that so the DOCX path is equally accountable.
 */
export type NativeDocxSkipReason =
  | 'not_certified'
  | 'visit_not_eligible'
  | 'fill_failed'
  | 'manifest_incomplete';

export interface NativeDocxOutcome {
  native: NativeTemplateExport | null;
  /** null when a native export WAS produced. */
  reason: NativeDocxSkipReason | null;
}

export async function loadOrComputeNativeTemplateDocxForVisit(
  visitId: string,
  practiceId: string,
  deps?: { storage?: TemplateTwinArtifactStore },
): Promise<NativeDocxOutcome> {
  const cached = await loadNativeTemplateDocxForVisit(visitId, practiceId, deps);
  if (cached) return { native: cached, reason: null };

  try {
    const visit = await prisma.transcribeVisit.findFirst({
      // ⚠️ PRACTICE-SCOPED, LIKE THE READ. A colleague requesting a document
      // that has not been filled yet must get the SAME answer the author would,
      // or the divergence simply moves into the fill window.
      where: { id: visitId, user: { practiceId }, deletedAt: null },
      select: {
        status: true,
        inputMode: true,
        transcriptText: true,
        entities: true,
        soapFinal: true,
        noteTemplateId: true,
        noteTemplateVersion: true,
        createdAt: true,
        signedAt: true,
        userId: true,
        user: { select: { practiceId: true } },
      },
    });
    if (
      !visit ||
      visit.status === 'SIGNED' ||
      !visit.soapFinal ||
      !visit.noteTemplateId ||
      visit.noteTemplateVersion == null ||
      !visit.user?.practiceId
    ) {
      return { native: null, reason: 'visit_not_eligible' };
    }
    const compiled = await prisma.templateTwinCompiledVersion.findUnique({
      where: { noteTemplateId: visit.noteTemplateId },
      select: { certificationStatus: true },
    });
    if (compiled?.certificationStatus !== 'CERTIFIED') {
      // The single most common reason a doctor's own document does not come
      // back: the template is uploaded and compiled but never certified.
      console.info(
        `[native-export] visit=${visitId} template not CERTIFIED ` +
          `(status=${compiled?.certificationStatus ?? 'NO_COMPILED_VERSION'}); styled fallback`,
      );
      return { native: null, reason: 'not_certified' };
    }

    await processTemplateTwinVisit({
      visitId,
      practiceId: visit.user.practiceId,
      // ⚠️ THE VISIT'S OWN DOCTOR, NOT THE REQUESTER. The fill belongs to the
      // record; attributing it to whoever happened to click download would put
      // a colleague's id on the author's document.
      doctorId: visit.userId,
      noteTemplateId: visit.noteTemplateId,
      noteTemplateVersion: visit.noteTemplateVersion,
      inputMode: mapInputMode(visit.inputMode),
      contextText: visit.transcriptText ?? '',
      entities: visit.entities,
      generatedNote: visit.soapFinal,
      validationNow: new Date(),
      // Encounter date for the DATE OF PROCEDURE metadata fill: the visit's
      // creation (encounter) date, ALWAYS. Ruling #115 — this used to prefer
      // `signedAt` "once frozen", which printed the day the note was signed as
      // the day the procedure happened. Freezing a note does not move a
      // procedure; the signing date lives in the signature chrome alone.
      visitDate: visit.createdAt,
      resolverModelVersion: null,
      storage: deps?.storage,
    });
    const produced = await loadNativeTemplateDocxForVisit(visitId, practiceId, deps);
    return produced
      ? { native: produced, reason: null }
      : { native: null, reason: 'manifest_incomplete' };
  } catch (err) {
    console.warn(
      `[native-export] on-demand fill failed for visit=${visitId}; styled fallback:`,
      err instanceof Error ? err.message : String(err),
    );
    return { native: null, reason: 'fill_failed' };
  }
}
