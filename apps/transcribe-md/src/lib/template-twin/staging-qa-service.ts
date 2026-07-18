import { createHash, randomUUID } from "node:crypto";

import prisma from "@meddoc/db";
import { Prisma, TranscribeVisitStatus } from "@prisma/client";
import { z } from "zod";

import { putAudioStream } from "@/lib/minio";
import { enqueueTemplateTwinSyntheticQaVisit } from "@/lib/queue";
import { runSerializableTransactionWithRetry } from "@/lib/db/transaction-retry";

import { enqueueTemplateTwinAudit } from "./audit-outbox";
import { canonicalSha256 } from "./canonical";
import { lockCurrentTemplateTwinVisit } from "./fill-engine";
import {
  buildTemplateTwinStagingQaWav,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
  TEMPLATE_TWIN_STAGING_QA_VOICE_TRANSCRIPT,
  TEMPLATE_TWIN_STAGING_QA_WAV_SIZE_BYTES,
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
} from "./staging-qa-fixtures";
import {
  templateTwinStagingQaPayloadSha256,
  templateTwinStagingQaRunRequestSha256,
} from "./staging-qa-digest";
import { assertTemplateTwinStagingQaGate } from "./staging-qa-gate";
import {
  lockAndAssertTemplateTwinStagingQaActor,
  lockAndAssertTemplateTwinStagingQaRun,
  TemplateTwinStagingQaVisitGuardError,
} from "./staging-qa-visit-guard";
import { assertTemplateTwinStagingQaEvidencePhiFree } from "./synthetic-evidence-gate";
import {
  beginTemplateTwinStagingQaVisitAdmission,
  lockAndAssertTemplateTwinStagingQaAdmission,
  markTemplateTwinStagingQaAdmissionFailed,
  runWithVerifiedTemplateTwinStagingQaAdmissionProvider,
  TemplateTwinStagingQaAdmissionError,
} from "./staging-qa-admission";
import {
  TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID,
  TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_NAME,
} from "./synthetic-qa-patient";
import {
  lockTemplateTwinRolloutForFinalClaim,
  type TemplateTwinRolloutToken,
} from "./rollout";

const IDEMPOTENCY_KEY = /^[A-Za-z0-9._~-]{16,128}$/u;
const MAX_ENCOUNTER_CHARS = 5_000;

const RunBaseSchema = z.object({
  templateId: z.string().trim().min(8).max(200),
  expectedTemplateVersion: z.number().int().positive(),
  idempotencyKey: z.string().regex(IDEMPOTENCY_KEY),
});

export const TemplateTwinStagingQaRunRequestSchema = z.discriminatedUnion(
  "mode",
  [
    RunBaseSchema.extend({
      mode: z.literal("typed"),
      encounterText: z.string().trim().min(30).max(MAX_ENCOUNTER_CHARS),
    }).strict(),
    RunBaseSchema.extend({
      mode: z.literal("mock_voice"),
      encounterText: z.never().optional(),
    }).strict(),
  ],
);

export type TemplateTwinStagingQaRunRequest = z.infer<
  typeof TemplateTwinStagingQaRunRequestSchema
>;

/**
 * A retry is the single monotonic transition from `expectedAttempt` to
 * `expectedAttempt + 1`. The pair (run id, expected attempt) is therefore the
 * durable idempotency identity for that retry: replaying it may heal the same
 * stable BullMQ admission, but can never reserve a later attempt.
 */
export const TemplateTwinStagingQaRetryRequestSchema = z
  .object({
    expectedAttempt: z.number().int().min(0).max(2_147_483_646),
  })
  .strict();

export type TemplateTwinStagingQaRetryRequest = z.infer<
  typeof TemplateTwinStagingQaRetryRequestSchema
>;

export interface TemplateTwinStagingQaActor {
  userId: string;
  userEmail: string;
  practiceId: string;
  rolloutToken: TemplateTwinRolloutToken;
}

export type TemplateTwinStagingQaErrorCode =
  | "NOT_FOUND"
  | "IDEMPOTENCY_CONFLICT"
  | "TEMPLATE_NOT_READY"
  | "ROLLOUT_CHANGED"
  | "RETRY_ATTEMPT_STALE"
  | "RUN_NOT_RETRYABLE"
  | "RUN_NOT_REGENERABLE"
  | "STORAGE_UNAVAILABLE"
  | "QUEUE_UNAVAILABLE";

export class TemplateTwinStagingQaError extends Error {
  constructor(
    readonly code: TemplateTwinStagingQaErrorCode,
    message: string,
    options?: ErrorOptions,
  ) {
    super(message, options);
    this.name = "TemplateTwinStagingQaError";
  }
}

