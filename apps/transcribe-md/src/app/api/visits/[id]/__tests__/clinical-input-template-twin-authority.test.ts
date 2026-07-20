import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  findVisit: vi.fn(),
  updateVisit: vi.fn(),
  txUpdateVisit: vi.fn(),
  transaction: vi.fn(),
  enqueue: vi.fn(),
  ownedStaging: vi.fn(),
  sameOrigin: vi.fn(),
  hasTwin: vi.fn(),
  loadAdmission: vi.fn(),
  pinMutation: vi.fn(),
  lockMutation: vi.fn(),
  lockOrdinary: vi.fn(),
  mutationAudit: vi.fn(),
  putAudio: vi.fn(),
  deleteAudio: vi.fn(),
  buildAudioKey: vi.fn(),
  logAudit: vi.fn(),
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
  RATE_LIMITS: { UPLOAD: {}, VISIT_OPS: {} },
  rateLimitOr429: vi.fn(() => null),
}));
vi.mock("@/lib/queue", () => ({ enqueueProcessVisit: mocks.enqueue }));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));
vi.mock("@/lib/log", () => ({
  log: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock("@/lib/minio", () => ({
  putAudioStream: mocks.putAudio,
  deleteAudioObject: mocks.deleteAudio,
  buildAudioObjectKey: mocks.buildAudioKey,
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
  hasDurableTemplateTwinClinicalMutationProvenance: mocks.hasTwin,
  loadTemplateTwinClinicalMutationAdmissionTarget: mocks.loadAdmission,
  pinTemplateTwinClinicalMutation: mocks.pinMutation,
  lockAndAssertTemplateTwinClinicalMutation: mocks.lockMutation,
  lockAndAssertOrdinaryClinicalMutation: mocks.lockOrdinary,
  enqueueTemplateTwinClinicalMutationAudit: mocks.mutationAudit,
}));
vi.mock("@/lib/auth", () => ({
  AuthError: class AuthError extends Error {},
  requireFreshDoctorIdentity: vi.fn(),
}));
vi.mock("@/lib/template-twin/staging-qa-gate", () => ({
  TemplateTwinStagingQaDisabledError: class TemplateTwinStagingQaDisabledError extends Error {},
}));
vi.mock("@/lib/template-twin/staging-qa-service", () => ({
  TemplateTwinStagingQaError: class TemplateTwinStagingQaError extends Error {},
  TemplateTwinStagingQaRetryRequestSchema: {
    safeParse: vi.fn(() => ({ success: false })),
  },
  retryTemplateTwinStagingQaRun: vi.fn(),
}));
vi.mock("@/lib/template-twin/staging-qa-request", () => ({
  TemplateTwinStagingQaRequestError: class TemplateTwinStagingQaRequestError extends Error {},
  readBoundedTemplateTwinStagingQaJson: vi.fn(),
}));

import { TranscribeVisitStatus } from "@prisma/client";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import { TemplateTwinClinicalMutationAuthorizationError } from "@/lib/template-twin/visit-mutation-authority";
import { POST as uploadDictation } from "../dictation/upload/route";
import { POST as retryVisit } from "../retry/route";
import { POST as submitText } from "../text/route";
import { POST as uploadAudio } from "../upload/route";

const VISIT_ID = "visit-1";
const USER_ID = "doctor-1";
const CONTEXT = { params: Promise.resolve({ id: VISIT_ID }) };

function row(overrides: Record<string, unknown> = {}) {
  return {
    id: VISIT_ID,
    userId: USER_ID,
    patientId: "patient-1",
    patient: { externalId: null },
    noteTemplateId: "ordinary-template-1",
    inputMode: "text_notes",
    status: TranscribeVisitStatus.QUEUED,
    rawTextInput: null,
    audioKey: null,
    dictationAudioKey: null,
    deletedAt: null,
    archivedAt: null,
    signedAt: null,
    updatedAt: new Date("2026-07-20T01:00:00.000Z"),
    manualRetryCount: 0,
    templateTwinSyntheticQaRun: null,
    twin: false,
    ...overrides,
  };
}

function textRequest(): NextRequest {
  return new Request(`https://app.example.test/api/visits/${VISIT_ID}/text`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      text: "Synthetic typed evidence with enough bounded characters.",
    }),
  }) as unknown as NextRequest;
}

