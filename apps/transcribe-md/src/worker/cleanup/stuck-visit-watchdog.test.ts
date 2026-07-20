import { beforeEach, describe, expect, it, vi } from "vitest";
import { TranscribeVisitStatus } from "@prisma/client";

const mocks = vi.hoisted(() => ({
  findMany: vi.fn(),
  txFindUnique: vi.fn(),
  txUpdateMany: vi.fn(),
  txQueryRaw: vi.fn(),
  runTransaction: vi.fn(),
  enqueueAudit: vi.fn(),
  logInfo: vi.fn(),
  logError: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: { transcribeVisit: { findMany: mocks.findMany } },
}));
vi.mock("@/lib/db/transaction-retry", () => ({
  runSerializableTransactionWithRetry: mocks.runTransaction,
}));
vi.mock("@/lib/template-twin/audit-outbox", () => ({
  enqueueIdempotentTemplateTwinAudit: mocks.enqueueAudit,
}));
vi.mock("@/lib/log", () => ({
  log: {
    info: mocks.logInfo,
    error: mocks.logError,
    warn: vi.fn(),
  },
}));

import { runStuckVisitWatchdog } from "./stuck-visit-watchdog";

const NOW = new Date("2026-07-20T03:00:00.000Z");
const STARTED = new Date("2026-07-20T02:30:00.000Z");

const ordinaryMarkers = {
  patient: { externalId: null },
  noteTemplate: {
    templateKind: "structured",
    templateTwinCompiledVersion: null,
  },
  templateTwinFill: null,
  templateTwinSyntheticQaRun: null,
  templateTwinSyntheticQaAdmission: null,
  templateTwinProviderExecutions: [],
} as const;

function candidate(overrides: Record<string, unknown> = {}) {
  return {
    id: "visit-stuck-1",
    status: TranscribeVisitStatus.DRAFTING,
    userId: "doctor-stuck-1",
    user: { practiceId: "practice-stuck-1" },
    processingStartedAt: STARTED,
    ...ordinaryMarkers,
    ...overrides,
  };
}

function lockedCandidate(overrides: Record<string, unknown> = {}) {
  const row = candidate(overrides);
  return {
    id: row.id,
    status: row.status,
    processingStartedAt: row.processingStartedAt,
    patient: row.patient,
    noteTemplate: row.noteTemplate,
    templateTwinFill: row.templateTwinFill,
    templateTwinSyntheticQaRun: row.templateTwinSyntheticQaRun,
    templateTwinSyntheticQaAdmission: row.templateTwinSyntheticQaAdmission,
    templateTwinProviderExecutions: row.templateTwinProviderExecutions,
  };
}

beforeEach(() => {
  vi.unstubAllEnvs();
  vi.clearAllMocks();
  mocks.findMany.mockResolvedValue([candidate()]);
  mocks.txFindUnique.mockResolvedValue(lockedCandidate());
  mocks.txUpdateMany.mockResolvedValue({ count: 1 });
  mocks.txQueryRaw.mockResolvedValue([{ id: "locked-row" }]);
  mocks.enqueueAudit.mockResolvedValue("CREATED");
  mocks.runTransaction.mockImplementation(
    async (input: { transaction: (tx: unknown) => Promise<unknown> }) =>
      input.transaction({
        transcribeVisit: {
          findUnique: mocks.txFindUnique,
          updateMany: mocks.txUpdateMany,
        },
        $queryRaw: mocks.txQueryRaw,
      }),
  );
});

