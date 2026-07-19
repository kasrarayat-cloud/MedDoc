#!/usr/bin/env tsx

// Actual-PostgreSQL proof for the Template Twin production control plane.
// The target must be a disposable database. The script exercises production
// service functions, independent database sessions, database-native
// capability enforcement, monotonic safety actions, immutable evidence, and
// all four release/enable race classes. Synthetic operational identities only;
// no clinical or patient content is created.

import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";

import { PrismaPg } from "@prisma/adapter-pg";
import { Prisma, PrismaClient } from "@prisma/client";

import {
  activateTemplateTwinReleaseCheckpoint,
  createTemplateTwinReleaseCandidate,
  freezeTemplateTwinReleaseCandidate,
  recordTemplateTwinReleaseApproval,
  recordTemplateTwinReleaseMetricSnapshot,
  passTemplateTwinReleaseCheckpoint,
  revokeTemplateTwinRelease,
  type TemplateTwinReleaseActor,
} from "../../../apps/transcribe-md/src/lib/template-twin/release-control";
import {
  TEMPLATE_TWIN_METRIC_DEFINITIONS,
  TEMPLATE_TWIN_RELEASE_DISCIPLINES,
  templateTwinApprovalConfirmation,
  templateTwinCheckpointConfirmation,
  type TemplateTwinGuardrailPolicy,
  type TemplateTwinMetricKey,
  type TemplateTwinReleaseDiscipline,
  type TemplateTwinReleaseIdentityEvidence,
} from "../../../apps/transcribe-md/src/lib/template-twin/release-control-contracts";
import { setTemplateTwinGlobalRollout } from "../../../apps/transcribe-md/src/lib/template-twin/rollout";
import { assertNonProdDatabase } from "../src/db-guard";

const databaseUrl =
  process.env.TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL ??
  process.env.DATABASE_URL;
if (!databaseUrl) {
  throw new Error("Disposable release-control test URL is required.");
}
assertNonProdDatabase(databaseUrl);
const disposableDatabaseUrl = databaseUrl;

process.env.TEMPLATE_TWIN_KILL_SWITCH = "false";
process.env.TEMPLATE_TWIN_RUNTIME_MODE = "standard";

const suffix = `${process.pid}-${Date.now()}`;
const syntheticSha = "a".repeat(64);
const scalePracticeCount = Number(
  process.env.TEMPLATE_TWIN_RELEASE_CONTROL_SCALE_PRACTICES ?? "10",
);
if (
  !Number.isSafeInteger(scalePracticeCount) ||
  scalePracticeCount < 10 ||
  scalePracticeCount > 10_000
) {
  throw new Error("Scale practice count must be an integer from 10 to 10,000.");
}
const administratorPracticeId = `synthetic-release-admin-${suffix}`;
const authorizedPracticeIds = Array.from(
  { length: scalePracticeCount },
  (_, index) => `synthetic-release-practice-${index + 1}-${suffix}`,
);
const creatorId = `synthetic-release-creator-${suffix}`;
const creatorSession = `synthetic-release-session-creator-${suffix}`;
const reviewerIds = new Map<TemplateTwinReleaseDiscipline, string>(
  TEMPLATE_TWIN_RELEASE_DISCIPLINES.map((discipline) => [
    discipline,
    `synthetic-release-reviewer-${discipline.toLowerCase()}-${suffix}`,
  ]),
);
const reviewerSessions = new Map<TemplateTwinReleaseDiscipline, string>(
  TEMPLATE_TWIN_RELEASE_DISCIPLINES.map((discipline) => [
    discipline,
    `synthetic-release-session-${discipline.toLowerCase()}-${suffix}`,
  ]),
);

function client(applicationName: string): PrismaClient {
  const url = new URL(disposableDatabaseUrl);
  url.searchParams.set("application_name", applicationName);
  return new PrismaClient({
    adapter: new PrismaPg({ connectionString: url.toString() }),
  });
}

const observer = client("template-twin-release-control-observer");
const attacker = client("template-twin-release-control-direct-sql");

const creator: TemplateTwinReleaseActor = {
  userId: creatorId,
  sessionId: creatorSession,
};

