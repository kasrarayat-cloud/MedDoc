import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TranscribeVisitStatus } from "@prisma/client";

const mocks = vi.hoisted(() => ({
  transaction: vi.fn(),
  rootRunFindFirst: vi.fn(),
  txRunFindFirst: vi.fn(),
  txRunUpdateMany: vi.fn(),
  txVisitUpdate: vi.fn(),
  rootVisitUpdateMany: vi.fn(),
  enqueueVisit: vi.fn(),
  putAudio: vi.fn(),
  lockRollout: vi.fn(),
  lockRun: vi.fn(),
  lockVisit: vi.fn(),
  enqueueAudit: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    $transaction: mocks.transaction,
    templateTwinSyntheticQaRun: { findFirst: mocks.rootRunFindFirst },
    transcribeVisit: { updateMany: mocks.rootVisitUpdateMany },
  },
}));
vi.mock("@/lib/queue", () => ({
  enqueueTemplateTwinSyntheticQaVisit: mocks.enqueueVisit,
}));
vi.mock("@/lib/minio", () => ({ putAudioStream: mocks.putAudio }));
vi.mock("../rollout", () => ({
  lockTemplateTwinRolloutForFinalClaim: mocks.lockRollout,
}));
vi.mock("../staging-qa-visit-guard", () => ({
  lockAndAssertTemplateTwinStagingQaRun: mocks.lockRun,
}));
vi.mock("../fill-engine", () => ({
  lockCurrentTemplateTwinVisit: mocks.lockVisit,
}));
vi.mock("../audit-outbox", () => ({
  enqueueTemplateTwinAudit: mocks.enqueueAudit,
}));

import {
  enqueueOwnedRun,
  type TemplateTwinStagingQaActor,
} from "../staging-qa-service";
import { TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION } from "../staging-qa-fixtures";

const ORIGINAL_ENV = { ...process.env };
const actor: TemplateTwinStagingQaActor = {
  userId: "doctor-synthetic-queue-1",
  userEmail: "doctor.queue@example.test",
  practiceId: "practice-synthetic-queue-1",
  rolloutToken: {
    practiceId: "practice-synthetic-queue-1",
    globalGeneration: BigInt(5),
    practiceGeneration: BigInt(8),
  },
};

interface QueueRunState {
  id: string;
  practiceId: string;
  doctorId: string;
  visitId: string;
  noteTemplateId: string;
  noteTemplateVersion: number;
  requestSha256: string;
  payloadSha256: string;
  mode: string;
  fixtureVersion: string;
  pinnedGlobalRolloutGeneration: bigint;
  pinnedPracticeRolloutGeneration: bigint;
  status: string;
  attempt: number;
  enqueuedAt: Date | null;
  createdAt: Date;
  visit: {
    status: TranscribeVisitStatus;
    inputMode: string;
    dictationAudioKey: string | null;
    audioUploadedAt: Date | null;
    deletedAt: Date | null;
    archivedAt: Date | null;
    templateTwinFill: null;
  };
}

function baseRun(overrides: Partial<QueueRunState> = {}): QueueRunState {
  return {
    id: "run-synthetic-queue-1",
    practiceId: actor.practiceId,
    doctorId: actor.userId,
    visitId: "visit-synthetic-queue-1",
    noteTemplateId: "template-synthetic-queue-1",
    noteTemplateVersion: 1,
    requestSha256: "a".repeat(64),
    payloadSha256: "b".repeat(64),
    mode: "typed",
    fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
    pinnedGlobalRolloutGeneration: BigInt(5),
    pinnedPracticeRolloutGeneration: BigInt(8),
    status: "ENQUEUED",
    attempt: 1,
    enqueuedAt: new Date("2026-07-17T02:15:00.000Z"),
    createdAt: new Date("2026-07-17T02:14:00.000Z"),
    visit: {
      status: TranscribeVisitStatus.QUEUED,
      inputMode: "text_notes",
      dictationAudioKey: null,
      audioUploadedAt: null,
      deletedAt: null,
      archivedAt: null,
      templateTwinFill: null,
    },
    ...overrides,
  };
}

