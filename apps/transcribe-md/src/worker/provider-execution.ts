import { getTemplateTwinSyntheticQaProviderContext } from "@meddoc/ai";
import prisma from "@meddoc/db";
import { Prisma } from "@prisma/client";
import { randomBytes, randomUUID } from "node:crypto";

import { canonicalSha256 } from "@/lib/template-twin/canonical";
import {
  runWithAutomationLayerEffectCapture,
  type CapturedAutomationLayerEffects,
} from "@/worker/automation-layer-effects";
import { runVisitAutomationTransaction } from "@/worker/automation-locks";
import type { VisitAutomationAttempt } from "@/worker/automation-manifest";
import type { VisitAutomationLayerId } from "@/worker/automation-policy";

export const VISIT_AUTOMATION_PROVIDER_RESULT_VERSION =
  "visit-automation-provider-result-v1" as const;

export interface VisitAutomationProviderDescriptor {
  provider: "anthropic";
  model: string;
  operationVersion: string;
}

interface ProviderResultEnvelope {
  contractVersion: typeof VISIT_AUTOMATION_PROVIDER_RESULT_VERSION;
  output: unknown;
  effects: CapturedAutomationLayerEffects;
}

interface LockedLayerExecutionIdentity {
  layerRowId: string;
  inputSha256: string;
  layerIdempotencyKey: string;
  manifestId: string;
  stagingAdmissionId: string | null;
  stagingRunId: string | null;
}

interface ProviderExecutionRow {
  id: string;
  practiceId: string;
  visitId: string;
  manifestId: string;
  automationLayerId: string;
  stagingAdmissionId: string | null;
  stagingRunId: string | null;
  inputSha256: string;
  provider: string;
  providerMode: string;
  model: string;
  operationVersion: string;
  idempotencyKey: string;
  status: string;
  invocationCount: number;
  resultPayload: Prisma.JsonValue | null;
  resultSha256: string | null;
  resultVersion: string | null;
}

const PROVIDER_EXECUTION_SAFE_SELECT = {
  id: true,
  practiceId: true,
  visitId: true,
  manifestId: true,
  automationLayerId: true,
  stagingAdmissionId: true,
  stagingRunId: true,
  inputSha256: true,
  provider: true,
  providerMode: true,
  model: true,
  operationVersion: true,
  idempotencyKey: true,
  status: true,
  invocationCount: true,
  resultPayload: true,
  resultSha256: true,
  resultVersion: true,
} as const;

type ProviderExecutionClaimResult =
  | {
      kind: "CLAIMED_BY_CALLER";
      executionId: string;
      claimId: string;
      idempotencyKey: string;
    }
  | { kind: "ALREADY_IN_PROGRESS"; executionId: string }
  | { kind: "ALREADY_SUCCEEDED"; executionId: string }
  | { kind: "FAILED"; executionId: string }
  | { kind: "UNKNOWN_OUTCOME"; executionId: string };

export interface VisitAutomationProviderClaimMetrics {
  claimedByCaller: number;
  alreadyInProgress: number;
  alreadySucceeded: number;
  failed: number;
  unknownOutcome: number;
}

let providerClaimMetrics: VisitAutomationProviderClaimMetrics = {
  claimedByCaller: 0,
  alreadyInProgress: 0,
  alreadySucceeded: 0,
  failed: 0,
  unknownOutcome: 0,
};

export function getVisitAutomationProviderClaimMetrics(): VisitAutomationProviderClaimMetrics {
  return { ...providerClaimMetrics };
}

export function resetVisitAutomationProviderClaimMetricsForTest(): void {
  providerClaimMetrics = {
    claimedByCaller: 0,
    alreadyInProgress: 0,
    alreadySucceeded: 0,
    failed: 0,
    unknownOutcome: 0,
  };
}

function recordClaimDisposition(
  kind: ProviderExecutionClaimResult["kind"],
): void {
  const key = {
    CLAIMED_BY_CALLER: "claimedByCaller",
    ALREADY_IN_PROGRESS: "alreadyInProgress",
    ALREADY_SUCCEEDED: "alreadySucceeded",
    FAILED: "failed",
    UNKNOWN_OUTCOME: "unknownOutcome",
  }[kind] as keyof VisitAutomationProviderClaimMetrics;
  providerClaimMetrics[key] += 1;
}

