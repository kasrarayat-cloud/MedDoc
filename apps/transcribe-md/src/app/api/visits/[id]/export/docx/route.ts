// ============================================================================
// GET /api/visits/[id]/export/docx (T-M7)
// ----------------------------------------------------------------------------
// Same shape as the PDF route; different generator + Content-Type.
// ============================================================================

import { NextResponse, type NextRequest } from 'next/server';

import { auth } from '@/lib/nextauth';
import { filenameSlug, formatVisitDate } from '@/lib/visit-export';
import { loadVisitExportData } from '@/lib/visit-export-server';
import { generateVisitDocx } from '@/lib/docx-generator';
import { logDelivery } from '@/lib/deliveries';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 60;

const DOCX_MIME =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

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

  let docx: Buffer;
  try {
    docx = await generateVisitDocx(data);
  } catch (err) {
    console.error('[docx-export] generation failed:', err);
    return new NextResponse('docx generation failed', { status: 500 });
  }

  logDelivery({
    visitId,
    channel: 'docx',
    sizeBytes: docx.byteLength,
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
