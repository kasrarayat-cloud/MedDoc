#!/usr/bin/env tsx

// Actual-PostgreSQL B-017 proof. Synthetic identities and non-clinical JSON
// only; no provider call is made. The target must be a disposable test DB.

import assert from "node:assert/strict";
import { createHash, createHmac, randomBytes, randomUUID } from "node:crypto";

import { PrismaPg } from "@prisma/adapter-pg";
import { Prisma, PrismaClient } from "@prisma/client";

import {
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
  TEMPLATE_TWIN_SYNTHETIC_QA_MODE,
  TEMPLATE_TWIN_SYNTHETIC_QA_RESOURCE_ATTESTATION,
  TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
} from "../../../packages/ai/src/synthetic-qa-context";
import { runWithTemplateTwinSyntheticQaProviderContext } from "../../../packages/ai/src/synthetic-qa-context";
import { canonicalSha256 } from "../../../apps/transcribe-md/src/lib/template-twin/canonical";
import { templateTwinVisitProviderSubjectSha256 } from "../../../apps/transcribe-md/src/lib/template-twin/live-provider-ownership";
import type {
  ProviderOwnershipDbClient,
  TemplateTwinProviderOwnershipContext,
} from "../../../apps/transcribe-md/src/lib/template-twin/provider-ownership";
import { assertNonProdDatabase } from "../src/db-guard";

const databaseUrl =
  process.env.TEMPLATE_TWIN_PROVIDER_OWNERSHIP_TEST_DATABASE_URL ||
  process.env.DATABASE_URL;
if (!databaseUrl)
  throw new Error("Disposable provider-ownership test URL is required.");
assertNonProdDatabase(databaseUrl);
const verifiedDatabaseUrl = databaseUrl;
const databaseTargetEnvironment = [
  "DATABASE_URL",
  "TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL",
  "TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL",
] as const;
const providerDatabaseTargetEnvironment = [
  "TEMPLATE_TWIN_PROVIDER_OWNERSHIP_TEST_DATABASE_URL",
  ...databaseTargetEnvironment,
] as const;
const divergentDatabaseTarget = providerDatabaseTargetEnvironment.find(
  (name) => {
    const value = process.env[name];
    return value && value !== verifiedDatabaseUrl;
  },
);
if (divergentDatabaseTarget) {
  throw new Error(
    `${divergentDatabaseTarget} must exactly match the guarded disposable provider-ownership test URL.`,
  );
}
process.env.TEMPLATE_TWIN_PROVIDER_OWNERSHIP_TEST_DATABASE_URL =
  verifiedDatabaseUrl;
for (const name of databaseTargetEnvironment) {
  process.env[name] = verifiedDatabaseUrl;
}

function client(applicationName: string, assumedRole?: string): PrismaClient {
  const url = new URL(verifiedDatabaseUrl);
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
const actorA2 = `synthetic-provider-doctor-a2-${suffix}`;
const adminA = `synthetic-provider-admin-a-${suffix}`;
const actorB = `synthetic-provider-doctor-b-${suffix}`;
const hash = (value: string): string =>
  createHash("sha256").update(value).digest("hex");
const joinedHash = (values: readonly string[]): string =>
  hash(values.join("|"));

type Operation = "SOURCE_PHI_SCAN" | "SOURCE_SEMANTIC_MAPPING";

interface LiveReleaseAuthority {
  readonly releaseId: string;
  readonly releaseIdentitySha256: string;
  readonly runtimeManifestSha256: string;
  readonly runtimeInstanceId: string;
  readonly pinnedGlobalRolloutGeneration: bigint;
  readonly pinnedPracticeRolloutGeneration: bigint;
}

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
  operationInstance: string;
  inputSha256: string;
  provider: string;
  providerMode: "LIVE" | "DETERMINISTIC_MOCK" | "SYNTHETIC_QA";
  model: string;
  operationVersion: string;
  providerConfigurationSha256: string;
  runtimeIdentitySha256: string;
  ownershipKey: string;
  idempotencyKey: string;
  pinnedGlobalRolloutGeneration: bigint;
  pinnedPracticeRolloutGeneration: bigint;
  syntheticAdmissionId: string | null;
  releaseId: string | null;
  releaseIdentitySha256: string | null;
  runtimeManifestSha256: string | null;
  runtimeInstanceId: string | null;
}

