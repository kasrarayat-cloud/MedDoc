#!/usr/bin/env tsx

// Actual-PostgreSQL proof for the Template Twin production control plane.
// The target must be a disposable database. The script exercises production
// service functions, independent database sessions, database-native
// capability enforcement, monotonic safety actions, immutable evidence, and
// all four release/enable race classes. Synthetic operational identities only;
// no clinical or patient content is created.

import assert from "node:assert/strict";
import { createHmac, randomBytes, randomUUID } from "node:crypto";

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
  type TemplateTwinReleaseStage,
  type TemplateTwinRuntimeComponent,
} from "../../../apps/transcribe-md/src/lib/template-twin/release-control-contracts";
import { setTemplateTwinGlobalRollout } from "../../../apps/transcribe-md/src/lib/template-twin/rollout";
import { drainTemplateTwinAuditOutbox } from "../../../apps/transcribe-md/src/lib/template-twin/audit-outbox";
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
const runtimeKeyId = `synthetic-runtime-${suffix}`;
const metricKeyId = `synthetic-metrics-${suffix}`;
const runtimeSigningSecret = randomBytes(32);
const metricSigningSecret = randomBytes(32);
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

function client(applicationName: string, assumedRole?: string): PrismaClient {
  const url = new URL(disposableDatabaseUrl);
  url.searchParams.set("application_name", applicationName);
  if (assumedRole) {
    url.searchParams.set("options", `-c role=${assumedRole}`);
  }
  return new PrismaClient({
    adapter: new PrismaPg({ connectionString: url.toString() }),
  });
}

const observer = client("template-twin-release-control-observer");
const attacker = client("template-twin-release-control-direct-sql");
const auditDispatcher = client(
  "template-twin-release-control-audit-dispatcher",
  "quillmd_audit_dispatcher",
);

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
    String(definition.direction === "MAX" ? definition.min : definition.max),
  ]),
) as Record<TemplateTwinMetricKey, string>;

let unconfiguredRuntimeEnv:
  | Readonly<Record<string, string | undefined>>
  | undefined;

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
  readonly appInstanceId: string;
  readonly workerInstanceId: string;
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

function runtimeEnv(input: {
  readonly evidence: TemplateTwinReleaseIdentityEvidence;
  readonly releaseIdentitySha256: string;
  readonly instanceId: string;
  readonly component: TemplateTwinRuntimeComponent;
  readonly leaseSeconds?: number;
}): Readonly<Record<string, string | undefined>> {
  const issuedAtEpochSeconds = Math.floor(Date.now() / 1_000) - 1;
  const expiresAtEpochSeconds =
    issuedAtEpochSeconds + (input.leaseSeconds ?? 3_600);
  const imageDigest =
    input.component === "APP"
      ? input.evidence.appImageDigest
      : input.evidence.workerImageDigest;
  const nonce = randomUUID();
  const message = [
    "template-twin-runtime-attestation-v1",
    runtimeKeyId,
    nonce,
    input.releaseIdentitySha256,
    input.instanceId,
    input.component,
    input.evidence.sourceCommitSha,
    imageDigest,
    String(issuedAtEpochSeconds),
    String(expiresAtEpochSeconds),
  ].join("\n");
  const envelope = {
    version: "template-twin-runtime-attestation-v1",
    keyId: runtimeKeyId,
    nonce,
    releaseIdentitySha256: input.releaseIdentitySha256,
    instanceId: input.instanceId,
    component: input.component,
    sourceCommitSha: input.evidence.sourceCommitSha,
    imageDigest,
    issuedAtEpochSeconds,
    expiresAtEpochSeconds,
    signature: createHmac("sha256", runtimeSigningSecret)
      .update(message)
      .digest("hex"),
  };
  return {
    TEMPLATE_TWIN_KILL_SWITCH: "false",
    TEMPLATE_TWIN_RUNTIME_MODE: "standard",
    TEMPLATE_TWIN_RELEASE_COMMIT_SHA: input.evidence.sourceCommitSha,
    TEMPLATE_TWIN_APP_IMAGE_DIGEST: input.evidence.appImageDigest,
    TEMPLATE_TWIN_WORKER_IMAGE_DIGEST: input.evidence.workerImageDigest,
    TEMPLATE_TWIN_MIGRATOR_IMAGE_DIGEST: input.evidence.migratorImageDigest,
    QUILLMD_IMAGE_REVISION: input.evidence.sourceCommitSha,
    QUILLMD_RUNTIME_COMPONENT: input.component,
    TEMPLATE_TWIN_RUNTIME_ATTESTATION: Buffer.from(
      JSON.stringify(envelope),
      "utf8",
    ).toString("base64url"),
  };
}

interface RuntimeEnvelope {
  readonly version: string;
  readonly keyId: string;
  readonly nonce: string;
  readonly releaseIdentitySha256: string;
  readonly instanceId: string;
  readonly component: string;
  readonly sourceCommitSha: string;
  readonly imageDigest: string;
  readonly issuedAtEpochSeconds: number;
  readonly expiresAtEpochSeconds: number;
  readonly signature: string;
}

function decodeRuntimeEnvelope(
  env: Readonly<Record<string, string | undefined>>,
): RuntimeEnvelope {
  const encoded = env.TEMPLATE_TWIN_RUNTIME_ATTESTATION;
  assert(encoded, "runtime attestation envelope must be present");
  return JSON.parse(
    Buffer.from(encoded, "base64url").toString("utf8"),
  ) as RuntimeEnvelope;
}

function replaceRuntimeEnvelope(
  env: Readonly<Record<string, string | undefined>>,
  envelope: RuntimeEnvelope,
): Readonly<Record<string, string | undefined>> {
  return {
    ...env,
    TEMPLATE_TWIN_RUNTIME_ATTESTATION: Buffer.from(
      JSON.stringify(envelope),
      "utf8",
    ).toString("base64url"),
  };
}

