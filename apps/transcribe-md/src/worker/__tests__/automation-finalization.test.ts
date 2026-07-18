import { describe, expect, it } from "vitest";

import { assessVisitAutomationProof } from "../automation-finalization";
import {
  buildVisitAutomationPolicy,
  VISIT_AUTOMATION_LAYER_IDS,
  VISIT_AUTOMATION_LAYER_VERSION,
  VISIT_AUTOMATION_POLICY_VERSION,
  VISIT_AUTOMATION_SOURCE_VERSION,
} from "../automation-policy";
import { canonicalSoapSha256 } from "@/lib/template-twin/soap-binding";
import type { VisitAutomationManifestProof } from "../automation-manifest";

const SOAP = "Synthetic assessment and plan for transaction QA.";

function proof(
  overrides: Partial<VisitAutomationManifestProof> = {},
): VisitAutomationManifestProof {
  return {
    id: "manifest-synthetic-1",
    practiceId: "practice-synthetic-1",
    visitId: "visit-synthetic-1",
    stagingAdmissionId: null,
    stagingRunId: null,
    soapVersion: 4,
    soapSha256: canonicalSoapSha256(SOAP),
    sourceVersion: VISIT_AUTOMATION_SOURCE_VERSION,
    sourceSha256: "a".repeat(64),
    policyVersion: VISIT_AUTOMATION_POLICY_VERSION,
    manifestVersion: 2,
    status: "COMPLETE",
    attemptCount: 1,
    pinnedGlobalRolloutGeneration: null,
    pinnedPracticeRolloutGeneration: null,
    completedAt: new Date("2026-07-17T23:00:00.000Z"),
    layers: VISIT_AUTOMATION_LAYER_IDS.map((layerId) => ({
      layerId,
      layerVersion: VISIT_AUTOMATION_LAYER_VERSION[layerId],
      requirement: "OPTIONAL",
      status: "SUCCEEDED",
      attemptCount: 1,
      inputSha256: "b".repeat(64),
      outputSha256: "c".repeat(64),
      failureCode: null,
      idempotencyKey: "d".repeat(64),
      startedAt: new Date("2026-07-17T22:59:00.000Z"),
      completedAt: new Date("2026-07-17T23:00:00.000Z"),
    })),
    ...overrides,
  };
}

function assess(manifest: VisitAutomationManifestProof | null) {
  return assessVisitAutomationProof({
    visitId: "visit-synthetic-1",
    practiceId: "practice-synthetic-1",
    soapVersion: 4,
    soapFinal: SOAP,
    manifest,
    staging: null,
  });
}

describe("visit automation completion proof", () => {
  it("accepts an exact terminal inventory with optional failures", () => {
    const manifest = proof();
    manifest.layers.find((layer) => layer.layerId === "referrals")!.status =
      "FAILED";
    manifest.layers.find(
      (layer) => layer.layerId === "referrals",
    )!.outputSha256 = null;
    manifest.layers.find(
      (layer) => layer.layerId === "referrals",
    )!.failureCode = "PROVIDER_FAILURE";

    expect(assess(manifest)).toEqual({ ready: true, blockerCodes: [] });
  });

  it.each(["PENDING", "RUNNING", "FAILED"] as const)(
    "blocks required layer status %s",
    (status) => {
      const manifest = proof();
      const layer = manifest.layers.find(
        (entry) => entry.layerId === "icd_coding",
      )!;
      layer.requirement = "REQUIRED";
      layer.status = status;
      layer.outputSha256 = null;
      manifest.status = "INCOMPLETE";

      expect(assess(manifest).ready).toBe(false);
    },
  );

  it("blocks missing, duplicated, version-shifted, and stale SOAP proof", () => {
    expect(assess(null).blockerCodes).toContain(
      "VISIT_AUTOMATION_PROOF_MISSING",
    );
    const missing = proof();
    missing.layers.pop();
    expect(assess(missing).blockerCodes).toContain(
      "VISIT_AUTOMATION_PROOF_STALE",
    );
    const duplicate = proof();
    duplicate.layers[5] = { ...duplicate.layers[0] };
    expect(assess(duplicate).ready).toBe(false);
    const wrongVersion = proof();
    wrongVersion.layers[0]!.layerVersion = "unexpected-version";
    expect(assess(wrongVersion).ready).toBe(false);
    expect(
      assessVisitAutomationProof({
        visitId: "visit-synthetic-1",
        practiceId: "practice-synthetic-1",
        soapVersion: 5,
        soapFinal: `${SOAP} Edited.`,
        manifest: proof(),
        staging: null,
      }).ready,
    ).toBe(false);
  });

  it("makes disabled layers explicit NOT_APPLICABLE", () => {
    const policy = buildVisitAutomationPolicy({
      staging: false,
      enabled: Object.fromEntries(
        VISIT_AUTOMATION_LAYER_IDS.map((id) => [id, id !== "cpt_coding"]),
      ) as Record<(typeof VISIT_AUTOMATION_LAYER_IDS)[number], boolean>,
    });
    expect(
      policy.find((entry) => entry.layerId === "cpt_coding"),
    ).toMatchObject({
      requirement: "NOT_APPLICABLE",
      initialStatus: "NOT_APPLICABLE",
    });
  });

  it("requires all enabled L7 layers in staging but preserves ordinary layers as optional", () => {
    const enabled = Object.fromEntries(
      VISIT_AUTOMATION_LAYER_IDS.map((id) => [id, id !== "em_mdm_prewarm"]),
    ) as Record<(typeof VISIT_AUTOMATION_LAYER_IDS)[number], boolean>;
    const staging = buildVisitAutomationPolicy({ staging: true, enabled });
    expect(
      staging
        .filter((entry) => entry.initialStatus !== "NOT_APPLICABLE")
        .every((entry) => entry.requirement === "REQUIRED"),
    ).toBe(true);
    const ordinary = buildVisitAutomationPolicy({ staging: false, enabled });
    expect(
      ordinary
        .filter((entry) => entry.initialStatus !== "NOT_APPLICABLE")
        .every((entry) => entry.requirement === "OPTIONAL"),
    ).toBe(true);
  });
});
