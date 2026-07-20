import {
  assertTemplateTwinSyntheticQaWorkerLeaseHealthy,
  getTemplateTwinSyntheticQaProviderContext,
  modelClient,
  transcribe,
  type AnthropicCompleteTextResult,
  type CompleteArgs,
  type CompleteTextArgs,
  type TranscribeArgs,
  type TranscribeResult,
} from "@meddoc/ai";
import prisma from "@meddoc/db";
import { Prisma } from "@prisma/client";
import { AsyncLocalStorage } from "node:async_hooks";
import { createHash, randomBytes, randomUUID } from "node:crypto";
import { z } from "zod";

import { canonicalSha256 } from "@/lib/template-twin/canonical";
import {
  evaluateTemplateTwinRollout,
  lockTemplateTwinRolloutForFinalClaim,
  type TemplateTwinRolloutToken,
} from "@/lib/template-twin/rollout";
import { templateTwinVisitProviderSubjectSha256 } from "./live-provider-ownership";
import {
  getTemplateTwinProviderCensusDecision,
  templateTwinProviderOwnershipRequiredByCensus,
} from "./provider-census";

export const TEMPLATE_TWIN_PROVIDER_RESULT_VERSION =
  "template-twin-provider-result-v1" as const;
export const TEMPLATE_TWIN_PROVIDER_RECEIPT_VERSION =
  "template-twin-provider-ownership-receipt-v2" as const;

export type TemplateTwinProviderScope =
  | "SOURCE_INTAKE"
  | "VISIT_PIPELINE"
  | "STATIC_ASSET"
  | "CUSTOM_EXAMPLE"
  | "SYNTHETIC_EVIDENCE";

export type TemplateTwinProviderOperation =
  | "SOURCE_PHI_SCAN"
  | "SOURCE_SEMANTIC_MAPPING"
  | "STATIC_ASSET_PRIVACY_SCAN"
  | "SYNTHETIC_EVIDENCE_PRIVACY_SCAN"
  | "SYNTHETIC_EVIDENCE_TRANSCRIPTION"
  | "SYNTHETIC_EVIDENCE_EXTRACTION"
  | "CUSTOM_EXAMPLE_EXTRACTION"
  | "CUSTOM_CONCEPT_EXTRACTION"
  | "L1_TRANSCRIBE"
  | "L1B_TRANSCRIBE"
  | "L2_SPEAKER_ROLES"
  | "L3_EXTRACT_ENTITIES"
  | "L4_GENERATE_SOAP"
  | "L4_ANCHOR_VERIFY"
  | "L5_SELF_CRITIQUE"
  | "L6_POLISH"
  | "L6_FIDELITY_VERIFY";

export type TemplateTwinProviderMode =
  | "LIVE"
  | "DETERMINISTIC_MOCK"
  | "SYNTHETIC_QA";

export interface TemplateTwinProviderOwnershipContext {
  readonly practiceId: string;
  readonly actorUserId: string;
  readonly visitId: string | null;
  /** Exact persisted TranscribeVisit input mode when visitId is present. */
  readonly visitInputMode: string | null;
  readonly scope: TemplateTwinProviderScope;
  /** Stable business attempt, not a BullMQ delivery/retry number. */
  readonly logicalAttempt: number;
  readonly subjectId: string;
  readonly subjectSha256: string;
  readonly sourceArtifactId: string | null;
  readonly compiledVersionId: string | null;
  readonly noteTemplateId: string | null;
  readonly noteTemplateVersion: number | null;
  readonly sourceLineageId: string | null;
  readonly sourceLineageVersion: number | null;
  readonly sourceSha256: string | null;
  readonly syntheticAdmissionId: string | null;
  readonly rolloutToken: TemplateTwinRolloutToken;
}

export interface TemplateTwinSyntheticVoiceSubjectIdentity {
  readonly admissionId: string;
  readonly parentAdmissionId: string;
  readonly practiceId: string;
  readonly actorUserId: string;
  readonly visitId: string;
  readonly inputMode: "audio_upload";
  readonly audioSha256: string;
  readonly audioSizeBytes: number;
  readonly audioMimeType: string;
  readonly audioObjectKey: string;
  readonly sourceArtifactId: string;
  readonly compiledVersionId: string;
  readonly noteTemplateId: string;
  readonly noteTemplateVersion: number;
  readonly sourceLineageId: string;
  readonly sourceLineageVersion: number;
  readonly sourceSha256: string;
  readonly logicalAttempt: 1;
}

export function templateTwinSyntheticVoiceSubjectSha256(
  input: TemplateTwinSyntheticVoiceSubjectIdentity,
): string {
  return canonicalSha256({
    contractVersion: "template-twin-synthetic-voice-subject-v1",
    ...input,
  });
}

export interface TemplateTwinProviderReceiptProjection {
  readonly subjectId: string;
  readonly subjectSha256: string;
  readonly visitId: string | null;
  readonly sourceArtifactId: string | null;
  readonly compiledVersionId: string | null;
  readonly noteTemplateId: string | null;
}

export interface TemplateTwinProviderExpectedPlanEntry {
  readonly operation: TemplateTwinProviderOperation;
  readonly operationInstance?: string;
  readonly disposition: "EXECUTED" | "NOT_APPLICABLE";
  readonly reasonCode?: string;
}

export interface TemplateTwinProviderOwnershipReceipt {
  readonly evidence: {
    readonly contractVersion: typeof TEMPLATE_TWIN_PROVIDER_RECEIPT_VERSION;
    readonly scope: TemplateTwinProviderScope;
    readonly practiceId: string;
    readonly actorUserId: string;
    readonly subjectId: string;
    readonly subjectSha256: string;
    readonly visitId: string | null;
    readonly sourceArtifactId: string | null;
    readonly compiledVersionId: string | null;
    readonly noteTemplateId: string | null;
    readonly noteTemplateVersion: number | null;
    readonly visitInputMode: string | null;
    readonly logicalAttempt: number;
    readonly sourceLineageId: string | null;
    readonly sourceLineageVersion: number | null;
    readonly sourceSha256: string | null;
    readonly providerMode: TemplateTwinProviderMode;
    readonly pinnedGlobalRolloutGeneration: string;
    readonly pinnedPracticeRolloutGeneration: string;
    readonly releaseId: string | null;
    readonly releaseIdentitySha256: string | null;
    readonly runtimeManifestSha256: string | null;
    readonly runtimeInstanceId: string | null;
    readonly runtimeIdentitySha256: string;
    readonly syntheticAdmissionId: string | null;
    readonly executionPlanSha256: string;
    readonly executionPlan: ReadonlyArray<{
      readonly operation: TemplateTwinProviderOperation;
      readonly operationInstance: string;
      readonly disposition: "EXECUTED" | "NOT_APPLICABLE";
      readonly reasonCode: string | null;
    }>;
    readonly executions: ReadonlyArray<{
      readonly executionId: string;
      readonly operation: TemplateTwinProviderOperation;
      readonly operationInstance: string;
      readonly resultSha256: string;
    }>;
  };
  readonly sha256: string;
}

interface ProviderReceiptExecution {
  readonly executionId: string;
  readonly operation: TemplateTwinProviderOperation;
  readonly operationInstance: string;
  readonly resultSha256: string;
  readonly actorUserId: string;
  readonly providerMode: TemplateTwinProviderMode;
  readonly pinnedGlobalRolloutGeneration: bigint;
  readonly pinnedPracticeRolloutGeneration: bigint;
  readonly releaseId: string | null;
  readonly releaseIdentitySha256: string | null;
  readonly runtimeManifestSha256: string | null;
  readonly runtimeInstanceId: string | null;
  readonly runtimeIdentitySha256: string;
  readonly syntheticAdmissionId: string | null;
}

interface ProviderOwnershipState {
  readonly context: TemplateTwinProviderOwnershipContext;
  readonly executions: Map<string, ProviderReceiptExecution>;
  readonly notApplicable: Map<
    string,
    {
      readonly operation: TemplateTwinProviderOperation;
      readonly operationInstance: string;
      readonly reasonCode: string;
    }
  >;
  active: boolean;
  tainted: boolean;
}

const ownershipContext = new AsyncLocalStorage<ProviderOwnershipState>();
const SHA256 = /^[a-f0-9]{64}$/u;
const OPERATION_INSTANCE = /^[a-z0-9][a-z0-9._:-]{0,119}$/u;
const PROVIDER_CORRELATION_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$/u;

export type TemplateTwinProviderOwnershipErrorCode =
  | "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID"
  | "TEMPLATE_TWIN_PROVIDER_CONTEXT_NESTED"
  | "TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH"
  | "TEMPLATE_TWIN_PROVIDER_ROLLOUT_REVOKED"
  | "TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED"
  | "TEMPLATE_TWIN_PROVIDER_EXECUTION_IN_PROGRESS"
  | "TEMPLATE_TWIN_PROVIDER_OUTCOME_UNKNOWN"
  | "TEMPLATE_TWIN_PROVIDER_EXECUTION_FAILED"
  | "TEMPLATE_TWIN_PROVIDER_RESULT_INVALID"
  | "TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE";

export class TemplateTwinProviderOwnershipError extends Error {
  constructor(readonly code: TemplateTwinProviderOwnershipErrorCode) {
    super(
      "The Template Twin provider result is unavailable or cannot be safely reused.",
    );
    this.name = "TemplateTwinProviderOwnershipError";
  }
}

function ownershipError(
  code: TemplateTwinProviderOwnershipErrorCode,
): TemplateTwinProviderOwnershipError {
  return new TemplateTwinProviderOwnershipError(code);
}

function assertProviderOwnershipMayBeAbsent(): void {
  if (templateTwinProviderOwnershipRequiredByCensus()) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
  }
}

function isProductionRolloutToken(
  token: TemplateTwinRolloutToken,
): token is Extract<TemplateTwinRolloutToken, { releaseId: string }> {
  return typeof token.releaseId === "string";
}

function assertValidContext(
  context: TemplateTwinProviderOwnershipContext,
): void {
  const lineageValues = [
    context.sourceLineageId,
    context.sourceLineageVersion,
    context.sourceSha256,
  ];
  const allLineageNull = lineageValues.every((value) => value === null);
  const allLineagePresent = lineageValues.every((value) => value !== null);
  if (
    context.rolloutToken.practiceId !== context.practiceId ||
    (context.visitId === null) !== (context.visitInputMode === null) ||
    !Number.isInteger(context.logicalAttempt) ||
    context.logicalAttempt < 1 ||
    context.logicalAttempt > 1_000 ||
    !SHA256.test(context.subjectSha256) ||
    (context.sourceSha256 !== null && !SHA256.test(context.sourceSha256)) ||
    (!allLineageNull && !allLineagePresent) ||
    (context.noteTemplateVersion !== null &&
      (!Number.isInteger(context.noteTemplateVersion) ||
        context.noteTemplateVersion < 1)) ||
    (context.sourceLineageVersion !== null &&
      (!Number.isInteger(context.sourceLineageVersion) ||
        context.sourceLineageVersion < 1))
  ) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
  }

  const census = getTemplateTwinProviderCensusDecision();
  if (
    (context.scope === "VISIT_PIPELINE" &&
      (!census ||
        census.classification !== "TEMPLATE_TWIN" ||
        census.templateId !== context.noteTemplateId ||
        census.templateVersion !== context.noteTemplateVersion)) ||
    (context.scope !== "VISIT_PIPELINE" &&
      census?.classification === "ORDINARY")
  ) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
  }

  const synthetic = getTemplateTwinSyntheticQaProviderContext();
  if (
    (synthetic &&
      (synthetic.practiceId !== context.practiceId ||
        (context.visitId !== null && synthetic.visitId !== context.visitId) ||
        context.syntheticAdmissionId !== synthetic.admissionId)) ||
    (!synthetic && context.syntheticAdmissionId !== null)
  ) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
  }
}

export async function runWithTemplateTwinProviderOwnershipContext<T>(
  context: TemplateTwinProviderOwnershipContext,
  callback: () => Promise<T>,
): Promise<T> {
  if (ownershipContext.getStore()?.active) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_NESTED");
  }
  assertValidContext(context);
  const state: ProviderOwnershipState = {
    context: Object.freeze({ ...context }),
    executions: new Map(),
    notApplicable: new Map(),
    active: true,
    tainted: false,
  };
  try {
    return await ownershipContext.run(state, callback);
  } finally {
    state.active = false;
  }
}

export function getTemplateTwinProviderOwnershipContext(): TemplateTwinProviderOwnershipContext | null {
  const state = ownershipContext.getStore();
  return state?.active ? state.context : null;
}

export function requireTemplateTwinProviderOwnershipContext(
  allowedScopes: readonly TemplateTwinProviderScope[],
): TemplateTwinProviderOwnershipContext {
  const context = getTemplateTwinProviderOwnershipContext();
  if (!context || !allowedScopes.includes(context.scope)) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
  }
  return context;
}

const PROVIDER_OPERATIONS_BY_SCOPE: Readonly<
  Record<TemplateTwinProviderScope, ReadonlySet<TemplateTwinProviderOperation>>
> = {
  SOURCE_INTAKE: new Set(["SOURCE_PHI_SCAN", "SOURCE_SEMANTIC_MAPPING"]),
  STATIC_ASSET: new Set(["STATIC_ASSET_PRIVACY_SCAN"]),
  CUSTOM_EXAMPLE: new Set(["CUSTOM_EXAMPLE_EXTRACTION"]),
  SYNTHETIC_EVIDENCE: new Set([
    "SYNTHETIC_EVIDENCE_PRIVACY_SCAN",
    "SYNTHETIC_EVIDENCE_TRANSCRIPTION",
    "SYNTHETIC_EVIDENCE_EXTRACTION",
  ]),
  VISIT_PIPELINE: new Set([
    "CUSTOM_CONCEPT_EXTRACTION",
    "L1_TRANSCRIBE",
    "L1B_TRANSCRIBE",
    "L2_SPEAKER_ROLES",
    "L3_EXTRACT_ENTITIES",
    "L4_GENERATE_SOAP",
    "L4_ANCHOR_VERIFY",
    "L5_SELF_CRITIQUE",
    "L6_POLISH",
    "L6_FIDELITY_VERIFY",
  ]),
};

