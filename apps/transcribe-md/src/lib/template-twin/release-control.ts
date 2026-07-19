import "server-only";

import { randomUUID } from "node:crypto";

import { Prisma, type PrismaClient } from "@prisma/client";

import { runSerializableTransactionWithRetry } from "@/lib/db/transaction-retry";
import {
  TEMPLATE_TWIN_ROLLBACK_COMPAT_RUNTIME_MODE,
  resolveTemplateTwinRuntimeMode,
} from "@/lib/runtime-protocol";
import {
  assertTemplateTwinAuditMetadata,
  type EnqueueTemplateTwinAuditInput,
} from "./audit-outbox";
import {
  TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID,
  TEMPLATE_TWIN_RELEASE_CONTROL_LOCK_KEY,
  TEMPLATE_TWIN_RELEASE_CONTROL_LOCK_NAMESPACE,
} from "./rollout";
import {
  buildTemplateTwinCohortPlan,
  buildTemplateTwinRuntimeManifest,
  parseTemplateTwinGuardrailPolicy,
  templateTwinApprovalConfirmation,
  templateTwinCheckpointConfirmation,
  templateTwinGuardrailPolicySha256,
  templateTwinReleaseIdentitySha256,
  TEMPLATE_TWIN_RELEASE_DISCIPLINES,
  TEMPLATE_TWIN_RELEASE_IDENTITY_VERSION,
  TEMPLATE_TWIN_RELEASE_STAGES,
  type TemplateTwinApprovalDecision,
  type TemplateTwinReleaseDiscipline,
  type TemplateTwinReleaseIdentityEvidence,
  type TemplateTwinRuntimeRequirementInput,
  type TemplateTwinReleaseStage,
  type TemplateTwinReleaseStatus,
} from "./release-control-contracts";
import releaseControlDatabase from "./release-control-db";

const database = releaseControlDatabase as PrismaClient;

export const TEMPLATE_TWIN_RELEASE_RUNTIME_ENV = {
  sourceCommitSha: "TEMPLATE_TWIN_RELEASE_COMMIT_SHA",
  appImageDigest: "TEMPLATE_TWIN_APP_IMAGE_DIGEST",
  workerImageDigest: "TEMPLATE_TWIN_WORKER_IMAGE_DIGEST",
  migratorImageDigest: "TEMPLATE_TWIN_MIGRATOR_IMAGE_DIGEST",
} as const;

export interface TemplateTwinReleaseActor {
  readonly userId: string;
  readonly sessionId: string;
}

interface VerifiedControlPrincipal {
  readonly userId: string;
  readonly email: string;
  readonly practiceId: string;
}

interface VerifiedReleaseActor extends VerifiedControlPrincipal {
  readonly sessionSha256: string;
}

interface VerifiedReleaseAction extends VerifiedReleaseActor {
  readonly nonce: string;
  readonly issuedAt: Date;
}

type VerifiedMonitoringPrincipal = VerifiedControlPrincipal;

interface GlobalControlRow {
  readonly enabled: boolean;
  readonly generation: bigint | number | string;
  readonly rollbackFenceState: string;
  readonly rollbackOperationId: string | null;
}

interface ReleaseRow extends TemplateTwinReleaseIdentityEvidence {
  readonly id: string;
  readonly identityVersion: string;
  readonly releaseIdentitySha256: string;
  readonly guardrailPolicySha256: string;
  readonly authorizedPracticeManifestSha256: string;
  readonly runtimeManifestSha256: string;
  readonly guardrailPolicy: unknown;
  readonly status: string;
  readonly generation: bigint | number | string;
  readonly createdById: string;
  readonly frozenById: string | null;
  readonly frozenAt: Date | null;
  readonly createdAt: Date;
  readonly updatedAt: Date;
}

interface ManifestRow {
  readonly id: string;
  readonly practiceId: string;
  readonly practiceSlugSnapshot: string;
  readonly physicianCountSnapshot: number;
  readonly cohortRank: number;
  readonly cohortHashSha256: string;
  readonly isCanary: boolean;
  readonly activationStage: string;
  readonly activationStageOrdinal: number;
  readonly templateTwinEnabled?: boolean;
  readonly templateTwinRolloutGeneration?: bigint | number | string;
  readonly isActive?: boolean;
}

interface RuntimeRequirementRow {
  readonly id: string;
  readonly instanceId: string;
  readonly component: "APP" | "WORKER";
  readonly sourceCommitSha: string;
  readonly imageDigest: string;
}

interface CheckpointRow {
  readonly id: string;
  readonly releaseId: string;
  readonly releaseIdentitySha256: string;
  readonly stage: string;
  readonly ordinal: number;
  readonly targetPercent: number;
  readonly targetPhysicianCount: number;
  readonly assignedPhysicianCount: number;
  readonly status: string;
  readonly minimumBakeSeconds: number;
  readonly activatedPhysicianCount: number | null;
  readonly passedPhysicianCount: number | null;
  readonly activatedAt: Date | null;
  readonly earliestPassAt: Date | null;
  readonly passedAt: Date | null;
  readonly revokedAt: Date | null;
  readonly activatedById: string | null;
  readonly passedById: string | null;
  readonly activationOutboxEventKey: string | null;
  readonly passOutboxEventKey: string | null;
}

interface MetricRow {
  readonly id: string;
  readonly checkpointId: string;
  readonly releaseGeneration: bigint | number | string;
  readonly globalGeneration: bigint | number | string;
  readonly schemaVersion: string;
  readonly sampleCount: number;
  readonly observationStartedAt: Date;
  readonly observationEndedAt: Date;
  readonly metrics: unknown;
  readonly canonicalSha256: string;
  readonly evaluation: string;
  readonly missingMetrics: string[];
  readonly breachedMetrics: string[];
  readonly blockingReasons: string[];
  readonly attestationKeyId: string;
  readonly attestationNonceSha256: string;
  readonly attestationSignatureSha256: string;
  readonly receiptVerified?: boolean;
  readonly createdAt: Date;
}

interface AuthorityRow {
  readonly id: string;
  readonly discipline: string;
}

interface ApprovalSummaryRow {
  readonly id: string;
  readonly discipline: string;
  readonly decision: string;
  readonly evidenceSha256: string;
  readonly actorId: string;
  readonly actorEmailSnapshot: string | null;
  readonly authorityAssignmentId: string;
  readonly auditOutboxEventKey: string;
  readonly decidedAt: Date;
  readonly authorityActive: boolean;
}

type ControlTransaction = Prisma.TransactionClient;

function releaseAuditValue(input: EnqueueTemplateTwinAuditInput): Prisma.Sql {
  assertTemplateTwinAuditMetadata(input.metadata);
  return Prisma.sql`(
    ${randomUUID()}, ${input.practiceId}, ${input.actorId ?? null},
    ${input.actorEmailSnapshot ?? null}, ${input.ipAddress ?? null}::INET,
    ${input.userAgent ?? null}, ${input.eventKey},
    ${input.action}::"AuditAction", ${input.targetId ?? null},
    ${input.targetType ?? null},
    ${JSON.stringify(input.metadata ?? null)}::JSONB,
    'PENDING'::"TemplateTwinAuditOutboxStatus", 0, CURRENT_TIMESTAMP
  )`;
}

async function enqueueReleaseAuditBatch(
  tx: ControlTransaction,
  inputs: readonly EnqueueTemplateTwinAuditInput[],
): Promise<void> {
  if (inputs.length === 0) return;
  await tx.$executeRaw(Prisma.sql`
    INSERT INTO "template_twin_audit_outbox" (
      "id", "practiceId", "actorId", "actorEmailSnapshot", "ipAddress",
      "userAgent", "eventKey", "action", "targetId", "targetType",
      "metadata", "status", "attemptCount", "updatedAt"
    ) VALUES ${Prisma.join(inputs.map(releaseAuditValue))}
  `);
}

async function enqueueReleaseAudit(
  tx: ControlTransaction,
  input: EnqueueTemplateTwinAuditInput,
): Promise<void> {
  await enqueueReleaseAuditBatch(tx, [input]);
}

export type TemplateTwinReleaseControlErrorCode =
  | "TEMPLATE_TWIN_RELEASE_INVALID_REQUEST"
  | "TEMPLATE_TWIN_RELEASE_UNAUTHORIZED"
  | "TEMPLATE_TWIN_RELEASE_NOT_FOUND"
  | "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT"
  | "TEMPLATE_TWIN_RELEASE_STALE_GENERATION"
  | "TEMPLATE_TWIN_RELEASE_IDENTITY_MISMATCH"
  | "TEMPLATE_TWIN_RELEASE_RUNTIME_MISMATCH"
  | "TEMPLATE_TWIN_RELEASE_APPROVAL_INCOMPLETE"
  | "TEMPLATE_TWIN_RELEASE_AUTHORITY_MISSING"
  | "TEMPLATE_TWIN_RELEASE_ROLLBACK_FENCED"
  | "TEMPLATE_TWIN_RELEASE_GUARDRAIL_BLOCKED"
  | "TEMPLATE_TWIN_RELEASE_CONTROL_UNAVAILABLE";

export class TemplateTwinReleaseControlError extends Error {
  constructor(
    readonly code: TemplateTwinReleaseControlErrorCode,
    message: string,
  ) {
    super(message);
    this.name = "TemplateTwinReleaseControlError";
  }
}

function exactGeneration(value: bigint | number | string): bigint {
  try {
    const parsed = typeof value === "bigint" ? value : BigInt(value);
    if (parsed <= BigInt(0)) throw new Error("non-positive");
    return parsed;
  } catch {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_CONTROL_UNAVAILABLE",
      "A persisted release generation is invalid.",
    );
  }
}

function expectedGeneration(value: string): bigint {
  if (!/^[1-9][0-9]{0,18}$/u.test(value)) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_INVALID_REQUEST",
      "Expected generation must be a positive decimal integer.",
    );
  }
  return BigInt(value);
}

function uuid(value: string, field = "identifier"): string {
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu.test(
      value,
    )
  ) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_INVALID_REQUEST",
      `Release ${field} is invalid.`,
    );
  }
  return value.toLowerCase();
}

function reasonCode(value: string): string {
  if (!/^[A-Z][A-Z0-9_]{2,79}$/u.test(value)) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_INVALID_REQUEST",
      "Revocation reason code is invalid.",
    );
  }
  return value;
}

function assertExactConfirmation(actual: string, expected: string): void {
  if (actual !== expected) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_INVALID_REQUEST",
      `Type exactly “${expected}” to confirm this operation.`,
    );
  }
}

async function acquireControlPlaneLock(tx: ControlTransaction): Promise<void> {
  await tx.$executeRaw(Prisma.sql`
    SELECT pg_advisory_xact_lock(
      ${TEMPLATE_TWIN_RELEASE_CONTROL_LOCK_NAMESPACE},
      ${TEMPLATE_TWIN_RELEASE_CONTROL_LOCK_KEY}
    )
  `);
}

