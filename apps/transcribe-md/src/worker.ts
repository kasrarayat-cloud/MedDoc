// ============================================================================
// apps/transcribe-md — BullMQ worker entrypoint (T-M4 + T-M5)
// ----------------------------------------------------------------------------
// Runs as a separate container (transcribe-md-worker). Pulls jobs off the
// shared `transcribe-md` queue and drives each visit through the pipeline.
//
// Pipeline branches by visit.inputMode:
//   audio_upload    → L1 (diarize) + L2 + L3 (conversation) + L4 + L5 + L6
//   voice_dictation → L1' (single-speaker) + L3 (dictation) + L4 + L5 + L6
//   text_notes      →                         L3 (text)     + L4 + L5 + L6
//
// Layers 4-6 are mode-agnostic: they consume (entities, contextText) and
// produce SOAP draft → critique → polish. That uniformity is the point —
// the doctor gets the same output quality regardless of input shape.
// ============================================================================

import "dotenv/config";
import { randomUUID } from "node:crypto";
// T-M16.3: init @sentry/node via side-effect import BEFORE any layer
// code runs. An early throw in Prisma / Redis init still flows to
// Sentry via global exception handlers.
import "./worker-sentry";
import { captureWorkerException } from "./worker-sentry";
import { Worker, type Job } from "bullmq";
import prisma from "@meddoc/db";
import { evidenceAnchorsEnabled } from "./worker/evidence-anchors-flag";
import { ANCHOR_GENERATION_ADDENDUM } from "./worker/layers/04b-anchor-verify";
import {
  Prisma,
  TranscribeVisitStatus,
  type NoteTemplate,
} from "@prisma/client";
import type { DeepgramBatchResponse, DeepgramUtterance } from "@meddoc/ai";
import {
  getTemplateTwinSyntheticQaProviderContext,
  isLegacyTemplateTwinInfrastructureFixtureEnvironment,
  redactPhi,
} from "@meddoc/ai";
import { log } from "@/lib/log";
import { shouldMarkVisitFailed } from "./worker/retry-decision";
import { categorizeError, type ErrorCategory } from "./worker/error-categorize";
import { loadResumeState, VisitNotFoundError } from "./worker/resume-state";
import { persistFailedState } from "./worker/persist-failed";
import { sanitizeConfidenceScores } from "./worker/confidence-scores";
import { notifyAdminOnFailure } from "./lib/admin-notifications";
import {
  assertQuillmdRuntimeProtocol,
  templateTwinRuntimeEnabled,
} from "@/lib/runtime-protocol";

import {
  QUEUE_NAME,
  JOB_PROCESS_VISIT,
  CLEANUP_QUEUE_NAME,
  JOB_MINIO_ORPHAN_CLEANUP,
  JOB_STALE_VISIT_CLEANUP,
  JOB_RETENTION_SWEEP,
  JOB_STUCK_VISIT_WATCHDOG,
  JOB_TEMPLATE_TWIN_MAINTENANCE,
  enqueueDlq,
  getSharedRedisConnection,
  getCleanupQueue,
  type ProcessVisitPayload,
} from "@/lib/queue";
import { ensureBucket } from "@/lib/minio";
import { runMinioOrphanCleanup } from "@/worker/cleanup/minio-orphans";
import { runStaleVisitCleanup } from "@/worker/cleanup/stale-visits";
import {
  runRetentionSweep,
  resolveRetentionDays,
} from "@/worker/cleanup/retention-sweep";
import { countUnclearMarkers } from "@/worker/layers/transcript-clarity";
import { runStuckVisitWatchdog } from "@/worker/cleanup/stuck-visit-watchdog";
import {
  resolveTemplateTwinMaintenanceConfig,
  runTemplateTwinMaintenance,
  scheduleTemplateTwinMaintenance,
} from "@/worker/cleanup/template-twin-maintenance";
import { recordCleanupHeartbeat } from "@/lib/cleanup-heartbeat";
import {
  isLayerComplete,
  logSkipSummary,
  logSkippedLayer,
  type PipelineLayer,
} from "@/worker/layer-skip";
import { runLayer1Transcribe } from "@/worker/layers/01-transcribe";
import { runLayer1bTranscribeDictation } from "@/worker/layers/01b-transcribe-dictation";
import { assertSufficientTranscript } from "@/worker/layers/guards";
import {
  runLayer2SpeakerRoles,
  type SpeakerMap,
} from "@/worker/layers/02-speaker-roles";
import {
  runLayer3ExtractEntities,
  buildRoleLabeledTranscript,
  type ExtractedEntities,
} from "@/worker/layers/03-extract-entities";
import { runLayer4GenerateSoap } from "@/worker/layers/04-generate-soap";
import { runLayer5SelfCritique } from "@/worker/layers/05-self-critique";
import type { AudioConfidenceStats } from "@/worker/layers/audio-confidence";
import { shouldFlagForReview } from "@/worker/layers/audio-confidence";
import { runLayer6Polish } from "@/worker/layers/06-polish";
import {
  assertTemplateTwinWorkerRuntimeAdmission,
  resolveActiveTemplateAdmission,
  resolveVisitTemplateAdmission,
  TemplateTwinWorkerRolloutError,
} from "@/worker/note-templates/resolve-active-template";
import {
  normalizeTemplate,
  type ResolvedNoteTemplate,
} from "@/worker/note-templates/build-soap-prompt";
import { SYSTEM_DEFAULT_NOTE_TEMPLATE } from "@/worker/note-templates/system-default-template";
import { runLayer7aIcdCoding } from "@/worker/layers/07a-icd-coding";
import { runLayer7bCptCoding } from "@/worker/layers/07b-cpt-coding";
import { runLayer7cRxDrafting } from "@/worker/layers/07c-rx-drafting";
import { runLayer7dReferrals } from "@/worker/layers/07d-referrals";
import { runLayer7ePatientSummary } from "@/worker/layers/07e-patient-summary";
import { logWorkerAudit } from "@/worker/worker-audit";
import { isImagingReportSpecialty } from "@meddoc/shared/specialties";
import {
  processTemplateTwinVisit,
  TEMPLATE_TWIN_REVIEW_REASON,
} from "@/lib/template-twin/fill-engine";
import type { TemplateTwinRolloutToken } from "@/lib/template-twin/rollout";
import {
  assertSyntheticQaResolvedRolloutToken,
  failTemplateTwinSyntheticQaProcessing,
  prepareTemplateTwinSyntheticQaDeliveryRetry,
  reconcileExpiredTemplateTwinSyntheticQaWorkerClaim,
  runWithWorkerSyntheticQaProviderSelection,
  templateTwinSyntheticQaWorkerFailureCode,
} from "@/worker/synthetic-qa-provider";
import { evaluateTemplateTwinStagingQaGate } from "@/lib/template-twin/staging-qa-gate";
import { startTemplateTwinSyntheticQaExpiredLeaseReconciler } from "@/worker/cleanup/staging-qa-expired-leases";
import {
  runTemplateTwinSyntheticQaClaimBoundMutation,
  updateTemplateTwinSyntheticQaClaimBoundVisit,
} from "@/worker/staging-qa-mutation-fence";
import { initializeVisitAutomationManifest } from "@/worker/automation-manifest";
import { buildVisitAutomationPolicy } from "@/worker/automation-policy";
import {
  runAutomationFanout,
  type AutomationFanoutTask,
} from "@/worker/run-automation-fanout";
import { finalizeVisitAutomationReady } from "@/worker/automation-finalization";

const CONCURRENCY = Number.parseInt(
  process.env.TRANSCRIBE_MD_WORKER_CONCURRENCY ?? "2",
  10,
);

/** T-M11 — hard cap per job attempt. Typical pipeline completes in
 *  3-5 min; a 45-min recording comfortably fits under 15. Anything
 *  past that is a genuine hang (stuck fetch, deadlocked query) and
 *  should fail-fast rather than occupy a worker slot indefinitely.
 *  The layer promises keep resolving in the background after timeout
 *  — their writes land on an already-FAILED row, which is harmless.
 *  Configurable via env so ops can tune without redeploy. */
// 2026-05-12 stuck-visit fix: bumped from 15 min → 20 min so the per-
// minute watchdog (15-min threshold) catches a stuck visit FIRST and
// transitions it to FAILED with a clear reviewReason. BullMQ's
// JOB_TIMEOUT_MS is now the belt-and-braces backstop, hitting only on
// a worker too wedged to be touched by the DB-side sweep.
const JOB_TIMEOUT_MS = Number.parseInt(
  process.env.TRANSCRIBE_MD_JOB_TIMEOUT_MS ?? String(20 * 60 * 1000),
  10,
);

// T-M12 — cleanup config. All three env vars default to "off" /
// "30-day retention" / "Sunday 3am UTC" / "dry-run yes" so a fresh
// deploy doesn't start deleting anything until ops explicitly opts in.
const CLEANUP_ENABLED = process.env.MINIO_ORPHAN_CLEANUP_ENABLED === "true";
const CLEANUP_DRY_RUN =
  (process.env.MINIO_ORPHAN_CLEANUP_DRY_RUN ?? "true").toLowerCase() !==
  "false";
const CLEANUP_RETENTION_DAYS = Number.parseInt(
  process.env.MINIO_ORPHAN_CLEANUP_RETENTION_DAYS ?? "30",
  10,
);
const CLEANUP_CRON =
  process.env.MINIO_ORPHAN_CLEANUP_CRON?.trim() || "0 3 * * 0";
// 5 min ceiling on the sweep itself. A cleanly-run sweep on our
// current bucket size takes seconds; 5 min gives head-room for a
// high-object-count bucket and auto-fails a hung MinIO connection.
const CLEANUP_TIMEOUT_MS = 5 * 60 * 1000;

// T-M17.3 — stale visit cleanup (abandoned QUEUED + expired trash).
// Defaults to enabled; flip STALE_VISIT_CLEANUP_ENABLED=false to
// keep the worker alive without the sweep. Cron defaults to daily
// at 3am UTC, which offsets from the weekly MinIO sweep so the two
// don't fight for DB connections.
const STALE_VISIT_CLEANUP_ENABLED =
  (process.env.STALE_VISIT_CLEANUP_ENABLED ?? "true").toLowerCase() !== "false";