function providerPlanKey(
  operation: TemplateTwinProviderOperation,
  operationInstance: string,
): string {
  return `${operation}:${operationInstance}`;
}

/** Records a deterministic branch that intentionally did not call a
 * provider. The decision is authorized and durably persisted, then projected
 * into the in-process receipt plan; it is not a fabricated provider execution
 * and carries no provider result identifier. */
export async function recordTemplateTwinProviderNotApplicable(input: {
  readonly operation: TemplateTwinProviderOperation;
  readonly operationInstance?: string;
  readonly reasonCode: string;
}): Promise<void> {
  const state = ownershipContext.getStore();
  const operationInstance = input.operationInstance ?? "primary";
  const key = providerPlanKey(input.operation, operationInstance);
  if (
    !state?.active ||
    !PROVIDER_OPERATIONS_BY_SCOPE[state.context.scope].has(input.operation) ||
    !OPERATION_INSTANCE.test(operationInstance) ||
    !/^[A-Z0-9_]{3,80}$/u.test(input.reasonCode) ||
    [...state.executions.values()].some(
      (execution) =>
        providerPlanKey(execution.operation, execution.operationInstance) ===
        key,
    )
  ) {
    if (state) state.tainted = true;
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE");
  }
  const existing = state.notApplicable.get(key);
  if (existing && existing.reasonCode !== input.reasonCode) {
    state.tainted = true;
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE");
  }
  if (!existing) {
    try {
      await persistTemplateTwinProviderNotApplicable({
        state,
        operation: input.operation,
        operationInstance,
        reasonCode: input.reasonCode,
      });
    } catch (error) {
      state.tainted = true;
      throw error;
    }
  }
  state.notApplicable.set(key, {
    operation: input.operation,
    operationInstance,
    reasonCode: input.reasonCode,
  });
}

/** Returns the already-observed disposition for one exact plan slot. This is
 * intentionally read-only: callers must independently enumerate the allowed
 * slots, while the provider layer proves that each slot either executed once
 * or reached an explicit deterministic not-applicable branch. */
export function getTemplateTwinProviderPlanDisposition(input: {
  readonly operation: TemplateTwinProviderOperation;
  readonly operationInstance?: string;
}): TemplateTwinProviderExpectedPlanEntry {
  const state = ownershipContext.getStore();
  const operationInstance = input.operationInstance ?? "primary";
  const key = providerPlanKey(input.operation, operationInstance);
  if (
    !state?.active ||
    !PROVIDER_OPERATIONS_BY_SCOPE[state.context.scope].has(input.operation) ||
    !OPERATION_INSTANCE.test(operationInstance)
  ) {
    if (state) state.tainted = true;
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE");
  }
  const executions = [...state.executions.values()].filter(
    (execution) =>
      providerPlanKey(execution.operation, execution.operationInstance) === key,
  );
  const notApplicable = state.notApplicable.get(key);
  if (
    executions.length > 1 ||
    (executions.length === 1) === Boolean(notApplicable)
  ) {
    state.tainted = true;
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE");
  }
  return executions.length === 1
    ? { operation: input.operation, operationInstance, disposition: "EXECUTED" }
    : {
        operation: input.operation,
        operationInstance,
        disposition: "NOT_APPLICABLE",
        reasonCode: notApplicable!.reasonCode,
      };
}

function assertExactProviderLogIdentity(input: {
  readonly context: TemplateTwinProviderOwnershipContext;
  readonly practiceId: string;
  readonly userId: string | null | undefined;
  readonly visitId: string | null | undefined;
  readonly providerCorrelationId?: string | null;
  readonly allowedCorrelationScopes: readonly TemplateTwinProviderScope[];
}): string | null {
  const correlation =
    input.providerCorrelationId === undefined
      ? input.context.visitId
      : input.providerCorrelationId;
  if (
    input.practiceId !== input.context.practiceId ||
    input.userId !== input.context.actorUserId ||
    (input.visitId ?? null) !== correlation ||
    (correlation !== null && !PROVIDER_CORRELATION_ID.test(correlation)) ||
    (input.providerCorrelationId !== undefined &&
      !input.allowedCorrelationScopes.includes(input.context.scope))
  ) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH");
  }
  return correlation;
}

interface VisitProviderTemplateRow {
  readonly compiledVersionId: string;
  readonly sourceArtifactId: string;
  readonly sourceLineageId: string;
  readonly sourceLineageVersion: number;
  readonly sourceSha256: string;
  readonly status: string;
}

/**
 * Pins a newly selected Twin before L1 and resolves its immutable lineage in
 * the same rollout-locked transaction. Ordinary templates never call this
 * function. Existing, pre-ledger source/compiled rows fail closed.
 */
export async function pinTemplateTwinVisitProviderOwnershipContext(input: {
  readonly practiceId: string;
  readonly actorUserId: string;
  readonly visitId: string;
  readonly noteTemplateId: string;
  readonly noteTemplateVersion: number;
  readonly logicalAttempt: number;
  readonly inputMode: string;
  readonly rolloutToken: TemplateTwinRolloutToken;
}): Promise<TemplateTwinProviderOwnershipContext> {
  const synthetic = getTemplateTwinSyntheticQaProviderContext();
  return prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
      const rollout = await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.practiceId,
        pinnedToken: input.rolloutToken,
      });
      if (
        !rollout.allowed ||
        !sameRolloutToken(rollout.token, input.rolloutToken)
      ) {
        throw ownershipError("TEMPLATE_TWIN_PROVIDER_ROLLOUT_REVOKED");
      }

      const actors = await tx.$queryRaw<
        Array<{
          id: string;
          practiceId: string;
          role: string;
          isActive: boolean;
          deactivatedAt: Date | null;
          suspendedAt: Date | null;
          softDeletedAt: Date | null;
          products: string[];
        }>
      >(Prisma.sql`
        SELECT "id", "practiceId", "role", "isActive", "deactivatedAt",
          "suspendedAt", "softDeletedAt", "products"
        FROM "users"
        WHERE "id" = ${input.actorUserId}
        FOR UPDATE
      `);
      const actor = actors[0];
      if (
        !actor ||
        actor.practiceId !== input.practiceId ||
        actor.role !== "DOCTOR" ||
        !actor.isActive ||
        actor.deactivatedAt !== null ||
        actor.suspendedAt !== null ||
        actor.softDeletedAt !== null ||
        !actor.products.includes("TRANSCRIBE_MD")
      ) {
        throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
      }

      const visits = await tx.$queryRaw<
        Array<{
          id: string;
          userId: string;
          inputMode: string;
          soapVersion: number;
          noteTemplateId: string | null;
          noteTemplateVersion: number | null;
          deletedAt: Date | null;
          archivedAt: Date | null;
        }>
      >(Prisma.sql`
        SELECT "id", "userId", "inputMode", "soapVersion", "noteTemplateId", "noteTemplateVersion",
          "deletedAt", "archivedAt"
        FROM "transcribe_visits"
        WHERE "id" = ${input.visitId}
        FOR UPDATE
      `);
      const visit = visits[0];
      if (
        !visit ||
        visit.userId !== input.actorUserId ||
        visit.inputMode !== input.inputMode ||
        visit.deletedAt !== null ||
        visit.archivedAt !== null ||
        Boolean(visit.noteTemplateId) !==
          (visit.noteTemplateVersion !== null) ||
        (visit.noteTemplateId !== null &&
          (visit.noteTemplateId !== input.noteTemplateId ||
            visit.noteTemplateVersion !== input.noteTemplateVersion))
      ) {
        throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
      }

      const templateAuthority = synthetic
        ? Prisma.sql`
            EXISTS (
              SELECT 1
              FROM "template_twin_synthetic_qa_admissions" admission
              JOIN "template_twin_synthetic_qa_runs" run
                ON run."admissionId" = admission."id"
              WHERE admission."id" = ${synthetic.admissionId}
                AND admission."practiceId" = ${input.practiceId}
                AND admission."actorId" = ${input.actorUserId}
                AND admission."purpose" = 'VISIT'
                AND admission."providerMode" IN
                  ('SYNTHETIC_TYPED', 'SYNTHETIC_MOCK_VOICE')
                AND admission."phase" IN
                  ('VISIT_LINKED', 'PROCESSING', 'REVIEW_READY')
                AND admission."visitId" = ${input.visitId}
                AND admission."sourceArtifactId" = source."id"
                AND admission."noteTemplateId" = template."id"
                AND admission."noteTemplateVersion" = template."version"
                AND admission."pinnedGlobalRolloutGeneration" =
                  ${input.rolloutToken.globalGeneration}
                AND admission."pinnedPracticeRolloutGeneration" =
                  ${input.rolloutToken.practiceGeneration}
                AND admission."failedAt" IS NULL
                AND admission."revokedAt" IS NULL
                AND admission."expiresAt" > CURRENT_TIMESTAMP
                AND run."practiceId" = ${input.practiceId}
                AND run."doctorId" = ${input.actorUserId}
                AND run."visitId" = ${input.visitId}
                AND run."noteTemplateId" = template."id"
                AND run."noteTemplateVersion" = template."version"
                AND run."status" IN ('PROCESSING', 'COMPLETED')
                AND admission."parentAdmissionId" IS NOT NULL
                AND public.template_twin_staging_provider_compilation_is_valid(
                  compiled."id", ${input.actorUserId},
                  admission."parentAdmissionId"
                )
                AND EXISTS (
                  SELECT 1
                  FROM "template_twin_certifications" certification
                  WHERE certification."compiledVersionId" = compiled."id"
                    AND certification."certifiedById" = ${input.actorUserId}
                    AND certification."providerAuthorizationMode" =
                      'SYNTHETIC_QA'
                    AND certification."providerAuthorizationAdmissionId" =
                      admission."parentAdmissionId"
                )
            )
          `
        : Prisma.sql`
            public.template_twin_live_provider_compilation_is_valid(
              compiled."id", ${input.actorUserId}
            )
            AND EXISTS (
              SELECT 1
              FROM "template_twin_certifications" certification
              WHERE certification."compiledVersionId" = compiled."id"
                AND certification."certifiedById" = ${input.actorUserId}
                AND certification."providerAuthorizationMode" = 'LIVE'
                AND certification."providerAuthorizationAdmissionId" IS NULL
            )
          `;

      const templates = await tx.$queryRaw<VisitProviderTemplateRow[]>(
        Prisma.sql`
          SELECT compiled."id" AS "compiledVersionId",
            source."id" AS "sourceArtifactId",
            source."lineageId" AS "sourceLineageId",
            source."lineageVersion" AS "sourceLineageVersion",
            source."sha256" AS "sourceSha256",
            template."status" AS "status"
          FROM "note_templates" template
          JOIN "template_twin_compiled_versions" compiled
            ON compiled."noteTemplateId" = template."id"
          JOIN "template_twin_source_artifacts" source
            ON source."id" = compiled."sourceArtifactId"
          WHERE template."id" = ${input.noteTemplateId}
            AND template."version" = ${input.noteTemplateVersion}
            AND template."doctorId" = ${input.actorUserId}
            AND template."templateKind" = 'template_twin_docx'
            AND (${templateAuthority})
            AND compiled."certificationStatus" = 'CERTIFIED'
            AND compiled."providerOwnershipSha256" IS NOT NULL
            AND source."practiceId" = ${input.practiceId}
            AND source."validationStatus" = 'accepted'
            AND source."providerOwnershipSha256" IS NOT NULL
        `,
      );
      const template = templates[0];
      if (!template) {
        throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
      }

      const subjectSha256 = templateTwinVisitProviderSubjectSha256({
        practiceId: input.practiceId,
        actorUserId: input.actorUserId,
        visitId: input.visitId,
        noteTemplateId: input.noteTemplateId,
        noteTemplateVersion: input.noteTemplateVersion,
        compiledVersionId: template.compiledVersionId,
        sourceArtifactId: template.sourceArtifactId,
        sourceLineageId: template.sourceLineageId,
        sourceLineageVersion: template.sourceLineageVersion,
        sourceSha256: template.sourceSha256,
        logicalAttempt: input.logicalAttempt,
        visitInputMode: input.inputMode,
      });

      if (!synthetic && template.status !== "active") {
        if (visit.noteTemplateId !== input.noteTemplateId) {
          throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
        }
        const runtimeIdentitySha256 = providerRuntimeIdentitySha256(
          "LIVE",
          input.rolloutToken,
        );
        const priorClaims = await tx.$queryRaw<Array<{ authorized: boolean }>>(
          Prisma.sql`
            SELECT EXISTS (
              SELECT 1
              FROM "template_twin_fill_manifests" fill
              WHERE fill."visitId" = ${input.visitId}
                AND fill."compiledVersionId" = ${template.compiledVersionId}
                AND fill."noteTemplateId" = ${input.noteTemplateId}
                AND fill."noteTemplateVersion" = ${input.noteTemplateVersion}
                AND fill."status" IN ('NEEDS_REVIEW', 'VERIFIED', 'SIGNED')
                AND fill."soapVersion" = ${visit.soapVersion}
                AND fill."pinnedGlobalRolloutGeneration" =
                  ${input.rolloutToken.globalGeneration}
                AND fill."pinnedPracticeRolloutGeneration" =
                  ${input.rolloutToken.practiceGeneration}
                AND fill."providerOwnershipEvidence"->>'providerMode' = 'LIVE'
                AND fill."providerOwnershipEvidence"->>'syntheticAdmissionId'
                  IS NULL
                AND fill."providerOwnershipEvidence"->>'subjectId' =
                  ${input.visitId}
                AND fill."providerOwnershipEvidence"->>'subjectSha256' =
                  ${subjectSha256}
                AND fill."providerOwnershipEvidence"->>'releaseId' =
                  ${input.rolloutToken.releaseId ?? null}
                AND fill."providerOwnershipEvidence"->>
                  'releaseIdentitySha256' =
                  ${input.rolloutToken.releaseIdentitySha256 ?? null}
                AND fill."providerOwnershipEvidence"->>
                  'runtimeManifestSha256' =
                  ${input.rolloutToken.runtimeManifestSha256 ?? null}
                AND fill."providerOwnershipEvidence"->>'runtimeInstanceId' =
                  ${input.rolloutToken.runtimeInstanceId ?? null}
                AND fill."providerOwnershipEvidence"->>
                  'runtimeIdentitySha256' = ${runtimeIdentitySha256}
                AND public.template_twin_provider_receipt_is_valid(
                  ${input.practiceId}, ${input.actorUserId},
                  'VISIT_PIPELINE', 'LIVE', NULL,
                  ${input.visitId}, ${subjectSha256}, ${input.visitId},
                  ${input.inputMode},
                  ${template.sourceArtifactId}, ${template.compiledVersionId},
                  ${input.noteTemplateId}, ${input.noteTemplateVersion},
                  ${input.logicalAttempt}, ${template.sourceLineageId},
                  ${template.sourceLineageVersion}, ${template.sourceSha256},
                  fill."providerOwnershipEvidence",
                  fill."providerOwnershipSha256"
                )
                AND NOT EXISTS (
                  SELECT 1
                  FROM jsonb_array_elements(
                    fill."providerOwnershipEvidence"->'executions'
                  ) receipt_execution
                  JOIN "template_twin_provider_executions" execution
                    ON execution."id" = receipt_execution->>'executionId'
                  WHERE execution."scope" <> 'VISIT_PIPELINE'
                    OR execution."logicalAttempt" <> ${input.logicalAttempt}
                    OR execution."visitInputMode" <> ${input.inputMode}
                    OR execution."sourceLineageId" <>
                      ${template.sourceLineageId}
                    OR execution."sourceLineageVersion" <>
                      ${template.sourceLineageVersion}
                    OR execution."sourceSha256" <> ${template.sourceSha256}
                )
            ) AS "authorized"
          `,
        );
        if (priorClaims[0]?.authorized !== true) {
          throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
        }
      }

      if (visit.noteTemplateId === null) {
        const pinned = await tx.$executeRaw(Prisma.sql`
          UPDATE "transcribe_visits"
          SET "noteTemplateId" = ${input.noteTemplateId},
            "noteTemplateVersion" = ${input.noteTemplateVersion},
            "updatedAt" = CURRENT_TIMESTAMP
          WHERE "id" = ${input.visitId}
            AND "userId" = ${input.actorUserId}
            AND "noteTemplateId" IS NULL
            AND "noteTemplateVersion" IS NULL
        `);
        if (pinned !== 1) {
          throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
        }
      }

      return {
        practiceId: input.practiceId,
        actorUserId: input.actorUserId,
        visitId: input.visitId,
        visitInputMode: input.inputMode,
        scope: "VISIT_PIPELINE",
        logicalAttempt: input.logicalAttempt,
        subjectId: input.visitId,
        subjectSha256,
        sourceArtifactId: template.sourceArtifactId,
        compiledVersionId: template.compiledVersionId,
        noteTemplateId: input.noteTemplateId,
        noteTemplateVersion: input.noteTemplateVersion,
        sourceLineageId: template.sourceLineageId,
        sourceLineageVersion: template.sourceLineageVersion,
        sourceSha256: template.sourceSha256,
        syntheticAdmissionId: synthetic?.admissionId ?? null,
        rolloutToken: input.rolloutToken,
      } satisfies TemplateTwinProviderOwnershipContext;
    },
    { isolationLevel: Prisma.TransactionIsolationLevel.ReadCommitted },
  );
}

