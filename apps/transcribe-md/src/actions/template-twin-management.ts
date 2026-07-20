"use server";

import { randomUUID } from "node:crypto";

import { Prisma } from "@prisma/client";
import prisma from "@meddoc/db";
import { revalidatePath } from "next/cache";
import { z } from "zod";

import { AuthError, requireDoctorSession } from "@/lib/auth";
import { enqueueTemplateTwinAudit } from "@/lib/template-twin/audit-outbox";
import { lockAndAssertCurrentTemplateTwinPhysician } from "@/lib/template-twin/final-claim-authority";
import {
  lockTemplateTwinRolloutForFinalClaim,
  type TemplateTwinRolloutToken,
} from "@/lib/template-twin/rollout";
import {
  TemplateTwinStagingQaLifecycleGuardError,
  runWithTemplateTwinStagingQaLifecycleGuard,
} from "@/lib/template-twin/staging-qa-lifecycle-guard";
import { createTemplateTwinStagingQaVersionAdmission } from "@/lib/template-twin/staging-qa-version-admission";
import {
  isTemplateTwinSourceAdmissionCurrent,
  TEMPLATE_TWIN_SOURCE_ADMISSION_GATE_MESSAGE,
} from "@/lib/template-twin/source-admission";

type TemplateTwinManagementCode =
  | "INVALID_INPUT"
  | "INVALID_IDENTITY"
  | "NOT_FOUND"
  | "NOT_CERTIFIED"
  | "RETIRED"
  | "SOURCE_UNSAFE"
  | "SOURCE_INCONSISTENT"
  | "INVALID_TRANSITION"
  | "ROLLBACK_REQUIRED"
  | "ROLLBACK_NOT_ALLOWED"
  | "CONFLICT"
  | "ROLLOUT_CHANGED"
  | "FORBIDDEN"
  | "PERSISTENCE_FAILED";

type TemplateTwinManagementFailure = {
  ok: false;
  code: TemplateTwinManagementCode;
  error: string;
};

type TemplateTwinStatusResult =
  | {
      ok: true;
      id: string;
      status: "draft" | "active" | "inactive" | "retired";
      changed: boolean;
    }
  | TemplateTwinManagementFailure;

type TemplateTwinVersionResult =
  | {
      ok: true;
      id: string;
      version: number;
      status: "draft";
    }
  | TemplateTwinManagementFailure;

type TemplateTwinRollbackResult =
  | {
      ok: true;
      id: string;
      status: "active";
      changed: true;
      rolledBackFromVersion: number;
      rolledBackToVersion: number;
    }
  | TemplateTwinManagementFailure;

export type TemplateTwinLineageVersion = {
  id: string;
  version: number;
  name: string;
  encounterType: string;
  versionDescription: string;
  status: "draft" | "active" | "inactive" | "retired";
  certificationStatus:
    | "recognized"
    | "needs_confirmation"
    | "unsupported"
    | "certified"
    | "quarantined";
  certifiedAtIso: string | null;
  compiledAtIso: string;
  compilerVersion: string;
  sourceSha256: string;
  sourceSizeBytes: number;
  sourceMimeType: string;
  rollbackEligible: boolean;
};

type TemplateTwinLineageResult =
  | {
      ok: true;
      lineage: {
        lineageId: string;
        activeVersion: number | null;
        versions: TemplateTwinLineageVersion[];
      };
    }
  | TemplateTwinManagementFailure;

interface TemplateTwinActor {
  userId: string;
  userEmail: string;
  practiceId: string;
  rolloutToken: TemplateTwinRolloutToken;
}

class TemplateTwinManagementError extends Error {
  constructor(
    readonly code: TemplateTwinManagementCode,
    message: string,
  ) {
    super(message);
    this.name = "TemplateTwinManagementError";
  }
}

const TemplateIdSchema = z.string().trim().min(1).max(160);
const NewVersionSchema = z.object({
  sourceNoteTemplateId: TemplateIdSchema,
  name: z.string().trim().min(3).max(120),
  encounterType: z.string().trim().min(3).max(120),
  versionDescription: z.string().trim().min(3).max(500),
});

