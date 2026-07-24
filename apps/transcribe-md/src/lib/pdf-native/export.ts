// ============================================================================
// PDF native export path (feat/pdf-native-fill). Server-only. Returns the
// doctor's OWN page filled with the visit's generated answers — or null to fall
// back to the styled generator. Gated: flag ON + a CERTIFIED PDF template (canvas
// + anchors stored). Deterministic; no AI.
// ============================================================================
import prisma from '@meddoc/db';
import { redactPhi } from '@meddoc/ai';

import { templateNativePdfEnabled } from '@/config/template-native-pdf';
import { getTemplateCanvas } from './store';
import { canvasHash } from './hash';
import { fillPdfTemplate, type PdfFillAnchor } from './fill-engine';
import { buildPdfFillTexts } from './note-to-texts';
import { sanitizeExportedSoap, coerceHeaderFields, extractSurgeonFromNote } from '@/lib/visit-export';
import type { NoteTemplateSection } from '@/worker/note-templates/system-default-template';

/** Why native fill did or did not apply — logged + surfaced on every export so a
 *  silent styled fallback (e.g. an orphaned cert after template-id rotation) is
 *  never invisible again. `'true'` = the doctor's own page was returned. */
export type NativePdfReason =
  | 'true'
  | 'flag_off'
  | 'not_certified'
  | 'stale_cert'
  | 'no_canvas'
  // Coded only — NEVER carries the raw error text (which can echo patient-derived
  // characters, e.g. a WinAnsi encode failure). The detail is logged redacted.
  | 'fill_error';

export interface NativePdfResult {
  /** The native-filled PDF, or null when native fill did not apply. */
  pdf: Buffer | null;
  /** True iff `pdf` is non-null (the doctor's own page was drawn). */
  applied: boolean;
  reason: NativePdfReason;
}

/** Shape-guard stored anchors (defense — they were written server-side at
 *  certify, but re-validate the essentials before drawing). */
function coerceAnchors(raw: unknown): PdfFillAnchor[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((a) => {
    if (!a || typeof a !== 'object') return [];
    const o = a as Record<string, unknown>;
    const nums = ['page', 'yTop', 'yBottom', 'firstLineX', 'wrapX', 'rightEdge', 'fontSize'];
    if (typeof o.key !== 'string' || typeof o.label !== 'string') return [];
    if (nums.some((n) => typeof o[n] !== 'number' || !Number.isFinite(o[n] as number))) return [];
    // page must be a real 0-based index — reject negative / fractional so a
    // tampered anchor can never route a fill to a non-existent page (which the
    // engine would silently skip, dropping the content).
    if (!Number.isInteger(o.page as number) || (o.page as number) < 0) return [];
    return [o as unknown as PdfFillAnchor];
  });
}

/**
 * Build the native-filled PDF for a visit + WHY it did or did not apply. The
 * reason is logged + surfaced by the export route so a styled fallback is never
 * silent (retiring the fail-open blind spot). `pdf` is null unless `reason` is
 * `'true'`.
 */
export async function nativePdfExport(visitId: string, userId: string): Promise<NativePdfResult> {
  const miss = (reason: NativePdfReason): NativePdfResult => ({ pdf: null, applied: false, reason });

  if (!templateNativePdfEnabled()) return miss('flag_off');

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
      rawTextInput: true,
      noteTemplate: { select: { id: true, sections: true, styleProfile: true } },
    },
  });
  // No visit / not the owner / no custom template → native simply does not apply.
  if (!visit || visit.userId !== userId || !visit.noteTemplate) return miss('not_certified');

  const sp = ((visit.noteTemplate.styleProfile ?? {}) as Record<string, unknown>) || {};
  if (sp.pdfNativeCertified !== true) return miss('not_certified');
  const anchors = coerceAnchors(sp.pdfNativeAnchors);
  if (anchors.length === 0) return miss('stale_cert'); // certified flag set but anchors unusable

  const canvas = await getTemplateCanvas(visit.noteTemplate.id);
  if (!canvas) return miss('no_canvas'); // cert claims native but the canvas is gone (orphaned)

  // Integrity: when a canvas signature was recorded at certify, the stored bytes
  // must still match it. A mismatch means the canvas was swapped/corrupted under
  // the cert (or carried forward from a different form) → do NOT draw the doctor's
  // answers onto an unverified page; fall back to styled with a visible reason.
  const recordedHash = typeof sp.pdfNativeCanvasHash === 'string' ? sp.pdfNativeCanvasHash : null;
  if (recordedHash && canvasHash(canvas) !== recordedHash) return miss('stale_cert');

  try {
    const raw =
      visit.status === 'SIGNED'
        ? visit.signedSoap ?? visit.soapFinal ?? ''
        : visit.soapFinal ?? '';
    const noteText = sanitizeExportedSoap(raw);
    const visitDate = visit.signedAt ?? visit.createdAt;

    const { texts, addenda } = buildPdfFillTexts({
      noteText,
      sections: (visit.noteTemplate.sections as unknown as NoteTemplateSection[]) ?? [],
      headerFields: coerceHeaderFields(sp.headerFields),
      headerCtx: {
        patientName: visit.patientName,
        visitDate,
        soapText: noteText,
        dictationText: visit.rawTextInput,
      },
    });

    // Addendum rule — a note section with content but NO anchor on the form is
    // never dropped; it renders on a labeled "Additional documentation" page.
    const anchoredKeys = new Set(anchors.map((a) => a.key));
    const unanchoredTexts = Object.entries(texts)
      .filter(([k]) => !anchoredKeys.has(k))
      .map(([k, v]) => ({ label: labelForKey(visit.noteTemplate!, k) ?? k, text: v }));
    const allAddenda = [...addenda, ...unanchoredTexts];

    const surgeon = extractSurgeonFromNote(noteText);
    const signedLine = visit.signedAt
      ? `Electronically signed${surgeon ? ` by ${surgeon}` : ''} on ${visitDate.toISOString().slice(0, 10)} · QuillMD`
      : null;

    const out = await fillPdfTemplate({
      canvasPdf: new Uint8Array(canvas),
      anchors,
      texts,
      addenda: allAddenda,
      signedStatusLine: signedLine,
    });
    return { pdf: Buffer.from(out), applied: true, reason: 'true' };
  } catch (err) {
    // Coded reason only (PHI-safe); the detail is logged redacted by the caller.
    console.error(
      '[pdf-native] fill failed:',
      redactPhi(err instanceof Error ? err.message : String(err))
    );
    return { pdf: null, applied: false, reason: 'fill_error' };
  }
}

/** Resolve a display label for an unanchored key (section or header field). */
function labelForKey(
  template: { sections: unknown; styleProfile: unknown },
  key: string
): string | null {
  const sections = (template.sections as unknown as NoteTemplateSection[]) ?? [];
  const s = sections.find((x) => x.key === key);
  if (s) return s.label;
  const hs = coerceHeaderFields((template.styleProfile as Record<string, unknown>)?.headerFields);
  const h = hs.find((x) => x.key === key);
  return h ? h.label : null;
}