async function submitRuntimeEnvelope(
  env: Readonly<Record<string, string | undefined>>,
): Promise<string | null> {
  const envelope = decodeRuntimeEnvelope(env);
  return observer.$transaction(async (tx) => {
    await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_runtime");
    const rows = await tx.$queryRaw<Array<{ receiptId: string | null }>>(
      Prisma.sql`
      SELECT template_twin_register_runtime_attestation(
        ${envelope.version}, ${envelope.keyId}, ${envelope.nonce}::UUID,
        ${envelope.releaseIdentitySha256}::CHAR(64), ${envelope.instanceId},
        ${envelope.component}, ${envelope.sourceCommitSha}::CHAR(40),
        ${envelope.imageDigest}, ${envelope.issuedAtEpochSeconds}::BIGINT,
        ${envelope.expiresAtEpochSeconds}::BIGINT,
        ${envelope.signature}::CHAR(64)
      ) AS "receiptId"
    `,
    );
    assert.equal(rows.length, 1);
    return rows[0]!.receiptId;
  });
}

async function registerRuntimeEnvelope(
  env: Readonly<Record<string, string | undefined>>,
): Promise<void> {
  assert(await submitRuntimeEnvelope(env), "runtime receipt must be admitted");
}

function metricAttestation(input: {
  readonly releaseId: string;
  readonly stage: TemplateTwinReleaseStage;
  readonly expectedReleaseGeneration: string;
  readonly expectedGlobalGeneration: string;
  readonly sampleCount: number;
  readonly observationStartedAt: Date;
  readonly observationEndedAt: Date;
  readonly metrics: Readonly<Record<string, string>>;
}) {
  const nonce = randomUUID();
  const issuedAtEpochSeconds = Math.floor(Date.now() / 1_000);
  const metricLines = Object.entries(input.metrics)
    .sort(([left], [right]) => (left < right ? -1 : left > right ? 1 : 0))
    .map(([key, value]) => `${key}=${value}`)
    .join("\n");
  const message = [
    "template-twin-metric-attestation-v1",
    metricKeyId,
    nonce,
    input.releaseId,
    input.stage,
    input.expectedReleaseGeneration,
    input.expectedGlobalGeneration,
    String(input.sampleCount),
    String(input.observationStartedAt.getTime()),
    String(input.observationEndedAt.getTime()),
    String(issuedAtEpochSeconds),
    metricLines,
  ].join("\n");
  return {
    version: "template-twin-metric-attestation-v1" as const,
    keyId: metricKeyId,
    nonce,
    issuedAtEpochSeconds,
    signature: createHmac("sha256", metricSigningSecret)
      .update(message)
      .digest("hex"),
  };
}

async function waitForObservationWindow(activatedAt: Date): Promise<Date> {
  const remaining = activatedAt.getTime() + 1_050 - Date.now();
  if (remaining > 0) {
    await new Promise<void>((resolve) => setTimeout(resolve, remaining));
  }
  return new Date();
}

function monitoringObservationStart(activatedAt: Date): Date {
  // PostgreSQL preserves microseconds while JavaScript Date preserves
  // milliseconds. Start the synthetic observation strictly after the
  // round-tripped activation timestamp so the database comparison remains
  // true for every sub-millisecond activation value.
  return new Date(activatedAt.getTime() + 1);
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
  const rejectionDiagnostics = results
    .filter(
      (result): result is PromiseRejectedResult => result.status === "rejected",
    )
    .map(({ reason }) =>
      reason instanceof Error ? (reason.stack ?? reason.message) : String(reason),
    );
  assert.equal(
    results.filter(({ status }) => status === "fulfilled").length,
    1,
    `${label} must have exactly one winner; rejections=${JSON.stringify(rejectionDiagnostics)}`,
  );
  return results;
}

