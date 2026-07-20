import { beforeEach, describe, expect, it, vi } from "vitest";

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
  getVisitAutomationProviderClaimMetrics,
  resetVisitAutomationProviderClaimMetricsForTest,
  runDurableVisitAutomationProvider,
} from "../provider-execution";

const ATTEMPT = {
  manifestId: "manifest-synthetic-claim",
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
}

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function harness(
  contenders: number,
  options: { replayClaimTransactionAfterCommit?: boolean } = {},
) {
  let execution: MemoryExecution | null = null;
  let rootReadCount = 0;
  let claimAttemptCount = 0;
  let lockTail = Promise.resolve();
  const committedReads = deferred();
  const claimAttempts = deferred();
  const layer = {
    layerRowId: "layer-synthetic-claim",
    inputSha256: "c".repeat(64),
    layerIdempotencyKey: "d".repeat(64),
    manifestId: ATTEMPT.manifestId,
    manifestVersion: ATTEMPT.manifestVersion,
    practiceId: "practice-synthetic-claim",
    visitId: "visit-synthetic-claim",
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
      findUnique: vi.fn(async () => (execution ? { ...execution } : null)),
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
          id: "execution-synthetic-claim",
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

  async function serial<T>(callback: () => Promise<T>): Promise<T> {
    const previous = lockTail;
    const release = deferred();
    lockTail = release.promise;
    await previous;
    try {
      return await callback();
    } finally {
      release.resolve();
    }
  }

  mocks.transaction.mockImplementation(async (input) =>
    serial(async () => {
      if (
        input.operation === "transition_visit_automation_provider_in_flight" ||
        input.operation === "claim_visit_automation_provider_execution"
      ) {
        claimAttemptCount += 1;
        if (claimAttemptCount === contenders) claimAttempts.resolve();
      }
      const first = await input.transaction(tx);
      if (
        input.operation === "claim_visit_automation_provider_execution" &&
        options.replayClaimTransactionAfterCommit
      ) {
        return input.transaction(tx);
      }
      return first;
    }),
  );
  mocks.rootFind.mockImplementation(
    async (args?: { where?: { id?: string; claimId?: string } }) => {
      if (
        args?.where?.claimId !== undefined &&
        execution?.claimId !== args.where.claimId
      ) {
        return null;
      }
      const snapshot = execution ? { ...execution } : null;
      rootReadCount += 1;
      if (rootReadCount === contenders) committedReads.resolve();
      if (rootReadCount <= contenders) await committedReads.promise;
      return snapshot;
    },
  );

  return {
    claimAttempts: claimAttempts.promise,
    execution: () => execution,
    replaceClaimWithNonOwner: () => {
      if (!execution || execution.status !== "IN_FLIGHT") {
        throw new Error("synthetic execution has no active owner");
      }
      execution = {
        ...execution,
        claimId: "e".repeat(64),
      };
    },
  };
}

function providerInput() {
  return {
    attempt: ATTEMPT,
    layerId: "icd_coding" as const,
    visitId: "visit-synthetic-claim",
    userId: "doctor-synthetic-claim",
    practiceId: "practice-synthetic-claim",
    descriptor: {
      provider: "anthropic" as const,
      model: "synthetic-model-v1",
      operationVersion: "l7a-v1",
    },
  };
}

describe("durable provider claim ownership", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.context.mockReturnValue(null);
    process.env.MOCK_AI_CALLS = "true";
    resetVisitAutomationProviderClaimMetricsForTest();
  });

  it("allows exactly one provider invocation after two committed RESERVED reads", async () => {
    const state = harness(2);
    const provider = vi.fn(async () => {
      await state.claimAttempts;
      return { codes: [{ code: "Z00.00" }] };
    });

    const results = await Promise.all([
      runDurableVisitAutomationProvider({
        ...providerInput(),
        invoke: provider,
      }),
      runDurableVisitAutomationProvider({
        ...providerInput(),
        invoke: provider,
      }),
    ]);

    expect(provider).toHaveBeenCalledTimes(1);
    expect(results.filter((result) => result.reused)).toHaveLength(1);
    expect(results.every((result) => !("claimId" in result))).toBe(true);
    expect(getVisitAutomationProviderClaimMetrics()).toMatchObject({
      claimedByCaller: 1,
      alreadyInProgress: 1,
    });
    expect(state.execution()).toMatchObject({
      status: "SUCCEEDED",
      invocationCount: 1,
    });
  });

  it("allows one claim owner when twenty workers race for one reservation", async () => {
    const contenders = 20;
    const state = harness(contenders);
    const provider = vi.fn(async () => {
      await state.claimAttempts;
      return { codes: [{ code: "Z00.00" }] };
    });

    const results = await Promise.all(
      Array.from({ length: contenders }, () =>
        runDurableVisitAutomationProvider({
          ...providerInput(),
          invoke: provider,
        }),
      ),
    );

    expect(provider).toHaveBeenCalledTimes(1);
    expect(results.filter((result) => !result.reused)).toHaveLength(1);
    expect(results.filter((result) => result.reused)).toHaveLength(19);
    expect(getVisitAutomationProviderClaimMetrics()).toMatchObject({
      claimedByCaller: 1,
      alreadyInProgress: 19,
    });
    expect(state.execution()).toMatchObject({
      status: "SUCCEEDED",
      invocationCount: 1,
    });
  });

  it("does not let a non-owner persist a successful result", async () => {
    const state = harness(1);
    const provider = vi.fn(async () => {
      state.replaceClaimWithNonOwner();
      return { codes: [{ code: "Z00.00" }] };
    });

    await expect(
      runDurableVisitAutomationProvider({
        ...providerInput(),
        invoke: provider,
      }),
    ).rejects.toThrow(/provider result persistence/iu);
    expect(provider).toHaveBeenCalledTimes(1);
    expect(state.execution()).toMatchObject({
      status: "IN_FLIGHT",
      resultPayload: null,
      resultSha256: null,
    });
  });

  it("does not let a non-owner persist a provider failure", async () => {
    const state = harness(1);
    const provider = vi.fn(async () => {
      state.replaceClaimWithNonOwner();
      throw new Error("synthetic provider failure");
    });

    await expect(
      runDurableVisitAutomationProvider({
        ...providerInput(),
        invoke: provider,
      }),
    ).rejects.toMatchObject({
      code: "VISIT_AUTOMATION_PROVIDER_EXECUTION_STALE",
    });
    expect(provider).toHaveBeenCalledTimes(1);
    expect(state.execution()).toMatchObject({
      status: "IN_FLIGHT",
      resultPayload: null,
      resultSha256: null,
    });
  });

  it("keeps the same owner across a complete-transaction acknowledgement retry", async () => {
    const state = harness(1, { replayClaimTransactionAfterCommit: true });
    const provider = vi.fn(async () => ({ codes: [{ code: "Z00.00" }] }));

    const result = await runDurableVisitAutomationProvider({
      ...providerInput(),
      invoke: provider,
    });

    expect(result).toMatchObject({ reused: false });
    expect(result).not.toHaveProperty("claimId");
    expect(provider).toHaveBeenCalledTimes(1);
    expect(state.execution()).toMatchObject({
      status: "SUCCEEDED",
      invocationCount: 1,
    });
  });
});
