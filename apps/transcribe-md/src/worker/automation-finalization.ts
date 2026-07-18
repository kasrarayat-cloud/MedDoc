import { getTemplateTwinSyntheticQaProviderContext } from "@meddoc/ai";
import { Prisma, TranscribeVisitStatus } from "@prisma/client";

import { enqueueTemplateTwinAudit } from "@/lib/template-twin/audit-outbox";
import { canonicalSoapSha256 } from "@/lib/template-twin/soap-binding";
import {
  type VisitAutomationAttempt,
  type VisitAutomationManifestProof,
  VISIT_AUTOMATION_MANIFEST_SELECT,
  VISIT_AUTOMATION_PROOF_VERSION,
} from "@/worker/automation-manifest";
import { runVisitAutomationTransaction } from "@/worker/automation-locks";
import {
  automationIncompleteReviewReason,
  VISIT_AUTOMATION_LAYER_IDS,
  VISIT_AUTOMATION_LAYER_VERSION,
  VISIT_AUTOMATION_POLICY_VERSION,
  VISIT_AUTOMATION_SOURCE_VERSION,
} from "@/worker/automation-policy";

interface LockedLayerProof {
  layerId: string;
  layerVersion: string;
  requirement: string;
  status: string;
  failureCode: string | null;
  inputSha256: string;
  outputSha256: string | null;
}

export type VisitAutomationProofCode =
  | "VISIT_AUTOMATION_PROOF_MISSING"
  | "VISIT_AUTOMATION_PROOF_STALE"
  | "VISIT_AUTOMATION_REQUIRED_LAYER_INCOMPLETE"
  | "VISIT_AUTOMATION_LAYER_RESULT_PENDING";

export class VisitAutomationIncompleteError extends Error {
  readonly code = "VISIT_AUTOMATION_INCOMPLETE" as const;

  constructor(readonly blockerCodes: readonly VisitAutomationProofCode[]) {
    super("Required visit automation is incomplete. Retry processing.");
    this.name = "VisitAutomationIncompleteError";
  }
}

function exactLayerInventory(
  layers: ReadonlyArray<{
    layerId: string;
    layerVersion: string;
    inputSha256: string;
    requirement?: string;
  }>,
  expectedPolicy?: VisitAutomationAttempt["policy"],
): boolean {
  return (
    layers.length === VISIT_AUTOMATION_LAYER_IDS.length &&
    VISIT_AUTOMATION_LAYER_IDS.every((layerId) => {
      const matches = layers.filter((layer) => layer.layerId === layerId);
      return (
        matches.length === 1 &&
        matches[0]?.layerVersion === VISIT_AUTOMATION_LAYER_VERSION[layerId] &&
        /^[a-f0-9]{64}$/u.test(matches[0]?.inputSha256 ?? "") &&
        (!expectedPolicy ||
          matches[0]?.requirement ===
            expectedPolicy.find((entry) => entry.layerId === layerId)
              ?.requirement)
      );
    })
  );
}

function proofBlockers(input: {
  visitId: string;
  practiceId: string;
  soapVersion: number;
  soapFinal: string | null;
  manifest: VisitAutomationManifestProof | null | undefined;
  staging?: {
    admissionId: string;
    runId: string;
    globalGeneration: bigint;
    practiceGeneration: bigint;
  } | null;
}): VisitAutomationProofCode[] {
  const manifest = input.manifest;
  if (!manifest) return ["VISIT_AUTOMATION_PROOF_MISSING"];
  const soapSha256 = input.soapFinal
    ? canonicalSoapSha256(input.soapFinal)
    : null;
  const stagingMismatch = input.staging
    ? manifest.stagingAdmissionId !== input.staging.admissionId ||
      manifest.stagingRunId !== input.staging.runId ||
      manifest.pinnedGlobalRolloutGeneration !==
        input.staging.globalGeneration ||
      manifest.pinnedPracticeRolloutGeneration !==
        input.staging.practiceGeneration
    : manifest.stagingAdmissionId !== null || manifest.stagingRunId !== null;
  if (
    manifest.visitId !== input.visitId ||
    manifest.practiceId !== input.practiceId ||
    manifest.policyVersion !== VISIT_AUTOMATION_POLICY_VERSION ||
    manifest.sourceVersion !== VISIT_AUTOMATION_SOURCE_VERSION ||
    manifest.soapVersion !== input.soapVersion ||
    manifest.soapSha256 !== soapSha256 ||
    !/^[a-f0-9]{64}$/u.test(manifest.sourceSha256) ||
    stagingMismatch ||
    !exactLayerInventory(manifest.layers)
  ) {
    return ["VISIT_AUTOMATION_PROOF_STALE"];
  }
  const blockers: VisitAutomationProofCode[] = [];
  if (
    manifest.layers.some(
      (layer) => layer.status === "PENDING" || layer.status === "RUNNING",
    )
  ) {
    blockers.push("VISIT_AUTOMATION_LAYER_RESULT_PENDING");
  }
  if (
    manifest.layers.some(
      (layer) =>
        layer.requirement === "REQUIRED" && layer.status !== "SUCCEEDED",
    )
  ) {
    blockers.push("VISIT_AUTOMATION_REQUIRED_LAYER_INCOMPLETE");
  }
  if (manifest.status !== "COMPLETE" || manifest.completedAt === null) {
    blockers.push("VISIT_AUTOMATION_REQUIRED_LAYER_INCOMPLETE");
  }
  return [...new Set(blockers)];
}