export interface TemplateTwinStagingQaRunView {
  runId: string;
  visitId: string;
  mode: "typed" | "mock_voice";
  fixtureVersion: string;
  status: string;
  visitStatus: string;
  attempt: number;
  templateId: string;
  templateVersion: number;
  globalRolloutGeneration: string;
  practiceRolloutGeneration: string;
  enqueuedAt: string | null;
  createdAt: string;
  reused: boolean;
}

function sha256Text(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

export function templateTwinStagingQaRequestDigests(input: {
  actor: Pick<TemplateTwinStagingQaActor, "userId" | "practiceId">;
  request: TemplateTwinStagingQaRunRequest;
  evidenceText: string;
}): { requestSha256: string; payloadSha256: string; evidenceSha256: string } {
  const evidenceSha256 = sha256Text(input.evidenceText);
  return {
    requestSha256: templateTwinStagingQaRunRequestSha256({
      practiceId: input.actor.practiceId,
      doctorId: input.actor.userId,
      idempotencyKey: input.request.idempotencyKey,
    }),
    payloadSha256: templateTwinStagingQaPayloadSha256({
      templateId: input.request.templateId,
      expectedTemplateVersion: input.request.expectedTemplateVersion,
      mode: input.request.mode,
      fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
      evidenceText: input.evidenceText,
    }),
    evidenceSha256,
  };
}

function pinnedToken(run: {
  practiceId: string;
  pinnedGlobalRolloutGeneration: bigint;
  pinnedPracticeRolloutGeneration: bigint;
}): TemplateTwinRolloutToken {
  return {
    practiceId: run.practiceId,
    globalGeneration: run.pinnedGlobalRolloutGeneration,
    practiceGeneration: run.pinnedPracticeRolloutGeneration,
  };
}

function serializeRun(
  run: {
    id: string;
    visitId: string;
    mode: string;
    fixtureVersion: string;
    status: string;
    attempt: number;
    noteTemplateId: string;
    noteTemplateVersion: number;
    pinnedGlobalRolloutGeneration: bigint;
    pinnedPracticeRolloutGeneration: bigint;
    enqueuedAt: Date | null;
    createdAt: Date;
    visit: { status: TranscribeVisitStatus | string };
  },
  reused: boolean,
): TemplateTwinStagingQaRunView {
  return {
    runId: run.id,
    visitId: run.visitId,
    mode: run.mode as "typed" | "mock_voice",
    fixtureVersion: run.fixtureVersion,
    status: run.status,
    visitStatus: run.visit.status,
    attempt: run.attempt,
    templateId: run.noteTemplateId,
    templateVersion: run.noteTemplateVersion,
    globalRolloutGeneration: run.pinnedGlobalRolloutGeneration.toString(),
    practiceRolloutGeneration: run.pinnedPracticeRolloutGeneration.toString(),
    enqueuedAt: run.enqueuedAt?.toISOString() ?? null,
    createdAt: run.createdAt.toISOString(),
    reused,
  };
}

const RUN_VIEW_SELECT = {
  id: true,
  practiceId: true,
  doctorId: true,
  visitId: true,
  noteTemplateId: true,
  noteTemplateVersion: true,
  admissionId: true,
  requestSha256: true,
  payloadSha256: true,
  mode: true,
  fixtureVersion: true,
  pinnedGlobalRolloutGeneration: true,
  pinnedPracticeRolloutGeneration: true,
  status: true,
  attempt: true,
  enqueuedAt: true,
  createdAt: true,
  visit: {
    select: {
      status: true,
      inputMode: true,
      dictationAudioKey: true,
      audioUploadedAt: true,
      deletedAt: true,
      archivedAt: true,
      templateTwinFill: {
        select: {
          status: true,
          signedDecisionAt: true,
          soapVersion: true,
          soapSha256: true,
          manifestVersion: true,
          manifestSha256: true,
        },
      },
    },
  },
} as const;

async function findOwnedRun(input: {
  actor: TemplateTwinStagingQaActor;
  runId?: string;
  visitId?: string;
}) {
  return prisma.templateTwinSyntheticQaRun.findFirst({
    where: {
      ...(input.runId ? { id: input.runId } : { visitId: input.visitId }),
      doctorId: input.actor.userId,
      practiceId: input.actor.practiceId,
    },
    select: RUN_VIEW_SELECT,
  });
}

async function recordEnqueueFailure(input: {
  runId: string;
  actor: TemplateTwinStagingQaActor;
  attempt: number;
  errorCode: "STORAGE_UNAVAILABLE" | "QUEUE_UNAVAILABLE";
}): Promise<void> {
  await runSerializableTransactionWithRetry({
    prisma,
    operation: "record_staging_qa_enqueue_failure",
    context: {
      practiceId: input.actor.practiceId,
      runId: input.runId,
    },
    transaction: async (tx: Prisma.TransactionClient) => {
      await tx.templateTwinSyntheticQaRun.updateMany({
        where: {
          id: input.runId,
          doctorId: input.actor.userId,
          practiceId: input.actor.practiceId,
          attempt: input.attempt,
          status: "ENQUEUED",
        },
        data: { status: "ENQUEUE_FAILED", enqueuedAt: null },
      });
      // Queue/object-store admission failed before a provider owned the run.
      // Keep the child admission at VISIT_LINKED so an exact, physician-requested
      // retry can advance its monotonic attempt. Provider/worker failures are
      // different: those transition the admission to terminal FAILED and cannot
      // be revived.
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:staging-qa:enqueue-blocked:${input.runId}:${input.attempt}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail,
        action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
        targetType: "TemplateTwinSyntheticQaRun",
        targetId: input.runId,
        metadata: {
          errorCode: input.errorCode,
          attempt: input.attempt,
          gateOutcome: "blocked",
        },
      });
    },
  });
}

