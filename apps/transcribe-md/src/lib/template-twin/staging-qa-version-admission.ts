import { TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION } from "@meddoc/ai";
import { Prisma } from "@prisma/client";

import { enqueueTemplateTwinAudit } from "./audit-outbox";
import { canonicalSha256 } from "./canonical";
import {
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
} from "./staging-qa-fixture-contract";
import type { TemplateTwinRolloutToken } from "./rollout";

export const TEMPLATE_TWIN_STAGING_QA_VERSION_ADMISSION_CONTRACT =
  "template-twin-staging-version-admission/1.0.0" as const;

/**
 * Give a newly forked version its own root lifecycle capability in the same
 * database transaction that creates the version. The source capability is
 * never moved or reused: the new row is independently bound to the new
 * immutable template ID/version and inherits only the unexpired rollout/source
 * proof. Ordinary templates return `null` without touching admission state.
 */
export async function createTemplateTwinStagingQaVersionAdmission(input: {
  tx: Prisma.TransactionClient;
  actor: {
    userId: string;
    userEmail: string | null;
    practiceId: string;
    rolloutToken: TemplateTwinRolloutToken;
  };
  source: {
    noteTemplateId: string;
    sourceArtifactId: string;
    sha256: string;
    sizeBytes: number;
  };
  target: { noteTemplateId: string; version: number };
  now?: Date;
}): Promise<string | null> {
  if (
    input.source.sha256 !== TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256 ||
    input.source.sizeBytes !== TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES
  ) {
    return null;
  }

  const now = input.now ?? new Date();
  const token = input.actor.rolloutToken;
  if (token.practiceId !== input.actor.practiceId) {
    throw new Error("Synthetic QA fork rollout identity mismatch.");
  }
  const sourceAdmission =
    await input.tx.templateTwinSyntheticQaAdmission.findFirst({
      where: {
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        purpose: "UPLOAD",
        providerMode: "SYNTHETIC_LIFECYCLE",
        phase: { in: ["TEMPLATE_LINKED", "CERTIFIED"] },
        noteTemplateId: input.source.noteTemplateId,
        sourceArtifactId: input.source.sourceArtifactId,
        sourceSha256: input.source.sha256,
        sourceSizeBytes: input.source.sizeBytes,
        pinnedGlobalRolloutGeneration: token.globalGeneration,
        pinnedPracticeRolloutGeneration: token.practiceGeneration,
        failedAt: null,
        revokedAt: null,
        expiresAt: { gt: now },
      },
      orderBy: { createdAt: "desc" },
      select: { id: true, expiresAt: true },
    });
  if (!sourceAdmission) {
    throw new Error(
      "The reviewed synthetic source no longer has a recoverable lifecycle admission.",
    );
  }

  const requestSha256 = canonicalSha256({
    contractVersion: TEMPLATE_TWIN_STAGING_QA_VERSION_ADMISSION_CONTRACT,
    practiceId: input.actor.practiceId,
    actorId: input.actor.userId,
    sourceAdmissionId: sourceAdmission.id,
    sourceArtifactId: input.source.sourceArtifactId,
    noteTemplateId: input.target.noteTemplateId,
    noteTemplateVersion: input.target.version,
  });
  const existing = await input.tx.templateTwinSyntheticQaAdmission.findFirst({
    where: {
      practiceId: input.actor.practiceId,
      actorId: input.actor.userId,
      requestSha256,
    },
    select: {
      id: true,
      noteTemplateId: true,
      noteTemplateVersion: true,
      sourceArtifactId: true,
      phase: true,
    },
  });
  if (existing) {
    if (
      existing.noteTemplateId !== input.target.noteTemplateId ||
      existing.noteTemplateVersion !== input.target.version ||
      existing.sourceArtifactId !== input.source.sourceArtifactId ||
      existing.phase !== "TEMPLATE_LINKED"
    ) {
      throw new Error("Synthetic QA fork admission identity conflict.");
    }
    return existing.id;
  }

  const admission = await input.tx.templateTwinSyntheticQaAdmission.create({
    data: {
      practiceId: input.actor.practiceId,
      actorId: input.actor.userId,
      sourceSha256: input.source.sha256,
      sourceSizeBytes: input.source.sizeBytes,
      fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
      providerMode: "SYNTHETIC_LIFECYCLE",
      purpose: "UPLOAD",
      // The durable admission trigger requires every capability to enter at
      // ADMITTED. Bind the immutable target identity now, then advance through
      // both required transitions below in this same fork transaction.
      phase: "ADMITTED",
      requestSha256,
      pinnedGlobalRolloutGeneration: token.globalGeneration,
      pinnedPracticeRolloutGeneration: token.practiceGeneration,
      sourceArtifactId: input.source.sourceArtifactId,
      noteTemplateId: input.target.noteTemplateId,
      noteTemplateVersion: input.target.version,
      expiresAt: sourceAdmission.expiresAt,
    },
    select: { id: true },
  });
  await enqueueTemplateTwinAudit(input.tx, {
    eventKey: `template-twin:staging-admission:version-created:${admission.id}`,
    practiceId: input.actor.practiceId,
    actorId: input.actor.userId,
    actorEmailSnapshot: input.actor.userEmail,
    action: "TEMPLATE_TWIN_STAGING_QA_ADMISSION_CREATED",
    targetType: "TemplateTwinSyntheticQaAdmission",
    targetId: admission.id,
    metadata: {
      contractVersion: TEMPLATE_TWIN_STAGING_QA_VERSION_ADMISSION_CONTRACT,
      sourceAdmissionId: sourceAdmission.id,
      sourceTemplateId: input.source.noteTemplateId,
      noteTemplateId: input.target.noteTemplateId,
      noteTemplateVersion: input.target.version,
      sourceArtifactId: input.source.sourceArtifactId,
      phase: "ADMITTED",
    },
  });
  await input.tx.templateTwinSyntheticQaAdmission.update({
    where: { id: admission.id },
    data: { phase: "SOURCE_VERIFIED", sourceVerifiedAt: now },
  });
  await input.tx.templateTwinSyntheticQaAdmission.update({
    where: { id: admission.id },
    data: { phase: "TEMPLATE_LINKED", templateLinkedAt: now },
  });
  await enqueueTemplateTwinAudit(input.tx, {
    eventKey: `template-twin:staging-admission:version-linked:${admission.id}:${input.target.noteTemplateId}`,
    practiceId: input.actor.practiceId,
    actorId: input.actor.userId,
    actorEmailSnapshot: input.actor.userEmail,
    action: "TEMPLATE_TWIN_STAGING_QA_ADMISSION_ADVANCED",
    targetType: "TemplateTwinSyntheticQaAdmission",
    targetId: admission.id,
    metadata: {
      contractVersion: TEMPLATE_TWIN_STAGING_QA_VERSION_ADMISSION_CONTRACT,
      sourceAdmissionId: sourceAdmission.id,
      sourceTemplateId: input.source.noteTemplateId,
      noteTemplateId: input.target.noteTemplateId,
      noteTemplateVersion: input.target.version,
      sourceArtifactId: input.source.sourceArtifactId,
      phase: "TEMPLATE_LINKED",
    },
  });
  return admission.id;
}