async function proveDatabaseRoleBoundaries(): Promise<void> {
  const roleAttributes = await attacker.$queryRaw<
    Array<{
      rolname: string;
      rolsuper: boolean;
      rolcreatedb: boolean;
      rolcreaterole: boolean;
      rolcanlogin: boolean;
      rolinherit: boolean;
      rolbypassrls: boolean;
    }>
  >(Prisma.sql`
    SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolcanlogin,
      rolinherit, rolbypassrls
    FROM pg_roles
    WHERE rolname IN (
      'quillmd_runtime', 'quillmd_release_control',
      'quillmd_release_security', 'quillmd_audit_dispatcher'
    )
    ORDER BY rolname
  `);
  assert.equal(roleAttributes.length, 4);
  for (const role of roleAttributes) {
    assert.equal(role.rolsuper, false, `${role.rolname} must not be superuser`);
    assert.equal(role.rolcreatedb, false, `${role.rolname} must not create DBs`);
    assert.equal(
      role.rolcreaterole,
      false,
      `${role.rolname} must not create roles`,
    );
    assert.equal(role.rolcanlogin, false, `${role.rolname} must be NOLOGIN`);
    assert.equal(role.rolinherit, false, `${role.rolname} must be NOINHERIT`);
    assert.equal(
      role.rolbypassrls,
      false,
      `${role.rolname} must not bypass RLS`,
    );
  }
  const loginAttributes = await attacker.$queryRaw<
    Array<{
      rolname: string;
      rolsuper: boolean;
      rolcreatedb: boolean;
      rolcreaterole: boolean;
      rolcanlogin: boolean;
      rolinherit: boolean;
      rolreplication: boolean;
      rolbypassrls: boolean;
    }>
  >(Prisma.sql`
    SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolcanlogin,
      rolinherit, rolreplication, rolbypassrls
    FROM pg_roles
    WHERE rolname IN (
      'meddoc_runtime', 'meddoc_release_control', 'meddoc_release_security',
      'meddoc_audit_dispatcher'
    )
    ORDER BY rolname
  `);
  assert.equal(loginAttributes.length, 4);
  for (const role of loginAttributes) {
    assert.equal(role.rolsuper, false, `${role.rolname} must not be superuser`);
    assert.equal(
      role.rolcreatedb,
      false,
      `${role.rolname} must not create DBs`,
    );
    assert.equal(
      role.rolcreaterole,
      false,
      `${role.rolname} must not create roles`,
    );
    assert.equal(role.rolcanlogin, true, `${role.rolname} must be LOGIN`);
    assert.equal(role.rolinherit, true, `${role.rolname} must inherit one role`);
    assert.equal(
      role.rolreplication,
      false,
      `${role.rolname} must not replicate`,
    );
    assert.equal(
      role.rolbypassrls,
      false,
      `${role.rolname} must not bypass RLS`,
    );
  }
  const loginMemberships = await attacker.$queryRaw<
    Array<{ loginRole: string; boundaryRole: string }>
  >(Prisma.sql`
    SELECT member.rolname AS "loginRole", granted.rolname AS "boundaryRole"
    FROM pg_auth_members membership
    JOIN pg_roles member ON member.oid = membership.member
    JOIN pg_roles granted ON granted.oid = membership.roleid
    WHERE member.rolname IN (
      'meddoc_runtime', 'meddoc_release_control', 'meddoc_release_security',
      'meddoc_audit_dispatcher'
    )
    ORDER BY member.rolname, granted.rolname
  `);
  assert.deepEqual(loginMemberships, [
    {
      loginRole: "meddoc_audit_dispatcher",
      boundaryRole: "quillmd_audit_dispatcher",
    },
    {
      loginRole: "meddoc_release_control",
      boundaryRole: "quillmd_release_control",
    },
    {
      loginRole: "meddoc_release_security",
      boundaryRole: "quillmd_release_security",
    },
    { loginRole: "meddoc_runtime", boundaryRole: "quillmd_runtime" },
  ]);
  const authorityProcedurePrivileges = await attacker.$queryRaw<
    Array<{ controlAllowed: boolean; securityAllowed: boolean }>
  >(Prisma.sql`
    SELECT has_function_privilege(
      'meddoc_release_control',
      'template_twin_revoke_release_authority(uuid,text,text,text,text)',
      'EXECUTE'
    ) AS "controlAllowed",
    has_function_privilege(
      'meddoc_release_security',
      'template_twin_revoke_release_authority(uuid,text,text,text,text)',
      'EXECUTE'
    ) AS "securityAllowed"
  `);
  assert.equal(authorityProcedurePrivileges[0]!.controlAllowed, false);
  assert.equal(authorityProcedurePrivileges[0]!.securityAllowed, true);
  const forbiddenMembership = await attacker.$queryRaw<
    Array<{ count: bigint }>
  >(Prisma.sql`
    SELECT COUNT(*)::BIGINT AS "count"
    FROM pg_auth_members membership
    JOIN pg_roles granted ON granted.oid = membership.roleid
    JOIN pg_roles member ON member.oid = membership.member
    WHERE granted.rolname = 'quillmd_runtime'
      AND member.rolname = 'quillmd_release_control'
  `);
  assert.equal(forbiddenMembership[0]!.count, BigInt(0));
  const unsafeDefiners = await attacker.$queryRaw<Array<{ count: bigint }>>(
    Prisma.sql`
      SELECT COUNT(*)::BIGINT AS "count"
      FROM pg_proc procedure
      JOIN pg_namespace namespace ON namespace.oid = procedure.pronamespace
      WHERE namespace.nspname = 'public'
        AND procedure.proname LIKE 'template_twin_%'
        AND procedure.prokind = 'f'
        AND NOT (
          COALESCE(procedure.proconfig, ARRAY[]::TEXT[])
            @> ARRAY['search_path=pg_catalog, public, pg_temp']::TEXT[]
        )
    `,
  );
  assert.equal(
    unsafeDefiners[0]!.count,
    BigInt(0),
    "every Template Twin guard must resolve caller temp schemas last",
  );
  const runtimeCanCreatePublic = await attacker.$queryRaw<
    Array<{ allowed: boolean }>
  >(Prisma.sql`
    SELECT has_schema_privilege(
      'quillmd_runtime', 'public', 'CREATE'
    ) AS "allowed"
  `);
  assert.equal(runtimeCanCreatePublic[0]!.allowed, false);

  await expectRejected("runtime direct global mutation", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_runtime");
      await tx.$executeRawUnsafe(
        `UPDATE "template_twin_rollout_controls"
         SET "enabled" = TRUE, "generation" = "generation" + 1
         WHERE "id" = 'global'`,
      );
    }),
  );
  await expectRejected("runtime direct practice exposure mutation", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_runtime");
      await tx.$executeRaw(Prisma.sql`
        UPDATE "practices" SET "templateTwinEnabled" = TRUE
        WHERE "id" = ${administratorPracticeId}
      `);
    }),
  );
  await expectRejected("runtime direct release evidence mutation", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_runtime");
      await tx.$executeRawUnsafe(
        `DELETE FROM "template_twin_release_candidates" WHERE FALSE`,
      );
    }),
  );
  await expectRejected("runtime audit delivery mutation", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_runtime");
      await tx.$executeRawUnsafe(
        `UPDATE "template_twin_audit_outbox" SET "attemptCount" = "attemptCount" WHERE FALSE`,
      );
    }),
  );
  await expectRejected("runtime attestation secret read", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_runtime");
      await tx.$queryRawUnsafe(
        `SELECT "secret" FROM "template_twin_release_attestation_keys" LIMIT 1`,
      );
    }),
  );
  await expectRejected("release-control attestation secret read", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_release_control");
      await tx.$queryRawUnsafe(
        `SELECT "secret" FROM "template_twin_release_attestation_keys" LIMIT 1`,
      );
    }),
  );
  await expectRejected("release-control session token read", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_release_control");
      await tx.$queryRawUnsafe(
        `SELECT "sessionToken" FROM "user_sessions" LIMIT 1`,
      );
    }),
  );
  await expectRejected("release-control session mutation", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_release_control");
      await tx.$executeRawUnsafe(
        `UPDATE "user_sessions" SET "lastActiveAt" = "lastActiveAt" WHERE FALSE`,
      );
    }),
  );
  await attacker.$transaction(async (tx) => {
    await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_release_control");
    const rows = await tx.$queryRaw<Array<{ userId: string }>>(Prisma.sql`
      SELECT "userId" FROM template_twin_verify_release_admin_session(
        ${creatorId}, ${creatorSession}
      )
    `);
    assert.deepEqual(rows, [{ userId: creatorId }]);
    const mismatch = await tx.$queryRaw<Array<{ userId: string }>>(Prisma.sql`
      SELECT "userId" FROM template_twin_verify_release_admin_session(
        ${creatorId}, ${`${creatorSession}-wrong`}
      )
    `);
    assert.equal(mismatch.length, 0);
  });
  await expectRejected("release-control audit outbox read", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_release_control");
      await tx.$queryRawUnsafe(
        `SELECT "metadata" FROM "template_twin_audit_outbox" LIMIT 1`,
      );
    }),
  );
  await expectRejected("release-control action receipt injection", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_release_control");
      await tx.$executeRaw(Prisma.sql`
        INSERT INTO "template_twin_release_action_receipts" (
          "nonce", "transactionId", "backendPid", "releaseId", "action",
          "actorId", "actorSessionSha256", "confirmationSha256",
          "issuedAt", "expiresAt"
        ) VALUES (
          ${randomUUID()}::UUID, txid_current(), pg_backend_pid(),
          ${randomUUID()}::UUID, 'FREEZE', ${creatorId}, ${syntheticSha},
          ${syntheticSha}, CURRENT_TIMESTAMP,
          CURRENT_TIMESTAMP + INTERVAL '1 minute'
        )
      `);
    }),
  );
  await expectRejected("release-control coupling receipt read", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_release_control");
      await tx.$queryRawUnsafe(
        `SELECT * FROM "template_twin_release_coupling_receipts" LIMIT 1`,
      );
    }),
  );
  await expectRejected("audit dispatcher release evidence read", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_audit_dispatcher");
      await tx.$queryRawUnsafe(
        `SELECT * FROM "template_twin_release_candidates" LIMIT 1`,
      );
    }),
  );
  await expectRejected("audit dispatcher global mutation", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_audit_dispatcher");
      await tx.$executeRawUnsafe(
        `UPDATE "template_twin_rollout_controls" SET "enabled" = FALSE WHERE FALSE`,
      );
    }),
  );
  await expectRejected("release-control authority mutation", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_release_control");
      await tx.$executeRawUnsafe(
        `DELETE FROM "template_twin_release_authorities" WHERE FALSE`,
      );
    }),
  );
  await expectRejected("release-control release-history delete", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_release_control");
      await tx.$executeRawUnsafe(
        `DELETE FROM "template_twin_release_candidates" WHERE FALSE`,
      );
    }),
  );
  await expectRejected("runtime human-approval state probe", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_runtime");
      await tx.$queryRawUnsafe(
        `SELECT template_twin_release_approvals_are_current(gen_random_uuid(), repeat('0', 64)::CHAR(64))`,
      );
    }),
  );
  for (const [label, table] of [
    ["human authority", "template_twin_release_authorities"],
    ["metric evidence", "template_twin_release_metric_snapshots"],
    ["capability evidence", "template_twin_release_capabilities"],
  ] as const) {
    await expectRejected(`runtime raw ${label} read`, () =>
      attacker.$transaction(async (tx) => {
        await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_runtime");
        await tx.$queryRawUnsafe(`SELECT * FROM "${table}" LIMIT 1`);
      }),
    );
  }
  await attacker.$transaction(async (tx) => {
    await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_runtime");
    const rows = await tx.$queryRaw<Array<{ count: bigint }>>(Prisma.sql`
      SELECT COUNT(*)::BIGINT AS "count"
      FROM template_twin_current_runtime_release()
    `);
    assert.equal(rows[0]!.count, BigInt(0));
  });
  await expectRejected("attestation key material mutation", () =>
    attacker.$executeRaw(Prisma.sql`
      UPDATE "template_twin_release_attestation_keys"
      SET "expiresAt" = "expiresAt" + INTERVAL '1 minute'
      WHERE "keyId" = ${runtimeKeyId}
    `),
  );
  await expectRejected("attestation key deletion", () =>
    attacker.$executeRaw(Prisma.sql`
      DELETE FROM "template_twin_release_attestation_keys"
      WHERE "keyId" = ${runtimeKeyId}
    `),
  );
  await expectRejected("attestation key truncation", () =>
    attacker.$executeRawUnsafe(
      `TRUNCATE TABLE "template_twin_release_attestation_keys"`,
    ),
  );
}

