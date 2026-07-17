import { TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION } from "@meddoc/ai";
import { Prisma } from "@prisma/client";

import type { TemplateTwinRolloutToken } from "./rollout";
import {
  assertTemplateTwinStagingQaGate,
  isTemplateTwinStagingQaRequested,
} from "./staging-qa-gate";
import {
  lockAndAssertTemplateTwinStagingQaAdmission,
  type TemplateTwinStagingQaAdmissionPhase,
  type TemplateTwinStagingQaAdmissionRow,
} from "./staging-qa-admission";

/**
 * Small projection shared by every visit-bound staging QA entry point. Keeping
 * this select in one module makes it difficult for a new route to accidentally
 * check only a visit owner while omitting the durable staging admission epoch.
 */
export const TEMPLATE_TWIN_STAGING_QA_RUN_GUARD_SELECT = {
  id: true,
  admissionId: true,
  visitId: true,
  practiceId: true,
  doctorId: true,
  noteTemplateId: true,
  noteTemplateVersion: true,
  requestSha256: true,
  payloadSha256: true,
  mode: true,
  status: true,
  fixtureVersion: true,
  attempt: true,
  pinnedGlobalRolloutGeneration: true,
  pinnedPracticeRolloutGeneration: true,
  admission: {
    select: {
      id: true,
      practiceId: true,
      actorId: true,
      parentAdmissionId: true,
      sourceSha256: true,
      sourceSizeBytes: true,
      fixtureVersion: true,
      providerMode: true,
      purpose: true,
      phase: true,
      requestSha256: true,
      payloadSha256: true,
      pinnedGlobalRolloutGeneration: true,
      pinnedPracticeRolloutGeneration: true,
      sourceArtifactId: true,
      noteTemplateId: true,
      noteTemplateVersion: true,
      certificationId: true,
      mappingSha256: true,
      visitId: true,
      attempt: true,
      expiresAt: true,
      failedAt: true,
      revokedAt: true,
      consumedAt: true,
    },
  },
} as const;

export interface TemplateTwinStagingQaRunGuardRow {
  id: string;
  admissionId: string | null;
  visitId: string;
  practiceId: string;
  doctorId: string;
  noteTemplateId: string;
  noteTemplateVersion: number;
  requestSha256: string;
  payloadSha256: string;
  mode: string;
  status: string;
  fixtureVersion: string;
  attempt: number;
  pinnedGlobalRolloutGeneration: bigint;
  pinnedPracticeRolloutGeneration: bigint;
  admission: TemplateTwinStagingQaAdmissionRow | null;
}

export type TemplateTwinStagingQaVisitGuardCode =
  | "TEMPLATE_TWIN_STAGING_QA_NOT_FOUND"
  | "TEMPLATE_TWIN_STAGING_QA_FIXTURE_STALE"
  | "TEMPLATE_TWIN_STAGING_QA_ROLLOUT_STALE"
  | "TEMPLATE_TWIN_STAGING_QA_ADMISSION_STALE"
  | "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE";

export class TemplateTwinStagingQaVisitGuardError extends Error {
  constructor(
    readonly code: TemplateTwinStagingQaVisitGuardCode,
    message: string,
  ) {
    super(message);
    this.name = "TemplateTwinStagingQaVisitGuardError";
  }
}

interface StagingQaRunLockClient {
  $queryRaw<T>(query: Prisma.Sql): Promise<T>;
}

interface LockedStagingQaActorRow {
  id: string;
  practiceId: string;
  role: string;
  isActive: boolean;
}

export async function lockAndAssertTemplateTwinStagingQaActor(input: {
  tx: StagingQaRunLockClient;
  actor: { userId: string; practiceId: string };
}): Promise<void> {
  const actors = await input.tx.$queryRaw<LockedStagingQaActorRow[]>(Prisma.sql`
    SELECT "id", "practiceId", "role"::text AS "role", "isActive"
    FROM "users"
    WHERE "id" = ${input.actor.userId}
    FOR UPDATE
  `);
  const actor = actors[0] ?? null;
  if (
    !actor ||
    actor.practiceId !== input.actor.practiceId ||
    actor.role !== "DOCTOR" ||
    actor.isActive !== true
  ) {
    throw new TemplateTwinStagingQaVisitGuardError(
      "TEMPLATE_TWIN_STAGING_QA_NOT_FOUND",
      "Synthetic QA visit not found.",
    );
  }
}

