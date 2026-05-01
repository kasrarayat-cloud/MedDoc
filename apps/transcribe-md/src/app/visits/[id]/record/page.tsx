// ============================================================================
// /visits/[id]/record — Linear V1 live-recording shell.
// Reference: docs/design-directions-v8-linear/recording.html
// ----------------------------------------------------------------------------
// 440px left column (mic + halo + waveform + status + actions) ‖ live
// transcript on the right. MediaRecorder flow reuses the existing
// /api/visits/[id]/dictation/upload endpoint so the worker pipeline
// runs unchanged. The scribe-ws live-transcript integration is a
// follow-up — the transcript area shows a "listening…" placeholder
// until the worker produces a transcript.
//
// 🔴 PROTECTED: All MediaRecorder lifecycle code lives in
// recording-client.tsx and is preserved byte-for-byte across the
// Linear V1 visual migration.
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
