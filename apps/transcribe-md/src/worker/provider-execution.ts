import { getTemplateTwinSyntheticQaProviderContext } from "@meddoc/ai";
import prisma from "@meddoc/db";
import { Prisma } from "@prisma/client";

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

export class VisitAutomationProviderExecutionError extends Error {
  constructor(
    readonly code:
      | "VISIT_AUTOMATION_PROVIDER_EXECUTION_STALE"
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
      const existing = await tx.visitAutomationProviderExecution.findFirst({
        where: {
          automationLayerId: identity.layerRowId,
          manifestId: identity.manifestId,
          practiceId: input.practiceId,
          visitId: input.visitId,
        },
      });
      const row = existing
        ? existing
        : await tx.visitAutomationProviderExecution.create({
            data: {
              practiceId: input.practiceId,
              visitId: input.visitId,
              manifestId: identity.manifestId,
              automationLayerId: identity.layerRowId,
              stagingAdmissionId: identity.stagingAdmissionId,
              stagingRunId: identity.stagingRunId,
              inputSha256: identity.inputSha256,
              provider: input.descriptor.provider,
              providerMode: mode,
              model: input.descriptor.model,
              operationVersion: input.descriptor.operationVersion,
              idempotencyKey,
            },
          });
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

async function transitionExecution(input: {
  row: ProviderExecutionRow;
  identity: LockedLayerExecutionIdentity;
  visitId: string;
  userId: string;
  practiceId: string;
  status: "IN_FLIGHT" | "FAILED" | "UNKNOWN_OUTCOME";
  failureCode?: string;
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
      if (input.status === "IN_FLIGHT" && current.status !== "RESERVED") {
        return current as ProviderExecutionRow;
      }
      if (
        input.status !== "IN_FLIGHT" &&
        current.status !== "RESERVED" &&
        current.status !== "IN_FLIGHT"
      ) {
        return current as ProviderExecutionRow;
      }
      return (await tx.visitAutomationProviderExecution.update({
        where: { id: current.id },
        data:
          input.status === "IN_FLIGHT"
            ? {
                status: "IN_FLIGHT",
                invocationCount: 1,
                invokedAt: new Date(),
              }
            : {
                status: input.status,
                completedAt: new Date(),
                failureCode: input.failureCode ?? "PROVIDER_EXECUTION_FAILED",
              },
      })) as ProviderExecutionRow;
    },
  });
}

async function persistSuccessfulResult(input: {
  row: ProviderExecutionRow;
  identity: LockedLayerExecutionIdentity;
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
        if (current.status === "SUCCEEDED") {
          if (current.resultSha256 !== resultSha256) {
            throw new VisitAutomationProviderExecutionError(
              "VISIT_AUTOMATION_PROVIDER_RESULT_INVALID",
            );
          }
          return current as ProviderExecutionRow;
        }
        if (current.status !== "IN_FLIGHT") {
          throw new VisitAutomationProviderExecutionError(
            "VISIT_AUTOMATION_PROVIDER_EXECUTION_STALE",
          );
        }
        return (await tx.visitAutomationProviderExecution.update({
          where: { id: current.id },
          data: {
            status: "SUCCEEDED",
            resultPayload: input.envelope as unknown as Prisma.InputJsonValue,
            resultSha256,
            resultVersion: VISIT_AUTOMATION_PROVIDER_RESULT_VERSION,
            completedAt: new Date(),
          },
        })) as ProviderExecutionRow;
      },
    });
  } catch (error) {
    const committed = await prisma.visitAutomationProviderExecution.findUnique({
      where: { id: input.row.id },
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
  let row = reserved.row;
  if (row.status === "SUCCEEDED") {
    const envelope = parseCommittedResult(row);
    input.validate?.(envelope.output as T);
    return {
      executionId: row.id,
      output: envelope.output as T,
      effects: envelope.effects,
      reused: true,
    };
  }
  if (row.status === "IN_FLIGHT") {
    await transitionExecution({
      ...input,
      row,
      identity: reserved.identity,
      status: "UNKNOWN_OUTCOME",
      failureCode: "PROVIDER_OUTCOME_AMBIGUOUS",
    });
    throw new VisitAutomationProviderExecutionError(
      "VISIT_AUTOMATION_PROVIDER_OUTCOME_UNKNOWN",
    );
  }
  if (row.status === "FAILED" || row.status === "UNKNOWN_OUTCOME") {
    throw new VisitAutomationProviderExecutionError(
      row.status === "UNKNOWN_OUTCOME"
        ? "VISIT_AUTOMATION_PROVIDER_OUTCOME_UNKNOWN"
        : "VISIT_AUTOMATION_PROVIDER_EXECUTION_FAILED",
    );
  }
  row = await transitionExecution({
    ...input,
    row,
    identity: reserved.identity,
    status: "IN_FLIGHT",
  });
  if (row.status !== "IN_FLIGHT") {
    throw new VisitAutomationProviderExecutionError(
      "VISIT_AUTOMATION_PROVIDER_EXECUTION_STALE",
    );
  }

  let captured: { output: T; effects: CapturedAutomationLayerEffects };
  try {
    captured = await runWithAutomationLayerEffectCapture({
      layerId: input.layerId,
      visitId: input.visitId,
      userId: input.userId,
      practiceId: input.practiceId,
      callback: () => input.invoke(row.idempotencyKey),
    });
  } catch (error) {
    await transitionExecution({
      ...input,
      row,
      identity: reserved.identity,
      status: providerMode() === "LIVE" ? "UNKNOWN_OUTCOME" : "FAILED",
      failureCode:
        providerMode() === "LIVE"
          ? "PROVIDER_OUTCOME_AMBIGUOUS"
          : "PROVIDER_EXECUTION_FAILED",
    });
    throw error;
  }
  try {
    input.validate?.(captured.output);
  } catch (error) {
    await transitionExecution({
      ...input,
      row,
      identity: reserved.identity,
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
  const succeeded = await persistSuccessfulResult({
    ...input,
    row,
    identity: reserved.identity,
    envelope,
  });
  parseCommittedResult(succeeded);
  return {
    executionId: succeeded.id,
    output: captured.output,
    effects: captured.effects,
    reused: false,
  };
}
