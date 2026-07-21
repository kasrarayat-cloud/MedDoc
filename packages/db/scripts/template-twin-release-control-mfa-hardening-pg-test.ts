#!/usr/bin/env tsx

// Disposable PostgreSQL proof for Template Twin control-plane complete MFA.
// The target must be a freshly migrated, pre-v4 database whose name starts
// with meddoc_mfa_v4_pg_. The script applies v4, exercises only synthetic
// identities, reruns the SQL idempotently, and drops the exact test database
// on every exit. It never reads or prints MFA secret material.

import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { PrismaPg } from "@prisma/adapter-pg";
import { Prisma, PrismaClient } from "@prisma/client";
import { Client } from "pg";

import type { TemplateTwinReleaseActor } from "../../../apps/transcribe-md/src/lib/template-twin/release-control";
import {
  TEMPLATE_TWIN_METRIC_DEFINITIONS,
  TEMPLATE_TWIN_RELEASE_DISCIPLINES,
  templateTwinApprovalConfirmation,
  type TemplateTwinGuardrailPolicy,
  type TemplateTwinMetricKey,
  type TemplateTwinReleaseDiscipline,
  type TemplateTwinReleaseIdentityEvidence,
} from "../../../apps/transcribe-md/src/lib/template-twin/release-control-contracts";
import { assertNonProdDatabase } from "../src/db-guard";

const databaseUrl =
  process.env.TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL ||
  process.env.DATABASE_URL;
if (!databaseUrl) {
  throw new Error("Disposable complete-MFA PostgreSQL test URL is required.");
}
assertNonProdDatabase(databaseUrl);
const verifiedDatabaseUrl = databaseUrl;
const databaseTargetEnvironment = [
  "DATABASE_URL",
  "TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL",
  "TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL",
] as const;
const divergentDatabaseTarget = databaseTargetEnvironment.find((name) => {
  const value = process.env[name];
  return value && value !== verifiedDatabaseUrl;
});
if (divergentDatabaseTarget) {
  throw new Error(
    `${divergentDatabaseTarget} must exactly match the guarded disposable complete-MFA test URL.`,
  );
}
for (const name of databaseTargetEnvironment) {
  process.env[name] = verifiedDatabaseUrl;
}

type ReleaseControlModule =
  typeof import("../../../apps/transcribe-md/src/lib/template-twin/release-control");
type ReleaseControlDatabaseModule =
  typeof import("../../../apps/transcribe-md/src/lib/template-twin/release-control-db");

let createTemplateTwinReleaseCandidate!: ReleaseControlModule["createTemplateTwinReleaseCandidate"];
let freezeTemplateTwinReleaseCandidate!: ReleaseControlModule["freezeTemplateTwinReleaseCandidate"];
let recordTemplateTwinReleaseApproval!: ReleaseControlModule["recordTemplateTwinReleaseApproval"];
let releaseControlDatabase: ReleaseControlDatabaseModule["default"] | undefined;

async function loadDatabaseBearingModules(): Promise<void> {
  const [releaseControl, releaseControlDatabaseModule] = await Promise.all([
    import("../../../apps/transcribe-md/src/lib/template-twin/release-control"),
    import("../../../apps/transcribe-md/src/lib/template-twin/release-control-db"),
  ]);
  ({
    createTemplateTwinReleaseCandidate,
    freezeTemplateTwinReleaseCandidate,
    recordTemplateTwinReleaseApproval,
  } = releaseControl);
  releaseControlDatabase = releaseControlDatabaseModule.default;
}

const parsedDatabaseUrl = new URL(verifiedDatabaseUrl);
const databaseName = decodeURIComponent(parsedDatabaseUrl.pathname.slice(1));
if (!/^meddoc_mfa_v4_pg_[a-z0-9_]+$/.test(databaseName)) {
  throw new Error(
    "Complete-MFA proof requires an exact meddoc_mfa_v4_pg_* database.",
  );
}

