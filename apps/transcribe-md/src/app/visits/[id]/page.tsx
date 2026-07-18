import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import * as Sentry from "@sentry/nextjs";

import prisma from "@meddoc/db";
import { TranscribeVisitStatus } from "@prisma/client";
import {
  findSpecialty,
  isImagingReportSpecialty,
  ultrasoundSpecialtyEnabled,
} from "@meddoc/shared/specialties";
import { auth } from "@/lib/nextauth";
import { AuthError, requireFreshDoctorIdentity } from "@/lib/auth";
import { logAudit, logRequiredAudit } from "@/lib/audit";
import { AppFrame } from "@/components/ui/app-frame";
import { Ic } from "@/components/ui/icon";
import { type SpecialtyKind } from "@/components/ui/spec-chip";
import { AudioUploader } from "@/components/audio-uploader";
import { VoiceDictator } from "@/components/voice-dictator";
import { TextComposer } from "@/components/text-composer";
import { TemplateTwinSyntheticQaBanner } from "@/components/template-twin-synthetic-qa-banner";

import { ProcessingTypewriter } from "./processing-typewriter";
import {
  VisitReadyView,
  type Utterance,
  type SpeakerInfo,
} from "./visit-ready-view";
import { VisitFailedView } from "./visit-failed-view";
import { VisitLifecycleActions } from "./visit-lifecycle-actions";
import { EditDraftDialog } from "./edit-draft-dialog";

import { isEmailDeliveryEnabled } from "@/lib/email-enabled";
import {
  extractIcdRows,
  extractRxRows,
  extractEmOverride,
} from "@/lib/em-coding/displayed-level";
import { unacknowledgedEmChange } from "@/lib/em-pending-change";
import {
  serializeTemplateTwinReview,
  type TemplateTwinReviewData,
  type TemplateTwinReviewRow,
} from "@/components/visit/template-twin-review-data";
import { evaluateTemplateTwinRollout } from "@/lib/template-twin/rollout";
import {
  evaluateTemplateTwinStagingQaGate,
  isTemplateTwinStagingQaRequested,
  TemplateTwinStagingQaDisabledError,
} from "@/lib/template-twin/staging-qa-gate";
import {
  assertTemplateTwinStagingQaVisitGuard,
  TEMPLATE_TWIN_STAGING_QA_RUN_GUARD_SELECT,
  type TemplateTwinStagingQaRunGuardRow,
  TemplateTwinStagingQaVisitGuardError,
} from "@/lib/template-twin/staging-qa-visit-guard";

export const metadata: Metadata = { title: "Visit" };

// E/M signal extractors (icd/rx/override) now come from the shared
// @/lib/em-coding/displayed-level so the initial render, the rescore route,
// and the sign gate all coerce identically (2026-06-13 trigger-parity fix).

/** Hybrid anchored generation (2026-06-11) — coerce the suggestedClaims
 *  jsonb into the lane's typed shape. STRICT: any malformed entry voids the
 *  whole array (returns null → lane hidden) so the lane's rendered indices
 *  can never drift from the DB array's indices, which the adopt/dismiss
 *  server actions validate against. */
function extractSuggestedClaims(
  raw: unknown,
): { text: string; reason: string; section: string; anchor: string }[] | null {
  if (!Array.isArray(raw) || raw.length === 0) return null;
  const out: {
    text: string;
    reason: string;
    section: string;
    anchor: string;
  }[] = [];
  for (const entry of raw) {
    if (entry === null || typeof entry !== "object") return null;
    const c = entry as Record<string, unknown>;
    if (
      typeof c.text !== "string" ||
      typeof c.reason !== "string" ||
      typeof c.section !== "string" ||
      typeof c.anchor !== "string"
    ) {
      return null;
    }
    out.push({
      text: c.text,
      reason: c.reason,
      section: c.section,
      anchor: c.anchor,
    });
  }
  return out;
}

const PROCESSING_STATES: ReadonlyArray<TranscribeVisitStatus> = [
  TranscribeVisitStatus.TRANSCRIBING,
  TranscribeVisitStatus.EXTRACTING,
  TranscribeVisitStatus.DRAFTING,
  TranscribeVisitStatus.CRITIQUING,
  TranscribeVisitStatus.POLISHING,
  TranscribeVisitStatus.AUTOMATING,
];

const KNOWN_SPECIALTIES: readonly SpecialtyKind[] = [
  "cardiology",
  "pain",
  "ortho",
  "primary",
  "pulmonology",
  "ophthalmology",
];

