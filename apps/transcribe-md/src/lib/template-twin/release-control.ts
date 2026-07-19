import "server-only";

import { randomUUID } from "node:crypto";

import prisma from "@meddoc/db";
import { Prisma, type PrismaClient } from "@prisma/client";

import { ADMIN_SESSION_MAX_AGE_HOURS } from "@/lib/admin-session-freshness";
import { runSerializableTransactionWithRetry } from "@/lib/db/transaction-retry";
import {
  TEMPLATE_TWIN_ROLLBACK_COMPAT_RUNTIME_MODE,
  resolveTemplateTwinRuntimeMode,
} from "@/lib/runtime-protocol";
import {
  assertTemplateTwinAuditMetadata,
  enqueueTemplateTwinAudit,
} from "./audit-outbox";
import { canonicalSha256 } from "./canonical";
import {
  applyTemplateTwinGlobalRolloutMutation,
  TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID,
  TEMPLATE_TWIN_RELEASE_CONTROL_LOCK_KEY,
  TEMPLATE_TWIN_RELEASE_CONTROL_LOCK_NAMESPACE,
} from "./rollout";
import {
  buildTemplateTwinCohortPlan,
  evaluateTemplateTwinMetricSnapshot,
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
  type TemplateTwinReleaseStage,
  type TemplateTwinReleaseStatus,
} from "./release-control-contracts";

const ADMIN_SESSION_MAX_AGE_MS = ADMIN_SESSION_MAX_AGE_HOURS * 60 * 60 * 1000;
const database = prisma as PrismaClient;

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

interface VerifiedReleaseActor {
  readonly userId: string;
  readonly email: string;
  readonly practiceId: string;
  readonly sessionSha256: string;
}

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
  return tx.$queryRaw<ManifestRow[]>(Prisma.sql`
    SELECT manifest.*,
      practice."templateTwinEnabled",
      practice."templateTwinRolloutGeneration"
    FROM "template_twin_release_practices" manifest
    JOIN "practices" practice ON practice."id" = manifest."practiceId"
    WHERE manifest."releaseId" = ${releaseId}::UUID
    ORDER BY manifest."cohortRank" ASC
    FOR UPDATE OF manifest, practice
  `);
}

async function verifyReleaseActor(
  tx: ControlTransaction,
  actor: TemplateTwinReleaseActor,
  now = new Date(),
): Promise<VerifiedReleaseActor> {
  if (!actor.userId || !actor.sessionId) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_UNAUTHORIZED",
      "A live, MFA-verified platform administrator session is required.",
    );
  }
  const rows = await tx.$queryRaw<
    Array<{
      userId: string;
      email: string;
      practiceId: string;
      products: string[];
      isActive: boolean;
      deactivatedAt: Date | null;
      suspendedAt: Date | null;
      softDeletedAt: Date | null;
      forceLogoutAt: Date | null;
      mfaEnabled: boolean;
      mfaVerifiedAt: Date | null;
      sessionCreatedAt: Date;
      sessionExpiresAt: Date;
    }>
  >(Prisma.sql`
    SELECT
      account."id" AS "userId", account."email", account."practiceId",
      account."products", account."isActive", account."deactivatedAt",
      account."suspendedAt", account."softDeletedAt", account."forceLogoutAt",
      account."mfaEnabled", account."mfaVerifiedAt",
      session."createdAt" AS "sessionCreatedAt",
      session."expiresAt" AS "sessionExpiresAt"
    FROM "users" account
    JOIN "user_sessions" session ON session."userId" = account."id"
    WHERE account."id" = ${actor.userId}
      AND session."sessionToken" = ${actor.sessionId}
    FOR SHARE OF account, session
  `);
  const row = rows[0];
  const nowMs = now.getTime();
  if (
    !row ||
    !row.isActive ||
    row.deactivatedAt !== null ||
    row.suspendedAt !== null ||
    row.softDeletedAt !== null ||
    !row.products.includes("SUPER_ADMIN") ||
    !row.mfaEnabled ||
    row.mfaVerifiedAt === null ||
    row.sessionCreatedAt.getTime() > nowMs ||
    nowMs - row.sessionCreatedAt.getTime() >= ADMIN_SESSION_MAX_AGE_MS ||
    row.sessionExpiresAt.getTime() <= nowMs ||
    (row.forceLogoutAt !== null &&
      row.forceLogoutAt.getTime() >= row.sessionCreatedAt.getTime())
  ) {
    throw new TemplateTwinReleaseControlError(
      "TEMPLATE_TWIN_RELEASE_UNAUTHORIZED",
      "A live, MFA-verified platform administrator session is required.",
    );
  }
  return {
    userId: row.userId,
    email: row.email,
    practiceId: row.practiceId,
    sessionSha256: canonicalSha256({
      version: "template-twin-release-actor-session-v1",
      sessionId: actor.sessionId,
    }),
  };
}

