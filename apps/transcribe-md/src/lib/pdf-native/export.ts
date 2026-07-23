// ============================================================================
// PDF native export path (feat/pdf-native-fill). Server-only. Returns the
// doctor's OWN page filled with the visit's generated answers — or null to fall
// back to the styled generator. Gated: flag ON + a CERTIFIED PDF template (canvas
// + anchors stored). Deterministic; no AI.
// ============================================================================
import prisma from '@meddoc/db';

import { templateNativePdfEnabled } from '@/config/template-native-pdf';
import { getTemplateCanvas } from './store';
import { fillPdfTemplate, type PdfFillAnchor } from './fill-engine';
import { buildPdfFillTexts } from './note-to-texts';
import { sanitizeExportedSoap, coerceHeaderFields, extractSurgeonFromNote } from '@/lib/visit-export';
import type { NoteTemplateSection } from '@/worker/note-templates/system-default-template';

/** Shape-guard stored anchors (defense — they were written server-side at
 *  certify, but re-validate the essentials before drawing). */
function coerceAnchors(raw: unknown): PdfFillAnchor[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((a) => {
    if (!a || typeof a !== 'object') return [];
    const o = a as Record<string, unknown>;
    const nums = ['page', 'yTop', 'yBottom', 'firstLineX', 'wrapX', 'rightEdge', 'fontSize'];
    if (typeof o.key !== 'string' || typeof o.label !== 'string') return [];
    if (nums.some((n) => typeof o[n] !== 'number')) return [];
    return [o as unknown as PdfFillAnchor];
  });
}

/**
 * Build the native-filled PDF for a visit, or null when native fill does not
 * apply (flag off / not owned / template not certified / no canvas).
 */
export async function nativePdfExport(visitId: string, userId: string): Promise<Buffer | null> {
  if (!templateNativePdfEnabled()) return null;

  const visit = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: {
      userId: true,
      patientName: true,
      status: true,
      createdAt: true,
      signedAt: true,
      soapFinal: true,
      signedSoap: true,
      noteTemplate: { select: { id: true, sections: true, styleProfile: true } },
    },
  });
  if (!visit || visit.userId !== userId || !visit.noteTemplate) return null;

  const sp = ((visit.noteTemplate.styleProfile ?? {}) as Record<string, unknown>) || {};
  if (sp.pdfNativeCertified !== true) return null;
  const anchors = coerceAnchors(sp.pdfNativeAnchors);
  if (anchors.length === 0) return null;

  const canvas = await getTemplateCanvas(visit.noteTemplate.id);
  if (!canvas) return null;

  const raw =
    visit.status === 'SIGNED'
      ? visit.signedSoap ?? visit.soapFinal ?? ''
      : visit.soapFinal ?? '';
  const noteText = sanitizeExportedSoap(raw);
  const visitDate = visit.signedAt ?? visit.createdAt;

  const texts = buildPdfFillTexts({
    noteText,
    sections: (visit.noteTemplate.sections as unknown as NoteTemplateSection[]) ?? [],
    headerFields: coerceHeaderFields(sp.headerFields),
    headerCtx: { patientName: visit.patientName, visitDate, soapText: noteText },
  });

  const surgeon = extractSurgeonFromNote(noteText);
  const signedLine = visit.signedAt
    ? `Electronically signed${surgeon ? ` by ${surgeon}` : ''} on ${visitDate.toISOString().slice(0, 10)} · QuillMD`
    : null;

  const out = await fillPdfTemplate({
    canvasPdf: new Uint8Array(canvas),
    anchors,
    texts,
    signedStatusLine: signedLine,
  });
  return Buffer.from(out);
}
