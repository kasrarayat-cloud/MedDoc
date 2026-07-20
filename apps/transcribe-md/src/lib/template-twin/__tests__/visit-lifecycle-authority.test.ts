import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findActor: vi.fn(),
  lockPhysician: vi.fn(),
  lockOrdinaryClinical: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: { user: { findUnique: mocks.findActor } },
}));
vi.mock("../final-claim-authority", () => ({
  TemplateTwinCurrentPhysicianAuthorityError: class TemplateTwinCurrentPhysicianAuthorityError extends Error {},
  lockAndAssertCurrentTemplateTwinPhysician: mocks.lockPhysician,
}));
vi.mock("../visit-mutation-authority", () => ({
  TEMPLATE_TWIN_CLINICAL_MUTATION_PROVENANCE_SELECT: {},
  hasDurableTemplateTwinClinicalMutationProvenance: (row: {
    patient?: { externalId?: string | null } | null;
    noteTemplate?: { templateKind?: string } | null;
    templateTwinFill?: unknown;
    templateTwinSyntheticQaRun?: unknown;
    templateTwinSyntheticQaAdmission?: unknown;
    templateTwinProviderExecutions?: unknown[];
  }) =>
    row.patient?.externalId === "SYNTHETIC-QA-ONLY" ||
    row.noteTemplate?.templateKind === "template_twin_docx" ||
    Boolean(row.templateTwinFill) ||
    Boolean(row.templateTwinSyntheticQaRun) ||
    Boolean(row.templateTwinSyntheticQaAdmission) ||
    Boolean(row.templateTwinProviderExecutions?.length),
  hasExactLiveTemplateTwinDataLifecycleProvenance: (row: {
    noteTemplate?: { templateKind?: string } | null;
    templateTwinSyntheticQaRun?: unknown;
    templateTwinSyntheticQaAdmission?: unknown;
  }) =>
    row.noteTemplate?.templateKind === "template_twin_docx" &&
    !row.templateTwinSyntheticQaRun &&
    !row.templateTwinSyntheticQaAdmission,
  lockAndAssertOrdinaryClinicalMutation: mocks.lockOrdinaryClinical,
  TemplateTwinClinicalMutationAuthorizationError: class TemplateTwinClinicalMutationAuthorizationError extends Error {},
}));

import { TemplateTwinCurrentPhysicianAuthorityError } from "../final-claim-authority";
import {
  lockAndAssertTemplateTwinDataLifecycleMutation,
  lockAndAssertOrdinaryDataLifecycleMutation,
  pinTemplateTwinDataLifecycleMutation,
  TemplateTwinDataLifecycleAuthorizationError,
} from "../visit-lifecycle-authority";

function provenance(overrides: Record<string, unknown> = {}) {
  return {
    patientId: "patient-1",
    patient: {
      id: "patient-1",
      practiceId: "practice-1",
      externalId: null,
    },
    noteTemplateId: "template-1",
    noteTemplateVersion: 3,
    noteTemplate: {
      id: "template-1",
      doctorId: "doctor-1",
      version: 3,
      templateKind: "template_twin_docx",
      templateTwinCompiledVersion: {
        id: "compiled-1",
        noteTemplateId: "template-1",
        sourceArtifactId: "source-1",
        certificationStatus: "CERTIFIED",
        sourceArtifact: {
          id: "source-1",
          practiceId: "practice-1",
          validationStatus: "accepted",
        },
        certification: {
          id: "certification-1",
          compiledVersionId: "compiled-1",
          certifiedById: "doctor-1",
          providerAuthorizationMode: "LIVE",
          providerAuthorizationAdmissionId: null,
        },
      },
    },
    templateTwinFill: {
      id: "fill-1",
      practiceId: "practice-1",
      compiledVersionId: "compiled-1",
      noteTemplateId: "template-1",
      noteTemplateVersion: 3,
      signedDecisionAt: new Date("2026-07-20T00:00:00.000Z"),
    },
    templateTwinSyntheticQaRun: null,
    templateTwinSyntheticQaAdmission: null,
    templateTwinProviderExecutions: [],
    ...overrides,
  };
}

function visit(overrides: Record<string, unknown> = {}) {
  return {
    id: "visit-1",
    userId: "doctor-1",
    status: "SIGNED",
    deletedAt: null,
    archivedAt: new Date("2026-07-20T01:00:00.000Z"),
    audioKey: null,
    dictationAudioKey: null,
    rawTextInput: "Synthetic evidence.",
    ...provenance(),
    ...overrides,
  };
}