// findSpecialty (shared) handles canonical ids, legacy display names
// ('Cardiology'), and legacy short ids ('pain') — returning the
// catalog entry whose .label is the human-readable form.
function specialtyLabel(raw: string): string {
  return findSpecialty(raw).label;
}

void KNOWN_SPECIALTIES;

// Phase 5 — collapse the seven-state TranscribeVisitStatus into the
// labels the meta strip + status pill exposes.
function visitStatusLabel(status: TranscribeVisitStatus, needsReview: boolean) {
  if (status === TranscribeVisitStatus.SIGNED) return "Signed";
  if (status === TranscribeVisitStatus.FAILED) return "Failed";
  if (status === TranscribeVisitStatus.READY)
    return needsReview ? "Needs review" : "Ready";
  if (status === TranscribeVisitStatus.QUEUED) return "Queued";
  return "Processing";
}

function visitStatusPillClass(
  status: TranscribeVisitStatus,
  needsReview: boolean,
) {
  if (status === TranscribeVisitStatus.SIGNED) {
    return "qm-lin-pill qm-lin-pill--signed";
  }
  if (status === TranscribeVisitStatus.FAILED) {
    return "qm-lin-pill bg-linear-danger/15 text-linear-danger";
  }
  if (status === TranscribeVisitStatus.READY) {
    return needsReview
      ? "qm-lin-pill qm-lin-pill--review"
      : "qm-lin-pill qm-lin-pill--ready";
  }
  if (status === TranscribeVisitStatus.QUEUED) {
    return "qm-lin-pill qm-lin-pill--draft";
  }
  return "qm-lin-pill qm-lin-pill--processing";
}