function executionIdentity(input: {
  marker: string;
  operation?: Operation;
  practiceId?: string;
  actorUserId?: string;
  model?: string;
  globalGeneration?: bigint;
  inputMarker?: string;
  operationVersion?: string;
  operationInstance?: string;
  subjectSha256?: string;
  providerMode?: "LIVE" | "DETERMINISTIC_MOCK" | "SYNTHETIC_QA";
  syntheticAdmissionId?: string | null;
  liveAuthority?: LiveReleaseAuthority;
}): ExecutionIdentity {
  const practiceId = input.practiceId ?? practiceA;
  const actorUserId = input.actorUserId ?? actorA;
  const operation = input.operation ?? "SOURCE_PHI_SCAN";
  const sourceArtifactId = `source-${input.marker}-${suffix}`;
  const compiledVersionId = `compiled-${input.marker}-${suffix}`;
  const noteTemplateId = `template-${input.marker}-${suffix}`;
  const subjectId = sourceArtifactId;
  const subjectSha256 = input.subjectSha256 ?? hash(`subject:${input.marker}`);
  const sourceLineageId = `lineage-${input.marker}-${suffix}`;
  const sourceSha256 = subjectSha256;
  const inputSha256 = hash(
    `input:${input.inputMarker ?? input.marker}:${operation}`,
  );
  const provider = "anthropic";
  const providerMode = input.providerMode ?? "DETERMINISTIC_MOCK";
  const model = input.model ?? "synthetic-model-v1";
  const operationVersion = input.operationVersion ?? "b017-pg-contract-v1";
  const operationInstance = input.operationInstance ?? "primary";
  const providerConfigurationSha256 = hash(
    "synthetic-provider-configuration-v1",
  );
  const globalGeneration =
    input.liveAuthority?.pinnedGlobalRolloutGeneration ??
    input.globalGeneration ??
    1n;
  const practiceGeneration =
    input.liveAuthority?.pinnedPracticeRolloutGeneration ?? 1n;
  const releaseId = input.liveAuthority?.releaseId ?? null;
  const releaseIdentitySha256 =
    input.liveAuthority?.releaseIdentitySha256 ?? null;
  const runtimeManifestSha256 =
    input.liveAuthority?.runtimeManifestSha256 ?? null;
  const runtimeInstanceId = input.liveAuthority?.runtimeInstanceId ?? null;
  const runtimeIdentitySha256 = joinedHash([
    "template-twin-provider-runtime-v1",
    providerMode,
    globalGeneration.toString(),
    practiceGeneration.toString(),
    releaseId ?? "-",
    releaseIdentitySha256 ?? "-",
    runtimeManifestSha256 ?? "-",
    runtimeInstanceId ?? "-",
  ]);
  const ownershipKey = joinedHash([
    "template-twin-provider-ownership-v2",
    practiceId,
    "SOURCE_INTAKE",
    subjectId,
    "1",
    operation,
    operationInstance,
  ]);
  const idempotencyKey = joinedHash([
    "template-twin-provider-idempotency-v2",
    ownershipKey,
    actorUserId,
    subjectSha256,
    inputSha256,
    provider,
    providerMode,
    model,
    operationVersion,
    providerConfigurationSha256,
    runtimeIdentitySha256,
    "-",
    "-",
    sourceArtifactId,
    compiledVersionId,
    noteTemplateId,
    "1",
    sourceLineageId,
    "1",
    sourceSha256,
    input.syntheticAdmissionId ?? "-",
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
    operationInstance,
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
    pinnedPracticeRolloutGeneration: practiceGeneration,
    syntheticAdmissionId: input.syntheticAdmissionId ?? null,
    releaseId,
    releaseIdentitySha256,
    runtimeManifestSha256,
    runtimeInstanceId,
  };
}

async function reserve(
  db: PrismaClient,
  identity: ExecutionIdentity,
): Promise<void> {
  await db.$executeRaw(Prisma.sql`
    INSERT INTO "template_twin_provider_executions" (
      "id", "practiceId", "actorUserId", "scope", "operation",
      "operationInstance", "logicalAttempt", "subjectId", "subjectSha256", "sourceArtifactId",
      "compiledVersionId", "noteTemplateId", "noteTemplateVersion",
      "sourceLineageId", "sourceLineageVersion", "sourceSha256",
      "inputSha256", "provider", "providerMode", "model",
      "operationVersion", "providerConfigurationSha256",
      "runtimeIdentitySha256", "ownershipKey", "idempotencyKey",
      "pinnedGlobalRolloutGeneration", "pinnedPracticeRolloutGeneration",
      "releaseId", "releaseIdentitySha256", "runtimeManifestSha256",
      "runtimeInstanceId", "syntheticAdmissionId", "updatedAt"
    ) VALUES (
      ${identity.id}, ${identity.practiceId}, ${identity.actorUserId},
      'SOURCE_INTAKE', ${identity.operation}, ${identity.operationInstance},
      1, ${identity.subjectId},
      ${identity.subjectSha256}, ${identity.sourceArtifactId},
      ${identity.compiledVersionId}, ${identity.noteTemplateId}, 1,
      ${identity.sourceLineageId}, 1, ${identity.sourceSha256},
      ${identity.inputSha256}, ${identity.provider}, ${identity.providerMode},
      ${identity.model}, ${identity.operationVersion},
      ${identity.providerConfigurationSha256},
      ${identity.runtimeIdentitySha256}, ${identity.ownershipKey},
      ${identity.idempotencyKey},
      ${identity.pinnedGlobalRolloutGeneration},
      ${identity.pinnedPracticeRolloutGeneration},
      ${identity.releaseId}::UUID, ${identity.releaseIdentitySha256},
      ${identity.runtimeManifestSha256}, ${identity.runtimeInstanceId},
      ${identity.syntheticAdmissionId}, clock_timestamp()
    )
  `);
}

async function reserveVisitPipelineExecution(input: {
  db: PrismaClient;
  marker: string;
  actorUserId: string;
  visitId: string;
  visitInputMode: "audio_upload" | "voice_dictation" | "text_notes";
  sourceArtifactId: string;
  compiledVersionId: string;
  noteTemplateId: string;
  sourceLineageId: string;
  sourceLineageVersion: number;
  sourceSha256: string;
}): Promise<void> {
  const subjectSha256 = hash(`visit-subject:${input.marker}`);
  const inputSha256 = hash(`visit-input:${input.marker}`);
  const runtimeIdentitySha256 = joinedHash([
    "template-twin-provider-runtime-v1",
    "DETERMINISTIC_MOCK",
    "1",
    "1",
    "-",
    "-",
    "-",
    "-",
  ]);
  const ownershipKey = joinedHash([
    "template-twin-provider-ownership-v2",
    practiceA,
    "VISIT_PIPELINE",
    input.visitId,
    "1",
    "L3_EXTRACT_ENTITIES",
    "primary",
  ]);
  const providerConfigurationSha256 = hash(
    "synthetic-provider-configuration-v1",
  );
  const idempotencyKey = joinedHash([
    "template-twin-provider-idempotency-v2",
    ownershipKey,
    input.actorUserId,
    subjectSha256,
    inputSha256,
    "anthropic",
    "DETERMINISTIC_MOCK",
    "synthetic-model-v1",
    "b017-pg-contract-v1",
    providerConfigurationSha256,
    runtimeIdentitySha256,
    input.visitId,
    input.visitInputMode,
    input.sourceArtifactId,
    input.compiledVersionId,
    input.noteTemplateId,
    "1",
    input.sourceLineageId,
    String(input.sourceLineageVersion),
    input.sourceSha256,
    "-",
  ]);
  await input.db.$executeRaw(Prisma.sql`
    INSERT INTO "template_twin_provider_executions" (
      "id", "practiceId", "actorUserId", "visitId", "visitInputMode",
      "scope", "operation", "operationInstance", "logicalAttempt",
      "subjectId", "subjectSha256", "sourceArtifactId",
      "compiledVersionId", "noteTemplateId", "noteTemplateVersion",
      "sourceLineageId", "sourceLineageVersion", "sourceSha256",
      "inputSha256", "provider", "providerMode", "model",
      "operationVersion", "providerConfigurationSha256",
      "runtimeIdentitySha256", "ownershipKey", "idempotencyKey",
      "pinnedGlobalRolloutGeneration", "pinnedPracticeRolloutGeneration",
      "syntheticAdmissionId", "updatedAt"
    ) VALUES (
      ${randomUUID()}, ${practiceA}, ${input.actorUserId}, ${input.visitId},
      ${input.visitInputMode}, 'VISIT_PIPELINE', 'L3_EXTRACT_ENTITIES',
      'primary', 1, ${input.visitId}, ${subjectSha256},
      ${input.sourceArtifactId}, ${input.compiledVersionId},
      ${input.noteTemplateId}, 1, ${input.sourceLineageId},
      ${input.sourceLineageVersion}, ${input.sourceSha256}, ${inputSha256},
      'anthropic', 'DETERMINISTIC_MOCK', 'synthetic-model-v1',
      'b017-pg-contract-v1', ${providerConfigurationSha256},
      ${runtimeIdentitySha256}, ${ownershipKey}, ${idempotencyKey},
      1, 1, NULL, clock_timestamp()
    )
  `);
}

async function reserveLiveVisitPipelineExecution(input: {
  db: PrismaClient;
  marker: string;
  authority: LiveReleaseAuthority;
  actorUserId: string;
  visitId: string;
  visitInputMode: "audio_upload" | "voice_dictation" | "text_notes";
  sourceArtifactId: string;
  compiledVersionId: string;
  noteTemplateId: string;
  sourceLineageId: string;
  sourceLineageVersion: number;
  sourceSha256: string;
}): Promise<string> {
  const id = randomUUID();
  const subjectSha256 = hash(`visit-subject:${input.marker}`);
  const inputSha256 = hash(`visit-input:${input.marker}`);
  const runtimeIdentitySha256 = joinedHash([
    "template-twin-provider-runtime-v1",
    "LIVE",
    input.authority.pinnedGlobalRolloutGeneration.toString(),
    input.authority.pinnedPracticeRolloutGeneration.toString(),
    input.authority.releaseId,
    input.authority.releaseIdentitySha256,
    input.authority.runtimeManifestSha256,
    input.authority.runtimeInstanceId,
  ]);
  const ownershipKey = joinedHash([
    "template-twin-provider-ownership-v2",
    practiceA,
    "VISIT_PIPELINE",
    input.visitId,
    "1",
    "L3_EXTRACT_ENTITIES",
    "primary",
  ]);
  const providerConfigurationSha256 = hash(
    "synthetic-provider-configuration-v1",
  );
  const idempotencyKey = joinedHash([
    "template-twin-provider-idempotency-v2",
    ownershipKey,
    input.actorUserId,
    subjectSha256,
    inputSha256,
    "anthropic",
    "LIVE",
    "synthetic-model-v1",
    "b017-pg-contract-v1",
    providerConfigurationSha256,
    runtimeIdentitySha256,
    input.visitId,
    input.visitInputMode,
    input.sourceArtifactId,
    input.compiledVersionId,
    input.noteTemplateId,
    "1",
    input.sourceLineageId,
    String(input.sourceLineageVersion),
    input.sourceSha256,
    "-",
  ]);
  await input.db.$executeRaw(Prisma.sql`
    INSERT INTO "template_twin_provider_executions" (
      "id", "practiceId", "actorUserId", "visitId", "visitInputMode",
      "scope", "operation", "operationInstance", "logicalAttempt",
      "subjectId", "subjectSha256", "sourceArtifactId",
      "compiledVersionId", "noteTemplateId", "noteTemplateVersion",
      "sourceLineageId", "sourceLineageVersion", "sourceSha256",
      "inputSha256", "provider", "providerMode", "model",
      "operationVersion", "providerConfigurationSha256",
      "runtimeIdentitySha256", "ownershipKey", "idempotencyKey",
      "pinnedGlobalRolloutGeneration", "pinnedPracticeRolloutGeneration",
      "releaseId", "releaseIdentitySha256", "runtimeManifestSha256",
      "runtimeInstanceId", "syntheticAdmissionId", "updatedAt"
    ) VALUES (
      ${id}, ${practiceA}, ${input.actorUserId}, ${input.visitId},
      ${input.visitInputMode}, 'VISIT_PIPELINE', 'L3_EXTRACT_ENTITIES',
      'primary', 1, ${input.visitId}, ${subjectSha256},
      ${input.sourceArtifactId}, ${input.compiledVersionId},
      ${input.noteTemplateId}, 1, ${input.sourceLineageId},
      ${input.sourceLineageVersion}, ${input.sourceSha256}, ${inputSha256},
      'anthropic', 'LIVE', 'synthetic-model-v1', 'b017-pg-contract-v1',
      ${providerConfigurationSha256}, ${runtimeIdentitySha256},
      ${ownershipKey}, ${idempotencyKey},
      ${input.authority.pinnedGlobalRolloutGeneration},
      ${input.authority.pinnedPracticeRolloutGeneration},
      ${input.authority.releaseId}::UUID,
      ${input.authority.releaseIdentitySha256},
      ${input.authority.runtimeManifestSha256},
      ${input.authority.runtimeInstanceId}, NULL, clock_timestamp()
    )
  `);
  return id;
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

async function succeed(
  db: PrismaClient,
  identity: ExecutionIdentity,
  output: Record<string, unknown>,
): Promise<string> {
  const claimId = randomBytes(32).toString("hex");
  assert.equal(await claim(db, identity.id, claimId), 1);
  const resultPayload = {
    contractVersion: "template-twin-provider-result-v1",
    output,
  };
  const resultSha256 = canonicalSha256(resultPayload);
  await db.$executeRaw(Prisma.sql`
    UPDATE "template_twin_provider_executions"
    SET "status" = 'SUCCEEDED'::"VisitAutomationProviderExecutionStatus",
        "resultPayload" = ${JSON.stringify(resultPayload)}::JSONB,
        "resultSha256" = ${resultSha256},
        "resultVersion" = 'template-twin-provider-result-v1',
        "completedAt" = clock_timestamp(), "updatedAt" = clock_timestamp()
    WHERE "id" = ${identity.id} AND "claimId" = ${claimId}
  `);
  return resultSha256;
}

interface ReceiptExecution {
  readonly identity: ExecutionIdentity;
  readonly resultSha256: string;
}

function receiptFor(input: {
  actorUserId: string;
  authority: ExecutionIdentity;
  executions: readonly ReceiptExecution[];
  compiledVersionId?: string | null;
  noteTemplateId?: string | null;
}): Record<string, unknown> {
  const executionPlan = input.executions
    .map(({ identity }) => ({
      operation: identity.operation,
      operationInstance: identity.operationInstance,
      disposition: "EXECUTED" as const,
      reasonCode: null,
    }))
    .sort((left, right) =>
      `${left.operation}:${left.operationInstance}`.localeCompare(
        `${right.operation}:${right.operationInstance}`,
      ),
    );
  const compiledVersionId =
    input.compiledVersionId === undefined
      ? input.authority.compiledVersionId
      : input.compiledVersionId;
  const noteTemplateId =
    input.noteTemplateId === undefined
      ? input.authority.noteTemplateId
      : input.noteTemplateId;
  return {
    contractVersion: "template-twin-provider-ownership-receipt-v2",
    scope: "SOURCE_INTAKE",
    practiceId: input.authority.practiceId,
    actorUserId: input.actorUserId,
    subjectId: input.authority.subjectId,
    subjectSha256: input.authority.subjectSha256,
    visitId: null,
    sourceArtifactId: input.authority.sourceArtifactId,
    compiledVersionId,
    noteTemplateId,
    noteTemplateVersion: 1,
    visitInputMode: null,
    logicalAttempt: 1,
    sourceLineageId: input.authority.sourceLineageId,
    sourceLineageVersion: 1,
    sourceSha256: input.authority.sourceSha256,
    providerMode: input.authority.providerMode,
    pinnedGlobalRolloutGeneration:
      input.authority.pinnedGlobalRolloutGeneration.toString(),
    pinnedPracticeRolloutGeneration:
      input.authority.pinnedPracticeRolloutGeneration.toString(),
    releaseId: input.authority.releaseId,
    releaseIdentitySha256: input.authority.releaseIdentitySha256,
    runtimeManifestSha256: input.authority.runtimeManifestSha256,
    runtimeInstanceId: input.authority.runtimeInstanceId,
    runtimeIdentitySha256: input.authority.runtimeIdentitySha256,
    syntheticAdmissionId: input.authority.syntheticAdmissionId,
    executionPlanSha256: canonicalSha256({
      contractVersion: "template-twin-provider-execution-plan-v1",
      scope: "SOURCE_INTAKE",
      entries: executionPlan,
    }),
    executionPlan,
    executions: input.executions
      .map(({ identity, resultSha256 }) => ({
        executionId: identity.id,
        operation: identity.operation,
        operationInstance: identity.operationInstance,
        resultSha256,
      }))
      .sort((left, right) =>
        `${left.operation}:${left.operationInstance}:${left.executionId}`.localeCompare(
          `${right.operation}:${right.operationInstance}:${right.executionId}`,
        ),
      ),
  };
}

function receiptExpectation(identity: ExecutionIdentity) {
  return {
    expectedPracticeId: identity.practiceId,
    expectedActorId: identity.actorUserId,
    expectedProviderMode: identity.providerMode,
    expectedSyntheticAdmissionId: identity.syntheticAdmissionId,
    expectedSubjectId: identity.subjectId,
    expectedSubjectSha256: identity.subjectSha256,
    expectedSourceArtifactId: identity.sourceArtifactId,
    expectedCompiledVersionId: identity.compiledVersionId,
    expectedNoteTemplateId: identity.noteTemplateId,
    expectedNoteTemplateVersion: 1,
    expectedLogicalAttempt: 1,
    expectedSourceLineageId: identity.sourceLineageId,
    expectedSourceLineageVersion: 1,
    expectedSourceSha256: identity.sourceSha256,
  } as const;
}

async function receiptIsValid(input: {
  expectedPracticeId: string;
  expectedActorId: string;
  expectedProviderMode: ExecutionIdentity["providerMode"];
  expectedSyntheticAdmissionId: string | null;
  expectedSubjectId: string;
  expectedSubjectSha256: string | null;
  expectedSourceArtifactId: string | null;
  expectedCompiledVersionId: string | null;
  expectedNoteTemplateId: string | null;
  expectedNoteTemplateVersion: number | null;
  expectedLogicalAttempt: number;
  expectedSourceLineageId: string | null;
  expectedSourceLineageVersion: number | null;
  expectedSourceSha256: string | null;
  receipt: Record<string, unknown>;
}): Promise<boolean> {
  const [row] = await executor.$queryRaw<Array<{ valid: boolean }>>(Prisma.sql`
    SELECT template_twin_provider_receipt_is_valid(
      ${input.expectedPracticeId}, ${input.expectedActorId},
      'SOURCE_INTAKE',
      ${input.expectedProviderMode}, ${input.expectedSyntheticAdmissionId},
      ${input.expectedSubjectId}, ${input.expectedSubjectSha256}, NULL,
      NULL,
      ${input.expectedSourceArtifactId}, ${input.expectedCompiledVersionId},
      ${input.expectedNoteTemplateId}, ${input.expectedNoteTemplateVersion},
      ${input.expectedLogicalAttempt}, ${input.expectedSourceLineageId},
      ${input.expectedSourceLineageVersion}, ${input.expectedSourceSha256},
      ${JSON.stringify(input.receipt)}::JSONB,
      ${canonicalSha256(input.receipt)}::CHAR(64)
    ) AS valid
  `);
  return row?.valid ?? false;
}

async function expectReject(
  action: () => Promise<unknown>,
  expected: RegExp,
): Promise<void> {
  await assert.rejects(action, expected);
}

async function createSyntheticAdmission(
  actorId: string,
  marker = "default",
): Promise<string> {
  const id = `synthetic-provider-admission-${marker}-${actorId}-${suffix}`;
  await observer.$executeRaw(Prisma.sql`
    INSERT INTO "template_twin_synthetic_qa_admissions" (
      "id", "practiceId", "actorId", "sourceSha256", "sourceSizeBytes",
      "fixtureVersion", "providerMode", "purpose", "requestSha256",
      "pinnedGlobalRolloutGeneration", "pinnedPracticeRolloutGeneration",
      "expiresAt", "updatedAt"
    ) VALUES (
      ${id}, ${practiceA}, ${actorId},
      '9c917a831e661d5fdcf92a6e13cbc542adda9fb86a2292cf34689fc333c375d4',
      4686, 'template-twin-staging-safe-docx/1.0.0',
      'SYNTHETIC_LIFECYCLE', 'UPLOAD', ${hash(`request:${id}`)},
      1, 1, clock_timestamp() + interval '15 minutes', clock_timestamp()
    )
  `);
  return id;
}

interface SyntheticStagingLineage {
  readonly uploadAdmissionId: string;
  readonly sourceArtifactId: string;
  readonly compiledVersionId: string;
  readonly noteTemplateId: string;
  readonly sourceLineageId: string;
  readonly sourceLineageVersion: number;
  readonly sourceSha256: string;
}

async function proveSyntheticStagingUploadAndPromotionFence(): Promise<SyntheticStagingLineage> {
  const rawSha256 =
    "9c917a831e661d5fdcf92a6e13cbc542adda9fb86a2292cf34689fc333c375d4";
  const rawSizeBytes = 4686;
  const admissionId = await createSyntheticAdmission(actorA, "staging-upload");
  const scan = executionIdentity({
    marker: "staging-upload-positive",
    subjectSha256: rawSha256,
    providerMode: "SYNTHETIC_QA",
    syntheticAdmissionId: admissionId,
  });
  const mapping = executionIdentity({
    marker: "staging-upload-positive",
    operation: "SOURCE_SEMANTIC_MAPPING",
    subjectSha256: rawSha256,
    providerMode: "SYNTHETIC_QA",
    syntheticAdmissionId: admissionId,
  });
  await reserve(executor, scan);
  await reserve(executor, mapping);
  const scanSha = await succeed(executor, scan, {
    classification: "synthetic-safe",
  });
  const mappingSha = await succeed(executor, mapping, { mappings: [] });
  const receipt = receiptFor({
    actorUserId: actorA,
    authority: scan,
    executions: [
      { identity: scan, resultSha256: scanSha },
      { identity: mapping, resultSha256: mappingSha },
    ],
    compiledVersionId: scan.compiledVersionId,
    noteTemplateId: scan.noteTemplateId,
  });
  const quarantineId = `quarantine-staging-positive-${suffix}`;
  const quarantineKey = `practices/${practiceA}/template-twin/quarantine/${quarantineId}.docx`;
  const sourceKey = `practices/${practiceA}/template-twin/sources/${scan.sourceArtifactId}.docx`;
  const outputKey =
    `practices/${practiceA}/template-twin/outputs/` +
    `synthetic-current-${suffix}.docx`;
  const outputVersionId = "synthetic-current-output-version";
  const outputEtag = "synthetic-current-output-etag";
  const outputSha256 = hash("synthetic-current-output");
  const scannedAt = new Date("2026-07-19T17:20:00.000Z");
  const malwareCore = {
    profileVersion: "template-twin-clamd-instream-v1",
    scanner: "clamav-clamd",
    transport: "unix-domain-socket",
    engineVersion: "synthetic-clamd-v1",
    signatureVersion: "1",
    sourceSha256: rawSha256,
    sourceSizeBytes: rawSizeBytes,
    verdict: "clean",
    threatNameSha256: null,
    scannedAt: scannedAt.toISOString(),
  };
  const malwareScanEvidence = {
    ...malwareCore,
    attestationSha256: hash(JSON.stringify(malwareCore)),
  };
  const metadataMinimizationEvidence = {
    profileVersion: "template-twin-docx-metadata-minimization-v1",
    originalSha256: rawSha256,
    minimizedSha256: scan.subjectSha256,
    zipEntryTimestampsNormalized: true,
    replacedParts: [],
  };

  await observer.$transaction(async (tx) => {
    await tx.templateTwinQuarantineArtifact.create({
      data: {
        id: quarantineId,
        practiceId: practiceA,
        createdById: actorA,
        lineageId: scan.sourceLineageId,
        lineageVersion: 1,
        intakeMode: "NATIVE_TEMPLATE",
        objectKey: quarantineKey,
        objectVersionId: "synthetic-quarantine-version",
        objectEtag: "synthetic-quarantine-etag",
        sha256: rawSha256,
        mimeType:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        sizeBytes: rawSizeBytes,
        status: "MALWARE_CLEAN",
        malwareScanEvidence,
        scannedAt,
      },
    });
    await tx.templateTwinObjectLedger.create({
      data: {
        id: `ledger-${quarantineId}`,
        practiceId: practiceA,
        objectKey: quarantineKey,
        objectVersionId: "synthetic-quarantine-version",
        objectEtag: "synthetic-quarantine-etag",
        sha256: rawSha256,
        sizeBytes: rawSizeBytes,
        kind: "quarantine",
        state: "CLAIMED",
        claimType: "quarantine_artifact",
        claimId: quarantineId,
      },
    });
    await tx.noteTemplate.create({
      data: {
        id: scan.noteTemplateId,
        doctorId: actorA,
        name: "Synthetic staging provider template",
        encounterType: "synthetic",
        sections: [],
        version: 1,
        versionDescription: "Synthetic staging provider proof",
        status: "draft",
        isSystemDefault: false,
        lineageId: scan.sourceLineageId,
        templateKind: "template_twin_docx",
      },
    });
    await tx.templateTwinSourceArtifact.create({
      data: {
        id: scan.sourceArtifactId,
        practiceId: practiceA,
        createdById: actorA,
        lineageId: scan.sourceLineageId,
        lineageVersion: 1,
        objectKey: sourceKey,
        objectVersionId: "synthetic-source-version",
        objectEtag: "synthetic-source-etag",
        sha256: scan.subjectSha256,
        mimeType:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        sizeBytes: rawSizeBytes,
        validationStatus: "accepted",
        rejectionCodes: [],
        privacyScanEvidence: {
          profileVersion: "template-twin-source-phi-safe-alpha-v1",
          approvedStaticAssetPolicySha256: hash(
            "synthetic-approved-static-asset-policy",
          ),
          approvedStaticAssetUsageSha256: hash(
            "synthetic-approved-static-asset-usage",
          ),
        },
        providerOwnershipEvidence: receipt as Prisma.InputJsonValue,
        providerOwnershipSha256: canonicalSha256(receipt),
        quarantineArtifactId: quarantineId,
      },
    });
    await tx.templateTwinObjectLedger.create({
      data: {
        id: `ledger-${scan.sourceArtifactId}`,
        practiceId: practiceA,
        objectKey: sourceKey,
        objectVersionId: "synthetic-source-version",
        objectEtag: "synthetic-source-etag",
        sha256: scan.subjectSha256,
        sizeBytes: rawSizeBytes,
        kind: "source",
        state: "CLAIMED",
        claimType: "source_artifact",
        claimId: scan.sourceArtifactId,
      },
    });
    await tx.templateTwinQuarantineArtifact.update({
      where: { id: quarantineId },
      data: {
        status: "ADMITTED",
        metadataMinimizationEvidence,
        admittedAt: new Date("2026-07-19T17:20:01.000Z"),
      },
    });
    await tx.templateTwinCompiledVersion.create({
      data: {
        id: scan.compiledVersionId,
        sourceArtifactId: scan.sourceArtifactId,
        noteTemplateId: scan.noteTemplateId,
        compilerVersion: "synthetic-compiler-v1",
        irSchemaVersion: 1,
        compiledDocumentIr: {},
        unsupportedElements: [],
        structureSha256: hash("synthetic-structure"),
        staticContentSha256: hash("synthetic-static"),
        certificationStatus: "NEEDS_CONFIRMATION",
        blockingUnsupportedCount: 0,
        latestSyntheticTestManifest: {},
        latestTestMappingsSha256: hash("synthetic-current-mappings"),
        latestTestOutputObjectKey: outputKey,
        latestTestOutputVersionId: outputVersionId,
        latestTestOutputEtag: outputEtag,
        latestTestOutputSha256: outputSha256,
        latestTestStaticContentSha256: hash("synthetic-static"),
        latestTestRoundTrip: {},
        latestTestVerifiedAt: new Date(),
        providerOwnershipEvidence: receipt as Prisma.InputJsonValue,
        providerOwnershipSha256: canonicalSha256(receipt),
      },
    });
    await tx.templateTwinObjectLedger.create({
      data: {
        id: `ledger-synthetic-current-output-${suffix}`,
        practiceId: practiceA,
        objectKey: outputKey,
        objectVersionId: outputVersionId,
        objectEtag: outputEtag,
        sha256: outputSha256,
        sizeBytes: rawSizeBytes,
        kind: "output",
        state: "CLAIMED",
        claimType: "compiled_test_output",
        claimId: scan.compiledVersionId,
      },
    });
  });

  const persisted = await observer.templateTwinCompiledVersion.findUnique({
    where: { id: scan.compiledVersionId },
    select: {
      providerOwnershipSha256: true,
      sourceArtifact: { select: { providerOwnershipSha256: true } },
    },
  });
  assert.equal(persisted?.providerOwnershipSha256, canonicalSha256(receipt));
  assert.equal(
    persisted?.sourceArtifact.providerOwnershipSha256,
    canonicalSha256(receipt),
  );
  await expectReject(
    () =>
      observer.templateTwinCertification.create({
        data: {
          id: `certification-staging-promotion-${suffix}`,
          compiledVersionId: scan.compiledVersionId,
          certifiedById: actorA,
          compiledStructureSha256: hash("synthetic-structure"),
          approvedMappingsSha256: hash("synthetic-mappings"),
          syntheticTestManifest: {},
          testOutputObjectKey: `practices/${practiceA}/template-twin/outputs/staging.docx`,
          testOutputSha256: hash("synthetic-output"),
        },
      }),
    /TEMPLATE_TWIN_CERTIFICATION_LIVE_PROVIDER_RECEIPT_REQUIRED/u,
  );
  await expectReject(
    () =>
      observer.noteTemplate.update({
        where: { id: scan.noteTemplateId },
        data: { status: "active" },
      }),
    /TEMPLATE_TWIN_ACTIVATION_LIVE_PROVIDER_RECEIPT_REQUIRED/u,
  );
  const linkedAt = new Date();
  await observer.templateTwinSyntheticQaAdmission.update({
    where: { id: admissionId },
    data: {
      phase: "SOURCE_VERIFIED",
      sourceArtifactId: scan.sourceArtifactId,
      sourceVerifiedAt: linkedAt,
    },
  });
  await observer.templateTwinSyntheticQaAdmission.update({
    where: { id: admissionId },
    data: {
      phase: "TEMPLATE_LINKED",
      noteTemplateId: scan.noteTemplateId,
      noteTemplateVersion: 1,
      templateLinkedAt: linkedAt,
    },
  });
  return {
    uploadAdmissionId: admissionId,
    sourceArtifactId: scan.sourceArtifactId,
    compiledVersionId: scan.compiledVersionId,
    noteTemplateId: scan.noteTemplateId,
    sourceLineageId: scan.sourceLineageId,
    sourceLineageVersion: 1,
    sourceSha256: scan.sourceSha256,
  };
}

interface PreCertificationVoiceFixture {
  readonly parentAdmissionId: string;
  readonly admissionId: string;
  readonly patientId: string;
  readonly visitId: string;
  readonly audioSha256: string;
  readonly audioSizeBytes: number;
  readonly audioMimeType: string;
  readonly audioObjectKey: string;
  readonly sourceArtifactId: string;
  readonly compiledVersionId: string;
  readonly noteTemplateId: string;
  readonly sourceLineageId: string;
  readonly sourceLineageVersion: number;
  readonly sourceSha256: string;
  readonly sourceSizeBytes: number;
}

async function createPreCertificationVoiceFixture(input: {
  readonly marker: string;
  readonly lineage: {
    readonly sourceArtifactId: string;
    readonly compiledVersionId: string;
    readonly noteTemplateId: string;
    readonly sourceLineageId: string;
    readonly sourceLineageVersion: number;
    readonly sourceSha256: string;
  };
}): Promise<PreCertificationVoiceFixture> {
  const source = await observer.templateTwinSourceArtifact.findUniqueOrThrow({
    where: { id: input.lineage.sourceArtifactId },
    select: { sizeBytes: true },
  });
  const parentAdmissionId = `synthetic-voice-parent-${input.marker}-${suffix}`;
  const admissionId = `synthetic-voice-child-${input.marker}-${suffix}`;
  const patientId = `synthetic-voice-patient-${input.marker}-${suffix}`;
  const visitId = `synthetic-voice-visit-${input.marker}-${suffix}`;
  const audioSha256 = hash(`synthetic-voice-audio:${input.marker}`);
  const audioSizeBytes = 512;
  const audioMimeType = "audio/wav";
  const audioObjectKey =
    `template-twin-synthetic-voice/${practiceA}/${actorA}/` +
    `${admissionId}/${audioSha256}`;
  const now = new Date();
  const expiresAt = new Date(now.getTime() + 15 * 60 * 1_000);

  await observer.templateTwinSyntheticQaAdmission.create({
    data: {
      id: parentAdmissionId,
      practiceId: practiceA,
      actorId: actorA,
      sourceSha256: input.lineage.sourceSha256,
      sourceSizeBytes: source.sizeBytes,
      fixtureVersion: "template-twin-staging-safe-docx/1.0.0",
      providerMode: "SYNTHETIC_LIFECYCLE",
      purpose: "UPLOAD",
      requestSha256: hash(`synthetic-voice-parent-request:${input.marker}`),
      pinnedGlobalRolloutGeneration: 1,
      pinnedPracticeRolloutGeneration: 1,
      sourceArtifactId: input.lineage.sourceArtifactId,
      noteTemplateId: input.lineage.noteTemplateId,
      noteTemplateVersion: 1,
      expiresAt,
    },
  });
  await observer.templateTwinSyntheticQaAdmission.update({
    where: { id: parentAdmissionId },
    data: { phase: "SOURCE_VERIFIED", sourceVerifiedAt: now },
  });
  await observer.templateTwinSyntheticQaAdmission.update({
    where: { id: parentAdmissionId },
    data: { phase: "TEMPLATE_LINKED", templateLinkedAt: now },
  });

  await observer.templateTwinSyntheticQaAdmission.create({
    data: {
      id: admissionId,
      practiceId: practiceA,
      actorId: actorA,
      parentAdmissionId,
      sourceSha256: input.lineage.sourceSha256,
      sourceSizeBytes: source.sizeBytes,
      fixtureVersion: "template-twin-staging-safe-docx/1.0.0",
      providerMode: "SYNTHETIC_MOCK_VOICE",
      purpose: "VISIT",
      requestSha256: hash(`synthetic-voice-child-request:${input.marker}`),
      payloadSha256: hash(`synthetic-voice-child-payload:${input.marker}`),
      preCertificationVoiceEvidence: true,
      audioSha256,
      audioSizeBytes,
      audioMimeType,
      audioObjectKey,
      pinnedGlobalRolloutGeneration: 1,
      pinnedPracticeRolloutGeneration: 1,
      sourceArtifactId: input.lineage.sourceArtifactId,
      noteTemplateId: input.lineage.noteTemplateId,
      noteTemplateVersion: 1,
      expiresAt,
    },
  });
  await observer.templateTwinSyntheticQaAdmission.update({
    where: { id: admissionId },
    data: { phase: "SOURCE_VERIFIED", sourceVerifiedAt: now },
  });
  await observer.templateTwinSyntheticQaAdmission.update({
    where: { id: admissionId },
    data: { phase: "TEMPLATE_LINKED", templateLinkedAt: now },
  });
  await observer.transcribeMdPatient.create({
    data: {
      id: patientId,
      practiceId: practiceA,
      name: "Template Twin Synthetic QA",
      externalId: "SYNTHETIC-QA-ONLY",
      allergies: [],
    },
  });
  await observer.transcribeVisit.create({
    data: {
      id: visitId,
      userId: actorA,
      patientId,
      patientName: "Template Twin Synthetic QA",
      specialty: "synthetic-template-review",
      chiefComplaint: "Synthetic Template Twin voice review only",
      inputMode: "audio_upload",
      status: "QUEUED",
      audioKey: audioObjectKey,
      audioMimeType,
      audioSizeBytes,
      audioUploadedAt: now,
      noteTemplateId: input.lineage.noteTemplateId,
      noteTemplateVersion: 1,
    },
  });
  await observer.templateTwinSyntheticQaAdmission.update({
    where: { id: admissionId },
    data: { phase: "VISIT_LINKED", visitId, visitLinkedAt: now },
  });
  return {
    parentAdmissionId,
    admissionId,
    patientId,
    visitId,
    audioSha256,
    audioSizeBytes,
    audioMimeType,
    audioObjectKey,
    sourceArtifactId: input.lineage.sourceArtifactId,
    compiledVersionId: input.lineage.compiledVersionId,
    noteTemplateId: input.lineage.noteTemplateId,
    sourceLineageId: input.lineage.sourceLineageId,
    sourceLineageVersion: input.lineage.sourceLineageVersion,
    sourceSha256: input.lineage.sourceSha256,
    sourceSizeBytes: source.sizeBytes,
  };
}

function preCertificationVoiceSubjectSha256(
  fixture: PreCertificationVoiceFixture,
): string {
  return canonicalSha256({
    contractVersion: "template-twin-synthetic-voice-subject-v1",
    admissionId: fixture.admissionId,
    parentAdmissionId: fixture.parentAdmissionId,
    practiceId: practiceA,
    actorUserId: actorA,
    visitId: fixture.visitId,
    inputMode: "audio_upload",
    audioSha256: fixture.audioSha256,
    audioSizeBytes: fixture.audioSizeBytes,
    audioMimeType: fixture.audioMimeType,
    audioObjectKey: fixture.audioObjectKey,
    sourceArtifactId: fixture.sourceArtifactId,
    compiledVersionId: fixture.compiledVersionId,
    noteTemplateId: fixture.noteTemplateId,
    noteTemplateVersion: 1,
    sourceLineageId: fixture.sourceLineageId,
    sourceLineageVersion: fixture.sourceLineageVersion,
    sourceSha256: fixture.sourceSha256,
    logicalAttempt: 1,
  });
}

async function insertPreCertificationVoiceExecution(input: {
  readonly fixture: PreCertificationVoiceFixture;
  readonly marker: string;
  readonly subjectSha256?: string;
  readonly logicalAttempt?: number;
  readonly operation?:
    | "SYNTHETIC_EVIDENCE_TRANSCRIPTION"
    | "SYNTHETIC_EVIDENCE_EXTRACTION";
}): Promise<string> {
  const id = randomUUID();
  const operation = input.operation ?? "SYNTHETIC_EVIDENCE_TRANSCRIPTION";
  const logicalAttempt = input.logicalAttempt ?? 1;
  const subjectSha256 =
    input.subjectSha256 ?? preCertificationVoiceSubjectSha256(input.fixture);
  const runtimeIdentitySha256 = joinedHash([
    "template-twin-provider-runtime-v1",
    "SYNTHETIC_QA",
    "1",
    "1",
    "-",
    "-",
    "-",
    "-",
  ]);
  const ownershipKey = joinedHash([
    "template-twin-provider-ownership-v2",
    practiceA,
    "SYNTHETIC_EVIDENCE",
    input.fixture.admissionId,
    String(logicalAttempt),
    operation,
    "primary",
  ]);
  const providerConfigurationSha256 = canonicalSha256({
    contractVersion: "template-twin-provider-configuration-v1",
    provider: "deepgram",
    model: "nova-3-medical",
    configuration: {
      mimeType: input.fixture.audioMimeType,
      crossProviderFallback: false,
      maxAttempts: 1,
    },
  });
  const inputSha256 = canonicalSha256({
    purpose: "tm_transcribe",
    audioSha256: input.fixture.audioSha256,
    audioSizeBytes: input.fixture.audioSizeBytes,
    audioMimeType: input.fixture.audioMimeType,
    audioObjectKey: input.fixture.audioObjectKey,
  });
  const idempotencyKey = joinedHash([
    "template-twin-provider-idempotency-v2",
    ownershipKey,
    actorA,
    subjectSha256,
    inputSha256,
    "deepgram",
    "SYNTHETIC_QA",
    "nova-3-medical",
    "synthetic-evidence-transcription-v1",
    providerConfigurationSha256,
    runtimeIdentitySha256,
    input.fixture.visitId,
    "audio_upload",
    input.fixture.sourceArtifactId,
    input.fixture.compiledVersionId,
    input.fixture.noteTemplateId,
    "1",
    input.fixture.sourceLineageId,
    String(input.fixture.sourceLineageVersion),
    input.fixture.sourceSha256,
    input.fixture.admissionId,
  ]);
  await executor.$executeRaw(Prisma.sql`
    INSERT INTO "template_twin_provider_executions" (
      "id", "practiceId", "actorUserId", "visitId", "visitInputMode",
      "scope", "operation", "operationInstance", "logicalAttempt",
      "subjectId", "subjectSha256", "sourceArtifactId",
      "compiledVersionId", "noteTemplateId", "noteTemplateVersion",
      "sourceLineageId", "sourceLineageVersion", "sourceSha256",
      "inputSha256", "provider", "providerMode", "model",
      "operationVersion", "providerConfigurationSha256",
      "runtimeIdentitySha256", "ownershipKey", "idempotencyKey",
      "pinnedGlobalRolloutGeneration", "pinnedPracticeRolloutGeneration",
      "releaseId", "releaseIdentitySha256", "runtimeManifestSha256",
      "runtimeInstanceId", "syntheticAdmissionId", "updatedAt"
    ) VALUES (
      ${id}, ${practiceA}, ${actorA}, ${input.fixture.visitId},
      'audio_upload', 'SYNTHETIC_EVIDENCE', ${operation}, 'primary',
      ${logicalAttempt}, ${input.fixture.admissionId}, ${subjectSha256},
      ${input.fixture.sourceArtifactId}, ${input.fixture.compiledVersionId},
      ${input.fixture.noteTemplateId}, 1, ${input.fixture.sourceLineageId},
      ${input.fixture.sourceLineageVersion}, ${input.fixture.sourceSha256},
      ${inputSha256}, 'deepgram', 'SYNTHETIC_QA', 'nova-3-medical',
      'synthetic-evidence-transcription-v1',
      ${providerConfigurationSha256}, ${runtimeIdentitySha256},
      ${ownershipKey}, ${idempotencyKey}, 1, 1, NULL, NULL, NULL, NULL,
      ${input.fixture.admissionId}, clock_timestamp()
    )
  `);
  return id;
}

async function provePreCertificationVoiceAuthority(input: {
  readonly sourceArtifactId: string;
  readonly compiledVersionId: string;
  readonly noteTemplateId: string;
  readonly sourceLineageId: string;
  readonly sourceLineageVersion: number;
  readonly sourceSha256: string;
}): Promise<void> {
  const fixture = await createPreCertificationVoiceFixture({
    marker: "positive",
    lineage: input,
  });
  await expectReject(
    () =>
      insertPreCertificationVoiceExecution({
        fixture,
        marker: "wrong-audio-subject",
        subjectSha256: hash("wrong-synthetic-voice-audio-subject"),
      }),
    /TEMPLATE_TWIN_PROVIDER_SYNTHETIC_ADMISSION_INVALID/u,
  );
  await expectReject(
    () =>
      insertPreCertificationVoiceExecution({
        fixture,
        marker: "wrong-attempt",
        logicalAttempt: 2,
      }),
    /template_twin_provider_execution_synthetic_voice_shape_check|TEMPLATE_TWIN_PROVIDER_SYNTHETIC_ADMISSION_INVALID/u,
  );
  await expectReject(
    () =>
      insertPreCertificationVoiceExecution({
        fixture,
        marker: "wrong-operation",
        operation: "SYNTHETIC_EVIDENCE_EXTRACTION",
      }),
    /TEMPLATE_TWIN_PROVIDER_SYNTHETIC_ADMISSION_INVALID/u,
  );

  await expectReject(
    () =>
      observer.transcribeVisit.update({
        where: { id: fixture.visitId },
        data: { audioMimeType: "audio/mpeg" },
      }),
    /Template Twin synthetic voice visit is immutable/u,
  );
  await expectReject(
    () => observer.transcribeVisit.delete({ where: { id: fixture.visitId } }),
    /Template Twin synthetic voice visit is immutable/u,
  );
  await expectReject(
    () =>
      observer.transcribeMdPatient.update({
        where: { id: fixture.patientId },
        data: { name: "Mutated synthetic patient" },
      }),
    /Template Twin synthetic QA patient is immutable/u,
  );
  await expectReject(
    () =>
      observer.transcribeMdPatient.delete({ where: { id: fixture.patientId } }),
    /Template Twin synthetic QA patient cannot be deleted/u,
  );
  await expectReject(
    () =>
      observer.templateTwinSyntheticQaAdmission.update({
        where: { id: fixture.admissionId },
        data: { audioSha256: hash("mutated-synthetic-audio") },
      }),
    /Template Twin synthetic QA admission identity is immutable/u,
  );
  await expectReject(
    () =>
      observer.templateTwinSyntheticQaAdmission.delete({
        where: { id: fixture.admissionId },
      }),
    /Template Twin synthetic voice admission is immutable/u,
  );

  const executionId = await insertPreCertificationVoiceExecution({
    fixture,
    marker: "positive",
  });
  const claimA = randomBytes(32).toString("hex");
  const claimB = randomBytes(32).toString("hex");
  const concurrentClaims = await Promise.all([
    claim(contenderA, executionId, claimA),
    claim(contenderB, executionId, claimB),
  ]);
  assert.deepEqual([...concurrentClaims].sort(), [0, 1]);
  const winningClaim = concurrentClaims[0] === 1 ? claimA : claimB;
  const resultPayload = {
    contractVersion: "template-twin-provider-result-v1",
    output: { provider: "deepgram-batch", synthetic: true },
  };
  assert.equal(
    await executor.$executeRaw(Prisma.sql`
      UPDATE "template_twin_provider_executions"
      SET "status" = 'SUCCEEDED'::"VisitAutomationProviderExecutionStatus",
          "resultPayload" = ${JSON.stringify(resultPayload)}::JSONB,
          "resultSha256" = ${canonicalSha256(resultPayload)},
          "resultVersion" = 'template-twin-provider-result-v1',
          "completedAt" = clock_timestamp(), "updatedAt" = clock_timestamp()
      WHERE "id" = ${executionId} AND "claimId" = ${winningClaim}
    `),
    1,
  );
  assert.equal(
    await claim(executor, executionId, randomBytes(32).toString("hex")),
    0,
  );

  const revokedChild = await createPreCertificationVoiceFixture({
    marker: "revoked-child",
    lineage: input,
  });
  await observer.templateTwinSyntheticQaAdmission.update({
    where: { id: revokedChild.admissionId },
    data: { phase: "REVOKED", revokedAt: new Date() },
  });
  await expectReject(
    () =>
      insertPreCertificationVoiceExecution({
        fixture: revokedChild,
        marker: "revoked-child",
      }),
    /TEMPLATE_TWIN_PROVIDER_SYNTHETIC_ADMISSION_INVALID/u,
  );

  const revokedParent = await createPreCertificationVoiceFixture({
    marker: "revoked-parent",
    lineage: input,
  });
  await observer.templateTwinSyntheticQaAdmission.update({
    where: { id: revokedParent.parentAdmissionId },
    data: { phase: "REVOKED", revokedAt: new Date() },
  });
  await expectReject(
    () =>
      insertPreCertificationVoiceExecution({
        fixture: revokedParent,
        marker: "revoked-parent",
      }),
    /TEMPLATE_TWIN_PROVIDER_SYNTHETIC_ADMISSION_INVALID/u,
  );
}

async function proveCrossPhysicianTemplateExecutionRejected(input: {
  readonly sourceArtifactId: string;
  readonly compiledVersionId: string;
  readonly noteTemplateId: string;
  readonly sourceLineageId: string;
  readonly sourceLineageVersion: number;
  readonly sourceSha256: string;
}): Promise<void> {
  const patientId = `synthetic-provider-patient-owner-fence-${suffix}`;
  const visitId = `synthetic-provider-visit-owner-fence-${suffix}`;
  await observer.transcribeMdPatient.create({
    data: {
      id: patientId,
      name: "Synthetic Provider Ownership",
      practiceId: practiceA,
    },
  });
  await observer.transcribeVisit.create({
    data: {
      id: visitId,
      userId: actorA2,
      patientId,
      specialty: "synthetic",
      inputMode: "text_notes",
      status: "QUEUED",
      noteTemplateId: input.noteTemplateId,
      noteTemplateVersion: 1,
    },
  });
  await expectReject(
    () =>
      reserveVisitPipelineExecution({
        db: executor,
        marker: "cross-physician-template-owner",
        actorUserId: actorA2,
        visitId,
        visitInputMode: "text_notes",
        ...input,
      }),
    /TEMPLATE_TWIN_PROVIDER_ARTIFACT_LINEAGE_MISMATCH/u,
  );
}

interface SyntheticCurrentAuthorityFixture extends SyntheticStagingLineage {
  readonly certificationId: string;
  readonly admissionId: string;
  readonly patientId: string;
  readonly visitId: string;
  readonly runId: string;
  readonly requestSha256: string;
  readonly payloadSha256: string;
  readonly workerClaimId: string;
}

function configureSyntheticProviderProofEnvironment(): void {
  Object.assign(process.env, {
    DATABASE_URL: databaseUrl,
    TEMPLATE_TWIN_STAGING_QA_ENABLED: "true",
    TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: "test",
    TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION:
      TEMPLATE_TWIN_SYNTHETIC_QA_RESOURCE_ATTESTATION,
    TEMPLATE_TWIN_STORAGE_PROFILE: "qa",
    REDIS_URL: "redis://127.0.0.1/15",
    MINIO_ENDPOINT: "127.0.0.1",
    MINIO_USE_SSL: "false",
    TRANSCRIBE_MD_MINIO_BUCKET: "meddoc-template-twin-qa-audio",
    TRANSCRIBE_MD_TEMPLATE_BUCKET: "meddoc-template-twin-qa-template",
    MOCK_AI_CALLS: "true",
    MOCK_TEMPLATE_TWIN_E2E: "true",
    APP_ENV: "test",
    APPLICATION_ENV: "test",
    DEPLOYMENT_ENV: "test",
    ENVIRONMENT: "test",
    SENTRY_ENVIRONMENT: "test",
    NEXT_PUBLIC_SENTRY_ENVIRONMENT: "test",
  });
}

async function createSyntheticCurrentAuthorityFixture(
  lineage: SyntheticStagingLineage,
): Promise<SyntheticCurrentAuthorityFixture> {
  const certificationId = `certification-synthetic-current-${suffix}`;
  const approvedMappingsSha256 = hash("synthetic-current-mappings");
  await observer.templateTwinCompiledVersion.update({
    where: { id: lineage.compiledVersionId },
    data: { certificationStatus: "CERTIFIED" },
  });
  await observer.templateTwinCertification.create({
    data: {
      id: certificationId,
      compiledVersionId: lineage.compiledVersionId,
      certifiedById: actorA,
      providerAuthorizationMode: "SYNTHETIC_QA",
      providerAuthorizationAdmissionId: lineage.uploadAdmissionId,
      compiledStructureSha256: hash("synthetic-structure"),
      approvedMappingsSha256,
      syntheticTestManifest: {},
      testOutputObjectKey:
        `practices/${practiceA}/template-twin/outputs/` +
        `synthetic-current-${suffix}.docx`,
      testOutputVersionId: "synthetic-current-output-version",
      testOutputEtag: "synthetic-current-output-etag",
      testOutputSha256: hash("synthetic-current-output"),
    },
  });
  await observer.templateTwinSyntheticQaAdmission.update({
    where: { id: lineage.uploadAdmissionId },
    data: {
      phase: "CERTIFIED",
      certificationId,
      mappingSha256: approvedMappingsSha256,
      certifiedAt: new Date(),
    },
  });
  await observer.noteTemplate.update({
    where: { id: lineage.noteTemplateId },
    data: { status: "active" },
  });

  const admissionId = `synthetic-current-admission-${suffix}`;
  const patientId = `synthetic-current-patient-${suffix}`;
  const visitId = `synthetic-current-visit-${suffix}`;
  const runId = `synthetic-current-run-${suffix}`;
  const requestSha256 = hash(`synthetic-current-request:${suffix}`);
  const payloadSha256 = hash(`synthetic-current-payload:${suffix}`);
  const workerClaimId = randomUUID();
  const now = new Date();
  const expiresAt = new Date(now.getTime() + 15 * 60 * 1_000);

  await observer.templateTwinSyntheticQaAdmission.create({
    data: {
      id: admissionId,
      practiceId: practiceA,
      actorId: actorA,
      parentAdmissionId: lineage.uploadAdmissionId,
      sourceSha256: lineage.sourceSha256,
      sourceSizeBytes: 4686,
      fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
      providerMode: "SYNTHETIC_TYPED",
      purpose: "VISIT",
      requestSha256,
      payloadSha256,
      pinnedGlobalRolloutGeneration: 1,
      pinnedPracticeRolloutGeneration: 1,
      sourceArtifactId: lineage.sourceArtifactId,
      noteTemplateId: lineage.noteTemplateId,
      noteTemplateVersion: 1,
      certificationId,
      mappingSha256: approvedMappingsSha256,
      expiresAt,
    },
  });
  await observer.templateTwinSyntheticQaAdmission.update({
    where: { id: admissionId },
    data: { phase: "SOURCE_VERIFIED", sourceVerifiedAt: now },
  });
  await observer.templateTwinSyntheticQaAdmission.update({
    where: { id: admissionId },
    data: { phase: "TEMPLATE_LINKED", templateLinkedAt: now },
  });
  await observer.templateTwinSyntheticQaAdmission.update({
    where: { id: admissionId },
    data: { phase: "CERTIFIED", certifiedAt: now },
  });
  await observer.transcribeMdPatient.create({
    data: {
      id: patientId,
      practiceId: practiceA,
      name: "Template Twin Synthetic QA",
      externalId: "SYNTHETIC-QA-ONLY",
      allergies: [],
    },
  });
  await observer.transcribeVisit.create({
    data: {
      id: visitId,
      userId: actorA,
      patientId,
      patientName: "Template Twin Synthetic QA",
      specialty: "synthetic-template-review",
      chiefComplaint: "Synthetic Template Twin QA only",
      inputMode: "text_notes",
      rawTextInput: TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
      status: "QUEUED",
      noteTemplateId: lineage.noteTemplateId,
      noteTemplateVersion: 1,
    },
  });
  await observer.templateTwinSyntheticQaAdmission.update({
    where: { id: admissionId },
    data: { phase: "VISIT_LINKED", visitId, visitLinkedAt: now },
  });
  await observer.templateTwinSyntheticQaRun.create({
    data: {
      id: runId,
      admissionId,
      practiceId: practiceA,
      doctorId: actorA,
      visitId,
      noteTemplateId: lineage.noteTemplateId,
      noteTemplateVersion: 1,
      requestSha256,
      payloadSha256,
      mode: "typed",
      fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
      pinnedGlobalRolloutGeneration: 1,
      pinnedPracticeRolloutGeneration: 1,
      status: "PENDING_ENQUEUE",
      attempt: 1,
    },
  });
  await observer.templateTwinSyntheticQaRun.update({
    where: { id: runId },
    data: { status: "ENQUEUED", enqueuedAt: now },
  });
  await observer.templateTwinSyntheticQaRun.update({
    where: { id: runId },
    data: {
      status: "PROCESSING",
      workerClaimId,
      workerClaimedAt: now,
      workerHeartbeatAt: now,
      workerLeaseExpiresAt: new Date(now.getTime() + 5 * 60 * 1_000),
      workerDeliveryCount: 1,
    },
  });
  await observer.templateTwinSyntheticQaAdmission.update({
    where: { id: admissionId },
    data: { phase: "PROCESSING" },
  });
  return {
    ...lineage,
    certificationId,
    admissionId,
    patientId,
    visitId,
    runId,
    requestSha256,
    payloadSha256,
    workerClaimId,
  };
}

function syntheticCurrentAuthorityContext(
  fixture: SyntheticCurrentAuthorityFixture,
  overrides: Partial<
    Pick<
      TemplateTwinProviderOwnershipContext,
      | "sourceArtifactId"
      | "compiledVersionId"
      | "noteTemplateId"
      | "noteTemplateVersion"
      | "sourceLineageId"
      | "sourceLineageVersion"
      | "sourceSha256"
    >
  > = {},
): TemplateTwinProviderOwnershipContext {
  const identity = {
    sourceArtifactId: overrides.sourceArtifactId ?? fixture.sourceArtifactId,
    compiledVersionId: overrides.compiledVersionId ?? fixture.compiledVersionId,
    noteTemplateId: overrides.noteTemplateId ?? fixture.noteTemplateId,
    noteTemplateVersion: overrides.noteTemplateVersion ?? 1,
    sourceLineageId: overrides.sourceLineageId ?? fixture.sourceLineageId,
    sourceLineageVersion:
      overrides.sourceLineageVersion ?? fixture.sourceLineageVersion,
    sourceSha256: overrides.sourceSha256 ?? fixture.sourceSha256,
  };
  return {
    practiceId: practiceA,
    actorUserId: actorA,
    visitId: fixture.visitId,
    visitInputMode: "text_notes",
    scope: "VISIT_PIPELINE",
    logicalAttempt: 1,
    subjectId: fixture.visitId,
    subjectSha256: templateTwinVisitProviderSubjectSha256({
      practiceId: practiceA,
      actorUserId: actorA,
      visitId: fixture.visitId,
      noteTemplateId: identity.noteTemplateId!,
      noteTemplateVersion: identity.noteTemplateVersion!,
      compiledVersionId: identity.compiledVersionId!,
      sourceArtifactId: identity.sourceArtifactId!,
      sourceLineageId: identity.sourceLineageId!,
      sourceLineageVersion: identity.sourceLineageVersion!,
      sourceSha256: identity.sourceSha256!,
      logicalAttempt: 1,
      visitInputMode: "text_notes",
    }),
    ...identity,
    syntheticAdmissionId: fixture.admissionId,
    rolloutToken: {
      practiceId: practiceA,
      globalGeneration: 1n,
      practiceGeneration: 1n,
    },
  };
}

function syntheticProviderContextInput(
  fixture: SyntheticCurrentAuthorityFixture,
  overrides: Partial<{
    admissionId: string;
    runId: string;
    visitId: string;
    practiceId: string;
    requestSha256: string;
    attempt: number;
    workerClaimId: string;
    pinnedGlobalGeneration: bigint;
    pinnedPracticeGeneration: bigint;
  }> = {},
) {
  return {
    mode: TEMPLATE_TWIN_SYNTHETIC_QA_MODE,
    fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
    admissionId: fixture.admissionId,
    runId: fixture.runId,
    visitId: fixture.visitId,
    practiceId: practiceA,
    requestSha256: fixture.requestSha256,
    attempt: 1,
    workerClaimId: fixture.workerClaimId,
    pinnedGlobalGeneration: 1n,
    pinnedPracticeGeneration: 1n,
    evidenceText: TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
    ...overrides,
  };
}

async function syntheticCurrentAuthority(input: {
  readonly fixture: SyntheticCurrentAuthorityFixture;
  readonly providerOverrides?: Parameters<
    typeof syntheticProviderContextInput
  >[1];
  readonly authorityOverrides?: Parameters<
    typeof syntheticCurrentAuthorityContext
  >[1];
}): Promise<boolean> {
  return runWithTemplateTwinSyntheticQaProviderContext(
    syntheticProviderContextInput(input.fixture, input.providerOverrides),
    () =>
      observer.$transaction((tx) =>
        currentProviderAuthority({
          tx,
          context: syntheticCurrentAuthorityContext(
            input.fixture,
            input.authorityOverrides,
          ),
          mode: "SYNTHETIC_QA",
        }),
      ),
    process.env,
  );
}

async function expectSyntheticAuthorityDriftDenied(input: {
  readonly fixture: SyntheticCurrentAuthorityFixture;
  readonly mutate: (tx: Prisma.TransactionClient) => Promise<unknown>;
}): Promise<void> {
  await runWithTemplateTwinSyntheticQaProviderContext(
    syntheticProviderContextInput(input.fixture),
    async () => {
      const expectedRollback = new Error(
        "expected-synthetic-authority-probe-rollback",
      );
      try {
        await observer.$transaction(async (tx) => {
          await tx.$executeRawUnsafe(
            "SET LOCAL session_replication_role = replica",
          );
          await input.mutate(tx);
          assert.equal(
            await currentProviderAuthority({
              tx,
              context: syntheticCurrentAuthorityContext(input.fixture),
              mode: "SYNTHETIC_QA",
            }),
            false,
          );
          throw expectedRollback;
        });
      } catch (error) {
        if (error !== expectedRollback) throw error;
      }
    },
    process.env,
  );
}

async function proveSyntheticCurrentProviderAuthority(
  lineage: SyntheticStagingLineage,
): Promise<void> {
  configureSyntheticProviderProofEnvironment();
  const fixture = await createSyntheticCurrentAuthorityFixture(lineage);
  assert.equal(await syntheticCurrentAuthority({ fixture }), true);
  assert.equal(
    await syntheticCurrentAuthority({
      fixture,
      providerOverrides: { runId: `wrong-run-${suffix}` },
    }),
    false,
  );
  assert.equal(
    await syntheticCurrentAuthority({
      fixture,
      providerOverrides: { workerClaimId: randomUUID() },
    }),
    false,
  );
  assert.equal(
    await syntheticCurrentAuthority({
      fixture,
      providerOverrides: { attempt: 2 },
    }),
    false,
  );
  assert.equal(
    await syntheticCurrentAuthority({
      fixture,
      providerOverrides: { pinnedGlobalGeneration: 2n },
    }),
    false,
  );
  assert.equal(
    await syntheticCurrentAuthority({
      fixture,
      authorityOverrides: { sourceArtifactId: `wrong-source-${suffix}` },
    }),
    false,
  );
  assert.equal(
    await syntheticCurrentAuthority({
      fixture,
      authorityOverrides: { noteTemplateId: `wrong-template-${suffix}` },
    }),
    false,
  );

  await expectSyntheticAuthorityDriftDenied({
    fixture,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "transcribe_md_patients"
        SET "mrn" = 'synthetic-invalid-mrn'
        WHERE "id" = ${fixture.patientId}
      `),
  });
  await expectSyntheticAuthorityDriftDenied({
    fixture,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_synthetic_qa_runs"
        SET "workerClaimedAt" = clock_timestamp() - interval '3 seconds',
          "workerHeartbeatAt" = clock_timestamp() - interval '2 seconds',
          "workerLeaseExpiresAt" = clock_timestamp() - interval '1 second'
        WHERE "id" = ${fixture.runId}
      `),
  });
  await expectSyntheticAuthorityDriftDenied({
    fixture,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_synthetic_qa_runs"
        SET "status" = 'ENQUEUED', "workerClaimId" = NULL,
          "workerClaimedAt" = NULL, "workerHeartbeatAt" = NULL,
          "workerLeaseExpiresAt" = NULL, "workerDeliveryCount" = 0
        WHERE "id" = ${fixture.runId}
      `),
  });
  await expectSyntheticAuthorityDriftDenied({
    fixture,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_synthetic_qa_runs"
        SET "doctorId" = ${actorA2}
        WHERE "id" = ${fixture.runId}
      `),
  });
  await expectSyntheticAuthorityDriftDenied({
    fixture,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_synthetic_qa_runs"
        SET "pinnedGlobalRolloutGeneration" = 2
        WHERE "id" = ${fixture.runId}
      `),
  });
  await expectSyntheticAuthorityDriftDenied({
    fixture,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_synthetic_qa_runs"
        SET "noteTemplateVersion" = 2
        WHERE "id" = ${fixture.runId}
      `),
  });
  await expectSyntheticAuthorityDriftDenied({
    fixture,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_synthetic_qa_admissions"
        SET "phase" = 'VISIT_LINKED'
        WHERE "id" = ${fixture.admissionId}
      `),
  });
  await expectSyntheticAuthorityDriftDenied({
    fixture,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_synthetic_qa_admissions"
        SET "phase" = 'REVOKED', "revokedAt" = clock_timestamp()
        WHERE "id" = ${fixture.uploadAdmissionId}
      `),
  });
  await expectSyntheticAuthorityDriftDenied({
    fixture,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_synthetic_qa_admissions"
        SET "expiresAt" = clock_timestamp() - interval '1 second'
        WHERE "id" = ${fixture.uploadAdmissionId}
      `),
  });
  await expectSyntheticAuthorityDriftDenied({
    fixture,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_certifications"
        SET "certifiedById" = ${actorA2}
        WHERE "id" = ${fixture.certificationId}
      `),
  });
  await expectSyntheticAuthorityDriftDenied({
    fixture,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_source_artifacts"
        SET "practiceId" = ${practiceB}
        WHERE "id" = ${fixture.sourceArtifactId}
      `),
  });
  await expectSyntheticAuthorityDriftDenied({
    fixture,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "note_templates"
        SET "templateKind" = 'structured'
        WHERE "id" = ${fixture.noteTemplateId}
      `),
  });
}

