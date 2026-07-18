import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  markRunning: vi.fn(),
  recordSuccess: vi.fn(),
  recordFailure: vi.fn(),
  runProvider: vi.fn(),
}));

vi.mock("../automation-manifest", () => ({
  markVisitAutomationLayerRunning: mocks.markRunning,
  recordVisitAutomationLayerSuccess: mocks.recordSuccess,
  recordVisitAutomationLayerFailure: mocks.recordFailure,
}));

vi.mock("../provider-execution", () => ({
  runDurableVisitAutomationProvider: mocks.runProvider,
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
const PROVIDER = {
  provider: "anthropic" as const,
  model: "synthetic-model-v1",
  operationVersion: "synthetic-layer-v1",
};

describe("controlled automation fanout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.markRunning.mockResolvedValue({ alreadySucceeded: false });
    mocks.recordSuccess.mockResolvedValue(undefined);
    mocks.recordFailure.mockResolvedValue(undefined);
    mocks.runProvider.mockImplementation(async (input) => {
      const output = await input.invoke("e".repeat(64));
      input.validate?.(output);
      return {
        executionId: "execution-synthetic-1",
        output,
        effects: { visitMutations: [], audits: [] },
        reused: false,
      };
    });
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
          provider: PROVIDER,
          run: async () => Promise.reject(first),
        },
        {
          key: "rx_drafting",
          enabled: true,
          provider: PROVIDER,
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
      provider: PROVIDER,
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
            provider: PROVIDER,
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

  it("reuses a committed provider result after clinical projection exhaustion", async () => {
    const provider = vi.fn().mockResolvedValue({ codes: [{ code: "Z00.00" }] });
    let committed: unknown;
    mocks.runProvider.mockImplementation(async (input) => {
      if (committed === undefined)
        committed = await input.invoke("e".repeat(64));
      return {
        executionId: "execution-synthetic-retry",
        output: committed,
        effects: { visitMutations: [], audits: [] },
        reused: provider.mock.calls.length === 1,
      };
    });
    mocks.recordSuccess.mockRejectedValueOnce(
      new Error("synthetic projection commit exhausted"),
    );
    const request = {
      attempt: ATTEMPT,
      visitId: "visit-synthetic-1",
      userId: "doctor-synthetic-1",
      practiceId: "practice-synthetic-1",
      tasks: [
        {
          key: "icd_coding" as const,
          enabled: true,
          provider: PROVIDER,
          run: provider,
        },
      ],
    };

    await expect(runAutomationFanout(request)).rejects.toBeInstanceOf(
      AutomationFanoutPersistenceError,
    );
    await expect(runAutomationFanout(request)).resolves.toMatchObject({
      icd_coding: { status: "ok" },
    });
    expect(provider).toHaveBeenCalledTimes(1);
    expect(mocks.recordSuccess).toHaveBeenCalledTimes(2);
  });

  it("does not invoke a provider for an already committed result", async () => {
    mocks.markRunning.mockResolvedValue({ alreadySucceeded: true });
    const provider = vi.fn();
    await runAutomationFanout({
      attempt: ATTEMPT,
      visitId: "visit-synthetic-1",
      userId: "doctor-synthetic-1",
      practiceId: "practice-synthetic-1",
      tasks: [
        {
          key: "icd_coding",
          enabled: true,
          provider: PROVIDER,
          run: provider,
        },
      ],
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
          provider: PROVIDER,
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
