// ============================================================================
// THE visit PDF — ONE builder, ONE truth. (Ruling #113, scoped by #116.)
// ----------------------------------------------------------------------------
// Every PDF a doctor receives of a visit is rendered HERE, and this function
// renders it by handing `generateVisitDocx`'s bytes to the Gotenberg sidecar.
// There is no second PDF builder, deliberately: `pdf-generator.ts` (pdfkit) was
// retired in this commit because it had no template or `formatHint` awareness
// at all, so the PDF download diverged from the Word export and from both
// preview surfaces — the exact drift #113 exists to end.
//
//     preview (pre-sign) ─┐
//     preview (signed)   ─┤
//     Word download      ─┼─→ generateVisitDocx ──→ (Gotenberg) ──→ PDF
//     PDF download       ─┘
//
// ⚠️ THE COST, NAMED IN ADVANCE RATHER THAN DISCOVERED IN AN INCIDENT.
// Before this change a doctor could download a signed PDF while the sidecar was
// down, because a second builder existed to fall back to. Delete-don't-hide
// leaves no fallback, so when the converter cannot render, THIS THROWS.
//
// That is the whole point, and it is RC-3's rule: the failure must be LOUD and
// NAMED. The alternatives are worse and both are forbidden here —
//   · a silent half-document (a PDF missing the sections the sidecar dropped),
//   · a DOCX wearing a PDF's content type (the browser opens garbage, the
//     doctor believes they have a signed record).
// A doctor who is told "the PDF renderer is unavailable, download the Word
// file" can act. A doctor holding a truncated PDF cannot, and does not know to.
//
// ⚠️ `convertDocxToPdf` NEVER THROWS — it returns `{ pdf: null, reason }` on
// every failure path. That fail-open shape is right for a PREVIEW and wrong for
// an EXPORT, so the translation from "null means fall back" to "null means
// refuse" happens here, once, rather than at each of the three call sites.
// ============================================================================

import { generateVisitDocx } from './docx-generator';
import { convertDocxToPdf, type ConvertFailure } from './docx-preview/convert';
import type { VisitExportData } from './visit-export';

/**
 * Thrown when the converter could not produce a PDF. Carries the converter's
 * own coded reason — `timeout` / `converter_error` / `empty_result` /
 * `too_large` — which is PHI-free by construction and safe to log and surface.
 */
export class VisitPdfUnavailableError extends Error {
  readonly reason: ConvertFailure;

  constructor(reason: ConvertFailure) {
    super(`visit PDF renderer unavailable (${reason})`);
    this.name = 'VisitPdfUnavailableError';
    this.reason = reason;
  }
}

/**
 * Render a visit as a PDF — the ONLY path to one.
 *
 * @throws {VisitPdfUnavailableError} when the sidecar cannot render. Callers
 * must surface that as a named failure; none of them may substitute another
 * artifact for it.
 */
export async function renderVisitPdf(data: VisitExportData): Promise<Buffer> {
  const docx = await generateVisitDocx(data);
  const { pdf, reason } = await convertDocxToPdf(
    new Uint8Array(docx),
    'visit.docx',
  );
  if (!pdf) {
    // `reason` is always present when pdf is null (convert.ts's contract), but
    // the fallback keeps the error total rather than trusting a comment.
    throw new VisitPdfUnavailableError(reason ?? 'converter_error');
  }
  return Buffer.from(pdf);
}
