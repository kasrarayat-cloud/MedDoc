import { createHash } from "node:crypto";

import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  claimVisit: vi.fn(),
  createFill: vi.fn(),
  findFill: vi.fn(),
  findTemplate: vi.fn(),
  updateFill: vi.fn(),
  transaction: vi.fn(),
  ledgerUpdate: vi.fn(),
  ledgerFind: vi.fn(),
  findPractice: vi.fn(),
  outboxCreate: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeVisit: { updateMany: mocks.claimVisit },
    noteTemplate: { findFirst: mocks.findTemplate },
    templateTwinFillManifest: {
      create: mocks.createFill,
      findUnique: mocks.findFill,
      updateMany: mocks.updateFill,
    },
    templateTwinAuditOutbox: { create: mocks.outboxCreate },
    $transaction: mocks.transaction,
    practice: { findFirst: mocks.findPractice },
  },
}));

import { templateTwinMappingsSha256 } from "../mapping-hash";
import { processTemplateTwinVisit } from "../fill-engine";
import { canonicalSha256 } from "../canonical";
import { canonicalSoapSha256 } from "../soap-binding";
import type { TemplateTwinArtifactStore } from "../storage";
import {
  buildTemplateTwinIntegrationFixture,
  SYNTHETIC_CONTEXT,
  SYNTHETIC_ENTITIES,
} from "./integration-fixture";

const PRACTICE_ID = "practice-fill-concurrency";
const DOCTOR_ID = "doctor-fill-concurrency";
const VISIT_ID = "visit-fill-concurrency";
const TEMPLATE_ID = "template-fill-concurrency";
const COMPILED_ID = "compiled-fill-concurrency";
const OLD_MANIFEST_SHA = "b".repeat(64);
const CURRENT_SOAP = "Synthetic current SOAP for concurrency verification.";
const SOURCE_PRIVACY_SCAN_EVIDENCE = {
  profileVersion: "template-twin-source-phi-safe-alpha-v1" as const,
  provider: "anthropic" as const,
  model: "synthetic-privacy-model-v1",
  scannedAt: "2026-07-15T12:00:00.000Z",
  scannedPartCount: 8,
  approvedStaticAssetPolicySha256: "a".repeat(64),
  approvedStaticAssetCount: 0,
  approvedStaticAssetUsedCount: 0,
  approvedStaticAssetUsageSha256: "b".repeat(64),
};

type Fixture = Awaited<ReturnType<typeof buildTemplateTwinIntegrationFixture>>;
let fixture: Fixture;
let outputWrites: number;

function templateRow() {
  return {
    id: TEMPLATE_ID,
    version: 1,
    templateTwinCompiledVersion: {
      id: COMPILED_ID,
      compilerVersion: fixture.ir.compilerVersion,
      compiledDocumentIr: fixture.ir,
      certificationStatus: "CERTIFIED",
      certification: {
        id: "certification-fill-concurrency",
        approvedMappingsSha256: templateTwinMappingsSha256(fixture.mappings),
        sourcePrivacyScanEvidenceSha256: canonicalSha256(
          SOURCE_PRIVACY_SCAN_EVIDENCE,
        ),
      },
      sourceArtifact: {
        practiceId: PRACTICE_ID,
        objectKey: `practices/${PRACTICE_ID}/template-twin/sources/lineage/v1/source/${fixture.ir.source.sha256}.docx`,
        objectVersionId: "provider-source-version-synthetic",
        objectEtag: "provider-source-etag-synthetic",
        sha256: fixture.ir.source.sha256,
        sizeBytes: fixture.source.byteLength,
        validationStatus: "accepted",
        privacyScanEvidence: SOURCE_PRIVACY_SCAN_EVIDENCE,
      },
      fields: fixture.mappings.map((mapping) => ({
        fieldId: mapping.fieldId,
        detectionStatus: "CERTIFIED",
        mapping: {
          clinicalConcept: mapping.clinicalConcept,
          expectedDataType: mapping.expectedDataType,
          polarityBehavior: mapping.polarityBehavior,
          temporality: mapping.temporality,
          laterality: mapping.laterality,
          unitPolicy: mapping.unitPolicy,
          approvedSynonyms: mapping.approvedSynonyms,
          required: mapping.required,
          blankPolicy: mapping.blankPolicy,
          unknownPolicy: mapping.unknownPolicy,
          practiceDefault: mapping.practiceDefault,
          mappingStatus: "CERTIFIED",
        },
      })),
    },
  };
}

