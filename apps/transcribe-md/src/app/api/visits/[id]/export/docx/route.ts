// ============================================================================
// GET /api/visits/[id]/export/docx (T-M7)
// ----------------------------------------------------------------------------
// Same shape as the PDF route; different generator + Content-Type.
// ============================================================================

import { NextResponse } from 'next/server';

import { auth } from '@/lib/nextauth';
import { filenameSlug, formatVisitDate } from '@/lib/visit-export';
import { loadVisitExportData } from '@/lib/visit-export-server';
import { generateVisitDocx } from '@/lib/docx-generator';
import { logDelivery } from '@/lib/deliveries';
import { templateNativeDocxEnabled } from '@/config/template-native-docx';
import { loadNativeTemplateDocxForVisit } from '@/lib/template-twin/native-export';

import { apiError, withApiHandler } from '@/lib/api-error';
import { redactPhi } from '@meddoc/ai';
import { logAudit } from '@/lib/audit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 60;

const DOCX_MIME =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

export const GET = withApiHandler<{ id: string }>(
  'api:visits:export:docx',
  async (_req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError('unauthorized', 401);

    const data = await loadVisitExportData(visitId, userId);
    if (!data) return apiError('not found', 404);

    let docx: Buffer;
    let nativeTemplate = false;
    try {
      // Flag ON: if this visit was filled against a Template Twin native
      // template, serve the doctor's OWN roundtrip-verified document; else fall
      // back to the QuillMD-styled export. Flag OFF: styled path only, byte-
      // identical to the live route. The sign route is NOT involved either way.
      const native = templateNativeDocxEnabled()
        ? await loadNativeTemplateDocxForVisit(visitId, userId)
        : null;
      if (native) {
        docx = native.bytes;
        nativeTemplate = true;
      } else {
        docx = await generateVisitDocx(data);
      }
    } catch (err) {
      console.error(
        '[api:visits:export:docx] generation failed:',
        redactPhi(err instanceof Error ? err.message : err)
      );
      return apiError('docx generation failed', 500);
    }

    logDelivery({
      visitId,
      channel: 'docx',
      sizeBytes: docx.byteLength,
    });
    void logAudit({
      action: 'EXPORT_DOCX_DOWNLOADED',
      targetType: 'TranscribeVisit',
      targetId: visitId,
      metadata: {
        sizeBytes: docx.byteLength,
        isSigned: data.signedAt !== null,
        // Additive only when a native template was actually served, so the
        // flag-OFF audit metadata stays byte-identical to the live route.
        ...(nativeTemplate ? { nativeTemplate: true } : {}),
      },
    });

    const filename = `visit-${filenameSlug(data.patientName)}-${formatVisitDate(
      data.signedAt ?? data.createdAt
    )}.docx`;

    return new NextResponse(docx as unknown as BodyInit, {
      status: 200,
      headers: {
        'Content-Type': DOCX_MIME,
        'Content-Length': String(docx.byteLength),
        'Content-Disposition': `attachment; filename="${filename}"`,
        'Cache-Control': 'no-store, private',
      },
    });
  }
);
