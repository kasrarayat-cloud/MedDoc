import prisma from "@meddoc/db";
import { Prisma, type AuditAction } from "@prisma/client";

import { canonicalSha256 } from "./canonical";
import {
  lockAndAssertCurrentTemplateTwinPhysician,
  TemplateTwinCurrentPhysicianAuthorityError,
} from "./final-claim-authority";
import {
  hasDurableTemplateTwinClinicalMutationProvenance,
  hasExactLiveTemplateTwinDataLifecycleProvenance,
  lockAndAssertOrdinaryClinicalMutation,
  TEMPLATE_TWIN_CLINICAL_MUTATION_PROVENANCE_SELECT,
  TemplateTwinClinicalMutationAuthorizationError,
  type TemplateTwinClinicalMutationProvenance,
} from "./visit-mutation-authority";
import type { TemplateTwinAuditMetadata } from "./audit-outbox";
import { enqueueTemplateTwinVisitMutationAudit } from "./visit-mutation-audit";

export const TEMPLATE_TWIN_DATA_LIFECYCLE_PROVENANCE_SELECT =
  TEMPLATE_TWIN_CLINICAL_MUTATION_PROVENANCE_SELECT;

export class TemplateTwinDataLifecycleAuthorizationError extends Error {
  readonly code = "TEMPLATE_TWIN_DATA_LIFECYCLE_NOT_AUTHORIZED" as const;

  constructor() {
    super("Current physician authorization is required for this visit.");
    this.name = "TemplateTwinDataLifecycleAuthorizationError";
  }
}

/** Final exact-epoch/durable-provenance fence for legacy lifecycle writes. */
export async function lockAndAssertOrdinaryDataLifecycleMutation(input: {
  tx: Prisma.TransactionClient;
  visitId: string;
  actorUserId: string;
  admittedVisitUpdatedAt: Date;
  admittedPatientId: string;
  admittedNoteTemplateId: string | null;
}): Promise<void> {
  try {
    await lockAndAssertOrdinaryClinicalMutation(input);
  } catch (error) {
    if (error instanceof TemplateTwinClinicalMutationAuthorizationError) {
      throw new TemplateTwinDataLifecycleAuthorizationError();
    }
    throw error;
  }
}

export interface TemplateTwinDataLifecycleClaim {
  readonly visitId: string;
  readonly actorUserId: string;
  readonly practiceId: string;
  readonly patientId: string;
  readonly noteTemplateId: string | null;
  readonly noteTemplateVersion: number | null;
  readonly compiledVersionId: string;
  readonly sourceArtifactId: string;
  readonly certificationId: string;
  readonly fillManifestId: string | null;
  readonly providerExecutionIds: readonly string[];
  readonly provenanceSha256: string;
}