/** @internal Exported for deterministic queue-admission regression tests. */
export async function enqueueOwnedRun(input: {
  actor: TemplateTwinStagingQaActor;
  runId: string;
  explicitRetry: boolean;
  expectedAttempt?: number;
}): Promise<TemplateTwinStagingQaRunView> {
  assertTemplateTwinStagingQaGate();
  if (
    input.explicitRetry &&
    (!Number.isInteger(input.expectedAttempt) || input.expectedAttempt! < 0)
  ) {
    throw new TemplateTwinStagingQaError(
      "RETRY_ATTEMPT_STALE",
      "Refresh this synthetic QA run before retrying.",
    );
  }
  const reserved = await runSerializableTransactionWithRetry({
    prisma,
    operation: "reserve_staging_qa_enqueue",
    context: {
      practiceId: input.actor.practiceId,
      runId: input.runId,
    },
    isolationLevel: Prisma.TransactionIsolationLevel.ReadCommitted,
    transaction: async (tx: Prisma.TransactionClient) => {
      const snapshot = await tx.templateTwinSyntheticQaRun.findFirst({
        where: {
          id: input.runId,
          doctorId: input.actor.userId,
          practiceId: input.actor.practiceId,
        },
        select: RUN_VIEW_SELECT,
      });
      if (!snapshot) {
        throw new TemplateTwinStagingQaError(
          "NOT_FOUND",
          "Synthetic QA run not found.",
        );
      }
      const rollout = await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: snapshot.practiceId,
        pinnedToken: pinnedToken(snapshot),
      });
      if (!rollout.allowed) {
        throw new TemplateTwinStagingQaError("ROLLOUT_CHANGED", rollout.reason);
      }
      try {
        await lockAndAssertTemplateTwinStagingQaRun({
          tx,
          runId: snapshot.id,
          actor: {
            userId: input.actor.userId,
            practiceId: input.actor.practiceId,
          },
          currentRolloutToken: rollout.token,
        });
      } catch (error) {
        if (error instanceof TemplateTwinStagingQaVisitGuardError) {
          throw new TemplateTwinStagingQaError(
            error.code === "TEMPLATE_TWIN_STAGING_QA_NOT_FOUND"
              ? "NOT_FOUND"
              : error.code === "TEMPLATE_TWIN_STAGING_QA_ROLLOUT_STALE"
                ? "ROLLOUT_CHANGED"
                : "RUN_NOT_RETRYABLE",
            error.code === "TEMPLATE_TWIN_STAGING_QA_NOT_FOUND"
              ? "Synthetic QA run not found."
              : "This synthetic QA admission is no longer current. Start a new synthetic run.",
            { cause: error },
          );
        }
        throw error;
      }
      await lockCurrentTemplateTwinVisit(tx, snapshot.visitId);
      const run = await tx.templateTwinSyntheticQaRun.findFirst({
        where: {
          id: snapshot.id,
          doctorId: input.actor.userId,
          practiceId: input.actor.practiceId,
        },
        select: RUN_VIEW_SELECT,
      });
      if (!run) {
        throw new TemplateTwinStagingQaError(
          "NOT_FOUND",
          "Synthetic QA run not found.",
        );
      }
      if (run.visit.deletedAt || run.visit.archivedAt) {
        throw new TemplateTwinStagingQaError(
          "RUN_NOT_RETRYABLE",
          "This synthetic QA visit is no longer active.",
        );
      }
      if (run.visit.status === TranscribeVisitStatus.SIGNED) {
        throw new TemplateTwinStagingQaError(
          "RUN_NOT_RETRYABLE",
          "A signed synthetic QA run cannot be retried.",
        );
      }

      if (input.explicitRetry) {
        const expectedAttempt = input.expectedAttempt!;
        const reservedAttempt = expectedAttempt + 1;

        if (run.attempt === reservedAttempt) {
          // This exact retry transition already committed. If Redis admission
          // may still be in the DB-commit -> queue.add crash window, replay
          // only the same stable job id. Never turn this replay into attempt
          // N+2, even if the duplicate request is serialized after the first.
          if (
            run.status === "ENQUEUED" &&
            run.visit.status === TranscribeVisitStatus.QUEUED
          ) {
            return { ...run, replayExistingAdmission: true };
          }
          return null;
        }

        if (run.attempt !== expectedAttempt) {
          throw new TemplateTwinStagingQaError(
            "RETRY_ATTEMPT_STALE",
            "A newer synthetic QA attempt already exists. Refresh before retrying again.",
          );
        }
      }
      if (run.status === "PROCESSING") {
        if (!input.explicitRetry) return null;
        throw new TemplateTwinStagingQaError(
          "RUN_NOT_RETRYABLE",
          "The synthetic QA worker still owns this attempt. Wait for it to finish or start a separate run after worker recovery.",
        );
      }
      if (
        !input.explicitRetry &&
        (run.status === "PROCESSING_FAILED" || run.status === "COMPLETED")
      ) {
        return null;
      }
      const regeneratingReadyVisit =
        run.visit.status === TranscribeVisitStatus.READY;
      if (regeneratingReadyVisit) {
        if (!input.explicitRetry && run.status === "ENQUEUED") return null;
        if (
          run.visit.templateTwinFill?.status !== "NEEDS_REVIEW" ||
          run.visit.templateTwinFill.signedDecisionAt !== null
        ) {
          throw new TemplateTwinStagingQaError(
            "RUN_NOT_REGENERABLE",
            "Regeneration is available only after the current Original Template DOCX is invalidated or needs physician review.",
          );
        }
      }
      const inFlight =
        run.visit.status !== TranscribeVisitStatus.QUEUED &&
        run.visit.status !== TranscribeVisitStatus.FAILED &&
        run.visit.status !== TranscribeVisitStatus.READY;
      if (inFlight) {
        if (!input.explicitRetry && run.status === "ENQUEUED") return null;
        throw new TemplateTwinStagingQaError(
          "RUN_NOT_RETRYABLE",
          "The synthetic QA run is still processing.",
        );
      }
      if (
        !input.explicitRetry &&
        run.status === "ENQUEUED" &&
        run.visit.status === TranscribeVisitStatus.QUEUED
      ) {
        // The database admission commits before Redis so the worker can never
        // observe an unadmitted attempt. If the request process crashes in
        // that narrow gap, an exact idempotent replay re-adds the same stable
        // BullMQ job ID instead of leaving a permanently jobless QUEUED visit.
        return { ...run, replayExistingAdmission: true };
      }
      if (
        !input.explicitRetry &&
        run.status === "ENQUEUED" &&
        run.visit.status !== TranscribeVisitStatus.FAILED
      ) {
        return null;
      }

      const incrementsAttempt =
        input.explicitRetry ||
        run.status === "ENQUEUE_FAILED" ||
        run.visit.status === TranscribeVisitStatus.FAILED ||
        run.attempt === 0;
      const attempt = incrementsAttempt ? run.attempt + 1 : run.attempt;
      const claim = await tx.templateTwinSyntheticQaRun.updateMany({
        where: {
          id: run.id,
          attempt: run.attempt,
          status: run.status,
        },
        data: {
          attempt,
          // This DB commit is the durable queue-admission point. The worker
          // may run immediately after queue.add, so it must already observe an
          // ENQUEUED row for this exact attempt. An add/storage failure moves
          // this exact attempt to ENQUEUE_FAILED transactionally with audit.
          status: "ENQUEUED",
          enqueuedAt: new Date(),
          workerClaimId: null,
          workerClaimedAt: null,
          workerHeartbeatAt: null,
          workerLeaseExpiresAt: null,
          ...(incrementsAttempt && run.attempt > 0
            ? { lastRetriedAt: new Date() }
            : {}),
        },
      });
      if (claim.count !== 1) return null;

      if (incrementsAttempt && run.attempt > 0 && run.admissionId) {
        const currentAdmissionPhase = regeneratingReadyVisit
          ? "REVIEW_READY"
          : "VISIT_LINKED";
        const reset = await tx.templateTwinSyntheticQaAdmission.updateMany({
          where: {
            id: run.admissionId,
            phase: currentAdmissionPhase,
            attempt: run.attempt,
          },
          data: {
            phase: "VISIT_LINKED",
            attempt,
          },
        });
        if (reset.count !== 1) {
          throw new TemplateTwinStagingQaError(
            "RUN_NOT_RETRYABLE",
            "The durable synthetic QA admission cannot be regenerated.",
          );
        }
      }

      if (
        run.visit.status === TranscribeVisitStatus.FAILED ||
        regeneratingReadyVisit
      ) {
        await tx.transcribeVisit.update({
          where: { id: run.visitId },
          data: {
            status: TranscribeVisitStatus.QUEUED,
            needsReview: false,
            reviewReason: null,
            failureCategory: null,
            processingFinishedAt: null,
          },
        });
      }
      if (incrementsAttempt && run.attempt > 0) {
        await enqueueTemplateTwinAudit(tx, {
          eventKey: `template-twin:staging-qa:retried:${run.id}:${attempt}`,
          practiceId: run.practiceId,
          actorId: input.actor.userId,
          actorEmailSnapshot: input.actor.userEmail,
          action: "TEMPLATE_TWIN_STAGING_QA_RUN_RETRIED",
          targetType: "TemplateTwinSyntheticQaRun",
          targetId: run.id,
          metadata: {
            attempt,
            mode: run.mode,
            fixtureVersion: run.fixtureVersion,
            globalRolloutGeneration:
              run.pinnedGlobalRolloutGeneration.toString(),
            practiceRolloutGeneration:
              run.pinnedPracticeRolloutGeneration.toString(),
            retryReason: regeneratingReadyVisit
              ? "FILL_NEEDS_REVIEW"
              : "PROCESSING_OR_ENQUEUE_RETRY",
          },
        });
      }
      return {
        ...run,
        attempt,
        status: "ENQUEUED" as const,
        replayExistingAdmission: false,
      };
    },
  });

  if (!reserved) {
    const current = await findOwnedRun({
      actor: input.actor,
      runId: input.runId,
    });
    if (!current) {
      throw new TemplateTwinStagingQaError(
        "NOT_FOUND",
        "Synthetic QA run not found.",
      );
    }
    return serializeRun(current, true);
  }

  if (reserved.mode === "mock_voice" && !reserved.visit.audioUploadedAt) {
    const wav = buildTemplateTwinStagingQaWav();
    try {
      await putAudioStream(
        reserved.visit.dictationAudioKey!,
        wav,
        wav.byteLength,
        "audio/wav",
      );
      await prisma.transcribeVisit.updateMany({
        where: {
          id: reserved.visitId,
          userId: input.actor.userId,
          dictationAudioKey: reserved.visit.dictationAudioKey,
        },
        data: { audioUploadedAt: new Date() },
      });
    } catch (error) {
      await recordEnqueueFailure({
        runId: reserved.id,
        actor: input.actor,
        attempt: reserved.attempt,
        errorCode: "STORAGE_UNAVAILABLE",
      });
      throw new TemplateTwinStagingQaError(
        "STORAGE_UNAVAILABLE",
        "Synthetic QA audio storage is unavailable. Retry this run later.",
        { cause: error },
      );
    }
  }

  try {
    await enqueueTemplateTwinSyntheticQaVisit({
      runId: reserved.id,
      attempt: reserved.attempt,
      visitId: reserved.visitId,
      userId: input.actor.userId,
    });
  } catch (error) {
    await recordEnqueueFailure({
      runId: reserved.id,
      actor: input.actor,
      attempt: reserved.attempt,
      errorCode: "QUEUE_UNAVAILABLE",
    });
    throw new TemplateTwinStagingQaError(
      "QUEUE_UNAVAILABLE",
      "The synthetic QA worker queue is unavailable. Retry this run later.",
      { cause: error },
    );
  }

  const current = await findOwnedRun({
    actor: input.actor,
    runId: reserved.id,
  });
  if (!current) {
    throw new TemplateTwinStagingQaError(
      "NOT_FOUND",
      "Synthetic QA run not found.",
    );
  }
  return serializeRun(
    current,
    reserved.replayExistingAdmission || reserved.attempt > 1,
  );
}

