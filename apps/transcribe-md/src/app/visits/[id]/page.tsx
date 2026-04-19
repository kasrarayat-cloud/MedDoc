import type { Metadata } from 'next';
import { notFound, redirect } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import { auth } from '@/lib/nextauth';
import { NavBar } from '@/components/nav-bar';
import { PageWrapper } from '@/components/page-wrapper';
import { SpecularButton } from '@/components/specular-button';
import { VisitOrb } from '@/components/visit-orb';
import { AudioUploader } from '@/components/audio-uploader';

import { ProcessingState } from './processing-state';
import { VisitReadyView, type Utterance, type SpeakerInfo } from './visit-ready-view';
import { VisitFailedView } from './visit-failed-view';

export const metadata: Metadata = { title: 'Visit' };

// Human-readable progress hint — duplicated from /api/visits/[id]/status
// so the initial SSR doesn't have to round-trip to itself.
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

const PROCESSING_STATES: ReadonlyArray<TranscribeVisitStatus> = [
  TranscribeVisitStatus.TRANSCRIBING,
  TranscribeVisitStatus.EXTRACTING,
  TranscribeVisitStatus.DRAFTING,
  TranscribeVisitStatus.CRITIQUING,
  TranscribeVisitStatus.POLISHING,
];

const MODE_PLACEHOLDER: Record<string, string> = {
  voice_dictation:
    'Voice dictation is coming in the next release. This mode will let you ' +
    'dictate a short summary into your mic and have it expanded into a full ' +
    'SOAP note. For now, please use Upload audio or Text to SOAP.',
  text_notes:
    'Text to SOAP is coming in the next release. This mode will let you type ' +
    'bullet points and have AI expand them into a full SOAP note. For now, ' +
    'please use Upload audio.',
};

export default async function VisitPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  const [user, visit] = await Promise.all([
    prisma.user.findUnique({
      where: { id: session.user.id },
      select: { name: true, email: true },
    }),
    prisma.transcribeVisit.findUnique({
      where: { id },
      select: {
        id: true,
        userId: true,
        patientName: true,
        specialty: true,
        chiefComplaint: true,
        inputMode: true,
        status: true,
        audioKey: true,
        audioDurationSec: true,
        transcriptRaw: true,
        speakerMap: true,
        entities: true,
        critique: true,
        soapFinal: true,
        signedSoap: true,
        needsReview: true,
        reviewReason: true,
        processingStartedAt: true,
        processingFinishedAt: true,
        processingCostCents: true,
      },
    }),
  ]);

  if (!user) redirect('/login');
  // 404 on both "no such visit" AND "visit belongs to another user" so
  // an attacker can't enumerate IDs to probe for existence.
  if (!visit || visit.userId !== session.user.id) notFound();

  return (
    <PageWrapper>
      <NavBar name={user.name} email={user.email} />

      <main className="mx-auto max-w-4xl px-4 pb-24 pt-8 sm:px-6 lg:px-8 lg:pt-12">
        <div className="mb-8">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1.5 rounded-md text-[13px] text-text-tertiary transition-colors hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
            Back to dashboard
          </Link>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-[13px]">
          {visit.patientName && <Chip>Patient: {visit.patientName}</Chip>}
          <Chip>{visit.specialty}</Chip>
          {visit.chiefComplaint && <Chip>CC: {visit.chiefComplaint}</Chip>}
          <Chip>Mode: {visit.inputMode.replace(/_/g, ' ')}</Chip>
          <Chip>Status: {visit.status.toLowerCase()}</Chip>
        </div>

        <div className="mt-10">
          <VisitBody
            visitId={visit.id}
            inputMode={visit.inputMode}
            status={visit.status}
            audioKey={visit.audioKey}
            audioDurationSec={visit.audioDurationSec}
            transcriptRaw={visit.transcriptRaw as unknown}
            speakerMap={visit.speakerMap as unknown}
            entities={visit.entities as unknown}
            critique={visit.critique as unknown}
            soapFinal={visit.soapFinal}
            signedSoap={visit.signedSoap}
            needsReview={visit.needsReview}
            reviewReason={visit.reviewReason}
            processingStartedAt={visit.processingStartedAt}
            processingFinishedAt={visit.processingFinishedAt}
            processingCostCents={visit.processingCostCents}
          />
        </div>
      </main>
    </PageWrapper>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full border border-border-subtle bg-bg-surface-2 px-2.5 py-1 text-[12px] font-medium tracking-tight text-text-tertiary">
      {children}
    </span>
  );
}