const OWNED_VERSION_SELECT = {
  id: true,
  doctorId: true,
  name: true,
  encounterType: true,
  versionDescription: true,
  version: true,
  status: true,
  lineageId: true,
  sections: true,
  styleProfile: true,
  specialtyBaseline: true,
  createdAt: true,
  templateTwinCompiledVersion: {
    select: {
      id: true,
      sourceArtifactId: true,
      compilerVersion: true,
      irSchemaVersion: true,
      compiledAt: true,
      compiledDocumentIr: true,
      unsupportedElements: true,
      structureSha256: true,
      staticContentSha256: true,
      certificationStatus: true,
      blockingUnsupportedCount: true,
      certification: {
        select: { id: true, certifiedAt: true },
      },
      sourceArtifact: {
        select: {
          practiceId: true,
          lineageId: true,
          objectVersionId: true,
          objectEtag: true,
          validationStatus: true,
          sha256: true,
          sizeBytes: true,
          mimeType: true,
          quarantineArtifact: {
            select: {
              practiceId: true,
              lineageId: true,
              sha256: true,
              sizeBytes: true,
              status: true,
              intakeMode: true,
              malwareScanEvidence: true,
              metadataMinimizationEvidence: true,
              rejectionCodes: true,
              scannedAt: true,
              admittedAt: true,
            },
          },
        },
      },
      fields: {
        orderBy: { displayOrder: "asc" as const },
        select: {
          fieldId: true,
          displayOrder: true,
          originalLabel: true,
          fieldKind: true,
          allowedOptions: true,
          rendererBinding: true,
          detectionStatus: true,
          clinicallyMaterial: true,
          criticality: true,
          required: true,
          mapping: {
            select: {
              clinicalConcept: true,
              expectedDataType: true,
              polarityBehavior: true,
              temporality: true,
              laterality: true,
              unitPolicy: true,
              approvedSynonyms: true,
              required: true,
              blankPolicy: true,
              unknownPolicy: true,
              practiceDefault: true,
              mappingStatus: true,
              proposedByModel: true,
            },
          },
        },
      },
    },
  },
} satisfies Prisma.NoteTemplateSelect;

type OwnedVersion = Prisma.NoteTemplateGetPayload<{
  select: typeof OWNED_VERSION_SELECT;
}>;

type TemplateTwinReadClient = Pick<Prisma.TransactionClient, "noteTemplate">;

function fail(error: unknown): TemplateTwinManagementFailure {
  if (error instanceof TemplateTwinStagingQaLifecycleGuardError) {
    return {
      ok: false,
      code: "NOT_FOUND",
      error:
        "That Template Twin version does not exist or is not available to this practice.",
    };
  }
  if (error instanceof TemplateTwinManagementError) {
    return { ok: false, code: error.code, error: error.message };
  }
  if (error instanceof AuthError) {
    return {
      ok: false,
      code: "FORBIDDEN",
      error:
        error.code === "UNAUTHENTICATED"
          ? "Sign in again before managing Template Twin."
          : error.message,
    };
  }
  if (
    error instanceof Prisma.PrismaClientKnownRequestError &&
    error.code === "P2002"
  ) {
    return {
      ok: false,
      code: "CONFLICT",
      error:
        "This template lineage changed in another request. Reload and try again.",
    };
  }
  return {
    ok: false,
    code: "PERSISTENCE_FAILED",
    error:
      "Template Twin could not complete that change. Nothing was partially activated.",
  };
}

async function currentActor(): Promise<TemplateTwinActor> {
  // requireDoctorSession performs a fresh database role/practice read and the
  // fail-closed global + practice rollout checks. JWT claims alone are never
  // sufficient for these lifecycle mutations.
  const session = await requireDoctorSession();
  return {
    userId: session.user.id,
    userEmail: session.user.email,
    practiceId: session.user.practiceId,
    rolloutToken: session.templateTwinRolloutToken,
  };
}

async function runManagementStagingGuard<T>(input: {
  noteTemplateId: string;
  actor: TemplateTwinActor;
  purpose: string;
  operation: () => Promise<T>;
}): Promise<T> {
  return runWithTemplateTwinStagingQaLifecycleGuard({
    noteTemplateId: input.noteTemplateId,
    actor: input.actor,
    purpose: input.purpose,
    isExpectedBusinessError: (error) =>
      error instanceof TemplateTwinManagementError ||
      (error instanceof Prisma.PrismaClientKnownRequestError &&
        error.code === "P2002"),
    operation: input.operation,
  });
}

async function assertManagementRolloutFinality(
  tx: Prisma.TransactionClient,
  actor: TemplateTwinActor,
  operation: string,
): Promise<void> {
  const decision = await lockTemplateTwinRolloutForFinalClaim({
    tx,
    practiceId: actor.practiceId,
    pinnedToken: actor.rolloutToken,
  });
  if (!decision.allowed) {
    throw new TemplateTwinManagementError(
      "ROLLOUT_CHANGED",
      `${decision.code}: Template Twin availability changed while ${operation}. Reload and try again.`,
    );
  }
}

