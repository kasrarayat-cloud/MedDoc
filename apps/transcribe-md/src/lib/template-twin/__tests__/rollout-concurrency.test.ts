import { beforeEach, describe, expect, it, vi } from "vitest";

const database = vi.hoisted(() => ({ transaction: vi.fn() }));

vi.mock("@meddoc/db", () => ({
  default: { $transaction: database.transaction },
}));

import {
  lockTemplateTwinRolloutForFinalClaim,
  setTemplateTwinGlobalRollout,
  setTemplateTwinPracticeRollout,
} from "../rollout";

function sqlText(query: unknown): string {
  return String(
    (query as { strings?: readonly string[] }).strings?.join(" ") ?? "",
  );
}

function barrier() {
  let entered!: () => void;
  let release!: () => void;
  const waiting = new Promise<void>((resolve) => {
    entered = resolve;
  });
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { entered, release, waiting, released };
}

class DeterministicRolloutDatabase {
  global = {
    enabled: true,
    generation: BigInt(1),
    rollbackFenceState: "OPEN",
    rollbackOperationId: null as string | null,
  };
  practice = { enabled: true, generation: BigInt(1) };
  lineagePhase = "CONTRACTED";
  auditEvents: unknown[] = [];
  queryOrder: string[] = [];
  pauseFirstGlobal: ReturnType<typeof barrier> | null = null;

  private nextTransaction = 0;
  private owners = new Map<string, number>();
  private waiters = new Map<
    string,
    Array<{ transactionId: number; resume: () => void }>
  >();
  private held = new Map<number, Set<string>>();

  private async acquire(transactionId: number, key: string): Promise<void> {
    if (this.owners.get(key) === transactionId) return;
    if (!this.owners.has(key)) {
      this.owners.set(key, transactionId);
      (this.held.get(transactionId) ?? new Set<string>()).add(key);
      this.held.set(
        transactionId,
        this.held.get(transactionId) ?? new Set([key]),
      );
      return;
    }
    await new Promise<void>((resume) => {
      const queue = this.waiters.get(key) ?? [];
      queue.push({ transactionId, resume });
      this.waiters.set(key, queue);
    });
    (this.held.get(transactionId) ?? new Set<string>()).add(key);
    this.held.set(
      transactionId,
      this.held.get(transactionId) ?? new Set([key]),
    );
  }

  private releaseAll(transactionId: number): void {
    for (const key of this.held.get(transactionId) ?? []) {
      const queue = this.waiters.get(key) ?? [];
      const next = queue.shift();
      if (next) {
        this.owners.set(key, next.transactionId);
        this.waiters.set(key, queue);
        next.resume();
      } else {
        this.owners.delete(key);
      }
    }
    this.held.delete(transactionId);
  }

  async transaction<T>(callback: (tx: unknown) => Promise<T>): Promise<T> {
    const transactionId = ++this.nextTransaction;
    const tx = {
      $queryRaw: async (query: unknown) => {
        const text = sqlText(query);
        if (
          text.includes("template_twin_rollout_controls") &&
          text.includes("FOR UPDATE")
        ) {
          await this.acquire(transactionId, "global");
          this.queryOrder.push(`${transactionId}:global`);
          if (transactionId === 1 && this.pauseFirstGlobal) {
            this.pauseFirstGlobal.entered();
            await this.pauseFirstGlobal.released;
          }
          return [{ ...this.global }];
        }
        if (text.includes('FROM "practices"') && text.includes("FOR UPDATE")) {
          await this.acquire(transactionId, "practice");
          this.queryOrder.push(`${transactionId}:practice`);
          return [
            {
              templateTwinEnabled: this.practice.enabled,
              templateTwinRolloutGeneration: this.practice.generation,
            },
          ];
        }
        if (text.includes("template_twin_lineage_migration_progress")) {
          return [{ phase: this.lineagePhase }];
        }
        if (text.includes('UPDATE "template_twin_rollout_controls"')) {
          this.global.generation += BigInt(1);
          this.global.enabled = text.includes("true");
          return [{ generation: this.global.generation }];
        }
        if (text.includes('UPDATE "practices"')) {
          this.practice.generation += BigInt(1);
          this.practice.enabled = text.includes("true");
          return [
            {
              templateTwinRolloutGeneration: this.practice.generation,
            },
          ];
        }
        throw new Error(`Unexpected synthetic SQL: ${text}`);
      },
      templateTwinAuditOutbox: {
        create: async (input: unknown) => {
          this.auditEvents.push(input);
          return { id: `outbox-${this.auditEvents.length}` };
        },
      },
    };
    try {
      return await callback(tx);
    } finally {
      this.releaseAll(transactionId);
    }
  }
}

const actor = {
  userId: "synthetic-rollout-operator",
  userEmail: "rollout-operator@synthetic.test",
  practiceId: "synthetic-practice",
};

let syntheticDb: DeterministicRolloutDatabase;

beforeEach(() => {
  vi.clearAllMocks();
  delete process.env.TEMPLATE_TWIN_RUNTIME_MODE;
  process.env.TEMPLATE_TWIN_KILL_SWITCH = "false";
  syntheticDb = new DeterministicRolloutDatabase();
  database.transaction.mockImplementation(
    (callback: (tx: unknown) => Promise<unknown>) =>
      syntheticDb.transaction(callback),
  );
});