export interface TemplateTwinSyntheticQaAttemptClaim {
  runId: string;
  visitId: string;
  practiceId: string;
  doctorId: string;
  fixtureVersion: string;
  requestSha256: string;
  attempt: number;
  workerClaimId: string;
  pinnedGlobalGeneration: bigint;
  pinnedPracticeGeneration: bigint;
}

export interface LockedStagingQaRunRow extends TemplateTwinStagingQaRunGuardRow {
  attempt: number;
  enqueuedAt: Date | null;
  workerClaimId: string | null;
  workerClaimedAt: Date | null;
  workerHeartbeatAt: Date | null;
  workerLeaseExpiresAt: Date | null;
}

/**
 * Locks one durable staging operation after the caller has acquired rollout
 * controls. All clinical transitions use the same order:
 * global rollout -> practice rollout -> durable admission -> staging run ->
 * actor -> visit -> fill.
 *
 * `expectedAttempt` is the admission epoch for retry/correction/signing. A
 * later retry increments it, so an operation that performed expensive work
 * against an older attempt loses closed even when the rollout generation did
 * not change.
 */
export async function lockAndAssertTemplateTwinStagingQaRun(input: {
  tx: StagingQaRunLockClient;
  runId: string;
  expectedAttempt?: number;
  actor: { userId: string; practiceId: string };
  currentRolloutToken: TemplateTwinRolloutToken;
  allowedAdmissionPhases?: readonly TemplateTwinStagingQaAdmissionPhase[];
}): Promise<LockedStagingQaRunRow> {
  const identities = await input.tx.$queryRaw<{ admissionId: string | null }[]>(
    Prisma.sql`
      SELECT "admissionId"
      FROM "template_twin_synthetic_qa_runs"
      WHERE "id" = ${input.runId}
    `,
  );
  const admissionId = identities[0]?.admissionId ?? null;
  if (!admissionId) {
    throw new TemplateTwinStagingQaVisitGuardError(
      "TEMPLATE_TWIN_STAGING_QA_ADMISSION_STALE",
      "Synthetic QA admission is unavailable.",
    );
  }
  const admission = await lockAndAssertTemplateTwinStagingQaAdmission({
    tx: input.tx,
    admissionId,
    actor: input.actor,
    currentToken: input.currentRolloutToken,
    allowedPhases: input.allowedAdmissionPhases ?? [
      "VISIT_LINKED",
      "PROCESSING",
      "REVIEW_READY",
      "SIGNED",
    ],
  });
  const rows = await input.tx.$queryRaw<LockedStagingQaRunRow[]>(Prisma.sql`
    SELECT
      "id", "admissionId", "visitId", "practiceId", "doctorId",
      "noteTemplateId", "noteTemplateVersion", "requestSha256",
      "payloadSha256", "mode", "fixtureVersion", "status", "attempt", "enqueuedAt",
      "workerClaimId", "workerClaimedAt", "workerHeartbeatAt",
      "workerLeaseExpiresAt",
      "pinnedGlobalRolloutGeneration", "pinnedPracticeRolloutGeneration"
    FROM "template_twin_synthetic_qa_runs"
    WHERE "id" = ${input.runId}
    FOR UPDATE
  `);
  const rawRun = rows[0] ?? null;
  const run = rawRun ? { ...rawRun, admission } : null;
  assertTemplateTwinStagingQaVisitGuard({
    run,
    actor: input.actor,
    currentRolloutToken: input.currentRolloutToken,
    expectedRunId: input.runId,
    allowedAdmissionPhases: input.allowedAdmissionPhases,
  });
  if (
    !run ||
    (input.expectedAttempt !== undefined &&
      run.attempt !== input.expectedAttempt)
  ) {
    throw new TemplateTwinStagingQaVisitGuardError(
      "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
      "A newer synthetic QA attempt replaced this operation. Retry from the current run.",
    );
  }
  await lockAndAssertTemplateTwinStagingQaActor({
    tx: input.tx,
    actor: input.actor,
  });
  return run;
}