const policy: TemplateTwinGuardrailPolicy = {
  schemaVersion: "template-twin-guardrails-v1",
  maxObservationAgeSeconds: 3_600,
  minimumBakeSecondsByStage: {
    CANARY: 1,
    PERCENT_10: 1,
    PERCENT_25: 1,
    PERCENT_50: 1,
    PERCENT_100: 1,
  },
  minimumSampleCountByStage: {
    CANARY: 1,
    PERCENT_10: 1,
    PERCENT_25: 1,
    PERCENT_50: 1,
    PERCENT_100: 1,
  },
  metrics: Object.fromEntries(
    Object.entries(TEMPLATE_TWIN_METRIC_DEFINITIONS).map(
      ([key, definition]) => [
        key,
        {
          direction: definition.direction,
          threshold:
            definition.direction === "MAX" ? definition.min : definition.max,
          critical: [
            "unsafe_bypass_attempt_count",
            "provider_ambiguous_outcome_count",
            "critical_field_accuracy",
            "hallucination_rate",
            "evidence_anchor_validity",
            "exact_dropdown_accuracy",
            "negation_accuracy",
            "laterality_accuracy",
            "table_placement_accuracy",
          ].includes(key),
        },
      ],
    ),
  ) as unknown as TemplateTwinGuardrailPolicy["metrics"],
};

const passingMetrics = Object.fromEntries(
  Object.entries(TEMPLATE_TWIN_METRIC_DEFINITIONS).map(([key, definition]) => [
    key,
    definition.direction === "MAX" ? definition.min : definition.max,
  ]),
) as Record<TemplateTwinMetricKey, number>;

interface ControlState {
  readonly enabled: boolean;
  readonly globalGeneration: bigint;
  readonly releaseStatus: string;
  readonly releaseGeneration: bigint;
}

interface ApprovedRelease {
  readonly releaseId: string;
  readonly identity: string;
  readonly evidence: TemplateTwinReleaseIdentityEvidence;
  readonly generation: string;
  readonly globalGeneration: string;
  readonly env: Readonly<Record<string, string | undefined>>;
}

function reviewerActor(
  discipline: TemplateTwinReleaseDiscipline,
): TemplateTwinReleaseActor {
  return {
    userId: reviewerIds.get(discipline)!,
    sessionId: reviewerSessions.get(discipline)!,
  };
}

function releaseEvidence(marker: string): TemplateTwinReleaseIdentityEvidence {
  return {
    sourceCommitSha: marker.repeat(40),
    baseCommitSha: "b".repeat(40),
    appImageDigest: `sha256:${"c".repeat(64)}`,
    workerImageDigest: `sha256:${"d".repeat(64)}`,
    migratorImageDigest: `sha256:${"e".repeat(64)}`,
    testCensusEvidenceSha256: "1".repeat(64),
    independentReviewEvidenceSha256: "2".repeat(64),
    securityEvidenceSha256: "3".repeat(64),
    migrationRestoreEvidenceSha256: "4".repeat(64),
    officeWordEvidenceSha256: "5".repeat(64),
  };
}

function runtimeEnv(
  evidence: TemplateTwinReleaseIdentityEvidence,
): Readonly<Record<string, string | undefined>> {
  return {
    TEMPLATE_TWIN_KILL_SWITCH: "false",
    TEMPLATE_TWIN_RUNTIME_MODE: "standard",
    TEMPLATE_TWIN_RELEASE_COMMIT_SHA: evidence.sourceCommitSha,
    TEMPLATE_TWIN_APP_IMAGE_DIGEST: evidence.appImageDigest,
    TEMPLATE_TWIN_WORKER_IMAGE_DIGEST: evidence.workerImageDigest,
    TEMPLATE_TWIN_MIGRATOR_IMAGE_DIGEST: evidence.migratorImageDigest,
  };
}

async function readGlobal(): Promise<{
  enabled: boolean;
  generation: bigint;
}> {
  const rows = await observer.$queryRaw<
    Array<{ enabled: boolean; generation: bigint }>
  >(Prisma.sql`
    SELECT "enabled", "generation"
    FROM "template_twin_rollout_controls"
    WHERE "id" = 'global'
  `);
  return rows[0]!;
}

async function readControlState(releaseId: string): Promise<ControlState> {
  const rows = await observer.$queryRaw<ControlState[]>(Prisma.sql`
    SELECT control."enabled", control."generation" AS "globalGeneration",
      candidate."status" AS "releaseStatus",
      candidate."generation" AS "releaseGeneration"
    FROM "template_twin_rollout_controls" control
    CROSS JOIN "template_twin_release_candidates" candidate
    WHERE control."id" = 'global' AND candidate."id" = ${releaseId}::UUID
  `);
  return rows[0]!;
}