export function buildTemplateTwinProviderOwnershipReceipt(input: {
  readonly projection: TemplateTwinProviderReceiptProjection;
  readonly expectedExecutionPlan: readonly TemplateTwinProviderExpectedPlanEntry[];
}): TemplateTwinProviderOwnershipReceipt {
  const state = ownershipContext.getStore();
  if (!state?.active) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
  }
  if (state.tainted) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE");
  }
  if (
    !SHA256.test(input.projection.subjectSha256) ||
    input.projection.subjectId.length === 0 ||
    input.projection.subjectId !== state.context.subjectId ||
    input.projection.subjectSha256 !== state.context.subjectSha256 ||
    input.projection.visitId !== state.context.visitId ||
    input.projection.sourceArtifactId !== state.context.sourceArtifactId ||
    input.projection.compiledVersionId !== state.context.compiledVersionId ||
    input.projection.noteTemplateId !== state.context.noteTemplateId
  ) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
  }
  const ownedExecutions = [...state.executions.values()];
  const authority = ownedExecutions[0];
  if (
    !authority ||
    ownedExecutions.some(
      (execution) =>
        execution.actorUserId !== state.context.actorUserId ||
        execution.actorUserId !== authority.actorUserId ||
        execution.providerMode !== authority.providerMode ||
        execution.pinnedGlobalRolloutGeneration !==
          authority.pinnedGlobalRolloutGeneration ||
        execution.pinnedPracticeRolloutGeneration !==
          authority.pinnedPracticeRolloutGeneration ||
        execution.releaseId !== authority.releaseId ||
        execution.releaseIdentitySha256 !== authority.releaseIdentitySha256 ||
        execution.runtimeManifestSha256 !== authority.runtimeManifestSha256 ||
        execution.runtimeInstanceId !== authority.runtimeInstanceId ||
        execution.runtimeIdentitySha256 !== authority.runtimeIdentitySha256 ||
        execution.syntheticAdmissionId !== authority.syntheticAdmissionId,
    ) ||
    authority.pinnedGlobalRolloutGeneration !==
      state.context.rolloutToken.globalGeneration ||
    authority.pinnedPracticeRolloutGeneration !==
      state.context.rolloutToken.practiceGeneration ||
    authority.releaseId !== (state.context.rolloutToken.releaseId ?? null) ||
    authority.releaseIdentitySha256 !==
      (state.context.rolloutToken.releaseIdentitySha256 ?? null) ||
    authority.runtimeManifestSha256 !==
      (state.context.rolloutToken.runtimeManifestSha256 ?? null) ||
    authority.runtimeInstanceId !==
      (state.context.rolloutToken.runtimeInstanceId ?? null) ||
    authority.syntheticAdmissionId !== state.context.syntheticAdmissionId ||
    (authority.providerMode === "LIVE" &&
      (!authority.releaseId ||
        !authority.releaseIdentitySha256 ||
        !authority.runtimeManifestSha256 ||
        !authority.runtimeInstanceId)) ||
    (authority.providerMode === "SYNTHETIC_QA" &&
      !authority.syntheticAdmissionId) ||
    (authority.providerMode !== "SYNTHETIC_QA" &&
      authority.syntheticAdmissionId !== null)
  ) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE");
  }
  const executions = ownedExecutions
    .map(({ executionId, operation, operationInstance, resultSha256 }) => ({
      executionId,
      operation,
      operationInstance,
      resultSha256,
    }))
    .sort((left, right) =>
      `${left.operation}:${left.operationInstance}:${left.executionId}`.localeCompare(
        `${right.operation}:${right.operationInstance}:${right.executionId}`,
      ),
    );
  const expectedPlan = input.expectedExecutionPlan
    .map((entry) => ({
      operation: entry.operation,
      operationInstance: entry.operationInstance ?? "primary",
      disposition: entry.disposition,
      reasonCode:
        entry.disposition === "NOT_APPLICABLE"
          ? (entry.reasonCode ?? null)
          : null,
    }))
    .sort((left, right) =>
      providerPlanKey(left.operation, left.operationInstance).localeCompare(
        providerPlanKey(right.operation, right.operationInstance),
      ),
    );
  const expectedKeys = expectedPlan.map((entry) =>
    providerPlanKey(entry.operation, entry.operationInstance),
  );
  const executedKeys = executions.map((entry) =>
    providerPlanKey(entry.operation, entry.operationInstance),
  );
  const notApplicable = [...state.notApplicable.values()];
  const notApplicableByKey = new Map(
    notApplicable.map((entry) => [
      providerPlanKey(entry.operation, entry.operationInstance),
      entry,
    ]),
  );
  if (
    expectedPlan.length === 0 ||
    expectedPlan.length > 64 ||
    executions.length > 64 ||
    notApplicable.length > 64 ||
    new Set(expectedKeys).size !== expectedKeys.length ||
    new Set(executedKeys).size !== executedKeys.length ||
    expectedPlan.some(
      (entry) =>
        !PROVIDER_OPERATIONS_BY_SCOPE[state.context.scope].has(
          entry.operation,
        ) ||
        !OPERATION_INSTANCE.test(entry.operationInstance) ||
        (entry.disposition === "EXECUTED" &&
          input.expectedExecutionPlan.some(
            (raw) =>
              raw.operation === entry.operation &&
              (raw.operationInstance ?? "primary") ===
                entry.operationInstance &&
              raw.reasonCode !== undefined,
          )) ||
        (entry.disposition === "NOT_APPLICABLE" &&
          !/^[A-Z0-9_]{3,80}$/u.test(entry.reasonCode ?? "")),
    ) ||
    executions.some(
      (entry) =>
        !expectedKeys.includes(
          providerPlanKey(entry.operation, entry.operationInstance),
        ),
    ) ||
    notApplicable.some(
      (entry) =>
        !expectedKeys.includes(
          providerPlanKey(entry.operation, entry.operationInstance),
        ),
    ) ||
    expectedPlan.some((entry) => {
      const key = providerPlanKey(entry.operation, entry.operationInstance);
      const executed = executedKeys.includes(key);
      const omitted = notApplicableByKey.get(key);
      return entry.disposition === "EXECUTED"
        ? !executed || omitted !== undefined
        : executed || omitted?.reasonCode !== entry.reasonCode;
    })
  ) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE");
  }
  const executionPlan = expectedPlan;
  const executionPlanSha256 = canonicalSha256({
    contractVersion: "template-twin-provider-execution-plan-v1",
    scope: state.context.scope,
    entries: executionPlan,
  });
  const evidence = {
    contractVersion: TEMPLATE_TWIN_PROVIDER_RECEIPT_VERSION,
    scope: state.context.scope,
    practiceId: state.context.practiceId,
    actorUserId: state.context.actorUserId,
    subjectId: input.projection.subjectId,
    subjectSha256: input.projection.subjectSha256,
    visitId: input.projection.visitId,
    sourceArtifactId: input.projection.sourceArtifactId,
    compiledVersionId: input.projection.compiledVersionId,
    noteTemplateId: input.projection.noteTemplateId,
    noteTemplateVersion: state.context.noteTemplateVersion,
    visitInputMode: state.context.visitInputMode,
    logicalAttempt: state.context.logicalAttempt,
    sourceLineageId: state.context.sourceLineageId,
    sourceLineageVersion: state.context.sourceLineageVersion,
    sourceSha256: state.context.sourceSha256,
    providerMode: authority.providerMode,
    pinnedGlobalRolloutGeneration:
      authority.pinnedGlobalRolloutGeneration.toString(),
    pinnedPracticeRolloutGeneration:
      authority.pinnedPracticeRolloutGeneration.toString(),
    releaseId: authority.releaseId,
    releaseIdentitySha256: authority.releaseIdentitySha256,
    runtimeManifestSha256: authority.runtimeManifestSha256,
    runtimeInstanceId: authority.runtimeInstanceId,
    runtimeIdentitySha256: authority.runtimeIdentitySha256,
    syntheticAdmissionId: authority.syntheticAdmissionId,
    executionPlanSha256,
    executionPlan,
    executions,
  } as const;
  return { evidence, sha256: canonicalSha256(evidence) };
}

interface ProviderResultEnvelope {
  readonly contractVersion: typeof TEMPLATE_TWIN_PROVIDER_RESULT_VERSION;
  readonly output: unknown;
}

interface ProviderExecutionRow {
  readonly id: string;
  readonly practiceId: string;
  readonly actorUserId: string;
  readonly visitId: string | null;
  readonly visitInputMode: string | null;
  readonly scope: string;
  readonly operation: string;
  readonly operationInstance: string;
  readonly logicalAttempt: number;
  readonly subjectId: string;
  readonly subjectSha256: string;
  readonly sourceArtifactId: string | null;
  readonly compiledVersionId: string | null;
  readonly noteTemplateId: string | null;
  readonly noteTemplateVersion: number | null;
  readonly sourceLineageId: string | null;
  readonly sourceLineageVersion: number | null;
  readonly sourceSha256: string | null;
  readonly inputSha256: string;
  readonly provider: string;
  readonly providerMode: string;
  readonly model: string;
  readonly operationVersion: string;
  readonly providerConfigurationSha256: string;
  readonly runtimeIdentitySha256: string;
  readonly ownershipKey: string;
  readonly idempotencyKey: string;
  readonly pinnedGlobalRolloutGeneration: bigint;
  readonly pinnedPracticeRolloutGeneration: bigint;
  readonly releaseId: string | null;
  readonly releaseIdentitySha256: string | null;
  readonly runtimeManifestSha256: string | null;
  readonly runtimeInstanceId: string | null;
  readonly syntheticAdmissionId: string | null;
  readonly status: string;
  readonly invocationCount: number;
  readonly claimId: string | null;
  readonly resultPayload: Prisma.JsonValue | null;
  readonly resultSha256: string | null;
  readonly resultVersion: string | null;
  readonly failureCode: string | null;
}

const PROVIDER_EXECUTION_SAFE_SELECT = {
  id: true,
  practiceId: true,
  actorUserId: true,
  visitId: true,
  visitInputMode: true,
  scope: true,
  operation: true,
  operationInstance: true,
  logicalAttempt: true,
  subjectId: true,
  subjectSha256: true,
  sourceArtifactId: true,
  compiledVersionId: true,
  noteTemplateId: true,
  noteTemplateVersion: true,
  sourceLineageId: true,
  sourceLineageVersion: true,
  sourceSha256: true,
  inputSha256: true,
  provider: true,
  providerMode: true,
  model: true,
  operationVersion: true,
  providerConfigurationSha256: true,
  runtimeIdentitySha256: true,
  ownershipKey: true,
  idempotencyKey: true,
  pinnedGlobalRolloutGeneration: true,
  pinnedPracticeRolloutGeneration: true,
  releaseId: true,
  releaseIdentitySha256: true,
  runtimeManifestSha256: true,
  runtimeInstanceId: true,
  syntheticAdmissionId: true,
  status: true,
  invocationCount: true,
  claimId: true,
  resultPayload: true,
  resultSha256: true,
  resultVersion: true,
  failureCode: true,
} as const;

