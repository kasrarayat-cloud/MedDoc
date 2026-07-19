#!/usr/bin/env tsx

// Actual-PostgreSQL B-017 proof. Synthetic identities and non-clinical JSON
// only; no provider call is made. The target must be a disposable test DB.

import assert from "node:assert/strict";
import { createHash, randomBytes, randomUUID } from "node:crypto";

import { PrismaPg } from "@prisma/adapter-pg";
import { Prisma, PrismaClient } from "@prisma/client";

import { canonicalSha256 } from "../../../apps/transcribe-md/src/lib/template-twin/canonical";
import { assertNonProdDatabase } from "../src/db-guard";

const databaseUrl =
  process.env.TEMPLATE_TWIN_PROVIDER_OWNERSHIP_TEST_DATABASE_URL ??
  process.env.DATABASE_URL;
if (!databaseUrl) throw new Error("Disposable provider-ownership test URL is required.");
assertNonProdDatabase(databaseUrl);

function client(applicationName: string, assumedRole?: string): PrismaClient {
  const url = new URL(databaseUrl!);
  url.searchParams.set("application_name", applicationName);
  if (assumedRole) url.searchParams.set("options", `-c role=${assumedRole}`);
  return new PrismaClient({
    adapter: new PrismaPg({ connectionString: url.toString(), max: 2 }),
  });
}

const observer = client("template-twin-provider-ownership-observer");
const executor = client(
  "template-twin-provider-ownership-runtime",
  "quillmd_runtime",
);
const contenderA = client(
  "template-twin-provider-ownership-contender-a",
  "quillmd_runtime",
);
const contenderB = client(
  "template-twin-provider-ownership-contender-b",
  "quillmd_runtime",
);

const suffix = `${process.pid}-${Date.now()}`;
const practiceA = `synthetic-provider-practice-a-${suffix}`;
const practiceB = `synthetic-provider-practice-b-${suffix}`;
const actorA = `synthetic-provider-doctor-a-${suffix}`;
const actorB = `synthetic-provider-doctor-b-${suffix}`;
const hash = (value: string): string =>
  createHash("sha256").update(value).digest("hex");
const joinedHash = (values: readonly string[]): string => hash(values.join("|"));

type Operation = "SOURCE_PHI_SCAN" | "SOURCE_SEMANTIC_MAPPING";

interface ExecutionIdentity {
  id: string;
  practiceId: string;
  actorUserId: string;
  subjectId: string;
  subjectSha256: string;
  sourceArtifactId: string;
  compiledVersionId: string;
  noteTemplateId: string;
  sourceLineageId: string;
  sourceSha256: string;
  operation: Operation;
  inputSha256: string;
  provider: string;
  providerMode: "DETERMINISTIC_MOCK";
  model: string;
  operationVersion: string;
  providerConfigurationSha256: string;
  runtimeIdentitySha256: string;
  ownershipKey: string;
  idempotencyKey: string;
  pinnedGlobalRolloutGeneration: bigint;
  pinnedPracticeRolloutGeneration: bigint;
}

