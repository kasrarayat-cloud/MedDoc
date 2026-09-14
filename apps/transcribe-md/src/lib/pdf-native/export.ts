// ============================================================================
// PDF native export path (feat/pdf-native-fill). Server-only. Returns the
// doctor's OWN page filled with the visit's generated answers — or null to fall
// back to the styled generator. Gated: flag ON + a CERTIFIED PDF template (canvas
// + anchors stored). Deterministic; no AI.
// ============================================================================
import prisma from '@meddoc/db';
import { getDocumentProxy } from 'unpdf';
import { visitByIdScope, type PracticeId } from '@/lib/practice-scope';
import { redactPhi } from '@meddoc/ai';

import { templateNativePdfEnabled } from '@/config/template-native-pdf';
import { templateNativeDocxEnabled } from '@/config/template-native-docx';
import { getTemplateCanvas } from './store';
import { canvasHash } from './hash';
import { fillPdfTemplate, type PdfFillAnchor } from './fill-engine';
import { buildPdfFillTexts } from './note-to-texts';
import { deriveTwinAnchors } from './twin-anchor-derivation';
import { buildTwinFillTexts } from './twin-value-bridge';
import { loadCertifiedTwinExportData } from './twin-export-data';
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
  // S2-4 (#322): a CERTIFIED twin resolved a value that cannot be placed on the
  // doctor's page — a field whose label/marker is absent from the PDF, or a
  // non-scalar (table) value. The route falls back to the twin's STRUCTURAL
  // styled render, which can place every field; no clinical value is dropped.
  | 'twin_unplaceable'
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
export async function nativePdfExport(
  visitId: string,
  practiceId: PracticeId,
): Promise<NativePdfResult> {
  const miss = (reason: NativePdfReason): NativePdfResult => ({ pdf: null, applied: false, reason });

  if (!templateNativePdfEnabled()) return miss('flag_off');

  const visit = await prisma.transcribeVisit.findFirst({
    where: visitByIdScope(visitId, practiceId),
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
  if (!visit || !visit.noteTemplate) return miss('not_certified');

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

  // ── S2-4 (#322): THE CERTIFIED TWIN DECIDES WHAT FILLS ────────────────────
  // When the template's compiled twin is CERTIFIED and the visit has a VERIFIED
  // fill manifest, the doctor's page is filled by the TWIN's resolved values —
  // not the note-heading split. The anchors are re-derived FROM the twin's own
  // fields (one per field, keyed by fieldId), so the value bridge is 1:1.
  //
  // Fail-safe: any error here falls THROUGH to the note-heading path below
  // (never a throw, never a blocked export). "A value that cannot be placed"
  // (a field with a value but no anchor, or a non-scalar value) declines with a
  // coded reason so the route renders the twin's structural styled document —
  // which can place every field — instead of a partial page (ruling #322).
  if (templateNativeDocxEnabled()) {
    try {
      const twin = await loadCertifiedTwinExportData(
        visitId,
        visit.noteTemplate.id,
        String(practiceId),
      );
      if (twin) {
        const proxy = await getDocumentProxy(new Uint8Array(canvas).slice());
        const { anchors: twinAnchors, unlocatable } = await deriveTwinAnchors(
          proxy as never,
          twin.fields,
        );
        const { texts, unplaceable } = buildTwinFillTexts(twin.resolutions, twinAnchors, unlocatable);
        if (unplaceable.length > 0) return miss('twin_unplaceable');
        const signedLine = visit.signedAt
          ? `Electronically signed on ${visit.signedAt.toISOString().slice(0, 10)} · QuillMD`
          : null;
        const out = await fillPdfTemplate({
          canvasPdf: new Uint8Array(canvas),
          anchors: twinAnchors,
          texts,
          signedStatusLine: signedLine,
        });
        return { pdf: Buffer.from(out), applied: true, reason: 'true' };
      }
    } catch (twinErr) {
      // Fall through to the note-heading path — the twin fill is a refinement,
      // never a gate. Coded log only (the message can echo patient characters).
      console.error(
        '[pdf-native] twin fill failed, falling back to note-heading fill:',
        redactPhi(twinErr instanceof Error ? twinErr.message : String(twinErr)),
      );
    }
  }

  try {
    const raw =
      visit.status === 'SIGNED'
        ? visit.signedSoap ?? visit.soapFinal ?? ''
        : visit.soapFinal ?? '';
    const noteText = sanitizeExportedSoap(raw);
    // Ruling #115 — TWO DATES, and they are not the same date. This used to be
    // one `visitDate = signedAt ?? createdAt` feeding BOTH the header fill and
    // the signed line below; collapsing them meant a note signed days later
    // printed the SIGNING date as DATE OF SURGERY. Splitting them is the fix,
    // and the split has to stay: changing the header source alone would have
    // silently moved the encounter date into the signature line instead.
    const encounterDate = visit.createdAt;

    const { texts, addenda } = buildPdfFillTexts({
      noteText,
      sections: (visit.noteTemplate.sections as unknown as NoteTemplateSection[]) ?? [],
      headerFields: coerceHeaderFields(sp.headerFields),
      headerCtx: {
        patientName: visit.patientName,
        visitDate: encounterDate,
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
      ? `Electronically signed${surgeon ? ` by ${surgeon}` : ''} on ${visit.signedAt.toISOString().slice(0, 10)} · QuillMD`
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