export default async function VisitPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const session = await auth();
  if (!session?.user?.id) redirect("/login");

  // Round 3 PR-H — A11-P1 Sentry context.
  // PHI guard: visitId is a UUID — safe. NEVER set patient name, MRN,
  // DOB, email, or transcript content as Sentry tags or context. The
  // redactPhi beforeSend hook is a backstop; primary defense is
  // never sending PHI in the first place.
  Sentry.setTag("visitId", id);
  Sentry.setUser({ id: session.user.id });

  type UserRow = {
    name: string | null;
    email: string;
    practice: { templateTwinEnabled: boolean };
  };
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
    suggestedClaims: unknown;
    /** E/M visible-confirm (prod smoke #311) — pending-change jsonb. */
    emPendingChange: unknown;
    patientSummary: string | null;
    confidenceScores: unknown;
    templateTwinFill: TemplateTwinReviewRow | null;
    templateTwinSyntheticQaRun: TemplateTwinStagingQaRunGuardRow | null;
  };

  // Round 4 critical-Rx-override fix: pull existing override rows so
  // the rail can hydrate with ✓ Overridden chips on already-acknowledged
  // warnings. Visit-scoped + persisted, so reload + cross-tab don't
  // lose the doctor's progress through multiple critical warnings.
  const [user, visit, rxOverrides] = (await Promise.all([
    prisma.user.findUnique({
      where: { id: session.user.id },
      select: {
        name: true,
        email: true,
        practice: { select: { templateTwinEnabled: true } },
      },
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
        suggestedClaims: true,
        emPendingChange: true,
        patientSummary: true,
        confidenceScores: true,
        templateTwinFill: {
          select: {
            id: true,
            status: true,
            manifestVersion: true,
            manifestSha256: true,
            fillManifest: true,
            filledCount: true,
            needsReviewCount: true,
            notMentionedCount: true,
            conflictCount: true,
            criticalUnresolvedCount: true,
            roundTripVerified: true,
            roundTripVerification: true,
            reviewedAt: true,
            reviewedManifestVersion: true,
            reviewedManifestSha256: true,
            compilerVersion: true,
            resolverVersion: true,
            resolverModelVersion: true,
            rendererVersion: true,
            soapVersion: true,
            soapSha256: true,
            outputSha256: true,
            outputSizeBytes: true,
            staticContentSha256: true,
            compiledVersion: {
              select: {
                noteTemplate: { select: { name: true } },
                certification: {
                  select: { approvedMappingsSha256: true },
                },
                fields: {
                  orderBy: { displayOrder: "asc" },
                  select: {
                    id: true,
                    fieldId: true,
                    displayOrder: true,
                    originalLabel: true,
                    fieldKind: true,
                    allowedOptions: true,
                    rendererBinding: true,
                    criticality: true,
                    required: true,
                  },
                },
              },
            },
          },
        },
        templateTwinSyntheticQaRun: {
          select: TEMPLATE_TWIN_STAGING_QA_RUN_GUARD_SELECT,
        },
      },
    }),
    prisma.rxWarningOverride.findMany({
      where: { visitId: id },
      select: { warningId: true },
    }),
  ])) as [UserRow | null, VisitRow | null, Array<{ warningId: string }>];

  if (!user) redirect("/login");
  if (!visit || visit.userId !== session.user.id) notFound();
  let syntheticQaAuditPracticeId: string | null = null;
  if (
    visit.templateTwinSyntheticQaRun ||
    isTemplateTwinStagingQaRequested()
  ) {
    try {
      const doctor = await requireFreshDoctorIdentity(session.user.id);
      syntheticQaAuditPracticeId = doctor.practiceId;
      assertTemplateTwinStagingQaVisitGuard({
        run: visit.templateTwinSyntheticQaRun,
        actor: {
          userId: session.user.id,
          practiceId: doctor.practiceId,
        },
        currentRolloutToken: doctor.rolloutToken,
      });
    } catch (error) {
      if (
        error instanceof AuthError ||
        error instanceof TemplateTwinStagingQaDisabledError ||
        error instanceof TemplateTwinStagingQaVisitGuardError
      ) {
        notFound();
      }
      throw error;
    }
  }
  const serializedTemplateTwinReview = evaluateTemplateTwinRollout({
    practiceEnabled: user.practice.templateTwinEnabled,
  }).allowed
    ? serializeTemplateTwinReview(visit.templateTwinFill)
    : null;
  const templateTwinReview = serializedTemplateTwinReview
    ? {
        ...serializedTemplateTwinReview,
        syntheticQaMode:
          visit.templateTwinSyntheticQaRun !== null &&
          evaluateTemplateTwinStagingQaGate(process.env).allowed,
        syntheticQaRunId:
          visit.templateTwinSyntheticQaRun !== null &&
          evaluateTemplateTwinStagingQaGate(process.env).allowed
            ? visit.templateTwinSyntheticQaRun.id
            : null,
        syntheticQaAttempt:
          visit.templateTwinSyntheticQaRun !== null &&
          evaluateTemplateTwinStagingQaGate(process.env).allowed
            ? visit.templateTwinSyntheticQaRun.attempt
            : null,
      }
    : null;
  const syntheticQaVisit = visit.templateTwinSyntheticQaRun !== null;

  // Round 3 PR-C — §164.312(b) PHI-read audit (A05-P0-004). Single
  // visit detail page is the highest-volume PHI surface — every doctor
  // visit-detail load lands a row.
  const viewAudit = {
    action: "VIEWED_VISIT" as const,
    targetId: visit.id,
    targetType: "TranscribeVisit",
    metadata: { source: "rsc:/visits/[id]", status: visit.status },
  };
  if (syntheticQaVisit) {
    if (!syntheticQaAuditPracticeId) notFound();
    await logRequiredAudit({
      ...viewAudit,
      userId: session.user.id,
      practiceId: syntheticQaAuditPracticeId,
    });
  } else {
    void logAudit(viewAudit);
  }

  const hasInput =
    visit.audioKey !== null ||
    visit.dictationAudioKey !== null ||
    (visit.rawTextInput !== null && visit.rawTextInput.length > 0);

  const patientDisplayName =
    visit.patient?.name ?? visit.patientName ?? "Patient";
  const statusLabel = visitStatusLabel(visit.status, visit.needsReview);
  const statusPillCls = visitStatusPillClass(visit.status, visit.needsReview);

  return (
    <AppFrame>
      {/* Linear V1 breadcrumb — sits at the top of the content
          column, hairline-separated from the meta strip below. */}
      <div
        style={{
          padding: "14px 24px 0",
          display: "flex",
          alignItems: "center",
          gap: 8,
          fontFamily: "var(--font-sans)",
          fontSize: 13,
          color: "var(--color-linear-text-3)",
        }}
      >
        <Link
          href="/dashboard"
          className="qm-tap-44"
          style={{
            color: "var(--color-linear-text-3)",
            textDecoration: "none",
            display: "inline-flex",
            alignItems: "center",
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
                color: "var(--color-linear-text-3)",
                textDecoration: "none",
                display: "inline-flex",
                alignItems: "center",
              }}
            >
              {visit.patient.name}
            </Link>
            <Ic.chevRight width={12} height={12} />
          </>
        ) : null}
        <span style={{ color: "var(--color-linear-text), inherit" }}>
          Visit · {visit.status.toLowerCase()}
        </span>
      </div>

      {/* Linear V1 patient meta strip — mono uppercase fields with
          hairline dividers. Mirrors visit-detail.html. */}
      <div
        style={{
          margin: "14px 24px 0",
          padding: "10px 0 14px",
          display: "flex",
          alignItems: "center",
          gap: 0,
          flexWrap: "wrap",
          borderBottom: "1px solid var(--color-linear-hairline)",
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          color: "var(--color-linear-text-2)",
        }}
      >
        <div
          style={{
            paddingRight: 14,
            borderRight: "1px solid var(--color-linear-hairline)",
            color: "var(--color-linear-text)",
            fontWeight: 500,
          }}
        >
          {patientDisplayName.toUpperCase()}
        </div>
        <div
          style={{
            padding: "0 14px",
            borderRight: "1px solid var(--color-linear-hairline)",
          }}
        >
          {specialtyLabel(visit.specialty)}
        </div>
        {visit.patient?.externalId && (
          <div
            style={{
              padding: "0 14px",
              borderRight: "1px solid var(--color-linear-hairline)",
            }}
          >
            <span style={{ color: "var(--color-linear-text-3)" }}>
              MRN&nbsp;
            </span>
            {visit.patient.externalId}
          </div>
        )}
        {visit.chiefComplaint && (
          <div
            style={{
              padding: "0 14px",
              borderRight: "1px solid var(--color-linear-hairline)",
            }}
          >
            <span style={{ color: "var(--color-linear-text-3)" }}>
              CC&nbsp;
            </span>
            <span style={{ textTransform: "none", letterSpacing: "-0.005em" }}>
              {visit.chiefComplaint}
            </span>
          </div>
        )}
        <div style={{ padding: "0 14px", marginLeft: "auto" }}>
          <span
            className={statusPillCls}
            style={{ textTransform: "uppercase" }}
          >
            {statusLabel}
          </span>
        </div>
      </div>

      <div style={{ padding: "14px 24px 0" }}>
        {!syntheticQaVisit && (
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
                      | "audio_upload"
                      | "voice_dictation"
                      | "text_notes"
                  }
                />
              ) : null
            }
          />
        )}
      </div>

      <div style={{ padding: "18px 24px 48px" }}>
        {syntheticQaVisit && (
          <div style={{ marginBottom: 18 }}>
            <TemplateTwinSyntheticQaBanner />
          </div>
        )}
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
          suggestedClaims={visit.suggestedClaims}
          emPendingChange={visit.emPendingChange}
          patientSummary={visit.patientSummary}
          confidenceScores={visit.confidenceScores}
          templateTwinReview={templateTwinReview}
          syntheticQaMode={syntheticQaVisit}
          syntheticQaAttempt={visit.templateTwinSyntheticQaRun?.attempt ?? null}
          // Phase 5.1.1 — V4 Extras card-stream wiring
          patientName={visit.patientName}
          patient={visit.patient}
          createdAt={visit.createdAt}
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
  /** Hybrid anchored generation — verifier-demoted claims jsonb (coerced
   *  via extractSuggestedClaims before reaching VisitReadyView). */
  suggestedClaims: unknown;
  /** E/M visible-confirm (prod smoke #311) — pending-change jsonb (coerced
   *  via unacknowledgedEmChange before reaching VisitReadyView). */
  emPendingChange: unknown;
  patientSummary: string | null;
  confidenceScores: unknown;
  templateTwinReview: TemplateTwinReviewData | null;
  /** Exact persisted visit identity; staging-only UI never infers this from
   *  document availability or from client-visible labels. */
  syntheticQaMode: boolean;
  syntheticQaAttempt: number | null;

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
}

