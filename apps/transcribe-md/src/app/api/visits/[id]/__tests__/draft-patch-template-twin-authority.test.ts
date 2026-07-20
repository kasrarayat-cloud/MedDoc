import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  findUser: vi.fn(),
  findVisit: vi.fn(),
  findPatient: vi.fn(),
  transaction: vi.fn(),
  txUpdate: vi.fn(),
  txQueryRaw: vi.fn(),
  ownedStaging: vi.fn(),
  sameOrigin: vi.fn(),
  loadAdmission: vi.fn(),
  hasTwin: vi.fn(),
  pinMutation: vi.fn(),
  lockTwin: vi.fn(),
  lockOrdinary: vi.fn(),
  mutationAudit: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    user: { findUnique: mocks.findUser },
    transcribeVisit: { findUnique: mocks.findVisit },
    transcribeMdPatient: { findUnique: mocks.findPatient },
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
vi.mock("@/lib/rate-limit", () => ({
  RATE_LIMITS: { VISIT_OPS: {} },
  rateLimitOr429: vi.fn(() => null),
}));
vi.mock("@/lib/log", () => ({
  log: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock("@/lib/audit", () => ({
  logAudit: vi.fn(),
  logRequiredAudit: vi.fn(),
}));
vi.mock("@/lib/template-twin/staging-qa-access", () => ({
  isOwnedTemplateTwinStagingQaVisit: mocks.ownedStaging,
}));
vi.mock("@/lib/template-twin/request-security", () => ({
  isSameOriginTemplateTwinMutation: mocks.sameOrigin,
}));
vi.mock("@/lib/template-twin/visit-mutation-authority", () => ({
  TEMPLATE_TWIN_CLINICAL_MUTATION_PROVENANCE_SELECT: {},
  TemplateTwinClinicalMutationAuthorizationError: class TemplateTwinClinicalMutationAuthorizationError extends Error {},
  loadTemplateTwinClinicalMutationAdmissionTarget: mocks.loadAdmission,
  hasDurableTemplateTwinClinicalMutationProvenance: mocks.hasTwin,
  pinTemplateTwinClinicalMutation: mocks.pinMutation,
  lockAndAssertTemplateTwinClinicalMutation: mocks.lockTwin,
  lockAndAssertOrdinaryClinicalMutation: mocks.lockOrdinary,
  enqueueTemplateTwinClinicalMutationAudit: mocks.mutationAudit,
}));
vi.mock("@/lib/template-twin/read-authority", () => ({
  TemplateTwinVisitReadAuthorityError: class TemplateTwinVisitReadAuthorityError extends Error {},
  requireTemplateTwinVisitReadAuthority: vi.fn(),
}));
vi.mock("@/lib/auth", () => ({
  AuthError: class AuthError extends Error {},
  requireFreshDoctorIdentity: vi.fn(),
}));
vi.mock("@/lib/template-twin/staging-qa-gate", () => ({
  isTemplateTwinStagingQaRequested: vi.fn(() => false),
  TemplateTwinStagingQaDisabledError: class TemplateTwinStagingQaDisabledError extends Error {},
}));
vi.mock("@/lib/template-twin/staging-qa-visit-guard", () => ({
  assertTemplateTwinStagingQaVisitGuard: vi.fn(),
  TEMPLATE_TWIN_STAGING_QA_RUN_GUARD_SELECT: {},
  TemplateTwinStagingQaVisitGuardError: class TemplateTwinStagingQaVisitGuardError extends Error {},
}));

import { TranscribeVisitStatus } from "@prisma/client";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import { TemplateTwinClinicalMutationAuthorizationError } from "@/lib/template-twin/visit-mutation-authority";
import { PATCH } from "../route";

const VISIT_ID = "visit-1";
const USER_ID = "doctor-1";
const UPDATED_AT = new Date("2026-07-20T00:00:00.000Z");
const CONTEXT = { params: Promise.resolve({ id: VISIT_ID }) };

function row(overrides: Record<string, unknown> = {}) {
  return {
    id: VISIT_ID,
    userId: USER_ID,
    patientId: "patient-1",
    noteTemplateId: "ordinary-template-1",
    specialty: "primary-care",
    chiefComplaint: null,
    inputMode: "text_notes",
    status: TranscribeVisitStatus.QUEUED,
    signedAt: null,
    audioKey: null,
    dictationAudioKey: null,
    rawTextInput: null,
    deletedAt: null,
    archivedAt: null,
    updatedAt: UPDATED_AT,
    patient: { externalId: null },
    twin: false,
    ...overrides,
  };
}

function request(
  body: Record<string, unknown> = { specialty: "cardiology" },
): NextRequest {
  return new Request(`https://app.example.test/api/visits/${VISIT_ID}`, {
    method: "PATCH",
    headers: {
      "content-type": "application/json",
      host: "app.example.test",
      origin: "https://app.example.test",
      "sec-fetch-site": "same-origin",
    },
    body: JSON.stringify(body),
  }) as unknown as NextRequest;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({
    user: { id: USER_ID, practiceId: "practice-1" },
  });
  mocks.findUser.mockResolvedValue({ practiceId: "practice-1" });
  mocks.findVisit.mockResolvedValue(row());
  mocks.loadAdmission.mockResolvedValue(row());
  mocks.hasTwin.mockImplementation(
    (target: {
      twin?: boolean;
      patient?: { externalId?: string | null } | null;
    }) =>
      Boolean(target.twin) ||
      target.patient?.externalId === "SYNTHETIC-QA-ONLY",
  );
  mocks.pinMutation.mockResolvedValue(null);
  mocks.lockTwin.mockResolvedValue(row({ twin: true }));
  mocks.lockOrdinary.mockResolvedValue(undefined);
  mocks.mutationAudit.mockResolvedValue(undefined);
  mocks.ownedStaging.mockResolvedValue(false);
  mocks.sameOrigin.mockReturnValue(true);
  mocks.findPatient.mockResolvedValue({
    id: "patient-2",
    name: "Synthetic Patient",
    practiceId: "practice-1",
    deletedAt: null,
    externalId: null,
  });
  mocks.txQueryRaw.mockResolvedValue([
    {
      id: "patient-2",
      name: "Synthetic Patient",
      practiceId: "practice-1",
      deletedAt: null,
      externalId: null,
    },
  ]);
  mocks.txUpdate.mockResolvedValue({
    id: VISIT_ID,
    patientId: "patient-1",
    specialty: "cardiology",
    chiefComplaint: null,
    inputMode: "text_notes",
    updatedAt: new Date(UPDATED_AT.getTime() + 1_000),
  });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        $queryRaw: mocks.txQueryRaw,
        transcribeVisit: { update: mocks.txUpdate },
      }),
  );
});