function tx(
  row: Record<string, unknown> = visit(),
  visitLock: Array<{ id: string }> = [{ id: "visit-1" }],
) {
  return {
    $queryRaw: vi
      .fn()
      .mockResolvedValueOnce([{ id: "practice-1", isActive: true }])
      .mockResolvedValueOnce([{ id: "template-1" }])
      .mockResolvedValueOnce([{ id: "compiled-1" }])
      .mockResolvedValueOnce([{ id: "source-1" }])
      .mockResolvedValueOnce([{ id: "certification-1" }])
      .mockResolvedValueOnce([{ id: "patient-1", practiceId: "practice-1" }])
      .mockResolvedValueOnce(visitLock)
      .mockResolvedValueOnce([{ id: "fill-1" }])
      .mockResolvedValueOnce([]),
    transcribeVisit: { findUnique: vi.fn().mockResolvedValue(row) },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.findActor.mockResolvedValue({
    id: "doctor-1",
    role: "DOCTOR",
    isActive: true,
    practiceId: "practice-1",
    deactivatedAt: null,
    suspendedAt: null,
    softDeletedAt: null,
    products: ["TRANSCRIBE_MD"],
    practice: { isActive: true },
  });
  mocks.lockPhysician.mockResolvedValue({ email: "doctor@example.test" });
  mocks.lockOrdinaryClinical.mockResolvedValue(undefined);
});