async function VisitBody(props: VisitBodyProps) {
  if (!props.syntheticQaMode && props.status === TranscribeVisitStatus.QUEUED) {
    if (props.inputMode === "audio_upload" && !props.audioKey) {
      return <AudioUploader visitId={props.visitId} />;
    }
    if (props.inputMode === "voice_dictation" && !props.dictationAudioKey) {
      return <VoiceDictator visitId={props.visitId} theme="clinician" />;
    }
    if (props.inputMode === "text_notes" && !props.rawTextInput) {
      return <TextComposer visitId={props.visitId} />;
    }
  }

  if (
    PROCESSING_STATES.includes(props.status) ||
    (props.status === TranscribeVisitStatus.QUEUED &&
      (props.syntheticQaMode ||
        props.audioKey ||
        props.dictationAudioKey ||
        props.rawTextInput))
  ) {
    // Pre-count chips so the typewriter can render the chip row without
    // a flash of "0" when AUTOMATING completes between page-load and
    // first poll. Tolerant of legacy rows whose JSONB shape may be
    // null or unexpected — same defensive pattern as the status route.
    const icdBlob = props.icdCodes as { codes?: unknown[] } | null;
    const cptBlob = props.cptCodes as { codes?: unknown[] } | null;
    const initialIcdCount = Array.isArray(icdBlob?.codes)
      ? icdBlob.codes.length
      : 0;
    const initialCptCount = Array.isArray(cptBlob?.codes)
      ? cptBlob.codes.length
      : 0;
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
        syntheticQaAttempt={props.syntheticQaAttempt}
      />
    );
  }

  if (props.status === TranscribeVisitStatus.FAILED) {
    if (props.syntheticQaMode) {
      return (
        <div className="space-y-4">
          <TemplateTwinSyntheticQaBanner />
          <VisitFailedView
            visitId={props.visitId}
            syntheticQaAttempt={props.syntheticQaAttempt}
            reason={props.reviewReason}
            failureCategory={props.failureCategory}
            inputMode={props.inputMode}
          />
        </div>
      );
    }
    return (
      <VisitFailedView
        visitId={props.visitId}
        syntheticQaAttempt={props.syntheticQaAttempt}
        reason={props.reviewReason}
        failureCategory={props.failureCategory}
        inputMode={props.inputMode}
      />
    );
  }

  const raw =
    (props.transcriptRaw as {
      results?: { utterances?: Utterance[] };
    } | null) ?? null;
  const utterances: Utterance[] = raw?.results?.utterances ?? [];

  const speakerMap =
    (props.speakerMap as Record<string, SpeakerInfo> | null) ?? {};

  const critique = props.critique as {
    issues: {
      severity: string;
      location: string;
      description: string;
      suggested_fix: string;
    }[];
    overall_quality: string;
    safe_to_sign_without_review: boolean;
  } | null;

  const soapText =
    props.status === TranscribeVisitStatus.SIGNED
      ? (props.signedSoap ?? props.soapFinal ?? "")
      : (props.soapFinal ?? "");

  const durationSec =
    props.inputMode === "voice_dictation"
      ? props.dictationDurationSec
      : props.audioDurationSec;

  const showPipelineTab = process.env.NEXT_PUBLIC_SHOW_PIPELINE_TAB === "true";

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
  const emNotApplicable =
    ultrasoundSpecialtyEnabled() && isImagingReportSpecialty(props.specialty);
  const syntheticQaMode = props.syntheticQaMode;
  // Imaging reports skip E/M scoring entirely (left null → the Billing surface
  // renders the "not applicable" note). Only clinic encounters are scored.
  let initialEmScore: import("@/lib/em-coding-ui/types").EmScore | null = null;
  // Synthetic QA is deliberately provider-isolated. Its worker already
  // produced the bounded mocked facts used by Template Twin; an on-read E/M
  // score could otherwise fall through to a live judge when the cache is
  // cold. The staging review does not need a billing recommendation.
  if (!emNotApplicable && !syntheticQaMode) {
    try {
      const { computeEmScore } = await import("@/lib/em-coding/score");
      const { engineToUiScore } = await import("@/lib/em-coding/to-ui-score");
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
        existingOverride,
      );
    } catch (e) {
      console.error("[em-score] initial render failed:", e);
    }
  }

  // E/M visible-confirm (prod smoke #311) — strict coercion of the
  // pending-change jsonb to the {from, to} pair the modal renders.
  // Imaging reports have no E/M level → never a pending E/M change to confirm.
  const pendingEm =
    emNotApplicable || syntheticQaMode
      ? null
      : unacknowledgedEmChange(props.emPendingChange);
  const pendingEmChange = pendingEm
    ? { from: pendingEm.from, to: pendingEm.to }
    : null;

  return (
    <VisitReadyView
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
      suggestedClaims={extractSuggestedClaims(props.suggestedClaims)}
      // E/M visible-confirm (prod smoke #311) — the unacknowledged
      // suggestion-caused level change, hydrating the Sign & Send
      // modal's confirm control ({from, to} codes only; null = nothing
      // to confirm). The server-side sign gate is the enforcement; this
      // is the visible half.
      emPendingChange={pendingEmChange}
      patientSummary={props.patientSummary}
      confidenceScores={props.confidenceScores}
      templateTwinReview={props.templateTwinReview}
      syntheticQaMode={props.syntheticQaMode}
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
      signedAt={props.signedAt ? props.signedAt.toISOString() : null}
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
      visitCreatedAt={props.createdAt ? props.createdAt.toISOString() : null}
    />
  );
}
