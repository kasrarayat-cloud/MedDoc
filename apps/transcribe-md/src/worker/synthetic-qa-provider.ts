import {
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
  TEMPLATE_TWIN_SYNTHETIC_QA_MODE,
  TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
  assertTemplateTwinSyntheticQaWorkerLeaseHealthy,
  assertTemplateTwinSyntheticQaProviderEnvironment,
  getTemplateTwinSyntheticQaProviderContext,
  markTemplateTwinSyntheticQaWorkerLeaseUnhealthy,
  runWithLegacyTemplateTwinInfrastructureFixture,
  type SyntheticQaProviderEnvironment,
} from "@meddoc/ai";
import { runWithTemplateTwinSyntheticQaProviderContext } from "@meddoc/ai/internal/synthetic-qa-context";

import {
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
  TEMPLATE_TWIN_STAGING_QA_WAV_SHA256,
  TEMPLATE_TWIN_STAGING_QA_WAV_SIZE_BYTES,
  templateTwinStagingQaSha256,
} from "../lib/template-twin/staging-qa-fixtures";
import prisma from "@meddoc/db";
import { Prisma, TranscribeVisitStatus } from "@prisma/client";

import { enqueueTemplateTwinAudit } from "@/lib/template-twin/audit-outbox";
import { lockCurrentTemplateTwinVisit } from "@/lib/template-twin/fill-engine";
import {
  lockTemplateTwinRolloutForFinalClaim,
  pinTemplateTwinRollout,
  type TemplateTwinRolloutToken,
} from "@/lib/template-twin/rollout";
import {
  lockAndAssertTemplateTwinStagingQaAttempt,
  lockAndAssertTemplateTwinStagingQaOperation,
  lockTemplateTwinStagingQaAdmissionThenRun,
} from "@/lib/template-twin/staging-qa-visit-guard";
import { isTemplateTwinStagingQaRequested } from "@/lib/template-twin/staging-qa-gate";
import { templateTwinStagingQaPayloadSha256 } from "@/lib/template-twin/staging-qa-digest";
import { downloadAudio } from "@/lib/minio";
import { runSerializableTransactionWithRetry } from "@/lib/db/transaction-retry";
import { markVisitAutomationManifestFailed } from "@/worker/automation-manifest";

export type TemplateTwinSyntheticQaWorkerAdmissionCode =
  | "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID"
  | "TEMPLATE_TWIN_SYNTHETIC_QA_TENANT_MISMATCH"
  | "TEMPLATE_TWIN_SYNTHETIC_QA_NOT_ENQUEUED"
  | "TEMPLATE_TWIN_SYNTHETIC_QA_MODE_MISMATCH"
  | "TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_UNSUPPORTED"
  | "TEMPLATE_TWIN_SYNTHETIC_QA_ROLLOUT_GENERATION_STALE"
  | "TEMPLATE_TWIN_SYNTHETIC_QA_FINAL_CLAIM_REJECTED";

export class TemplateTwinSyntheticQaWorkerAdmissionError extends Error {
  constructor(
    readonly code: TemplateTwinSyntheticQaWorkerAdmissionCode,
    message: string,
  ) {
    super(message);
    this.name = "TemplateTwinSyntheticQaWorkerAdmissionError";
  }
}

export const TEMPLATE_TWIN_SYNTHETIC_QA_JOB_FAILURE_CODE =
  "TEMPLATE_TWIN_SYNTHETIC_QA_JOB_FAILED" as const;
export const TEMPLATE_TWIN_SYNTHETIC_QA_WORKER_LEASE_MS = 20_000;
export const TEMPLATE_TWIN_SYNTHETIC_QA_WORKER_HEARTBEAT_MS = 5_000;
export const TEMPLATE_TWIN_SYNTHETIC_QA_MAX_WORKER_DELIVERIES = 3;

/**
 * Closed-set code for global worker failure telemetry. Provider, validation,
 * and document errors may contain synthetic encounter/document text in their
 * message, so the BullMQ failure handler must never log or persist that
 * message for a staging job.
 */
export function templateTwinSyntheticQaWorkerFailureCode(
  error: unknown,
):
  | TemplateTwinSyntheticQaWorkerAdmissionCode
  | typeof TEMPLATE_TWIN_SYNTHETIC_QA_JOB_FAILURE_CODE {
  return error instanceof TemplateTwinSyntheticQaWorkerAdmissionError
    ? error.code
    : TEMPLATE_TWIN_SYNTHETIC_QA_JOB_FAILURE_CODE;
}

export interface TemplateTwinSyntheticQaRunSnapshot {
  readonly id: string;
  readonly admissionId: string | null;
  readonly visitId: string;
  readonly practiceId: string;
  readonly doctorId: string;
  readonly noteTemplateId: string;
  readonly noteTemplateVersion: number;
  readonly requestSha256: string;
  readonly payloadSha256: string;
  readonly mode: string;
  readonly fixtureVersion: string;
  readonly pinnedGlobalRolloutGeneration: bigint;
  readonly pinnedPracticeRolloutGeneration: bigint;
  readonly status: string;
  readonly attempt: number;
  readonly enqueuedAt: Date | null;
  readonly workerClaimId: string | null;
  readonly workerClaimedAt: Date | null;
  readonly workerHeartbeatAt: Date | null;
  readonly workerLeaseExpiresAt: Date | null;
  readonly workerDeliveryCount: number;
  readonly workerRetryReadyAt: Date | null;
  readonly admission: {
    readonly id: string;
    readonly practiceId: string;
    readonly actorId: string;
    readonly parentAdmissionId: string | null;
    readonly sourceSha256: string;
    readonly sourceSizeBytes: number;
    readonly providerMode: string;
    readonly purpose: string;
    readonly phase: string;
    readonly requestSha256: string;
    readonly payloadSha256: string | null;
    readonly noteTemplateId: string | null;
    readonly noteTemplateVersion: number | null;
    readonly certificationId: string | null;
    readonly visitId: string | null;
    readonly attempt: number;
    readonly expiresAt: Date;
    readonly failedAt: Date | null;
    readonly revokedAt: Date | null;
    readonly pinnedGlobalRolloutGeneration: bigint;
    readonly pinnedPracticeRolloutGeneration: bigint;
  } | null;
}

