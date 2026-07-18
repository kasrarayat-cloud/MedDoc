import { getTemplateTwinSyntheticQaProviderContext } from "@meddoc/ai";
import type { Prisma } from "@prisma/client";

import { type AuditLogInput } from "@/lib/audit";
import {
  enqueueIdempotentTemplateTwinAudit,
  type TemplateTwinAuditMetadata,
} from "@/lib/template-twin/audit-outbox";
import { canonicalSha256 } from "@/lib/template-twin/canonical";
import {
  captureAutomationLayerAudit,
  type CapturedWorkerAudit,
} from "@/worker/automation-layer-effects";
import { runVisitAutomationTransaction } from "@/worker/automation-locks";

function jsonSafeMetadata(
  metadata: Record<string, unknown> | undefined,
): TemplateTwinAuditMetadata | undefined {
  if (!metadata) return undefined;
  return JSON.parse(JSON.stringify(metadata)) as TemplateTwinAuditMetadata;
}

/**
 * Worker audit events are awaited and durable. Both ordinary and staging
 * workers acquire the canonical automation locks before enqueueing into the
 * transactional outbox. This avoids the audit_logs FK lock order that caused
 * the independently reproduced practice/user deadlock, and prevents the
 * legacy swallow-on-error logger from hiding a failed worker audit.
 */
function prepareWorkerAudit(input: AuditLogInput): CapturedWorkerAudit {
  const context = getTemplateTwinSyntheticQaProviderContext();
  if (!input.targetId || !input.practiceId || !input.userId) {
    throw new Error(
      "Worker audit requires visit, practice, and actor identity.",
    );
  }
  if (context) {
    if (
      input.targetId !== context.visitId ||
      input.practiceId !== context.practiceId
    ) {
      throw new Error("Synthetic QA worker audit identity mismatch.");
    }
  }
  const metadata = jsonSafeMetadata(input.metadata);
  const discriminator = canonicalSha256({
    action: input.action,
    targetId: input.targetId,
    practiceId: input.practiceId,
    actorId: input.userId,
    runId: context?.runId ?? null,
    attempt: context?.attempt ?? null,
    success: input.success ?? true,
    errorCode: input.errorCode ?? null,
    metadata: metadata ?? null,
  });
  return {
    eventKey: `visit-worker-audit:${discriminator}`,
    practiceId: input.practiceId,
    actorId: input.userId,
    action: input.action,
    targetId: input.targetId,
    targetType: input.targetType ?? null,
    metadata,
  };
}

export async function enqueuePreparedWorkerAuditInTransaction(
  tx: Prisma.TransactionClient,
  audit: CapturedWorkerAudit,
): Promise<void> {
  await enqueueIdempotentTemplateTwinAudit(tx, {
    eventKey: audit.eventKey,
    practiceId: audit.practiceId,
    actorId: audit.actorId,
    action: audit.action,
    targetId: audit.targetId,
    targetType: audit.targetType,
    metadata: audit.metadata,
  });
}

export async function logWorkerAudit(input: AuditLogInput): Promise<void> {
  const audit = prepareWorkerAudit(input);
  if (captureAutomationLayerAudit(audit)) return;
  await runVisitAutomationTransaction({
    operation: "enqueue_visit_worker_audit",
    visitId: audit.targetId,
    userId: audit.actorId,
    practiceId: audit.practiceId,
    transaction: async (tx) => {
      await enqueuePreparedWorkerAuditInTransaction(tx, audit);
    },
  });
}
