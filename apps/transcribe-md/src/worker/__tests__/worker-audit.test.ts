import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  context: vi.fn(),
  transaction: vi.fn(),
  enqueue: vi.fn(),
}));

vi.mock("@meddoc/ai", () => ({
  getTemplateTwinSyntheticQaProviderContext: mocks.context,
}));

vi.mock("@/worker/automation-locks", () => ({
  runVisitAutomationTransaction: mocks.transaction,
}));

vi.mock("@/lib/template-twin/audit-outbox", () => ({
  enqueueIdempotentTemplateTwinAudit: mocks.enqueue,
}));

import { logWorkerAudit } from "../worker-audit";

describe("durable worker audit boundary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.context.mockReturnValue(null);
    mocks.enqueue.mockResolvedValue("CREATED");
    mocks.transaction.mockImplementation(
      async (input: {
        transaction: (tx: object) => Promise<void>;
      }): Promise<void> => input.transaction({ syntheticTx: true }),
    );
  });

  it("routes an ordinary worker audit through canonical locks and the outbox", async () => {
    await logWorkerAudit({
      action: "VISIT_AUTOMATION_INCOMPLETE",
      targetType: "TranscribeVisit",
      targetId: "visit-synthetic-1",
      userId: "doctor-synthetic-1",
      practiceId: "practice-synthetic-1",
      success: false,
      metadata: { layer: "l7a", reasonCode: "SYNTHETIC_FAILURE" },
    });
    expect(mocks.transaction).toHaveBeenCalledWith(
      expect.objectContaining({
        operation: "enqueue_visit_worker_audit",
        visitId: "visit-synthetic-1",
        userId: "doctor-synthetic-1",
        practiceId: "practice-synthetic-1",
      }),
    );
    expect(mocks.enqueue).toHaveBeenCalledTimes(1);
  });

  it("propagates durable outbox failure instead of swallowing it", async () => {
    mocks.enqueue.mockRejectedValue(new Error("synthetic outbox unavailable"));
    await expect(
      logWorkerAudit({
        action: "VISIT_AUTOMATION_INCOMPLETE",
        targetType: "TranscribeVisit",
        targetId: "visit-synthetic-1",
        userId: "doctor-synthetic-1",
        practiceId: "practice-synthetic-1",
      }),
    ).rejects.toThrow("synthetic outbox unavailable");
  });

  it("rejects an audit identity outside the admitted staging visit", async () => {
    mocks.context.mockReturnValue({
      visitId: "visit-synthetic-1",
      practiceId: "practice-synthetic-1",
      runId: "run-synthetic-1",
      attempt: 1,
    });
    await expect(
      logWorkerAudit({
        action: "VISIT_AUTOMATION_INCOMPLETE",
        targetType: "TranscribeVisit",
        targetId: "visit-synthetic-other",
        userId: "doctor-synthetic-1",
        practiceId: "practice-synthetic-1",
      }),
    ).rejects.toThrow("identity mismatch");
    expect(mocks.transaction).not.toHaveBeenCalled();
  });
});