export interface TemplateTwinSyntheticQaVisitSnapshot {
  readonly id: string;
  readonly userId: string;
  readonly practiceId: string;
  readonly inputMode: string;
  readonly noteTemplateId: string | null;
  readonly noteTemplateVersion: number | null;
  readonly rawTextInput: string | null;
  readonly dictationAudioKey: string | null;
  readonly audioMimeType: string | null;
  readonly audioSizeBytes: number | null;
  readonly templateAdmission: {
    readonly status: string;
    readonly templateKind: string;
    readonly certificationStatus: string | null;
    readonly hasCertification: boolean;
    readonly sourceValidationStatus: string | null;
    readonly sourceArtifactSha256: string | null;
    readonly sourceArtifactSizeBytes: number | null;
  } | null;
  readonly syntheticQaRun: TemplateTwinSyntheticQaRunSnapshot | null;
}

export interface TemplateTwinSyntheticQaJobAdmission {
  readonly userId: string;
  readonly syntheticQaRunId?: string;
  readonly syntheticQaAttempt?: number;
  readonly workerClaimId?: string;
  readonly workerDeliveryNumber?: number;
}

interface SyntheticQaWorkerProviderDependencies {
  readonly pinRollout: (input: {
    practiceId: string;
  }) => Promise<TemplateTwinRolloutToken>;
  readonly claimAttempt: (input: {
    visit: TemplateTwinSyntheticQaVisitSnapshot;
    run: TemplateTwinSyntheticQaRunSnapshot;
    currentToken: TemplateTwinRolloutToken;
    workerClaimId: string;
    workerDeliveryNumber: number;
  }) => Promise<void>;
  readonly verifyEvidence: (input: {
    visit: TemplateTwinSyntheticQaVisitSnapshot;
    run: TemplateTwinSyntheticQaRunSnapshot;
  }) => Promise<void>;
  readonly env: SyntheticQaProviderEnvironment;
}

export async function verifyTemplateTwinSyntheticQaWorkerEvidence(input: {
  visit: TemplateTwinSyntheticQaVisitSnapshot;
  run: TemplateTwinSyntheticQaRunSnapshot;
}): Promise<void> {
  const evidenceText =
    input.run.mode === "typed"
      ? (input.visit.rawTextInput ?? "")
      : TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT;
  const payloadSha256 = templateTwinStagingQaPayloadSha256({
    templateId: input.run.noteTemplateId,
    expectedTemplateVersion: input.run.noteTemplateVersion,
    mode: input.run.mode as "typed" | "mock_voice",
    fixtureVersion: input.run.fixtureVersion,
    evidenceText,
  });
  if (payloadSha256 !== input.run.payloadSha256) {
    fail(
      "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID",
      "Synthetic QA evidence no longer matches its immutable admission digest.",
    );
  }
  if (input.run.mode === "typed") {
    if (
      input.visit.dictationAudioKey !== null ||
      input.visit.audioMimeType !== null ||
      input.visit.audioSizeBytes !== null
    ) {
      fail(
        "TEMPLATE_TWIN_SYNTHETIC_QA_MODE_MISMATCH",
        "Typed synthetic QA admission contains unexpected audio metadata.",
      );
    }
    return;
  }
  const expectedKey = `${input.visit.userId}/${input.visit.id}/template-twin-synthetic-qa.wav`;
  if (
    input.visit.dictationAudioKey !== expectedKey ||
    input.visit.audioMimeType !== "audio/wav" ||
    input.visit.audioSizeBytes !== TEMPLATE_TWIN_STAGING_QA_WAV_SIZE_BYTES
  ) {
    fail(
      "TEMPLATE_TWIN_SYNTHETIC_QA_MODE_MISMATCH",
      "Mock-voice synthetic QA audio metadata is not the reviewed fixture.",
    );
  }
  const audio = await downloadAudio(expectedKey);
  if (
    audio.byteLength !== TEMPLATE_TWIN_STAGING_QA_WAV_SIZE_BYTES ||
    templateTwinStagingQaSha256(audio) !== TEMPLATE_TWIN_STAGING_QA_WAV_SHA256
  ) {
    fail(
      "TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_UNSUPPORTED",
      "Mock-voice synthetic QA audio bytes are missing or changed.",
    );
  }
}

function fail(
  code: TemplateTwinSyntheticQaWorkerAdmissionCode,
  message: string,
): never {
  throw new TemplateTwinSyntheticQaWorkerAdmissionError(code, message);
}