export async function lockAndAssertTemplateTwinStagingQaOperation(input: {
  tx: StagingQaRunLockClient;
  runId: string;
  expectedAttempt: number;
  actor: { userId: string; practiceId: string };
  currentRolloutToken: TemplateTwinRolloutToken;
  allowedStatuses?: readonly string[];
  allowedAdmissionPhases?: readonly TemplateTwinStagingQaAdmissionPhase[];
}): Promise<LockedStagingQaRunRow> {
  const run = await lockAndAssertTemplateTwinStagingQaRun(input);
  const allowedStatuses = input.allowedStatuses ?? [
    "ENQUEUED",
    "PROCESSING",
    "COMPLETED",
  ];
  if (!allowedStatuses.includes(run.status) || run.enqueuedAt === null) {
    throw new TemplateTwinStagingQaVisitGuardError(
      "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
      "This synthetic QA operation is no longer durably enqueued.",
    );
  }
  return run;
}

/**
 * Final worker-output admission. Call only after the global and practice
 * rollout locks are held; this then locks the durable run, preserving the
 * global -> practice -> run -> visit/fill lock order. A retry increments the
 * attempt, so an older BullMQ delivery can never claim its rendered object.
 */
export async function lockAndAssertTemplateTwinStagingQaAttempt(input: {
  tx: StagingQaRunLockClient;
  claim: TemplateTwinSyntheticQaAttemptClaim | null;
  currentRolloutToken: TemplateTwinRolloutToken;
  allowedStatuses?: readonly string[];
  allowedAdmissionPhases?: readonly TemplateTwinStagingQaAdmissionPhase[];
  requireLiveWorkerLease?: boolean;
}): Promise<void> {
  if (!input.claim) return;
  const run = await lockAndAssertTemplateTwinStagingQaOperation({
    tx: input.tx,
    runId: input.claim.runId,
    expectedAttempt: input.claim.attempt,
    actor: {
      userId: input.claim.doctorId,
      practiceId: input.claim.practiceId,
    },
    currentRolloutToken: input.currentRolloutToken,
    allowedStatuses: input.allowedStatuses,
    allowedAdmissionPhases: input.allowedAdmissionPhases,
  });
  if (
    run.visitId !== input.claim.visitId ||
    run.requestSha256 !== input.claim.requestSha256 ||
    run.workerClaimId !== input.claim.workerClaimId ||
    run.fixtureVersion !== input.claim.fixtureVersion ||
    run.pinnedGlobalRolloutGeneration !== input.claim.pinnedGlobalGeneration ||
    run.pinnedPracticeRolloutGeneration !== input.claim.pinnedPracticeGeneration
  ) {
    throw new TemplateTwinStagingQaVisitGuardError(
      "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
      "A newer synthetic QA attempt replaced this worker claim. Retry from the current run.",
    );
  }
  if (input.requireLiveWorkerLease === true) {
    // This query deliberately runs *after* SELECT ... FOR UPDATE returned.
    // CURRENT_TIMESTAMP is the transaction-start instant and can be stale
    // after a lock wait; clock_timestamp() is PostgreSQL wall time at this
    // exact post-lock fencing point.
    const clockRows = await input.tx.$queryRaw<{ databaseNow: Date }[]>(
      Prisma.sql`SELECT clock_timestamp() AS "databaseNow"`,
    );
    const databaseNow = clockRows[0]?.databaseNow;
    if (
      !databaseNow ||
      run.workerHeartbeatAt === null ||
      run.workerLeaseExpiresAt === null ||
      run.workerLeaseExpiresAt <= databaseNow
    ) {
      throw new TemplateTwinStagingQaVisitGuardError(
        "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
        "The synthetic QA worker lease expired before this final claim. Retry from the current run.",
      );
    }
  }
}

/**
 * Fail-closed admission for an already-created synthetic QA visit.
 *
 * Normal visits have no staging row and preserve their existing behavior. A
 * marked visit, however, remains synthetic-only for its entire lifetime: the
 * process gate must still be explicitly enabled, actor and tenant must match,
 * the fixture contract must still be current, and the current database-backed
 * rollout epoch must equal the immutable epoch pinned when the run was
 * admitted. Disable/re-enable increments an epoch, so it cannot revive an old
 * staging visit.
 *
 * Callers that make a state transition must still use the normal rollout lock
 * in their final transaction. This admission comparison complements, rather
 * than replaces, that linearizable final-claim check.
 */
