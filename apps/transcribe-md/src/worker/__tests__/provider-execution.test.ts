import { beforeEach, describe, expect, it, vi } from "vitest";

import { captureAutomationLayerVisitMutation } from "../automation-layer-effects";

const mocks = vi.hoisted(() => {
  class LiveAuthorityRevokedError extends Error {}
  return {
    context: vi.fn(),
    rootFind: vi.fn(),
    transaction: vi.fn(),
    terminalize: vi.fn(),
    LiveAuthorityRevokedError,
  };
});

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
  runVisitAutomationRevokedAuthorityTerminalization: mocks.terminalize,
  VisitAutomationLiveAuthorityRevokedError: mocks.LiveAuthorityRevokedError,
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
  claimId: string | null;
  claimedAt: Date | null;
  resultPayload: unknown;
  resultSha256: string | null;
  resultVersion: string | null;
  failureCode: string | null;
}

function harness() {
  let execution: MemoryExecution | null = null;
  let failResultPersistence = false;
  const authorityRejectedOperations = new Set<string>();
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
    $queryRaw: vi.fn(
      async (query: {
        strings?: readonly string[];
        values?: readonly unknown[];
      }) => {
        const sql = query.strings?.join("?") ?? "";
        if (
          sql.includes('INSERT INTO "visit_automation_provider_executions"')
        ) {
          if (execution) return [];
          trace.push("reservation-created");
          execution = {
            id: String(query.values?.[0]),
            practiceId: String(query.values?.[1]),
            visitId: String(query.values?.[2]),
            manifestId: String(query.values?.[3]),
            automationLayerId: String(query.values?.[4]),
            stagingAdmissionId: (query.values?.[5] as null | undefined) ?? null,
            stagingRunId: (query.values?.[6] as null | undefined) ?? null,
            inputSha256: String(query.values?.[7]),
            provider: String(query.values?.[8]),
            providerMode: String(query.values?.[9]),
            model: String(query.values?.[10]),
            operationVersion: String(query.values?.[11]),
            idempotencyKey: String(query.values?.[12]),
            status: "RESERVED",
            invocationCount: 0,
            claimId: null,
            claimedAt: null,
            resultPayload: null,
            resultSha256: null,
            resultVersion: null,
            failureCode: null,
          };
          return [{ ...execution }];
        }
        if (
          sql.includes('UPDATE "visit_automation_provider_executions"') &&
          sql.includes('"claimId" IS NULL')
        ) {
          const claimId = String(query.values?.[0]);
          const executionId = String(query.values?.[1]);
          if (
            !execution ||
            execution.id !== executionId ||
            execution.status !== "RESERVED" ||
            execution.claimId !== null
          ) {
            return [];
          }
          execution = {
            ...execution,
            status: "IN_FLIGHT",
            claimId,
            claimedAt: new Date(),
            invocationCount: 1,
          };
          return [
            {
              id: execution.id,
              idempotencyKey: execution.idempotencyKey,
              claimId,
            },
          ];
        }
        if (
          sql.includes('SELECT "id", "idempotencyKey"') &&
          sql.includes('"claimId" =')
        ) {
          const executionId = String(query.values?.[0]);
          const claimId = String(query.values?.[1]);
          return execution?.id === executionId &&
            execution.status === "IN_FLIGHT" &&
            execution.claimId === claimId
            ? [{ id: execution.id, idempotencyKey: execution.idempotencyKey }]
            : [];
        }
        if (sql.includes("visit_automation_provider_executions")) {
          return execution ? [{ ...execution }] : [];
        }
        return [layer];
      },
    ),
    visitAutomationProviderExecution: {
      findFirst: vi.fn(
        async ({ where }: { where: { id?: string; claimId?: string } }) =>
          execution &&
          (where.id === undefined || execution.id === where.id) &&
          (where.claimId === undefined || execution.claimId === where.claimId)
            ? { ...execution }
            : null,
      ),
      create: vi.fn(async ({ data }: { data: Record<string, unknown> }) => {
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
          claimId: null,
          claimedAt: null,
          resultPayload: null,
          resultSha256: null,
          resultVersion: null,
          failureCode: null,
        };
        return { ...execution };
      }),
      update: vi.fn(async ({ data }: { data: Record<string, unknown> }) => {
        if (!execution) throw new Error("missing synthetic execution");
        execution = { ...execution, ...data } as MemoryExecution;
        return { ...execution };
      }),
      updateMany: vi.fn(
        async ({
          where,
          data,
        }: {
          where: { id: string; status?: string; claimId?: string | null };
          data: Record<string, unknown>;
        }) => {
          if (
            !execution ||
            execution.id !== where.id ||
            (where.status !== undefined && execution.status !== where.status) ||
            (where.claimId !== undefined && execution.claimId !== where.claimId)
          ) {
            return { count: 0 };
          }
          execution = { ...execution, ...data } as MemoryExecution;
          return { count: 1 };
        },
      ),
    },
  };
  mocks.rootFind.mockImplementation(
    async (args?: { where?: { id?: string; claimId?: string } }) => {
      trace.push("committed-reread");
      if (
        args?.where?.claimId !== undefined &&
        execution?.claimId !== args.where.claimId
      ) {
        return null;
      }
      return execution ? { ...execution } : null;
    },
  );
  mocks.transaction.mockImplementation(async (input) => {
    trace.push(`transaction:${input.operation}`);
    if (authorityRejectedOperations.has(input.operation)) {
      throw new mocks.LiveAuthorityRevokedError();
    }
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
  mocks.terminalize.mockImplementation(async (input) => input.transaction(tx));
  return {
    trace,
    execution: () => execution,
    failResultPersistence: () => {
      failResultPersistence = true;
    },
    rejectAuthorityAt: (operation: string) => {
      authorityRejectedOperations.add(operation);
    },
    restoreAuthority: () => {
      authorityRejectedOperations.clear();
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

  it("terminalizes a reserved row when exact compilation authority is revoked before claim", async () => {
    const state = harness();
    state.rejectAuthorityAt("claim_visit_automation_provider_execution");
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

    await expect(
      runDurableVisitAutomationProvider(input),
    ).rejects.toBeInstanceOf(mocks.LiveAuthorityRevokedError);
    expect(provider).not.toHaveBeenCalled();
    expect(state.trace).toContain(
      "transaction:claim_visit_automation_provider_execution",
    );
    expect(state.execution()).toMatchObject({
      status: "FAILED",
      invocationCount: 0,
      claimId: null,
      failureCode: "AUTHORITY_REVOKED_BEFORE_PROVIDER",
      resultPayload: null,
    });

    state.restoreAuthority();
    await expect(
      runDurableVisitAutomationProvider(input),
    ).rejects.toBeInstanceOf(VisitAutomationProviderExecutionError);
    expect(provider).not.toHaveBeenCalled();
  });

  it("marks the caller-owned invocation unknown when source/receipt authority changes after provider return", async () => {
    const state = harness();
    state.rejectAuthorityAt("persist_visit_automation_provider_result");
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

    await expect(
      runDurableVisitAutomationProvider(input),
    ).rejects.toBeInstanceOf(mocks.LiveAuthorityRevokedError);
    expect(provider).toHaveBeenCalledTimes(1);
    expect(state.trace).toContain(
      "transaction:persist_visit_automation_provider_result",
    );
    expect(state.execution()).toMatchObject({
      status: "UNKNOWN_OUTCOME",
      invocationCount: 1,
      failureCode: "AUTHORITY_REVOKED_AFTER_PROVIDER",
      resultPayload: null,
      resultSha256: null,
    });

    state.restoreAuthority();
    await expect(
      runDurableVisitAutomationProvider(input),
    ).rejects.toBeInstanceOf(VisitAutomationProviderExecutionError);
    expect(provider).toHaveBeenCalledTimes(1);
  });

  it("refuses committed-result reuse while compilation authority is revoked", async () => {
    const state = harness();
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
    await expect(
      runDurableVisitAutomationProvider(input),
    ).resolves.toMatchObject({ reused: false });

    state.rejectAuthorityAt("reserve_visit_automation_provider_execution");
    await expect(
      runDurableVisitAutomationProvider(input),
    ).rejects.toBeInstanceOf(mocks.LiveAuthorityRevokedError);
    expect(provider).toHaveBeenCalledTimes(1);
    expect(state.trace).toContain(
      "transaction:reserve_visit_automation_provider_execution",
    );
    expect(state.execution()?.status).toBe("SUCCEEDED");

    state.restoreAuthority();
    await expect(
      runDurableVisitAutomationProvider(input),
    ).resolves.toMatchObject({ reused: true });
    expect(provider).toHaveBeenCalledTimes(1);
  });
});
