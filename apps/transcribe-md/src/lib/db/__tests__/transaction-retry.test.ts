import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Prisma } from "@prisma/client";

import {
  DatabaseTransactionRetryExhaustedError,
  getDatabaseTransactionRetryMetrics,
  resetDatabaseTransactionRetryMetricsForTest,
  retriableDatabaseCode,
  runSerializableTransactionWithRetry,
  type TransactionHost,
} from "../transaction-retry";

function hostWithFailures(failures: unknown[]) {
  let calls = 0;
  return {
    host: {
      $transaction: vi.fn(
        async (
          callback: (tx: Prisma.TransactionClient) => Promise<unknown>,
        ) => {
          const index = calls++;
          const result = await callback({
            attempt: calls,
          } as unknown as Prisma.TransactionClient);
          if (index < failures.length) throw failures[index];
          return result;
        },
      ),
    } as unknown as TransactionHost,
    calls: () => calls,
  };
}

describe("whole-transaction PostgreSQL retry", () => {
  beforeEach(() => resetDatabaseTransactionRetryMetricsForTest());

  it.each(["40P01", "40001", "P2034"] as const)(
    "retries the complete transaction after %s",
    async (code) => {
      const harness = hostWithFailures([{ code }]);
      const transaction = vi.fn().mockResolvedValue("committed");
      const onRetry = vi.fn();

      await expect(
        runSerializableTransactionWithRetry({
          prisma: harness.host,
          operation: "synthetic_transaction",
          transaction,
          retryHooks: {
            sleep: async () => undefined,
            random: () => 0,
            onRetry,
          },
        }),
      ).resolves.toBe("committed");

      expect(harness.calls()).toBe(2);
      expect(transaction).toHaveBeenCalledTimes(2);
      expect(onRetry).toHaveBeenCalledWith(
        expect.objectContaining({ attempt: 1, code }),
      );
    },
  );

  it("recognizes a PostgreSQL code nested below a Prisma cause", () => {
    expect(
      retriableDatabaseCode({
        code: "P2010",
        cause: { sqlState: "40P01" },
      }),
    ).toBe("40P01");
    expect(
      retriableDatabaseCode({
        code: "P2010",
        meta: {
          driverAdapterError: {
            cause: { originalCode: "40001" },
          },
        },
      }),
    ).toBe("40001");
  });

  it("bounds exhaustion and exposes safe retry metrics", async () => {
    const harness = hostWithFailures([
      { code: "40001" },
      { code: "40001" },
      { code: "40001" },
    ]);

    await expect(
      runSerializableTransactionWithRetry({
        prisma: harness.host,
        operation: "synthetic_exhaustion",
        transaction: async () => "never",
        retryHooks: { sleep: async () => undefined, random: () => 0 },
      }),
    ).rejects.toBeInstanceOf(DatabaseTransactionRetryExhaustedError);

    expect(harness.calls()).toBe(3);
    expect(getDatabaseTransactionRetryMetrics()).toMatchObject({
      retries: 2,
      exhausted: 1,
      serializationFailures: 3,
    });
  });

  it("rejects a caller override above the hard three-attempt ceiling", async () => {
    const harness = hostWithFailures([]);
    const transaction = vi.fn().mockResolvedValue("unreachable");

    await expect(
      runSerializableTransactionWithRetry({
        prisma: harness.host,
        operation: "invalid_retry_override",
        maxAttempts: 4,
        transaction,
      }),
    ).rejects.toThrow(/between 1 and 3/u);

    expect(transaction).not.toHaveBeenCalled();
    expect(harness.calls()).toBe(0);
  });

  it("does not repeat an external provider call when the database commit retries", async () => {
    const provider = vi.fn().mockResolvedValue({ synthetic: true });
    const providerResult = await provider();
    const harness = hostWithFailures([{ code: "40P01" }]);
    const commits: unknown[] = [];

    await runSerializableTransactionWithRetry({
      prisma: harness.host,
      operation: "commit_provider_result",
      transaction: async () => {
        commits.push(providerResult);
      },
      retryHooks: { sleep: async () => undefined, random: () => 0 },
    });

    expect(provider).toHaveBeenCalledTimes(1);
    expect(commits).toEqual([providerResult, providerResult]);
    expect(harness.calls()).toBe(2);
  });

  it("never retries unrelated failures", async () => {
    const failure = new Error("synthetic validation failure");
    const harness = hostWithFailures([failure]);
    await expect(
      runSerializableTransactionWithRetry({
        prisma: harness.host,
        operation: "non_database_failure",
        transaction: async () => undefined,
      }),
    ).rejects.toBe(failure);
    expect(harness.calls()).toBe(1);
  });
});
