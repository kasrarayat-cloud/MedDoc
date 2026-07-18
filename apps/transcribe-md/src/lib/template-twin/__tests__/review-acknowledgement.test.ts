import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findVisit: vi.fn(),
  updateFill: vi.fn(),
  outboxCreate: vi.fn(),
  transaction: vi.fn(),
  pinRollout: vi.fn(),
  finalRollout: vi.fn(),
  assessAutomation: vi.fn(),
  lockAutomation: vi.fn(),
  lockActor: vi.fn(),
  lockVisit: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeVisit: { findFirst: mocks.findVisit },
    $transaction: mocks.transaction,
  },
}));
vi.mock("../rollout", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../rollout")>();
  return {
    ...actual,
    pinTemplateTwinRollout: mocks.pinRollout,
    lockTemplateTwinRolloutForFinalClaim: mocks.finalRollout,
    templateTwinRolloutAuditMetadata: () => ({
      pinnedGlobalGeneration: "1",
      pinnedPracticeGeneration: "1",
      currentGlobalGeneration: "1",
      currentPracticeGeneration: "1",
    }),
  };
});
vi.mock("../fill-engine", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../fill-engine")>()),
  lockCurrentTemplateTwinVisit: mocks.lockVisit,
}));
vi.mock("../staging-qa-visit-guard", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../staging-qa-visit-guard")>()),
  lockAndAssertTemplateTwinStagingQaActor: mocks.lockActor,
}));
vi.mock("@/worker/automation-finalization", async (importOriginal) => ({
  ...(await importOriginal<
    typeof import("@/worker/automation-finalization")
  >()),
  assessVisitAutomationProof: mocks.assessAutomation,
  lockAndAssertVisitAutomationProof: mocks.lockAutomation,
}));

import { canonicalSoapSha256 } from "../soap-binding";
import { prepareTemplateTwinFill } from "../fill-engine";
import { acknowledgeTemplateTwinReview } from "../review-acknowledgement";
import { VisitAutomationIncompleteError } from "@/worker/automation-finalization";
import {
  buildTemplateTwinIntegrationFixture,
  factsForMode,
} from "./integration-fixture";

const SOAP = "Synthetic SOAP reviewed for Template Twin.";
const ACTOR = {
  userId: "doctor-review-ack",
  userEmail: "doctor-review-ack@synthetic.test",
  practiceId: "practice-review-ack",
};
let manifest: Awaited<ReturnType<typeof prepareTemplateTwinFill>>["manifest"];
let manifestSha256: string;

beforeAll(async () => {
  const fixture = await buildTemplateTwinIntegrationFixture();
  const prepared = await prepareTemplateTwinFill({
    soapVersion: 4,
    soapFinal: SOAP,
    compiledVersionId: "compiled-review-ack",
    noteTemplateId: "template-review-ack",
    noteTemplateVersion: 2,
    ir: fixture.ir,
    mappings: fixture.mappings,
    facts: factsForMode("text"),
    certifiedFieldIds: fixture.ir.fields.map((field) => field.fieldId),
    source: fixture.source,
    resolverModelVersion: "synthetic-model",
    validationNow: "2026-07-15T12:00:00.000Z",
  });
  manifest = prepared.manifest;
  manifestSha256 = prepared.manifestSha256;
});