async function proveRevokedAuthorityTerminalization(): Promise<void> {
  const reservedFailure = executionIdentity({
    marker: "authority-revoked-before-provider",
    actorUserId: actorA2,
  });
  const ambiguousFailure = executionIdentity({
    marker: "authority-revoked-ambiguous-provider",
    actorUserId: actorA2,
  });
  await reserve(executor, reservedFailure);
  await reserve(executor, ambiguousFailure);
  const ambiguousClaim = randomBytes(32).toString("hex");
  assert.equal(await claim(executor, ambiguousFailure.id, ambiguousClaim), 1);

  await observer.user.update({
    where: { id: actorA2 },
    data: { deactivatedAt: new Date(), isActive: false },
  });
  assert.equal(
    await executor.$executeRaw(Prisma.sql`
      UPDATE "template_twin_provider_executions"
      SET "status" = 'FAILED'::"VisitAutomationProviderExecutionStatus",
          "failureCode" = 'AUTHORITY_REVOKED_BEFORE_PROVIDER',
          "completedAt" = clock_timestamp(), "updatedAt" = clock_timestamp()
      WHERE "id" = ${reservedFailure.id}
        AND "status" = 'RESERVED'::"VisitAutomationProviderExecutionStatus"
    `),
    1,
  );
  assert.equal(
    await executor.$executeRaw(Prisma.sql`
      UPDATE "template_twin_provider_executions"
      SET "status" = 'UNKNOWN_OUTCOME'::"VisitAutomationProviderExecutionStatus",
          "failureCode" = 'PROVIDER_OUTCOME_UNKNOWN',
          "completedAt" = clock_timestamp(), "updatedAt" = clock_timestamp()
      WHERE "id" = ${ambiguousFailure.id}
        AND "status" = 'IN_FLIGHT'::"VisitAutomationProviderExecutionStatus"
        AND "claimId" = ${ambiguousClaim}
    `),
    1,
  );
  const rows = await observer.templateTwinProviderExecution.findMany({
    where: { id: { in: [reservedFailure.id, ambiguousFailure.id] } },
    select: {
      id: true,
      status: true,
      invocationCount: true,
      failureCode: true,
      resultPayload: true,
      resultSha256: true,
    },
    orderBy: { id: "asc" },
  });
  assert.deepEqual(
    rows.map((row) => ({
      status: row.status,
      invocationCount: row.invocationCount,
      failureCode: row.failureCode,
      resultPayload: row.resultPayload,
      resultSha256: row.resultSha256,
    })),
    [reservedFailure, ambiguousFailure]
      .sort((left, right) => left.id.localeCompare(right.id))
      .map((identity) =>
        identity.id === reservedFailure.id
          ? {
              status: "FAILED",
              invocationCount: 0,
              failureCode: "AUTHORITY_REVOKED_BEFORE_PROVIDER",
              resultPayload: null,
              resultSha256: null,
            }
          : {
              status: "UNKNOWN_OUTCOME",
              invocationCount: 1,
              failureCode: "PROVIDER_OUTCOME_UNKNOWN",
              resultPayload: null,
              resultSha256: null,
            },
      ),
  );
  assert.equal(
    await claim(executor, ambiguousFailure.id, randomBytes(32).toString("hex")),
    0,
  );
  await expectReject(
    () =>
      executor.$executeRaw(Prisma.sql`
        UPDATE "template_twin_provider_executions"
        SET "status" = 'SUCCEEDED'::"VisitAutomationProviderExecutionStatus",
            "resultPayload" = '{}'::JSONB,
            "resultSha256" = ${canonicalSha256({})},
            "resultVersion" = 'template-twin-provider-result-v1',
            "failureCode" = NULL, "updatedAt" = clock_timestamp()
        WHERE "id" = ${ambiguousFailure.id}
      `),
    /TEMPLATE_TWIN_PROVIDER_ACTOR_NOT_AUTHORIZED/u,
  );
  await observer.user.update({
    where: { id: actorA2 },
    data: { deactivatedAt: null, isActive: true },
  });
  await expectReject(
    () =>
      executor.$executeRaw(Prisma.sql`
        UPDATE "template_twin_provider_executions"
        SET "status" = 'SUCCEEDED'::"VisitAutomationProviderExecutionStatus",
            "resultPayload" = '{}'::JSONB,
            "resultSha256" = ${canonicalSha256({})},
            "resultVersion" = 'template-twin-provider-result-v1',
            "failureCode" = NULL, "updatedAt" = clock_timestamp()
        WHERE "id" = ${ambiguousFailure.id}
      `),
    /TEMPLATE_TWIN_PROVIDER_EXECUTION_TERMINAL_IMMUTABLE/u,
  );
}

