import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  freshDoctor: vi.fn(),
  finalRollout: vi.fn(),
  lockPhysician: vi.fn(),
  canonicalCompilation: vi.fn(),
  admissionTarget: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    $queryRaw: mocks.canonicalCompilation,
    transcribeVisit: { findUnique: mocks.admissionTarget },
  },
}));

vi.mock("@/lib/auth", () => ({
  AuthError: class AuthError extends Error {},
  requireFreshDoctorIdentity: mocks.freshDoctor,
}));
vi.mock("../rollout", () => ({
  lockTemplateTwinRolloutForFinalClaim: mocks.finalRollout,
}));
vi.mock("../final-claim-authority", () => ({
  TemplateTwinCurrentPhysicianAuthorityError: class TemplateTwinCurrentPhysicianAuthorityError extends Error {},
  lockAndAssertCurrentTemplateTwinPhysician: mocks.lockPhysician,
}));

import { AuthError } from "@/lib/auth";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";
import { TemplateTwinCurrentPhysicianAuthorityError } from "../final-claim-authority";
import {
  loadTemplateTwinClinicalMutationAdmissionTarget,
  lockAndAssertTemplateTwinClinicalMutation,
  lockAndAssertOrdinaryClinicalMutation,
  pinTemplateTwinClinicalMutation,
  TemplateTwinClinicalMutationAuthorizationError,
  type TemplateTwinClinicalMutationProvenance,
} from "../visit-mutation-authority";

const TOKEN = {
  practiceId: "practice-1",
  globalGeneration: BigInt(3),
  practiceGeneration: BigInt(5),
};
const ADMITTED_AT = new Date("2026-07-20T00:00:00.000Z");

function provenance(
  overrides: Partial<TemplateTwinClinicalMutationProvenance> = {},
): TemplateTwinClinicalMutationProvenance {
  return {
    patientId: "patient-1",
    patient: {
      id: "patient-1",
      practiceId: "practice-1",
      externalId: null,
    },
    noteTemplateId: "template-1",
    noteTemplateVersion: 7,
    noteTemplate: {
      id: "template-1",
      doctorId: "doctor-1",
      version: 7,
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
      noteTemplateVersion: 7,
      signedDecisionAt: null,
    },
    templateTwinSyntheticQaRun: null,
    templateTwinSyntheticQaAdmission: null,
    templateTwinProviderExecutions: [],
    ...overrides,
  };
}

function withoutProperty<T extends object>(value: T, key: keyof T): Partial<T> {
  const copy: Partial<T> = { ...value };
  Reflect.deleteProperty(copy, key);
  return copy;
}

function lockedVisit(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    id: "visit-1",
    userId: "doctor-1",
    status: "READY",
    deletedAt: null,
    archivedAt: null,
    signedAt: null,
    updatedAt: new Date("2026-07-20T00:00:00.000Z"),
    inputMode: "text_notes",
    rawTextInput: "Synthetic input.",
    audioKey: null,
    dictationAudioKey: null,
    soapDraft: "Synthetic SOAP.",
    soapFinal: "Synthetic SOAP.",
    soapVersion: 4,
    speakerMap: null,
    icdCodes: null,
    cptCodes: null,
    rxDrafts: null,
    audioDurationSec: null,
    dictationDurationSec: null,
    manualRetryCount: 0,
    ...provenance(),
    ...overrides,
  };
}

function txWithVisit(
  row: Record<string, unknown> = lockedVisit(),
  visitLock: Array<{ id: string }> = [{ id: "visit-1" }],
) {
  const queryRaw = vi
    .fn()
    .mockResolvedValueOnce([{ id: "template-1" }])
    .mockResolvedValueOnce([{ id: "compiled-1" }])
    .mockResolvedValueOnce([{ id: "source-1" }])
    .mockResolvedValueOnce([{ id: "certification-1" }])
    .mockResolvedValueOnce([{ valid: true }])
    .mockResolvedValueOnce([{ id: "patient-1", practiceId: "practice-1" }])
    .mockResolvedValueOnce(visitLock)
    .mockResolvedValueOnce([{ id: "fill-1" }])
    .mockResolvedValueOnce([]);
  return {
    $queryRaw: queryRaw,
    transcribeVisit: { findUnique: vi.fn().mockResolvedValue(row) },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.freshDoctor.mockResolvedValue({
    role: "DOCTOR",
    practiceId: "practice-1",
    rolloutToken: TOKEN,
  });
  mocks.finalRollout.mockResolvedValue({ allowed: true, token: TOKEN });
  mocks.lockPhysician.mockResolvedValue({
    email: "current-doctor@example.test",
  });
  mocks.canonicalCompilation.mockResolvedValue([{ valid: true }]);
  mocks.admissionTarget.mockResolvedValue(null);
});