interface ProviderExecutionDelegate {
  create(args: unknown): Promise<ProviderExecutionRow>;
  findUnique(args: unknown): Promise<ProviderExecutionRow | null>;
  updateMany(args: unknown): Promise<{ count: number }>;
}

interface ProviderOwnershipDbClient {
  readonly templateTwinProviderExecution: ProviderExecutionDelegate;
  $queryRaw<T>(query: Prisma.Sql): Promise<T>;
}

interface ProviderOwnershipDbHost extends ProviderOwnershipDbClient {
  $transaction<T>(
    callback: (tx: ProviderOwnershipDbClient) => Promise<T>,
    options?: { isolationLevel?: Prisma.TransactionIsolationLevel },
  ): Promise<T>;
}

export interface TemplateTwinProviderRuntimeDependencies {
  readonly db: ProviderOwnershipDbHost;
  readonly providerMode: () => TemplateTwinProviderMode;
  readonly lockRollout: (input: {
    readonly tx: ProviderOwnershipDbClient;
    readonly context: TemplateTwinProviderOwnershipContext;
    readonly mode: TemplateTwinProviderMode;
  }) => Promise<boolean>;
  readonly currentAuthority: (input: {
    readonly tx: ProviderOwnershipDbClient;
    readonly context: TemplateTwinProviderOwnershipContext;
    readonly mode: TemplateTwinProviderMode;
  }) => Promise<boolean>;
  readonly executionId: () => string;
  readonly claimId: () => string;
  readonly now: () => Date;
  readonly sleep: (milliseconds: number) => Promise<void>;
  readonly terminalWaitMs: number;
  readonly pollMs: number;
}

function pipeSha256(parts: readonly (string | number | bigint)[]): string {
  return createHash("sha256").update(parts.join("|"), "utf8").digest("hex");
}

function providerRuntimeIdentitySha256(
  mode: TemplateTwinProviderMode,
  token: TemplateTwinRolloutToken,
): string {
  return pipeSha256([
    "template-twin-provider-runtime-v1",
    mode,
    token.globalGeneration,
    token.practiceGeneration,
    token.releaseId ?? "-",
    token.releaseIdentitySha256 ?? "-",
    token.runtimeManifestSha256 ?? "-",
    token.runtimeInstanceId ?? "-",
  ]);
}

function sameRolloutToken(
  left: TemplateTwinRolloutToken,
  right: TemplateTwinRolloutToken,
): boolean {
  return (
    left.practiceId === right.practiceId &&
    left.globalGeneration === right.globalGeneration &&
    left.practiceGeneration === right.practiceGeneration &&
    left.releaseId === right.releaseId &&
    left.releaseIdentitySha256 === right.releaseIdentitySha256 &&
    left.runtimeManifestSha256 === right.runtimeManifestSha256 &&
    left.runtimeInstanceId === right.runtimeInstanceId
  );
}

async function lockLegacyNonLiveRollout(input: {
  readonly tx: ProviderOwnershipDbClient;
  readonly context: TemplateTwinProviderOwnershipContext;
}): Promise<boolean> {
  const decision = evaluateTemplateTwinRollout({ practiceEnabled: true });
  if (!decision.allowed) return false;
  const globalRows = await input.tx.$queryRaw<
    Array<{ enabled: boolean; generation: bigint; rollbackFenceState: string }>
  >(Prisma.sql`
    SELECT "enabled", "generation", "rollbackFenceState"
    FROM "template_twin_rollout_controls"
    WHERE "id" = 'global'
    FOR UPDATE
  `);
  const practiceRows = await input.tx.$queryRaw<
    Array<{
      templateTwinEnabled: boolean;
      templateTwinRolloutGeneration: bigint;
      isActive: boolean;
    }>
  >(Prisma.sql`
    SELECT "templateTwinEnabled", "templateTwinRolloutGeneration", "isActive"
    FROM "practices"
    WHERE "id" = ${input.context.practiceId}
    FOR UPDATE
  `);
  const global = globalRows[0];
  const practice = practiceRows[0];
  return Boolean(
    global?.enabled &&
    global.rollbackFenceState === "OPEN" &&
    BigInt(global.generation) === input.context.rolloutToken.globalGeneration &&
    practice?.isActive &&
    practice.templateTwinEnabled &&
    BigInt(practice.templateTwinRolloutGeneration) ===
      input.context.rolloutToken.practiceGeneration,
  );
}

async function defaultLockRollout(input: {
  readonly tx: ProviderOwnershipDbClient;
  readonly context: TemplateTwinProviderOwnershipContext;
  readonly mode: TemplateTwinProviderMode;
}): Promise<boolean> {
  if (!isProductionRolloutToken(input.context.rolloutToken)) {
    if (input.mode === "LIVE") return false;
    return lockLegacyNonLiveRollout(input);
  }
  const decision = await lockTemplateTwinRolloutForFinalClaim({
    tx: input.tx as Prisma.TransactionClient,
    practiceId: input.context.practiceId,
    pinnedToken: input.context.rolloutToken,
  });
  return (
    decision.allowed &&
    sameRolloutToken(decision.token, input.context.rolloutToken)
  );
}

async function defaultCurrentAuthority(input: {
  readonly tx: ProviderOwnershipDbClient;
  readonly context: TemplateTwinProviderOwnershipContext;
  readonly mode: TemplateTwinProviderMode;
}): Promise<boolean> {
  const context = input.context;
  const actorRows = await input.tx.$queryRaw<
    Array<{
      practiceId: string;
      role: string;
      isActive: boolean;
      deactivatedAt: Date | null;
      suspendedAt: Date | null;
      softDeletedAt: Date | null;
      products: string[];
    }>
  >(Prisma.sql`
    SELECT actor."practiceId", actor."role", actor."isActive",
      actor."deactivatedAt", actor."suspendedAt", actor."softDeletedAt",
      actor."products"
    FROM "users" actor
    WHERE actor."id" = ${context.actorUserId}
    FOR SHARE
  `);
  const actor = actorRows[0];
  const expectedRole =
    context.scope === "STATIC_ASSET"
      ? new Set(["ADMIN", "SUPER_ADMIN"])
      : new Set(["DOCTOR"]);
  if (
    !actor ||
    actor.practiceId !== context.practiceId ||
    !expectedRole.has(actor.role) ||
    !actor.isActive ||
    actor.deactivatedAt !== null ||
    actor.suspendedAt !== null ||
    actor.softDeletedAt !== null ||
    !actor.products.includes("TRANSCRIBE_MD")
  ) {
    return false;
  }

  let preCertificationVoice = false;
  let syntheticVoiceAuthority: {
    readonly id: string;
    readonly parentAdmissionId: string | null;
    readonly audioSha256: string | null;
    readonly audioSizeBytes: number | null;
    readonly audioMimeType: string | null;
    readonly audioObjectKey: string | null;
  } | null = null;
  if (input.mode === "SYNTHETIC_QA") {
    if (!context.syntheticAdmissionId) return false;
    const admissions = await input.tx.$queryRaw<
      Array<{
        id: string;
        parentAdmissionId: string | null;
        practiceId: string;
        actorId: string;
        providerMode: string;
        fixtureVersion: string;
        purpose: string;
        phase: string;
        pinnedGlobalRolloutGeneration: bigint;
        pinnedPracticeRolloutGeneration: bigint;
        sourceArtifactId: string | null;
        noteTemplateId: string | null;
        noteTemplateVersion: number | null;
        visitId: string | null;
        sourceSha256: string;
        preCertificationVoiceEvidence: boolean;
        audioSha256: string | null;
        audioSizeBytes: number | null;
        audioMimeType: string | null;
        audioObjectKey: string | null;
        attempt: number;
        certificationId: string | null;
        mappingSha256: string | null;
        consumedAt: Date | null;
        parentPracticeId: string | null;
        parentActorId: string | null;
        parentProviderMode: string | null;
        parentPurpose: string | null;
        parentPhase: string | null;
        parentSourceArtifactId: string | null;
        parentNoteTemplateId: string | null;
        parentNoteTemplateVersion: number | null;
        parentCertificationId: string | null;
        parentMappingSha256: string | null;
        parentVisitId: string | null;
        parentFailedAt: Date | null;
        parentRevokedAt: Date | null;
        parentConsumedAt: Date | null;
        parentNotExpired: boolean | null;
        parentPreCertificationVoiceEvidence: boolean | null;
        parentPinnedGlobalRolloutGeneration: bigint | null;
        parentPinnedPracticeRolloutGeneration: bigint | null;
        notExpired: boolean;
        failedAt: Date | null;
        revokedAt: Date | null;
      }>
    >(Prisma.sql`
      SELECT admission."id", admission."parentAdmissionId",
        admission."practiceId", admission."actorId",
        admission."providerMode", admission."fixtureVersion",
        admission."purpose", admission."phase",
        admission."pinnedGlobalRolloutGeneration",
        admission."pinnedPracticeRolloutGeneration",
        admission."sourceArtifactId", admission."noteTemplateId",
        admission."noteTemplateVersion", admission."visitId",
        admission."sourceSha256", admission."preCertificationVoiceEvidence",
        admission."audioSha256", admission."audioSizeBytes",
        admission."audioMimeType", admission."audioObjectKey",
        admission."attempt", admission."certificationId",
        admission."mappingSha256", admission."consumedAt",
        parent."practiceId" AS "parentPracticeId",
        parent."actorId" AS "parentActorId",
        parent."providerMode" AS "parentProviderMode",
        parent."purpose" AS "parentPurpose",
        parent."phase" AS "parentPhase",
        parent."sourceArtifactId" AS "parentSourceArtifactId",
        parent."noteTemplateId" AS "parentNoteTemplateId",
        parent."noteTemplateVersion" AS "parentNoteTemplateVersion",
        parent."certificationId" AS "parentCertificationId",
        parent."mappingSha256" AS "parentMappingSha256",
        parent."visitId" AS "parentVisitId",
        parent."failedAt" AS "parentFailedAt",
        parent."revokedAt" AS "parentRevokedAt",
        parent."consumedAt" AS "parentConsumedAt",
        parent."expiresAt" > CURRENT_TIMESTAMP AS "parentNotExpired",
        parent."preCertificationVoiceEvidence" AS
          "parentPreCertificationVoiceEvidence",
        parent."pinnedGlobalRolloutGeneration" AS
          "parentPinnedGlobalRolloutGeneration",
        parent."pinnedPracticeRolloutGeneration" AS
          "parentPinnedPracticeRolloutGeneration",
        admission."expiresAt" > CURRENT_TIMESTAMP AS "notExpired",
        admission."failedAt", admission."revokedAt"
      FROM "template_twin_synthetic_qa_admissions" admission
      LEFT JOIN "template_twin_synthetic_qa_admissions" parent
        ON parent."id" = admission."parentAdmissionId"
      WHERE admission."id" = ${context.syntheticAdmissionId}
      FOR SHARE OF admission, parent
    `);
    const admission = admissions[0];
    preCertificationVoice = admission?.preCertificationVoiceEvidence === true;
    if (preCertificationVoice && admission) {
      syntheticVoiceAuthority = {
        id: admission.id,
        parentAdmissionId: admission.parentAdmissionId,
        audioSha256: admission.audioSha256,
        audioSizeBytes: admission.audioSizeBytes,
        audioMimeType: admission.audioMimeType,
        audioObjectKey: admission.audioObjectKey,
      };
    }
    if (
      !admission ||
      admission.practiceId !== context.practiceId ||
      admission.actorId !== context.actorUserId ||
      !admission.notExpired ||
      admission.failedAt !== null ||
      admission.revokedAt !== null ||
      admission.pinnedGlobalRolloutGeneration !==
        context.rolloutToken.globalGeneration ||
      admission.pinnedPracticeRolloutGeneration !==
        context.rolloutToken.practiceGeneration ||
      (context.scope === "SOURCE_INTAKE"
        ? admission.providerMode !== "SYNTHETIC_LIFECYCLE" ||
          admission.fixtureVersion !==
            "template-twin-staging-safe-docx/1.0.0" ||
          admission.purpose !== "UPLOAD" ||
          admission.phase !== "ADMITTED" ||
          admission.visitId !== null ||
          context.visitId !== null ||
          admission.preCertificationVoiceEvidence
        : preCertificationVoice
          ? context.scope !== "SYNTHETIC_EVIDENCE" ||
            context.subjectId !== admission.id ||
            context.logicalAttempt !== 1 ||
            context.visitInputMode !== "audio_upload" ||
            admission.purpose !== "VISIT" ||
            admission.providerMode !== "SYNTHETIC_MOCK_VOICE" ||
            admission.phase !== "VISIT_LINKED" ||
            admission.attempt !== 1 ||
            admission.certificationId !== null ||
            admission.mappingSha256 !== null ||
            admission.consumedAt !== null ||
            admission.visitId !== context.visitId ||
            admission.sourceArtifactId !== context.sourceArtifactId ||
            admission.noteTemplateId !== context.noteTemplateId ||
            admission.noteTemplateVersion !== context.noteTemplateVersion ||
            admission.sourceSha256 !== context.sourceSha256 ||
            admission.parentPracticeId !== context.practiceId ||
            admission.parentActorId !== context.actorUserId ||
            admission.parentProviderMode !== "SYNTHETIC_LIFECYCLE" ||
            admission.parentPurpose !== "UPLOAD" ||
            admission.parentPhase !== "TEMPLATE_LINKED" ||
            admission.parentSourceArtifactId !== context.sourceArtifactId ||
            admission.parentNoteTemplateId !== context.noteTemplateId ||
            admission.parentNoteTemplateVersion !==
              context.noteTemplateVersion ||
            admission.parentCertificationId !== null ||
            admission.parentMappingSha256 !== null ||
            admission.parentVisitId !== null ||
            admission.parentFailedAt !== null ||
            admission.parentRevokedAt !== null ||
            admission.parentConsumedAt !== null ||
            admission.parentNotExpired !== true ||
            admission.parentPreCertificationVoiceEvidence !== false ||
            admission.parentPinnedGlobalRolloutGeneration !==
              context.rolloutToken.globalGeneration ||
            admission.parentPinnedPracticeRolloutGeneration !==
              context.rolloutToken.practiceGeneration
          : admission.purpose !== "VISIT" ||
            admission.preCertificationVoiceEvidence ||
            !["SYNTHETIC_TYPED", "SYNTHETIC_MOCK_VOICE"].includes(
              admission.providerMode,
            ) ||
            ![
              "CERTIFIED",
              "VISIT_LINKED",
              "PROCESSING",
              "REVIEW_READY",
            ].includes(admission.phase) ||
            admission.visitId !== context.visitId ||
            (admission.sourceArtifactId !== null &&
              admission.sourceArtifactId !== context.sourceArtifactId) ||
            (admission.noteTemplateId !== null &&
              admission.noteTemplateId !== context.noteTemplateId) ||
            (admission.noteTemplateVersion !== null &&
              admission.noteTemplateVersion !== context.noteTemplateVersion))
    ) {
      return false;
    }
  } else if (context.syntheticAdmissionId !== null) {
    return false;
  }

  if (context.visitId !== null) {
    const visits = await input.tx.$queryRaw<
      Array<{
        userId: string;
        inputMode: string;
        noteTemplateId: string | null;
        noteTemplateVersion: number | null;
        deletedAt: Date | null;
        archivedAt: Date | null;
        status: string;
        audioKey: string | null;
        audioMimeType: string | null;
        audioSizeBytes: number | null;
        rawTextInput: string | null;
        dictationAudioKey: string | null;
        signedAt: Date | null;
        patientPracticeId: string;
        patientName: string;
        patientExternalId: string | null;
        patientDateOfBirth: Date | null;
        patientMrn: string | null;
        patientInsurance: string | null;
        patientProblemList: unknown | null;
        patientWeightKg: number | null;
        patientAllergies: string[];
        patientDeletedAt: Date | null;
      }>
    >(Prisma.sql`
      SELECT visit."userId", visit."inputMode", visit."noteTemplateId",
        visit."noteTemplateVersion", visit."deletedAt", visit."archivedAt",
        visit."status", visit."audioKey", visit."audioMimeType",
        visit."audioSizeBytes", visit."rawTextInput",
        visit."dictationAudioKey", visit."signedAt",
        patient."practiceId" AS "patientPracticeId",
        patient."name" AS "patientName",
        patient."externalId" AS "patientExternalId",
        patient."dateOfBirth" AS "patientDateOfBirth",
        patient."mrn" AS "patientMrn",
        patient."insurance" AS "patientInsurance",
        patient."problemList" AS "patientProblemList",
        patient."weightKg" AS "patientWeightKg",
        patient."allergies" AS "patientAllergies",
        patient."deletedAt" AS "patientDeletedAt"
      FROM "transcribe_visits" visit
      JOIN "transcribe_md_patients" patient ON patient."id" = visit."patientId"
      WHERE visit."id" = ${context.visitId}
      FOR SHARE OF visit, patient
    `);
    const visit = visits[0];
    if (
      !visit ||
      visit.userId !== context.actorUserId ||
      visit.inputMode !== context.visitInputMode ||
      visit.deletedAt !== null ||
      visit.archivedAt !== null ||
      (context.noteTemplateId !== null &&
        visit.noteTemplateId !== context.noteTemplateId) ||
      (context.noteTemplateVersion !== null &&
        visit.noteTemplateVersion !== context.noteTemplateVersion)
    ) {
      return false;
    }
    if (
      preCertificationVoice &&
      (visit.status !== "QUEUED" ||
        visit.audioKey !== syntheticVoiceAuthority?.audioObjectKey ||
        visit.audioMimeType !== syntheticVoiceAuthority?.audioMimeType ||
        visit.audioSizeBytes !== syntheticVoiceAuthority?.audioSizeBytes ||
        visit.rawTextInput !== null ||
        visit.dictationAudioKey !== null ||
        visit.signedAt !== null ||
        visit.patientPracticeId !== context.practiceId ||
        visit.patientName !== "Template Twin Synthetic QA" ||
        visit.patientExternalId !== "SYNTHETIC-QA-ONLY" ||
        visit.patientDateOfBirth !== null ||
        visit.patientMrn !== null ||
        visit.patientInsurance !== null ||
        visit.patientProblemList !== null ||
        visit.patientWeightKg !== null ||
        visit.patientAllergies.length !== 0 ||
        visit.patientDeletedAt !== null)
    ) {
      return false;
    }
  }

  if (context.scope === "SOURCE_INTAKE") {
    const collisions = await input.tx.$queryRaw<Array<{ collision: boolean }>>(
      Prisma.sql`
        SELECT (
          EXISTS (SELECT 1 FROM "template_twin_source_artifacts"
            WHERE "id" = ${context.sourceArtifactId})
          OR EXISTS (SELECT 1 FROM "template_twin_compiled_versions"
            WHERE "id" = ${context.compiledVersionId})
          OR EXISTS (SELECT 1 FROM "note_templates"
            WHERE "id" = ${context.noteTemplateId})
        ) AS "collision"
      `,
    );
    return collisions[0]?.collision === false;
  }

  if (context.sourceArtifactId !== null) {
    const artifacts = await input.tx.$queryRaw<Array<{ authorized: boolean }>>(
      Prisma.sql`
        SELECT EXISTS (
          SELECT 1
          FROM "template_twin_compiled_versions" compiled
          JOIN "template_twin_source_artifacts" source
            ON source."id" = compiled."sourceArtifactId"
          JOIN "note_templates" template
            ON template."id" = compiled."noteTemplateId"
          WHERE source."id" = ${context.sourceArtifactId}
            AND compiled."id" = ${context.compiledVersionId}
            AND template."id" = ${context.noteTemplateId}
            AND template."doctorId" = ${context.actorUserId}
            AND template."version" = ${context.noteTemplateVersion}
            AND source."practiceId" = ${context.practiceId}
            AND source."lineageId" = ${context.sourceLineageId}
            AND source."lineageVersion" = ${context.sourceLineageVersion}
            AND source."sha256" = ${context.sourceSha256}
            AND source."validationStatus" = 'accepted'
            AND template."templateKind" = 'template_twin_docx'
            AND (${!preCertificationVoice}
              OR compiled."certificationStatus" <> 'CERTIFIED')
        ) AS "authorized"
      `,
    );
    if (artifacts[0]?.authorized !== true) return false;
  }
  if (
    preCertificationVoice &&
    (!syntheticVoiceAuthority ||
      !syntheticVoiceAuthority.parentAdmissionId ||
      !syntheticVoiceAuthority.audioSha256 ||
      !syntheticVoiceAuthority.audioSizeBytes ||
      !syntheticVoiceAuthority.audioMimeType ||
      !syntheticVoiceAuthority.audioObjectKey ||
      !context.compiledVersionId ||
      !context.sourceArtifactId ||
      !context.noteTemplateId ||
      context.noteTemplateVersion === null ||
      !context.sourceLineageId ||
      context.sourceLineageVersion === null ||
      !context.sourceSha256 ||
      context.subjectSha256 !==
        templateTwinSyntheticVoiceSubjectSha256({
          admissionId: syntheticVoiceAuthority.id,
          parentAdmissionId: syntheticVoiceAuthority.parentAdmissionId,
          practiceId: context.practiceId,
          actorUserId: context.actorUserId,
          visitId: context.visitId!,
          inputMode: "audio_upload",
          audioSha256: syntheticVoiceAuthority.audioSha256,
          audioSizeBytes: syntheticVoiceAuthority.audioSizeBytes,
          audioMimeType: syntheticVoiceAuthority.audioMimeType,
          audioObjectKey: syntheticVoiceAuthority.audioObjectKey,
          sourceArtifactId: context.sourceArtifactId,
          compiledVersionId: context.compiledVersionId,
          noteTemplateId: context.noteTemplateId,
          noteTemplateVersion: context.noteTemplateVersion,
          sourceLineageId: context.sourceLineageId,
          sourceLineageVersion: context.sourceLineageVersion,
          sourceSha256: context.sourceSha256,
          logicalAttempt: 1,
        }))
  ) {
    return false;
  }
  return true;
}

