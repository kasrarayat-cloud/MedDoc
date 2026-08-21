// ============================================================================
// GET /api/visits/[id]/export/docx (T-M7)
// ----------------------------------------------------------------------------
// Same shape as the PDF route; different generator + Content-Type.
// ============================================================================

import { NextResponse } from 'next/server';

import { getSession } from '@/lib/auth';
import { filenameSlug, formatVisitDate } from '@/lib/visit-export';
import { loadVisitExportData } from '@/lib/visit-export-server';
import { logDelivery } from '@/lib/deliveries';
import { resolveVisitDocx } from '@/lib/visit-docx-source';

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
      // ⚠️ F5-f — THE SAME FUNCTION THE PDF ROUTE ASKS. This block used to live
      // here only, and the PDF route grew its own (different, wrong) native
      // branch, so Word and PDF served two different documents for one record.
      // The decision now lives on the shared thing; a hand-kept list of callers
      // was already wrong once.
      const source = await resolveVisitDocx(
        visitId,
        session.user.practiceId,
        data,
        '[api:visits:export:docx]',
      );
      docx = source.bytes;
      nativeTemplate = source.native;
      nativeReason = source.reason;
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

    // Ruling #115 — the filename names the ENCOUNTER, so it carries the same
    // date the document's own "Visit date" row does. A file dated the signing
    // day beside a document dated the visit day is two records.
    const filename = `visit-${filenameSlug(data.patientName)}-${formatVisitDate(
      data.createdAt
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