async function lockGlobalControl(
  tx: ControlTransaction,
): Promise<GlobalControlRow> {
  const rows = await tx.$queryRaw<GlobalControlRow[]>(Prisma.sql`
    SELECT "enabled", "generation", "rollbackFenceState", "rollbackOperationId"
    FROM "template_twin_rollout_controls"
    WHERE "id" = ${TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID}
    FOR UPDATE
  `);
  const row = rows[0];
  if (!row) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_CONTROL_UNAVAILABLE",
      "The global Template Twin rollout control is unavailable.",
    );
  }
  return row;
}

async function lockRelease(
  tx: ControlTransaction,
  releaseId: string,
): Promise<ReleaseRow> {
  const rows = await tx.$queryRaw<ReleaseRow[]>(Prisma.sql`
    SELECT * FROM "template_twin_release_candidates"
    WHERE "id" = ${releaseId}::UUID
    FOR UPDATE
  `);
  const row = rows[0];
  if (!row) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_NOT_FOUND",
      "The release candidate was not found.",
    );
  }
  return row;
}

async function lockCheckpoints(
  tx: ControlTransaction,
  releaseId: string,
): Promise<CheckpointRow[]> {
  return tx.$queryRaw<CheckpointRow[]>(Prisma.sql`
    SELECT * FROM "template_twin_release_checkpoints"
    WHERE "releaseId" = ${releaseId}::UUID
    ORDER BY "ordinal" ASC
    FOR UPDATE
  `);
}

async function lockManifest(
  tx: ControlTransaction,
  releaseId: string,
): Promise<ManifestRow[]> {
  // Manifest rows are immutable and every mutation of the joined practice
  // state takes the release advisory lock.  A row lock here would require the
  // least-privilege control role to have UPDATE on both tables even though this
  // path only reads them.
  return tx.$queryRaw<ManifestRow[]>(Prisma.sql`
    SELECT manifest.*,
      practice."templateTwinEnabled",
      practice."templateTwinRolloutGeneration", practice."isActive"
    FROM "template_twin_release_practices" manifest
    JOIN "practices" practice ON practice."id" = manifest."practiceId"
    WHERE manifest."releaseId" = ${releaseId}::UUID
    ORDER BY manifest."cohortRank" ASC
  `);
}

function assertManifestPracticesActive(manifest: readonly ManifestRow[]): void {
  if (manifest.length === 0 || manifest.some(({ isActive }) => !isActive)) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
      "Every release practice must remain active; remove deactivated tenants in a new exact release candidate.",
    );
  }
}

async function assertRuntimeReplicaReadiness(input: {
  readonly tx: ControlTransaction;
  readonly release: ReleaseRow;
}): Promise<void> {
  const rows = await input.tx.$queryRaw<Array<{ ready: boolean }>>(Prisma.sql`
    SELECT template_twin_release_runtime_ready(
      ${input.release.id}::UUID,
      ${input.release.releaseIdentitySha256}::CHAR(64)
    ) AS "ready"
  `);
  if (rows[0]?.ready !== true) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_RUNTIME_MISMATCH",
      "Every pinned application and worker replica must have a fresh deployment-authority attestation.",
    );
  }
}

async function lockRuntimeRequirements(
  tx: ControlTransaction,
  releaseId: string,
): Promise<RuntimeRequirementRow[]> {
  // Runtime requirements are append-only while the candidate is DRAFT and
  // immutable afterward.  The release advisory lock provides serialization;
  // no write-capable table privilege is needed for this read.
  return tx.$queryRaw<RuntimeRequirementRow[]>(Prisma.sql`
    SELECT "id", "instanceId", "component", "sourceCommitSha", "imageDigest"
    FROM "template_twin_release_runtime_requirements"
    WHERE "releaseId" = ${releaseId}::UUID
    ORDER BY "component", "instanceId"
  `);
}

async function verifyReleaseActor(
  tx: ControlTransaction,
  actor: TemplateTwinReleaseActor,
): Promise<VerifiedReleaseActor> {
  if (!actor.userId || !actor.sessionId) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_UNAUTHORIZED",
      "A live, MFA-verified platform administrator session is required.",
    );
  }
  const rows = await tx.$queryRaw<VerifiedReleaseActor[]>(Prisma.sql`
    SELECT * FROM template_twin_verify_release_actor(
      ${actor.userId}, ${actor.sessionId}
    )
  `);
  const row = rows[0];
  if (!row) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_UNAUTHORIZED",
      "A live, MFA-verified platform administrator session is required.",
    );
  }
  return row;
}

async function issueReleaseActionReceipt(input: {
  readonly tx: ControlTransaction;
  readonly actor: TemplateTwinReleaseActor;
  readonly releaseId: string;
  readonly checkpointId?: string;
  readonly action: "FREEZE" | "APPROVAL" | "ACTIVATE" | "PASS";
  readonly discipline?: TemplateTwinReleaseDiscipline;
  readonly decision?: TemplateTwinApprovalDecision;
  readonly confirmation: string;
}): Promise<VerifiedReleaseAction> {
  if (!input.actor.userId || !input.actor.sessionId) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_UNAUTHORIZED",
      "A live, MFA-verified platform administrator session is required.",
    );
  }
  const rows = await input.tx.$queryRaw<VerifiedReleaseAction[]>(Prisma.sql`
    SELECT * FROM template_twin_issue_release_action_receipt(
      ${input.actor.userId}, ${input.actor.sessionId}, ${input.releaseId}::UUID,
      ${input.checkpointId ?? null}::UUID, ${input.action},
      ${input.discipline ?? null}, ${input.decision ?? null},
      ${input.confirmation}
    )
  `);
  const receipt = rows[0];
  if (!receipt) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_UNAUTHORIZED",
      "A transaction-bound release action receipt could not be issued.",
    );
  }
  return receipt;
}

async function loadMonitoringPrincipal(
  tx: ControlTransaction,
  userId: string,
): Promise<VerifiedMonitoringPrincipal> {
  const rows = await tx.$queryRaw<VerifiedMonitoringPrincipal[]>(Prisma.sql`
    SELECT "id" AS "userId", "email", "practiceId"
    FROM "users"
    WHERE "id" = ${userId}
      AND "isActive" = TRUE
      AND "deactivatedAt" IS NULL
      AND "suspendedAt" IS NULL
      AND "softDeletedAt" IS NULL
  `);
  if (!rows[0]) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_UNAUTHORIZED",
      "The signed monitoring principal is inactive or unavailable.",
    );
  }
  return rows[0];
}

async function approvalsAreCurrent(
  tx: ControlTransaction,
  release: ReleaseRow,
): Promise<boolean> {
  const rows = await tx.$queryRaw<Array<{ approved: boolean }>>(Prisma.sql`
    SELECT template_twin_release_approvals_are_current(
      ${release.id}::UUID, ${release.releaseIdentitySha256}::CHAR(64)
    ) AS "approved"
  `);
  return rows[0]?.approved === true;
}

function assertExpectedReleaseGeneration(
  release: ReleaseRow,
  expected: bigint,
): void {
  if (exactGeneration(release.generation) !== expected) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_STALE_GENERATION",
      "The release changed after this workbench was loaded. Refresh and review the new state.",
    );
  }
}

function assertExpectedGlobalGeneration(
  global: GlobalControlRow,
  expected: bigint,
): void {
  if (exactGeneration(global.generation) !== expected) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_STALE_GENERATION",
      "The global rollout changed after this workbench was loaded. Refresh and review the new state.",
    );
  }
}

/**
 * Safety actions are deliberately monotonic: a revocation based on this exact
 * immutable release identity may cross a concurrently committed enablement.
 * A caller can never claim a generation from the future, but an intervening
 * checkpoint advance must not make a human rejection or kill request inert.
 */
function assertSafetyGenerationNotFuture(
  persisted: bigint | number | string,
  requested: bigint,
): bigint {
  const observed = exactGeneration(persisted);
  if (requested > observed) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_STALE_GENERATION",
      "The requested safety generation is ahead of persisted release state.",
    );
  }
  return observed;
}

function assertRollbackFenceOpen(global: GlobalControlRow): void {
  if (
    global.rollbackFenceState !== "OPEN" ||
    global.rollbackOperationId !== null
  ) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_ROLLBACK_FENCED",
      "Template Twin rollout cannot advance while the rollback fence is active.",
    );
  }
}

function assertRuntimeIdentity(
  release: ReleaseRow,
  env: Readonly<Record<string, string | undefined>> = process.env,
): void {
  let runtimeMode: string;
  try {
    runtimeMode = resolveTemplateTwinRuntimeMode(env);
  } catch {
    runtimeMode = "invalid";
  }
  if (
    env.TEMPLATE_TWIN_KILL_SWITCH?.trim().toLowerCase() !== "false" ||
    runtimeMode === TEMPLATE_TWIN_ROLLBACK_COMPAT_RUNTIME_MODE ||
    env[TEMPLATE_TWIN_RELEASE_RUNTIME_ENV.sourceCommitSha] !==
      release.sourceCommitSha ||
    env[TEMPLATE_TWIN_RELEASE_RUNTIME_ENV.appImageDigest] !==
      release.appImageDigest ||
    env[TEMPLATE_TWIN_RELEASE_RUNTIME_ENV.workerImageDigest] !==
      release.workerImageDigest ||
    env[TEMPLATE_TWIN_RELEASE_RUNTIME_ENV.migratorImageDigest] !==
      release.migratorImageDigest
  ) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_RUNTIME_MISMATCH",
      "The deployed commit, image identity, runtime mode, or process kill switch does not match this release.",
    );
  }
}

async function assertLineageContracted(tx: ControlTransaction): Promise<void> {
  const rows = await tx.$queryRaw<Array<{ phase: string }>>(Prisma.sql`
    SELECT "phase" FROM "template_twin_lineage_migration_progress"
    WHERE "operationKey" = 'note_templates_lineage_v1'
  `);
  if (rows[0]?.phase !== "CONTRACTED") {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
      "Template lineage migration is not fully contracted.",
    );
  }
}

async function censusAuthorizedPhysicians(
  tx: ControlTransaction,
  practiceIds: readonly string[],
): Promise<number> {
  if (practiceIds.length === 0) return 0;
  const rows = await tx.$queryRaw<Array<{ count: bigint | number | string }>>(
    Prisma.sql`
      SELECT COUNT(*)::BIGINT AS "count"
      FROM "users" clinician
      WHERE clinician."practiceId" IN (${Prisma.join(practiceIds)})
        AND clinician."role" = 'DOCTOR'::"UserRole"
        AND 'TRANSCRIBE_MD'::"Product" = ANY(clinician."products")
        AND clinician."isActive" = TRUE
        AND clinician."deactivatedAt" IS NULL
        AND clinician."suspendedAt" IS NULL
        AND clinician."softDeletedAt" IS NULL
    `,
  );
  const count = Number(rows[0]?.count ?? 0);
  if (!Number.isSafeInteger(count) || count < 0) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_CONTROL_UNAVAILABLE",
      "Authorized physician census could not be represented safely.",
    );
  }
  return count;
}

async function disableReleaseExposure(input: {
  tx: ControlTransaction;
  actor: VerifiedControlPrincipal;
  global: GlobalControlRow;
  manifest: readonly ManifestRow[];
}): Promise<bigint> {
  const generation = await applyReleaseGlobalExposure({
    tx: input.tx,
    enabled: false,
    actor: input.actor,
    current: input.global,
  });
  await applyReleasePracticeExposureBatch({
    tx: input.tx,
    practices: input.manifest.filter(
      ({ templateTwinEnabled }) => templateTwinEnabled,
    ),
    enabled: false,
    actor: input.actor,
  });
  return generation;
}

