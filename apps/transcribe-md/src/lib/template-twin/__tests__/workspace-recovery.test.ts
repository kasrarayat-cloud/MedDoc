import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ findFirst: vi.fn() }));

vi.mock("@meddoc/db", () => ({
  default: { noteTemplate: { findFirst: mocks.findFirst } },
}));

import { findTemplateTwinWorkspaceRecoveryCandidate } from "../workspace-recovery";

const INPUT = {
  noteTemplateId: "template-v1",
  doctorId: "doctor-synthetic-1",
  practiceId: "practice-synthetic-1",
};

beforeEach(() => vi.clearAllMocks());

describe("Template Twin workspace recovery", () => {
  it("returns only a newer same-lineage, same-source candidate", async () => {
    mocks.findFirst
      .mockResolvedValueOnce({
        id: "template-v1",
        lineageId: "lineage-1",
        version: 1,
        templateTwinCompiledVersion: {
          sourceArtifactId: "source-1",
          sourceArtifact: { practiceId: INPUT.practiceId },
        },
      })
      .mockResolvedValueOnce({ id: "template-v3", version: 3 });

    await expect(
      findTemplateTwinWorkspaceRecoveryCandidate(INPUT),
    ).resolves.toEqual({ id: "template-v3", version: 3 });
    expect(mocks.findFirst).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        where: expect.objectContaining({
          id: { not: "template-v1" },
          doctorId: INPUT.doctorId,
          lineageId: "lineage-1",
          version: { gt: 1 },
          templateTwinCompiledVersion: {
            is: {
              sourceArtifactId: "source-1",
              sourceArtifact: { is: { practiceId: INPUT.practiceId } },
            },
          },
        }),
      }),
    );
  });

  it("fails closed before successor lookup when source practice differs", async () => {
    mocks.findFirst.mockResolvedValueOnce({
      id: "template-v1",
      lineageId: "lineage-1",
      version: 1,
      templateTwinCompiledVersion: {
        sourceArtifactId: "source-1",
        sourceArtifact: { practiceId: "practice-foreign" },
      },
    });

    await expect(
      findTemplateTwinWorkspaceRecoveryCandidate(INPUT),
    ).resolves.toBeNull();
    expect(mocks.findFirst).toHaveBeenCalledTimes(1);
  });

  it("does not reinterpret a missing or unowned version as recoverable", async () => {
    mocks.findFirst.mockResolvedValueOnce(null);

    await expect(
      findTemplateTwinWorkspaceRecoveryCandidate(INPUT),
    ).resolves.toBeNull();
    expect(mocks.findFirst).toHaveBeenCalledTimes(1);
  });
});