function visitRow(overrides: Record<string, unknown> = {}) {
  return {
    status: "READY",
    soapVersion: 4,
    soapFinal: SOAP,
    user: { practice: { templateTwinEnabled: true } },
    templateTwinFill: {
      id: "fill-review-ack",
      practiceId: ACTOR.practiceId,
      status: "VERIFIED",
      signedDecisionAt: null,
      manifestVersion: 3,
      manifestSha256,
      fillManifest: manifest,
      soapVersion: 4,
      soapSha256: canonicalSoapSha256(SOAP),
      needsReviewCount: 0,
      conflictCount: 0,
      criticalUnresolvedCount: 0,
      roundTripVerified: true,
      reviewedAt: null,
      reviewedById: null,
      reviewedManifestVersion: null,
      reviewedManifestSha256: null,
      pinnedGlobalRolloutGeneration: BigInt(1),
      pinnedPracticeRolloutGeneration: BigInt(1),
    },
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  process.env.TEMPLATE_TWIN_KILL_SWITCH = "false";
  mocks.findVisit.mockResolvedValue(visitRow());
  mocks.updateFill.mockResolvedValue({ count: 1 });
  mocks.outboxCreate.mockResolvedValue({ id: "outbox-review-ack" });
  mocks.pinRollout.mockResolvedValue({
    practiceId: ACTOR.practiceId,
    globalGeneration: BigInt(1),
    practiceGeneration: BigInt(1),
  });
  mocks.finalRollout.mockResolvedValue({
    allowed: true,
    token: {
      practiceId: ACTOR.practiceId,
      globalGeneration: BigInt(1),
      practiceGeneration: BigInt(1),
    },
  });
  mocks.assessAutomation.mockReturnValue({ ready: true, blockerCodes: [] });
  mocks.lockAutomation.mockResolvedValue({ id: "automation-proof-synthetic" });
  mocks.lockActor.mockResolvedValue(undefined);
  mocks.lockVisit.mockResolvedValue({
    id: "visit-review-ack",
    userId: ACTOR.userId,
    status: "READY",
    deletedAt: null,
    archivedAt: null,
    soapVersion: 4,
    soapFinal: SOAP,
  });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        templateTwinFillManifest: { updateMany: mocks.updateFill },
        templateTwinAuditOutbox: { create: mocks.outboxCreate },
      }),
  );
});