async function applyReleaseGlobalExposure(input: {
  readonly tx: ControlTransaction;
  readonly enabled: boolean;
  readonly actor: VerifiedControlPrincipal;
  readonly current: GlobalControlRow;
}): Promise<bigint> {
  const currentGeneration = exactGeneration(input.current.generation);
  const rows = await input.tx.$queryRaw<
    Array<{ generation: bigint | number | string }>
  >(Prisma.sql`
    UPDATE "template_twin_rollout_controls"
    SET "enabled" = ${input.enabled}, "generation" = "generation" + 1,
        "updatedAt" = CURRENT_TIMESTAMP
    WHERE "id" = ${TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID}
      AND "generation" = ${currentGeneration}
    RETURNING "generation"
  `);
  const updated = rows[0];
  if (!updated) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_STALE_GENERATION",
      "The global rollout generation changed before the release mutation.",
    );
  }
  const nextGeneration = exactGeneration(updated.generation);
  await enqueueReleaseAudit(input.tx, {
    eventKey: `template-twin:global-rollout:${nextGeneration.toString()}`,
    practiceId: input.actor.practiceId,
    actorId: input.actor.userId,
    actorEmailSnapshot: input.actor.email,
    action: input.enabled
      ? "TEMPLATE_TWIN_ACTIVATED"
      : "TEMPLATE_TWIN_DEACTIVATED",
    targetType: "TemplateTwinRolloutControl",
    targetId: TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID,
    metadata: {
      scope: "global",
      enabled: input.enabled,
      previousGeneration: currentGeneration.toString(),
      generation: nextGeneration.toString(),
    },
  });
  return nextGeneration;
}

async function applyReleasePracticeExposureBatch(input: {
  readonly tx: ControlTransaction;
  readonly practices: readonly ManifestRow[];
  readonly enabled: boolean;
  readonly actor: VerifiedControlPrincipal;
}): Promise<void> {
  if (input.practices.length === 0) return;
  const practiceIds = input.practices.map(({ practiceId }) => practiceId);
  const updated = await input.tx.$queryRaw<
    Array<{
      practiceId: string;
      generation: bigint | number | string;
    }>
  >(Prisma.sql`
    UPDATE "practices"
    SET "templateTwinEnabled" = ${input.enabled},
        "templateTwinRolloutGeneration" =
          "templateTwinRolloutGeneration" + 1,
        "updatedAt" = CURRENT_TIMESTAMP
    WHERE "id" IN (${Prisma.join(practiceIds)})
      AND "templateTwinEnabled" = ${!input.enabled}
    RETURNING "id" AS "practiceId",
      "templateTwinRolloutGeneration" AS "generation"
  `);
  if (updated.length !== practiceIds.length) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
      "A practice exposure changed outside the locked release cohort.",
    );
  }
  const auditRows = updated.map((practice) => {
    const nextGeneration = exactGeneration(practice.generation);
    const metadata = {
      scope: "practice",
      enabled: input.enabled,
      previousGeneration: (nextGeneration - BigInt(1)).toString(),
      generation: nextGeneration.toString(),
    };
    assertTemplateTwinAuditMetadata(metadata);
    return {
      eventKey:
        `template-twin:practice-rollout:${practice.practiceId}:` +
        nextGeneration.toString(),
      practiceId: practice.practiceId,
      actorId: input.actor.userId,
      actorEmailSnapshot: input.actor.email,
      action: input.enabled
        ? ("TEMPLATE_TWIN_ACTIVATED" as const)
        : ("TEMPLATE_TWIN_DEACTIVATED" as const),
      targetType: "Practice",
      targetId: practice.practiceId,
      metadata,
      status: "PENDING" as const,
      attemptCount: 0,
    };
  });
  for (let offset = 0; offset < auditRows.length; offset += 500) {
    await enqueueReleaseAuditBatch(
      input.tx,
      auditRows.slice(offset, offset + 500),
    );
  }
}

function releaseIdentityInput(release: ReleaseRow) {
  return {
    sourceCommitSha: release.sourceCommitSha,
    baseCommitSha: release.baseCommitSha,
    appImageDigest: release.appImageDigest,
    workerImageDigest: release.workerImageDigest,
    migratorImageDigest: release.migratorImageDigest,
    testCensusEvidenceSha256: release.testCensusEvidenceSha256,
    independentReviewEvidenceSha256: release.independentReviewEvidenceSha256,
    securityEvidenceSha256: release.securityEvidenceSha256,
    migrationRestoreEvidenceSha256: release.migrationRestoreEvidenceSha256,
    officeWordEvidenceSha256: release.officeWordEvidenceSha256,
    guardrailPolicySha256: release.guardrailPolicySha256,
    authorizedPracticeManifestSha256: release.authorizedPracticeManifestSha256,
    runtimeManifestSha256: release.runtimeManifestSha256,
  };
}

export async function createTemplateTwinReleaseCandidate(input: {
  readonly actor: TemplateTwinReleaseActor;
  readonly confirmation: string;
  readonly evidence: TemplateTwinReleaseIdentityEvidence;
  readonly guardrailPolicy: unknown;
  readonly authorizedPracticeIds: readonly string[];
  readonly canaryPracticeIds: readonly string[];
  readonly runtimeInstances: readonly TemplateTwinRuntimeRequirementInput[];
}): Promise<{
  readonly releaseId: string;
  readonly releaseIdentitySha256: string;
  readonly authorizedPracticeManifestSha256: string;
  readonly guardrailPolicySha256: string;
  readonly generation: string;
}> {
  assertExactConfirmation(input.confirmation, "CREATE EXACT RELEASE");
  const policy = parseTemplateTwinGuardrailPolicy(input.guardrailPolicy);
  const policySha256 = templateTwinGuardrailPolicySha256(policy);
  const requestedPracticeIds = [...new Set(input.authorizedPracticeIds)];
  if (
    requestedPracticeIds.length !== input.authorizedPracticeIds.length ||
    requestedPracticeIds.length === 0 ||
    input.canaryPracticeIds.length === 0
  ) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_INVALID_REQUEST",
      "Authorized and canary practice identifiers must be non-empty and unique.",
    );
  }

  return database.$transaction(
    async (tx) => {
      await acquireControlPlaneLock(tx);
      const global = await lockGlobalControl(tx);
      const actor = await verifyReleaseActor(tx, input.actor);
      assertRollbackFenceOpen(global);
      if (global.enabled) {
        throw new TemplateTwinReleaseControlError(
          "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
          "A release candidate can be created only while Template Twin is globally disabled.",
        );
      }

      const practices = await tx.$queryRaw<
        Array<{
          id: string;
          slug: string;
          isActive: boolean;
          templateTwinEnabled: boolean;
        }>
      >(Prisma.sql`
        SELECT "id", "slug", "isActive", "templateTwinEnabled"
        FROM "practices"
        WHERE "id" IN (${Prisma.join(requestedPracticeIds)})
        ORDER BY "id" ASC
        FOR SHARE
      `);
      if (
        practices.length !== requestedPracticeIds.length ||
        practices.some(
          (practice) => !practice.isActive || practice.templateTwinEnabled,
        )
      ) {
        throw new TemplateTwinReleaseControlError(
          "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
          "Every authorized practice must exist, be active, and remain rollout-disabled while the release is drafted.",
        );
      }
      const counts = await tx.$queryRaw<
        Array<{ practiceId: string; count: bigint | number | string }>
      >(Prisma.sql`
        SELECT practice."id" AS "practiceId", COUNT(clinician."id")::BIGINT AS "count"
        FROM "practices" practice
        LEFT JOIN "users" clinician
          ON clinician."practiceId" = practice."id"
         AND clinician."role" = 'DOCTOR'::"UserRole"
         AND 'TRANSCRIBE_MD'::"Product" = ANY(clinician."products")
         AND clinician."isActive" = TRUE
         AND clinician."deactivatedAt" IS NULL
         AND clinician."suspendedAt" IS NULL
         AND clinician."softDeletedAt" IS NULL
        WHERE practice."id" IN (${Prisma.join(requestedPracticeIds)})
        GROUP BY practice."id"
        ORDER BY practice."id" ASC
      `);
      const countByPractice = new Map(
        counts.map((row) => [row.practiceId, Number(row.count)]),
      );
      const plan = buildTemplateTwinCohortPlan({
        sourceCommitSha: input.evidence.sourceCommitSha,
        practices: practices.map((practice) => ({
          practiceId: practice.id,
          practiceSlug: practice.slug,
          physicianCount: countByPractice.get(practice.id) ?? 0,
        })),
        canaryPracticeIds: input.canaryPracticeIds,
      });
      const runtimeManifest = buildTemplateTwinRuntimeManifest({
        sourceCommitSha: input.evidence.sourceCommitSha,
        appImageDigest: input.evidence.appImageDigest,
        workerImageDigest: input.evidence.workerImageDigest,
        instances: input.runtimeInstances,
      });
      const identityInput = {
        ...input.evidence,
        guardrailPolicySha256: policySha256,
        authorizedPracticeManifestSha256: plan.authorizedPracticeManifestSha256,
        runtimeManifestSha256: runtimeManifest.runtimeManifestSha256,
      };
      const releaseIdentitySha256 =
        templateTwinReleaseIdentitySha256(identityInput);
      const releaseId = randomUUID();
      const eventKey = `template-twin:release:${releaseId}:created`;

      await tx.$executeRaw(Prisma.sql`
        INSERT INTO "template_twin_release_candidates" (
          "id", "identityVersion", "releaseIdentitySha256",
          "sourceCommitSha", "baseCommitSha", "appImageDigest",
          "workerImageDigest", "migratorImageDigest",
          "testCensusEvidenceSha256", "independentReviewEvidenceSha256",
          "securityEvidenceSha256", "migrationRestoreEvidenceSha256",
          "officeWordEvidenceSha256", "guardrailPolicySha256",
          "authorizedPracticeManifestSha256", "guardrailPolicy",
          "runtimeManifestSha256",
          "status", "generation", "createdById"
        ) VALUES (
          ${releaseId}::UUID, ${TEMPLATE_TWIN_RELEASE_IDENTITY_VERSION},
          ${releaseIdentitySha256}, ${input.evidence.sourceCommitSha},
          ${input.evidence.baseCommitSha}, ${input.evidence.appImageDigest},
          ${input.evidence.workerImageDigest}, ${input.evidence.migratorImageDigest},
          ${input.evidence.testCensusEvidenceSha256},
          ${input.evidence.independentReviewEvidenceSha256},
          ${input.evidence.securityEvidenceSha256},
          ${input.evidence.migrationRestoreEvidenceSha256},
          ${input.evidence.officeWordEvidenceSha256}, ${policySha256},
          ${plan.authorizedPracticeManifestSha256},
          ${JSON.stringify(policy)}::JSONB,
          ${runtimeManifest.runtimeManifestSha256}, 'DRAFT', 1, ${actor.userId}
        )
      `);

      const runtimeRows = runtimeManifest.instances.map(
        (instance) => Prisma.sql`(
          ${randomUUID()}::UUID, ${releaseId}::UUID, ${releaseIdentitySha256},
          ${instance.instanceId}, ${instance.component},
          ${input.evidence.sourceCommitSha}, ${instance.imageDigest}
        )`,
      );
      await tx.$executeRaw(Prisma.sql`
        INSERT INTO "template_twin_release_runtime_requirements" (
          "id", "releaseId", "releaseIdentitySha256", "instanceId",
          "component", "sourceCommitSha", "imageDigest"
        ) VALUES ${Prisma.join(runtimeRows)}
      `);

      const manifestRows = plan.practices.map(
        (practice) =>
          Prisma.sql`(
          ${randomUUID()}::UUID, ${releaseId}::UUID, ${releaseIdentitySha256},
          ${practice.practiceId}, ${practice.practiceSlug},
          ${practice.physicianCount}, ${practice.cohortRank},
          ${practice.cohortHashSha256}, ${practice.isCanary},
          ${practice.activationStage}, ${practice.activationStageOrdinal}
        )`,
      );
      // A production manifest may contain thousands of practices. Keep the
      // transaction bounded to a few bulk statements rather than one network
      // round trip per practice while preserving deterministic row identity.
      for (let offset = 0; offset < manifestRows.length; offset += 500) {
        await tx.$executeRaw(Prisma.sql`
          INSERT INTO "template_twin_release_practices" (
            "id", "releaseId", "releaseIdentitySha256", "practiceId",
            "practiceSlugSnapshot", "physicianCountSnapshot", "cohortRank",
            "cohortHashSha256", "isCanary", "activationStage",
            "activationStageOrdinal"
          ) VALUES ${Prisma.join(manifestRows.slice(offset, offset + 500))}
        `);
      }
      for (const checkpoint of plan.checkpoints) {
        await tx.$executeRaw(Prisma.sql`
          INSERT INTO "template_twin_release_checkpoints" (
            "id", "releaseId", "releaseIdentitySha256", "stage", "ordinal",
            "targetPercent", "targetPhysicianCount", "assignedPhysicianCount",
            "status", "minimumBakeSeconds"
          ) VALUES (
            ${randomUUID()}::UUID, ${releaseId}::UUID, ${releaseIdentitySha256},
            ${checkpoint.stage}, ${checkpoint.ordinal},
            ${checkpoint.targetPercent}, ${checkpoint.targetPhysicianCount},
            ${checkpoint.assignedPhysicianCount}, 'PENDING',
            ${policy.minimumBakeSecondsByStage[checkpoint.stage]}
          )
        `);
      }
      await enqueueReleaseAudit(tx, {
        eventKey,
        practiceId: actor.practiceId,
        actorId: actor.userId,
        actorEmailSnapshot: actor.email,
        action: "TEMPLATE_TWIN_RELEASE_CREATED",
        targetType: "TemplateTwinReleaseCandidate",
        targetId: releaseId,
        metadata: {
          releaseIdentitySha256,
          sourceCommitSha: input.evidence.sourceCommitSha,
          authorizedPracticeCount: plan.practices.length,
          authorizedPhysicianCount:
            plan.checkpoints.at(-1)!.assignedPhysicianCount,
          guardrailPolicySha256: policySha256,
          manifestSha256: plan.authorizedPracticeManifestSha256,
          runtimeManifestSha256: runtimeManifest.runtimeManifestSha256,
          runtimeInstanceCount: runtimeManifest.instances.length,
        },
      });
      return {
        releaseId,
        releaseIdentitySha256,
        authorizedPracticeManifestSha256: plan.authorizedPracticeManifestSha256,
        guardrailPolicySha256: policySha256,
        runtimeManifestSha256: runtimeManifest.runtimeManifestSha256,
        generation: "1",
      };
    },
    { isolationLevel: "Serializable", maxWait: 5_000, timeout: 30_000 },
  );
}

