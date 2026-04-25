import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import { auth } from '@/lib/nextauth';
import { AppFrame } from '@/components/ui/app-frame';
import { Ic } from '@/components/ui/icon';
import { SpecChip, type SpecialtyKind } from '@/components/ui/spec-chip';
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
function toSpecKind(raw: string): SpecialtyKind {
  const lower = raw.toLowerCase() as SpecialtyKind;
  return KNOWN_SPECIALTIES.includes(lower) ? lower : 'primary';
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

  const isReadyOrSigned =
    visit.status === TranscribeVisitStatus.READY ||
    visit.status === TranscribeVisitStatus.SIGNED;

  const patientDisplayName =
    visit.patient?.name ?? visit.patientName ?? 'Patient';
  const nameTrim = patientDisplayName.trim();
  const nameSpaceIdx = nameTrim.lastIndexOf(' ');
  const nameFirst =
    nameSpaceIdx >= 0 ? nameTrim.slice(0, nameSpaceIdx) : nameTrim;
  const nameLast = nameSpaceIdx >= 0 ? nameTrim.slice(nameSpaceIdx + 1) : '';

  return (
    <AppFrame>
      <div
        style={{
          padding: '18px 32px 0',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontSize: 12.5,
          color: 'var(--fg-3)',
        }}
      >
        <Link
          href="/dashboard"
          style={{ color: 'var(--fg-3)', textDecoration: 'none' }}
        >
          Dashboard
        </Link>
        <Ic.chevRight width={12} height={12} />
        {visit.patient ? (
          <>
            <Link
              href={`/patients/${visit.patient.id}`}
              style={{ color: 'var(--fg-3)', textDecoration: 'none' }}
            >
              {visit.patient.name}
            </Link>
            <Ic.chevRight width={12} height={12} />
          </>
        ) : null}
        <span style={{ color: 'var(--fg)' }}>
          Visit · {visit.status.toLowerCase()}
        </span>
      </div>

      {isReadyOrSigned && (
        <VisitReadyHeader
          title={
            <>
              {nameFirst}
              {nameLast && (
                <>
                  {' '}
                  <em style={{ color: 'var(--accent-bright)' }}>{nameLast}</em>
                </>
              )}
            </>
          }
          specialty={visit.specialty}
          chiefComplaint={visit.chiefComplaint}
          status={visit.status}
          needsReview={visit.needsReview}
        />
      )}

      <div style={{ padding: '12px 32px 0' }}>
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

      <div style={{ padding: '18px 32px 48px' }}>
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

function VisitReadyHeader({
  title,
  specialty,
  chiefComplaint,
  status,
  needsReview,
}: {
  title: React.ReactNode;
  specialty: string;
  chiefComplaint: string | null;
  status: TranscribeVisitStatus;
  needsReview: boolean;
}) {
  const signed = status === TranscribeVisitStatus.SIGNED;
  const statusLabel = signed ? 'Signed' : needsReview ? 'Needs review' : 'Ready';
  const statusClass = signed
    ? 'qm-status qm-status-signed'
    : needsReview
      ? 'qm-status qm-status-review'
      : 'qm-status qm-status-ready';
  return (
    <div
      style={{
        padding: '16px 32px 24px',
        display: 'flex',
        alignItems: 'flex-end',
        gap: 20,
        borderBottom: '1px solid var(--line)',
        flexWrap: 'wrap',
      }}
    >
      <div style={{ flex: 1, minWidth: 280 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            marginBottom: 10,
          }}
        >
          <SpecChip kind={toSpecKind(specialty)} size="md" />
          <span className={statusClass}>{statusLabel}</span>
        </div>
        <h1
          className="qm-serif"
          style={{
            margin: 0,
            fontSize: 34,
            fontWeight: 400,
            letterSpacing: '-0.02em',
            lineHeight: 1.1,
          }}
        >
          {title}
        </h1>
        {chiefComplaint && (
          <p
            style={{
              margin: '8px 0 0',
              fontSize: 13.5,
              color: 'var(--fg-3)',
              lineHeight: 1.5,
            }}
          >
            <span
              style={{
                fontFamily: 'var(--mono)',
                fontSize: 11.5,
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
                color: 'var(--fg-4)',
                marginRight: 8,
              }}
            >
              CC
            </span>
            {chiefComplaint}
          </p>
        )}
      </div>
    </div>
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
      return <VoiceDictator visitId={props.visitId} />;
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
    />
  );
}
