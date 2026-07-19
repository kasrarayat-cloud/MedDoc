import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  buildTemplateTwinProviderOwnershipReceipt,
  runTemplateTwinOwnedProvider,
  runWithTemplateTwinProviderOwnershipContext,
  TemplateTwinProviderOwnershipError,
  type TemplateTwinProviderOwnershipContext,
} from "../provider-ownership";

interface StoredRow extends Record<string, unknown> {
  id: string;
  ownershipKey: string;
  idempotencyKey: string;
  status: string;
  invocationCount: number;
  claimId: string | null;
  resultPayload: unknown;
  resultSha256: string | null;
  resultVersion: string | null;
}

function whereMatches(row: StoredRow, where: Record<string, unknown>): boolean {
  return Object.entries(where).every(([key, value]) => row[key] === value);
}

class MemoryProviderDatabase {
  readonly rows = new Map<string, StoredRow>();
  throwAfterSuccessfulCompletion = false;

  readonly templateTwinProviderExecution = {
    create: async (raw: unknown): Promise<StoredRow> => {
      const args = raw as { data: Record<string, unknown> };
      const duplicate = [...this.rows.values()].find(
        (row) =>
          row.ownershipKey === args.data.ownershipKey ||
          row.idempotencyKey === args.data.idempotencyKey,
      );
      if (duplicate) {
        throw Object.assign(new Error("synthetic unique conflict"), {
          code: "P2002",
        });
      }
      const row = {
        ...args.data,
        status: "RESERVED",
        invocationCount: 0,
        claimId: null,
        resultPayload: null,
        resultSha256: null,
        resultVersion: null,
      } as StoredRow;
      this.rows.set(row.id, row);
      return { ...row };
    },
    findUnique: async (raw: unknown): Promise<StoredRow | null> => {
      const args = raw as { where: Record<string, unknown> };
      const row = [...this.rows.values()].find((candidate) =>
        whereMatches(candidate, args.where),
      );
      return row ? { ...row } : null;
    },
    updateMany: async (raw: unknown): Promise<{ count: number }> => {
      const args = raw as {
        where: Record<string, unknown>;
        data: Record<string, unknown>;
      };
      const row = [...this.rows.values()].find((candidate) =>
        whereMatches(candidate, args.where),
      );
      if (!row) return { count: 0 };
      Object.assign(row, args.data);
      return { count: 1 };
    },
  };

  async $queryRaw<T>(): Promise<T> {
    return [] as T;
  }

  async $transaction<T>(
    callback: (tx: MemoryProviderDatabase) => Promise<T>,
  ): Promise<T> {
    const result = await callback(this);
    if (
      this.throwAfterSuccessfulCompletion &&
      [...this.rows.values()].some((row) => row.status === "SUCCEEDED")
    ) {
      this.throwAfterSuccessfulCompletion = false;
      throw new Error("synthetic commit acknowledgement lost");
    }
    return result;
  }
}

const CONTEXT: TemplateTwinProviderOwnershipContext = {
  practiceId: "practice-provider-owner",
  actorUserId: "doctor-provider-owner",
  visitId: "visit-provider-owner",
  scope: "VISIT_PIPELINE",
  logicalAttempt: 1,
  subjectId: "visit-provider-owner",
  subjectSha256: "1".repeat(64),
  sourceArtifactId: "source-provider-owner",
  compiledVersionId: "compiled-provider-owner",
  noteTemplateId: "template-provider-owner",
  noteTemplateVersion: 4,
  sourceLineageId: "lineage-provider-owner",
  sourceLineageVersion: 2,
  sourceSha256: "2".repeat(64),
  rolloutToken: {
    practiceId: "practice-provider-owner",
    globalGeneration: BigInt(7),
    practiceGeneration: BigInt(9),
    releaseId: "77777777-7777-4777-8777-777777777777",
    releaseIdentitySha256: "3".repeat(64),
    runtimeManifestSha256: "4".repeat(64),
    runtimeInstanceId: "worker-provider-owner-1",
  },
};

