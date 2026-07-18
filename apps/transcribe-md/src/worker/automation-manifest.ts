import { getTemplateTwinSyntheticQaProviderContext } from "@meddoc/ai";
import { Prisma, type VisitAutomationLayerStatus } from "@prisma/client";

import { canonicalSha256 } from "@/lib/template-twin/canonical";
import { canonicalSoapSha256 } from "@/lib/template-twin/soap-binding";
import { runVisitAutomationTransaction } from "@/worker/automation-locks";
import {
  classifyVisitAutomationFailure,
  type VisitAutomationFailureCode,
  type VisitAutomationLayerId,
  type VisitAutomationLayerPolicy,
  VISIT_AUTOMATION_POLICY_VERSION,
  VISIT_AUTOMATION_SOURCE_VERSION,
} from "@/worker/automation-policy";

export const VISIT_AUTOMATION_PROOF_VERSION =
  "visit-automation-proof-v1" as const;

export const VISIT_AUTOMATION_MANIFEST_SELECT = {
  id: true,
  practiceId: true,
  visitId: true,
  stagingAdmissionId: true,
  stagingRunId: true,
  soapVersion: true,
  soapSha256: true,
  sourceVersion: true,
  sourceSha256: true,
  policyVersion: true,
  manifestVersion: true,
  status: true,
  attemptCount: true,
  pinnedGlobalRolloutGeneration: true,
  pinnedPracticeRolloutGeneration: true,
  completedAt: true,
  layers: {
    orderBy: { layerId: "asc" as const },
    select: {
      layerId: true,
      layerVersion: true,
      requirement: true,
      status: true,
      attemptCount: true,
      inputSha256: true,
      outputSha256: true,
      failureCode: true,
      idempotencyKey: true,
      startedAt: true,
      completedAt: true,
    },
  },
} as const;

export interface VisitAutomationManifestProof {
  id: string;
  practiceId: string;
  visitId: string;
  stagingAdmissionId: string | null;
  stagingRunId: string | null;
  soapVersion: number;
  soapSha256: string;
  sourceVersion: string;
  sourceSha256: string;
  policyVersion: string;
  manifestVersion: number;
  status: string;
  attemptCount: number;
  pinnedGlobalRolloutGeneration: bigint | null;
  pinnedPracticeRolloutGeneration: bigint | null;
  completedAt: Date | null;
  layers: Array<{
    layerId: string;
    layerVersion: string;
    requirement: string;
    status: string;
    attemptCount: number;
    inputSha256: string;
    outputSha256: string | null;
    failureCode: string | null;
    idempotencyKey: string;
    startedAt: Date | null;
    completedAt: Date | null;
  }>;
}

export interface VisitAutomationAttempt {
  manifestId: string;
  manifestVersion: number;
  soapVersion: number;
  soapSha256: string;
  sourceSha256: string;
  policy: VisitAutomationLayerPolicy[];
}

interface LockedManifestIdentity {
  id: string;
  practiceId: string;
  visitId: string;
  stagingAdmissionId: string | null;
  stagingRunId: string | null;
  soapVersion: number;
  soapSha256: string;
  sourceVersion: string;
  sourceSha256: string;
  policyVersion: string;
  manifestVersion: number;
  status: string;
  pinnedGlobalRolloutGeneration: bigint | null;
  pinnedPracticeRolloutGeneration: bigint | null;
}

async function lockManifest(
  tx: Prisma.TransactionClient,
  visitId: string,
): Promise<LockedManifestIdentity | null> {
  const rows = await tx.$queryRaw<LockedManifestIdentity[]>(Prisma.sql`
    SELECT
      "id", "practiceId", "visitId", "stagingAdmissionId", "stagingRunId",
      "soapVersion", "soapSha256", "sourceVersion", "sourceSha256",
      "policyVersion", "manifestVersion", "status",
      "pinnedGlobalRolloutGeneration", "pinnedPracticeRolloutGeneration"
    FROM "visit_automation_manifests"
    WHERE "visitId" = ${visitId}
    FOR UPDATE
  `);
  return rows[0] ?? null;
}