async function lockAndAssertManagementAuthority(
  tx: Prisma.TransactionClient,
  actor: TemplateTwinActor,
): Promise<{ email: string }> {
  // assertManagementRolloutFinality has already acquired the canonical global
  // then practice locks and proved that the practice is active. Take the actor
  // lock last so a concurrent suspension, demotion, product revocation, or
  // practice transfer is ordered against the same transaction as the write.
  return lockAndAssertCurrentTemplateTwinPhysician({ tx, actor });
}

async function loadOwnedVersion(
  client: TemplateTwinReadClient,
  noteTemplateId: string,
  actor: TemplateTwinActor,
): Promise<OwnedVersion> {
  const row = await client.noteTemplate.findFirst({
    where: {
      id: noteTemplateId,
      doctorId: actor.userId,
      templateKind: "template_twin_docx",
    },
    select: OWNED_VERSION_SELECT,
  });
  if (
    !row?.templateTwinCompiledVersion ||
    row.templateTwinCompiledVersion.sourceArtifact.practiceId !==
      actor.practiceId
  ) {
    throw new TemplateTwinManagementError(
      "NOT_FOUND",
      "That Template Twin version does not exist or is not available to this practice.",
    );
  }
  return row;
}

function compiled(row: OwnedVersion) {
  const value = row.templateTwinCompiledVersion;
  if (!value) {
    throw new TemplateTwinManagementError(
      "SOURCE_INCONSISTENT",
      "This Template Twin version has no compiled structure and cannot be managed.",
    );
  }
  return value;
}

function assertAcceptedSource(row: OwnedVersion): void {
  if (!isTemplateTwinSourceAdmissionCurrent(compiled(row).sourceArtifact)) {
    throw new TemplateTwinManagementError(
      "SOURCE_UNSAFE",
      TEMPLATE_TWIN_SOURCE_ADMISSION_GATE_MESSAGE,
    );
  }
}

function assertCertified(row: OwnedVersion): void {
  const version = compiled(row);
  if (version.certificationStatus !== "CERTIFIED" || !version.certification) {
    throw new TemplateTwinManagementError(
      "NOT_CERTIFIED",
      "This version must pass synthetic testing and physician certification before activation.",
    );
  }
}

function assertActivationIdentity(row: OwnedVersion): void {
  if (
    row.name.trim().length < 3 ||
    !row.encounterType ||
    row.encounterType.trim().length < 3 ||
    !row.versionDescription ||
    row.versionDescription.trim().length < 3
  ) {
    throw new TemplateTwinManagementError(
      "INVALID_IDENTITY",
      "Name the template, choose its visit scope, and describe this version before activation.",
    );
  }
}

function asInputJson(value: Prisma.JsonValue): Prisma.InputJsonValue {
  return value as Prisma.InputJsonValue;
}

function publicStatus(value: string): TemplateTwinLineageVersion["status"] {
  if (
    value === "draft" ||
    value === "active" ||
    value === "inactive" ||
    value === "retired"
  ) {
    return value;
  }
  // Unknown legacy states are never treated as active/eligible.
  return "inactive";
}

function certificationStatus(
  value: string,
): TemplateTwinLineageVersion["certificationStatus"] {
  const lowered = value.toLowerCase();
  if (
    lowered === "recognized" ||
    lowered === "needs_confirmation" ||
    lowered === "unsupported" ||
    lowered === "certified" ||
    lowered === "quarantined"
  ) {
    return lowered;
  }
  return "needs_confirmation";
}

function revalidateTemplateManagement(): void {
  revalidatePath("/settings");
  revalidatePath("/settings/note-format");
}

/**
 * Fork a certified immutable version into a new draft while reusing the exact
 * immutable source artifact. Structure and mappings are copied, but every
 * approval, synthetic proof, waiver, and certification is deliberately reset.
 */
