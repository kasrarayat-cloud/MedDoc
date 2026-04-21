import type { Metadata } from 'next';
import { notFound, redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import { auth } from '@/lib/nextauth';
import { NavBar } from '@/components/nav-bar';
import { PageWrapper } from '@/components/page-wrapper';
import { AudioUploader } from '@/components/audio-uploader';
import { VoiceDictator } from '@/components/voice-dictator';
import { TextComposer } from '@/components/text-composer';

import { ProcessingState } from './processing-state';
import { VisitReadyView, type Utterance, type SpeakerInfo } from './visit-ready-view';
import { VisitFailedView } from './visit-failed-view';
import { BackToPatientLink } from './back-link';
import { VisitLifecycleActions } from './visit-lifecycle-actions';
import { EditDraftDialog } from './edit-draft-dialog';

// T-M16.2: the flag check moved to @/lib/email-enabled as the single
// source of truth (used by signup, login, forgot-password, change-
// email, and the Sign & Send modal). See that module for the
// RESEND_API_KEY + RESEND_FROM_VERIFIED reasoning.
import { isEmailDeliveryEnabled } from '@/lib/email-enabled';

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
  AUTOMATING: 'Generating codes, prescriptions, and summary',
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
  TranscribeVisitStatus.AUTOMATING,
];

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
        patientId: true,
        patientName: true,
        specialty: true,
        chiefComplaint: true,
        inputMode: true,
        status: true,
        // T-M17.3: feed the lifecycle banner + action buttons.
        deletedAt: true,
        archivedAt: true,
        // Commit 7 — Edit Draft dialog needs the full patient record
        // to render the "current patient" pill. Only used when the
        // visit is a draft; cheap to include unconditionally.
        patient: {
          select: {
            id: true,
            name: true,
            dateOfBirth: true,
            externalId: true,
          },
        },
        audioKey: true,
        audioDurationSec: true,
        dictationAudioKey: true,
        dictationDurationSec: true,
        rawTextInput: true,
        transcriptRaw: true,
        transcriptText: true,
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
        // T-M6 automation outputs.
        icdCodes: true,
        cptCodes: true,
        rxDrafts: true,
        referrals: true,
        patientSummary: true,
        confidenceScores: true,
        // T-M24 — surface the template download tab when the worker
        // has produced a filledTemplate. The join gives us the name
        // for the button label; `deletedAt` check is done below
        // since the filled JSON remains valid even if the source
        // template was soft-deleted after generation.
        templateId: true,
        filledTemplate: true,
        template: {
          select: { id: true, name: true, deletedAt: true },
        },
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
          <BackToPatientLink patientId={visit.patientId} />
        </div>

        <VisitLifecycleActions
          visitId={visit.id}
          status={visit.status}
          deletedAt={visit.deletedAt ? visit.deletedAt.toISOString() : null}
          archivedAt={
            visit.archivedAt ? visit.archivedAt.toISOString() : null
          }
          hasInput={
            visit.audioKey !== null ||
            visit.dictationAudioKey !== null ||
            (visit.rawTextInput !== null && visit.rawTextInput.length > 0)
          }
          editSlot={
            // Only offer Edit while the visit is a QUEUED blank
            // draft — the server enforces the same gate, the UI
            // just hides the button when it would fail.
            visit.status === TranscribeVisitStatus.QUEUED &&
            visit.audioKey === null &&
            visit.dictationAudioKey === null &&
            (visit.rawTextInput === null ||
              visit.rawTextInput.length === 0) &&
            visit.deletedAt === null &&
            visit.patient !== null ? (
              <EditDraftDialog
                visitId={visit.id}
                initialPatient={{
                  id: visit.patient.id,
                  name: visit.patient.name,
                  dateOfBirth: visit.patient.dateOfBirth
                    ? visit.patient.dateOfBirth.toISOString().slice(0, 10)
                    : null,
                  externalId: visit.patient.externalId,
                }}
                initialSpecialty={visit.specialty}
                initialChiefComplaint={visit.chiefComplaint}
                initialInputMode={
                  visit.inputMode as
                    | 'audio_upload'
                    | 'voice_dictation'
                    | 'text_notes'
                }
              />
            ) : null
          }
        />

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
            doctorEmail={user.email}
            emailEnabled={isEmailDeliveryEnabled()}
            inputMode={visit.inputMode}
            status={visit.status}
            audioKey={visit.audioKey}
            audioDurationSec={visit.audioDurationSec}
            dictationAudioKey={visit.dictationAudioKey}
            dictationDurationSec={visit.dictationDurationSec}
            rawTextInput={visit.rawTextInput}
            transcriptRaw={visit.transcriptRaw as unknown}
            transcriptText={visit.transcriptText}
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
            icdCodes={visit.icdCodes as unknown}
            cptCodes={visit.cptCodes as unknown}
            rxDrafts={visit.rxDrafts as unknown}
            referrals={visit.referrals as unknown}
            patientSummary={visit.patientSummary}
            confidenceScores={visit.confidenceScores as unknown}
            filledTemplate={visit.filledTemplate}
            template={
              visit.template
                ? { id: visit.template.id, name: visit.template.name }
                : null
            }
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
  doctorEmail: string;
  emailEnabled: boolean;
  inputMode: string;
  status: TranscribeVisitStatus;
  audioKey: string | null;
  audioDurationSec: number | null;
  dictationAudioKey: string | null;
  dictationDurationSec: number | null;
  rawTextInput: string | null;
  transcriptRaw: unknown;
  transcriptText: string | null;
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
  icdCodes: unknown;
  cptCodes: unknown;
  rxDrafts: unknown;
  referrals: unknown;
  patientSummary: string | null;
  confidenceScores: unknown;
  filledTemplate: string | null;
  template: { id: string; name: string } | null;
}