function installStatefulQueueHarness(
  initial: QueueRunState,
  options: { serializeTransactions?: boolean } = {},
) {
  let state = initial;
  let transactionTail = Promise.resolve();
  const snapshot = () => ({ ...state, visit: { ...state.visit } });
  const tx = {
    templateTwinSyntheticQaRun: {
      findFirst: mocks.txRunFindFirst,
      updateMany: mocks.txRunUpdateMany,
    },
    transcribeVisit: { update: mocks.txVisitUpdate },
  };

  mocks.transaction.mockImplementation(
    async (callback: (client: typeof tx) => Promise<unknown>) => {
      if (!options.serializeTransactions) return callback(tx);
      const previous = transactionTail;
      let release!: () => void;
      transactionTail = new Promise<void>((resolve) => {
        release = resolve;
      });
      await previous;
      try {
        return await callback(tx);
      } finally {
        release();
      }
    },
  );
  mocks.txRunFindFirst.mockImplementation(async () => snapshot());
  mocks.rootRunFindFirst.mockImplementation(async () => snapshot());
  mocks.txRunUpdateMany.mockImplementation(
    async (input: {
      where: { attempt?: number; status?: string };
      data: Partial<QueueRunState>;
    }) => {
      if (
        (input.where.attempt !== undefined &&
          input.where.attempt !== state.attempt) ||
        (input.where.status !== undefined &&
          input.where.status !== state.status)
      ) {
        return { count: 0 };
      }
      state = { ...state, ...input.data };
      return { count: 1 };
    },
  );
  mocks.lockRollout.mockResolvedValue({
    allowed: true,
    token: actor.rolloutToken,
  });
  mocks.lockRun.mockResolvedValue(undefined);
  mocks.lockVisit.mockResolvedValue(undefined);
  mocks.enqueueAudit.mockResolvedValue(undefined);
  mocks.enqueueVisit.mockResolvedValue(undefined);
  mocks.txVisitUpdate.mockImplementation(
    async (input: {
      data: Partial<QueueRunState["visit"]>;
    }) => {
      state = { ...state, visit: { ...state.visit, ...input.data } };
      return { ...state.visit };
    },
  );

  return { state: () => snapshot() };
}

beforeEach(() => {
  process.env = {
    ...ORIGINAL_ENV,
    TEMPLATE_TWIN_STAGING_QA_ENABLED: "true",
    TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: "test",
    TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION: "isolated-disposable-qa-v1",
    TEMPLATE_TWIN_STORAGE_PROFILE: "qa",
    DATABASE_URL: "postgresql:///meddoc_qa_test",
    REDIS_URL: "redis://redis:6379/15",
    MINIO_ENDPOINT: "minio:9000",
    MINIO_USE_SSL: "false",
    TRANSCRIBE_MD_MINIO_BUCKET: "transcribe-md-audio-qa",
    TRANSCRIBE_MD_TEMPLATE_BUCKET: "transcribe-md-template-artifacts-qa",
    MOCK_AI_CALLS: "true",
    MOCK_TEMPLATE_TWIN_E2E: "true",
  };
  for (const mock of Object.values(mocks)) mock.mockReset();
});

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
});