async function expectProductionArtifactModeRejected(input: {
  marker: string;
  receipt: Record<string, unknown>;
}): Promise<void> {
  await expectReject(
    () =>
      observer.$executeRaw(Prisma.sql`
        INSERT INTO "template_twin_static_assets" (
          "id", "practiceId", "sha256", "mimeType", "width", "height",
          "sizeBytes", "scannerVersion", "ocrEngineVersion", "ocrTextSha256",
          "metadataEvidenceSha256", "privacyEvidenceSha256",
          "privacyScanProvider", "privacyScanModel",
          "inspectionEvidenceSha256", "inspectionEvidence", "createdById",
          "providerOwnershipEvidence", "providerOwnershipSha256", "updatedAt"
        ) VALUES (
          ${`static-${input.marker}-${suffix}`}, ${practiceA},
          ${hash(`static:${input.marker}`)}, 'image/png', 1, 1, 68,
          'synthetic-scanner-v1', 'synthetic-ocr-v1', ${hash("ocr")},
          ${hash("metadata")}, ${hash("privacy")}, 'anthropic',
          'synthetic-model-v1', ${hash("inspection")}, '{}'::JSONB, ${adminA},
          ${JSON.stringify(input.receipt)}::JSONB,
          ${canonicalSha256(input.receipt)}::CHAR(64), clock_timestamp()
        )
      `),
    /TEMPLATE_TWIN_PROVIDER_RECEIPT_MODE_INVALID/u,
  );
}