let sequence = 0;

function dependencies(
  database: MemoryProviderDatabase,
  input: {
    mode?: "LIVE" | "DETERMINISTIC_MOCK" | "SYNTHETIC_QA";
    rolloutCurrent?: boolean;
  } = {},
): NonNullable<Parameters<typeof runTemplateTwinOwnedProvider>[1]> {
  return {
    db: database,
    providerMode: () => input.mode ?? "DETERMINISTIC_MOCK",
    lockRollout: async () => input.rolloutCurrent ?? true,
    executionId: () => `provider-execution-${++sequence}`,
    claimId: () => `${sequence.toString(16).padStart(64, "0")}`,
    now: () => new Date("2026-07-19T17:20:00.000Z"),
    sleep: (milliseconds: number) =>
      new Promise((resolve) => setTimeout(resolve, milliseconds)),
    terminalWaitMs: 250,
    pollMs: 1,
  } as unknown as NonNullable<
    Parameters<typeof runTemplateTwinOwnedProvider>[1]
  >;
}

function providerInput(invoke: () => Promise<{ facts: string[] }>) {
  return {
    operation: "L3_EXTRACT_ENTITIES" as const,
    operationVersion: "l3-provider-owner-v1",
    provider: "anthropic",
    model: "claude-synthetic-1",
    providerConfiguration: { temperature: 0, maxTokens: 512 },
    inputIdentity: {
      purpose: "tm_entities",
      evidence: "private synthetic input must never enter the receipt",
    },
    invoke,
    validate: (output: unknown) => {
      if (
        !output ||
        typeof output !== "object" ||
        !Array.isArray((output as { facts?: unknown }).facts)
      ) {
        throw new Error("invalid synthetic provider result");
      }
      return output as { facts: string[] };
    },
  };
}

async function errorCode(promise: Promise<unknown>): Promise<string | null> {
  try {
    await promise;
    return null;
  } catch (error) {
    return error instanceof TemplateTwinProviderOwnershipError
      ? error.code
      : "UNEXPECTED";
  }
}

beforeEach(() => {
  sequence = 0;
});

