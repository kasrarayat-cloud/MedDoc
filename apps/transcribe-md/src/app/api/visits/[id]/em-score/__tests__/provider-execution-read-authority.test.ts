import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  findUnique: vi.fn(),
  transaction: vi.fn(),
  requireRead: vi.fn(),
  isOwnedStagingVisit: vi.fn(),
  computeEmScore: vi.fn(),
  engineToUiScore: vi.fn(),
  lockOrdinary: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeVisit: { findUnique: mocks.findUnique },
    $transaction: mocks.transaction,
  },
}));
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
vi.mock("@/lib/template-twin/staging-qa-access", () => ({
  isOwnedTemplateTwinStagingQaVisit: mocks.isOwnedStagingVisit,
}));
vi.mock("@/lib/template-twin/request-security", () => ({
  isSameOriginTemplateTwinMutation: () => true,
}));
vi.mock("@/lib/template-twin/read-authority", () => ({
  TemplateTwinVisitReadAuthorityError: class TemplateTwinVisitReadAuthorityError extends Error {},
  requireTemplateTwinVisitReadAuthority: mocks.requireRead,
}));
vi.mock("@/lib/template-twin/visit-mutation-authority", () => ({
  TemplateTwinClinicalMutationAuthorizationError: class TemplateTwinClinicalMutationAuthorizationError extends Error {},
  lockAndAssertOrdinaryClinicalMutation: mocks.lockOrdinary,
}));
vi.mock("@/lib/em-coding/score", () => ({
  computeEmScore: mocks.computeEmScore,
}));
vi.mock("@/lib/em-coding/to-ui-score", () => ({
  engineToUiScore: mocks.engineToUiScore,
}));
vi.mock("@/lib/em-coding/displayed-level", () => ({
  extractIcdRows: () => [],
  extractRxRows: () => [],
  extractEmOverride: () => undefined,
}));

import { TemplateTwinVisitReadAuthorityError } from "@/lib/template-twin/read-authority";
import { TemplateTwinClinicalMutationAuthorizationError } from "@/lib/template-twin/visit-mutation-authority";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import { POST } from "../route";

const VISIT_ID = "visit-provider-execution-boundary";
const DOCTOR_ID = "doctor-provider-execution-boundary";

const ordinaryRead = {
  visitId: VISIT_ID,
  isTemplateTwin: false,
  isSyntheticTemplateTwin: false,
  practiceId: null,
  templateTwinEnabled: null,
};
const twinRead = {
  visitId: VISIT_ID,
  isTemplateTwin: true,
  isSyntheticTemplateTwin: false,
  practiceId: "practice-provider-execution-boundary",
  templateTwinEnabled: true,
};

function visitRow(overrides: Record<string, unknown> = {}) {
  return {
    id: VISIT_ID,
    userId: DOCTOR_ID,
    patientId: "patient-provider-execution-boundary",
    noteTemplateId: "ordinary-template-provider-execution-boundary",
    updatedAt: new Date("2026-07-20T03:00:00.000Z"),
    deletedAt: null,
    archivedAt: null,
    patient: { externalId: null },
    icdCodes: [],
    rxDrafts: [],
    cptCodes: {},
    inputMode: "text_note",
    audioDurationSec: null,
    dictationDurationSec: null,
    noteTemplate: {
      templateKind: "structured",
      templateTwinCompiledVersion: null,
    },
    templateTwinFill: null,
    templateTwinSyntheticQaRun: null,
    templateTwinSyntheticQaAdmission: null,
    templateTwinProviderExecutions: [],
    ...overrides,
  };
}

function request(): NextRequest {
  return new Request(
    `https://app.example.test/api/visits/${VISIT_ID}/em-score`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
        host: "app.example.test",
        origin: "https://app.example.test",
        "sec-fetch-site": "same-origin",
      },
      body: JSON.stringify({ soapText: "Synthetic caller evidence." }),
    },
  ) as unknown as NextRequest;
}

const context = { params: Promise.resolve({ id: VISIT_ID }) };

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({
    user: {
      id: DOCTOR_ID,
      practiceId: "practice-provider-execution-boundary",
    },
  });
  mocks.isOwnedStagingVisit.mockResolvedValue(false);
  mocks.requireRead.mockResolvedValue(ordinaryRead);
  mocks.findUnique.mockResolvedValue(visitRow());
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) => callback({}),
  );
  mocks.lockOrdinary.mockResolvedValue(undefined);
  mocks.computeEmScore.mockResolvedValue({ code: "99213" });
  mocks.engineToUiScore.mockReturnValue({ suggestedCode: "99213" });
});