function assertRunMatchesVisit(
  visit: TemplateTwinSyntheticQaVisitSnapshot,
  run: TemplateTwinSyntheticQaRunSnapshot,
): void {
  if (
    !run.admissionId ||
    run.visitId !== visit.id ||
    run.practiceId !== visit.practiceId ||
    run.doctorId !== visit.userId ||
    run.noteTemplateId !== visit.noteTemplateId ||
    run.noteTemplateVersion !== visit.noteTemplateVersion
  ) {
    fail(
      "TEMPLATE_TWIN_SYNTHETIC_QA_TENANT_MISMATCH",
      "Synthetic QA run does not match the visit owner and immutable template version.",
    );
  }
  const admission = run.admission;
  const expectedProviderMode =
    run.mode === "typed" ? "SYNTHETIC_TYPED" : "SYNTHETIC_MOCK_VOICE";
  const expectedAdmissionPhase =
    run.status === "PROCESSING" || run.status === "RETRY_ENQUEUED"
      ? "PROCESSING"
      : "VISIT_LINKED";
  if (
    !admission ||
    admission.id !== run.admissionId ||
    admission.practiceId !== run.practiceId ||
    admission.actorId !== run.doctorId ||
    !admission.parentAdmissionId ||
    admission.sourceSha256 !== TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256 ||
    admission.sourceSizeBytes !== TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES ||
    admission.providerMode !== expectedProviderMode ||
    admission.purpose !== "VISIT" ||
    admission.phase !== expectedAdmissionPhase ||
    admission.requestSha256 !== run.requestSha256 ||
    admission.payloadSha256 !== run.payloadSha256 ||
    admission.noteTemplateId !== run.noteTemplateId ||
    admission.noteTemplateVersion !== run.noteTemplateVersion ||
    !admission.certificationId ||
    admission.visitId !== run.visitId ||
    admission.attempt !== run.attempt ||
    admission.failedAt !== null ||
    admission.revokedAt !== null ||
    admission.expiresAt <= new Date() ||
    admission.pinnedGlobalRolloutGeneration !==
      run.pinnedGlobalRolloutGeneration ||
    admission.pinnedPracticeRolloutGeneration !==
      run.pinnedPracticeRolloutGeneration
  ) {
    fail(
      "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID",
      "Synthetic QA worker run lacks its current durable provider admission.",
    );
  }
  if (
    !run.id.trim() ||
    !/^[a-f0-9]{64}$/u.test(run.requestSha256) ||
    !/^[a-f0-9]{64}$/u.test(run.payloadSha256) ||
    run.pinnedGlobalRolloutGeneration < BigInt(1) ||
    run.pinnedPracticeRolloutGeneration < BigInt(1)
  ) {
    fail(
      "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID",
      "Synthetic QA run metadata is invalid.",
    );
  }
  const hasValidWorkerLease =
    run.workerClaimId !== null &&
    run.workerClaimedAt !== null &&
    run.workerHeartbeatAt !== null &&
    run.workerLeaseExpiresAt !== null &&
    run.workerLeaseExpiresAt > run.workerHeartbeatAt &&
    run.workerHeartbeatAt >= run.workerClaimedAt;
  const hasNoWorkerLease =
    run.workerClaimId === null &&
    run.workerClaimedAt === null &&
    run.workerHeartbeatAt === null &&
    run.workerLeaseExpiresAt === null;
  if (
    !["ENQUEUED", "RETRY_ENQUEUED", "PROCESSING"].includes(run.status) ||
    (run.status === "ENQUEUED" &&
      (!hasNoWorkerLease ||
        run.workerDeliveryCount !== 0 ||
        run.workerRetryReadyAt !== null)) ||
    (run.status === "RETRY_ENQUEUED" &&
      (!hasNoWorkerLease ||
        run.workerDeliveryCount < 1 ||
        run.workerDeliveryCount >=
          TEMPLATE_TWIN_SYNTHETIC_QA_MAX_WORKER_DELIVERIES ||
        run.workerRetryReadyAt === null)) ||
    (run.status === "PROCESSING" &&
      (!hasValidWorkerLease ||
        run.workerDeliveryCount < 1 ||
        run.workerDeliveryCount >
          TEMPLATE_TWIN_SYNTHETIC_QA_MAX_WORKER_DELIVERIES ||
        run.workerRetryReadyAt !== null)) ||
    run.enqueuedAt === null ||
    !Number.isSafeInteger(run.attempt) ||
    run.attempt < 1
  ) {
    fail(
      "TEMPLATE_TWIN_SYNTHETIC_QA_NOT_ENQUEUED",
      "Synthetic QA run is not durably enqueued.",
    );
  }
  if (run.fixtureVersion !== TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION) {
    fail(
      "TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_UNSUPPORTED",
      "Synthetic QA fixture version is not supported by this worker.",
    );
  }

  const template = visit.templateAdmission;
  if (
    template?.status !== "active" ||
    template.templateKind !== "template_twin_docx" ||
    template.certificationStatus !== "CERTIFIED" ||
    !template.hasCertification ||
    template.sourceValidationStatus !== "accepted" ||
    template.sourceArtifactSha256 !== TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256 ||
    template.sourceArtifactSizeBytes !==
      TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES
  ) {
    fail(
      "TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_UNSUPPORTED",
      "Synthetic QA requires the exact reviewed, physician-certified fixture artifact.",
    );
  }

  const modeMatches =
    (run.mode === "typed" && visit.inputMode === "text_notes") ||
    (run.mode === "mock_voice" && visit.inputMode === "voice_dictation");
  if (!modeMatches) {
    fail(
      "TEMPLATE_TWIN_SYNTHETIC_QA_MODE_MISMATCH",
      "Synthetic QA mode does not match the immutable visit input mode.",
    );
  }
}

function isStagingFixtureTemplate(
  template: TemplateTwinSyntheticQaVisitSnapshot["templateAdmission"],
): boolean {
  return Boolean(
    template &&
    template.templateKind === "template_twin_docx" &&
    template.sourceArtifactSha256 === TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256 &&
    template.sourceArtifactSizeBytes ===
      TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
  );
}

function isCertifiedTemplateTwin(
  template: TemplateTwinSyntheticQaVisitSnapshot["templateAdmission"],
): boolean {
  return Boolean(
    template &&
    template.status === "active" &&
    template.templateKind === "template_twin_docx" &&
    template.certificationStatus === "CERTIFIED" &&
    template.hasCertification &&
    template.sourceValidationStatus === "accepted" &&
    template.sourceArtifactSha256 &&
    template.sourceArtifactSizeBytes &&
    template.sourceArtifactSizeBytes > 0,
  );
}

function assertPinnedGeneration(
  run: TemplateTwinSyntheticQaRunSnapshot,
  current: TemplateTwinRolloutToken,
): void {
  if (
    current.practiceId !== run.practiceId ||
    current.globalGeneration !== run.pinnedGlobalRolloutGeneration ||
    current.practiceGeneration !== run.pinnedPracticeRolloutGeneration
  ) {
    fail(
      "TEMPLATE_TWIN_SYNTHETIC_QA_ROLLOUT_GENERATION_STALE",
      "Template Twin availability changed after this synthetic QA run was admitted. Start a new run.",
    );
  }
}

/**
 * Linearization point for a synthetic worker attempt. Rollout controls are
 * locked first, followed by the run, actor, and visit. Only one BullMQ
 * delivery can move an exact attempt from ENQUEUED to PROCESSING; duplicate
 * or stalled deliveries fail before provider, renderer, or object writes.
 */