const DEFAULT_DEPENDENCIES: TemplateTwinProviderRuntimeDependencies = {
  db: prisma as unknown as ProviderOwnershipDbHost,
  providerMode: () => {
    if (getTemplateTwinSyntheticQaProviderContext()) return "SYNTHETIC_QA";
    return process.env.MOCK_AI_CALLS === "true" ? "DETERMINISTIC_MOCK" : "LIVE";
  },
  lockRollout: defaultLockRollout,
  currentAuthority: defaultCurrentAuthority,
  executionId: randomUUID,
  claimId: () => randomBytes(32).toString("hex"),
  now: () => new Date(),
  sleep: (milliseconds) =>
    new Promise((resolve) => setTimeout(resolve, milliseconds)),
  terminalWaitMs: 5_000,
  pollMs: 20,
};

function providerPlanDecisionOwnershipKey(input: {
  readonly context: TemplateTwinProviderOwnershipContext;
  readonly mode: TemplateTwinProviderMode;
  readonly operation: TemplateTwinProviderOperation;
  readonly operationInstance: string;
}): string {
  const context = input.context;
  const token = context.rolloutToken;
  return pipeSha256([
    "template-twin-provider-plan-decision-v1",
    context.practiceId,
    context.actorUserId,
    context.visitId ?? "-",
    context.visitInputMode ?? "-",
    context.scope,
    context.logicalAttempt,
    context.subjectId,
    context.subjectSha256,
    context.sourceArtifactId ?? "-",
    context.compiledVersionId ?? "-",
    context.noteTemplateId ?? "-",
    context.noteTemplateVersion ?? "-",
    context.sourceLineageId ?? "-",
    context.sourceLineageVersion ?? "-",
    context.sourceSha256 ?? "-",
    input.mode,
    input.operation,
    input.operationInstance,
    token.globalGeneration,
    token.practiceGeneration,
    token.releaseId ?? "-",
    token.releaseIdentitySha256 ?? "-",
    token.runtimeManifestSha256 ?? "-",
    token.runtimeInstanceId ?? "-",
    providerRuntimeIdentitySha256(input.mode, token),
    context.syntheticAdmissionId ?? "-",
  ]);
}

async function persistTemplateTwinProviderNotApplicable(input: {
  readonly state: ProviderOwnershipState;
  readonly operation: TemplateTwinProviderOperation;
  readonly operationInstance: string;
  readonly reasonCode: string;
}): Promise<void> {
  const context = input.state.context;
  const mode = DEFAULT_DEPENDENCIES.providerMode();
  if (mode === "SYNTHETIC_QA") {
    assertTemplateTwinSyntheticQaWorkerLeaseHealthy();
  }
  const token = context.rolloutToken;
  const runtimeIdentitySha256 = providerRuntimeIdentitySha256(mode, token);
  const ownershipKey = providerPlanDecisionOwnershipKey({
    context,
    mode,
    operation: input.operation,
    operationInstance: input.operationInstance,
  });
  const decisionId = randomUUID();
  const rows = await DEFAULT_DEPENDENCIES.db.$transaction(
    async (tx) => {
      if (
        !(await DEFAULT_DEPENDENCIES.lockRollout({ tx, context, mode })) ||
        !(await DEFAULT_DEPENDENCIES.currentAuthority({ tx, context, mode }))
      ) {
        throw ownershipError("TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED");
      }
      await tx.$queryRaw(Prisma.sql`
        INSERT INTO "template_twin_provider_plan_decisions" (
          "id", "practiceId", "actorUserId", "visitId", "visitInputMode",
          "scope", "operation", "operationInstance", "logicalAttempt",
          "subjectId", "subjectSha256", "sourceArtifactId",
          "compiledVersionId", "noteTemplateId", "noteTemplateVersion",
          "sourceLineageId", "sourceLineageVersion", "sourceSha256",
          "providerMode", "pinnedGlobalRolloutGeneration",
          "pinnedPracticeRolloutGeneration", "releaseId",
          "releaseIdentitySha256", "runtimeManifestSha256",
          "runtimeInstanceId", "runtimeIdentitySha256",
          "syntheticAdmissionId", "reasonCode", "ownershipKey",
          "createdAt"
        ) VALUES (
          ${decisionId}, ${context.practiceId}, ${context.actorUserId},
          ${context.visitId}, ${context.visitInputMode}, ${context.scope},
          ${input.operation}, ${input.operationInstance},
          ${context.logicalAttempt}, ${context.subjectId},
          ${context.subjectSha256}, ${context.sourceArtifactId},
          ${context.compiledVersionId}, ${context.noteTemplateId},
          ${context.noteTemplateVersion}, ${context.sourceLineageId},
          ${context.sourceLineageVersion}, ${context.sourceSha256}, ${mode},
          ${token.globalGeneration}, ${token.practiceGeneration},
          ${token.releaseId ?? null}::UUID,
          ${token.releaseIdentitySha256 ?? null},
          ${token.runtimeManifestSha256 ?? null},
          ${token.runtimeInstanceId ?? null}, ${runtimeIdentitySha256},
          ${context.syntheticAdmissionId}, ${input.reasonCode}, ${ownershipKey},
          CURRENT_TIMESTAMP
        )
        ON CONFLICT ("ownershipKey") DO NOTHING
        RETURNING "id"
      `);
      return tx.$queryRaw<
        Array<{
          operation: string;
          operationInstance: string;
          reasonCode: string;
        }>
      >(Prisma.sql`
        SELECT "operation", "operationInstance", "reasonCode"
        FROM "template_twin_provider_plan_decisions"
        WHERE "ownershipKey" = ${ownershipKey}
        FOR SHARE
      `);
    },
    { isolationLevel: Prisma.TransactionIsolationLevel.ReadCommitted },
  );
  if (
    rows.length !== 1 ||
    rows[0].operation !== input.operation ||
    rows[0].operationInstance !== input.operationInstance ||
    rows[0].reasonCode !== input.reasonCode
  ) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE");
  }
}

