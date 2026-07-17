import {
  assertTemplateTwinSyntheticQaWorkerLeaseHealthy,
  getTemplateTwinSyntheticQaProviderContext,
} from "@meddoc/ai";
import prisma from "@meddoc/db";
import { Prisma, TranscribeVisitStatus } from "@prisma/client";

import { lockTemplateTwinRolloutForFinalClaim } from "@/lib/template-twin/rollout";
import {
  lockAndAssertTemplateTwinStagingQaAttempt,
  TemplateTwinStagingQaVisitGuardError,
} from "@/lib/template-twin/staging-qa-visit-guard";

interface LockedVisitMutationRow {
  id: string;
  userId: string;
  status: TranscribeVisitStatus;
  deletedAt: Date | null;
  archivedAt: Date | null;
}

const MUTABLE_PROCESSING_STATUSES = new Set<TranscribeVisitStatus>([
  TranscribeVisitStatus.QUEUED,
  TranscribeVisitStatus.TRANSCRIBING,
  TranscribeVisitStatus.EXTRACTING,
  TranscribeVisitStatus.DRAFTING,
  TranscribeVisitStatus.CRITIQUING,
  TranscribeVisitStatus.POLISHING,
  TranscribeVisitStatus.AUTOMATING,
]);

export class TemplateTwinSyntheticQaMutationFenceError extends Error {
  readonly code = "TEMPLATE_TWIN_SYNTHETIC_QA_MUTATION_FENCED" as const;

  constructor() {
    super("Synthetic QA worker ownership changed before a pipeline write.");
    this.name = "TemplateTwinSyntheticQaMutationFenceError";
  }
}

/**
 * Executes one staging pipeline mutation at the worker-claim linearization
 * point. Expensive provider work happens outside this transaction; immediately
 * before each resulting write we lock global rollout -> practice rollout ->
 * run -> actor -> visit, compare the exact claim and post-lock database wall
 * clock, then mutate. A replacement delivery cannot reclaim while this short
 * transaction holds the run/visit locks, and an old delivery cannot write once
 * the replacement claim commits.
 *
 * Ordinary visits have no synthetic provider context and retain their existing
 * single-write behavior without consulting staging infrastructure.
 */
export async function runTemplateTwinSyntheticQaClaimBoundMutation<T>(input: {
  visitId: string;
  userId: string;
  practiceId: string;
  mutate(client: Prisma.TransactionClient): Promise<T>;
}): Promise<T> {
  const context = getTemplateTwinSyntheticQaProviderContext();
  if (!context) {
    return input.mutate(prisma as Prisma.TransactionClient);
  }
  if (
    context.visitId !== input.visitId ||
    context.practiceId !== input.practiceId
  ) {
    throw new TemplateTwinSyntheticQaMutationFenceError();
  }
  assertTemplateTwinSyntheticQaWorkerLeaseHealthy();

  return prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
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
        throw new TemplateTwinSyntheticQaMutationFenceError();
      }
      try {
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
          requireLiveWorkerLease: true,
        });
      } catch (error) {
        if (error instanceof TemplateTwinStagingQaVisitGuardError) {
          throw new TemplateTwinSyntheticQaMutationFenceError();
        }
        throw error;
      }

      const visits = await tx.$queryRaw<LockedVisitMutationRow[]>(Prisma.sql`
        SELECT "id", "userId", "status", "deletedAt", "archivedAt"
        FROM "transcribe_visits"
        WHERE "id" = ${input.visitId}
        FOR UPDATE
      `);
      const visit = visits[0] ?? null;
      if (
        !visit ||
        visit.userId !== input.userId ||
        visit.deletedAt !== null ||
        visit.archivedAt !== null ||
        !MUTABLE_PROCESSING_STATUSES.has(visit.status)
      ) {
        throw new TemplateTwinSyntheticQaMutationFenceError();
      }
      return input.mutate(tx);
    },
    { isolationLevel: "Serializable" },
  );
}

export async function updateTemplateTwinSyntheticQaClaimBoundVisit(input: {
  visitId: string;
  userId: string;
  practiceId: string;
  data:
    | Prisma.TranscribeVisitUpdateInput
    | Prisma.TranscribeVisitUncheckedUpdateInput;
}): Promise<void> {
  await runTemplateTwinSyntheticQaClaimBoundMutation({
    visitId: input.visitId,
    userId: input.userId,
    practiceId: input.practiceId,
    mutate: async (client) => {
      await client.transcribeVisit.update({
        where: { id: input.visitId },
        data: input.data,
      });
    },
  });
}