async function proveCustomExampleFailurePersistence(): Promise<void> {
  const noteTemplateId = `template-custom-failure-${suffix}`;
  const sourceArtifactId = `source-custom-failure-${suffix}`;
  const compiledVersionId = `compiled-custom-failure-${suffix}`;
  const fieldDefinitionId = `field-custom-failure-${suffix}`;
  const fieldIntentDecisionId = `intent-custom-failure-${suffix}`;
  const commonHash = hash(`custom-failure:${suffix}`);
  await observer.noteTemplate.create({
    data: {
      id: noteTemplateId,
      doctorId: actorA,
      name: "Synthetic custom failure template",
      encounterType: "synthetic",
      sections: [],
      version: 1,
      versionDescription: "Synthetic database contract fixture",
      status: "draft",
      isSystemDefault: false,
      lineageId: `lineage-custom-failure-${suffix}`,
      templateKind: "template_twin_docx",
    },
  });
  await observer.$executeRawUnsafe(
    'ALTER TABLE "template_twin_source_artifacts" DISABLE TRIGGER USER',
  );
  await observer.$executeRawUnsafe(
    'ALTER TABLE "template_twin_compiled_versions" DISABLE TRIGGER USER',
  );
  try {
    await observer.$executeRaw(Prisma.sql`
      INSERT INTO "template_twin_source_artifacts" (
        "id", "practiceId", "createdById", "lineageId", "lineageVersion",
        "sha256", "mimeType", "sizeBytes", "validationStatus",
        "rejectionCodes"
      ) VALUES (
        ${sourceArtifactId}, ${practiceA}, ${actorA},
        ${`lineage-custom-failure-${suffix}`}, 1, ${commonHash},
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        1024, 'quarantined', ARRAY['SYNTHETIC_FIXTURE']::TEXT[]
      )
    `);
    await observer.$executeRaw(Prisma.sql`
      INSERT INTO "template_twin_compiled_versions" (
        "id", "sourceArtifactId", "noteTemplateId", "compilerVersion",
        "irSchemaVersion", "compiledDocumentIr", "unsupportedElements",
        "structureSha256", "staticContentSha256", "certificationStatus",
        "blockingUnsupportedCount"
      ) VALUES (
        ${compiledVersionId}, ${sourceArtifactId}, ${noteTemplateId},
        'synthetic-compiler-v1', 1, '{}'::JSONB, '[]'::JSONB, ${commonHash},
        ${hash(`static:${suffix}`)},
        'NEEDS_CONFIRMATION'::"TemplateTwinCertificationStatus", 0
      )
    `);
  } finally {
    await observer.$executeRawUnsafe(
      'ALTER TABLE "template_twin_compiled_versions" ENABLE TRIGGER USER',
    );
    await observer.$executeRawUnsafe(
      'ALTER TABLE "template_twin_source_artifacts" ENABLE TRIGGER USER',
    );
  }
  await observer.templateTwinFieldDefinition.create({
    data: {
      id: fieldDefinitionId,
      compiledVersionId,
      fieldId: "synthetic-custom-field",
      displayOrder: 0,
      originalLabel: "Synthetic custom field",
      fieldKind: "plain_text",
      allowedOptions: [],
      rendererBinding: { synthetic: true },
      detectionStatus: "NEEDS_CONFIRMATION",
      clinicallyMaterial: false,
      criticality: "routine",
      required: false,
    },
  });
  await observer.templateTwinFieldIntentDecision.create({
    data: {
      id: fieldIntentDecisionId,
      fieldDefinitionId,
      version: 1,
      intentKind: "CUSTOM_CONCEPT",
      customConceptId: "synthetic.custom.concept",
      customSpec: { synthetic: true },
      customSpecSha256: hash("synthetic-custom-spec"),
      reason: "Synthetic custom example database contract",
      decidedById: actorA,
    },
  });
  const failureId = `custom-failure-${suffix}`;
  const commonInsert = {
    batchId: `custom-batch-${suffix}`,
    practiceId: practiceA,
    compiledVersionId,
    fieldDefinitionId,
    fieldIntentDecisionId,
    fieldId: "synthetic-custom-field",
    conceptId: "synthetic.custom.concept",
    exampleKind: "POSITIVE",
    exampleDefinitionSha256: hash("definition"),
    exampleEvidenceSha256: hash("evidence"),
    specificationSha256: hash("specification"),
    specificationSetSha256: hash("specification-set"),
    mappingsSha256: hash("mappings"),
    fieldIntentsSha256: hash("field-intents"),
    contractVersion: "template-twin-custom-example-proof/1.0.0",
    extractionSchemaSha256: hash("schema"),
    extractorVersion: "synthetic-extractor-v1",
    extractionSchemaVersion: "synthetic-schema-v1",
    provider: "anthropic",
    providerSha256: hash("anthropic"),
    model: "synthetic-model-v1",
    modelSha256: hash("synthetic-model-v1"),
    executedById: actorA,
  };
  await observer.templateTwinCustomExampleExecution.create({
    data: {
      id: failureId,
      ...commonInsert,
      exampleId: "failure",
      resultStatus: "extraction_rejected",
      resultValue: { value: null, unit: null },
      resultFactCount: 0,
      resultSummary: { targetPresent: false, extractionRejected: true },
      resultSha256: hash("failure-result"),
      passed: false,
      failureCode: "TT_CUSTOM_EXAMPLE_EXTRACTION_REJECTED",
    },
  });
  const persisted =
    await observer.templateTwinCustomExampleExecution.findUnique({
      where: { id: failureId },
      select: {
        passed: true,
        failureCode: true,
        providerOwnershipSha256: true,
      },
    });
  assert.deepEqual(persisted, {
    passed: false,
    failureCode: "TT_CUSTOM_EXAMPLE_EXTRACTION_REJECTED",
    providerOwnershipSha256: null,
  });
  await expectReject(
    () =>
      observer.templateTwinCustomExampleExecution.create({
        data: {
          id: `custom-unowned-success-${suffix}`,
          ...commonInsert,
          exampleId: "unowned-success",
          resultStatus: "supported",
          resultValue: { value: "synthetic", unit: null },
          resultFactCount: 1,
          resultSummary: { targetPresent: true },
          resultSha256: hash("unowned-success-result"),
          passed: true,
          failureCode: null,
        },
      }),
    /TEMPLATE_TWIN_PROVIDER_RECEIPT_REQUIRED/u,
  );
}

interface LiveReleaseFixture {
  readonly authority: LiveReleaseAuthority;
  readonly releaseActor: {
    readonly userId: string;
    readonly sessionId: string;
  };
  readonly releaseActorEmail: string;
  readonly releaseActorPracticeId: string;
}