export function assessVisitAutomationProof(input: {
  visitId: string;
  practiceId: string;
  soapVersion: number;
  soapFinal: string | null;
  manifest: VisitAutomationManifestProof | null | undefined;
  staging?: {
    admissionId: string;
    runId: string;
    globalGeneration: bigint;
    practiceGeneration: bigint;
  } | null;
}): { ready: boolean; blockerCodes: VisitAutomationProofCode[] } {
  const blockerCodes = proofBlockers(input);
  return { ready: blockerCodes.length === 0, blockerCodes };
}

export async function loadVisitAutomationProof(input: {
  visitId: string;
  practiceId: string;
  soapVersion: number;
  soapFinal: string | null;
}): Promise<{ ready: boolean; blockerCodes: VisitAutomationProofCode[] }> {
  const { default: prisma } = await import("@meddoc/db");
  const manifest = await prisma.visitAutomationManifest.findUnique({
    where: { visitId: input.visitId },
    select: VISIT_AUTOMATION_MANIFEST_SELECT,
  });
  return assessVisitAutomationProof({ ...input, manifest });
}

/** Lock and independently re-evaluate the proof inside sign/export claims. */
export async function lockAndAssertVisitAutomationProof(input: {
  tx: Prisma.TransactionClient;
  visitId: string;
  practiceId: string;
  soapVersion: number;
  soapFinal: string | null;
  staging?: {
    admissionId: string;
    runId: string;
    globalGeneration: bigint;
    practiceGeneration: bigint;
  } | null;
}): Promise<VisitAutomationManifestProof> {
  await input.tx.$queryRaw(Prisma.sql`
    SELECT "id"
    FROM "visit_automation_manifests"
    WHERE "visitId" = ${input.visitId}
    FOR UPDATE
  `);
  await input.tx.$queryRaw(Prisma.sql`
    SELECT "id"
    FROM "visit_automation_layers"
    WHERE "visitId" = ${input.visitId}
    ORDER BY "layerId"
    FOR UPDATE
  `);
  const manifest = await input.tx.visitAutomationManifest.findUnique({
    where: { visitId: input.visitId },
    select: VISIT_AUTOMATION_MANIFEST_SELECT,
  });
  const assessment = assessVisitAutomationProof({ ...input, manifest });
  if (!assessment.ready || !manifest) {
    throw new VisitAutomationIncompleteError(assessment.blockerCodes);
  }
  return manifest as VisitAutomationManifestProof;
}

function appendReviewReason(
  current: string | null | undefined,
  failedLayerIds: readonly string[],
): string {
  const addition = automationIncompleteReviewReason(failedLayerIds);
  if (!current) return addition;
  if (current.includes(addition)) return current;
  return `${current} ${addition}`;
}

/**
 * The sole AUTOMATING -> READY transition. It locks and checks every durable
 * layer result, publishes COMPLETE plus its audit outbox row atomically, and
 * only then advances the visit. Promise resolution is never completion proof.
 */