function VisitBody(props: VisitBodyProps) {
  // ── Input stage — show the right "collect input" UI per mode ──
  if (props.status === TranscribeVisitStatus.QUEUED) {
    if (props.inputMode === 'audio_upload' && !props.audioKey) {
      return <AudioUploader visitId={props.visitId} />;
    }
    if (
      props.inputMode === 'voice_dictation' &&
      !props.dictationAudioKey
    ) {
      return <VoiceDictator visitId={props.visitId} />;
    }
    if (props.inputMode === 'text_notes' && !props.rawTextInput) {
      return <TextComposer visitId={props.visitId} />;
    }
    // else: input is already captured — fall through to the
    // "processing / ready / failed" branches below.
  }

  // ── Processing — any worker-active state, plus QUEUED with captured
  //    input (worker just hasn't picked up the job yet) ──
  if (
    PROCESSING_STATES.includes(props.status) ||
    (props.status === TranscribeVisitStatus.QUEUED &&
      (props.audioKey ||
        props.dictationAudioKey ||
        props.rawTextInput))
  ) {
    return (
      <ProcessingState
        visitId={props.visitId}
        initialStatus={props.status}
        initialHint={PROGRESS_HINT[props.status]}
      />
    );
  }

  // ── Failed ──
  if (props.status === TranscribeVisitStatus.FAILED) {
    return (
      <VisitFailedView visitId={props.visitId} reason={props.reviewReason} />
    );
  }

  // ── READY or SIGNED ──
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

  // Pick the duration number to show in the Pipeline tab: audioDurationSec
  // for audio_upload, dictationDurationSec for voice_dictation, null
  // for text_notes (there's no media to time).
  const displayDurationSec =
    props.inputMode === 'audio_upload'
      ? props.audioDurationSec
      : props.inputMode === 'voice_dictation'
        ? props.dictationDurationSec
        : null;

  return (
    <VisitReadyView
      visitId={props.visitId}
      doctorEmail={props.doctorEmail}
      emailEnabled={props.emailEnabled}
      inputMode={props.inputMode}
      soapText={soapText}
      readonly={readonly}
      needsReview={props.needsReview}
      reviewReason={props.reviewReason}
      overallQuality={overallQuality}
      utterances={utterances}
      speakerMap={speakerMap}
      dictationTranscript={
        props.inputMode === 'voice_dictation' ? props.transcriptText : null
      }
      rawTextInput={
        props.inputMode === 'text_notes' ? props.rawTextInput : null
      }
      entities={props.entities}
      critique={critique}
      icdCodes={props.icdCodes}
      cptCodes={props.cptCodes}
      rxDrafts={props.rxDrafts}
      referrals={props.referrals}
      patientSummary={props.patientSummary}
      confidenceScores={props.confidenceScores}
      durationSec={displayDurationSec}
      costCents={props.processingCostCents}
      processingStartedAt={props.processingStartedAt?.toISOString() ?? null}
      processingFinishedAt={props.processingFinishedAt?.toISOString() ?? null}
      // T-M20.3: gate the Pipeline tab (dev-facing raw entities JSON +
      // cost + wall-time) behind a runtime env flag. Server component
      // so the check happens per-request — dev can flip it via env
      // override without a rebuild. Default false: hidden in prod.
      showPipelineTab={process.env.NEXT_PUBLIC_SHOW_PIPELINE_TAB === 'true'}
      // T-M24 — show the Download-template button when the worker
      // filled the template. Both fields must be present; filled
      // without a template means the source row was deleted before
      // we could render the link (we leave the filled JSON around
      // for re-renders, but the name + FK are what the button needs).
      filledTemplate={props.filledTemplate}
      template={props.template}
    />
  );
}