export async function createTemplateTwinVersionAction(
  rawInput: unknown,
): Promise<TemplateTwinVersionResult> {
  try {
    const actor = await currentActor();
    const input = NewVersionSchema.safeParse(rawInput);
    if (!input.success) {
      throw new TemplateTwinManagementError(
        "INVALID_IDENTITY",
        "Name the template, choose its visit scope, and describe this version.",
      );
    }

    const noteTemplateId = randomUUID();
    const compiledVersionId = randomUUID();
    const result = await runManagementStagingGuard<{ version: number }>({
      noteTemplateId: input.data.sourceNoteTemplateId,
      actor,
      purpose: "management-create-version",
      operation: () =>
        prisma.$transaction(
          async (tx: Prisma.TransactionClient) => {
            await assertManagementRolloutFinality(
              tx,
              actor,
              "the new template version was being created",
            );
            const currentActor = await lockAndAssertManagementAuthority(
              tx,
              actor,
            );
            const source = await loadOwnedVersion(
              tx,
              input.data.sourceNoteTemplateId,
              actor,
            );
            assertAcceptedSource(source);
            assertCertified(source);
            const sourceCompiled = compiled(source);
            if (source.encounterType !== input.data.encounterType) {
              throw new TemplateTwinManagementError(
                "INVALID_IDENTITY",
                "A version must keep the same visit scope. Upload a separate template to create a new scope.",
              );
            }

            const latest = await tx.noteTemplate.findFirst({
              where: {
                doctorId: actor.userId,
                lineageId: source.lineageId,
                templateKind: "template_twin_docx",
              },
              orderBy: { version: "desc" },
              select: { version: true },
            });
            if (!latest) {
              throw new TemplateTwinManagementError(
                "SOURCE_INCONSISTENT",
                "This Template Twin lineage could not be verified.",
              );
            }
            const nextVersion = latest.version + 1;

            await tx.noteTemplate.create({
              data: {
                id: noteTemplateId,
                doctorId: actor.userId,
                name: input.data.name,
                encounterType: input.data.encounterType,
                sections: asInputJson(source.sections),
                ...(source.styleProfile === null
                  ? {}
                  : { styleProfile: asInputJson(source.styleProfile) }),
                specialtyBaseline: source.specialtyBaseline,
                version: nextVersion,
                versionDescription: input.data.versionDescription,
                status: "draft",
                isSystemDefault: false,
                lineageId: source.lineageId,
                parentVersionId: source.id,
                templateKind: "template_twin_docx",
              },
              select: { id: true },
            });

            const fieldCreates = sourceCompiled.fields.map((field) => {
              if (!field.mapping) {
                throw new TemplateTwinManagementError(
                  "SOURCE_INCONSISTENT",
                  "A certified field is missing its semantic mapping.",
                );
              }
              const unsupported =
                field.detectionStatus === "UNSUPPORTED" ||
                field.mapping.mappingStatus === "UNSUPPORTED";
              return {
                fieldId: field.fieldId,
                displayOrder: field.displayOrder,
                originalLabel: field.originalLabel,
                fieldKind: field.fieldKind,
                ...(field.allowedOptions === null
                  ? {}
                  : { allowedOptions: asInputJson(field.allowedOptions) }),
                rendererBinding: asInputJson(field.rendererBinding),
                detectionStatus: unsupported
                  ? ("UNSUPPORTED" as const)
                  : ("NEEDS_CONFIRMATION" as const),
                clinicallyMaterial: field.clinicallyMaterial,
                criticality: field.criticality,
                required: field.required,
                mapping: {
                  create: {
                    clinicalConcept: field.mapping.clinicalConcept,
                    expectedDataType: field.mapping.expectedDataType,
                    polarityBehavior: field.mapping.polarityBehavior,
                    temporality: field.mapping.temporality,
                    laterality: field.mapping.laterality,
                    unitPolicy: field.mapping.unitPolicy,
                    approvedSynonyms: asInputJson(
                      field.mapping.approvedSynonyms,
                    ),
                    required: field.mapping.required,
                    blankPolicy: field.mapping.blankPolicy,
                    unknownPolicy: field.mapping.unknownPolicy,
                    practiceDefault: field.mapping.practiceDefault,
                    mappingStatus: unsupported
                      ? ("UNSUPPORTED" as const)
                      : ("NEEDS_CONFIRMATION" as const),
                    proposedByModel: field.mapping.proposedByModel,
                    approvedById: null,
                    approvedAt: null,
                  },
                },
              };
            });

            await tx.templateTwinCompiledVersion.create({
              data: {
                id: compiledVersionId,
                sourceArtifactId: sourceCompiled.sourceArtifactId,
                noteTemplateId,
                compilerVersion: sourceCompiled.compilerVersion,
                irSchemaVersion: sourceCompiled.irSchemaVersion,
                compiledDocumentIr: asInputJson(
                  sourceCompiled.compiledDocumentIr,
                ),
                unsupportedElements: asInputJson(
                  sourceCompiled.unsupportedElements,
                ),
                structureSha256: sourceCompiled.structureSha256,
                staticContentSha256: sourceCompiled.staticContentSha256,
                certificationStatus:
                  sourceCompiled.blockingUnsupportedCount > 0
                    ? "UNSUPPORTED"
                    : "NEEDS_CONFIRMATION",
                blockingUnsupportedCount:
                  sourceCompiled.blockingUnsupportedCount,
                fields: { create: fieldCreates },
              },
              select: { id: true },
            });

            await createTemplateTwinStagingQaVersionAdmission({
              tx,
              actor: {
                userId: actor.userId,
                userEmail: currentActor.email,
                practiceId: actor.practiceId,
                rolloutToken: actor.rolloutToken,
              },
              source: {
                noteTemplateId: source.id,
                sourceArtifactId: sourceCompiled.sourceArtifactId,
                sha256: sourceCompiled.sourceArtifact.sha256,
                sizeBytes: sourceCompiled.sourceArtifact.sizeBytes,
                intakeSha256:
                  sourceCompiled.sourceArtifact.quarantineArtifact?.status ===
                    "ADMITTED" &&
                  sourceCompiled.sourceArtifact.quarantineArtifact
                    .intakeMode === "NATIVE_TEMPLATE"
                    ? sourceCompiled.sourceArtifact.quarantineArtifact.sha256
                    : null,
                intakeSizeBytes:
                  sourceCompiled.sourceArtifact.quarantineArtifact?.status ===
                    "ADMITTED" &&
                  sourceCompiled.sourceArtifact.quarantineArtifact
                    .intakeMode === "NATIVE_TEMPLATE"
                    ? sourceCompiled.sourceArtifact.quarantineArtifact.sizeBytes
                    : null,
              },
              target: { noteTemplateId, version: nextVersion },
            });

            await enqueueTemplateTwinAudit(tx, {
              eventKey: `template-twin:compiled:${compiledVersionId}:v${nextVersion}`,
              practiceId: actor.practiceId,
              actorId: actor.userId,
              actorEmailSnapshot: currentActor.email,
              action: "TEMPLATE_TWIN_COMPILED",
              targetType: "TemplateTwinCompiledVersion",
              targetId: compiledVersionId,
              metadata: {
                templateVersion: nextVersion,
                parentVersion: source.version,
                sourceArtifactId: sourceCompiled.sourceArtifactId,
                structureSha256: sourceCompiled.structureSha256,
                fieldCount: fieldCreates.length,
                certificationReset: true,
                rolloutGlobalGeneration:
                  actor.rolloutToken.globalGeneration.toString(),
                rolloutPracticeGeneration:
                  actor.rolloutToken.practiceGeneration.toString(),
              },
            });
            return { version: nextVersion };
          },
          // Compiled-lineage triggers intentionally require READ COMMITTED so a
          // post-advisory-lock ownership read cannot use a stale transaction
          // snapshot. The lineage/version unique constraints still make a losing
          // concurrent fork fail closed.
          { isolationLevel: "ReadCommitted" },
        ),
    });

    revalidateTemplateManagement();
    return {
      ok: true,
      id: noteTemplateId,
      version: result.version,
      status: "draft",
    };
  } catch (error) {
    return fail(error);
  }
}