describe("whole-manifest Template Twin review acknowledgement", () => {
  it("blocks review before the transaction when automation proof is incomplete", async () => {
    mocks.assessAutomation.mockReturnValue({
      ready: false,
      blockerCodes: ["VISIT_AUTOMATION_REQUIRED_LAYER_INCOMPLETE"],
    });
    await expect(
      acknowledgeTemplateTwinReview({
        visitId: "visit-review-ack",
        expectedManifestVersion: 3,
        expectedManifestSha256: manifestSha256,
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({ code: "VISIT_AUTOMATION_INCOMPLETE" });
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("rolls review back when automation becomes incomplete after the precheck", async () => {
    mocks.lockAutomation.mockRejectedValue(
      new VisitAutomationIncompleteError([
        "VISIT_AUTOMATION_REQUIRED_LAYER_INCOMPLETE",
      ]),
    );

    await expect(
      acknowledgeTemplateTwinReview({
        visitId: "visit-review-ack",
        expectedManifestVersion: 3,
        expectedManifestSha256: manifestSha256,
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({ code: "VISIT_AUTOMATION_INCOMPLETE" });
    expect(mocks.updateFill).not.toHaveBeenCalled();
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
  });

  it("pins physician identity and the exact manifest version/hash transactionally", async () => {
    const now = new Date("2026-07-15T12:05:00.000Z");
    const result = await acknowledgeTemplateTwinReview({
      visitId: "visit-review-ack",
      expectedManifestVersion: 3,
      expectedManifestSha256: manifestSha256,
      actor: ACTOR,
      now,
    });

    expect(result).toEqual({
      fillManifestId: "fill-review-ack",
      manifestVersion: 3,
      reviewedAt: now.toISOString(),
    });
    expect(mocks.updateFill).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          manifestVersion: 3,
          manifestSha256,
          reviewedAt: null,
          needsReviewCount: 0,
          conflictCount: 0,
          soapVersion: 4,
          soapSha256: canonicalSoapSha256(SOAP),
          pinnedGlobalRolloutGeneration: BigInt(1),
          pinnedPracticeRolloutGeneration: BigInt(1),
          practice: {
            is: {
              id: ACTOR.practiceId,
              templateTwinEnabled: true,
            },
          },
        }),
        data: {
          reviewedAt: now,
          reviewedById: ACTOR.userId,
          reviewedManifestVersion: 3,
          reviewedManifestSha256: manifestSha256,
        },
      }),
    );
    expect(mocks.outboxCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          action: "TEMPLATE_TWIN_FIELD_REVIEWED",
          practiceId: ACTOR.practiceId,
        }),
      }),
    );
  });

  it("rejects a stale browser review of an older manifest version", async () => {
    await expect(
      acknowledgeTemplateTwinReview({
        visitId: "visit-review-ack",
        expectedManifestVersion: 2,
        expectedManifestSha256: manifestSha256,
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({
      code: "OPTIMISTIC_CONFLICT",
    });
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("rejects a stale browser hash even when the manifest version is unchanged", async () => {
    await expect(
      acknowledgeTemplateTwinReview({
        visitId: "visit-review-ack",
        expectedManifestVersion: 3,
        expectedManifestSha256: "f".repeat(64),
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({
      code: "OPTIMISTIC_CONFLICT",
    });
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("rejects acknowledgement after the SOAP binding becomes stale", async () => {
    mocks.findVisit.mockResolvedValue(
      visitRow({ soapVersion: 5, soapFinal: `${SOAP} Edited.` }),
    );
    await expect(
      acknowledgeTemplateTwinReview({
        visitId: "visit-review-ack",
        expectedManifestVersion: 3,
        expectedManifestSha256: manifestSha256,
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({
      code: "SOAP_BINDING_STALE",
    });
  });

  it("rejects direct acknowledgement while any routine field still needs attention", async () => {
    const row = visitRow();
    row.templateTwinFill.needsReviewCount = 1;
    mocks.findVisit.mockResolvedValue(row);
    await expect(
      acknowledgeTemplateTwinReview({
        visitId: "visit-review-ack",
        expectedManifestVersion: 3,
        expectedManifestSha256: manifestSha256,
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({ code: "NOT_READY" });
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("fails closed when regeneration wins the acknowledgement race", async () => {
    mocks.updateFill.mockResolvedValue({ count: 0 });
    await expect(
      acknowledgeTemplateTwinReview({
        visitId: "visit-review-ack",
        expectedManifestVersion: 3,
        expectedManifestSha256: manifestSha256,
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({
      code: "OPTIMISTIC_CONFLICT",
    });
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
  });

  it("reports a stale global generation distinctly before review", async () => {
    mocks.pinRollout.mockResolvedValue({
      practiceId: ACTOR.practiceId,
      globalGeneration: BigInt(2),
      practiceGeneration: BigInt(1),
    });

    await expect(
      acknowledgeTemplateTwinReview({
        visitId: "visit-review-ack",
        expectedManifestVersion: 3,
        expectedManifestSha256: manifestSha256,
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_GLOBAL_GENERATION_STALE",
    });
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("reports a stale practice generation distinctly before review", async () => {
    mocks.pinRollout.mockResolvedValue({
      practiceId: ACTOR.practiceId,
      globalGeneration: BigInt(1),
      practiceGeneration: BigInt(2),
    });

    await expect(
      acknowledgeTemplateTwinReview({
        visitId: "visit-review-ack",
        expectedManifestVersion: 3,
        expectedManifestSha256: manifestSha256,
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_PRACTICE_GENERATION_STALE",
    });
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("does not authorize review when rollout is revoked before the final claim", async () => {
    mocks.finalRollout.mockResolvedValue({
      allowed: false,
      code: "TEMPLATE_TWIN_GLOBAL_DISABLED",
      reason: "Template Twin is temporarily unavailable.",
      currentToken: {
        practiceId: ACTOR.practiceId,
        globalGeneration: BigInt(2),
        practiceGeneration: BigInt(1),
      },
    });

    await expect(
      acknowledgeTemplateTwinReview({
        visitId: "visit-review-ack",
        expectedManifestVersion: 3,
        expectedManifestSha256: manifestSha256,
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({ code: "TEMPLATE_TWIN_GLOBAL_DISABLED" });
    expect(mocks.updateFill).not.toHaveBeenCalled();
    expect(mocks.outboxCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
          metadata: expect.objectContaining({
            operation: "whole_manifest_review_final_claim",
          }),
        }),
      }),
    );
  });
});
