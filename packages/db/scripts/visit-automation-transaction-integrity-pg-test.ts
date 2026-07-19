#!/usr/bin/env tsx

/**
 * Actual-PostgreSQL visit-automation transaction proof.
 *
 * The harness accepts only a positively identified disposable QA/test
 * database. It exercises the production manifest, fanout, finalization, and
 * whole-transaction retry code with synthetic values. It never invokes a
 * provider, queue, object store, or production service.
 */

import { performance } from "node:perf_hooks";

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";

import {
  getDatabaseTransactionRetryMetrics,
  resetDatabaseTransactionRetryMetricsForTest,
  runSerializableTransactionWithRetry,
} from "../../../apps/transcribe-md/src/lib/db/transaction-retry";
import {
  VisitAutomationIncompleteError,
  finalizeVisitAutomationReady,
} from "../../../apps/transcribe-md/src/worker/automation-finalization";
import {
  initializeVisitAutomationManifest,
  markVisitAutomationLayerRunning,
  recordVisitAutomationLayerSuccess,
} from "../../../apps/transcribe-md/src/worker/automation-manifest";
import { runVisitAutomationTransaction } from "../../../apps/transcribe-md/src/worker/automation-locks";
import {
  buildVisitAutomationPolicy,
  VISIT_AUTOMATION_LAYER_IDS,
} from "../../../apps/transcribe-md/src/worker/automation-policy";
import { runAutomationFanout } from "../../../apps/transcribe-md/src/worker/run-automation-fanout";
import {
  getVisitAutomationProviderClaimMetrics,
  resetVisitAutomationProviderClaimMetricsForTest,
  runDurableVisitAutomationProvider,
} from "../../../apps/transcribe-md/src/worker/provider-execution";
import { assertNonProdDatabase } from "../src/db-guard";

const databaseUrl =
  process.env.VISIT_AUTOMATION_TEST_DATABASE_URL ?? process.env.DATABASE_URL;
assertNonProdDatabase(databaseUrl);
if (!databaseUrl)
  throw new Error("Disposable automation test URL is required.");
const verifiedDatabaseUrl = databaseUrl;

const suffix = `${process.pid}-${Date.now()}`;
const practiceId = `synthetic-automation-practice-${suffix}`;
const userId = `synthetic-automation-doctor-${suffix}`;
const patientId = `synthetic-automation-patient-${suffix}`;
const soap = "Synthetic transaction-integrity QA note with no patient data.";
const syntheticHash = "a".repeat(64);
const journeyCount = Number(process.env.VISIT_AUTOMATION_JOURNEY_COUNT ?? "20");
if (!Number.isInteger(journeyCount) || journeyCount < 1 || journeyCount > 100) {
  throw new Error("VISIT_AUTOMATION_JOURNEY_COUNT must be an integer 1..100.");
}
process.env.MOCK_AI_CALLS = "true";

const APPLICABLE_LAYER_IDS = VISIT_AUTOMATION_LAYER_IDS.filter(
  (layerId) => layerId !== "em_mdm_prewarm",
);