function executionIdentity(input: {
  marker: string;
  operation?: Operation;
  practiceId?: string;
  actorUserId?: string;
  model?: string;
  globalGeneration?: bigint;
}): ExecutionIdentity {
  const practiceId = input.practiceId ?? practiceA;
  const actorUserId = input.actorUserId ?? actorA;
  const operation = input.operation ?? "SOURCE_PHI_SCAN";
  const sourceArtifactId = `source-${input.marker}-${suffix}`;
  const compiledVersionId = `compiled-${input.marker}-${suffix}`;
  const noteTemplateId = `template-${input.marker}-${suffix}`;
  const subjectId = sourceArtifactId;
  const subjectSha256 = hash(`subject:${input.marker}`);
  const sourceLineageId = `lineage-${input.marker}-${suffix}`;
  const sourceSha256 = hash(`source:${input.marker}`);
  const inputSha256 = hash(`input:${input.marker}:${operation}`);
  const provider = "anthropic";
  const providerMode = "DETERMINISTIC_MOCK" as const;
  const model = input.model ?? "synthetic-model-v1";
  const operationVersion = "b017-pg-contract-v1";
  const providerConfigurationSha256 = hash("synthetic-provider-configuration-v1");
  const globalGeneration = input.globalGeneration ?? 1n;
  const runtimeIdentitySha256 = joinedHash([
    "template-twin-provider-runtime-v1",
    providerMode,
    globalGeneration.toString(),
    "1",
    "-",
    "-",
    "-",
    "-",
  ]);
  const ownershipKey = joinedHash([
    "template-twin-provider-ownership-v1",
    practiceId,
    actorUserId,
    "SOURCE_INTAKE",
    subjectId,
    subjectSha256,
    "1",
    operation,
    inputSha256,
    "-",
    sourceArtifactId,
    compiledVersionId,
    noteTemplateId,
    "1",
    sourceLineageId,
    "1",
    sourceSha256,
  ]);
  const idempotencyKey = joinedHash([
    "template-twin-provider-idempotency-v1",
    ownershipKey,
    provider,
    providerMode,
    model,
    operationVersion,
    providerConfigurationSha256,
    runtimeIdentitySha256,
  ]);
  return {
    id: randomUUID(),
    practiceId,
    actorUserId,
    subjectId,
    subjectSha256,
    sourceArtifactId,
    compiledVersionId,
    noteTemplateId,
    sourceLineageId,
    sourceSha256,
    operation,
    inputSha256,
    provider,
    providerMode,
    model,
    operationVersion,
    providerConfigurationSha256,
    runtimeIdentitySha256,
    ownershipKey,
    idempotencyKey,
    pinnedGlobalRolloutGeneration: globalGeneration,
    pinnedPracticeRolloutGeneration: 1n,
  };
}

async function reserve(
  db: PrismaClient,
  identity: ExecutionIdentity,
): Promise<void> {
  await db.$executeRaw(Prisma.sql`
    INSERT INTO "template_twin_provider_executions" (
      "id", "practiceId", "actorUserId", "scope", "operation",
      "logicalAttempt", "subjectId", "subjectSha256", "sourceArtifactId",
      "compiledVersionId", "noteTemplateId", "noteTemplateVersion",
      "sourceLineageId", "sourceLineageVersion", "sourceSha256",
      "inputSha256", "provider", "providerMode", "model",
      "operationVersion", "providerConfigurationSha256",
      "runtimeIdentitySha256", "ownershipKey", "idempotencyKey",
      "pinnedGlobalRolloutGeneration", "pinnedPracticeRolloutGeneration",
      "updatedAt"
    ) VALUES (
      ${identity.id}, ${identity.practiceId}, ${identity.actorUserId},
      'SOURCE_INTAKE', ${identity.operation}, 1, ${identity.subjectId},
      ${identity.subjectSha256}, ${identity.sourceArtifactId},
      ${identity.compiledVersionId}, ${identity.noteTemplateId}, 1,
      ${identity.sourceLineageId}, 1, ${identity.sourceSha256},
      ${identity.inputSha256}, ${identity.provider}, ${identity.providerMode},
      ${identity.model}, ${identity.operationVersion},
      ${identity.providerConfigurationSha256},
      ${identity.runtimeIdentitySha256}, ${identity.ownershipKey},
      ${identity.idempotencyKey},
      ${identity.pinnedGlobalRolloutGeneration},
      ${identity.pinnedPracticeRolloutGeneration}, clock_timestamp()
    )
  `);
}

async function claim(
  db: PrismaClient,
  executionId: string,
  claimId: string,
): Promise<number> {
  return db.$executeRaw(Prisma.sql`
    UPDATE "template_twin_provider_executions"
    SET "status" = 'IN_FLIGHT'::"VisitAutomationProviderExecutionStatus",
        "claimId" = ${claimId}, "claimedAt" = clock_timestamp(),
        "invocationCount" = 1, "invokedAt" = clock_timestamp(),
        "updatedAt" = clock_timestamp()
    WHERE "id" = ${executionId}
      AND "status" = 'RESERVED'::"VisitAutomationProviderExecutionStatus"
      AND "claimId" IS NULL
  `);
}

async function expectReject(
  action: () => Promise<unknown>,
  expected: RegExp,
): Promise<void> {
  await assert.rejects(action, expected);
}