describe("Template Twin clinical-mutation admission", () => {
  it("binds the actor in the same statement as the provenance projection", async () => {
    await expect(
      loadTemplateTwinClinicalMutationAdmissionTarget({
        visitId: "visit-foreign",
        actorUserId: "doctor-1",
      }),
    ).resolves.toBeNull();

    expect(mocks.admissionTarget).toHaveBeenCalledWith(
      expect.objectContaining({
        where: {
          id: "visit-foreign",
          ...currentClinicalVisitActorWhere("doctor-1"),
        },
      }),
    );
  });

  it("locks and reasserts the exact ordinary template/patient/visit epoch", async () => {
    const client = {
      $queryRaw: vi
        .fn()
        .mockResolvedValueOnce([{ id: "practice-1", isActive: true }])
        .mockResolvedValueOnce([{ id: "doctor-1" }])
        .mockResolvedValueOnce([{ id: "ordinary-1" }])
        .mockResolvedValueOnce([{ id: "visit-1" }]),
    };

    await expect(
      lockAndAssertOrdinaryClinicalMutation({
        tx: client as never,
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedVisitUpdatedAt: ADMITTED_AT,
        admittedPatientId: "patient-1",
        admittedNoteTemplateId: "ordinary-1",
      }),
    ).resolves.toBeUndefined();
    expect(client.$queryRaw).toHaveBeenCalledTimes(4);

    const locks = client.$queryRaw.mock.calls.map(
      ([sql]) => sql?.strings?.join(" ") ?? "",
    );
    expect(locks[0]).toContain('FROM "practices"');
    expect(locks[0]).toContain('FROM "users" actor');
    expect(locks[0]).toContain('practice."isActive" = TRUE');
    expect(locks[1]).toContain('FROM "users" actor');
    expect(locks[1]).toContain('actor."practiceId" =');
    expect(locks[1]).toContain("actor.\"role\" = 'DOCTOR'");
    expect(locks[1]).toContain('actor."isActive" = TRUE');
    expect(locks[1]).toContain('actor."deactivatedAt" IS NULL');
    expect(locks[1]).toContain('actor."suspendedAt" IS NULL');
    expect(locks[1]).toContain('actor."softDeletedAt" IS NULL');
    expect(locks[1]).toContain("'TRANSCRIBE_MD'::\"Product\"");
    expect(locks[2]).toContain('FROM "note_templates"');
    expect(locks[3]).toContain('FROM "transcribe_visits"');
    expect(locks[3]).toContain('patient."practiceId" =');
  });

  it("fails before target locks when the canonical practice is inactive", async () => {
    const client = { $queryRaw: vi.fn().mockResolvedValueOnce([]) };

    await expect(
      lockAndAssertOrdinaryClinicalMutation({
        tx: client as never,
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedVisitUpdatedAt: ADMITTED_AT,
        admittedPatientId: "patient-1",
        admittedNoteTemplateId: "ordinary-1",
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
    });
    expect(client.$queryRaw).toHaveBeenCalledOnce();
  });

  it.each([
    "role removal",
    "deactivation",
    "suspension",
    "soft deletion",
    "product removal",
    "practice transfer after the practice lock",
  ])("fails before target locks on current actor %s", async () => {
    const client = {
      $queryRaw: vi
        .fn()
        .mockResolvedValueOnce([{ id: "practice-1", isActive: true }])
        .mockResolvedValueOnce([]),
    };

    await expect(
      lockAndAssertOrdinaryClinicalMutation({
        tx: client as never,
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedVisitUpdatedAt: ADMITTED_AT,
        admittedPatientId: "patient-1",
        admittedNoteTemplateId: "ordinary-1",
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
    });
    expect(client.$queryRaw).toHaveBeenCalledTimes(2);
  });

  it("fails the ordinary final fence when a durable marker appears", async () => {
    const client = {
      $queryRaw: vi
        .fn()
        .mockResolvedValueOnce([{ id: "practice-1", isActive: true }])
        .mockResolvedValueOnce([{ id: "doctor-1" }])
        .mockResolvedValueOnce([{ id: "ordinary-1" }])
        .mockResolvedValueOnce([]),
    };

    await expect(
      lockAndAssertOrdinaryClinicalMutation({
        tx: client as never,
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedVisitUpdatedAt: ADMITTED_AT,
        admittedPatientId: "patient-1",
        admittedNoteTemplateId: "ordinary-1",
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
    });
  });

  it("fails the ordinary template lock when compiled lineage survives kind drift", async () => {
    const client = {
      // The exact SQL template lock returns no row when the compiled relation
      // exists, even if mutable templateKind now says `structured`.
      $queryRaw: vi
        .fn()
        .mockResolvedValueOnce([{ id: "practice-1", isActive: true }])
        .mockResolvedValueOnce([{ id: "doctor-1" }])
        .mockResolvedValueOnce([]),
    };

    await expect(
      lockAndAssertOrdinaryClinicalMutation({
        tx: client as never,
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedVisitUpdatedAt: ADMITTED_AT,
        admittedPatientId: "patient-1",
        admittedNoteTemplateId: "kind-drifted-template",
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
    });
    expect(client.$queryRaw).toHaveBeenCalledTimes(3);
  });

  it("leaves an ordinary visit on the exact legacy path", async () => {
    await expect(
      pinTemplateTwinClinicalMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedVisitUpdatedAt: ADMITTED_AT,
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
        }),
      }),
    ).resolves.toBeNull();
    expect(mocks.freshDoctor).not.toHaveBeenCalled();
  });

  it("leaves an ordinary non-reserved patient on the exact legacy path", async () => {
    await expect(
      pinTemplateTwinClinicalMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedVisitUpdatedAt: ADMITTED_AT,
        provenance: provenance({
          patient: {
            id: "patient-1",
            practiceId: "practice-1",
            externalId: "ORDINARY-EXTERNAL-ID",
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
        }),
      }),
    ).resolves.toBeNull();
    expect(mocks.freshDoctor).not.toHaveBeenCalled();
  });

  it("rejects an orphaned reserved synthetic patient even without relation markers", async () => {
    await expect(
      pinTemplateTwinClinicalMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedVisitUpdatedAt: ADMITTED_AT,
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
        }),
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
    });
    expect(mocks.freshDoctor).not.toHaveBeenCalled();
  });

  it("rejects compiled lineage as invalid when mutable template kind drifted", async () => {
    await expect(
      pinTemplateTwinClinicalMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedVisitUpdatedAt: ADMITTED_AT,
        provenance: provenance({
          noteTemplate: {
            ...provenance().noteTemplate!,
            templateKind: "structured",
          },
          templateTwinFill: null,
          templateTwinSyntheticQaRun: null,
          templateTwinSyntheticQaAdmission: null,
          templateTwinProviderExecutions: [],
        }),
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_PROVENANCE_INVALID",
    });
    expect(mocks.freshDoctor).not.toHaveBeenCalled();
  });

  it.each([
    ["missing patient relation key", withoutProperty(provenance(), "patient")],
    ["null patient relation", { ...provenance(), patient: null }],
    [
      "missing template kind",
      {
        ...provenance(),
        noteTemplate: withoutProperty(
          provenance().noteTemplate!,
          "templateKind",
        ),
      },
    ],
    [
      "missing compiled relation key",
      {
        ...provenance(),
        noteTemplate: withoutProperty(
          provenance().noteTemplate!,
          "templateTwinCompiledVersion",
        ),
      },
    ],
    [
      "missing fill relation key",
      withoutProperty(provenance(), "templateTwinFill"),
    ],
    [
      "missing synthetic run relation key",
      withoutProperty(provenance(), "templateTwinSyntheticQaRun"),
    ],
    [
      "missing synthetic admission relation key",
      withoutProperty(provenance(), "templateTwinSyntheticQaAdmission"),
    ],
    [
      "non-array provider executions",
      { ...provenance(), templateTwinProviderExecutions: null },
    ],
    [
      "malformed provider execution",
      {
        ...provenance(),
        templateTwinProviderExecutions: [{ id: "execution-incomplete" }],
      },
    ],
  ])(
    "fails malformed runtime provenance closed: %s",
    async (_label, malformed) => {
      await expect(
        pinTemplateTwinClinicalMutation({
          visitId: "visit-1",
          actorUserId: "doctor-1",
          admittedVisitUpdatedAt: ADMITTED_AT,
          provenance: malformed as never,
        }),
      ).rejects.toMatchObject({
        code: "TEMPLATE_TWIN_MUTATION_PROVENANCE_INVALID",
      });
      expect(mocks.freshDoctor).not.toHaveBeenCalled();
    },
  );

  it("admits a current live Twin before its first fill exists", async () => {
    await expect(
      pinTemplateTwinClinicalMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedVisitUpdatedAt: ADMITTED_AT,
        provenance: provenance({ templateTwinFill: null }),
      }),
    ).resolves.toMatchObject({
      practiceId: "practice-1",
      noteTemplateId: "template-1",
      fillManifestId: null,
    });
  });

  it.each([
    ["detached fill", provenance({ noteTemplate: null })],
    [
      "mutated kind",
      provenance({
        noteTemplate: {
          id: "template-1",
          doctorId: "doctor-1",
          version: 7,
          templateKind: "structured",
          templateTwinCompiledVersion:
            provenance().noteTemplate!.templateTwinCompiledVersion,
        },
      }),
    ],
    [
      "mismatched fill version",
      provenance({
        templateTwinFill: {
          id: "fill-1",
          practiceId: "practice-1",
          compiledVersionId: "compiled-1",
          noteTemplateId: "template-1",
          noteTemplateVersion: 6,
          signedDecisionAt: null,
        },
      }),
    ],
    [
      "mismatched fill compiled lineage",
      provenance({
        templateTwinFill: {
          ...provenance().templateTwinFill!,
          compiledVersionId: "compiled-other",
        },
      }),
    ],
    [
      "provider-owned history with an ordinary current template",
      provenance({
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
        templateTwinProviderExecutions: [
          {
            id: "execution-1",
            practiceId: "practice-1",
            actorUserId: "doctor-1",
            visitId: "visit-1",
            sourceArtifactId: "source-1",
            compiledVersionId: "compiled-1",
            noteTemplateId: "ordinary-1",
            noteTemplateVersion: 1,
            providerMode: "LIVE",
            syntheticAdmissionId: null,
          },
        ],
      }),
    ],
    [
      "unaccepted source",
      provenance({
        noteTemplate: {
          ...provenance().noteTemplate!,
          templateTwinCompiledVersion: {
            ...provenance().noteTemplate!.templateTwinCompiledVersion!,
            sourceArtifact: {
              ...provenance().noteTemplate!.templateTwinCompiledVersion!
                .sourceArtifact,
              validationStatus: "rejected",
            },
          },
        },
      }),
    ],
    [
      "malformed provider execution identity",
      provenance({
        templateTwinProviderExecutions: [
          {
            id: "execution-1",
            practiceId: "practice-1",
            actorUserId: "other-doctor",
            visitId: "visit-1",
            sourceArtifactId: "source-1",
            compiledVersionId: "compiled-1",
            noteTemplateId: "template-1",
            noteTemplateVersion: 7,
            providerMode: "LIVE",
            syntheticAdmissionId: null,
          },
        ],
      }),
    ],
    [
      "mismatched provider execution compiled lineage",
      provenance({
        templateTwinProviderExecutions: [
          {
            id: "execution-1",
            practiceId: "practice-1",
            actorUserId: "doctor-1",
            visitId: "visit-1",
            sourceArtifactId: "source-1",
            compiledVersionId: "compiled-other",
            noteTemplateId: "template-1",
            noteTemplateVersion: 7,
            providerMode: "LIVE",
            syntheticAdmissionId: null,
          },
        ],
      }),
    ],
    [
      "mismatched provider execution source lineage",
      provenance({
        templateTwinProviderExecutions: [
          {
            id: "execution-1",
            practiceId: "practice-1",
            actorUserId: "doctor-1",
            visitId: "visit-1",
            sourceArtifactId: "source-other",
            compiledVersionId: "compiled-1",
            noteTemplateId: "template-1",
            noteTemplateVersion: 7,
            providerMode: "LIVE",
            syntheticAdmissionId: null,
          },
        ],
      }),
    ],
  ])("fails closed for %s provenance", async (_label, row) => {
    await expect(
      pinTemplateTwinClinicalMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedVisitUpdatedAt: ADMITTED_AT,
        provenance: row,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_PROVENANCE_INVALID",
    });
    expect(mocks.freshDoctor).not.toHaveBeenCalled();
  });

  it.each([
    ["synthetic run", { templateTwinSyntheticQaRun: { id: "run-1" } }],
    [
      "pre-certification admission",
      { templateTwinSyntheticQaAdmission: { id: "admission-1" } },
    ],
  ])("excludes a %s from generic mutation", async (_label, overrides) => {
    await expect(
      pinTemplateTwinClinicalMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedVisitUpdatedAt: ADMITTED_AT,
        provenance: provenance(overrides),
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
    });
  });

  it.each([
    "suspended physician",
    "deactivated physician",
    "removed doctor role",
    "removed TRANSCRIBE_MD product",
  ])("fails closed when fresh admission rejects a %s", async () => {
    mocks.freshDoctor.mockRejectedValue(new AuthError("FORBIDDEN", "revoked"));
    await expect(
      pinTemplateTwinClinicalMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedVisitUpdatedAt: ADMITTED_AT,
        provenance: provenance(),
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
    });
  });

  it("rejects a current-practice mismatch at admission", async () => {
    mocks.freshDoctor.mockResolvedValue({
      role: "DOCTOR",
      practiceId: "practice-2",
      rolloutToken: { ...TOKEN, practiceId: "practice-2" },
    });
    await expect(
      pinTemplateTwinClinicalMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedVisitUpdatedAt: ADMITTED_AT,
        provenance: provenance(),
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
    });
  });

  it("rejects an accepted source from another practice", async () => {
    const base = provenance();
    await expect(
      pinTemplateTwinClinicalMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedVisitUpdatedAt: ADMITTED_AT,
        provenance: {
          ...base,
          noteTemplate: {
            ...base.noteTemplate!,
            templateTwinCompiledVersion: {
              ...base.noteTemplate!.templateTwinCompiledVersion!,
              sourceArtifact: {
                ...base.noteTemplate!.templateTwinCompiledVersion!
                  .sourceArtifact,
                practiceId: "practice-2",
              },
            },
          },
        },
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
    });
  });

  it("rejects a patient linked to another practice", async () => {
    await expect(
      pinTemplateTwinClinicalMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedVisitUpdatedAt: ADMITTED_AT,
        provenance: provenance({
          patient: {
            id: "patient-1",
            practiceId: "practice-2",
            externalId: null,
          },
        }),
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
    });
  });

  it("rejects a compilation that loses canonical LIVE authority at admission", async () => {
    mocks.canonicalCompilation.mockResolvedValue([{ valid: false }]);
    await expect(
      pinTemplateTwinClinicalMutation({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedVisitUpdatedAt: ADMITTED_AT,
        provenance: provenance(),
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_PROVENANCE_INVALID",
    });
  });
});