async function lockLayer(
  tx: Prisma.TransactionClient,
  manifestId: string,
  layerId: VisitAutomationLayerId,
): Promise<{
  id: string;
  status: VisitAutomationLayerStatus;
  outputSha256: string | null;
} | null> {
  const rows = await tx.$queryRaw<
    Array<{
      id: string;
      status: VisitAutomationLayerStatus;
      outputSha256: string | null;
    }>
  >(Prisma.sql`
    SELECT "id", "status", "outputSha256"
    FROM "visit_automation_layers"
    WHERE "manifestId" = ${manifestId}
      AND "layerId" = ${layerId}
    FOR UPDATE
  `);
  return rows[0] ?? null;
}

function assertCurrentBinding(input: {
  manifest: LockedManifestIdentity | null;
  practiceId: string;
  visitId: string;
  soapVersion: number;
  soapSha256: string;
}): asserts input is typeof input & { manifest: LockedManifestIdentity } {
  const context = getTemplateTwinSyntheticQaProviderContext();
  const manifest = input.manifest;
  if (
    !manifest ||
    manifest.practiceId !== input.practiceId ||
    manifest.visitId !== input.visitId ||
    manifest.soapVersion !== input.soapVersion ||
    manifest.soapSha256 !== input.soapSha256 ||
    manifest.sourceVersion !== VISIT_AUTOMATION_SOURCE_VERSION ||
    manifest.policyVersion !== VISIT_AUTOMATION_POLICY_VERSION ||
    (context
      ? manifest.stagingAdmissionId !== context.admissionId ||
        manifest.stagingRunId !== context.runId ||
        manifest.pinnedGlobalRolloutGeneration !==
          context.pinnedGlobalGeneration ||
        manifest.pinnedPracticeRolloutGeneration !==
          context.pinnedPracticeGeneration
      : manifest.stagingAdmissionId !== null || manifest.stagingRunId !== null)
  ) {
    throw new VisitAutomationManifestError("VISIT_AUTOMATION_MANIFEST_STALE");
  }
}

export class VisitAutomationManifestError extends Error {
  constructor(
    readonly code:
      | "VISIT_AUTOMATION_MANIFEST_STALE"
      | "VISIT_AUTOMATION_LAYER_NOT_FOUND"
      | "VISIT_AUTOMATION_LAYER_STATE_INVALID",
  ) {
    super("The durable visit automation proof is unavailable or stale.");
    this.name = "VisitAutomationManifestError";
  }
}

/**
 * Terminally closes any nonterminal layer rows after the visit row is locked.
 * Callers must use the canonical transaction helper so lock order remains
 * visit -> manifest -> layer rows -> outbox. Clinical content is never stored.
 */
export async function markVisitAutomationManifestFailed(
  tx: Prisma.TransactionClient,
  input: {
    visitId: string;
    failureCode: "WORKER_ATTEMPT_FAILED" | "WORKER_LEASE_EXPIRED";
    completedAt: Date;
  },
): Promise<{
  id: string;
  manifestVersion: number;
  attemptCount: number;
} | null> {
  const manifest = await lockManifest(tx, input.visitId);
  if (!manifest) return null;
  if (manifest.status === "COMPLETE") {
    throw new VisitAutomationManifestError(
      "VISIT_AUTOMATION_LAYER_STATE_INVALID",
    );
  }
  await tx.$queryRaw(Prisma.sql`
    SELECT "id"
    FROM "visit_automation_layers"
    WHERE "manifestId" = ${manifest.id}
    ORDER BY "layerId"
    FOR UPDATE
  `);
  await tx.$executeRaw(Prisma.sql`
    UPDATE "visit_automation_layers"
    SET "status" = 'FAILED'::"VisitAutomationLayerStatus",
        "attemptCount" = GREATEST("attemptCount", 1),
        "outputSha256" = NULL,
        "failureCode" = ${input.failureCode},
        "startedAt" = COALESCE("startedAt", ${input.completedAt}),
        "completedAt" = ${input.completedAt},
        "updatedAt" = ${input.completedAt}
    WHERE "manifestId" = ${manifest.id}
      AND "status" IN (
        'PENDING'::"VisitAutomationLayerStatus",
        'RUNNING'::"VisitAutomationLayerStatus"
      )
  `);
  await tx.visitAutomationManifest.update({
    where: { id: manifest.id },
    data: { status: "FAILED", completedAt: input.completedAt },
  });
  const current = await tx.visitAutomationManifest.findUniqueOrThrow({
    where: { id: manifest.id },
    select: { id: true, manifestVersion: true, attemptCount: true },
  });
  return current;
}