export async function freezeTemplateTwinReleaseCandidate(input: {
  readonly actor: TemplateTwinReleaseActor;
  readonly releaseId: string;
  readonly expectedReleaseGeneration: string;
  readonly confirmation: string;
}): Promise<{ readonly generation: string; readonly status: "FROZEN" }> {
  const releaseId = uuid(input.releaseId);
  const expected = expectedGeneration(input.expectedReleaseGeneration);
  return database.$transaction(
    async (tx) => {
      await acquireControlPlaneLock(tx);
      const global = await lockGlobalControl(tx);
      const release = await lockRelease(tx, releaseId);
      const manifest = await lockManifest(tx, releaseId);
      const runtimeRequirements = await lockRuntimeRequirements(tx, releaseId);
      await lockCheckpoints(tx, releaseId);
      assertManifestPracticesActive(manifest);
      assertExpectedReleaseGeneration(release, expected);
      assertRollbackFenceOpen(global);
      if (release.status !== "DRAFT" || global.enabled) {
        throw new TemplateTwinReleaseControlError(
          "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
          "Only a globally disabled draft release can be frozen.",
        );
      }
      assertExactConfirmation(
        input.confirmation,
        `FREEZE ${release.releaseIdentitySha256.slice(0, 12)}`,
      );

      const policy = parseTemplateTwinGuardrailPolicy(release.guardrailPolicy);
      const plan = buildTemplateTwinCohortPlan({
        sourceCommitSha: release.sourceCommitSha,
        practices: manifest.map((practice) => ({
          practiceId: practice.practiceId,
          practiceSlug: practice.practiceSlugSnapshot,
          physicianCount: practice.physicianCountSnapshot,
        })),
        canaryPracticeIds: manifest
          .filter(({ isCanary }) => isCanary)
          .map(({ practiceId }) => practiceId),
      });
      const runtimeManifest = buildTemplateTwinRuntimeManifest({
        sourceCommitSha: release.sourceCommitSha,
        appImageDigest: release.appImageDigest,
        workerImageDigest: release.workerImageDigest,
        instances: runtimeRequirements,
      });
      if (
        templateTwinGuardrailPolicySha256(policy) !==
          release.guardrailPolicySha256 ||
        plan.authorizedPracticeManifestSha256 !==
          release.authorizedPracticeManifestSha256 ||
        runtimeManifest.runtimeManifestSha256 !==
          release.runtimeManifestSha256 ||
        templateTwinReleaseIdentitySha256(releaseIdentityInput(release)) !==
          release.releaseIdentitySha256 ||
        plan.practices.some((planned, index) => {
          const persisted = manifest[index];
          return (
            !persisted ||
            persisted.practiceId !== planned.practiceId ||
            persisted.cohortRank !== planned.cohortRank ||
            persisted.cohortHashSha256 !== planned.cohortHashSha256 ||
            persisted.activationStage !== planned.activationStage ||
            persisted.activationStageOrdinal !== planned.activationStageOrdinal
          );
        })
      ) {
        throw new TemplateTwinReleaseControlError(
          "TEMPLATE_TWIN_RELEASE_IDENTITY_MISMATCH",
          "Release identity, policy, or authorized-practice manifest no longer matches its canonical digest.",
        );
      }

      const actor = await issueReleaseActionReceipt({
        tx,
        actor: input.actor,
        releaseId,
        action: "FREEZE",
        confirmation: input.confirmation,
      });

      const eventKey = `template-twin:release:${releaseId}:frozen`;
      await enqueueReleaseAudit(tx, {
        eventKey,
        practiceId: actor.practiceId,
        actorId: actor.userId,
        actorEmailSnapshot: actor.email,
        action: "TEMPLATE_TWIN_RELEASE_FROZEN",
        targetType: "TemplateTwinReleaseCandidate",
        targetId: releaseId,
        metadata: {
          releaseIdentitySha256: release.releaseIdentitySha256,
          previousGeneration: expected.toString(),
          generation: (expected + BigInt(1)).toString(),
          actionReceiptNonce: actor.nonce,
        },
      });
      await tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_release_candidates"
        SET "status" = 'FROZEN', "generation" = "generation" + 1,
            "frozenById" = ${actor.userId},
            "frozenAt" = CURRENT_TIMESTAMP,
            "freezeActionReceiptNonce" = ${actor.nonce}::UUID,
            "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" = ${releaseId}::UUID
      `);
      return {
        generation: (expected + BigInt(1)).toString(),
        status: "FROZEN",
      };
    },
    { isolationLevel: "Serializable", maxWait: 5_000, timeout: 30_000 },
  );
}

export async function recordTemplateTwinReleaseApproval(input: {
  readonly actor: TemplateTwinReleaseActor;
  readonly releaseId: string;
  readonly expectedReleaseGeneration: string;
  readonly discipline: TemplateTwinReleaseDiscipline;
  readonly decision: TemplateTwinApprovalDecision;
  readonly evidenceSha256: string;
  readonly confirmation: string;
}): Promise<{
  readonly generation: string;
  readonly status: TemplateTwinReleaseStatus;
  readonly decisionId: string;
}> {
  const releaseId = uuid(input.releaseId);
  const expected = expectedGeneration(input.expectedReleaseGeneration);
  if (
    !TEMPLATE_TWIN_RELEASE_DISCIPLINES.includes(input.discipline) ||
    !["APPROVE", "REJECT", "REVOKE"].includes(input.decision) ||
    !/^[0-9a-f]{64}$/u.test(input.evidenceSha256)
  ) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_INVALID_REQUEST",
      "Human decision discipline, value, or evidence digest is invalid.",
    );
  }
  const transaction = async (tx: ControlTransaction) => {
    await acquireControlPlaneLock(tx);
    const global = await lockGlobalControl(tx);
    const release = await lockRelease(tx, releaseId);
    const checkpoints = await lockCheckpoints(tx, releaseId);
    const manifest = await lockManifest(tx, releaseId);
    const actor = await issueReleaseActionReceipt({
      tx,
      actor: input.actor,
      releaseId,
      action: "APPROVAL",
      discipline: input.discipline,
      decision: input.decision,
      confirmation: input.confirmation,
    });
    const observedGeneration =
      input.decision === "APPROVE"
        ? (assertExpectedReleaseGeneration(release, expected), expected)
        : assertSafetyGenerationNotFuture(release.generation, expected);
    if (
      !["FROZEN", "APPROVED", "ROLLING_OUT", "STABLE_100"].includes(
        release.status,
      )
    ) {
      throw new TemplateTwinReleaseControlError(
        "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
        "This release is not open for a human decision.",
      );
    }
    if (
      ["ROLLING_OUT", "STABLE_100"].includes(release.status) &&
      input.decision === "APPROVE"
    ) {
      throw new TemplateTwinReleaseControlError(
        "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
        "A rolling release accepts only a rejecting or revoking human decision; approvals cannot be refreshed mid-rollout.",
      );
    }
    if (
      actor.userId === release.createdById ||
      actor.userId === release.frozenById
    ) {
      throw new TemplateTwinReleaseControlError(
        "TEMPLATE_TWIN_RELEASE_UNAUTHORIZED",
        "The release creator/finalizer cannot approve or reject the same release.",
      );
    }
    assertExactConfirmation(
      input.confirmation,
      templateTwinApprovalConfirmation({
        decision: input.decision,
        discipline: input.discipline,
        releaseIdentitySha256: release.releaseIdentitySha256,
      }),
    );

    const authorities = await tx.$queryRaw<AuthorityRow[]>(Prisma.sql`
        SELECT "id", "discipline"
        FROM "template_twin_release_authorities"
        WHERE "userId" = ${actor.userId}
          AND "discipline" = ${input.discipline}
          AND "effectiveAt" <= CURRENT_TIMESTAMP
          AND "revokedAt" IS NULL
        ORDER BY "effectiveAt" DESC, "id" DESC
        LIMIT 1
      `);
    const authority = authorities[0];
    if (!authority) {
      throw new TemplateTwinReleaseControlError(
        "TEMPLATE_TWIN_RELEASE_AUTHORITY_MISSING",
        "The current human operator has no active out-of-band authority for this discipline.",
      );
    }
    const decisionId = randomUUID();
    const eventKey = `template-twin:release:${releaseId}:approval:${decisionId}`;
    await enqueueReleaseAudit(tx, {
      eventKey,
      practiceId: actor.practiceId,
      actorId: actor.userId,
      actorEmailSnapshot: actor.email,
      action: "TEMPLATE_TWIN_RELEASE_APPROVAL_RECORDED",
      targetType: "TemplateTwinReleaseApprovalDecision",
      targetId: decisionId,
      metadata: {
        releaseId,
        releaseIdentitySha256: release.releaseIdentitySha256,
        discipline: input.discipline,
        decision: input.decision,
        evidenceSha256: input.evidenceSha256,
        authorityAssignmentId: authority.id,
        actionReceiptNonce: actor.nonce,
        requestedReleaseGeneration: expected.toString(),
        previousReleaseGeneration: observedGeneration.toString(),
      },
    });
    await tx.$executeRaw(Prisma.sql`
        INSERT INTO "template_twin_release_approval_decisions" (
          "id", "releaseId", "releaseIdentitySha256", "discipline",
          "decision", "evidenceSha256", "confirmation", "actorId",
          "actorEmailSnapshot", "actorSessionSha256",
          "authorityAssignmentId", "auditOutboxEventKey",
          "actionReceiptNonce", "decidedAt"
        ) VALUES (
          ${decisionId}::UUID, ${releaseId}::UUID,
          ${release.releaseIdentitySha256}, ${input.discipline},
          ${input.decision}, ${input.evidenceSha256}, ${input.confirmation},
          ${actor.userId}, ${actor.email}, ${actor.sessionSha256},
          ${authority.id}::UUID, ${eventKey}, ${actor.nonce}::UUID,
          CURRENT_TIMESTAMP
        )
      `);

    const approved = await approvalsAreCurrent(tx, release);
    const nextStatus: TemplateTwinReleaseStatus =
      input.decision === "APPROVE"
        ? approved
          ? "APPROVED"
          : (release.status as TemplateTwinReleaseStatus)
        : "REJECTED";
    if (input.decision !== "APPROVE") {
      await disableReleaseExposure({ tx, actor, global, manifest });
      const active = checkpoints.find(({ status }) => status === "ACTIVE");
      if (active) {
        await tx.$executeRaw(Prisma.sql`
            UPDATE "template_twin_release_checkpoints"
            SET "status" = 'REVOKED', "revokedAt" = CURRENT_TIMESTAMP,
                "updatedAt" = CURRENT_TIMESTAMP
            WHERE "id" = ${active.id}::UUID
          `);
      }
    }
    await tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_release_candidates"
        SET "status" = ${nextStatus}, "generation" = "generation" + 1,
            "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" = ${releaseId}::UUID
      `);
    return {
      generation: (observedGeneration + BigInt(1)).toString(),
      status: nextStatus,
      decisionId,
    };
  };
  if (input.decision === "APPROVE") {
    return database.$transaction(transaction, {
      isolationLevel: "Serializable",
      maxWait: 5_000,
      timeout: 30_000,
    });
  }
  return runSerializableTransactionWithRetry({
    prisma: database,
    operation: "template_twin_release_human_revoke",
    maxWait: 10_000,
    timeout: 60_000,
    transaction,
  });
}

