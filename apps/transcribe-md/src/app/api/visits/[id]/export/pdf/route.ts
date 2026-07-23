// ============================================================================
// GET /api/visits/[id]/export/pdf (T-M7)
// ----------------------------------------------------------------------------
// Generates the PDF on the fly — no caching layer. For T-M7 that's fine;
// if we ever see measurable traffic on re-exports we can memoise per
// (visitId, signedAt) into MinIO. Today's bottleneck is the upstream
// pipeline, not the PDF render.
// ============================================================================

import { NextResponse } from 'next/server';

import { auth } from '@/lib/nextauth';
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

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError('unauthorized', 401);

    const data = await loadVisitExportData(visitId, userId);
    // 404 covers both "missing" and "not yours" — anti-enumeration.
    if (!data) return apiError('not found', 404);

    let pdf: Buffer;
    try {
      // feat/pdf-native-fill: when the flag is ON and the visit's template is a
      // CERTIFIED flat PDF, return the doctor's OWN page with answers drawn into
      // its blanks; otherwise fall through to the styled generator. Fail-open —
      // any native-fill error falls back to the styled export, never a 500.
      let nativePdf: Buffer | null = null;
      try {
        nativePdf = await nativePdfExport(visitId, userId);
      } catch (nativeErr) {
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

    logDelivery({
      visitId,
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
      },
    });

    const filename = `visit-${filenameSlug(data.patientName)}-${formatVisitDate(
      data.signedAt ?? data.createdAt
    )}.pdf`;

    return new NextResponse(pdf as unknown as BodyInit, {
      status: 200,
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Length': String(pdf.byteLength),
        'Content-Disposition': `attachment; filename="${filename}"`,
        'Cache-Control': 'no-store, private',
      },
    });
  }
);