function layerInputSha256(input: {
  layer: VisitAutomationLayerPolicy;
  soapSha256: string;
  sourceSha256: string;
}): string {
  return canonicalSha256({
    proofVersion: VISIT_AUTOMATION_PROOF_VERSION,
    policyVersion: VISIT_AUTOMATION_POLICY_VERSION,
    layerId: input.layer.layerId,
    layerVersion: input.layer.layerVersion,
    requirement: input.layer.requirement,
    soapSha256: input.soapSha256,
    sourceSha256: input.sourceSha256,
  });
}

function layerIdempotencyKey(input: {
  visitId: string;
  manifestVersion: number;
  layer: VisitAutomationLayerPolicy;
  inputSha256: string;
}): string {
  return canonicalSha256({
    proofVersion: VISIT_AUTOMATION_PROOF_VERSION,
    visitId: input.visitId,
    manifestVersion: input.manifestVersion,
    layerId: input.layer.layerId,
    layerVersion: input.layer.layerVersion,
    inputSha256: input.inputSha256,
  });
}

export async function initializeVisitAutomationManifest(input: {
  visitId: string;
  userId: string;
  practiceId: string;
  soapVersion: number;
  soapFinal: string;
  sourceFacts: unknown;
  policy: VisitAutomationLayerPolicy[];
}): Promise<VisitAutomationAttempt> {
  const soapSha256 = canonicalSoapSha256(input.soapFinal);
  const sourceSha256 = canonicalSha256({
    soapSha256,
    sourceFactsSha256: canonicalSha256(input.sourceFacts),
  });
  const context = getTemplateTwinSyntheticQaProviderContext();

  return runVisitAutomationTransaction({
    operation: "initialize_visit_automation_manifest",
    visitId: input.visitId,
    userId: input.userId,
    practiceId: input.practiceId,
    transaction: async (tx, visit) => {
      if (
        visit.status !== "AUTOMATING" ||
        visit.soapVersion !== input.soapVersion ||
        !visit.soapFinal ||
        canonicalSoapSha256(visit.soapFinal) !== soapSha256
      ) {
        throw new VisitAutomationManifestError(
          "VISIT_AUTOMATION_MANIFEST_STALE",
        );
      }
      const existing = await lockManifest(tx, input.visitId);
      const sameBinding = Boolean(
        existing &&
        existing.practiceId === input.practiceId &&
        existing.soapVersion === input.soapVersion &&
        existing.soapSha256 === soapSha256 &&
        existing.sourceSha256 === sourceSha256 &&
        existing.sourceVersion === VISIT_AUTOMATION_SOURCE_VERSION &&
        existing.policyVersion === VISIT_AUTOMATION_POLICY_VERSION &&
        (context
          ? existing.stagingAdmissionId === context.admissionId &&
            existing.stagingRunId === context.runId &&
            existing.pinnedGlobalRolloutGeneration ===
              context.pinnedGlobalGeneration &&
            existing.pinnedPracticeRolloutGeneration ===
              context.pinnedPracticeGeneration
          : existing.stagingAdmissionId === null &&
            existing.stagingRunId === null),
      );
      const restartCompletedProof = existing?.status === "COMPLETE";
      const reusableBinding = sameBinding && !restartCompletedProof;
      const nextManifestVersion = reusableBinding
        ? existing!.manifestVersion
        : (existing?.manifestVersion ?? 0) + 1;

      // A signed visit can never reach AUTOMATING, but an unsigned visit may
      // be deliberately reprocessed after a SOAP edit or a later-stage Twin
      // invalidation. A prior COMPLETE proof is therefore a checkpoint, not a
      // terminal lock: changed provenance creates the next manifest version;
      // unchanged provenance reuses successful layer hashes idempotently.

      let manifestId: string;
      if (!existing) {
        const created = await tx.visitAutomationManifest.create({
          data: {
            practiceId: input.practiceId,
            visitId: input.visitId,
            stagingAdmissionId: context?.admissionId ?? null,
            stagingRunId: context?.runId ?? null,
            soapVersion: input.soapVersion,
            soapSha256,
            sourceVersion: VISIT_AUTOMATION_SOURCE_VERSION,
            sourceSha256,
            policyVersion: VISIT_AUTOMATION_POLICY_VERSION,
            manifestVersion: nextManifestVersion,
            status: "RUNNING",
            attemptCount: 1,
            pinnedGlobalRolloutGeneration:
              context?.pinnedGlobalGeneration ?? null,
            pinnedPracticeRolloutGeneration:
              context?.pinnedPracticeGeneration ?? null,
            startedAt: new Date(),
          },
          select: { id: true },
        });
        manifestId = created.id;
      } else if (!reusableBinding) {
        await tx.visitAutomationLayer.deleteMany({
          where: { manifestId: existing.id },
        });
        const reset = await tx.visitAutomationManifest.update({
          where: { id: existing.id },
          data: {
            stagingAdmissionId: context?.admissionId ?? null,
            stagingRunId: context?.runId ?? null,
            soapVersion: input.soapVersion,
            soapSha256,
            sourceVersion: VISIT_AUTOMATION_SOURCE_VERSION,
            sourceSha256,
            policyVersion: VISIT_AUTOMATION_POLICY_VERSION,
            manifestVersion: nextManifestVersion,
            status: "RUNNING",
            attemptCount: { increment: 1 },
            pinnedGlobalRolloutGeneration:
              context?.pinnedGlobalGeneration ?? null,
            pinnedPracticeRolloutGeneration:
              context?.pinnedPracticeGeneration ?? null,
            startedAt: new Date(),
            completedAt: null,
          },
          select: { id: true },
        });
        manifestId = reset.id;
      } else {
        manifestId = existing.id;
        await tx.visitAutomationManifest.update({
          where: { id: manifestId },
          data: {
            status: "RUNNING",
            attemptCount: { increment: 1 },
            startedAt: new Date(),
            completedAt: null,
          },
        });
        const interrupted = await tx.visitAutomationLayer.findMany({
          where: { manifestId, status: "RUNNING" },
          select: { id: true },
        });
        for (const layer of interrupted) {
          await tx.visitAutomationLayer.update({
            where: { id: layer.id },
            data: {
              status: "FAILED",
              outputSha256: null,
              failureCode: "ATTEMPT_INTERRUPTED",
              completedAt: new Date(),
            },
          });
        }
      }

      const existingLayers = reusableBinding
        ? await tx.visitAutomationLayer.findMany({
            where: { manifestId },
            select: {
              layerId: true,
              layerVersion: true,
              requirement: true,
              inputSha256: true,
              idempotencyKey: true,
            },
          })
        : [];
      const existingById = new Map(
        existingLayers.map((layer) => [layer.layerId, layer]),
      );
      for (const layer of input.policy) {
        const inputSha256 = layerInputSha256({
          layer,
          soapSha256,
          sourceSha256,
        });
        const idempotencyKey = layerIdempotencyKey({
          visitId: input.visitId,
          manifestVersion: nextManifestVersion,
          layer,
          inputSha256,
        });
        const persisted = existingById.get(layer.layerId);
        if (persisted) {
          if (
            persisted.layerVersion !== layer.layerVersion ||
            persisted.requirement !== layer.requirement ||
            persisted.inputSha256 !== inputSha256 ||
            persisted.idempotencyKey !== idempotencyKey
          ) {
            throw new VisitAutomationManifestError(
              "VISIT_AUTOMATION_MANIFEST_STALE",
            );
          }
          continue;
        }
        await tx.visitAutomationLayer.create({
          data: {
            manifestId,
            practiceId: input.practiceId,
            visitId: input.visitId,
            layerId: layer.layerId,
            layerVersion: layer.layerVersion,
            requirement: layer.requirement,
            status: layer.initialStatus,
            inputSha256,
            idempotencyKey,
            completedAt:
              layer.initialStatus === "NOT_APPLICABLE" ? new Date() : null,
          },
        });
      }
      if (existingById.size > input.policy.length) {
        throw new VisitAutomationManifestError(
          "VISIT_AUTOMATION_MANIFEST_STALE",
        );
      }
      return {
        manifestId,
        manifestVersion: nextManifestVersion,
        soapVersion: input.soapVersion,
        soapSha256,
        sourceSha256,
        policy: input.policy,
      };
    },
  });
}

