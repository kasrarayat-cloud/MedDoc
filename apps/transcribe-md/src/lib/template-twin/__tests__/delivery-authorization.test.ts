import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findVisit: vi.fn(),
  runTransaction: vi.fn(),
  freshDoctor: vi.fn(),
  assessSigning: vi.fn(),
  finalRollout: vi.fn(),
  lockPhysician: vi.fn(),
  lockVisit: vi.fn(),
  findRetry: vi.fn(),
  findFill: vi.fn(),
  verifyEncounter: vi.fn(),
  lockAutomation: vi.fn(),
  assertStaging: vi.fn(),
  lockStaging: vi.fn(),
  enqueueAudit: vi.fn(),
  requireRead: vi.fn(),
  requireSyntheticRead: vi.fn(),
  claimOrdinaryActor: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeVisit: { findFirst: mocks.findVisit },
  },
}));
vi.mock("@/lib/auth", () => ({
  AuthError: class AuthError extends Error {
    constructor(
      public readonly code: string,
      message: string,
    ) {
      super(message);
    }
  },
  requireFreshDoctorIdentity: mocks.freshDoctor,
}));
vi.mock("@/lib/clinical-visit-authority", () => ({
  currentClinicalVisitActorWhere: (actorUserId: string) => ({
    userId: actorUserId,
    user: { is: { id: actorUserId, isActive: true } },
  }),
  claimCurrentOrdinaryVisitDeliveryActor: mocks.claimOrdinaryActor,
}));
vi.mock("@/lib/db/transaction-retry", () => ({
  runSerializableTransactionWithRetry: mocks.runTransaction,
}));
vi.mock("@/worker/automation-finalization", () => ({
  lockAndAssertVisitAutomationProof: mocks.lockAutomation,
  VisitAutomationIncompleteError: class VisitAutomationIncompleteError extends Error {},
}));
vi.mock("../final-claim-authority", () => ({
  lockAndAssertCurrentTemplateTwinPhysician: mocks.lockPhysician,
  TemplateTwinCurrentPhysicianAuthorityError: class TemplateTwinCurrentPhysicianAuthorityError extends Error {},
}));
vi.mock("../fill-engine", () => ({
  lockCurrentTemplateTwinVisit: mocks.lockVisit,
}));
vi.mock("../rollout", () => ({
  lockTemplateTwinRolloutForFinalClaim: mocks.finalRollout,
  TemplateTwinRolloutError: class TemplateTwinRolloutError extends Error {},
}));
vi.mock("../signing-gate", () => ({
  TEMPLATE_TWIN_SIGNING_VISIT_SELECT: {},
  assessTemplateTwinSigning: mocks.assessSigning,
}));
vi.mock("../staging-qa-gate", () => ({
  TemplateTwinStagingQaDisabledError: class TemplateTwinStagingQaDisabledError extends Error {},
}));
vi.mock("../staging-qa-visit-guard", () => ({
  assertTemplateTwinStagingQaVisitGuard: mocks.assertStaging,
  lockAndAssertTemplateTwinStagingQaOperation: mocks.lockStaging,
  TemplateTwinStagingQaVisitGuardError: class TemplateTwinStagingQaVisitGuardError extends Error {},
}));
vi.mock("../encounter-evidence-verification", () => ({
  persistedTemplateTwinEncounterEvidenceIsValid: mocks.verifyEncounter,
}));
vi.mock("../audit-outbox", () => ({
  enqueueTemplateTwinAudit: mocks.enqueueAudit,
}));
vi.mock("../read-authority", () => ({
  TemplateTwinVisitReadAuthorityError: class TemplateTwinVisitReadAuthorityError extends Error {},
  requireTemplateTwinVisitReadAuthority: mocks.requireRead,
}));
vi.mock("../synthetic-read-admission", () => ({
  TemplateTwinSyntheticReadAdmissionError: class TemplateTwinSyntheticReadAdmissionError extends Error {},
  requireTemplateTwinSyntheticReadAdmission: mocks.requireSyntheticRead,
}));