async function expectRejected(
  label: string,
  operation: () => Promise<unknown>,
): Promise<string> {
  try {
    await operation();
  } catch (error) {
    return error instanceof Error ? error.message : String(error);
  }
  throw new Error(`${label} unexpectedly succeeded.`);
}

async function expectExactlyOneFulfilled(
  label: string,
  operations: readonly [Promise<unknown>, Promise<unknown>],
): Promise<readonly PromiseSettledResult<unknown>[]> {
  const results = await Promise.allSettled(operations);
  assert.equal(
    results.filter(({ status }) => status === "fulfilled").length,
    1,
    `${label} must have exactly one winner`,
  );
  return results;
}

async function seedSyntheticAuthorities(): Promise<void> {
  const expiresAt = new Date(Date.now() + 60 * 60 * 1000);
  await observer.practice.create({
    data: {
      id: administratorPracticeId,
      name: "Synthetic release administration",
      slug: administratorPracticeId,
      templateTwinEnabled: false,
    },
  });
  const practices = authorizedPracticeIds.map((practiceId, index) => ({
    id: practiceId,
    name: `Synthetic authorized practice ${index + 1}`,
    slug: practiceId,
    templateTwinEnabled: false,
  }));
  const physicians = authorizedPracticeIds.map((practiceId, index) => ({
    id: `synthetic-release-physician-${index + 1}-${suffix}`,
    email: `release-physician-${index + 1}-${suffix}@synthetic.test`,
    passwordHash: "synthetic-not-a-login-credential",
    role: "DOCTOR" as const,
    products: ["TRANSCRIBE_MD" as const],
    practiceId,
  }));
  for (let offset = 0; offset < authorizedPracticeIds.length; offset += 500) {
    await observer.practice.createMany({
      data: practices.slice(offset, offset + 500),
    });
    await observer.user.createMany({
      data: physicians.slice(offset, offset + 500),
    });
  }

  const administrators = [
    {
      id: creatorId,
      email: `release-creator-${suffix}@synthetic.test`,
      session: creatorSession,
    },
    ...TEMPLATE_TWIN_RELEASE_DISCIPLINES.map((discipline) => ({
      id: reviewerIds.get(discipline)!,
      email: `release-reviewer-${discipline.toLowerCase()}-${suffix}@synthetic.test`,
      session: reviewerSessions.get(discipline)!,
    })),
  ];
  for (const administrator of administrators) {
    await observer.user.create({
      data: {
        id: administrator.id,
        email: administrator.email,
        passwordHash: "synthetic-not-a-login-credential",
        role: "ADMIN",
        products: ["SUPER_ADMIN"],
        practiceId: administratorPracticeId,
        mfaEnabled: true,
        mfaVerifiedAt: new Date(),
      },
    });
    await observer.userSession.create({
      data: {
        userId: administrator.id,
        sessionToken: administrator.session,
        expiresAt,
      },
    });
  }

  for (const discipline of TEMPLATE_TWIN_RELEASE_DISCIPLINES) {
    await observer.$executeRaw(Prisma.sql`
      INSERT INTO "template_twin_release_authorities" (
        "id", "userId", "discipline", "sourceRef"
      ) VALUES (
        ${randomUUID()}::UUID, ${reviewerIds.get(discipline)!}, ${discipline},
        ${`synthetic-pg-test/${discipline.toLowerCase()}`}
      )
    `);
  }
  await observer.$executeRaw(Prisma.sql`
    UPDATE "template_twin_lineage_migration_progress"
    SET "phase" = 'CONTRACTED', "completedAt" = CURRENT_TIMESTAMP,
        "updatedAt" = CURRENT_TIMESTAMP
    WHERE "operationKey" = 'note_templates_lineage_v1'
  `);
}