async function proveUnconfiguredRuntimeAttestation(): Promise<void> {
  unconfiguredRuntimeEnv = runtimeEnv({
    evidence: releaseEvidence("9"),
    releaseIdentitySha256: "9".repeat(64),
    instanceId: `missing-app-${suffix}`,
    component: "APP",
  });
  assert.equal(
    await submitRuntimeEnvelope(unconfiguredRuntimeEnv),
    null,
    "a valid signed image absent from every eligible manifest is not configured",
  );
  const envelope = decodeRuntimeEnvelope(unconfiguredRuntimeEnv);
  await expectRejected("invalid signature is checked before manifest absence", () =>
    submitRuntimeEnvelope(
      replaceRuntimeEnvelope(unconfiguredRuntimeEnv!, {
        ...envelope,
        signature: "0".repeat(64),
      }),
    ),
  );
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

  const effectiveAt = new Date(Date.now() - 60_000);
  const attestationExpiresAt = new Date(Date.now() + 2 * 60 * 60 * 1_000);
  await observer.$executeRaw(Prisma.sql`
    INSERT INTO "template_twin_release_attestation_keys" (
      "keyId", "purpose", "secret", "principalUserId",
      "effectiveAt", "expiresAt"
    ) VALUES
      (${runtimeKeyId}, 'RUNTIME', ${runtimeSigningSecret}, NULL,
       ${effectiveAt}, ${attestationExpiresAt}),
      (${metricKeyId}, 'METRICS', ${metricSigningSecret}, ${creatorId},
       ${effectiveAt}, ${attestationExpiresAt})
  `);

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
      AND "phase" <> 'CONTRACTED'
  `);
}

async function createApprovedRelease(marker: string): Promise<ApprovedRelease> {
  const evidence = releaseEvidence(marker);
  const appInstanceId = `app-${marker}-${suffix}`;
  const workerInstanceId = `worker-${marker}-${suffix}`;
  process.stderr.write(`[template-twin-control-plane] release-${marker}:create\n`);
  const created = await createTemplateTwinReleaseCandidate({
    actor: creator,
    confirmation: "CREATE EXACT RELEASE",
    evidence,
    guardrailPolicy: policy,
    authorizedPracticeIds,
    canaryPracticeIds: [authorizedPracticeIds[0]!],
    runtimeInstances: [
      {
        instanceId: appInstanceId,
        component: "APP",
        imageDigest: evidence.appImageDigest,
      },
      {
        instanceId: workerInstanceId,
        component: "WORKER",
        imageDigest: evidence.workerImageDigest,
      },
    ],
  });
  process.stderr.write(`[template-twin-control-plane] release-${marker}:freeze\n`);
  let generation = (
    await freezeTemplateTwinReleaseCandidate({
      actor: creator,
      releaseId: created.releaseId,
      expectedReleaseGeneration: created.generation,
      confirmation: `FREEZE ${created.releaseIdentitySha256.slice(0, 12)}`,
    })
  ).generation;
  if (marker === "1") {
    await expectRejected("post-freeze runtime-manifest append", () =>
      attacker.$transaction(async (tx) => {
        await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_release_control");
        await tx.$executeRaw(Prisma.sql`
          INSERT INTO "template_twin_release_runtime_requirements" (
            "id", "releaseId", "releaseIdentitySha256", "instanceId",
            "component", "sourceCommitSha", "imageDigest"
          ) VALUES (
            ${randomUUID()}::UUID, ${created.releaseId}::UUID,
            ${created.releaseIdentitySha256}, ${`late-app-${suffix}`}, 'APP',
            ${evidence.sourceCommitSha}, ${evidence.appImageDigest}
          )
        `);
      }),
    );
  }

  for (const [
    index,
    discipline,
  ] of TEMPLATE_TWIN_RELEASE_DISCIPLINES.entries()) {
    process.stderr.write(
      `[template-twin-control-plane] release-${marker}:approve-${discipline}\n`,
    );
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
  const env = runtimeEnv({
    evidence,
    releaseIdentitySha256: created.releaseIdentitySha256,
    instanceId: appInstanceId,
    component: "APP",
  });
  const workerEnv = runtimeEnv({
    evidence,
    releaseIdentitySha256: created.releaseIdentitySha256,
    instanceId: workerInstanceId,
    component: "WORKER",
  });
  const approvedRelease: ApprovedRelease = {
    releaseId: created.releaseId,
    identity: created.releaseIdentitySha256,
    evidence,
    generation,
    globalGeneration: global.generation.toString(),
    env,
    appInstanceId,
    workerInstanceId,
  };
  await registerRuntimeEnvelope(env);
  if (marker === "1") {
    const message = await expectRejected("missing worker replica", () =>
      activation(approvedRelease),
    );
    assert.match(message, /pinned application and worker replica|runtime/u);
  }
  await registerRuntimeEnvelope(workerEnv);
  return approvedRelease;
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

type UnsignedMetricSnapshot = Omit<
  Parameters<typeof recordTemplateTwinReleaseMetricSnapshot>[0],
  "attestation"
>;

async function recordSignedMetricSnapshot(input: UnsignedMetricSnapshot) {
  return recordTemplateTwinReleaseMetricSnapshot({
    ...input,
    attestation: metricAttestation(input),
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
  await expectRejected("release policy digest update", () =>
    attacker.$executeRaw(Prisma.sql`
      UPDATE "template_twin_release_candidates"
      SET "guardrailPolicySha256" = ${"e".repeat(64)}
      WHERE "id" = ${release.releaseId}::UUID
    `),
  );
  await expectRejected("release cohort assignment update", () =>
    attacker.$executeRaw(Prisma.sql`
      UPDATE "template_twin_release_practices"
      SET "activationStage" = 'PERCENT_100',
          "activationStageOrdinal" = 5
      WHERE "releaseId" = ${release.releaseId}::UUID
        AND "cohortRank" = 1
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
  const operationAuthority = await observer.$queryRaw<Array<{ id: string }>>(
    Prisma.sql`
      SELECT "id" FROM "template_twin_release_authorities"
      WHERE "userId" = ${reviewerIds.get("OPERATIONS")!}
        AND "discipline" = 'OPERATIONS' AND "revokedAt" IS NULL
    `,
  );
  await expectRejected("forged approval session", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_release_control");
      await tx.$executeRaw(Prisma.sql`
        INSERT INTO "template_twin_release_approval_decisions" (
          "id", "releaseId", "releaseIdentitySha256", "discipline",
          "decision", "evidenceSha256", "confirmation", "actorId",
          "actorEmailSnapshot", "actorSessionSha256",
          "authorityAssignmentId", "auditOutboxEventKey",
          "actionReceiptNonce", "decidedAt"
        ) VALUES (
          ${randomUUID()}::UUID, ${release.releaseId}::UUID,
          ${release.identity}, 'OPERATIONS', 'REVOKE', ${syntheticSha},
          ${templateTwinApprovalConfirmation({
            decision: "REVOKE",
            discipline: "OPERATIONS",
            releaseIdentitySha256: release.identity,
          })},
          ${reviewerIds.get("OPERATIONS")!},
          ${`release-reviewer-operations-${suffix}@synthetic.test`},
          ${"0".repeat(64)}, ${operationAuthority[0]!.id}::UUID,
          ${`template-twin:release:${release.releaseId}:approval:${randomUUID()}`},
          ${randomUUID()}::UUID,
          CURRENT_TIMESTAMP + INTERVAL '100 years'
        )
      `);
    }),
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
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe(
        `SELECT set_config('meddoc.template_twin_release_coupling_verified_tx', txid_current()::text, true)`,
      );
      await tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_release_checkpoints"
        SET "status" = 'PASSED'
        WHERE "releaseId" = ${release.releaseId}::UUID AND "ordinal" = 5
      `);
    }),
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
    Array<{ id: string; activatedAt: Date }>
  >(Prisma.sql`
    SELECT "id", "activatedAt" FROM "template_twin_release_checkpoints"
    WHERE "releaseId" = ${release.releaseId}::UUID AND "stage" = 'CANARY'
  `);
  await expectRejected("active checkpoint activation evidence rewrite", () =>
    attacker.$executeRaw(Prisma.sql`
      UPDATE "template_twin_release_checkpoints"
      SET "activatedAt" = "activatedAt" + INTERVAL '1 second'
      WHERE "id" = ${checkpoint[0]!.id}::UUID
    `),
  );
  await expectRejected("release-control forged capability insert", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_release_control");
      await tx.$executeRaw(Prisma.sql`
        INSERT INTO "template_twin_release_capabilities" (
          "nonce", "transactionId", "backendPid", "releaseId",
          "releaseIdentitySha256", "checkpointId", "stageOrdinal",
          "releaseGeneration", "expectedGlobalGeneration", "expiresAt"
        ) VALUES (
          ${randomUUID()}::UUID, txid_current(), pg_backend_pid(),
          ${release.releaseId}::UUID, ${release.identity},
          ${checkpoint[0]!.id}::UUID, 1, ${activated.releaseGeneration}::BIGINT,
          ${activated.globalGeneration}::BIGINT,
          CURRENT_TIMESTAMP + INTERVAL '5 minutes'
        )
      `);
    }),
  );
  await expectRejected(
    "release-control checkpoint pass without signed metric",
    () =>
      attacker.$transaction(async (tx) => {
        await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_release_control");
        await tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_release_checkpoints"
        SET "status" = 'PASSED', "passedPhysicianCount" = 1,
          "passedAt" = CURRENT_TIMESTAMP, "passedById" = ${creatorId},
          "passOutboxEventKey" = ${`template-twin:release:${release.releaseId}:checkpoint:CANARY:forged-pass`},
          "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" = ${checkpoint[0]!.id}::UUID
      `);
      }),
  );
  await expectRejected("release-control premature stable release", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_release_control");
      await tx.$executeRawUnsafe(
        `SELECT set_config('meddoc.template_twin_release_coupling_verified_tx', txid_current()::text, true)`,
      );
      await tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_release_candidates"
        SET "status" = 'STABLE_100', "generation" = "generation" + 1,
          "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" = ${release.releaseId}::UUID
      `);
    }),
  );
  await expectRejected("future global rollout audit pre-seed", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_runtime");
      await tx.$executeRawUnsafe(
        `SELECT set_config('meddoc.template_twin_release_coupling_verified_tx', txid_current()::text, true)`,
      );
      await tx.$executeRaw(Prisma.sql`
        INSERT INTO "template_twin_audit_outbox" (
          "id", "practiceId", "actorId", "actorEmailSnapshot", "eventKey",
          "action", "targetId", "targetType", "metadata", "status",
          "attemptCount", "updatedAt"
        ) VALUES (
          ${randomUUID()}, ${administratorPracticeId}, ${creatorId},
          ${`release-creator-${suffix}@synthetic.test`},
          ${`template-twin:global-rollout:${(BigInt(activated.globalGeneration) + BigInt(1)).toString()}`},
          'TEMPLATE_TWIN_DEACTIVATED', 'global',
          'TemplateTwinRolloutControl',
          ${JSON.stringify({ scope: "global", enabled: false, generation: (BigInt(activated.globalGeneration) + BigInt(1)).toString() })}::JSONB,
          'PENDING', 0, CURRENT_TIMESTAMP
        )
      `);
    }),
  );
  await expectRejected("future checkpoint audit pre-seed", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_runtime");
      await tx.$executeRaw(Prisma.sql`
        INSERT INTO "template_twin_audit_outbox" (
          "id", "practiceId", "actorId", "actorEmailSnapshot", "eventKey",
          "action", "targetId", "targetType", "metadata", "status",
          "attemptCount", "updatedAt"
        ) VALUES (
          ${randomUUID()}, ${administratorPracticeId}, ${creatorId},
          ${`release-creator-${suffix}@synthetic.test`},
          ${`template-twin:release:${release.releaseId}:checkpoint:PERCENT_10:activated`},
          'TEMPLATE_TWIN_ROLLOUT_CHECKPOINT_ACTIVATED', ${randomUUID()}::TEXT,
          'TemplateTwinReleaseCheckpoint',
          ${JSON.stringify({
            releaseId: release.releaseId,
            releaseIdentitySha256: release.identity,
            stage: "PERCENT_10",
          })}::JSONB,
          'PENDING', 0, CURRENT_TIMESTAMP
        )
      `);
    }),
  );
  await expectRejected("unsigned release-control metric insert", () =>
    attacker.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_release_control");
      await tx.$executeRaw(Prisma.sql`
        INSERT INTO "template_twin_release_metric_snapshots" (
          "id", "releaseId", "checkpointId", "releaseIdentitySha256",
          "policySha256", "schemaVersion", "sampleCount",
          "observationStartedAt", "observationEndedAt", "metrics",
          "canonicalSha256", "attestationKeyId",
          "attestationNonceSha256", "attestationSignatureSha256",
          "evaluation", "missingMetrics", "breachedMetrics",
          "blockingReasons", "recordedById"
        ) VALUES (
          ${randomUUID()}::UUID, ${release.releaseId}::UUID,
          ${checkpoint[0]!.id}::UUID, ${release.identity}, ${syntheticSha},
          'template-twin-guardrails-v1', 1, CURRENT_TIMESTAMP - INTERVAL '1 second',
          CURRENT_TIMESTAMP, '{}'::JSONB, ${randomBytes(32).toString("hex")},
          ${metricKeyId}, ${randomBytes(32).toString("hex")},
          ${randomBytes(32).toString("hex")}, 'BLOCK', ARRAY[]::TEXT[],
          ARRAY[]::TEXT[], ARRAY[]::TEXT[], ${creatorId}
        )
      `);
    }),
  );
  const observationStartedAt = monitoringObservationStart(
    checkpoint[0]!.activatedAt,
  );
  const observationEndedAt =
    await waitForObservationWindow(observationStartedAt);
  const metricInput: UnsignedMetricSnapshot = {
    releaseId: release.releaseId,
    stage: "CANARY",
    expectedReleaseGeneration: activated.releaseGeneration.toString(),
    expectedGlobalGeneration: activated.globalGeneration.toString(),
    sampleCount: 1,
    observationStartedAt,
    observationEndedAt,
    metrics: passingMetrics,
  };
  const signed = metricAttestation(metricInput);
  await expectRejected("tampered monitoring signature", () =>
    recordTemplateTwinReleaseMetricSnapshot({
      ...metricInput,
      attestation: { ...signed, signature: "0".repeat(64) },
    }),
  );
  const metric = await recordSignedMetricSnapshot(metricInput);
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
    const startedAt = monitoringObservationStart(
      checkpointRows[0]!.activatedAt,
    );
    const endedAt = await waitForObservationWindow(startedAt);
    const stageMetric = await recordSignedMetricSnapshot({
      releaseId: release.releaseId,
      stage,
      expectedReleaseGeneration: active.releaseGeneration.toString(),
      expectedGlobalGeneration: active.globalGeneration.toString(),
      sampleCount: 1,
      observationStartedAt: startedAt,
      observationEndedAt: endedAt,
      metrics: passingMetrics,
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
  const killedGeneration = await setTemplateTwinGlobalRollout({
    enabled: false,
    actor: {
      userId: creatorId,
      userEmail: `release-creator-${suffix}@synthetic.test`,
      practiceId: administratorPracticeId,
    },
  });
  const killed = await readControlState(release.releaseId);
  assert.equal(killed.releaseStatus, "STABLE_100");
  assert.equal(killed.enabled, false, "a post-stable global kill must commit");
  assert.equal(killed.globalGeneration, killedGeneration);

  const deactivatedPracticeId = authorizedPracticeIds[0]!;
  const beforeDeactivation = await observer.practice.findUniqueOrThrow({
    where: { id: deactivatedPracticeId },
    select: {
      templateTwinEnabled: true,
      templateTwinRolloutGeneration: true,
    },
  });
  assert.equal(beforeDeactivation.templateTwinEnabled, true);
  await observer.practice.update({
    where: { id: deactivatedPracticeId },
    data: { isActive: false },
  });
  const afterDeactivation = await observer.practice.findUniqueOrThrow({
    where: { id: deactivatedPracticeId },
    select: {
      isActive: true,
      templateTwinEnabled: true,
      templateTwinRolloutGeneration: true,
    },
  });
  assert.equal(afterDeactivation.isActive, false);
  assert.equal(afterDeactivation.templateTwinEnabled, false);
  assert.equal(
    afterDeactivation.templateTwinRolloutGeneration,
    beforeDeactivation.templateTwinRolloutGeneration + BigInt(1),
  );
  const deactivationAudit = await observer.$queryRaw<Array<{ count: bigint }>>(
    Prisma.sql`
      SELECT COUNT(*)::BIGINT AS "count"
      FROM "template_twin_audit_outbox"
      WHERE "eventKey" = ${
        `template-twin:practice-rollout:${deactivatedPracticeId}:` +
        afterDeactivation.templateTwinRolloutGeneration.toString()
      }
        AND "action" = 'TEMPLATE_TWIN_DEACTIVATED'
    `,
  );
  assert.equal(deactivationAudit[0]!.count, BigInt(1));
  await revokeCurrentRelease(release, "SYNTHETIC_ADVANCE_RACE_COMPLETE");
  await observer.practice.update({
    where: { id: deactivatedPracticeId },
    data: { isActive: true },
  });
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
  const observationStartedAt = monitoringObservationStart(
    checkpoint[0]!.activatedAt,
  );
  const observationEndedAt =
    await waitForObservationWindow(observationStartedAt);
  const criticalMetrics = {
    ...passingMetrics,
    critical_field_accuracy: "0",
  };
  const metric = await recordSignedMetricSnapshot({
    releaseId: release.releaseId,
    stage: "CANARY",
    expectedReleaseGeneration: active.releaseGeneration.toString(),
    expectedGlobalGeneration: active.globalGeneration.toString(),
    sampleCount: 1,
    observationStartedAt,
    observationEndedAt,
    metrics: criticalMetrics,
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
  const observationStartedAt = monitoringObservationStart(
    checkpoint[0]!.activatedAt,
  );
  const observationEndedAt =
    await waitForObservationWindow(observationStartedAt);
  const passing = await recordSignedMetricSnapshot({
    releaseId: release.releaseId,
    stage: "CANARY",
    expectedReleaseGeneration: active.releaseGeneration.toString(),
    expectedGlobalGeneration: active.globalGeneration.toString(),
    sampleCount: 1,
    observationStartedAt,
    observationEndedAt,
    metrics: passingMetrics,
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
  const critical = recordSignedMetricSnapshot({
    releaseId: release.releaseId,
    stage: "CANARY",
    expectedReleaseGeneration: passing.releaseGeneration,
    expectedGlobalGeneration: passing.globalGeneration,
    sampleCount: 1,
    observationStartedAt,
    observationEndedAt,
    metrics: { ...passingMetrics, critical_field_accuracy: "0" },
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

async function proveAuditDispatcherBoundary(): Promise<void> {
  const result = await drainTemplateTwinAuditOutbox({
    prisma: auditDispatcher,
    now: new Date(),
    limit: 5,
  });
  assert.deepEqual(result, { delivered: 5, failed: 0, contended: 0 });
  const delivered = await observer.templateTwinAuditOutbox.findFirstOrThrow({
    where: {
      status: "DELIVERED",
      eventKey: { startsWith: "template-twin:release:" },
    },
    select: { id: true },
  });
  await expectRejected("dispatcher cannot rewrite release audit identity", () =>
    auditDispatcher.templateTwinAuditOutbox.update({
      where: { id: delivered.id },
      data: { targetType: "ForgedReleaseTarget" },
    }),
  );
  const assertion = await observer.$queryRaw<Array<{ result: string | null }>>(
    Prisma.sql`
      SELECT template_twin_assert_release_audit_delivery()::TEXT AS "result"
    `,
  );
  assert.equal(assertion.length, 1);
}

async function assertAuditCensus(): Promise<number> {
  const rows = await observer.$queryRaw<
    Array<{
      count: bigint;
      distinctCount: bigint;
      pendingCount: bigint;
      deliveredCount: bigint;
      otherCount: bigint;
    }>
  >(Prisma.sql`
    SELECT COUNT(*)::BIGINT AS "count",
      COUNT(DISTINCT "eventKey")::BIGINT AS "distinctCount",
      COUNT(*) FILTER (WHERE "status" = 'PENDING')::BIGINT AS "pendingCount",
      COUNT(*) FILTER (WHERE "status" = 'DELIVERED')::BIGINT AS "deliveredCount",
      COUNT(*) FILTER (
        WHERE "status" NOT IN ('PENDING', 'DELIVERED')
      )::BIGINT AS "otherCount"
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
    row.pendingCount + row.deliveredCount,
    row.count,
    "synthetic release events are either pending or durably delivered",
  );
  assert(row.deliveredCount >= BigInt(5), "dispatcher must deliver its batch");
  assert.equal(row.otherCount, BigInt(0));
  const deliveredPairs = await observer.$queryRaw<Array<{ count: bigint }>>(
    Prisma.sql`
      SELECT COUNT(*)::BIGINT AS "count"
      FROM "template_twin_audit_outbox" outbox
      JOIN "audit_logs" log
        ON log."templateTwinOutboxEventKey" = outbox."eventKey"
       AND log."timestamp" = outbox."deliveredAt"
       AND log."action" = outbox."action"
      WHERE outbox."eventKey" LIKE 'template-twin:release:%'
        AND outbox."status" = 'DELIVERED'
    `,
  );
  assert.equal(deliveredPairs[0]!.count, row.deliveredCount);
  assert(row.count >= BigInt(46), "expected complete release audit evidence");
  return Number(row.count);
}

