import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findVisit: vi.fn(),
  transaction: vi.fn(),
  txUpdate: vi.fn(),
  txUpdateMany: vi.fn(),
  session: vi.fn(),
  pinStaging: vi.fn(),
  lockStaging: vi.fn(),
  stagingAudit: vi.fn(),
  ownedStaging: vi.fn(),
  hasTwin: vi.fn(),
  loadAdmission: vi.fn(),
  pinMutation: vi.fn(),
  lockMutation: vi.fn(),
  lockOrdinary: vi.fn(),
  mutationAudit: vi.fn(),
  invalidate: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeVisit: {
      findUnique: mocks.findVisit,
      updateMany: mocks.txUpdateMany,
    },
    $transaction: mocks.transaction,
  },
}));
vi.mock("@/lib/auth", () => ({ requireSession: mocks.session }));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
vi.mock("@/lib/template-twin/soap-binding", () => ({
  invalidateTemplateTwinAfterSoapEdit: mocks.invalidate,
}));
vi.mock("@/lib/template-twin/staging-qa-mutation", () => ({
  pinTemplateTwinStagingQaMutation: mocks.pinStaging,
  lockTemplateTwinStagingQaMutation: mocks.lockStaging,
  assertTemplateTwinStagingQaSoapEdit: vi.fn(),
  enqueueTemplateTwinStagingQaMutationAudit: mocks.stagingAudit,
}));
vi.mock("@/lib/template-twin/staging-qa-visit-guard", () => ({
  TEMPLATE_TWIN_STAGING_QA_RUN_GUARD_SELECT: {},
}));
vi.mock("@/lib/template-twin/staging-qa-access", () => ({
  isOwnedTemplateTwinStagingQaVisit: mocks.ownedStaging,
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

import { TranscribeVisitStatus } from "@prisma/client";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import { TemplateTwinClinicalMutationAuthorizationError } from "@/lib/template-twin/visit-mutation-authority";
import { reassignSpeakerAction, saveSoapDraftAction } from "../soap";

const VISIT_ID = "visit-1";

function liveVisit(overrides: Record<string, unknown> = {}) {
  return {
    id: VISIT_ID,
    userId: "doctor-1",
    status: TranscribeVisitStatus.READY,
    deletedAt: null,
    archivedAt: null,
    signedAt: null,
    updatedAt: new Date("2026-07-20T00:00:00.000Z"),
    soapFinal: "Synthetic SOAP before edit.",
    soapVersion: 7,
    speakerMap: {},
    templateTwinSyntheticQaRun: null,
    twin: true,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.session.mockResolvedValue({
    user: { id: "doctor-1", email: "doctor@example.test" },
  });
  mocks.findVisit.mockResolvedValue(liveVisit());
  mocks.loadAdmission.mockResolvedValue(liveVisit());
  mocks.pinStaging.mockResolvedValue(null);
  mocks.lockStaging.mockResolvedValue(null);
  mocks.ownedStaging.mockResolvedValue(false);
  mocks.hasTwin.mockImplementation((visit: { twin?: boolean }) =>
    Boolean(visit.twin),
  );
  mocks.pinMutation.mockResolvedValue({ visitId: VISIT_ID });
  mocks.lockMutation.mockResolvedValue(liveVisit());
  mocks.mutationAudit.mockResolvedValue(undefined);
  mocks.lockOrdinary.mockResolvedValue(undefined);
  mocks.txUpdateMany.mockResolvedValue({ count: 1 });
  mocks.txUpdate.mockResolvedValue({ soapVersion: 8 });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        transcribeVisit: {
          update: mocks.txUpdate,
          updateMany: mocks.txUpdateMany,
        },
      }),
  );
});