function audioRequest(path: string): NextRequest {
  const body = Buffer.from("RIFF0000WAVEfmt ", "ascii");
  return new Request(`https://app.example.test${path}`, {
    method: "POST",
    headers: {
      "content-type": "audio/wav",
      "content-length": String(body.byteLength),
      "x-tm-filename": "synthetic.wav",
    },
    body,
  }) as unknown as NextRequest;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({
    user: { id: USER_ID, email: "doctor@example.test" },
  });
  mocks.findVisit.mockResolvedValue(row());
  mocks.loadAdmission.mockImplementation(async () => mocks.findVisit());
  mocks.updateVisit.mockResolvedValue({ id: VISIT_ID });
  mocks.txUpdateVisit.mockResolvedValue({ id: VISIT_ID });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({ transcribeVisit: { update: mocks.txUpdateVisit } }),
  );
  mocks.enqueue.mockResolvedValue(undefined);
  mocks.ownedStaging.mockResolvedValue(false);
  mocks.sameOrigin.mockReturnValue(true);
  mocks.hasTwin.mockImplementation(
    (visit: {
      twin?: boolean;
      patient?: { externalId?: string | null } | null;
    }) =>
      Boolean(visit.twin) || visit.patient?.externalId === "SYNTHETIC-QA-ONLY",
  );
  mocks.pinMutation.mockResolvedValue({ visitId: VISIT_ID });
  mocks.lockMutation.mockResolvedValue(row({ twin: true }));
  mocks.lockOrdinary.mockResolvedValue(undefined);
  mocks.mutationAudit.mockResolvedValue(undefined);
  mocks.putAudio.mockResolvedValue(undefined);
  mocks.deleteAudio.mockResolvedValue(undefined);
  mocks.buildAudioKey.mockReturnValue(
    `${USER_ID}/${VISIT_ID}/new-synthetic.wav`,
  );
});