const STALE_VISIT_CLEANUP_CRON =
  process.env.STALE_VISIT_CLEANUP_CRON?.trim() || "0 3 * * *";
const STALE_VISIT_CLEANUP_TIMEOUT_MS = 5 * 60 * 1000;

// T-M18.1 A3 — audio retention sweep (SIGNED visits past the audio
// retention window; default 90d — see retention-sweep.ts).
// Opt-out via env. Cron offset 1h from the T-M17.3 stale-visit sweep
// so the two don't contend for DB + MinIO connections.
const RETENTION_SWEEP_ENABLED =
  (process.env.RETENTION_SWEEP_ENABLED ?? "true").toLowerCase() !== "false";
const RETENTION_SWEEP_CRON =
  process.env.RETENTION_SWEEP_CRON?.trim() || "0 4 * * *";
const RETENTION_SWEEP_TIMEOUT_MS = 10 * 60 * 1000;

// 2026-05-12 stuck-visit watchdog. Runs every minute by default so a
// pipeline stall is caught within ~1 min of crossing the threshold.
// Default cron `* * * * *` = every minute UTC.
// Default opt-IN (the failure mode it catches is silent + serious —
// visits stuck at status=POLISHING/etc for hours). Flip
// STUCK_VISIT_WATCHDOG_ENABLED=false to disable in dev environments
// where intentional long sleeps are common.
const STUCK_VISIT_WATCHDOG_ENABLED =
  (process.env.STUCK_VISIT_WATCHDOG_ENABLED ?? "true").toLowerCase() !==
  "false";
const STUCK_VISIT_WATCHDOG_CRON =
  process.env.STUCK_VISIT_WATCHDOG_CRON?.trim() || "* * * * *";
const STUCK_VISIT_WATCHDOG_TIMEOUT_MS = 60_000;

// Template Twin audit delivery and object-ledger reconciliation are opt-in
// until the additive database migration and dedicated bucket are provisioned.
// Purging has a separate exact-true approval flag inside the maintenance job.
const TEMPLATE_TWIN_MAINTENANCE_ENABLED = resolveTemplateTwinMaintenanceConfig(
  process.env,
).enabled;
const TEMPLATE_TWIN_MAINTENANCE_TIMEOUT_MS = 5 * 60 * 1000;

function withTimeout<T>(p: Promise<T>, ms: number, tag: string): Promise<T> {
  return Promise.race([
    p,
    new Promise<never>((_, reject) =>
      setTimeout(
        () =>
          reject(
            new Error(
              `${tag} exceeded ${ms}ms hard cap — fail-fast, retry per BullMQ attempts`,
            ),
          ),
        ms,
      ),
    ),
  ]);
}

// T-M13 / FIND-P1-011 — `loadResumeState` was extracted to
// `./worker/resume-state.ts` so it could be unit-tested for the
// "visit deleted during retry" race (worker.ts has module-level side
// effects — Worker creation, Redis connect, Sentry init — which make
// it un-importable from tests).

async function processVisit(
  job: Job<ProcessVisitPayload>,
  workerClaimId?: string,
  workerDeliveryNumber?: number,
): Promise<void> {
  const admission = await prisma.transcribeVisit.findUnique({
    where: { id: job.data.visitId },
    select: {
      id: true,
      userId: true,
      inputMode: true,
      specialty: true,
      rawTextInput: true,
      dictationAudioKey: true,
      audioMimeType: true,
      audioSizeBytes: true,
      noteTemplateId: true,
      noteTemplateVersion: true,
      noteTemplate: {
        select: {
          status: true,
          templateKind: true,
          templateTwinCompiledVersion: {
            select: {
              certificationStatus: true,
              certification: { select: { id: true } },
              sourceArtifact: {
                select: {
                  validationStatus: true,
                  sha256: true,
                  sizeBytes: true,
                },
              },
            },
          },
        },
      },
      user: { select: { practiceId: true } },
      templateTwinSyntheticQaRun: {
        select: {
          id: true,
          admissionId: true,
          visitId: true,
          practiceId: true,
          doctorId: true,
          noteTemplateId: true,
          noteTemplateVersion: true,
          requestSha256: true,
          payloadSha256: true,
          mode: true,
          fixtureVersion: true,
          pinnedGlobalRolloutGeneration: true,
          pinnedPracticeRolloutGeneration: true,
          status: true,
          attempt: true,
          enqueuedAt: true,
          workerClaimId: true,
          workerClaimedAt: true,
          workerHeartbeatAt: true,
          workerLeaseExpiresAt: true,
          workerDeliveryCount: true,
          workerRetryReadyAt: true,
          admission: {
            select: {
              id: true,
              practiceId: true,
              actorId: true,
              parentAdmissionId: true,
              sourceSha256: true,
              sourceSizeBytes: true,
              providerMode: true,
              purpose: true,
              phase: true,
              requestSha256: true,
              payloadSha256: true,
              noteTemplateId: true,
              noteTemplateVersion: true,
              certificationId: true,
              visitId: true,
              attempt: true,
              expiresAt: true,
              failedAt: true,
              revokedAt: true,
              pinnedGlobalRolloutGeneration: true,
              pinnedPracticeRolloutGeneration: true,
            },
          },
        },
      },
    },
  });
  if (!admission) {
    throw new Error(`Visit ${job.data.visitId} not found`);
  }
  // Bridge mode must reject an already-queued/pinned Twin before the provider
  // context, transcription, extraction, or any other clinical model call.
  assertTemplateTwinWorkerRuntimeAdmission(
    admission.noteTemplate?.templateKind,
    process.env,
  );

  // Scenario 29 predates visit-time template pinning: the normal pipeline
  // resolves the active template at L4, after transcription/entity calls.
  // In the isolated QA harness only, pre-resolve that same active selection so
  // the legacy deterministic provider fixture can be scoped to this one
  // certified Template Twin visit instead of changing every visit process-wide.
  // This does not persist a pin or participate in the staging workflow; the
  // durable staging run remains the sole admission for the reviewed fixture.
  let providerTemplate = admission.noteTemplate;
  if (
    !providerTemplate &&
    isLegacyTemplateTwinInfrastructureFixtureEnvironment(process.env)
  ) {
    const resolved = await resolveActiveTemplateAdmission({
      doctorId: admission.userId,
      encounterType: admission.specialty,
    });
    if (resolved.template.templateKind === "template_twin_docx") {
      providerTemplate = await prisma.noteTemplate.findFirst({
        where: {
          id: resolved.template.id,
          doctorId: admission.userId,
          status: "active",
          templateKind: "template_twin_docx",
        },
        select: {
          status: true,
          templateKind: true,
          templateTwinCompiledVersion: {
            select: {
              certificationStatus: true,
              certification: { select: { id: true } },
              sourceArtifact: {
                select: {
                  validationStatus: true,
                  sha256: true,
                  sizeBytes: true,
                },
              },
            },
          },
        },
      });
    }
  }

  await runWithWorkerSyntheticQaProviderSelection(
    {
      id: admission.id,
      userId: admission.userId,
      practiceId: admission.user.practiceId,
      inputMode: admission.inputMode,
      noteTemplateId: admission.noteTemplateId,
      noteTemplateVersion: admission.noteTemplateVersion,
      rawTextInput: admission.rawTextInput,
      dictationAudioKey: admission.dictationAudioKey,
      audioMimeType: admission.audioMimeType,
      audioSizeBytes: admission.audioSizeBytes,
      templateAdmission: providerTemplate
        ? {
            status: providerTemplate.status,
            templateKind: providerTemplate.templateKind,
            certificationStatus:
              providerTemplate.templateTwinCompiledVersion
                ?.certificationStatus ?? null,
            hasCertification: Boolean(
              providerTemplate.templateTwinCompiledVersion?.certification,
            ),
            sourceValidationStatus:
              providerTemplate.templateTwinCompiledVersion?.sourceArtifact
                .validationStatus ?? null,
            sourceArtifactSha256:
              providerTemplate.templateTwinCompiledVersion?.sourceArtifact
                .sha256 ?? null,
            sourceArtifactSizeBytes:
              providerTemplate.templateTwinCompiledVersion?.sourceArtifact
                .sizeBytes ?? null,
          }
        : null,
      syntheticQaRun: admission.templateTwinSyntheticQaRun,
    },
    {
      userId: job.data.userId,
      syntheticQaRunId: job.data.syntheticQaRunId,
      syntheticQaAttempt: job.data.syntheticQaAttempt,
      workerClaimId,
      workerDeliveryNumber,
    },
    () => processVisitPipeline(job),
  );
}