describe("Template Twin data-lifecycle authority", () => {
  it("delegates ordinary lifecycle writes to the exact ordinary final fence", async () => {
    await expect(
      lockAndAssertOrdinaryDataLifecycleMutation({
        tx: {} as never,
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedVisitUpdatedAt: new Date("2026-07-20T00:00:00.000Z"),
        admittedPatientId: "patient-1",
        admittedNoteTemplateId: "ordinary-1",
      }),
    ).resolves.toBeUndefined();
    expect(mocks.lockOrdinaryClinical).toHaveBeenCalledTimes(1);
  });

  it("leaves ordinary cleanup on the legacy path", async () => {
    await expect(
      pinTemplateTwinDataLifecycleMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        provenance: provenance({
          noteTemplateId: "ordinary-1",
          noteTemplateVersion: 1,
          noteTemplate: {
            id: "ordinary-1",
            doctorId: "doctor-1",
            version: 1,
            templateKind: "structured",
            templateTwinCompiledVersion: null,
          },
          templateTwinFill: null,
        }) as never,
      }),
    ).resolves.toBeNull();
    expect(mocks.findActor).not.toHaveBeenCalled();
  });

  it("admits a signed Twin without consulting rollout state", async () => {
    await expect(
      pinTemplateTwinDataLifecycleMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        provenance: provenance() as never,
      }),
    ).resolves.toMatchObject({
      practiceId: "practice-1",
      patientId: "patient-1",
      fillManifestId: "fill-1",
    });
  });

  it("rejects an orphaned reserved synthetic patient without relation markers", async () => {
    await expect(
      pinTemplateTwinDataLifecycleMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        provenance: provenance({
          patient: {
            id: "patient-1",
            practiceId: "practice-1",
            externalId: "SYNTHETIC-QA-ONLY",
          },
          noteTemplateId: "ordinary-1",
          noteTemplateVersion: 1,
          noteTemplate: {
            id: "ordinary-1",
            doctorId: "doctor-1",
            version: 1,
            templateKind: "structured",
            templateTwinCompiledVersion: null,
          },
          templateTwinFill: null,
          templateTwinSyntheticQaRun: null,
          templateTwinSyntheticQaAdmission: null,
          templateTwinProviderExecutions: [],
        }) as never,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinDataLifecycleAuthorizationError);
    expect(mocks.findActor).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["suspension", { suspendedAt: new Date() }],
    ["deactivation", { isActive: false }],
    ["role removal", { role: "ADMIN" }],
    ["product removal", { products: [] }],
  ])("rejects %s at lifecycle admission", async (_label, actorOverride) => {
    mocks.findActor.mockResolvedValue({
      id: "doctor-1",
      role: "DOCTOR",
      isActive: true,
      practiceId: "practice-1",
      deactivatedAt: null,
      suspendedAt: null,
      softDeletedAt: null,
      products: ["TRANSCRIBE_MD"],
      practice: { isActive: true },
      ...actorOverride,
    });
    await expect(
      pinTemplateTwinDataLifecycleMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        provenance: provenance() as never,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinDataLifecycleAuthorizationError);
  });

  it("rejects cross-practice patient provenance", async () => {
    await expect(
      pinTemplateTwinDataLifecycleMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        provenance: provenance({
          patient: {
            id: "patient-1",
            practiceId: "practice-2",
            externalId: null,
          },
        }) as never,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinDataLifecycleAuthorizationError);
  });

  it("rejects an inactive practice without consulting rollout", async () => {
    mocks.findActor.mockResolvedValue({
      id: "doctor-1",
      role: "DOCTOR",
      isActive: true,
      practiceId: "practice-1",
      deactivatedAt: null,
      suspendedAt: null,
      softDeletedAt: null,
      products: ["TRANSCRIBE_MD"],
      practice: { isActive: false },
    });
    await expect(
      pinTemplateTwinDataLifecycleMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        provenance: provenance() as never,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinDataLifecycleAuthorizationError);
  });

  it("excludes synthetic and pre-certification visits", async () => {
    await expect(
      pinTemplateTwinDataLifecycleMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        provenance: provenance({
          templateTwinSyntheticQaAdmission: { id: "admission-1" },
        }) as never,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinDataLifecycleAuthorizationError);
  });

  it("rechecks current physician and exact provenance under final locks", async () => {
    const claim = (await pinTemplateTwinDataLifecycleMutation({
      visitId: "visit-1",
      actorUserId: "doctor-1",
      provenance: provenance() as never,
    }))!;
    const client = tx();

    await expect(
      lockAndAssertTemplateTwinDataLifecycleMutation({
        tx: client as never,
        claim,
      }),
    ).resolves.toMatchObject({ id: "visit-1", status: "SIGNED" });
    expect(mocks.lockPhysician).toHaveBeenCalledTimes(1);
    expect(client.$queryRaw).toHaveBeenCalledTimes(9);
    const visitLock = client.$queryRaw.mock.calls[6]?.[0];
    expect(visitLock?.strings?.join(" ")).toContain('visit."userId" =');
    expect(client.transcribeVisit.findUnique).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { id: "visit-1", userId: "doctor-1" },
      }),
    );
  });

  it("blocks pre-lock reassignment without projecting PHI", async () => {
    const claim = (await pinTemplateTwinDataLifecycleMutation({
      visitId: "visit-1",
      actorUserId: "doctor-1",
      provenance: provenance() as never,
    }))!;
    const client = tx(visit({ userId: "other-doctor" }), []);

    await expect(
      lockAndAssertTemplateTwinDataLifecycleMutation({
        tx: client as never,
        claim,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinDataLifecycleAuthorizationError);

    const visitLock = client.$queryRaw.mock.calls[6]?.[0];
    expect(visitLock?.strings?.join(" ")).toContain('visit."userId" =');
    expect(visitLock?.values).toEqual(
      expect.arrayContaining(["visit-1", "doctor-1"]),
    );
    expect(client.transcribeVisit.findUnique).not.toHaveBeenCalled();
  });

  it("blocks a practice transfer between admission and final claim", async () => {
    const claim = (await pinTemplateTwinDataLifecycleMutation({
      visitId: "visit-1",
      actorUserId: "doctor-1",
      provenance: provenance() as never,
    }))!;
    mocks.lockPhysician.mockRejectedValue(
      new TemplateTwinCurrentPhysicianAuthorityError(),
    );

    await expect(
      lockAndAssertTemplateTwinDataLifecycleMutation({
        tx: tx() as never,
        claim,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinDataLifecycleAuthorizationError);
  });

  it("blocks practice deactivation between admission and final claim", async () => {
    const claim = (await pinTemplateTwinDataLifecycleMutation({
      visitId: "visit-1",
      actorUserId: "doctor-1",
      provenance: provenance() as never,
    }))!;
    const client = tx();
    client.$queryRaw
      .mockReset()
      .mockResolvedValueOnce([{ id: "practice-1", isActive: false }]);

    await expect(
      lockAndAssertTemplateTwinDataLifecycleMutation({
        tx: client as never,
        claim,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinDataLifecycleAuthorizationError);
    expect(mocks.lockPhysician).not.toHaveBeenCalled();
  });

  it("blocks a patient relink before lifecycle mutation", async () => {
    const claim = (await pinTemplateTwinDataLifecycleMutation({
      visitId: "visit-1",
      actorUserId: "doctor-1",
      provenance: provenance() as never,
    }))!;
    const changed = visit({
      patientId: "patient-2",
      patient: {
        id: "patient-2",
        practiceId: "practice-1",
        externalId: null,
      },
    });

    await expect(
      lockAndAssertTemplateTwinDataLifecycleMutation({
        tx: tx(changed) as never,
        claim,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinDataLifecycleAuthorizationError);
  });
});