export async function markVisitAutomationLayerRunning(input: {
  attempt: VisitAutomationAttempt;
  visitId: string;
  userId: string;
  practiceId: string;
  layerId: VisitAutomationLayerId;
}): Promise<{ alreadySucceeded: boolean }> {
  return runVisitAutomationTransaction({
    operation: "mark_visit_automation_layer_running",
    visitId: input.visitId,
    userId: input.userId,
    practiceId: input.practiceId,
    transaction: async (tx, visit) => {
      const manifest = await lockManifest(tx, input.visitId);
      assertCurrentBinding({
        manifest,
        practiceId: input.practiceId,
        visitId: input.visitId,
        soapVersion: input.attempt.soapVersion,
        soapSha256: input.attempt.soapSha256,
      });
      if (!manifest) {
        throw new VisitAutomationManifestError(
          "VISIT_AUTOMATION_MANIFEST_STALE",
        );
      }
      if (
        visit.status !== "AUTOMATING" ||
        visit.soapVersion !== input.attempt.soapVersion
      ) {
        throw new VisitAutomationManifestError(
          "VISIT_AUTOMATION_MANIFEST_STALE",
        );
      }
      const layer = await lockLayer(tx, manifest.id, input.layerId);
      if (!layer) {
        throw new VisitAutomationManifestError(
          "VISIT_AUTOMATION_LAYER_NOT_FOUND",
        );
      }
      if (layer.status === "SUCCEEDED") return { alreadySucceeded: true };
      if (layer.status === "NOT_APPLICABLE") {
        throw new VisitAutomationManifestError(
          "VISIT_AUTOMATION_LAYER_STATE_INVALID",
        );
      }
      if (layer.status !== "RUNNING") {
        await tx.visitAutomationLayer.update({
          where: { id: layer.id },
          data: {
            status: "RUNNING",
            attemptCount: { increment: 1 },
            outputSha256: null,
            failureCode: null,
            startedAt: new Date(),
            completedAt: null,
          },
        });
      }
      return { alreadySucceeded: false };
    },
  });
}