async function processVisitPipeline(
  job: Job<ProcessVisitPayload>,
): Promise<void> {
  const { visitId } = job.data;

  // T-M16.3: tracks which pipeline layer is currently running. Updated
  // right before each `await runLayerX(...)` call so the outer catch
  // block can tag the Sentry event with an accurate `layer` value.
  // Values mirror the PipelineLayer enum in layer-skip.ts ('L1', 'L1b',
  // 'L2', 'L3', 'L4', 'L5', 'L6', 'automation') plus 'init'/'finalize'
  // bookends.
  let currentLayer: string = "init";

  const visit = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: {
      id: true,
      userId: true,
      audioKey: true,
      audioMimeType: true,
      dictationAudioKey: true,
      rawTextInput: true,
      specialty: true,
      inputMode: true,
      interpreterMode: true,
      createdAt: true,
      noteTemplateId: true,
      noteTemplateVersion: true,
      templateTwinFill: {
        select: { noteTemplateId: true, noteTemplateVersion: true },
      },
      user: { select: { practiceId: true } },
      // Fix-Pack 1 Q0-2 / audit Finding 01.1 — pull patient demographic
      // + safety context for L7c pediatric framing. Round 3 PR-D added
      // weightKg + allergies to TranscribeMdPatient; the FK is
      // NOT NULL since T-M17.2 so this select always populates.
      patient: {
        select: {
          dateOfBirth: true,
          weightKg: true,
          allergies: true,
        },
      },
    },
  });
  if (!visit) throw new Error(`Visit ${visitId} not found`);

  const practiceId = visit.user.practiceId;
  const startedAt = new Date();

  // Per-mode input validation. Keeps the branch bodies below simple.
  if (visit.inputMode === "audio_upload") {
    if (!visit.audioKey)
      throw new Error(`Visit ${visitId} has no audioKey (audio_upload mode).`);
    if (!visit.audioMimeType)
      throw new Error(`Visit ${visitId} has no audioMimeType.`);
  } else if (visit.inputMode === "voice_dictation") {
    if (!visit.dictationAudioKey)
      throw new Error(`Visit ${visitId} has no dictationAudioKey.`);
  } else if (visit.inputMode === "text_notes") {
    if (!visit.rawTextInput?.trim())
      throw new Error(`Visit ${visitId} has no rawTextInput.`);
  } else {
    throw new Error(`Unknown inputMode: ${visit.inputMode}`);
  }

  // text_notes skips TRANSCRIBING — nothing to transcribe.
  const initialStatus =
    visit.inputMode === "text_notes"
      ? TranscribeVisitStatus.EXTRACTING
      : TranscribeVisitStatus.TRANSCRIBING;

  await updateTemplateTwinSyntheticQaClaimBoundVisit({
    visitId,
    userId: visit.userId,
    practiceId,
    data: {
      status: initialStatus,
      processingStartedAt: startedAt,
      needsReview: false,
      reviewReason: null,
      // T-M13: previously cleared the five L7 columns here so a retry
      // wouldn't carry stale 'failed' entries. With per-layer resume
      // (below), successful L7 outputs are a CHECKPOINT — wiping them
      // would defeat resumability. Failed L7 layers are nulled by the
      // per-task catch (clearAutomationColumn) so the skip check
      // naturally re-runs only those. confidenceScores IS still
      // cleared because it's rebuilt from scratch in the roll-up
      // below, and stale failed entries would otherwise leak through.
      confidenceScores: Prisma.JsonNull,
    },
  });

  // T-M13 — load the per-layer checkpoint state BEFORE the sequential
  // stage. On attempt 1 (and after a user-triggered upload reset)
  // every column is null and the skip checks all return false, so
  // behavior matches the pre-T-M13 happy path. On BullMQ retry
  // (attempt > 1) whatever L1-L6 already succeeded is preserved in
  // columns — the checks below short-circuit those and the retry
  // resumes at the first non-populated layer.
  const attempt = job.attemptsMade + 1;
  const resumeState = await loadResumeState(visitId, job.attemptsMade);
  const skipped: PipelineLayer[] = [];

  try {
    // -------------------------------------------------------------------
    // Per-mode input stage — produces (entities, contextText).
    // -------------------------------------------------------------------
    let entities: ExtractedEntities;
    let contextText: string;
    // Round 3 quality fix-pack Q0-5 (audit Findings 02.5 + 07.3) —
    // visit-level Deepgram confidence aggregate. Populated by L1 /
    // L1b; null for text_notes (no audio) and for dictation runs
    // that disable utterance segmentation.
    let audioConfidenceStats: AudioConfidenceStats | null = null;

    if (visit.inputMode === "audio_upload") {
      // ── L1 — Deepgram with diarize on ───────────────────────────
      if (isLayerComplete(resumeState, "L1")) {
        logSkippedLayer(visitId, "L1", attempt);
        skipped.push("L1");
      } else {
        currentLayer = "L1";
        await runLayer1Transcribe({
          visitId,
          practiceId,
          userId: visit.userId,
          audioKey: visit.audioKey!,
          audioMimeType: visit.audioMimeType!,
          interpreterMode: visit.interpreterMode,
          // Issues #202 + #206 — scope keyterm payload to the visit's
          // clinical context. Free-text; builder normalizes.
          specialty: visit.specialty,
        });
      }

      // Always re-read transcriptRaw — whether L1 ran or was skipped,
      // downstream layers need the utterances.
      const withTranscript = await prisma.transcribeVisit.findUnique({
        where: { id: visitId },
        select: {
          transcriptRaw: true,
          speakerMap: true,
          // Round 3 PR-D — A06-P0-001 empty-transcript guard reads
          // these two columns. L1 wrote them; if they're missing the
          // guard fails the visit before L2 burns Anthropic budget.
          audioDurationSec: true,
          transcriptText: true,
          // Round 3 quality fix-pack Q0-5 — L1 wrote this column
          // with the Deepgram per-utterance confidence aggregate.
          // L4 + L5 read it through the worker plumbing below.
          audioConfidenceStats: true,
        },
      });
      const raw = withTranscript?.transcriptRaw as
        | DeepgramBatchResponse
        | null
        | undefined;
      const utterances: DeepgramUtterance[] = raw?.results?.utterances ?? [];
      audioConfidenceStats =
        (withTranscript?.audioConfidenceStats as
          | AudioConfidenceStats
          | null
          | undefined) ?? null;

      // Round 3 PR-D — A06-P0-001 empty-transcript guard. Throws
      // PipelineRejectError on insufficient audio/transcript; the
      // outer catch maps it to FAILED + needsReview with the
      // doctor-actionable humanReason rendered in the visit banner.
      await assertSufficientTranscript({
        visitId,
        practiceId,
        userId: visit.userId,
        durationSec: withTranscript?.audioDurationSec ?? 0,
        transcriptText: withTranscript?.transcriptText ?? "",
      });

      // ── L2 — speaker roles ──────────────────────────────────────
      await updateTemplateTwinSyntheticQaClaimBoundVisit({
        visitId,
        userId: visit.userId,
        practiceId,
        data: { status: TranscribeVisitStatus.EXTRACTING },
      });
      let speakerMap: SpeakerMap;
      if (isLayerComplete(resumeState, "L2")) {
        logSkippedLayer(visitId, "L2", attempt);
        skipped.push("L2");
        speakerMap = (withTranscript?.speakerMap ?? {}) as SpeakerMap;
      } else {
        currentLayer = "L2";
        const r = await runLayer2SpeakerRoles({
          visitId,
          practiceId,
          userId: visit.userId,
          utterances,
          interpreterMode: visit.interpreterMode,
        });
        speakerMap = r.speakerMap;
      }

      // ── L3 — conversation entities ──────────────────────────────
      if (isLayerComplete(resumeState, "L3")) {
        logSkippedLayer(visitId, "L3", attempt);
        skipped.push("L3");
        entities = resumeState.entities as ExtractedEntities;
        // contextText is a derived string (not persisted) — rebuild
        // from the same inputs L3 would have used.
        contextText = buildRoleLabeledTranscript(utterances, speakerMap);
      } else {
        currentLayer = "L3";
        const l3 = await runLayer3ExtractEntities({
          visitId,
          practiceId,
          userId: visit.userId,
          mode: "conversation",
          utterances,
          speakerMap,
        });
        entities = l3.entities;
        contextText = l3.contextText;
      }
      // 2026-06-11 inaudible-span hardening telemetry (audit WARN-2): the
      // per-visit marker count is the observable for threshold tuning and
      // doctor-habituation monitoring during the pilot. Clean prod audio is
      // expected at ~2-6; a flood means the mic or threshold needs review.
      {
        const unclearMarkers = countUnclearMarkers(contextText);
        if (unclearMarkers > 0) {
          log.info(
            "transcribe-md-worker",
            "unclear-span markers in transcript",
            {
              visitId,
              unclearMarkers,
              utterances: utterances.length,
            },
          );
        }
      }
    } else if (visit.inputMode === "voice_dictation") {
      // ── L1' — single-speaker Deepgram ──────────────────────────
      let dictationText: string;
      if (isLayerComplete(resumeState, "L1b")) {
        logSkippedLayer(visitId, "L1b", attempt);
        skipped.push("L1b");
        dictationText = resumeState.transcriptText ?? "";
      } else {
        currentLayer = "L1b";
        const r = await runLayer1bTranscribeDictation({
          visitId,
          practiceId,
          userId: visit.userId,
          dictationAudioKey: visit.dictationAudioKey!,
          // Dictations come from browser MediaRecorder → webm/opus.
          // Deepgram auto-detects encoding from the Content-Type header.
          dictationMimeType:
            process.env.TRANSCRIBE_MD_DICTATION_MIME ?? "audio/webm",
          interpreterMode: visit.interpreterMode,
          // Issues #202 + #206 — scope keyterm payload to the visit's
          // clinical context.
          specialty: visit.specialty,
        });
        dictationText = r.transcript;
      }

      // Round 3 PR-D — A06-P0-001 empty-transcript guard (dictation
      // path). Read the duration L1b just wrote and run the same
      // assertion the audio_upload path uses.
      // Round 3 quality fix-pack Q0-5 — also read audioConfidenceStats
      // here so L4/L5 can see it on the dictation branch (will be
      // null today since L1b runs Deepgram with utterances disabled,
      // but the wiring is parallel to the audio_upload branch).
      const withDictationDuration = await prisma.transcribeVisit.findUnique({
        where: { id: visitId },
        select: {
          dictationDurationSec: true,
          audioConfidenceStats: true,
        },
      });
      await assertSufficientTranscript({
        visitId,
        practiceId,
        userId: visit.userId,
        durationSec: withDictationDuration?.dictationDurationSec ?? 0,
        transcriptText: dictationText,
      });
      audioConfidenceStats =
        (withDictationDuration?.audioConfidenceStats as
          | AudioConfidenceStats
          | null
          | undefined) ?? null;

      // ── L3 — dictation entities ─────────────────────────────────
      await updateTemplateTwinSyntheticQaClaimBoundVisit({
        visitId,
        userId: visit.userId,
        practiceId,
        data: { status: TranscribeVisitStatus.EXTRACTING },
      });
      if (isLayerComplete(resumeState, "L3")) {
        logSkippedLayer(visitId, "L3", attempt);
        skipped.push("L3");
        entities = resumeState.entities as ExtractedEntities;
        contextText = dictationText.trim();
      } else {
        currentLayer = "L3";
        const l3 = await runLayer3ExtractEntities({
          visitId,
          practiceId,
          userId: visit.userId,
          mode: "dictation",
          dictationText,
        });
        entities = l3.entities;
        contextText = l3.contextText;
      }
    } else {
      // text_notes — no transcription step. L3 is the earliest layer.
      if (isLayerComplete(resumeState, "L3")) {
        logSkippedLayer(visitId, "L3", attempt);
        skipped.push("L3");
        entities = resumeState.entities as ExtractedEntities;
        contextText = (visit.rawTextInput ?? "").trim();
      } else {
        currentLayer = "L3";
        const l3 = await runLayer3ExtractEntities({
          visitId,
          practiceId,
          userId: visit.userId,
          mode: "text",
          rawText: visit.rawTextInput!,
        });
        entities = l3.entities;
        contextText = l3.contextText;
      }
    }

    // Q1 #02.8: if the extractor flagged a conflicting/superseded allergy
    // statement, surface a visible needsReview so the doctor resolves it.
    // (The conflict also renders in the SOAP allergies via conflict_note +
    // drives the Rx contraindication warning.) COALESCE keeps any existing
    // reviewReason (low-conf / fallback) rather than clobbering it; the
    // needsReview boolean is purely additive. Never blocks the pipeline.
    if (entities.allergies?.some((a) => a.superseded === true)) {
      try {
        await runTemplateTwinSyntheticQaClaimBoundMutation({
          visitId,
          userId: visit.userId,
          practiceId,
          mutate: async (client) => {
            await client.$executeRaw`
              UPDATE "transcribe_visits"
              SET "needsReview" = true,
                  "reviewReason" = COALESCE(
                    "reviewReason",
                    'Conflicting allergy statements were detected in this visit — verify the allergy list before signing.'
                  )
              WHERE id = ${visitId}
            `;
          },
        });
      } catch {
        // Review-flag is advisory; the conflict still surfaces in the SOAP
        // + the Rx warning. Never fail the visit on this write.
      }
    }

    // -------------------------------------------------------------------
    // Layers 4-6 — mode-agnostic.
    // -------------------------------------------------------------------
    await updateTemplateTwinSyntheticQaClaimBoundVisit({
      visitId,
      userId: visit.userId,
      practiceId,
      data: { status: TranscribeVisitStatus.DRAFTING },
    });
    // Resolve the doctor's template once, then reuse the exact persisted pin
    // on retries. A first-pass generic-template lookup may retain the legacy
    // system-default fallback; existing provenance must fail closed instead
    // of silently switching layout versions.
    let noteTemplate: ResolvedNoteTemplate;
    let selectedTemplate: NoteTemplate | null = null;
    let selectedTemplateRolloutToken: TemplateTwinRolloutToken | null = null;
    const fillPin = visit.templateTwinFill;
    const pinnedTemplateId = fillPin?.noteTemplateId ?? visit.noteTemplateId;
    const pinnedTemplateVersion =
      fillPin?.noteTemplateVersion ?? visit.noteTemplateVersion;
    try {
      if (
        fillPin &&
        visit.noteTemplateId &&
        (fillPin.noteTemplateId !== visit.noteTemplateId ||
          fillPin.noteTemplateVersion !== visit.noteTemplateVersion)
      ) {
        throw new Error(
          "Template Twin visit provenance is internally inconsistent.",
        );
      }
      const admission = await resolveVisitTemplateAdmission({
        visitId,
        doctorId: visit.userId ?? "",
        encounterType: visit.specialty,
        pinnedTemplateId,
        pinnedTemplateVersion,
      });
      selectedTemplate = admission.template;
      selectedTemplateRolloutToken = admission.templateTwinRolloutToken;
      noteTemplate = normalizeTemplate(selectedTemplate);
    } catch (err) {
      if (pinnedTemplateId || pinnedTemplateVersion != null) throw err;
      log.warn(
        "worker:note-template",
        "initial template resolution failed; falling back to system default",
        { visitId, err: err instanceof Error ? err.message : String(err) },
      );
      noteTemplate = SYSTEM_DEFAULT_NOTE_TEMPLATE;
    }

    let soapDraft: string;
    if (isLayerComplete(resumeState, "L4")) {
      logSkippedLayer(visitId, "L4", attempt);
      skipped.push("L4");
      soapDraft = resumeState.soapDraft ?? "";
    } else {
      currentLayer = "L4";
      soapDraft = await runLayer4GenerateSoap({
        visitId,
        practiceId,
        userId: visit.userId,
        specialty: visit.specialty,
        roleLabeledTranscript: contextText,
        entities,
        // Round 3 quality fix-pack Q0-5 — visit-level Deepgram
        // confidence aggregate. Drives the L4 hedge prompt when
        // the audio fidelity was poor.
        audioConfidenceStats,
        interpreterMode: visit.interpreterMode,
        noteTemplate,
      });
    }

    await updateTemplateTwinSyntheticQaClaimBoundVisit({
      visitId,
      userId: visit.userId,
      practiceId,
      data: { status: TranscribeVisitStatus.CRITIQUING },
    });
    let critique: Awaited<ReturnType<typeof runLayer5SelfCritique>>;
    if (isLayerComplete(resumeState, "L5")) {
      logSkippedLayer(visitId, "L5", attempt);
      skipped.push("L5");
      critique = resumeState.critique as typeof critique;
    } else {
      currentLayer = "L5";
      critique = await runLayer5SelfCritique({
        visitId,
        practiceId,
        userId: visit.userId,
        specialty: visit.specialty,
        soapDraft,
        roleLabeledTranscript: contextText,
        entities,
        // Round 3 quality fix-pack Q0-5 — same hedge signal L4 sees,
        // so the auditor can flag SOAP content the audio doesn't
        // clearly support as critical hallucinations.
        audioConfidenceStats,
        noteTemplate,
      });
    }

    await updateTemplateTwinSyntheticQaClaimBoundVisit({
      visitId,
      userId: visit.userId,
      practiceId,
      data: { status: TranscribeVisitStatus.POLISHING },
    });
    let polished: { soapFinal: string };
    if (isLayerComplete(resumeState, "L6")) {
      logSkippedLayer(visitId, "L6", attempt);
      skipped.push("L6");
      polished = { soapFinal: resumeState.soapFinal ?? "" };
    } else {
      currentLayer = "L6";
      polished = await runLayer6Polish({
        visitId,
        practiceId,
        userId: visit.userId,
        soapDraft,
        critique,
        noteTemplate,
      });
    }

    // Template Twin is generated only after the exact physician-visible SOAP
    // exists. The immutable fill manifest pins that current SOAP version and
    // canonical digest; a later edit invalidates the fill and the sign gate
    // independently compares both values again.
    if (selectedTemplate?.templateKind === "template_twin_docx") {
      currentLayer = "template_twin";
      if (!selectedTemplateRolloutToken) {
        throw new TemplateTwinWorkerRolloutError();
      }
      assertSyntheticQaResolvedRolloutToken(selectedTemplateRolloutToken);
      const currentSoap = await prisma.transcribeVisit.findUnique({
        where: { id: visitId },
        select: { soapFinal: true, soapVersion: true },
      });
      if (!currentSoap?.soapFinal?.trim()) {
        throw new Error(
          "Template Twin requires a current SOAP note before rendering.",
        );
      }
      const twinFill = await processTemplateTwinVisit({
        visitId,
        soapVersion: currentSoap.soapVersion,
        soapFinal: currentSoap.soapFinal,
        practiceId,
        doctorId: visit.userId,
        noteTemplateId: selectedTemplate.id,
        noteTemplateVersion: selectedTemplate.version,
        inputMode:
          visit.inputMode === "audio_upload"
            ? "conversation"
            : visit.inputMode === "voice_dictation"
              ? "dictation"
              : "text",
        contextText,
        entities,
        asrQuality: audioConfidenceStats
          ? shouldFlagForReview(audioConfidenceStats)
            ? "review"
            : "high"
          : "unknown",
        validationNow: visit.createdAt,
        resolverModelVersion:
          process.env.TRANSCRIBE_MD_CLINICAL_MODEL || "claude-sonnet-4-6",
        rolloutToken: selectedTemplateRolloutToken,
      });
      if (
        twinFill.manifest.counts.needsReview > 0 ||
        twinFill.render === null
      ) {
        await runTemplateTwinSyntheticQaClaimBoundMutation({
          visitId,
          userId: visit.userId,
          practiceId,
          mutate: async (client) => {
            await client.$executeRaw`
              UPDATE "transcribe_visits"
              SET "reviewReason" = CASE
                    WHEN "needsReview" = false
                      THEN ${TEMPLATE_TWIN_REVIEW_REASON}
                    ELSE "reviewReason"
                  END,
                  "needsReview" = true
              WHERE id = ${visitId}
            `;
          },
        });
      }
    }

    // -------------------------------------------------------------------
    // T-M6 — controlled automation fan-out. Each L7x layer runs against the
    // same polished SOAP + entities and every outcome is persisted. Ordinary
    // visits retain the existing optional-layer contract; synthetic staging
    // requires all five deterministic L7 fixtures before finalization.
    // -------------------------------------------------------------------
    currentLayer = "automation";
    await updateTemplateTwinSyntheticQaClaimBoundVisit({
      visitId,
      userId: visit.userId,
      practiceId,
      data: { status: TranscribeVisitStatus.AUTOMATING },
    });

    const soapFinalForFanout = polished.soapFinal;
    const entitiesJson = JSON.stringify(entities);

    // Env feature flags — operators can disable any layer without a
    // code change if costs spike or a layer misbehaves in prod.
    // An IMAGING REPORT (e.g. ultrasound) has no office-visit E/M level, so
    // suppress L7b (CPT/E&M) for those specialties — its task records
    // status:'skipped' (never a needsReview false-flag). ICD/Rx/referrals stay
    // on (a venous study can still carry an indication diagnosis). This is the
    // pipeline-level E/M suppression; the on-read E/M coaching score is
    // suppressed separately at the visit-detail read (see page.tsx).
    const isImagingReport = isImagingReportSpecialty(visit.specialty);
    const flags = {
      icd: process.env.TM_ENABLE_ICD_CPT !== "false",
      cpt: process.env.TM_ENABLE_ICD_CPT !== "false" && !isImagingReport,
      rx: process.env.TM_ENABLE_RX !== "false",
      referrals: process.env.TM_ENABLE_REFERRALS !== "false",
      summary: process.env.TM_ENABLE_PATIENT_SUMMARY !== "false",
    };

    const tasks: AutomationFanoutTask[] = [
      {
        key: "icd_coding",
        enabled: flags.icd,
        provider: {
          provider: "anthropic",
          model: "claude-sonnet-4-6",
          operationVersion: "l7a-v1",
        },
        run: (providerIdempotencyKey) =>
          runLayer7aIcdCoding({
            visitId,
            practiceId,
            userId: visit.userId,
            specialty: visit.specialty,
            soapFinal: soapFinalForFanout,
            entitiesJson,
            providerIdempotencyKey,
          }),
        validate: (output) => {
          const codes = (output as { codes?: Array<{ code?: string }> }).codes;
          if (
            !Array.isArray(codes) ||
            codes.length === 0 ||
            (codes.length === 1 && codes[0]?.code?.toUpperCase() === "Z76.89")
          ) {
            const error = new Error("Required ICD output validation failed.");
            error.name = "AutomationOutputValidationError";
            throw error;
          }
        },
      },
      {
        key: "cpt_coding",
        enabled: flags.cpt,
        provider: {
          provider: "anthropic",
          model: "claude-sonnet-4-6",
          operationVersion: "l7b-v1",
        },
        run: (providerIdempotencyKey) =>
          runLayer7bCptCoding({
            visitId,
            practiceId,
            userId: visit.userId,
            specialty: visit.specialty,
            soapFinal: soapFinalForFanout,
            entitiesJson,
            providerIdempotencyKey,
          }),
        validate: (output) => {
          const result = output as {
            em?: { code?: string | null } | null;
            procedures?: unknown[];
          };
          if (
            !result.em?.code &&
            (!Array.isArray(result.procedures) ||
              result.procedures.length === 0)
          ) {
            const error = new Error("Required CPT output validation failed.");
            error.name = "AutomationOutputValidationError";
            throw error;
          }
        },
      },
      {
        key: "rx_drafting",
        enabled: flags.rx,
        provider: {
          provider: "anthropic",
          model: process.env.TRANSCRIBE_MD_CLINICAL_MODEL || "claude-opus-4-8",
          operationVersion: "l7c-v1",
        },
        run: (providerIdempotencyKey) =>
          runLayer7cRxDrafting({
            visitId,
            practiceId,
            userId: visit.userId,
            soapFinal: soapFinalForFanout,
            entitiesJson,
            providerIdempotencyKey,
            // Fix-Pack 1 Q0-2 / audit Finding 01.1 — patient context
            // for pediatric mg/kg/day framing. `patient` is non-null
            // because TranscribeVisit.patientId is NOT NULL since
            // T-M17.2; the field-level guards (DOB, weight) are
            // resolved inside the layer.
            patient: {
              dateOfBirth: visit.patient.dateOfBirth,
              weightKg: visit.patient.weightKg,
              allergies: visit.patient.allergies,
            },
          }),
      },
      {
        key: "referrals",
        enabled: flags.referrals,
        provider: {
          provider: "anthropic",
          model: "claude-sonnet-4-6",
          operationVersion: "l7d-v1",
        },
        run: (providerIdempotencyKey) =>
          runLayer7dReferrals({
            visitId,
            practiceId,
            userId: visit.userId,
            soapFinal: soapFinalForFanout,
            entitiesJson,
            providerIdempotencyKey,
          }),
      },
      {
        key: "patient_summary",
        enabled: flags.summary,
        provider: {
          provider: "anthropic",
          model: "claude-sonnet-4-6",
          operationVersion: "l7e-v1",
        },
        run: (providerIdempotencyKey) =>
          runLayer7ePatientSummary({
            visitId,
            practiceId,
            userId: visit.userId,
            specialty: visit.specialty,
            soapFinal: soapFinalForFanout,
            entitiesJson,
            providerIdempotencyKey,
          }),
        metadata: (output) => {
          const result = output as {
            fleschKincaid?: number;
            flagged?: boolean;
          };
          return {
            flesch_kincaid: result.fleschKincaid,
            flagged: result.flagged,
          };
        },
      },
    ];

    const stagingAutomation = Boolean(
      getTemplateTwinSyntheticQaProviderContext(),
    );
    // E/M scoring remains available on demand, but cache prewarm is explicitly
    // NOT_APPLICABLE in this durable fanout. The legacy direct SDK helper has
    // an internal parse retry and Redis write that cannot satisfy the provider
    // execution ledger's at-most-once projection contract.
    const emMdmPrewarmEnabled = false;
    tasks.push({
      key: "em_mdm_prewarm",
      enabled: emMdmPrewarmEnabled,
      provider: {
        provider: "anthropic",
        model: "claude-sonnet-4-6",
        operationVersion: "em-mdm-prewarm-v1-disabled",
      },
      run: async () => {
        throw new Error("E/M prewarm is not applicable to durable fanout.");
      },
    });

    const automationSoap = await prisma.transcribeVisit.findUnique({
      where: { id: visitId },
      select: { soapFinal: true, soapVersion: true },
    });
    if (!automationSoap?.soapFinal) {
      throw new Error("Current SOAP is unavailable for automation binding.");
    }
    const automationPolicy = buildVisitAutomationPolicy({
      staging: stagingAutomation,
      enabled: {
        icd_coding: flags.icd,
        cpt_coding: flags.cpt,
        rx_drafting: flags.rx,
        referrals: flags.referrals,
        patient_summary: flags.summary,
        em_mdm_prewarm: emMdmPrewarmEnabled,
      },
    });
    const automationAttempt = await initializeVisitAutomationManifest({
      visitId,
      userId: visit.userId,
      practiceId,
      soapVersion: automationSoap.soapVersion,
      soapFinal: automationSoap.soapFinal,
      sourceFacts: entities,
      policy: automationPolicy,
    });
    const confidenceScores = await runAutomationFanout({
      attempt: automationAttempt,
      visitId,
      userId: visit.userId,
      practiceId,
      tasks,
    });

    // -------------------------------------------------------------------
    // Finalise. Sum per-layer costs from ai_calls (includes T-M4 layers
    // + T-M6 layers). Fail-open if AiCall read errors; the cost number
    // is observability, not load-bearing for correctness.
    // -------------------------------------------------------------------
    const costRows = await prisma.aiCall.findMany({
      where: { visitId },
      select: { costUsdCents: true },
    });
    const totalCents = costRows.reduce(
      (sum: number, r: { costUsdCents: number | null }) =>
        sum + (r.costUsdCents ?? 0),
      0,
    );

    // FIND-P1-012 (2026-05-14): parse + JSON-round-trip
    // confidenceScores before the write. Prisma's JSONB adapter
    // silently coerces non-serializable values (Map → {}, function
    // → drop) which can leave the column with a shape that L2/L7
    // can't read back. The sanitizer returns null on schema-fail or
    // serialize-fail; null is the same shape the column carries on
    // first-attempt initial state (worker.ts:297), so downstream
    // readers handle it.
    const safeConfidenceScores = sanitizeConfidenceScores(confidenceScores);
    if (safeConfidenceScores === null) {
      console.warn(
        `[transcribe-md-worker] confidenceScores schema/serialize fail for visit=${visitId}, writing null`,
      );
    }
    const processingFinishedAt = new Date();
    await finalizeVisitAutomationReady({
      attempt: automationAttempt,
      visitId,
      userId: visit.userId,
      practiceId,
      processingFinishedAt,
      processingCostCents: totalCents,
      confidenceScores: safeConfidenceScores as Prisma.InputJsonValue | null,
    });
    // T-M13 summary line — logs only when at least one layer was
    // skipped, so happy-path first attempts stay quiet.
    logSkipSummary(visitId, attempt, skipped);
  } catch (err) {
    // FIND-P1-011: visit deleted between top-level findUnique and a
    // BullMQ retry's resume-state load. Short-circuit: don't try to
    // write FAILED state to a non-existent row (P2025), don't burn
    // the admin notify, don't pretend this needs further retry.
    // Returning cleanly tells BullMQ the job is done — which it is,
    // the visit's gone. The cleanup sweep handles the orphaned audio.
    if (err instanceof VisitNotFoundError) {
      log.info(
        "transcribe-md-worker",
        "visit deleted during retry, dropping job",
        { visitId, attemptsMade: job.attemptsMade ?? 0 },
      );
      return;
    }

    const category = categorizeError(err);
    const attemptsMade = job.attemptsMade ?? 0;
    const attempts = job.opts.attempts ?? 1;
    const isFinalAttempt = shouldMarkVisitFailed(attemptsMade, attempts);
    const stagingContext = getTemplateTwinSyntheticQaProviderContext();
    if (stagingContext && !isFinalAttempt && category !== "permanent") {
      try {
        await prepareTemplateTwinSyntheticQaDeliveryRetry({
          visitId,
          userId: visit.userId,
          practiceId: visit.user?.practiceId ?? "",
          nextWorkerDeliveryNumber: attemptsMade + 2,
        });
      } catch (handoffError) {
        // A retry without a committed lease handoff is forbidden. Retire the
        // attempt under the same canonical locks; if that also fails, the
        // original handoff error remains visible to BullMQ and finalization
        // stays blocked by the nonterminal manifest.
        await failTemplateTwinSyntheticQaProcessing({
          visitId,
          userId: visit.userId,
          practiceId: visit.user?.practiceId ?? "",
          reviewReason: buildUserFacingFailureReason(
            currentLayer,
            categorizeError(handoffError),
            handoffError,
          ),
          failureCategory: categorizeError(handoffError),
        });
        throw handoffError;
      }
      log.warn(
        "transcribe-md-worker",
        "synthetic QA delivery failed; durable retry handoff committed",
        {
          visitId,
          layer: currentLayer,
          nextWorkerDeliveryNumber: attemptsMade + 2,
        },
      );
      throw err;
    }

    // T-M16.3: Deepgram/Anthropic errors can quote audio/file metadata
    // or URLs — scrub before emitting to container stdout. Sentry path
    // (captureWorkerException below) does its own redactPhi via the
    // beforeSend hook, so double-coverage is intentional.
    const stagingFailure = await failTemplateTwinSyntheticQaProcessing({
      visitId,
      userId: visit.userId,
      practiceId: visit.user?.practiceId ?? "",
      reviewReason: buildUserFacingFailureReason(
        currentLayer,
        category,
        err,
      ),
      failureCategory: category,
    });
    if (stagingFailure) {
      log.warn(
        "transcribe-md-worker",
        "synthetic QA attempt failed without external notification",
        { visitId, layer: currentLayer },
      );
      throw err;
    }
    console.error(
      `[transcribe-md-worker] visit ${visitId} failed:`,
      redactPhi(err instanceof Error ? err.message : err),
    );
    // T-M16.3: capture to Sentry BEFORE the re-throw so BullMQ's retry
    // still sees the original error. The {visitId, layer} tags let ops
    // filter errors by failure point without reading the stack trace.
    // Round 3 PR-H: pass userId + practiceId as tags too — IDs only,
    // never email/name/MRN.
    captureWorkerException(err, {
      visitId,
      layer: currentLayer,
      userId: visit.userId,
      practiceId,
    });

    // T-M23.A: only persist FAILED on the final BullMQ attempt …
    // *unless* this fix-pass classifies the error as `permanent`. A
    // permanent error (Zod, "unsupported format", zero-byte audio,
    // etc.) will fail the same way on every retry — burning two more
    // BullMQ attempts is just two more Anthropic / Deepgram calls
    // for the same outcome. Fail-fast in that case so the doctor
    // sees the actionable banner ~5s instead of ~25s after submit.
    const categoryForOrdinaryVisit: ErrorCategory = category;
    // Q1 #09.1: surface Anthropic content-policy refusals as a distinct,
    // countable audit action (categorizeError maps them permanent → the
    // fail-fast path below fires on the first attempt, so this emits once).
    // This PHI-safe refusal audit is awaited. If durable enqueue fails, the
    // worker must fail rather than advancing through an unaudited branch.
    if (err instanceof Error && err.name === "AnthropicRefusalError") {
      const refusal = err as Error & { model?: string; purpose?: string };
      await logWorkerAudit({
        action: "AI_REFUSAL",
        targetType: "TranscribeVisit",
        targetId: visitId,
        userId: visit.userId,
        practiceId,
        success: false,
        errorCode: "AI_REFUSAL",
        metadata: {
          layer: currentLayer,
          model: refusal.model ?? null,
          purpose: refusal.purpose ?? null,
        },
      });
    }
    const shouldFailNow =
      isFinalAttempt || categoryForOrdinaryVisit === "permanent";
    if (!shouldFailNow) {
      log.info(
        "transcribe-md-worker",
        "transient failure, awaiting BullMQ retry",
        {
          visitId,
          layer: currentLayer,
          category: categoryForOrdinaryVisit,
          attemptsMade,
          attempts,
        },
      );
      throw err;
    }
    if (categoryForOrdinaryVisit === "permanent" && !isFinalAttempt) {
      log.info(
        "transcribe-md-worker",
        "permanent failure, fail-fast (skipping BullMQ retries)",
        { visitId, layer: currentLayer, attemptsMade, attempts },
      );
    }

    // FIND-P1-014: persist FAILED-state via a helper that returns
    // a structured {persistOk, persistErr} result instead of silently
    // swallowing write failures. The original `err` already went to
    // Sentry above; the helper additionally logs + captures the
    // *secondary* (persist) failure so post-mortems have both halves.
    // Policy: re-throw `persistErr` below so BullMQ marks the job
    // failed with the persist failure as the proximate cause —
    // silent stuck-in-non-terminal is the worse failure mode.
    const { persistOk, persistErr } = await persistFailedState({
      visitId,
      category: categoryForOrdinaryVisit,
      layer: currentLayer,
      originalErr: err,
      reviewReason: buildUserFacingFailureReason(
        currentLayer,
        categoryForOrdinaryVisit,
        err,
      ),
      userId: visit.userId,
      practiceId,
    });

    // Best-effort admin alert. notifyAdminOnFailure swallows every
    // failure path internally — a misconfigured Resend account must
    // never mask the underlying pipeline error in Sentry.
    void prisma.user
      .findUnique({
        where: { id: visit.userId },
        select: { email: true },
      })
      .then((u: { email: string } | null) =>
        notifyAdminOnFailure({
          visitId,
          userId: visit.userId,
          userEmail: u?.email ?? null,
          practiceId: visit.user?.practiceId ?? null,
          layer: currentLayer,
          category,
          scrubbedError: redactPhi(
            err instanceof Error ? err.message : String(err ?? ""),
          ),
          audioDurationSec: null,
        }),
      )
      .catch((notifyErr: unknown) => {
        console.error(
          "[transcribe-md-worker] admin-notify outer catch:",
          redactPhi(notifyErr instanceof Error ? notifyErr.message : notifyErr),
        );
      });

    // FIND-P1-014: if FAILED-state persist failed, surface the
    // persist error to BullMQ. The visit row remains in its
    // non-terminal status (POLISHING / AUTOMATING / etc.) until the
    // stuck-visit watchdog catches it at the 15-min threshold and
    // force-fails it. Re-throwing here (rather than the original
    // `err`) gives BullMQ the persist context as the job's proximate
    // failure; the original error is already in Sentry.
    if (!persistOk) {
      throw persistErr;
    }

    throw err;
  }
}