describe("provider-execution-aware E/M read admission", () => {
  it("denies stale physician authority before projecting clinical columns", async () => {
    mocks.requireRead.mockRejectedValueOnce(
      new TemplateTwinVisitReadAuthorityError(),
    );

    const response = await POST(request(), context);

    expect(response.status).toBe(404);
    expect(mocks.findUnique).not.toHaveBeenCalled();
    expect(mocks.computeEmScore).not.toHaveBeenCalled();
  });

  it("rechecks authority after projection and before model or cache access", async () => {
    mocks.requireRead
      .mockResolvedValueOnce(ordinaryRead)
      .mockRejectedValueOnce(new TemplateTwinVisitReadAuthorityError());

    const response = await POST(request(), context);

    expect(response.status).toBe(404);
    expect(mocks.findUnique).toHaveBeenCalledTimes(1);
    expect(mocks.computeEmScore).not.toHaveBeenCalled();
  });

  it.each(["a durable relation marker", "compiled-version lineage"])(
    "keeps %s races out of the ordinary PHI projection",
    async () => {
      mocks.findUnique.mockResolvedValueOnce(null);

      const response = await POST(request(), context);

      expect(response.status).toBe(404);
      expect(mocks.findUnique).toHaveBeenCalledWith(
        expect.objectContaining({
          where: expect.objectContaining({
            id: VISIT_ID,
            userId: DOCTOR_ID,
            ...TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE,
          }),
        }),
      );
      expect(mocks.computeEmScore).not.toHaveBeenCalled();
    },
  );

  it("blocks provider-execution-only provenance before model or cache access", async () => {
    mocks.requireRead.mockResolvedValue(twinRead);
    mocks.findUnique.mockResolvedValue(
      visitRow({
        noteTemplate: null,
        templateTwinProviderExecutions: [{ id: "execution-1" }],
      }),
    );

    const response = await POST(request(), context);

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      code: "TEMPLATE_TWIN_PROVIDER_BACKED_EM_UNAVAILABLE",
    });
    expect(mocks.computeEmScore).not.toHaveBeenCalled();
    expect(mocks.engineToUiScore).not.toHaveBeenCalled();
  });

  it("blocks an orphaned reserved synthetic patient before projecting clinical fields", async () => {
    mocks.requireRead.mockResolvedValue({
      ...twinRead,
      isSyntheticTemplateTwin: true,
    });
    mocks.findUnique.mockResolvedValue(
      visitRow({
        patient: { externalId: "SYNTHETIC-QA-ONLY" },
        noteTemplate: null,
      }),
    );

    const response = await POST(request(), context);

    expect(response.status).toBe(404);
    expect(mocks.findUnique).not.toHaveBeenCalled();
    expect(mocks.computeEmScore).not.toHaveBeenCalled();
    expect(mocks.engineToUiScore).not.toHaveBeenCalled();
  });

  it("blocks a full synthetic QA decision before projecting clinical fields", async () => {
    mocks.requireRead.mockResolvedValue({
      ...twinRead,
      isSyntheticTemplateTwin: true,
    });

    const response = await POST(request(), context);

    expect(response.status).toBe(404);
    expect(mocks.findUnique).not.toHaveBeenCalled();
    expect(mocks.computeEmScore).not.toHaveBeenCalled();
    expect(mocks.engineToUiScore).not.toHaveBeenCalled();
  });

  it("fails closed when the durable census changes between authority and projection", async () => {
    mocks.requireRead
      .mockResolvedValueOnce(ordinaryRead)
      .mockResolvedValueOnce(twinRead);

    const response = await POST(request(), context);

    expect(response.status).toBe(404);
    expect(mocks.computeEmScore).not.toHaveBeenCalled();
  });

  it("locks exact ordinary provenance before provider egress and after return", async () => {
    const admitted = visitRow();
    mocks.findUnique.mockResolvedValue(admitted);

    const response = await POST(request(), context);

    expect(response.status).toBe(200);
    expect(mocks.lockOrdinary).toHaveBeenCalledTimes(2);
    expect(mocks.lockOrdinary).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        visitId: VISIT_ID,
        actorUserId: DOCTOR_ID,
        admittedVisitUpdatedAt: admitted.updatedAt,
        admittedPatientId: admitted.patientId,
        admittedNoteTemplateId: admitted.noteTemplateId,
      }),
    );
    expect(mocks.computeEmScore).toHaveBeenCalledTimes(1);
  });

  it("blocks an ordinary-to-Twin transition immediately before egress", async () => {
    mocks.lockOrdinary.mockRejectedValueOnce(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
      ),
    );

    const response = await POST(request(), context);

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_CONFLICT",
    });
    expect(mocks.computeEmScore).not.toHaveBeenCalled();
  });

  it("discards the provider result when ordinary provenance changes after return", async () => {
    mocks.lockOrdinary
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(
        new TemplateTwinClinicalMutationAuthorizationError(
          "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
        ),
      );

    const response = await POST(request(), context);

    expect(response.status).toBe(409);
    expect(mocks.computeEmScore).toHaveBeenCalledTimes(1);
    expect(mocks.engineToUiScore).not.toHaveBeenCalled();
  });
});
