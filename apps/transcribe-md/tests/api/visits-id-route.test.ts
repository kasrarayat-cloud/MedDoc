// ============================================================================
// Unit tests for /api/visits/[id] (smoke F-B-003 fix).
// ----------------------------------------------------------------------------
// Covers GET (added in this PR) plus a PATCH happy-path regression so the
// new GET handler can't accidentally break the existing edit handler.
//
// Mocks:
//   @meddoc/db        — prisma.transcribeVisit.findUnique / update,
//                       prisma.user.findUnique
//   @/lib/nextauth    — auth() returning a session
//   @/lib/rate-limit  — rateLimitOr429 returning null (always allow)
//   @/lib/log         — log.info no-op
// ============================================================================

import { beforeEach, describe, expect, it, vi } from "vitest";
import { TranscribeVisitStatus } from "@prisma/client";

const mocks = vi.hoisted(() => ({
  visitFindFirst: vi.fn(),
  visitFindUnique: vi.fn(),
  visitUpdate: vi.fn(),
  userFindUnique: vi.fn(),
  patientFindUnique: vi.fn(),
  stagingRunFindFirst: vi.fn(),
  readQueryRaw: vi.fn(),
  txQueryRaw: vi.fn(),
  transaction: vi.fn(),
  auth: vi.fn(),
  rateLimitOr429: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeVisit: {
      findFirst: mocks.visitFindFirst,
      findUnique: mocks.visitFindUnique,
      update: mocks.visitUpdate,
    },
    user: { findUnique: mocks.userFindUnique },
    transcribeMdPatient: { findUnique: mocks.patientFindUnique },
    templateTwinSyntheticQaRun: { findFirst: mocks.stagingRunFindFirst },
    $queryRaw: mocks.readQueryRaw,
    $transaction: mocks.transaction,
  },
}));

vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));

vi.mock("@/lib/rate-limit", () => ({
  RATE_LIMITS: {
    VISIT_OPS: { bucket: "visit-ops", limit: 30, windowMs: 3_600_000 },
  },
  rateLimitOr429: mocks.rateLimitOr429,
}));

vi.mock("@/lib/log", () => ({
  log: { info: vi.fn(), error: vi.fn(), warn: vi.fn() },
}));

import { GET, PATCH } from "@/app/api/visits/[id]/route";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";

const FAKE_USER_ID = "user_owner_1";
const FAKE_VISIT_ID = "cmoqn96fe001501l543vfe1u2";
const FAKE_PATIENT_ID = "pat_1";
const FAKE_PRACTICE_ID = "practice_1";
const UPDATED_AT = new Date("2026-07-20T00:00:00.000Z");

const ORDINARY_PROVENANCE = {
  patientId: FAKE_PATIENT_ID,
  patient: {
    id: FAKE_PATIENT_ID,
    practiceId: FAKE_PRACTICE_ID,
    externalId: null,
  },
  noteTemplateId: null,
  noteTemplateVersion: null,
  noteTemplate: null,
  templateTwinFill: null,
  templateTwinSyntheticQaRun: null,
  templateTwinSyntheticQaAdmission: null,
  templateTwinProviderExecutions: [],
} as const;

function ordinaryDraft(overrides: Record<string, unknown> = {}) {
  return {
    id: FAKE_VISIT_ID,
    userId: FAKE_USER_ID,
    updatedAt: UPDATED_AT,
    status: TranscribeVisitStatus.QUEUED,
    signedAt: null,
    audioKey: null,
    dictationAudioKey: null,
    rawTextInput: null,
    deletedAt: null,
    archivedAt: null,
    specialty: "primary-care",
    chiefComplaint: "initial CC",
    inputMode: "audio_upload",
    ...ORDINARY_PROVENANCE,
    ...overrides,
  };
}

const ORDINARY_READ_AUTHORITY = {
  visitId: FAKE_VISIT_ID,
  isTemplateTwin: false,
  isSyntheticTemplateTwin: false,
  isInternalPreCertification: false,
  authorized: true,
  practiceId: null,
  templateTwinEnabled: null,
} as const;

function makeReq(method: string, body?: unknown) {
  const init: RequestInit = { method };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
    init.headers = { "content-type": "application/json" };
  }
  return new Request(
    `http://localhost/api/visits/${FAKE_VISIT_ID}`,
    init,
  ) as unknown as Parameters<typeof GET>[0];
}

const ctx = { params: Promise.resolve({ id: FAKE_VISIT_ID }) };