export async function activateTemplateTwinVersionAction(
  rawId: unknown,
): Promise<TemplateTwinStatusResult> {
  try {
    const actor = await currentActor();
    const id = TemplateIdSchema.safeParse(rawId);
    if (!id.success) {
      throw new TemplateTwinManagementError(
        "INVALID_INPUT",
        "Choose a valid template version.",
      );
    }
    const operationId = randomUUID();
    const result = await runManagementStagingGuard<{ changed: boolean }>({
      noteTemplateId: id.data,
      actor,
      purpose: "management-activate",
      operation: () =>
        prisma.$transaction(
          async (tx: Prisma.TransactionClient) => {
            await assertManagementRolloutFinality(
              tx,
              actor,
              "the template version was being activated",
            );
            const currentActor = await lockAndAssertManagementAuthority(
              tx,
              actor,
            );
            const target = await loadOwnedVersion(tx, id.data, actor);
            if (target.status === "retired") {
              throw new TemplateTwinManagementError(
                "RETIRED",
                "A retired Template Twin version cannot be activated.",
              );
            }
            assertAcceptedSource(target);
            assertCertified(target);
            assertActivationIdentity(target);
            if (target.status === "active") return { changed: false };

            const current = await tx.noteTemplate.findFirst({
              where: {
                doctorId: actor.userId,
                encounterType: target.encounterType,
                status: "active",
              },
              select: { id: true, lineageId: true, version: true },
            });
            if (
              current?.lineageId === target.lineageId &&
              current.version > target.version
            ) {
              throw new TemplateTwinManagementError(
                "ROLLBACK_REQUIRED",
                "Use the explicit rollback action to restore an older certified version.",
              );
            }
            await tx.noteTemplate.updateMany({
              where: {
                doctorId: actor.userId,
                encounterType: target.encounterType,
                status: "active",
                NOT: { id: target.id },
              },
              data: { status: "inactive" },
            });
            const activated = await tx.noteTemplate.updateMany({
              where: {
                id: target.id,
                doctorId: actor.userId,
                status: { in: ["draft", "inactive"] },
              },
              data: { status: "active" },
            });
            if (activated.count !== 1) {
              throw new TemplateTwinManagementError(
                "CONFLICT",
                "This version changed in another request. Reload before activating.",
              );
            }
            await enqueueTemplateTwinAudit(tx, {
              eventKey: `template-twin:activated:${target.id}:${operationId}`,
              practiceId: actor.practiceId,
              actorId: actor.userId,
              actorEmailSnapshot: currentActor.email,
              action: "TEMPLATE_TWIN_ACTIVATED",
              targetType: "NoteTemplate",
              targetId: target.id,
              metadata: {
                templateVersion: target.version,
                compiledVersionId: compiled(target).id,
                previousActiveId: current?.id ?? null,
                rolloutGlobalGeneration:
                  actor.rolloutToken.globalGeneration.toString(),
                rolloutPracticeGeneration:
                  actor.rolloutToken.practiceGeneration.toString(),
              },
            });
            return { changed: true };
          },
          { isolationLevel: "Serializable" },
        ),
    });
    if (result.changed) revalidateTemplateManagement();
    return { ok: true, id: id.data, status: "active", changed: result.changed };
  } catch (error) {
    return fail(error);
  }
}