export async function createTemplateTwinStagingQaRun(input: {
  actor: TemplateTwinStagingQaActor;
  request: TemplateTwinStagingQaRunRequest;
}): Promise<TemplateTwinStagingQaRunView> {
  assertTemplateTwinStagingQaGate();
  const parsed = TemplateTwinStagingQaRunRequestSchema.parse(input.request);
  const evidenceText =
    parsed.mode === "typed"
      ? parsed.encounterText
      : TEMPLATE_TWIN_STAGING_QA_VOICE_TRANSCRIPT;
  const digests = templateTwinStagingQaRequestDigests({
    actor: input.actor,
    request: parsed,
    evidenceText,
  });
  let durableAdmission: Awaited<
    ReturnType<typeof beginTemplateTwinStagingQaVisitAdmission>
  >;
  try {
    durableAdmission = await beginTemplateTwinStagingQaVisitAdmission({
      actor: input.actor,
      idempotencyKey: parsed.idempotencyKey,
      noteTemplateId: parsed.templateId,
      noteTemplateVersion: parsed.expectedTemplateVersion,
      mode: parsed.mode,
      payloadSha256: digests.payloadSha256,
    });
  } catch (error) {
    if (error instanceof TemplateTwinStagingQaAdmissionError) {
      if (error.code === "TEMPLATE_TWIN_STAGING_QA_ADMISSION_MISMATCH") {
        throw new TemplateTwinStagingQaError(
          "IDEMPOTENCY_CONFLICT",
          "That request token was already used for different synthetic evidence.",
          { cause: error },
        );
      }
      throw new TemplateTwinStagingQaError(
        error.code === "TEMPLATE_TWIN_STAGING_QA_ADMISSION_STALE"
          ? "ROLLOUT_CHANGED"
          : "TEMPLATE_NOT_READY",
        "The durable synthetic QA admission is unavailable.",
        { cause: error },
      );
    }
    throw error;
  }
  if (durableAdmission.phase !== "CERTIFIED") {
    const existingRun = await prisma.templateTwinSyntheticQaRun.findFirst({
      where: {
        admissionId: durableAdmission.id,
        practiceId: input.actor.practiceId,
        doctorId: input.actor.userId,
      },
      select: { id: true },
    });
    if (!existingRun) {
      throw new TemplateTwinStagingQaError(
        "TEMPLATE_NOT_READY",
        "The durable synthetic QA admission is incomplete.",
      );
    }
    return enqueueOwnedRun({
      actor: input.actor,
      runId: existingRun.id,
      explicitRetry: false,
    });
  }
  try {
    await runWithVerifiedTemplateTwinStagingQaAdmissionProvider({
      admissionId: durableAdmission.id,
      actor: input.actor,
      allowedPhases: ["CERTIFIED"],
      expectedProviderMode:
        parsed.mode === "typed" ? "SYNTHETIC_TYPED" : "SYNTHETIC_MOCK_VOICE",
      expectedTemplate: {
        id: parsed.templateId,
        version: parsed.expectedTemplateVersion,
      },
      evidenceText,
      operation: (providerVisitId) =>
        assertTemplateTwinStagingQaEvidencePhiFree({
          encounterText: evidenceText,
          practiceId: input.actor.practiceId,
          userId: input.actor.userId,
          providerVisitId,
        }),
    });
  } catch (error) {
    await markTemplateTwinStagingQaAdmissionFailed({
      admissionId: durableAdmission.id,
      actor: input.actor,
      failureCode: "VISIT_EVIDENCE_REJECTED",
    });
    if (error instanceof TemplateTwinStagingQaAdmissionError) {
      throw new TemplateTwinStagingQaError(
        "TEMPLATE_NOT_READY",
        "The durable synthetic QA admission is unavailable.",
        { cause: error },
      );
    }
    throw error;
  }
  // A callback may have observed an operator revocation. Recheck before the
  // visit/run link; the transaction below separately locks rollout generations.
  assertTemplateTwinStagingQaGate();

  let runId: string;
  try {
    const runAdmission = await runSerializableTransactionWithRetry({
      prisma,
      operation: "create_staging_qa_visit_and_run",
      context: { practiceId: input.actor.practiceId },
      transaction: async (tx: Prisma.TransactionClient) => {
        const rollout = await lockTemplateTwinRolloutForFinalClaim({
          tx,
          practiceId: input.actor.practiceId,
          pinnedToken: input.actor.rolloutToken,
        });
        if (!rollout.allowed) {
          throw new TemplateTwinStagingQaError(
            "ROLLOUT_CHANGED",
            rollout.reason,
          );
        }
        await lockAndAssertTemplateTwinStagingQaAdmission({
          tx,
          admissionId: durableAdmission.id,
          actor: input.actor,
          currentToken: rollout.token,
          allowedPhases: ["CERTIFIED"],
          expectedProviderMode:
            parsed.mode === "typed"
              ? "SYNTHETIC_TYPED"
              : "SYNTHETIC_MOCK_VOICE",
          expectedTemplate: {
            id: parsed.templateId,
            version: parsed.expectedTemplateVersion,
          },
        });
        // Canonical lock order: rollout -> practice -> admission -> actor.
        // Keep this after the durable-admission lock; the previous inverse
        // order could oppose worker finalization under concurrency.
        await lockAndAssertTemplateTwinStagingQaActor({
          tx,
          actor: {
            userId: input.actor.userId,
            practiceId: input.actor.practiceId,
          },
        });
        const existing = await tx.templateTwinSyntheticQaRun.findFirst({
          where: {
            practiceId: input.actor.practiceId,
            doctorId: input.actor.userId,
            requestSha256: digests.requestSha256,
          },
          select: { id: true, payloadSha256: true, admissionId: true },
        });
        if (existing) {
          if (
            existing.payloadSha256 !== digests.payloadSha256 ||
            existing.admissionId !== durableAdmission.id
          ) {
            throw new TemplateTwinStagingQaError(
              "IDEMPOTENCY_CONFLICT",
              "That request token was already used for different synthetic evidence.",
            );
          }
          return { runId: existing.id };
        }

        const template = await tx.noteTemplate.findFirst({
          where: {
            id: parsed.templateId,
            doctorId: input.actor.userId,
            version: parsed.expectedTemplateVersion,
            templateKind: "template_twin_docx",
            status: "active",
            templateTwinCompiledVersion: {
              is: {
                certificationStatus: "CERTIFIED",
                certification: { isNot: null },
                sourceArtifact: {
                  is: {
                    practiceId: input.actor.practiceId,
                    validationStatus: "accepted",
                    sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
                    sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
                  },
                },
              },
            },
          },
          select: { id: true, version: true, encounterType: true },
        });
        if (!template) {
          throw new TemplateTwinStagingQaError(
            "TEMPLATE_NOT_READY",
            "Choose an active, physician-certified synthetic Template Twin version.",
          );
        }

        const patientId = `ttqa-${canonicalSha256({
          practiceId: input.actor.practiceId,
          doctorId: input.actor.userId,
          purpose: "template-twin-synthetic-qa-patient-v1",
        }).slice(0, 40)}`;
        const patient = await tx.transcribeMdPatient.upsert({
          where: { id: patientId },
          create: {
            id: patientId,
            practiceId: input.actor.practiceId,
            name: TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_NAME,
            externalId: TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID,
          },
          update: {},
          select: {
            id: true,
            practiceId: true,
            name: true,
            externalId: true,
            dateOfBirth: true,
            mrn: true,
            insurance: true,
            problemList: true,
            weightKg: true,
            allergies: true,
            deletedAt: true,
          },
        });
        if (
          patient.practiceId !== input.actor.practiceId ||
          patient.name !== TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_NAME ||
          patient.externalId !==
            TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID ||
          patient.dateOfBirth !== null ||
          patient.mrn !== null ||
          patient.insurance !== null ||
          patient.problemList !== null ||
          patient.weightKg !== null ||
          patient.allergies.length !== 0 ||
          patient.deletedAt !== null
        ) {
          throw new TemplateTwinStagingQaError(
            "TEMPLATE_NOT_READY",
            "The isolated synthetic QA patient is unavailable.",
          );
        }

        const visitId = randomUUID();
        const voiceObjectKey = `${input.actor.userId}/${visitId}/template-twin-synthetic-qa.wav`;
        await tx.transcribeVisit.create({
          data: {
            id: visitId,
            userId: input.actor.userId,
            patientId: patient.id,
            patientName: TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_NAME,
            specialty: template.encounterType ?? "unspecified",
            chiefComplaint: "Synthetic Template Twin QA only",
            inputMode:
              parsed.mode === "typed" ? "text_notes" : "voice_dictation",
            rawTextInput: parsed.mode === "typed" ? evidenceText : null,
            dictationAudioKey:
              parsed.mode === "mock_voice" ? voiceObjectKey : null,
            audioMimeType: parsed.mode === "mock_voice" ? "audio/wav" : null,
            audioSizeBytes:
              parsed.mode === "mock_voice"
                ? TEMPLATE_TWIN_STAGING_QA_WAV_SIZE_BYTES
                : null,
            noteTemplateId: template.id,
            noteTemplateVersion: template.version,
            status: TranscribeVisitStatus.QUEUED,
          },
          select: { id: true },
        });
        await tx.templateTwinSyntheticQaAdmission.update({
          where: { id: durableAdmission.id },
          data: {
            phase: "VISIT_LINKED",
            visitId,
            visitLinkedAt: new Date(),
          },
        });

        const run = await tx.templateTwinSyntheticQaRun.create({
          data: {
            id: randomUUID(),
            admissionId: durableAdmission.id,
            practiceId: input.actor.practiceId,
            doctorId: input.actor.userId,
            visitId,
            noteTemplateId: template.id,
            noteTemplateVersion: template.version,
            requestSha256: digests.requestSha256,
            payloadSha256: digests.payloadSha256,
            mode: parsed.mode,
            fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
            pinnedGlobalRolloutGeneration:
              input.actor.rolloutToken.globalGeneration,
            pinnedPracticeRolloutGeneration:
              input.actor.rolloutToken.practiceGeneration,
            status: "PENDING_ENQUEUE",
            // The durable child admission starts at attempt one. Persist the
            // matching run epoch before any queue operation so the shared
            // admission guard can validate the initial enqueue transaction.
            attempt: 1,
          },
          select: { id: true },
        });
        await enqueueTemplateTwinAudit(tx, {
          eventKey: `template-twin:staging-qa:created:${run.id}`,
          practiceId: input.actor.practiceId,
          actorId: input.actor.userId,
          actorEmailSnapshot: input.actor.userEmail,
          action: "TEMPLATE_TWIN_STAGING_QA_RUN_CREATED",
          targetType: "TemplateTwinSyntheticQaRun",
          targetId: run.id,
          metadata: {
            mode: parsed.mode,
            fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
            noteTemplateVersion: template.version,
            requestSha256: digests.requestSha256,
            payloadSha256: digests.payloadSha256,
            evidenceSha256: digests.evidenceSha256,
            admissionId: durableAdmission.id,
            globalRolloutGeneration:
              input.actor.rolloutToken.globalGeneration.toString(),
            practiceRolloutGeneration:
              input.actor.rolloutToken.practiceGeneration.toString(),
          },
        });
        return { runId: run.id };
      },
    });
    runId = runAdmission.runId;
  } catch (error) {
    if (
      error instanceof Prisma.PrismaClientKnownRequestError &&
      error.code === "P2002"
    ) {
      const existing = await prisma.templateTwinSyntheticQaRun.findFirst({
        where: {
          practiceId: input.actor.practiceId,
          doctorId: input.actor.userId,
          requestSha256: digests.requestSha256,
        },
        select: { id: true, payloadSha256: true, admissionId: true },
      });
      if (
        !existing ||
        existing.payloadSha256 !== digests.payloadSha256 ||
        existing.admissionId !== durableAdmission.id
      ) {
        throw new TemplateTwinStagingQaError(
          "IDEMPOTENCY_CONFLICT",
          "That request token was already used for different synthetic evidence.",
        );
      }
      runId = existing.id;
    } else {
      throw error;
    }
  }
  return enqueueOwnedRun({ actor: input.actor, runId, explicitRetry: false });
}

