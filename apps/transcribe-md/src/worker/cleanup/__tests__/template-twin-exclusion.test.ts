import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  visitFindMany: vi.fn(),
  visitUpdateMany: vi.fn(),
  visitDeleteMany: vi.fn(),
  aiDeleteMany: vi.fn(),
  accountFindMany: vi.fn(),
  accountDeleteMany: vi.fn(),
  transaction: vi.fn(),
  deleteAudio: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeVisit: {
      findMany: mocks.visitFindMany,
      updateMany: mocks.visitUpdateMany,
    },
    accountDeletion: {
      findMany: mocks.accountFindMany,
      deleteMany: mocks.accountDeleteMany,
    },
    $transaction: mocks.transaction,
  },
}));
vi.mock("@/lib/minio", () => ({ deleteAudioObject: mocks.deleteAudio }));
vi.mock("@/lib/log", () => ({
  log: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock("@meddoc/ai", () => ({ redactPhi: (value: unknown) => value }));

import { hasDurableTemplateTwinVisitProvenance } from "@/lib/template-twin/durable-visit-provenance";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import { runRetentionSweep } from "../retention-sweep";
import { runStaleVisitCleanup } from "../stale-visits";

const ORDINARY = {
  patient: { externalId: null },
  noteTemplate: {
    templateKind: "structured",
    templateTwinCompiledVersion: null,
  },
  templateTwinFill: null,
  templateTwinSyntheticQaRun: null,
  templateTwinSyntheticQaAdmission: null,
  templateTwinProviderExecutions: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  delete process.env.AUDIO_RETENTION_DAYS;
  mocks.visitFindMany.mockResolvedValue([]);
  mocks.visitUpdateMany.mockResolvedValue({ count: 1 });
  mocks.accountFindMany.mockResolvedValue([]);
  mocks.accountDeleteMany.mockResolvedValue({ count: 0 });
  mocks.deleteAudio.mockResolvedValue(undefined);
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        transcribeVisit: {
          findMany: vi.fn().mockResolvedValue([]),
          deleteMany: mocks.visitDeleteMany,
        },
        aiCall: { deleteMany: mocks.aiDeleteMany },
      }),
  );
});

describe("generic cleanup durable-provenance exclusion", () => {
  it.each([
    [
      "template kind",
      {
        noteTemplate: {
          templateKind: "template_twin_docx",
          templateTwinCompiledVersion: { id: "compiled-1" },
        },
      },
    ],
    [
      "compiled lineage after mutable kind drift",
      {
        noteTemplate: {
          templateKind: "structured",
          templateTwinCompiledVersion: { id: "compiled-1" },
        },
      },
    ],
    ["fill only", { noteTemplate: null, templateTwinFill: { id: "fill-1" } }],
    ["run only", { templateTwinSyntheticQaRun: { id: "run-1" } }],
    ["admission only", { templateTwinSyntheticQaAdmission: { id: "admission-1" } }],
    ["provider execution only", { templateTwinProviderExecutions: [{ id: "execution-1" }] }],
    ["reserved synthetic patient only", { patient: { externalId: "SYNTHETIC-QA-ONLY" } }],
    [
      "detached template evidence",
      {
        noteTemplate: null,
        templateTwinFill: { id: "fill-1" },
        templateTwinProviderExecutions: [{ id: "execution-1" }],
      },
    ],
  ])("classifies %s as durable", (_label, marker) => {
    expect(
      hasDurableTemplateTwinVisitProvenance({ ...ORDINARY, ...marker }),
    ).toBe(true);
  });

  it("leaves a complete ordinary provenance row on the legacy path", () => {
    expect(hasDurableTemplateTwinVisitProvenance(ORDINARY)).toBe(false);
  });

  it("applies every durable marker exclusion to abandoned and trash selection", async () => {
    await runStaleVisitCleanup();

    expect(mocks.visitFindMany).toHaveBeenCalledTimes(2);
    for (const [{ where }] of mocks.visitFindMany.mock.calls) {
      expect(where).toEqual(
        expect.objectContaining(TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE),
      );
    }
  });

  it("still purges an ordinary abandoned visit through the final ordinary-only CAS", async () => {
    const target = {
      id: "ordinary-abandoned-1",
      userId: "doctor-1",
      audioKey: null,
      dictationAudioKey: null,
    };
    const txFindMany = vi.fn().mockResolvedValue([{ id: target.id }]);
    mocks.visitFindMany
      .mockResolvedValueOnce([target])
      .mockResolvedValueOnce([]);
    mocks.visitDeleteMany.mockResolvedValueOnce({ count: 1 });
    mocks.aiDeleteMany.mockResolvedValueOnce({ count: 0 });
    mocks.transaction.mockImplementationOnce(
      async (callback: (tx: unknown) => Promise<unknown>) =>
        callback({
          transcribeVisit: {
            findMany: txFindMany,
            deleteMany: mocks.visitDeleteMany,
          },
          aiCall: { deleteMany: mocks.aiDeleteMany },
        }),
    );

    await expect(runStaleVisitCleanup()).resolves.toMatchObject({
      abandoned: { found: 1, deleted: 1, minioFailures: 0 },
    });
    expect(txFindMany).toHaveBeenCalledWith({
      where: {
        id: { in: [target.id] },
        ...TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE,
      },
      select: { id: true },
    });
    expect(mocks.visitDeleteMany).toHaveBeenCalledWith({
      where: {
        id: { in: [target.id] },
        ...TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE,
      },
    });
    expect(mocks.aiDeleteMany).toHaveBeenCalledWith({
      where: { visitId: { in: [target.id] } },
    });
  });

  it("applies the same marker exclusion and CAS to audio retention", async () => {
    const target = {
      id: "ordinary-visit-1",
      userId: "doctor-1",
      audioKey: "doctor-1/ordinary-visit-1/audio.wav",
      dictationAudioKey: null,
      signedAt: new Date("2026-01-01T00:00:00.000Z"),
    };
    mocks.visitFindMany.mockResolvedValueOnce([target]);

    await expect(runRetentionSweep()).resolves.toMatchObject({
      found: 1,
      audioDeleted: 1,
    });
    expect(mocks.visitFindMany.mock.calls[0]?.[0].where).toEqual(
      expect.objectContaining(TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE),
    );
    expect(mocks.visitUpdateMany.mock.calls[0]?.[0].where).toEqual(
      expect.objectContaining(TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE),
    );
    expect(mocks.deleteAudio).toHaveBeenCalledTimes(1);
  });

  it("does not delete object bytes when the final ordinary-only CAS misses", async () => {
    mocks.visitFindMany.mockResolvedValueOnce([
      {
        id: "visit-became-twin",
        userId: "doctor-1",
        audioKey: "doctor-1/visit-became-twin/audio.wav",
        dictationAudioKey: null,
        signedAt: new Date("2026-01-01T00:00:00.000Z"),
      },
    ]);
    mocks.visitUpdateMany.mockResolvedValueOnce({ count: 0 });

    await expect(runRetentionSweep()).resolves.toMatchObject({
      found: 1,
      audioDeleted: 0,
    });
    expect(mocks.deleteAudio).not.toHaveBeenCalled();
  });
});