import { AuthError } from "@/lib/auth";
import { TemplateTwinCurrentPhysicianAuthorityError } from "../final-claim-authority";
import { TemplateTwinVisitReadAuthorityError } from "../read-authority";
import { TemplateTwinSyntheticReadAdmissionError } from "../synthetic-read-admission";
import {
  authorizeVisitDeliveryFinalClaim,
  TemplateTwinDeliveryAuthorizationError,
} from "../delivery-authorization";

const TOKEN = {
  practiceId: "practice-1",
  globalGeneration: BigInt(7),
  practiceGeneration: BigInt(11),
};
const REVIEWED_AT = new Date("2026-07-20T00:00:00.000Z");
const UPDATED_AT = new Date("2026-07-20T00:01:00.000Z");
const PROVIDER_EVIDENCE = {
  scope: "VISIT_PIPELINE",
  executionId: "receipt-result-identifier-must-not-escape",
};

function fill() {
  return {
    id: "fill-1",
    compiledVersionId: "compiled-1",
    noteTemplateId: "template-1",
    noteTemplateVersion: 3,
    fillManifest: { synthetic: true },
    pinnedGlobalRolloutGeneration: TOKEN.globalGeneration,
    pinnedPracticeRolloutGeneration: TOKEN.practiceGeneration,
    signedGlobalRolloutGeneration: TOKEN.globalGeneration,
    signedPracticeRolloutGeneration: TOKEN.practiceGeneration,
  };
}

function visit(overrides: Record<string, unknown> = {}) {
  return {
    id: "visit-1",
    userId: "doctor-1",
    status: "SIGNED",
    deletedAt: null,
    archivedAt: null,
    user: { practiceId: "practice-1" },
    soapFinal: "Synthetic signed SOAP.",
    soapVersion: 7,
    manualRetryCount: 0,
    inputMode: "text_notes",
    rawTextInput: "Synthetic evidence.",
    transcriptText: null,
    transcriptRaw: null,
    speakerMap: null,
    noteTemplateId: "template-1",
    noteTemplateVersion: 3,
    noteTemplate: { templateKind: "template_twin_docx" },
    templateTwinFill: fill(),
    templateTwinSyntheticQaRun: null,
    ...overrides,
  };
}

function claim() {
  return {
    id: "fill-1",
    manifestVersion: 4,
    manifestSha256: "a".repeat(64),
    reviewedAt: REVIEWED_AT,
    reviewedById: "doctor-1",
    soapVersion: 7,
    soapSha256: "b".repeat(64),
    outputObjectKey: "practices/practice-1/template-twin/output.docx",
    outputVersionId: "object-version-1",
    outputEtag: "object-etag-1",
    outputSha256: "c".repeat(64),
    outputSizeBytes: 4096,
    providerOwnershipEvidence: PROVIDER_EVIDENCE,
    providerOwnershipSha256: "d".repeat(64),
    updatedAt: UPDATED_AT,
  };
}

