import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  markRunning: vi.fn(),
  recordSuccess: vi.fn(),
  recordFailure: vi.fn(),
}));

vi.mock("../automation-manifest", () => ({
  markVisitAutomationLayerRunning: mocks.markRunning,
  recordVisitAutomationLayerSuccess: mocks.recordSuccess,
  recordVisitAutomationLayerFailure: mocks.recordFailure,
}));

import {
  AutomationFanoutPersistenceError,
  runAutomationFanout,
} from "../run-automation-fanout";

const ATTEMPT = {
  manifestId: "manifest-synthetic-1",
  manifestVersion: 1,
  soapVersion: 1,
  soapSha256: "a".repeat(64),
  sourceSha256: "b".repeat(64),
  policy: [],
};

describe("controlled automation fanout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.markRunning.mockResolvedValue({ alreadySucceeded: false });
    mocks.recordSuccess.mockResolvedValue(undefined);
    mocks.recordFailure.mockResolvedValue(undefined);
  });

  it("records every configured provider rejection", async () => {
    const first = new Error("synthetic provider failure one");
    const second = new Error("synthetic provider failure two");
    const outcomes = await runAutomationFanout({
      attempt: ATTEMPT,
      visitId: "visit-synthetic-1",
      userId: "doctor-synthetic-1",
      practiceId: "practice-synthetic-1",
      tasks: [
        {
          key: "icd_coding",
          enabled: true,
          run: async () => Promise.reject(first),
        },
        {
          key: "rx_drafting",
          enabled: true,
          run: async () => Promise.reject(second),
        },
      ],
    });

    expect(mocks.recordFailure).toHaveBeenCalledTimes(2);
    expect(mocks.recordFailure).toHaveBeenCalledWith(
      expect.objectContaining({ layerId: "icd_coding", error: first }),
    );
    expect(mocks.recordFailure).toHaveBeenCalledWith(
      expect.objectContaining({ layerId: "rx_drafting", error: second }),
    );
    expect(outcomes).toMatchObject({
      icd_coding: { status: "failed" },
      rx_drafting: { status: "failed" },
    });
  });

  it("serializes database-owning layer tasks in deterministic order", async () => {
    let active = 0;
    let maximumActive = 0;
    const calls: string[] = [];
    const task = (key: "icd_coding" | "cpt_coding") => ({
      key,
      enabled: true,
      run: async () => {
        active += 1;
        maximumActive = Math.max(maximumActive, active);
        calls.push(key);
        await Promise.resolve();
        active -= 1;
        return { synthetic: true };
      },
    });
    await runAutomationFanout({
      attempt: ATTEMPT,
      visitId: "visit-synthetic-1",
      userId: "doctor-synthetic-1",
      practiceId: "practice-synthetic-1",
      tasks: [task("icd_coding"), task("cpt_coding")],
    });
    expect(maximumActive).toBe(1);
    expect(calls).toEqual(["icd_coding", "cpt_coding"]);
  });

  it("surfaces every outcome-persistence rejection to the worker", async () => {
    mocks.recordSuccess.mockRejectedValue(
      new Error("synthetic database commit unavailable"),
    );
    await expect(
      runAutomationFanout({
        attempt: ATTEMPT,
        visitId: "visit-synthetic-1",
        userId: "doctor-synthetic-1",
        practiceId: "practice-synthetic-1",
        tasks: [
          {
            key: "icd_coding",
            enabled: true,
            run: async () => ({ codes: [{ code: "Z00.00" }] }),
          },
        ],
      }),
    ).rejects.toEqual(
      expect.objectContaining<Partial<AutomationFanoutPersistenceError>>({
        code: "AUTOMATION_FANOUT_PERSISTENCE_FAILED",
        failedLayerIds: ["icd_coding"],
      }),
    );
  });

  it("does not invoke a provider for an already committed result", async () => {
    mocks.markRunning.mockResolvedValue({ alreadySucceeded: true });
    const provider = vi.fn();
    await runAutomationFanout({
      attempt: ATTEMPT,
      visitId: "visit-synthetic-1",
      userId: "doctor-synthetic-1",
      practiceId: "practice-synthetic-1",
      tasks: [{ key: "icd_coding", enabled: true, run: provider }],
    });
    expect(provider).not.toHaveBeenCalled();
    expect(mocks.recordSuccess).not.toHaveBeenCalled();
  });

  it("persists a validator rejection instead of treating it as success", async () => {
    await runAutomationFanout({
      attempt: ATTEMPT,
      visitId: "visit-synthetic-1",
      userId: "doctor-synthetic-1",
      practiceId: "practice-synthetic-1",
      tasks: [
        {
          key: "cpt_coding",
          enabled: true,
          run: async () => ({ procedures: [] }),
          validate: () => {
            throw new Error("synthetic required output missing");
          },
        },
      ],
    });
    expect(mocks.recordFailure).toHaveBeenCalledTimes(1);
    expect(mocks.recordSuccess).not.toHaveBeenCalled();
  });
});