describe("Template Twin rollout transaction protocol", () => {
  it("locks global before practice for every final claim", async () => {
    await syntheticDb.transaction((tx) =>
      lockTemplateTwinRolloutForFinalClaim({
        tx: tx as never,
        practiceId: actor.practiceId,
        pinnedToken: {
          practiceId: actor.practiceId,
          globalGeneration: BigInt(1),
          practiceGeneration: BigInt(1),
        },
      }),
    );

    expect(syntheticDb.queryOrder).toEqual(["1:global", "1:practice"]);
  });

  it("fences final claims only after taking global then practice locks", async () => {
    syntheticDb.global.rollbackFenceState = "PREPARED";
    syntheticDb.global.rollbackOperationId =
      "4d5cb6df-91bb-4b1e-8d2a-3ecbbf421cea";

    const decision = await syntheticDb.transaction((tx) =>
      lockTemplateTwinRolloutForFinalClaim({
        tx: tx as never,
        practiceId: actor.practiceId,
        pinnedToken: {
          practiceId: actor.practiceId,
          globalGeneration: BigInt(1),
          practiceGeneration: BigInt(1),
        },
      }),
    );

    expect(decision).toMatchObject({
      allowed: false,
      code: "TEMPLATE_TWIN_ROLLBACK_FENCE_ACTIVE",
    });
    expect(syntheticDb.queryOrder).toEqual(["1:global", "1:practice"]);
  });

  it("does not deadlock when a final claim opposes a practice disable", async () => {
    const latch = barrier();
    syntheticDb.pauseFirstGlobal = latch;
    const claim = syntheticDb.transaction((tx) =>
      lockTemplateTwinRolloutForFinalClaim({
        tx: tx as never,
        practiceId: actor.practiceId,
        pinnedToken: {
          practiceId: actor.practiceId,
          globalGeneration: BigInt(1),
          practiceGeneration: BigInt(1),
        },
      }),
    );
    await latch.waiting;

    const disable = setTemplateTwinPracticeRollout({
      practiceId: actor.practiceId,
      enabled: false,
      actor,
    });
    latch.release();

    await expect(claim).resolves.toMatchObject({ allowed: true });
    await expect(disable).resolves.toBe(BigInt(2));
    expect(syntheticDb.queryOrder).toEqual([
      "1:global",
      "1:practice",
      "2:global",
      "2:practice",
    ]);
    expect(syntheticDb.practice).toEqual({
      enabled: false,
      generation: BigInt(2),
    });
  });

  it("refuses both global and practice enable while lineage contract is incomplete", async () => {
    syntheticDb.global.enabled = false;
    syntheticDb.practice.enabled = false;
    syntheticDb.lineagePhase = "BACKFILLING";

    await expect(
      setTemplateTwinGlobalRollout({ enabled: true, actor }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_LINEAGE_MIGRATION_INCOMPLETE",
    });
    await expect(
      setTemplateTwinPracticeRollout({
        practiceId: actor.practiceId,
        enabled: true,
        actor,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_LINEAGE_MIGRATION_INCOMPLETE",
    });
    expect(syntheticDb.global.enabled).toBe(false);
    expect(syntheticDb.practice.enabled).toBe(false);
    expect(syntheticDb.auditEvents).toHaveLength(0);
  });

  it("permits revocation but rejects re-enable in rollback compatibility mode", async () => {
    process.env.TEMPLATE_TWIN_RUNTIME_MODE = "rollback-compat-v2";

    await expect(
      setTemplateTwinGlobalRollout({ enabled: false, actor }),
    ).resolves.toBe(BigInt(2));
    await expect(
      setTemplateTwinPracticeRollout({
        practiceId: actor.practiceId,
        enabled: false,
        actor,
      }),
    ).resolves.toBe(BigInt(2));
    const revocationTransactionCount = database.transaction.mock.calls.length;

    await expect(
      setTemplateTwinGlobalRollout({ enabled: true, actor }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_ROLLBACK_COMPAT_ACTIVE",
    });
    await expect(
      setTemplateTwinPracticeRollout({
        practiceId: actor.practiceId,
        enabled: true,
        actor,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_ROLLBACK_COMPAT_ACTIVE",
    });
    expect(database.transaction).toHaveBeenCalledTimes(
      revocationTransactionCount,
    );
    expect(syntheticDb.global.enabled).toBe(false);
    expect(syntheticDb.practice.enabled).toBe(false);
  });

  it("rejects global and practice enable while the rollback fence is prepared", async () => {
    syntheticDb.global.enabled = false;
    syntheticDb.practice.enabled = false;
    syntheticDb.global.rollbackFenceState = "PREPARED";
    syntheticDb.global.rollbackOperationId =
      "4d5cb6df-91bb-4b1e-8d2a-3ecbbf421cea";

    await expect(
      setTemplateTwinGlobalRollout({ enabled: true, actor }),
    ).rejects.toMatchObject({ code: "TEMPLATE_TWIN_ROLLBACK_FENCE_ACTIVE" });
    await expect(
      setTemplateTwinPracticeRollout({
        practiceId: actor.practiceId,
        enabled: true,
        actor,
      }),
    ).rejects.toMatchObject({ code: "TEMPLATE_TWIN_ROLLBACK_FENCE_ACTIVE" });
    expect(syntheticDb.global.enabled).toBe(false);
    expect(syntheticDb.practice.enabled).toBe(false);
    expect(syntheticDb.auditEvents).toHaveLength(0);
  });
});