const migrationSql = readFileSync(
  fileURLToPath(
    new URL(
      "../prisma/migrations/20260720123000_template_twin_production_control_plane_mfa_hardening_v4/migration.sql",
      import.meta.url,
    ),
  ),
  "utf8",
);
const graphProbeRole = `synthetic_mfa_v4_graph_${process.pid}`;
const suffix = `${process.pid}-${Date.now()}`;
const administratorPracticeId = `synthetic-mfa-admin-${suffix}`;
const physicianPracticeId = `synthetic-mfa-practice-${suffix}`;
const physicianId = `synthetic-mfa-physician-${suffix}`;
const creatorId = `synthetic-mfa-creator-${suffix}`;
const creatorSession = `synthetic-mfa-creator-session-${suffix}`;
const reviewerIds = new Map<TemplateTwinReleaseDiscipline, string>();
const reviewerSessions = new Map<TemplateTwinReleaseDiscipline, string>();
const authorityIds = new Map<TemplateTwinReleaseDiscipline, string>();
const syntheticCompleteSecret = "SYNTHETIC-MFA-V4-BASE32-SECRET";

const observer = new PrismaClient({
  adapter: new PrismaPg({ connectionString: verifiedDatabaseUrl }),
});

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
  ) as unknown as Record<
    TemplateTwinMetricKey,
    TemplateTwinGuardrailPolicy["metrics"][TemplateTwinMetricKey]
  >,
};

interface ApprovedRelease {
  readonly id: string;
  readonly identity: string;
  readonly generation: string;
}

interface SessionCase {
  readonly label: string;
  readonly mfaSecret: string | null;
  readonly mfaVerifiedAt: Date | null;
  readonly expected: boolean;
}

