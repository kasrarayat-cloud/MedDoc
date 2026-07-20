import type { AuditAction, Prisma } from "@prisma/client";

import {
  enqueueTemplateTwinAudit,
  type TemplateTwinAuditMetadata,
} from "./audit-outbox";
import { canonicalSha256 } from "./canonical";

export type TemplateTwinVisitMutationOperation =
  | "soap_save"
  | "em_override"
  | "rx_warning_override"
  | "text_submit"
  | "audio_upload"
  | "dictation_upload"
  | "retry"
  | "generic_patch"
  | "archive"
  | "unarchive"
  | "restore"
  | "soft_delete"
  | "hard_delete";

/**
 * Durable, PHI-free audit receipt for a live Template Twin visit mutation.
 * Callers must await this inside the same transaction that holds final
 * authority locks and applies the target CAS. Any outbox failure therefore
 * aborts the protected mutation instead of degrading to best-effort logging.
 */
export async function enqueueTemplateTwinVisitMutationAudit(input: {
  tx: Prisma.TransactionClient;
  practiceId: string;
  actorUserId: string;
  visitId: string;
  operation: TemplateTwinVisitMutationOperation;
  action: AuditAction;
  admittedVisitUpdatedAtEpochMs: number;
  noteTemplateId?: string | null;
  noteTemplateVersion?: number | null;
  /** PHI-free stable identity when one visit epoch permits multiple events. */
  discriminator?: string | number | null;
  metadata?: TemplateTwinAuditMetadata;
}): Promise<void> {
  const eventKey = `template-twin:visit-mutation:${canonicalSha256({
    operation: input.operation,
    visitId: input.visitId,
    admittedVisitUpdatedAtEpochMs: input.admittedVisitUpdatedAtEpochMs,
    discriminator: input.discriminator ?? null,
  })}`;
  await enqueueTemplateTwinAudit(input.tx, {
    eventKey,
    practiceId: input.practiceId,
    actorId: input.actorUserId,
    action: input.action,
    targetType: "TranscribeVisit",
    targetId: input.visitId,
    metadata: {
      operation: input.operation,
      admittedVisitUpdatedAtEpochMs: input.admittedVisitUpdatedAtEpochMs,
      noteTemplateId: input.noteTemplateId ?? null,
      noteTemplateVersion: input.noteTemplateVersion ?? null,
      ...(input.metadata ?? {}),
    },
  });
}