const PROVIDER_EXECUTION_TERMINAL_WAIT_MS = 5_000;
const PROVIDER_EXECUTION_POLL_MS = 20;

export class VisitAutomationProviderExecutionError extends Error {
  constructor(
    readonly code:
      | "VISIT_AUTOMATION_PROVIDER_EXECUTION_STALE"
      | "VISIT_AUTOMATION_PROVIDER_EXECUTION_IN_PROGRESS"
      | "VISIT_AUTOMATION_PROVIDER_OUTCOME_UNKNOWN"
      | "VISIT_AUTOMATION_PROVIDER_EXECUTION_FAILED"
      | "VISIT_AUTOMATION_PROVIDER_RESULT_INVALID",
  ) {
    super(
      "The automation provider result is unavailable or cannot be safely replayed.",
    );
    this.name = "VisitAutomationProviderExecutionError";
  }
}

function providerMode(): "SYNTHETIC_QA" | "DETERMINISTIC_MOCK" | "LIVE" {
  if (getTemplateTwinSyntheticQaProviderContext()) return "SYNTHETIC_QA";
  return process.env.MOCK_AI_CALLS === "true" ? "DETERMINISTIC_MOCK" : "LIVE";
}

function executionIdempotencyKey(input: {
  layerIdempotencyKey: string;
  descriptor: VisitAutomationProviderDescriptor;
  mode: string;
}): string {
  return canonicalSha256({
    contractVersion: "visit-automation-provider-execution-v1",
    layerIdempotencyKey: input.layerIdempotencyKey,
    provider: input.descriptor.provider,
    providerMode: input.mode,
    model: input.descriptor.model,
    operationVersion: input.descriptor.operationVersion,
  });
}

async function lockLayerIdentity(input: {
  tx: Prisma.TransactionClient;
  attempt: VisitAutomationAttempt;
  layerId: VisitAutomationLayerId;
  practiceId: string;
  visitId: string;
}): Promise<LockedLayerExecutionIdentity> {
  const rows = await input.tx.$queryRaw<
    Array<{
      layerRowId: string;
      inputSha256: string;
      layerIdempotencyKey: string;
      manifestId: string;
      manifestVersion: number;
      practiceId: string;
      visitId: string;
      stagingAdmissionId: string | null;
      stagingRunId: string | null;
    }>
  >(Prisma.sql`
    SELECT
      l."id" AS "layerRowId", l."inputSha256",
      l."idempotencyKey" AS "layerIdempotencyKey",
      m."id" AS "manifestId", m."manifestVersion", m."practiceId",
      m."visitId", m."stagingAdmissionId", m."stagingRunId"
    FROM "visit_automation_manifests" m
    JOIN "visit_automation_layers" l ON l."manifestId" = m."id"
    WHERE m."id" = ${input.attempt.manifestId}
      AND l."layerId" = ${input.layerId}
    FOR UPDATE OF m, l
  `);
  const row = rows[0];
  if (
    !row ||
    row.manifestVersion !== input.attempt.manifestVersion ||
    row.practiceId !== input.practiceId ||
    row.visitId !== input.visitId
  ) {
    throw new VisitAutomationProviderExecutionError(
      "VISIT_AUTOMATION_PROVIDER_EXECUTION_STALE",
    );
  }
  return row;
}

async function lockProviderExecution(input: {
  tx: Prisma.TransactionClient;
  row: ProviderExecutionRow;
  identity: LockedLayerExecutionIdentity;
}): Promise<ProviderExecutionRow> {
  const layers = await input.tx.$queryRaw<Array<{ layerRowId: string }>>(
    Prisma.sql`
      SELECT l."id" AS "layerRowId"
      FROM "visit_automation_manifests" m
      JOIN "visit_automation_layers" l ON l."manifestId" = m."id"
      WHERE m."id" = ${input.identity.manifestId}
        AND l."id" = ${input.identity.layerRowId}
      FOR UPDATE OF m, l
    `,
  );
  if (layers[0]?.layerRowId !== input.identity.layerRowId) {
    throw new VisitAutomationProviderExecutionError(
      "VISIT_AUTOMATION_PROVIDER_EXECUTION_STALE",
    );
  }
  const executions = await input.tx.$queryRaw<
    ProviderExecutionRow[]
  >(Prisma.sql`
    SELECT
      "id", "practiceId", "visitId", "manifestId", "automationLayerId",
      "stagingAdmissionId", "stagingRunId", "inputSha256", "provider",
      "providerMode", "model", "operationVersion", "idempotencyKey",
      "status", "invocationCount", "resultPayload", "resultSha256",
      "resultVersion"
    FROM "visit_automation_provider_executions"
    WHERE "id" = ${input.row.id}
    FOR UPDATE
  `);
  const current = executions[0];
  if (!current) {
    throw new VisitAutomationProviderExecutionError(
      "VISIT_AUTOMATION_PROVIDER_EXECUTION_STALE",
    );
  }
  return current;
}