async function createApprovedRelease(marker: string): Promise<ApprovedRelease> {
  const evidence = releaseEvidence(marker);
  const created = await createTemplateTwinReleaseCandidate({
    actor: creator,
    confirmation: "CREATE EXACT RELEASE",
    evidence,
    guardrailPolicy: policy,
    authorizedPracticeIds,
    canaryPracticeIds: [authorizedPracticeIds[0]!],
  });
  let generation = (
    await freezeTemplateTwinReleaseCandidate({
      actor: creator,
      releaseId: created.releaseId,
      expectedReleaseGeneration: created.generation,
      confirmation: `FREEZE ${created.releaseIdentitySha256.slice(0, 12)}`,
    })
  ).generation;

  for (const [
    index,
    discipline,
  ] of TEMPLATE_TWIN_RELEASE_DISCIPLINES.entries()) {
    const decision = await recordTemplateTwinReleaseApproval({
      actor: reviewerActor(discipline),
      releaseId: created.releaseId,
      expectedReleaseGeneration: generation,
      discipline,
      decision: "APPROVE",
      evidenceSha256: String(index + 6).repeat(64),
      confirmation: templateTwinApprovalConfirmation({
        decision: "APPROVE",
        discipline,
        releaseIdentitySha256: created.releaseIdentitySha256,
      }),
    });
    generation = decision.generation;
  }
  const global = await readGlobal();
  const state = await readControlState(created.releaseId);
  assert.equal(state.releaseStatus, "APPROVED");
  assert.equal(state.enabled, false);
  return {
    releaseId: created.releaseId,
    identity: created.releaseIdentitySha256,
    evidence,
    generation,
    globalGeneration: global.generation.toString(),
    env: runtimeEnv(evidence),
  };
}

function activation(release: ApprovedRelease, actor = creator) {
  return activateTemplateTwinReleaseCheckpoint({
    actor,
    releaseId: release.releaseId,
    stage: "CANARY",
    expectedReleaseGeneration: release.generation,
    expectedGlobalGeneration: release.globalGeneration,
    confirmation: templateTwinCheckpointConfirmation({
      verb: "ACTIVATE",
      stage: "CANARY",
      releaseIdentitySha256: release.identity,
    }),
    env: release.env,
  });
}

async function revokeCurrentRelease(
  release: ApprovedRelease,
  reasonCode: string,
): Promise<void> {
  const state = await readControlState(release.releaseId);
  await revokeTemplateTwinRelease({
    actor: creator,
    releaseId: release.releaseId,
    expectedReleaseGeneration: state.releaseGeneration.toString(),
    expectedGlobalGeneration: state.globalGeneration.toString(),
    reasonCode,
    confirmation: `REVOKE ${release.identity.slice(0, 12)}`,
  });
  const terminal = await readControlState(release.releaseId);
  assert.equal(terminal.releaseStatus, "REVOKED");
  assert.equal(terminal.enabled, false);
}

async function proveDirectSqlAndEvidenceGuards(
  release: ApprovedRelease,
): Promise<void> {
  const globalBefore = await readGlobal();
  await expectRejected("direct SQL global enable", () =>
    attacker.$executeRawUnsafe(
      `UPDATE "template_twin_rollout_controls"
       SET "enabled" = TRUE, "generation" = "generation" + 1
       WHERE "id" = 'global'`,
    ),
  );
  await expectRejected("forged local capability", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe(
        `SET LOCAL meddoc.template_twin_release_capability = '${randomUUID()}'`,
      );
      await tx.$executeRawUnsafe(
        `UPDATE "template_twin_rollout_controls"
         SET "enabled" = TRUE, "generation" = "generation" + 1
         WHERE "id" = 'global'`,
      );
    }),
  );
  assert.deepEqual(await readGlobal(), globalBefore);

  await expectRejected("release identity update", () =>
    attacker.$executeRaw(Prisma.sql`
      UPDATE "template_twin_release_candidates"
      SET "sourceCommitSha" = ${"f".repeat(40)}
      WHERE "id" = ${release.releaseId}::UUID
    `),
  );
  await expectRejected("approval update", () =>
    attacker.$executeRaw(Prisma.sql`
      UPDATE "template_twin_release_approval_decisions"
      SET "evidenceSha256" = ${syntheticSha}
      WHERE "releaseId" = ${release.releaseId}::UUID
    `),
  );
  await expectRejected("approval delete", () =>
    attacker.$executeRaw(Prisma.sql`
      DELETE FROM "template_twin_release_approval_decisions"
      WHERE "releaseId" = ${release.releaseId}::UUID
    `),
  );
  await expectRejected("authority revoke while release is live", () =>
    attacker.$executeRaw(Prisma.sql`
      UPDATE "template_twin_release_authorities"
      SET "revokedAt" = CURRENT_TIMESTAMP
      WHERE "userId" = ${reviewerIds.get("OPERATIONS")!}
        AND "discipline" = 'OPERATIONS'
        AND "revokedAt" IS NULL
    `),
  );
  await expectRejected("checkpoint skip", () =>
    attacker.$executeRaw(Prisma.sql`
      UPDATE "template_twin_release_checkpoints"
      SET "status" = 'PASSED'
      WHERE "releaseId" = ${release.releaseId}::UUID AND "ordinal" = 5
    `),
  );
  for (const table of [
    "template_twin_release_candidates",
    "template_twin_release_practices",
    "template_twin_release_approval_decisions",
    "template_twin_release_checkpoints",
    "template_twin_release_metric_snapshots",
    "template_twin_release_capabilities",
  ]) {
    await expectRejected(`truncate ${table}`, () =>
      attacker.$executeRawUnsafe(`TRUNCATE TABLE "${table}"`),
    );
  }
}

