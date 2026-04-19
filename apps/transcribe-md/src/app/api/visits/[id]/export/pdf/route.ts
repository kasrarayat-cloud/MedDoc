// ============================================================================
// GET /api/visits/[id]/export/pdf (T-M7)
// ----------------------------------------------------------------------------
// Generates the PDF on the fly — no caching layer. For T-M7 that's fine;
// if we ever see measurable traffic on re-exports we can memoise per
// (visitId, signedAt) into MinIO. Today's bottleneck is the upstream
// pipeline, not the PDF render.
// ============================================================================

import { NextResponse, type NextRequest } from 'next/server';

import { auth } from '@/lib/nextauth';
import { filenameSlug, formatVisitDate } from '@/lib/visit-export';
import { loadVisitExportData } from '@/lib/visit-export-server';
import { generateVisitPdf } from '@/lib/pdf-generator';
import { logDelivery } from '@/lib/deliveries';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 60;

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: visitId } = await params;

  const session = await auth();
  const userId = session?.user?.id;
  if (!userId) {
    return new NextResponse('unauthorized', { status: 401 });
  }

  const data = await loadVisitExportData(visitId, userId);
  if (!data) {
    return new NextResponse('not found', { status: 404 });
  }

  let pdf: Buffer;
  try {
    pdf = await generateVisitPdf(data);
  } catch (err) {
    console.error('[pdf-export] generation failed:', err);
    return new NextResponse('pdf generation failed', { status: 500 });
  }

  logDelivery({
    visitId,
    channel: 'pdf',
    sizeBytes: pdf.byteLength,
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
