import {
  assertTemplateTwinSyntheticQaWorkerLeaseHealthy,
  getTemplateTwinSyntheticQaProviderContext,
  modelClient,
  type AnthropicCompleteTextResult,
  type CompleteArgs,
  type CompleteTextArgs,
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

export const TEMPLATE_TWIN_PROVIDER_RESULT_VERSION =
  "template-twin-provider-result-v1" as const;
export const TEMPLATE_TWIN_PROVIDER_RECEIPT_VERSION =
  "template-twin-provider-ownership-receipt-v1" as const;

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
  readonly rolloutToken: TemplateTwinRolloutToken;
}

export interface TemplateTwinProviderReceiptProjection {
  readonly subjectId: string;
  readonly subjectSha256: string;
  readonly visitId: string | null;
  readonly sourceArtifactId: string | null;
  readonly compiledVersionId: string | null;
  readonly noteTemplateId: string | null;
}

export interface TemplateTwinProviderOwnershipReceipt {
  readonly evidence: {
    readonly contractVersion: typeof TEMPLATE_TWIN_PROVIDER_RECEIPT_VERSION;
    readonly practiceId: string;
    readonly subjectId: string;
    readonly subjectSha256: string;
    readonly visitId: string | null;
    readonly sourceArtifactId: string | null;
    readonly compiledVersionId: string | null;
    readonly noteTemplateId: string | null;
    readonly executions: ReadonlyArray<{
      readonly executionId: string;
      readonly operation: TemplateTwinProviderOperation;
      readonly resultSha256: string;
    }>;
  };
  readonly sha256: string;
}

interface ProviderReceiptExecution {
  readonly executionId: string;
  readonly operation: TemplateTwinProviderOperation;
  readonly resultSha256: string;
}

interface ProviderOwnershipState {
  readonly context: TemplateTwinProviderOwnershipContext;
  readonly executions: Map<string, ProviderReceiptExecution>;
  active: boolean;
}

const ownershipContext = new AsyncLocalStorage<ProviderOwnershipState>();
const SHA256 = /^[a-f0-9]{64}$/u;

export type TemplateTwinProviderOwnershipErrorCode =
  | "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID"
  | "TEMPLATE_TWIN_PROVIDER_CONTEXT_NESTED"
  | "TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH"
  | "TEMPLATE_TWIN_PROVIDER_ROLLOUT_REVOKED"
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

  const synthetic = getTemplateTwinSyntheticQaProviderContext();
  if (
    synthetic &&
    (synthetic.practiceId !== context.practiceId ||
      (context.visitId !== null && synthetic.visitId !== context.visitId))
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
    active: true,
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

export function buildTemplateTwinProviderOwnershipReceipt(input: {
  readonly projection: TemplateTwinProviderReceiptProjection;
  readonly requiredOperations: readonly TemplateTwinProviderOperation[];
}): TemplateTwinProviderOwnershipReceipt {
  const state = ownershipContext.getStore();
  if (!state?.active) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
  }
  if (
    !SHA256.test(input.projection.subjectSha256) ||
    input.projection.subjectId.length === 0
  ) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
  }
  const executions = [...state.executions.values()].sort((left, right) =>
    `${left.operation}:${left.executionId}`.localeCompare(
      `${right.operation}:${right.executionId}`,
    ),
  );
  const available = new Set(executions.map((entry) => entry.operation));
  if (
    executions.length === 0 ||
    input.requiredOperations.some((operation) => !available.has(operation))
  ) {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE");
  }
  const evidence = {
    contractVersion: TEMPLATE_TWIN_PROVIDER_RECEIPT_VERSION,
    practiceId: state.context.practiceId,
    subjectId: input.projection.subjectId,
    subjectSha256: input.projection.subjectSha256,
    visitId: input.projection.visitId,
    sourceArtifactId: input.projection.sourceArtifactId,
    compiledVersionId: input.projection.compiledVersionId,
    noteTemplateId: input.projection.noteTemplateId,
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
  readonly scope: string;
  readonly operation: string;
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
  readonly status: string;
  readonly invocationCount: number;
  readonly claimId: string | null;
  readonly resultPayload: Prisma.JsonValue | null;
  readonly resultSha256: string | null;
  readonly resultVersion: string | null;
}

