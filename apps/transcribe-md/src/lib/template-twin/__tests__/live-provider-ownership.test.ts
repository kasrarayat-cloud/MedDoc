import { describe, expect, it } from "vitest";

import { canonicalSha256 } from "../canonical";
import { isTemplateTwinVisitProviderReceiptOwned } from "../live-provider-ownership";
import { visitProviderOwnershipFixture } from "./provider-ownership-fixture";

const IDENTITY = {
  practiceId: "practice-visit-receipt",
  actorUserId: "doctor-visit-receipt",
  visitId: "visit-receipt",
  visitInputMode: "text_notes" as const,
  sourceArtifactId: "source-visit-receipt",
  sourceSha256: "a".repeat(64),
  compiledVersionId: "compiled-visit-receipt",
  noteTemplateId: "template-visit-receipt",
  noteTemplateVersion: 1,
  sourceLineageId: "lineage-visit-receipt",
  sourceLineageVersion: 1,
  logicalAttempt: 1,
};

function valid(mode: "audio_upload" | "voice_dictation" | "text_notes") {
  const identity = { ...IDENTITY, visitInputMode: mode };
  const receipt = visitProviderOwnershipFixture(identity);
  return {
    identity,
    receipt,
    input: {
      ...identity,
      evidence: receipt.evidence,
      evidenceSha256: receipt.sha256,
      providerMode: "LIVE" as const,
      syntheticAdmissionId: null,
      pinnedGlobalRolloutGeneration: BigInt(1),
      pinnedPracticeRolloutGeneration: BigInt(1),
    },
  };
}

describe("strict Template Twin visit provider receipt", () => {
  it.each(["audio_upload", "voice_dictation", "text_notes"] as const)(
    "accepts the exact %s execution plan",
    (mode) => {
      expect(isTemplateTwinVisitProviderReceiptOwned(valid(mode).input)).toBe(
        true,
      );
    },
  );

  it.each([
    ["actorUserId", "different-doctor"],
    ["visitInputMode", "voice_dictation"],
    ["logicalAttempt", 2],
    ["sourceLineageVersion", 2],
    ["noteTemplateVersion", 2],
    ["pinnedGlobalRolloutGeneration", BigInt(2)],
  ] as const)("rejects stale or cross-bound %s", (field, value) => {
    const fixture = valid("text_notes");
    expect(
      isTemplateTwinVisitProviderReceiptOwned({
        ...fixture.input,
        [field]: value,
      }),
    ).toBe(false);
  });

  it.each([
    "missing-plan-entry",
    "duplicate-plan-entry",
    "wrong-mode-reason",
    "wrong-anchor-instance",
    "omitted-execution",
    "extra-execution",
    "forged-plan-hash",
  ] as const)("rejects %s even with a recomputed outer receipt hash", (kind) => {
    const fixture = valid("text_notes");
    const evidence = structuredClone(fixture.receipt.evidence) as {
      executionPlanSha256: string;
      executionPlan: Array<{
        operation: string;
        operationInstance: string;
        disposition: string;
        reasonCode: string | null;
      }>;
      executions: Array<{
        executionId: string;
        operation: string;
        operationInstance: string;
        resultSha256: string;
      }>;
    } & Record<string, unknown>;
    if (kind === "missing-plan-entry") evidence.executionPlan.pop();
    if (kind === "duplicate-plan-entry") {
      evidence.executionPlan[1] = { ...evidence.executionPlan[0]! };
    }
    if (kind === "wrong-mode-reason") {
      const entry = evidence.executionPlan.find(
        (candidate) => candidate.operation === "L1_TRANSCRIBE",
      )!;
      entry.reasonCode = "INPUT_MODE_DICTATION";
    }
    if (kind === "wrong-anchor-instance") {
      const entry = evidence.executionPlan.find(
        (candidate) => candidate.operation === "L4_ANCHOR_VERIFY",
      )!;
      entry.operationInstance = "primary";
    }
    if (kind === "omitted-execution") evidence.executions.pop();
    if (kind === "extra-execution") {
      evidence.executions.push({
        executionId: "unexpected-execution",
        operation: "L6_POLISH",
        operationInstance: "primary",
        resultSha256: "f".repeat(64),
      });
    }
    evidence.executionPlanSha256 =
      kind === "forged-plan-hash"
        ? "f".repeat(64)
        : canonicalSha256({
            contractVersion: "template-twin-provider-execution-plan-v1",
            scope: "VISIT_PIPELINE",
            entries: evidence.executionPlan,
          });
    expect(
      isTemplateTwinVisitProviderReceiptOwned({
        ...fixture.input,
        evidence,
        evidenceSha256: canonicalSha256(evidence),
      }),
    ).toBe(false);
  });
});
