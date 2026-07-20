import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findVisit: vi.fn(),
  requireFreshDoctor: vi.fn(),
  assertGuard: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: { transcribeVisit: { findUnique: mocks.findVisit } },
}));
vi.mock("@/lib/auth", () => ({
  AuthError: class AuthError extends Error {},
  requireFreshDoctorIdentity: mocks.requireFreshDoctor,
}));
vi.mock("../staging-qa-gate", () => ({
  TemplateTwinStagingQaDisabledError: class TemplateTwinStagingQaDisabledError extends Error {},
}));
vi.mock("../staging-qa-visit-guard", () => ({
  TEMPLATE_TWIN_STAGING_QA_RUN_GUARD_SELECT: {
    id: true,
    attempt: true,
    admission: { select: { id: true } },
  },
  TemplateTwinStagingQaVisitGuardError: class TemplateTwinStagingQaVisitGuardError extends Error {},
  assertTemplateTwinStagingQaVisitGuard: mocks.assertGuard,
}));

import { TemplateTwinStagingQaVisitGuardError } from "../staging-qa-visit-guard";
import {
  requireTemplateTwinSyntheticReadAdmission,
  TemplateTwinSyntheticReadAdmissionError,
} from "../synthetic-read-admission";

const liveDecision = {
  visitId: "visit-1",
  isTemplateTwin: true,
  isSyntheticTemplateTwin: false,
  practiceId: "practice-1",
  templateTwinEnabled: true,
};
const syntheticDecision = {
  ...liveDecision,
  isSyntheticTemplateTwin: true,
};
const run = { id: "run-1", attempt: 4 };

beforeEach(() => {
  vi.clearAllMocks();
  mocks.findVisit.mockResolvedValue({
    id: "visit-1",
    userId: "doctor-1",
    templateTwinSyntheticQaRun: run,
  });
  mocks.requireFreshDoctor.mockResolvedValue({
    practiceId: "practice-1",
    rolloutToken: { practiceId: "practice-1" },
  });
});

describe("PHI-minimal synthetic read admission", () => {
  it("does no staging lookup for ordinary or live-Twin reads", async () => {
    await expect(
      requireTemplateTwinSyntheticReadAdmission({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        readDecision: liveDecision,
      }),
    ).resolves.toBeNull();
    expect(mocks.findVisit).not.toHaveBeenCalled();
  });

  it.each(["admission-only", "pre-certification", "orphan reserved-patient"])(
    "denies %s state when no exact full QA run exists",
    async () => {
      mocks.findVisit.mockResolvedValue({
        id: "visit-1",
        userId: "doctor-1",
        templateTwinSyntheticQaRun: null,
      });

      await expect(
        requireTemplateTwinSyntheticReadAdmission({
          visitId: "visit-1",
          actorUserId: "doctor-1",
          readDecision: syntheticDecision,
        }),
      ).rejects.toBeInstanceOf(TemplateTwinSyntheticReadAdmissionError);
      expect(mocks.requireFreshDoctor).not.toHaveBeenCalled();
      expect(mocks.assertGuard).not.toHaveBeenCalled();
      const projection = JSON.stringify(mocks.findVisit.mock.calls[0]?.[0]);
      expect(projection).not.toMatch(/soap|transcript|audio|patientName/i);
    },
  );

  it("admits only the exact current run, physician, practice, and rollout epoch", async () => {
    await expect(
      requireTemplateTwinSyntheticReadAdmission({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        readDecision: syntheticDecision,
      }),
    ).resolves.toEqual({
      visitId: "visit-1",
      practiceId: "practice-1",
      runId: "run-1",
      attempt: 4,
    });
    expect(mocks.assertGuard).toHaveBeenCalledWith(
      expect.objectContaining({
        run,
        actor: { userId: "doctor-1", practiceId: "practice-1" },
        expectedRunId: "run-1",
      }),
    );
    expect(mocks.findVisit).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { id: "visit-1", userId: "doctor-1" },
      }),
    );
  });

  it("fails closed when the attempt changes between admission and response", async () => {
    await expect(
      requireTemplateTwinSyntheticReadAdmission({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        readDecision: syntheticDecision,
        expected: {
          visitId: "visit-1",
          practiceId: "practice-1",
          runId: "run-1",
          attempt: 3,
        },
      }),
    ).rejects.toBeInstanceOf(TemplateTwinSyntheticReadAdmissionError);
    expect(mocks.assertGuard).not.toHaveBeenCalled();
  });

  it("rejects a classifier decision for a different visit before any lookup", async () => {
    await expect(
      requireTemplateTwinSyntheticReadAdmission({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        readDecision: { ...syntheticDecision, visitId: "visit-other" },
      }),
    ).rejects.toBeInstanceOf(TemplateTwinSyntheticReadAdmissionError);
    expect(mocks.findVisit).not.toHaveBeenCalled();
    expect(mocks.requireFreshDoctor).not.toHaveBeenCalled();
    expect(mocks.assertGuard).not.toHaveBeenCalled();
  });

  it("fails closed when rollout/admission authority is revoked at reassertion", async () => {
    mocks.assertGuard.mockImplementation(() => {
      throw new TemplateTwinStagingQaVisitGuardError(
        "TEMPLATE_TWIN_STAGING_QA_ROLLOUT_STALE",
        "synthetic private detail",
      );
    });

    await expect(
      requireTemplateTwinSyntheticReadAdmission({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        readDecision: syntheticDecision,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinSyntheticReadAdmissionError);
  });
});
