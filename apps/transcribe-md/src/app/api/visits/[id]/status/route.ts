// ============================================================================
// GET /api/visits/[id]/status (T-M4)
// ----------------------------------------------------------------------------
// Polled by the AudioUploader once an upload lands and by the
// /visits/[id] "Processing…" screen. Returns the current status and a
// human-readable progress hint so the UI can show a phase label
// without owning the enum → phrase mapping.
// ============================================================================

import { NextResponse, type NextRequest } from 'next/server';

import { auth } from '@/lib/nextauth';
import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** Enum-driven label for the polling UI. Kept in sync with the 6-layer
 *  sequence so the user can see which step is running. */
const PROGRESS_HINT: Record<TranscribeVisitStatus, string> = {
  QUEUED: 'Queued — waiting for a worker',
  TRANSCRIBING: 'Transcribing audio',
  EXTRACTING: 'Identifying speakers and extracting medical entities',
  DRAFTING: 'Drafting the SOAP note',
  CRITIQUING: 'Auditing the draft for clinical accuracy',
  POLISHING: 'Applying polish fixes',
  READY: 'Ready to review',
  FAILED: 'Processing failed',
  SIGNED: 'Signed and locked',
};

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: visitId } = await params;

  const session = await auth();
  const userId = session?.user?.id;
  if (!userId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const visit = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: {
      id: true,
      userId: true,
      status: true,
      needsReview: true,
      reviewReason: true,
      audioDurationSec: true,
    },
  });
  if (!visit || visit.userId !== userId) {
    return NextResponse.json({ error: 'not found' }, { status: 404 });
  }

  const status = visit.status as TranscribeVisitStatus;
  return NextResponse.json(
    {
      visitId: visit.id,
      status,
      progressHint: PROGRESS_HINT[status] ?? status,
      needsReview: visit.needsReview,
      reviewReason: visit.reviewReason,
      audioDurationSec: visit.audioDurationSec,
    },
    { status: 200 }
  );
}
