// ============================================================================
// /visits/[id]/record — cinematic live recording (HANDOFF §2.3 Gate 9).
// ----------------------------------------------------------------------------
// Full-bleed layout: centered LiveOrb + timer. MediaRecorder flow reuses
// the existing /api/visits/[id]/dictation/upload endpoint so the worker
// pipeline runs unchanged. The scribe-ws live-transcript integration is
// a follow-up — the right rail shows a "listening…" placeholder until
// the worker produces a transcript.
//
// Mark Moment button stores timestampMs offsets locally and flushes
// them into TranscribeVisit.markedMoments on stop via a PATCH-style
// POST so the Transcript tab can render glyph markers on the timeline
// after the visit lands in READY.
// ============================================================================

import type { Metadata } from 'next';
import { notFound, redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { auth } from '@/lib/nextauth';
import { AppFrame } from '@/components/ui/app-frame';
import { RecordingClient } from './recording-client';

export const metadata: Metadata = { title: 'Recording' };

export default async function RecordVisitPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  type VisitRow = {
    id: string;
    userId: string;
    status: string;
    patient: { name: string } | null;
    specialty: string;
  };
  const visit: VisitRow | null = await prisma.transcribeVisit.findUnique({
    where: { id },
    select: {
      id: true,
      userId: true,
      status: true,
      patient: { select: { name: true } },
      specialty: true,
    },
  });
  if (!visit || visit.userId !== session.user.id) notFound();

  // Only QUEUED visits are eligible for recording. Anything further
  // along the pipeline sends the doctor to the regular visit page.
  if (visit.status !== 'QUEUED') {
    redirect(`/visits/${id}`);
  }

  return (
    <AppFrame>
      <RecordingClient
        visitId={visit.id}
        patientName={visit.patient?.name ?? 'Patient'}
        specialty={visit.specialty}
      />
    </AppFrame>
  );
}
