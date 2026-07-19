import { beforeEach, describe, expect, it, vi } from "vitest";

import type { TemplateTwinArtifactStore } from "../storage";

const mocks = vi.hoisted(() => ({
  transaction: vi.fn(),
  candidateCreate: vi.fn(),
  candidateFindFirst: vi.fn(),
  candidateUpdateMany: vi.fn(),
  regionUpdateMany: vi.fn(),
  queryRaw: vi.fn(),
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
const CANDIDATE_SHA = "a".repeat(64);
const INVENTORY_SHA = "b".repeat(64);
const REGION_ONE = "tccr_111111111111111111111111";
const REGION_TWO = "tccr_222222222222222222222222";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.transaction.mockImplementation(
    async (callback: (client: typeof tx) => Promise<unknown>) => callback(tx),
  );
  mocks.queryRaw.mockResolvedValue([]);
  mocks.candidateCreate.mockResolvedValue({ id: "candidate_synthetic" });
  mocks.candidateUpdateMany.mockResolvedValue({ count: 1 });
  mocks.regionUpdateMany.mockResolvedValue({ count: 1 });
  mocks.finalRollout.mockResolvedValue({ allowed: true, code: "ALLOWED" });
  mocks.claimObject.mockResolvedValue(undefined);
  mocks.audit.mockResolvedValue(undefined);
  mocks.isolate.mockResolvedValue(undefined);
  mocks.reject.mockResolvedValue(undefined);
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
    mocks.convert.mockResolvedValue({
      document: Buffer.from("new blank candidate"),
      candidateSha256: CANDIDATE_SHA,
      candidateStructureSha256: "c".repeat(64),
      inventorySha256: INVENTORY_SHA,
      converterVersion: "completed-document-candidate/1.0.0",
      exampleStructureSha256: "d".repeat(64),
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
        profileVersion: "completed-candidate-local-synthetic-privacy/1.1.0",
        providerEgress: false,
        exampleCount: 2,
        sentinelVerified: true,
        structuredIdentifierClasses: [],
        sourceBinding: "minimized-package-structure-visible-text-digests",
        exampleEvidenceSha256s: ["8".repeat(64), "9".repeat(64)],
        evidenceSha256: "e".repeat(64),
      },
      regions: [
        {
          regionId: REGION_ONE,
          displayOrder: 0,
          label: "Finding",
          evidenceType: "stable_label_changed_scalar_cell",
          partName: "word/document.xml",
          tableIndex: 0,
          rowIndex: 0,
          cellIndex: 1,
          candidateTag: "qmd:candidate:111111111111111111111111",
          candidateSdtId: "123",
          sourceEvidenceSha256: "f".repeat(64),
        },
      ],
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

  it("requires every pending region exactly once and records a terminal rejection", async () => {
    mocks.candidateFindFirst.mockResolvedValue({
      id: "candidate_synthetic",
      practiceId: ACTOR.practiceId,
      createdById: ACTOR.userId,
      status: "PENDING_REVIEW",
      inventorySha256: INVENTORY_SHA,
      regions: [
        { id: "row_one", regionId: REGION_ONE, decision: "PENDING" },
        { id: "row_two", regionId: REGION_TWO, decision: "PENDING" },
      ],
    });

    const result = await reviewCompletedCandidate({
      candidateId: "candidate_synthetic",
      payload: {
        decisions: [
          { regionId: REGION_ONE, decision: "APPROVED" },
          { regionId: REGION_TWO, decision: "REJECTED" },
        ],
        physicianAttestation: true,
      },
      actor: ACTOR,
    });

    expect(result).toEqual({ status: "REJECTED" });
    expect(mocks.regionUpdateMany).toHaveBeenCalledTimes(2);
    expect(mocks.candidateUpdateMany).toHaveBeenCalledWith({
      where: { id: "candidate_synthetic", status: "PENDING_REVIEW" },
      data: { status: "REJECTED", reviewedAt: expect.any(Date) },
    });
    expect(mocks.audit).toHaveBeenCalledWith(
      tx,
      expect.objectContaining({
        action: "TEMPLATE_TWIN_COMPLETED_CANDIDATE_REVIEWED",
        metadata: expect.objectContaining({
          regionCount: 2,
          approvedCount: 1,
          rejectedCount: 1,
          gateOutcome: "rejected",
        }),
      }),
    );
  });

  it("fails closed before persistence when a region decision is missing", async () => {
    mocks.candidateFindFirst.mockResolvedValue({
      id: "candidate_synthetic",
      practiceId: ACTOR.practiceId,
      createdById: ACTOR.userId,
      status: "PENDING_REVIEW",
      inventorySha256: INVENTORY_SHA,
      regions: [
        { id: "row_one", regionId: REGION_ONE, decision: "PENDING" },
        { id: "row_two", regionId: REGION_TWO, decision: "PENDING" },
      ],
    });

    await expect(
      reviewCompletedCandidate({
        candidateId: "candidate_synthetic",
        payload: {
          decisions: [{ regionId: REGION_ONE, decision: "APPROVED" }],
          physicianAttestation: true,
        },
        actor: ACTOR,
      }),
    ).rejects.toMatchObject({
      code: "INVALID_INPUT",
    });
    expect(mocks.regionUpdateMany).not.toHaveBeenCalled();
    expect(mocks.candidateUpdateMany).not.toHaveBeenCalled();
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
