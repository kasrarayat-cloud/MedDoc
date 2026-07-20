#!/usr/bin/env tsx

// Actual-PostgreSQL proof that a Template Twin source/certification claim and
// a practice static-asset revocation have one database-linearized order. The
// harness imports the production lock/revalidation and revocation helpers,
// uses database-observed lock blocking instead of timing sleeps, and refuses
// any database that is not positively identified as disposable QA/test.

import assert from "node:assert/strict";
import { createHash, createHmac, randomBytes, randomUUID } from "node:crypto";
import { deflateSync } from "node:zlib";

import { PrismaPg } from "@prisma/adapter-pg";
import { Prisma, PrismaClient } from "@prisma/client";

import type {
  TemplateTwinStaticAssetActor,
  TemplateTwinStaticAssetApprovalBinding,
  TemplateTwinStaticAssetClaimDb,
  TemplateTwinStaticAssetDb,
} from "../../../apps/transcribe-md/src/lib/template-twin/static-assets";
import { assertNonProdDatabase } from "../src/db-guard";

type StaticAssetsModule =
  typeof import("../../../apps/transcribe-md/src/lib/template-twin/static-assets");

const databaseUrl =
  process.env.TEMPLATE_TWIN_STATIC_ASSET_TEST_DATABASE_URL ??
  process.env.DATABASE_URL;
assertNonProdDatabase(databaseUrl);
if (!databaseUrl) {
  throw new Error("A disposable static-asset test database URL is required.");
}
const verifiedDatabaseUrl = databaseUrl;
const alternateDatabaseTargets = [
  ["DATABASE_URL", process.env.DATABASE_URL],
  [
    "TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL",
    process.env.TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL,
  ],
  [
    "TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL",
    process.env.TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL,
  ],
] as const;
const divergentDatabaseTarget = alternateDatabaseTargets.find(
  ([, value]) => value && value !== verifiedDatabaseUrl,
);
if (divergentDatabaseTarget) {
  throw new Error(
    `${divergentDatabaseTarget[0]} must exactly match the guarded disposable static-asset test URL.`,
  );
}
process.env.DATABASE_URL = verifiedDatabaseUrl;
process.env.TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL = verifiedDatabaseUrl;
process.env.TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL =
  verifiedDatabaseUrl;
process.env.TEMPLATE_TWIN_KILL_SWITCH = "false";
process.env.TEMPLATE_TWIN_RUNTIME_MODE = "standard";

const staticAssetsModulePromise: Promise<StaticAssetsModule> =
  import("../../../apps/transcribe-md/src/lib/template-twin/static-assets");
let staticAssetsModule: StaticAssetsModule;

const suffix = `${process.pid}-${Date.now()}`;
const practiceId = `synthetic-static-asset-practice-${suffix}`;
const adminId = `synthetic-static-asset-admin-${suffix}`;
const adminEmail = `static-asset-${suffix}@synthetic.test`;
const physicianId = `synthetic-static-asset-physician-${suffix}`;
const releaseAdministratorPracticeId = `synthetic-static-release-admin-practice-${suffix}`;
const releaseCreatorId = `synthetic-static-release-creator-${suffix}`;
const releaseCreatorSession = `synthetic-static-release-session-${suffix}`;
const runtimeKeyId = `synthetic-static-runtime-${suffix}`;
const runtimeSigningSecret = randomBytes(32);
const revokerApplicationName = `tt-static-asset-revoker-${suffix}`;
let assetId = "";
let digest = "";
let inspectionDigest = "";
let privacyDigest = "";
let syntheticPrivacyProviderCalls = 0;
let exactProviderExecutionReuse = false;
let changedBytesDistinctProviderExecution = false;
let whitespaceMfaListDenied = false;
let whitespaceMfaWriteDeniedBeforeProvider = false;
let whitespaceMfaMutationPreservedRelease = false;
let globalRolloutGeneration = BigInt(1);
let practiceRolloutGeneration = BigInt(1);

interface SyntheticReleaseLifecycle {
  readonly releaseId: string;
  readonly releaseIdentitySha256: string;
  readonly actor: { readonly userId: string; readonly sessionId: string };
}

interface SyntheticReleaseAuthority extends SyntheticReleaseLifecycle {
  readonly runtimeManifestSha256: string;
  readonly runtimeInstanceId: string;
  readonly runtimeEnvironment: Readonly<Record<string, string>>;
}

let syntheticReleaseLifecycle: SyntheticReleaseLifecycle | null = null;
let syntheticReleaseAuthority: SyntheticReleaseAuthority | null = null;

interface RawSqlDb {
  $executeRawUnsafe(query: string, ...values: unknown[]): Promise<number>;
}

function client(applicationName: string, assumedRole?: string): PrismaClient {
  const url = new URL(verifiedDatabaseUrl);
  url.searchParams.set("application_name", applicationName);
  if (assumedRole) {
    url.searchParams.set("options", `-c role=${assumedRole}`);
  }
  return new PrismaClient({
    adapter: new PrismaPg({
      connectionString: url.toString(),
      max: 1,
      connectionTimeoutMillis: 10_000,
    }),
  });
}

function latch(): { promise: Promise<void>; release: () => void } {
  let release!: () => void;
  const promise = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { promise, release };
}

const claimant = client(`tt-static-asset-claimant-${suffix}`);
const revoker = client(revokerApplicationName);
const observer = client(`tt-static-asset-observer-${suffix}`);
const runtimeRegistrar = client(
  `tt-static-asset-runtime-${suffix}`,
  "quillmd_runtime",
);

let binding: TemplateTwinStaticAssetApprovalBinding;

function staticAssetActor(): TemplateTwinStaticAssetActor {
  if (!syntheticReleaseAuthority) {
    throw new Error("Synthetic release authority has not been established.");
  }
  return {
    userId: adminId,
    userEmail: adminEmail,
    practiceId,
    role: "ADMIN",
    rolloutToken: {
      practiceId,
      globalGeneration: globalRolloutGeneration,
      practiceGeneration: practiceRolloutGeneration,
      releaseId: syntheticReleaseAuthority.releaseId,
      releaseIdentitySha256: syntheticReleaseAuthority.releaseIdentitySha256,
      runtimeManifestSha256: syntheticReleaseAuthority.runtimeManifestSha256,
      runtimeInstanceId: syntheticReleaseAuthority.runtimeInstanceId,
    },
  };
}

const syntheticOcr = {
  async scan() {
    return {
      local: true as const,
      complete: true as const,
      engineVersion: "synthetic-local-ocr/1.0",
      text: "Synthetic Clinic",
    };
  },
};

const syntheticPrivacyClient = {
  async complete() {
    syntheticPrivacyProviderCalls += 1;
    return { phiFields: [], anyUncertain: false };
  },
};

