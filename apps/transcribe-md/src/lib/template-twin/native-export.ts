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

function mapInputMode(inputMode: string): EncounterInputMode {
  if (inputMode === 'voice_dictation') return 'dictation';
  if (inputMode === 'text_notes') return 'text';
  return 'conversation';
}

export async function loadNativeTemplateDocxForVisit(
  visitId: string,
  userId: string,
  deps?: { storage?: TemplateTwinArtifactStore },
): Promise<NativeTemplateExport | null> {
  const manifest = await prisma.templateTwinFillManifest.findFirst({
    where: {
      visitId,
      // Ownership: the fill manifest's visit must belong to the requester.
      visit: { userId, deletedAt: null },
      status: 'VERIFIED',
      roundTripVerified: true,
      outputObjectKey: { not: null },
    },
    select: {
      practiceId: true,
      outputObjectKey: true,
      outputSha256: true,
      outputSizeBytes: true,
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
  userId: string,
  deps?: { storage?: TemplateTwinArtifactStore },
): Promise<NativeDocxOutcome> {
  const cached = await loadNativeTemplateDocxForVisit(visitId, userId, deps);
  if (cached) return { native: cached, reason: null };

  try {
    const visit = await prisma.transcribeVisit.findFirst({
      where: { id: visitId, userId, deletedAt: null },
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
      doctorId: userId,
      noteTemplateId: visit.noteTemplateId,
      noteTemplateVersion: visit.noteTemplateVersion,
      inputMode: mapInputMode(visit.inputMode),
      contextText: visit.transcriptText ?? '',
      entities: visit.entities,
      generatedNote: visit.soapFinal,
      validationNow: new Date(),
      // Encounter date for the DATE OF PROCEDURE metadata fill: the signed date
      // once frozen, else the visit's creation (encounter) date.
      visitDate: visit.signedAt ?? visit.createdAt,
      resolverModelVersion: null,
      storage: deps?.storage,
    });
    const produced = await loadNativeTemplateDocxForVisit(visitId, userId, deps);
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
