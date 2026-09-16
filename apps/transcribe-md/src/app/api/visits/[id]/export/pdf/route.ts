// ============================================================================
// GET /api/visits/[id]/export/pdf (T-M7)
// ----------------------------------------------------------------------------
// Generates the PDF on the fly — no caching layer. For T-M7 that's fine;
// if we ever see measurable traffic on re-exports we can memoise per
// (visitId, signedAt) into MinIO. Today's bottleneck is the upstream
// pipeline, not the PDF render.
// ============================================================================

import { NextResponse } from 'next/server';

import { getSession } from '@/lib/auth';
import { filenameSlug, formatVisitDate } from '@/lib/visit-export';
import { loadVisitExportData } from '@/lib/visit-export-server';
import { renderVisitPdfFromDocx, VisitPdfUnavailableError } from '@/lib/visit-pdf';
import { resolveVisitDocx } from '@/lib/visit-docx-source';
import { nativePdfExport } from '@/lib/pdf-native/export';
import { detectedFormExport } from '@/lib/form-fill';
import { logDelivery } from '@/lib/deliveries';

import { apiError, withApiHandler } from '@/lib/api-error';
import { redactPhi } from '@meddoc/ai';
import { logAudit } from '@/lib/audit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 60;

export const GET = withApiHandler<{ id: string }>(
  'api:visits:export:pdf',
  async (_req, { params }) => {
    const { id: visitId } = await params;

    const session = await getSession();
    const userId = session?.user.id;
    if (!userId) return apiError('unauthorized', 401);

    const data = await loadVisitExportData(visitId, session.user.practiceId);
    // 404 covers both "missing" and "not yours" — anti-enumeration.
    if (!data) return apiError('not found', 404);

    let pdf: Buffer;
    // Visibility (feat/pdf-native-durable-cert): every export records whether the
    // native path applied and, if not, WHY — so a styled fallback is never silent
    // (e.g. an orphaned cert after template-id rotation surfaces as stale_cert /
    // no_canvas instead of vanishing). Logged + returned on the response.
    let nativeApplied = false;
    let nativeTwinDocx = false;
    let nativeReason = 'flag_off';
    try {
      // feat/pdf-native-fill: when the flag is ON and the visit's template is a
      // CERTIFIED flat PDF, return the doctor's OWN page with answers drawn into
      // its blanks; otherwise fall through to the styled generator. Fail-open —
      // any native-fill error falls back to the styled export, never a 500.
      let nativePdf: Buffer | null = null;
      // #326 ONE-PIPELINE (Slice B) — a CERTIFIED detected form fills the doctor's
      // OWN page from the detect→fill pipeline. Behind formDetectFillEnabled (it
      // returns flag_off → not applied → the pdf-native + styled paths below run
      // unchanged). Fail-open, exactly like the pdf-native path.
      try {
        const detected = await detectedFormExport(visitId, session.user.practiceId);
        if (detected.applied && detected.pdf) {
          nativePdf = detected.pdf;
          nativeApplied = true;
          nativeReason = detected.reason;
        }
      } catch (detErr) {
        console.error(
          '[api:visits:export:pdf] detected-form fill failed, falling back:',
          redactPhi(detErr instanceof Error ? detErr.message : detErr)
        );
      }
      if (!nativePdf) try {
        const native = await nativePdfExport(visitId, session.user.practiceId);
        nativePdf = native.pdf;
        nativeApplied = native.applied;
        nativeReason = native.reason;
      } catch (nativeErr) {
        // Coded reason only — the raw message can echo patient-derived characters
        // and, unnormalized, could even break the response header. Detail → log.
        nativeReason = 'fill_error';
        console.error(
          '[api:visits:export:pdf] native fill failed, falling back to styled:',
          redactPhi(nativeErr instanceof Error ? nativeErr.message : nativeErr)
        );
      }
      // ⚠️ F5-f — THE PDF DERIVES FROM THE SAME DOCUMENT THE WORD DOWNLOAD SERVES.
      //
      // `nativePdf` above is the FLAT PDF TEMPLATE path (`pdf-native`), which
      // declines for a DOCX-derived Template Twin. It used to fall through to
      // `renderVisitPdf(data)`, which calls `generateVisitDocx` — the STYLED
      // layout — while `export/docx/route.ts` served the doctor's OWN
      // roundtrip-verified document. One record, two formats, two documents.
      //
      // Measured on the owner's first certified-twin visit: Word was his
      // letterhead (VERIFIED manifest, 49,418 bytes), PDF was the generic
      // layout. Now both ask `resolveVisitDocx` and the PDF is a CONVERSION of
      // whatever that returns — never a second render.
      if (nativePdf) {
        pdf = nativePdf;
      } else {
        const source = await resolveVisitDocx(
          visitId,
          session.user.practiceId,
          data,
          '[api:visits:export:pdf]',
        );
        nativeTwinDocx = source.native;
        if (!source.native) nativeReason = source.reason ?? nativeReason;
        pdf = await renderVisitPdfFromDocx(source.bytes);
      }
    } catch (err) {
      // Ruling #113/#116 — the styled PDF is now a Gotenberg render of the Word
      // export, and there is no second builder to fall back to. A sidecar that
      // cannot render must therefore say so BY NAME: never a half-document,
      // never a DOCX wearing a PDF's content type. The doctor can still take
      // the Word export, and the message has to tell them that.
      if (err instanceof VisitPdfUnavailableError) {
        console.error(
          `[api:visits:export:pdf] renderer unavailable reason=${err.reason}`
        );
        return apiError(
          `the PDF renderer is unavailable (${err.reason}) — the Word export is unaffected`,
          503
        );
      }
      console.error(
        '[api:visits:export:pdf] generation failed:',
        redactPhi(err instanceof Error ? err.message : err)
      );
      return apiError('pdf generation failed', 500);
    }
    console.info(
      `[api:visits:export:pdf] nativePdfApplied=${nativeApplied} nativeTwinDocx=${nativeTwinDocx} reason=${nativeReason}`
    );

    logDelivery({
      visitId,
      practiceId: session.user.practiceId,
      channel: 'pdf',
      sizeBytes: pdf.byteLength,
    });
    void logAudit({
      action: 'EXPORT_PDF_DOWNLOADED',
      targetType: 'TranscribeVisit',
      targetId: visitId,
      metadata: {
        sizeBytes: pdf.byteLength,
        isSigned: data.signedAt !== null,
        // Native-PDF visibility — structured, non-PHI (a boolean + a coded reason).
        nativePdfApplied: nativeApplied,
        nativePdfReason: nativeReason,
      },
    });

    // Ruling #115 — the filename names the ENCOUNTER, so it carries the same
    // date the document's own "Visit date" row does. A file dated the signing
    // day beside a document dated the visit day is two records.
    const filename = `visit-${filenameSlug(data.patientName)}-${formatVisitDate(
      data.createdAt
    )}.pdf`;

    return new NextResponse(pdf as unknown as BodyInit, {
      status: 200,
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Length': String(pdf.byteLength),
        'Content-Disposition': `attachment; filename="${filename}"`,
        'Cache-Control': 'no-store, private',
        // Surfaced like a provenance signal — inspectable without opening the PDF.
        'X-Native-Pdf-Applied': String(nativeApplied),
        'X-Native-Pdf-Reason': nativeReason,
      },
    });
  }
);