export async function activateTemplateTwinReleaseCheckpoint(input: {
  readonly actor: TemplateTwinReleaseActor;
  readonly releaseId: string;
  readonly stage: TemplateTwinReleaseStage;
  readonly expectedReleaseGeneration: string;
  readonly expectedGlobalGeneration: string;
  readonly confirmation: string;
  readonly env?: Readonly<Record<string, string | undefined>>;
}): Promise<{
  readonly releaseGeneration: string;
  readonly globalGeneration: string;
  readonly stage: TemplateTwinReleaseStage;
  readonly targetPhysicianCount: number;
  readonly assignedPhysicianCount: number;
  readonly activatedPhysicianCount: number;
}> {
  const releaseId = uuid(input.releaseId);
  const expectedRelease = expectedGeneration(input.expectedReleaseGeneration);
  const expectedGlobal = expectedGeneration(input.expectedGlobalGeneration);
  const stageDefinition = TEMPLATE_TWIN_RELEASE_STAGES.find(
    ({ stage }) => stage === input.stage,
  );
  if (!stageDefinition) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_INVALID_REQUEST",
      "The rollout checkpoint is not in the fixed stage rail.",
    );
  }
  return database.$transaction(
    async (tx) => {
      await acquireControlPlaneLock(tx);
      const global = await lockGlobalControl(tx);
      const release = await lockRelease(tx, releaseId);
      const checkpoints = await lockCheckpoints(tx, releaseId);
      const manifest = await lockManifest(tx, releaseId);
      assertExpectedReleaseGeneration(release, expectedRelease);
      assertExpectedGlobalGeneration(global, expectedGlobal);
      assertRollbackFenceOpen(global);
      assertRuntimeIdentity(release, input.env);
      assertManifestPracticesActive(manifest);
      await assertRuntimeReplicaReadiness({
        tx,
        release,
      });
      await assertLineageContracted(tx);
      if (!(await approvalsAreCurrent(tx, release))) {
        throw new TemplateTwinReleaseControlError(
          "TEMPLATE_TWIN_RELEASE_APPROVAL_INCOMPLETE",
          "Every required human discipline must currently approve this exact release.",
        );
      }
      const checkpoint = checkpoints.find(({ stage }) => stage === input.stage);
      if (!checkpoint || checkpoint.status !== "PENDING") {
        throw new TemplateTwinReleaseControlError(
          "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
          "The requested checkpoint is not pending.",
        );
      }
      const prior = checkpoints.filter(
        ({ ordinal }) => ordinal < checkpoint.ordinal,
      );
      const futureOrCurrentActive = checkpoints.some(
        (row) => row.status === "ACTIVE",
      );
      if (
        futureOrCurrentActive ||
        prior.some(({ status }) => status !== "PASSED") ||
        (checkpoint.ordinal === 1 && release.status !== "APPROVED") ||
        (checkpoint.ordinal > 1 && release.status !== "ROLLING_OUT")
      ) {
        throw new TemplateTwinReleaseControlError(
          "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
          "Checkpoints cannot be skipped, replayed, or activated while another checkpoint is active.",
        );
      }
      assertExactConfirmation(
        input.confirmation,
        templateTwinCheckpointConfirmation({
          verb: "ACTIVATE",
          stage: input.stage,
          releaseIdentitySha256: release.releaseIdentitySha256,
        }),
      );
      const actor = await issueReleaseActionReceipt({
        tx,
        actor: input.actor,
        releaseId,
        checkpointId: checkpoint.id,
        action: "ACTIVATE",
        confirmation: input.confirmation,
      });

      const inScope = manifest.filter(
        ({ activationStageOrdinal }) =>
          activationStageOrdinal <= checkpoint.ordinal,
      );
      const newlyInScope = manifest.filter(
        ({ activationStageOrdinal }) =>
          activationStageOrdinal === checkpoint.ordinal,
      );
      if (newlyInScope.some(({ templateTwinEnabled }) => templateTwinEnabled)) {
        throw new TemplateTwinReleaseControlError(
          "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
          "A future cohort practice is already enabled outside this checkpoint.",
        );
      }
      const activatedPhysicianCount = await censusAuthorizedPhysicians(
        tx,
        inScope.map(({ practiceId }) => practiceId),
      );
      const eventKey =
        `template-twin:release:${releaseId}:checkpoint:` +
        `${input.stage}:activated`;
      await enqueueReleaseAudit(tx, {
        eventKey,
        practiceId: actor.practiceId,
        actorId: actor.userId,
        actorEmailSnapshot: actor.email,
        action: "TEMPLATE_TWIN_ROLLOUT_CHECKPOINT_ACTIVATED",
        targetType: "TemplateTwinReleaseCheckpoint",
        targetId: checkpoint.id,
        metadata: {
          releaseId,
          releaseIdentitySha256: release.releaseIdentitySha256,
          stage: input.stage,
          targetPercent: checkpoint.targetPercent,
          targetPhysicianCount: checkpoint.targetPhysicianCount,
          assignedPhysicianCount: checkpoint.assignedPhysicianCount,
          activatedPhysicianCount,
          previousReleaseGeneration: expectedRelease.toString(),
          previousGlobalGeneration: expectedGlobal.toString(),
          actionReceiptNonce: actor.nonce,
        },
      });
      await tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_release_checkpoints"
        SET "status" = 'ACTIVE', "activatedPhysicianCount" = ${activatedPhysicianCount},
            "activatedAt" = CURRENT_TIMESTAMP,
            "earliestPassAt" = CURRENT_TIMESTAMP +
              ${checkpoint.minimumBakeSeconds} * INTERVAL '1 second',
            "activatedById" = ${actor.userId},
            "activationOutboxEventKey" = ${eventKey},
            "activationActionReceiptNonce" = ${actor.nonce}::UUID,
            "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" = ${checkpoint.id}::UUID
      `);
      const nextReleaseGeneration = expectedRelease + BigInt(1);
      await tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_release_candidates"
        SET "status" = 'ROLLING_OUT', "generation" = "generation" + 1,
            "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" = ${releaseId}::UUID
      `);
      await tx.$queryRaw(Prisma.sql`
        SELECT template_twin_issue_release_capability(
          ${releaseId}::UUID, ${release.releaseIdentitySha256}::CHAR(64),
          ${checkpoint.id}::UUID, ${nextReleaseGeneration}, ${expectedGlobal}
        )
      `);

      const nextGlobalGeneration = await applyReleaseGlobalExposure({
        tx,
        enabled: true,
        actor,
        current: global,
      });
      await applyReleasePracticeExposureBatch({
        tx,
        practices: newlyInScope,
        enabled: true,
        actor,
      });
      return {
        releaseGeneration: nextReleaseGeneration.toString(),
        globalGeneration: nextGlobalGeneration.toString(),
        stage: input.stage,
        targetPhysicianCount: checkpoint.targetPhysicianCount,
        assignedPhysicianCount: checkpoint.assignedPhysicianCount,
        activatedPhysicianCount,
      };
    },
    { isolationLevel: "Serializable", maxWait: 10_000, timeout: 60_000 },
  );
}