export async function recordVisitAutomationLayerSuccess(input: {
  attempt: VisitAutomationAttempt;
  visitId: string;
  userId: string;
  practiceId: string;
  layerId: VisitAutomationLayerId;
  output: unknown;
}): Promise<void> {
  const outputSha256 = canonicalSha256(input.output);
  await runVisitAutomationTransaction({
    operation: "record_visit_automation_layer_success",
    visitId: input.visitId,
    userId: input.userId,
    practiceId: input.practiceId,
    transaction: async (tx) => {
      const manifest = await lockManifest(tx, input.visitId);
      assertCurrentBinding({
        manifest,
        practiceId: input.practiceId,
        visitId: input.visitId,
        soapVersion: input.attempt.soapVersion,
        soapSha256: input.attempt.soapSha256,
      });
      if (!manifest) {
        throw new VisitAutomationManifestError(
          "VISIT_AUTOMATION_MANIFEST_STALE",
        );
      }
      const layer = await lockLayer(tx, manifest.id, input.layerId);
      if (!layer) {
        throw new VisitAutomationManifestError(
          "VISIT_AUTOMATION_LAYER_NOT_FOUND",
        );
      }
      if (layer.status === "SUCCEEDED") {
        if (layer.outputSha256 !== outputSha256) {
          throw new VisitAutomationManifestError(
            "VISIT_AUTOMATION_LAYER_STATE_INVALID",
          );
        }
        return;
      }
      if (layer.status !== "RUNNING") {
        throw new VisitAutomationManifestError(
          "VISIT_AUTOMATION_LAYER_STATE_INVALID",
        );
      }
      await tx.visitAutomationLayer.update({
        where: { id: layer.id },
        data: {
          status: "SUCCEEDED",
          outputSha256,
          failureCode: null,
          completedAt: new Date(),
        },
      });
    },
  });
}