async function main(): Promise<void> {
  await observer.practice.createMany({
    data: [
      { id: practiceA, name: "Synthetic Provider Practice A", slug: practiceA },
      { id: practiceB, name: "Synthetic Provider Practice B", slug: practiceB },
    ],
  });
  await observer.user.createMany({
    data: [
      {
        id: actorA,
        email: `${actorA}@synthetic.test`,
        passwordHash: "not-a-real-credential",
        role: "DOCTOR",
        practiceId: practiceA,
        products: ["TRANSCRIBE_MD"],
      },
      {
        id: actorB,
        email: `${actorB}@synthetic.test`,
        passwordHash: "not-a-real-credential",
        role: "DOCTOR",
        practiceId: practiceB,
        products: ["TRANSCRIBE_MD"],
      },
    ],
  });

  const ambiguous = executionIdentity({ marker: "ambiguous" });
  await reserve(executor, ambiguous);
  const claimA = randomBytes(32).toString("hex");
  const claimB = randomBytes(32).toString("hex");
  const claims = await Promise.all([
    claim(contenderA, ambiguous.id, claimA),
    claim(contenderB, ambiguous.id, claimB),
  ]);
  assert.deepEqual([...claims].sort(), [0, 1]);
  const winningClaim = claims[0] === 1 ? claimA : claimB;
  await executor.$executeRaw(Prisma.sql`
    UPDATE "template_twin_provider_executions"
    SET "status" = 'UNKNOWN_OUTCOME'::"VisitAutomationProviderExecutionStatus",
        "failureCode" = 'PROVIDER_OUTCOME_AMBIGUOUS',
        "completedAt" = clock_timestamp(), "updatedAt" = clock_timestamp()
    WHERE "id" = ${ambiguous.id} AND "claimId" = ${winningClaim}
  `);
  assert.equal(await claim(contenderA, ambiguous.id, randomBytes(32).toString("hex")), 0);
  await expectReject(
    () =>
      executor.$executeRaw(Prisma.sql`
        UPDATE "template_twin_provider_executions"
        SET "failureCode" = 'MUTATED', "updatedAt" = clock_timestamp()
        WHERE "id" = ${ambiguous.id}
      `),
    /TEMPLATE_TWIN_PROVIDER_EXECUTION_TERMINAL_IMMUTABLE/u,
  );

  const changedModel = executionIdentity({ marker: "ambiguous", model: "synthetic-model-v2" });
  await expectReject(
    () => reserve(executor, changedModel),
    /template_twin_provider_execution_ownership_key/u,
  );
  const changedRuntime = executionIdentity({ marker: "ambiguous", globalGeneration: 2n });
  await expectReject(
    () => reserve(executor, changedRuntime),
    /template_twin_provider_execution_ownership_key/u,
  );
  const crossTenantActor = executionIdentity({
    marker: "cross-tenant-actor",
    practiceId: practiceA,
    actorUserId: actorB,
  });
  await expectReject(
    () => reserve(executor, crossTenantActor),
    /TEMPLATE_TWIN_PROVIDER_ACTOR_NOT_AUTHORIZED/u,
  );

  const succeeded = executionIdentity({ marker: "succeeded" });
  await reserve(executor, succeeded);
  const successClaim = randomBytes(32).toString("hex");
  assert.equal(await claim(executor, succeeded.id, successClaim), 1);
  const resultPayload = {
    contractVersion: "template-twin-provider-result-v1",
    output: { classification: "synthetic-safe" },
  };
  const resultSha256 = canonicalSha256(resultPayload);
  await expectReject(
    () =>
      executor.$executeRaw(Prisma.sql`
        UPDATE "template_twin_provider_executions"
        SET "status" = 'SUCCEEDED'::"VisitAutomationProviderExecutionStatus",
            "resultPayload" = ${JSON.stringify(resultPayload)}::JSONB,
            "resultSha256" = ${"0".repeat(64)},
            "resultVersion" = 'template-twin-provider-result-v1',
            "completedAt" = clock_timestamp(), "updatedAt" = clock_timestamp()
        WHERE "id" = ${succeeded.id} AND "claimId" = ${successClaim}
      `),
    /TEMPLATE_TWIN_PROVIDER_RESULT_INVALID/u,
  );
  await executor.$executeRaw(Prisma.sql`
    UPDATE "template_twin_provider_executions"
    SET "status" = 'SUCCEEDED'::"VisitAutomationProviderExecutionStatus",
        "resultPayload" = ${JSON.stringify(resultPayload)}::JSONB,
        "resultSha256" = ${resultSha256},
        "resultVersion" = 'template-twin-provider-result-v1',
        "completedAt" = clock_timestamp(), "updatedAt" = clock_timestamp()
    WHERE "id" = ${succeeded.id} AND "claimId" = ${successClaim}
  `);

  const receipt = {
    contractVersion: "template-twin-provider-ownership-receipt-v1",
    practiceId: practiceA,
    subjectId: succeeded.subjectId,
    subjectSha256: succeeded.subjectSha256,
    visitId: null,
    sourceArtifactId: succeeded.sourceArtifactId,
    compiledVersionId: null,
    noteTemplateId: null,
    executions: [
      {
        executionId: succeeded.id,
        operation: succeeded.operation,
        resultSha256,
      },
    ],
  };
  const [validReceipt] = await executor.$queryRaw<Array<{ valid: boolean }>>(
    Prisma.sql`
      SELECT template_twin_provider_receipt_is_valid(
        ${practiceA}, ${succeeded.subjectId}, ${succeeded.subjectSha256}, NULL,
        ${succeeded.sourceArtifactId}, NULL, NULL,
        ${JSON.stringify(receipt)}::JSONB,
        ${canonicalSha256(receipt)}::CHAR(64)
      ) AS valid
    `,
  );
  assert.equal(validReceipt?.valid, true);
  const [mismatchReceipt] = await executor.$queryRaw<Array<{ valid: boolean }>>(
    Prisma.sql`
      SELECT template_twin_provider_receipt_is_valid(
        ${practiceB}, ${succeeded.subjectId}, ${succeeded.subjectSha256}, NULL,
        ${succeeded.sourceArtifactId}, NULL, NULL,
        ${JSON.stringify(receipt)}::JSONB,
        ${canonicalSha256(receipt)}::CHAR(64)
      ) AS valid
    `,
  );
  assert.equal(mismatchReceipt?.valid, false);

  const unknownReceipt = {
    ...receipt,
    subjectId: ambiguous.subjectId,
    subjectSha256: ambiguous.subjectSha256,
    sourceArtifactId: ambiguous.sourceArtifactId,
    executions: [
      {
        executionId: ambiguous.id,
        operation: ambiguous.operation,
        resultSha256: hash("non-result"),
      },
    ],
  };
  const [unknownAccepted] = await executor.$queryRaw<Array<{ valid: boolean }>>(
    Prisma.sql`
      SELECT template_twin_provider_receipt_is_valid(
        ${practiceA}, ${ambiguous.subjectId}, ${ambiguous.subjectSha256}, NULL,
        ${ambiguous.sourceArtifactId}, NULL, NULL,
        ${JSON.stringify(unknownReceipt)}::JSONB,
        ${canonicalSha256(unknownReceipt)}::CHAR(64)
      ) AS valid
    `,
  );
  assert.equal(unknownAccepted?.valid, false);
  await expectReject(
    () =>
      executor.$executeRaw(Prisma.sql`
        DELETE FROM "template_twin_provider_executions"
        WHERE "id" = ${succeeded.id}
      `),
    /permission denied for table template_twin_provider_executions/u,
  );

  const census = await observer.templateTwinProviderExecution.groupBy({
    by: ["status"],
    where: { actorUserId: actorA },
    _count: { _all: true },
  });
  process.stdout.write(
    `${JSON.stringify({
      profile: "template-twin-provider-ownership-pg-v1",
      synthetic: true,
      concurrentClaimCounts: claims,
      statusCensus: census,
      crossTenantActorRejected: true,
      providerSwapRejected: true,
      runtimeSwapRejected: true,
      unknownReplayRejected: true,
      mismatchedReceiptRejected: true,
      resultHashMismatchRejected: true,
      runtimeDeleteRejected: true,
      result: "passed",
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
      executor.$disconnect(),
      contenderA.$disconnect(),
      contenderB.$disconnect(),
    ]);
  });