function lifecycleIdentity(input: {
  visitId: string;
  actorUserId: string;
  practiceId: string;
  provenance: TemplateTwinClinicalMutationProvenance;
}) {
  const provenance = input.provenance;
  if (
    !hasExactLiveTemplateTwinDataLifecycleProvenance(provenance) ||
    provenance.templateTwinSyntheticQaRun ||
    provenance.templateTwinSyntheticQaAdmission ||
    provenance.patientId !== provenance.patient.id ||
    provenance.patient.practiceId !== input.practiceId ||
    (provenance.noteTemplate?.doctorId != null &&
      provenance.noteTemplate.doctorId !== input.actorUserId) ||
    (provenance.templateTwinFill != null &&
      provenance.templateTwinFill.practiceId !== input.practiceId) ||
    (provenance.noteTemplate?.templateTwinCompiledVersion != null &&
      provenance.noteTemplate.templateTwinCompiledVersion.sourceArtifact
        .practiceId !== input.practiceId) ||
    (provenance.templateTwinProviderExecutions ?? []).some(
      (execution) =>
        execution.practiceId !== input.practiceId ||
        execution.actorUserId !== input.actorUserId ||
        execution.visitId !== input.visitId ||
        execution.syntheticAdmissionId !== null,
    )
  ) {
    throw new TemplateTwinDataLifecycleAuthorizationError();
  }
  const executions = [...(provenance.templateTwinProviderExecutions ?? [])]
    .map((execution) => ({
      id: execution.id,
      practiceId: execution.practiceId,
      actorUserId: execution.actorUserId,
      visitId: execution.visitId,
      sourceArtifactId: execution.sourceArtifactId,
      compiledVersionId: execution.compiledVersionId,
      noteTemplateId: execution.noteTemplateId,
      noteTemplateVersion: execution.noteTemplateVersion,
      providerMode: execution.providerMode,
      syntheticAdmissionId: execution.syntheticAdmissionId,
    }))
    .sort((left, right) => left.id.localeCompare(right.id));
  const compiled = provenance.noteTemplate!.templateTwinCompiledVersion!;
  const certification = compiled.certification!;
  const identity = {
    visitId: input.visitId,
    actorUserId: input.actorUserId,
    practiceId: input.practiceId,
    patientId: provenance.patientId,
    patientPracticeId: provenance.patient.practiceId,
    noteTemplateId: provenance.noteTemplateId,
    noteTemplateVersion: provenance.noteTemplateVersion,
    compiledVersionId: compiled.id,
    sourceArtifactId: compiled.sourceArtifact.id,
    certificationId: certification.id,
    noteTemplate: provenance.noteTemplate,
    fill: provenance.templateTwinFill,
    providerExecutions: executions,
  };
  return {
    patientId: provenance.patientId,
    noteTemplateId: provenance.noteTemplateId,
    noteTemplateVersion: provenance.noteTemplateVersion,
    compiledVersionId: compiled.id,
    sourceArtifactId: compiled.sourceArtifact.id,
    certificationId: certification.id,
    fillManifestId: provenance.templateTwinFill?.id ?? null,
    providerExecutionIds: executions.map(({ id }) => id),
    provenanceSha256: canonicalSha256(identity),
  };
}

export async function enqueueTemplateTwinDataLifecycleMutationAudit(input: {
  tx: Prisma.TransactionClient;
  claim: TemplateTwinDataLifecycleClaim;
  operation:
    | "archive"
    | "unarchive"
    | "restore"
    | "soft_delete"
    | "hard_delete";
  action: AuditAction;
  admittedVisitUpdatedAtEpochMs: number;
  discriminator?: string | number | null;
  metadata?: TemplateTwinAuditMetadata;
}): Promise<void> {
  await enqueueTemplateTwinVisitMutationAudit({
    tx: input.tx,
    practiceId: input.claim.practiceId,
    actorUserId: input.claim.actorUserId,
    visitId: input.claim.visitId,
    operation: input.operation,
    action: input.action,
    admittedVisitUpdatedAtEpochMs: input.admittedVisitUpdatedAtEpochMs,
    noteTemplateId: input.claim.noteTemplateId,
    noteTemplateVersion: input.claim.noteTemplateVersion,
    discriminator: input.discriminator,
    metadata: input.metadata,
  });
}

/**
 * Data lifecycle admission intentionally does not consult rollout state: a
 * kill switch must not strand retention, restoration, or archival. It still
 * requires current DB-backed physician/product/practice authority and exact
 * patient/Twin tenant provenance.
 */
export async function pinTemplateTwinDataLifecycleMutation(input: {
  visitId: string;
  actorUserId: string;
  provenance: TemplateTwinClinicalMutationProvenance;
}): Promise<TemplateTwinDataLifecycleClaim | null> {
  if (!hasDurableTemplateTwinClinicalMutationProvenance(input.provenance)) {
    return null;
  }
  const actor = await prisma.user.findUnique({
    where: { id: input.actorUserId },
    select: {
      id: true,
      role: true,
      isActive: true,
      practiceId: true,
      deactivatedAt: true,
      suspendedAt: true,
      softDeletedAt: true,
      products: true,
      practice: { select: { isActive: true } },
    },
  });
  if (
    !actor ||
    actor.id !== input.actorUserId ||
    actor.role !== "DOCTOR" ||
    !actor.isActive ||
    actor.deactivatedAt !== null ||
    actor.suspendedAt !== null ||
    actor.softDeletedAt !== null ||
    !actor.practice.isActive ||
    !actor.products.includes("TRANSCRIBE_MD")
  ) {
    throw new TemplateTwinDataLifecycleAuthorizationError();
  }
  const identity = lifecycleIdentity({
    ...input,
    practiceId: actor.practiceId,
  });
  return {
    visitId: input.visitId,
    actorUserId: input.actorUserId,
    practiceId: actor.practiceId,
    ...identity,
  };
}

