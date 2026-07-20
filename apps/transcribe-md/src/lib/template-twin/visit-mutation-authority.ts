import prisma from "@meddoc/db";
import { Prisma, type AuditAction } from "@prisma/client";

import { AuthError, requireFreshDoctorIdentity } from "@/lib/auth";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";

import {
  lockAndAssertCurrentTemplateTwinPhysician,
  TemplateTwinCurrentPhysicianAuthorityError,
} from "./final-claim-authority";
import {
  lockTemplateTwinRolloutForFinalClaim,
  type TemplateTwinRolloutToken,
} from "./rollout";
import type { TemplateTwinAuditMetadata } from "./audit-outbox";
import { TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID } from "./synthetic-qa-patient";
import {
  enqueueTemplateTwinVisitMutationAudit,
  type TemplateTwinVisitMutationOperation,
} from "./visit-mutation-audit";
import {
  lockAndAssertOrdinaryClinicalMutation,
  TemplateTwinClinicalMutationAuthorizationError,
} from "./ordinary-visit-mutation-authority";

export {
  lockAndAssertOrdinaryClinicalMutation,
  TemplateTwinClinicalMutationAuthorizationError,
};
export type { TemplateTwinClinicalMutationAuthorizationCode } from "./ordinary-visit-mutation-authority";

export const TEMPLATE_TWIN_CLINICAL_MUTATION_PROVENANCE_SELECT = {
  patientId: true,
  patient: { select: { id: true, practiceId: true, externalId: true } },
  noteTemplateId: true,
  noteTemplateVersion: true,
  noteTemplate: {
    select: {
      id: true,
      doctorId: true,
      version: true,
      templateKind: true,
      templateTwinCompiledVersion: {
        select: {
          id: true,
          noteTemplateId: true,
          sourceArtifactId: true,
          certificationStatus: true,
          sourceArtifact: {
            select: {
              id: true,
              practiceId: true,
              validationStatus: true,
            },
          },
          certification: {
            select: {
              id: true,
              compiledVersionId: true,
              certifiedById: true,
              providerAuthorizationMode: true,
              providerAuthorizationAdmissionId: true,
            },
          },
        },
      },
    },
  },
  templateTwinFill: {
    select: {
      id: true,
      practiceId: true,
      compiledVersionId: true,
      noteTemplateId: true,
      noteTemplateVersion: true,
      signedDecisionAt: true,
    },
  },
  templateTwinSyntheticQaRun: { select: { id: true } },
  templateTwinSyntheticQaAdmission: { select: { id: true } },
  templateTwinProviderExecutions: {
    select: {
      id: true,
      practiceId: true,
      actorUserId: true,
      visitId: true,
      sourceArtifactId: true,
      compiledVersionId: true,
      noteTemplateId: true,
      noteTemplateVersion: true,
      providerMode: true,
      syntheticAdmissionId: true,
    },
    orderBy: { id: "asc" as const },
  },
} as const;

export interface TemplateTwinClinicalMutationProvenance {
  patientId: string;
  patient: { id: string; practiceId: string; externalId: string | null };
  noteTemplateId: string | null;
  noteTemplateVersion: number | null;
  noteTemplate: {
    id: string;
    doctorId: string | null;
    version: number;
    templateKind: string;
    templateTwinCompiledVersion: {
      id: string;
      noteTemplateId: string;
      sourceArtifactId: string;
      certificationStatus: string;
      sourceArtifact: {
        id: string;
        practiceId: string;
        validationStatus: string;
      };
      certification: {
        id: string;
        compiledVersionId: string;
        certifiedById: string;
        providerAuthorizationMode: string;
        providerAuthorizationAdmissionId: string | null;
      } | null;
    } | null;
  } | null;
  templateTwinFill: {
    id: string;
    practiceId: string;
    compiledVersionId: string;
    noteTemplateId: string;
    noteTemplateVersion: number;
    signedDecisionAt: Date | null;
  } | null;
  templateTwinSyntheticQaRun: { id: string } | null;
  templateTwinSyntheticQaAdmission: { id: string } | null;
  templateTwinProviderExecutions: Array<{
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
  }>;
}

