import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  findVisit: vi.fn(),
  updateVisit: vi.fn(),
  transaction: vi.fn(),
  txUpdate: vi.fn(),
  txDelete: vi.fn(),
  txDeleteCalls: vi.fn(),
  ownedStaging: vi.fn(),
  sameOrigin: vi.fn(),
  pinLifecycle: vi.fn(),
  lockLifecycle: vi.fn(),
  lockOrdinaryLifecycle: vi.fn(),
  lifecycleAudit: vi.fn(),
  loadAdmission: vi.fn(),
  hasTwin: vi.fn(),
  deleteAudio: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeVisit: {
      findUnique: mocks.findVisit,
      update: mocks.updateVisit,
    },
    $transaction: mocks.transaction,
  },
}));
vi.mock("@meddoc/ai", () => ({ redactPhi: (value: unknown) => value }));
vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("@/lib/api-error", () => ({
  apiError: (
    error: string,
    status: number,
    details?: Record<string, unknown>,
  ) => Response.json({ error, ...details }, { status }),
  withApiHandler: (
    _name: string,
    handler: (
      request: Request,
      context: { params: Promise<{ id: string }> },
    ) => Promise<Response>,
  ) => handler,
}));
vi.mock("@/lib/rate-limit", () => ({
  RATE_LIMITS: { VISIT_OPS: {} },
  rateLimitOr429: vi.fn(() => null),
}));
vi.mock("@/lib/audit", () => ({ logAudit: vi.fn() }));
vi.mock("@/lib/log", () => ({
  log: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock("@/lib/minio", () => ({ deleteAudioObject: mocks.deleteAudio }));
vi.mock("@/lib/template-twin/staging-qa-access", () => ({
  isOwnedTemplateTwinStagingQaVisit: mocks.ownedStaging,
}));
vi.mock("@/lib/template-twin/request-security", () => ({
  isSameOriginTemplateTwinMutation: mocks.sameOrigin,
}));
vi.mock("@/lib/template-twin/visit-lifecycle-authority", () => ({
  TEMPLATE_TWIN_DATA_LIFECYCLE_PROVENANCE_SELECT: {},
  TemplateTwinDataLifecycleAuthorizationError: class TemplateTwinDataLifecycleAuthorizationError extends Error {},
  pinTemplateTwinDataLifecycleMutation: mocks.pinLifecycle,
  lockAndAssertTemplateTwinDataLifecycleMutation: mocks.lockLifecycle,
  lockAndAssertOrdinaryDataLifecycleMutation: mocks.lockOrdinaryLifecycle,
  enqueueTemplateTwinDataLifecycleMutationAudit: mocks.lifecycleAudit,
}));
vi.mock("@/lib/template-twin/visit-mutation-authority", () => ({
  loadTemplateTwinClinicalMutationAdmissionTarget: mocks.loadAdmission,
  hasDurableTemplateTwinClinicalMutationProvenance: mocks.hasTwin,
}));

import { TranscribeVisitStatus } from "@prisma/client";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import { TemplateTwinDataLifecycleAuthorizationError } from "@/lib/template-twin/visit-lifecycle-authority";
import { POST as archiveVisit } from "../archive/route";
import { POST as deleteVisit } from "../delete/route";
import { POST as restoreVisit } from "../restore/route";
import { POST as unarchiveVisit } from "../unarchive/route";

const VISIT_ID = "visit-1";
const CONTEXT = { params: Promise.resolve({ id: VISIT_ID }) };
const UPDATED_AT = new Date("2026-07-20T01:00:00.000Z");

function visit(overrides: Record<string, unknown> = {}) {
  return {
    id: VISIT_ID,
    userId: "doctor-1",
    patientId: "patient-1",
    patient: { externalId: null },
    noteTemplateId: "template-1",
    noteTemplate: { templateKind: "template_twin_docx" },
    status: TranscribeVisitStatus.SIGNED,
    updatedAt: UPDATED_AT,
    deletedAt: null,
    archivedAt: null,
    audioKey: null,
    dictationAudioKey: null,
    rawTextInput: "Synthetic evidence.",
    templateTwinFill: { id: "fill-1" },
    templateTwinProviderExecutions: [],
    ...overrides,
  };
}

function request(path: string): NextRequest {
  return new Request(`https://app.example.test${path}`, {
    method: "POST",
  }) as unknown as NextRequest;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({ user: { id: "doctor-1" } });
  mocks.findVisit.mockResolvedValue(visit());
  mocks.loadAdmission.mockImplementation(async () => mocks.findVisit());
  mocks.hasTwin.mockImplementation(
    (row: {
      templateTwinFill?: unknown;
      templateTwinProviderExecutions?: unknown[];
      noteTemplate?: { templateKind?: string } | null;
      patient?: { externalId?: string | null } | null;
    }) =>
      row.patient?.externalId === "SYNTHETIC-QA-ONLY" ||
      Boolean(row.templateTwinFill) ||
      Boolean(row.templateTwinProviderExecutions?.length) ||
      row.noteTemplate?.templateKind === "template_twin_docx",
  );
  mocks.updateVisit.mockResolvedValue({ id: VISIT_ID });
  mocks.txUpdate.mockResolvedValue({ id: VISIT_ID });
  mocks.txDelete.mockResolvedValue({ id: VISIT_ID });
  mocks.txDeleteCalls.mockResolvedValue({ count: 0 });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        transcribeVisit: {
          update: mocks.txUpdate,
          delete: mocks.txDelete,
        },
        aiCall: { deleteMany: mocks.txDeleteCalls },
      }),
  );
  mocks.ownedStaging.mockResolvedValue(false);
  mocks.sameOrigin.mockReturnValue(true);
  mocks.pinLifecycle.mockResolvedValue(null);
  mocks.lockLifecycle.mockResolvedValue(visit());
  mocks.lockOrdinaryLifecycle.mockResolvedValue(undefined);
  mocks.lifecycleAudit.mockResolvedValue(undefined);
  mocks.deleteAudio.mockResolvedValue(undefined);
});