function currentFill(overrides: Record<string, unknown> = {}) {
  return {
    practiceId: "practice-1",
    visitId: "visit-1",
    compiledVersionId: "compiled-1",
    noteTemplateId: "template-1",
    noteTemplateVersion: 3,
    status: "SIGNED",
    manifestVersion: 4,
    manifestSha256: "a".repeat(64),
    soapVersion: 7,
    soapSha256: "b".repeat(64),
    reviewedAt: REVIEWED_AT,
    reviewedById: "doctor-1",
    reviewedManifestVersion: 4,
    reviewedManifestSha256: "a".repeat(64),
    signedDecisionAt: new Date("2026-07-20T00:00:30.000Z"),
    outputObjectKey: "practices/practice-1/template-twin/output.docx",
    outputVersionId: "object-version-1",
    outputEtag: "object-etag-1",
    outputSha256: "c".repeat(64),
    outputSizeBytes: 4096,
    providerOwnershipEvidence: PROVIDER_EVIDENCE,
    providerOwnershipSha256: "d".repeat(64),
    pinnedGlobalRolloutGeneration: TOKEN.globalGeneration,
    pinnedPracticeRolloutGeneration: TOKEN.practiceGeneration,
    signedGlobalRolloutGeneration: TOKEN.globalGeneration,
    signedPracticeRolloutGeneration: TOKEN.practiceGeneration,
    updatedAt: UPDATED_AT,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireRead.mockResolvedValue({
    visitId: "visit-1",
    isTemplateTwin: true,
    isSyntheticTemplateTwin: false,
    practiceId: "practice-1",
    templateTwinEnabled: true,
  });
  mocks.requireSyntheticRead.mockResolvedValue(null);
  mocks.claimOrdinaryActor.mockResolvedValue({
    id: "doctor-1",
    practiceId: "practice-1",
    email: "current-doctor@example.test",
  });
  mocks.findVisit.mockResolvedValue(visit());
  mocks.freshDoctor.mockResolvedValue({
    role: "DOCTOR",
    practiceId: "practice-1",
    rolloutToken: TOKEN,
  });
  mocks.assessSigning.mockReturnValue({
    applies: true,
    ready: true,
    blockerCodes: [],
    compiledVersionId: "compiled-1",
    fillManifestId: "fill-1",
    claim: claim(),
  });
  mocks.assertStaging.mockImplementation(({ run }: { run: unknown }) =>
    run ? { applies: true, runId: "run-1" } : { applies: false },
  );
  mocks.finalRollout.mockResolvedValue({ allowed: true, token: TOKEN });
  mocks.lockPhysician.mockResolvedValue({
    email: "current-doctor@example.test",
  });
  mocks.lockVisit.mockResolvedValue({
    id: "visit-1",
    userId: "doctor-1",
    status: "SIGNED",
    deletedAt: null,
    archivedAt: null,
    soapVersion: 7,
    soapFinal: "Synthetic signed SOAP.",
    inputMode: "text_notes",
    noteTemplateId: "template-1",
    noteTemplateVersion: 3,
  });
  mocks.findRetry.mockResolvedValue({ manualRetryCount: 0 });
  mocks.findFill.mockResolvedValue(currentFill());
  mocks.verifyEncounter.mockReturnValue(true);
  mocks.lockAutomation.mockResolvedValue({ id: "automation-proof-1" });
  mocks.lockStaging.mockResolvedValue({
    id: "run-1",
    admissionId: "admission-1",
  });
  mocks.runTransaction.mockImplementation(
    async (input: { transaction: (tx: unknown) => Promise<unknown> }) =>
      input.transaction({
        transcribeVisit: { findUnique: mocks.findRetry },
        templateTwinFillManifest: { findUnique: mocks.findFill },
      }),
  );
});