/**
 * PHI-minimal visit projection used before any generic mutation selects SOAP,
 * warnings, audio object metadata, or other clinical state.  Identifiers and
 * immutable Template Twin lineage are sufficient to decide whether the
 * ordinary path is allowed or a fresh physician/rollout claim is required.
 */
export const TEMPLATE_TWIN_CLINICAL_MUTATION_ADMISSION_SELECT = {
  id: true,
  userId: true,
  updatedAt: true,
  ...TEMPLATE_TWIN_CLINICAL_MUTATION_PROVENANCE_SELECT,
} as const;

export interface TemplateTwinClinicalMutationAdmissionTarget extends TemplateTwinClinicalMutationProvenance {
  id: string;
  userId: string;
  updatedAt: Date;
}

export async function loadTemplateTwinClinicalMutationAdmissionTarget(input: {
  visitId: string;
  actorUserId: string;
}): Promise<TemplateTwinClinicalMutationAdmissionTarget | null> {
  return prisma.transcribeVisit.findUnique({
    // The admission projection includes the patient identity needed to
    // distinguish reserved synthetic provenance. Bind the actor in this same
    // statement so a guessed foreign visit ID never projects that identity
    // before the caller's ownership check.
    where: {
      id: input.visitId,
      ...currentClinicalVisitActorWhere(input.actorUserId),
    },
    select: TEMPLATE_TWIN_CLINICAL_MUTATION_ADMISSION_SELECT,
  });
}

export interface TemplateTwinClinicalMutationClaim {
  readonly visitId: string;
  readonly actorUserId: string;
  readonly practiceId: string;
  readonly patientId: string;
  readonly noteTemplateId: string;
  readonly noteTemplateVersion: number;
  readonly compiledVersionId: string;
  readonly sourceArtifactId: string;
  readonly certificationId: string;
  readonly fillManifestId: string | null;
  readonly providerExecutionIds: readonly string[];
  /** Exact visit-row epoch admitted before any clinical projection. */
  readonly visitUpdatedAtEpochMs: number;
  readonly rolloutToken: TemplateTwinRolloutToken;
}

export async function enqueueTemplateTwinClinicalMutationAudit(input: {
  tx: Prisma.TransactionClient;
  claim: TemplateTwinClinicalMutationClaim;
  operation: Exclude<
    TemplateTwinVisitMutationOperation,
    "archive" | "unarchive" | "restore" | "soft_delete" | "hard_delete"
  >;
  action: AuditAction;
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
    admittedVisitUpdatedAtEpochMs: input.claim.visitUpdatedAtEpochMs,
    noteTemplateId: input.claim.noteTemplateId,
    noteTemplateVersion: input.claim.noteTemplateVersion,
    discriminator: input.discriminator,
    metadata: input.metadata,
  });
}

type ProvenanceClassification =
  | { kind: "ORDINARY" }
  | {
      kind: "LIVE";
      noteTemplateId: string;
      noteTemplateVersion: number;
      compiledVersionId: string;
      sourceArtifactId: string;
      certificationId: string;
      fillManifestId: string | null;
      providerExecutionIds: string[];
    }
  | { kind: "RESTRICTED" }
  | { kind: "INVALID" };

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function owns(record: Record<string, unknown>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(record, key);
}