/** Maps `currentLayer` (the worker's pipeline tracker — 'L1', 'L2',
 *  'automation', etc.) to a human-readable phrase used in the
 *  FAILED-state banner. Never includes any content from the thrown
 *  error, so PHI can't bleed into the UI. Doctors see a layer name,
 *  ops + Sentry see the full scrubbed error + stack.
 *
 *  The `category` argument tunes the call-to-action sentence so a
 *  permanent / provider-down failure says something more useful
 *  than a generic "try retrying". Falls back to the original copy
 *  for unknown / transient cases so existing UI snapshots still
 *  match. */
function buildUserFacingFailureReason(
  currentLayer: string,
  category: ErrorCategory = "transient",
  err?: unknown,
): string {
  // Round 3 PR-D — A06-P0-001 empty-transcript guard. PipelineRejectError
  // carries a doctor-actionable humanReason ("Recording is 1.4s; need at
  // least 3s ..."). Use it verbatim so the visit banner tells the doctor
  // exactly what happened, not the generic "audio may be corrupt" copy.
  if (
    err instanceof Error &&
    err.name === "PipelineRejectError" &&
    typeof (err as unknown as { humanReason?: unknown }).humanReason ===
      "string"
  ) {
    return (err as unknown as { humanReason: string }).humanReason;
  }

  // Q1 #09.1: a content-policy refusal is NOT an audio/format problem —
  // the generic "permanent" copy ("file may be corrupt") would mislead.
  // Give the doctor an accurate, actionable banner.
  if (err instanceof Error && err.name === "AnthropicRefusalError") {
    return "Processing was declined by the AI provider’s safety system for this visit’s content. This is not an audio problem — please review the recording/notes, and if the content is clinically appropriate, contact support.";
  }

  const phraseByLayer: Record<string, string> = {
    init: "setup",
    L1: "transcription",
    L1b: "transcription",
    L2: "speaker identification",
    L3: "entity extraction",
    L4: "SOAP drafting",
    L5: "clinical audit",
    L6: "polish",
    automation: "codes / Rx / referrals generation",
    finalize: "finalization",
  };
  const phrase = phraseByLayer[currentLayer] ?? "processing";
  if (category === "permanent") {
    return `Processing failed during ${phrase}. The audio file may be corrupt or in an unsupported format — please re-upload to try again.`;
  }
  if (category === "provider_down") {
    return `Processing failed during ${phrase}. Our transcription provider is temporarily unavailable; please try again in a few minutes.`;
  }
  return `Processing failed during ${phrase}. Try retrying this visit, or contact support if it keeps failing.`;
}