async function proveAdvanceRaceAndCapabilityReplay(): Promise<void> {
  const release = await createApprovedRelease("1");
  await proveDirectSqlAndEvidenceGuards(release);
  await expectExactlyOneFulfilled("advance/advance", [
    activation(release),
    activation(release),
  ]);
  const activated = await readControlState(release.releaseId);
  assert.equal(activated.releaseStatus, "ROLLING_OUT");
  assert.equal(activated.enabled, true);

  const capabilities = await observer.$queryRaw<
    Array<{ nonce: string; checkpointId: string; issuedAt: Date }>
  >(Prisma.sql`
    SELECT "nonce", "checkpointId", "issuedAt"
    FROM "template_twin_release_capabilities"
    WHERE "releaseId" = ${release.releaseId}::UUID
    ORDER BY "issuedAt" DESC
    LIMIT 1
  `);
  const capability = capabilities[0]!;
  await expectRejected("cross-transaction capability replay", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe(
        `SET LOCAL meddoc.template_twin_release_capability = '${capability.nonce}'`,
      );
      await tx.$executeRawUnsafe(
        `UPDATE "template_twin_rollout_controls"
         SET "generation" = "generation" + 1 WHERE "id" = 'global'`,
      );
    }),
  );
  await expectRejected("capability retarget", () =>
    attacker.$executeRaw(Prisma.sql`
      UPDATE "template_twin_release_capabilities"
      SET "transactionId" = txid_current()
      WHERE "nonce" = ${capability.nonce}::UUID
    `),
  );
  await expectRejected("capability delete", () =>
    attacker.$executeRaw(Prisma.sql`
      DELETE FROM "template_twin_release_capabilities"
      WHERE "nonce" = ${capability.nonce}::UUID
    `),
  );

  const checkpoint = await observer.$queryRaw<
    Array<{ activatedAt: Date }>
  >(Prisma.sql`
    SELECT "activatedAt" FROM "template_twin_release_checkpoints"
    WHERE "releaseId" = ${release.releaseId}::UUID AND "stage" = 'CANARY'
  `);
  const observationStartedAt = checkpoint[0]!.activatedAt;
  const observationEndedAt = new Date(observationStartedAt.getTime() + 1_000);
  const metric = await recordTemplateTwinReleaseMetricSnapshot({
    actor: creator,
    releaseId: release.releaseId,
    stage: "CANARY",
    expectedReleaseGeneration: activated.releaseGeneration.toString(),
    expectedGlobalGeneration: activated.globalGeneration.toString(),
    sampleCount: 1,
    observationStartedAt,
    observationEndedAt,
    metrics: passingMetrics,
    now: observationEndedAt,
  });
  assert.equal(metric.evaluation, "PASS");
  await expectRejected("metric update", () =>
    attacker.$executeRaw(Prisma.sql`
      UPDATE "template_twin_release_metric_snapshots"
      SET "sampleCount" = 2 WHERE "id" = ${metric.snapshotId}::UUID
    `),
  );
  await expectRejected("metric delete", () =>
    attacker.$executeRaw(Prisma.sql`
      DELETE FROM "template_twin_release_metric_snapshots"
      WHERE "id" = ${metric.snapshotId}::UUID
    `),
  );
  const passed = await passTemplateTwinReleaseCheckpoint({
    actor: creator,
    releaseId: release.releaseId,
    stage: "CANARY",
    expectedReleaseGeneration: metric.releaseGeneration,
    expectedGlobalGeneration: metric.globalGeneration,
    confirmation: templateTwinCheckpointConfirmation({
      verb: "PASS",
      stage: "CANARY",
      releaseIdentitySha256: release.identity,
    }),
    env: release.env,
    now: observationEndedAt,
  });
  assert.equal(passed.releaseStatus, "ROLLING_OUT");

  for (const stage of [
    "PERCENT_10",
    "PERCENT_25",
    "PERCENT_50",
    "PERCENT_100",
  ] as const) {
    const before = await readControlState(release.releaseId);
    await activateTemplateTwinReleaseCheckpoint({
      actor: creator,
      releaseId: release.releaseId,
      stage,
      expectedReleaseGeneration: before.releaseGeneration.toString(),
      expectedGlobalGeneration: before.globalGeneration.toString(),
      confirmation: templateTwinCheckpointConfirmation({
        verb: "ACTIVATE",
        stage,
        releaseIdentitySha256: release.identity,
      }),
      env: release.env,
    });
    const active = await readControlState(release.releaseId);
    const checkpointRows = await observer.$queryRaw<
      Array<{ activatedAt: Date }>
    >(Prisma.sql`
      SELECT "activatedAt" FROM "template_twin_release_checkpoints"
      WHERE "releaseId" = ${release.releaseId}::UUID AND "stage" = ${stage}
    `);
    const startedAt = checkpointRows[0]!.activatedAt;
    const endedAt = new Date(startedAt.getTime() + 1_000);
    const stageMetric = await recordTemplateTwinReleaseMetricSnapshot({
      actor: creator,
      releaseId: release.releaseId,
      stage,
      expectedReleaseGeneration: active.releaseGeneration.toString(),
      expectedGlobalGeneration: active.globalGeneration.toString(),
      sampleCount: 1,
      observationStartedAt: startedAt,
      observationEndedAt: endedAt,
      metrics: passingMetrics,
      now: endedAt,
    });
    assert.equal(stageMetric.evaluation, "PASS");
    await passTemplateTwinReleaseCheckpoint({
      actor: creator,
      releaseId: release.releaseId,
      stage,
      expectedReleaseGeneration: stageMetric.releaseGeneration,
      expectedGlobalGeneration: stageMetric.globalGeneration,
      confirmation: templateTwinCheckpointConfirmation({
        verb: "PASS",
        stage,
        releaseIdentitySha256: release.identity,
      }),
      env: release.env,
      now: endedAt,
    });
  }
  const stable = await readControlState(release.releaseId);
  assert.equal(stable.releaseStatus, "STABLE_100");
  assert.equal(stable.enabled, true);
  const exposure = await observer.$queryRaw<Array<{ count: bigint }>>(
    Prisma.sql`
      SELECT COUNT(*)::BIGINT AS "count" FROM "practices"
      WHERE "id" IN (${Prisma.join(authorizedPracticeIds)})
        AND "templateTwinEnabled" = TRUE
    `,
  );
  assert.equal(exposure[0]!.count, BigInt(authorizedPracticeIds.length));
  await revokeCurrentRelease(release, "SYNTHETIC_ADVANCE_RACE_COMPLETE");
}