function assertExecutionIdentity(input: {
  row: ProviderExecutionRow;
  identity: LockedLayerExecutionIdentity;
  practiceId: string;
  visitId: string;
  descriptor: VisitAutomationProviderDescriptor;
  mode: string;
  idempotencyKey: string;
}): void {
  const row = input.row;
  if (
    row.practiceId !== input.practiceId ||
    row.visitId !== input.visitId ||
    row.manifestId !== input.identity.manifestId ||
    row.automationLayerId !== input.identity.layerRowId ||
    row.stagingAdmissionId !== input.identity.stagingAdmissionId ||
    row.stagingRunId !== input.identity.stagingRunId ||
    row.inputSha256 !== input.identity.inputSha256 ||
    row.provider !== input.descriptor.provider ||
    row.providerMode !== input.mode ||
    row.model !== input.descriptor.model ||
    row.operationVersion !== input.descriptor.operationVersion ||
    row.idempotencyKey !== input.idempotencyKey
  ) {
    throw new VisitAutomationProviderExecutionError(
      "VISIT_AUTOMATION_PROVIDER_EXECUTION_STALE",
    );
  }
}

async function reserveExecution(input: {
  attempt: VisitAutomationAttempt;
  layerId: VisitAutomationLayerId;
  visitId: string;
  userId: string;
  practiceId: string;
  descriptor: VisitAutomationProviderDescriptor;
}): Promise<{
  row: ProviderExecutionRow;
  identity: LockedLayerExecutionIdentity;
}> {
  const mode = providerMode();
  const reserved = await runVisitAutomationTransaction({
    operation: "reserve_visit_automation_provider_execution",
    visitId: input.visitId,
    userId: input.userId,
    practiceId: input.practiceId,
    transaction: async (tx) => {
      const identity = await lockLayerIdentity({ tx, ...input });
      const idempotencyKey = executionIdempotencyKey({
        layerIdempotencyKey: identity.layerIdempotencyKey,
        descriptor: input.descriptor,
        mode,
      });
      const inserted = await tx.$queryRaw<ProviderExecutionRow[]>(Prisma.sql`
        INSERT INTO "visit_automation_provider_executions" (
          "id", "practiceId", "visitId", "manifestId", "automationLayerId",
          "stagingAdmissionId", "stagingRunId", "inputSha256", "provider",
          "providerMode", "model", "operationVersion", "idempotencyKey",
          "updatedAt"
        )
        VALUES (
          ${randomUUID()}, ${input.practiceId}, ${input.visitId},
          ${identity.manifestId}, ${identity.layerRowId},
          ${identity.stagingAdmissionId}, ${identity.stagingRunId},
          ${identity.inputSha256}, ${input.descriptor.provider}, ${mode},
          ${input.descriptor.model}, ${input.descriptor.operationVersion},
          ${idempotencyKey}, clock_timestamp()
        )
        ON CONFLICT (
          "automationLayerId", "manifestId", "practiceId", "visitId"
        ) DO NOTHING
        RETURNING
          "id", "practiceId", "visitId", "manifestId", "automationLayerId",
          "stagingAdmissionId", "stagingRunId", "inputSha256", "provider",
          "providerMode", "model", "operationVersion", "idempotencyKey",
          "status", "invocationCount", "resultPayload", "resultSha256",
          "resultVersion"
      `);
      const row =
        inserted[0] ??
        (await tx.visitAutomationProviderExecution.findFirst({
          where: {
            automationLayerId: identity.layerRowId,
            manifestId: identity.manifestId,
            practiceId: input.practiceId,
            visitId: input.visitId,
          },
          select: PROVIDER_EXECUTION_SAFE_SELECT,
        }));
      if (!row) {
        throw new VisitAutomationProviderExecutionError(
          "VISIT_AUTOMATION_PROVIDER_EXECUTION_STALE",
        );
      }
      assertExecutionIdentity({
        row,
        identity,
        practiceId: input.practiceId,
        visitId: input.visitId,
        descriptor: input.descriptor,
        mode,
        idempotencyKey,
      });
      return { row: row as ProviderExecutionRow, identity };
    },
  });

  // This independent root-client read proves the reservation committed before
  // provider selection or invocation is possible.
  const committed = await prisma.visitAutomationProviderExecution.findUnique({
    where: { id: reserved.row.id },
    select: PROVIDER_EXECUTION_SAFE_SELECT,
  });
  if (!committed) {
    throw new VisitAutomationProviderExecutionError(
      "VISIT_AUTOMATION_PROVIDER_EXECUTION_STALE",
    );
  }
  assertExecutionIdentity({
    row: committed as ProviderExecutionRow,
    identity: reserved.identity,
    practiceId: input.practiceId,
    visitId: input.visitId,
    descriptor: input.descriptor,
    mode,
    idempotencyKey: reserved.row.idempotencyKey,
  });
  return {
    row: committed as ProviderExecutionRow,
    identity: reserved.identity,
  };
}

