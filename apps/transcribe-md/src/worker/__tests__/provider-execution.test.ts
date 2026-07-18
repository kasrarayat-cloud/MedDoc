import { beforeEach, describe, expect, it, vi } from "vitest";

import { captureAutomationLayerVisitMutation } from "../automation-layer-effects";

const mocks = vi.hoisted(() => ({
  context: vi.fn(),
  rootFind: vi.fn(),
  transaction: vi.fn(),
}));

vi.mock("@meddoc/ai", () => ({
  getTemplateTwinSyntheticQaProviderContext: mocks.context,
}));

vi.mock("@meddoc/db", () => ({
  default: {
    visitAutomationProviderExecution: { findUnique: mocks.rootFind },
  },
}));

vi.mock("../automation-locks", () => ({
  runVisitAutomationTransaction: mocks.transaction,
}));

import {
  runDurableVisitAutomationProvider,
  VisitAutomationProviderExecutionError,
} from "../provider-execution";

const ATTEMPT = {
  manifestId: "manifest-synthetic-1",
  manifestVersion: 1,
  soapVersion: 1,
  soapSha256: "a".repeat(64),
  sourceSha256: "b".repeat(64),
  policy: [],
};

interface MemoryExecution {
  id: string;
  practiceId: string;
  visitId: string;
  manifestId: string;
  automationLayerId: string;
  stagingAdmissionId: null;
  stagingRunId: null;
  inputSha256: string;
  provider: string;
  providerMode: string;
  model: string;
  operationVersion: string;
  idempotencyKey: string;
  status: string;
  invocationCount: number;
  resultPayload: unknown;
  resultSha256: string | null;
  resultVersion: string | null;
}

function harness() {
  let execution: MemoryExecution | null = null;
  let failResultPersistence = false;
  const trace: string[] = [];
  const layer = {
    layerRowId: "layer-synthetic-1",
    inputSha256: "c".repeat(64),
    layerIdempotencyKey: "d".repeat(64),
    manifestId: ATTEMPT.manifestId,
    manifestVersion: ATTEMPT.manifestVersion,
    practiceId: "practice-synthetic-1",
    visitId: "visit-synthetic-1",
    stagingAdmissionId: null,
    stagingRunId: null,
  };
  const tx = {
    $queryRaw: vi.fn(async (query: { strings?: readonly string[] }) => {
      const sql = query.strings?.join("?") ?? "";
      if (sql.includes("visit_automation_provider_executions")) {
        return execution ? [{ ...execution }] : [];
      }
      return [layer];
    }),
    visitAutomationProviderExecution: {
      findFirst: vi.fn(async () => (execution ? { ...execution } : null)),
      create: vi.fn(async ({ data }: { data: Record<string, unknown> }) => {
        trace.push("reservation-created");
        execution = {
          id: "execution-synthetic-1",
          practiceId: String(data.practiceId),
          visitId: String(data.visitId),
          manifestId: String(data.manifestId),
          automationLayerId: String(data.automationLayerId),
          stagingAdmissionId: null,
          stagingRunId: null,
          inputSha256: String(data.inputSha256),
          provider: String(data.provider),
          providerMode: String(data.providerMode),
          model: String(data.model),
          operationVersion: String(data.operationVersion),
          idempotencyKey: String(data.idempotencyKey),
          status: "RESERVED",
          invocationCount: 0,
          resultPayload: null,
          resultSha256: null,
          resultVersion: null,
        };
        return { ...execution };
      }),
      update: vi.fn(async ({ data }: { data: Record<string, unknown> }) => {
        if (!execution) throw new Error("missing synthetic execution");
        execution = { ...execution, ...data } as MemoryExecution;
        return { ...execution };
      }),
    },
  };
  mocks.rootFind.mockImplementation(async () => {
    trace.push("committed-reread");
    return execution ? { ...execution } : null;
  });
  mocks.transaction.mockImplementation(async (input) => {
    trace.push(`transaction:${input.operation}`);
    if (
      input.operation === "persist_visit_automation_provider_result" &&
      failResultPersistence
    ) {
      throw Object.assign(new Error("synthetic persistence exhaustion"), {
        code: "P2034",
      });
    }
    return input.transaction(tx);
  });
  return {
    trace,
    execution: () => execution,
    failResultPersistence: () => {
      failResultPersistence = true;
    },
  };
}

describe("durable automation provider execution", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.context.mockReturnValue(null);
    process.env.MOCK_AI_CALLS = "true";
  });

  it("commits and independently rereads a reservation before invoking once", async () => {
    const state = harness();
    const provider = vi.fn(async (idempotencyKey: string) => {
      state.trace.push("provider-invoked");
      expect(idempotencyKey).toMatch(/^[a-f0-9]{64}$/u);
      expect(
        captureAutomationLayerVisitMutation({
          visitId: "visit-synthetic-1",
          userId: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
          data: { icdCodes: [{ code: "Z00.00" }] },
        }),
      ).toBe(true);
      return { codes: [{ code: "Z00.00" }] };
    });
    const input = {
      attempt: ATTEMPT,
      layerId: "icd_coding" as const,
      visitId: "visit-synthetic-1",
      userId: "doctor-synthetic-1",
      practiceId: "practice-synthetic-1",
      descriptor: {
        provider: "anthropic" as const,
        model: "synthetic-model-v1",
        operationVersion: "l7a-v1",
      },
      invoke: provider,
    };

    const first = await runDurableVisitAutomationProvider(input);
    const second = await runDurableVisitAutomationProvider(input);

    expect(first.reused).toBe(false);
    expect(second.reused).toBe(true);
    expect(provider).toHaveBeenCalledTimes(1);
    expect(state.execution()?.status).toBe("SUCCEEDED");
    expect(state.execution()?.invocationCount).toBe(1);
    expect(state.trace.indexOf("committed-reread")).toBeLessThan(
      state.trace.indexOf("provider-invoked"),
    );
    expect(second.effects.visitMutations).toHaveLength(1);
  });

  it("never repeats a call after an ambiguous post-provider persistence failure", async () => {
    const state = harness();
    state.failResultPersistence();
    const provider = vi.fn().mockResolvedValue({ codes: [{ code: "Z00.00" }] });
    const input = {
      attempt: ATTEMPT,
      layerId: "icd_coding" as const,
      visitId: "visit-synthetic-1",
      userId: "doctor-synthetic-1",
      practiceId: "practice-synthetic-1",
      descriptor: {
        provider: "anthropic" as const,
        model: "synthetic-model-v1",
        operationVersion: "l7a-v1",
      },
      invoke: provider,
    };

    await expect(runDurableVisitAutomationProvider(input)).rejects.toThrow(
      /persistence exhaustion/u,
    );
    await expect(
      runDurableVisitAutomationProvider(input),
    ).rejects.toBeInstanceOf(VisitAutomationProviderExecutionError);
    expect(provider).toHaveBeenCalledTimes(1);
    expect(state.execution()?.status).toBe("UNKNOWN_OUTCOME");
  });
});
