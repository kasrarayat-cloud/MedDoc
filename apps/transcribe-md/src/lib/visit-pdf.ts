// ============================================================================
// THE STYLED visit PDF — ONE builder, ONE truth. (Ruling #113, scoped by #116.)
// ----------------------------------------------------------------------------
// Every STYLED PDF of a visit is rendered HERE, by handing `generateVisitDocx`'s
// bytes to the Gotenberg sidecar.
//
// ⚠️ "STYLED" IS LOAD-BEARING AND AN EARLIER DRAFT OF THIS HEADER OMITTED IT,
// claiming instead that every PDF a doctor receives is rendered here. That was
// FALSE AS SHIPPED. `nativePdfExport` short-circuits ahead of this module in
// `export/pdf/route.ts` — `pdf = nativePdf ?? (await renderVisitPdf(data))` —
// and `NEXT_PUBLIC_TEMPLATE_NATIVE_PDF` is **true in production**, so a doctor
// whose template is a CERTIFIED flat PDF receives their OWN page and never
// reaches this function. Caught by the refutation pass over this file's own
// diff; recorded rather than quietly reworded, because a new file asserting an
// invariant it does not hold is the `DEPLOYMENT_RUNBOOK.md` §5.6 shape being
// created rather than inherited.
//
// So the scope is: the DEFAULT/styled render. There is no second STYLED PDF
// builder, deliberately: `pdf-generator.ts` (pdfkit) was
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
/**
 * The note an ARCHIVE writes in place of a signed PDF it could not render.
 *
 * ⚠️ IT DISCRIMINATES ON THE ERROR, AND THAT IS THE WHOLE POINT. The first
 * version of this text was a single fixed paragraph asserting *"nothing about
 * the visit itself is missing or wrong — the PDF renderer was unavailable"* and
 * directing the doctor to the Word export. The archive routes catch a BARE
 * error, so a throw out of `generateVisitDocx` — a malformed visit, not a
 * sidecar problem — produced that identical text: a confident false statement
 * about the cause, and a pointer at the Word export, which is the very thing
 * that had just failed and would fail again on every retry.
 *
 * **A WRONG FIELD IS WORSE THAN AN ABSENT ONE**, and this file was added
 * specifically so the absence would not be silent. Found by the refutation pass.
 *
 * Lives here, not in each route, because two copies of a doctor-facing
 * explanation drift the day either is edited.
 */
export function unavailableNote(visitId: string, err: unknown): string {
  const shared =
    `The visit's full record is in visits/${visitId}.json in this archive, and ` +
    `the visit in QuillMD itself is unaffected.\n`;

  if (err instanceof VisitPdfUnavailableError) {
    return (
      `The signed PDF for this visit could not be rendered when this archive ` +
      `was built: the PDF renderer did not return (${err.reason}).\n\n` +
      `Nothing about the visit itself is missing or wrong.\n\n` +
      shared +
      `Re-exporting later will usually succeed, and the Word export from the ` +
      `visit page is unaffected.\n`
    );
  }

  // Deliberately does NOT claim the renderer was at fault, and does NOT send
  // the doctor to the Word export — the document builder is shared, so if it
  // threw, that export will fail the same way.
  return (
    `The signed PDF for this visit could not be built when this archive was ` +
    `built.\n\n` +
    `This is NOT a renderer outage: the document itself could not be ` +
    `assembled, so re-exporting is likely to fail the same way and the Word ` +
    `export may too.\n\n` +
    shared +
    `Please report this visit id to support so the record can be checked.\n`
  );
}

/**
 * Render a PDF from DOCX bytes that have already been resolved.
 *
 * ⚠️ THE CALLER CHOOSES THE SOURCE, AND THAT IS THE POINT — F5-f. When the visit
 * is bound to a certified Template Twin the source is the doctor's OWN
 * roundtrip-verified document, so the PDF is a CONVERSION OF THE SAME ARTIFACT
 * the Word download serves rather than a second render of a different one.
 *
 * Before this, `renderVisitPdf` always called `generateVisitDocx` itself, so a
 * twin visit's PDF was the styled layout while its Word download was the
 * doctor's letterhead — one record, two documents.
 */
export async function renderVisitPdfFromDocx(docx: Buffer): Promise<Buffer> {
  return convertOrThrow(docx);
}

export async function renderVisitPdf(data: VisitExportData): Promise<Buffer> {
  const docx = await generateVisitDocx(data);
  return convertOrThrow(docx);
}

async function convertOrThrow(docx: Buffer): Promise<Buffer> {
  const { pdf, reason } = await convertDocxToPdf(
    new Uint8Array(docx),
    'visit.docx',
  );
  if (!pdf) {
    // `reason` is always present when pdf is null (convert.ts's contract), but
    // the fallback keeps the error total rather than trusting a comment.
    throw new VisitPdfUnavailableError(reason ?? 'converter_error');
  }

  // ⚠️ THE BYTES ARE CHECKED, NOT ASSUMED — and this file's own header is why.
  // `convertDocxToPdf` returns whatever a 200 carried; it checks the LENGTH and
  // never the CONTENT (`convert.ts`: empty → `empty_result`, over cap →
  // `too_large`, and otherwise straight through). So a mis-proxied sidecar
  // answering `200` with an HTML error page yields a non-empty body that this
  // function would have handed to the route, which streams it as
  // `Content-Type: application/pdf`.
  //
  // That is EXACTLY the artifact the header above declares forbidden — a
  // doctor downloading a "signed record" that is not a PDF at all — and it was
  // reachable in the first draft of this module. Found by the refutation pass
  // over this diff.
  //
  // The check stays HERE rather than in `convert.ts` on purpose: previews are
  // allowed to be tolerant and fall back to rendering the true bytes in the
  // browser, while an EXPORT must refuse. Same reason the null-means-refuse
  // translation lives here.
  if (!isPdf(pdf)) {
    throw new VisitPdfUnavailableError('converter_error');
  }
  return Buffer.from(pdf);
}

/** `%PDF` — the five-byte header every PDF starts with. */
function isPdf(bytes: Uint8Array): boolean {
  return (
    bytes.length >= 4 &&
    bytes[0] === 0x25 && // %
    bytes[1] === 0x50 && // P
    bytes[2] === 0x44 && // D
    bytes[3] === 0x46 //// F
  );
}