export async function deactivateTemplateTwinVersionAction(
  rawId: unknown,
): Promise<TemplateTwinStatusResult> {
  try {
    const actor = await currentActor();
    const id = TemplateIdSchema.safeParse(rawId);
    if (!id.success) {
      throw new TemplateTwinManagementError(
        "INVALID_INPUT",
        "Choose a valid template version.",
      );
    }
    const operationId = randomUUID();
    const result = await runManagementStagingGuard<{ changed: boolean }>({
      noteTemplateId: id.data,
      actor,
      purpose: "management-deactivate",
      operation: () =>
        prisma.$transaction(
          async (tx: Prisma.TransactionClient) => {
            await assertManagementRolloutFinality(
              tx,
              actor,
              "the template version was being deactivated",
            );
            const currentActor = await lockAndAssertManagementAuthority(
              tx,
              actor,
            );
            const target = await loadOwnedVersion(tx, id.data, actor);
            if (target.status === "retired") {
              throw new TemplateTwinManagementError(
                "RETIRED",
                "This Template Twin version is already retired.",
              );
            }
            if (target.status === "inactive") return { changed: false };
            if (target.status !== "active") {
              throw new TemplateTwinManagementError(
                "INVALID_TRANSITION",
                "Only the active Template Twin version can be deactivated.",
              );
            }
            const changed = await tx.noteTemplate.updateMany({
              where: {
                id: target.id,
                doctorId: actor.userId,
                status: "active",
              },
              data: { status: "inactive" },
            });
            if (changed.count !== 1) {
              throw new TemplateTwinManagementError(
                "CONFLICT",
                "This version changed in another request. Reload before deactivating.",
              );
            }
            await enqueueTemplateTwinAudit(tx, {
              eventKey: `template-twin:deactivated:${target.id}:${operationId}`,
              practiceId: actor.practiceId,
              actorId: actor.userId,
              actorEmailSnapshot: currentActor.email,
              action: "TEMPLATE_TWIN_DEACTIVATED",
              targetType: "NoteTemplate",
              targetId: target.id,
              metadata: {
                templateVersion: target.version,
                compiledVersionId: compiled(target).id,
              },
            });
            return { changed: true };
          },
          { isolationLevel: "Serializable" },
        ),
    });
    if (result.changed) revalidateTemplateManagement();
    return {
      ok: true,
      id: id.data,
      status: "inactive",
      changed: result.changed,
    };
  } catch (error) {
    return fail(error);
  }
}