const OUTPUT_COLUMN_BY_LAYER: Partial<
  Record<VisitAutomationLayerId, keyof Prisma.TranscribeVisitUpdateInput>
> = {
  icd_coding: "icdCodes",
  cpt_coding: "cptCodes",
  rx_drafting: "rxDrafts",
  referrals: "referrals",
  patient_summary: "patientSummary",
};

export async function recordVisitAutomationLayerFailure(input: {
  attempt: VisitAutomationAttempt;
  visitId: string;
  userId: string;
  practiceId: string;
  layerId: VisitAutomationLayerId;
  error: unknown;
  failureCode?: VisitAutomationFailureCode | "ATTEMPT_INTERRUPTED";
}): Promise<void> {
  const failureCode =
    input.failureCode ?? classifyVisitAutomationFailure(input.error);
  await runVisitAutomationTransaction({
    operation: "record_visit_automation_layer_failure",
    visitId: input.visitId,
    userId: input.userId,
    practiceId: input.practiceId,
    transaction: async (tx) => {
      const manifest = await lockManifest(tx, input.visitId);
      assertCurrentBinding({
        manifest,
        practiceId: input.practiceId,
        visitId: input.visitId,
        soapVersion: input.attempt.soapVersion,
        soapSha256: input.attempt.soapSha256,
      });
      if (!manifest) {
        throw new VisitAutomationManifestError(
          "VISIT_AUTOMATION_MANIFEST_STALE",
        );
      }
      const layer = await lockLayer(tx, manifest.id, input.layerId);
      if (!layer) {
        throw new VisitAutomationManifestError(
          "VISIT_AUTOMATION_LAYER_NOT_FOUND",
        );
      }
      if (layer.status === "SUCCEEDED" || layer.status === "NOT_APPLICABLE") {
        throw new VisitAutomationManifestError(
          "VISIT_AUTOMATION_LAYER_STATE_INVALID",
        );
      }
      const outputColumn = OUTPUT_COLUMN_BY_LAYER[input.layerId];
      if (outputColumn) {
        await tx.transcribeVisit.update({
          where: { id: input.visitId },
          data: { [outputColumn]: null },
        });
      }
      await tx.visitAutomationLayer.update({
        where: { id: layer.id },
        data: {
          status: "FAILED",
          attemptCount:
            layer.status === "PENDING" ? { increment: 1 } : undefined,
          outputSha256: null,
          failureCode,
          startedAt: layer.status === "PENDING" ? new Date() : undefined,
          completedAt: new Date(),
        },
      });
    },
  });
}

export function persistedAutomationOutput(input: {
  layerId: VisitAutomationLayerId;
  resumeState: {
    icdCodes: unknown;
    cptCodes: unknown;
    rxDrafts: unknown;
    referrals: unknown;
    patientSummary: string | null;
  };
}): unknown {
  switch (input.layerId) {
    case "icd_coding":
      return input.resumeState.icdCodes;
    case "cpt_coding":
      return input.resumeState.cptCodes;
    case "rx_drafting":
      return input.resumeState.rxDrafts;
    case "referrals":
      return input.resumeState.referrals;
    case "patient_summary":
      return input.resumeState.patientSummary;
    case "em_mdm_prewarm":
      return { cacheWarm: true };
  }
}