function storage(): TemplateTwinArtifactStore {
  return {
    bucket: "synthetic-memory-only",
    storeSourceArtifact: vi.fn(),
    readSourceArtifact: vi.fn(async () => Buffer.from(fixture.source)),
    readOutputArtifact: vi.fn(),
    storeOutputArtifact: vi.fn(async (input) => {
      outputWrites += 1;
      const outputSha256 = createHash("sha256")
        .update(input.bytes)
        .digest("hex");
      return {
        bucket: "synthetic-memory-only",
        objectKey: `practices/${PRACTICE_ID}/template-twin/outputs/${VISIT_ID}/${input.manifestSha256}/artifact/${outputSha256}.docx`,
        objectVersionId: "provider-output-version-synthetic",
        objectEtag: "provider-output-etag-synthetic",
        sha256: outputSha256,
        mimeType:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document" as const,
        sizeBytes: input.bytes.byteLength,
        created: true,
      };
    }),
  };
}

function processInput(artifactStorage = storage()) {
  return {
    visitId: VISIT_ID,
    soapVersion: 1,
    soapFinal: CURRENT_SOAP,
    practiceId: PRACTICE_ID,
    doctorId: DOCTOR_ID,
    noteTemplateId: TEMPLATE_ID,
    noteTemplateVersion: 1,
    inputMode: "text" as const,
    contextText: SYNTHETIC_CONTEXT,
    entities: SYNTHETIC_ENTITIES,
    validationNow: "2026-07-15T12:00:00.000Z",
    resolverModelVersion: "synthetic-resolver-model",
    storage: artifactStorage,
  };
}

beforeAll(async () => {
  fixture = await buildTemplateTwinIntegrationFixture();
});

beforeEach(() => {
  vi.clearAllMocks();
  process.env.TEMPLATE_TWIN_KILL_SWITCH = "false";
  outputWrites = 0;
  mocks.claimVisit.mockResolvedValue({ count: 1 });
  mocks.findTemplate.mockImplementation(async () => templateRow());
  mocks.createFill.mockResolvedValue({ id: "fill-created" });
  mocks.updateFill.mockResolvedValue({ count: 1 });
  mocks.findPractice.mockResolvedValue({ templateTwinEnabled: true });
  mocks.ledgerUpdate.mockResolvedValue({ count: 1 });
  mocks.ledgerFind.mockResolvedValue(null);
  mocks.outboxCreate.mockResolvedValue({ id: "render-audit-outbox" });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        templateTwinFillManifest: {
          create: mocks.createFill,
          findUnique: mocks.findFill,
          updateMany: mocks.updateFill,
        },
        templateTwinObjectLedger: {
          updateMany: mocks.ledgerUpdate,
          findUnique: mocks.ledgerFind,
        },
        templateTwinAuditOutbox: { create: mocks.outboxCreate },
      }),
  );
});