/** T-M12 — start the MinIO orphan cleanup worker + schedule the
 *  recurring job. No-op unless MINIO_ORPHAN_CLEANUP_ENABLED=true, so
 *  production deployments stay off until ops flips the flag. */
async function startCleanupWorker(): Promise<void> {
  // T-M17.3: the cleanup worker now handles TWO job types on the
  // shared CLEANUP_QUEUE_NAME — MinIO orphan sweeps (T-M12) and
  // stale-visit sweeps (T-M17.3). Start the worker if EITHER is
  // enabled; register each scheduler independently below.
  if (
    !CLEANUP_ENABLED &&
    !STALE_VISIT_CLEANUP_ENABLED &&
    !RETENTION_SWEEP_ENABLED &&
    !STUCK_VISIT_WATCHDOG_ENABLED &&
    !TEMPLATE_TWIN_MAINTENANCE_ENABLED
  ) {
    log.info("ops:cleanup", "disabled", {
      reason:
        "all cleanup flags off (MINIO_ORPHAN_CLEANUP_ENABLED, STALE_VISIT_CLEANUP_ENABLED, RETENTION_SWEEP_ENABLED, STUCK_VISIT_WATCHDOG_ENABLED, TEMPLATE_TWIN_MAINTENANCE_ENABLED)",
    });
    return;
  }

  const cleanupWorker = new Worker(
    CLEANUP_QUEUE_NAME,
    async (job) => {
      if (job.name === JOB_MINIO_ORPHAN_CLEANUP) {
        // Read env on every run so ops can toggle dryRun between
        // scheduled invocations without touching the scheduler.
        const dryRun =
          (process.env.MINIO_ORPHAN_CLEANUP_DRY_RUN ?? "true").toLowerCase() !==
          "false";
        const retentionDays = Number.parseInt(
          process.env.MINIO_ORPHAN_CLEANUP_RETENTION_DAYS ?? "30",
          10,
        );
        await withTimeout(
          runMinioOrphanCleanup({ dryRun, retentionDays }),
          CLEANUP_TIMEOUT_MS,
          "minio-orphan-cleanup",
        );
        // T-M18.2 A13: mark "I ran" so /api/health can surface a
        // silently-dead cron.
        await recordCleanupHeartbeat("minio-orphan-cleanup", {
          dryRun,
          retentionDays,
        });
        return;
      }
      if (job.name === JOB_STALE_VISIT_CLEANUP) {
        const result = await withTimeout(
          runStaleVisitCleanup(),
          STALE_VISIT_CLEANUP_TIMEOUT_MS,
          "stale-visit-cleanup",
        );
        await recordCleanupHeartbeat("stale-visit-cleanup", {
          abandoned: result.abandoned.deleted,
          trash: result.trash.deleted,
          accountDeletions: result.accountDeletions.deleted,
        });
        return;
      }
      if (job.name === JOB_RETENTION_SWEEP) {
        const result = await withTimeout(
          runRetentionSweep(),
          RETENTION_SWEEP_TIMEOUT_MS,
          "retention-sweep",
        );
        await recordCleanupHeartbeat("retention-sweep", {
          found: result.found,
          audioDeleted: result.audioDeleted,
          minioFailures: result.minioFailures,
        });
        return;
      }
      if (job.name === JOB_STUCK_VISIT_WATCHDOG) {
        const result = await withTimeout(
          runStuckVisitWatchdog(),
          STUCK_VISIT_WATCHDOG_TIMEOUT_MS,
          "stuck-visit-watchdog",
        );
        // Heartbeat write is intentionally conditional: with the cron
        // running every minute, an always-on heartbeat would generate
        // 1,440 Redis writes/day per worker just for a "scan was 0"
        // signal. Only record when something interesting happened so
        // the /api/health ageSeconds tracks real activity.
        if (result.rescued > 0 || result.errors > 0) {
          await recordCleanupHeartbeat("stuck-visit-watchdog", {
            scanned: result.scanned,
            rescued: result.rescued,
            errors: result.errors,
          });
        }
        return;
      }
      if (job.name === JOB_TEMPLATE_TWIN_MAINTENANCE) {
        const result = await withTimeout(
          runTemplateTwinMaintenance({
            prisma,
            // Read process.env on every run. Operations may disable future
            // work or approve a purge without rebuilding the worker image.
            env: process.env,
          }),
          TEMPLATE_TWIN_MAINTENANCE_TIMEOUT_MS,
          "template-twin-maintenance",
        );
        if (!result.enabled) return;
        log.info("ops:template-twin-maintenance", "completed", {
          auditDelivered: result.audit.delivered,
          auditFailed: result.audit.failed,
          auditContended: result.audit.contended,
          objectsRecovered: result.objects.recovered,
          objectsScheduled: result.objects.scheduled,
          objectsPurged: result.objects.purged,
          objectFailures: result.objects.failed,
          purgeApproved: result.purgeApproved,
        });
        await recordCleanupHeartbeat("template-twin-maintenance", {
          auditDelivered: result.audit.delivered,
          auditFailed: result.audit.failed,
          objectsRecovered: result.objects.recovered,
          objectsPurged: result.objects.purged,
          objectFailures: result.objects.failed,
          purgeApproved: result.purgeApproved,
        });
        return;
      }
      throw new Error(`Unknown cleanup job name: ${job.name}`);
    },
    {
      connection: getSharedRedisConnection(),
      concurrency: 1,
    },
  );

  cleanupWorker.on("failed", (job, err) => {
    console.error(
      `[ops:cleanup] job ${job?.name}/${job?.id} failed:`,
      redactPhi(err instanceof Error ? err.message : err),
    );
  });

  // ── T-M12 MinIO orphan sweep (opt-in) ─────────────────────────
  if (CLEANUP_ENABLED) {
    await getCleanupQueue().upsertJobScheduler(
      "minio-orphan-cleanup",
      { pattern: CLEANUP_CRON, tz: "UTC" },
      {
        name: JOB_MINIO_ORPHAN_CLEANUP,
        data: {},
        opts: { attempts: 1 },
      },
    );
    log.info("ops:minio-cleanup", "enabled", {
      cron: CLEANUP_CRON,
      tz: "UTC",
      retentionDays: CLEANUP_RETENTION_DAYS,
      dryRun: CLEANUP_DRY_RUN,
    });
  } else {
    log.info("ops:minio-cleanup", "disabled", {
      reason: 'MINIO_ORPHAN_CLEANUP_ENABLED != "true"',
    });
  }

  // ── T-M17.3 stale-visit sweep (default: on) ───────────────────
  if (STALE_VISIT_CLEANUP_ENABLED) {
    await getCleanupQueue().upsertJobScheduler(
      "stale-visit-cleanup",
      { pattern: STALE_VISIT_CLEANUP_CRON, tz: "UTC" },
      {
        name: JOB_STALE_VISIT_CLEANUP,
        data: {},
        opts: { attempts: 1 },
      },
    );
    log.info("ops:stale-visit-cleanup", "T-M17.3 cleanup job scheduled", {
      cron: STALE_VISIT_CLEANUP_CRON,
      tz: "UTC",
      timeoutMs: STALE_VISIT_CLEANUP_TIMEOUT_MS,
    });
  } else {
    log.info("ops:stale-visit-cleanup", "disabled", {
      reason: 'STALE_VISIT_CLEANUP_ENABLED == "false"',
    });
  }

  // ── T-M18.1 A3 audio retention sweep (default: on) ────────────
  if (RETENTION_SWEEP_ENABLED) {
    await getCleanupQueue().upsertJobScheduler(
      "retention-sweep",
      { pattern: RETENTION_SWEEP_CRON, tz: "UTC" },
      {
        name: JOB_RETENTION_SWEEP,
        data: {},
        opts: { attempts: 1 },
      },
    );
    log.info("ops:retention-sweep", "T-M18.1 retention sweep scheduled", {
      cron: RETENTION_SWEEP_CRON,
      tz: "UTC",
      timeoutMs: RETENTION_SWEEP_TIMEOUT_MS,
      // Single source of truth — same resolver the sweep uses, so the
      // logged window can't drift from the actual deletion behavior (the
      // pre-2026-06-11 duplicate hardcoded '180' here logged 180 while the
      // sweep already ran at its 90-day default).
      retentionDays: resolveRetentionDays(),
    });
  } else {
    log.info("ops:retention-sweep", "disabled", {
      reason: 'RETENTION_SWEEP_ENABLED == "false"',
    });
  }

  // ── 2026-05-12 stuck-visit watchdog (default: on) ─────────────
  if (STUCK_VISIT_WATCHDOG_ENABLED) {
    await getCleanupQueue().upsertJobScheduler(
      "stuck-visit-watchdog",
      { pattern: STUCK_VISIT_WATCHDOG_CRON, tz: "UTC" },
      {
        name: JOB_STUCK_VISIT_WATCHDOG,
        data: {},
        opts: { attempts: 1 },
      },
    );
    log.info("ops:stuck-visit-watchdog", "scheduled", {
      cron: STUCK_VISIT_WATCHDOG_CRON,
      tz: "UTC",
      timeoutMs: STUCK_VISIT_WATCHDOG_TIMEOUT_MS,
      thresholdMin: Math.round(
        Number.parseInt(
          process.env.STUCK_VISIT_THRESHOLD_MS ?? String(15 * 60 * 1000),
          10,
        ) / 60_000,
      ),
    });
  } else {
    log.info("ops:stuck-visit-watchdog", "disabled", {
      reason: 'STUCK_VISIT_WATCHDOG_ENABLED == "false"',
    });
  }

  // ── Template Twin audit + orphan-ledger maintenance (opt-in) ──
  if (TEMPLATE_TWIN_MAINTENANCE_ENABLED) {
    const config = await scheduleTemplateTwinMaintenance({
      queue: getCleanupQueue(),
      env: process.env,
    });
    log.info("ops:template-twin-maintenance", "scheduled", {
      cron: config.cron,
      tz: "UTC",
      timeoutMs: TEMPLATE_TWIN_MAINTENANCE_TIMEOUT_MS,
      purgeApproved: config.purgeApproved,
    });
  } else {
    log.info("ops:template-twin-maintenance", "disabled", {
      reason: 'TEMPLATE_TWIN_MAINTENANCE_ENABLED != "true"',
    });
  }
}