async function createLiveReleaseFixture(): Promise<LiveReleaseFixture> {
  process.env.DATABASE_URL ??= databaseUrl;
  process.env.TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL = databaseUrl;
  process.env.TEMPLATE_TWIN_KILL_SWITCH = "false";
  process.env.TEMPLATE_TWIN_RUNTIME_MODE = "standard";
  const releaseControl =
    await import("../../../apps/transcribe-md/src/lib/template-twin/release-control");
  const contracts =
    await import("../../../apps/transcribe-md/src/lib/template-twin/release-control-contracts");

  const administratorPracticeId = `synthetic-provider-release-admin-${suffix}`;
  const creatorId = `synthetic-provider-release-creator-${suffix}`;
  const creatorEmail = `${creatorId}@synthetic.test`;
  const creatorSession = `synthetic-provider-release-session-${suffix}`;
  const runtimeKeyId = `provider-runtime-${suffix}`;
  const runtimeSigningSecret = randomBytes(32);
  const expiresAt = new Date(Date.now() + 60 * 60 * 1_000);
  await observer.practice.create({
    data: {
      id: administratorPracticeId,
      name: "Synthetic provider release administration",
      slug: administratorPracticeId,
    },
  });
  const reviewerIds = new Map<string, string>();
  const administrators = [
    {
      id: creatorId,
      email: creatorEmail,
      session: creatorSession,
      discipline: null,
    },
    ...contracts.TEMPLATE_TWIN_RELEASE_DISCIPLINES.map((discipline) => {
      const id = `synthetic-provider-reviewer-${discipline.toLowerCase()}-${suffix}`;
      reviewerIds.set(discipline, id);
      return {
        id,
        email: `${id}@synthetic.test`,
        session: `synthetic-provider-session-${discipline.toLowerCase()}-${suffix}`,
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
        practiceId: administratorPracticeId,
        mfaEnabled: true,
        mfaSecret: "SYNTHETIC-PROVIDER-OWNERSHIP-RELEASE-MFA",
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
          ${`synthetic-provider-pg/${administrator.discipline.toLowerCase()}`}
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
  await observer.$executeRaw(Prisma.sql`
    UPDATE "template_twin_lineage_migration_progress"
    SET "phase" = 'CONTRACTED', "completedAt" = CURRENT_TIMESTAMP,
        "updatedAt" = CURRENT_TIMESTAMP
    WHERE "operationKey" = 'note_templates_lineage_v1'
      AND "phase" <> 'CONTRACTED'
  `);

  const evidence = {
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
  const appInstanceId = `provider-app-${suffix}`;
  const workerInstanceId = `provider-worker-${suffix}`;
  const releaseActor = { userId: creatorId, sessionId: creatorSession };
  const created = await releaseControl.createTemplateTwinReleaseCandidate({
    actor: releaseActor,
    confirmation: "CREATE EXACT RELEASE",
    evidence,
    guardrailPolicy,
    authorizedPracticeIds: [practiceA],
    canaryPracticeIds: [practiceA],
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
        sessionId: `synthetic-provider-session-${discipline.toLowerCase()}-${suffix}`,
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

  function runtimeEnvironment(input: {
    readonly instanceId: string;
    readonly component: "APP" | "WORKER";
    readonly imageDigest: string;
  }) {
    const issuedAtEpochSeconds = Math.floor(Date.now() / 1_000) - 1;
    const expiresAtEpochSeconds = issuedAtEpochSeconds + 3_600;
    const nonce = randomUUID();
    const message = [
      "template-twin-runtime-attestation-v1",
      runtimeKeyId,
      nonce,
      created.releaseIdentitySha256,
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
      releaseIdentitySha256: created.releaseIdentitySha256,
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
  const appRuntime = runtimeEnvironment({
    instanceId: appInstanceId,
    component: "APP",
    imageDigest: evidence.appImageDigest,
  });
  const workerRuntime = runtimeEnvironment({
    instanceId: workerInstanceId,
    component: "WORKER",
    imageDigest: evidence.workerImageDigest,
  });
  for (const runtime of [appRuntime, workerRuntime]) {
    const envelope = runtime.envelope;
    const rows = await executor.$queryRaw<Array<{ receiptId: string | null }>>(
      Prisma.sql`
        SELECT template_twin_register_runtime_attestation(
          ${envelope.version}, ${envelope.keyId}, ${envelope.nonce}::UUID,
          ${envelope.releaseIdentitySha256}::CHAR(64),
          ${envelope.instanceId}, ${envelope.component},
          ${envelope.sourceCommitSha}::CHAR(40), ${envelope.imageDigest},
          ${envelope.issuedAtEpochSeconds}::BIGINT,
          ${envelope.expiresAtEpochSeconds}::BIGINT,
          ${envelope.signature}::CHAR(64)
        ) AS "receiptId"
      `,
    );
    assert(
      rows[0]?.receiptId,
      "synthetic runtime attestation must be admitted",
    );
  }
  const [globalBefore] = await observer.$queryRaw<
    Array<{ generation: bigint }>
  >(Prisma.sql`
    SELECT "generation" FROM "template_twin_rollout_controls"
    WHERE "id" = 'global'
  `);
  assert(globalBefore);
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
      releaseId: string;
      releaseIdentitySha256: string;
      runtimeManifestSha256: string;
      globalGeneration: bigint;
      practiceGeneration: bigint;
      enabled: boolean;
      practiceEnabled: boolean;
      releaseStatus: string;
    }>
  >(Prisma.sql`
    SELECT candidate."id"::TEXT AS "releaseId",
      candidate."releaseIdentitySha256",
      candidate."runtimeManifestSha256",
      global_control."generation" AS "globalGeneration",
      practice."templateTwinRolloutGeneration" AS "practiceGeneration",
      global_control."enabled", practice."templateTwinEnabled" AS "practiceEnabled",
      candidate."status" AS "releaseStatus"
    FROM "template_twin_release_candidates" candidate
    CROSS JOIN "template_twin_rollout_controls" global_control
    JOIN "practices" practice ON practice."id" = ${practiceA}
    WHERE candidate."id" = ${created.releaseId}::UUID
      AND global_control."id" = 'global'
  `);
  assert(current);
  assert.equal(current.enabled, true);
  assert.equal(current.practiceEnabled, true);
  assert.equal(current.releaseStatus, "ROLLING_OUT");
  return {
    authority: {
      releaseId: current.releaseId,
      releaseIdentitySha256: current.releaseIdentitySha256,
      runtimeManifestSha256: current.runtimeManifestSha256,
      runtimeInstanceId: appInstanceId,
      pinnedGlobalRolloutGeneration: current.globalGeneration,
      pinnedPracticeRolloutGeneration: current.practiceGeneration,
    },
    releaseActor,
    releaseActorEmail: creatorEmail,
    releaseActorPracticeId: administratorPracticeId,
  };
}

interface LiveProviderVisitFixture {
  readonly release: LiveReleaseFixture;
  readonly patientId: string;
  readonly visitId: string;
  readonly visitInputMode: "audio_upload";
  readonly sourceArtifactId: string;
  readonly compiledVersionId: string;
  readonly noteTemplateId: string;
  readonly sourceLineageId: string;
  readonly sourceLineageVersion: number;
  readonly sourceSha256: string;
}

async function createLiveProviderVisitFixture(
  release: LiveReleaseFixture,
): Promise<LiveProviderVisitFixture> {
  const scan = executionIdentity({
    marker: "live-plan-source",
    providerMode: "LIVE",
    liveAuthority: release.authority,
  });
  const mapping = executionIdentity({
    marker: "live-plan-source",
    operation: "SOURCE_SEMANTIC_MAPPING",
    providerMode: "LIVE",
    liveAuthority: release.authority,
  });
  await reserve(executor, scan);
  await reserve(executor, mapping);
  const scanSha = await succeed(executor, scan, {
    classification: "synthetic-safe",
  });
  const mappingSha = await succeed(executor, mapping, { mappings: [] });
  const receipt = receiptFor({
    actorUserId: actorA,
    authority: scan,
    executions: [
      { identity: scan, resultSha256: scanSha },
      { identity: mapping, resultSha256: mappingSha },
    ],
  });
  const quarantineId = `quarantine-live-plan-${suffix}`;
  const quarantineKey = `practices/${practiceA}/template-twin/quarantine/${quarantineId}.docx`;
  const sourceKey = `practices/${practiceA}/template-twin/sources/${scan.sourceArtifactId}.docx`;
  const outputKey = `practices/${practiceA}/template-twin/outputs/live-provider-${suffix}.docx`;
  const outputSha256 = hash("synthetic-live-output");
  const sourceSizeBytes = 4096;
  const scannedAt = new Date();
  const malwareCore = {
    profileVersion: "template-twin-clamd-instream-v1",
    scanner: "clamav-clamd",
    transport: "unix-domain-socket",
    engineVersion: "synthetic-clamd-v1",
    signatureVersion: "1",
    sourceSha256: scan.sourceSha256,
    sourceSizeBytes,
    verdict: "clean",
    threatNameSha256: null,
    scannedAt: scannedAt.toISOString(),
  };
  await observer.$transaction(async (tx) => {
    await tx.templateTwinQuarantineArtifact.create({
      data: {
        id: quarantineId,
        practiceId: practiceA,
        createdById: actorA,
        lineageId: scan.sourceLineageId,
        lineageVersion: 1,
        intakeMode: "NATIVE_TEMPLATE",
        objectKey: quarantineKey,
        objectVersionId: "synthetic-live-quarantine-version",
        objectEtag: "synthetic-live-quarantine-etag",
        sha256: scan.sourceSha256,
        mimeType:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        sizeBytes: sourceSizeBytes,
        status: "MALWARE_CLEAN",
        malwareScanEvidence: {
          ...malwareCore,
          attestationSha256: hash(JSON.stringify(malwareCore)),
        },
        scannedAt,
      },
    });
    await tx.templateTwinObjectLedger.create({
      data: {
        id: `ledger-${quarantineId}`,
        practiceId: practiceA,
        objectKey: quarantineKey,
        objectVersionId: "synthetic-live-quarantine-version",
        objectEtag: "synthetic-live-quarantine-etag",
        sha256: scan.sourceSha256,
        sizeBytes: sourceSizeBytes,
        kind: "quarantine",
        state: "CLAIMED",
        claimType: "quarantine_artifact",
        claimId: quarantineId,
      },
    });
    await tx.noteTemplate.create({
      data: {
        id: scan.noteTemplateId,
        doctorId: actorA,
        name: "Synthetic LIVE provider template",
        encounterType: "synthetic",
        sections: [],
        version: 1,
        versionDescription: "Synthetic LIVE database authority proof",
        status: "draft",
        isSystemDefault: false,
        lineageId: scan.sourceLineageId,
        templateKind: "template_twin_docx",
      },
    });
    await tx.templateTwinSourceArtifact.create({
      data: {
        id: scan.sourceArtifactId,
        practiceId: practiceA,
        createdById: actorA,
        lineageId: scan.sourceLineageId,
        lineageVersion: 1,
        objectKey: sourceKey,
        objectVersionId: "synthetic-live-source-version",
        objectEtag: "synthetic-live-source-etag",
        sha256: scan.sourceSha256,
        mimeType:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        sizeBytes: sourceSizeBytes,
        validationStatus: "accepted",
        rejectionCodes: [],
        privacyScanEvidence: {
          profileVersion: "template-twin-source-phi-safe-alpha-v1",
          approvedStaticAssetPolicySha256: hash(
            "synthetic-live-approved-static-asset-policy",
          ),
          approvedStaticAssetUsageSha256: hash(
            "synthetic-live-approved-static-asset-usage",
          ),
        },
        providerOwnershipEvidence: receipt as Prisma.InputJsonValue,
        providerOwnershipSha256: canonicalSha256(receipt),
        quarantineArtifactId: quarantineId,
      },
    });
    await tx.templateTwinObjectLedger.create({
      data: {
        id: `ledger-${scan.sourceArtifactId}`,
        practiceId: practiceA,
        objectKey: sourceKey,
        objectVersionId: "synthetic-live-source-version",
        objectEtag: "synthetic-live-source-etag",
        sha256: scan.sourceSha256,
        sizeBytes: sourceSizeBytes,
        kind: "source",
        state: "CLAIMED",
        claimType: "source_artifact",
        claimId: scan.sourceArtifactId,
      },
    });
    await tx.templateTwinQuarantineArtifact.update({
      where: { id: quarantineId },
      data: {
        status: "ADMITTED",
        metadataMinimizationEvidence: {
          profileVersion: "template-twin-docx-metadata-minimization-v1",
          originalSha256: scan.sourceSha256,
          minimizedSha256: scan.sourceSha256,
          zipEntryTimestampsNormalized: true,
          replacedParts: [],
        },
        admittedAt: new Date(),
      },
    });
    await tx.templateTwinCompiledVersion.create({
      data: {
        id: scan.compiledVersionId,
        sourceArtifactId: scan.sourceArtifactId,
        noteTemplateId: scan.noteTemplateId,
        compilerVersion: "synthetic-live-compiler-v1",
        irSchemaVersion: 1,
        compiledDocumentIr: {},
        unsupportedElements: [],
        structureSha256: hash("synthetic-live-structure"),
        staticContentSha256: hash("synthetic-live-static"),
        certificationStatus: "NEEDS_CONFIRMATION",
        blockingUnsupportedCount: 0,
        latestSyntheticTestManifest: {},
        latestTestMappingsSha256: hash("synthetic-live-mappings"),
        latestTestOutputObjectKey: outputKey,
        latestTestOutputVersionId: "synthetic-live-output-version",
        latestTestOutputEtag: "synthetic-live-output-etag",
        latestTestOutputSha256: outputSha256,
        latestTestStaticContentSha256: hash("synthetic-live-static"),
        latestTestRoundTrip: {},
        latestTestVerifiedAt: new Date(),
        providerOwnershipEvidence: receipt as Prisma.InputJsonValue,
        providerOwnershipSha256: canonicalSha256(receipt),
      },
    });
    await tx.templateTwinObjectLedger.create({
      data: {
        id: `ledger-live-provider-output-${suffix}`,
        practiceId: practiceA,
        objectKey: outputKey,
        objectVersionId: "synthetic-live-output-version",
        objectEtag: "synthetic-live-output-etag",
        sha256: outputSha256,
        sizeBytes: sourceSizeBytes,
        kind: "output",
        state: "CLAIMED",
        claimType: "compiled_test_output",
        claimId: scan.compiledVersionId,
      },
    });
    await tx.templateTwinCompiledVersion.update({
      where: { id: scan.compiledVersionId },
      data: { certificationStatus: "CERTIFIED" },
    });
  });
  await observer.templateTwinCertification.create({
    data: {
      id: `certification-live-provider-${suffix}`,
      compiledVersionId: scan.compiledVersionId,
      certifiedById: actorA,
      providerAuthorizationMode: "LIVE",
      providerAuthorizationAdmissionId: null,
      compiledStructureSha256: hash("synthetic-live-structure"),
      approvedMappingsSha256: hash("synthetic-live-mappings"),
      syntheticTestManifest: {},
      testOutputObjectKey: outputKey,
      testOutputVersionId: "synthetic-live-output-version",
      testOutputEtag: "synthetic-live-output-etag",
      testOutputSha256: outputSha256,
    },
  });
  const patientId = `synthetic-provider-live-patient-${suffix}`;
  const visitId = `synthetic-provider-live-visit-${suffix}`;
  await observer.transcribeMdPatient.create({
    data: {
      id: patientId,
      name: "Synthetic LIVE Provider",
      practiceId: practiceA,
    },
  });
  await observer.transcribeVisit.create({
    data: {
      id: visitId,
      userId: actorA,
      patientId,
      specialty: "synthetic",
      inputMode: "audio_upload",
      status: "QUEUED",
      noteTemplateId: scan.noteTemplateId,
      noteTemplateVersion: 1,
    },
  });
  return {
    release,
    patientId,
    visitId,
    visitInputMode: "audio_upload",
    sourceArtifactId: scan.sourceArtifactId,
    compiledVersionId: scan.compiledVersionId,
    noteTemplateId: scan.noteTemplateId,
    sourceLineageId: scan.sourceLineageId,
    sourceLineageVersion: 1,
    sourceSha256: scan.sourceSha256,
  };
}

function liveCurrentAuthorityContext(
  fixture: LiveProviderVisitFixture,
  overrides: Partial<
    Pick<
      TemplateTwinProviderOwnershipContext,
      | "visitId"
      | "visitInputMode"
      | "sourceArtifactId"
      | "compiledVersionId"
      | "noteTemplateId"
      | "noteTemplateVersion"
      | "sourceLineageId"
      | "sourceLineageVersion"
      | "sourceSha256"
    >
  > = {},
): TemplateTwinProviderOwnershipContext {
  const identity = {
    visitId: overrides.visitId ?? fixture.visitId,
    visitInputMode: overrides.visitInputMode ?? fixture.visitInputMode,
    sourceArtifactId: overrides.sourceArtifactId ?? fixture.sourceArtifactId,
    compiledVersionId: overrides.compiledVersionId ?? fixture.compiledVersionId,
    noteTemplateId: overrides.noteTemplateId ?? fixture.noteTemplateId,
    noteTemplateVersion: overrides.noteTemplateVersion ?? 1,
    sourceLineageId: overrides.sourceLineageId ?? fixture.sourceLineageId,
    sourceLineageVersion:
      overrides.sourceLineageVersion ?? fixture.sourceLineageVersion,
    sourceSha256: overrides.sourceSha256 ?? fixture.sourceSha256,
  };
  const context: TemplateTwinProviderOwnershipContext = {
    practiceId: practiceA,
    actorUserId: actorA,
    visitId: identity.visitId,
    visitInputMode: identity.visitInputMode,
    scope: "VISIT_PIPELINE",
    logicalAttempt: 1,
    subjectId: identity.visitId!,
    subjectSha256: templateTwinVisitProviderSubjectSha256({
      practiceId: practiceA,
      actorUserId: actorA,
      visitId: identity.visitId!,
      noteTemplateId: identity.noteTemplateId!,
      noteTemplateVersion: identity.noteTemplateVersion!,
      compiledVersionId: identity.compiledVersionId!,
      sourceArtifactId: identity.sourceArtifactId!,
      sourceLineageId: identity.sourceLineageId!,
      sourceLineageVersion: identity.sourceLineageVersion!,
      sourceSha256: identity.sourceSha256!,
      logicalAttempt: 1,
      visitInputMode: identity.visitInputMode!,
    }),
    ...identity,
    syntheticAdmissionId: null,
    rolloutToken: {
      practiceId: practiceA,
      globalGeneration: fixture.release.authority.pinnedGlobalRolloutGeneration,
      practiceGeneration:
        fixture.release.authority.pinnedPracticeRolloutGeneration,
      releaseId: fixture.release.authority.releaseId,
      releaseIdentitySha256: fixture.release.authority.releaseIdentitySha256,
      runtimeManifestSha256: fixture.release.authority.runtimeManifestSha256,
      runtimeInstanceId: fixture.release.authority.runtimeInstanceId,
    },
  };
  return context;
}

async function currentProviderAuthority(input: {
  readonly tx: Prisma.TransactionClient;
  readonly context: TemplateTwinProviderOwnershipContext;
  readonly mode: "LIVE" | "SYNTHETIC_QA";
}): Promise<boolean> {
  const { isTemplateTwinProviderAuthorityCurrent } =
    await import("../../../apps/transcribe-md/src/lib/template-twin/provider-ownership");
  return isTemplateTwinProviderAuthorityCurrent({
    tx: input.tx as unknown as ProviderOwnershipDbClient,
    context: input.context,
    mode: input.mode,
  });
}

async function expectLiveAuthorityDriftDenied(input: {
  readonly context: TemplateTwinProviderOwnershipContext;
  readonly mutate: (tx: Prisma.TransactionClient) => Promise<unknown>;
}): Promise<void> {
  const expectedRollback = new Error("expected-live-authority-probe-rollback");
  try {
    await observer.$transaction(async (tx) => {
      // Simulate durable corruption/drift without committing it. The proof is
      // intentionally owner-only, transaction-local, and always rolled back.
      await tx.$executeRawUnsafe(
        "SET LOCAL session_replication_role = replica",
      );
      await input.mutate(tx);
      assert.equal(
        await currentProviderAuthority({
          tx,
          context: input.context,
          mode: "LIVE",
        }),
        false,
      );
      throw expectedRollback;
    });
  } catch (error) {
    if (error !== expectedRollback) throw error;
  }
}

async function proveLiveCurrentProviderAuthority(
  fixture: LiveProviderVisitFixture,
): Promise<void> {
  const context = liveCurrentAuthorityContext(fixture);
  assert.equal(
    await observer.$transaction((tx) =>
      currentProviderAuthority({ tx, context, mode: "LIVE" }),
    ),
    true,
  );

  assert.equal(
    await observer.$transaction((tx) =>
      currentProviderAuthority({
        tx,
        context: liveCurrentAuthorityContext(fixture, {
          sourceArtifactId: `wrong-source-${suffix}`,
        }),
        mode: "LIVE",
      }),
    ),
    false,
  );
  assert.equal(
    await observer.$transaction((tx) =>
      currentProviderAuthority({
        tx,
        context: liveCurrentAuthorityContext(fixture, {
          noteTemplateId: `wrong-template-${suffix}`,
        }),
        mode: "LIVE",
      }),
    ),
    false,
  );

  await expectLiveAuthorityDriftDenied({
    context,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "transcribe_md_patients"
        SET "practiceId" = ${practiceB}
        WHERE "id" = ${fixture.patientId}
      `),
  });
  await expectLiveAuthorityDriftDenied({
    context,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "transcribe_md_patients"
        SET "deletedAt" = clock_timestamp()
        WHERE "id" = ${fixture.patientId}
      `),
  });
  await expectLiveAuthorityDriftDenied({
    context,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "transcribe_md_patients"
        SET "externalId" = 'SYNTHETIC-QA-ONLY'
        WHERE "id" = ${fixture.patientId}
      `),
  });
  await expectLiveAuthorityDriftDenied({
    context,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "note_templates"
        SET "doctorId" = ${actorA2}
        WHERE "id" = ${fixture.noteTemplateId}
      `),
  });
  await expectLiveAuthorityDriftDenied({
    context,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "note_templates"
        SET "templateKind" = 'structured'
        WHERE "id" = ${fixture.noteTemplateId}
      `),
  });
  await expectLiveAuthorityDriftDenied({
    context,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_compiled_versions"
        SET "certificationStatus" = 'NEEDS_CONFIRMATION'
        WHERE "id" = ${fixture.compiledVersionId}
      `),
  });
  await expectLiveAuthorityDriftDenied({
    context,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_source_artifacts"
        SET "practiceId" = ${practiceB}
        WHERE "id" = ${fixture.sourceArtifactId}
      `),
  });
  await expectLiveAuthorityDriftDenied({
    context,
    mutate: (tx) =>
      tx.$executeRaw(Prisma.sql`
        UPDATE "template_twin_certifications"
        SET "certifiedById" = ${actorA2}
        WHERE "compiledVersionId" = ${fixture.compiledVersionId}
      `),
  });
}

async function insertLivePlanDecision(input: {
  readonly fixture: LiveProviderVisitFixture;
  readonly operation:
    | "L1B_TRANSCRIBE"
    | "L4_ANCHOR_VERIFY"
    | "L6_POLISH"
    | "L6_FIDELITY_VERIFY";
  readonly operationInstance: string;
  readonly reasonCode: string;
  readonly pinnedGlobalRolloutGeneration?: bigint;
  readonly pinnedPracticeRolloutGeneration?: bigint;
}): Promise<string> {
  const globalGeneration =
    input.pinnedGlobalRolloutGeneration ??
    input.fixture.release.authority.pinnedGlobalRolloutGeneration;
  const practiceGeneration =
    input.pinnedPracticeRolloutGeneration ??
    input.fixture.release.authority.pinnedPracticeRolloutGeneration;
  const authority = input.fixture.release.authority;
  const subjectSha256 = canonicalSha256({
    contractVersion: "template-twin-visit-provider-subject-v1",
    practiceId: practiceA,
    actorUserId: actorA,
    visitId: input.fixture.visitId,
    noteTemplateId: input.fixture.noteTemplateId,
    noteTemplateVersion: 1,
    compiledVersionId: input.fixture.compiledVersionId,
    sourceArtifactId: input.fixture.sourceArtifactId,
    sourceLineageId: input.fixture.sourceLineageId,
    sourceLineageVersion: input.fixture.sourceLineageVersion,
    sourceSha256: input.fixture.sourceSha256,
    logicalAttempt: 1,
    inputMode: input.fixture.visitInputMode,
  });
  const runtimeIdentitySha256 = joinedHash([
    "template-twin-provider-runtime-v1",
    "LIVE",
    globalGeneration.toString(),
    practiceGeneration.toString(),
    authority.releaseId,
    authority.releaseIdentitySha256,
    authority.runtimeManifestSha256,
    authority.runtimeInstanceId,
  ]);
  const ownershipKey = joinedHash([
    "template-twin-provider-plan-decision-v1",
    practiceA,
    actorA,
    input.fixture.visitId,
    input.fixture.visitInputMode,
    "VISIT_PIPELINE",
    "1",
    input.fixture.visitId,
    subjectSha256,
    input.fixture.sourceArtifactId,
    input.fixture.compiledVersionId,
    input.fixture.noteTemplateId,
    "1",
    input.fixture.sourceLineageId,
    String(input.fixture.sourceLineageVersion),
    input.fixture.sourceSha256,
    "LIVE",
    input.operation,
    input.operationInstance,
    globalGeneration.toString(),
    practiceGeneration.toString(),
    authority.releaseId,
    authority.releaseIdentitySha256,
    authority.runtimeManifestSha256,
    authority.runtimeInstanceId,
    runtimeIdentitySha256,
    "-",
  ]);
  const id = `plan-${input.operation.toLowerCase()}-${input.operationInstance}-${randomUUID()}`;
  await executor.$executeRaw(Prisma.sql`
    INSERT INTO "template_twin_provider_plan_decisions" (
      "id", "practiceId", "actorUserId", "visitId", "visitInputMode",
      "scope", "operation", "operationInstance", "logicalAttempt",
      "subjectId", "subjectSha256", "sourceArtifactId",
      "compiledVersionId", "noteTemplateId", "noteTemplateVersion",
      "sourceLineageId", "sourceLineageVersion", "sourceSha256",
      "providerMode", "pinnedGlobalRolloutGeneration",
      "pinnedPracticeRolloutGeneration", "releaseId",
      "releaseIdentitySha256", "runtimeManifestSha256", "runtimeInstanceId",
      "runtimeIdentitySha256", "syntheticAdmissionId", "reasonCode",
      "ownershipKey"
    ) VALUES (
      ${id}, ${practiceA}, ${actorA}, ${input.fixture.visitId},
      ${input.fixture.visitInputMode}, 'VISIT_PIPELINE', ${input.operation},
      ${input.operationInstance}, 1, ${input.fixture.visitId},
      ${subjectSha256}, ${input.fixture.sourceArtifactId},
      ${input.fixture.compiledVersionId}, ${input.fixture.noteTemplateId}, 1,
      ${input.fixture.sourceLineageId}, ${input.fixture.sourceLineageVersion},
      ${input.fixture.sourceSha256}, 'LIVE', ${globalGeneration},
      ${practiceGeneration}, ${authority.releaseId}::UUID,
      ${authority.releaseIdentitySha256}, ${authority.runtimeManifestSha256},
      ${authority.runtimeInstanceId}, ${runtimeIdentitySha256}, NULL,
      ${input.reasonCode}, ${ownershipKey}
    )
  `);
  return id;
}

async function proveLivePlanDecisionAuthority(): Promise<void> {
  const release = await createLiveReleaseFixture();
  const fixture = await createLiveProviderVisitFixture(release);
  await proveLiveCurrentProviderAuthority(fixture);
  const positiveId = await insertLivePlanDecision({
    fixture,
    operation: "L1B_TRANSCRIBE",
    operationInstance: "primary",
    reasonCode: "INPUT_MODE_CONVERSATION",
  });
  const [positive] = await observer.$queryRaw<Array<{ count: bigint }>>(
    Prisma.sql`
      SELECT COUNT(*)::BIGINT AS "count"
      FROM "template_twin_provider_plan_decisions"
      WHERE "id" = ${positiveId}
    `,
  );
  assert.equal(positive?.count, BigInt(1));
  await expectReject(
    () =>
      observer.$executeRaw(Prisma.sql`
        UPDATE "template_twin_provider_plan_decisions"
        SET "reasonCode" = "reasonCode"
        WHERE "id" = ${positiveId}
      `),
    /TEMPLATE_TWIN_PROVIDER_PLAN_DECISION_IMMUTABLE/u,
  );
  await expectReject(
    () =>
      observer.$executeRaw(Prisma.sql`
        UPDATE "template_twin_provider_plan_decisions"
        SET "reasonCode" = 'INPUT_MODE_TEXT'
        WHERE "id" = ${positiveId}
      `),
    /TEMPLATE_TWIN_PROVIDER_PLAN_DECISION_IMMUTABLE/u,
  );
  await expectReject(
    () =>
      observer.$executeRaw(Prisma.sql`
        DELETE FROM "template_twin_provider_plan_decisions"
        WHERE "id" = ${positiveId}
      `),
    /TEMPLATE_TWIN_PROVIDER_PLAN_DECISION_IMMUTABLE/u,
  );
  await expectReject(
    () =>
      insertLivePlanDecision({
        fixture,
        operation: "L4_ANCHOR_VERIFY",
        operationInstance: "ensemble-pass-1",
        reasonCode: "EVIDENCE_ANCHORS_DISABLED",
        pinnedGlobalRolloutGeneration:
          release.authority.pinnedGlobalRolloutGeneration + BigInt(1),
      }),
    /TEMPLATE_TWIN_PROVIDER_PLAN_RUNTIME_NOT_AUTHORIZED/u,
  );
  await expectReject(
    () =>
      insertLivePlanDecision({
        fixture,
        operation: "L4_ANCHOR_VERIFY",
        operationInstance: "ensemble-pass-2",
        reasonCode: "EVIDENCE_ANCHORS_DISABLED",
        pinnedPracticeRolloutGeneration:
          release.authority.pinnedPracticeRolloutGeneration + BigInt(1),
      }),
    /TEMPLATE_TWIN_PROVIDER_PLAN_RUNTIME_NOT_AUTHORIZED/u,
  );

  const postProviderExecutionId = await reserveLiveVisitPipelineExecution({
    db: executor,
    marker: "live-authority-revoked-after-provider",
    authority: release.authority,
    actorUserId: actorA,
    visitId: fixture.visitId,
    visitInputMode: fixture.visitInputMode,
    sourceArtifactId: fixture.sourceArtifactId,
    compiledVersionId: fixture.compiledVersionId,
    noteTemplateId: fixture.noteTemplateId,
    sourceLineageId: fixture.sourceLineageId,
    sourceLineageVersion: fixture.sourceLineageVersion,
    sourceSha256: fixture.sourceSha256,
  });
  const postProviderClaimId = randomBytes(32).toString("hex");
  assert.equal(
    await claim(executor, postProviderExecutionId, postProviderClaimId),
    1,
  );

  const rollout =
    await import("../../../apps/transcribe-md/src/lib/template-twin/rollout");
  const disabledGeneration = await rollout.setTemplateTwinGlobalRollout({
    enabled: false,
    actor: {
      userId: release.releaseActor.userId,
      userEmail: release.releaseActorEmail,
      practiceId: release.releaseActorPracticeId,
    },
  });
  await expectReject(
    () =>
      insertLivePlanDecision({
        fixture,
        operation: "L6_POLISH",
        operationInstance: "primary",
        reasonCode: "NO_FIXABLE_CRITIQUE_WORK",
        pinnedGlobalRolloutGeneration: disabledGeneration,
      }),
    /TEMPLATE_TWIN_PROVIDER_PLAN_RUNTIME_NOT_AUTHORIZED/u,
  );

  const escapedResultPayload = {
    contractVersion: "template-twin-provider-result-v1",
    output: { synthetic: true },
  };
  await expectReject(
    () =>
      executor.$executeRaw(Prisma.sql`
        UPDATE "template_twin_provider_executions"
        SET "status" = 'SUCCEEDED'::"VisitAutomationProviderExecutionStatus",
            "resultPayload" = ${JSON.stringify(escapedResultPayload)}::JSONB,
            "resultSha256" = ${canonicalSha256(escapedResultPayload)},
            "resultVersion" = 'template-twin-provider-result-v1',
            "completedAt" = clock_timestamp(), "updatedAt" = clock_timestamp()
        WHERE "id" = ${postProviderExecutionId}
          AND "claimId" = ${postProviderClaimId}
      `),
    /TEMPLATE_TWIN_PROVIDER_RUNTIME_NOT_AUTHORIZED/u,
  );
  const beforeTerminalization =
    await observer.templateTwinProviderExecution.findUniqueOrThrow({
      where: { id: postProviderExecutionId },
      select: {
        status: true,
        resultPayload: true,
        resultSha256: true,
        resultVersion: true,
      },
    });
  assert.deepEqual(beforeTerminalization, {
    status: "IN_FLIGHT",
    resultPayload: null,
    resultSha256: null,
    resultVersion: null,
  });
  assert.equal(
    await executor.$executeRaw(Prisma.sql`
      UPDATE "template_twin_provider_executions"
      SET "status" = 'UNKNOWN_OUTCOME'::"VisitAutomationProviderExecutionStatus",
          "failureCode" = 'AUTHORITY_REVOKED_AFTER_PROVIDER',
          "completedAt" = clock_timestamp(), "updatedAt" = clock_timestamp()
      WHERE "id" = ${postProviderExecutionId}
        AND "status" = 'IN_FLIGHT'::"VisitAutomationProviderExecutionStatus"
        AND "claimId" = ${postProviderClaimId}
    `),
    1,
  );
  const terminalized =
    await observer.templateTwinProviderExecution.findUniqueOrThrow({
      where: { id: postProviderExecutionId },
      select: {
        status: true,
        invocationCount: true,
        failureCode: true,
        resultPayload: true,
        resultSha256: true,
        resultVersion: true,
      },
    });
  assert.deepEqual(terminalized, {
    status: "UNKNOWN_OUTCOME",
    invocationCount: 1,
    failureCode: "AUTHORITY_REVOKED_AFTER_PROVIDER",
    resultPayload: null,
    resultSha256: null,
    resultVersion: null,
  });
  assert.equal(
    await claim(
      executor,
      postProviderExecutionId,
      randomBytes(32).toString("hex"),
    ),
    0,
  );

  const [beforeRevoke] = await observer.$queryRaw<
    Array<{ releaseGeneration: bigint; globalGeneration: bigint }>
  >(Prisma.sql`
    SELECT candidate."generation" AS "releaseGeneration",
      control."generation" AS "globalGeneration"
    FROM "template_twin_release_candidates" candidate
    CROSS JOIN "template_twin_rollout_controls" control
    WHERE candidate."id" = ${release.authority.releaseId}::UUID
      AND control."id" = 'global'
  `);
  assert(beforeRevoke);
  const releaseControl =
    await import("../../../apps/transcribe-md/src/lib/template-twin/release-control");
  await releaseControl.revokeTemplateTwinRelease({
    actor: release.releaseActor,
    releaseId: release.authority.releaseId,
    expectedReleaseGeneration: beforeRevoke.releaseGeneration.toString(),
    expectedGlobalGeneration: beforeRevoke.globalGeneration.toString(),
    reasonCode: "SYNTHETIC_PROVIDER_AUTHORITY_PROOF_COMPLETE",
    confirmation: `REVOKE ${release.authority.releaseIdentitySha256.slice(0, 12)}`,
  });
  const [revoked] = await observer.$queryRaw<
    Array<{ status: string; globalGeneration: bigint; enabled: boolean }>
  >(Prisma.sql`
    SELECT candidate."status", control."generation" AS "globalGeneration",
      control."enabled"
    FROM "template_twin_release_candidates" candidate
    CROSS JOIN "template_twin_rollout_controls" control
    WHERE candidate."id" = ${release.authority.releaseId}::UUID
      AND control."id" = 'global'
  `);
  assert(revoked);
  assert.equal(revoked.status, "REVOKED");
  assert.equal(revoked.enabled, false);
  await expectReject(
    () =>
      insertLivePlanDecision({
        fixture,
        operation: "L6_FIDELITY_VERIFY",
        operationInstance: "primary",
        reasonCode: "POLISH_NOT_EXECUTED",
        pinnedGlobalRolloutGeneration: revoked.globalGeneration,
      }),
    /TEMPLATE_TWIN_PROVIDER_PLAN_RUNTIME_NOT_AUTHORIZED/u,
  );
}

async function revokeInterruptedSyntheticReleaseFixture(): Promise<void> {
  process.env.DATABASE_URL = databaseUrl;
  process.env.TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL = databaseUrl;
  process.env.TEMPLATE_TWIN_KILL_SWITCH = "false";
  process.env.TEMPLATE_TWIN_RUNTIME_MODE = "standard";
  const candidates = await observer.$queryRaw<
    Array<{
      id: string;
      releaseIdentitySha256: string;
      generation: bigint;
      createdById: string;
    }>
  >(Prisma.sql`
    SELECT "id"::TEXT, "releaseIdentitySha256", "generation", "createdById"
    FROM "template_twin_release_candidates"
    WHERE "status" = 'ROLLING_OUT'
      AND "createdById" LIKE 'synthetic-provider-release-creator-%'
    ORDER BY "createdAt"
  `);
  if (candidates.length === 0) return;
  assert.equal(
    candidates.length,
    1,
    "only one interrupted synthetic provider release may own global rollout",
  );
  const candidate = candidates[0]!;
  const session = await observer.userSession.findFirst({
    where: {
      userId: candidate.createdById,
      expiresAt: { gt: new Date() },
    },
    select: { sessionToken: true },
    orderBy: { createdAt: "desc" },
  });
  assert(session, "interrupted synthetic release actor session is required");
  const [global] = await observer.$queryRaw<Array<{ generation: bigint }>>(
    Prisma.sql`
      SELECT "generation"
      FROM "template_twin_rollout_controls"
      WHERE "id" = 'global'
    `,
  );
  assert(global);
  const releaseControl =
    await import("../../../apps/transcribe-md/src/lib/template-twin/release-control");
  await releaseControl.revokeTemplateTwinRelease({
    actor: {
      userId: candidate.createdById,
      sessionId: session.sessionToken,
    },
    releaseId: candidate.id,
    expectedReleaseGeneration: candidate.generation.toString(),
    expectedGlobalGeneration: global.generation.toString(),
    reasonCode: "SYNTHETIC_PROVIDER_PROOF_INTERRUPTED",
    confirmation: `REVOKE ${candidate.releaseIdentitySha256.slice(0, 12)}`,
  });
}

async function main(): Promise<void> {
  await revokeInterruptedSyntheticReleaseFixture();
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
      {
        id: actorA2,
        email: `${actorA2}@synthetic.test`,
        passwordHash: "not-a-real-credential",
        role: "DOCTOR",
        practiceId: practiceA,
        products: ["TRANSCRIBE_MD"],
      },
      {
        id: adminA,
        email: `${adminA}@synthetic.test`,
        passwordHash: "not-a-real-credential",
        role: "ADMIN",
        practiceId: practiceA,
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
  await expectReject(
    () =>
      executor.$executeRaw(Prisma.sql`
        UPDATE "template_twin_provider_executions"
        SET "status" = "status"
        WHERE "id" = ${ambiguous.id}
      `),
    /TEMPLATE_TWIN_PROVIDER_EXECUTION_TERMINAL_IMMUTABLE/u,
  );
  assert.equal(
    await claim(contenderA, ambiguous.id, randomBytes(32).toString("hex")),
    0,
  );
  await expectReject(
    () =>
      executor.$executeRaw(Prisma.sql`
        UPDATE "template_twin_provider_executions"
        SET "failureCode" = 'MUTATED', "updatedAt" = clock_timestamp()
        WHERE "id" = ${ambiguous.id}
      `),
    /TEMPLATE_TWIN_PROVIDER_EXECUTION_TERMINAL_IMMUTABLE/u,
  );

  const changedModel = executionIdentity({
    marker: "ambiguous",
    model: "synthetic-model-v2",
  });
  await expectReject(
    () => reserve(executor, changedModel),
    /template_twin_provider_execution_ownership_key/u,
  );
  const changedRuntime = executionIdentity({
    marker: "ambiguous",
    globalGeneration: 2n,
  });
  await expectReject(
    () => reserve(executor, changedRuntime),
    /template_twin_provider_execution_ownership_key/u,
  );
  const changedInput = executionIdentity({
    marker: "ambiguous",
    inputMarker: "drifted-input",
  });
  await expectReject(
    () => reserve(executor, changedInput),
    /template_twin_provider_execution_ownership_key/u,
  );
  const changedVersion = executionIdentity({
    marker: "ambiguous",
    operationVersion: "b017-pg-contract-v2",
  });
  await expectReject(
    () => reserve(executor, changedVersion),
    /template_twin_provider_execution_ownership_key/u,
  );
  const distinctInstance = executionIdentity({
    marker: "ambiguous",
    operationInstance: "ensemble-pass-2",
  });
  await reserve(executor, distinctInstance);
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

  const deterministicReceipt = receiptFor({
    actorUserId: actorA,
    authority: succeeded,
    executions: [{ identity: succeeded, resultSha256 }],
  });
  assert.equal(
    await receiptIsValid({
      ...receiptExpectation(succeeded),
      receipt: deterministicReceipt,
    }),
    false,
  );

  const admissionA = await createSyntheticAdmission(actorA);
  const admissionA2 = await createSyntheticAdmission(actorA2);
  const syntheticScan = executionIdentity({
    marker: "synthetic-receipt",
    providerMode: "SYNTHETIC_QA",
    syntheticAdmissionId: admissionA,
  });
  const syntheticMapping = executionIdentity({
    marker: "synthetic-receipt",
    operation: "SOURCE_SEMANTIC_MAPPING",
    actorUserId: actorA2,
    providerMode: "SYNTHETIC_QA",
    syntheticAdmissionId: admissionA2,
  });
  await reserve(executor, syntheticScan);
  await reserve(executor, syntheticMapping);
  const syntheticScanSha = await succeed(executor, syntheticScan, {
    classification: "synthetic-safe",
  });
  const syntheticMappingSha = await succeed(executor, syntheticMapping, {
    mappings: [],
  });
  const syntheticReceipt = receiptFor({
    actorUserId: actorA,
    authority: syntheticScan,
    executions: [{ identity: syntheticScan, resultSha256: syntheticScanSha }],
  });
  assert.equal(
    await receiptIsValid({
      ...receiptExpectation(syntheticScan),
      receipt: syntheticReceipt,
    }),
    true,
  );
  const crossPhysicianReceipt = receiptFor({
    actorUserId: actorA2,
    authority: syntheticScan,
    executions: [{ identity: syntheticScan, resultSha256: syntheticScanSha }],
  });
  assert.equal(
    await receiptIsValid({
      ...receiptExpectation(syntheticScan),
      expectedActorId: actorA2,
      receipt: crossPhysicianReceipt,
    }),
    false,
  );
  const mixedPhysicianReceipt = receiptFor({
    actorUserId: actorA,
    authority: syntheticScan,
    executions: [
      { identity: syntheticScan, resultSha256: syntheticScanSha },
      { identity: syntheticMapping, resultSha256: syntheticMappingSha },
    ],
  });
  assert.equal(
    await receiptIsValid({
      ...receiptExpectation(syntheticScan),
      receipt: mixedPhysicianReceipt,
    }),
    false,
  );

  const syntheticUnknown = executionIdentity({
    marker: "synthetic-unknown",
    providerMode: "SYNTHETIC_QA",
    syntheticAdmissionId: admissionA,
  });
  await reserve(executor, syntheticUnknown);
  const syntheticUnknownClaim = randomBytes(32).toString("hex");
  assert.equal(
    await claim(executor, syntheticUnknown.id, syntheticUnknownClaim),
    1,
  );
  await executor.$executeRaw(Prisma.sql`
    UPDATE "template_twin_provider_executions"
    SET "status" = 'UNKNOWN_OUTCOME'::"VisitAutomationProviderExecutionStatus",
        "failureCode" = 'PROVIDER_OUTCOME_AMBIGUOUS',
        "completedAt" = clock_timestamp(), "updatedAt" = clock_timestamp()
    WHERE "id" = ${syntheticUnknown.id}
      AND "claimId" = ${syntheticUnknownClaim}
  `);
  const syntheticUnknownReceipt = receiptFor({
    actorUserId: actorA,
    authority: syntheticUnknown,
    executions: [
      { identity: syntheticUnknown, resultSha256: hash("non-result") },
    ],
  });
  assert.equal(
    await receiptIsValid({
      ...receiptExpectation(syntheticUnknown),
      receipt: syntheticUnknownReceipt,
    }),
    false,
  );
  await expectProductionArtifactModeRejected({
    marker: "deterministic",
    receipt: deterministicReceipt,
  });
  await expectProductionArtifactModeRejected({
    marker: "synthetic",
    receipt: syntheticReceipt,
  });
  const stagingLineage = await proveSyntheticStagingUploadAndPromotionFence();
  await provePreCertificationVoiceAuthority(stagingLineage);
  await proveCrossPhysicianTemplateExecutionRejected(stagingLineage);
  await proveSyntheticCurrentProviderAuthority(stagingLineage);
  await proveRevokedAuthorityTerminalization();
  await proveLivePlanDecisionAuthority();

  const [visitForeignKey] = await observer.$queryRaw<
    Array<{ validated: boolean; target: string }>
  >(Prisma.sql`
    SELECT constraint_row.convalidated AS validated,
      constraint_row.confrelid::regclass::TEXT AS target
    FROM pg_constraint constraint_row
    WHERE constraint_row.conname = 'template_twin_provider_execution_visit_fkey'
  `);
  assert.deepEqual(visitForeignKey, {
    validated: true,
    target: "transcribe_visits",
  });

  const routines = await observer.$queryRaw<
    Array<{
      proname: string;
      proconfig: string[] | null;
      prosecdef: boolean;
      publicExecute: boolean;
    }>
  >(Prisma.sql`
    SELECT procedure.proname, procedure.proconfig, procedure.prosecdef,
      EXISTS (
        SELECT 1
        FROM aclexplode(COALESCE(
          procedure.proacl,
          acldefault('f', procedure.proowner)
        )) privilege
        WHERE privilege.grantee = 0
          AND privilege.privilege_type = 'EXECUTE'
      ) AS "publicExecute"
    FROM pg_proc procedure
    JOIN pg_namespace namespace ON namespace.oid = procedure.pronamespace
    WHERE namespace.nspname = 'public'
      AND procedure.proname IN (
        'template_twin_assert_synthetic_qa_admission_lineage',
        'template_twin_guard_synthetic_qa_admission_transition',
        'template_twin_guard_pre_cert_voice_admission_removal',
        'template_twin_guard_pre_cert_voice_visit',
        'template_twin_guard_synthetic_qa_patient',
        'template_twin_guard_synthetic_qa_patient_truncate',
        'template_twin_provider_execution_guard_identity',
        'template_twin_provider_execution_guard_transition',
        'template_twin_provider_execution_guard_live_claim',
        'template_twin_provider_execution_guard_remove',
        'template_twin_provider_plan_decision_guard',
        'template_twin_provider_receipt_is_valid',
        'template_twin_provider_receipt_has_operation',
        'template_twin_provider_receipt_plan_has',
        'template_twin_provider_receipt_plan_is_exact',
        'template_twin_guard_provider_owned_artifact',
        'template_twin_staging_provider_compilation_is_valid',
        'template_twin_live_provider_compilation_is_valid',
        'template_twin_require_live_provider_certification',
        'template_twin_require_live_provider_activation'
      )
    ORDER BY procedure.proname
  `);
  assert.equal(routines.length, 20);
  for (const routine of routines) {
    assert.deepEqual(routine.proconfig, [
      "search_path=pg_catalog, public, pg_temp",
    ]);
    assert.equal(routine.publicExecute, false);
  }
  assert.deepEqual(
    routines
      .filter((routine) => routine.prosecdef)
      .map((routine) => routine.proname)
      .sort(),
    [
      "template_twin_live_provider_compilation_is_valid",
      "template_twin_provider_execution_guard_identity",
      "template_twin_provider_execution_guard_live_claim",
      "template_twin_provider_execution_guard_remove",
      "template_twin_provider_execution_guard_transition",
      "template_twin_provider_plan_decision_guard",
      "template_twin_provider_receipt_is_valid",
      "template_twin_staging_provider_compilation_is_valid",
    ],
  );

  await proveCustomExampleFailurePersistence();
  await expectReject(
    () =>
      executor.$executeRaw(Prisma.sql`
        DELETE FROM "template_twin_provider_executions"
        WHERE "id" = ${succeeded.id}
      `),
    /permission denied for table template_twin_provider_executions/u,
  );
  await expectReject(
    () =>
      observer.$executeRaw(Prisma.sql`
        DELETE FROM "template_twin_provider_executions"
        WHERE "id" = ${succeeded.id}
      `),
    /TEMPLATE_TWIN_PROVIDER_EXECUTION_IMMUTABLE/u,
  );
  await expectReject(
    () =>
      observer.$executeRawUnsafe(
        'TRUNCATE TABLE "template_twin_provider_executions"',
      ),
    /TEMPLATE_TWIN_PROVIDER_EXECUTION_IMMUTABLE/u,
  );
  await expectReject(
    () =>
      observer.$executeRawUnsafe(
        'TRUNCATE TABLE "template_twin_provider_plan_decisions"',
      ),
    /TEMPLATE_TWIN_PROVIDER_PLAN_DECISION_IMMUTABLE/u,
  );
  await expectReject(
    () =>
      observer.$executeRawUnsafe(
        'TRUNCATE TABLE "template_twin_synthetic_qa_admissions" CASCADE',
      ),
    /Template Twin synthetic voice admission is immutable/u,
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
      inputSwapRejected: true,
      operationVersionSwapRejected: true,
      distinctOperationInstanceAdmitted: true,
      unknownReplayRejected: true,
      crossPhysicianReceiptRejected: true,
      mixedPhysicianReceiptRejected: true,
      deterministicArtifactRejected: true,
      syntheticArtifactRejected: true,
      syntheticStagingUploadPersisted: true,
      syntheticPromotionRejected: true,
      visitForeignKeyValidated: true,
      customFailurePersistedWithoutFabricatedReceipt: true,
      routineSearchPathsAndAclsVerified: true,
      resultHashMismatchRejected: true,
      runtimeDeleteRejected: true,
      ownerDeleteRejected: true,
      executionTruncateRejected: true,
      planDecisionTruncateRejected: true,
      terminalExecutionNoopUpdateRejected: true,
      planDecisionNoopUpdateRejected: true,
      crossPhysicianTemplateExecutionRejected: true,
      revokedReservedTerminalizedWithoutEgress: true,
      revokedAmbiguousOutcomeTerminalizedWithoutReplay: true,
      livePlanDecisionCurrentAuthorityAccepted: true,
      livePlanDecisionStaleGlobalEpochRejected: true,
      livePlanDecisionStalePracticeEpochRejected: true,
      livePlanDecisionGlobalDisableRejected: true,
      livePlanDecisionRevokedReleaseRejected: true,
      livePlanDecisionUpdateAndDeleteRejected: true,
      livePostProviderSuccessProjectionRejected: true,
      livePostProviderUnknownOutcomeTerminalizedWithoutReplay: true,
      preCertificationVoiceExactExecutionAccepted: true,
      preCertificationVoiceConcurrentClaimSingleWinner: true,
      preCertificationVoiceWrongAudioAttemptAndOperationRejected: true,
      preCertificationVoiceRevokedChildAndParentRejected: true,
      preCertificationVoiceVisitPatientAndAdmissionImmutable: true,
      liveCurrentAuthorityAccepted: true,
      livePatientTenantLifecycleAndReservedIdentityRejected: true,
      liveSourceTemplateCompilationAndCertificationDriftRejected: true,
      syntheticCurrentAuthorityAccepted: true,
      syntheticReservedPatientPhiDriftRejected: true,
      syntheticRunAdmissionAttemptClaimAndGenerationDriftRejected: true,
      syntheticExpiredDatabaseLeaseRejected: true,
      syntheticParentRevocationAndExpiryRejected: true,
      syntheticSourceTemplateCompilationAndCertificationDriftRejected: true,
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
