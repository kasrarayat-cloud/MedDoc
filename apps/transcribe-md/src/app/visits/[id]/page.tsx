import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';
import * as Sentry from '@sentry/nextjs';

import prisma from '@meddoc/db';
import { TranscribeVisitStatus } from '@prisma/client';
import {
  emAppliesToSpecialty,
  findSpecialty,
  isImagingReportSpecialty,
  ultrasoundSpecialtyEnabled,
} from '@meddoc/shared/specialties';
import { auth } from '@/lib/nextauth';
import { logAudit } from '@/lib/audit';
import { AppFrame } from '@/components/ui/app-frame';
import { Ic } from '@/components/ui/icon';
import { type SpecialtyKind } from '@/components/ui/spec-chip';
import { AudioUploader } from '@/components/audio-uploader';
import { VoiceDictator } from '@/components/voice-dictator';
import { TextComposer } from '@/components/text-composer';

import { ProcessingTypewriter } from './processing-typewriter';
import { VisitReadyView, type Utterance, type SpeakerInfo } from './visit-ready-view';
import { VisitFailedView } from './visit-failed-view';
import { VisitLifecycleActions } from './visit-lifecycle-actions';
import { EditDraftDialog } from './edit-draft-dialog';

import { isEmailDeliveryEnabled } from '@/lib/email-enabled';
import {
  extractIcdRows,
  extractRxRows,
  extractEmOverride,
} from '@/lib/em-coding/displayed-level';
import { parseEmPendingChange, unacknowledgedEmChange } from '@/lib/em-pending-change';
import { isSkinRounds } from '@/config/skin-rounds';
import { signGates } from '@/lib/sign-gates';
import { toStageIdentity, toQueuePosition } from '@/lib/rounds/stage-data';
import { fetchStageQueueIds } from '@/lib/rounds/stage-queue';
import type { RoundsStageData } from '@/lib/rounds/stage-view-model';

export const metadata: Metadata = { title: 'Visit' };

// E/M signal extractors (icd/rx/override) now come from the shared
// @/lib/em-coding/displayed-level so the initial render, the rescore route,
// and the sign gate all coerce identically (2026-06-13 trigger-parity fix).

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

// findSpecialty (shared) handles canonical ids, legacy display names
// ('Cardiology'), and legacy short ids ('pain') — returning the
// catalog entry whose .label is the human-readable form.
function specialtyLabel(raw: string): string {
  return findSpecialty(raw).label;
}

/** The CANONICAL id, for predicates. Routed through the same resolver as the
 *  label so a legacy row ('Cardiology', 'pain') answers a predicate the same
 *  way a canonical one does — a visit created before the catalog existed is
 *  still the specialty it always was. */