function parseCommittedResult(
  row: ProviderExecutionRow,
): ProviderResultEnvelope {
  const payload = row.resultPayload as unknown;
  if (
    row.status !== "SUCCEEDED" ||
    row.resultVersion !== VISIT_AUTOMATION_PROVIDER_RESULT_VERSION ||
    !row.resultSha256 ||
    !payload ||
    Array.isArray(payload) ||
    typeof payload !== "object" ||
    (payload as { contractVersion?: unknown }).contractVersion !==
      VISIT_AUTOMATION_PROVIDER_RESULT_VERSION ||
    canonicalSha256(payload) !== row.resultSha256
  ) {
    throw new VisitAutomationProviderExecutionError(
      "VISIT_AUTOMATION_PROVIDER_RESULT_INVALID",
    );
  }
  return payload as ProviderResultEnvelope;
}

async function readCommittedExecution(
  executionId: string,
): Promise<ProviderExecutionRow | null> {
  return (await prisma.visitAutomationProviderExecution.findUnique({
    where: { id: executionId },
    select: PROVIDER_EXECUTION_SAFE_SELECT,
  })) as ProviderExecutionRow | null;
}

async function claimProviderExecution(input: {
  row: ProviderExecutionRow;
  identity: LockedLayerExecutionIdentity;
  visitId: string;
  userId: string;
  practiceId: string;
}): Promise<ProviderExecutionClaimResult> {
  // Generated outside the retried transaction so a commit-acknowledgement
  // retry can prove that this same caller already won without learning any
  // other worker's internal concurrency token.
  const claimId = randomBytes(32).toString("hex");
  return runVisitAutomationTransaction({
    operation: "claim_visit_automation_provider_execution",
    visitId: input.visitId,
    userId: input.userId,
    practiceId: input.practiceId,
    transaction: async (tx) => {
      const current = await lockProviderExecution({
        tx,
        row: input.row,
        identity: input.identity,
      });
      const claimed = await tx.$queryRaw<
        Array<{ id: string; idempotencyKey: string; claimId: string }>
      >(Prisma.sql`
        UPDATE "visit_automation_provider_executions"
        SET "status" = 'IN_FLIGHT'::"VisitAutomationProviderExecutionStatus",
            "claimId" = ${claimId},
            "claimedAt" = clock_timestamp(),
            "invocationCount" = 1,
            "invokedAt" = clock_timestamp(),
            "updatedAt" = clock_timestamp()
        WHERE "id" = ${current.id}
          AND "status" = 'RESERVED'::"VisitAutomationProviderExecutionStatus"
          AND "claimId" IS NULL
        RETURNING "id", "idempotencyKey", "claimId"
      `);
      const winner = claimed[0];
      if (winner) {
        if (winner.id !== current.id || winner.claimId !== claimId) {
          throw new VisitAutomationProviderExecutionError(
            "VISIT_AUTOMATION_PROVIDER_EXECUTION_STALE",
          );
        }
        return {
          kind: "CLAIMED_BY_CALLER",
          executionId: winner.id,
          claimId,
          idempotencyKey: winner.idempotencyKey,
        };
      }

      // The transaction wrapper may retry after PostgreSQL committed the CAS
      // but before the client observed it. Match only the caller-generated
      // token; never read or return a competing worker's token.
      const callerOwns = await tx.$queryRaw<
        Array<{ id: string; idempotencyKey: string }>
      >(Prisma.sql`
        SELECT "id", "idempotencyKey"
        FROM "visit_automation_provider_executions"
        WHERE "id" = ${current.id}
          AND "status" = 'IN_FLIGHT'::"VisitAutomationProviderExecutionStatus"
          AND "claimId" = ${claimId}
      `);
      if (callerOwns[0]) {
        return {
          kind: "CLAIMED_BY_CALLER",
          executionId: callerOwns[0].id,
          claimId,
          idempotencyKey: callerOwns[0].idempotencyKey,
        };
      }

      switch (current.status) {
        case "IN_FLIGHT":
          return { kind: "ALREADY_IN_PROGRESS", executionId: current.id };
        case "SUCCEEDED":
          return { kind: "ALREADY_SUCCEEDED", executionId: current.id };
        case "FAILED":
          return { kind: "FAILED", executionId: current.id };
        case "UNKNOWN_OUTCOME":
          return { kind: "UNKNOWN_OUTCOME", executionId: current.id };
        default:
          throw new VisitAutomationProviderExecutionError(
            "VISIT_AUTOMATION_PROVIDER_EXECUTION_STALE",
          );
      }
    },
  });
}

