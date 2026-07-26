'use server';

// ============================================================================
// previewVisitDocumentAction — the visit, as the doctor's own page.
// ----------------------------------------------------------------------------
// The review screen shows the note. This shows the DOCUMENT: their form, filled
// with what has been captured so far, blanks where nothing has. It is the same
// fill the export produces, computed through the same code
// (readAndPrepareTemplateTwinFill), so what they read before signing is what
// comes out afterwards.
//
// IT WRITES NOTHING. Not a fill manifest, not an artifact, not a template
// claim. That is not tidiness — the sign gate validates a STORED manifest
// against the certified IR, so a manifest written mid-review would let a doctor
// sign a fill that predates their own adoptions. The preview reads and computes
// and then forgets.
//
// AND IT GATES NOTHING. Every failure returns a named reason; the caller falls
// back to the styled note and the doctor signs exactly as before.
// ============================================================================

import prisma from '@meddoc/db';

import { requireSession } from '@/lib/auth';
import { convertDocxToPdf } from '@/lib/docx-preview/convert';
import { readAndPrepareTemplateTwinFill } from '@/lib/template-twin/fill-engine';
import { loadNativeTemplateDocxForVisit } from '@/lib/template-twin/native-export';
import type { NativePreviewResult } from './preview-native-document';

/** Why there is no document to show. Every one is surfaced, and none is fatal. */
export type VisitPreviewMiss =
  /** Not a native-template visit — the styled note is the right page. */
  | 'not_template_visit'
  /** Template uploaded and compiled, but never certified. */
  | 'not_certified'
  /** The fill ran and produced no document (nothing renderable yet). */
  | 'no_render'
  /** The fill itself failed. Named, so it is never a blank screen. */
  | 'fill_failed';

export interface VisitPreviewResult extends Omit<NativePreviewResult, 'reason'> {
  reason: NativePreviewResult['reason'] | VisitPreviewMiss | null;
  /** How much of their form is actually filled — shown honestly above the page
   *  so blanks read as "not dictated yet" rather than "the export is broken". */
  counts: { filled: number; needsReview: number; notMentioned: number } | null;
  /** Changes whenever the underlying fill changes. The client uses it to tell
   *  a genuine update from a re-fetch that produced the same document. */
  fillSha: string | null;
}

function miss(reason: VisitPreviewResult['reason']): VisitPreviewResult {
  return { ok: false, kind: null, data: null, reason, counts: null, fillSha: null };
}

export async function previewVisitDocumentAction(
  visitId: string,
): Promise<VisitPreviewResult> {
  const session = await requireSession();

  // Ownership is a WHERE clause, never a check after the fact.
  const visit = await prisma.transcribeVisit.findFirst({
    // Mirrors the fill path's own filters (fill-engine's template claim), not
    // just the client's. A server action is a POST endpoint — "the page does
    // not render it for a signed visit" is not an access control.
    where: { id: visitId, userId: session.user.id, deletedAt: null, archivedAt: null },
    select: {
      signedAt: true,
      inputMode: true,
      transcriptText: true,
      entities: true,
      soapFinal: true,
      noteTemplateId: true,
      noteTemplateVersion: true,
      createdAt: true,
      user: { select: { practiceId: true } },
    },
  });
  if (
    !visit ||
    !visit.soapFinal ||
    !visit.noteTemplateId ||
    visit.noteTemplateVersion == null ||
    !visit.user?.practiceId
  ) {
    return miss('not_template_visit');
  }

  const compiled = await prisma.templateTwinCompiledVersion.findUnique({
    where: { noteTemplateId: visit.noteTemplateId },
    select: { certificationStatus: true },
  });
  if (!compiled) return miss('not_template_visit');
  if (compiled.certificationStatus !== 'CERTIFIED') return miss('not_certified');

  let docx: Buffer;
  let counts: VisitPreviewResult['counts'] = null;
  let fillSha: string;

  // SIGNED: serve the STORED, roundtrip-verified bytes — the actual file that
  // was delivered. Never re-derive a signed document; a fresh fill could differ
  // from what the doctor put their name to, and the twin fill path refuses a
  // signed visit anyway.
  if (visit.signedAt) {
    const stored = await loadNativeTemplateDocxForVisit(visitId, session.user.id);
    if (!stored) return miss('no_render');
    const conv = await convertDocxToPdf(stored.bytes, 'visit.docx');
    return conv.pdf
      ? {
          ok: true,
          kind: 'pdf',
          data: Buffer.from(conv.pdf).toString('base64'),
          reason: null,
          counts: null,
          fillSha: stored.outputSha256,
        }
      : {
          ok: true,
          kind: 'docx_fallback',
          data: stored.bytes.toString('base64'),
          reason: conv.reason,
          counts: null,
          fillSha: stored.outputSha256,
        };
  }

  try {
    const { prepared } = await readAndPrepareTemplateTwinFill({
      practiceId: visit.user.practiceId,
      doctorId: session.user.id,
      noteTemplateId: visit.noteTemplateId,
      noteTemplateVersion: visit.noteTemplateVersion,
      inputMode:
        visit.inputMode === 'voice_dictation'
          ? 'dictation'
          : visit.inputMode === 'text_notes'
            ? 'text'
            : 'conversation',
      contextText: visit.transcriptText ?? '',
      entities: visit.entities,
      generatedNote: visit.soapFinal,
      validationNow: new Date(),
      visitDate: visit.createdAt,
      resolverModelVersion: null,
    });
    if (!prepared.render?.document) return miss('no_render');
    docx = prepared.render.document;
    counts = {
      filled: prepared.manifest.counts.filled,
      needsReview: prepared.manifest.counts.needsReview,
      notMentioned: prepared.manifest.counts.notMentioned,
    };
    fillSha = prepared.manifestSha256;
  } catch (err) {
    const cls = err instanceof Error ? err.constructor.name : 'Unknown';
    console.warn(
      `[visit-preview] visit=${visitId} fill failed (${cls}); the styled note still renders`,
    );
    return miss('fill_failed');
  }

  const converted = await convertDocxToPdf(docx, 'visit.docx');
  if (converted.pdf) {
    return {
      ok: true,
      kind: 'pdf',
      data: Buffer.from(converted.pdf).toString('base64'),
      reason: null,
      counts,
      fillSha,
    };
  }
  // Converter unavailable — hand the true bytes over and let the browser draw.
  return {
    ok: true,
    kind: 'docx_fallback',
    data: Buffer.from(docx).toString('base64'),
    reason: converted.reason,
    counts,
    fillSha,
  };
}