const PROVIDER_EXECUTION_SAFE_SELECT = {
  id: true,
  practiceId: true,
  actorUserId: true,
  visitId: true,
  scope: true,
  operation: true,
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
  status: true,
  invocationCount: true,
  claimId: true,
  resultPayload: true,
  resultSha256: true,
  resultVersion: true,
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

interface TemplateTwinProviderRuntimeDependencies {
  readonly db: ProviderOwnershipDbHost;
  readonly providerMode: () => TemplateTwinProviderMode;
  readonly lockRollout: (input: {
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

const DEFAULT_DEPENDENCIES: TemplateTwinProviderRuntimeDependencies = {
  db: prisma as unknown as ProviderOwnershipDbHost,
  providerMode: () => {
    if (getTemplateTwinSyntheticQaProviderContext()) return "SYNTHETIC_QA";
    return process.env.MOCK_AI_CALLS === "true" ? "DETERMINISTIC_MOCK" : "LIVE";
  },
  lockRollout: defaultLockRollout,
  executionId: randomUUID,
  claimId: () => randomBytes(32).toString("hex"),
  now: () => new Date(),
  sleep: (milliseconds) =>
    new Promise((resolve) => setTimeout(resolve, milliseconds)),
  terminalWaitMs: 5_000,
  pollMs: 20,
};

export interface TemplateTwinOwnedProviderInput<T> {
  readonly operation: TemplateTwinProviderOperation;
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
  readonly scope: TemplateTwinProviderScope;
  readonly operation: TemplateTwinProviderOperation;
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
  const runtimeIdentitySha256 = pipeSha256([
    "template-twin-provider-runtime-v1",
    input.mode,
    token.globalGeneration,
    token.practiceGeneration,
    releaseId ?? "-",
    releaseIdentitySha256 ?? "-",
    runtimeManifestSha256 ?? "-",
    runtimeInstanceId ?? "-",
  ]);
  const ownershipKey = pipeSha256([
    "template-twin-provider-ownership-v1",
    input.context.practiceId,
    input.context.actorUserId,
    input.context.scope,
    input.context.subjectId,
    input.context.subjectSha256,
    input.context.logicalAttempt,
    input.provider.operation,
    inputSha256,
    input.context.visitId ?? "-",
    input.context.sourceArtifactId ?? "-",
    input.context.compiledVersionId ?? "-",
    input.context.noteTemplateId ?? "-",
    input.context.noteTemplateVersion ?? "-",
    input.context.sourceLineageId ?? "-",
    input.context.sourceLineageVersion ?? "-",
    input.context.sourceSha256 ?? "-",
  ]);
  const idempotencyKey = pipeSha256([
    "template-twin-provider-idempotency-v1",
    ownershipKey,
    input.provider.provider,
    input.mode,
    input.provider.model,
    input.provider.operationVersion,
    providerConfigurationSha256,
    runtimeIdentitySha256,
  ]);
  return {
    id: input.executionId,
    practiceId: input.context.practiceId,
    actorUserId: input.context.actorUserId,
    visitId: input.context.visitId,
    scope: input.context.scope,
    operation: input.provider.operation,
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
  };
}

const IDENTITY_KEYS = [
  "practiceId",
  "actorUserId",
  "visitId",
  "scope",
  "operation",
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
  | { readonly kind: "ROLLOUT_REVOKED"; readonly row: ProviderExecutionRow };

function disposition(row: ProviderExecutionRow): ClaimDisposition {
  switch (row.status) {
    case "SUCCEEDED":
      return { kind: "SUCCEEDED", row };
    case "IN_FLIGHT":
      return { kind: "IN_PROGRESS", row };
    case "FAILED":
      return { kind: "FAILED", row };
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
          return { count: 0, rolloutRevoked: true };
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
        return { count: update.count, rolloutRevoked: false };
      },
      { isolationLevel: Prisma.TransactionIsolationLevel.ReadCommitted },
    );
    if (completion.rolloutRevoked) {
      throw ownershipError("TEMPLATE_TWIN_PROVIDER_ROLLOUT_REVOKED");
    }
  } catch (error) {
    if (
      error instanceof TemplateTwinProviderOwnershipError &&
      error.code === "TEMPLATE_TWIN_PROVIDER_ROLLOUT_REVOKED"
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
    resultSha256: row.resultSha256,
  });
}

export async function runTemplateTwinOwnedProvider<T>(
  input: TemplateTwinOwnedProviderInput<T>,
  dependencyOverrides: Partial<TemplateTwinProviderRuntimeDependencies> = {},
): Promise<T> {
  const state = ownershipContext.getStore();
  if (!state?.active) return input.invoke({});
  const dependencies = { ...DEFAULT_DEPENDENCIES, ...dependencyOverrides };
  const mode = dependencies.providerMode();
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
    const output = validatedResult(claim.row, input.validate);
    recordReceiptExecution(state, claim.row);
    return output;
  }
  if (claim.kind === "ROLLOUT_REVOKED") {
    throw ownershipError("TEMPLATE_TWIN_PROVIDER_ROLLOUT_REVOKED");
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

export async function runTemplateTwinOwnedModelComplete<T>(input: {
  readonly operation: TemplateTwinProviderOperation;
  readonly operationVersion: string;
  readonly args: CompleteArgs<T>;
}): Promise<T> {
  if (!getTemplateTwinProviderOwnershipContext()) {
    return modelClient.complete(input.args);
  }
  const schemaIdentity = z.toJSONSchema(input.args.schema);
  return runTemplateTwinOwnedProvider({
    operation: input.operation,
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
      system: input.args.system,
      user: input.args.user,
      schema: schemaIdentity,
    },
    invoke: ({ idempotencyKey }) =>
      modelClient.complete({
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
  readonly operationVersion: string;
  readonly args: CompleteTextArgs;
}): Promise<AnthropicCompleteTextResult> {
  if (!getTemplateTwinProviderOwnershipContext()) {
    return modelClient.completeText(input.args);
  }
  return runTemplateTwinOwnedProvider({
    operation: input.operation,
    operationVersion: input.operationVersion,
    provider: input.args.provider,
    model: input.args.model,
    providerConfiguration: {
      maxTokens: input.args.maxTokens ?? null,
      temperature: input.args.temperature ?? null,
    },
    inputIdentity: {
      purpose: input.args.purpose,
      system: input.args.system,
      user: input.args.user,
    },
    invoke: ({ idempotencyKey }) =>
      modelClient.completeText({ ...input.args, idempotencyKey }),
    validate: (output) => completeTextResultSchema.parse(output),
  });
}