async function proveGlobalKillRace(): Promise<void> {
  const release = await createApprovedRelease("2");
  const kill = setTemplateTwinGlobalRollout({
    enabled: false,
    actor: {
      userId: creatorId,
      userEmail: `release-creator-${suffix}@synthetic.test`,
      practiceId: administratorPracticeId,
    },
  });
  const results = await Promise.allSettled([activation(release), kill]);
  assert.equal(results[1]!.status, "fulfilled", "global kill must commit");
  const state = await readControlState(release.releaseId);
  assert.equal(state.enabled, false, "global kill/advance must end disabled");
  await revokeCurrentRelease(release, "SYNTHETIC_GLOBAL_KILL_RACE_COMPLETE");
}

async function proveApprovalRevokeRace(): Promise<void> {
  const release = await createApprovedRelease("3");
  const revokeDecision = recordTemplateTwinReleaseApproval({
    actor: reviewerActor("OPERATIONS"),
    releaseId: release.releaseId,
    expectedReleaseGeneration: release.generation,
    discipline: "OPERATIONS",
    decision: "REVOKE",
    evidenceSha256: "f".repeat(64),
    confirmation: templateTwinApprovalConfirmation({
      decision: "REVOKE",
      discipline: "OPERATIONS",
      releaseIdentitySha256: release.identity,
    }),
  });
  const results = await Promise.allSettled([
    activation(release),
    revokeDecision,
  ]);
  assert.equal(results[1]!.status, "fulfilled", "human revoke must commit");
  const state = await readControlState(release.releaseId);
  assert.equal(state.releaseStatus, "REJECTED");
  assert.equal(
    state.enabled,
    false,
    "approval revoke/advance must end disabled",
  );
}

