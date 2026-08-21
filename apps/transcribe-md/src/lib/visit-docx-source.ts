// ============================================================================
// WHICH DOCUMENT IS THIS VISIT'S DOCUMENT? — asked ONCE, for every format.
// ----------------------------------------------------------------------------
// ⚠️ WHY THIS MODULE EXISTS. Ruling #113 established ONE builder, ONE truth:
// every visit format derives from `generateVisitDocx` via the Gotenberg sidecar,
// so the Word download and the PDF download cannot diverge. `visit-pdf.ts` still
// carries that diagram:
//
//     Word download      ─┼─→ generateVisitDocx ──→ (Gotenberg) ──→ PDF
//     PDF download       ─┘
//
// The Template Twin native path was then added to the WORD route only
// (`export/docx/route.ts` calls `loadOrComputeNativeTemplateDocxForVisit`), and
// the PDF route was never given the same branch. The diagram silently stopped
// being true.
//
// ⚠️ MEASURED ON THE OWNER'S FIRST CERTIFIED-TWIN VISIT, 2026-08-21: the Word
// download was his own letterhead — a VERIFIED fill manifest, 49,418 bytes,
// roundTripVerified — and the PDF download of THE SAME RECORD was QuillMD's
// generic layout. One record, two formats, two different documents.
//
// ⚠️ AND THE PDF ROUTE **LOOKED** COVERED, WHICH IS WHY IT SURVIVED REVIEW. It
// has a native branch — `nativePdfExport` — but that is the FLAT PDF TEMPLATE
// feature (`pdf-native`), which requires `styleProfile.pdfNativeCertified`. The
// owner's template is a DOCX-derived twin and carries no such key, so it
// declines with `not_certified` and falls through to the styled render. Two
// features named "native", one route, and the wrong one wired.
//
// So the question "which docx is this visit's docx" is answered HERE, once, and
// both routes ask it. The treatment lives on the shared thing rather than on a
// hand-kept list of callers — a list that was already wrong.
// ============================================================================
import { templateNativeDocxEnabled } from '@/config/template-native-docx';
import { loadOrComputeNativeTemplateDocxForVisit } from '@/lib/template-twin/native-export';
import { generateVisitDocx } from './docx-generator';
import { redactPhi } from '@meddoc/ai';
import type { VisitExportData } from './visit-export';

export interface VisitDocxSource {
  /** The bytes every format for this visit must derive from. */
  bytes: Buffer;
  /** True when these are the doctor's OWN roundtrip-verified document. */
  native: boolean;
  /** Why the doctor's own document was NOT used. Null when it was. */
  reason: string | null;
}

/**
 * Resolve the ONE document this visit exports as, in any format.
 *
 * A native-load failure DEGRADES to the styled export rather than failing the
 * download — the doctor always gets a valid document, never a 500 and never a
 * corrupt native one. That behaviour is inherited from the Word route, where it
 * was already correct, rather than reinvented.
 */
export async function resolveVisitDocx(
  visitId: string,
  practiceId: string,
  data: VisitExportData,
  logTag: string,
): Promise<VisitDocxSource> {
  const outcome = templateNativeDocxEnabled()
    ? await loadOrComputeNativeTemplateDocxForVisit(visitId, practiceId).catch((err) => {
        console.warn(
          `${logTag} native load failed; falling back to styled:`,
          redactPhi(err instanceof Error ? err.message : err),
        );
        return { native: null, reason: 'fill_failed' as const };
      })
    : { native: null, reason: null };

  if (outcome.native) {
    return { bytes: outcome.native.bytes, native: true, reason: null };
  }
  return { bytes: await generateVisitDocx(data), native: false, reason: outcome.reason };
}
