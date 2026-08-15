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
import { generateVisitPdf } from '@/lib/pdf-generator';
import { nativePdfExport } from '@/lib/pdf-native/export';
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
    let nativeReason = 'flag_off';
    try {
      // feat/pdf-native-fill: when the flag is ON and the visit's template is a
      // CERTIFIED flat PDF, return the doctor's OWN page with answers drawn into
      // its blanks; otherwise fall through to the styled generator. Fail-open —
      // any native-fill error falls back to the styled export, never a 500.
      let nativePdf: Buffer | null = null;
      try {
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
      pdf = nativePdf ?? (await generateVisitPdf(data));
    } catch (err) {
      console.error(
        '[api:visits:export:pdf] generation failed:',
        redactPhi(err instanceof Error ? err.message : err)
      );
      return apiError('pdf generation failed', 500);
    }
    console.info(`[api:visits:export:pdf] nativePdfApplied=${nativeApplied} reason=${nativeReason}`);

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