export async function retireTemplateTwinVersionAction(
  rawId: unknown,
): Promise<TemplateTwinStatusResult> {
  try {
    const actor = await currentActor();
    const id = TemplateIdSchema.safeParse(rawId);
    if (!id.success) {
      throw new TemplateTwinManagementError(
        "INVALID_INPUT",
        "Choose a valid template version.",
      );
    }
    const operationId = randomUUID();
    const result = await runManagementStagingGuard<{ changed: boolean }>({
      noteTemplateId: id.data,
      actor,
      purpose: "management-retire",
      operation: () =>
        prisma.$transaction(
          async (tx: Prisma.TransactionClient) => {
            await assertManagementRolloutFinality(
              tx,
              actor,
              "the template version was being retired",
            );
            const currentActor = await lockAndAssertManagementAuthority(
              tx,
              actor,
            );
            const target = await loadOwnedVersion(tx, id.data, actor);
            if (target.status === "retired") return { changed: false };
            const wasActive = target.status === "active";
            const changed = await tx.noteTemplate.updateMany({
              where: {
                id: target.id,
                doctorId: actor.userId,
                status: { not: "retired" },
              },
              data: { status: "retired" },
            });
            if (changed.count !== 1) {
              throw new TemplateTwinManagementError(
                "CONFLICT",
                "This version changed in another request. Reload before retiring.",
              );
            }
            if (wasActive) {
              await enqueueTemplateTwinAudit(tx, {
                eventKey: `template-twin:deactivated:${target.id}:${operationId}`,
                practiceId: actor.practiceId,
                actorId: actor.userId,
                actorEmailSnapshot: currentActor.email,
                action: "TEMPLATE_TWIN_DEACTIVATED",
                targetType: "NoteTemplate",
                targetId: target.id,
                metadata: {
                  templateVersion: target.version,
                  compiledVersionId: compiled(target).id,
                  reasonCode: "VERSION_RETIRED",
                },
              });
            }
            await enqueueTemplateTwinAudit(tx, {
              eventKey: `template-twin:retired:${target.id}:${operationId}`,
              practiceId: actor.practiceId,
              actorId: actor.userId,
              actorEmailSnapshot: currentActor.email,
              action: "TEMPLATE_TWIN_RETIRED",
              targetType: "NoteTemplate",
              targetId: target.id,
              metadata: {
                templateVersion: target.version,
                compiledVersionId: compiled(target).id,
                priorStatus: publicStatus(target.status),
              },
            });
            return { changed: true };
          },
          { isolationLevel: "Serializable" },
        ),
    });
    if (result.changed) revalidateTemplateManagement();
    return {
      ok: true,
      id: id.data,
      status: "retired",
      changed: result.changed,
    };
  } catch (error) {
    return fail(error);
  }
}

export async function inspectTemplateTwinLineageAction(
  rawId: unknown,
): Promise<TemplateTwinLineageResult> {
  try {
    const actor = await currentActor();
    const id = TemplateIdSchema.safeParse(rawId);
    if (!id.success) {
      throw new TemplateTwinManagementError(
        "INVALID_INPUT",
        "Choose a valid template version.",
      );
    }
    return await runManagementStagingGuard({
      noteTemplateId: id.data,
      actor,
      purpose: "management-lineage-read",
      operation: async () => {
        const seed = await loadOwnedVersion(prisma, id.data, actor);
        const rows: OwnedVersion[] = await prisma.noteTemplate.findMany({
          where: {
            doctorId: actor.userId,
            lineageId: seed.lineageId,
            templateKind: "template_twin_docx",
          },
          select: OWNED_VERSION_SELECT,
          orderBy: { version: "desc" },
        });
        if (
          rows.length === 0 ||
          rows.some(
            (row) =>
              !row.templateTwinCompiledVersion ||
              row.templateTwinCompiledVersion.sourceArtifact.practiceId !==
                actor.practiceId,
          )
        ) {
          throw new TemplateTwinManagementError(
            "SOURCE_INCONSISTENT",
            "This Template Twin lineage crosses an invalid practice boundary.",
          );
        }
        const ordered = [...rows].sort(
          (left, right) => right.version - left.version,
        );
        const activeVersion =
          ordered.find((row) => row.status === "active")?.version ?? null;
        return {
          ok: true,
          lineage: {
            lineageId: seed.lineageId,
            activeVersion,
            versions: ordered.map((row) => {
              const rowCompiled = compiled(row);
              const hasIdentity = Boolean(
                row.name.trim().length >= 3 &&
                row.encounterType &&
                row.encounterType.trim().length >= 3 &&
                row.versionDescription &&
                row.versionDescription.trim().length >= 3,
              );
              return {
                id: row.id,
                version: row.version,
                name: row.name,
                encounterType: row.encounterType ?? "",
                versionDescription: row.versionDescription ?? "",
                status: publicStatus(row.status),
                certificationStatus: certificationStatus(
                  rowCompiled.certificationStatus,
                ),
                certifiedAtIso:
                  rowCompiled.certification?.certifiedAt.toISOString() ?? null,
                compiledAtIso: rowCompiled.compiledAt.toISOString(),
                compilerVersion: rowCompiled.compilerVersion,
                sourceSha256: rowCompiled.sourceArtifact.sha256,
                sourceSizeBytes: rowCompiled.sourceArtifact.sizeBytes,
                sourceMimeType: rowCompiled.sourceArtifact.mimeType,
                rollbackEligible: Boolean(
                  activeVersion !== null &&
                  row.version < activeVersion &&
                  row.status === "inactive" &&
                  rowCompiled.certificationStatus === "CERTIFIED" &&
                  rowCompiled.certification &&
                  isTemplateTwinSourceAdmissionCurrent(
                    rowCompiled.sourceArtifact,
                  ) &&
                  hasIdentity,
                ),
              };
            }),
          },
        };
      },
    });
  } catch (error) {
    return fail(error);
  }
}