export async function lockAndAssertTemplateTwinDataLifecycleMutation(input: {
  tx: Prisma.TransactionClient;
  claim: TemplateTwinDataLifecycleClaim;
}) {
  const practice = await input.tx.$queryRaw<
    Array<{ id: string; isActive: boolean }>
  >(Prisma.sql`
    SELECT practice."id", practice."isActive"
    FROM "practices" practice
    WHERE practice."id" = ${input.claim.practiceId}
    FOR UPDATE
  `);
  if (
    practice.length !== 1 ||
    practice[0]?.id !== input.claim.practiceId ||
    !practice[0]?.isActive
  ) {
    throw new TemplateTwinDataLifecycleAuthorizationError();
  }
  try {
    await lockAndAssertCurrentTemplateTwinPhysician({
      tx: input.tx,
      actor: {
        userId: input.claim.actorUserId,
        practiceId: input.claim.practiceId,
      },
    });
  } catch (error) {
    if (error instanceof TemplateTwinCurrentPhysicianAuthorityError) {
      throw new TemplateTwinDataLifecycleAuthorizationError();
    }
    throw error;
  }
  if (input.claim.noteTemplateId) {
    const template = await input.tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
      SELECT template."id"
      FROM "note_templates" template
      WHERE template."id" = ${input.claim.noteTemplateId}
      FOR UPDATE
    `);
    if (
      template.length !== 1 ||
      template[0]?.id !== input.claim.noteTemplateId
    ) {
      throw new TemplateTwinDataLifecycleAuthorizationError();
    }
  }
  const compiled = await input.tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT compiled."id"
    FROM "template_twin_compiled_versions" compiled
    WHERE compiled."id" = ${input.claim.compiledVersionId}
      AND compiled."noteTemplateId" = ${input.claim.noteTemplateId}
    FOR UPDATE
  `);
  if (
    compiled.length !== 1 ||
    compiled[0]?.id !== input.claim.compiledVersionId
  ) {
    throw new TemplateTwinDataLifecycleAuthorizationError();
  }
  const source = await input.tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT source."id"
    FROM "template_twin_source_artifacts" source
    WHERE source."id" = ${input.claim.sourceArtifactId}
      AND source."practiceId" = ${input.claim.practiceId}
    FOR UPDATE
  `);
  if (source.length !== 1 || source[0]?.id !== input.claim.sourceArtifactId) {
    throw new TemplateTwinDataLifecycleAuthorizationError();
  }
  const certification = await input.tx.$queryRaw<Array<{ id: string }>>(
    Prisma.sql`
      SELECT certification."id"
      FROM "template_twin_certifications" certification
      WHERE certification."id" = ${input.claim.certificationId}
        AND certification."compiledVersionId" = ${input.claim.compiledVersionId}
      FOR UPDATE
    `,
  );
  if (
    certification.length !== 1 ||
    certification[0]?.id !== input.claim.certificationId
  ) {
    throw new TemplateTwinDataLifecycleAuthorizationError();
  }
  const patient = await input.tx.$queryRaw<
    Array<{ id: string; practiceId: string }>
  >(Prisma.sql`
    SELECT patient."id", patient."practiceId"
    FROM "transcribe_md_patients" patient
    WHERE patient."id" = ${input.claim.patientId}
    FOR UPDATE
  `);
  if (
    patient.length !== 1 ||
    patient[0]?.id !== input.claim.patientId ||
    patient[0]?.practiceId !== input.claim.practiceId
  ) {
    throw new TemplateTwinDataLifecycleAuthorizationError();
  }
  const visitLock = await input.tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT visit."id"
    FROM "transcribe_visits" visit
    WHERE visit."id" = ${input.claim.visitId}
      AND visit."userId" = ${input.claim.actorUserId}
    FOR UPDATE
  `);
  if (visitLock.length !== 1 || visitLock[0]?.id !== input.claim.visitId) {
    throw new TemplateTwinDataLifecycleAuthorizationError();
  }
  if (input.claim.fillManifestId) {
    const fill = await input.tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
      SELECT fill."id"
      FROM "template_twin_fill_manifests" fill
      WHERE fill."id" = ${input.claim.fillManifestId}
        AND fill."visitId" = ${input.claim.visitId}
        AND fill."practiceId" = ${input.claim.practiceId}
        AND fill."compiledVersionId" = ${input.claim.compiledVersionId}
        AND fill."noteTemplateId" = ${input.claim.noteTemplateId}
        AND fill."noteTemplateVersion" = ${input.claim.noteTemplateVersion}
      FOR UPDATE
    `);
    if (fill.length !== 1 || fill[0]?.id !== input.claim.fillManifestId) {
      throw new TemplateTwinDataLifecycleAuthorizationError();
    }
  }
  const executions = await input.tx.$queryRaw<
    Array<{
      id: string;
      practiceId: string;
      actorUserId: string;
      visitId: string | null;
      sourceArtifactId: string | null;
      compiledVersionId: string | null;
      noteTemplateId: string | null;
      noteTemplateVersion: number | null;
      providerMode: string;
      syntheticAdmissionId: string | null;
    }>
  >(
    Prisma.sql`
      SELECT
        execution."id", execution."practiceId", execution."actorUserId",
        execution."visitId", execution."sourceArtifactId",
        execution."compiledVersionId", execution."noteTemplateId",
        execution."noteTemplateVersion", execution."providerMode"::text,
        execution."syntheticAdmissionId"
      FROM "template_twin_provider_executions" execution
      WHERE execution."visitId" = ${input.claim.visitId}
      ORDER BY execution."id" ASC
      FOR UPDATE
    `,
  );
  if (
    executions.length !== input.claim.providerExecutionIds.length ||
    executions.some(
      ({ id }, index) => id !== input.claim.providerExecutionIds[index],
    ) ||
    executions.some(
      (execution) =>
        execution.practiceId !== input.claim.practiceId ||
        execution.actorUserId !== input.claim.actorUserId ||
        execution.visitId !== input.claim.visitId ||
        execution.sourceArtifactId !== input.claim.sourceArtifactId ||
        execution.compiledVersionId !== input.claim.compiledVersionId ||
        execution.noteTemplateId !== input.claim.noteTemplateId ||
        execution.noteTemplateVersion !== input.claim.noteTemplateVersion ||
        execution.providerMode !== "LIVE" ||
        execution.syntheticAdmissionId !== null,
    )
  ) {
    throw new TemplateTwinDataLifecycleAuthorizationError();
  }
  const visit = await input.tx.transcribeVisit.findUnique({
    where: {
      id: input.claim.visitId,
      userId: input.claim.actorUserId,
    },
    select: {
      id: true,
      userId: true,
      status: true,
      updatedAt: true,
      soapVersion: true,
      deletedAt: true,
      archivedAt: true,
      audioKey: true,
      dictationAudioKey: true,
      rawTextInput: true,
      ...TEMPLATE_TWIN_DATA_LIFECYCLE_PROVENANCE_SELECT,
    },
  });
  if (!visit || visit.userId !== input.claim.actorUserId) {
    throw new TemplateTwinDataLifecycleAuthorizationError();
  }
  const identity = lifecycleIdentity({
    visitId: input.claim.visitId,
    actorUserId: input.claim.actorUserId,
    practiceId: input.claim.practiceId,
    provenance: visit,
  });
  if (identity.provenanceSha256 !== input.claim.provenanceSha256) {
    throw new TemplateTwinDataLifecycleAuthorizationError();
  }
  return visit;
}