/** Restore exact successes after a BullMQ delivery resumes past a persisted
 * layer. Any nonterminal/failed/unknown execution in this exact runtime epoch
 * taints the context and blocks artifact admission. */
export async function hydrateTemplateTwinProviderOwnershipReceipt(): Promise<void> {
  const state = ownershipContext.getStore();
  if (!state?.active) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
  }
  const mode = DEFAULT_DEPENDENCIES.providerMode();
  if (mode === "SYNTHETIC_QA") {
    assertTemplateTwinSyntheticQaWorkerLeaseHealthy();
  }
  const context = state.context;
  await assertCurrentProviderAuthority({
    dependencies: DEFAULT_DEPENDENCIES,
    context,
    mode,
  });
  const token = context.rolloutToken;
  const rows = (await prisma.templateTwinProviderExecution.findMany({
    where: {
      practiceId: context.practiceId,
      actorUserId: context.actorUserId,
      visitId: context.visitId,
      visitInputMode: context.visitInputMode,
      scope: context.scope,
      logicalAttempt: context.logicalAttempt,
      subjectId: context.subjectId,
      subjectSha256: context.subjectSha256,
      sourceArtifactId: context.sourceArtifactId,
      compiledVersionId: context.compiledVersionId,
      noteTemplateId: context.noteTemplateId,
      noteTemplateVersion: context.noteTemplateVersion,
      sourceLineageId: context.sourceLineageId,
      sourceLineageVersion: context.sourceLineageVersion,
      sourceSha256: context.sourceSha256,
      providerMode: mode,
      runtimeIdentitySha256: providerRuntimeIdentitySha256(mode, token),
      pinnedGlobalRolloutGeneration: token.globalGeneration,
      pinnedPracticeRolloutGeneration: token.practiceGeneration,
      releaseId: token.releaseId ?? null,
      releaseIdentitySha256: token.releaseIdentitySha256 ?? null,
      runtimeManifestSha256: token.runtimeManifestSha256 ?? null,
      runtimeInstanceId: token.runtimeInstanceId ?? null,
      syntheticAdmissionId: context.syntheticAdmissionId,
    },
    select: PROVIDER_EXECUTION_SAFE_SELECT,
  })) as ProviderExecutionRow[];
  for (const row of rows) {
    if (row.status !== "SUCCEEDED") {
      state.tainted = true;
      throw ownershipError(
        row.status === "UNKNOWN_OUTCOME"
          ? "TEMPLATE_TWIN_PROVIDER_OUTCOME_UNKNOWN"
          : row.status === "FAILED"
            ? "TEMPLATE_TWIN_PROVIDER_EXECUTION_FAILED"
            : "TEMPLATE_TWIN_PROVIDER_EXECUTION_IN_PROGRESS",
      );
    }
    if (
      row.resultVersion !== TEMPLATE_TWIN_PROVIDER_RESULT_VERSION ||
      !row.resultSha256 ||
      !row.resultPayload ||
      canonicalSha256(row.resultPayload) !== row.resultSha256
    ) {
      state.tainted = true;
      throw ownershipError("TEMPLATE_TWIN_PROVIDER_RESULT_INVALID");
    }
    recordReceiptExecution(state, row);
  }
  const planDecisions = await (prisma as unknown as ProviderOwnershipDbClient)
    .$queryRaw<
    Array<{
      operation: string;
      operationInstance: string;
      reasonCode: string;
    }>
  >(Prisma.sql`
    SELECT decision."operation", decision."operationInstance",
      decision."reasonCode"
    FROM "template_twin_provider_plan_decisions" decision
    WHERE decision."practiceId" = ${context.practiceId}
      AND decision."actorUserId" = ${context.actorUserId}
      AND decision."visitId" IS NOT DISTINCT FROM ${context.visitId}
      AND decision."visitInputMode" IS NOT DISTINCT FROM ${context.visitInputMode}
      AND decision."scope" = ${context.scope}
      AND decision."logicalAttempt" = ${context.logicalAttempt}
      AND decision."subjectId" = ${context.subjectId}
      AND decision."subjectSha256" = ${context.subjectSha256}
      AND decision."sourceArtifactId" IS NOT DISTINCT FROM ${context.sourceArtifactId}
      AND decision."compiledVersionId" IS NOT DISTINCT FROM ${context.compiledVersionId}
      AND decision."noteTemplateId" IS NOT DISTINCT FROM ${context.noteTemplateId}
      AND decision."noteTemplateVersion" IS NOT DISTINCT FROM ${context.noteTemplateVersion}
      AND decision."sourceLineageId" IS NOT DISTINCT FROM ${context.sourceLineageId}
      AND decision."sourceLineageVersion" IS NOT DISTINCT FROM ${context.sourceLineageVersion}
      AND decision."sourceSha256" IS NOT DISTINCT FROM ${context.sourceSha256}
      AND decision."providerMode" = ${mode}
      AND decision."pinnedGlobalRolloutGeneration" = ${token.globalGeneration}
      AND decision."pinnedPracticeRolloutGeneration" = ${token.practiceGeneration}
      AND decision."releaseId"::TEXT IS NOT DISTINCT FROM ${token.releaseId ?? null}
      AND decision."releaseIdentitySha256" IS NOT DISTINCT FROM ${token.releaseIdentitySha256 ?? null}
      AND decision."runtimeManifestSha256" IS NOT DISTINCT FROM ${token.runtimeManifestSha256 ?? null}
      AND decision."runtimeInstanceId" IS NOT DISTINCT FROM ${token.runtimeInstanceId ?? null}
      AND decision."runtimeIdentitySha256" = ${providerRuntimeIdentitySha256(mode, token)}
      AND decision."syntheticAdmissionId" IS NOT DISTINCT FROM ${context.syntheticAdmissionId}
    ORDER BY decision."operation", decision."operationInstance"
  `);
  for (const decision of planDecisions) {
    const operation = decision.operation as TemplateTwinProviderOperation;
    const key = providerPlanKey(operation, decision.operationInstance);
    if (
      !PROVIDER_OPERATIONS_BY_SCOPE[context.scope].has(operation) ||
      !OPERATION_INSTANCE.test(decision.operationInstance) ||
      !/^[A-Z0-9_]{3,80}$/u.test(decision.reasonCode) ||
      state.notApplicable.has(key)
    ) {
      state.tainted = true;
      throw ownershipError("TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE");
    }
    state.notApplicable.set(key, {
      operation,
      operationInstance: decision.operationInstance,
      reasonCode: decision.reasonCode,
    });
  }
}

export interface TemplateTwinOwnedProviderInput<T> {
  readonly operation: TemplateTwinProviderOperation;
  /** Stable structural ordinal for legitimately repeated provider operations. */
  readonly operationInstance?: string;
  readonly operationVersion: string;
  readonly provider: string;
  readonly model: string;
  /** Provider configuration identity only. Never include credentials. */
  readonly providerConfiguration: unknown;
  /** Exact clinical/provider input identity. The ledger persists only its hash. */
  readonly inputIdentity: unknown;
  readonly invoke: (input: { readonly idempotencyKey?: string }) => Promise<T>;
  readonly validate: (output: unknown) => T;
}

interface ProviderExecutionIdentity {
  readonly id: string;
  readonly practiceId: string;
  readonly actorUserId: string;
  readonly visitId: string | null;
  readonly visitInputMode: string | null;
  readonly scope: TemplateTwinProviderScope;
  readonly operation: TemplateTwinProviderOperation;
  readonly operationInstance: string;
  readonly logicalAttempt: number;
  readonly subjectId: string;
  readonly subjectSha256: string;
  readonly sourceArtifactId: string | null;
  readonly compiledVersionId: string | null;
  readonly noteTemplateId: string | null;
  readonly noteTemplateVersion: number | null;
  readonly sourceLineageId: string | null;
  readonly sourceLineageVersion: number | null;
  readonly sourceSha256: string | null;
  readonly inputSha256: string;
  readonly provider: string;
  readonly providerMode: TemplateTwinProviderMode;
  readonly model: string;
  readonly operationVersion: string;
  readonly providerConfigurationSha256: string;
  readonly runtimeIdentitySha256: string;
  readonly ownershipKey: string;
  readonly idempotencyKey: string;
  readonly pinnedGlobalRolloutGeneration: bigint;
  readonly pinnedPracticeRolloutGeneration: bigint;
  readonly releaseId: string | null;
  readonly releaseIdentitySha256: string | null;
  readonly runtimeManifestSha256: string | null;
  readonly runtimeInstanceId: string | null;
  readonly syntheticAdmissionId: string | null;
}

function buildIdentity(input: {
  readonly context: TemplateTwinProviderOwnershipContext;
  readonly provider: TemplateTwinOwnedProviderInput<unknown>;
  readonly mode: TemplateTwinProviderMode;
  readonly executionId: string;
}): ProviderExecutionIdentity {
  const token = input.context.rolloutToken;
  if (input.mode === "LIVE" && !isProductionRolloutToken(token)) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_ROLLOUT_REVOKED");
  }
  const operationInstance = input.provider.operationInstance ?? "primary";
  if (!OPERATION_INSTANCE.test(operationInstance)) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
  }
  const syntheticContext = getTemplateTwinSyntheticQaProviderContext();
  const syntheticAdmissionId =
    input.mode === "SYNTHETIC_QA"
      ? (syntheticContext?.admissionId ?? null)
      : null;
  if (
    syntheticAdmissionId !== input.context.syntheticAdmissionId ||
    (input.mode === "SYNTHETIC_QA" && !syntheticAdmissionId) ||
    (input.mode !== "SYNTHETIC_QA" &&
      input.context.syntheticAdmissionId !== null)
  ) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
  }
  const inputSha256 = canonicalSha256(input.provider.inputIdentity);
  const providerConfigurationSha256 = canonicalSha256({
    contractVersion: "template-twin-provider-configuration-v1",
    provider: input.provider.provider,
    model: input.provider.model,
    configuration: input.provider.providerConfiguration,
  });
  const releaseId = token.releaseId ?? null;
  const releaseIdentitySha256 = token.releaseIdentitySha256 ?? null;
  const runtimeManifestSha256 = token.runtimeManifestSha256 ?? null;
  const runtimeInstanceId = token.runtimeInstanceId ?? null;
  const runtimeIdentitySha256 = providerRuntimeIdentitySha256(
    input.mode,
    token,
  );
  const ownershipKey = pipeSha256([
    "template-twin-provider-ownership-v2",
    input.context.practiceId,
    input.context.scope,
    input.context.subjectId,
    input.context.logicalAttempt,
    input.provider.operation,
    operationInstance,
  ]);
  const idempotencyKey = pipeSha256([
    "template-twin-provider-idempotency-v2",
    ownershipKey,
    input.context.actorUserId,
    input.context.subjectSha256,
    inputSha256,
    input.provider.provider,
    input.mode,
    input.provider.model,
    input.provider.operationVersion,
    providerConfigurationSha256,
    runtimeIdentitySha256,
    input.context.visitId ?? "-",
    input.context.visitInputMode ?? "-",
    input.context.sourceArtifactId ?? "-",
    input.context.compiledVersionId ?? "-",
    input.context.noteTemplateId ?? "-",
    input.context.noteTemplateVersion ?? "-",
    input.context.sourceLineageId ?? "-",
    input.context.sourceLineageVersion ?? "-",
    input.context.sourceSha256 ?? "-",
    syntheticAdmissionId ?? "-",
  ]);
  return {
    id: input.executionId,
    practiceId: input.context.practiceId,
    actorUserId: input.context.actorUserId,
    visitId: input.context.visitId,
    visitInputMode: input.context.visitInputMode,
    scope: input.context.scope,
    operation: input.provider.operation,
    operationInstance,
    logicalAttempt: input.context.logicalAttempt,
    subjectId: input.context.subjectId,
    subjectSha256: input.context.subjectSha256,
    sourceArtifactId: input.context.sourceArtifactId,
    compiledVersionId: input.context.compiledVersionId,
    noteTemplateId: input.context.noteTemplateId,
    noteTemplateVersion: input.context.noteTemplateVersion,
    sourceLineageId: input.context.sourceLineageId,
    sourceLineageVersion: input.context.sourceLineageVersion,
    sourceSha256: input.context.sourceSha256,
    inputSha256,
    provider: input.provider.provider,
    providerMode: input.mode,
    model: input.provider.model,
    operationVersion: input.provider.operationVersion,
    providerConfigurationSha256,
    runtimeIdentitySha256,
    ownershipKey,
    idempotencyKey,
    pinnedGlobalRolloutGeneration: token.globalGeneration,
    pinnedPracticeRolloutGeneration: token.practiceGeneration,
    releaseId,
    releaseIdentitySha256,
    runtimeManifestSha256,
    runtimeInstanceId,
    syntheticAdmissionId,
  };
}

const IDENTITY_KEYS = [
  "practiceId",
  "actorUserId",
  "visitId",
  "visitInputMode",
  "scope",
  "operation",
  "operationInstance",
  "logicalAttempt",
  "subjectId",
  "subjectSha256",
  "sourceArtifactId",
  "compiledVersionId",
  "noteTemplateId",
  "noteTemplateVersion",
  "sourceLineageId",
  "sourceLineageVersion",
  "sourceSha256",
  "inputSha256",
  "provider",
  "providerMode",
  "model",
  "operationVersion",
  "providerConfigurationSha256",
  "runtimeIdentitySha256",
  "ownershipKey",
  "idempotencyKey",
  "pinnedGlobalRolloutGeneration",
  "pinnedPracticeRolloutGeneration",
  "releaseId",
  "releaseIdentitySha256",
  "runtimeManifestSha256",
  "runtimeInstanceId",
  "syntheticAdmissionId",
] as const satisfies readonly (keyof ProviderExecutionIdentity)[];

