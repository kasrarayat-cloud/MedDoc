import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  visitFindUnique: vi.fn(),
  userFindUnique: vi.fn(),
  createPattern: vi.fn(),
  executeRaw: vi.fn(),
  transaction: vi.fn(),
  embedText: vi.fn(),
  lockOrdinary: vi.fn(),
  logInfo: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeVisit: { findUnique: mocks.visitFindUnique },
    user: { findUnique: mocks.userFindUnique },
    $transaction: mocks.transaction,
  },
}));
vi.mock("@meddoc/ai", () => ({
  embedText: mocks.embedText,
  redactPhi: (value: unknown) => value,
}));
vi.mock("@/lib/template-twin/visit-mutation-authority", () => ({
  TemplateTwinClinicalMutationAuthorizationError: class TemplateTwinClinicalMutationAuthorizationError extends Error {},
  lockAndAssertOrdinaryClinicalMutation: mocks.lockOrdinary,
}));
vi.mock("@/lib/log", () => ({
  log: { info: mocks.logInfo },
}));

import { TemplateTwinClinicalMutationAuthorizationError } from "@/lib/template-twin/visit-mutation-authority";
import { captureEditPattern } from "../edit-tracking";

const VISIT_ID = "ordinary-edit-pattern-visit";
const DOCTOR_ID = "ordinary-edit-pattern-doctor";
const UPDATED_AT = new Date("2026-07-20T03:00:00.000Z");

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  mocks.visitFindUnique.mockResolvedValue({
    soapL6Original: "Synthetic ordinary original note.",
    signedSoap: "Synthetic ordinary signed note.",
    userId: DOCTOR_ID,
    patientId: "ordinary-patient-1",
    noteTemplateId: "ordinary-template-1",
    updatedAt: UPDATED_AT,
    user: { practiceId: "ordinary-practice-1" },
  });
  mocks.userFindUnique.mockResolvedValue({ practiceId: "ordinary-practice-1" });
  mocks.createPattern.mockResolvedValue({ id: "edit-pattern-1" });
  mocks.executeRaw.mockResolvedValue(1);
  mocks.embedText.mockResolvedValue({ embedding: [0.25, 0.5] });
  mocks.lockOrdinary.mockResolvedValue(undefined);
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        doctorEditPattern: { create: mocks.createPattern },
        $executeRaw: mocks.executeRaw,
      }),
  );
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ordinary edit-pattern provider authority", () => {
  it("fences the exact ordinary snapshot before persistence, before egress, and before the vector write", async () => {
    await expect(
      captureEditPattern({ visitId: VISIT_ID, doctorId: DOCTOR_ID }),
    ).resolves.toBeUndefined();

    expect(mocks.visitFindUnique).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          id: VISIT_ID,
          userId: DOCTOR_ID,
          user: expect.any(Object),
          patient: expect.any(Object),
        }),
      }),
    );
    expect(mocks.lockOrdinary).toHaveBeenCalledTimes(3);
    expect(mocks.lockOrdinary).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        visitId: VISIT_ID,
        actorUserId: DOCTOR_ID,
        admittedVisitUpdatedAt: UPDATED_AT,
        admittedPatientId: "ordinary-patient-1",
        admittedNoteTemplateId: "ordinary-template-1",
      }),
    );
    expect(mocks.embedText).toHaveBeenCalledTimes(1);
    expect(mocks.executeRaw).toHaveBeenCalledTimes(1);
  });

  it("blocks an ordinary-to-Twin transition immediately before provider egress", async () => {
    mocks.lockOrdinary
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(
        new TemplateTwinClinicalMutationAuthorizationError(
          "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
        ),
      );

    await expect(
      captureEditPattern({ visitId: VISIT_ID, doctorId: DOCTOR_ID }),
    ).resolves.toBeUndefined();

    expect(mocks.createPattern).toHaveBeenCalledTimes(1);
    expect(mocks.embedText).not.toHaveBeenCalled();
    expect(mocks.executeRaw).not.toHaveBeenCalled();
  });

  it("discards a returned embedding when ordinary provenance changes before write", async () => {
    mocks.lockOrdinary
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(
        new TemplateTwinClinicalMutationAuthorizationError(
          "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
        ),
      );

    await expect(
      captureEditPattern({ visitId: VISIT_ID, doctorId: DOCTOR_ID }),
    ).resolves.toBeUndefined();

    expect(mocks.embedText).toHaveBeenCalledTimes(1);
    expect(mocks.executeRaw).not.toHaveBeenCalled();
  });
});
