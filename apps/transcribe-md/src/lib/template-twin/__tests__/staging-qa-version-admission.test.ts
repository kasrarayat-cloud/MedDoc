import type { Prisma } from "@prisma/client";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ enqueueAudit: vi.fn() }));

vi.mock("../audit-outbox", () => ({
  enqueueTemplateTwinAudit: mocks.enqueueAudit,
}));

import {
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
} from "../staging-qa-fixture-contract";
import { createTemplateTwinStagingQaVersionAdmission } from "../staging-qa-version-admission";

const ACTOR = {
  userId: "doctor-synthetic-1",
  userEmail: "doctor@synthetic.test",
  practiceId: "practice-synthetic-1",
  rolloutToken: {
    practiceId: "practice-synthetic-1",
    globalGeneration: BigInt(4),
    practiceGeneration: BigInt(7),
  },
};
const NOW = new Date("2026-07-19T04:00:00.000Z");

function transaction() {
  return {
    templateTwinSyntheticQaAdmission: {
      findFirst: vi
        .fn()
        .mockResolvedValueOnce({
          id: "admission-source",
          expiresAt: new Date("2026-07-20T04:00:00.000Z"),
        })
        .mockResolvedValueOnce(null),
      create: vi.fn().mockResolvedValue({ id: "admission-fork" }),
      update: vi.fn().mockResolvedValue({ id: "admission-fork" }),
    },
  };
}

beforeEach(() => vi.clearAllMocks());

describe("synthetic QA version admission", () => {
  it("atomically binds a fresh lifecycle capability to the forked version", async () => {
    const tx = transaction();

    await expect(
      createTemplateTwinStagingQaVersionAdmission({
        tx: tx as unknown as Prisma.TransactionClient,
        actor: ACTOR,
        source: {
          noteTemplateId: "template-v1",
          sourceArtifactId: "source-1",
          sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
          sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
        },
        target: { noteTemplateId: "template-v2", version: 2 },
        now: NOW,
      }),
    ).resolves.toBe("admission-fork");

    expect(tx.templateTwinSyntheticQaAdmission.create).toHaveBeenCalledWith({
      data: expect.objectContaining({
        practiceId: ACTOR.practiceId,
        actorId: ACTOR.userId,
        providerMode: "SYNTHETIC_LIFECYCLE",
        purpose: "UPLOAD",
        phase: "ADMITTED",
        sourceArtifactId: "source-1",
        noteTemplateId: "template-v2",
        noteTemplateVersion: 2,
        pinnedGlobalRolloutGeneration: BigInt(4),
        pinnedPracticeRolloutGeneration: BigInt(7),
      }),
      select: { id: true },
    });
    expect(tx.templateTwinSyntheticQaAdmission.update).toHaveBeenNthCalledWith(
      1,
      {
        where: { id: "admission-fork" },
        data: { phase: "SOURCE_VERIFIED", sourceVerifiedAt: NOW },
      },
    );
    expect(tx.templateTwinSyntheticQaAdmission.update).toHaveBeenNthCalledWith(
      2,
      {
        where: { id: "admission-fork" },
        data: { phase: "TEMPLATE_LINKED", templateLinkedAt: NOW },
      },
    );
    expect(mocks.enqueueAudit).toHaveBeenLastCalledWith(
      tx,
      expect.objectContaining({
        action: "TEMPLATE_TWIN_STAGING_QA_ADMISSION_ADVANCED",
        actorId: ACTOR.userId,
        targetId: "admission-fork",
        metadata: expect.objectContaining({
          sourceAdmissionId: "admission-source",
          sourceTemplateId: "template-v1",
          noteTemplateId: "template-v2",
        }),
      }),
    );
  });

  it("does nothing for an arbitrary source", async () => {
    const tx = transaction();

    await expect(
      createTemplateTwinStagingQaVersionAdmission({
        tx: tx as unknown as Prisma.TransactionClient,
        actor: ACTOR,
        source: {
          noteTemplateId: "ordinary-v1",
          sourceArtifactId: "ordinary-source",
          sha256: "f".repeat(64),
          sizeBytes: 1234,
        },
        target: { noteTemplateId: "ordinary-v2", version: 2 },
        now: NOW,
      }),
    ).resolves.toBeNull();
    expect(
      tx.templateTwinSyntheticQaAdmission.findFirst,
    ).not.toHaveBeenCalled();
    expect(tx.templateTwinSyntheticQaAdmission.create).not.toHaveBeenCalled();
    expect(mocks.enqueueAudit).not.toHaveBeenCalled();
  });

  it("fails closed when the source capability is stale or absent", async () => {
    const tx = transaction();
    tx.templateTwinSyntheticQaAdmission.findFirst.mockReset();
    tx.templateTwinSyntheticQaAdmission.findFirst.mockResolvedValue(null);

    await expect(
      createTemplateTwinStagingQaVersionAdmission({
        tx: tx as unknown as Prisma.TransactionClient,
        actor: ACTOR,
        source: {
          noteTemplateId: "template-v1",
          sourceArtifactId: "source-1",
          sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
          sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
        },
        target: { noteTemplateId: "template-v2", version: 2 },
        now: NOW,
      }),
    ).rejects.toThrow("recoverable lifecycle admission");
    expect(tx.templateTwinSyntheticQaAdmission.create).not.toHaveBeenCalled();
  });
});