async function proveLiveUserLifecycleRevocation(): Promise<void> {
  const release = await createApprovedRelease("7");
  await activation(release);
  const active = await readControlState(release.releaseId);
  assert.equal(active.releaseStatus, "ROLLING_OUT");
  assert.equal(active.enabled, true);
  await expectRejected("live runtime key revocation without disable", () =>
    observer.$executeRaw(Prisma.sql`
      UPDATE "template_twin_release_attestation_keys"
      SET "revokedAt" = CURRENT_TIMESTAMP
      WHERE "keyId" = ${runtimeKeyId} AND "revokedAt" IS NULL
    `),
  );
  const updated = await observer.$executeRaw(Prisma.sql`
    UPDATE "users"
    SET "products" = array_remove(
      "products", 'SUPER_ADMIN'::"Product"
    )
    WHERE "id" = ${reviewerIds.get("OPERATIONS")!}
      AND 'SUPER_ADMIN'::"Product" = ANY("products")
  `);
  assert.equal(updated, 1, "reviewer entitlement transition must commit");
  const revoked = await readControlState(release.releaseId);
  assert.equal(revoked.releaseStatus, "REVOKED");
  assert.equal(revoked.enabled, false);
  const authority = await observer.$queryRaw<Array<{ revokedAt: Date | null }>>(
    Prisma.sql`
      SELECT "revokedAt" FROM "template_twin_release_authorities"
      WHERE "userId" = ${reviewerIds.get("OPERATIONS")!}
        AND "discipline" = 'OPERATIONS'
    `,
  );
  assert(authority[0]!.revokedAt, "lifecycle transition must revoke authority");
  await observer.$executeRaw(Prisma.sql`
    UPDATE "template_twin_release_attestation_keys"
    SET "revokedAt" = CURRENT_TIMESTAMP
    WHERE "keyId" = ${runtimeKeyId} AND "revokedAt" IS NULL
  `);
  assert(unconfiguredRuntimeEnv, "unconfigured runtime proof must run first");
  await expectRejected(
    "revoked runtime key cannot masquerade as an unconfigured release",
    () => submitRuntimeEnvelope(unconfiguredRuntimeEnv!),
  );
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
  const runProof = async (name: string, proof: () => Promise<void>) => {
    process.stderr.write(`[template-twin-control-plane] ${name}\n`);
    await proof();
  };
  const auditBaseline = await observer.$queryRaw<Array<{ count: bigint }>>(
    Prisma.sql`
      SELECT COUNT(*)::BIGINT AS "count"
      FROM "template_twin_audit_outbox"
      WHERE "eventKey" LIKE 'template-twin:release:%'
    `,
  );
  await runProof("seed-synthetic-authorities", seedSyntheticAuthorities);
  await runProof(
    "unconfigured-runtime-attestation",
    proveUnconfiguredRuntimeAttestation,
  );
  await runProof("database-role-boundaries", proveDatabaseRoleBoundaries);
  await runProof("advance-race-and-capability-replay", proveAdvanceRaceAndCapabilityReplay);
  await runProof("global-kill-race", proveGlobalKillRace);
  await runProof("approval-revoke-race", proveApprovalRevokeRace);
  await runProof("operational-revoke-race", proveOperationalRevokeRace);
  await runProof("critical-guardrail-revoke", proveCriticalGuardrailRevoke);
  await runProof("critical-guardrail-pass-race", proveCriticalGuardrailPassRace);
  await runProof("live-user-lifecycle-revocation", proveLiveUserLifecycleRevocation);
  await runProof("isolated-audit-dispatcher", proveAuditDispatcherBoundary);
  const releaseAuditEventTotal = await assertAuditCensus();
  const releaseAuditEventCount =
    releaseAuditEventTotal - Number(auditBaseline[0]!.count);
  assert(
    releaseAuditEventCount >= 46,
    "this proof run must append complete release audit evidence",
  );
  const global = await readGlobal();
  assert.equal(global.enabled, false);

  process.stdout.write(
    `${JSON.stringify({
      profile: "template-twin-production-release-control-postgres-v3",
      synthetic: true,
      databaseGuard: "passed",
      migrations: "fresh-deploy-required",
      directSqlEnableRejected: true,
      nonOwnerRoleBoundaryRejected: true,
      signedRuntimeReplicaBarrier: true,
      signedMonitoringReceipts: true,
      isolatedAuditDispatcher: true,
      liveRuntimeKeyRevocationWithoutDisableRejected: true,
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
      authorityLifecycle: "atomic-revoke-and-disable",
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
    await Promise.all([
      observer.$disconnect(),
      attacker.$disconnect(),
      auditDispatcher.$disconnect(),
    ]);
  });