export async function claimTemplateTwinSyntheticQaWorkerAttempt(input: {
  visit: TemplateTwinSyntheticQaVisitSnapshot;
  run: TemplateTwinSyntheticQaRunSnapshot;
  currentToken: TemplateTwinRolloutToken;
  workerClaimId: string;
  workerDeliveryNumber: number;
}): Promise<void> {
  if (
    !/^[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/u.test(
      input.workerClaimId,
    )
  ) {
    fail(
      "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID",
      "Synthetic QA worker claim identifier is invalid.",
    );
  }
  if (
    !Number.isSafeInteger(input.workerDeliveryNumber) ||
    input.workerDeliveryNumber < 1 ||
    input.workerDeliveryNumber >
      TEMPLATE_TWIN_SYNTHETIC_QA_MAX_WORKER_DELIVERIES
  ) {
    fail(
      "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID",
      "Synthetic QA worker delivery number is invalid.",
    );
  }
  await runSerializableTransactionWithRetry({
    prisma,
    operation: "claim_template_twin_synthetic_qa_worker_attempt",
    context: {
      visitId: input.visit.id,
      practiceId: input.visit.practiceId,
      runId: input.run.id,
    },
    transaction: async (tx: Prisma.TransactionClient) => {
      const rollout = await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.visit.practiceId,
        pinnedToken: input.currentToken,
      });
      if (!rollout.allowed) {
        fail(
          "TEMPLATE_TWIN_SYNTHETIC_QA_ROLLOUT_GENERATION_STALE",
          rollout.reason,
        );
      }
      const lockedRun = await lockAndAssertTemplateTwinStagingQaOperation({
        tx,
        currentRolloutToken: rollout.token,
        runId: input.run.id,
        expectedAttempt: input.run.attempt,
        actor: {
          userId: input.visit.userId,
          practiceId: input.visit.practiceId,
        },
        allowedStatuses: ["ENQUEUED", "RETRY_ENQUEUED", "PROCESSING"],
      });
      const visit = await lockCurrentTemplateTwinVisit(tx, input.visit.id);
      if (
        !visit ||
        visit.userId !== input.visit.userId ||
        (lockedRun.status === "ENQUEUED" &&
          visit.status !== TranscribeVisitStatus.QUEUED) ||
        (lockedRun.status === "RETRY_ENQUEUED" &&
          (visit.status === TranscribeVisitStatus.READY ||
            visit.status === TranscribeVisitStatus.SIGNED ||
            visit.status === TranscribeVisitStatus.FAILED)) ||
        (lockedRun.status === "PROCESSING" &&
          (visit.status === TranscribeVisitStatus.READY ||
            visit.status === TranscribeVisitStatus.SIGNED ||
            visit.status === TranscribeVisitStatus.FAILED)) ||
        visit.deletedAt !== null ||
        visit.archivedAt !== null
      ) {
        fail(
          "TEMPLATE_TWIN_SYNTHETIC_QA_NOT_ENQUEUED",
          "Synthetic QA visit is not available for this worker attempt.",
        );
      }
      const claimed = await tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
        UPDATE "template_twin_synthetic_qa_runs"
        SET "status" = 'PROCESSING',
            "workerClaimId" = ${input.workerClaimId},
            "workerClaimedAt" = clock_timestamp(),
            "workerHeartbeatAt" = clock_timestamp(),
            "workerLeaseExpiresAt" = clock_timestamp()
              + ${TEMPLATE_TWIN_SYNTHETIC_QA_WORKER_LEASE_MS} * INTERVAL '1 millisecond',
            "workerDeliveryCount" = "workerDeliveryCount" + 1,
            "workerRetryReadyAt" = NULL,
            "updatedAt" = clock_timestamp()
        WHERE "id" = ${input.run.id}
          AND "visitId" = ${input.visit.id}
          AND "doctorId" = ${input.visit.userId}
          AND "practiceId" = ${input.visit.practiceId}
          AND "attempt" = ${input.run.attempt}
          AND (
            ("status" = 'ENQUEUED'
              AND "workerClaimId" IS NULL
              AND "workerDeliveryCount" = 0
              AND ${input.workerDeliveryNumber} = 1)
            OR
            ("status" = 'RETRY_ENQUEUED'
              AND "workerClaimId" IS NULL
              AND "workerRetryReadyAt" IS NOT NULL
              AND "workerDeliveryCount" + 1 = ${input.workerDeliveryNumber})
            OR
            ("status" = 'PROCESSING'
              AND "workerLeaseExpiresAt" <= clock_timestamp()
              AND "workerDeliveryCount" + 1 = ${input.workerDeliveryNumber})
          )
        RETURNING "id"
      `);
      if (claimed.length !== 1) {
        fail(
          "TEMPLATE_TWIN_SYNTHETIC_QA_NOT_ENQUEUED",
          "Synthetic QA worker attempt was already claimed or replaced.",
        );
      }
      if (lockedRun.status === "ENQUEUED") {
        const advancedAdmission =
          await tx.templateTwinSyntheticQaAdmission.updateMany({
            where: {
              id: input.run.admissionId!,
              practiceId: input.visit.practiceId,
              actorId: input.visit.userId,
              visitId: input.visit.id,
              attempt: input.run.attempt,
              phase: "VISIT_LINKED",
            },
            data: { phase: "PROCESSING" },
          });
        if (advancedAdmission.count !== 1) {
          fail(
            "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID",
            "Synthetic QA durable admission could not enter processing.",
          );
        }
      }
      if (lockedRun.status === "PROCESSING") {
        await enqueueTemplateTwinAudit(tx, {
          eventKey: `template-twin:staging-worker-reclaimed:${input.run.id}:${input.run.attempt}:${input.workerClaimId}`,
          practiceId: input.visit.practiceId,
          actorId: input.visit.userId,
          action: "TEMPLATE_TWIN_STAGING_QA_RUN_RETRIED",
          targetType: "TemplateTwinSyntheticQaRun",
          targetId: input.run.id,
          metadata: {
            operation: "stalled_worker_lease_reclaim",
            stagingQaAttempt: input.run.attempt,
            workerDeliveryNumber: input.workerDeliveryNumber,
          },
        });
      } else if (lockedRun.status === "RETRY_ENQUEUED") {
        await enqueueTemplateTwinAudit(tx, {
          eventKey: `template-twin:staging-worker-delivery-retried:${input.run.id}:${input.run.attempt}:${input.workerDeliveryNumber}`,
          practiceId: input.visit.practiceId,
          actorId: input.visit.userId,
          action: "TEMPLATE_TWIN_STAGING_QA_RUN_RETRIED",
          targetType: "TemplateTwinSyntheticQaRun",
          targetId: input.run.id,
          metadata: {
            operation: "bounded_worker_delivery_retry",
            stagingQaAttempt: input.run.attempt,
            workerDeliveryNumber: input.workerDeliveryNumber,
          },
        });
      }
    },
  });
}

/**
 * Relinquish one failed BullMQ delivery without retiring its immutable
 * clinical attempt. This is the only PROCESSING -> RETRY_ENQUEUED transition.
 * It consumes the current claim under the canonical lock order and leaves the
 * admission in PROCESSING, so the next bounded delivery must acquire a fresh
 * claim before it can reuse a committed provider result.
 */
export async function prepareTemplateTwinSyntheticQaDeliveryRetry(input: {
  visitId: string;
  userId: string;
  practiceId: string;
  nextWorkerDeliveryNumber: number;
}): Promise<boolean> {
  const context = getTemplateTwinSyntheticQaProviderContext();
  if (!context) return false;
  if (
    context.visitId !== input.visitId ||
    context.practiceId !== input.practiceId ||
    !Number.isSafeInteger(input.nextWorkerDeliveryNumber) ||
    input.nextWorkerDeliveryNumber < 2 ||
    input.nextWorkerDeliveryNumber >
      TEMPLATE_TWIN_SYNTHETIC_QA_MAX_WORKER_DELIVERIES
  ) {
    fail(
      "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID",
      "Synthetic QA retry delivery does not match its durable admission.",
    );
  }
  await runSerializableTransactionWithRetry({
    prisma,
    operation: "prepare_template_twin_synthetic_qa_delivery_retry",
    context: {
      visitId: input.visitId,
      practiceId: input.practiceId,
      runId: context.runId,
    },
    transaction: async (tx: Prisma.TransactionClient) => {
      const rollout = await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.practiceId,
        pinnedToken: {
          practiceId: input.practiceId,
          globalGeneration: context.pinnedGlobalGeneration,
          practiceGeneration: context.pinnedPracticeGeneration,
        },
      });
      if (!rollout.allowed) {
        fail(
          "TEMPLATE_TWIN_SYNTHETIC_QA_ROLLOUT_GENERATION_STALE",
          rollout.reason,
        );
      }
      await lockAndAssertTemplateTwinStagingQaAttempt({
        tx,
        currentRolloutToken: rollout.token,
        claim: {
          runId: context.runId,
          visitId: context.visitId,
          practiceId: context.practiceId,
          doctorId: input.userId,
          fixtureVersion: context.fixtureVersion,
          requestSha256: context.requestSha256,
          attempt: context.attempt,
          workerClaimId: context.workerClaimId,
          pinnedGlobalGeneration: context.pinnedGlobalGeneration,
          pinnedPracticeGeneration: context.pinnedPracticeGeneration,
        },
        allowedStatuses: ["PROCESSING"],
        allowedAdmissionPhases: ["PROCESSING"],
        requireLiveWorkerLease: true,
      });
      const visit = await lockCurrentTemplateTwinVisit(tx, input.visitId);
      if (
        !visit ||
        visit.userId !== input.userId ||
        visit.status === TranscribeVisitStatus.READY ||
        visit.status === TranscribeVisitStatus.SIGNED ||
        visit.status === TranscribeVisitStatus.FAILED
      ) {
        fail(
          "TEMPLATE_TWIN_SYNTHETIC_QA_FINAL_CLAIM_REJECTED",
          "Synthetic QA retry found an incompatible visit state.",
        );
      }
      const retryReadyAt = new Date();
      const released = await tx.templateTwinSyntheticQaRun.updateMany({
        where: {
          id: context.runId,
          visitId: context.visitId,
          doctorId: input.userId,
          practiceId: input.practiceId,
          attempt: context.attempt,
          status: "PROCESSING",
          workerClaimId: context.workerClaimId,
          workerDeliveryCount: input.nextWorkerDeliveryNumber - 1,
          workerRetryReadyAt: null,
        },
        data: {
          status: "RETRY_ENQUEUED",
          workerClaimId: null,
          workerClaimedAt: null,
          workerHeartbeatAt: null,
          workerLeaseExpiresAt: null,
          workerRetryReadyAt: retryReadyAt,
        },
      });
      if (released.count !== 1) {
        fail(
          "TEMPLATE_TWIN_SYNTHETIC_QA_FINAL_CLAIM_REJECTED",
          "Synthetic QA delivery was replaced before retry handoff.",
        );
      }
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:staging-worker-delivery-retry-ready:${context.runId}:${context.attempt}:${input.nextWorkerDeliveryNumber}`,
        practiceId: input.practiceId,
        actorId: input.userId,
        action: "TEMPLATE_TWIN_STAGING_QA_RUN_RETRIED",
        targetType: "TemplateTwinSyntheticQaRun",
        targetId: context.runId,
        metadata: {
          operation: "bounded_worker_delivery_retry_ready",
          stagingQaAttempt: context.attempt,
          nextWorkerDeliveryNumber: input.nextWorkerDeliveryNumber,
        },
      });
    },
  });
  return true;
}