function evidence(): TemplateTwinReleaseIdentityEvidence {
  return {
    sourceCommitSha: "a".repeat(40),
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

function reviewerActor(
  discipline: TemplateTwinReleaseDiscipline,
): TemplateTwinReleaseActor {
  return {
    userId: reviewerIds.get(discipline)!,
    sessionId: reviewerSessions.get(discipline)!,
  };
}

async function expectRejected(
  label: string,
  operation: () => Promise<unknown>,
): Promise<void> {
  let rejected = false;
  try {
    await operation();
  } catch {
    rejected = true;
  }
  assert(rejected, `${label} must be rejected`);
}

async function applyMfaMigration(): Promise<void> {
  const client = new Client({ connectionString: verifiedDatabaseUrl });
  try {
    await client.connect();
    await client.query(migrationSql);
  } finally {
    await client.end().catch(() => undefined);
  }
}

async function expectMigrationRoleGraphRejected(label: string): Promise<void> {
  let rejected = false;
  try {
    await applyMfaMigration();
  } catch {
    rejected = true;
  }
  assert(rejected, `${label} must reject v4 before any side effect commits`);
}

async function proveMigrationRoleGraphGuard(): Promise<void> {
  assert.match(graphProbeRole, /^[a-z0-9_]+$/u);
  const client = new Client({ connectionString: verifiedDatabaseUrl });
  try {
    await client.connect();
    await client.query(`CREATE ROLE "${graphProbeRole}" NOLOGIN`);

    await client.query(
      `GRANT "${graphProbeRole}" TO quillmd_audit_dispatcher
       WITH ADMIN FALSE, INHERIT TRUE, SET FALSE`,
    );
    await expectMigrationRoleGraphRejected("outgoing boundary membership");
    await client.query(
      `REVOKE "${graphProbeRole}" FROM quillmd_audit_dispatcher`,
    );

    await client.query(
      `GRANT meddoc_audit_dispatcher TO "${graphProbeRole}"
       WITH ADMIN FALSE, INHERIT TRUE, SET FALSE`,
    );
    await expectMigrationRoleGraphRejected("inbound trusted-login membership");
    await client.query(
      `REVOKE meddoc_audit_dispatcher FROM "${graphProbeRole}"`,
    );

    await client.query(
      `GRANT "${graphProbeRole}" TO meddoc_audit_dispatcher
       WITH ADMIN FALSE, INHERIT TRUE, SET FALSE`,
    );
    await expectMigrationRoleGraphRejected("extra login membership");
    await client.query(
      `REVOKE "${graphProbeRole}" FROM meddoc_audit_dispatcher`,
    );

    await client.query(
      `GRANT quillmd_audit_dispatcher TO meddoc_audit_dispatcher
       WITH ADMIN FALSE, INHERIT TRUE, SET TRUE`,
    );
    await expectMigrationRoleGraphRejected("SET ROLE membership option");
    await client.query(
      `GRANT quillmd_audit_dispatcher TO meddoc_audit_dispatcher
       WITH ADMIN FALSE, INHERIT TRUE, SET FALSE`,
    );
  } finally {
    await client
      .query(`REVOKE "${graphProbeRole}" FROM quillmd_audit_dispatcher`)
      .catch(() => undefined);
    await client
      .query(`REVOKE meddoc_audit_dispatcher FROM "${graphProbeRole}"`)
      .catch(() => undefined);
    await client
      .query(`REVOKE "${graphProbeRole}" FROM meddoc_audit_dispatcher`)
      .catch(() => undefined);
    await client
      .query(`DROP ROLE IF EXISTS "${graphProbeRole}"`)
      .catch(() => undefined);
    await client.end().catch(() => undefined);
  }
}

async function seedPreV4Release(): Promise<ApprovedRelease> {
  const expiresAt = new Date(Date.now() + 60 * 60 * 1_000);
  await observer.practice.createMany({
    data: [
      {
        id: administratorPracticeId,
        name: "Synthetic MFA release administration",
        slug: administratorPracticeId,
        templateTwinEnabled: false,
      },
      {
        id: physicianPracticeId,
        name: "Synthetic MFA canary practice",
        slug: physicianPracticeId,
        templateTwinEnabled: false,
      },
    ],
  });
  await observer.user.create({
    data: {
      id: physicianId,
      email: `${physicianId}@synthetic.test`,
      passwordHash: "synthetic-not-a-login-credential",
      role: "DOCTOR",
      products: ["TRANSCRIBE_MD"],
      practiceId: physicianPracticeId,
    },
  });
  await observer.user.create({
    data: {
      id: creatorId,
      email: `${creatorId}@synthetic.test`,
      passwordHash: "synthetic-not-a-login-credential",
      role: "ADMIN",
      products: ["SUPER_ADMIN"],
      practiceId: administratorPracticeId,
      mfaEnabled: true,
      mfaSecret: syntheticCompleteSecret,
      mfaVerifiedAt: new Date(Date.now() - 60_000),
    },
  });
  await observer.userSession.create({
    data: {
      userId: creatorId,
      sessionToken: creatorSession,
      expiresAt,
    },
  });

  for (const discipline of TEMPLATE_TWIN_RELEASE_DISCIPLINES) {
    const reviewerId = `synthetic-mfa-reviewer-${discipline.toLowerCase()}-${suffix}`;
    const session = `synthetic-mfa-reviewer-session-${discipline.toLowerCase()}-${suffix}`;
    const authorityId = randomUUID();
    reviewerIds.set(discipline, reviewerId);
    reviewerSessions.set(discipline, session);
    authorityIds.set(discipline, authorityId);
    await observer.user.create({
      data: {
        id: reviewerId,
        email: `${reviewerId}@synthetic.test`,
        passwordHash: "synthetic-not-a-login-credential",
        role: "ADMIN",
        products: ["SUPER_ADMIN"],
        practiceId: administratorPracticeId,
        mfaEnabled: true,
        mfaSecret: syntheticCompleteSecret,
        mfaVerifiedAt: new Date(Date.now() - 60_000),
      },
    });
    await observer.userSession.create({
      data: { userId: reviewerId, sessionToken: session, expiresAt },
    });
    await observer.$executeRaw(Prisma.sql`
      INSERT INTO "template_twin_release_authorities" (
        "id", "userId", "discipline", "sourceRef"
      ) VALUES (
        ${authorityId}::UUID, ${reviewerId}, ${discipline},
        ${`synthetic-mfa-v4/${discipline.toLowerCase()}`}
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

  const releaseEvidence = evidence();
  const created = await createTemplateTwinReleaseCandidate({
    actor: { userId: creatorId, sessionId: creatorSession },
    confirmation: "CREATE EXACT RELEASE",
    evidence: releaseEvidence,
    guardrailPolicy: policy,
    authorizedPracticeIds: [physicianPracticeId],
    canaryPracticeIds: [physicianPracticeId],
    runtimeInstances: [
      {
        instanceId: `synthetic-mfa-app-${suffix}`,
        component: "APP",
        imageDigest: releaseEvidence.appImageDigest,
      },
      {
        instanceId: `synthetic-mfa-worker-${suffix}`,
        component: "WORKER",
        imageDigest: releaseEvidence.workerImageDigest,
      },
    ],
  });
  let generation = (
    await freezeTemplateTwinReleaseCandidate({
      actor: { userId: creatorId, sessionId: creatorSession },
      releaseId: created.releaseId,
      expectedReleaseGeneration: created.generation,
      confirmation: `FREEZE ${created.releaseIdentitySha256.slice(0, 12)}`,
    })
  ).generation;
  for (const [
    index,
    discipline,
  ] of TEMPLATE_TWIN_RELEASE_DISCIPLINES.entries()) {
    const recorded = await recordTemplateTwinReleaseApproval({
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
    generation = recorded.generation;
  }
  return {
    id: created.releaseId,
    identity: created.releaseIdentitySha256,
    generation,
  };
}

async function approvalsAreCurrent(release: ApprovedRelease): Promise<boolean> {
  const rows = await observer.$queryRaw<Array<{ current: boolean }>>(Prisma.sql`
    SELECT public.template_twin_release_approvals_are_current(
      ${release.id}::UUID, ${release.identity}::CHAR(64)
    ) AS "current"
  `);
  return rows[0]!.current;
}

async function seedSessionCases(): Promise<SessionCase[]> {
  const now = Date.now();
  const cases: SessionCase[] = [
    {
      label: "missing-secret",
      mfaSecret: null,
      mfaVerifiedAt: new Date(now - 60_000),
      expected: false,
    },
    {
      label: "empty-secret",
      mfaSecret: "",
      mfaVerifiedAt: new Date(now - 60_000),
      expected: false,
    },
    {
      label: "space-secret",
      mfaSecret: "   ",
      mfaVerifiedAt: new Date(now - 60_000),
      expected: false,
    },
    {
      label: "tab-newline-secret",
      mfaSecret: "\t\n\r",
      mfaVerifiedAt: new Date(now - 60_000),
      expected: false,
    },
    {
      label: "non-breaking-space-secret",
      mfaSecret: "\u00a0",
      mfaVerifiedAt: new Date(now - 60_000),
      expected: false,
    },
    {
      label: "figure-space-secret",
      mfaSecret: "\u2007",
      mfaVerifiedAt: new Date(now - 60_000),
      expected: false,
    },
    {
      label: "narrow-non-breaking-space-secret",
      mfaSecret: "\u202f",
      mfaVerifiedAt: new Date(now - 60_000),
      expected: false,
    },
    {
      label: "byte-order-mark-secret",
      mfaSecret: "\ufeff",
      mfaVerifiedAt: new Date(now - 60_000),
      expected: false,
    },
    {
      label: "missing-verification",
      mfaSecret: syntheticCompleteSecret,
      mfaVerifiedAt: null,
      expected: false,
    },
    {
      label: "future-verification",
      mfaSecret: syntheticCompleteSecret,
      mfaVerifiedAt: new Date(now + 60 * 60 * 1_000),
      expected: false,
    },
    {
      label: "complete-current",
      mfaSecret: syntheticCompleteSecret,
      mfaVerifiedAt: new Date(now - 60_000),
      expected: true,
    },
    {
      label: "arbitrary-nonblank-current",
      mfaSecret: "\u00a0synthetic:not-base32\ufeff",
      mfaVerifiedAt: new Date(now - 60_000),
      expected: true,
    },
  ];
  for (const testCase of cases) {
    const id = `synthetic-mfa-session-${testCase.label}-${suffix}`;
    const token = `synthetic-mfa-token-${testCase.label}-${suffix}`;
    await observer.user.create({
      data: {
        id,
        email: `${id}@synthetic.test`,
        passwordHash: "synthetic-not-a-login-credential",
        role: "ADMIN",
        products: ["SUPER_ADMIN"],
        practiceId: administratorPracticeId,
        mfaEnabled: true,
        mfaSecret: testCase.mfaSecret,
        mfaVerifiedAt: testCase.mfaVerifiedAt,
      },
    });
    await observer.userSession.create({
      data: {
        userId: id,
        sessionToken: token,
        expiresAt: new Date(now + 60 * 60 * 1_000),
      },
    });
  }
  return cases;
}

async function proveSessionPredicates(cases: SessionCase[]): Promise<void> {
  for (const testCase of cases) {
    const id = `synthetic-mfa-session-${testCase.label}-${suffix}`;
    const token = `synthetic-mfa-token-${testCase.label}-${suffix}`;
    const rows = await observer.$queryRaw<
      Array<{ actorCount: bigint; adminCount: bigint }>
    >(Prisma.sql`
      SELECT
        (SELECT COUNT(*)::BIGINT
         FROM public.template_twin_verify_release_actor(${id}, ${token}))
          AS "actorCount",
        (SELECT COUNT(*)::BIGINT
         FROM public.template_twin_verify_release_admin_session(${id}, ${token}))
          AS "adminCount"
    `);
    const expected = testCase.expected ? BigInt(1) : BigInt(0);
    assert.equal(rows[0]!.actorCount, expected, testCase.label);
    assert.equal(rows[0]!.adminCount, expected, testCase.label);
  }

  const complete = cases.find((testCase) => testCase.expected)!;
  const id = `synthetic-mfa-session-${complete.label}-${suffix}`;
  const token = `synthetic-mfa-token-${complete.label}-${suffix}`;
  await observer.$transaction(async (tx) => {
    await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_release_control");
    const rows = await tx.$queryRaw<Array<{ count: bigint }>>(Prisma.sql`
      SELECT COUNT(*)::BIGINT AS "count"
      FROM public.template_twin_verify_release_admin_session(${id}, ${token})
    `);
    assert.equal(rows[0]!.count, BigInt(1));
  });
  await expectRejected("release-control raw MFA secret read", () =>
    observer.$transaction(async (tx) => {
      await tx.$executeRawUnsafe("SET LOCAL ROLE quillmd_release_control");
      await tx.$queryRawUnsafe(
        `SELECT "mfaSecret" FROM public."users" WHERE "id" = 'never-returned'`,
      );
    }),
  );
}

async function proveInstalledFunctionBoundary(): Promise<void> {
  const expectedFunctions = [
    "template_twin_verify_release_actor",
    "template_twin_release_approvals_are_current",
    "template_twin_guard_release_approval_insert",
    "template_twin_guard_checkpoint_pass",
    "template_twin_verify_release_admin_session",
    "template_twin_revoke_authority_on_user_lifecycle",
  ];
  const rows = await observer.$queryRaw<
    Array<{
      name: string;
      securityDefiner: boolean;
      configuration: string[] | null;
      resultType: string;
    }>
  >(Prisma.sql`
    SELECT procedure.proname AS "name",
      procedure.prosecdef AS "securityDefiner",
      procedure.proconfig AS "configuration",
      pg_get_function_result(procedure.oid) AS "resultType"
    FROM pg_proc procedure
    JOIN pg_namespace namespace ON namespace.oid = procedure.pronamespace
    WHERE namespace.nspname = 'public'
      AND procedure.proname = ANY(${expectedFunctions}::TEXT[])
    ORDER BY procedure.proname
  `);
  assert.equal(rows.length, expectedFunctions.length);
  for (const row of rows) {
    assert.equal(row.securityDefiner, true, row.name);
    assert(
      row.configuration?.includes("search_path=pg_catalog, public, pg_temp"),
      `${row.name} must use the trusted path`,
    );
    assert(!row.resultType.toLowerCase().includes("mfasecret"));
  }

  const privilegeRows = await observer.$queryRaw<
    Array<{
      controlActor: boolean;
      controlAdmin: boolean;
      runtimeActor: boolean;
    }>
  >(Prisma.sql`
    SELECT
      has_function_privilege(
        'quillmd_release_control',
        'public.template_twin_verify_release_actor(text,text)', 'EXECUTE'
      ) AS "controlActor",
      has_function_privilege(
        'quillmd_release_control',
        'public.template_twin_verify_release_admin_session(text,text)', 'EXECUTE'
      ) AS "controlAdmin",
      has_function_privilege(
        'quillmd_runtime',
        'public.template_twin_verify_release_actor(text,text)', 'EXECUTE'
      ) AS "runtimeActor"
  `);
  assert.equal(privilegeRows[0]!.controlActor, true);
  assert.equal(privilegeRows[0]!.controlAdmin, true);
  assert.equal(privilegeRows[0]!.runtimeActor, false);

  const triggerRows = await observer.$queryRaw<Array<{ definition: string }>>(
    Prisma.sql`
      SELECT pg_get_triggerdef(trigger.oid) AS "definition"
      FROM pg_trigger trigger
      WHERE trigger.tgrelid = 'public.users'::REGCLASS
        AND trigger.tgname IN (
          'aaa_template_twin_user_lifecycle_statement_lock',
          'template_twin_user_lifecycle_authority_revoke'
        )
      ORDER BY trigger.tgname
    `,
  );
  assert.equal(triggerRows.length, 2);
  for (const row of triggerRows) {
    assert(row.definition.includes("mfaSecret"));
    assert(row.definition.includes("mfaVerifiedAt"));
    assert(row.definition.includes("products"));
  }
}

async function seedLifecycleAuthority(label: string): Promise<{
  userId: string;
  authorityId: string;
}> {
  const userId = `synthetic-mfa-lifecycle-${label}-${suffix}`;
  const authorityId = randomUUID();
  await observer.user.create({
    data: {
      id: userId,
      email: `${userId}@synthetic.test`,
      passwordHash: "synthetic-not-a-login-credential",
      role: "ADMIN",
      products: ["SUPER_ADMIN"],
      practiceId: administratorPracticeId,
      mfaEnabled: true,
      mfaSecret: syntheticCompleteSecret,
      mfaVerifiedAt: new Date(Date.now() - 60_000),
    },
  });
  await observer.$executeRaw(Prisma.sql`
    INSERT INTO "template_twin_release_authorities" (
      "id", "userId", "discipline", "sourceRef"
    ) VALUES (
      ${authorityId}::UUID, ${userId}, 'OPERATIONS',
      ${`synthetic-mfa-lifecycle/${label}`}
    )
  `);
  return { userId, authorityId };
}

async function assertAuthorityRevoked(authorityId: string): Promise<void> {
  const rows = await observer.$queryRaw<
    Array<{ revokedAt: Date | null; auditCount: bigint }>
  >(Prisma.sql`
    SELECT authority."revokedAt",
      (SELECT COUNT(*)::BIGINT
       FROM "template_twin_audit_outbox" outbox
       WHERE outbox."targetType" = 'TemplateTwinReleaseAuthority'
         AND outbox."targetId" = authority."id"::TEXT) AS "auditCount"
    FROM "template_twin_release_authorities" authority
    WHERE authority."id" = ${authorityId}::UUID
  `);
  assert(rows[0]!.revokedAt, "authority must be durably revoked");
  assert.equal(rows[0]!.auditCount, BigInt(1));
}

async function proveLifecycleRevocation(): Promise<void> {
  const removal = await seedLifecycleAuthority("secret-removal");
  await observer.user.update({
    where: { id: removal.userId },
    data: { mfaSecret: null },
  });
  await assertAuthorityRevoked(removal.authorityId);

  const whitespace = await seedLifecycleAuthority("secret-whitespace");
  await observer.user.update({
    where: { id: whitespace.userId },
    data: { mfaSecret: " \t\n\r " },
  });
  await assertAuthorityRevoked(whitespace.authorityId);

  const unicodeWhitespace = await seedLifecycleAuthority(
    "secret-unicode-whitespace",
  );
  await observer.user.update({
    where: { id: unicodeWhitespace.userId },
    data: { mfaSecret: "\u00a0\u2007\u202f\ufeff" },
  });
  await assertAuthorityRevoked(unicodeWhitespace.authorityId);

  const rotation = await seedLifecycleAuthority("secret-rotation");
  await observer.user.update({
    where: { id: rotation.userId },
    data: { mfaSecret: "SYNTHETIC-ROTATED-MFA-SECRET" },
  });
  await assertAuthorityRevoked(rotation.authorityId);

  const missingVerification = await seedLifecycleAuthority(
    "missing-verification",
  );
  await observer.user.update({
    where: { id: missingVerification.userId },
    data: { mfaVerifiedAt: null },
  });
  await assertAuthorityRevoked(missingVerification.authorityId);

  const futureVerification = await seedLifecycleAuthority(
    "future-verification",
  );
  await observer.user.update({
    where: { id: futureVerification.userId },
    data: { mfaVerifiedAt: new Date(Date.now() + 60 * 60 * 1_000) },
  });
  await assertAuthorityRevoked(futureVerification.authorityId);

  const complete = await seedLifecycleAuthority("complete-current");
  await observer.$executeRaw(Prisma.sql`
    UPDATE "users" SET "mfaSecret" = "mfaSecret"
    WHERE "id" = ${complete.userId}
  `);
  const current = await observer.$queryRaw<Array<{ count: bigint }>>(
    Prisma.sql`
      SELECT COUNT(*)::BIGINT AS "count"
      FROM "template_twin_release_authorities"
      WHERE "id" = ${complete.authorityId}::UUID AND "revokedAt" IS NULL
    `,
  );
  assert.equal(current[0]!.count, BigInt(1));
}

async function main(): Promise<Record<string, unknown>> {
  const residual = await observer.$queryRaw<
    Array<{ releases: bigint; users: bigint; authorities: bigint }>
  >(Prisma.sql`
    SELECT
      (SELECT COUNT(*)::BIGINT FROM "template_twin_release_candidates")
        AS "releases",
      (SELECT COUNT(*)::BIGINT FROM "users") AS "users",
      (SELECT COUNT(*)::BIGINT FROM "template_twin_release_authorities")
        AS "authorities"
  `);
  assert.deepEqual(residual[0], {
    releases: BigInt(0),
    users: BigInt(0),
    authorities: BigInt(0),
  });

  await proveMigrationRoleGraphGuard();

  const release = await seedPreV4Release();
  assert.equal(await approvalsAreCurrent(release), true);
  const decisionsBefore = await observer.$queryRaw<Array<{ count: bigint }>>(
    Prisma.sql`
      SELECT COUNT(*)::BIGINT AS "count"
      FROM "template_twin_release_approval_decisions"
      WHERE "releaseId" = ${release.id}::UUID
    `,
  );
  assert.equal(decisionsBefore[0]!.count, BigInt(4));

  const unicodeStaleDiscipline = "PRIVACY_LEGAL" as const;
  await observer.user.update({
    where: { id: reviewerIds.get(unicodeStaleDiscipline)! },
    data: { mfaSecret: "\u00a0\u2007\u202f\ufeff" },
  });
  assert.equal(
    await approvalsAreCurrent(release),
    true,
    "the pre-v4 predicate must reproduce the Unicode-whitespace parity defect",
  );
  const staleDiscipline = "OPERATIONS" as const;
  await observer.user.update({
    where: { id: reviewerIds.get(staleDiscipline)! },
    data: { mfaSecret: null },
  });
  assert.equal(
    await approvalsAreCurrent(release),
    true,
    "the pre-v4 predicate must reproduce the missing-secret defect",
  );
  const staleAuthorityBefore = await observer.$queryRaw<
    Array<{ revokedAt: Date | null }>
  >(Prisma.sql`
    SELECT "revokedAt" FROM "template_twin_release_authorities"
    WHERE "id" = ${authorityIds.get(staleDiscipline)!}::UUID
  `);
  assert.equal(staleAuthorityBefore[0]!.revokedAt, null);

  const sessionCases = await seedSessionCases();
  await applyMfaMigration();
  assert.equal(await approvalsAreCurrent(release), false);
  const reconciled = await observer.$queryRaw<
    Array<{
      releaseStatus: string;
      authorityRevokedAt: Date | null;
      globalEnabled: boolean;
      decisionCount: bigint;
      installAuditCount: bigint;
    }>
  >(Prisma.sql`
    SELECT candidate."status" AS "releaseStatus",
      authority."revokedAt" AS "authorityRevokedAt",
      control."enabled" AS "globalEnabled",
      (SELECT COUNT(*)::BIGINT
       FROM "template_twin_release_approval_decisions" decision
       WHERE decision."releaseId" = candidate."id") AS "decisionCount",
      (SELECT COUNT(*)::BIGINT FROM "template_twin_audit_outbox" outbox
       WHERE outbox."metadata"->>'reasonCode' =
         'AUTHORITY_MFA_INCOMPLETE_INSTALL') AS "installAuditCount"
    FROM "template_twin_release_candidates" candidate
    CROSS JOIN "template_twin_rollout_controls" control
    JOIN "template_twin_release_authorities" authority
      ON authority."id" = ${authorityIds.get(staleDiscipline)!}::UUID
    WHERE candidate."id" = ${release.id}::UUID AND control."id" = 'global'
  `);
  assert.equal(reconciled[0]!.releaseStatus, "REVOKED");
  assert(reconciled[0]!.authorityRevokedAt);
  const unicodeReconciled = await observer.$queryRaw<
    Array<{ authorityRevokedAt: Date | null }>
  >(Prisma.sql`
    SELECT "revokedAt" AS "authorityRevokedAt"
    FROM "template_twin_release_authorities"
    WHERE "id" = ${authorityIds.get(unicodeStaleDiscipline)!}::UUID
  `);
  assert(
    unicodeReconciled[0]!.authorityRevokedAt,
    "install must revoke Unicode-whitespace-only MFA authority",
  );
  assert.equal(reconciled[0]!.globalEnabled, false);
  assert.equal(reconciled[0]!.decisionCount, BigInt(4));
  assert(reconciled[0]!.installAuditCount >= BigInt(1));

  await proveSessionPredicates(sessionCases);
  await proveInstalledFunctionBoundary();

  const installAuditCount = reconciled[0]!.installAuditCount;
  await applyMfaMigration();
  const repeated = await observer.$queryRaw<
    Array<{ installAuditCount: bigint; decisionCount: bigint }>
  >(Prisma.sql`
    SELECT
      (SELECT COUNT(*)::BIGINT FROM "template_twin_audit_outbox" outbox
       WHERE outbox."metadata"->>'reasonCode' =
         'AUTHORITY_MFA_INCOMPLETE_INSTALL') AS "installAuditCount",
      (SELECT COUNT(*)::BIGINT
       FROM "template_twin_release_approval_decisions" decision
       WHERE decision."releaseId" = ${release.id}::UUID) AS "decisionCount"
  `);
  assert.equal(repeated[0]!.installAuditCount, installAuditCount);
  assert.equal(repeated[0]!.decisionCount, BigInt(4));

  await proveLifecycleRevocation();
  return {
    profile: "template-twin-production-control-plane-complete-mfa-v4",
    synthetic: true,
    residualObjectCensus: "zero-before-seed",
    preV4DefectReproduced: true,
    missingSecretRejected: true,
    blankAndWhitespaceSecretRejected: true,
    tabAndNewlineSecretRejected: true,
    unicodeWhitespaceSecretRejected: true,
    missingVerificationRejected: true,
    futureVerificationRejected: true,
    completeCurrentMfaAccepted: true,
    arbitraryNonblankSecretAccepted: true,
    staleApprovalRevokedWithEvidencePreserved: true,
    secretRemovalUnicodeWhitespaceAndRotationRevoked: true,
    definerSearchPathAndGrantsVerified: true,
    rawSecretProjectionRejected: true,
    migrationSqlRepeatIdempotent: true,
    unsafeOutgoingBoundaryMembershipRejected: true,
    inboundTrustedLoginMembershipRejected: true,
    extraLoginMembershipRejected: true,
    membershipSetOptionRejected: true,
    cleanRoleGraphAccepted: true,
  };
}

async function dropDisposableDatabase(): Promise<void> {
  const adminUrl = new URL(verifiedDatabaseUrl);
  adminUrl.pathname = "/postgres";
  const admin = new Client({ connectionString: adminUrl.toString() });
  try {
    await admin.connect();
    await admin.query(
      `SELECT pg_terminate_backend(pid) FROM pg_stat_activity
       WHERE datname = $1 AND pid <> pg_backend_pid()`,
      [databaseName],
    );
    await admin.query(`DROP DATABASE "${databaseName}"`);
    const rows = await admin.query<{ count: string }>(
      "SELECT COUNT(*)::TEXT AS count FROM pg_database WHERE datname = $1",
      [databaseName],
    );
    assert.equal(rows.rows[0]!.count, "0");
  } finally {
    await admin.end().catch(() => undefined);
  }
}

async function run(): Promise<void> {
  let report: Record<string, unknown> | undefined;
  let primaryError: unknown;
  try {
    await loadDatabaseBearingModules();
    report = await main();
  } catch (error) {
    primaryError = error;
  }
  await Promise.allSettled([
    observer.$disconnect(),
    ...(releaseControlDatabase ? [releaseControlDatabase.$disconnect()] : []),
  ]);
  try {
    await dropDisposableDatabase();
  } catch (cleanupError) {
    if (!primaryError) primaryError = cleanupError;
    else {
      process.stderr.write(
        "Disposable complete-MFA database cleanup failed.\n",
      );
    }
  }
  if (primaryError) throw primaryError;
  process.stdout.write(
    `${JSON.stringify({ ...report, cleanup: "exact-test-database-dropped" })}\n`,
  );
}

void run().catch((error: unknown) => {
  process.stderr.write(
    `${error instanceof Error ? (error.stack ?? error.message) : String(error)}\n`,
  );
  process.exitCode = 1;
});