/** Round 3 PR-H — A11-P1 worker liveness heartbeat.
 *  Writes a Unix-timestamp file every 15s. The compose healthcheck reads it and
 *  treats the worker as unhealthy when the timestamp is >60s stale, so a
 *  deadlocked event loop (Prisma deadlock, infinite-loop guard, hung Anthropic
 *  stream) surfaces as an unhealthy container instead of a silently-stuck worker.
 *
 *  F6 (full-qa-20260604T202447Z) — make the heartbeat HONEST:
 *   1. START gating (in main): it is only started after worker.waitUntilReady()
 *      resolves, so a worker that fails boot (missing AUTH_SECRET → module-load
 *      crash) or can't reach Redis never writes it → healthcheck UNHEALTHY.
 *   2. Per-tick liveness: each tick SKIPS the write while the shared Redis
 *      connection isn't 'ready', so a persistent disconnect lets the file go
 *      stale (unhealthy) within the 60s window. Transient reconnects are
 *      tolerated — the 60s window absorbs ~3 missed 15s ticks, so a healthy
 *      worker (whose status is 'ready') never flaps unhealthy.
 *  Returns a handle so a graceful 'closed' can stop refreshing.
 *  (Was: a bare setInterval(...).unref() started BEFORE the Redis connection,
 *  so a crash-looping or disconnected worker still reported HEALTHY.) */