function identityMatches(
  row: ProviderExecutionRow,
  identity: ProviderExecutionIdentity,
): boolean {
  return IDENTITY_KEYS.every((key) => row[key] === identity[key]);
}

function isUniqueConflict(error: unknown): boolean {
  return Boolean(
    error &&
    typeof error === "object" &&
    "code" in error &&
    (error as { code?: unknown }).code === "P2002",
  );
}

async function reserveExecution(
  dependencies: TemplateTwinProviderRuntimeDependencies,
  identity: ProviderExecutionIdentity,
): Promise<ProviderExecutionRow> {
  try {
    return await dependencies.db.templateTwinProviderExecution.create({
      data: identity,
      select: PROVIDER_EXECUTION_SAFE_SELECT,
    });
  } catch (error) {
    const existing =
      await dependencies.db.templateTwinProviderExecution.findUnique({
        where: { ownershipKey: identity.ownershipKey },
        select: PROVIDER_EXECUTION_SAFE_SELECT,
      });
    if (existing) {
      if (!identityMatches(existing, identity)) {
        throw ownershipError("TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH");
      }
      return existing;
    }
    if (isUniqueConflict(error)) {
      throw ownershipError("TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH");
    }
    throw error;
  }
}

type ClaimDisposition =
  | { readonly kind: "CLAIMED"; readonly row: ProviderExecutionRow }
  | { readonly kind: "SUCCEEDED"; readonly row: ProviderExecutionRow }
  | { readonly kind: "IN_PROGRESS"; readonly row: ProviderExecutionRow }
  | { readonly kind: "FAILED"; readonly row: ProviderExecutionRow }
  | { readonly kind: "UNKNOWN"; readonly row: ProviderExecutionRow }
  | { readonly kind: "AUTHORITY_REVOKED"; readonly row: ProviderExecutionRow }
  | { readonly kind: "ROLLOUT_REVOKED"; readonly row: ProviderExecutionRow };

function disposition(row: ProviderExecutionRow): ClaimDisposition {
  switch (row.status) {
    case "SUCCEEDED":
      return { kind: "SUCCEEDED", row };
    case "IN_FLIGHT":
      return { kind: "IN_PROGRESS", row };
    case "FAILED":
      return row.failureCode?.startsWith("AUTHORITY_REVOKED_")
        ? { kind: "AUTHORITY_REVOKED", row }
        : { kind: "FAILED", row };
    case "UNKNOWN_OUTCOME":
      return { kind: "UNKNOWN", row };
    default:
      return { kind: "IN_PROGRESS", row };
  }
}

async function claimExecution(input: {
  readonly dependencies: TemplateTwinProviderRuntimeDependencies;
  readonly identity: ProviderExecutionIdentity;
  readonly context: TemplateTwinProviderOwnershipContext;
  readonly mode: TemplateTwinProviderMode;
  readonly claimId: string;
}): Promise<ClaimDisposition> {
  const runClaim = () =>
    input.dependencies.db.$transaction(
      async (tx) => {
        const rolloutCurrent = await input.dependencies.lockRollout({
          tx,
          context: input.context,
          mode: input.mode,
        });
        const row = await tx.templateTwinProviderExecution.findUnique({
          where: { ownershipKey: input.identity.ownershipKey },
          select: PROVIDER_EXECUTION_SAFE_SELECT,
        });
        if (!row || !identityMatches(row, input.identity)) {
          throw ownershipError("TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH");
        }
        if (!rolloutCurrent) {
          if (row.status === "RESERVED" || row.status === "IN_FLIGHT") {
            await tx.templateTwinProviderExecution.updateMany({
              where: { id: row.id, status: row.status },
              data: {
                status: "FAILED",
                completedAt: input.dependencies.now(),
                failureCode: "ROLLOUT_REVOKED",
              },
            });
          }
          const current =
            (await tx.templateTwinProviderExecution.findUnique({
              where: { id: row.id },
              select: PROVIDER_EXECUTION_SAFE_SELECT,
            })) ?? row;
          return { kind: "ROLLOUT_REVOKED", row: current } as const;
        }
        const authorityCurrent = await input.dependencies.currentAuthority({
          tx,
          context: input.context,
          mode: input.mode,
        });
        if (!authorityCurrent) {
          if (row.status === "RESERVED" || row.status === "IN_FLIGHT") {
            await tx.templateTwinProviderExecution.updateMany({
              where: { id: row.id, status: row.status },
              data: {
                status: "FAILED",
                completedAt: input.dependencies.now(),
                failureCode: "AUTHORITY_REVOKED_BEFORE_PROVIDER",
              },
            });
          }
          const current =
            (await tx.templateTwinProviderExecution.findUnique({
              where: { id: row.id },
              select: PROVIDER_EXECUTION_SAFE_SELECT,
            })) ?? row;
          return { kind: "AUTHORITY_REVOKED", row: current } as const;
        }
        if (row.status !== "RESERVED") return disposition(row);
        const claimedAt = input.dependencies.now();
        const claimed = await tx.templateTwinProviderExecution.updateMany({
          where: { id: row.id, status: "RESERVED", claimId: null },
          data: {
            status: "IN_FLIGHT",
            invocationCount: 1,
            claimId: input.claimId,
            claimedAt,
            invokedAt: claimedAt,
          },
        });
        const current = await tx.templateTwinProviderExecution.findUnique({
          where: { id: row.id },
          select: PROVIDER_EXECUTION_SAFE_SELECT,
        });
        if (!current || !identityMatches(current, input.identity)) {
          throw ownershipError("TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH");
        }
        return claimed.count === 1 && current.claimId === input.claimId
          ? ({ kind: "CLAIMED", row: current } as const)
          : disposition(current);
      },
      { isolationLevel: Prisma.TransactionIsolationLevel.ReadCommitted },
    );

  try {
    return await runClaim();
  } catch (error) {
    const current =
      await input.dependencies.db.templateTwinProviderExecution.findUnique({
        where: { ownershipKey: input.identity.ownershipKey },
        select: PROVIDER_EXECUTION_SAFE_SELECT,
      });
    if (!current || !identityMatches(current, input.identity)) throw error;
    if (current.status === "RESERVED") {
      // The uncertain transaction provably did not commit a claim. Repeating
      // the same CAS token cannot create a second owner.
      return runClaim();
    }
    if (current.status === "IN_FLIGHT" && current.claimId === input.claimId) {
      return { kind: "CLAIMED", row: current };
    }
    return disposition(current);
  }
}

function jsonRoundTrip(value: unknown): Prisma.JsonValue {
  let serialized: string | undefined;
  try {
    serialized = JSON.stringify(value);
  } catch {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_RESULT_INVALID");
  }
  if (serialized === undefined) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_RESULT_INVALID");
  }
  return JSON.parse(serialized) as Prisma.JsonValue;
}

function validatedResult<T>(
  row: ProviderExecutionRow,
  validate: (output: unknown) => T,
): T {
  const payload = row.resultPayload;
  if (
    row.status !== "SUCCEEDED" ||
    row.resultVersion !== TEMPLATE_TWIN_PROVIDER_RESULT_VERSION ||
    !row.resultSha256 ||
    !payload ||
    typeof payload !== "object" ||
    Array.isArray(payload) ||
    (payload as { contractVersion?: unknown }).contractVersion !==
      TEMPLATE_TWIN_PROVIDER_RESULT_VERSION ||
    canonicalSha256(payload) !== row.resultSha256
  ) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_RESULT_INVALID");
  }
  try {
    return validate((payload as unknown as ProviderResultEnvelope).output);
  } catch {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_RESULT_INVALID");
  }
}

async function terminalRow(input: {
  readonly dependencies: TemplateTwinProviderRuntimeDependencies;
  readonly executionId: string;
}): Promise<ProviderExecutionRow | null> {
  const deadline = Date.now() + input.dependencies.terminalWaitMs;
  do {
    const row =
      await input.dependencies.db.templateTwinProviderExecution.findUnique({
        where: { id: input.executionId },
        select: PROVIDER_EXECUTION_SAFE_SELECT,
      });
    if (!row || row.status !== "IN_FLIGHT") return row;
    await input.dependencies.sleep(input.dependencies.pollMs);
  } while (Date.now() < deadline);
  return input.dependencies.db.templateTwinProviderExecution.findUnique({
    where: { id: input.executionId },
    select: PROVIDER_EXECUTION_SAFE_SELECT,
  });
}

async function finishFailure(input: {
  readonly dependencies: TemplateTwinProviderRuntimeDependencies;
  readonly executionId: string;
  readonly claimId: string;
  readonly mode: TemplateTwinProviderMode;
}): Promise<never> {
  const unknown = input.mode === "LIVE";
  try {
    await input.dependencies.db.templateTwinProviderExecution.updateMany({
      where: {
        id: input.executionId,
        status: "IN_FLIGHT",
        claimId: input.claimId,
      },
      data: {
        status: unknown ? "UNKNOWN_OUTCOME" : "FAILED",
        completedAt: input.dependencies.now(),
        failureCode: unknown
          ? "PROVIDER_OUTCOME_UNKNOWN"
          : "PROVIDER_INVOCATION_FAILED",
      },
    });
  } catch {
    // A database outage must not permit provider replay. The original error
    // is deliberately replaced by the safe terminal classification below.
  }
  throw ownershipError(
    unknown
      ? "TEMPLATE_TWIN_PROVIDER_OUTCOME_UNKNOWN"
      : "TEMPLATE_TWIN_PROVIDER_EXECUTION_FAILED",
  );
}

async function finishSuccess<T>(input: {
  readonly dependencies: TemplateTwinProviderRuntimeDependencies;
  readonly identity: ProviderExecutionIdentity;
  readonly context: TemplateTwinProviderOwnershipContext;
  readonly mode: TemplateTwinProviderMode;
  readonly claimId: string;
  readonly output: T;
  readonly validate: (output: unknown) => T;
}): Promise<{ readonly row: ProviderExecutionRow; readonly output: T }> {
  const canonicalOutput = jsonRoundTrip(input.output);
  let validated: T;
  try {
    validated = input.validate(canonicalOutput);
  } catch {
    return finishFailure({
      dependencies: input.dependencies,
      executionId: input.identity.id,
      claimId: input.claimId,
      mode: "DETERMINISTIC_MOCK",
    });
  }
  const resultPayload: Prisma.InputJsonValue = {
    contractVersion: TEMPLATE_TWIN_PROVIDER_RESULT_VERSION,
    output: canonicalOutput,
  };
  const resultSha256 = canonicalSha256(resultPayload);
  try {
    const completion = await input.dependencies.db.$transaction(
      async (tx) => {
        const rolloutCurrent = await input.dependencies.lockRollout({
          tx,
          context: input.context,
          mode: input.mode,
        });
        if (!rolloutCurrent) {
          await tx.templateTwinProviderExecution.updateMany({
            where: {
              id: input.identity.id,
              status: "IN_FLIGHT",
              claimId: input.claimId,
            },
            data: {
              status: "FAILED",
              completedAt: input.dependencies.now(),
              failureCode: "ROLLOUT_REVOKED_AFTER_PROVIDER",
            },
          });
          return {
            count: 0,
            rolloutRevoked: true,
            authorityRevoked: false,
          };
        }
        const authorityCurrent = await input.dependencies.currentAuthority({
          tx,
          context: input.context,
          mode: input.mode,
        });
        if (!authorityCurrent) {
          await tx.templateTwinProviderExecution.updateMany({
            where: {
              id: input.identity.id,
              status: "IN_FLIGHT",
              claimId: input.claimId,
            },
            data: {
              status: "FAILED",
              completedAt: input.dependencies.now(),
              failureCode: "AUTHORITY_REVOKED_AFTER_PROVIDER",
            },
          });
          return {
            count: 0,
            rolloutRevoked: false,
            authorityRevoked: true,
          };
        }
        const update = await tx.templateTwinProviderExecution.updateMany({
          where: {
            id: input.identity.id,
            status: "IN_FLIGHT",
            claimId: input.claimId,
          },
          data: {
            status: "SUCCEEDED",
            resultPayload,
            resultSha256,
            resultVersion: TEMPLATE_TWIN_PROVIDER_RESULT_VERSION,
            completedAt: input.dependencies.now(),
          },
        });
        return {
          count: update.count,
          rolloutRevoked: false,
          authorityRevoked: false,
        };
      },
      { isolationLevel: Prisma.TransactionIsolationLevel.ReadCommitted },
    );
    if (completion.rolloutRevoked) {
      throw ownershipError("TEMPLATE_TWIN_PROVIDER_ROLLOUT_REVOKED");
    }
    if (completion.authorityRevoked) {
      throw ownershipError("TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED");
    }
  } catch (error) {
    if (
      error instanceof TemplateTwinProviderOwnershipError &&
      (error.code === "TEMPLATE_TWIN_PROVIDER_ROLLOUT_REVOKED" ||
        error.code === "TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED")
    ) {
      throw error;
    }
    const current =
      await input.dependencies.db.templateTwinProviderExecution.findUnique({
        where: { id: input.identity.id },
        select: PROVIDER_EXECUTION_SAFE_SELECT,
      });
    if (
      current?.status === "SUCCEEDED" &&
      current.claimId === input.claimId &&
      current.resultSha256 === resultSha256
    ) {
      await assertCurrentProviderAuthority({
        dependencies: input.dependencies,
        context: input.context,
        mode: input.mode,
      });
      return { row: current, output: validatedResult(current, input.validate) };
    }
    try {
      await input.dependencies.db.templateTwinProviderExecution.updateMany({
        where: {
          id: input.identity.id,
          status: "IN_FLIGHT",
          claimId: input.claimId,
        },
        data: {
          status: "UNKNOWN_OUTCOME",
          completedAt: input.dependencies.now(),
          failureCode: "RESULT_COMMIT_AMBIGUOUS",
        },
      });
    } catch {
      // Fail closed even if the database cannot record the terminal marker.
    }
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_OUTCOME_UNKNOWN");
  }
  const row =
    await input.dependencies.db.templateTwinProviderExecution.findUnique({
      where: { id: input.identity.id },
      select: PROVIDER_EXECUTION_SAFE_SELECT,
    });
  if (
    !row ||
    row.claimId !== input.claimId ||
    row.resultSha256 !== resultSha256
  ) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_OUTCOME_UNKNOWN");
  }
  return { row, output: validated };
}

