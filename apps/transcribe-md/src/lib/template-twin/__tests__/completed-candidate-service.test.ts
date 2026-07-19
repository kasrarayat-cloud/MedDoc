import { createHash } from "node:crypto";

import { beforeEach, describe, expect, it, vi } from "vitest";

import type { TemplateTwinArtifactStore } from "../storage";
import { canonicalSha256 } from "../canonical";

const mocks = vi.hoisted(() => ({
  transaction: vi.fn(),
  candidateCreate: vi.fn(),
  candidateFindFirst: vi.fn(),
  candidateUpdateMany: vi.fn(),
  regionUpdateMany: vi.fn(),
  receiptCreate: vi.fn(),
  queryRaw: vi.fn(),
  compile: vi.fn(),
  begin: vi.fn(),
  scan: vi.fn(),
  isolate: vi.fn(),
  reject: vi.fn(),
  minimize: vi.fn(),
  convert: vi.fn(),
  finalRollout: vi.fn(),
  claimObject: vi.fn(),
  audit: vi.fn(),
  assertOwner: vi.fn(),
}));

const tx = {
  $queryRaw: mocks.queryRaw,
  templateTwinCompletedCandidate: {
    create: mocks.candidateCreate,
    findFirst: mocks.candidateFindFirst,
    updateMany: mocks.candidateUpdateMany,
  },
  templateTwinCompletedCandidateRegion: {
    updateMany: mocks.regionUpdateMany,
  },
  templateTwinCompletedCandidateReviewReceipt: {
    create: mocks.receiptCreate,
  },
};

vi.mock("@meddoc/db", () => ({
  default: {
    $transaction: mocks.transaction,
    templateTwinCompletedCandidate: {
      findFirst: mocks.candidateFindFirst,
    },
  },
}));

vi.mock("../quarantine-admission", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("../quarantine-admission")>();
  return {
    ...actual,
    beginTemplateTwinQuarantine: mocks.begin,
    scanTemplateTwinQuarantine: mocks.scan,
    isolateCompletedExampleQuarantine: mocks.isolate,
    rejectTemplateTwinQuarantine: mocks.reject,
  };
});

vi.mock("../source-metadata", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../source-metadata")>();
  return { ...actual, minimizeTemplateTwinSourceMetadata: mocks.minimize };
});

vi.mock("../completed-candidate-converter", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("../completed-candidate-converter")>();
  return { ...actual, convertCompletedDocumentsToCandidate: mocks.convert };
});

vi.mock("@/lib/note-template-docx", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/note-template-docx")>();
  return { ...actual, compileTemplateDocx: mocks.compile };
});

vi.mock("../rollout", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../rollout")>();
  return {
    ...actual,
    lockTemplateTwinRolloutForFinalClaim: mocks.finalRollout,
  };
});

vi.mock("../audit-outbox", () => ({
  enqueueTemplateTwinAudit: mocks.audit,
}));

vi.mock("../storage", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../storage")>();
  return {
    ...actual,
    assertTemplateTwinRecordOwner: mocks.assertOwner,
    claimTemplateTwinObject: mocks.claimObject,
  };
});

import {
  createCompletedCandidate,
  issueCompletedCandidateReviewPreview,
  readApprovedCompletedCandidate,
  reviewCompletedCandidate,
} from "../completed-candidate-service";

const ACTOR = {
  userId: "doctor_synthetic_1",
  userEmail: "doctor@synthetic.test",
  practiceId: "practice_synthetic_1",
  rolloutToken: {
    practiceId: "practice_synthetic_1",
    globalGeneration: BigInt(11),
    practiceGeneration: BigInt(7),
  },
};
const CANDIDATE_BYTES = Buffer.from("new blank candidate");
const CANDIDATE_SHA = createHash("sha256")
  .update(CANDIDATE_BYTES)
  .digest("hex");
