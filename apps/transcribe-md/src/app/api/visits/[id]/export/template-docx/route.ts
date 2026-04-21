// ============================================================================
// GET /api/visits/[id]/export/template-docx (T-M24)
// ----------------------------------------------------------------------------
// On-demand regeneration of a filled template .docx. Reads the visit's
// L7f output + the template binary from MinIO, runs docxtemplater,
// streams the resulting bytes back as an attachment.
//
// No binary is persisted — we regenerate from the stored JSON content
// dict each time the doctor downloads. Cost is ~tens of ms of
// docxtemplater runtime per request, well below the network overhead
// of the download itself.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';
import { redactPhi } from '@meddoc/ai';

import { apiError, withApiHandler } from '@/lib/api-error';
import { auth } from '@/lib/nextauth';
import { downloadTemplate } from '@/lib/minio';
import { fillTemplate } from '@/lib/template-docx-generator';
import { logDelivery } from '@/lib/deliveries';
import { formatVisitDate, filenameSlug } from '@/lib/visit-export';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export const GET = withApiHandler<{ id: string }>(
  'api:visits:export:template-docx',
  async (_req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError('unauthorized', 401);

    const visit = await prisma.transcribeVisit.findUnique({
      where: { id: visitId },
      select: {
        id: true,
        userId: true,
        patientName: true,
        signedAt: true,
        createdAt: true,
        templateId: true,
        filledTemplate: true,
        template: {
          select: {
            id: true,
            name: true,
            originalFileName: true,
            minioKey: true,
            deletedAt: true,
          },
        },
      },
    });

    if (!visit || visit.userId !== userId) return apiError('not found', 404);

    if (!visit.templateId || !visit.template) {
      return apiError(
        'This visit was not processed with a template.',
        409
      );
    }
    if (visit.template.deletedAt !== null) {
      return apiError(
        'The template used for this visit has been deleted. Re-process the visit with an active template.',
        410
      );
    }
    if (!visit.filledTemplate) {
      return apiError(
        'Template fill is still processing. Try again in a moment.',
        425
      );
    }

    // filledTemplate is JSON.stringify'd at layer-write time; parse
    // defensively so a bad row doesn't 500 — return 422 and let ops
    // investigate.
    let content: Record<string, string>;
    try {
      const parsed = JSON.parse(visit.filledTemplate) as unknown;
      if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('filledTemplate is not an object');
      }
      content = parsed as Record<string, string>;
    } catch (err) {
      console.error(
        '[api:visits:export:template-docx] filledTemplate parse failed:',
        redactPhi(err instanceof Error ? err.message : err)
      );
      return apiError(
        'Template fill output is corrupted. Re-process the visit.',
        422
      );
    }

    let templateBuffer: Buffer;
    try {
      templateBuffer = await downloadTemplate(visit.template.minioKey);
    } catch (err) {
      console.error(
        '[api:visits:export:template-docx] MinIO read failed:',
        redactPhi(err instanceof Error ? err.message : err)
      );
      return apiError(
        'Could not fetch the template right now. Try again in a minute.',
        502
      );
    }

    let filledBuffer: Buffer;
    try {
      filledBuffer = fillTemplate(templateBuffer, content);
    } catch (err) {
      // docxtemplater throws on template syntax errors (unbalanced
      // braces, broken tag names). Return 422 with the scrubbed
      // message — the doctor needs to fix their template.
      console.error(
        '[api:visits:export:template-docx] docxtemplater render failed:',
        redactPhi(err instanceof Error ? err.message : err)
      );
      return apiError(
        'Template rendering failed. Check the template for unmatched {{braces}} or stray syntax.',
        422
      );
    }

    // Fire-and-forget delivery log so the T-M7 audit trail captures
    // the download. Matches the pattern used by the PDF + standard-
    // DOCX export endpoints.
    logDelivery({
      visitId: visit.id,
      channel: 'docx',
      destination: null,
      sizeBytes: filledBuffer.length,
    });

    const dateSlug = formatVisitDate(visit.signedAt ?? visit.createdAt);
    const patientSlug = filenameSlug(visit.patientName);
    const filename = `${dateSlug}-${patientSlug}-${filenameSlug(visit.template.name)}.docx`;

    // Allocate a clean ArrayBuffer copy for NextResponse — the Buffer
    // returned by docxtemplater may be pooled.
    const arrayBufferCopy = new ArrayBuffer(filledBuffer.length);
    new Uint8Array(arrayBufferCopy).set(filledBuffer);

    return new NextResponse(arrayBufferCopy, {
      status: 200,
      headers: {
        'Content-Type':
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'Content-Disposition': `attachment; filename="${filename}"`,
        'Content-Length': String(filledBuffer.length),
        'Cache-Control': 'private, no-store',
      },
    });
  }
);