export async function rollbackTemplateTwinVersionAction(
  rawId: unknown,
): Promise<TemplateTwinRollbackResult> {
  try {
    const actor = await currentActor();
    const id = TemplateIdSchema.safeParse(rawId);
    if (!id.success) {
      throw new TemplateTwinManagementError(
        "INVALID_INPUT",
        "Choose a valid template version.",
      );
    }
    const operationId = randomUUID();
    const result = await runManagementStagingGuard<{
      fromVersion: number;
      toVersion: number;
    }>({
      noteTemplateId: id.data,
      actor,
      purpose: "management-rollback",
      operation: () =>
        prisma.$transaction(
          async (tx: Prisma.TransactionClient) => {
            await assertManagementRolloutFinality(
              tx,
              actor,
              "the prior template version was being restored",
            );
            const currentActor = await lockAndAssertManagementAuthority(
              tx,
              actor,
            );
            const target = await loadOwnedVersion(tx, id.data, actor);
            if (target.status === "retired") {
              throw new TemplateTwinManagementError(
                "RETIRED",
                "A retired version cannot be restored. Create a new version instead.",
              );
            }
            assertAcceptedSource(target);
            assertCertified(target);
            assertActivationIdentity(target);
            if (target.status !== "inactive") {
              throw new TemplateTwinManagementError(
                "ROLLBACK_NOT_ALLOWED",
                "Rollback requires an inactive, previously certified version.",
              );
            }
            const current = await tx.noteTemplate.findFirst({
              where: {
                doctorId: actor.userId,
                encounterType: target.encounterType,
                status: "active",
              },
              select: { id: true, lineageId: true, version: true },
            });
            if (
              !current ||
              current.lineageId !== target.lineageId ||
              current.version <= target.version
            ) {
              throw new TemplateTwinManagementError(
                "ROLLBACK_NOT_ALLOWED",
                "Choose an older certified version from the currently active lineage.",
              );
            }

            const deactivated = await tx.noteTemplate.updateMany({
              where: {
                id: current.id,
                doctorId: actor.userId,
                status: "active",
                lineageId: target.lineageId,
              },
              data: { status: "inactive" },
            });
            const activated = await tx.noteTemplate.updateMany({
              where: {
                id: target.id,
                doctorId: actor.userId,
                status: "inactive",
                lineageId: target.lineageId,
              },
              data: { status: "active" },
            });
            if (deactivated.count !== 1 || activated.count !== 1) {
              throw new TemplateTwinManagementError(
                "CONFLICT",
                "This lineage changed in another request. Reload before rolling back.",
              );
            }

            await enqueueTemplateTwinAudit(tx, {
              eventKey: `template-twin:rolled-back:${target.id}:${operationId}`,
              practiceId: actor.practiceId,
              actorId: actor.userId,
              actorEmailSnapshot: currentActor.email,
              action: "TEMPLATE_TWIN_ROLLED_BACK",
              targetType: "NoteTemplate",
              targetId: target.id,
              metadata: {
                fromTemplateId: current.id,
                fromVersion: current.version,
                toVersion: target.version,
                compiledVersionId: compiled(target).id,
              },
            });
            await enqueueTemplateTwinAudit(tx, {
              eventKey: `template-twin:activated:${target.id}:${operationId}`,
              practiceId: actor.practiceId,
              actorId: actor.userId,
              actorEmailSnapshot: currentActor.email,
              action: "TEMPLATE_TWIN_ACTIVATED",
              targetType: "NoteTemplate",
              targetId: target.id,
              metadata: {
                templateVersion: target.version,
                compiledVersionId: compiled(target).id,
                activationReason: "ROLLBACK",
              },
            });
            return {
              fromVersion: current.version,
              toVersion: target.version,
            };
          },
          { isolationLevel: "Serializable" },
        ),
    });

    revalidateTemplateManagement();
    return {
      ok: true,
      id: id.data,
      status: "active",
      changed: true,
      rolledBackFromVersion: result.fromVersion,
      rolledBackToVersion: result.toVersion,
    };
  } catch (error) {
    return fail(error);
  }
}