const REGION_ONE = "tccr_111111111111111111111111";
const REVIEW_RECEIPT_ID = "123e4567-e89b-42d3-a456-426614174001";
const REVIEW_RECEIPT = `${REVIEW_RECEIPT_ID}.${"R".repeat(43)}`;
const CANDIDATE_STRUCTURE_SHA = "c".repeat(64);
const EXAMPLE_STRUCTURE_SHA = "d".repeat(64);
const REGION = {
  regionId: REGION_ONE,
  displayOrder: 0,
  label: "Finding",
  evidenceType: "stable_label_changed_scalar_cell" as const,
  partName: "word/document.xml" as const,
  tableIndex: 0,
  rowIndex: 0,
  cellIndex: 1,
  candidateTag: "qmd:candidate:111111111111111111111111",
  candidateSdtId: "123",
  sourceEvidenceSha256: "f".repeat(64),
  sourceDescription: "Synthetic values differed.",
  candidateDescription: "Blank text control.",
};
const INVENTORY_SHA = canonicalSha256([REGION]);
const PROJECTION = {
  profileVersion:
    "completed-candidate-redacted-structural-review/1.0.0" as const,
  valuesRedacted: true as const,
  sourceBytesReturned: false as const,
  providerEgress: false as const,
  paginationRepresented: false as const,
  sourceExampleSha256s: ["1".repeat(64), "2".repeat(64)],
  sourceStructureSha256: EXAMPLE_STRUCTURE_SHA,
  candidateStructureSha256: CANDIDATE_STRUCTURE_SHA,
  inventorySha256: INVENTORY_SHA,
  candidateSha256: CANDIDATE_SHA,
  blocks: [
    {
      kind: "table" as const,
      blockKey: "table:0:/w:document[1]/w:body[1]/w:tbl[1]",
      displayOrder: 0,
      tableIndex: 0,
      gridColumnBasisPoints: [4000, 6000],
      rows: [
        {
          rowIndex: 0,
          cells: [
            {
              cellKey: "table:0:row:0:cell:0",
              cellIndex: 0,
              columnStart: 0,
              columnSpan: 1,
              rowSpan: 1 as const,
              role: {
                kind: "stable_label" as const,
                label: "Finding",
                forRegionId: REGION_ONE,
              },
            },
            {
              cellKey: "table:0:row:0:cell:1",
              cellIndex: 1,
              columnStart: 1,
              columnSpan: 1,
              rowSpan: 1 as const,
              role: {
                kind: "candidate_region" as const,
                regionId: REGION_ONE,
                candidateTag: REGION.candidateTag,
                controlKind: "plain_text" as const,
                sourceState: "VALUE_WITHHELD" as const,
                candidateState: "BLANK_CONTROL" as const,
              },
            },
          ],
        },
      ],
    },
  ],
  regionCount: 1,
};
const PROJECTION_SHA = canonicalSha256(PROJECTION);

function pendingCandidate() {
  return {
    id: "candidate_synthetic",
    practiceId: ACTOR.practiceId,
    createdById: ACTOR.userId,
    status: "PENDING_REVIEW",
    candidateSha256: CANDIDATE_SHA,
    candidateStructureSha256: CANDIDATE_STRUCTURE_SHA,
    inventorySha256: INVENTORY_SHA,
    converterVersion: "completed-document-candidate/1.1.0",
    reviewProjection: PROJECTION,
    reviewProjectionSha256: PROJECTION_SHA,
    examples: [
      {
        ordinal: 1,
        minimizedSha256: "1".repeat(64),
        documentStructureSha256: EXAMPLE_STRUCTURE_SHA,
      },
      {
        ordinal: 2,
        minimizedSha256: "2".repeat(64),
        documentStructureSha256: EXAMPLE_STRUCTURE_SHA,
      },
    ],
    regions: [{ id: "row_one", ...REGION, decision: "PENDING" }],
  };
}