describe("SOAP and speaker Template Twin mutation authority", () => {
  it("returns no SOAP snapshot when durable lineage appears after ordinary admission", async () => {
    const ordinary = liveVisit({ twin: false });
    mocks.loadAdmission.mockResolvedValueOnce(ordinary);
    mocks.pinMutation.mockResolvedValueOnce(null);
    mocks.findVisit.mockResolvedValueOnce(null);

    await expect(
      saveSoapDraftAction(VISIT_ID, "Synthetic SOAP after edit.", 7),
    ).resolves.toMatchObject({ ok: false, error: "Visit not found." });
    expect(mocks.findVisit).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          ...currentClinicalVisitActorWhere("doctor-1"),
          ...TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE,
        }),
      }),
    );
    expect(mocks.txUpdateMany).not.toHaveBeenCalled();
  });

  it("saves a live Twin SOAP edit only after the locked exact-version claim", async () => {
    const result = await saveSoapDraftAction(
      VISIT_ID,
      "Synthetic SOAP after edit.",
      7,
    );

    expect(result).toEqual({ ok: true, newVersion: 8 });
    expect(mocks.lockMutation).toHaveBeenCalledTimes(1);
    expect(mocks.txUpdateMany).toHaveBeenCalledTimes(1);
    expect(mocks.invalidate).toHaveBeenCalledTimes(1);
    expect(mocks.mutationAudit).toHaveBeenCalledTimes(1);
  });

  it("blocks physician, product, practice, or rollout revocation at final claim", async () => {
    mocks.lockMutation.mockRejectedValue(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
      ),
    );

    const result = await saveSoapDraftAction(
      VISIT_ID,
      "Synthetic SOAP after edit.",
      7,
    );

    expect(result).toMatchObject({
      ok: false,
      error: expect.stringContaining("authorization changed"),
    });
    expect(mocks.txUpdateMany).not.toHaveBeenCalled();
    expect(mocks.invalidate).not.toHaveBeenCalled();
  });

  it("returns a PHI-free conflict when SOAP changes or authority is revoked before the write", async () => {
    mocks.lockMutation.mockResolvedValue(
      liveVisit({
        soapFinal: "Concurrent synthetic SOAP.",
        soapVersion: 8,
      }),
    );
    mocks.findVisit.mockResolvedValue(liveVisit());

    const result = await saveSoapDraftAction(
      VISIT_ID,
      "Stale synthetic SOAP.",
      7,
    );

    expect(result).toEqual({ ok: false, error: "conflict" });
    expect(mocks.findVisit).toHaveBeenCalledTimes(1);
    expect(mocks.txUpdateMany).not.toHaveBeenCalled();
    expect(mocks.invalidate).not.toHaveBeenCalled();
  });

  it("rolls back a live Twin SOAP write when required outbox enqueue fails", async () => {
    mocks.mutationAudit.mockRejectedValueOnce(new Error("outbox unavailable"));
    let committed = false;
    mocks.transaction.mockImplementationOnce(
      async (callback: (tx: unknown) => Promise<unknown>) => {
        let staged = false;
        try {
          const result = await callback({
            transcribeVisit: {
              update: mocks.txUpdate,
              updateMany: vi.fn(async (...args: unknown[]) => {
                staged = true;
                return mocks.txUpdateMany(...args);
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
      saveSoapDraftAction(VISIT_ID, "Synthetic SOAP after edit.", 7),
    ).rejects.toThrow("outbox unavailable");
    expect(committed).toBe(false);
    expect(mocks.mutationAudit).toHaveBeenCalledTimes(1);
  });

  it("rejects a legacy no-version Twin save", async () => {
    const result = await saveSoapDraftAction(
      VISIT_ID,
      "Synthetic SOAP after edit.",
    );

    expect(result).toMatchObject({
      ok: false,
      error: expect.stringContaining("current SOAP version"),
    });
    expect(mocks.transaction).not.toHaveBeenCalled();
  });

  it("excludes speaker reassignment because it cannot regenerate Twin evidence", async () => {
    const result = await reassignSpeakerAction(VISIT_ID, "speaker-0", "doctor");

    expect(result).toMatchObject({
      ok: false,
      error: expect.stringContaining("unavailable for Template Twin"),
    });
    expect(mocks.transaction).not.toHaveBeenCalled();
    expect(mocks.txUpdate).not.toHaveBeenCalled();
  });

  it("keeps ordinary speaker reassignment behind the exact final ordinary CAS", async () => {
    const ordinary = liveVisit({
      twin: false,
      speakerMap: {
        "speaker-0": {
          role: "unknown",
          confidence: 0.5,
          reasoning: "Synthetic test fixture.",
        },
      },
    });
    mocks.loadAdmission.mockResolvedValue(ordinary);
    mocks.findVisit.mockResolvedValue(ordinary);

    const result = await reassignSpeakerAction(VISIT_ID, "speaker-0", "doctor");

    expect(result).toEqual({ ok: true });
    expect(mocks.txUpdateMany).toHaveBeenCalledWith({
      where: {
        id: VISIT_ID,
        userId: "doctor-1",
        updatedAt: ordinary.updatedAt,
        deletedAt: null,
        archivedAt: null,
        signedAt: null,
        status: { not: TranscribeVisitStatus.SIGNED },
        speakerMap: { equals: ordinary.speakerMap },
        ...TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE,
      },
      data: {
        speakerMap: {
          "speaker-0": expect.objectContaining({ role: "doctor" }),
        },
      },
    });
    expect(mocks.logAudit).toHaveBeenCalledTimes(1);
  });

  it("fails closed when ordinary current authority is revoked before the speaker write", async () => {
    const ordinary = liveVisit({ twin: false });
    mocks.loadAdmission.mockResolvedValue(ordinary);
    mocks.findVisit.mockResolvedValue(ordinary);
    mocks.lockOrdinary.mockRejectedValueOnce(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
      ),
    );

    const result = await reassignSpeakerAction(VISIT_ID, "speaker-0", "doctor");

    expect(result).toMatchObject({
      ok: false,
      error: expect.stringContaining("changed"),
    });
    expect(mocks.txUpdateMany).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("fails closed when a durable relation appears before the speaker write", async () => {
    const ordinary = liveVisit({ twin: false });
    mocks.loadAdmission.mockResolvedValue(ordinary);
    mocks.findVisit.mockResolvedValue(ordinary);
    mocks.txUpdateMany.mockResolvedValueOnce({ count: 0 });

    const result = await reassignSpeakerAction(VISIT_ID, "speaker-0", "doctor");

    expect(result).toMatchObject({
      ok: false,
      error: expect.stringContaining("changed"),
    });
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });
});
