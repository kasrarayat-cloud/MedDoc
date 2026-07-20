import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findUnique: vi.fn(),
  transaction: vi.fn(),
  txVisitUpdate: vi.fn(),
  txVisitUpdateMany: vi.fn(),
  txFillUpdateMany: vi.fn(),
  txQueryRaw: vi.fn(),
  requireSession: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeVisit: { findUnique: mocks.findUnique },
    $transaction: mocks.transaction,
  },
}));
vi.mock("@/lib/auth", () => ({ requireSession: mocks.requireSession }));
vi.mock("@/lib/audit", () => ({ logAudit: vi.fn() }));
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));

import { TranscribeVisitStatus } from "@prisma/client";

import { saveSoapDraftAction } from "../soap";

const VISIT_ID = "visit-soap-binding";
const PATIENT_ID = "patient-soap-binding";
const PRACTICE_ID = "practice-soap-binding";
const UPDATED_AT = new Date("2026-07-20T00:00:00.000Z");

function ordinaryVisit(overrides: Record<string, unknown> = {}) {
  return {
    id: VISIT_ID,
    userId: "doctor-1",
    updatedAt: UPDATED_AT,
    status: TranscribeVisitStatus.READY,
    deletedAt: null,
    archivedAt: null,
    signedAt: null,
    soapFinal: "Synthetic SOAP before edit.",
    soapVersion: 7,
    patientId: PATIENT_ID,
    patient: {
      id: PATIENT_ID,
      practiceId: PRACTICE_ID,
      externalId: null,
    },
    noteTemplateId: null,
    noteTemplateVersion: null,
    noteTemplate: null,
    templateTwinFill: null,
    templateTwinSyntheticQaRun: null,
    templateTwinSyntheticQaAdmission: null,
    templateTwinProviderExecutions: [],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireSession.mockResolvedValue({
    user: { id: "doctor-1", email: "doctor@example.test" },
  });
  mocks.findUnique.mockResolvedValue(ordinaryVisit());
  mocks.txVisitUpdateMany.mockResolvedValue({ count: 1 });
  mocks.txVisitUpdate.mockResolvedValue({ soapVersion: 8 });
  mocks.txFillUpdateMany.mockResolvedValue({ count: 1 });
  mocks.txQueryRaw.mockImplementation(async (query: { strings?: string[] }) => {
    const sql = query.strings?.join(" ") ?? "";
    if (sql.includes('FROM "practices"')) {
      return [{ id: PRACTICE_ID, isActive: true }];
    }
    if (sql.includes('FROM "users"')) {
      return [{ id: "doctor-1" }];
    }
    return [{ id: VISIT_ID }];
  });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        $queryRaw: mocks.txQueryRaw,
        transcribeVisit: {
          update: mocks.txVisitUpdate,
          updateMany: mocks.txVisitUpdateMany,
        },
        templateTwinFillManifest: {
          updateMany: mocks.txFillUpdateMany,
        },
      }),
  );
});

describe("SOAP edit invalidates an existing Template Twin", () => {
  it.each([
    ["allergy", "## Allergies\nSynthetic penicillin allergy."],
    ["medication", "## Medications\nSynthetic amoxicillin 500 mg."],
    ["assessment", "## Assessment\nSynthetic viral syndrome."],
    ["plan", "## Plan\nSynthetic hydration plan."],
  ])(
    "atomically invalidates after edited %s content",
    async (_section, soap) => {
      const result = await saveSoapDraftAction(VISIT_ID, soap, 7);

      expect(result).toEqual({ ok: true, newVersion: 8 });
      expect(mocks.transaction).toHaveBeenCalledTimes(1);
      expect(mocks.txVisitUpdateMany).toHaveBeenCalledWith({
        where: {
          id: VISIT_ID,
          userId: "doctor-1",
          soapVersion: 7,
          status: TranscribeVisitStatus.READY,
        },
        data: {
          soapFinal: soap,
          soapVersion: { increment: 1 },
        },
      });
      expect(mocks.txFillUpdateMany).toHaveBeenCalledWith({
        where: {
          visitId: VISIT_ID,
          status: { not: "SIGNED" },
          signedDecisionAt: null,
        },
        data: {
          status: "NEEDS_REVIEW",
          reviewedAt: null,
          reviewedById: null,
          reviewedManifestVersion: null,
          reviewedManifestSha256: null,
        },
      });
    },
  );

  it("does not invalidate a Twin when the SOAP version claim loses", async () => {
    mocks.txVisitUpdateMany.mockResolvedValue({ count: 0 });
    mocks.findUnique
      .mockResolvedValueOnce(ordinaryVisit())
      .mockResolvedValueOnce(ordinaryVisit())
      .mockResolvedValueOnce({
        soapVersion: 9,
        soapFinal: "Newer synthetic SOAP.",
      });

    const result = await saveSoapDraftAction(
      VISIT_ID,
      "Stale synthetic SOAP.",
      7,
    );

    expect(result).toMatchObject({ ok: false, error: "conflict" });
    expect(mocks.txFillUpdateMany).not.toHaveBeenCalled();
  });

  it("invalidates in the legacy no-version save transaction too", async () => {
    const result = await saveSoapDraftAction(
      VISIT_ID,
      "## Plan\nSynthetic legacy-client edit.",
    );

    expect(result).toEqual({ ok: true, newVersion: 8 });
    expect(mocks.txVisitUpdate).toHaveBeenCalledWith({
      where: {
        id: VISIT_ID,
        userId: "doctor-1",
        status: TranscribeVisitStatus.READY,
      },
      data: {
        soapFinal: "## Plan\nSynthetic legacy-client edit.",
        soapVersion: { increment: 1 },
      },
      select: { soapVersion: true },
    });
    expect(mocks.txFillUpdateMany).toHaveBeenCalledTimes(1);
  });
});