async function waitForProviderExecutionTerminal(
  executionId: string,
): Promise<ProviderExecutionRow> {
  const deadline = Date.now() + PROVIDER_EXECUTION_TERMINAL_WAIT_MS;
  while (Date.now() < deadline) {
    const current = await readCommittedExecution(executionId);
    if (!current) {
      throw new VisitAutomationProviderExecutionError(
        "VISIT_AUTOMATION_PROVIDER_EXECUTION_STALE",
      );
    }
    if (current.status !== "IN_FLIGHT") return current;
    await new Promise<void>((resolve) => {
      setTimeout(resolve, PROVIDER_EXECUTION_POLL_MS);
    });
  }
  throw new VisitAutomationProviderExecutionError(
    "VISIT_AUTOMATION_PROVIDER_EXECUTION_IN_PROGRESS",
  );
}

async function transitionClaimedExecution(input: {
  row: ProviderExecutionRow;
  identity: LockedLayerExecutionIdentity;
  claim: Extract<ProviderExecutionClaimResult, { kind: "CLAIMED_BY_CALLER" }>;
  visitId: string;
  userId: string;
  practiceId: string;
  status: "FAILED" | "UNKNOWN_OUTCOME";
  failureCode: string;
}): Promise<ProviderExecutionRow> {
  return runVisitAutomationTransaction({
    operation: `transition_visit_automation_provider_${input.status.toLowerCase()}`,
    visitId: input.visitId,
    userId: input.userId,
    practiceId: input.practiceId,
    transaction: async (tx) => {
      const current = await lockProviderExecution({
        tx,
        row: input.row,
        identity: input.identity,
      });
      const updated = await tx.visitAutomationProviderExecution.updateMany({
        where: {
          id: input.claim.executionId,
          status: "IN_FLIGHT",
          claimId: input.claim.claimId,
        },
        data: {
          status: input.status,
          completedAt: new Date(),
          failureCode: input.failureCode,
        },
      });
      const owned = await tx.visitAutomationProviderExecution.findFirst({
        where: {
          id: input.claim.executionId,
          claimId: input.claim.claimId,
        },
        select: PROVIDER_EXECUTION_SAFE_SELECT,
      });
      if (updated.count === 1 && owned?.status === input.status) {
        return owned as ProviderExecutionRow;
      }
      if (updated.count === 0 && owned?.status === input.status) {
        return owned as ProviderExecutionRow;
      }
      if (current.status === "IN_FLIGHT" || !owned) {
        throw new VisitAutomationProviderExecutionError(
          "VISIT_AUTOMATION_PROVIDER_EXECUTION_STALE",
        );
      }
      throw new VisitAutomationProviderExecutionError(
        current.status === "UNKNOWN_OUTCOME"
          ? "VISIT_AUTOMATION_PROVIDER_OUTCOME_UNKNOWN"
          : "VISIT_AUTOMATION_PROVIDER_EXECUTION_FAILED",
      );
    },
  });
}