function client(applicationName: string): PrismaClient {
  const url = new URL(verifiedDatabaseUrl);
  url.searchParams.set("application_name", applicationName);
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

const observer = client(`visit-automation-observer-${suffix}`);
const contenderA = client(`visit-automation-contender-a-${suffix}`);
const contenderB = client(`visit-automation-contender-b-${suffix}`);

async function seedIdentity(): Promise<void> {
  await observer.practice.create({
    data: {
      id: practiceId,
      name: "Synthetic transaction-integrity practice",
      slug: practiceId,
      templateTwinEnabled: false,
    },
  });
  await observer.user.create({
    data: {
      id: userId,
      email: `transaction-integrity-${suffix}@synthetic.test`,
      passwordHash: "synthetic-not-a-credential",
      role: "DOCTOR",
      practiceId,
    },
  });
  await observer.transcribeMdPatient.create({
    data: {
      id: patientId,
      name: "Synthetic Automation",
      practiceId,
    },
  });
}

async function createVisit(label: string): Promise<string> {
  const visitId = `synthetic-automation-${label}-${suffix}`;
  await observer.transcribeVisit.create({
    data: {
      id: visitId,
      userId,
      patientId,
      specialty: "primary-care",
      inputMode: "text",
      status: "AUTOMATING",
      soapFinal: soap,
      soapVersion: 1,
    },
  });
  return visitId;
}

function policy(staging = false) {
  return buildVisitAutomationPolicy({
    staging,
    enabled: Object.fromEntries(
      VISIT_AUTOMATION_LAYER_IDS.map((layerId) => [
        layerId,
        layerId !== "em_mdm_prewarm",
      ]),
    ) as Record<(typeof VISIT_AUTOMATION_LAYER_IDS)[number], boolean>,
  });
}

function syntheticTasks(providerCalls: Map<string, number>) {
  return VISIT_AUTOMATION_LAYER_IDS.map((key) => ({
    key,
    enabled: key !== "em_mdm_prewarm",
    provider: {
      provider: "anthropic" as const,
      model: "synthetic-automation-model-v1",
      operationVersion: `${key}-synthetic-v1`,
    },
    run: async (_providerIdempotencyKey: string) => {
      providerCalls.set(key, (providerCalls.get(key) ?? 0) + 1);
      return { synthetic: true, layer: key };
    },
  }));
}

async function runSuccessfulJourney(label: string): Promise<{
  visitId: string;
  durationMs: number;
  providerCalls: number;
}> {
  const visitId = await createVisit(label);
  const started = performance.now();
  const attempt = await initializeVisitAutomationManifest({
    visitId,
    userId,
    practiceId,
    soapVersion: 1,
    soapFinal: soap,
    sourceFacts: { synthetic: true, label },
    policy: policy(true),
  });
  const providerCalls = new Map<string, number>();
  await runAutomationFanout({
    attempt,
    visitId,
    userId,
    practiceId,
    tasks: syntheticTasks(providerCalls),
  });
  await finalizeVisitAutomationReady({
    attempt,
    visitId,
    userId,
    practiceId,
    processingFinishedAt: new Date(),
    processingCostCents: 0,
    confidenceScores: { synthetic: true },
  });
  const [visit, manifest, providerExecutions, layerAudits, completionAudits] =
    await Promise.all([
      observer.transcribeVisit.findUniqueOrThrow({
        where: { id: visitId },
        select: { status: true },
      }),
      observer.visitAutomationManifest.findUniqueOrThrow({
        where: { visitId },
        include: { layers: true },
      }),
      observer.visitAutomationProviderExecution.findMany({
        where: { visitId },
        select: { status: true, invocationCount: true, resultSha256: true },
      }),
      observer.templateTwinAuditOutbox.count({
        where: {
          targetId: visitId,
          targetType: "VisitAutomationLayer",
          action: "VISIT_AUTOMATION_COMPLETED",
        },
      }),
      observer.templateTwinAuditOutbox.count({
        where: {
          eventKey: `visit-automation:completed:${visitId}:${attempt.manifestVersion}`,
        },
      }),
    ]);
  if (
    visit.status !== "READY" ||
    manifest.status !== "COMPLETE" ||
    manifest.layers.length !== VISIT_AUTOMATION_LAYER_IDS.length ||
    manifest.layers.some((layer) =>
      layer.layerId === "em_mdm_prewarm"
        ? layer.status !== "NOT_APPLICABLE" || layer.completedAt === null
        : layer.status !== "SUCCEEDED" ||
          layer.outputSha256 === null ||
          layer.completedAt === null,
    ) ||
    providerExecutions.length !== APPLICABLE_LAYER_IDS.length ||
    providerExecutions.some(
      (execution) =>
        execution.status !== "SUCCEEDED" ||
        execution.invocationCount !== 1 ||
        execution.resultSha256 === null,
    ) ||
    layerAudits !== APPLICABLE_LAYER_IDS.length ||
    completionAudits !== 1 ||
    [...providerCalls.values()].some((count) => count !== 1)
  ) {
    throw new Error("A synthetic automation journey lacked terminal proof.");
  }
  return {
    visitId,
    durationMs: performance.now() - started,
    providerCalls: [...providerCalls.values()].reduce(
      (sum, count) => sum + count,
      0,
    ),
  };
}

async function provePostProviderProjectionRollbackAndReuse(): Promise<void> {
  const visitId = await createVisit("provider-projection-retry");
  const attempt = await initializeVisitAutomationManifest({
    visitId,
    userId,
    practiceId,
    soapVersion: 1,
    soapFinal: soap,
    sourceFacts: { synthetic: true, case: "provider-projection-retry" },
    policy: buildVisitAutomationPolicy({
      staging: false,
      enabled: Object.fromEntries(
        VISIT_AUTOMATION_LAYER_IDS.map((layerId) => [
          layerId,
          layerId === "icd_coding",
        ]),
      ) as Record<(typeof VISIT_AUTOMATION_LAYER_IDS)[number], boolean>,
    }),
  });
  await markVisitAutomationLayerRunning({
    attempt,
    visitId,
    userId,
    practiceId,
    layerId: "icd_coding",
  });
  let providerCalls = 0;
  const providerInput = {
    attempt,
    visitId,
    userId,
    practiceId,
    layerId: "icd_coding" as const,
    descriptor: {
      provider: "anthropic" as const,
      model: "synthetic-automation-model-v1",
      operationVersion: "icd-projection-retry-v1",
    },
    invoke: async (_providerIdempotencyKey: string) => {
      providerCalls += 1;
      return { codes: [{ code: "Z00.00" }] };
    },
  };
  const first = await runDurableVisitAutomationProvider(providerInput);
  await observer.$executeRawUnsafe(`
    CREATE OR REPLACE FUNCTION qa_force_automation_outbox_failure()
    RETURNS trigger AS $body$
    BEGIN
      RAISE EXCEPTION 'synthetic audit outbox failure' USING ERRCODE = '23514';
    END
    $body$ LANGUAGE plpgsql;
    CREATE TRIGGER qa_force_automation_outbox_failure
      BEFORE INSERT ON template_twin_audit_outbox
      FOR EACH ROW EXECUTE FUNCTION qa_force_automation_outbox_failure();
  `);
  const effects = {
    visitMutations: [{ data: { icdCodes: { codes: [{ code: "Z00.00" }] } } }],
    audits: [],
  };
  try {
    await recordVisitAutomationLayerSuccess({
      attempt,
      visitId,
      userId,
      practiceId,
      layerId: "icd_coding",
      output: first.output,
      providerExecutionId: first.executionId,
      effects,
    }).then(
      () => {
        throw new Error("Layer projection advanced despite audit failure.");
      },
      () => undefined,
    );
  } finally {
    await observer.$executeRawUnsafe(`
      DROP TRIGGER IF EXISTS qa_force_automation_outbox_failure
        ON template_twin_audit_outbox;
      DROP FUNCTION IF EXISTS qa_force_automation_outbox_failure();
    `);
  }
  const afterFailure = await observer.transcribeVisit.findUniqueOrThrow({
    where: { id: visitId },
    select: {
      icdCodes: true,
      automationManifest: {
        select: {
          layers: {
            where: { layerId: "icd_coding" },
            select: { status: true },
          },
        },
      },
    },
  });
  if (
    afterFailure.icdCodes !== null ||
    afterFailure.automationManifest?.layers[0]?.status !== "RUNNING"
  ) {
    throw new Error("Layer audit failure left a partial clinical projection.");
  }
  const reused = await runDurableVisitAutomationProvider(providerInput);
  if (!reused.reused || providerCalls !== 1) {
    throw new Error("Projection retry repeated a durable provider execution.");
  }
  await recordVisitAutomationLayerSuccess({
    attempt,
    visitId,
    userId,
    practiceId,
    layerId: "icd_coding",
    output: reused.output,
    providerExecutionId: reused.executionId,
    effects: reused.effects,
  });
  const committed = await observer.visitAutomationLayer.findFirstOrThrow({
    where: { manifestId: attempt.manifestId, layerId: "icd_coding" },
    select: { status: true },
  });
  if (committed.status !== "SUCCEEDED") {
    throw new Error("Reused provider result did not commit exactly once.");
  }
}

async function proveProviderClaimOwnershipRace(): Promise<{
  contenders: number;
  claimWinners: number;
  nonWinners: number;
  providerInvocations: number;
  databaseRetryMetrics: ReturnType<typeof getDatabaseTransactionRetryMetrics>;
}> {
  const contenders = 20;
  const visitId = await createVisit("provider-claim-race");
  const attempt = await initializeVisitAutomationManifest({
    visitId,
    userId,
    practiceId,
    soapVersion: 1,
    soapFinal: soap,
    sourceFacts: { synthetic: true, case: "provider-claim-race" },
    policy: buildVisitAutomationPolicy({
      staging: false,
      enabled: Object.fromEntries(
        VISIT_AUTOMATION_LAYER_IDS.map((layerId) => [
          layerId,
          layerId === "icd_coding",
        ]),
      ) as Record<(typeof VISIT_AUTOMATION_LAYER_IDS)[number], boolean>,
    }),
  });
  await markVisitAutomationLayerRunning({
    attempt,
    visitId,
    userId,
    practiceId,
    layerId: "icd_coding",
  });
  resetVisitAutomationProviderClaimMetricsForTest();
  resetDatabaseTransactionRetryMetricsForTest();
  const providerEntered = latch();
  const releaseProvider = latch();
  let providerInvocations = 0;
  const providerInput = {
    attempt,
    visitId,
    userId,
    practiceId,
    layerId: "icd_coding" as const,
    descriptor: {
      provider: "anthropic" as const,
      model: "synthetic-automation-model-v1",
      operationVersion: "icd-provider-claim-race-v1",
    },
    invoke: async (_providerIdempotencyKey: string) => {
      providerInvocations += 1;
      providerEntered.release();
      await releaseProvider.promise;
      return { codes: [{ code: "Z00.00" }] };
    },
  };
  const runs = Array.from({ length: contenders }, () =>
    runDurableVisitAutomationProvider(providerInput),
  );
  await providerEntered.promise;
  const claimDeadline = Date.now() + 4_000;
  while (Date.now() < claimDeadline) {
    const metrics = getVisitAutomationProviderClaimMetrics();
    if (metrics.claimedByCaller + metrics.alreadyInProgress === contenders) {
      break;
    }
    await new Promise<void>((resolve) => setTimeout(resolve, 5));
  }
  const observed = getVisitAutomationProviderClaimMetrics();
  if (observed.claimedByCaller + observed.alreadyInProgress !== contenders) {
    releaseProvider.release();
    await Promise.allSettled(runs);
    throw new Error("The provider claim race did not reach every contender.");
  }
  const active =
    await observer.visitAutomationProviderExecution.findFirstOrThrow({
      where: { visitId, automationLayer: { layerId: "icd_coding" } },
      select: { id: true, status: true },
    });
  const nonOwnerMutationCount = await observer.$executeRaw`
    UPDATE "visit_automation_provider_executions"
    SET "status" = 'FAILED'::"VisitAutomationProviderExecutionStatus",
        "completedAt" = clock_timestamp(),
        "failureCode" = 'PROVIDER_EXECUTION_FAILED',
        "updatedAt" = clock_timestamp()
    WHERE "id" = ${active.id}
      AND "status" = 'IN_FLIGHT'::"VisitAutomationProviderExecutionStatus"
      AND "claimId" = ${"f".repeat(64)}
  `;
  if (active.status !== "IN_FLIGHT" || nonOwnerMutationCount !== 0) {
    releaseProvider.release();
    await Promise.allSettled(runs);
    throw new Error("A non-owner altered the active provider execution.");
  }
  releaseProvider.release();
  const results = await Promise.all(runs);
  const execution =
    await observer.visitAutomationProviderExecution.findFirstOrThrow({
      where: { visitId, automationLayer: { layerId: "icd_coding" } },
      select: {
        status: true,
        invocationCount: true,
        claimId: true,
      claimedAt: true,
    },
  });
  const databaseRetryMetrics = getDatabaseTransactionRetryMetrics();
  if (
    providerInvocations !== 1 ||
    observed.claimedByCaller !== 1 ||
    observed.alreadyInProgress !== contenders - 1 ||
    results.filter((result) => !result.reused).length !== 1 ||
    results.filter((result) => result.reused).length !== contenders - 1 ||
    execution.status !== "SUCCEEDED" ||
    execution.invocationCount !== 1 ||
    execution.claimId === null ||
    execution.claimedAt === null ||
    databaseRetryMetrics.exhausted !== 0
  ) {
    throw new Error("Provider execution ownership was not single-winner.");
  }
  return {
    contenders,
    claimWinners: observed.claimedByCaller,
    nonWinners: observed.alreadyInProgress,
    providerInvocations,
    databaseRetryMetrics,
  };
}

async function proveRequiredFailuresPersist(): Promise<void> {
  const visitId = await createVisit("required-failure");
  const attempt = await initializeVisitAutomationManifest({
    visitId,
    userId,
    practiceId,
    soapVersion: 1,
    soapFinal: soap,
    sourceFacts: { synthetic: true, case: "required-failure" },
    policy: policy(true),
  });
  const tasks = syntheticTasks(new Map());
  for (const task of tasks) {
    if (task.key === "icd_coding" || task.key === "rx_drafting") {
      task.run = async () => {
        throw new Error("synthetic provider failure");
      };
    }
  }
  await runAutomationFanout({
    attempt,
    visitId,
    userId,
    practiceId,
    tasks,
  });
  let blocked = false;
  try {
    await finalizeVisitAutomationReady({
      attempt,
      visitId,
      userId,
      practiceId,
      processingFinishedAt: new Date(),
      processingCostCents: 0,
      confidenceScores: null,
    });
  } catch (error) {
    blocked = error instanceof VisitAutomationIncompleteError;
  }
  const manifest = await observer.visitAutomationManifest.findUniqueOrThrow({
    where: { visitId },
    include: { layers: true, visit: { select: { status: true } } },
  });
  const failedIds = manifest.layers
    .filter((layer) => layer.status === "FAILED")
    .map((layer) => layer.layerId)
    .sort();
  if (
    !blocked ||
    manifest.status !== "INCOMPLETE" ||
    manifest.visit.status === "READY" ||
    failedIds.join(",") !== "icd_coding,rx_drafting"
  ) {
    throw new Error("Required layer failures did not block finalization.");
  }
  await observer.transcribeVisit
    .update({ where: { id: visitId }, data: { status: "SIGNED" } })
    .then(
      () => {
        throw new Error("Database allowed SIGNED with incomplete automation.");
      },
      () => undefined,
    );
}

async function proveAuditRollbackAndRetry(): Promise<void> {
  const visitId = await createVisit("audit-rollback");
  const attempt = await initializeVisitAutomationManifest({
    visitId,
    userId,
    practiceId,
    soapVersion: 1,
    soapFinal: soap,
    sourceFacts: { synthetic: true, case: "audit-rollback" },
    policy: policy(),
  });
  const providerCalls = new Map<string, number>();
  await runAutomationFanout({
    attempt,
    visitId,
    userId,
    practiceId,
    tasks: syntheticTasks(providerCalls),
  });
  const completionKey = `visit-automation:completed:${visitId}:${attempt.manifestVersion}`;
  await observer.templateTwinAuditOutbox.create({
    data: {
      practiceId,
      actorId: userId,
      eventKey: completionKey,
      action: "VISIT_AUTOMATION_INCOMPLETE",
      targetType: "TranscribeVisit",
      targetId: visitId,
      metadata: { syntheticCollision: true },
    },
  });
  await finalizeVisitAutomationReady({
    attempt,
    visitId,
    userId,
    practiceId,
    processingFinishedAt: new Date(),
    processingCostCents: 0,
    confidenceScores: null,
  }).then(
    () => {
      throw new Error("Finalization advanced despite audit insertion failure.");
    },
    () => undefined,
  );
  const rolledBack = await observer.transcribeVisit.findUniqueOrThrow({
    where: { id: visitId },
    select: { status: true, automationManifest: { select: { status: true } } },
  });
  if (
    rolledBack.status !== "AUTOMATING" ||
    rolledBack.automationManifest?.status !== "RUNNING"
  ) {
    throw new Error("Audit failure left a partial clinical state.");
  }
  await observer.templateTwinAuditOutbox.delete({
    where: { eventKey: completionKey },
  });
  await finalizeVisitAutomationReady({
    attempt,
    visitId,
    userId,
    practiceId,
    processingFinishedAt: new Date(),
    processingCostCents: 0,
    confidenceScores: null,
  });
  if ([...providerCalls.values()].some((count) => count !== 1)) {
    throw new Error("Database retry duplicated a provider result.");
  }
}

async function proveUnsignedReprocessAndSignedImmutability(): Promise<void> {
  const first = await runSuccessfulJourney("unsigned-reprocess");
  const updatedSoap = `${soap} Synthetic reviewed amendment.`;
  await observer.transcribeVisit.update({
    where: { id: first.visitId },
    data: {
      status: "AUTOMATING",
      soapFinal: updatedSoap,
      soapVersion: { increment: 1 },
    },
  });
  const attempt = await initializeVisitAutomationManifest({
    visitId: first.visitId,
    userId,
    practiceId,
    soapVersion: 2,
    soapFinal: updatedSoap,
    sourceFacts: { synthetic: true, case: "unsigned-reprocess-v2" },
    policy: policy(true),
  });
  if (attempt.manifestVersion !== 2) {
    throw new Error("Unsigned reprocessing did not advance the proof version.");
  }
  await runAutomationFanout({
    attempt,
    visitId: first.visitId,
    userId,
    practiceId,
    tasks: syntheticTasks(new Map()),
  });
  await finalizeVisitAutomationReady({
    attempt,
    visitId: first.visitId,
    userId,
    practiceId,
    processingFinishedAt: new Date(),
    processingCostCents: 0,
    confidenceScores: { synthetic: true },
  });
  const reprocessed = await observer.visitAutomationManifest.findUniqueOrThrow({
    where: { visitId: first.visitId },
    include: { layers: true, visit: { select: { status: true } } },
  });
  if (
    reprocessed.status !== "COMPLETE" ||
    reprocessed.manifestVersion !== 2 ||
    reprocessed.soapVersion !== 2 ||
    reprocessed.visit.status !== "READY" ||
    reprocessed.layers.length !== VISIT_AUTOMATION_LAYER_IDS.length
  ) {
    throw new Error("Unsigned reprocessing did not create an exact v2 proof.");
  }
  await observer.transcribeVisit.update({
    where: { id: first.visitId },
    data: { status: "SIGNED", signedAt: new Date() },
  });
  await observer.visitAutomationManifest
    .update({
      where: { visitId: first.visitId },
      data: {
        status: "RUNNING",
        manifestVersion: { increment: 1 },
        completedAt: null,
      },
    })
    .then(
      () => {
        throw new Error("A signed COMPLETE proof was mutable.");
      },
      () => undefined,
    );
  const terminalLayer = reprocessed.layers[0];
  if (!terminalLayer) throw new Error("Signed proof had no layer rows.");
  await observer.visitAutomationLayer
    .update({
      where: { id: terminalLayer.id },
      data: { outputSha256: "f".repeat(64) },
    })
    .then(
      () => {
        throw new Error("A signed COMPLETE layer result was mutable.");
      },
      () => undefined,
    );
}

async function proveDatabaseConstraints(): Promise<void> {
  const visitId = await createVisit("constraint");
  await observer.transcribeVisit
    .create({
      data: {
        id: `synthetic-automation-ready-insert-${suffix}`,
        userId,
        patientId,
        specialty: "primary-care",
        inputMode: "text",
        status: "READY",
        soapFinal: soap,
        soapVersion: 1,
      },
    })
    .then(
      () => {
        throw new Error("READY insert was accepted without automation proof.");
      },
      () => undefined,
    );
  await observer.transcribeVisit
    .update({ where: { id: visitId }, data: { status: "READY" } })
    .then(
      () => {
        throw new Error("READY was accepted without an automation manifest.");
      },
      () => undefined,
    );

  const foreignPracticeId = `synthetic-automation-foreign-${suffix}`;
  await observer.practice.create({
    data: {
      id: foreignPracticeId,
      name: "Synthetic foreign automation practice",
      slug: foreignPracticeId,
    },
  });
  await observer.visitAutomationManifest
    .create({
      data: {
        practiceId: foreignPracticeId,
        visitId,
        soapVersion: 1,
        soapSha256: syntheticHash,
        sourceVersion: "soap-final-v1",
        sourceSha256: syntheticHash,
        policyVersion: "visit-automation-policy-v1",
        status: "RUNNING",
      },
    })
    .then(
      () => {
        throw new Error("Cross-practice automation manifest was accepted.");
      },
      () => undefined,
    );

  const attempt = await initializeVisitAutomationManifest({
    visitId,
    userId,
    practiceId,
    soapVersion: 1,
    soapFinal: soap,
    sourceFacts: { synthetic: true, case: "constraint-terminal-proof" },
    policy: policy(),
  });
  await observer.visitAutomationManifest
    .update({
      where: { visitId },
      data: { status: "COMPLETE", completedAt: new Date() },
    })
    .then(
      () => {
        throw new Error("Incomplete manifest was accepted as COMPLETE.");
      },
      () => undefined,
    );
  await runAutomationFanout({
    attempt,
    visitId,
    userId,
    practiceId,
    tasks: syntheticTasks(new Map()),
  });
  const terminalLayer = await observer.visitAutomationLayer.findFirstOrThrow({
    where: { manifestId: attempt.manifestId, layerId: "icd_coding" },
    select: { id: true },
  });
  await observer.visitAutomationLayer
    .update({
      where: { id: terminalLayer.id },
      data: { outputSha256: "b".repeat(64) },
    })
    .then(
      () => {
        throw new Error("Terminal layer result was mutable.");
      },
      () => undefined,
    );
  await finalizeVisitAutomationReady({
    attempt,
    visitId,
    userId,
    practiceId,
    processingFinishedAt: new Date(),
    processingCostCents: 0,
    confidenceScores: { synthetic: true },
  });
  await observer.visitAutomationManifest
    .update({
      where: { visitId },
      data: { attemptCount: { increment: 1 } },
    })
    .then(
      () => {
        throw new Error("A COMPLETE automation manifest was mutable.");
      },
      () => undefined,
    );
}

async function proveCanonicalLockOrder(): Promise<{
  blockingObserved: boolean;
  deadlocks: number;
}> {
  const firstVisitId = await createVisit("canonical-lock-a");
  const secondVisitId = await createVisit("canonical-lock-b");
  const firstEntered = latch();
  const releaseFirst = latch();
  let firstPid = 0;
  resetDatabaseTransactionRetryMetricsForTest();
  const first = runVisitAutomationTransaction({
    operation: "canonical_lock_probe_a",
    visitId: firstVisitId,
    userId,
    practiceId,
    transaction: async (tx) => {
      const rows = await tx.$queryRawUnsafe<Array<{ pid: number }>>(
        "SELECT pg_backend_pid() AS pid",
      );
      firstPid = rows[0]?.pid ?? 0;
      firstEntered.release();
      await releaseFirst.promise;
    },
  });
  await firstEntered.promise;
  if (firstPid <= 0) throw new Error("Canonical lock probe lost its backend.");
  const second = runVisitAutomationTransaction({
    operation: "canonical_lock_probe_b",
    visitId: secondVisitId,
    userId,
    practiceId,
    transaction: async () => undefined,
  });
  let blockingObserved = false;
  for (let attempt = 0; attempt < 5_000; attempt += 1) {
    const rows = await observer.$queryRawUnsafe<Array<{ blocked: number }>>(
      `SELECT COUNT(*)::int AS blocked
       FROM pg_stat_activity
       WHERE datname = current_database()
         AND $1 = ANY(pg_blocking_pids(pid))`,
      firstPid,
    );
    if ((rows[0]?.blocked ?? 0) > 0) {
      blockingObserved = true;
      break;
    }
    await new Promise<void>((resolve) => setImmediate(resolve));
  }
  releaseFirst.release();
  await Promise.all([first, second]);
  const metrics = getDatabaseTransactionRetryMetrics();
  if (!blockingObserved || metrics.deadlocks !== 0 || metrics.exhausted !== 0) {
    throw new Error("Canonical lock order did not serialize cleanly.");
  }
  return { blockingObserved, deadlocks: metrics.deadlocks };
}

async function proveDeadlockRetry(): Promise<{
  events: number;
  retries: number;
  exhausted: number;
  resolutionMs: number;
}> {
  resetDatabaseTransactionRetryMetricsForTest();
  const started = performance.now();
  const readyA = latch();
  const readyB = latch();
  const firstLock = 8_410_001;
  const secondLock = 8_410_002;
  const attemptsA: number[] = [];
  const attemptsB: number[] = [];
  const run = (
    prisma: PrismaClient,
    operation: string,
    own: number,
    other: number,
    ownReady: ReturnType<typeof latch>,
    otherReady: ReturnType<typeof latch>,
    attempts: number[],
  ) =>
    runSerializableTransactionWithRetry({
      prisma,
      operation,
      transaction: async (tx, attempt) => {
        attempts.push(attempt);
        if (attempt === 1) {
          await tx.$executeRawUnsafe("SELECT pg_advisory_xact_lock($1)", own);
          ownReady.release();
          await otherReady.promise;
          await tx.$executeRawUnsafe("SELECT pg_advisory_xact_lock($1)", other);
        } else {
          await tx.$executeRawUnsafe(
            "SELECT pg_advisory_xact_lock($1)",
            Math.min(own, other),
          );
          await tx.$executeRawUnsafe(
            "SELECT pg_advisory_xact_lock($1)",
            Math.max(own, other),
          );
        }
        return true;
      },
    });
  await Promise.all([
    run(
      contenderA,
      "postgres_deadlock_probe_a",
      firstLock,
      secondLock,
      readyA,
      readyB,
      attemptsA,
    ),
    run(
      contenderB,
      "postgres_deadlock_probe_b",
      secondLock,
      firstLock,
      readyB,
      readyA,
      attemptsB,
    ),
  ]);
  const metrics = getDatabaseTransactionRetryMetrics();
  if (
    metrics.deadlocks < 1 ||
    metrics.exhausted !== 0 ||
    attemptsA.length + attemptsB.length < 3
  ) {
    throw new Error(
      "PostgreSQL deadlock was not retried as a whole transaction.",
    );
  }
  return {
    events: metrics.deadlocks,
    retries: metrics.retries,
    exhausted: metrics.exhausted,
    resolutionMs: Math.round(performance.now() - started),
  };
}

async function proveSerializationRetry(): Promise<{
  events: number;
  retries: number;
  exhausted: number;
}> {
  await observer.$executeRawUnsafe(
    `CREATE TABLE IF NOT EXISTS qa_visit_automation_serialization_probe (
       id TEXT PRIMARY KEY,
       value INTEGER NOT NULL
     )`,
  );
  await observer.$executeRawUnsafe(
    "TRUNCATE qa_visit_automation_serialization_probe",
  );
  await observer.$executeRawUnsafe(
    "INSERT INTO qa_visit_automation_serialization_probe (id, value) VALUES ('a', 0), ('b', 0)",
  );
  resetDatabaseTransactionRetryMetricsForTest();
  const readA = latch();
  const readB = latch();
  const run = (
    prisma: PrismaClient,
    id: "a" | "b",
    ownRead: ReturnType<typeof latch>,
    otherRead: ReturnType<typeof latch>,
  ) =>
    runSerializableTransactionWithRetry({
      prisma,
      operation: `postgres_serialization_probe_${id}`,
      transaction: async (tx, attempt) => {
        await tx.$queryRawUnsafe(
          "SELECT SUM(value) FROM qa_visit_automation_serialization_probe",
        );
        if (attempt === 1) {
          ownRead.release();
          await otherRead.promise;
        }
        await tx.$executeRawUnsafe(
          "UPDATE qa_visit_automation_serialization_probe SET value = value + 1 WHERE id = $1",
          id,
        );
      },
    });
  await Promise.all([
    run(contenderA, "a", readA, readB),
    run(contenderB, "b", readB, readA),
  ]);
  const metrics = getDatabaseTransactionRetryMetrics();
  const rows = await observer.$queryRawUnsafe<Array<{ total: bigint }>>(
    "SELECT SUM(value)::bigint AS total FROM qa_visit_automation_serialization_probe",
  );
  if (
    metrics.serializationFailures < 1 ||
    metrics.exhausted !== 0 ||
    rows[0]?.total !== BigInt(2)
  ) {
    throw new Error(
      "PostgreSQL serialization retry did not commit exactly once.",
    );
  }
  return {
    events: metrics.serializationFailures,
    retries: metrics.retries,
    exhausted: metrics.exhausted,
  };
}

async function cleanup(): Promise<void> {
  await observer.$executeRawUnsafe(`
    DROP TRIGGER IF EXISTS qa_force_automation_outbox_failure
      ON template_twin_audit_outbox;
    DROP FUNCTION IF EXISTS qa_force_automation_outbox_failure();
  `);
  await observer.templateTwinAuditOutbox.deleteMany({
    where: {
      practiceId: {
        in: [practiceId, `synthetic-automation-foreign-${suffix}`],
      },
    },
  });
  await observer.transcribeVisit.deleteMany({ where: { userId } });
  await observer.transcribeMdPatient.deleteMany({ where: { id: patientId } });
  await observer.user.deleteMany({ where: { id: userId } });
  await observer.practice.deleteMany({
    where: {
      id: { in: [practiceId, `synthetic-automation-foreign-${suffix}`] },
    },
  });
  await observer.$executeRawUnsafe(
    "DROP TABLE IF EXISTS qa_visit_automation_serialization_probe",
  );
}

async function main(): Promise<void> {
  const deadlockBefore = await observer.$queryRawUnsafe<
    Array<{ deadlocks: bigint }>
  >(
    "SELECT deadlocks::bigint FROM pg_stat_database WHERE datname = current_database()",
  );
  const started = performance.now();
  try {
    await seedIdentity();
    await proveDatabaseConstraints();
    const canonicalLockOrder = await proveCanonicalLockOrder();
    await proveRequiredFailuresPersist();
    const providerClaimRace = await proveProviderClaimOwnershipRace();
    await provePostProviderProjectionRollbackAndReuse();
    await proveAuditRollbackAndRetry();
    await proveUnsignedReprocessAndSignedImmutability();
    const forcedDeadlock = await proveDeadlockRetry();
    const forcedSerialization = await proveSerializationRetry();
    const deadlockAfterFaults = await observer.$queryRawUnsafe<
      Array<{ deadlocks: bigint }>
    >(
      "SELECT deadlocks::bigint FROM pg_stat_database WHERE datname = current_database()",
    );
    resetDatabaseTransactionRetryMetricsForTest();
    const journeys = [];
    for (let index = 1; index <= journeyCount; index += 1) {
      journeys.push(
        await runSuccessfulJourney(
          `repeat-${index.toString().padStart(2, "0")}`,
        ),
      );
    }
    const deadlockAfter = await observer.$queryRawUnsafe<
      Array<{ deadlocks: bigint }>
    >(
      "SELECT deadlocks::bigint FROM pg_stat_database WHERE datname = current_database()",
    );
    const durations = journeys.map((journey) => journey.durationMs);
    const journeyRetryMetrics = getDatabaseTransactionRetryMetrics();
    process.stdout.write(
      `${JSON.stringify(
        {
          status: "PASS",
          syntheticOnly: true,
          journeyCount: journeys.length,
          expectedLayerRows:
            journeys.length * VISIT_AUTOMATION_LAYER_IDS.length,
          completionAuditCount: journeys.length,
          providerInvocationCount: journeys.reduce(
            (sum, journey) => sum + journey.providerCalls,
            0,
          ),
          providerClaimRace,
          forcedDeadlock,
          forcedSerialization,
          canonicalLockOrder,
          repeatedJourneyRetryMetrics: journeyRetryMetrics,
          repeatedJourneyDeadlockCounterDelta: Number(
            (deadlockAfter[0]?.deadlocks ?? BigInt(0)) -
              (deadlockAfterFaults[0]?.deadlocks ?? BigInt(0)),
          ),
          totalDeadlockCounterDelta: Number(
            (deadlockAfter[0]?.deadlocks ?? BigInt(0)) -
              (deadlockBefore[0]?.deadlocks ?? BigInt(0)),
          ),
          blockedOrFailedJourneyWrites: 0,
          durationMs: Math.round(performance.now() - started),
          maximumJourneyMs: Math.round(Math.max(...durations)),
          minimumJourneyMs: Math.round(Math.min(...durations)),
        },
        null,
        2,
      )}\n`,
    );
  } finally {
    await cleanup().catch(() => undefined);
    await Promise.all([
      observer.$disconnect(),
      contenderA.$disconnect(),
      contenderB.$disconnect(),
    ]);
  }
}

main().catch((error: unknown) => {
  process.stderr.write(
    `${error instanceof Error ? error.message : "Synthetic QA database proof failed."}\n`,
  );
  process.exitCode = 1;
});
