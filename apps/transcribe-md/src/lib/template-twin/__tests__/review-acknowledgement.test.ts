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
  lockCurrentPhysician: vi.fn(),
  findCurrentVisit: vi.fn(),
  findCurrentFill: vi.fn(),
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
  SYNTHETIC_CONTEXT,
} from "./integration-fixture";
import { createTemplateTwinEncounterSourceReceipt } from "../canonical-encounter-source";
import {
  sourceProviderOwnershipFixture,
  visitProviderOwnershipFixture,
} from "./provider-ownership-fixture";

const SOAP = "Synthetic SOAP reviewed for Template Twin.";
const ACTOR = {
  userId: "doctor-review-ack",
  userEmail: "doctor-review-ack@synthetic.test",
  practiceId: "practice-review-ack",
};
let manifest: Awaited<ReturnType<typeof prepareTemplateTwinFill>>["manifest"];
let manifestSha256: string;
let sourceOwnership: ReturnType<typeof sourceProviderOwnershipFixture>;
let visitOwnership: ReturnType<typeof visitProviderOwnershipFixture>;
let sourceSha256: string;

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
    encounterSourceReceipt: createTemplateTwinEncounterSourceReceipt({
      mode: "text",
      contextText: SYNTHETIC_CONTEXT,
    }),
    certifiedFieldIds: fixture.ir.fields.map((field) => field.fieldId),
    source: fixture.source,
    resolverModelVersion: "synthetic-model",
    validationNow: "2026-07-15T12:00:00.000Z",
  });
  manifest = prepared.manifest;
  manifestSha256 = prepared.manifestSha256;
  sourceSha256 = fixture.ir.source.sha256;
  sourceOwnership = sourceProviderOwnershipFixture({
    practiceId: ACTOR.practiceId,
    actorUserId: ACTOR.userId,
    sourceArtifactId: "source-review-ack",
    sourceSha256,
    compiledVersionId: "compiled-review-ack",
    noteTemplateId: "template-review-ack",
    noteTemplateVersion: 2,
    sourceLineageId: "lineage-review-ack",
    sourceLineageVersion: 1,
  });
  visitOwnership = visitProviderOwnershipFixture({
    practiceId: ACTOR.practiceId,
    actorUserId: ACTOR.userId,
    visitId: "visit-review-ack",
    visitInputMode: "text_notes",
    sourceArtifactId: "source-review-ack",
    sourceSha256,
    compiledVersionId: "compiled-review-ack",
    noteTemplateId: "template-review-ack",
    noteTemplateVersion: 2,
    sourceLineageId: "lineage-review-ack",
    sourceLineageVersion: 1,
    logicalAttempt: 1,
  });
});

function visitRow(overrides: Record<string, unknown> = {}) {
  return {
    status: "READY",
    soapVersion: 4,
    manualRetryCount: 0,
    soapFinal: SOAP,
    inputMode: "text_notes",
    rawTextInput: SYNTHETIC_CONTEXT,
    transcriptText: null,
    transcriptRaw: null,
    speakerMap: null,
    noteTemplateId: "template-review-ack",
    noteTemplateVersion: 2,
    noteTemplate: {
      id: "template-review-ack",
      doctorId: ACTOR.userId,
      version: 2,
      templateKind: "template_twin_docx",
      templateTwinCompiledVersion: {
        id: "compiled-review-ack",
        providerOwnershipEvidence: sourceOwnership.evidence,
        providerOwnershipSha256: sourceOwnership.sha256,
        sourceArtifact: {
          id: "source-review-ack",
          lineageId: "lineage-review-ack",
          lineageVersion: 1,
          sha256: sourceSha256,
          providerOwnershipEvidence: sourceOwnership.evidence,
          providerOwnershipSha256: sourceOwnership.sha256,
        },
      },
    },
    user: { practice: { templateTwinEnabled: true } },
    templateTwinFill: {
      id: "fill-review-ack",
      practiceId: ACTOR.practiceId,
      compiledVersionId: "compiled-review-ack",
      noteTemplateId: "template-review-ack",
      noteTemplateVersion: 2,
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
      providerOwnershipEvidence: visitOwnership.evidence,
      providerOwnershipSha256: visitOwnership.sha256,
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
    inputMode: "text_notes",
    rawTextInput: SYNTHETIC_CONTEXT,
    transcriptText: null,
    transcriptRaw: null,
    speakerMap: null,
  });
  mocks.lockCurrentPhysician.mockResolvedValue([{ id: ACTOR.userId }]);
  mocks.findCurrentVisit.mockResolvedValue({ manualRetryCount: 0 });
  mocks.findCurrentFill.mockResolvedValue({ id: "fill-review-ack" });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        $queryRaw: mocks.lockCurrentPhysician,
        transcribeVisit: { findUnique: mocks.findCurrentVisit },
        templateTwinFillManifest: {
          updateMany: mocks.updateFill,
          findFirst: mocks.findCurrentFill,
        },
        templateTwinAuditOutbox: { create: mocks.outboxCreate },
      }),
  );
});

describe("whole-manifest Template Twin review acknowledgement", () => {
  it("blocks review confirmation when the canonical encounter source is missing", async () => {
    mocks.findVisit.mockResolvedValue(visitRow({ rawTextInput: null }));

    await expect(
      acknowledgeTemplateTwinReview({
        visitId: "visit-review-ack",
        expectedManifestVersion: 3,
        expectedManifestSha256: manifestSha256,
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({ code: "ENCOUNTER_EVIDENCE_INVALID" });
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("blocks and audits review when encounter evidence changes before the final claim", async () => {
    mocks.lockVisit.mockResolvedValue({
      id: "visit-review-ack",
      userId: ACTOR.userId,
      status: "READY",
      deletedAt: null,
      archivedAt: null,
      soapVersion: 4,
      soapFinal: SOAP,
      inputMode: "text_notes",
      rawTextInput: `${SYNTHETIC_CONTEXT}\nSynthetic source drift.`,
      transcriptText: null,
      transcriptRaw: null,
      speakerMap: null,
    });

    await expect(
      acknowledgeTemplateTwinReview({
        visitId: "visit-review-ack",
        expectedManifestVersion: 3,
        expectedManifestSha256: manifestSha256,
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({ code: "ENCOUNTER_EVIDENCE_INVALID" });
    expect(mocks.updateFill).not.toHaveBeenCalled();
    expect(mocks.outboxCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
          metadata: expect.objectContaining({
            reasonCode: "ENCOUNTER_EVIDENCE_INVALID",
            operation: "whole_manifest_review_final_claim",
          }),
        }),
      }),
    );
  });

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

  it("fails closed when physician authority is revoked before the final review claim", async () => {
    mocks.lockCurrentPhysician.mockResolvedValue([]);

    await expect(
      acknowledgeTemplateTwinReview({
        visitId: "visit-review-ack",
        expectedManifestVersion: 3,
        expectedManifestSha256: manifestSha256,
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_CURRENT_PHYSICIAN_REQUIRED",
      message: "Current physician authorization is required for Template Twin.",
    });
    expect(mocks.updateFill).not.toHaveBeenCalled();
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
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
