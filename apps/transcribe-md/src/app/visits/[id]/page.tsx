import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import { auth } from '@/lib/nextauth';
import { AppFrame } from '@/components/ui/app-frame';
import { Ic } from '@/components/ui/icon';
import { type SpecialtyKind } from '@/components/ui/spec-chip';
import { AudioUploader } from '@/components/audio-uploader';
import { VoiceDictator } from '@/components/voice-dictator';
import { TextComposer } from '@/components/text-composer';

import { ProcessingState } from './processing-state';
import { VisitReadyView, type Utterance, type SpeakerInfo } from './visit-ready-view';
import { VisitFailedView } from './visit-failed-view';
import { VisitLifecycleActions } from './visit-lifecycle-actions';
import { EditDraftDialog } from './edit-draft-dialog';

import { isEmailDeliveryEnabled } from '@/lib/email-enabled';

export const metadata: Metadata = { title: 'Visit' };

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

const KNOWN_SPECIALTIES: readonly SpecialtyKind[] = [
  'cardiology',
  'pain',
  'ortho',
  'primary',
  'pulmonology',
  'ophthalmology',
];

// Phase 5 — Linear V1 meta strip pretty-prints the specialty key.
const SPECIALTY_LABEL: Record<string, string> = {
  primary: 'Family Medicine',
  cardiology: 'Cardiology',
  pain: 'Pain Management',
  ortho: 'Orthopedics',
  pulmonology: 'Pulmonology',
  ophthalmology: 'Ophthalmology',
};
function specialtyLabel(raw: string): string {
  const key = raw.toLowerCase();
  return (
    SPECIALTY_LABEL[key] ??
    raw.charAt(0).toUpperCase() + raw.slice(1).toLowerCase()
  );
}

void KNOWN_SPECIALTIES;

// Phase 5 — collapse the seven-state TranscribeVisitStatus into the
// labels the meta strip + status pill exposes.
function visitStatusLabel(status: TranscribeVisitStatus, needsReview: boolean) {
  if (status === TranscribeVisitStatus.SIGNED) return 'Signed';
  if (status === TranscribeVisitStatus.FAILED) return 'Failed';
  if (status === TranscribeVisitStatus.READY)
    return needsReview ? 'Needs review' : 'Ready';
  if (status === TranscribeVisitStatus.QUEUED) return 'Queued';
  return 'Processing';
}

function visitStatusPillClass(
  status: TranscribeVisitStatus,
  needsReview: boolean
) {
  if (status === TranscribeVisitStatus.SIGNED) {
    return 'qm-lin-pill qm-lin-pill--signed';
  }
  if (status === TranscribeVisitStatus.FAILED) {
    return 'qm-lin-pill bg-linear-danger/15 text-linear-danger';
  }
  if (status === TranscribeVisitStatus.READY) {
    return needsReview ? 'qm-lin-pill qm-lin-pill--review' : 'qm-lin-pill qm-lin-pill--ready';
  }
  if (status === TranscribeVisitStatus.QUEUED) {
    return 'qm-lin-pill qm-lin-pill--draft';
  }
  return 'qm-lin-pill qm-lin-pill--processing';
}