async function proveOperationalRevokeRace(): Promise<void> {
  const release = await createApprovedRelease("4");
  const revoke = revokeTemplateTwinRelease({
    actor: creator,
    releaseId: release.releaseId,
    expectedReleaseGeneration: release.generation,
    expectedGlobalGeneration: release.globalGeneration,
    reasonCode: "SYNTHETIC_CONCURRENT_REVOKE",
    confirmation: `REVOKE ${release.identity.slice(0, 12)}`,
  });
  const results = await Promise.allSettled([activation(release), revoke]);
  assert.equal(
    results[1]!.status,
    "fulfilled",
    "operational revoke must commit",
  );
  const state = await readControlState(release.releaseId);
  assert.equal(state.releaseStatus, "REVOKED");
  assert.equal(state.enabled, false, "advance/revoke must end disabled");
}

async function proveCriticalGuardrailRevoke(): Promise<void> {
  const release = await createApprovedRelease("5");
  await activation(release);
  const active = await readControlState(release.releaseId);
  const checkpoint = await observer.$queryRaw<Array<{ activatedAt: Date }>>(
    Prisma.sql`
      SELECT "activatedAt" FROM "template_twin_release_checkpoints"
      WHERE "releaseId" = ${release.releaseId}::UUID AND "stage" = 'CANARY'
    `,
  );
  const observationStartedAt = checkpoint[0]!.activatedAt;
  const observationEndedAt = new Date(observationStartedAt.getTime() + 1_000);
  const criticalMetrics = {
    ...passingMetrics,
    critical_field_accuracy: 0,
  };
  const metric = await recordTemplateTwinReleaseMetricSnapshot({
    actor: creator,
    releaseId: release.releaseId,
    stage: "CANARY",
    expectedReleaseGeneration: active.releaseGeneration.toString(),
    expectedGlobalGeneration: active.globalGeneration.toString(),
    sampleCount: 1,
    observationStartedAt,
    observationEndedAt,
    metrics: criticalMetrics,
    now: observationEndedAt,
  });
  assert.equal(metric.evaluation, "CRITICAL_REVOKE");
  const revoked = await readControlState(release.releaseId);
  assert.equal(revoked.releaseStatus, "REVOKED");
  assert.equal(revoked.enabled, false);
}

async function proveCriticalGuardrailPassRace(): Promise<void> {
  const release = await createApprovedRelease("6");
  await activation(release);
  const active = await readControlState(release.releaseId);
  const checkpoint = await observer.$queryRaw<Array<{ activatedAt: Date }>>(
    Prisma.sql`
      SELECT "activatedAt" FROM "template_twin_release_checkpoints"
      WHERE "releaseId" = ${release.releaseId}::UUID AND "stage" = 'CANARY'
    `,
  );
  const observationStartedAt = checkpoint[0]!.activatedAt;
  const observationEndedAt = new Date(observationStartedAt.getTime() + 1_000);
  const passing = await recordTemplateTwinReleaseMetricSnapshot({
    actor: creator,
    releaseId: release.releaseId,
    stage: "CANARY",
    expectedReleaseGeneration: active.releaseGeneration.toString(),
    expectedGlobalGeneration: active.globalGeneration.toString(),
    sampleCount: 1,
    observationStartedAt,
    observationEndedAt,
    metrics: passingMetrics,
    now: observationEndedAt,
  });
  assert.equal(passing.evaluation, "PASS");

  const pass = passTemplateTwinReleaseCheckpoint({
    actor: creator,
    releaseId: release.releaseId,
    stage: "CANARY",
    expectedReleaseGeneration: passing.releaseGeneration,
    expectedGlobalGeneration: passing.globalGeneration,
    confirmation: templateTwinCheckpointConfirmation({
      verb: "PASS",
      stage: "CANARY",
      releaseIdentitySha256: release.identity,
    }),
    env: release.env,
    now: observationEndedAt,
  });
  const critical = recordTemplateTwinReleaseMetricSnapshot({
    actor: creator,
    releaseId: release.releaseId,
    stage: "CANARY",
    expectedReleaseGeneration: passing.releaseGeneration,
    expectedGlobalGeneration: passing.globalGeneration,
    sampleCount: 1,
    observationStartedAt,
    observationEndedAt,
    metrics: { ...passingMetrics, critical_field_accuracy: 0 },
    now: observationEndedAt,
  });
  const results = await Promise.allSettled([pass, critical]);
  assert.equal(
    results[1]!.status,
    "fulfilled",
    "critical guardrail must commit across a concurrent checkpoint pass",
  );
  const revoked = await readControlState(release.releaseId);
  assert.equal(revoked.releaseStatus, "REVOKED");
  assert.equal(
    revoked.enabled,
    false,
    "critical guardrail/pass race must end disabled",
  );
}