export async function recordTemplateTwinReleaseMetricSnapshot(input: {
  readonly releaseId: string;
  readonly stage: TemplateTwinReleaseStage;
  readonly expectedReleaseGeneration: string;
  readonly expectedGlobalGeneration: string;
  readonly sampleCount: number;
  readonly observationStartedAt: Date;
  readonly observationEndedAt: Date;
  readonly metrics: Readonly<Record<string, string>>;
  readonly attestation: {
    readonly version: "template-twin-metric-attestation-v1";
    readonly keyId: string;
    readonly nonce: string;
    readonly issuedAtEpochSeconds: number;
    readonly signature: string;
  };
}): Promise<{
  readonly snapshotId: string;
  readonly canonicalSha256: string;
  readonly evaluation: "PASS" | "BLOCK" | "CRITICAL_REVOKE";
  readonly releaseStatus: TemplateTwinReleaseStatus;
  readonly releaseGeneration: string;
  readonly globalGeneration: string;
  readonly missingMetrics: readonly string[];
  readonly breachedMetrics: readonly string[];
  readonly blockingReasons: readonly string[];
}> {
  const releaseId = uuid(input.releaseId);
  const expectedRelease = expectedGeneration(input.expectedReleaseGeneration);
  const expectedGlobal = expectedGeneration(input.expectedGlobalGeneration);
  if (
    input.attestation.version !== "template-twin-metric-attestation-v1" ||
    !/^[A-Za-z0-9][A-Za-z0-9._:-]{2,79}$/u.test(input.attestation.keyId) ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u.test(
      input.attestation.nonce,
    ) ||
    !Number.isSafeInteger(input.attestation.issuedAtEpochSeconds) ||
    !/^[0-9a-f]{64}$/u.test(input.attestation.signature)
  ) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_INVALID_REQUEST",
      "The monitoring attestation shape is invalid.",
    );
  }
  return runSerializableTransactionWithRetry({
    prisma: database,
    operation: "template_twin_release_metric_snapshot",
    maxWait: 10_000,
    timeout: 60_000,
    transaction: async (tx) => {
      await acquireControlPlaneLock(tx);
      const global = await lockGlobalControl(tx);
      const release = await lockRelease(tx, releaseId);
      const checkpoints = await lockCheckpoints(tx, releaseId);
      const manifest = await lockManifest(tx, releaseId);
      const checkpoint = checkpoints.find(({ stage }) => stage === input.stage);
      if (!checkpoint?.activatedAt) {
        throw new TemplateTwinReleaseControlError(
          "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
          "Metrics can be attached only to an activated checkpoint.",
        );
      }
      const receiptRows = await tx.$queryRaw<
        Array<{
          receiptNonce: string;
          principalUserId: string;
          schemaVersion: string;
          canonicalSha256: string;
          evaluation: "PASS" | "BLOCK" | "CRITICAL_REVOKE";
          metrics: unknown;
          missingMetrics: string[];
          breachedMetrics: string[];
          blockingReasons: string[];
          attestationNonceSha256: string;
          attestationSignatureSha256: string;
        }>
      >(Prisma.sql`
        SELECT * FROM template_twin_issue_metric_receipt(
          ${input.attestation.version}, ${input.attestation.keyId},
          ${input.attestation.nonce}::UUID, ${releaseId}::UUID,
          ${input.stage}, ${expectedRelease}, ${expectedGlobal},
          ${input.sampleCount}, ${input.observationStartedAt.getTime()}::BIGINT,
          ${input.observationEndedAt.getTime()}::BIGINT,
          ${JSON.stringify(input.metrics)}::JSONB,
          ${input.attestation.issuedAtEpochSeconds}::BIGINT,
          ${input.attestation.signature}::CHAR(64)
        )
      `);
      const evaluation = receiptRows[0];
      if (!evaluation) {
        throw new TemplateTwinReleaseControlError(
          "TEMPLATE_TWIN_RELEASE_CONTROL_UNAVAILABLE",
          "The database did not issue a signed monitoring receipt.",
        );
      }
      const actor = await loadMonitoringPrincipal(
        tx,
        evaluation.principalUserId,
      );
      const isCritical = evaluation.evaluation === "CRITICAL_REVOKE";
      let releaseGeneration: bigint;
      let globalGeneration: bigint;
      if (isCritical) {
        releaseGeneration = assertSafetyGenerationNotFuture(
          release.generation,
          expectedRelease,
        );
        globalGeneration = assertSafetyGenerationNotFuture(
          global.generation,
          expectedGlobal,
        );
        if (
          !["ROLLING_OUT", "STABLE_100"].includes(release.status) ||
          !["ACTIVE", "PASSED"].includes(checkpoint.status)
        ) {
          throw new TemplateTwinReleaseControlError(
            "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
            "A critical snapshot can revoke only a live release and an activated checkpoint.",
          );
        }
      } else {
        assertExpectedReleaseGeneration(release, expectedRelease);
        assertExpectedGlobalGeneration(global, expectedGlobal);
        if (
          release.status !== "ROLLING_OUT" ||
          checkpoint.status !== "ACTIVE"
        ) {
          throw new TemplateTwinReleaseControlError(
            "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
            "Noncritical metrics can be attached only to the active checkpoint.",
          );
        }
        releaseGeneration = expectedRelease;
        globalGeneration = expectedGlobal;
      }
      const snapshotId = randomUUID();
      const criticalEventKey = isCritical
        ? `template-twin:release:${releaseId}:metric:${snapshotId}:critical-revoke`
        : null;
      if (criticalEventKey) {
        await enqueueReleaseAudit(tx, {
          eventKey: criticalEventKey,
          practiceId: actor.practiceId,
          actorId: actor.userId,
          actorEmailSnapshot: actor.email,
          action: "TEMPLATE_TWIN_ROLLOUT_GUARDRAIL_REVOKED",
          targetType: "TemplateTwinReleaseMetricSnapshot",
          targetId: snapshotId,
          metadata: {
            releaseId,
            releaseIdentitySha256: release.releaseIdentitySha256,
            stage: input.stage,
            snapshotSha256: evaluation.canonicalSha256,
            breachedMetrics: [...evaluation.breachedMetrics],
            requestedReleaseGeneration: expectedRelease.toString(),
            requestedGlobalGeneration: expectedGlobal.toString(),
            previousReleaseGeneration: releaseGeneration.toString(),
            previousGlobalGeneration: globalGeneration.toString(),
          },
        });
      }
      await tx.$executeRaw(Prisma.sql`
        INSERT INTO "template_twin_release_metric_snapshots" (
          "id", "releaseId", "checkpointId", "releaseIdentitySha256",
          "releaseGeneration", "globalGeneration",
          "policySha256", "schemaVersion", "sampleCount",
          "observationStartedAt", "observationEndedAt", "metrics",
          "canonicalSha256", "evaluation", "missingMetrics",
          "breachedMetrics", "blockingReasons", "recordedById",
          "criticalOutboxEventKey", "attestationKeyId",
          "attestationNonceSha256", "attestationSignatureSha256"
        ) VALUES (
          ${snapshotId}::UUID, ${releaseId}::UUID, ${checkpoint.id}::UUID,
          ${release.releaseIdentitySha256}, ${expectedRelease}, ${expectedGlobal},
          ${release.guardrailPolicySha256},
          ${evaluation.schemaVersion}, ${input.sampleCount},
          ${input.observationStartedAt}, ${input.observationEndedAt},
          ${JSON.stringify(evaluation.metrics)}::JSONB,
          ${evaluation.canonicalSha256}, ${evaluation.evaluation},
          ${evaluation.missingMetrics}::TEXT[],
          ${evaluation.breachedMetrics}::TEXT[],
          ${evaluation.blockingReasons}::TEXT[], ${actor.userId},
          ${criticalEventKey}, ${input.attestation.keyId},
          ${evaluation.attestationNonceSha256},
          ${evaluation.attestationSignatureSha256}
        )
      `);

      let releaseStatus = release.status as TemplateTwinReleaseStatus;
      if (isCritical) {
        globalGeneration = await disableReleaseExposure({
          tx,
          actor,
          global,
          manifest,
        });
        const activeCheckpoint = checkpoints.find(
          ({ status }) => status === "ACTIVE",
        );
        if (activeCheckpoint) {
          await tx.$executeRaw(Prisma.sql`
            UPDATE "template_twin_release_checkpoints"
            SET "status" = 'REVOKED', "revokedAt" = CURRENT_TIMESTAMP,
                "updatedAt" = CURRENT_TIMESTAMP
            WHERE "id" = ${activeCheckpoint.id}::UUID
          `);
        }
        await tx.$executeRaw(Prisma.sql`
          UPDATE "template_twin_release_candidates"
          SET "status" = 'REVOKED', "generation" = "generation" + 1,
              "updatedAt" = CURRENT_TIMESTAMP
          WHERE "id" = ${releaseId}::UUID
        `);
        releaseStatus = "REVOKED";
        releaseGeneration += BigInt(1);
      }
      return {
        snapshotId,
        canonicalSha256: evaluation.canonicalSha256,
        evaluation: evaluation.evaluation,
        releaseStatus,
        releaseGeneration: releaseGeneration.toString(),
        globalGeneration: globalGeneration.toString(),
        missingMetrics: evaluation.missingMetrics,
        breachedMetrics: evaluation.breachedMetrics,
        blockingReasons: evaluation.blockingReasons,
      };
    },
  });
}