async function startHeartbeat(
  connection: ReturnType<typeof getSharedRedisConnection>,
): Promise<{ stop: () => void }> {
  const HEARTBEAT_PATH = "/tmp/worker-heartbeat";
  const HEARTBEAT_INTERVAL_MS = 15_000;
  const tick = async () => {
    // Only assert liveness while Redis is genuinely up; otherwise let the file
    // go stale rather than claim a health the disconnected worker doesn't have.
    if (connection.status !== "ready") return;
    try {
      const fs = await import("node:fs/promises");
      await fs.writeFile(HEARTBEAT_PATH, String(Date.now()));
    } catch (err) {
      console.error(
        "[transcribe-md-worker] heartbeat write failed:",
        redactPhi(err instanceof Error ? err.message : err),
      );
    }
  };
  await tick();
  const timer = setInterval(() => void tick(), HEARTBEAT_INTERVAL_MS);
  timer.unref();
  return { stop: () => clearInterval(timer) };
}

async function main() {
  const runtimeProtocol = assertQuillmdRuntimeProtocol(process.env);
  log.info("transcribe-md-worker", "booting", {
    runtimeProtocolEpoch: runtimeProtocol.epoch,
    runtimeMode: runtimeProtocol.mode,
  });
  // Flag-vs-capability assertion (#311 lesson: a flag flipped ON against a
  // stale image that lacks the capability is SILENTLY inert — no error, no
  // log). This line is the operator check: after any flag flip + recreate,
  // its presence proves the image carries the capability; its ABSENCE on a
  // flag-on deploy means a stale image. A flag-on/capability-missing
  // combination logs at error level.
  {
    const flags: { flag: string; on: boolean; capability: () => boolean }[] = [
      {
        flag: "TRANSCRIBE_MD_EVIDENCE_ANCHORS",
        on: evidenceAnchorsEnabled(),
        capability: () => ANCHOR_GENERATION_ADDENDUM.length > 0,
      },
      {
        flag: "TRANSCRIBE_MD_WHISPER_FALLBACK_ENABLED",
        on: process.env.TRANSCRIBE_MD_WHISPER_FALLBACK_ENABLED === "true",
        capability: () => true, // shipped with the kill-switch itself
      },
    ];
    for (const f of flags) {
      let present = false;
      try {
        present = f.capability();
      } catch {
        present = false;
      }
      const line = { flag: f.flag, enabled: f.on, capabilityPresent: present };
      if (f.on && !present) {
        log.error(
          "transcribe-md-worker",
          "FLAG ON BUT CAPABILITY MISSING — stale image?",
          line,
        );
      } else {
        log.info("transcribe-md-worker", "feature-flag state", line);
      }
    }
  }
  await ensureBucket();
  log.info("transcribe-md-worker", "bucket ready");

  const worker = new Worker<ProcessVisitPayload>(
    QUEUE_NAME,
    async (job) => {
      if (job.name !== JOB_PROCESS_VISIT) {
        throw new Error(`Unknown job name: ${job.name}`);
      }
      if (job.data.syntheticQaRunId) {
        // Promise.race timeouts do not cancel their underlying work. Synthetic
        // attempts use a DB-exclusive, heartbeating delivery lease instead.
        // BullMQ may redeliver a stalled job only after that lease expires;
        // every output/READY claim also matches the replacement claim id.
        await processVisit(job, randomUUID(), (job.attemptsMade ?? 0) + 1);
      } else {
        await withTimeout(
          processVisit(job),
          JOB_TIMEOUT_MS,
          `visit ${job.data.visitId}`,
        );
      }
    },
    {
      connection: getSharedRedisConnection(),
      concurrency: CONCURRENCY,
      // BullMQ declares a dead delivery stalled only after the 20s database
      // lease has expired. One same-job redelivery can then reclaim the exact
      // attempt; a second hard crash reaches failed-event reconciliation.
      lockDuration: 30_000,
      stalledInterval: 30_000,
      maxStalledCount: 1,
    },
  );

  worker.on("completed", (job) => {
    log.info("transcribe-md-worker", "visit completed", {
      jobId: job.id,
      visitId: job.data.visitId,
    });
  });
  worker.on("failed", (job, err) => {
    const syntheticQaFailureCode = job?.data.syntheticQaRunId
      ? templateTwinSyntheticQaWorkerFailureCode(err)
      : null;
    if (syntheticQaFailureCode) {
      log.warn("transcribe-md-worker", "synthetic QA worker job failed", {
        code: syntheticQaFailureCode,
        jobId: job?.id ?? null,
        visitId: job?.data.visitId ?? null,
        syntheticQaRunId: job?.data.syntheticQaRunId ?? null,
        syntheticQaAttempt: job?.data.syntheticQaAttempt ?? null,
      });
      if (
        templateTwinRuntimeEnabled(process.env) &&
        job?.data.syntheticQaRunId &&
        job.data.syntheticQaAttempt !== undefined
      ) {
        void reconcileExpiredTemplateTwinSyntheticQaWorkerClaim({
          runId: job.data.syntheticQaRunId,
          visitId: job.data.visitId,
          userId: job.data.userId,
          attempt: job.data.syntheticQaAttempt,
        }).catch((reconcileError: unknown) => {
          log.warn(
            "transcribe-md-worker",
            "synthetic QA worker crash reconciliation deferred",
            {
              code: templateTwinSyntheticQaWorkerFailureCode(reconcileError),
              jobId: job.id ?? null,
              visitId: job.data.visitId,
              syntheticQaRunId: job.data.syntheticQaRunId,
              syntheticQaAttempt: job.data.syntheticQaAttempt,
            },
          );
        });
      }
    } else {
      console.error(
        `[transcribe-md-worker] job ${job?.id} visit ${job?.data.visitId} FAILED:`,
        redactPhi(err instanceof Error ? err.message : err),
      );
    }
    // PR-L: when the retry budget is exhausted, ship the job to the
    // DLQ so an operator can see + decide via /admin/queues. The
    // `failed` event fires AFTER each failed attempt — only enqueue
    // when the FINAL attempt failed (attemptsMade equals the
    // configured ceiling). Best-effort: if Redis is unhappy we log +
    // drop rather than crash the worker (the next failure will retry
    // the DLQ enqueue too).
    if (
      job &&
      typeof job.attemptsMade === "number" &&
      typeof job.opts?.attempts === "number" &&
      job.attemptsMade >= job.opts.attempts
    ) {
      void enqueueDlq({
        originalQueue: QUEUE_NAME,
        originalJobId: job.id ?? null,
        originalJobName: job.name,
        originalPayload: job.data,
        // Audit P0-A (2026-05-13): the DLQ row is DURABLE storage
        // reviewed via /admin/queues. Prisma errors + Anthropic 400
        // bodies frequently quote prompt fragments (transcript +
        // SOAP draft), so an unscrubbed err.message leaks PHI into
        // an admin-visible table indefinitely. redactPhi keeps the
        // operational signal (column name, error class, generic
        // shape) and drops the verbatim content.
        lastError:
          syntheticQaFailureCode ??
          redactPhi(
            err instanceof Error
              ? err.message
              : String(err ?? "(no error message)"),
          ),
        exhaustedAt: new Date().toISOString(),
        totalAttempts: job.opts.attempts,
      }).catch((dlqErr) => {
        console.error(
          `[transcribe-md-worker] DLQ enqueue failed for job ${job.id}:`,
          redactPhi(dlqErr instanceof Error ? dlqErr.message : dlqErr),
        );
      });
    }
  });

  // F6 (full-qa-20260604T202447Z) — honest heartbeat. Do NOT write the liveness
  // heartbeat until the worker is GENUINELY ready: waitUntilReady() resolves
  // only once both the main + blocking Redis connections are up (the worker can
  // fetch + process jobs). A worker that fails boot (missing AUTH_SECRET →
  // module-load crash) or can't reach Redis never reaches here → never writes
  // the heartbeat → the file-freshness healthcheck correctly reports UNHEALTHY.
  // (Was: startHeartbeat ran before the Worker connected, so a boot/Redis
  // failure still looked healthy.)
  await worker.waitUntilReady();
  log.info("transcribe-md-worker", "ready — listening on queue", {
    queue: QUEUE_NAME,
    concurrency: CONCURRENCY,
  });
  const heartbeat = await startHeartbeat(getSharedRedisConnection());
  const stagingQaLeaseReconciler =
    startTemplateTwinSyntheticQaExpiredLeaseReconciler({
      // rollback-compat-v2 keeps ordinary maintenance/outbox reconciliation
      // online, but must not mutate the synthetic Template Twin QA lifecycle.
      enabled:
        templateTwinRuntimeEnabled(process.env) &&
        evaluateTemplateTwinStagingQaGate(process.env).allowed,
      onError: () => {
        log.warn(
          "transcribe-md-worker",
          "synthetic QA expired-lease reconciliation deferred",
          { code: "TEMPLATE_TWIN_SYNTHETIC_QA_LEASE_SCAN_DEFERRED" },
        );
      },
      onResult: (result) => {
        if (result.failed === 0) return;
        log.warn(
          "transcribe-md-worker",
          "synthetic QA expired-lease reconciliation incomplete",
          {
            code: "TEMPLATE_TWIN_SYNTHETIC_QA_LEASE_SCAN_PARTIAL",
            scanned: result.scanned,
            reconciled: result.reconciled,
            failed: result.failed,
          },
        );
      },
    });
  // Graceful shutdown stops the heartbeat so the file goes stale (unhealthy)
  // within the 60s window. A crash kills the process (→ stale too); a persistent
  // Redis disconnect is handled inside the tick (skips the write while down).
  worker.on("closed", () => {
    heartbeat.stop();
    stagingQaLeaseReconciler.stop();
  });

  // T-M12 — schedule cleanup AFTER the main worker is up. Cleanup
  // failure should never block pipeline processing.
  await startCleanupWorker();
}

main().catch((err) => {
  console.error(
    "[transcribe-md-worker] fatal:",
    redactPhi(err instanceof Error ? err.message : err),
  );
  process.exit(1);
});