function receipt(notExpired = true) {
  return {
    id: REVIEW_RECEIPT_ID,
    candidateId: "candidate_synthetic",
    practiceId: ACTOR.practiceId,
    reviewedById: ACTOR.userId,
    tokenSha256: createHash("sha256").update(REVIEW_RECEIPT).digest("hex"),
    candidateSha256: CANDIDATE_SHA,
    candidateStructureSha256: CANDIDATE_STRUCTURE_SHA,
    inventorySha256: INVENTORY_SHA,
    reviewProjectionSha256: PROJECTION_SHA,
    converterVersion: "completed-document-candidate/1.1.0",
    globalRolloutGeneration: ACTOR.rolloutToken.globalGeneration,
    practiceRolloutGeneration: ACTOR.rolloutToken.practiceGeneration,
    expiresAt: new Date(Date.now() + 60_000),
    consumedAt: null,
    notExpired,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.transaction.mockImplementation(
    async (callback: (client: typeof tx) => Promise<unknown>) => callback(tx),
  );
  mocks.queryRaw.mockResolvedValue([]);
  mocks.candidateCreate.mockResolvedValue({ id: "candidate_synthetic" });
  mocks.receiptCreate.mockResolvedValue({ id: REVIEW_RECEIPT_ID });
  mocks.candidateUpdateMany.mockResolvedValue({ count: 1 });
  mocks.regionUpdateMany.mockResolvedValue({ count: 1 });
  mocks.finalRollout.mockResolvedValue({ allowed: true, code: "ALLOWED" });
  mocks.claimObject.mockResolvedValue(undefined);
  mocks.audit.mockResolvedValue(undefined);
  mocks.isolate.mockResolvedValue(undefined);
  mocks.reject.mockResolvedValue(undefined);
  mocks.compile.mockReturnValue({
    structureSha256: CANDIDATE_STRUCTURE_SHA,
    stats: { blockingUnsupported: 0 },
    fields: [
      {
        rendererBinding: {
          bindingType: "content_control",
          tag: REGION.candidateTag,
          sdtId: REGION.candidateSdtId,
        },
      },
    ],
  });
});