describe("Template Twin worker provenance and manifest concurrency", () => {
  it("durably records a failed clinical render gate in the manifest transaction", async () => {
    mocks.findFill.mockResolvedValue(null);

    const result = await processTemplateTwinVisit({
      ...processInput(),
      entities: [],
    });

    expect(result.render).toBeNull();
    expect(mocks.createFill).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ status: "NEEDS_REVIEW" }),
      }),
    );
    expect(mocks.outboxCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
          metadata: expect.objectContaining({
            reasonCode: "FIELD_VALIDATION_BLOCKED_RENDER",
            blockerCount: expect.any(Number),
          }),
        }),
      }),
    );
    expect(outputWrites).toBe(0);
  });

  it("fails before pinning or rendering when the practice rollout flag is disabled", async () => {
    mocks.findPractice.mockResolvedValue({ templateTwinEnabled: false });
    const artifacts = storage();

    await expect(
      processTemplateTwinVisit(processInput(artifacts)),
    ).rejects.toMatchObject({
      code: "ROLLOUT_DISABLED",
      message: "Template Twin is not enabled for this practice.",
    });

    expect(mocks.claimVisit).not.toHaveBeenCalled();
    expect(artifacts.readSourceArtifact).not.toHaveBeenCalled();
    expect(outputWrites).toBe(0);
  });

  it("pins the selected template before source access and stops on a conflicting pin", async () => {
    const artifacts = storage();
    mocks.claimVisit.mockResolvedValue({ count: 0 });

    await expect(
      processTemplateTwinVisit(processInput(artifacts)),
    ).rejects.toMatchObject({ code: "TEMPLATE_PROVENANCE_MISMATCH" });

    expect(mocks.claimVisit).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: VISIT_ID,
          userId: DOCTOR_ID,
        }),
        data: {
          noteTemplateId: TEMPLATE_ID,
          noteTemplateVersion: 1,
        },
      }),
    );
    expect(mocks.findTemplate).not.toHaveBeenCalled();
    expect(artifacts.readSourceArtifact).not.toHaveBeenCalled();
  });

  it("cannot overwrite a manifest that is signed while rendering is in flight", async () => {
    mocks.findFill
      .mockResolvedValueOnce({
        id: "fill-existing",
        status: "VERIFIED",
        signedDecisionAt: null,
        reviewedAt: null,
        soapVersion: 1,
        soapSha256: canonicalSoapSha256(CURRENT_SOAP),
        manifestVersion: 4,
        manifestSha256: OLD_MANIFEST_SHA,
        roundTripVerified: true,
      })
      .mockResolvedValueOnce({
        status: "SIGNED",
        signedDecisionAt: new Date("2026-07-15T12:05:00.000Z"),
      });
    mocks.updateFill.mockResolvedValue({ count: 0 });

    await expect(
      processTemplateTwinVisit(processInput()),
    ).rejects.toMatchObject({
      code: "SIGNED_MANIFEST_IMMUTABLE",
    });

    expect(outputWrites).toBe(1);
    expect(mocks.updateFill).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: "fill-existing",
          status: { not: "SIGNED" },
          signedDecisionAt: null,
          reviewedAt: null,
          soapVersion: 1,
          soapSha256: canonicalSoapSha256(CURRENT_SOAP),
          manifestVersion: 4,
          manifestSha256: OLD_MANIFEST_SHA,
        }),
      }),
    );
    expect(mocks.createFill).not.toHaveBeenCalled();
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
  });

  it("never replaces a clinician-reviewed manifest with stale worker evidence", async () => {
    mocks.findFill.mockResolvedValue({
      id: "fill-existing",
      status: "VERIFIED",
      signedDecisionAt: null,
      reviewedAt: new Date("2026-07-15T12:03:00.000Z"),
      soapVersion: 1,
      soapSha256: canonicalSoapSha256(CURRENT_SOAP),
      manifestVersion: 5,
      manifestSha256: OLD_MANIFEST_SHA,
      roundTripVerified: true,
    });

    await expect(
      processTemplateTwinVisit(processInput()),
    ).rejects.toMatchObject({
      code: "MANIFEST_CONFLICT",
    });

    expect(outputWrites).toBe(0);
    expect(mocks.updateFill).not.toHaveBeenCalled();
    expect(mocks.createFill).not.toHaveBeenCalled();
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
  });

  it("regenerates an explicitly invalidated reviewed manifest after a SOAP edit", async () => {
    const reviewedAt = new Date("2026-07-15T12:03:00.000Z");
    mocks.findFill.mockResolvedValue({
      id: "fill-existing",
      status: "NEEDS_REVIEW",
      signedDecisionAt: null,
      reviewedAt,
      soapVersion: 1,
      soapSha256: canonicalSoapSha256(CURRENT_SOAP),
      manifestVersion: 6,
      manifestSha256: OLD_MANIFEST_SHA,
      roundTripVerified: false,
    });

    const editedSoap = `${CURRENT_SOAP} Synthetic plan edit.`;
    await expect(
      processTemplateTwinVisit({
        ...processInput(),
        soapVersion: 2,
        soapFinal: editedSoap,
      }),
    ).resolves.toBeDefined();

    expect(mocks.updateFill).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: "fill-existing",
          reviewedAt,
          soapVersion: 1,
          soapSha256: canonicalSoapSha256(CURRENT_SOAP),
        }),
        data: expect.objectContaining({
          soapVersion: 2,
          soapSha256: canonicalSoapSha256(editedSoap),
          reviewedAt: null,
          manifestVersion: { increment: 1 },
        }),
      }),
    );
  });

  it("updates only the exact unsigned manifest version observed before storage", async () => {
    mocks.findFill.mockResolvedValue({
      id: "fill-existing",
      status: "NEEDS_REVIEW",
      signedDecisionAt: null,
      reviewedAt: null,
      soapVersion: 1,
      soapSha256: canonicalSoapSha256(CURRENT_SOAP),
      manifestVersion: 7,
      manifestSha256: OLD_MANIFEST_SHA,
      roundTripVerified: false,
    });

    const result = await processTemplateTwinVisit(processInput());

    expect(result.manifest.validation.issues).toEqual([]);
    expect(result.render?.verification.verified).toBe(true);
    const outputObjectKey =
      `practices/${PRACTICE_ID}/template-twin/outputs/${VISIT_ID}/` +
      `${result.manifestSha256}/artifact/${result.render!.outputSha256}.docx`;
    const expectedRenderEventKey =
      `template-twin:render-verified:${canonicalSha256({
        visitId: VISIT_ID,
        manifestSha256: result.manifestSha256,
        outputObjectKey,
      })}`;
    expect(mocks.updateFill).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: "fill-existing",
          manifestVersion: 7,
          manifestSha256: OLD_MANIFEST_SHA,
          signedDecisionAt: null,
          reviewedAt: null,
          soapVersion: 1,
          soapSha256: canonicalSoapSha256(CURRENT_SOAP),
        }),
        data: expect.objectContaining({
          status: "VERIFIED",
          manifestVersion: { increment: 1 },
          criticalUnresolvedCount: 0,
          roundTripVerified: true,
        }),
      }),
    );
    expect(mocks.ledgerUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          practiceId: PRACTICE_ID,
          state: { in: ["WRITTEN_UNCLAIMED", "CLAIMED"] },
        }),
        data: expect.objectContaining({
          state: "CLAIMED",
          claimType: "fill_manifest",
          claimId: "fill-existing",
        }),
      }),
    );
    expect(mocks.outboxCreate).toHaveBeenCalledWith({
      data: expect.objectContaining({
        eventKey: expectedRenderEventKey,
        practiceId: PRACTICE_ID,
        actorId: DOCTOR_ID,
        action: "TEMPLATE_TWIN_RENDER_VERIFIED",
        targetType: "TranscribeVisit",
        targetId: VISIT_ID,
        metadata: expect.objectContaining({
          compiledVersionId: COMPILED_ID,
          manifestSha256: result.manifestSha256,
          outputSha256: result.render!.outputSha256,
          rendererVersion: result.render!.rendererVersion,
        }),
      }),
    });
    expect(mocks.ledgerUpdate.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.outboxCreate.mock.invocationCallOrder[0]!,
    );
  });

  it("claims a newly created output for the manifest in the same transaction", async () => {
    mocks.findFill.mockResolvedValue(null);
    mocks.createFill.mockResolvedValue({ id: "fill-created" });

    await expect(
      processTemplateTwinVisit(processInput()),
    ).resolves.toBeDefined();

    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(mocks.createFill).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          practiceId: PRACTICE_ID,
          visitId: VISIT_ID,
          soapVersion: 1,
          soapSha256: expect.stringMatching(/^[a-f0-9]{64}$/),
        }),
        select: { id: true },
      }),
    );
    expect(mocks.ledgerUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          state: "CLAIMED",
          claimType: "fill_manifest",
          claimId: "fill-created",
        }),
      }),
    );
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(1);
  });

  it("does not enqueue render verification when the object claim fails", async () => {
    mocks.findFill.mockResolvedValue(null);
    mocks.ledgerUpdate.mockResolvedValue({ count: 0 });
    mocks.ledgerFind.mockResolvedValue(null);

    await expect(
      processTemplateTwinVisit(processInput()),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_OBJECT_LEDGER_CONFLICT",
    });

    expect(mocks.createFill).toHaveBeenCalledTimes(1);
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
  });

  it("fails closed when durable render audit enqueue fails", async () => {
    mocks.findFill.mockResolvedValue(null);
    mocks.outboxCreate.mockRejectedValue(
      new Error("synthetic audit outbox unavailable"),
    );

    await expect(
      processTemplateTwinVisit(processInput()),
    ).rejects.toThrow("synthetic audit outbox unavailable");

    expect(mocks.ledgerUpdate).toHaveBeenCalledTimes(1);
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(1);
  });
});