export function assertTemplateTwinStagingQaVisitGuard(input: {
  run: TemplateTwinStagingQaRunGuardRow | null | undefined;
  actor: { userId: string; practiceId: string };
  currentRolloutToken: TemplateTwinRolloutToken;
  expectedRunId?: string;
  allowedAdmissionPhases?: readonly TemplateTwinStagingQaAdmissionPhase[];
  env?: Readonly<Record<string, string | undefined>>;
}): { applies: false } | { applies: true; runId: string } {
  if (!input.run) {
    if (input.expectedRunId || isTemplateTwinStagingQaRequested(input.env)) {
      throw new TemplateTwinStagingQaVisitGuardError(
        "TEMPLATE_TWIN_STAGING_QA_NOT_FOUND",
        "Synthetic QA visit not found.",
      );
    }
    return { applies: false };
  }

  assertTemplateTwinStagingQaGate();

  if (
    input.run.doctorId !== input.actor.userId ||
    input.run.practiceId !== input.actor.practiceId ||
    input.currentRolloutToken.practiceId !== input.actor.practiceId ||
    (input.expectedRunId !== undefined && input.run.id !== input.expectedRunId)
  ) {
    throw new TemplateTwinStagingQaVisitGuardError(
      "TEMPLATE_TWIN_STAGING_QA_NOT_FOUND",
      "Synthetic QA visit not found.",
    );
  }
  const admission = input.run.admission;
  const allowedAdmissionPhases = input.allowedAdmissionPhases ?? [
    "VISIT_LINKED",
    "PROCESSING",
    "REVIEW_READY",
    "SIGNED",
  ];
  const expectedProviderMode =
    input.run.mode === "typed"
      ? "SYNTHETIC_TYPED"
      : input.run.mode === "mock_voice"
        ? "SYNTHETIC_MOCK_VOICE"
        : null;
  if (
    !admission ||
    input.run.admissionId !== admission.id ||
    admission.practiceId !== input.run.practiceId ||
    admission.actorId !== input.run.doctorId ||
    !admission.parentAdmissionId ||
    admission.purpose !== "VISIT" ||
    admission.providerMode !== expectedProviderMode ||
    !allowedAdmissionPhases.includes(
      admission.phase as TemplateTwinStagingQaAdmissionPhase,
    ) ||
    admission.requestSha256 !== input.run.requestSha256 ||
    admission.payloadSha256 !== input.run.payloadSha256 ||
    admission.noteTemplateId !== input.run.noteTemplateId ||
    admission.noteTemplateVersion !== input.run.noteTemplateVersion ||
    admission.visitId !== input.run.visitId ||
    admission.attempt !== input.run.attempt ||
    admission.failedAt !== null ||
    admission.revokedAt !== null ||
    (admission.phase === "SIGNED"
      ? admission.consumedAt === null
      : admission.consumedAt !== null) ||
    admission.expiresAt <= new Date() ||
    admission.pinnedGlobalRolloutGeneration !==
      input.run.pinnedGlobalRolloutGeneration ||
    admission.pinnedPracticeRolloutGeneration !==
      input.run.pinnedPracticeRolloutGeneration
  ) {
    throw new TemplateTwinStagingQaVisitGuardError(
      "TEMPLATE_TWIN_STAGING_QA_ADMISSION_STALE",
      "Synthetic QA admission is unavailable.",
    );
  }
  if (input.run.fixtureVersion !== TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION) {
    throw new TemplateTwinStagingQaVisitGuardError(
      "TEMPLATE_TWIN_STAGING_QA_FIXTURE_STALE",
      "This synthetic QA run uses an older fixture contract. Create a new run.",
    );
  }
  if (
    input.run.pinnedGlobalRolloutGeneration !==
      input.currentRolloutToken.globalGeneration ||
    input.run.pinnedPracticeRolloutGeneration !==
      input.currentRolloutToken.practiceGeneration
  ) {
    throw new TemplateTwinStagingQaVisitGuardError(
      "TEMPLATE_TWIN_STAGING_QA_ROLLOUT_STALE",
      "Synthetic QA rollout changed after this run began. Create a new run.",
    );
  }
  return { applies: true, runId: input.run.id };
}

/** Production delivery is deliberately narrower for synthetic QA visits. */
export function templateTwinStagingQaDestinationsAreAllowed(
  run: TemplateTwinStagingQaRunGuardRow | null | undefined,
  destinations: readonly string[],
): boolean {
  if (!run) return true;
  return (
    destinations.length <= 1 &&
    destinations.every(
      (destination) => destination === "docx_original_template",
    )
  );
}