describe("stuck visit watchdog durable provenance boundary", () => {
  it("rescues only an ordinary visit and commits its outbox audit in the locked transaction", async () => {
    await expect(
      runStuckVisitWatchdog({ thresholdMs: 15 * 60_000, now: NOW }),
    ).resolves.toEqual({ scanned: 1, rescued: 1, errors: 0 });

    const initialWhere = mocks.findMany.mock.calls[0]?.[0].where;
    expect(initialWhere.AND).toEqual(
      expect.arrayContaining([
        { templateTwinFill: { is: null } },
        { templateTwinSyntheticQaRun: { is: null } },
        { templateTwinSyntheticQaAdmission: { is: null } },
        { templateTwinProviderExecutions: { none: {} } },
      ]),
    );
    expect(JSON.stringify(initialWhere)).toContain("SYNTHETIC-QA-ONLY");
    expect(mocks.runTransaction).toHaveBeenCalledWith(
      expect.objectContaining({
        operation: "stuck_visit_watchdog",
        context: {
          visitId: "visit-stuck-1",
          practiceId: "practice-stuck-1",
        },
      }),
    );
    const lockedUpdateWhere = mocks.txUpdateMany.mock.calls[0]?.[0].where;
    expect(lockedUpdateWhere.AND).toEqual(
      expect.arrayContaining([
        { templateTwinFill: { is: null } },
        { templateTwinSyntheticQaRun: { is: null } },
        { templateTwinSyntheticQaAdmission: { is: null } },
        { templateTwinProviderExecutions: { none: {} } },
      ]),
    );
    expect(JSON.stringify(lockedUpdateWhere)).toContain("SYNTHETIC-QA-ONLY");
    expect(mocks.enqueueAudit).toHaveBeenCalledWith(
      expect.objectContaining({ transcribeVisit: expect.any(Object) }),
      expect.objectContaining({
        action: "VISIT_PROCESSING_TIMEOUT",
        targetId: "visit-stuck-1",
        practiceId: "practice-stuck-1",
        actorId: "doctor-stuck-1",
      }),
    );
  });

  it("preserves ordinary rescue with Twin runtime disabled and an inactive actor", async () => {
    vi.stubEnv("TEMPLATE_TWIN_ENABLED", "false");
    vi.stubEnv("TEMPLATE_TWIN_ROLLOUT_ENABLED", "false");
    mocks.txQueryRaw.mockResolvedValue([{ id: "locked-row", isActive: false }]);

    await expect(
      runStuckVisitWatchdog({ thresholdMs: 15 * 60_000, now: NOW }),
    ).resolves.toEqual({ scanned: 1, rescued: 1, errors: 0 });

    expect(mocks.txQueryRaw).toHaveBeenCalledTimes(3);
    expect(mocks.txUpdateMany).toHaveBeenCalledTimes(1);
    expect(mocks.enqueueAudit).toHaveBeenCalledTimes(1);
  });

  it.each([
    [
      "reserved synthetic patient-only provenance",
      {
        patient: { externalId: "SYNTHETIC-QA-ONLY" },
        noteTemplate: null,
      },
    ],
    [
      "provider-execution-only detached provenance",
      {
        noteTemplate: null,
        templateTwinProviderExecutions: [{ id: "execution-1" }],
      },
    ],
    [
      "fill-only detached provenance",
      { noteTemplate: null, templateTwinFill: { id: "fill-1" } },
    ],
    [
      "admission-only provenance",
      { templateTwinSyntheticQaAdmission: { id: "admission-1" } },
    ],
    [
      "current Twin template",
      {
        noteTemplate: {
          templateKind: "template_twin_docx",
          templateTwinCompiledVersion: { id: "compiled-1" },
        },
      },
    ],
  ])(
    "rejects %s before any terminal write or audit",
    async (_label, marker) => {
      mocks.findMany.mockResolvedValue([candidate(marker)]);

      await expect(
        runStuckVisitWatchdog({ thresholdMs: 15 * 60_000, now: NOW }),
      ).resolves.toEqual({ scanned: 1, rescued: 0, errors: 1 });

      expect(mocks.runTransaction).not.toHaveBeenCalled();
      expect(mocks.txUpdateMany).not.toHaveBeenCalled();
      expect(mocks.enqueueAudit).not.toHaveBeenCalled();
    },
  );

  it("rejects durable Twin provenance that appears after the initial scan under the visit lock", async () => {
    mocks.txFindUnique.mockResolvedValue(
      lockedCandidate({
        noteTemplate: null,
        templateTwinProviderExecutions: [{ id: "execution-1" }],
      }),
    );

    await expect(
      runStuckVisitWatchdog({ thresholdMs: 15 * 60_000, now: NOW }),
    ).resolves.toEqual({ scanned: 1, rescued: 0, errors: 1 });

    expect(mocks.txUpdateMany).not.toHaveBeenCalled();
    expect(mocks.enqueueAudit).not.toHaveBeenCalled();
  });

  it("does not report a rescue when the required outbox write aborts the transaction", async () => {
    mocks.enqueueAudit.mockRejectedValue(new Error("outbox unavailable"));

    await expect(
      runStuckVisitWatchdog({ thresholdMs: 15 * 60_000, now: NOW }),
    ).resolves.toEqual({ scanned: 1, rescued: 0, errors: 1 });

    expect(mocks.txUpdateMany).toHaveBeenCalledTimes(1);
    expect(mocks.enqueueAudit).toHaveBeenCalledTimes(1);
    expect(mocks.logInfo).not.toHaveBeenCalled();
  });
});