function recordReceiptExecution(
  state: ProviderOwnershipState,
  row: ProviderExecutionRow,
): void {
  if (!row.resultSha256 || !SHA256.test(row.resultSha256)) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_RESULT_INVALID");
  }
  state.executions.set(row.id, {
    executionId: row.id,
    operation: row.operation as TemplateTwinProviderOperation,
    operationInstance: row.operationInstance,
    resultSha256: row.resultSha256,
    actorUserId: row.actorUserId,
    providerMode: row.providerMode as TemplateTwinProviderMode,
    pinnedGlobalRolloutGeneration: row.pinnedGlobalRolloutGeneration,
    pinnedPracticeRolloutGeneration: row.pinnedPracticeRolloutGeneration,
    releaseId: row.releaseId,
    releaseIdentitySha256: row.releaseIdentitySha256,
    runtimeManifestSha256: row.runtimeManifestSha256,
    runtimeInstanceId: row.runtimeInstanceId,
    runtimeIdentitySha256: row.runtimeIdentitySha256,
    syntheticAdmissionId: row.syntheticAdmissionId,
  });
}

async function assertCurrentProviderAuthority(input: {
  readonly dependencies: TemplateTwinProviderRuntimeDependencies;
  readonly context: TemplateTwinProviderOwnershipContext;
  readonly mode: TemplateTwinProviderMode;
}): Promise<void> {
  const authorized = await input.dependencies.db.$transaction(
    async (tx) =>
      (await input.dependencies.lockRollout({
        tx,
        context: input.context,
        mode: input.mode,
      })) &&
      (await input.dependencies.currentAuthority({
        tx,
        context: input.context,
        mode: input.mode,
      })),
    { isolationLevel: Prisma.TransactionIsolationLevel.ReadCommitted },
  );
  if (!authorized) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED");
  }
}

async function runTemplateTwinOwnedProviderInContext<T>(
  input: TemplateTwinOwnedProviderInput<T>,
  state: ProviderOwnershipState,
  dependencyOverrides: Partial<TemplateTwinProviderRuntimeDependencies>,
): Promise<T> {
  if (state.tainted) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE");
  }
  const operationInstance = input.operationInstance ?? "primary";
  if (
    state.notApplicable.has(providerPlanKey(input.operation, operationInstance))
  ) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE");
  }
  const dependencies = { ...DEFAULT_DEPENDENCIES, ...dependencyOverrides };
  const mode = dependencies.providerMode();
  if (
    input.operation === "SYNTHETIC_EVIDENCE_TRANSCRIPTION" &&
    mode !== "SYNTHETIC_QA"
  ) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
  }
  if (mode === "SYNTHETIC_QA") {
    assertTemplateTwinSyntheticQaWorkerLeaseHealthy();
  }
  const identity = buildIdentity({
    context: state.context,
    provider: input,
    mode,
    executionId: dependencies.executionId(),
  });
  const reserved = await reserveExecution(dependencies, identity);
  if (!identityMatches(reserved, identity)) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH");
  }
  const claimId = dependencies.claimId();
  let claim = await claimExecution({
    dependencies,
    identity: { ...identity, id: reserved.id },
    context: state.context,
    mode,
    claimId,
  });
  if (claim.kind === "IN_PROGRESS") {
    const row = await terminalRow({
      dependencies,
      executionId: claim.row.id,
    });
    if (!row) {
      throw ownershipError("TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH");
    }
    claim = disposition(row);
  }
  if (claim.kind === "SUCCEEDED") {
    await assertCurrentProviderAuthority({
      dependencies,
      context: state.context,
      mode,
    });
    const output = validatedResult(claim.row, input.validate);
    recordReceiptExecution(state, claim.row);
    return output;
  }
  if (claim.kind === "ROLLOUT_REVOKED") {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_ROLLOUT_REVOKED");
  }
  if (claim.kind === "AUTHORITY_REVOKED") {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED");
  }
  if (claim.kind === "UNKNOWN") {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_OUTCOME_UNKNOWN");
  }
  if (claim.kind === "FAILED") {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_EXECUTION_FAILED");
  }
  if (claim.kind !== "CLAIMED") {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_EXECUTION_IN_PROGRESS");
  }

  let providerOutput: T;
  try {
    providerOutput = await input.invoke({
      idempotencyKey: identity.idempotencyKey,
    });
  } catch {
    return finishFailure({
      dependencies,
      executionId: claim.row.id,
      claimId,
      mode,
    });
  }
  const completed = await finishSuccess({
    dependencies,
    identity: { ...identity, id: claim.row.id },
    context: state.context,
    mode,
    claimId,
    output: providerOutput,
    validate: input.validate,
  });
  recordReceiptExecution(state, completed.row);
  return completed.output;
}

export async function runTemplateTwinOwnedProvider<T>(
  input: TemplateTwinOwnedProviderInput<T>,
  dependencyOverrides: Partial<TemplateTwinProviderRuntimeDependencies> = {},
): Promise<T> {
  const state = ownershipContext.getStore();
  if (!state?.active) {
    assertProviderOwnershipMayBeAbsent();
    return input.invoke({});
  }
  try {
    return await runTemplateTwinOwnedProviderInContext(
      input,
      state,
      dependencyOverrides,
    );
  } catch (error) {
    state.tainted = true;
    throw error;
  }
}

export async function runTemplateTwinOwnedModelComplete<T>(input: {
  readonly operation: TemplateTwinProviderOperation;
  readonly operationInstance?: string;
  readonly operationVersion: string;
  /**
   * Provider-only correlation. It is hashed into the exact input identity but
   * never occupies the visit ledger field unless it is a real visit ID.
   */
  readonly providerCorrelationId?: string | null;
  readonly args: CompleteArgs<T>;
  readonly client?: Pick<typeof modelClient, "complete">;
}): Promise<T> {
  const client = input.client ?? modelClient;
  const context = getTemplateTwinProviderOwnershipContext();
  if (!context) {
    assertProviderOwnershipMayBeAbsent();
    return client.complete(input.args);
  }
  const providerCorrelationId = assertExactProviderLogIdentity({
    context,
    practiceId: input.args.practiceId,
    userId: input.args.userId,
    visitId: input.args.visitId,
    providerCorrelationId: input.providerCorrelationId,
    allowedCorrelationScopes: [
      "SOURCE_INTAKE",
      "CUSTOM_EXAMPLE",
      "SYNTHETIC_EVIDENCE",
    ],
  });
  const schemaIdentity = z.toJSONSchema(input.args.schema);
  return runTemplateTwinOwnedProvider({
    operation: input.operation,
    operationInstance: input.operationInstance,
    operationVersion: input.operationVersion,
    provider: input.args.provider,
    model: input.args.model,
    providerConfiguration: {
      maxTokens: input.args.maxTokens ?? null,
      temperature: input.args.temperature ?? null,
      useToolUse: input.args.useToolUse ?? null,
      schema: schemaIdentity,
    },
    inputIdentity: {
      purpose: input.args.purpose,
      providerCorrelationId,
      system: input.args.system,
      user: input.args.user,
      schema: schemaIdentity,
    },
    invoke: ({ idempotencyKey }) =>
      client.complete({
        ...input.args,
        idempotencyKey,
        retryOnSchemaFail: idempotencyKey
          ? false
          : input.args.retryOnSchemaFail,
      }),
    validate: (output) => input.args.schema.parse(output),
  });
}

const completeTextResultSchema = z.object({
  text: z.string(),
  inputTokens: z.number().int().nonnegative(),
  outputTokens: z.number().int().nonnegative(),
});

export async function runTemplateTwinOwnedModelCompleteText(input: {
  readonly operation: TemplateTwinProviderOperation;
  readonly operationInstance?: string;
  readonly operationVersion: string;
  readonly providerCorrelationId?: string | null;
  readonly args: CompleteTextArgs;
  readonly client?: Pick<typeof modelClient, "completeText">;
}): Promise<AnthropicCompleteTextResult> {
  const client = input.client ?? modelClient;
  const context = getTemplateTwinProviderOwnershipContext();
  if (!context) {
    assertProviderOwnershipMayBeAbsent();
    return client.completeText(input.args);
  }
  const providerCorrelationId = assertExactProviderLogIdentity({
    context,
    practiceId: input.args.practiceId,
    userId: input.args.userId,
    visitId: input.args.visitId,
    providerCorrelationId: input.providerCorrelationId,
    allowedCorrelationScopes: [
      "SOURCE_INTAKE",
      "CUSTOM_EXAMPLE",
      "SYNTHETIC_EVIDENCE",
    ],
  });
  return runTemplateTwinOwnedProvider({
    operation: input.operation,
    operationInstance: input.operationInstance,
    operationVersion: input.operationVersion,
    provider: input.args.provider,
    model: input.args.model,
    providerConfiguration: {
      maxTokens: input.args.maxTokens ?? null,
      temperature: input.args.temperature ?? null,
    },
    inputIdentity: {
      purpose: input.args.purpose,
      providerCorrelationId,
      system: input.args.system,
      user: input.args.user,
    },
    invoke: ({ idempotencyKey }) =>
      client.completeText({ ...input.args, idempotencyKey }),
    validate: (output) => completeTextResultSchema.parse(output),
  });
}

export interface TemplateTwinTranscriptionAudioIdentity {
  readonly objectKey: string;
  readonly objectEtag: string | null;
  readonly sizeBytes: number;
  readonly lastModifiedIso: string | null;
  readonly sha256?: string;
}

function validateOwnedTranscriptionResult(output: unknown): TranscribeResult {
  if (
    !output ||
    typeof output !== "object" ||
    (output as { provider?: unknown }).provider !== "deepgram-batch" ||
    typeof (output as { transcript?: unknown }).transcript !== "string" ||
    typeof (output as { durationSec?: unknown }).durationSec !== "number" ||
    !Number.isFinite((output as { durationSec: number }).durationSec) ||
    (output as { fallbackUsed?: unknown }).fallbackUsed !== false ||
    (output as { raw?: { kind?: unknown } }).raw?.kind !== "deepgram"
  ) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_RESULT_INVALID");
  }
  return output as TranscribeResult;
}

export async function runTemplateTwinOwnedTranscribe(input: {
  readonly operation:
    | "L1_TRANSCRIBE"
    | "L1B_TRANSCRIBE"
    | "SYNTHETIC_EVIDENCE_TRANSCRIPTION";
  readonly operationVersion: string;
  readonly providerCorrelationId?: string | null;
  readonly audioIdentity: TemplateTwinTranscriptionAudioIdentity;
  readonly args: TranscribeArgs;
  readonly transcriber?: typeof transcribe;
  readonly dependencies?: Partial<TemplateTwinProviderRuntimeDependencies>;
}): Promise<TranscribeResult> {
  const invokeTranscription = input.transcriber ?? transcribe;
  const context = getTemplateTwinProviderOwnershipContext();
  if (!context) {
    if (input.operation === "SYNTHETIC_EVIDENCE_TRANSCRIPTION") {
      throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
    }
    assertProviderOwnershipMayBeAbsent();
    return invokeTranscription(input.args);
  }
  if (
    input.operation === "SYNTHETIC_EVIDENCE_TRANSCRIPTION" &&
    (context.scope !== "SYNTHETIC_EVIDENCE" ||
      context.visitId === null ||
      context.visitInputMode !== "audio_upload" ||
      context.logicalAttempt !== 1 ||
      context.syntheticAdmissionId === null ||
      !Buffer.isBuffer(input.args.audio) ||
      input.audioIdentity.sha256 === undefined ||
      !SHA256.test(input.audioIdentity.sha256) ||
      createHash("sha256").update(input.args.audio).digest("hex") !==
        input.audioIdentity.sha256 ||
      input.args.audio.byteLength !== input.audioIdentity.sizeBytes ||
      input.args.allowCrossProviderFallback === true ||
      (input.args.deepgram?.maxAttempts !== undefined &&
        input.args.deepgram.maxAttempts !== 1))
  ) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
  }
  const providerCorrelationId = assertExactProviderLogIdentity({
    context,
    practiceId: input.args.practiceId,
    userId: input.args.userId,
    visitId: input.args.visitId,
    providerCorrelationId: input.providerCorrelationId,
    allowedCorrelationScopes: ["SYNTHETIC_EVIDENCE"],
  });
  if (
    input.audioIdentity.objectKey.length === 0 ||
    !input.audioIdentity.objectEtag?.trim() ||
    !Number.isSafeInteger(input.audioIdentity.sizeBytes) ||
    input.audioIdentity.sizeBytes < 1
  ) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
  }
  const model =
    input.args.deepgram?.model ??
    process.env.DEEPGRAM_MODEL?.trim() ??
    "nova-3-medical";
  const options = input.args.deepgram?.options ?? {};
  const ownedArgs: TranscribeArgs = {
    ...input.args,
    allowCrossProviderFallback: false,
    deepgram: {
      ...input.args.deepgram,
      maxAttempts: 1,
    },
  };
  return runTemplateTwinOwnedProvider(
    {
      operation: input.operation,
      operationVersion: input.operationVersion,
      provider: "deepgram",
      model,
      providerConfiguration: {
        mimeType: input.args.mimeType,
        language: input.args.language ?? "en",
        timeoutMs: input.args.deepgram?.timeoutMs ?? 10 * 60 * 1_000,
        diarize: options.diarize ?? true,
        utterances: options.utterances ?? true,
        detectLanguage: options.detectLanguage ?? false,
        keyterms: input.args.deepgram?.keyterms ?? [],
        crossProviderFallback: false,
        maxAttempts: 1,
      },
      inputIdentity: {
        purpose: input.args.purpose,
        providerCorrelationId,
        audio: input.audioIdentity,
        mimeType: input.args.mimeType,
        language: input.args.language ?? "en",
      },
      invoke: () => invokeTranscription(ownedArgs),
      validate: validateOwnedTranscriptionResult,
    },
    input.dependencies,
  );
}