describe("Template Twin exact provider ownership runtime", () => {
  it("leaves an ordinary provider call unchanged when no Twin context exists", async () => {
    const invoke = vi.fn(async (claim: { idempotencyKey?: string }) => ({
      facts: [claim.idempotencyKey ?? "ordinary"],
    }));

    const result = await runTemplateTwinOwnedProvider({
      ...providerInput(() => invoke({})),
      invoke,
    });

    expect(result).toEqual({ facts: ["ordinary"] });
    expect(invoke).toHaveBeenCalledOnce();
    expect(invoke).toHaveBeenCalledWith({});
  });

  it("admits exactly one concurrent provider invocation and reuses its committed result", async () => {
    const database = new MemoryProviderDatabase();
    let release!: () => void;
    let started!: () => void;
    const providerStarted = new Promise<void>((resolve) => {
      started = resolve;
    });
    const providerReleased = new Promise<void>((resolve) => {
      release = resolve;
    });
    const invoke = vi.fn(async () => {
      started();
      await providerReleased;
      return { facts: ["synthetic fact"] };
    });
    const run = () =>
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database),
        ),
      );

    const first = run();
    await providerStarted;
    const second = run();
    await new Promise((resolve) => setTimeout(resolve, 5));
    release();

    await expect(Promise.all([first, second])).resolves.toEqual([
      { facts: ["synthetic fact"] },
      { facts: ["synthetic fact"] },
    ]);
    expect(invoke).toHaveBeenCalledOnce();
    expect([...database.rows.values()]).toHaveLength(1);
    expect([...database.rows.values()][0]).toMatchObject({
      status: "SUCCEEDED",
      invocationCount: 1,
    });
  });

  it("treats a provider or runtime swap as an identity mismatch, not a new call", async () => {
    const database = new MemoryProviderDatabase();
    const firstInvoke = vi.fn(async () => ({ facts: ["first"] }));
    await runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
      runTemplateTwinOwnedProvider(
        providerInput(firstInvoke),
        dependencies(database),
      ),
    );
    const swappedInvoke = vi.fn(async () => ({ facts: ["second"] }));
    const swapped = providerInput(swappedInvoke);

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          { ...swapped, provider: "different-provider" },
          dependencies(database, { mode: "LIVE" }),
        ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH");
    expect(firstInvoke).toHaveBeenCalledOnce();
    expect(swappedInvoke).not.toHaveBeenCalled();
    expect(database.rows).toHaveProperty("size", 1);
  });

  it("makes an ambiguous live provider failure terminal and blocks replay", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => {
      throw new Error("synthetic network acknowledgement lost");
    });
    const run = () =>
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database, { mode: "LIVE" }),
        ),
      );

    expect(await errorCode(run())).toBe(
      "TEMPLATE_TWIN_PROVIDER_OUTCOME_UNKNOWN",
    );
    expect(await errorCode(run())).toBe(
      "TEMPLATE_TWIN_PROVIDER_OUTCOME_UNKNOWN",
    );
    expect(invoke).toHaveBeenCalledOnce();
    expect([...database.rows.values()][0]).toMatchObject({
      status: "UNKNOWN_OUTCOME",
      invocationCount: 1,
    });
  });

  it("recovers an exact committed result when the commit acknowledgement is lost", async () => {
    const database = new MemoryProviderDatabase();
    database.throwAfterSuccessfulCompletion = true;
    const invoke = vi.fn(async () => ({ facts: ["committed once"] }));

    const result = await runWithTemplateTwinProviderOwnershipContext(
      CONTEXT,
      () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database),
        ),
    );

    expect(result).toEqual({ facts: ["committed once"] });
    expect(invoke).toHaveBeenCalledOnce();
    expect([...database.rows.values()][0]?.status).toBe("SUCCEEDED");
  });

  it("rejects a tampered committed result before it can be reused", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["exact"] }));
    await runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
      runTemplateTwinOwnedProvider(
        providerInput(invoke),
        dependencies(database),
      ),
    );
    const row = [...database.rows.values()][0];
    if (!row) throw new Error("synthetic row missing");
    row.resultSha256 = "f".repeat(64);

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database),
        ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_RESULT_INVALID");
    expect(invoke).toHaveBeenCalledOnce();
  });

  it("builds a minimal canonical receipt without provider inputs or claim tokens", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["receipt"] }));

    const receipt = await runWithTemplateTwinProviderOwnershipContext(
      CONTEXT,
      async () => {
        await runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database),
        );
        return buildTemplateTwinProviderOwnershipReceipt({
          projection: {
            subjectId: CONTEXT.subjectId,
            subjectSha256: CONTEXT.subjectSha256,
            visitId: CONTEXT.visitId,
            sourceArtifactId: CONTEXT.sourceArtifactId,
            compiledVersionId: CONTEXT.compiledVersionId,
            noteTemplateId: CONTEXT.noteTemplateId,
          },
          requiredOperations: ["L3_EXTRACT_ENTITIES"],
        });
      },
    );
    const serialized = JSON.stringify(receipt);

    expect(receipt.sha256).toMatch(/^[a-f0-9]{64}$/u);
    expect(receipt.evidence.executions).toHaveLength(1);
    expect(serialized).not.toContain("private synthetic input");
    expect(serialized).not.toContain("idempotency");
    expect(serialized).not.toContain("claimId");
    expect(serialized).not.toContain("resultPayload");
  });

  it("fails a reserved execution closed when rollout authority is revoked", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["must not run"] }));

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database, { rolloutCurrent: false }),
        ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_ROLLOUT_REVOKED");
    expect(invoke).not.toHaveBeenCalled();
    expect([...database.rows.values()][0]?.status).toBe("FAILED");
  });
});