async function persistSuccessfulResult(input: {
  row: ProviderExecutionRow;
  identity: LockedLayerExecutionIdentity;
  claim: Extract<ProviderExecutionClaimResult, { kind: "CLAIMED_BY_CALLER" }>;
  visitId: string;
  userId: string;
  practiceId: string;
  envelope: ProviderResultEnvelope;
}): Promise<ProviderExecutionRow> {
  const resultSha256 = canonicalSha256(input.envelope);
  try {
    return await runVisitAutomationTransaction({
      operation: "persist_visit_automation_provider_result",
      visitId: input.visitId,
      userId: input.userId,
      practiceId: input.practiceId,
      transaction: async (tx) => {
        const current = await lockProviderExecution({
          tx,
          row: input.row,
          identity: input.identity,
        });
        const updated = await tx.visitAutomationProviderExecution.updateMany({
          where: {
            id: input.claim.executionId,
            status: "IN_FLIGHT",
            claimId: input.claim.claimId,
          },
          data: {
            status: "SUCCEEDED",
            resultPayload: input.envelope as unknown as Prisma.InputJsonValue,
            resultSha256,
            resultVersion: VISIT_AUTOMATION_PROVIDER_RESULT_VERSION,
            completedAt: new Date(),
          },
        });
        const owned = await tx.visitAutomationProviderExecution.findFirst({
          where: {
            id: input.claim.executionId,
            claimId: input.claim.claimId,
          },
          select: PROVIDER_EXECUTION_SAFE_SELECT,
        });
        if (updated.count === 1 && owned?.status === "SUCCEEDED") {
          return owned as ProviderExecutionRow;
        }
        if (
          updated.count === 0 &&
          owned?.status === "SUCCEEDED" &&
          owned.resultSha256 === resultSha256
        ) {
          return owned as ProviderExecutionRow;
        }
        if (current.status === "SUCCEEDED" && !owned) {
          throw new VisitAutomationProviderExecutionError(
            "VISIT_AUTOMATION_PROVIDER_EXECUTION_STALE",
          );
        }
        throw new VisitAutomationProviderExecutionError(
          current.status === "SUCCEEDED"
            ? "VISIT_AUTOMATION_PROVIDER_RESULT_INVALID"
            : "VISIT_AUTOMATION_PROVIDER_EXECUTION_STALE",
        );
      },
    });
  } catch (error) {
    const committed = await prisma.visitAutomationProviderExecution.findUnique({
      where: { claimId: input.claim.claimId },
      select: PROVIDER_EXECUTION_SAFE_SELECT,
    });
    if (
      committed?.status === "SUCCEEDED" &&
      committed.resultSha256 === resultSha256
    ) {
      return committed as ProviderExecutionRow;
    }
    throw error;
  }
}