export async function finalizeVisitAutomationReady(input: {
  attempt: VisitAutomationAttempt;
  visitId: string;
  userId: string;
  practiceId: string;
  processingFinishedAt: Date;
  processingCostCents: number;
  confidenceScores: Prisma.InputJsonValue | null;
}): Promise<void> {
  const context = getTemplateTwinSyntheticQaProviderContext();
  const result = await runVisitAutomationTransaction({
    operation: "finalize_visit_automation_ready",
    visitId: input.visitId,
    userId: input.userId,
    practiceId: input.practiceId,
    transaction: async (tx, visit) => {
      const manifests = await tx.$queryRaw<
        Array<{
          id: string;
          status: string;
          manifestVersion: number;
          soapVersion: number;
          soapSha256: string;
          sourceVersion: string;
          sourceSha256: string;
          policyVersion: string;
          stagingAdmissionId: string | null;
          stagingRunId: string | null;
          pinnedGlobalRolloutGeneration: bigint | null;
          pinnedPracticeRolloutGeneration: bigint | null;
          attemptCount: number;
        }>
      >(Prisma.sql`
        SELECT
          "id", "status", "manifestVersion", "soapVersion", "soapSha256",
          "sourceVersion", "sourceSha256", "policyVersion",
          "stagingAdmissionId", "stagingRunId",
          "pinnedGlobalRolloutGeneration", "pinnedPracticeRolloutGeneration",
          "attemptCount"
        FROM "visit_automation_manifests"
        WHERE "visitId" = ${input.visitId}
        FOR UPDATE
      `);
      const manifest = manifests[0];
      const layers = manifest
        ? await tx.$queryRaw<LockedLayerProof[]>(Prisma.sql`
            SELECT
              "layerId", "layerVersion",
              "requirement"::text AS "requirement",
              "status"::text AS "status", "failureCode",
              "inputSha256", "outputSha256"
            FROM "visit_automation_layers"
            WHERE "manifestId" = ${manifest.id}
            ORDER BY "layerId"
            FOR UPDATE
          `)
        : [];
      const bindingStale = Boolean(
        !manifest ||
        manifest.id !== input.attempt.manifestId ||
        manifest.manifestVersion !== input.attempt.manifestVersion ||
        manifest.soapVersion !== input.attempt.soapVersion ||
        manifest.soapSha256 !== input.attempt.soapSha256 ||
        manifest.sourceVersion !== VISIT_AUTOMATION_SOURCE_VERSION ||
        manifest.sourceSha256 !== input.attempt.sourceSha256 ||
        manifest.policyVersion !== VISIT_AUTOMATION_POLICY_VERSION ||
        visit.soapVersion !== input.attempt.soapVersion ||
        !visit.soapFinal ||
        canonicalSoapSha256(visit.soapFinal) !== input.attempt.soapSha256 ||
        (context
          ? manifest.stagingAdmissionId !== context.admissionId ||
            manifest.stagingRunId !== context.runId ||
            manifest.pinnedGlobalRolloutGeneration !==
              context.pinnedGlobalGeneration ||
            manifest.pinnedPracticeRolloutGeneration !==
              context.pinnedPracticeGeneration
          : manifest.stagingAdmissionId !== null ||
            manifest.stagingRunId !== null),
      );
      const inventoryInvalid = !exactLayerInventory(
        layers,
        input.attempt.policy,
      );
      const nonTerminal = layers.filter(
        (layer) => layer.status === "PENDING" || layer.status === "RUNNING",
      );
      const failedRequired = layers.filter(
        (layer) =>
          layer.requirement === "REQUIRED" && layer.status !== "SUCCEEDED",
      );
      const blockerCodes: VisitAutomationProofCode[] = [];
      if (bindingStale || inventoryInvalid) {
        blockerCodes.push("VISIT_AUTOMATION_PROOF_STALE");
      }
      if (nonTerminal.length > 0) {
        blockerCodes.push("VISIT_AUTOMATION_LAYER_RESULT_PENDING");
      }
      if (failedRequired.length > 0) {
        blockerCodes.push("VISIT_AUTOMATION_REQUIRED_LAYER_INCOMPLETE");
      }

      let fill: {
        id: string;
        status: string;
        signedDecisionAt: Date | null;
        manifestVersion: number;
        pinnedGlobalRolloutGeneration: bigint | null;
        pinnedPracticeRolloutGeneration: bigint | null;
      } | null = null;
      if (context && manifest) {
        fill = await tx.templateTwinFillManifest.findUnique({
          where: { visitId: input.visitId },
          select: {
            id: true,
            status: true,
            signedDecisionAt: true,
            manifestVersion: true,
            pinnedGlobalRolloutGeneration: true,
            pinnedPracticeRolloutGeneration: true,
          },
        });
        if (
          !fill ||
          (fill.status !== "VERIFIED" && fill.status !== "NEEDS_REVIEW") ||
          fill.signedDecisionAt !== null ||
          fill.pinnedGlobalRolloutGeneration !==
            context.pinnedGlobalGeneration ||
          fill.pinnedPracticeRolloutGeneration !==
            context.pinnedPracticeGeneration
        ) {
          blockerCodes.push("VISIT_AUTOMATION_PROOF_STALE");
        }
      }

      if (blockerCodes.length > 0 || !manifest) {
        if (manifest) {
          const failedLayerIds = [
            ...new Set(
              [...failedRequired, ...nonTerminal].map((layer) => layer.layerId),
            ),
          ];
          await tx.visitAutomationManifest.update({
            where: { id: manifest.id },
            data: {
              status: "INCOMPLETE",
              completedAt: input.processingFinishedAt,
            },
          });
          await tx.transcribeVisit.update({
            where: { id: input.visitId },
            data: {
              needsReview: true,
              reviewReason: appendReviewReason(
                visit.reviewReason,
                failedLayerIds,
              ),
              confidenceScores:
                input.confidenceScores === null
                  ? Prisma.JsonNull
                  : input.confidenceScores,
              processingFinishedAt: input.processingFinishedAt,
              processingCostCents: input.processingCostCents,
            },
          });
          await enqueueTemplateTwinAudit(tx, {
            eventKey:
              `visit-automation:incomplete:${input.visitId}:` +
              `${manifest.manifestVersion}:${manifest.attemptCount}`,
            practiceId: input.practiceId,
            actorId: input.userId,
            action: "VISIT_AUTOMATION_INCOMPLETE",
            targetType: "TranscribeVisit",
            targetId: input.visitId,
            metadata: {
              proofVersion: VISIT_AUTOMATION_PROOF_VERSION,
              manifestId: manifest.id,
              manifestVersion: manifest.manifestVersion,
              failedLayers: failedLayerIds,
              blockerCodes: [...new Set(blockerCodes)],
            },
          });
        }
        return {
          complete: false as const,
          blockerCodes: [...new Set(blockerCodes)],
        };
      }

      if (
        manifest.status === "COMPLETE" &&
        visit.status === TranscribeVisitStatus.READY
      ) {
        return { complete: true as const };
      }

      await tx.visitAutomationManifest.update({
        where: { id: manifest.id },
        data: { status: "COMPLETE", completedAt: input.processingFinishedAt },
      });
      const visitUpdated = await tx.transcribeVisit.updateMany({
        where: {
          id: input.visitId,
          userId: input.userId,
          status: TranscribeVisitStatus.AUTOMATING,
          soapVersion: input.attempt.soapVersion,
          deletedAt: null,
          archivedAt: null,
        },
        data: {
          status: TranscribeVisitStatus.READY,
          processingFinishedAt: input.processingFinishedAt,
          processingCostCents: input.processingCostCents,
          confidenceScores:
            input.confidenceScores === null
              ? Prisma.JsonNull
              : input.confidenceScores,
        },
      });
      if (visitUpdated.count !== 1) {
        throw new VisitAutomationIncompleteError([
          "VISIT_AUTOMATION_PROOF_STALE",
        ]);
      }
      if (context) {
        const completed = await tx.templateTwinSyntheticQaRun.updateMany({
          where: {
            id: context.runId,
            visitId: input.visitId,
            doctorId: input.userId,
            practiceId: input.practiceId,
            attempt: context.attempt,
            status: "PROCESSING",
            workerClaimId: context.workerClaimId,
          },
          data: { status: "COMPLETED" },
        });
        const readyAdmission =
          await tx.templateTwinSyntheticQaAdmission.updateMany({
            where: {
              id: context.admissionId,
              practiceId: input.practiceId,
              actorId: input.userId,
              visitId: input.visitId,
              attempt: context.attempt,
              phase: "PROCESSING",
            },
            data: { phase: "REVIEW_READY" },
          });
        if (completed.count !== 1 || readyAdmission.count !== 1 || !fill) {
          throw new VisitAutomationIncompleteError([
            "VISIT_AUTOMATION_PROOF_STALE",
          ]);
        }
        await enqueueTemplateTwinAudit(tx, {
          eventKey: `template-twin:staging-ready:${context.runId}:${context.attempt}:${fill.manifestVersion}`,
          practiceId: input.practiceId,
          actorId: input.userId,
          action: "TEMPLATE_TWIN_RENDER_VERIFIED",
          targetType: "TranscribeVisit",
          targetId: input.visitId,
          metadata: {
            operation: "staging_visit_ready_final_claim",
            stagingQaRunId: context.runId,
            stagingQaAttempt: context.attempt,
            fillManifestId: fill.id,
            manifestVersion: fill.manifestVersion,
            fillStatus: fill.status,
          },
        });
      }
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `visit-automation:completed:${input.visitId}:${manifest.manifestVersion}`,
        practiceId: input.practiceId,
        actorId: input.userId,
        action: "VISIT_AUTOMATION_COMPLETED",
        targetType: "TranscribeVisit",
        targetId: input.visitId,
        metadata: {
          proofVersion: VISIT_AUTOMATION_PROOF_VERSION,
          manifestId: manifest.id,
          manifestVersion: manifest.manifestVersion,
          requiredLayerCount: layers.filter(
            (layer) => layer.requirement === "REQUIRED",
          ).length,
          optionalFailureCount: layers.filter(
            (layer) =>
              layer.requirement === "OPTIONAL" && layer.status === "FAILED",
          ).length,
        },
      });
      return { complete: true as const };
    },
  });
  if (!result.complete) {
    throw new VisitAutomationIncompleteError(result.blockerCodes);
  }
}