beforeEach(() => {
  vi.clearAllMocks();
  mocks.rateLimitOr429.mockReturnValue(null);
  mocks.stagingRunFindFirst.mockResolvedValue(null);
  mocks.readQueryRaw.mockResolvedValue([ORDINARY_READ_AUTHORITY]);
  mocks.txQueryRaw.mockResolvedValue([{ id: FAKE_VISIT_ID }]);
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        $queryRaw: mocks.txQueryRaw,
        transcribeVisit: { update: mocks.visitUpdate },
      }),
  );
});

describe("GET /api/visits/[id]", () => {
  it("returns 200 + visit JSON for the owner", async () => {
    mocks.auth.mockResolvedValue({ user: { id: FAKE_USER_ID } });
    mocks.visitFindFirst.mockResolvedValue({
      id: FAKE_VISIT_ID,
      userId: FAKE_USER_ID,
      patientId: FAKE_PATIENT_ID,
      patientName: "Smoke Patient",
      specialty: "primary-care",
      chiefComplaint: "chest pain",
      inputMode: "audio_upload",
      status: TranscribeVisitStatus.READY,
      needsReview: true,
      reviewReason: "missing red-flag screening",
      audioDurationSec: 56,
      soapFinal: "## Subjective\n...",
      transcriptText: "Doctor: ...",
      icdCodes: { codes: [] },
      cptCodes: { codes: [] },
      rxDrafts: { prescriptions: [] },
      patient: {
        id: FAKE_PATIENT_ID,
        name: "Smoke Patient",
        dateOfBirth: new Date("1965-03-15"),
      },
      createdAt: new Date("2026-05-04T03:32:46.155Z"),
      updatedAt: UPDATED_AT,
      deletedAt: null,
      archivedAt: null,
    });

    const res = await GET(makeReq("GET"), ctx);
    expect(res.status).toBe(200);
    const body = (await res.json()) as {
      visit: { id: string; status: string };
    };
    expect(body.visit.id).toBe(FAKE_VISIT_ID);
    expect(body.visit.status).toBe("READY");
  });

  it("returns 404 for a foreign visit (anti-enumeration: same code as not-found)", async () => {
    mocks.auth.mockResolvedValue({ user: { id: FAKE_USER_ID } });
    mocks.readQueryRaw.mockResolvedValue([]);
    mocks.visitFindFirst.mockResolvedValue({
      id: FAKE_VISIT_ID,
      userId: "user_owner_2", // different owner
      patientId: "pat_2",
      patientName: "Other",
      specialty: "primary-care",
      chiefComplaint: "x",
      inputMode: "audio_upload",
      status: TranscribeVisitStatus.READY,
    });

    const res = await GET(makeReq("GET"), ctx);
    expect(res.status).toBe(404);
  });

  it("returns 404 when the visit row does not exist", async () => {
    mocks.auth.mockResolvedValue({ user: { id: FAKE_USER_ID } });
    mocks.readQueryRaw.mockResolvedValue([]);
    mocks.visitFindFirst.mockResolvedValue(null);

    const res = await GET(makeReq("GET"), ctx);
    expect(res.status).toBe(404);
  });

  it("returns 401 for unauthenticated callers", async () => {
    mocks.auth.mockResolvedValue(null);

    const res = await GET(makeReq("GET"), ctx);
    expect(res.status).toBe(401);
    expect(mocks.visitFindFirst).not.toHaveBeenCalled();
    expect(mocks.readQueryRaw).not.toHaveBeenCalled();
  });
});

describe("PATCH /api/visits/[id] (regression)", () => {
  it("updates the chief complaint of a draft visit", async () => {
    mocks.auth.mockResolvedValue({ user: { id: FAKE_USER_ID } });
    mocks.userFindUnique.mockResolvedValue({ practiceId: FAKE_PRACTICE_ID });
    mocks.visitFindUnique.mockResolvedValue(ordinaryDraft());
    mocks.txQueryRaw
      .mockResolvedValueOnce([{ id: FAKE_PRACTICE_ID, isActive: true }])
      .mockResolvedValueOnce([{ id: FAKE_USER_ID }])
      .mockResolvedValueOnce([{ id: FAKE_VISIT_ID }]);
    mocks.visitUpdate.mockResolvedValue({
      id: FAKE_VISIT_ID,
      patientId: "pat_1",
      specialty: "primary-care",
      chiefComplaint: "updated CC",
      inputMode: "audio_upload",
      updatedAt: new Date(),
    });

    const res = await PATCH(
      makeReq("PATCH", { chiefComplaint: "updated CC" }),
      ctx,
    );
    expect(res.status).toBe(200);
    const body = (await res.json()) as { visit: { chiefComplaint: string } };
    expect(body.visit.chiefComplaint).toBe("updated CC");
    expect(mocks.visitFindUnique).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        where: expect.objectContaining(
          TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE,
        ),
      }),
    );
    expect(mocks.txQueryRaw).toHaveBeenCalledTimes(3);
  });
});