function rolloutActor(actor: VerifiedReleaseActor) {
  return {
    userId: actor.userId,
    userEmail: actor.email,
    practiceId: actor.practiceId,
  };
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
    FOR SHARE
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
  actor: VerifiedReleaseActor;
  global: GlobalControlRow;
  manifest: readonly ManifestRow[];
}): Promise<bigint> {
  const generation = await applyTemplateTwinGlobalRolloutMutation({
    tx: input.tx,
    enabled: false,
    actor: rolloutActor(input.actor),
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

async function applyReleasePracticeExposureBatch(input: {
  readonly tx: ControlTransaction;
  readonly practices: readonly ManifestRow[];
  readonly enabled: boolean;
  readonly actor: VerifiedReleaseActor;
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
    await input.tx.templateTwinAuditOutbox.createMany({
      data: auditRows.slice(offset, offset + 500),
    });
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
  };
}

export async function createTemplateTwinReleaseCandidate(input: {
  readonly actor: TemplateTwinReleaseActor;
  readonly confirmation: string;
  readonly evidence: TemplateTwinReleaseIdentityEvidence;
  readonly guardrailPolicy: unknown;
  readonly authorizedPracticeIds: readonly string[];
  readonly canaryPracticeIds: readonly string[];
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
      const identityInput = {
        ...input.evidence,
        guardrailPolicySha256: policySha256,
        authorizedPracticeManifestSha256: plan.authorizedPracticeManifestSha256,
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
          ${JSON.stringify(policy)}::JSONB, 'DRAFT', 1, ${actor.userId}
        )
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
      await enqueueTemplateTwinAudit(tx, {
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
        },
      });
      return {
        releaseId,
        releaseIdentitySha256,
        authorizedPracticeManifestSha256: plan.authorizedPracticeManifestSha256,
        guardrailPolicySha256: policySha256,
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
      const actor = await verifyReleaseActor(tx, input.actor);
      const manifest = await lockManifest(tx, releaseId);
      await lockCheckpoints(tx, releaseId);
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
      if (
        templateTwinGuardrailPolicySha256(policy) !==
          release.guardrailPolicySha256 ||
        plan.authorizedPracticeManifestSha256 !==
          release.authorizedPracticeManifestSha256 ||
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

      const eventKey = `template-twin:release:${releaseId}:frozen`;
      await enqueueTemplateTwinAudit(tx, {
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
        },
      });
      await tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_release_candidates"
        SET "status" = 'FROZEN', "generation" = "generation" + 1,
            "frozenById" = ${actor.userId}, "frozenAt" = CURRENT_TIMESTAMP,
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
    const actor = await verifyReleaseActor(tx, input.actor);
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
        FOR SHARE
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
    await enqueueTemplateTwinAudit(tx, {
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
        requestedReleaseGeneration: expected.toString(),
        previousReleaseGeneration: observedGeneration.toString(),
      },
    });
    await tx.$executeRaw(Prisma.sql`
        INSERT INTO "template_twin_release_approval_decisions" (
          "id", "releaseId", "releaseIdentitySha256", "discipline",
          "decision", "evidenceSha256", "confirmation", "actorId",
          "actorEmailSnapshot", "actorSessionSha256",
          "authorityAssignmentId", "auditOutboxEventKey"
        ) VALUES (
          ${decisionId}::UUID, ${releaseId}::UUID,
          ${release.releaseIdentitySha256}, ${input.discipline},
          ${input.decision}, ${input.evidenceSha256}, ${input.confirmation},
          ${actor.userId}, ${actor.email}, ${actor.sessionSha256},
          ${authority.id}::UUID, ${eventKey}
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
      const actor = await verifyReleaseActor(tx, input.actor);
      assertExpectedReleaseGeneration(release, expectedRelease);
      assertExpectedGlobalGeneration(global, expectedGlobal);
      assertRollbackFenceOpen(global);
      assertRuntimeIdentity(release, input.env);
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
      const now = new Date();
      const eventKey =
        `template-twin:release:${releaseId}:checkpoint:` +
        `${input.stage}:activated`;
      await enqueueTemplateTwinAudit(tx, {
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
        },
      });
      await tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_release_checkpoints"
        SET "status" = 'ACTIVE', "activatedPhysicianCount" = ${activatedPhysicianCount},
            "activatedAt" = ${now},
            "earliestPassAt" = ${new Date(
              now.getTime() + checkpoint.minimumBakeSeconds * 1000,
            )},
            "activatedById" = ${actor.userId},
            "activationOutboxEventKey" = ${eventKey},
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

      const nextGlobalGeneration = await applyTemplateTwinGlobalRolloutMutation(
        {
          tx,
          enabled: true,
          actor: rolloutActor(actor),
        },
      );
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
  readonly actor: TemplateTwinReleaseActor;
  readonly releaseId: string;
  readonly stage: TemplateTwinReleaseStage;
  readonly expectedReleaseGeneration: string;
  readonly expectedGlobalGeneration: string;
  readonly sampleCount: number;
  readonly observationStartedAt: Date;
  readonly observationEndedAt: Date;
  readonly metrics: unknown;
  readonly now?: Date;
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
  const evaluationNow = input.now ?? new Date();
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
      const actor = await verifyReleaseActor(tx, input.actor, evaluationNow);
      const checkpoint = checkpoints.find(({ stage }) => stage === input.stage);
      if (!checkpoint?.activatedAt) {
        throw new TemplateTwinReleaseControlError(
          "TEMPLATE_TWIN_RELEASE_STATE_CONFLICT",
          "Metrics can be attached only to an activated checkpoint.",
        );
      }
      const policy = parseTemplateTwinGuardrailPolicy(release.guardrailPolicy);
      const evaluation = evaluateTemplateTwinMetricSnapshot({
        releaseIdentitySha256: release.releaseIdentitySha256,
        policy,
        policySha256: release.guardrailPolicySha256,
        stage: input.stage,
        checkpointActivatedAt: checkpoint.activatedAt,
        sampleCount: input.sampleCount,
        observationStartedAt: input.observationStartedAt,
        observationEndedAt: input.observationEndedAt,
        metrics: input.metrics,
        now: evaluationNow,
      });
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
        await enqueueTemplateTwinAudit(tx, {
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
          "policySha256", "schemaVersion", "sampleCount",
          "observationStartedAt", "observationEndedAt", "metrics",
          "canonicalSha256", "evaluation", "missingMetrics",
          "breachedMetrics", "blockingReasons", "recordedById",
          "criticalOutboxEventKey"
        ) VALUES (
          ${snapshotId}::UUID, ${releaseId}::UUID, ${checkpoint.id}::UUID,
          ${release.releaseIdentitySha256}, ${release.guardrailPolicySha256},
          ${policy.schemaVersion}, ${input.sampleCount},
          ${input.observationStartedAt}, ${input.observationEndedAt},
          ${JSON.stringify(evaluation.metrics)}::JSONB,
          ${evaluation.canonicalSha256}, ${evaluation.evaluation},
          ${evaluation.missingMetrics}::TEXT[],
          ${evaluation.breachedMetrics}::TEXT[],
          ${evaluation.blockingReasons}::TEXT[], ${actor.userId},
          ${criticalEventKey}
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
      const actor = await verifyReleaseActor(tx, input.actor, input.now);
      assertExpectedReleaseGeneration(release, expectedRelease);
      assertExpectedGlobalGeneration(global, expectedGlobal);
      assertRollbackFenceOpen(global);
      assertRuntimeIdentity(release, input.env);
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
      const metricRows = await tx.$queryRaw<MetricRow[]>(Prisma.sql`
        SELECT * FROM "template_twin_release_metric_snapshots"
        WHERE "checkpointId" = ${checkpoint.id}::UUID
        ORDER BY "createdAt" DESC, "id" DESC
        LIMIT 1
        FOR SHARE
      `);
      const metric = metricRows[0];
      const policy = parseTemplateTwinGuardrailPolicy(release.guardrailPolicy);
      if (
        !metric ||
        metric.evaluation !== "PASS" ||
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
      const eventKey =
        `template-twin:release:${releaseId}:checkpoint:` +
        `${input.stage}:passed`;
      await enqueueTemplateTwinAudit(tx, {
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
        },
      });
      await tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_release_checkpoints"
        SET "status" = 'PASSED', "passedPhysicianCount" = ${passedPhysicianCount},
            "passedAt" = ${now}, "passedById" = ${actor.userId},
            "passOutboxEventKey" = ${eventKey},
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
      await enqueueTemplateTwinAudit(tx, {
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
    };
    readonly status: string;
    readonly generation: string;
    readonly frozenAt: string | null;
    readonly createdAt: string;
    readonly updatedAt: string;
    readonly approvals: readonly ApprovalSummaryView[];
    readonly checkpoints: readonly CheckpointView[];
    readonly practices: readonly PracticeView[];
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
  const [approvals, checkpoints, practices, metrics, authorities] =
    await Promise.all([
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
      operatorAuthorities: authorities.map(({ discipline }) => discipline),
    },
  };
}