async function waitUntilRevocationBlocked(): Promise<{
  pid: number;
  waitEvent: string;
}> {
  for (let attempt = 0; attempt < 5_000; attempt += 1) {
    const rows = await observer.$queryRawUnsafe<
      Array<{ pid: number; waitEvent: string | null }>
    >(
      `SELECT pid, wait_event AS "waitEvent"
       FROM pg_stat_activity
       WHERE application_name = $1
         AND wait_event_type = 'Lock'`,
      revokerApplicationName,
    );
    const row = rows[0];
    if (row?.waitEvent) return { pid: row.pid, waitEvent: row.waitEvent };
    await new Promise<void>((resolve) => setImmediate(resolve));
  }
  throw new Error(
    "PostgreSQL never reported static-asset revocation waiting on the final-claim lock.",
  );
}

let directRolloutEnableRejected = false;
let releaseControlActivated = false;
let releaseControlRevoked = false;

function syntheticReleaseEvidence() {
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

function syntheticRuntimeEnvironment(input: {
  readonly releaseIdentitySha256: string;
  readonly instanceId: string;
  readonly component: "APP" | "WORKER";
  readonly imageDigest: string;
}) {
  const evidence = syntheticReleaseEvidence();
  const issuedAtEpochSeconds = Math.floor(Date.now() / 1_000) - 1;
  const expiresAtEpochSeconds = issuedAtEpochSeconds + 3_600;
  const nonce = randomUUID();
  const message = [
    "template-twin-runtime-attestation-v1",
    runtimeKeyId,
    nonce,
    input.releaseIdentitySha256,
    input.instanceId,
    input.component,
    evidence.sourceCommitSha,
    input.imageDigest,
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
    sourceCommitSha: evidence.sourceCommitSha,
    imageDigest: input.imageDigest,
    issuedAtEpochSeconds,
    expiresAtEpochSeconds,
    signature: createHmac("sha256", runtimeSigningSecret)
      .update(message)
      .digest("hex"),
  };
  return {
    envelope,
    env: {
      TEMPLATE_TWIN_KILL_SWITCH: "false",
      TEMPLATE_TWIN_RUNTIME_MODE: "standard",
      TEMPLATE_TWIN_RELEASE_COMMIT_SHA: evidence.sourceCommitSha,
      TEMPLATE_TWIN_APP_IMAGE_DIGEST: evidence.appImageDigest,
      TEMPLATE_TWIN_WORKER_IMAGE_DIGEST: evidence.workerImageDigest,
      TEMPLATE_TWIN_MIGRATOR_IMAGE_DIGEST: evidence.migratorImageDigest,
      QUILLMD_IMAGE_REVISION: evidence.sourceCommitSha,
      QUILLMD_RUNTIME_COMPONENT: input.component,
      TEMPLATE_TWIN_RUNTIME_ATTESTATION: Buffer.from(
        JSON.stringify(envelope),
        "utf8",
      ).toString("base64url"),
    },
  };
}

async function registerSyntheticRuntime(
  input: ReturnType<typeof syntheticRuntimeEnvironment>,
): Promise<void> {
  const envelope = input.envelope;
  const rows = await runtimeRegistrar.$queryRaw<
    Array<{ receiptId: string | null }>
  >(Prisma.sql`
    SELECT template_twin_register_runtime_attestation(
      ${envelope.version}, ${envelope.keyId}, ${envelope.nonce}::UUID,
      ${envelope.releaseIdentitySha256}::CHAR(64), ${envelope.instanceId},
      ${envelope.component}, ${envelope.sourceCommitSha}::CHAR(40),
      ${envelope.imageDigest}, ${envelope.issuedAtEpochSeconds}::BIGINT,
      ${envelope.expiresAtEpochSeconds}::BIGINT,
      ${envelope.signature}::CHAR(64)
    ) AS "receiptId"
  `);
  assert(rows[0]?.receiptId, "Synthetic runtime attestation must be admitted.");
}

async function revokeSyntheticReleaseIfActive(input: {
  readonly lifecycle: SyntheticReleaseLifecycle;
  readonly reasonCode: string;
}): Promise<boolean> {
  const [state] = await observer.$queryRaw<
    Array<{
      releaseStatus: string;
      releaseGeneration: bigint;
      globalGeneration: bigint;
    }>
  >(Prisma.sql`
    SELECT candidate."status" AS "releaseStatus",
      candidate."generation" AS "releaseGeneration",
      control."generation" AS "globalGeneration"
    FROM "template_twin_release_candidates" candidate
    CROSS JOIN "template_twin_rollout_controls" control
    WHERE candidate."id" = ${input.lifecycle.releaseId}::UUID
      AND control."id" = 'global'
  `);
  if (!state || state.releaseStatus !== "ROLLING_OUT") return false;
  const releaseControl =
    await import("../../../apps/transcribe-md/src/lib/template-twin/release-control");
  await releaseControl.revokeTemplateTwinRelease({
    actor: input.lifecycle.actor,
    releaseId: input.lifecycle.releaseId,
    expectedReleaseGeneration: state.releaseGeneration.toString(),
    expectedGlobalGeneration: state.globalGeneration.toString(),
    reasonCode: input.reasonCode,
    confirmation: `REVOKE ${input.lifecycle.releaseIdentitySha256.slice(0, 12)}`,
  });
  const [terminal] = await observer.$queryRaw<
    Array<{
      releaseStatus: string;
      globalEnabled: boolean;
      practiceEnabled: boolean;
    }>
  >(Prisma.sql`
    SELECT candidate."status" AS "releaseStatus",
      control."enabled" AS "globalEnabled",
      practice."templateTwinEnabled" AS "practiceEnabled"
    FROM "template_twin_release_candidates" candidate
    CROSS JOIN "template_twin_rollout_controls" control
    JOIN "practices" practice ON practice."id" = ${practiceId}
    WHERE candidate."id" = ${input.lifecycle.releaseId}::UUID
      AND control."id" = 'global'
  `);
  assert.deepEqual(terminal, {
    releaseStatus: "REVOKED",
    globalEnabled: false,
    practiceEnabled: false,
  });
  return true;
}

async function revokeInterruptedSyntheticRelease(): Promise<void> {
  const candidates = await observer.$queryRaw<
    Array<{
      id: string;
      releaseIdentitySha256: string;
      createdById: string;
    }>
  >(Prisma.sql`
    SELECT "id"::TEXT, "releaseIdentitySha256", "createdById"
    FROM "template_twin_release_candidates"
    WHERE "status" = 'ROLLING_OUT'
      AND "createdById" LIKE 'synthetic-static-release-creator-%'
    ORDER BY "createdAt"
  `);
  assert(
    candidates.length <= 1,
    "Only one interrupted synthetic static-asset release may own rollout.",
  );
  const candidate = candidates[0];
  if (!candidate) return;
  const session = await observer.userSession.findFirst({
    where: {
      userId: candidate.createdById,
      expiresAt: { gt: new Date() },
    },
    select: { sessionToken: true },
    orderBy: { createdAt: "desc" },
  });
  assert(session, "Interrupted synthetic release actor session is required.");
  await revokeSyntheticReleaseIfActive({
    lifecycle: {
      releaseId: candidate.id,
      releaseIdentitySha256: candidate.releaseIdentitySha256,
      actor: {
        userId: candidate.createdById,
        sessionId: session.sessionToken,
      },
    },
    reasonCode: "SYNTHETIC_STATIC_ASSET_PROOF_INTERRUPTED",
  });
}

async function activateSyntheticReleaseControl(): Promise<void> {
  const releaseControl =
    await import("../../../apps/transcribe-md/src/lib/template-twin/release-control");
  const contracts =
    await import("../../../apps/transcribe-md/src/lib/template-twin/release-control-contracts");
  const reviewerIds = new Map<string, string>();
  const reviewerSessions = new Map<string, string>();
  const expiresAt = new Date(Date.now() + 60 * 60 * 1_000);
  await observer.practice.create({
    data: {
      id: releaseAdministratorPracticeId,
      name: "Synthetic static-asset release administration",
      slug: releaseAdministratorPracticeId,
    },
  });
  const administrators = [
    {
      id: releaseCreatorId,
      email: `${releaseCreatorId}@synthetic.test`,
      session: releaseCreatorSession,
      discipline: null,
    },
    ...contracts.TEMPLATE_TWIN_RELEASE_DISCIPLINES.map((discipline) => {
      const id = `synthetic-static-release-reviewer-${discipline.toLowerCase()}-${suffix}`;
      const session = `synthetic-static-release-reviewer-session-${discipline.toLowerCase()}-${suffix}`;
      reviewerIds.set(discipline, id);
      reviewerSessions.set(discipline, session);
      return {
        id,
        email: `${id}@synthetic.test`,
        session,
        discipline,
      };
    }),
  ];
  for (const administrator of administrators) {
    await observer.user.create({
      data: {
        id: administrator.id,
        email: administrator.email,
        passwordHash: "synthetic-not-a-login-credential",
        role: "ADMIN",
        products: ["SUPER_ADMIN"],
        practiceId: releaseAdministratorPracticeId,
        mfaEnabled: true,
        mfaSecret: "SYNTHETIC-STATIC-ASSET-RELEASE-MFA",
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
    if (administrator.discipline) {
      await observer.$executeRaw(Prisma.sql`
        INSERT INTO "template_twin_release_authorities" (
          "id", "userId", "discipline", "sourceRef"
        ) VALUES (
          ${randomUUID()}::UUID, ${administrator.id},
          ${administrator.discipline},
          ${`synthetic-static-asset-pg/${administrator.discipline.toLowerCase()}`}
        )
      `);
    }
  }
  await observer.$executeRaw(Prisma.sql`
    INSERT INTO "template_twin_release_attestation_keys" (
      "keyId", "purpose", "secret", "principalUserId",
      "effectiveAt", "expiresAt"
    ) VALUES (
      ${runtimeKeyId}, 'RUNTIME', ${runtimeSigningSecret}, NULL,
      clock_timestamp() - interval '1 minute',
      clock_timestamp() + interval '2 hours'
    )
  `);

  const evidence = syntheticReleaseEvidence();
  const criticalMetrics = new Set([
    "unsafe_bypass_attempt_count",
    "provider_ambiguous_outcome_count",
    "critical_field_accuracy",
    "hallucination_rate",
    "evidence_anchor_validity",
    "exact_dropdown_accuracy",
    "negation_accuracy",
    "laterality_accuracy",
    "table_placement_accuracy",
  ]);
  const guardrailPolicy = {
    schemaVersion: "template-twin-guardrails-v1" as const,
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
      Object.entries(contracts.TEMPLATE_TWIN_METRIC_DEFINITIONS).map(
        ([key, definition]) => [
          key,
          {
            direction: definition.direction,
            threshold:
              definition.direction === "MAX" ? definition.min : definition.max,
            critical: criticalMetrics.has(key),
          },
        ],
      ),
    ),
  };
  const appInstanceId = `static-asset-app-${suffix}`;
  const workerInstanceId = `static-asset-worker-${suffix}`;
  const releaseActor = {
    userId: releaseCreatorId,
    sessionId: releaseCreatorSession,
  };
  const created = await releaseControl.createTemplateTwinReleaseCandidate({
    actor: releaseActor,
    confirmation: "CREATE EXACT RELEASE",
    evidence,
    guardrailPolicy,
    authorizedPracticeIds: [practiceId],
    canaryPracticeIds: [practiceId],
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
  syntheticReleaseLifecycle = {
    releaseId: created.releaseId,
    releaseIdentitySha256: created.releaseIdentitySha256,
    actor: releaseActor,
  };
  let releaseGeneration = (
    await releaseControl.freezeTemplateTwinReleaseCandidate({
      actor: releaseActor,
      releaseId: created.releaseId,
      expectedReleaseGeneration: created.generation,
      confirmation: `FREEZE ${created.releaseIdentitySha256.slice(0, 12)}`,
    })
  ).generation;
  for (const [
    index,
    discipline,
  ] of contracts.TEMPLATE_TWIN_RELEASE_DISCIPLINES.entries()) {
    const decision = await releaseControl.recordTemplateTwinReleaseApproval({
      actor: {
        userId: reviewerIds.get(discipline)!,
        sessionId: reviewerSessions.get(discipline)!,
      },
      releaseId: created.releaseId,
      expectedReleaseGeneration: releaseGeneration,
      discipline,
      decision: "APPROVE",
      evidenceSha256: String(index + 6).repeat(64),
      confirmation: contracts.templateTwinApprovalConfirmation({
        decision: "APPROVE",
        discipline,
        releaseIdentitySha256: created.releaseIdentitySha256,
      }),
    });
    releaseGeneration = decision.generation;
  }

  const appRuntime = syntheticRuntimeEnvironment({
    releaseIdentitySha256: created.releaseIdentitySha256,
    instanceId: appInstanceId,
    component: "APP",
    imageDigest: evidence.appImageDigest,
  });
  const workerRuntime = syntheticRuntimeEnvironment({
    releaseIdentitySha256: created.releaseIdentitySha256,
    instanceId: workerInstanceId,
    component: "WORKER",
    imageDigest: evidence.workerImageDigest,
  });
  await registerSyntheticRuntime(appRuntime);
  await registerSyntheticRuntime(workerRuntime);
  const [globalBefore] = await observer.$queryRaw<
    Array<{ generation: bigint }>
  >(Prisma.sql`
    SELECT "generation" FROM "template_twin_rollout_controls"
    WHERE "id" = 'global'
  `);
  assert(globalBefore, "Synthetic global rollout control is required.");
  await releaseControl.activateTemplateTwinReleaseCheckpoint({
    actor: releaseActor,
    releaseId: created.releaseId,
    stage: "CANARY",
    expectedReleaseGeneration: releaseGeneration,
    expectedGlobalGeneration: globalBefore.generation.toString(),
    confirmation: contracts.templateTwinCheckpointConfirmation({
      verb: "ACTIVATE",
      stage: "CANARY",
      releaseIdentitySha256: created.releaseIdentitySha256,
    }),
    env: appRuntime.env,
  });
  const [current] = await observer.$queryRaw<
    Array<{
      releaseStatus: string;
      releaseIdentitySha256: string;
      runtimeManifestSha256: string;
      globalEnabled: boolean;
      practiceEnabled: boolean;
      globalGeneration: bigint;
      practiceGeneration: bigint;
    }>
  >(Prisma.sql`
    SELECT candidate."status" AS "releaseStatus",
      candidate."releaseIdentitySha256", candidate."runtimeManifestSha256",
      control."enabled" AS "globalEnabled",
      practice."templateTwinEnabled" AS "practiceEnabled",
      control."generation" AS "globalGeneration",
      practice."templateTwinRolloutGeneration" AS "practiceGeneration"
    FROM "template_twin_release_candidates" candidate
    CROSS JOIN "template_twin_rollout_controls" control
    JOIN "practices" practice ON practice."id" = ${practiceId}
    WHERE candidate."id" = ${created.releaseId}::UUID
      AND control."id" = 'global'
  `);
  assert(current, "Activated synthetic release state is required.");
  assert.equal(current.releaseStatus, "ROLLING_OUT");
  assert.equal(current.globalEnabled, true);
  assert.equal(current.practiceEnabled, true);
  globalRolloutGeneration = current.globalGeneration;
  practiceRolloutGeneration = current.practiceGeneration;
  syntheticReleaseAuthority = {
    ...syntheticReleaseLifecycle,
    runtimeManifestSha256: current.runtimeManifestSha256,
    runtimeInstanceId: appInstanceId,
    runtimeEnvironment: appRuntime.env,
  };
  Object.assign(process.env, appRuntime.env);
  releaseControlActivated = true;
}

async function createSyntheticFixture(): Promise<void> {
  const lineage = await observer.$queryRawUnsafe<Array<{ phase: string }>>(
    `SELECT "phase"
     FROM "template_twin_lineage_migration_progress"
     WHERE "operationKey" = 'note_templates_lineage_v1'`,
  );
  if (lineage[0]?.phase !== "CONTRACTED") {
    throw new Error(
      "Disposable QA lineage must be CONTRACTED before static-asset proof.",
    );
  }
  await observer.practice.create({
    data: {
      id: practiceId,
      name: "Synthetic static asset concurrency practice",
      slug: practiceId,
    },
  });
  await observer.user.create({
    data: {
      id: adminId,
      email: adminEmail,
      passwordHash: "synthetic-not-a-login-credential",
      role: "ADMIN",
      products: ["TRANSCRIBE_MD"],
      practiceId,
    },
  });
  await observer.user.create({
    data: {
      id: physicianId,
      email: `${physicianId}@synthetic.test`,
      passwordHash: "synthetic-not-a-login-credential",
      role: "DOCTOR",
      products: ["TRANSCRIBE_MD"],
      practiceId,
    },
  });
  await expectDatabaseRejection(
    "direct rollout enable without release capability",
    /production enablement requires an active release capability/u,
    () =>
      observer.templateTwinRolloutControl.update({
        where: { id: "global" },
        data: { enabled: true, generation: { increment: 1 } },
      }),
  );
  directRolloutEnableRejected = true;
  await activateSyntheticReleaseControl();
  await observer.user.update({
    where: { id: adminId },
    data: {
      products: { set: ["TRANSCRIBE_MD", "SUPER_ADMIN"] },
      mfaEnabled: true,
      mfaSecret: "\u00a0\u2007\u202f\ufeff",
      mfaVerifiedAt: new Date(),
    },
  });
  const providerCallsBeforeWhitespaceProof = syntheticPrivacyProviderCalls;
  const whitespaceMfaBytes = syntheticPng(0x5f);
  const whitespaceMfaSubjectSha256 = createHash("sha256")
    .update(whitespaceMfaBytes)
    .digest("hex");
  try {
    await staticAssetsModule.listTemplateTwinStaticAssetsForPractice({
      actor: staticAssetActor(),
      db: observer as unknown as TemplateTwinStaticAssetDb,
    });
  } catch (error) {
    whitespaceMfaListDenied =
      typeof error === "object" &&
      error !== null &&
      "code" in error &&
      error.code === "TT_STATIC_ASSET_ADMIN_REQUIRED";
  }
  try {
    await staticAssetsModule.inspectTemplateTwinStaticAssetForReview({
      bytes: whitespaceMfaBytes,
      claimedMimeType: "image/png",
      actor: staticAssetActor(),
      ocr: syntheticOcr,
      client: syntheticPrivacyClient,
      db: observer as unknown as TemplateTwinStaticAssetDb,
    });
  } catch (error) {
    whitespaceMfaWriteDeniedBeforeProvider =
      typeof error === "object" &&
      error !== null &&
      "code" in error &&
      error.code === "TT_STATIC_ASSET_ADMIN_REQUIRED";
  }
  assert.equal(whitespaceMfaListDenied, true);
  assert.equal(whitespaceMfaWriteDeniedBeforeProvider, true);
  assert.equal(
    syntheticPrivacyProviderCalls,
    providerCallsBeforeWhitespaceProof,
    "Unicode-whitespace-only platform MFA must deny before provider egress.",
  );
  await observer.user.update({
    where: { id: adminId },
    data: {
      products: { set: ["TRANSCRIBE_MD"] },
      mfaEnabled: false,
      mfaSecret: null,
      mfaVerifiedAt: null,
    },
  });
  assert(syntheticReleaseLifecycle, "Synthetic release lifecycle is required.");
  const [releaseAfterMfaMutation] = await observer.$queryRaw<
    Array<{
      releaseStatus: string;
      globalEnabled: boolean;
      practiceEnabled: boolean;
      globalGeneration: bigint;
      practiceGeneration: bigint;
    }>
  >(Prisma.sql`
    SELECT candidate."status" AS "releaseStatus",
      control."enabled" AS "globalEnabled",
      practice."templateTwinEnabled" AS "practiceEnabled",
      control."generation" AS "globalGeneration",
      practice."templateTwinRolloutGeneration" AS "practiceGeneration"
    FROM "template_twin_release_candidates" candidate
    CROSS JOIN "template_twin_rollout_controls" control
    JOIN "practices" practice ON practice."id" = ${practiceId}
    WHERE candidate."id" = ${syntheticReleaseLifecycle.releaseId}::UUID
      AND control."id" = 'global'
  `);
  assert.deepEqual(releaseAfterMfaMutation, {
    releaseStatus: "ROLLING_OUT",
    globalEnabled: true,
    practiceEnabled: true,
    globalGeneration: globalRolloutGeneration,
    practiceGeneration: practiceRolloutGeneration,
  });
  whitespaceMfaMutationPreservedRelease = true;
  const bytes = syntheticPng();
  const review =
    await staticAssetsModule.inspectTemplateTwinStaticAssetForReview({
      bytes,
      claimedMimeType: "image/png",
      actor: staticAssetActor(),
      ocr: syntheticOcr,
      client: syntheticPrivacyClient,
      db: observer as unknown as TemplateTwinStaticAssetDb,
    });
  const reviewReceiptId = review.previewReviewReceipt.split(".")[0]!;
  const beforeApproval =
    await observer.templateTwinStaticAssetReviewReceipt.findUniqueOrThrow({
      where: { id: reviewReceiptId },
      select: { consumedAt: true },
    });
  if (beforeApproval.consumedAt !== null) {
    throw new Error("Production inspection persisted a pre-consumed receipt.");
  }
  binding = await staticAssetsModule.approveTemplateTwinStaticAsset({
    bytes,
    claimedMimeType: "image/png",
    actor: staticAssetActor(),
    ocr: syntheticOcr,
    client: syntheticPrivacyClient,
    previewReviewReceipt: review.previewReviewReceipt,
    expectedSha256: review.evidence.sha256,
    attestedReusableBlankAsset: true,
    reason: "Synthetic reusable blank image approval.",
    db: observer as unknown as TemplateTwinStaticAssetDb,
  });
  assetId = binding.assetId;
  digest = binding.sha256;
  inspectionDigest = binding.inspectionEvidenceSha256;
  privacyDigest = binding.privacyEvidenceSha256;
  const afterApproval =
    await observer.templateTwinStaticAssetReviewReceipt.findUniqueOrThrow({
      where: { id: reviewReceiptId },
      select: { consumedAt: true, expiresAt: true },
    });
  if (
    afterApproval.consumedAt === null ||
    afterApproval.consumedAt > afterApproval.expiresAt
  ) {
    throw new Error("Production approval did not consume a valid receipt.");
  }

  const repeatReview =
    await staticAssetsModule.inspectTemplateTwinStaticAssetForReview({
      bytes,
      claimedMimeType: "image/png",
      actor: staticAssetActor(),
      ocr: syntheticOcr,
      client: syntheticPrivacyClient,
      db: observer as unknown as TemplateTwinStaticAssetDb,
    });
  const repeatReceiptId = repeatReview.previewReviewReceipt.split(".")[0]!;
  binding = await staticAssetsModule.approveTemplateTwinStaticAsset({
    bytes,
    claimedMimeType: "image/png",
    actor: staticAssetActor(),
    ocr: syntheticOcr,
    client: syntheticPrivacyClient,
    previewReviewReceipt: repeatReview.previewReviewReceipt,
    expectedSha256: repeatReview.evidence.sha256,
    attestedReusableBlankAsset: true,
    reason: "Synthetic repeat approval records a fresh decision.",
    db: observer as unknown as TemplateTwinStaticAssetDb,
  });
  const repeatReceipt =
    await observer.templateTwinStaticAssetReviewReceipt.findUniqueOrThrow({
      where: { id: repeatReceiptId },
      select: { consumedAt: true, expiresAt: true },
    });
  if (
    binding.decisionVersion !== 2 ||
    repeatReceipt.consumedAt === null ||
    repeatReceipt.consumedAt > repeatReceipt.expiresAt
  ) {
    throw new Error(
      "A repeat production approval did not append a decision and consume its fresh receipt.",
    );
  }

  const changedBytes = syntheticPng(0x6f);
  const changedReview =
    await staticAssetsModule.inspectTemplateTwinStaticAssetForReview({
      bytes: changedBytes,
      claimedMimeType: "image/png",
      actor: staticAssetActor(),
      ocr: syntheticOcr,
      client: syntheticPrivacyClient,
      db: observer as unknown as TemplateTwinStaticAssetDb,
    });
  if (changedReview.evidence.sha256 === digest) {
    throw new Error(
      "Changed synthetic bytes reused the original subject hash.",
    );
  }
  const executions = await observer.$queryRaw<
    Array<{
      subjectSha256: string;
      operationInstance: string;
      status: string;
      invocationCount: number;
      resultSha256: string | null;
      failureCode: string | null;
    }>
  >(Prisma.sql`
    SELECT "subjectSha256", "operationInstance", "status",
      "invocationCount", "resultSha256", "failureCode"
    FROM "template_twin_provider_executions"
    WHERE "practiceId" = ${practiceId}
      AND "actorUserId" = ${adminId}
      AND "scope" = 'STATIC_ASSET'
      AND "operation" = 'STATIC_ASSET_PRIVACY_SCAN'
    ORDER BY "subjectSha256"
  `);
  const originalExecutions = executions.filter(
    (execution) => execution.subjectSha256 === digest,
  );
  const changedExecutions = executions.filter(
    (execution) => execution.subjectSha256 === changedReview.evidence.sha256,
  );
  const whitespaceMfaExecutions = executions.filter(
    (execution) => execution.subjectSha256 === whitespaceMfaSubjectSha256,
  );
  const successfulExecutions = [...originalExecutions, ...changedExecutions];
  if (
    syntheticPrivacyProviderCalls !== 2 ||
    originalExecutions.length !== 1 ||
    changedExecutions.length !== 1 ||
    whitespaceMfaExecutions.length !== 1 ||
    whitespaceMfaExecutions[0]?.operationInstance !== "primary" ||
    whitespaceMfaExecutions[0]?.status !== "FAILED" ||
    whitespaceMfaExecutions[0]?.invocationCount !== 0 ||
    whitespaceMfaExecutions[0]?.resultSha256 !== null ||
    whitespaceMfaExecutions[0]?.failureCode !==
      "AUTHORITY_REVOKED_BEFORE_PROVIDER" ||
    successfulExecutions.some(
      (execution) =>
        execution.operationInstance !== "primary" ||
        execution.status !== "SUCCEEDED" ||
        execution.invocationCount !== 1 ||
        !execution.resultSha256,
    )
  ) {
    throw new Error(
      "Static-asset provider execution reuse did not remain exact and subject-bound.",
    );
  }
  exactProviderExecutionReuse = true;
  changedBytesDistinctProviderExecution = true;
}

function syntheticPng(fillByte = 0x7f): Uint8Array {
  const width = 2;
  const height = 2;
  const ihdr = new Uint8Array(13);
  writeU32(ihdr, 0, width);
  writeU32(ihdr, 4, height);
  ihdr.set([8, 6, 0, 0, 0], 8);
  const scanlines = new Uint8Array((width * 4 + 1) * height);
  for (let row = 0; row < height; row += 1) {
    scanlines[row * (width * 4 + 1)] = 0;
    scanlines.fill(
      fillByte,
      row * (width * 4 + 1) + 1,
      (row + 1) * (width * 4 + 1),
    );
  }
  return concat(
    Uint8Array.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    pngChunk("IHDR", ihdr),
    pngChunk("IDAT", deflateSync(scanlines)),
    pngChunk("IEND", new Uint8Array()),
  );
}

function pngChunk(type: string, data: Uint8Array): Uint8Array {
  const typeBytes = new TextEncoder().encode(type);
  const output = new Uint8Array(12 + data.byteLength);
  writeU32(output, 0, data.byteLength);
  output.set(typeBytes, 4);
  output.set(data, 8);
  writeU32(output, 8 + data.byteLength, crc32(concat(typeBytes, data)));
  return output;
}

function concat(...values: Uint8Array[]): Uint8Array {
  const output = new Uint8Array(
    values.reduce((total, value) => total + value.byteLength, 0),
  );
  let offset = 0;
  for (const value of values) {
    output.set(value, offset);
    offset += value.byteLength;
  }
  return output;
}

function writeU32(bytes: Uint8Array, offset: number, value: number): void {
  bytes[offset] = (value >>> 24) & 0xff;
  bytes[offset + 1] = (value >>> 16) & 0xff;
  bytes[offset + 2] = (value >>> 8) & 0xff;
  bytes[offset + 3] = value & 0xff;
}

function crc32(bytes: Uint8Array): number {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

async function expectDatabaseRejection(
  label: string,
  expectedCode: RegExp,
  operation: () => Promise<unknown>,
): Promise<string> {
  try {
    await operation();
  } catch (error) {
    const text = error instanceof Error ? error.message : String(error);
    if (expectedCode.test(text)) return label;
    throw new Error(`${label} failed with the wrong database error: ${text}`);
  }
  throw new Error(`${label} unexpectedly passed.`);
}

async function insertRawReceipt(
  input: {
    id: string;
    inspectionEvidenceSha256?: string;
    scannerVersion?: string;
    ocrEngineVersion?: string;
    privacyEvidenceSha256?: string;
    globalGeneration?: bigint;
    practiceGeneration?: bigint;
    expiresSql?: string;
    consumedSql?: string;
  },
  db: RawSqlDb = observer as unknown as RawSqlDb,
): Promise<void> {
  const expiresSql =
    input.expiresSql ?? "CURRENT_TIMESTAMP + INTERVAL '10 minutes'";
  const consumedSql = input.consumedSql ?? "NULL";
  await db.$executeRawUnsafe(
    `INSERT INTO "template_twin_static_asset_review_receipts" (
       "id", "practiceId", "reviewedById", "tokenSha256", "assetSha256",
       "inspectionEvidenceSha256", "scannerVersion", "ocrEngineVersion",
       "privacyEvidenceSha256", "globalRolloutGeneration",
       "practiceRolloutGeneration", "expiresAt", "consumedAt"
     ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,${expiresSql},${consumedSql})`,
    input.id,
    practiceId,
    adminId,
    createHash("sha256").update(input.id).digest("hex"),
    digest,
    input.inspectionEvidenceSha256 ?? inspectionDigest,
    input.scannerVersion ??
      staticAssetsModule.TEMPLATE_TWIN_STATIC_ASSET_SCANNER,
    input.ocrEngineVersion ?? "synthetic-local-ocr/1.0",
    input.privacyEvidenceSha256 ?? privacyDigest,
    input.globalGeneration ?? globalRolloutGeneration,
    input.practiceGeneration ?? practiceRolloutGeneration,
  );
}

async function consumeRawReceipt(
  id: string,
  db: RawSqlDb = observer as unknown as RawSqlDb,
): Promise<void> {
  const count = await db.$executeRawUnsafe(
    `UPDATE "template_twin_static_asset_review_receipts"
     SET "consumedAt" = CURRENT_TIMESTAMP WHERE "id" = $1`,
    id,
  );
  if (count !== 1) throw new Error(`Receipt ${id} was not consumed once.`);
}

function rawApprovalIdentity(label: string): {
  decisionId: string;
  auditEventKey: string;
} {
  const decisionId = `synthetic-adversarial-decision-${label}-${suffix}`;
  return {
    decisionId,
    auditEventKey: `template-twin:static-asset-approved:${decisionId}`,
  };
}

async function insertRawApprovalAudit(
  label: string,
  options: {
    action?: string;
    practiceId?: string;
    actorId?: string;
    targetId?: string;
    metadataDecisionId?: string;
  } = {},
  db: RawSqlDb = observer as unknown as RawSqlDb,
): Promise<void> {
  const identity = rawApprovalIdentity(label);
  await db.$executeRawUnsafe(
    `INSERT INTO "template_twin_audit_outbox" (
       "id", "practiceId", "actorId", "actorEmailSnapshot", "eventKey",
       "action", "targetId", "targetType", "metadata", "status", "attemptCount",
       "updatedAt"
     ) VALUES ($1,$2,$3,$4,$5,$6::"AuditAction",$7,'TemplateTwinStaticAsset',$8::jsonb,'PENDING',0,CURRENT_TIMESTAMP)`,
    `synthetic-adversarial-audit-${label}-${suffix}`,
    options.practiceId ?? practiceId,
    options.actorId ?? adminId,
    adminEmail,
    identity.auditEventKey,
    options.action ?? "TEMPLATE_TWIN_STATIC_ASSET_APPROVED",
    options.targetId ?? assetId,
    JSON.stringify({
      decisionId: options.metadataDecisionId ?? identity.decisionId,
      synthetic: true,
    }),
  );
}

async function attemptRawApproval(
  receiptId: string,
  label: string,
  db: RawSqlDb = observer as unknown as RawSqlDb,
): Promise<string> {
  const identity = rawApprovalIdentity(label);
  await db.$executeRawUnsafe(
    `INSERT INTO "template_twin_static_asset_decisions" (
       "id", "assetId", "version", "decision", "reason",
       "attestedReusableBlankAsset", "inspectionEvidenceSha256",
       "reviewReceiptId", "auditEventKey", "decidedById"
     ) VALUES ($1,$2,$3,'APPROVED',$4,true,$5,$6,$7,$8)`,
    identity.decisionId,
    assetId,
    binding.decisionVersion + 1,
    "Synthetic direct database approval proof.",
    inspectionDigest,
    receiptId,
    identity.auditEventKey,
    adminId,
  );
  return identity.decisionId;
}

async function runReceiptAdversarialProofs(): Promise<string[]> {
  const rejected: string[] = [];
  const preConsumedId = `synthetic-preconsumed-${suffix}`;
  rejected.push(
    await expectDatabaseRejection(
      "pre-consumed receipt insert",
      /TT_STATIC_ASSET_PREVIEW_RECEIPT_INVALID/,
      () =>
        insertRawReceipt({
          id: preConsumedId,
          consumedSql: "CURRENT_TIMESTAMP",
        }),
    ),
  );
  rejected.push(
    await expectDatabaseRejection(
      "expired receipt insert",
      /TT_STATIC_ASSET_PREVIEW_RECEIPT_INVALID/,
      () =>
        insertRawReceipt({
          id: `synthetic-expired-${suffix}`,
          expiresSql: "CURRENT_TIMESTAMP - INTERVAL '1 second'",
        }),
    ),
  );
  rejected.push(
    await expectDatabaseRejection(
      "stale global rollout generation receipt",
      /TT_STATIC_ASSET_ROLLOUT_STALE/,
      () =>
        insertRawReceipt({
          id: `synthetic-generation-${suffix}`,
          globalGeneration: globalRolloutGeneration + BigInt(1),
        }),
    ),
  );
  rejected.push(
    await expectDatabaseRejection(
      "stale practice rollout generation receipt",
      /TT_STATIC_ASSET_ROLLOUT_STALE/,
      () =>
        insertRawReceipt({
          id: `synthetic-practice-generation-${suffix}`,
          practiceGeneration: practiceRolloutGeneration + BigInt(1),
        }),
    ),
  );

  const replayId = `synthetic-replay-${suffix}`;
  await insertRawReceipt({ id: replayId });
  await consumeRawReceipt(replayId);
  rejected.push(
    await expectDatabaseRejection(
      "second receipt consumption",
      /TEMPLATE_TWIN_STATIC_ASSET_REVIEW_RECEIPT_IMMUTABLE/,
      () => consumeRawReceipt(replayId),
    ),
  );

  const missingOutboxReceiptId = `synthetic-missing-outbox-${suffix}`;
  await insertRawReceipt({ id: missingOutboxReceiptId });
  await consumeRawReceipt(missingOutboxReceiptId);
  rejected.push(
    await expectDatabaseRejection(
      "decision without audit outbox",
      /TT_STATIC_ASSET_AUDIT_OUTBOX_INVALID/,
      () => attemptRawApproval(missingOutboxReceiptId, "missing-outbox"),
    ),
  );

  rejected.push(
    await expectDatabaseRejection(
      "decision with mismatched audit outbox",
      /TT_STATIC_ASSET_AUDIT_OUTBOX_INVALID/,
      () =>
        observer.$transaction(async (tx) => {
          const db = tx as unknown as RawSqlDb;
          const id = `synthetic-mismatched-outbox-${suffix}`;
          await insertRawReceipt({ id }, db);
          await consumeRawReceipt(id, db);
          await insertRawApprovalAudit(
            "mismatched-outbox",
            { action: "TEMPLATE_TWIN_STATIC_ASSET_REJECTED" },
            db,
          );
          await attemptRawApproval(id, "mismatched-outbox", db);
        }),
    ),
  );

  const mismatches = [
    {
      label: "wrong inspection evidence",
      receipt: { inspectionEvidenceSha256: "1".repeat(64) },
    },
    {
      label: "wrong scanner version",
      receipt: { scannerVersion: "synthetic-wrong-scanner/1.0" },
    },
    {
      label: "wrong OCR version",
      receipt: { ocrEngineVersion: "synthetic-wrong-ocr/1.0" },
    },
    {
      label: "wrong privacy evidence",
      receipt: { privacyEvidenceSha256: "2".repeat(64) },
    },
  ] as const;
  for (const [index, mismatch] of mismatches.entries()) {
    rejected.push(
      await expectDatabaseRejection(
        mismatch.label,
        /TT_STATIC_ASSET_PREVIEW_RECEIPT_INVALID/,
        () =>
          observer.$transaction(async (tx) => {
            const db = tx as unknown as RawSqlDb;
            const id = `synthetic-mismatch-${index}-${suffix}`;
            const label = `receipt-mismatch-${index}`;
            await insertRawReceipt({ id, ...mismatch.receipt }, db);
            await consumeRawReceipt(id, db);
            await insertRawApprovalAudit(label, {}, db);
            await attemptRawApproval(id, label, db);
          }),
      ),
    );
  }
  return rejected;
}

async function proveSelfConsistentDirectSqlApproval(): Promise<string> {
  const label = "self-consistent";
  const receiptId = `synthetic-self-consistent-${suffix}`;
  await insertRawReceipt({ id: receiptId });
  await consumeRawReceipt(receiptId);
  await insertRawApprovalAudit(label);
  const decisionId = await attemptRawApproval(receiptId, label);
  const [proof] = await observer.$queryRawUnsafe<
    Array<{
      decisionId: string;
      auditEventKey: string;
      action: string;
      status: string;
    }>
  >(
    `SELECT decision."id" AS "decisionId",
            decision."auditEventKey" AS "auditEventKey",
            outbox."action"::text AS "action",
            outbox."status"::text AS "status"
     FROM "template_twin_static_asset_decisions" decision
     JOIN "template_twin_audit_outbox" outbox
       ON outbox."eventKey" = decision."auditEventKey"
     WHERE decision."id" = $1`,
    decisionId,
  );
  if (
    proof?.decisionId !== decisionId ||
    proof.auditEventKey !== rawApprovalIdentity(label).auditEventKey ||
    proof.action !== "TEMPLATE_TWIN_STATIC_ASSET_APPROVED" ||
    proof.status !== "PENDING"
  ) {
    throw new Error(
      "A self-consistent direct database decision did not retain its durable audit identity.",
    );
  }
  binding = {
    ...binding,
    decisionId,
    decisionVersion: binding.decisionVersion + 1,
  };
  return decisionId;
}

async function main(): Promise<void> {
  staticAssetsModule = await staticAssetsModulePromise;
  await revokeInterruptedSyntheticRelease();
  await createSyntheticFixture();
  const directSqlReceiptRejections = await runReceiptAdversarialProofs();
  const directSqlAuditedDecisionId =
    await proveSelfConsistentDirectSqlApproval();

  const claimHasLocked = latch();
  const releaseClaim = latch();
  const commitOrder: string[] = [];

  const claim = claimant
    .$transaction(
      async (tx) => {
        await staticAssetsModule.lockAndAssertTemplateTwinStaticAssetBindingsCurrent(
          {
            practiceId,
            bindings: [binding],
            db: tx as unknown as TemplateTwinStaticAssetClaimDb,
          },
        );
        claimHasLocked.release();
        await releaseClaim.promise;
      },
      { isolationLevel: "Serializable" },
    )
    .then(() => {
      commitOrder.push("claim");
    });

  await claimHasLocked.promise;
  const revocation = staticAssetsModule
    .revokeTemplateTwinStaticAsset({
      practiceId,
      sha256: digest,
      actor: staticAssetActor(),
      reason: "Synthetic concurrent revocation proof.",
      db: revoker as unknown as TemplateTwinStaticAssetDb,
    })
    .then(() => {
      commitOrder.push("revocation");
    });

  const blocked = await waitUntilRevocationBlocked();
  releaseClaim.release();
  await Promise.all([claim, revocation]);

  if (commitOrder.join(",") !== "claim,revocation") {
    throw new Error(
      `Unexpected static-asset linearization order: ${commitOrder.join(",")}`,
    );
  }

  let staleClaimCode: string | null = null;
  try {
    await claimant.$transaction(
      (tx) =>
        staticAssetsModule.lockAndAssertTemplateTwinStaticAssetBindingsCurrent({
          practiceId,
          bindings: [binding],
          db: tx as unknown as TemplateTwinStaticAssetClaimDb,
        }),
      { isolationLevel: "Serializable" },
    );
  } catch (error) {
    staleClaimCode =
      typeof error === "object" && error !== null && "code" in error
        ? String((error as { code: unknown }).code)
        : null;
  }
  if (staleClaimCode !== "TT_STATIC_ASSET_NOT_APPROVED") {
    throw new Error(
      `A post-revocation claim did not fail closed (code=${staleClaimCode ?? "none"}).`,
    );
  }

  const [asset, approvalAuditCount, revocationAuditCount] = await Promise.all([
    observer.templateTwinStaticAsset.findUniqueOrThrow({
      where: { id: assetId },
      select: { currentStatus: true, currentDecisionVersion: true },
    }),
    observer.templateTwinAuditOutbox.count({
      where: {
        action: "TEMPLATE_TWIN_STATIC_ASSET_APPROVED",
        targetId: assetId,
        status: "PENDING",
      },
    }),
    observer.templateTwinAuditOutbox.count({
      where: {
        action: "TEMPLATE_TWIN_STATIC_ASSET_REVOKED",
        targetId: assetId,
        status: "PENDING",
      },
    }),
  ]);
  if (
    asset.currentStatus !== "REVOKED" ||
    asset.currentDecisionVersion !== 4 ||
    approvalAuditCount !== 3 ||
    revocationAuditCount !== 1
  ) {
    throw new Error("Revocation state and durable audit evidence diverged.");
  }

  assert(syntheticReleaseLifecycle, "Synthetic release lifecycle is required.");
  releaseControlRevoked = await revokeSyntheticReleaseIfActive({
    lifecycle: syntheticReleaseLifecycle,
    reasonCode: "SYNTHETIC_STATIC_ASSET_PROOF_COMPLETE",
  });
  assert.equal(releaseControlRevoked, true);

  process.stdout.write(
    `${JSON.stringify({
      verdict: "PASS",
      profile: "template-twin-static-asset-receipt-and-revocation-postgres-v2",
      synthetic: true,
      databaseGuard: "passed",
      productionHelpersExercised: [
        "createTemplateTwinReleaseCandidate",
        "freezeTemplateTwinReleaseCandidate",
        "recordTemplateTwinReleaseApproval",
        "activateTemplateTwinReleaseCheckpoint",
        "lockAndAssertTemplateTwinStaticAssetBindingsCurrent",
        "inspectTemplateTwinStaticAssetForReview",
        "approveTemplateTwinStaticAsset",
        "revokeTemplateTwinStaticAsset",
        "revokeTemplateTwinRelease",
      ],
      directRolloutEnableRejected,
      releaseControlActivated,
      releaseControlRevoked,
      rolloutCleanup: "revoked-via-release-control",
      signedRuntimeReplicaBarrier: true,
      releaseCapabilityBypassUsed: false,
      exactProviderExecutionReuse,
      changedBytesDistinctProviderExecution,
      whitespaceMfaListDenied,
      whitespaceMfaWriteDeniedBeforeProvider,
      unicodeWhitespaceMfaRejectedBeforeProvider:
        whitespaceMfaListDenied && whitespaceMfaWriteDeniedBeforeProvider,
      whitespaceMfaMutationPreservedRelease,
      syntheticPrivacyProviderCalls,
      productionLikeReceiptFlow: true,
      directSqlReceiptRejections,
      durableApprovalAudit: approvalAuditCount === 3,
      repeatApprovalDecisionRecorded: true,
      directSqlDecisionAuditBound: directSqlAuditedDecisionId.length > 0,
      previewAuthenticityBoundary:
        "application bearer-secret verification plus least-privilege database writers; a privileged direct database writer can synthesize self-consistent receipt evidence but cannot create an unaudited decision",
      databaseObservedBlocking: true,
      blockedWaitEvent: blocked.waitEvent,
      linearizationOrder: commitOrder,
      postRevocationClaimCode: staleClaimCode,
      finalStatus: asset.currentStatus,
      decisionVersion: asset.currentDecisionVersion,
      durableRevocationAudit: revocationAuditCount === 1,
      fixtureLifecycle:
        "retained only in the disposable database because asset evidence is immutable",
    })}\n`,
  );
}

void main()
  .catch(async (error: unknown) => {
    let cleanupError: unknown = null;
    if (syntheticReleaseLifecycle) {
      try {
        await revokeSyntheticReleaseIfActive({
          lifecycle: syntheticReleaseLifecycle,
          reasonCode: "SYNTHETIC_STATIC_ASSET_PROOF_FAILED",
        });
      } catch (cause) {
        cleanupError = cause;
      }
    }
    process.stderr.write(
      `${error instanceof Error ? (error.stack ?? error.message) : String(error)}\n`,
    );
    if (cleanupError) {
      process.stderr.write(
        `Synthetic release cleanup failed: ${cleanupError instanceof Error ? (cleanupError.stack ?? cleanupError.message) : String(cleanupError)}\n`,
      );
    }
    process.exitCode = 1;
  })
  .finally(async () => {
    await Promise.all([
      claimant.$disconnect(),
      revoker.$disconnect(),
      observer.$disconnect(),
      runtimeRegistrar.$disconnect(),
    ]);
  });
