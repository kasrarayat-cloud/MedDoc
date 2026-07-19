import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findCandidate: vi.fn(),
  readWorkspace: vi.fn(),
  lifecycleGuard: vi.fn((input: { operation: () => unknown }) =>
    input.operation(),
  ),
}));

vi.mock("../workspace-recovery", () => ({
  findTemplateTwinWorkspaceRecoveryCandidate: mocks.findCandidate,
}));
vi.mock("../workspace-read", () => ({
  readTemplateTwinWorkspace: mocks.readWorkspace,
}));
vi.mock("../staging-qa-lifecycle-guard", () => ({
  TemplateTwinStagingQaLifecycleGuardError:
    class TemplateTwinStagingQaLifecycleGuardError extends Error {},
  runWithTemplateTwinStagingQaLifecycleGuard: mocks.lifecycleGuard,
}));

import { TemplateTwinStagingQaLifecycleGuardError } from "../staging-qa-lifecycle-guard";
import { readGuardedTemplateTwinWorkspaceRecovery } from "../workspace-recovery-guarded";

const ACTOR = {
  userId: "doctor-recovery-1",
  practiceId: "practice-recovery-1",
  rolloutToken: {
    practiceId: "practice-recovery-1",
    globalGeneration: BigInt(3),
    practiceGeneration: BigInt(5),
  },
};

function workspace(canEdit = true) {
  return {
    template: { id: "template-v2", version: 2 },
    canEdit,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.findCandidate.mockResolvedValue({ id: "template-v2", version: 2 });
  mocks.readWorkspace.mockResolvedValue(workspace());
  mocks.lifecycleGuard.mockImplementation(
    (input: { operation: () => unknown }) => input.operation(),
  );
});

describe("guarded Template Twin workspace recovery", () => {
  it("returns only an editable successor read through its own capability", async () => {
    await expect(
      readGuardedTemplateTwinWorkspaceRecovery({
        noteTemplateId: "template-v1",
        actor: ACTOR,
      }),
    ).resolves.toEqual({
      candidate: { id: "template-v2", version: 2 },
      workspace: workspace(),
    });
    expect(mocks.lifecycleGuard).toHaveBeenCalledWith(
      expect.objectContaining({
        noteTemplateId: "template-v2",
        purpose: "workspace-recovery-read",
      }),
    );
    expect(mocks.readWorkspace).toHaveBeenCalledWith({
      noteTemplateId: "template-v2",
      doctorId: ACTOR.userId,
      practiceId: ACTOR.practiceId,
    });
  });

  it("does not return a non-editable successor as a rebase target", async () => {
    mocks.readWorkspace.mockResolvedValue(workspace(false));
    await expect(
      readGuardedTemplateTwinWorkspaceRecovery({
        noteTemplateId: "template-v1",
        actor: ACTOR,
      }),
    ).resolves.toBeNull();
  });

  it("fails closed when the successor capability is stale", async () => {
    mocks.lifecycleGuard.mockRejectedValue(
      new TemplateTwinStagingQaLifecycleGuardError(),
    );
    await expect(
      readGuardedTemplateTwinWorkspaceRecovery({
        noteTemplateId: "template-v1",
        actor: ACTOR,
      }),
    ).resolves.toBeNull();
  });

  it("propagates database failures without misclassifying them as capability denial", async () => {
    mocks.readWorkspace.mockRejectedValue(new Error("synthetic database fault"));
    await expect(
      readGuardedTemplateTwinWorkspaceRecovery({
        noteTemplateId: "template-v1",
        actor: ACTOR,
      }),
    ).rejects.toThrow("synthetic database fault");
  });
});