/** Extend only the currently-owned attempt lease under the normal lock order. */
export async function renewTemplateTwinSyntheticQaWorkerLease(input: {
  visitId: string;
  userId: string;
  practiceId: string;
  runId: string;
  requestSha256: string;
  fixtureVersion: string;
  attempt: number;
  workerClaimId: string;
  pinnedGlobalGeneration: bigint;
  pinnedPracticeGeneration: bigint;
}): Promise<void> {
  await runSerializableTransactionWithRetry({
    prisma,
    operation: "renew_template_twin_synthetic_qa_worker_lease",
    context: {
      visitId: input.visitId,
      practiceId: input.practiceId,
      runId: input.runId,
    },
    transaction: async (tx: Prisma.TransactionClient) => {
      const rollout = await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.practiceId,
        pinnedToken: {
          practiceId: input.practiceId,
          globalGeneration: input.pinnedGlobalGeneration,
          practiceGeneration: input.pinnedPracticeGeneration,
        },
      });
      if (!rollout.allowed) {
        fail(
          "TEMPLATE_TWIN_SYNTHETIC_QA_ROLLOUT_GENERATION_STALE",
          rollout.reason,
        );
      }
      await lockAndAssertTemplateTwinStagingQaAttempt({
        tx,
        currentRolloutToken: rollout.token,
        claim: {
          runId: input.runId,
          visitId: input.visitId,
          practiceId: input.practiceId,
          doctorId: input.userId,
          fixtureVersion: input.fixtureVersion,
          requestSha256: input.requestSha256,
          attempt: input.attempt,
          workerClaimId: input.workerClaimId,
          pinnedGlobalGeneration: input.pinnedGlobalGeneration,
          pinnedPracticeGeneration: input.pinnedPracticeGeneration,
        },
        allowedStatuses: ["PROCESSING"],
        allowedAdmissionPhases: ["PROCESSING"],
        requireLiveWorkerLease: true,
      });
      const renewed = await tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
        UPDATE "template_twin_synthetic_qa_runs"
        SET "workerHeartbeatAt" = clock_timestamp(),
            "workerLeaseExpiresAt" = clock_timestamp()
              + ${TEMPLATE_TWIN_SYNTHETIC_QA_WORKER_LEASE_MS} * INTERVAL '1 millisecond',
            "updatedAt" = clock_timestamp()
        WHERE "id" = ${input.runId}
          AND "visitId" = ${input.visitId}
          AND "doctorId" = ${input.userId}
          AND "practiceId" = ${input.practiceId}
          AND "attempt" = ${input.attempt}
          AND "status" = 'PROCESSING'
          AND "workerClaimId" = ${input.workerClaimId}
          AND "workerLeaseExpiresAt" > clock_timestamp()
        RETURNING "id"
      `);
      if (renewed.length !== 1) {
        fail(
          "TEMPLATE_TWIN_SYNTHETIC_QA_FINAL_CLAIM_REJECTED",
          "Synthetic QA worker lease ownership changed.",
        );
      }
    },
  });
}

async function runWithTemplateTwinSyntheticQaLeaseHeartbeat<T>(
  input: Parameters<typeof renewTemplateTwinSyntheticQaWorkerLease>[0],
  callback: () => Promise<T> | T,
): Promise<T> {
  let stopped = false;
  let heartbeatInFlight = false;
  let heartbeatFailure: unknown = null;
  const timer = setInterval(() => {
    if (stopped || heartbeatInFlight || heartbeatFailure) return;
    heartbeatInFlight = true;
    void renewTemplateTwinSyntheticQaWorkerLease(input)
      .catch((error: unknown) => {
        heartbeatFailure = error;
        markTemplateTwinSyntheticQaWorkerLeaseUnhealthy();
      })
      .finally(() => {
        heartbeatInFlight = false;
      });
  }, TEMPLATE_TWIN_SYNTHETIC_QA_WORKER_HEARTBEAT_MS);
  timer.unref?.();
  try {
    return await callback();
  } finally {
    stopped = true;
    clearInterval(timer);
  }
}

/**
 * Choose the provider for exactly one durable visit. A visit without a QA-run
 * relation takes the unchanged live/generic worker path. A visit with a run is
 * admitted only after its rollout generations are re-pinned and compared.
 */
export async function runWithWorkerSyntheticQaProviderSelection<T>(
  visit: TemplateTwinSyntheticQaVisitSnapshot,
  job: TemplateTwinSyntheticQaJobAdmission,
  callback: () => Promise<T> | T,
  dependencies: Partial<SyntheticQaWorkerProviderDependencies> = {},
): Promise<T> {
  const run = visit.syntheticQaRun;
  const env = dependencies.env ?? process.env;
  if (job.userId !== visit.userId) {
    fail(
      "TEMPLATE_TWIN_SYNTHETIC_QA_TENANT_MISMATCH",
      "Worker job owner does not match the visit owner.",
    );
  }
  if (!run) {
    if (
      job.syntheticQaRunId !== undefined ||
      job.syntheticQaAttempt !== undefined ||
      job.workerClaimId !== undefined ||
      job.workerDeliveryNumber !== undefined
    ) {
      fail(
        "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID",
        "A synthetic QA worker claim has no durable run.",
      );
    }
    if (
      isTemplateTwinStagingQaRequested(env) &&
      isCertifiedTemplateTwin(visit.templateAdmission)
    ) {
      fail(
        "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID",
        "Template Twin staging requires a durable synthetic QA admission.",
      );
    }
    if (isStagingFixtureTemplate(visit.templateAdmission)) {
      fail(
        "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID",
        "The staging fixture cannot run without its durable synthetic QA admission.",
      );
    }
    if (isCertifiedTemplateTwin(visit.templateAdmission)) {
      return runWithLegacyTemplateTwinInfrastructureFixture(callback, env);
    }
    return callback();
  }

  const workerClaimId = job.workerClaimId;
  const workerDeliveryNumber = job.workerDeliveryNumber;
  if (
    job.syntheticQaRunId !== run.id ||
    job.syntheticQaAttempt !== run.attempt ||
    !workerClaimId ||
    !Number.isSafeInteger(workerDeliveryNumber)
  ) {
    fail(
      "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID",
      "Worker job run or attempt does not match the durable synthetic QA admission.",
    );
  }

  assertRunMatchesVisit(visit, run);
  const pinRollout = dependencies.pinRollout ?? pinTemplateTwinRollout;
  const claimAttempt =
    dependencies.claimAttempt ?? claimTemplateTwinSyntheticQaWorkerAttempt;
  const verifyEvidence =
    dependencies.verifyEvidence ?? verifyTemplateTwinSyntheticQaWorkerEvidence;
  // Validate every process/resource/provider boundary before the durable
  // ENQUEUED -> PROCESSING claim. A configuration rejection must not strand
  // an attempt that no worker context ever entered.
  assertTemplateTwinSyntheticQaProviderEnvironment(env);
  const currentToken = await pinRollout({
    practiceId: visit.practiceId,
  });
  assertPinnedGeneration(run, currentToken);
  await verifyEvidence({ visit, run });
  await claimAttempt({
    visit,
    run,
    currentToken,
    workerClaimId,
    workerDeliveryNumber: workerDeliveryNumber!,
  });

  const providerContext = {
    mode: TEMPLATE_TWIN_SYNTHETIC_QA_MODE,
    fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
    admissionId: run.admissionId!,
    runId: run.id,
    visitId: visit.id,
    practiceId: visit.practiceId,
    requestSha256: run.requestSha256,
    attempt: run.attempt,
    workerClaimId,
    pinnedGlobalGeneration: run.pinnedGlobalRolloutGeneration,
    pinnedPracticeGeneration: run.pinnedPracticeRolloutGeneration,
    evidenceText:
      run.mode === "typed"
        ? (visit.rawTextInput ?? "")
        : TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
  } as const;
  return runWithTemplateTwinSyntheticQaProviderContext(
    providerContext,
    () =>
      runWithTemplateTwinSyntheticQaLeaseHeartbeat(
        {
          visitId: visit.id,
          userId: visit.userId,
          practiceId: visit.practiceId,
          runId: run.id,
          requestSha256: run.requestSha256,
          fixtureVersion: run.fixtureVersion,
          attempt: run.attempt,
          workerClaimId,
          pinnedGlobalGeneration: run.pinnedGlobalRolloutGeneration,
          pinnedPracticeGeneration: run.pinnedPracticeRolloutGeneration,
        },
        callback,
      ),
    env,
  );
}

/**
 * Terminal BullMQ failure reconciliation for a delivery that died outside the
 * application catch path (for example SIGKILL after PROCESSING). It never
 * reclaims or publishes output. Once the current claim lease has expired it
 * atomically exposes PROCESSING_FAILED/FAILED so the physician can reserve a
 * new monotonic attempt through the normal retry path.
 */
export async function reconcileExpiredTemplateTwinSyntheticQaWorkerClaim(input: {
  runId: string;
  visitId: string;
  userId: string;
  attempt: number;
  now?: Date;
}): Promise<boolean> {
  const snapshot = await prisma.templateTwinSyntheticQaRun.findFirst({
    where: {
      id: input.runId,
      visitId: input.visitId,
      doctorId: input.userId,
      attempt: input.attempt,
    },
    select: {
      admissionId: true,
      practiceId: true,
      pinnedGlobalRolloutGeneration: true,
      pinnedPracticeRolloutGeneration: true,
    },
  });
  if (!snapshot) return false;
  return runSerializableTransactionWithRetry({
    prisma,
    operation: "reconcile_expired_template_twin_worker_claim",
    context: {
      visitId: input.visitId,
      practiceId: snapshot.practiceId,
      runId: input.runId,
    },
    transaction: async (tx: Prisma.TransactionClient) => {
      // Acquire global then practice even when the old token is revoked. This
      // transition only removes authority; it never exposes an output.
      await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: snapshot.practiceId,
        pinnedToken: {
          practiceId: snapshot.practiceId,
          globalGeneration: snapshot.pinnedGlobalRolloutGeneration,
          practiceGeneration: snapshot.pinnedPracticeRolloutGeneration,
        },
      });
      if (!snapshot.admissionId) {
        fail(
          "TEMPLATE_TWIN_SYNTHETIC_QA_RUN_INVALID",
          "Synthetic QA crash reconciliation lacks durable admission.",
        );
      }
      const locked = await lockTemplateTwinStagingQaAdmissionThenRun({
        tx,
        runId: input.runId,
        expectedAdmissionId: snapshot.admissionId,
      });
      const now =
        input.now ??
        (
          await tx.$queryRaw<{ databaseNow: Date }[]>(Prisma.sql`
            SELECT CURRENT_TIMESTAMP AS "databaseNow"
          `)
        )[0]?.databaseNow;
      if (!now) {
        fail(
          "TEMPLATE_TWIN_SYNTHETIC_QA_FINAL_CLAIM_REJECTED",
          "Synthetic QA crash reconciliation could not establish database time.",
        );
      }
      const run = locked.run;
      if (
        run.visitId !== input.visitId ||
        run.doctorId !== input.userId ||
        run.practiceId !== snapshot.practiceId ||
        run.attempt !== input.attempt ||
        run.status !== "PROCESSING" ||
        run.workerClaimId === null ||
        run.workerLeaseExpiresAt === null ||
        run.workerLeaseExpiresAt > now
      ) {
        return false;
      }
      await tx.templateTwinSyntheticQaRun.update({
        where: { id: run.id },
        data: { status: "PROCESSING_FAILED" },
      });
      const failedAdmission =
        await tx.templateTwinSyntheticQaAdmission.updateMany({
          where: {
            id: snapshot.admissionId,
            practiceId: snapshot.practiceId,
            actorId: input.userId,
            visitId: input.visitId,
            attempt: input.attempt,
            phase: "PROCESSING",
          },
          data: {
            phase: "FAILED",
            failedAt: now,
            failureCode: "TEMPLATE_TWIN_SYNTHETIC_QA_WORKER_LEASE_EXPIRED",
          },
        });
      if (failedAdmission.count !== 1) {
        fail(
          "TEMPLATE_TWIN_SYNTHETIC_QA_FINAL_CLAIM_REJECTED",
          "Synthetic QA crash reconciliation could not retire its admission.",
        );
      }
      const visit = await lockCurrentTemplateTwinVisit(tx, input.visitId);
      if (
        !visit ||
        visit.userId !== input.userId ||
        visit.status === TranscribeVisitStatus.READY ||
        visit.status === TranscribeVisitStatus.SIGNED
      ) {
        fail(
          "TEMPLATE_TWIN_SYNTHETIC_QA_FINAL_CLAIM_REJECTED",
          "Synthetic QA crash reconciliation found an incompatible visit state.",
        );
      }
      await markVisitAutomationManifestFailed(tx, {
        visitId: input.visitId,
        failureCode: "WORKER_LEASE_EXPIRED",
        completedAt: now,
      });
      await tx.transcribeVisit.update({
        where: { id: input.visitId },
        data: {
          status: TranscribeVisitStatus.FAILED,
          processingFinishedAt: now,
          needsReview: true,
          reviewReason:
            "The synthetic QA worker stopped before verification completed. Retry to start a new guarded attempt.",
          failureCategory: "transient",
        },
      });
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:staging-worker-crash-reconciled:${input.runId}:${input.attempt}`,
        practiceId: snapshot.practiceId,
        actorId: input.userId,
        action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
        targetType: "TemplateTwinSyntheticQaRun",
        targetId: input.runId,
        metadata: {
          reasonCode: "TEMPLATE_TWIN_SYNTHETIC_QA_WORKER_LEASE_EXPIRED",
          operation: "stalled_worker_terminal_reconciliation",
          stagingQaAttempt: input.attempt,
        },
      });
      return true;
    },
  });
}