export async function passTemplateTwinReleaseCheckpoint(input: {
  readonly actor: TemplateTwinReleaseActor;
  readonly releaseId: string;
  readonly stage: TemplateTwinReleaseStage;
  readonly expectedReleaseGeneration: string;
  readonly expectedGlobalGeneration: string;
  readonly confirmation: string;
  readonly env?: Readonly<Record<string, string | undefined>>;
  readonly now?: Date;
}): Promise<{
  readonly releaseGeneration: string;
  readonly globalGeneration: string;
  readonly releaseStatus: TemplateTwinReleaseStatus;
  readonly stage: TemplateTwinReleaseStage;
  readonly passedPhysicianCount: number;
}> {
  const releaseId = uuid(input.releaseId);
  const expectedRelease = expectedGeneration(input.expectedReleaseGeneration);
  const expectedGlobal = expectedGeneration(input.expectedGlobalGeneration);
  return database.$transaction(
    async (tx) => {
      await acquireControlPlaneLock(tx);
      const global = await lockGlobalControl(tx);
      const release = await lockRelease(tx, releaseId);
      const checkpoints = await lockCheckpoints(tx, releaseId);
      const manifest = await lockManifest(tx, releaseId);
      assertExpectedReleaseGeneration(release, expectedRelease);
      assertExpectedGlobalGeneration(global, expectedGlobal);
      assertRollbackFenceOpen(global);
      assertRuntimeIdentity(release, input.env);
      assertManifestPracticesActive(manifest);
      await assertRuntimeReplicaReadiness({
        tx,
        release,
      });
      if (!(await approvalsAreCurrent(tx, release))) {
        throw new TemplateTwinReleaseControlError(
          "TEMPLATE_TWIN_RELEASE_APPROVAL_INCOMPLETE",
          "Human approval authority changed; the checkpoint cannot pass.",
        );
      }
      const checkpoint = checkpoints.find(({ stage }) => stage === input.stage);
      const now = input.now ?? new Date();
      if (
        release.status !== "ROLLING_OUT" ||
        !checkpoint ||
        checkpoint.status !== "ACTIVE" ||
        !checkpoint.activatedAt ||
        !checkpoint.earliestPassAt ||
        checkpoint.earliestPassAt > now
      ) {
        throw new TemplateTwinReleaseControlError(
          "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
          "The checkpoint is not active or its minimum bake time has not elapsed.",
        );
      }
      assertExactConfirmation(
        input.confirmation,
        templateTwinCheckpointConfirmation({
          verb: "PASS",
          stage: input.stage,
          releaseIdentitySha256: release.releaseIdentitySha256,
        }),
      );
      // Metric snapshots and their signed receipts are append-only. The
      // advisory release lock serializes checkpoint transitions, so this read
      // must not request a row lock (which would require UPDATE privilege on
      // immutable evidence).
      const metricRows = await tx.$queryRaw<MetricRow[]>(Prisma.sql`
        SELECT metric.*, EXISTS (
          SELECT 1 FROM "template_twin_release_metric_receipts" receipt
          WHERE receipt."releaseId" = metric."releaseId"
            AND receipt."checkpointId" = metric."checkpointId"
            AND receipt."releaseGeneration" = metric."releaseGeneration"
            AND receipt."globalGeneration" = metric."globalGeneration"
            AND receipt."releaseIdentitySha256" = metric."releaseIdentitySha256"
            AND receipt."policySha256" = metric."policySha256"
            AND receipt."schemaVersion" = metric."schemaVersion"
            AND receipt."sampleCount" = metric."sampleCount"
            AND receipt."observationStartedAt" = metric."observationStartedAt"
            AND receipt."observationEndedAt" = metric."observationEndedAt"
            AND receipt."metrics" = metric."metrics"
            AND receipt."canonicalSha256" = metric."canonicalSha256"
            AND receipt."evaluation" = metric."evaluation"
            AND receipt."missingMetrics" = metric."missingMetrics"
            AND receipt."breachedMetrics" = metric."breachedMetrics"
            AND receipt."blockingReasons" = metric."blockingReasons"
            AND receipt."principalUserId" = metric."recordedById"
            AND receipt."attestationKeyId" = metric."attestationKeyId"
            AND receipt."attestationNonceSha256" = metric."attestationNonceSha256"
            AND receipt."attestationSignatureSha256" = metric."attestationSignatureSha256"
        ) AS "receiptVerified"
        FROM "template_twin_release_metric_snapshots" metric
        WHERE metric."checkpointId" = ${checkpoint.id}::UUID
        ORDER BY metric."createdAt" DESC, metric."id" DESC
        LIMIT 1
      `);
      const metric = metricRows[0];
      const policy = parseTemplateTwinGuardrailPolicy(release.guardrailPolicy);
      if (
        !metric ||
        metric.receiptVerified !== true ||
        metric.evaluation !== "PASS" ||
        metric.schemaVersion !== "template-twin-guardrails-v1" ||
        metric.missingMetrics.length !== 0 ||
        metric.breachedMetrics.length !== 0 ||
        metric.blockingReasons.length !== 0 ||
        metric.observationStartedAt < checkpoint.activatedAt ||
        now.getTime() - metric.observationEndedAt.getTime() >
          policy.maxObservationAgeSeconds * 1000
      ) {
        throw new TemplateTwinReleaseControlError(
          "TEMPLATE_TWIN_RELEASE_GUARDRAIL_BLOCKED",
          "A fresh, complete, passing metric snapshot is required for this checkpoint.",
        );
      }
      const inScope = manifest.filter(
        ({ activationStageOrdinal }) =>
          activationStageOrdinal <= checkpoint.ordinal,
      );
      if (inScope.some(({ templateTwinEnabled }) => !templateTwinEnabled)) {
        throw new TemplateTwinReleaseControlError(
          "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
          "The persisted practice exposure does not match this checkpoint.",
        );
      }
      if (
        checkpoint.stage === "PERCENT_100" &&
        inScope.length !== manifest.length
      ) {
        throw new TemplateTwinReleaseControlError(
          "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
          "The 100% checkpoint does not cover every authorized practice.",
        );
      }
      const passedPhysicianCount = await censusAuthorizedPhysicians(
        tx,
        inScope.map(({ practiceId }) => practiceId),
      );
      const actor = await issueReleaseActionReceipt({
        tx,
        actor: input.actor,
        releaseId,
        checkpointId: checkpoint.id,
        action: "PASS",
        confirmation: input.confirmation,
      });
      const eventKey =
        `template-twin:release:${releaseId}:checkpoint:` +
        `${input.stage}:passed`;
      await enqueueReleaseAudit(tx, {
        eventKey,
        practiceId: actor.practiceId,
        actorId: actor.userId,
        actorEmailSnapshot: actor.email,
        action: "TEMPLATE_TWIN_ROLLOUT_CHECKPOINT_PASSED",
        targetType: "TemplateTwinReleaseCheckpoint",
        targetId: checkpoint.id,
        metadata: {
          releaseId,
          releaseIdentitySha256: release.releaseIdentitySha256,
          stage: input.stage,
          metricSnapshotSha256: metric.canonicalSha256,
          targetPhysicianCount: checkpoint.targetPhysicianCount,
          assignedPhysicianCount: checkpoint.assignedPhysicianCount,
          passedPhysicianCount,
          actionReceiptNonce: actor.nonce,
        },
      });
      await tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_release_checkpoints"
        SET "status" = 'PASSED', "passedPhysicianCount" = ${passedPhysicianCount},
            "passedAt" = CURRENT_TIMESTAMP,
            "passedById" = ${actor.userId},
            "passOutboxEventKey" = ${eventKey},
            "passActionReceiptNonce" = ${actor.nonce}::UUID,
            "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" = ${checkpoint.id}::UUID
      `);
      const releaseStatus: TemplateTwinReleaseStatus =
        checkpoint.stage === "PERCENT_100" ? "STABLE_100" : "ROLLING_OUT";
      await tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_release_candidates"
        SET "status" = ${releaseStatus}, "generation" = "generation" + 1,
            "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" = ${releaseId}::UUID
      `);
      return {
        releaseGeneration: (expectedRelease + BigInt(1)).toString(),
        globalGeneration: expectedGlobal.toString(),
        releaseStatus,
        stage: input.stage,
        passedPhysicianCount,
      };
    },
    { isolationLevel: "Serializable", maxWait: 10_000, timeout: 60_000 },
  );
}