describe("Template Twin visit data-lifecycle authority", () => {
  it.each([
    ["archive", archiveVisit, `/api/visits/${VISIT_ID}/archive`],
    ["unarchive", unarchiveVisit, `/api/visits/${VISIT_ID}/unarchive`],
    ["restore", restoreVisit, `/api/visits/${VISIT_ID}/restore`],
    ["delete", deleteVisit, `/api/visits/${VISIT_ID}/delete`],
  ] as const)(
    "returns no %s lifecycle snapshot when durable lineage appears after admission",
    async (_label, handler, path) => {
      const ordinary = visit({
        noteTemplateId: "ordinary-template-1",
        noteTemplate: {
          templateKind: "structured",
          templateTwinCompiledVersion: null,
        },
        templateTwinFill: null,
      });
      if (handler === deleteVisit) {
        mocks.loadAdmission.mockResolvedValueOnce(ordinary);
        mocks.findVisit.mockResolvedValueOnce(null);
      } else {
        mocks.findVisit
          .mockResolvedValueOnce(ordinary)
          .mockResolvedValueOnce(null);
      }

      const response = await handler(request(path), CONTEXT);

      expect(response.status).toBe(404);
      const clinicalCall = mocks.findVisit.mock.calls.find(
        ([args]) =>
          args?.where?.updatedAt instanceof Date &&
          Object.prototype.hasOwnProperty.call(args.where, "AND"),
      );
      expect(clinicalCall?.[0].where).toEqual(
        expect.objectContaining(TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE),
      );
      if (_label === "delete") {
        expect(clinicalCall?.[0].where).toEqual(
          expect.objectContaining(currentClinicalVisitActorWhere("doctor-1")),
        );
      }
      expect(mocks.txUpdate).not.toHaveBeenCalled();
      expect(mocks.txDelete).not.toHaveBeenCalled();
    },
  );

  it("preserves ordinary archive behind the exact final ordinary lock", async () => {
    const ordinary = visit({
      noteTemplateId: "ordinary-template-1",
      noteTemplate: { templateKind: "structured" },
      templateTwinFill: null,
    });
    mocks.findVisit.mockResolvedValue(ordinary);
    const response = await archiveVisit(
      request(`/api/visits/${VISIT_ID}/archive`),
      CONTEXT,
    );

    expect(response.status).toBe(200);
    expect(mocks.txUpdate).toHaveBeenCalledTimes(1);
    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(mocks.lockOrdinaryLifecycle).toHaveBeenCalledWith(
      expect.objectContaining({
        visitId: VISIT_ID,
        actorUserId: "doctor-1",
        admittedPatientId: "patient-1",
        admittedNoteTemplateId: "ordinary-template-1",
      }),
    );
    expect(mocks.lockLifecycle).not.toHaveBeenCalled();
  });

  it("blocks an ordinary archive when durable provenance appears before the write", async () => {
    const ordinary = visit({
      noteTemplateId: "ordinary-template-1",
      noteTemplate: { templateKind: "structured" },
      templateTwinFill: null,
    });
    mocks.findVisit.mockResolvedValue(ordinary);
    mocks.lockOrdinaryLifecycle.mockRejectedValueOnce(
      new TemplateTwinDataLifecycleAuthorizationError(),
    );

    const response = await archiveVisit(
      request(`/api/visits/${VISIT_ID}/archive`),
      CONTEXT,
    );

    expect(response.status).toBe(409);
    expect(mocks.txUpdate).not.toHaveBeenCalled();
  });

  it("rejects an orphaned reserved synthetic patient before lifecycle mutation", async () => {
    mocks.findVisit.mockResolvedValue(
      visit({
        patient: { externalId: "SYNTHETIC-QA-ONLY" },
        noteTemplateId: "ordinary-template-1",
        noteTemplate: { templateKind: "structured" },
        templateTwinFill: null,
      }),
    );
    mocks.pinLifecycle.mockRejectedValueOnce(
      new TemplateTwinDataLifecycleAuthorizationError(),
    );

    const response = await archiveVisit(
      request(`/api/visits/${VISIT_ID}/archive`),
      CONTEXT,
    );

    expect(response.status).toBe(404);
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("archives a Twin only after its current locked target claim", async () => {
    const current = visit();
    mocks.findVisit.mockResolvedValue(current);
    mocks.pinLifecycle.mockResolvedValue({ visitId: VISIT_ID });
    mocks.lockLifecycle.mockResolvedValue(current);

    const response = await archiveVisit(
      request(`/api/visits/${VISIT_ID}/archive`),
      CONTEXT,
    );

    expect(response.status).toBe(200);
    expect(mocks.lockLifecycle).toHaveBeenCalledTimes(1);
    expect(mocks.txUpdate).toHaveBeenCalledTimes(1);
    expect(mocks.updateVisit).not.toHaveBeenCalled();
    expect(mocks.lifecycleAudit).toHaveBeenCalledTimes(1);
  });

  it("blocks archive when clinical state changes after admission", async () => {
    const current = visit();
    mocks.findVisit.mockResolvedValue(current);
    mocks.pinLifecycle.mockResolvedValue({ visitId: VISIT_ID });
    mocks.lockLifecycle.mockResolvedValue(
      visit({ updatedAt: new Date(UPDATED_AT.getTime() + 1_000) }),
    );

    const response = await archiveVisit(
      request(`/api/visits/${VISIT_ID}/archive`),
      CONTEXT,
    );

    expect(response.status).toBe(409);
    expect(mocks.txUpdate).not.toHaveBeenCalled();
  });

  it("rolls back a Twin archive when required outbox enqueue fails", async () => {
    const current = visit();
    mocks.findVisit.mockResolvedValue(current);
    mocks.pinLifecycle.mockResolvedValue({ visitId: VISIT_ID });
    mocks.lockLifecycle.mockResolvedValue(current);
    mocks.lifecycleAudit.mockRejectedValueOnce(new Error("outbox unavailable"));
    let committed = false;
    mocks.transaction.mockImplementationOnce(
      async (callback: (tx: unknown) => Promise<unknown>) => {
        let staged = false;
        try {
          const result = await callback({
            transcribeVisit: {
              update: vi.fn(async (...args: unknown[]) => {
                staged = true;
                return mocks.txUpdate(...args);
              }),
              delete: mocks.txDelete,
            },
            aiCall: { deleteMany: mocks.txDeleteCalls },
          });
          committed = staged;
          return result;
        } catch (error) {
          committed = false;
          throw error;
        }
      },
    );

    await expect(
      archiveVisit(request(`/api/visits/${VISIT_ID}/archive`), CONTEXT),
    ).rejects.toThrow("outbox unavailable");
    expect(committed).toBe(false);
    expect(mocks.lifecycleAudit).toHaveBeenCalledTimes(1);
  });

  it.each([
    [
      "unarchive",
      unarchiveVisit,
      visit({ archivedAt: new Date("2026-07-20T00:00:00.000Z") }),
      `/api/visits/${VISIT_ID}/unarchive`,
    ],
    [
      "restore",
      restoreVisit,
      visit({
        status: TranscribeVisitStatus.READY,
        deletedAt: new Date("2026-07-20T00:00:00.000Z"),
      }),
      `/api/visits/${VISIT_ID}/restore`,
    ],
  ] as const)(
    "%s requires same-origin and a locked exact version",
    async (_label, handler, current, path) => {
      mocks.findVisit.mockResolvedValue(current);
      mocks.pinLifecycle.mockResolvedValue({ visitId: VISIT_ID });
      mocks.lockLifecycle.mockResolvedValue(current);

      const response = await handler(request(path), CONTEXT);

      expect(response.status).toBe(200);
      expect(mocks.lockLifecycle).toHaveBeenCalledTimes(1);
      expect(mocks.txUpdate).toHaveBeenCalledTimes(1);
    },
  );

  it("blocks cross-origin Twin lifecycle mutation before final claim", async () => {
    mocks.pinLifecycle.mockResolvedValue({ visitId: VISIT_ID });
    mocks.sameOrigin.mockReturnValue(false);

    const response = await archiveVisit(
      request(`/api/visits/${VISIT_ID}/archive`),
      CONTEXT,
    );

    expect(response.status).toBe(404);
    expect(mocks.lockLifecycle).not.toHaveBeenCalled();
    expect(mocks.updateVisit).not.toHaveBeenCalled();
  });

  it("blocks lifecycle mutation when current physician/practice authority is revoked", async () => {
    mocks.pinLifecycle.mockResolvedValue({ visitId: VISIT_ID });
    mocks.lockLifecycle.mockRejectedValue(
      new TemplateTwinDataLifecycleAuthorizationError(),
    );

    const response = await archiveVisit(
      request(`/api/visits/${VISIT_ID}/archive`),
      CONTEXT,
    );

    expect(response.status).toBe(404);
    expect(mocks.txUpdate).not.toHaveBeenCalled();
  });

  it.each([
    ["fill evidence", { fillManifestId: "fill-1", providerExecutionIds: [] }],
    [
      "provider evidence",
      { fillManifestId: null, providerExecutionIds: ["execution-1"] },
    ],
  ])("retains Twin %s instead of hard-purging", async (_label, claim) => {
    mocks.findVisit.mockResolvedValue(
      visit({
        status: TranscribeVisitStatus.FAILED,
        deletedAt: new Date("2026-07-20T00:00:00.000Z"),
      }),
    );
    mocks.pinLifecycle.mockResolvedValue({ visitId: VISIT_ID, ...claim });

    const response = await deleteVisit(
      request(`/api/visits/${VISIT_ID}/delete?permanent=1`),
      CONTEXT,
    );

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      code: "TEMPLATE_TWIN_IMMUTABLE_EVIDENCE_RETAINED",
    });
    expect(mocks.transaction).not.toHaveBeenCalled();
    expect(mocks.txDelete).not.toHaveBeenCalled();
  });

  it("soft-deletes a Twin only after unchanged final target state", async () => {
    const current = visit({ status: TranscribeVisitStatus.READY });
    mocks.findVisit.mockResolvedValue(current);
    mocks.pinLifecycle.mockResolvedValue({
      visitId: VISIT_ID,
      fillManifestId: "fill-1",
      providerExecutionIds: [],
    });
    mocks.lockLifecycle.mockResolvedValue(current);

    const response = await deleteVisit(
      request(`/api/visits/${VISIT_ID}/delete`),
      CONTEXT,
    );

    expect(response.status).toBe(200);
    expect(mocks.txUpdate).toHaveBeenCalledTimes(1);
    expect(mocks.updateVisit).not.toHaveBeenCalled();
  });
});