interface VisitBodyProps {
  visitId: string;
  inputMode: string;
  status: TranscribeVisitStatus;
  audioKey: string | null;
  audioDurationSec: number | null;
  transcriptRaw: unknown;
  speakerMap: unknown;
  entities: unknown;
  critique: unknown;
  soapFinal: string | null;
  signedSoap: string | null;
  needsReview: boolean;
  reviewReason: string | null;
  processingStartedAt: Date | null;
  processingFinishedAt: Date | null;
  processingCostCents: number | null;
}

function VisitBody(props: VisitBodyProps) {
  // Non-audio modes show upgraded T-M5 placeholder copy.
  if (props.inputMode !== 'audio_upload') {
    return <ModePlaceholder mode={props.inputMode} />;
  }

  // State A — no audio yet.
  if (props.status === TranscribeVisitStatus.QUEUED && !props.audioKey) {
    return <AudioUploader visitId={props.visitId} />;
  }

  // State B — mid-pipeline (or QUEUED with audio already sitting in
  // MinIO waiting for the worker to wake up).
  if (
    PROCESSING_STATES.includes(props.status) ||
    (props.status === TranscribeVisitStatus.QUEUED && props.audioKey !== null)
  ) {
    return (
      <ProcessingState
        visitId={props.visitId}
        initialStatus={props.status}
        initialHint={PROGRESS_HINT[props.status]}
      />
    );
  }

  // State D — failed.
  if (props.status === TranscribeVisitStatus.FAILED) {
    return <VisitFailedView visitId={props.visitId} reason={props.reviewReason} />;
  }

  // State C — READY or SIGNED.
  const raw = (props.transcriptRaw as
    | { results?: { utterances?: Utterance[] } }
    | null) ?? null;
  const utterances: Utterance[] = raw?.results?.utterances ?? [];

  const speakerMap =
    (props.speakerMap as Record<string, SpeakerInfo> | null) ?? {};

  const critique = props.critique as
    | {
        issues: {
          severity: string;
          location: string;
          description: string;
          suggested_fix: string;
        }[];
        overall_quality: string;
        safe_to_sign_without_review: boolean;
      }
    | null;

  const overallQuality =
    critique?.overall_quality === 'high' ||
    critique?.overall_quality === 'medium' ||
    critique?.overall_quality === 'low'
      ? critique.overall_quality
      : null;

  const readonly = props.status === TranscribeVisitStatus.SIGNED;
  const soapText = readonly
    ? props.signedSoap ?? props.soapFinal ?? ''
    : props.soapFinal ?? '';

  return (
    <VisitReadyView
      visitId={props.visitId}
      soapText={soapText}
      readonly={readonly}
      needsReview={props.needsReview}
      reviewReason={props.reviewReason}
      overallQuality={overallQuality}
      utterances={utterances}
      speakerMap={speakerMap}
      entities={props.entities}
      critique={critique}
      durationSec={props.audioDurationSec}
      costCents={props.processingCostCents}
      processingStartedAt={props.processingStartedAt?.toISOString() ?? null}
      processingFinishedAt={props.processingFinishedAt?.toISOString() ?? null}
    />
  );
}

function ModePlaceholder({ mode }: { mode: string }) {
  const copy = MODE_PLACEHOLDER[mode] ?? 'This visit mode is not yet supported.';
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center py-16 text-center sm:py-24">
      <div className="relative mb-10 h-56 w-56">
        <div
          aria-hidden
          className="orb-pulse pointer-events-none absolute inset-0 -z-10 rounded-full"
          style={{
            background:
              'radial-gradient(ellipse at center, rgba(139,92,246,0.4) 0%, rgba(139,92,246,0.1) 40%, transparent 70%)',
            filter: 'blur(28px)',
          }}
        />
        <VisitOrb />
      </div>
      <p className="max-w-xl text-center text-[15px] leading-relaxed text-text-secondary">
        {copy}
      </p>
      <div className="mt-8">
        <SpecularButton href="/visits/new" variant="secondary" size="md">
          Start a new visit
        </SpecularButton>
      </div>
    </div>
  );
}