describe("Template Twin clinical-mutation final claim", () => {
  async function claim() {
    return (await pinTemplateTwinClinicalMutation({
      visitId: "visit-1",
      actorUserId: "doctor-1",
      admittedVisitUpdatedAt: ADMITTED_AT,
      provenance: provenance(),
    }))!;
  }

  it("locks authority and provenance in canonical order before returning the target", async () => {
    const pinned = await claim();
    const tx = txWithVisit();

    await expect(
      lockAndAssertTemplateTwinClinicalMutation({
        tx: tx as never,
        claim: pinned,
      }),
    ).resolves.toMatchObject({ id: "visit-1", soapVersion: 4 });
    expect(mocks.finalRollout).toHaveBeenCalledWith({
      tx,
      practiceId: "practice-1",
      pinnedToken: TOKEN,
    });
    expect(mocks.lockPhysician).toHaveBeenCalledWith({
      tx,
      actor: { userId: "doctor-1", practiceId: "practice-1" },
    });
    expect(tx.$queryRaw).toHaveBeenCalledTimes(9);
    const lockOrder = tx.$queryRaw.mock.calls.map(
      ([sql]) => sql?.strings?.join(" ") ?? "",
    );
    expect(lockOrder[0]).toContain('FROM "note_templates"');
    expect(lockOrder[1]).toContain('FROM "template_twin_compiled_versions"');
    expect(lockOrder[2]).toContain('FROM "template_twin_source_artifacts"');
    expect(lockOrder[3]).toContain('FROM "template_twin_certifications"');
    expect(lockOrder[4]).toContain(
      "template_twin_live_provider_compilation_is_valid",
    );
    expect(lockOrder[5]).toContain('FROM "transcribe_md_patients"');
    expect(lockOrder[6]).toContain('FROM "transcribe_visits"');
    expect(lockOrder[6]).toContain('visit."userId" =');
    expect(lockOrder[7]).toContain('FROM "template_twin_fill_manifests"');
    expect(lockOrder[8]).toContain('FROM "template_twin_provider_executions"');
    expect(tx.transcribeVisit.findUnique).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { id: "visit-1", userId: "doctor-1" },
      }),
    );
  });

  it("blocks pre-lock reassignment without projecting PHI", async () => {
    const pinned = await claim();
    const tx = txWithVisit(lockedVisit({ userId: "other-doctor" }), []);

    await expect(
      lockAndAssertTemplateTwinClinicalMutation({
        tx: tx as never,
        claim: pinned,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
    });

    const visitLock = tx.$queryRaw.mock.calls[6]?.[0];
    expect(visitLock?.strings?.join(" ")).toContain('visit."userId" =');
    expect(visitLock?.values).toEqual(
      expect.arrayContaining(["visit-1", "doctor-1"]),
    );
    expect(tx.transcribeVisit.findUnique).not.toHaveBeenCalled();
  });

  it("blocks a rollout revocation before the target lock/mutation", async () => {
    const pinned = await claim();
    mocks.finalRollout.mockResolvedValue({
      allowed: false,
      code: "TEMPLATE_TWIN_GLOBAL_DISABLED",
    });
    const tx = txWithVisit();

    await expect(
      lockAndAssertTemplateTwinClinicalMutation({
        tx: tx as never,
        claim: pinned,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_ROLLOUT_REVOKED",
    });
    expect(mocks.lockPhysician).not.toHaveBeenCalled();
    expect(tx.$queryRaw).not.toHaveBeenCalled();
  });

  it("blocks a runtime-instance drift omitted by the lower-level rollout comparison", async () => {
    mocks.freshDoctor.mockResolvedValue({
      role: "DOCTOR",
      practiceId: "practice-1",
      rolloutToken: { ...TOKEN, runtimeInstanceId: "instance-before" },
    });
    const pinned = await claim();
    mocks.finalRollout.mockResolvedValue({
      allowed: true,
      token: { ...TOKEN, runtimeInstanceId: "instance-after" },
    });
    const tx = txWithVisit();

    await expect(
      lockAndAssertTemplateTwinClinicalMutation({
        tx: tx as never,
        claim: pinned,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_ROLLOUT_REVOKED",
    });
    expect(mocks.lockPhysician).not.toHaveBeenCalled();
    expect(tx.$queryRaw).not.toHaveBeenCalled();
  });

  it.each([
    "suspension",
    "deactivation",
    "role removal",
    "product removal",
    "practice transfer",
  ])("blocks %s between admission and final claim", async () => {
    const pinned = await claim();
    mocks.lockPhysician.mockRejectedValue(
      new TemplateTwinCurrentPhysicianAuthorityError(),
    );
    const tx = txWithVisit();

    await expect(
      lockAndAssertTemplateTwinClinicalMutation({
        tx: tx as never,
        claim: pinned,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
    });
    expect(tx.$queryRaw).not.toHaveBeenCalled();
  });

  it.each([
    [
      "template kind mutation",
      lockedVisit({
        noteTemplate: {
          id: "template-1",
          doctorId: "doctor-1",
          version: 7,
          templateKind: "structured",
          templateTwinCompiledVersion:
            provenance().noteTemplate!.templateTwinCompiledVersion,
        },
      }),
    ],
    ["fill replacement", lockedVisit({ templateTwinFill: null })],
    [
      "practice transfer",
      lockedVisit({
        templateTwinFill: {
          ...provenance().templateTwinFill!,
          practiceId: "practice-2",
        },
      }),
    ],
    [
      "cross-practice patient relink",
      lockedVisit({
        patient: {
          id: "patient-1",
          practiceId: "practice-2",
          externalId: null,
        },
      }),
    ],
  ])("blocks %s after admission", async (_label, row) => {
    const pinned = await claim();
    const tx = txWithVisit(row);
    await expect(
      lockAndAssertTemplateTwinClinicalMutation({
        tx: tx as never,
        claim: pinned,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinClinicalMutationAuthorizationError);
  });
});