function isStringOrNull(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isIntegerOrNull(value: unknown): value is number | null {
  return (
    value === null || (typeof value === "number" && Number.isInteger(value))
  );
}

/** Runtime projection validator: incomplete selects and malformed relation
 * payloads are inconsistent durable provenance, never an ordinary visit. */
function hasCompleteClinicalMutationProvenance(
  value: unknown,
): value is TemplateTwinClinicalMutationProvenance {
  if (!isRecord(value)) return false;
  const required = [
    "patientId",
    "patient",
    "noteTemplateId",
    "noteTemplateVersion",
    "noteTemplate",
    "templateTwinFill",
    "templateTwinSyntheticQaRun",
    "templateTwinSyntheticQaAdmission",
    "templateTwinProviderExecutions",
  ];
  if (required.some((key) => !owns(value, key))) return false;
  if (
    typeof value.patientId !== "string" ||
    !isStringOrNull(value.noteTemplateId) ||
    !isIntegerOrNull(value.noteTemplateVersion)
  ) {
    return false;
  }

  const patient = value.patient;
  if (
    !isRecord(patient) ||
    typeof patient.id !== "string" ||
    typeof patient.practiceId !== "string" ||
    !owns(patient, "externalId") ||
    !isStringOrNull(patient.externalId)
  ) {
    return false;
  }

  const template = value.noteTemplate;
  if (template !== null) {
    if (
      !isRecord(template) ||
      typeof template.id !== "string" ||
      !isStringOrNull(template.doctorId) ||
      typeof template.version !== "number" ||
      !Number.isInteger(template.version) ||
      !owns(template, "templateKind") ||
      typeof template.templateKind !== "string" ||
      template.templateKind.trim().length === 0 ||
      !owns(template, "templateTwinCompiledVersion")
    ) {
      return false;
    }
    const compiled = template.templateTwinCompiledVersion;
    if (compiled !== null) {
      if (
        !isRecord(compiled) ||
        typeof compiled.id !== "string" ||
        typeof compiled.noteTemplateId !== "string" ||
        typeof compiled.sourceArtifactId !== "string" ||
        typeof compiled.certificationStatus !== "string" ||
        !isRecord(compiled.sourceArtifact) ||
        typeof compiled.sourceArtifact.id !== "string" ||
        typeof compiled.sourceArtifact.practiceId !== "string" ||
        typeof compiled.sourceArtifact.validationStatus !== "string" ||
        !owns(compiled, "certification")
      ) {
        return false;
      }
      const certification = compiled.certification;
      if (
        certification !== null &&
        (!isRecord(certification) ||
          typeof certification.id !== "string" ||
          typeof certification.compiledVersionId !== "string" ||
          typeof certification.certifiedById !== "string" ||
          typeof certification.providerAuthorizationMode !== "string" ||
          !isStringOrNull(certification.providerAuthorizationAdmissionId))
      ) {
        return false;
      }
    }
  }

  const fill = value.templateTwinFill;
  if (
    fill !== null &&
    (!isRecord(fill) ||
      typeof fill.id !== "string" ||
      typeof fill.practiceId !== "string" ||
      typeof fill.compiledVersionId !== "string" ||
      typeof fill.noteTemplateId !== "string" ||
      typeof fill.noteTemplateVersion !== "number" ||
      !Number.isInteger(fill.noteTemplateVersion) ||
      !owns(fill, "signedDecisionAt") ||
      (fill.signedDecisionAt !== null &&
        !(fill.signedDecisionAt instanceof Date)))
  ) {
    return false;
  }

  for (const key of [
    "templateTwinSyntheticQaRun",
    "templateTwinSyntheticQaAdmission",
  ] as const) {
    const marker = value[key];
    if (
      marker !== null &&
      (!isRecord(marker) || typeof marker.id !== "string")
    ) {
      return false;
    }
  }

  const executions = value.templateTwinProviderExecutions;
  if (!Array.isArray(executions)) return false;
  return executions.every(
    (execution) =>
      isRecord(execution) &&
      typeof execution.id === "string" &&
      typeof execution.practiceId === "string" &&
      typeof execution.actorUserId === "string" &&
      isStringOrNull(execution.visitId) &&
      isStringOrNull(execution.sourceArtifactId) &&
      isStringOrNull(execution.compiledVersionId) &&
      isStringOrNull(execution.noteTemplateId) &&
      isIntegerOrNull(execution.noteTemplateVersion) &&
      typeof execution.providerMode === "string" &&
      isStringOrNull(execution.syntheticAdmissionId),
  );
}

function classifyProvenance(
  provenance: TemplateTwinClinicalMutationProvenance,
  options: { allowSignedFill?: boolean } = {},
): ProvenanceClassification {
  if (!hasCompleteClinicalMutationProvenance(provenance)) {
    return { kind: "INVALID" };
  }
  const hasTwinTemplate =
    provenance.noteTemplate?.templateKind === "template_twin_docx";
  // Compiled lineage is immutable durable evidence. A mutable templateKind
  // drift cannot reclassify a compiled Twin as an ordinary template.
  const hasCompiledTemplateLineage =
    provenance.noteTemplate?.templateTwinCompiledVersion != null;
  const hasFill = provenance.templateTwinFill != null;
  const hasSynthetic =
    provenance.templateTwinSyntheticQaRun != null ||
    provenance.templateTwinSyntheticQaAdmission != null ||
    provenance.patient.externalId ===
      TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID;
  const providerExecutions = Array.isArray(
    provenance.templateTwinProviderExecutions,
  )
    ? provenance.templateTwinProviderExecutions
    : [];
  const providerExecutionIds = providerExecutions.map(({ id }) => id).sort();
  const hasProviderExecution = providerExecutionIds.length > 0;

  if (
    !hasTwinTemplate &&
    !hasCompiledTemplateLineage &&
    !hasFill &&
    !hasSynthetic &&
    !hasProviderExecution
  ) {
    return { kind: "ORDINARY" };
  }
  if (hasSynthetic) return { kind: "RESTRICTED" };
  if (!hasTwinTemplate || !provenance.noteTemplate) {
    // A detached/mutated template cannot erase an immutable fill's Twin
    // provenance. It is an inconsistent Twin, never an ordinary visit.
    return { kind: "INVALID" };
  }
  if (
    provenance.noteTemplateId !== provenance.noteTemplate.id ||
    provenance.noteTemplateVersion !== provenance.noteTemplate.version
  ) {
    return { kind: "INVALID" };
  }
  const compiled = provenance.noteTemplate.templateTwinCompiledVersion;
  const certification = compiled?.certification;
  if (
    !compiled ||
    compiled.noteTemplateId !== provenance.noteTemplate.id ||
    compiled.sourceArtifactId !== compiled.sourceArtifact.id ||
    compiled.certificationStatus !== "CERTIFIED" ||
    compiled.sourceArtifact.validationStatus !== "accepted" ||
    !certification ||
    certification.compiledVersionId !== compiled.id ||
    certification.certifiedById !== provenance.noteTemplate.doctorId ||
    certification.providerAuthorizationMode !== "LIVE" ||
    certification.providerAuthorizationAdmissionId !== null
  ) {
    return { kind: "INVALID" };
  }
  if (
    providerExecutions.some(
      (execution) =>
        execution.actorUserId !== provenance.noteTemplate!.doctorId ||
        execution.visitId == null ||
        execution.sourceArtifactId !== compiled.sourceArtifact.id ||
        execution.compiledVersionId !== compiled.id ||
        execution.noteTemplateId !== provenance.noteTemplate!.id ||
        execution.noteTemplateVersion !== provenance.noteTemplate!.version ||
        execution.providerMode !== "LIVE" ||
        execution.syntheticAdmissionId !== null,
    )
  ) {
    return { kind: "INVALID" };
  }
  if (
    provenance.templateTwinFill &&
    (provenance.templateTwinFill.noteTemplateId !==
      provenance.noteTemplate.id ||
      provenance.templateTwinFill.compiledVersionId !== compiled.id ||
      provenance.templateTwinFill.noteTemplateVersion !==
        provenance.noteTemplate.version ||
      (!options.allowSignedFill &&
        provenance.templateTwinFill.signedDecisionAt !== null))
  ) {
    return { kind: "INVALID" };
  }
  return {
    kind: "LIVE",
    noteTemplateId: provenance.noteTemplate.id,
    noteTemplateVersion: provenance.noteTemplate.version,
    compiledVersionId: compiled.id,
    sourceArtifactId: compiled.sourceArtifact.id,
    certificationId: certification.id,
    fillManifestId: provenance.templateTwinFill?.id ?? null,
    providerExecutionIds,
  };
}

export function hasDurableTemplateTwinClinicalMutationProvenance(
  provenance: TemplateTwinClinicalMutationProvenance,
): boolean {
  return classifyProvenance(provenance).kind !== "ORDINARY";
}

/** Exact LIVE lineage check without consulting current rollout state. */
export function hasExactLiveTemplateTwinClinicalMutationProvenance(
  provenance: TemplateTwinClinicalMutationProvenance,
): boolean {
  return classifyProvenance(provenance).kind === "LIVE";
}

/** Exact LIVE lineage for archive/restore/retention of signed or unsigned rows. */
export function hasExactLiveTemplateTwinDataLifecycleProvenance(
  provenance: TemplateTwinClinicalMutationProvenance,
): boolean {
  return (
    classifyProvenance(provenance, { allowSignedFill: true }).kind === "LIVE"
  );
}

async function canonicalLiveCompilationIsCurrent(input: {
  client: Pick<Prisma.TransactionClient, "$queryRaw">;
  compiledVersionId: string;
  sourceArtifactId: string;
  certificationId: string;
  actorUserId: string;
  practiceId: string;
}): Promise<boolean> {
  const rows = await input.client.$queryRaw<
    Array<{ valid: boolean }>
  >(Prisma.sql`
    SELECT (
      public.template_twin_live_provider_compilation_is_valid(
        ${input.compiledVersionId}, ${input.actorUserId}
      )
      AND EXISTS (
        SELECT 1
        FROM "template_twin_compiled_versions" compiled
        JOIN "template_twin_source_artifacts" source
          ON source."id" = compiled."sourceArtifactId"
        JOIN "template_twin_certifications" certification
          ON certification."compiledVersionId" = compiled."id"
        WHERE compiled."id" = ${input.compiledVersionId}
          AND source."id" = ${input.sourceArtifactId}
          AND source."practiceId" = ${input.practiceId}
          AND source."validationStatus" = 'accepted'
          AND certification."id" = ${input.certificationId}
          AND certification."certifiedById" = ${input.actorUserId}
          AND certification."providerAuthorizationMode" = 'LIVE'
          AND certification."providerAuthorizationAdmissionId" IS NULL
      )
    ) AS "valid"
  `);
  return rows.length === 1 && rows[0]?.valid === true;
}

/**
 * Admission fence for a generic mutation that has already loaded its target.
 * Ordinary visits return null without consulting Template Twin rollout state.
 * Live Twins receive fresh DB-backed doctor/product/practice and rollout
 * evidence; synthetic, pre-certification, and inconsistent provenance fail
 * closed before clinical state is changed.
 */
export async function pinTemplateTwinClinicalMutation(input: {
  visitId: string;
  actorUserId: string;
  admittedVisitUpdatedAt: Date;
  provenance: TemplateTwinClinicalMutationProvenance;
}): Promise<TemplateTwinClinicalMutationClaim | null> {
  const classified = classifyProvenance(input.provenance);
  if (classified.kind === "ORDINARY") return null;
  if (classified.kind === "RESTRICTED") {
    throw new TemplateTwinClinicalMutationAuthorizationError(
      "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
    );
  }
  if (classified.kind === "INVALID") {
    throw new TemplateTwinClinicalMutationAuthorizationError(
      "TEMPLATE_TWIN_MUTATION_PROVENANCE_INVALID",
    );
  }

  try {
    const doctor = await requireFreshDoctorIdentity(input.actorUserId);
    if (
      input.provenance.noteTemplate?.doctorId !== input.actorUserId ||
      input.provenance.patientId !== input.provenance.patient.id ||
      input.provenance.patient.practiceId !== doctor.practiceId ||
      input.provenance.noteTemplate?.templateTwinCompiledVersion?.sourceArtifact
        .practiceId !== doctor.practiceId ||
      (input.provenance.templateTwinFill !== null &&
        input.provenance.templateTwinFill.practiceId !== doctor.practiceId) ||
      (input.provenance.templateTwinProviderExecutions ?? []).some(
        (execution) =>
          execution.practiceId !== doctor.practiceId ||
          execution.actorUserId !== input.actorUserId ||
          execution.visitId !== input.visitId ||
          execution.noteTemplateId !== classified.noteTemplateId ||
          execution.noteTemplateVersion !== classified.noteTemplateVersion,
      )
    ) {
      throw new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
      );
    }
    if (
      !(await canonicalLiveCompilationIsCurrent({
        client: prisma,
        compiledVersionId: classified.compiledVersionId,
        sourceArtifactId: classified.sourceArtifactId,
        certificationId: classified.certificationId,
        actorUserId: input.actorUserId,
        practiceId: doctor.practiceId,
      }))
    ) {
      throw new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_PROVENANCE_INVALID",
      );
    }
    return {
      visitId: input.visitId,
      actorUserId: input.actorUserId,
      practiceId: doctor.practiceId,
      patientId: input.provenance.patientId,
      noteTemplateId: classified.noteTemplateId,
      noteTemplateVersion: classified.noteTemplateVersion,
      compiledVersionId: classified.compiledVersionId,
      sourceArtifactId: classified.sourceArtifactId,
      certificationId: classified.certificationId,
      fillManifestId: classified.fillManifestId,
      providerExecutionIds: classified.providerExecutionIds,
      visitUpdatedAtEpochMs: input.admittedVisitUpdatedAt.getTime(),
      rolloutToken: doctor.rolloutToken,
    };
  } catch (error) {
    if (error instanceof TemplateTwinClinicalMutationAuthorizationError) {
      throw error;
    }
    if (error instanceof AuthError) {
      throw new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
      );
    }
    throw error;
  }
}