describe("completed candidate service", () => {
  it("quarantines and locally scans every example before deterministic conversion", async () => {
    const sourceOne = Buffer.from("synthetic example one");
    const sourceTwo = Buffer.from("synthetic example two");
    mocks.begin
      .mockResolvedValueOnce({ id: "q_one" })
      .mockResolvedValueOnce({ id: "q_two" });
    mocks.scan.mockResolvedValue(undefined);
    mocks.minimize
      .mockResolvedValueOnce({
        document: Buffer.from("minimized one"),
        evidence: { minimizedSha256: "1".repeat(64) },
      })
      .mockResolvedValueOnce({
        document: Buffer.from("minimized two"),
        evidence: { minimizedSha256: "2".repeat(64) },
      });
    const privacyReceipt = {
      profileVersion:
        "completed-candidate-local-synthetic-privacy/1.1.0" as const,
      providerEgress: false as const,
      exampleCount: 2,
      sentinelVerified: true as const,
      structuredIdentifierClasses: [] as const,
      sourceBinding:
        "minimized-package-structure-visible-text-digests" as const,
      exampleEvidenceSha256s: ["8".repeat(64), "9".repeat(64)],
    };
    mocks.convert.mockResolvedValue({
      document: CANDIDATE_BYTES,
      candidateSha256: CANDIDATE_SHA,
      candidateStructureSha256: CANDIDATE_STRUCTURE_SHA,
      inventorySha256: INVENTORY_SHA,
      converterVersion: "completed-document-candidate/1.1.0",
      exampleStructureSha256: EXAMPLE_STRUCTURE_SHA,
      comparison: {
        exampleCount: 2,
        identicalStructure: true,
        sourceBlockCount: 4,
        candidateFieldCount: 1,
        preservedStaticBlockCount: 3,
        sourceSummary: "safe",
        candidateSummary: "safe",
      },
      privacyEvidence: {
        ...privacyReceipt,
        evidenceSha256: canonicalSha256(privacyReceipt),
      },
      reviewProjection: PROJECTION,
      reviewProjectionSha256: PROJECTION_SHA,
      regions: [REGION],
    });
    const storeCandidateArtifact = vi.fn().mockResolvedValue({
      bucket: "synthetic-private-bucket",
      objectKey:
        "practices/practice_synthetic_1/template-twin/candidates/candidate/v1/artifact/a.docx",
      objectVersionId: "candidate-version-synthetic",
      objectEtag: "candidate-etag-synthetic",
      sha256: CANDIDATE_SHA,
      mimeType:
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      sizeBytes: 19,
      created: true,
    });
    const storage = {
      bucket: "synthetic-private-bucket",
      storeCandidateArtifact,
    } as unknown as TemplateTwinArtifactStore;

    const result = await createCompletedCandidate({
      examples: [sourceOne, sourceTwo],
      identity: {
        name: "Synthetic candidate",
        encounterScope: "Synthetic follow-up",
        versionDescription: "Two matching synthetic examples",
      },
      actor: ACTOR,
      storage,
    });

    expect(result.reviewUrl).toMatch(
      /^\/settings\/note-format\/completed-candidate\/[0-9a-f-]+$/u,
    );
    expect(mocks.begin).toHaveBeenCalledTimes(2);
    expect(mocks.begin).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        source: sourceOne,
        intakeMode: "COMPLETED_EXAMPLE",
        lineageVersion: 1,
      }),
    );
    expect(mocks.scan).toHaveBeenCalledTimes(2);
    expect(mocks.convert).toHaveBeenCalledTimes(1);
    expect(mocks.scan.mock.invocationCallOrder[1]).toBeLessThan(
      mocks.convert.mock.invocationCallOrder[0]!,
    );
    expect(storeCandidateArtifact.mock.invocationCallOrder[0]).toBeGreaterThan(
      mocks.convert.mock.invocationCallOrder[0]!,
    );
    expect(mocks.isolate).toHaveBeenCalledTimes(2);
    expect(mocks.claimObject).toHaveBeenCalledWith(
      tx,
      expect.objectContaining({
        claimType: "completed_candidate",
        practiceId: ACTOR.practiceId,
      }),
    );
    expect(mocks.candidateCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          status: "PENDING_REVIEW",
          privacyEvidence: expect.objectContaining({ providerEgress: false }),
          converterVersion: "completed-document-candidate/1.1.0",
          reviewProjection: PROJECTION,
          reviewProjectionSha256: PROJECTION_SHA,
          examples: expect.any(Object),
          regions: expect.any(Object),
        }),
      }),
    );
    const createdExamples = mocks.candidateCreate.mock.calls[0]![0].data
      .examples.create as Array<{ localPrivacyEvidenceSha256: string }>;
    expect(
      createdExamples.map((example) => example.localPrivacyEvidenceSha256),
    ).toEqual(["8".repeat(64), "9".repeat(64)]);
  });

  it("issues a hashed 15-minute receipt only after rollout and candidate locks", async () => {
    mocks.candidateFindFirst.mockResolvedValue(pendingCandidate());

    const result = await issueCompletedCandidateReviewPreview({
      candidateId: "candidate_synthetic",
      actor: ACTOR,
    });

    expect(result.projection).toEqual(PROJECTION);
    expect(result.reviewReceipt).toMatch(/^[0-9a-f-]{36}\.[A-Za-z0-9_-]{43}$/u);
    expect(mocks.finalRollout.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.queryRaw.mock.invocationCallOrder[0]!,
    );
    const receiptData = mocks.receiptCreate.mock.calls[0]![0].data;
    expect(receiptData).toMatchObject({
      candidateId: "candidate_synthetic",
      reviewProjectionSha256: PROJECTION_SHA,
      converterVersion: "completed-document-candidate/1.1.0",
    });
    expect(receiptData.tokenSha256).toMatch(/^[a-f0-9]{64}$/u);
    expect(receiptData.tokenSha256).not.toBe(result.reviewReceipt);
    expect(
      receiptData.expiresAt.getTime() - receiptData.createdAt.getTime(),
    ).toBe(15 * 60 * 1000);
    expect(JSON.stringify(mocks.audit.mock.calls)).not.toContain(
      result.reviewReceipt,
    );
  });

  it("treats the stored projection as untrusted and issues no receipt when its binding is tampered", async () => {
    const tamperedProjection = {
      ...PROJECTION,
      blocks: [
        {
          ...PROJECTION.blocks[0],
          rows: [
            {
              ...PROJECTION.blocks[0].rows[0],
              cells: PROJECTION.blocks[0].rows[0].cells.map((cell) =>
                cell.role.kind === "candidate_region"
                  ? {
                      ...cell,
                      role: {
                        ...cell.role,
                        candidateTag: "qmd:candidate:222222222222222222222222",
                      },
                    }
                  : cell,
              ),
            },
          ],
        },
      ],
    };
    mocks.candidateFindFirst.mockResolvedValue({
      ...pendingCandidate(),
      reviewProjection: tamperedProjection,
      reviewProjectionSha256: canonicalSha256(tamperedProjection),
    });

    await expect(
      issueCompletedCandidateReviewPreview({
        candidateId: "candidate_synthetic",
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({ code: "PERSISTENCE_FAILED" });

    expect(mocks.receiptCreate).not.toHaveBeenCalled();
    expect(mocks.audit).not.toHaveBeenCalled();
  });

  it("binds the projection to the candidate structure digest before issuing a receipt", async () => {
    const tamperedProjection = {
      ...PROJECTION,
      candidateStructureSha256: "a".repeat(64),
    };
    mocks.candidateFindFirst.mockResolvedValue({
      ...pendingCandidate(),
      reviewProjection: tamperedProjection,
      reviewProjectionSha256: canonicalSha256(tamperedProjection),
    });

    await expect(
      issueCompletedCandidateReviewPreview({
        candidateId: "candidate_synthetic",
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({ code: "PERSISTENCE_FAILED" });

    expect(mocks.receiptCreate).not.toHaveBeenCalled();
    expect(mocks.audit).not.toHaveBeenCalled();
  });

  it("consumes the exact preview receipt and records a terminal rejection atomically", async () => {
    mocks.candidateFindFirst.mockResolvedValue(pendingCandidate());
    mocks.queryRaw
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([receipt()])
      .mockResolvedValueOnce([{ id: REVIEW_RECEIPT_ID }]);

    const result = await reviewCompletedCandidate({
      candidateId: "candidate_synthetic",
      payload: {
        decisions: [{ regionId: REGION_ONE, decision: "REJECTED" }],
        physicianAttestation: true,
        reviewReceipt: REVIEW_RECEIPT,
      },
      actor: ACTOR,
    });

    expect(result).toEqual({ status: "REJECTED" });
    expect(mocks.regionUpdateMany).toHaveBeenCalledTimes(1);
    expect(mocks.candidateUpdateMany).toHaveBeenCalledWith({
      where: { id: "candidate_synthetic", status: "PENDING_REVIEW" },
      data: {
        status: "REJECTED",
        reviewedAt: expect.any(Date),
        reviewReceiptId: REVIEW_RECEIPT_ID,
      },
    });
    expect(mocks.audit).toHaveBeenCalledWith(
      tx,
      expect.objectContaining({
        action: "TEMPLATE_TWIN_COMPLETED_CANDIDATE_REVIEWED",
        metadata: expect.objectContaining({
          reviewReceiptId: REVIEW_RECEIPT_ID,
          reviewProjectionSha256: PROJECTION_SHA,
          regionCount: 1,
          approvedCount: 0,
          rejectedCount: 1,
          gateOutcome: "rejected",
        }),
      }),
    );
  });

  it("fails closed before persistence when a region decision is missing", async () => {
    await expect(
      reviewCompletedCandidate({
        candidateId: "candidate_synthetic",
        payload: {
          decisions: [],
          physicianAttestation: true,
          reviewReceipt: REVIEW_RECEIPT,
        },
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({
      code: "INVALID_INPUT",
    });
    expect(mocks.regionUpdateMany).not.toHaveBeenCalled();
    expect(mocks.candidateUpdateMany).not.toHaveBeenCalled();
  });

  it("fails closed on an expired receipt before any decision is written", async () => {
    mocks.candidateFindFirst.mockResolvedValue(pendingCandidate());
    mocks.queryRaw
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([receipt(false)]);

    await expect(
      reviewCompletedCandidate({
        candidateId: "candidate_synthetic",
        payload: {
          decisions: [{ regionId: REGION_ONE, decision: "APPROVED" }],
          physicianAttestation: true,
          reviewReceipt: REVIEW_RECEIPT,
        },
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({ code: "REVIEW_PREVIEW_REQUIRED" });

    expect(mocks.regionUpdateMany).not.toHaveBeenCalled();
    expect(mocks.candidateUpdateMany).not.toHaveBeenCalled();
    expect(mocks.audit).not.toHaveBeenCalled();
  });

  it("fails closed on a consumed receipt before any decision is written", async () => {
    mocks.candidateFindFirst.mockResolvedValue(pendingCandidate());
    mocks.queryRaw
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([{ ...receipt(), consumedAt: new Date() }]);

    await expect(
      reviewCompletedCandidate({
        candidateId: "candidate_synthetic",
        payload: {
          decisions: [{ regionId: REGION_ONE, decision: "APPROVED" }],
          physicianAttestation: true,
          reviewReceipt: REVIEW_RECEIPT,
        },
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({ code: "REVIEW_PREVIEW_REQUIRED" });

    expect(mocks.regionUpdateMany).not.toHaveBeenCalled();
    expect(mocks.candidateUpdateMany).not.toHaveBeenCalled();
    expect(mocks.audit).not.toHaveBeenCalled();
  });

  it("rechecks rollout under final locks after reading approved candidate bytes", async () => {
    const bytes = Buffer.from("approved blank synthetic candidate");
    mocks.candidateFindFirst
      .mockResolvedValueOnce({
        id: "candidate_synthetic",
        practiceId: ACTOR.practiceId,
        createdById: ACTOR.userId,
        candidateObjectKey: "private/candidate.docx",
        candidateObjectVersionId: "version-1",
        candidateObjectEtag: "etag-1",
        candidateSha256: CANDIDATE_SHA,
        candidateSizeBytes: bytes.byteLength,
        inventorySha256: INVENTORY_SHA,
        _count: { regions: 1 },
      })
      .mockResolvedValueOnce({ id: "candidate_synthetic" });
    const readCandidateArtifact = vi.fn().mockResolvedValue(bytes);
    const storage = {
      readCandidateArtifact,
    } as unknown as TemplateTwinArtifactStore;

    await expect(
      readApprovedCompletedCandidate({
        candidateId: "candidate_synthetic",
        actor: ACTOR,
        storage,
      }),
    ).resolves.toEqual(bytes);

    expect(readCandidateArtifact.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.finalRollout.mock.invocationCallOrder.at(-1)!,
    );
    expect(mocks.finalRollout).toHaveBeenLastCalledWith({
      tx,
      practiceId: ACTOR.practiceId,
      pinnedToken: ACTOR.rolloutToken,
    });
    expect(mocks.audit).toHaveBeenCalledWith(
      tx,
      expect.objectContaining({
        action: "EXPORT_TEMPLATE_TWIN_CANDIDATE_DOCX_DOWNLOADED",
      }),
    );
  });

  it("returns no approved bytes when rollout changed during the object read", async () => {
    const bytes = Buffer.from("approved blank synthetic candidate");
    mocks.candidateFindFirst.mockResolvedValueOnce({
      id: "candidate_synthetic",
      practiceId: ACTOR.practiceId,
      createdById: ACTOR.userId,
      candidateObjectKey: "private/candidate.docx",
      candidateObjectVersionId: "version-1",
      candidateObjectEtag: "etag-1",
      candidateSha256: CANDIDATE_SHA,
      candidateSizeBytes: bytes.byteLength,
      inventorySha256: INVENTORY_SHA,
      _count: { regions: 1 },
    });
    const readCandidateArtifact = vi.fn().mockResolvedValue(bytes);
    mocks.finalRollout.mockResolvedValueOnce({
      allowed: false,
      code: "GLOBAL_DISABLED",
    });

    await expect(
      readApprovedCompletedCandidate({
        candidateId: "candidate_synthetic",
        actor: ACTOR,
        storage: {
          readCandidateArtifact,
        } as unknown as TemplateTwinArtifactStore,
      }),
    ).rejects.toMatchObject({ code: "ROLLOUT_CHANGED" });

    expect(readCandidateArtifact).toHaveBeenCalledTimes(1);
    expect(mocks.audit).not.toHaveBeenCalled();
    expect(mocks.candidateFindFirst).toHaveBeenCalledTimes(1);
  });
});
