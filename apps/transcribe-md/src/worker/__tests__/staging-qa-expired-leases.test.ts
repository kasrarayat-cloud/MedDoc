import { afterEach, describe, expect, it, vi } from "vitest";

const moduleMocks = vi.hoisted(() => ({
  findMany: vi.fn(),
  reconcile: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    templateTwinSyntheticQaRun: { findMany: moduleMocks.findMany },
  },
}));
vi.mock("../synthetic-qa-provider", () => ({
  reconcileExpiredTemplateTwinSyntheticQaWorkerClaim: moduleMocks.reconcile,
}));

import {
  scanExpiredTemplateTwinSyntheticQaWorkerClaims,
  startTemplateTwinSyntheticQaExpiredLeaseReconciler,
} from "../cleanup/staging-qa-expired-leases";

const NOW = new Date("2026-07-17T04:00:00.000Z");
const CANDIDATE = {
  id: "run-synthetic-1",
  visitId: "visit-synthetic-1",
  doctorId: "doctor-synthetic-1",
  attempt: 3,
  workerLeaseExpiresAt: new Date("2026-07-17T03:00:00.000Z"),
};
const FIRST_CURSOR = {
  workerLeaseExpiresAt: CANDIDATE.workerLeaseExpiresAt,
  id: CANDIDATE.id,
};

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe("synthetic QA expired worker lease scanner", () => {
  it("recovers an expired claim even when the BullMQ failed event was lost", async () => {
    const listExpired = vi.fn().mockResolvedValue([CANDIDATE]);
    const reconcile = vi.fn().mockResolvedValue(true);

    await expect(
      scanExpiredTemplateTwinSyntheticQaWorkerClaims({
        now: NOW,
        dependencies: { listExpired, reconcile },
      }),
    ).resolves.toEqual({
      scanned: 1,
      reconciled: 1,
      failed: 0,
      nextCursor: FIRST_CURSOR,
    });
    expect(reconcile).toHaveBeenCalledWith({
      runId: CANDIDATE.id,
      visitId: CANDIDATE.visitId,
      userId: CANDIDATE.doctorId,
      attempt: CANDIDATE.attempt,
      now: NOW,
    });
  });

  it("retries on the next periodic tick after a transient database failure", async () => {
    vi.useFakeTimers();
    const onError = vi.fn();
    const scan = vi
      .fn()
      .mockRejectedValueOnce(new Error("synthetic transient database outage"))
      .mockResolvedValue({
        scanned: 1,
        reconciled: 1,
        failed: 0,
        nextCursor: FIRST_CURSOR,
      });
    const scheduler = startTemplateTwinSyntheticQaExpiredLeaseReconciler({
      enabled: true,
      intervalMs: 1_000,
      scan,
      onError,
    });

    await vi.advanceTimersByTimeAsync(0);
    expect(scan).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(1_000);
    expect(scan).toHaveBeenCalledTimes(2);
    expect(await scheduler.runNow()).toEqual({
      scanned: 1,
      reconciled: 1,
      failed: 0,
      nextCursor: FIRST_CURSOR,
    });
    expect(scan).toHaveBeenNthCalledWith(3, FIRST_CURSOR);
    scheduler.stop();
  });

  it("is safe when concurrent scanner replicas select the same claim", async () => {
    let available = true;
    const reconcile = vi.fn(async () => {
      if (!available) return false;
      available = false;
      return true;
    });
    const dependencies = {
      listExpired: vi.fn().mockResolvedValue([CANDIDATE]),
      reconcile,
    };

    const results = await Promise.all([
      scanExpiredTemplateTwinSyntheticQaWorkerClaims({
        now: NOW,
        dependencies,
      }),
      scanExpiredTemplateTwinSyntheticQaWorkerClaims({
        now: NOW,
        dependencies,
      }),
    ]);

    expect(results).toEqual([
      { scanned: 1, reconciled: 1, failed: 0, nextCursor: FIRST_CURSOR },
      { scanned: 1, reconciled: 0, failed: 0, nextCursor: FIRST_CURSOR },
    ]);
    expect(reconcile).toHaveBeenCalledTimes(2);
  });

  it("does not overlap periodic scans and stops with the worker lifecycle", async () => {
    vi.useFakeTimers();
    let finish!: (value: {
      scanned: number;
      reconciled: number;
      failed: number;
      nextCursor: typeof FIRST_CURSOR | null;
    }) => void;
    const first = new Promise<{
      scanned: number;
      reconciled: number;
      failed: number;
      nextCursor: typeof FIRST_CURSOR | null;
    }>((resolve) => {
      finish = resolve;
    });
    const scan = vi.fn().mockReturnValue(first);
    const scheduler = startTemplateTwinSyntheticQaExpiredLeaseReconciler({
      enabled: true,
      intervalMs: 1_000,
      scan,
    });

    await vi.advanceTimersByTimeAsync(3_000);
    expect(scan).toHaveBeenCalledTimes(1);
    finish({ scanned: 0, reconciled: 0, failed: 0, nextCursor: null });
    await first;
    scheduler.stop();
    await vi.advanceTimersByTimeAsync(3_000);
    expect(scan).toHaveBeenCalledTimes(1);
    expect(await scheduler.runNow()).toBeNull();
  });

  it("isolates a poison row and continues reconciling later candidates", async () => {
    const later = {
      ...CANDIDATE,
      id: "run-synthetic-2",
      visitId: "visit-synthetic-2",
      workerLeaseExpiresAt: new Date("2026-07-17T03:00:01.000Z"),
    };
    const reconcile = vi
      .fn()
      .mockRejectedValueOnce(new Error("synthetic corrupt row"))
      .mockResolvedValueOnce(true);

    await expect(
      scanExpiredTemplateTwinSyntheticQaWorkerClaims({
        now: NOW,
        dependencies: {
          listExpired: vi.fn().mockResolvedValue([CANDIDATE, later]),
          reconcile,
        },
      }),
    ).resolves.toEqual({
      scanned: 2,
      reconciled: 1,
      failed: 1,
      nextCursor: {
        workerLeaseExpiresAt: later.workerLeaseExpiresAt,
        id: later.id,
      },
    });
    expect(reconcile).toHaveBeenCalledTimes(2);
  });

  it("rotates beyond a full poison page so later expired rows cannot starve", async () => {
    const rows = Array.from({ length: 30 }, (_, index) => ({
      ...CANDIDATE,
      id: `run-synthetic-${String(index + 1).padStart(2, "0")}`,
      visitId: `visit-synthetic-${String(index + 1).padStart(2, "0")}`,
      workerLeaseExpiresAt: new Date(
        CANDIDATE.workerLeaseExpiresAt.getTime() + index * 1_000,
      ),
    }));
    const listExpired = vi.fn(
      async (input: { limit: number; cursor: typeof FIRST_CURSOR | null }) => {
        const after = input.cursor
          ? rows.findIndex(
              (row) =>
                row.id === input.cursor!.id &&
                row.workerLeaseExpiresAt.getTime() ===
                  input.cursor!.workerLeaseExpiresAt.getTime(),
            ) + 1
          : 0;
        return [...rows.slice(after), ...rows.slice(0, after)].slice(
          0,
          input.limit,
        );
      },
    );
    const reconcile = vi.fn(async (input: { runId: string }) => {
      const ordinal = Number(input.runId.slice(-2));
      if (ordinal <= 25) throw new Error("synthetic permanent poison row");
      return true;
    });

    const first = await scanExpiredTemplateTwinSyntheticQaWorkerClaims({
      now: NOW,
      limit: 25,
      dependencies: { listExpired, reconcile },
    });
    expect(first).toMatchObject({ scanned: 25, reconciled: 0, failed: 25 });

    const second = await scanExpiredTemplateTwinSyntheticQaWorkerClaims({
      now: NOW,
      limit: 25,
      cursor: first.nextCursor,
      dependencies: { listExpired, reconcile },
    });
    expect(second).toMatchObject({ scanned: 25, reconciled: 5, failed: 20 });
    expect(reconcile).toHaveBeenCalledWith(
      expect.objectContaining({ runId: "run-synthetic-30" }),
    );
  });
});