export const TEMPLATE_TWIN_LOCKED_CLINICAL_VISIT_SELECT = {
  id: true,
  userId: true,
  status: true,
  deletedAt: true,
  archivedAt: true,
  signedAt: true,
  updatedAt: true,
  inputMode: true,
  specialty: true,
  chiefComplaint: true,
  rawTextInput: true,
  audioKey: true,
  dictationAudioKey: true,
  soapDraft: true,
  soapFinal: true,
  soapVersion: true,
  speakerMap: true,
  icdCodes: true,
  cptCodes: true,
  rxDrafts: true,
  audioDurationSec: true,
  dictationDurationSec: true,
  manualRetryCount: true,
  ...TEMPLATE_TWIN_CLINICAL_MUTATION_PROVENANCE_SELECT,
} as const;

/**
 * Final transaction-locked authority and provenance claim. Callers must make
 * their target-specific snapshot/CAS checks and mutation in this same
 * transaction. Lock order matches the release control contract:
 * global -> practice -> actor -> template -> compiled -> source ->
 * certification -> patient -> visit -> fill/executions.
 */
export async function lockAndAssertTemplateTwinClinicalMutation(input: {
  tx: Prisma.TransactionClient;
  claim: TemplateTwinClinicalMutationClaim;
}) {
  const finalRollout = await lockTemplateTwinRolloutForFinalClaim({
    tx: input.tx,
    practiceId: input.claim.practiceId,
    pinnedToken: input.claim.rolloutToken,
  });
  if (!finalRollout.allowed) {
    throw new TemplateTwinClinicalMutationAuthorizationError(
      "TEMPLATE_TWIN_MUTATION_ROLLOUT_REVOKED",
    );
  }
  const currentToken = finalRollout.token;
  const pinnedToken = input.claim.rolloutToken;
  if (
    currentToken.practiceId !== pinnedToken.practiceId ||
    currentToken.globalGeneration !== pinnedToken.globalGeneration ||
    currentToken.practiceGeneration !== pinnedToken.practiceGeneration ||
    currentToken.releaseId !== pinnedToken.releaseId ||
    currentToken.releaseIdentitySha256 !== pinnedToken.releaseIdentitySha256 ||
    currentToken.runtimeManifestSha256 !== pinnedToken.runtimeManifestSha256 ||
    currentToken.runtimeInstanceId !== pinnedToken.runtimeInstanceId
  ) {
    throw new TemplateTwinClinicalMutationAuthorizationError(
      "TEMPLATE_TWIN_MUTATION_ROLLOUT_REVOKED",
    );
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
      throw new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
      );
    }
    throw error;
  }

  const templateLock = await input.tx.$queryRaw<Array<{ id: string }>>(
    Prisma.sql`
      SELECT template."id"
      FROM "note_templates" template
      WHERE template."id" = ${input.claim.noteTemplateId}
      FOR UPDATE
    `,
  );
  if (
    templateLock.length !== 1 ||
    templateLock[0]?.id !== input.claim.noteTemplateId
  ) {
    throw new TemplateTwinClinicalMutationAuthorizationError(
      "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
    );
  }
  const compiledLock = await input.tx.$queryRaw<Array<{ id: string }>>(
    Prisma.sql`
      SELECT compiled."id"
      FROM "template_twin_compiled_versions" compiled
      WHERE compiled."id" = ${input.claim.compiledVersionId}
        AND compiled."noteTemplateId" = ${input.claim.noteTemplateId}
      FOR UPDATE
    `,
  );
  if (
    compiledLock.length !== 1 ||
    compiledLock[0]?.id !== input.claim.compiledVersionId
  ) {
    throw new TemplateTwinClinicalMutationAuthorizationError(
      "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
    );
  }
  const sourceLock = await input.tx.$queryRaw<Array<{ id: string }>>(
    Prisma.sql`
      SELECT source."id"
      FROM "template_twin_source_artifacts" source
      WHERE source."id" = ${input.claim.sourceArtifactId}
      FOR UPDATE
    `,
  );
  if (
    sourceLock.length !== 1 ||
    sourceLock[0]?.id !== input.claim.sourceArtifactId
  ) {
    throw new TemplateTwinClinicalMutationAuthorizationError(
      "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
    );
  }
  const certificationLock = await input.tx.$queryRaw<Array<{ id: string }>>(
    Prisma.sql`
      SELECT certification."id"
      FROM "template_twin_certifications" certification
      WHERE certification."id" = ${input.claim.certificationId}
        AND certification."compiledVersionId" = ${input.claim.compiledVersionId}
      FOR UPDATE
    `,
  );
  if (
    certificationLock.length !== 1 ||
    certificationLock[0]?.id !== input.claim.certificationId
  ) {
    throw new TemplateTwinClinicalMutationAuthorizationError(
      "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
    );
  }
  if (
    !(await canonicalLiveCompilationIsCurrent({
      client: input.tx,
      compiledVersionId: input.claim.compiledVersionId,
      sourceArtifactId: input.claim.sourceArtifactId,
      certificationId: input.claim.certificationId,
      actorUserId: input.claim.actorUserId,
      practiceId: input.claim.practiceId,
    }))
  ) {
    throw new TemplateTwinClinicalMutationAuthorizationError(
      "TEMPLATE_TWIN_MUTATION_PROVENANCE_INVALID",
    );
  }
  const patientLock = await input.tx.$queryRaw<
    Array<{ id: string; practiceId: string }>
  >(Prisma.sql`
    SELECT patient."id", patient."practiceId"
    FROM "transcribe_md_patients" patient
    WHERE patient."id" = ${input.claim.patientId}
    FOR UPDATE
  `);
  if (
    patientLock.length !== 1 ||
    patientLock[0]?.id !== input.claim.patientId ||
    patientLock[0]?.practiceId !== input.claim.practiceId
  ) {
    throw new TemplateTwinClinicalMutationAuthorizationError(
      "TEMPLATE_TWIN_MUTATION_PROVENANCE_INVALID",
    );
  }
  const visitLock = await input.tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT visit."id"
    FROM "transcribe_visits" visit
    WHERE visit."id" = ${input.claim.visitId}
      AND visit."userId" = ${input.claim.actorUserId}
    FOR UPDATE
  `);
  if (visitLock.length !== 1 || visitLock[0]?.id !== input.claim.visitId) {
    throw new TemplateTwinClinicalMutationAuthorizationError(
      "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
    );
  }
  if (input.claim.fillManifestId) {
    const fillLock = await input.tx.$queryRaw<Array<{ id: string }>>(
      Prisma.sql`
        SELECT fill."id"
        FROM "template_twin_fill_manifests" fill
        WHERE fill."id" = ${input.claim.fillManifestId}
          AND fill."visitId" = ${input.claim.visitId}
          AND fill."practiceId" = ${input.claim.practiceId}
          AND fill."compiledVersionId" = ${input.claim.compiledVersionId}
          AND fill."noteTemplateId" = ${input.claim.noteTemplateId}
          AND fill."noteTemplateVersion" = ${input.claim.noteTemplateVersion}
        FOR UPDATE
      `,
    );
    if (
      fillLock.length !== 1 ||
      fillLock[0]?.id !== input.claim.fillManifestId
    ) {
      throw new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
      );
    }
  }
  const providerExecutionLocks = await input.tx.$queryRaw<
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
  >(Prisma.sql`
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
  `);
  const lockedProviderExecutionIds = providerExecutionLocks.map(({ id }) => id);
  if (
    lockedProviderExecutionIds.length !==
      input.claim.providerExecutionIds.length ||
    lockedProviderExecutionIds.some(
      (id, index) => id !== input.claim.providerExecutionIds[index],
    ) ||
    providerExecutionLocks.some(
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
    throw new TemplateTwinClinicalMutationAuthorizationError(
      "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
    );
  }

  const visit = await input.tx.transcribeVisit.findUnique({
    where: {
      id: input.claim.visitId,
      userId: input.claim.actorUserId,
    },
    select: TEMPLATE_TWIN_LOCKED_CLINICAL_VISIT_SELECT,
  });
  if (!visit || visit.userId !== input.claim.actorUserId) {
    throw new TemplateTwinClinicalMutationAuthorizationError(
      "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
    );
  }
  const classified = classifyProvenance(visit);
  if (
    classified.kind !== "LIVE" ||
    classified.noteTemplateId !== input.claim.noteTemplateId ||
    classified.noteTemplateVersion !== input.claim.noteTemplateVersion ||
    classified.compiledVersionId !== input.claim.compiledVersionId ||
    classified.sourceArtifactId !== input.claim.sourceArtifactId ||
    classified.certificationId !== input.claim.certificationId ||
    visit.updatedAt.getTime() !== input.claim.visitUpdatedAtEpochMs ||
    visit.patientId !== input.claim.patientId ||
    visit.patient.id !== input.claim.patientId ||
    visit.patient.practiceId !== input.claim.practiceId ||
    classified.fillManifestId !== input.claim.fillManifestId ||
    classified.providerExecutionIds.length !==
      input.claim.providerExecutionIds.length ||
    classified.providerExecutionIds.some(
      (id, index) => id !== input.claim.providerExecutionIds[index],
    ) ||
    visit.noteTemplate?.doctorId !== input.claim.actorUserId ||
    visit.noteTemplate?.templateTwinCompiledVersion?.sourceArtifact
      .practiceId !== input.claim.practiceId ||
    (visit.templateTwinFill !== null &&
      visit.templateTwinFill.practiceId !== input.claim.practiceId) ||
    visit.templateTwinProviderExecutions.some(
      (execution) =>
        execution.practiceId !== input.claim.practiceId ||
        execution.actorUserId !== input.claim.actorUserId ||
        execution.visitId !== input.claim.visitId ||
        execution.noteTemplateId !== input.claim.noteTemplateId ||
        execution.noteTemplateVersion !== input.claim.noteTemplateVersion ||
        execution.providerMode !== "LIVE" ||
        execution.syntheticAdmissionId !== null,
    )
  ) {
    throw new TemplateTwinClinicalMutationAuthorizationError(
      "TEMPLATE_TWIN_MUTATION_PROVENANCE_INVALID",
    );
  }
  return visit;
}
