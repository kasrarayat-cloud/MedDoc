import {
  assertTemplateTwinSyntheticQaWorkerLeaseHealthy,
  getTemplateTwinSyntheticQaProviderContext,
} from "@meddoc/ai";
import prisma from "@meddoc/db";
import { Prisma, TranscribeVisitStatus } from "@prisma/client";

import { runSerializableTransactionWithRetry } from "@/lib/db/transaction-retry";
import { lockTemplateTwinRolloutForFinalClaim } from "@/lib/template-twin/rollout";
import { lockAndAssertTemplateTwinStagingQaAttempt } from "@/lib/template-twin/staging-qa-visit-guard";

export const VISIT_AUTOMATION_CANONICAL_LOCK_ORDER = [
  "global_rollout",
  "practice",
  "staging_admission",
  "staging_run",
  "actor",
  "visit",
  "automation_manifest",
  "automation_layers",
  "audit_outbox",
] as const;

export interface LockedAutomationVisit {
  id: string;
  userId: string;
  status: TranscribeVisitStatus;
  soapVersion: number;
  soapFinal: string | null;
  reviewReason: string | null;
  deletedAt: Date | null;
  archivedAt: Date | null;
}

async function lockOrdinaryScope(input: {
  tx: Prisma.TransactionClient;
  visitId: string;
  userId: string;
  practiceId: string;
}): Promise<LockedAutomationVisit> {
  const practices = await input.tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT "id"
    FROM "practices"
    WHERE "id" = ${input.practiceId}
    FOR UPDATE
  `);
  if (practices.length !== 1) throw new VisitAutomationLockError();

  const actors = await input.tx.$queryRaw<
    Array<{ id: string; practiceId: string; isActive: boolean }>
  >(Prisma.sql`
    SELECT "id", "practiceId", "isActive"
    FROM "users"
    WHERE "id" = ${input.userId}
    FOR UPDATE
  `);
  const actor = actors[0];
  if (
    !actor ||
    actor.practiceId !== input.practiceId ||
    actor.isActive !== true
  ) {
    throw new VisitAutomationLockError();
  }
  return lockVisit(input);
}

async function lockVisit(input: {
  tx: Prisma.TransactionClient;
  visitId: string;
  userId: string;
}): Promise<LockedAutomationVisit> {
  const visits = await input.tx.$queryRaw<LockedAutomationVisit[]>(Prisma.sql`
    SELECT
      "id", "userId", "status", "soapVersion", "soapFinal", "reviewReason",
      "deletedAt", "archivedAt"
    FROM "transcribe_visits"
    WHERE "id" = ${input.visitId}
    FOR UPDATE
  `);
  const visit = visits[0];
  if (!visit || visit.userId !== input.userId) {
    throw new VisitAutomationLockError();
  }
  return visit;
}

export class VisitAutomationLockError extends Error {
  readonly code = "VISIT_AUTOMATION_LOCK_REJECTED" as const;

  constructor() {
    super("The visit automation transaction no longer owns this visit.");
    this.name = "VisitAutomationLockError";
  }
}

/**
 * Executes one idempotent automation database transaction under the shared
 * lock order. Provider calls and object writes must happen before this helper.
 */
export async function runVisitAutomationTransaction<T>(input: {
  operation: string;
  visitId: string;
  userId: string;
  practiceId: string;
  transaction: (
    tx: Prisma.TransactionClient,
    visit: LockedAutomationVisit,
  ) => Promise<T>;
}): Promise<T> {
  const context = getTemplateTwinSyntheticQaProviderContext();
  if (context) {
    if (
      context.visitId !== input.visitId ||
      context.practiceId !== input.practiceId
    ) {
      throw new VisitAutomationLockError();
    }
    assertTemplateTwinSyntheticQaWorkerLeaseHealthy();
  }

  return runSerializableTransactionWithRetry({
    prisma,
    operation: input.operation,
    context: {
      visitId: input.visitId,
      practiceId: input.practiceId,
      runId: context?.runId,
    },
    transaction: async (tx) => {
      let visit: LockedAutomationVisit;
      if (context) {
        const rollout = await lockTemplateTwinRolloutForFinalClaim({
          tx,
          practiceId: input.practiceId,
          pinnedToken: {
            practiceId: input.practiceId,
            globalGeneration: context.pinnedGlobalGeneration,
            practiceGeneration: context.pinnedPracticeGeneration,
          },
        });
        if (!rollout.allowed) throw new VisitAutomationLockError();
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
        // lockAndAssert... acquired admission -> run -> actor.
        visit = await lockVisit({
          tx,
          visitId: input.visitId,
          userId: input.userId,
        });
      } else {
        visit = await lockOrdinaryScope({ tx, ...input });
      }
      if (visit.deletedAt !== null || visit.archivedAt !== null) {
        throw new VisitAutomationLockError();
      }
      return input.transaction(tx, visit);
    },
  });
}