export async function retryTemplateTwinStagingQaRun(input: {
  actor: TemplateTwinStagingQaActor;
  runId?: string;
  visitId?: string;
  expectedAttempt: number;
}): Promise<TemplateTwinStagingQaRunView> {
  assertTemplateTwinStagingQaGate();
  const retry = TemplateTwinStagingQaRetryRequestSchema.parse({
    expectedAttempt: input.expectedAttempt,
  });
  if (Boolean(input.runId) === Boolean(input.visitId)) {
    throw new TemplateTwinStagingQaError(
      "NOT_FOUND",
      "Identify exactly one synthetic QA run.",
    );
  }
  const run = await findOwnedRun({
    actor: input.actor,
    runId: input.runId,
    visitId: input.visitId,
  });
  if (!run) {
    throw new TemplateTwinStagingQaError(
      "NOT_FOUND",
      "Synthetic QA run not found.",
    );
  }
  return enqueueOwnedRun({
    actor: input.actor,
    runId: run.id,
    explicitRetry: true,
    expectedAttempt: retry.expectedAttempt,
  });
}

export async function readTemplateTwinStagingQaRun(input: {
  actor: TemplateTwinStagingQaActor;
  runId: string;
}): Promise<TemplateTwinStagingQaRunView> {
  assertTemplateTwinStagingQaGate();
  const run = await findOwnedRun(input);
  if (!run) {
    throw new TemplateTwinStagingQaError(
      "NOT_FOUND",
      "Synthetic QA run not found.",
    );
  }
  if (
    input.actor.rolloutToken.practiceId !== run.practiceId ||
    input.actor.rolloutToken.globalGeneration !==
      run.pinnedGlobalRolloutGeneration ||
    input.actor.rolloutToken.practiceGeneration !==
      run.pinnedPracticeRolloutGeneration
  ) {
    throw new TemplateTwinStagingQaError(
      "ROLLOUT_CHANGED",
      "Template Twin availability changed after this synthetic QA run was admitted. Start a new run.",
    );
  }
  return serializeRun(run, true);
}