async function assertAuditCensus(): Promise<number> {
  const rows = await observer.$queryRaw<
    Array<{ count: bigint; distinctCount: bigint; pendingCount: bigint }>
  >(Prisma.sql`
    SELECT COUNT(*)::BIGINT AS "count",
      COUNT(DISTINCT "eventKey")::BIGINT AS "distinctCount",
      COUNT(*) FILTER (WHERE "status" = 'PENDING')::BIGINT AS "pendingCount"
    FROM "template_twin_audit_outbox"
    WHERE "eventKey" LIKE 'template-twin:release:%'
  `);
  const row = rows[0]!;
  assert.equal(
    row.count,
    row.distinctCount,
    "release event keys must be unique",
  );
  assert.equal(
    row.count,
    row.pendingCount,
    "undrained synthetic events stay pending",
  );
  assert(row.count >= BigInt(46), "expected complete release audit evidence");
  return Number(row.count);
}

async function proveTerminalAuthorityRevocation(): Promise<void> {
  const updated = await observer.$executeRaw(Prisma.sql`
    UPDATE "template_twin_release_authorities"
    SET "revokedAt" = CURRENT_TIMESTAMP
    WHERE "userId" = ${reviewerIds.get("OPERATIONS")!}
      AND "discipline" = 'OPERATIONS'
      AND "revokedAt" IS NULL
  `);
  assert.equal(updated, 1, "terminal authority revocation must be retained");
  await expectRejected("authority revocation replay", () =>
    attacker.$executeRaw(Prisma.sql`
      UPDATE "template_twin_release_authorities"
      SET "revokedAt" = CURRENT_TIMESTAMP
      WHERE "userId" = ${reviewerIds.get("OPERATIONS")!}
        AND "discipline" = 'OPERATIONS'
    `),
  );
}

async function main(): Promise<void> {
  await seedSyntheticAuthorities();
  await proveAdvanceRaceAndCapabilityReplay();
  await proveGlobalKillRace();
  await proveApprovalRevokeRace();
  await proveOperationalRevokeRace();
  await proveCriticalGuardrailRevoke();
  await proveCriticalGuardrailPassRace();
  await proveTerminalAuthorityRevocation();
  const releaseAuditEventCount = await assertAuditCensus();
  const global = await readGlobal();
  assert.equal(global.enabled, false);

  process.stdout.write(
    `${JSON.stringify({
      profile: "template-twin-production-release-control-postgres-v1",
      synthetic: true,
      databaseGuard: "passed",
      migrations: "fresh-deploy-required",
      directSqlEnableRejected: true,
      forgedCapabilityRejected: true,
      capabilityReplayRejected: true,
      capabilityReceiptsImmutable: true,
      releaseEvidenceImmutable: true,
      races: {
        advanceAdvance: "exactly-one-winner",
        globalKillAdvance: "disabled",
        approvalRevokeAdvance: "rejected-and-disabled",
        operationalRevokeAdvance: "revoked-and-disabled",
        criticalGuardrailPass: "revoked-and-disabled",
      },
      criticalGuardrail: "atomic-revoke-and-disable",
      scalePracticeCount,
      releaseAuditEventCount,
      finalGlobalEnabled: global.enabled,
      fixtureLifecycle: "disposable-database-only",
    })}\n`,
  );
}

void main()
  .catch((error: unknown) => {
    process.stderr.write(
      `${error instanceof Error ? (error.stack ?? error.message) : String(error)}\n`,
    );
    process.exitCode = 1;
  })
  .finally(async () => {
    await Promise.all([observer.$disconnect(), attacker.$disconnect()]);
  });