export default async function VisitPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const session = await auth();
  if (!session?.user?.id) redirect('/login');

  type UserRow = { name: string | null; email: string };
  type VisitRow = {
    id: string;
    userId: string;
    patientId: string;
    patientName: string | null;
    specialty: string;
    chiefComplaint: string | null;
    inputMode: string;
    status: TranscribeVisitStatus;
    signedAt: Date | null;
    deletedAt: Date | null;
    archivedAt: Date | null;
    patient: {
      id: string;
      name: string;
      dateOfBirth: Date | null;
      externalId: string | null;
    } | null;
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
    failureCategory: string | null;
    processingStartedAt: Date | null;
    processingFinishedAt: Date | null;
    processingCostCents: number | null;
    icdCodes: unknown;
    cptCodes: unknown;
    rxDrafts: unknown;
    referrals: unknown;
    patientSummary: string | null;
    confidenceScores: unknown;
  };

  const [user, visit] = (await Promise.all([
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
        signedAt: true,
        deletedAt: true,
        archivedAt: true,
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
        failureCategory: true,
        processingStartedAt: true,
        processingFinishedAt: true,
        processingCostCents: true,
        icdCodes: true,
        cptCodes: true,
        rxDrafts: true,
        referrals: true,
        patientSummary: true,
        confidenceScores: true,
      },
    }),
  ])) as [UserRow | null, VisitRow | null];

  if (!user) redirect('/login');
  if (!visit || visit.userId !== session.user.id) notFound();

  const hasInput =
    visit.audioKey !== null ||
    visit.dictationAudioKey !== null ||
    (visit.rawTextInput !== null && visit.rawTextInput.length > 0);

  const patientDisplayName =
    visit.patient?.name ?? visit.patientName ?? 'Patient';
  const statusLabel = visitStatusLabel(visit.status, visit.needsReview);
  const statusPillCls = visitStatusPillClass(visit.status, visit.needsReview);

  return (
    <AppFrame>
      {/* Linear V1 breadcrumb — sits at the top of the content
          column, hairline-separated from the meta strip below. */}
      <div
        style={{
          padding: '14px 24px 0',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontFamily: 'var(--font-sans)',
          fontSize: 13,
          color: 'var(--color-linear-text-3)',
        }}
      >
        <Link
          href="/dashboard"
          style={{
            color: 'var(--color-linear-text-3)',
            textDecoration: 'none',
          }}
        >
          Dashboard
        </Link>
        <Ic.chevRight width={12} height={12} />
        {visit.patient ? (
          <>
            <Link
              href={`/patients/${visit.patient.id}`}
              style={{
                color: 'var(--color-linear-text-3)',
                textDecoration: 'none',
              }}
            >
              {visit.patient.name}
            </Link>
            <Ic.chevRight width={12} height={12} />
          </>
        ) : null}
        <span style={{ color: 'var(--color-linear-text), inherit' }}>
          Visit · {visit.status.toLowerCase()}
        </span>
      </div>

      {/* Linear V1 patient meta strip — mono uppercase fields with
          hairline dividers. Mirrors visit-detail.html. */}
      <div
        style={{
          margin: '14px 24px 0',
          padding: '10px 0 14px',
          display: 'flex',
          alignItems: 'center',
          gap: 0,
          flexWrap: 'wrap',
          borderBottom: '1px solid var(--color-linear-hairline)',
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          color: 'var(--color-linear-text-2)',
        }}
      >
        <div
          style={{
            paddingRight: 14,
            borderRight: '1px solid var(--color-linear-hairline)',
            color: 'var(--color-linear-text)',
            fontWeight: 500,
          }}
        >
          {patientDisplayName.toUpperCase()}
        </div>
        <div
          style={{
            padding: '0 14px',
            borderRight: '1px solid var(--color-linear-hairline)',
          }}
        >
          {specialtyLabel(visit.specialty)}
        </div>
        {visit.patient?.externalId && (
          <div
            style={{
              padding: '0 14px',
              borderRight: '1px solid var(--color-linear-hairline)',
            }}
          >
            <span style={{ color: 'var(--color-linear-text-3)' }}>MRN&nbsp;</span>
            {visit.patient.externalId}
          </div>
        )}
        {visit.chiefComplaint && (
          <div
            style={{
              padding: '0 14px',
              borderRight: '1px solid var(--color-linear-hairline)',
            }}
          >
            <span style={{ color: 'var(--color-linear-text-3)' }}>CC&nbsp;</span>
            <span style={{ textTransform: 'none', letterSpacing: '-0.005em' }}>
              {visit.chiefComplaint}
            </span>
          </div>
        )}
        <div style={{ padding: '0 14px', marginLeft: 'auto' }}>
          <span className={statusPillCls} style={{ textTransform: 'uppercase' }}>
            {statusLabel}
          </span>
        </div>
      </div>

      <div style={{ padding: '14px 24px 0' }}>
        <VisitLifecycleActions
          visitId={visit.id}
          status={visit.status}
          deletedAt={visit.deletedAt ? visit.deletedAt.toISOString() : null}
          archivedAt={
            visit.archivedAt ? visit.archivedAt.toISOString() : null
          }
          hasInput={hasInput}
          editSlot={
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
      </div>

      <div style={{ padding: '18px 24px 48px' }}>
        <VisitBody
          visitId={visit.id}
          doctorEmail={user.email}
          doctorName={user.name}
          specialty={specialtyLabel(visit.specialty)}
          emailEnabled={isEmailDeliveryEnabled()}
          inputMode={visit.inputMode}
          status={visit.status}
          signedAt={visit.signedAt}
          audioKey={visit.audioKey}
          audioDurationSec={visit.audioDurationSec}
          dictationAudioKey={visit.dictationAudioKey}
          dictationDurationSec={visit.dictationDurationSec}
          rawTextInput={visit.rawTextInput}
          transcriptRaw={visit.transcriptRaw}
          transcriptText={visit.transcriptText}
          speakerMap={visit.speakerMap}
          entities={visit.entities}
          critique={visit.critique}
          soapFinal={visit.soapFinal}
          signedSoap={visit.signedSoap}
          needsReview={visit.needsReview}
          reviewReason={visit.reviewReason}
          failureCategory={visit.failureCategory}
          processingStartedAt={visit.processingStartedAt}
          processingFinishedAt={visit.processingFinishedAt}
          processingCostCents={visit.processingCostCents}
          icdCodes={visit.icdCodes}
          cptCodes={visit.cptCodes}
          rxDrafts={visit.rxDrafts}
          referrals={visit.referrals}
          patientSummary={visit.patientSummary}
          confidenceScores={visit.confidenceScores}
        />
      </div>
    </AppFrame>
  );
}