function specialtyId(raw: string): string {
  return findSpecialty(raw).id;
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

  // Round 3 PR-H — A11-P1 Sentry context.
  // PHI guard: visitId is a UUID — safe. NEVER set patient name, MRN,
  // DOB, email, or transcript content as Sentry tags or context. The
  // redactPhi beforeSend hook is a backstop; primary defense is
  // never sending PHI in the first place.
  Sentry.setTag('visitId', id);
  Sentry.setUser({ id: session.user.id });

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
      // Phase 5.1.1 — V4 Extras card-stream
      mrn: string | null;
      insurance: string | null;
      problemList: unknown;
    } | null;
    createdAt: Date;
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
    soapVersion: number;
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
    /** Hybrid anchored generation — verifier-demoted claims jsonb. */
    /** E/M visible-confirm (prod smoke #311) — pending-change jsonb. */
    emPendingChange: unknown;
  emStale: boolean;
  emScoredCode: string | null;
    patientSummary: string | null;
    confidenceScores: unknown;
  };

  // Round 4 critical-Rx-override fix: pull existing override rows so
  // the rail can hydrate with ✓ Overridden chips on already-acknowledged
  // warnings. Visit-scoped + persisted, so reload + cross-tab don't
  // lose the doctor's progress through multiple critical warnings.
  const [user, visit, rxOverrides] = (await Promise.all([
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
            // Phase 5.1.1 — V4 Extras card-stream wiring
            mrn: true,
            insurance: true,
            problemList: true,
          },
        },
        createdAt: true,
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
        soapVersion: true,
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
        emPendingChange: true,
        emStale: true,
        emScoredCode: true,
        patientSummary: true,
        confidenceScores: true,
      },
    }),
    prisma.rxWarningOverride.findMany({
      // ⚠️ THE `where` IS DELIBERATELY UNNARROWED. This same array populates
      // `rxOverriddenWarningIds`, which is the COVERAGE INPUT to `signGates`
      // and mirrors what `POST /sign` validates. Adding `severity: 'critical'`
      // here to serve Screen 4's trail card would silently narrow the gate's
      // notion of what has been overridden. Select more; filter in the reader.
      where: { visitId: id },
      select: {
        warningId: true,
        severity: true,
        overriddenAt: true,
      },
    }),
  ])) as [
    UserRow | null,
    VisitRow | null,
    Array<{ warningId: string; severity: string; overriddenAt: Date }>,
  ];

  if (!user) redirect('/login');
  if (!visit || visit.userId !== session.user.id) notFound();

  // Round 3 PR-C — §164.312(b) PHI-read audit (A05-P0-004). Single
  // visit detail page is the highest-volume PHI surface — every doctor
  // visit-detail load lands a row.
  void logAudit({
    action: 'VIEWED_VISIT',
    targetId: visit.id,
    targetType: 'TranscribeVisit',
    metadata: { source: 'rsc:/visits/[id]', status: visit.status },
  });

  const hasInput =
    visit.audioKey !== null ||
    visit.dictationAudioKey !== null ||
    (visit.rawTextInput !== null && visit.rawTextInput.length > 0);

  const patientDisplayName =
    visit.patient?.name ?? visit.patientName ?? 'Patient';
  const statusLabel = visitStatusLabel(visit.status, visit.needsReview);
  const statusPillCls = visitStatusPillClass(visit.status, visit.needsReview);

  // ── R1 — THE STAGE STOPS RENDERING TWO GENERATIONS AT ONCE ──────────────
  // Everything between here and the VisitBody wrapper is pre-Rounds chrome:
  // a "Dashboard › <name> › Visit · ready" breadcrumb, a meta strip that
  // reprints the patient name (uppercased), specialty, MRN and chief complaint,
  // and a right-aligned Delete row. Under Rounds every one of those is drawn
  // AGAIN, better, by `RoundsStageIdentity` — so the live page showed the
  // patient's name three times and their MRN twice, with the status word
  // uppercased into a "NEEDS REVIEW" badge that the Rounds pipeline strip
  // already states.
  // It is gated rather than deleted because the flag-OFF build is still a
  // supported build until F-ret retires it, and that build has no other header.
  const roundsChrome = isSkinRounds();

  // The lifecycle actions (Delete, and the draft-edit dialog) are hoisted so
  // BOTH shells can place them. Off Rounds they keep their prime-header row.
  // Under Rounds they move into a quiet disclosure BELOW the note: destroying
  // a visit is not a primary action on the screen where you read it, and a
  // right-aligned `Delete` sitting level with the patient's name is one
  // mis-click from a surface whose whole job is careful review.
  const lifecycleActions = (
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
  );

  return (
    <AppFrame>
      {!roundsChrome && (
      <>
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
          className="qm-tap-44"
          style={{
            color: 'var(--color-linear-text-3)',
            textDecoration: 'none',
            display: 'inline-flex',
            alignItems: 'center',
          }}
        >
          Dashboard
        </Link>
        <Ic.chevRight width={12} height={12} />
        {visit.patient ? (
          <>
            <Link
              href={`/patients/${visit.patient.id}`}
              className="qm-tap-44"
              style={{
                color: 'var(--color-linear-text-3)',
                textDecoration: 'none',
                display: 'inline-flex',
                alignItems: 'center',
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

      <div style={{ padding: '14px 24px 0' }}>{lifecycleActions}</div>
      </>
      )}

      <div style={{ padding: '18px 24px 48px' }}>
        <VisitBody
          visitId={visit.id}
          doctorEmail={user.email}
          doctorName={user.name}
          specialty={specialtyLabel(visit.specialty)}
          specialtyId={specialtyId(visit.specialty)}
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
          soapVersion={visit.soapVersion}
          needsReview={visit.needsReview}
          reviewReason={visit.reviewReason}
          failureCategory={visit.failureCategory}
          processingStartedAt={visit.processingStartedAt}
          processingFinishedAt={visit.processingFinishedAt}
          processingCostCents={visit.processingCostCents}
          icdCodes={visit.icdCodes}
          cptCodes={visit.cptCodes}
          rxDrafts={visit.rxDrafts}
          rxOverriddenWarningIds={rxOverrides.map((o) => o.warningId)}
          referrals={visit.referrals}
          emPendingChange={visit.emPendingChange}
          emStale={visit.emStale}
          emScoredCode={visit.emScoredCode}
          patientSummary={visit.patientSummary}
          confidenceScores={visit.confidenceScores}
          // Phase 5.1.1 — V4 Extras card-stream wiring
          patientName={visit.patientName}
          patient={visit.patient}
          createdAt={visit.createdAt}
          // Selected since the meta strip needed it; threaded down now because
          // the Rounds identity header renders it as the reason line. Inert on
          // the flag-off path.
          chiefComplaint={visit.chiefComplaint}
          rxOverrides={rxOverrides}
        />
      </div>

      {roundsChrome && (
        <details className="qm-rounds-overflow" data-testid="rounds-visit-overflow">
          <summary className="qm-rounds-overflow-summary">Visit actions</summary>
          <div className="qm-rounds-overflow-body">{lifecycleActions}</div>
        </details>
      )}
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
   *  metadata rail. DISPLAY ONLY — never compare it against a specialty id. */
  specialty: string;
  /** The RAW specialty id off the visit row ('ultrasound'), for predicates.
   *
   *  `specialty` above is `specialtyLabel(visit.specialty)` — 'Ultrasound', not
   *  'ultrasound' — and it was being fed to `isImagingReportSpecialty`, which
   *  compares against the id. That comparison was therefore ALWAYS false, so
   *  `emNotApplicable` never became true on the one specialty it exists for:
   *  every ultrasound visit computed an office E/M level and PERSISTED it to
   *  `emScoredCode`. A clinic code on an imaging report is wrong as data, not
   *  just as pixels — it reaches the billing surface, the export, and the
   *  signed record. Two props now, because one string cannot be both a label
   *  and a key. */
  specialtyId: string;
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
  soapVersion: number;
  needsReview: boolean;
  reviewReason: string | null;
  failureCategory: string | null;
  processingStartedAt: Date | null;
  processingFinishedAt: Date | null;
  processingCostCents: number | null;
  icdCodes: unknown;
  cptCodes: unknown;
  rxDrafts: unknown;
  /** Round 4 critical-Rx-override fix: warningIds with existing
   *  RxWarningOverride rows. Hydrates the rail's ✓ Overridden chips
   *  on initial paint so reload + cross-tab persistence works. */
  rxOverriddenWarningIds: string[];
  referrals: unknown;
  /** E/M visible-confirm (prod smoke #311) — pending-change jsonb (coerced
   *  via unacknowledgedEmChange before reaching VisitReadyView). */
  emPendingChange: unknown;
  emStale: boolean;
  emScoredCode: string | null;
  patientSummary: string | null;
  confidenceScores: unknown;

  // Phase 5.1.1 — V4 Extras card-stream wiring.
  patientName: string | null;
  patient: {
    id: string;
    name: string;
    dateOfBirth: Date | null;
    externalId: string | null;
    mrn: string | null;
    insurance: string | null;
    problemList: unknown;
  } | null;
  createdAt: Date;
  /** The reason line on the Rounds identity header. Display only. */
  chiefComplaint: string | null;
  /** The persisted override rows, for Screen 4's safety trail. `severity` is
   *  filtered by the READER, never by the query — the same rows are the sign
   *  gate's coverage input. */
  rxOverrides: { warningId: string; severity: string; overriddenAt: Date }[];
}

async function VisitBody(props: VisitBodyProps) {
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
    // Pre-count chips so the typewriter can render the chip row without
    // a flash of "0" when AUTOMATING completes between page-load and
    // first poll. Tolerant of legacy rows whose JSONB shape may be
    // null or unexpected — same defensive pattern as the status route.
    const icdBlob = props.icdCodes as { codes?: unknown[] } | null;
    const cptBlob = props.cptCodes as { codes?: unknown[] } | null;
    const initialIcdCount = Array.isArray(icdBlob?.codes) ? icdBlob.codes.length : 0;
    const initialCptCount = Array.isArray(cptBlob?.codes) ? cptBlob.codes.length : 0;
    return (
      <ProcessingTypewriter
        visitId={props.visitId}
        initialStatus={props.status}
        initialIcdCount={initialIcdCount}
        initialCptCount={initialCptCount}
        initialProcessingStartedAt={
          props.processingStartedAt
            ? props.processingStartedAt.toISOString()
            : null
        }
        specialtyLabel={props.specialty}
      />
    );
  }

  if (props.status === TranscribeVisitStatus.FAILED) {
    return (
      <VisitFailedView
        visitId={props.visitId}
        reason={props.reviewReason}
        failureCategory={props.failureCategory}
        inputMode={props.inputMode}
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

  // Server-side initial E&M score for the Coding Coach rail. As of
  // feat/em-score-precomputed-judge: routes through the LLM-judge
  // path (omitting `mdmCachedJudgement`) so the rail's `suggestedCode`
  // + `bump.toCode` agree with what the apply-additions route will
  // actually deliver. The pipeline (worker.ts L7 fan-out) pre-warms
  // the judge cache for every visit before transitioning to READY, so
  // this call should be a <50ms Redis cache hit on the vast majority
  // of page loads.
  //
  // Fallback: pre-2026-05-11 visits + visits where the pipeline pre-
  // warm failed silently pay one LLM call here (~10-30s) the first
  // time the page is opened, then are cached for the next 7 days. The
  // server-side render blocks on this — fine for a one-time backfill
  // cost; doesn't recur.
  //
  // Note: a previous design (PR pre-#207) used `mdmCachedJudgement:
  // null` here to keep render at <10ms p95. The trade-off was honest
  // tier display vs page-load speed. Pre-warm gives us both: the
  // deterministic shortcut is gone but the cache hit is just as fast.
  const session = await auth();
  const sessionPracticeId = session?.user?.practiceId as string | undefined;
  // E/M does not apply to an IMAGING REPORT (e.g. ultrasound) — it has no
  // office-visit E/M level. Suppress the on-read coaching score (the pipeline
  // already skips L7b CPT/E&M). The Billing surface shows an explicit
  // "not applicable" note instead of a forced clinic-visit code.
  // `props.specialtyId`, NOT `props.specialty` — the latter is the display
  // label and this comparator takes an id. See the prop doc above.
  const emNotApplicable =
    !emAppliesToSpecialty(props.specialtyId);
  // Imaging reports skip E/M scoring entirely (left null → the Billing surface
  // renders the "not applicable" note). Only clinic encounters are scored.
  let initialEmScore: import('@/lib/em-coding-ui/types').EmScore | null = null;
  if (!emNotApplicable) {
  try {
    const { computeEmScore } = await import('@/lib/em-coding/score');
    const { engineToUiScore } = await import('@/lib/em-coding/to-ui-score');
    const engineScore = await computeEmScore(soapText, {
      practiceId: sessionPracticeId,
      visitId: props.visitId,
      userId: session?.user?.id,
      icdCodes: extractIcdRows(props.icdCodes),
      rxDrafts: extractRxRows(props.rxDrafts),
    });
    // Hydrate the doctor's previously-set override (if any) from
    // cptCodes.em.override so the rail renders the doctor-set code on
    // page load. The server route at POST /em-score/override writes
    // here; this read is the round-trip back to the rail.
    const existingOverride = extractEmOverride(props.cptCodes);
    initialEmScore = engineToUiScore(
      engineScore,
      durationSec ?? 0,
      existingOverride
    );

    // SEED THE BASELINE, once per visit.
    //
    // `emScoredCode` is what a re-score measures movement against. Nothing
    // else writes it, so without this every visit's FIRST re-score would find
    // no baseline, conclude nothing had moved, and clear the gate — one free
    // unvalidated level change per visit, on the common path (edit once, sign).
    //
    // Here is the honest place: the level has just been computed against the
    // note as it stands, and the note has not been edited since (an edit sets
    // emStale, and a stale visit is re-scored before it can be signed). Guarded
    // on null and on READY, so it writes once and never over a signed row.
    if (props.emScoredCode == null && props.status === TranscribeVisitStatus.READY) {
      // The DISPLAYED level: the doctor's override when they set one, else
      // the rubric's suggestion — the same projection the rail renders and the
      // re-score compares against.
      const code =
        initialEmScore?.override?.code ?? initialEmScore?.suggestedCode ?? null;
      if (code) {
        await prisma.transcribeVisit.updateMany({
          where: {
            id: props.visitId,
            status: TranscribeVisitStatus.READY,
            emScoredCode: null,
          },
          data: { emScoredCode: code },
        });
      }
    }
  } catch (e) {
    console.error('[em-score] initial render failed:', e);
  }
  }

  // E/M visible-confirm (prod smoke #311) — strict coercion of the
  // pending-change jsonb to the {from, to} pair the modal renders.
  // Imaging reports have no E/M level → never a pending E/M change to confirm.
  const pendingEm = emNotApplicable
    ? null
    : unacknowledgedEmChange(props.emPendingChange);
  const pendingEmChange = pendingEm
    ? { from: pendingEm.from, to: pendingEm.to }
    : null;

  // ── ROUNDS, Screen 2 — computed HERE and handed down as data ──────────────
  //
  // WHY THE SERVER, AND WHY THIS LATE. Two of `signGates`' three inputs are
  // only correct on this side of the boundary:
  //
  //   * the RAW specialty ID. The client has `specialtyLabel(...)` in scope,
  //     and `findSpecialty('Ultrasound').id` is 'unspecified' with no throw.
  //     That substitution is how every ultrasound visit once computed and
  //     PERSISTED an office E/M level. Computing here means the wrong value is
  //     not within reach of the right call.
  //   * the RAW `emPendingChange` jsonb. Ten lines above it has already been
  //     coerced to the `{from, to}` display pair, and the coercion fails CLOSED
  //     on that shape — feeding it back would invent a blocker on every visit
  //     carrying a pending change, silently and in the safe-looking direction.
  //
  // And it is placed after the E/M compute and after the `emScoredCode`
  // baseline write on purpose: there is no early return between here and the
  // top of the function, so a flag-off render executes every statement above
  // in the same order and differs only by one prop whose value is null.
  // `isSkinRounds()` inlines at build time, so flag-off never runs the query.
  let rounds: RoundsStageData | null = null;
  if (isSkinRounds()) {
    const userId = session?.user?.id;
    const queueIds = userId ? await fetchStageQueueIds(userId) : [];

    if (userId) {
      // The flag-on path reads OTHER visits' rows to place this one in the
      // queue. §164.312(b) wants that recorded, exactly as /board records it.
      // Names and free text stay out — a count is enough to show the read.
      void logAudit({
        action: 'VIEWED_VISIT_LIST',
        targetType: 'TranscribeVisit',
        metadata: {
          source: 'rsc:/visits/[id]#rounds-queue',
          count: queueIds.length,
        },
      });
    }

    const gateSet = signGates({
      rxDrafts: props.rxDrafts,
      overriddenWarningIds: props.rxOverriddenWarningIds,
      specialty: props.specialtyId,
      emPendingChange: props.emPendingChange,
      emStale: props.emStale,
    });

    rounds = {
      status: props.status,
      signedAt: props.signedAt?.toISOString() ?? null,
      identity: toStageIdentity({
        id: props.visitId,
        patientName: props.patient?.name ?? null,
        patientFallback: props.patientName,
        patientExternalId: props.patient?.externalId ?? null,
        patientDob: props.patient?.dateOfBirth ?? null,
        chiefComplaint: props.chiefComplaint,
        createdAt: props.createdAt,
        // The RESOLVED duration, not `props.audioDurationSec` — a dictated
        // visit keeps its length in `dictationDurationSec`, so the raw column
        // would render every one of them as a plausible empty slot.
        audioDurationSec: durationSec,
      }),
      queue: toQueuePosition(props.visitId, queueIds),
      gates: gateSet.gates,
      n: gateSet.n,
      emArtifact: gateSet.emArtifact,
      // OFF THE SAME GATE SET. Deriving it a second time from
      // `unmetCriticalWarnings` would put two computations of one number on
      // one screen, and the band would eventually contradict the padlock.
      criticalUnresolved:
        gateSet.gates.find((g) => g.id === 'rx')?.unresolved ?? 0,
      // ── Screen 4's safety trail — only what a column can prove ──────────
      trail: {
        // Severity filtered HERE, not in the query: the same rows populate
        // `rxOverriddenWarningIds`, which is the sign gate's coverage input.
        // And compared against the signature rather than assumed — the override
        // route guards ownership, not visit status, so a row CAN postdate a
        // signature and "overridden before signing" has to mean it.
        criticalOverridesBeforeSign: props.signedAt
          ? props.rxOverrides.filter(
              (o) =>
                o.severity === 'critical' &&
                o.overriddenAt.getTime() <= props.signedAt!.getTime()
            ).length
          : 0,
        // The RAW column, not the coerced display pair — that one is null on
        // every signed visit by construction, because the coercion returns null
        // once the change has been acknowledged.
        emAcknowledgedAt: emNotApplicable
          ? null
          : (parseEmPendingChange(props.emPendingChange)?.acknowledgedAt ?? null),
      },
    };
  }

  return (
    <VisitReadyView
      rounds={rounds}
      visitId={props.visitId}
      // 2026-06-11 L6-gate smoke finding: the review reason was DB-only —
      // the READY view never received it, so the doctor saw a bare
      // "Needs review" pill with no explanation.
      needsReview={props.needsReview}
      reviewReason={props.reviewReason}
      inputMode={props.inputMode}
      soapText={soapText}
      soapVersion={props.soapVersion}
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
      rxOverriddenWarningIds={props.rxOverriddenWarningIds}
      referrals={props.referrals}
      // Hybrid anchored generation — lane claims (strictly coerced; null
      // when absent/malformed so the lane simply doesn't render).
      // E/M visible-confirm (prod smoke #311) — the unacknowledged
      // suggestion-caused level change, hydrating the Sign & Send
      // modal's confirm control ({from, to} codes only; null = nothing
      // to confirm). The server-side sign gate is the enforcement; this
      // is the visible half.
      emPendingChange={pendingEmChange}
      // STALENESS WAS NEVER PASSED. `VisitReadyView` declared `emStale?` and
      // seeded `useState(props.emStale ?? false)` from it, so on every page load
      // it was false no matter what the column said. The stale gate — the card
      // that says "the note changed after this visit's level was scored" and
      // offers the re-check — therefore appeared ONLY inside the session that
      // did the editing. Reload, second tab, or come back tomorrow, and a visit
      // whose level needs re-checking rendered as "Reviewed" with nothing to do.
      //
      // Not a weakened gate: POST /sign re-scores a stale visit unconditionally
      // and refuses, so nothing unvalidated could be signed. But it moved the
      // warning from "before the signature" to "at the signature", which is the
      // failure the inline gate stack exists to prevent — the same reason the
      // stale badge came off the "⋯ details" disclosure.
      emStale={props.emStale}
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
      // Phase 5.2 — server-rendered initial E&M score for the Coding Coach
      initialEmScore={initialEmScore}
      // Ultrasound (flag-gated): imaging report → no E/M level applies.
      emNotApplicable={emNotApplicable}
      // Phase 5.1.1 — V4 Extras card-stream wiring
      patientName={props.patient?.name ?? props.patientName}
      patientDob={
        props.patient?.dateOfBirth
          ? props.patient.dateOfBirth.toISOString().slice(0, 10)
          : null
      }
      patientMrn={props.patient?.mrn ?? null}
      patientInsurance={props.patient?.insurance ?? null}
      patientExternalId={props.patient?.externalId ?? null}
      patientProblemList={props.patient?.problemList ?? null}
      visitCreatedAt={
        props.createdAt ? props.createdAt.toISOString() : null
      }
    />
  );
}