export async function revokeTemplateTwinRelease(input: {
  readonly actor: TemplateTwinReleaseActor;
  readonly releaseId: string;
  readonly expectedReleaseGeneration: string;
  readonly expectedGlobalGeneration: string;
  readonly reasonCode: string;
  readonly confirmation: string;
}): Promise<{
  readonly releaseGeneration: string;
  readonly globalGeneration: string;
  readonly status: "REVOKED";
}> {
  const releaseId = uuid(input.releaseId);
  const expectedRelease = expectedGeneration(input.expectedReleaseGeneration);
  const expectedGlobal = expectedGeneration(input.expectedGlobalGeneration);
  const validatedReason = reasonCode(input.reasonCode);
  return runSerializableTransactionWithRetry({
    prisma: database,
    operation: "template_twin_release_operational_revoke",
    maxWait: 10_000,
    timeout: 60_000,
    transaction: async (tx) => {
      await acquireControlPlaneLock(tx);
      const global = await lockGlobalControl(tx);
      const release = await lockRelease(tx, releaseId);
      const checkpoints = await lockCheckpoints(tx, releaseId);
      const manifest = await lockManifest(tx, releaseId);
      const actor = await verifyReleaseActor(tx, input.actor);
      const observedReleaseGeneration = assertSafetyGenerationNotFuture(
        release.generation,
        expectedRelease,
      );
      const observedGlobalGeneration = assertSafetyGenerationNotFuture(
        global.generation,
        expectedGlobal,
      );
      if (
        !["FROZEN", "APPROVED", "ROLLING_OUT", "STABLE_100"].includes(
          release.status,
        )
      ) {
        throw new TemplateTwinReleaseControlError(
          "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
          "This release is already terminal and cannot be revoked again.",
        );
      }
      assertExactConfirmation(
        input.confirmation,
        `REVOKE ${release.releaseIdentitySha256.slice(0, 12)}`,
      );
      const eventKey = `template-twin:release:${releaseId}:revoked:${expectedRelease.toString()}`;
      await enqueueReleaseAudit(tx, {
        eventKey,
        practiceId: actor.practiceId,
        actorId: actor.userId,
        actorEmailSnapshot: actor.email,
        action: "TEMPLATE_TWIN_RELEASE_REVOKED",
        targetType: "TemplateTwinReleaseCandidate",
        targetId: releaseId,
        metadata: {
          releaseIdentitySha256: release.releaseIdentitySha256,
          reasonCode: validatedReason,
          requestedReleaseGeneration: expectedRelease.toString(),
          requestedGlobalGeneration: expectedGlobal.toString(),
          previousReleaseGeneration: observedReleaseGeneration.toString(),
          previousGlobalGeneration: observedGlobalGeneration.toString(),
        },
      });
      const globalGeneration = await disableReleaseExposure({
        tx,
        actor,
        global,
        manifest,
      });
      const active = checkpoints.find(({ status }) => status === "ACTIVE");
      if (active) {
        await tx.$executeRaw(Prisma.sql`
          UPDATE "template_twin_release_checkpoints"
          SET "status" = 'REVOKED', "revokedAt" = CURRENT_TIMESTAMP,
              "updatedAt" = CURRENT_TIMESTAMP
          WHERE "id" = ${active.id}::UUID
        `);
      }
      await tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_release_candidates"
        SET "status" = 'REVOKED', "generation" = "generation" + 1,
            "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" = ${releaseId}::UUID
      `);
      return {
        releaseGeneration: (observedReleaseGeneration + BigInt(1)).toString(),
        globalGeneration: globalGeneration.toString(),
        status: "REVOKED",
      };
    },
  });
}

export interface TemplateTwinReleaseControlView {
  readonly global: {
    readonly enabled: boolean;
    readonly generation: string;
    readonly rollbackFenceState: string;
  };
  readonly release: null | {
    readonly id: string;
    readonly releaseIdentitySha256: string;
    readonly sourceCommitSha: string;
    readonly baseCommitSha: string;
    readonly appImageDigest: string;
    readonly workerImageDigest: string;
    readonly migratorImageDigest: string;
    readonly evidence: {
      readonly testCensusEvidenceSha256: string;
      readonly independentReviewEvidenceSha256: string;
      readonly securityEvidenceSha256: string;
      readonly migrationRestoreEvidenceSha256: string;
      readonly officeWordEvidenceSha256: string;
      readonly guardrailPolicySha256: string;
      readonly authorizedPracticeManifestSha256: string;
      readonly runtimeManifestSha256: string;
    };
    readonly status: string;
    readonly generation: string;
    readonly frozenAt: string | null;
    readonly createdAt: string;
    readonly updatedAt: string;
    readonly approvals: readonly ApprovalSummaryView[];
    readonly checkpoints: readonly CheckpointView[];
    readonly practices: readonly PracticeView[];
    readonly runtimeRequirements: readonly RuntimeRequirementView[];
    readonly operatorAuthorities: readonly string[];
  };
}

interface ApprovalSummaryView {
  readonly id: string;
  readonly discipline: string;
  readonly decision: string;
  readonly evidenceSha256: string;
  readonly actorId: string;
  readonly actorEmailSnapshot: string | null;
  readonly authorityAssignmentId: string;
  readonly authorityActive: boolean;
  readonly auditOutboxEventKey: string;
  readonly decidedAt: string;
}

interface CheckpointView {
  readonly id: string;
  readonly stage: string;
  readonly ordinal: number;
  readonly targetPercent: number;
  readonly targetPhysicianCount: number;
  readonly assignedPhysicianCount: number;
  readonly status: string;
  readonly minimumBakeSeconds: number;
  readonly activatedPhysicianCount: number | null;
  readonly passedPhysicianCount: number | null;
  readonly activatedAt: string | null;
  readonly earliestPassAt: string | null;
  readonly passedAt: string | null;
  readonly revokedAt: string | null;
  readonly latestMetric: null | {
    readonly canonicalSha256: string;
    readonly evaluation: string;
    readonly sampleCount: number;
    readonly observationStartedAt: string;
    readonly observationEndedAt: string;
    readonly missingMetrics: readonly string[];
    readonly breachedMetrics: readonly string[];
    readonly blockingReasons: readonly string[];
  };
}

interface PracticeView {
  readonly practiceId: string;
  readonly practiceSlugSnapshot: string;
  readonly physicianCountSnapshot: number;
  readonly cohortRank: number;
  readonly isCanary: boolean;
  readonly activationStage: string;
  readonly templateTwinEnabled: boolean;
  readonly rolloutGeneration: string;
}

interface RuntimeRequirementView {
  readonly instanceId: string;
  readonly component: string;
  readonly sourceCommitSha: string;
  readonly imageDigest: string;
  readonly ready: boolean;
  readonly lastSeenAt: string | null;
  readonly expiresAt: string | null;
}

export async function inspectTemplateTwinReleaseControl(
  input: {
    readonly releaseId?: string;
    readonly operatorUserId?: string;
  } = {},
): Promise<TemplateTwinReleaseControlView> {
  const requestedId = input.releaseId ? uuid(input.releaseId) : null;
  const [globalRows, releaseRows] = await Promise.all([
    database.$queryRaw<GlobalControlRow[]>(Prisma.sql`
      SELECT "enabled", "generation", "rollbackFenceState", "rollbackOperationId"
      FROM "template_twin_rollout_controls"
      WHERE "id" = ${TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID}
    `),
    requestedId
      ? database.$queryRaw<ReleaseRow[]>(Prisma.sql`
          SELECT * FROM "template_twin_release_candidates"
          WHERE "id" = ${requestedId}::UUID
          LIMIT 1
        `)
      : database.$queryRaw<ReleaseRow[]>(Prisma.sql`
          SELECT * FROM "template_twin_release_candidates"
          ORDER BY "createdAt" DESC, "id" DESC
          LIMIT 1
        `),
  ]);
  const global = globalRows[0];
  if (!global) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_CONTROL_UNAVAILABLE",
      "The global Template Twin rollout control is unavailable.",
    );
  }
  const release = releaseRows[0];
  if (!release) {
    return {
      global: {
        enabled: global.enabled,
        generation: exactGeneration(global.generation).toString(),
        rollbackFenceState: global.rollbackFenceState,
      },
      release: null,
    };
  }
  const [
    approvals,
    checkpoints,
    practices,
    metrics,
    runtimeRequirements,
    authorities,
  ] = await Promise.all([
    database.$queryRaw<ApprovalSummaryRow[]>(Prisma.sql`
        SELECT DISTINCT ON (decision."discipline")
          decision."id", decision."discipline", decision."decision",
          decision."evidenceSha256", decision."actorId",
          decision."actorEmailSnapshot", decision."authorityAssignmentId",
          decision."auditOutboxEventKey", decision."decidedAt",
          (authority."revokedAt" IS NULL) AS "authorityActive"
        FROM "template_twin_release_approval_decisions" decision
        JOIN "template_twin_release_authorities" authority
          ON authority."id" = decision."authorityAssignmentId"
        WHERE decision."releaseId" = ${release.id}::UUID
        ORDER BY decision."discipline", decision."decidedAt" DESC, decision."id" DESC
      `),
    database.$queryRaw<CheckpointRow[]>(Prisma.sql`
        SELECT * FROM "template_twin_release_checkpoints"
        WHERE "releaseId" = ${release.id}::UUID
        ORDER BY "ordinal" ASC
      `),
    database.$queryRaw<ManifestRow[]>(Prisma.sql`
        SELECT manifest.*, practice."templateTwinEnabled",
          practice."templateTwinRolloutGeneration"
        FROM "template_twin_release_practices" manifest
        JOIN "practices" practice ON practice."id" = manifest."practiceId"
        WHERE manifest."releaseId" = ${release.id}::UUID
        ORDER BY manifest."cohortRank" ASC
      `),
    database.$queryRaw<MetricRow[]>(Prisma.sql`
        SELECT DISTINCT ON (metric."checkpointId") metric.*
        FROM "template_twin_release_metric_snapshots" metric
        WHERE metric."releaseId" = ${release.id}::UUID
        ORDER BY metric."checkpointId", metric."createdAt" DESC, metric."id" DESC
      `),
    database.$queryRaw<
      Array<{
        instanceId: string;
        component: string;
        sourceCommitSha: string;
        imageDigest: string;
        ready: boolean;
        lastSeenAt: Date | null;
        expiresAt: Date | null;
      }>
    >(Prisma.sql`
        SELECT requirement."instanceId", requirement."component",
          requirement."sourceCommitSha", requirement."imageDigest",
          (latest."expiresAt" > clock_timestamp() + INTERVAL '30 seconds'
            AND latest."lastSeenAt" > clock_timestamp() - INTERVAL '75 seconds') AS "ready",
          latest."lastSeenAt", latest."expiresAt"
        FROM "template_twin_release_runtime_requirements" requirement
        LEFT JOIN LATERAL (
          SELECT attestation."lastSeenAt", attestation."expiresAt"
          FROM "template_twin_release_runtime_attestations" attestation
          WHERE attestation."requirementId" = requirement."id"
          ORDER BY attestation."lastSeenAt" DESC, attestation."id" DESC
          LIMIT 1
        ) latest ON TRUE
        WHERE requirement."releaseId" = ${release.id}::UUID
        ORDER BY requirement."component", requirement."instanceId"
      `),
    input.operatorUserId
      ? database.$queryRaw<AuthorityRow[]>(Prisma.sql`
            SELECT "id", "discipline"
            FROM "template_twin_release_authorities"
            WHERE "userId" = ${input.operatorUserId}
              AND "effectiveAt" <= CURRENT_TIMESTAMP
              AND "revokedAt" IS NULL
            ORDER BY "discipline" ASC
          `)
      : Promise.resolve([] as AuthorityRow[]),
  ]);
  const metricByCheckpoint = new Map(
    metrics.map((metric) => [metric.checkpointId, metric]),
  );
  return {
    global: {
      enabled: global.enabled,
      generation: exactGeneration(global.generation).toString(),
      rollbackFenceState: global.rollbackFenceState,
    },
    release: {
      id: release.id,
      releaseIdentitySha256: release.releaseIdentitySha256,
      sourceCommitSha: release.sourceCommitSha,
      baseCommitSha: release.baseCommitSha,
      appImageDigest: release.appImageDigest,
      workerImageDigest: release.workerImageDigest,
      migratorImageDigest: release.migratorImageDigest,
      evidence: {
        testCensusEvidenceSha256: release.testCensusEvidenceSha256,
        independentReviewEvidenceSha256:
          release.independentReviewEvidenceSha256,
        securityEvidenceSha256: release.securityEvidenceSha256,
        migrationRestoreEvidenceSha256: release.migrationRestoreEvidenceSha256,
        officeWordEvidenceSha256: release.officeWordEvidenceSha256,
        guardrailPolicySha256: release.guardrailPolicySha256,
        authorizedPracticeManifestSha256:
          release.authorizedPracticeManifestSha256,
        runtimeManifestSha256: release.runtimeManifestSha256,
      },
      status: release.status,
      generation: exactGeneration(release.generation).toString(),
      frozenAt: release.frozenAt?.toISOString() ?? null,
      createdAt: release.createdAt.toISOString(),
      updatedAt: release.updatedAt.toISOString(),
      approvals: approvals.map((approval) => ({
        ...approval,
        decidedAt: approval.decidedAt.toISOString(),
      })),
      checkpoints: checkpoints.map((checkpoint) => {
        const metric = metricByCheckpoint.get(checkpoint.id);
        return {
          id: checkpoint.id,
          stage: checkpoint.stage,
          ordinal: checkpoint.ordinal,
          targetPercent: checkpoint.targetPercent,
          targetPhysicianCount: checkpoint.targetPhysicianCount,
          assignedPhysicianCount: checkpoint.assignedPhysicianCount,
          status: checkpoint.status,
          minimumBakeSeconds: checkpoint.minimumBakeSeconds,
          activatedPhysicianCount: checkpoint.activatedPhysicianCount,
          passedPhysicianCount: checkpoint.passedPhysicianCount,
          activatedAt: checkpoint.activatedAt?.toISOString() ?? null,
          earliestPassAt: checkpoint.earliestPassAt?.toISOString() ?? null,
          passedAt: checkpoint.passedAt?.toISOString() ?? null,
          revokedAt: checkpoint.revokedAt?.toISOString() ?? null,
          latestMetric: metric
            ? {
                canonicalSha256: metric.canonicalSha256,
                evaluation: metric.evaluation,
                sampleCount: metric.sampleCount,
                observationStartedAt: metric.observationStartedAt.toISOString(),
                observationEndedAt: metric.observationEndedAt.toISOString(),
                missingMetrics: metric.missingMetrics,
                breachedMetrics: metric.breachedMetrics,
                blockingReasons: metric.blockingReasons,
              }
            : null,
        };
      }),
      practices: practices.map((practice) => ({
        practiceId: practice.practiceId,
        practiceSlugSnapshot: practice.practiceSlugSnapshot,
        physicianCountSnapshot: practice.physicianCountSnapshot,
        cohortRank: practice.cohortRank,
        isCanary: practice.isCanary,
        activationStage: practice.activationStage,
        templateTwinEnabled: practice.templateTwinEnabled ?? false,
        rolloutGeneration: exactGeneration(
          practice.templateTwinRolloutGeneration ?? 1,
        ).toString(),
      })),
      runtimeRequirements: runtimeRequirements.map((requirement) => ({
        ...requirement,
        ready: requirement.ready === true,
        lastSeenAt: requirement.lastSeenAt?.toISOString() ?? null,
        expiresAt: requirement.expiresAt?.toISOString() ?? null,
      })),
      operatorAuthorities: authorities.map(({ discipline }) => discipline),
    },
  };
}