describe("Template Twin staging queue-admission healing", () => {
  it("replays an exact ENQUEUED plus QUEUED admission with the same attempt", async () => {
    const harness = installStatefulQueueHarness(baseRun());
    const { templateTwinSyntheticQaJobId } =
      await vi.importActual<typeof import("../../queue")>("../../queue");

    const first = await enqueueOwnedRun({
      actor,
      runId: "run-synthetic-queue-1",
      explicitRetry: false,
    });
    const second = await enqueueOwnedRun({
      actor,
      runId: "run-synthetic-queue-1",
      explicitRetry: false,
    });

    expect(first).toMatchObject({ attempt: 1, reused: true });
    expect(second).toMatchObject({ attempt: 1, reused: true });
    expect(harness.state()).toMatchObject({
      status: "ENQUEUED",
      attempt: 1,
    });
    expect(mocks.txRunUpdateMany).not.toHaveBeenCalled();
    expect(
      templateTwinSyntheticQaJobId({
        runId: "run-synthetic-queue-1",
        attempt: 1,
      }),
    ).toBe("template-twin-qa-run-synthetic-queue-1-attempt-1");
    expect(
      templateTwinSyntheticQaJobId({
        runId: "run-synthetic-queue-1",
        attempt: 2,
      }),
    ).not.toBe("template-twin-qa-run-synthetic-queue-1-attempt-1");
    expect(mocks.enqueueVisit.mock.calls).toEqual([
      [
        {
          runId: "run-synthetic-queue-1",
          attempt: 1,
          visitId: "visit-synthetic-queue-1",
          userId: actor.userId,
        },
      ],
      [
        {
          runId: "run-synthetic-queue-1",
          attempt: 1,
          visitId: "visit-synthetic-queue-1",
          userId: actor.userId,
        },
      ],
    ]);
  });

  it("leaves a queue-add failure retryable and advances only the subsequent retry", async () => {
    const harness = installStatefulQueueHarness(
      baseRun({
        status: "PENDING_ENQUEUE",
        attempt: 0,
        enqueuedAt: null,
      }),
    );
    mocks.enqueueVisit.mockRejectedValueOnce(
      new Error("synthetic Redis unavailable"),
    );

    await expect(
      enqueueOwnedRun({
        actor,
        runId: "run-synthetic-queue-1",
        explicitRetry: false,
      }),
    ).rejects.toMatchObject({
      code: "QUEUE_UNAVAILABLE",
    });
    expect(harness.state()).toMatchObject({
      status: "ENQUEUE_FAILED",
      attempt: 1,
      enqueuedAt: null,
    });

    await expect(
      enqueueOwnedRun({
        actor,
        runId: "run-synthetic-queue-1",
        explicitRetry: false,
      }),
    ).resolves.toMatchObject({ attempt: 2, reused: true });
    expect(harness.state()).toMatchObject({
      status: "ENQUEUED",
      attempt: 2,
    });
    expect(
      mocks.enqueueVisit.mock.calls.map(([input]) => input.attempt),
    ).toEqual([1, 2]);
    expect(mocks.enqueueAudit).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
        metadata: expect.objectContaining({
          errorCode: "QUEUE_UNAVAILABLE",
          attempt: 1,
        }),
      }),
    );
  });

  it("serializes a repeated retry into one durable next attempt", async () => {
    const harness = installStatefulQueueHarness(
      baseRun({
        status: "PROCESSING_FAILED",
        attempt: 1,
        visit: {
          ...baseRun().visit,
          status: TranscribeVisitStatus.FAILED,
        },
      }),
      { serializeTransactions: true },
    );

    const first = await enqueueOwnedRun({
      actor,
      runId: "run-synthetic-queue-1",
      explicitRetry: true,
      expectedAttempt: 1,
    });
    const repeated = await enqueueOwnedRun({
      actor,
      runId: "run-synthetic-queue-1",
      explicitRetry: true,
      expectedAttempt: 1,
    });

    expect(first).toMatchObject({ attempt: 2, reused: true });
    expect(repeated).toMatchObject({ attempt: 2, reused: true });
    expect(harness.state()).toMatchObject({
      status: "ENQUEUED",
      attempt: 2,
      visit: { status: TranscribeVisitStatus.QUEUED },
    });
    expect(
      mocks.enqueueVisit.mock.calls.map(([input]) => input.attempt),
    ).toEqual([2, 2]);
    expect(mocks.txRunUpdateMany).toHaveBeenCalledTimes(1);
    expect(mocks.enqueueAudit).toHaveBeenCalledTimes(1);
  });

  it("collapses concurrent double-submit requests under the run lock", async () => {
    const harness = installStatefulQueueHarness(
      baseRun({
        status: "PROCESSING_FAILED",
        attempt: 4,
        visit: {
          ...baseRun().visit,
          status: TranscribeVisitStatus.FAILED,
        },
      }),
      { serializeTransactions: true },
    );

    const [left, right] = await Promise.all([
      enqueueOwnedRun({
        actor,
        runId: "run-synthetic-queue-1",
        explicitRetry: true,
        expectedAttempt: 4,
      }),
      enqueueOwnedRun({
        actor,
        runId: "run-synthetic-queue-1",
        explicitRetry: true,
        expectedAttempt: 4,
      }),
    ]);

    expect(left.attempt).toBe(5);
    expect(right.attempt).toBe(5);
    expect(harness.state().attempt).toBe(5);
    expect(mocks.txRunUpdateMany).toHaveBeenCalledTimes(1);
    expect(
      new Set(
        mocks.enqueueVisit.mock.calls.map(([input]) => input.attempt),
      ),
    ).toEqual(new Set([5]));
  });

  it("rejects a stale retry instead of reserving another attempt", async () => {
    const harness = installStatefulQueueHarness(
      baseRun({ status: "PROCESSING_FAILED", attempt: 5 }),
    );

    await expect(
      enqueueOwnedRun({
        actor,
        runId: "run-synthetic-queue-1",
        explicitRetry: true,
        expectedAttempt: 2,
      }),
    ).rejects.toMatchObject({ code: "RETRY_ATTEMPT_STALE" });
    expect(harness.state().attempt).toBe(5);
    expect(mocks.txRunUpdateMany).not.toHaveBeenCalled();
    expect(mocks.enqueueVisit).not.toHaveBeenCalled();
  });
});