describe("draft PATCH Template Twin mutation authority", () => {
  it("returns no metadata snapshot when durable lineage appears after ordinary admission", async () => {
    mocks.loadAdmission.mockResolvedValueOnce(row());
    mocks.findVisit.mockResolvedValueOnce(null);

    const response = await PATCH(request(), CONTEXT);

    expect(response.status).toBe(404);
    expect(mocks.findVisit).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining(
          TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE,
        ),
      }),
    );
    expect(mocks.txUpdate).not.toHaveBeenCalled();
  });

  it("preserves ordinary draft edits behind the exact final ordinary lock", async () => {
    const response = await PATCH(request(), CONTEXT);

    expect(response.status).toBe(200);
    expect(mocks.lockOrdinary).toHaveBeenCalledWith(
      expect.objectContaining({
        visitId: VISIT_ID,
        actorUserId: USER_ID,
        admittedPatientId: "patient-1",
        admittedNoteTemplateId: "ordinary-template-1",
      }),
    );
    expect(mocks.txUpdate).toHaveBeenCalledTimes(1);
    expect(mocks.mutationAudit).not.toHaveBeenCalled();
    expect(mocks.findVisit).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          userId: USER_ID,
          user: {
            is: expect.objectContaining({
              id: USER_ID,
              role: "DOCTOR",
              suspendedAt: null,
              products: { has: "TRANSCRIBE_MD" },
            }),
          },
        }),
      }),
    );
  });

  it("blocks an ordinary-to-Twin race before the metadata write", async () => {
    mocks.lockOrdinary.mockRejectedValueOnce(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
      ),
    );

    const response = await PATCH(request(), CONTEXT);

    expect(response.status).toBe(409);
    expect(mocks.txUpdate).not.toHaveBeenCalled();
  });

  it("rejects an orphaned reserved synthetic patient before consuming the body", async () => {
    const reserved = row({
      patient: { externalId: "SYNTHETIC-QA-ONLY" },
    });
    mocks.loadAdmission.mockResolvedValue(reserved);
    mocks.pinMutation.mockRejectedValueOnce(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
      ),
    );
    const patchRequest = request();
    const json = vi.spyOn(patchRequest, "json");

    const response = await PATCH(patchRequest, CONTEXT);

    expect(response.status).toBe(404);
    expect(json).not.toHaveBeenCalled();
    expect(mocks.findVisit).not.toHaveBeenCalled();
  });

  it("writes and audits a live Twin only after its final exact lock", async () => {
    const twin = row({
      twin: true,
      noteTemplateId: "twin-template-1",
    });
    mocks.loadAdmission.mockResolvedValue(twin);
    mocks.findVisit.mockResolvedValue(twin);
    mocks.pinMutation.mockResolvedValue({
      visitId: VISIT_ID,
      practiceId: "practice-1",
    });
    mocks.lockTwin.mockResolvedValue(twin);

    const response = await PATCH(request(), CONTEXT);

    expect(response.status).toBe(200);
    expect(mocks.lockTwin).toHaveBeenCalledTimes(1);
    expect(mocks.txUpdate).toHaveBeenCalledTimes(1);
    expect(mocks.mutationAudit).toHaveBeenCalledWith(
      expect.objectContaining({ operation: "generic_patch" }),
    );
  });

  it("blocks a live Twin when physician or rollout authority changes", async () => {
    const twin = row({ twin: true });
    mocks.loadAdmission.mockResolvedValue(twin);
    mocks.findVisit.mockResolvedValue(twin);
    mocks.pinMutation.mockResolvedValue({
      visitId: VISIT_ID,
      practiceId: "practice-1",
    });
    mocks.lockTwin.mockRejectedValueOnce(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
      ),
    );

    const response = await PATCH(request(), CONTEXT);

    expect(response.status).toBe(409);
    expect(mocks.txUpdate).not.toHaveBeenCalled();
    expect(mocks.mutationAudit).not.toHaveBeenCalled();
  });

  it("blocks a live Twin when admitted metadata changes before final lock", async () => {
    const twin = row({ twin: true });
    mocks.loadAdmission.mockResolvedValue(twin);
    mocks.findVisit.mockResolvedValue(twin);
    mocks.pinMutation.mockResolvedValue({
      visitId: VISIT_ID,
      practiceId: "practice-1",
    });
    mocks.lockTwin.mockResolvedValue(
      row({ twin: true, specialty: "psychiatry" }),
    );

    const response = await PATCH(request(), CONTEXT);

    expect(response.status).toBe(409);
    expect(mocks.txUpdate).not.toHaveBeenCalled();
    expect(mocks.mutationAudit).not.toHaveBeenCalled();
  });

  it("rolls back a live Twin write when the required outbox enqueue fails", async () => {
    const twin = row({ twin: true });
    mocks.loadAdmission.mockResolvedValue(twin);
    mocks.findVisit.mockResolvedValue(twin);
    mocks.pinMutation.mockResolvedValue({
      visitId: VISIT_ID,
      practiceId: "practice-1",
    });
    mocks.lockTwin.mockResolvedValue(twin);
    mocks.mutationAudit.mockRejectedValueOnce(new Error("outbox unavailable"));
    let committed = false;
    mocks.transaction.mockImplementationOnce(
      async (callback: (tx: unknown) => Promise<unknown>) => {
        let staged = false;
        try {
          const result = await callback({
            $queryRaw: mocks.txQueryRaw,
            transcribeVisit: {
              update: vi.fn(async (...args: unknown[]) => {
                staged = true;
                return mocks.txUpdate(...args);
              }),
            },
          });
          committed = staged;
          return result;
        } catch (error) {
          committed = false;
          throw error;
        }
      },
    );

    await expect(PATCH(request(), CONTEXT)).rejects.toThrow(
      "outbox unavailable",
    );
    expect(committed).toBe(false);
    expect(mocks.mutationAudit).toHaveBeenCalledTimes(1);
  });

  it("relinks from the final current-authority patient lock in the visit transaction", async () => {
    mocks.txUpdate.mockResolvedValueOnce({
      id: VISIT_ID,
      patientId: "patient-2",
      specialty: "primary-care",
      chiefComplaint: null,
      inputMode: "text_notes",
      updatedAt: new Date(UPDATED_AT.getTime() + 1_000),
    });

    const response = await PATCH(request({ patientId: "patient-2" }), CONTEXT);

    expect(response.status).toBe(200);
    expect(mocks.txUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          patientId: "patient-2",
          patientName: "Synthetic Patient",
        }),
      }),
    );
  });

  it("rejects a patient relink if the final locked patient is unavailable", async () => {
    mocks.txQueryRaw.mockResolvedValueOnce([]);

    const response = await PATCH(request({ patientId: "patient-2" }), CONTEXT);

    expect(response.status).toBe(400);
    expect(mocks.txUpdate).not.toHaveBeenCalled();
    const patientSql = mocks.txQueryRaw.mock.calls[0]?.[0];
    const patientText = patientSql?.strings?.join(" ") ?? "";
    expect(patientText).toContain('JOIN "practices" practice');
    expect(patientText).toContain('JOIN "users" actor');
    expect(patientText).toContain('actor."practiceId" = practice."id"');
    expect(patientText).toContain('actor."suspendedAt" IS NULL');
    expect(patientText).toContain("'TRANSCRIBE_MD'::\"Product\"");
    expect(patientText).toContain('patient."deletedAt" IS NULL');
    expect(patientText).toContain('patient."externalId" IS DISTINCT FROM');
    expect(patientText).toContain("FOR UPDATE OF patient");
  });
});