/**
 * Terminal failure publication for one admitted synthetic attempt. It is the
 * only failure path used by the staging worker: no generic Sentry, Resend, or
 * live-provider notification is invoked. A failed attempt can be explicitly
 * retried as a new monotonically increasing attempt; the old attempt cannot
 * resume or overwrite the new one.
 */
export async function failTemplateTwinSyntheticQaProcessing(input: {
  visitId: string;
  userId: string;
  practiceId: string;
  reviewReason: string;
  failureCategory: string;
}): Promise<boolean> {
  const context = getTemplateTwinSyntheticQaProviderContext();
  if (!context) return false;
  if (
    context.visitId !== input.visitId ||
    context.practiceId !== input.practiceId
  ) {
    fail(
      "TEMPLATE_TWIN_SYNTHETIC_QA_TENANT_MISMATCH",
      "Synthetic QA failure state does not match the admitted visit.",
    );
  }
  assertTemplateTwinSyntheticQaWorkerLeaseHealthy();
  await runSerializableTransactionWithRetry({
    prisma,
    operation: "fail_template_twin_synthetic_qa_processing",
    context: {
      visitId: input.visitId,
      practiceId: input.practiceId,
      runId: context.runId,
    },
    transaction: async (tx: Prisma.TransactionClient) => {
      // This acquires global then practice rollout locks. Failure publication
      // is permitted after revocation because FAILED/PROCESSING_FAILED cannot
      // expose or authorize an output, but it still serializes with disable.
      await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.practiceId,
        pinnedToken: {
          practiceId: input.practiceId,
          globalGeneration: context.pinnedGlobalGeneration,
          practiceGeneration: context.pinnedPracticeGeneration,
        },
      });
      await lockAndAssertTemplateTwinStagingQaAttempt({
        tx,
        // Failure publication removes authority and is therefore permitted
        // after rollout revocation. The rollout records are nevertheless
        // locked above; use the immutable admission epoch here to prove the
        // exact run/attempt/worker claim and its still-live database lease.
        currentRolloutToken: {
          practiceId: input.practiceId,
          globalGeneration: context.pinnedGlobalGeneration,
          practiceGeneration: context.pinnedPracticeGeneration,
        },
        claim: {
          runId: context.runId,
          visitId: context.visitId,
          practiceId: context.practiceId,
          doctorId: input.userId,
          fixtureVersion: context.fixtureVersion,
          requestSha256: context.requestSha256,
          attempt: context.attempt,
          workerClaimId: context.workerClaimId,
          pinnedGlobalGeneration: context.pinnedGlobalGeneration,
          pinnedPracticeGeneration: context.pinnedPracticeGeneration,
        },
        allowedStatuses: ["PROCESSING"],
        allowedAdmissionPhases: ["PROCESSING"],
        requireLiveWorkerLease: true,
      });
      const failed = await tx.templateTwinSyntheticQaRun.updateMany({
        where: {
          id: context.runId,
          visitId: input.visitId,
          doctorId: input.userId,
          practiceId: input.practiceId,
          attempt: context.attempt,
          status: "PROCESSING",
          workerClaimId: context.workerClaimId,
        },
        data: { status: "PROCESSING_FAILED" },
      });
      if (failed.count !== 1) {
        fail(
          "TEMPLATE_TWIN_SYNTHETIC_QA_FINAL_CLAIM_REJECTED",
          "Synthetic QA attempt was replaced before failure publication.",
        );
      }
      const failedAdmission =
        await tx.templateTwinSyntheticQaAdmission.updateMany({
          where: {
            id: context.admissionId,
            practiceId: input.practiceId,
            actorId: input.userId,
            visitId: input.visitId,
            attempt: context.attempt,
            phase: "PROCESSING",
          },
          data: {
            phase: "FAILED",
            failedAt: new Date(),
            failureCode: "TEMPLATE_TWIN_SYNTHETIC_QA_PROCESSING_FAILED",
          },
        });
      if (failedAdmission.count !== 1) {
        fail(
          "TEMPLATE_TWIN_SYNTHETIC_QA_FINAL_CLAIM_REJECTED",
          "Synthetic QA failure could not retire its durable admission.",
        );
      }
      const visit = await lockCurrentTemplateTwinVisit(tx, input.visitId);
      if (
        !visit ||
        visit.userId !== input.userId ||
        visit.status === TranscribeVisitStatus.READY ||
        visit.status === TranscribeVisitStatus.SIGNED
      ) {
        fail(
          "TEMPLATE_TWIN_SYNTHETIC_QA_FINAL_CLAIM_REJECTED",
          "Synthetic QA visit reached an incompatible terminal state.",
        );
      }
      const failedAt = new Date();
      await markVisitAutomationManifestFailed(tx, {
        visitId: input.visitId,
        failureCode: "WORKER_ATTEMPT_FAILED",
        completedAt: failedAt,
      });
      await tx.transcribeVisit.update({
        where: { id: input.visitId },
        data: {
          status: TranscribeVisitStatus.FAILED,
          processingFinishedAt: failedAt,
          needsReview: true,
          reviewReason: input.reviewReason,
          failureCategory: input.failureCategory,
        },
      });
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:staging-processing-failed:${context.runId}:${context.attempt}`,
        practiceId: input.practiceId,
        actorId: input.userId,
        action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
        targetType: "TranscribeVisit",
        targetId: input.visitId,
        metadata: {
          reasonCode: "TEMPLATE_TWIN_SYNTHETIC_QA_PROCESSING_FAILED",
          operation: "staging_worker_processing",
          stagingQaRunId: context.runId,
          stagingQaAttempt: context.attempt,
        },
      });
    },
  });
  return true;
}

/**
 * L4 resolves the template after transcription/entity extraction. Re-check its
 * token against the context pinned at worker admission so disable/re-enable
 * cannot revive an old synthetic run between those stages.
 */
export function assertSyntheticQaResolvedRolloutToken(
  resolvedToken: TemplateTwinRolloutToken,
): void {
  const context = getTemplateTwinSyntheticQaProviderContext();
  if (!context) return;
  if (
    resolvedToken.practiceId !== context.practiceId ||
    resolvedToken.globalGeneration !== context.pinnedGlobalGeneration ||
    resolvedToken.practiceGeneration !== context.pinnedPracticeGeneration
  ) {
    fail(
      "TEMPLATE_TWIN_SYNTHETIC_QA_ROLLOUT_GENERATION_STALE",
      "Template Twin availability changed while the synthetic QA run was processing. Start a new run.",
    );
  }
}

// READY finalization is intentionally owned by automation-finalization.ts.
// Keeping a second staging-only finalizer made it possible to publish READY
// without proving every required automation layer. Do not add a fallback here.