describe("Template Twin delivery final authorization", () => {
  it.each(["suspended", "product removed", "practice transferred"])(
    "does not select signing/clinical payload when minimal authority is %s",
    async () => {
      mocks.requireRead.mockRejectedValue(
        new TemplateTwinVisitReadAuthorityError(),
      );

      await expect(
        authorizeVisitDeliveryFinalClaim({
          visitId: "visit-1",
          actorUserId: "doctor-1",
        }),
      ).rejects.toMatchObject({ code: "NOT_FOUND", status: 404 });

      expect(mocks.findVisit).not.toHaveBeenCalled();
      expect(mocks.freshDoctor).not.toHaveBeenCalled();
    },
  );

  it("leaves an ordinary owned visit on the existing delivery path", async () => {
    mocks.requireRead.mockResolvedValue({
      visitId: "visit-1",
      isTemplateTwin: false,
      isSyntheticTemplateTwin: false,
      practiceId: null,
      templateTwinEnabled: null,
    });
    mocks.findVisit.mockResolvedValue(
      visit({
        noteTemplate: { templateKind: "structured" },
        templateTwinFill: null,
      }),
    );

    await expect(
      authorizeVisitDeliveryFinalClaim({
        visitId: "visit-1",
        actorUserId: "doctor-1",
      }),
    ).resolves.toEqual({
      templateTwin: false,
      currentPhysicianEmail: "current-doctor@example.test",
    });
    expect(mocks.claimOrdinaryActor).toHaveBeenCalledWith({
      visitId: "visit-1",
      actorUserId: "doctor-1",
    });
    expect(mocks.freshDoctor).not.toHaveBeenCalled();
    expect(mocks.runTransaction).not.toHaveBeenCalled();
  });

  it.each([
    ["suspension", null],
    [
      "practice transfer",
      {
        id: "doctor-1",
        practiceId: "practice-other",
        email: "current-doctor@example.test",
      },
    ],
  ])("blocks an ordinary delivery after current %s", async (_label, actor) => {
    mocks.requireRead.mockResolvedValue({
      visitId: "visit-1",
      isTemplateTwin: false,
      isSyntheticTemplateTwin: false,
      practiceId: null,
      templateTwinEnabled: null,
    });
    mocks.findVisit.mockResolvedValue(
      visit({
        noteTemplate: { templateKind: "structured" },
        templateTwinFill: null,
      }),
    );
    mocks.claimOrdinaryActor.mockResolvedValue(actor);

    await expect(
      authorizeVisitDeliveryFinalClaim({
        visitId: "visit-1",
        actorUserId: "doctor-1",
      }),
    ).rejects.toBeInstanceOf(TemplateTwinDeliveryAuthorizationError);
  });

  it("does not select signing PHI when durable lineage appears after ordinary classification", async () => {
    mocks.requireRead.mockResolvedValue({
      visitId: "visit-1",
      isTemplateTwin: false,
      isSyntheticTemplateTwin: false,
      practiceId: null,
      templateTwinEnabled: null,
    });
    mocks.findVisit.mockImplementationOnce(async (query) => {
      expect(query.where).toMatchObject({ id: "visit-1" });
      expect(JSON.stringify(query.where)).toContain(
        "templateTwinCompiledVersion",
      );
      return null;
    });

    await expect(
      authorizeVisitDeliveryFinalClaim({
        visitId: "visit-1",
        actorUserId: "doctor-1",
      }),
    ).rejects.toMatchObject({ code: "NOT_FOUND", status: 404 });

    expect(mocks.assessSigning).not.toHaveBeenCalled();
    expect(mocks.runTransaction).not.toHaveBeenCalled();
  });

  it.each(["reserved-patient orphan", "admission-only synthetic state"])(
    "denies %s before selecting signing or clinical PHI",
    async () => {
      mocks.requireRead.mockResolvedValue({
        visitId: "visit-1",
        isTemplateTwin: true,
        isSyntheticTemplateTwin: true,
        practiceId: "practice-1",
        templateTwinEnabled: true,
      });
      mocks.requireSyntheticRead.mockRejectedValue(
        new TemplateTwinSyntheticReadAdmissionError(),
      );

      await expect(
        authorizeVisitDeliveryFinalClaim({
          visitId: "visit-1",
          actorUserId: "doctor-1",
          allowSyntheticOriginalTemplate: true,
        }),
      ).rejects.toMatchObject({ code: "NOT_FOUND", status: 404 });

      expect(mocks.requireSyntheticRead).toHaveBeenCalledTimes(1);
      expect(mocks.findVisit).not.toHaveBeenCalled();
      expect(mocks.assessSigning).not.toHaveBeenCalled();
      expect(mocks.runTransaction).not.toHaveBeenCalled();
    },
  );

  it("returns the same not-found boundary for a missing or cross-owner visit", async () => {
    for (const row of [null, visit({ userId: "other-doctor" })]) {
      mocks.findVisit.mockResolvedValueOnce(row);
      await expect(
        authorizeVisitDeliveryFinalClaim({
          visitId: "visit-secret",
          actorUserId: "doctor-1",
        }),
      ).rejects.toMatchObject({ code: "NOT_FOUND", status: 404 });
    }
    expect(mocks.freshDoctor).not.toHaveBeenCalled();
  });

  it("blocks an unsigned Twin before any delivery transaction", async () => {
    mocks.findVisit.mockResolvedValue(visit({ status: "READY" }));

    await expect(
      authorizeVisitDeliveryFinalClaim({
        visitId: "visit-1",
        actorUserId: "doctor-1",
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_DELIVERY_BLOCKED",
      status: 409,
    });
    expect(mocks.runTransaction).not.toHaveBeenCalled();
  });

  it("blocks a stale provider receipt without exposing receipt details", async () => {
    mocks.assessSigning.mockReturnValue({
      applies: true,
      ready: false,
      blockerCodes: ["PROVIDER_OWNERSHIP_INVALID"],
      claim: null,
    });

    const error = await authorizeVisitDeliveryFinalClaim({
      visitId: "visit-1",
      actorUserId: "doctor-1",
    }).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(TemplateTwinDeliveryAuthorizationError);
    expect(error).toMatchObject({
      code: "TEMPLATE_TWIN_DELIVERY_BLOCKED",
      status: 409,
    });
    expect(JSON.stringify(error)).not.toMatch(
      /receipt-result-identifier|providerOwnership|executionId/i,
    );
    expect(mocks.runTransaction).not.toHaveBeenCalled();
  });

  it("accepts a valid LIVE exact-head delivery claim", async () => {
    await expect(
      authorizeVisitDeliveryFinalClaim({
        visitId: "visit-1",
        actorUserId: "doctor-1",
      }),
    ).resolves.toEqual({
      templateTwin: true,
      currentPhysicianEmail: "current-doctor@example.test",
    });

    expect(mocks.lockPhysician).toHaveBeenCalledWith({
      tx: expect.anything(),
      actor: { userId: "doctor-1", practiceId: "practice-1" },
    });
    expect(mocks.lockAutomation).toHaveBeenCalledTimes(1);
    expect(mocks.findFill).toHaveBeenCalledWith(
      expect.objectContaining({ where: { id: "fill-1" } }),
    );
  });

  it("returns the current locked physician email instead of a stale session snapshot", async () => {
    await expect(
      authorizeVisitDeliveryFinalClaim({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        emailDelivery: {},
      }),
    ).resolves.toEqual({
      templateTwin: true,
      currentPhysicianEmail: "current-doctor@example.test",
    });
    expect(mocks.enqueueAudit).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        actorEmailSnapshot: "current-doctor@example.test",
        action: "TEMPLATE_TWIN_DELIVERY_AUTHORIZED",
      }),
    );
  });

  it("fails closed when an explicit email target no longer matches the locked physician row", async () => {
    await expect(
      authorizeVisitDeliveryFinalClaim({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        emailDelivery: { targetEmail: "stale-session@example.test" },
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_DELIVERY_BLOCKED",
      status: 409,
    });
    expect(mocks.findFill).not.toHaveBeenCalled();
    expect(mocks.enqueueAudit).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        actorEmailSnapshot: "current-doctor@example.test",
        action: "TEMPLATE_TWIN_DELIVERY_BLOCKED",
        metadata: expect.objectContaining({
          reasonCode: "EMAIL_TARGET_MISMATCH",
        }),
      }),
    );
  });

  it("fails closed when the exact fill CAS changes after admission", async () => {
    mocks.findFill.mockResolvedValue(
      currentFill({ providerOwnershipSha256: "e".repeat(64) }),
    );

    await expect(
      authorizeVisitDeliveryFinalClaim({
        visitId: "visit-1",
        actorUserId: "doctor-1",
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_DELIVERY_BLOCKED",
      status: 409,
    });
  });

  it.each([
    ["inactive actor", "actor was suspended"],
    ["removed product", "TRANSCRIBE_MD was removed"],
  ])(
    "maps a revoked %s admission to a fixed physician denial",
    async (_label, detail) => {
      mocks.freshDoctor.mockRejectedValue(
        new AuthError("FORBIDDEN", `synthetic private detail: ${detail}`),
      );

      const error = await authorizeVisitDeliveryFinalClaim({
        visitId: "visit-1",
        actorUserId: "doctor-1",
      }).catch((caught: unknown) => caught);

      expect(error).toMatchObject({
        code: "TEMPLATE_TWIN_CURRENT_PHYSICIAN_REQUIRED",
        status: 403,
        message:
          "Current physician authorization is required for Template Twin.",
      });
      expect(String((error as Error).message)).not.toContain(detail);
    },
  );

  it("blocks a physician revocation at the locked final claim", async () => {
    mocks.lockPhysician.mockRejectedValue(
      new TemplateTwinCurrentPhysicianAuthorityError(),
    );

    await expect(
      authorizeVisitDeliveryFinalClaim({
        visitId: "visit-1",
        actorUserId: "doctor-1",
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_CURRENT_PHYSICIAN_REQUIRED",
      status: 403,
    });
  });

  it.each(["TEMPLATE_TWIN_PRACTICE_DISABLED", "TEMPLATE_TWIN_GLOBAL_DISABLED"])(
    "blocks final delivery when rollout is revoked: %s",
    async (code) => {
      mocks.finalRollout.mockResolvedValue({
        allowed: false,
        code,
        reason: "private rollout detail",
      });

      await expect(
        authorizeVisitDeliveryFinalClaim({
          visitId: "visit-1",
          actorUserId: "doctor-1",
        }),
      ).rejects.toMatchObject({
        code: "TEMPLATE_TWIN_DELIVERY_BLOCKED",
        status: 409,
      });
      expect(mocks.findFill).not.toHaveBeenCalled();
    },
  );

  it("permits a synthetic visit only for the original-template path", async () => {
    mocks.requireRead.mockResolvedValue({
      visitId: "visit-1",
      isTemplateTwin: true,
      isSyntheticTemplateTwin: true,
      practiceId: "practice-1",
      templateTwinEnabled: true,
    });
    mocks.requireSyntheticRead.mockResolvedValue({
      visitId: "visit-1",
      practiceId: "practice-1",
      runId: "run-1",
      attempt: 2,
    });
    mocks.findVisit.mockResolvedValue(
      visit({
        templateTwinSyntheticQaRun: {
          id: "run-1",
          admissionId: "admission-1",
          attempt: 2,
        },
      }),
    );

    await expect(
      authorizeVisitDeliveryFinalClaim({
        visitId: "visit-1",
        actorUserId: "doctor-1",
      }),
    ).rejects.toMatchObject({ code: "NOT_FOUND", status: 404 });
    expect(mocks.findVisit).not.toHaveBeenCalled();
    expect(mocks.runTransaction).not.toHaveBeenCalled();

    await expect(
      authorizeVisitDeliveryFinalClaim({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        allowSyntheticOriginalTemplate: true,
      }),
    ).resolves.toEqual({
      templateTwin: true,
      currentPhysicianEmail: "current-doctor@example.test",
    });
    expect(mocks.lockStaging).toHaveBeenCalledWith(
      expect.objectContaining({
        runId: "run-1",
        expectedAttempt: 2,
        allowedAdmissionPhases: ["SIGNED"],
      }),
    );
    expect(mocks.requireSyntheticRead).toHaveBeenCalledTimes(3);
    expect(mocks.requireSyntheticRead).toHaveBeenLastCalledWith(
      expect.objectContaining({
        visitId: "visit-1",
        expected: {
          visitId: "visit-1",
          practiceId: "practice-1",
          runId: "run-1",
          attempt: 2,
        },
      }),
    );
  });
});
