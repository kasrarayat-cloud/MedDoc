// ============================================================================
// GET /api/visits/[id]/export/docx (T-M7)
// ----------------------------------------------------------------------------
// Same shape as the PDF route; different generator + Content-Type.
// ============================================================================

import { NextResponse } from 'next/server';

import { getSession } from '@/lib/auth';
import { filenameSlug, formatVisitDate } from '@/lib/visit-export';
import { loadVisitExportData } from '@/lib/visit-export-server';
import { generateVisitDocx } from '@/lib/docx-generator';
import { logDelivery } from '@/lib/deliveries';
import { templateNativeDocxEnabled } from '@/config/template-native-docx';
import { loadOrComputeNativeTemplateDocxForVisit } from '@/lib/template-twin/native-export';

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

    const session = await getSession();
    const userId = session?.user.id;
    if (!userId) return apiError('unauthorized', 401);

    const data = await loadVisitExportData(visitId, session.user.practiceId);
    if (!data) return apiError('not found', 404);

    let docx: Buffer;
    let nativeTemplate = false;
    // Why the doctor's own document was NOT returned. Mirrors the PDF route's
    // nativePdfReason so a styled fallback is never silent on either path.
    let nativeReason: string | null = null;
    try {
      // Flag ON: if this visit was filled against a Template Twin native
      // template, serve the doctor's OWN roundtrip-verified document; else fall
      // back to the QuillMD-styled export. Flag OFF: styled path only, byte-
      // identical to the live route. The sign route is NOT involved either way.
      // A native-load failure (MinIO read / sha256 or size integrity mismatch)
      // DEGRADES to the styled export rather than failing the download — the
      // doctor always gets a valid document, never a 500 or a corrupt native one.
      const outcome = templateNativeDocxEnabled()
        ? await loadOrComputeNativeTemplateDocxForVisit(visitId, userId).catch((err) => {
            console.warn(
              '[api:visits:export:docx] native load failed; falling back to styled:',
              redactPhi(err instanceof Error ? err.message : err)
            );
            return { native: null, reason: 'fill_failed' as const };
          })
        : { native: null, reason: null };
      if (outcome.native) {
        docx = outcome.native.bytes;
        nativeTemplate = true;
      } else {
        nativeReason = outcome.reason;
        docx = await generateVisitDocx(data);
      }
      console.info(
        `[api:visits:export:docx] nativeTemplateApplied=${nativeTemplate} reason=${nativeReason ?? 'n/a'}`
      );
    } catch (err) {
      console.error(
        '[api:visits:export:docx] generation failed:',
        redactPhi(err instanceof Error ? err.message : err)
      );
      return apiError('docx generation failed', 500);
    }

    logDelivery({
      visitId,
      practiceId: session.user.practiceId,
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
        // Only when the flag is ON and we fell back — keeps flag-OFF audit
        // metadata byte-identical to the live route.
        ...(!nativeTemplate && nativeReason ? { nativeTemplateReason: nativeReason } : {}),
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