interface VisitBodyProps {
  visitId: string;
  doctorEmail: string;
  /** Batch H — display name of the signer (i.e., the visit owner who
   *  is the same person as the authed user per the ownership guard).
   *  Threaded into VisitReadyView for the "Signed at … by …" card. */
  doctorName: string | null;
  /** Phase 5.1 — pretty-printed specialty for the Transcript V3
   *  metadata rail. */
  specialty: string;
  emailEnabled: boolean;
  inputMode: string;
  status: TranscribeVisitStatus;
  /** Batch H — moment the doctor signed the note (or null while
   *  drafting). Drives the visual signed-state pill + calm card. */
  signedAt: Date | null;
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
  failureCategory: string | null;
  processingStartedAt: Date | null;
  processingFinishedAt: Date | null;
  processingCostCents: number | null;
  icdCodes: unknown;
  cptCodes: unknown;
  rxDrafts: unknown;
  referrals: unknown;
  patientSummary: string | null;
  confidenceScores: unknown;
}

function VisitBody(props: VisitBodyProps) {
  if (props.status === TranscribeVisitStatus.QUEUED) {
    if (props.inputMode === 'audio_upload' && !props.audioKey) {
      return <AudioUploader visitId={props.visitId} />;
    }
    if (
      props.inputMode === 'voice_dictation' &&
      !props.dictationAudioKey
    ) {
      return <VoiceDictator visitId={props.visitId} theme="clinician" />;
    }
    if (props.inputMode === 'text_notes' && !props.rawTextInput) {
      return <TextComposer visitId={props.visitId} />;
    }
  }

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

  if (props.status === TranscribeVisitStatus.FAILED) {
    return (
      <VisitFailedView
        visitId={props.visitId}
        reason={props.reviewReason}
        failureCategory={props.failureCategory}
      />
    );
  }

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

  const soapText =
    props.status === TranscribeVisitStatus.SIGNED
      ? (props.signedSoap ?? props.soapFinal ?? '')
      : (props.soapFinal ?? '');

  const durationSec =
    props.inputMode === 'voice_dictation'
      ? props.dictationDurationSec
      : props.audioDurationSec;

  const showPipelineTab =
    process.env.NEXT_PUBLIC_SHOW_PIPELINE_TAB === 'true';

  return (
    <VisitReadyView
      visitId={props.visitId}
      inputMode={props.inputMode}
      soapText={soapText}
      readonly={props.status === TranscribeVisitStatus.SIGNED}
      utterances={utterances}
      speakerMap={speakerMap}
      dictationTranscript={props.transcriptText}
      rawTextInput={props.rawTextInput}
      entities={props.entities}
      critique={critique}
      icdCodes={props.icdCodes}
      cptCodes={props.cptCodes}
      rxDrafts={props.rxDrafts}
      referrals={props.referrals}
      patientSummary={props.patientSummary}
      confidenceScores={props.confidenceScores}
      durationSec={durationSec}
      costCents={props.processingCostCents}
      processingStartedAt={
        props.processingStartedAt
          ? props.processingStartedAt.toISOString()
          : null
      }
      processingFinishedAt={
        props.processingFinishedAt
          ? props.processingFinishedAt.toISOString()
          : null
      }
      doctorEmail={props.doctorEmail}
      emailEnabled={props.emailEnabled}
      showPipelineTab={showPipelineTab}
      signedAt={
        props.signedAt ? props.signedAt.toISOString() : null
      }
      signedByName={props.doctorName}
      specialtyLabel={props.specialty}
      recordedByName={props.doctorName}
    />
  );
}