export async function runDurableVisitAutomationProvider<T>(input: {
  attempt: VisitAutomationAttempt;
  layerId: VisitAutomationLayerId;
  visitId: string;
  userId: string;
  practiceId: string;
  descriptor: VisitAutomationProviderDescriptor;
  invoke: (idempotencyKey: string) => Promise<T>;
  validate?: (output: T) => void;
}): Promise<{
  executionId: string;
  output: T;
  effects: CapturedAutomationLayerEffects;
  reused: boolean;
}> {
  const reserved = await reserveExecution(input);
  const reuseCommitted = (row: ProviderExecutionRow) => {
    const envelope = parseCommittedResult(row);
    input.validate?.(envelope.output as T);
    return {
      executionId: row.id,
      output: envelope.output as T,
      effects: envelope.effects,
      reused: true,
    };
  };
  const rejectTerminal = (row: ProviderExecutionRow): never => {
    throw new VisitAutomationProviderExecutionError(
      row.status === "UNKNOWN_OUTCOME"
        ? "VISIT_AUTOMATION_PROVIDER_OUTCOME_UNKNOWN"
        : "VISIT_AUTOMATION_PROVIDER_EXECUTION_FAILED",
    );
  };

  if (reserved.row.status === "SUCCEEDED") {
    return reuseCommitted(reserved.row);
  }
  if (
    reserved.row.status === "FAILED" ||
    reserved.row.status === "UNKNOWN_OUTCOME"
  ) {
    return rejectTerminal(reserved.row);
  }

  const claim = await claimProviderExecution({
    row: reserved.row,
    identity: reserved.identity,
    visitId: input.visitId,
    userId: input.userId,
    practiceId: input.practiceId,
  });
  recordClaimDisposition(claim.kind);
  if (claim.kind !== "CLAIMED_BY_CALLER") {
    if (claim.kind === "FAILED" || claim.kind === "UNKNOWN_OUTCOME") {
      return rejectTerminal({
        ...reserved.row,
        status: claim.kind === "UNKNOWN_OUTCOME" ? "UNKNOWN_OUTCOME" : "FAILED",
      });
    }
    const completed =
      claim.kind === "ALREADY_SUCCEEDED"
        ? await readCommittedExecution(claim.executionId)
        : await waitForProviderExecutionTerminal(claim.executionId);
    if (!completed) {
      throw new VisitAutomationProviderExecutionError(
        "VISIT_AUTOMATION_PROVIDER_EXECUTION_STALE",
      );
    }
    if (completed.status === "SUCCEEDED") return reuseCommitted(completed);
    if (
      completed.status === "FAILED" ||
      completed.status === "UNKNOWN_OUTCOME"
    ) {
      return rejectTerminal(completed);
    }
    throw new VisitAutomationProviderExecutionError(
      "VISIT_AUTOMATION_PROVIDER_EXECUTION_IN_PROGRESS",
    );
  }

  let captured: { output: T; effects: CapturedAutomationLayerEffects };
  try {
    captured = await runWithAutomationLayerEffectCapture({
      layerId: input.layerId,
      visitId: input.visitId,
      userId: input.userId,
      practiceId: input.practiceId,
      callback: () => input.invoke(claim.idempotencyKey),
    });
  } catch (error) {
    await transitionClaimedExecution({
      row: reserved.row,
      identity: reserved.identity,
      claim,
      visitId: input.visitId,
      userId: input.userId,
      practiceId: input.practiceId,
      status:
        reserved.row.providerMode === "LIVE" ? "UNKNOWN_OUTCOME" : "FAILED",
      failureCode:
        reserved.row.providerMode === "LIVE"
          ? "PROVIDER_OUTCOME_AMBIGUOUS"
          : "PROVIDER_EXECUTION_FAILED",
    });
    throw error;
  }
  try {
    input.validate?.(captured.output);
  } catch (error) {
    await transitionClaimedExecution({
      row: reserved.row,
      identity: reserved.identity,
      claim,
      visitId: input.visitId,
      userId: input.userId,
      practiceId: input.practiceId,
      status: "FAILED",
      failureCode: "PROVIDER_OUTPUT_INVALID",
    });
    throw error;
  }
  const envelope: ProviderResultEnvelope = {
    contractVersion: VISIT_AUTOMATION_PROVIDER_RESULT_VERSION,
    output: captured.output,
    effects: captured.effects,
  };
  let succeeded: ProviderExecutionRow;
  try {
    succeeded = await persistSuccessfulResult({
      row: reserved.row,
      identity: reserved.identity,
      claim,
      visitId: input.visitId,
      userId: input.userId,
      practiceId: input.practiceId,
      envelope,
    });
  } catch (persistenceError) {
    try {
      await transitionClaimedExecution({
        row: reserved.row,
        identity: reserved.identity,
        claim,
        visitId: input.visitId,
        userId: input.userId,
        practiceId: input.practiceId,
        status: "UNKNOWN_OUTCOME",
        failureCode: "PROVIDER_RESULT_PERSISTENCE_AMBIGUOUS",
      });
    } catch (transitionError) {
      throw new AggregateError(
        [persistenceError, transitionError],
        "Provider result persistence and ambiguity recording both failed.",
      );
    }
    throw persistenceError;
  }
  parseCommittedResult(succeeded);
  return {
    executionId: succeeded.id,
    output: captured.output,
    effects: captured.effects,
    reused: false,
  };
}