describe("generic clinical-input Twin mutation authority", () => {
  it.each([
    ["typed input", submitText, textRequest],
    [
      "bulk audio",
      uploadAudio,
      () => audioRequest("/api/visits/visit-1/upload"),
    ],
    [
      "dictation",
      uploadDictation,
      () => audioRequest("/api/visits/visit-1/dictation/upload"),
    ],
  ] as const)(
    "returns no clinical snapshot for %s when durable lineage appears after admission",
    async (_label, handler, requestFactory) => {
      const ordinary = row({
        inputMode:
          handler === uploadAudio
            ? "audio_upload"
            : handler === uploadDictation
              ? "voice_dictation"
              : "text_notes",
      });
      mocks.loadAdmission.mockResolvedValueOnce(ordinary);
      // Models the same SELECT missing because its conditional durable
      // predicate observes a newly attached relation/compiled marker.
      mocks.findVisit.mockResolvedValueOnce(null);

      const response = await handler(requestFactory(), CONTEXT);

      expect(response.status).toBe(404);
      expect(mocks.findVisit).toHaveBeenCalledWith(
        expect.objectContaining({
          where: expect.objectContaining({
            ...currentClinicalVisitActorWhere(USER_ID),
            ...TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE,
          }),
        }),
      );
      expect(mocks.txUpdateVisit).not.toHaveBeenCalled();
      expect(mocks.putAudio).not.toHaveBeenCalled();
      expect(mocks.enqueue).not.toHaveBeenCalled();
    },
  );

  it("preserves ordinary typed input behind the exact final ordinary lock", async () => {
    const response = await submitText(textRequest(), CONTEXT);

    expect(response.status).toBe(202);
    expect(mocks.txUpdateVisit).toHaveBeenCalledTimes(1);
    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(mocks.lockOrdinary).toHaveBeenCalledWith(
      expect.objectContaining({
        visitId: VISIT_ID,
        actorUserId: USER_ID,
        admittedPatientId: "patient-1",
        admittedNoteTemplateId: "ordinary-template-1",
      }),
    );
    expect(mocks.lockMutation).not.toHaveBeenCalled();
    expect(mocks.enqueue).toHaveBeenCalledTimes(1);
  });

  it("blocks an ordinary-to-Twin relation race before typed input is written", async () => {
    mocks.lockOrdinary.mockRejectedValueOnce(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
      ),
    );

    const response = await submitText(textRequest(), CONTEXT);

    expect(response.status).toBe(409);
    expect(mocks.txUpdateVisit).not.toHaveBeenCalled();
    expect(mocks.enqueue).not.toHaveBeenCalled();
  });

  it("rejects an orphaned reserved synthetic patient before reading typed clinical input", async () => {
    mocks.findVisit.mockResolvedValue(
      row({ patient: { externalId: "SYNTHETIC-QA-ONLY" } }),
    );
    mocks.pinMutation.mockRejectedValueOnce(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
      ),
    );
    const request = textRequest();
    const json = vi.spyOn(request, "json");

    const response = await submitText(request, CONTEXT);

    expect(response.status).toBe(404);
    expect(json).not.toHaveBeenCalled();
    expect(mocks.txUpdateVisit).not.toHaveBeenCalled();
  });

  it("rejects a cross-origin Twin typed mutation before reading the clinical body", async () => {
    mocks.findVisit.mockResolvedValue(row({ twin: true }));
    mocks.sameOrigin.mockReturnValue(false);
    const request = textRequest();
    const json = vi.spyOn(request, "json");

    const response = await submitText(request, CONTEXT);

    expect(response.status).toBe(404);
    expect(json).not.toHaveBeenCalled();
    expect(mocks.pinMutation).not.toHaveBeenCalled();
    expect(mocks.updateVisit).not.toHaveBeenCalled();
  });

  it("blocks Twin typed input when final physician/rollout authority is revoked", async () => {
    mocks.findVisit.mockResolvedValue(row({ twin: true }));
    mocks.lockMutation.mockRejectedValue(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
      ),
    );

    const response = await submitText(textRequest(), CONTEXT);

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      code: "TEMPLATE_TWIN_AUTHORIZATION_CHANGED",
    });
    expect(mocks.txUpdateVisit).not.toHaveBeenCalled();
    expect(mocks.enqueue).not.toHaveBeenCalled();
  });

  it("blocks a concurrent Twin typed-input claim", async () => {
    mocks.findVisit.mockResolvedValue(row({ twin: true }));
    mocks.lockMutation.mockResolvedValue(
      row({ twin: true, rawTextInput: "Concurrent synthetic evidence." }),
    );

    const response = await submitText(textRequest(), CONTEXT);

    expect(response.status).toBe(409);
    expect(mocks.txUpdateVisit).not.toHaveBeenCalled();
    expect(mocks.enqueue).not.toHaveBeenCalled();
  });

  it.each([
    ["bulk audio", uploadAudio, "/api/visits/visit-1/upload", "audio_upload"],
    [
      "dictation",
      uploadDictation,
      "/api/visits/visit-1/dictation/upload",
      "voice_dictation",
    ],
  ] as const)(
    "rejects cross-origin Twin %s before object storage",
    async (_label, handler, path, inputMode) => {
      mocks.findVisit.mockResolvedValue(row({ twin: true, inputMode }));
      mocks.sameOrigin.mockReturnValue(false);

      const response = await handler(audioRequest(path), CONTEXT);

      expect(response.status).toBe(404);
      expect(mocks.putAudio).not.toHaveBeenCalled();
      expect(mocks.updateVisit).not.toHaveBeenCalled();
    },
  );

  it("rolls back Twin upload metadata and deletes object bytes when outbox enqueue fails", async () => {
    const current = row({ twin: true, inputMode: "audio_upload" });
    mocks.findVisit.mockResolvedValue(current);
    mocks.lockMutation.mockResolvedValue(current);
    mocks.mutationAudit.mockRejectedValueOnce(new Error("outbox unavailable"));
    let committed = false;
    mocks.transaction.mockImplementationOnce(
      async (callback: (tx: unknown) => Promise<unknown>) => {
        let staged = false;
        try {
          const result = await callback({
            transcribeVisit: {
              update: vi.fn(async (...args: unknown[]) => {
                staged = true;
                return mocks.txUpdateVisit(...args);
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

    await expect(
      uploadAudio(audioRequest("/api/visits/visit-1/upload"), CONTEXT),
    ).rejects.toThrow("outbox unavailable");
    expect(committed).toBe(false);
    expect(mocks.deleteAudio).toHaveBeenCalledTimes(1);
    expect(mocks.enqueue).not.toHaveBeenCalled();
  });

  it("deletes an ordinary upload object when Twin provenance appears before the DB write", async () => {
    mocks.findVisit.mockResolvedValue(row({ inputMode: "audio_upload" }));
    mocks.lockOrdinary.mockRejectedValueOnce(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
      ),
    );

    const response = await uploadAudio(
      audioRequest("/api/visits/visit-1/upload"),
      CONTEXT,
    );

    expect(response.status).toBe(409);
    expect(mocks.putAudio).toHaveBeenCalledTimes(1);
    expect(mocks.deleteAudio).toHaveBeenCalledTimes(1);
    expect(mocks.txUpdateVisit).not.toHaveBeenCalled();
    expect(mocks.enqueue).not.toHaveBeenCalled();
  });

  it.each([
    ["bulk audio", uploadAudio, "/api/visits/visit-1/upload", "audio_upload"],
    [
      "dictation",
      uploadDictation,
      "/api/visits/visit-1/dictation/upload",
      "voice_dictation",
    ],
  ] as const)(
    "rolls back a stored Twin %s object when final authority is revoked",
    async (_label, handler, path, inputMode) => {
      const current = row({ twin: true, inputMode });
      mocks.findVisit.mockResolvedValue(current);
      mocks.lockMutation.mockRejectedValue(
        new TemplateTwinClinicalMutationAuthorizationError(
          "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
        ),
      );

      const response = await handler(audioRequest(path), CONTEXT);

      expect(response.status).toBe(409);
      expect(mocks.putAudio).toHaveBeenCalledTimes(1);
      expect(mocks.deleteAudio).toHaveBeenCalledTimes(1);
      expect(mocks.txUpdateVisit).not.toHaveBeenCalled();
      expect(mocks.enqueue).not.toHaveBeenCalled();
    },
  );

  it("retries a live Twin only after an exact locked target claim", async () => {
    const current = row({
      twin: true,
      inputMode: "text_notes",
      status: TranscribeVisitStatus.FAILED,
      updatedAt: new Date("2026-07-20T00:00:00.000Z"),
    });
    mocks.findVisit.mockResolvedValue(current);
    mocks.lockMutation.mockResolvedValue(current);

    const response = await retryVisit(
      new Request(`https://app.example.test/api/visits/${VISIT_ID}/retry`, {
        method: "POST",
      }) as unknown as NextRequest,
      CONTEXT,
    );

    expect(response.status).toBe(200);
    expect(mocks.lockMutation).toHaveBeenCalledTimes(1);
    expect(mocks.txUpdateVisit).toHaveBeenCalledTimes(1);
    expect(mocks.enqueue).toHaveBeenCalledTimes(1);
  });

  it("blocks retry when the Twin retry counter changes before final claim", async () => {
    const current = row({
      twin: true,
      status: TranscribeVisitStatus.FAILED,
      updatedAt: new Date("2026-07-20T00:00:00.000Z"),
    });
    mocks.findVisit.mockResolvedValue(current);
    mocks.lockMutation.mockResolvedValue({
      ...current,
      manualRetryCount: 1,
    });

    const response = await retryVisit(
      new Request(`https://app.example.test/api/visits/${VISIT_ID}/retry`, {
        method: "POST",
      }) as unknown as NextRequest,
      CONTEXT,
    );

    expect(response.status).toBe(409);
    expect(mocks.txUpdateVisit).not.toHaveBeenCalled();
    expect(mocks.enqueue).not.toHaveBeenCalled();
  });
});
