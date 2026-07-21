import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  requireDoctorSession: vi.fn(),
  noteTemplateFindFirst: vi.fn(),
  noteTemplateFindMany: vi.fn(),
  noteTemplateCreate: vi.fn(),
  noteTemplateUpdateMany: vi.fn(),
  compiledCreate: vi.fn(),
  outboxCreate: vi.fn(),
  transaction: vi.fn(),
  revalidatePath: vi.fn(),
  finalRollout: vi.fn(),
  currentPhysician: vi.fn(),
  lifecycleGuard: vi.fn(async (input: { operation: () => unknown }) =>
    input.operation(),
  ),
  versionAdmission: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  requireDoctorSession: mocks.requireDoctorSession,
  AuthError: class AuthError extends Error {
    constructor(
      readonly code: "UNAUTHENTICATED" | "FORBIDDEN",
      message: string,
    ) {
      super(message);
    }
  },
}));

vi.mock("next/cache", () => ({
  revalidatePath: mocks.revalidatePath,
}));

vi.mock("@/lib/template-twin/rollout", async (importOriginal) => {
  const actual =
    (await importOriginal()) as typeof import("@/lib/template-twin/rollout");
  return {
    ...actual,
    lockTemplateTwinRolloutForFinalClaim: mocks.finalRollout,
  };
});

vi.mock("@/lib/template-twin/final-claim-authority", () => ({
  lockAndAssertCurrentTemplateTwinPhysician: mocks.currentPhysician,
}));

vi.mock("@/lib/template-twin/staging-qa-lifecycle-guard", () => ({
  TemplateTwinStagingQaLifecycleGuardError: class TemplateTwinStagingQaLifecycleGuardError extends Error {},
  runWithTemplateTwinStagingQaLifecycleGuard: mocks.lifecycleGuard,
}));

vi.mock("@/lib/template-twin/staging-qa-version-admission", () => ({
  createTemplateTwinStagingQaVersionAdmission: mocks.versionAdmission,
}));

vi.mock("@meddoc/db", () => {
  const tx = {
    noteTemplate: {
      findFirst: mocks.noteTemplateFindFirst,
      findMany: mocks.noteTemplateFindMany,
      create: mocks.noteTemplateCreate,
      updateMany: mocks.noteTemplateUpdateMany,
    },
    templateTwinCompiledVersion: {
      create: mocks.compiledCreate,
    },
    templateTwinAuditOutbox: {
      create: mocks.outboxCreate,
    },
  };
  const prisma = {
    ...tx,
    $transaction: mocks.transaction,
  };
  return { default: prisma, prisma };
});

import {
  activateTemplateTwinVersionAction,
  createTemplateTwinVersionAction,
  deactivateTemplateTwinVersionAction,
  inspectTemplateTwinLineageAction,
  retireTemplateTwinVersionAction,
  rollbackTemplateTwinVersionAction,
} from "@/actions/template-twin-management";
import { TemplateTwinStagingQaLifecycleGuardError } from "@/lib/template-twin/staging-qa-lifecycle-guard";
import { syntheticSourceAdmission } from "@/lib/template-twin/__tests__/source-admission-fixture";

const DOCTOR_ID = "doctor-synthetic";
const PRACTICE_ID = "practice-synthetic";
const EMAIL = "physician@synthetic.test";

function latch<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function certifiedVersion(overrides: Record<string, unknown> = {}) {
  return {
    id: "template-v1",
    doctorId: DOCTOR_ID,
    name: "Synthetic primary care template",
    encounterType: "primary-care",
    versionDescription: "Initial synthetic certification",
    version: 1,
    status: "active",
    lineageId: "lineage-synthetic",
    sections: [{ key: "subjective" }],
    styleProfile: { tone: "concise" },
    specialtyBaseline: "primary-care",
    createdAt: new Date("2026-07-01T00:00:00.000Z"),
    templateTwinCompiledVersion: {
      id: "compiled-v1",
      sourceArtifactId: "source-v1",
      compilerVersion: "template-docx-v1",
      irSchemaVersion: 1,
      compiledAt: new Date("2026-07-01T00:00:00.000Z"),
      compiledDocumentIr: { compilerVersion: "template-docx-v1", fields: [] },
      unsupportedElements: [],
      structureSha256: "a".repeat(64),
      staticContentSha256: "b".repeat(64),
      certificationStatus: "CERTIFIED",
      blockingUnsupportedCount: 0,
      certification: {
        id: "cert-v1",
        certifiedAt: new Date("2026-07-02T00:00:00.000Z"),
      },
      sourceArtifact: {
        ...syntheticSourceAdmission({
          practiceId: PRACTICE_ID,
          lineageId: "lineage-synthetic",
          minimizedSha256: "c".repeat(64),
          minimizedSizeBytes: 4096,
        }),
        mimeType:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      },
      fields: [
        {
          fieldId: "field-1",
          displayOrder: 0,
          originalLabel: "Synthetic label",
          fieldKind: "narrative_text",
          allowedOptions: null,
          rendererBinding: {
            partName: "word/document.xml",
            path: "/w:document/w:body/w:sdt[1]",
          },
          detectionStatus: "CERTIFIED",
          clinicallyMaterial: true,
          criticality: "routine",
          required: true,
          mapping: {
            clinicalConcept: "subjective",
            expectedDataType: "string",
            polarityBehavior: "affirmative_only",
            temporality: "current",
            laterality: null,
            unitPolicy: null,
            approvedSynonyms: ["history"],
            required: true,
            blankPolicy: "leave_blank",
            unknownPolicy: "needs_review",
            practiceDefault: null,
            mappingStatus: "CERTIFIED",
            proposedByModel: "mock-provider",
          },
        },
      ],
    },
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.finalRollout.mockResolvedValue({
    allowed: true,
    token: {
      practiceId: PRACTICE_ID,
      globalGeneration: BigInt(11),
      practiceGeneration: BigInt(17),
    },
  });
  mocks.currentPhysician.mockResolvedValue({ email: EMAIL });
  mocks.lifecycleGuard.mockImplementation(
    async (input: { operation: () => unknown }) => input.operation(),
  );
  mocks.requireDoctorSession.mockResolvedValue({
    templateTwinRolloutToken: {
      practiceId: PRACTICE_ID,
      globalGeneration: BigInt(11),
      practiceGeneration: BigInt(17),
    },
    user: {
      id: DOCTOR_ID,
      email: EMAIL,
      practiceId: PRACTICE_ID,
      role: "DOCTOR",
      fullName: "Synthetic Physician",
    },
  });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        noteTemplate: {
          findFirst: mocks.noteTemplateFindFirst,
          findMany: mocks.noteTemplateFindMany,
          create: mocks.noteTemplateCreate,
          updateMany: mocks.noteTemplateUpdateMany,
        },
        templateTwinCompiledVersion: { create: mocks.compiledCreate },
        templateTwinAuditOutbox: { create: mocks.outboxCreate },
      }),
  );
  mocks.noteTemplateCreate.mockResolvedValue({ id: "template-v2" });
  mocks.compiledCreate.mockResolvedValue({ id: "compiled-v2" });
  mocks.noteTemplateUpdateMany.mockResolvedValue({ count: 1 });
  mocks.outboxCreate.mockResolvedValue({ id: "outbox-synthetic" });
});

describe("staging lifecycle management boundary", () => {
  it("does not enter a management transaction after staging admission is revoked", async () => {
    mocks.lifecycleGuard.mockRejectedValue(
      new TemplateTwinStagingQaLifecycleGuardError(),
    );

    await expect(
      activateTemplateTwinVersionAction("template-staging-revoked"),
    ).resolves.toEqual({
      ok: false,
      code: "NOT_FOUND",
      error:
        "That Template Twin version does not exist or is not available to this practice.",
    });
    expect(mocks.transaction).not.toHaveBeenCalled();
  });
});

describe("final current-physician authority", () => {
  const versionInput = {
    sourceNoteTemplateId: "template-v1",
    name: "Synthetic primary care template",
    encounterType: "primary-care",
    versionDescription: "Synthetic current-authority race proof",
  };

  it.each([
    ["create version", () => createTemplateTwinVersionAction(versionInput)],
    ["activate", () => activateTemplateTwinVersionAction("template-v1")],
    ["deactivate", () => deactivateTemplateTwinVersionAction("template-v1")],
    ["retire", () => retireTemplateTwinVersionAction("template-v1")],
    ["rollback", () => rollbackTemplateTwinVersionAction("template-v1")],
  ])(
    "fails %s closed when physician authority is revoked after request admission",
    async (_operation, invoke) => {
      mocks.currentPhysician.mockRejectedValueOnce(
        new Error("synthetic current physician authority revoked"),
      );

      await expect(invoke()).resolves.toMatchObject({
        ok: false,
        code: "PERSISTENCE_FAILED",
      });

      expect(mocks.transaction).toHaveBeenCalledTimes(1);
      expect(mocks.finalRollout).toHaveBeenCalledTimes(1);
      expect(mocks.currentPhysician).toHaveBeenCalledWith({
        tx: expect.any(Object),
        actor: expect.objectContaining({
          userId: DOCTOR_ID,
          practiceId: PRACTICE_ID,
        }),
      });
      expect(mocks.finalRollout.mock.invocationCallOrder[0]).toBeLessThan(
        mocks.currentPhysician.mock.invocationCallOrder[0]!,
      );
      expect(mocks.noteTemplateFindFirst).not.toHaveBeenCalled();
      expect(mocks.noteTemplateCreate).not.toHaveBeenCalled();
      expect(mocks.noteTemplateUpdateMany).not.toHaveBeenCalled();
      expect(mocks.compiledCreate).not.toHaveBeenCalled();
      expect(mocks.versionAdmission).not.toHaveBeenCalled();
      expect(mocks.outboxCreate).not.toHaveBeenCalled();
    },
  );
});

describe("createTemplateTwinVersionAction", () => {
  it("clones immutable source and structure into a fresh uncertified version", async () => {
    mocks.noteTemplateFindFirst
      .mockResolvedValueOnce(certifiedVersion())
      .mockResolvedValueOnce({ version: 1 });

    const result = await createTemplateTwinVersionAction({
      sourceNoteTemplateId: "template-v1",
      name: "Synthetic primary care template",
      encounterType: "primary-care",
      versionDescription: "Adjust the approved mapping for synthetic testing",
    });

    expect(result).toMatchObject({ ok: true, version: 2, status: "draft" });
    expect(mocks.requireDoctorSession).toHaveBeenCalledTimes(1);
    expect(mocks.transaction).toHaveBeenCalledWith(expect.any(Function), {
      isolationLevel: "ReadCommitted",
    });
    expect(mocks.noteTemplateFindFirst.mock.calls[0][0].where).toEqual({
      id: "template-v1",
      doctorId: DOCTOR_ID,
      templateKind: "template_twin_docx",
    });
    expect(mocks.noteTemplateFindFirst.mock.calls[1][0]).toMatchObject({
      where: {
        doctorId: DOCTOR_ID,
        lineageId: "lineage-synthetic",
        templateKind: "template_twin_docx",
      },
      orderBy: { version: "desc" },
    });

    const noteData = mocks.noteTemplateCreate.mock.calls[0][0].data;
    expect(noteData).toMatchObject({
      doctorId: DOCTOR_ID,
      name: "Synthetic primary care template",
      encounterType: "primary-care",
      versionDescription: "Adjust the approved mapping for synthetic testing",
      version: 2,
      status: "draft",
      lineageId: "lineage-synthetic",
      parentVersionId: "template-v1",
      templateKind: "template_twin_docx",
    });

    const compiledData = mocks.compiledCreate.mock.calls[0][0].data;
    expect(compiledData).toMatchObject({
      sourceArtifactId: "source-v1",
      compilerVersion: "template-docx-v1",
      certificationStatus: "NEEDS_CONFIRMATION",
      blockingUnsupportedCount: 0,
    });
    expect(compiledData.noteTemplateId).toEqual(noteData.id);
    expect(compiledData.fields.create[0]).toMatchObject({
      fieldId: "field-1",
      detectionStatus: "NEEDS_CONFIRMATION",
      mapping: {
        create: {
          clinicalConcept: "subjective",
          mappingStatus: "NEEDS_CONFIRMATION",
          approvedById: null,
          approvedAt: null,
        },
      },
    });
    expect(compiledData.certification).toBeUndefined();
    expect(compiledData.latestSyntheticTestManifest).toBeUndefined();
    expect(mocks.versionAdmission).toHaveBeenCalledWith(
      expect.objectContaining({
        actor: expect.objectContaining({
          userId: DOCTOR_ID,
          practiceId: PRACTICE_ID,
        }),
        source: expect.objectContaining({
          noteTemplateId: "template-v1",
          sourceArtifactId: "source-v1",
        }),
        target: expect.objectContaining({ version: 2 }),
      }),
    );
    expect(mocks.outboxCreate.mock.calls[0][0].data).toMatchObject({
      action: "TEMPLATE_TWIN_COMPILED",
      practiceId: PRACTICE_ID,
      actorId: DOCTOR_ID,
      targetType: "TemplateTwinCompiledVersion",
    });
  });

  it("returns a recoverable conflict to the losing concurrent immutable fork", async () => {
    const { Prisma } = await import("@prisma/client");
    const releaseLosingCreate = latch<void>();
    let createAttempt = 0;

    mocks.noteTemplateFindFirst.mockImplementation(
      async (query: { where: { id?: string } }) =>
        query.where.id ? certifiedVersion() : { version: 1 },
    );
    mocks.noteTemplateCreate.mockImplementation(async () => {
      createAttempt += 1;
      if (createAttempt === 1) {
        await releaseLosingCreate.promise;
        throw new Prisma.PrismaClientKnownRequestError(
          "Unique constraint failed on the lineage version",
          {
            code: "P2002",
            clientVersion: "test",
            meta: { target: ["doctorId", "lineageId", "version"] },
          },
        );
      }
      releaseLosingCreate.resolve();
      return { id: "template-winning-fork" };
    });

    const input = {
      sourceNoteTemplateId: "template-v1",
      name: "Synthetic primary care template",
      encounterType: "primary-care",
      versionDescription: "Concurrent synthetic mapping save",
    };
    const results = await Promise.all([
      createTemplateTwinVersionAction(input),
      createTemplateTwinVersionAction(input),
    ]);

    expect(results).toEqual(
      expect.arrayContaining([
        {
          ok: false,
          code: "CONFLICT",
          error:
            "This template lineage changed in another request. Reload and try again.",
        },
        expect.objectContaining({ ok: true, version: 2, status: "draft" }),
      ]),
    );
    expect(mocks.noteTemplateCreate).toHaveBeenCalledTimes(2);
    expect(mocks.compiledCreate).toHaveBeenCalledTimes(1);
    expect(mocks.versionAdmission).toHaveBeenCalledTimes(1);
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(1);
    const guardInput = mocks.lifecycleGuard.mock.calls[0]?.[0] as unknown as {
      isExpectedBusinessError?: (error: unknown) => boolean;
    };
    const p2002 = new Prisma.PrismaClientKnownRequestError(
      "Unique constraint failed on the lineage version",
      {
        code: "P2002",
        clientVersion: "test",
      },
    );
    expect(guardInput.isExpectedBusinessError?.(p2002)).toBe(true);
    expect(
      guardInput.isExpectedBusinessError?.(
        new Prisma.PrismaClientKnownRequestError("Database unavailable", {
          code: "P1001",
          clientVersion: "test",
        }),
      ),
    ).toBe(false);
    expect(
      guardInput.isExpectedBusinessError?.(new Error("unknown failure")),
    ).toBe(false);
  });

  it("requires physician-readable name, scope, and version description", async () => {
    const result = await createTemplateTwinVersionAction({
      sourceNoteTemplateId: "template-v1",
      name: "",
      encounterType: "",
      versionDescription: "",
    });

    expect(result).toMatchObject({ ok: false, code: "INVALID_IDENTITY" });
    expect(mocks.noteTemplateCreate).not.toHaveBeenCalled();
    expect(mocks.compiledCreate).not.toHaveBeenCalled();
  });

  it("does not fork an uncertified or cross-tenant source", async () => {
    mocks.noteTemplateFindFirst.mockResolvedValueOnce(
      certifiedVersion({
        templateTwinCompiledVersion: {
          ...certifiedVersion().templateTwinCompiledVersion,
          certificationStatus: "NEEDS_CONFIRMATION",
          certification: null,
        },
      }),
    );
    const uncertified = await createTemplateTwinVersionAction({
      sourceNoteTemplateId: "template-v1",
      name: "Synthetic primary care template",
      encounterType: "primary-care",
      versionDescription: "Synthetic version description",
    });
    expect(uncertified).toMatchObject({ ok: false, code: "NOT_CERTIFIED" });

    mocks.noteTemplateFindFirst.mockResolvedValueOnce(null);
    const notOwned = await createTemplateTwinVersionAction({
      sourceNoteTemplateId: "template-other-practice",
      name: "Synthetic primary care template",
      encounterType: "primary-care",
      versionDescription: "Synthetic version description",
    });
    expect(notOwned).toMatchObject({ ok: false, code: "NOT_FOUND" });
    expect(mocks.noteTemplateCreate).not.toHaveBeenCalled();
  });

  it("keeps a version lineage in one visit scope", async () => {
    mocks.noteTemplateFindFirst.mockResolvedValueOnce(certifiedVersion());

    const result = await createTemplateTwinVersionAction({
      sourceNoteTemplateId: "template-v1",
      name: "Synthetic cardiology template",
      encounterType: "cardiology",
      versionDescription: "Synthetic scope-change attempt",
    });

    expect(result).toMatchObject({ ok: false, code: "INVALID_IDENTITY" });
    expect(mocks.noteTemplateCreate).not.toHaveBeenCalled();
    expect(mocks.compiledCreate).not.toHaveBeenCalled();
  });

  it("does not persist a new version after its pinned rollout epoch is revoked", async () => {
    const entered = latch<void>();
    const release = latch<{
      allowed: false;
      code: "TEMPLATE_TWIN_PRACTICE_GENERATION_STALE";
      reason: string;
      currentToken: {
        practiceId: string;
        globalGeneration: bigint;
        practiceGeneration: bigint;
      };
    }>();
    mocks.finalRollout.mockImplementationOnce(async () => {
      entered.resolve();
      return release.promise;
    });

    const pending = createTemplateTwinVersionAction({
      sourceNoteTemplateId: "template-v1",
      name: "Synthetic primary care template",
      encounterType: "primary-care",
      versionDescription: "Synthetic stale-generation fork",
    });
    await entered.promise;
    expect(mocks.noteTemplateFindFirst).not.toHaveBeenCalled();
    expect(mocks.noteTemplateCreate).not.toHaveBeenCalled();

    release.resolve({
      allowed: false,
      code: "TEMPLATE_TWIN_PRACTICE_GENERATION_STALE",
      reason: "Synthetic practice generation changed.",
      currentToken: {
        practiceId: PRACTICE_ID,
        globalGeneration: BigInt(11),
        practiceGeneration: BigInt(18),
      },
    });

    await expect(pending).resolves.toMatchObject({
      ok: false,
      code: "ROLLOUT_CHANGED",
      error: expect.stringContaining("TEMPLATE_TWIN_PRACTICE_GENERATION_STALE"),
    });
    expect(mocks.noteTemplateCreate).not.toHaveBeenCalled();
    expect(mocks.compiledCreate).not.toHaveBeenCalled();
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
  });
});

describe("Template Twin status transitions", () => {
  it("activates only a certified owned version and durably audits in the transaction", async () => {
    mocks.noteTemplateFindFirst
      .mockResolvedValueOnce(
        certifiedVersion({ id: "template-v2", status: "inactive", version: 2 }),
      )
      .mockResolvedValueOnce(null);

    const result = await activateTemplateTwinVersionAction("template-v2");

    expect(result).toMatchObject({ ok: true, status: "active" });
    expect(mocks.noteTemplateUpdateMany.mock.calls[0][0]).toEqual({
      where: {
        doctorId: DOCTOR_ID,
        encounterType: "primary-care",
        status: "active",
        NOT: { id: "template-v2" },
      },
      data: { status: "inactive" },
    });
    expect(mocks.noteTemplateUpdateMany.mock.calls[1][0]).toEqual({
      where: {
        id: "template-v2",
        doctorId: DOCTOR_ID,
        status: { in: ["draft", "inactive"] },
      },
      data: { status: "active" },
    });
    expect(mocks.outboxCreate.mock.calls[0][0].data.action).toBe(
      "TEMPLATE_TWIN_ACTIVATED",
    );
  });

  it("refuses activation of a legacy certified version without current source admission", async () => {
    const admitted = certifiedVersion({
      id: "template-legacy",
      status: "inactive",
      version: 2,
    });
    const legacy = {
      ...admitted,
      templateTwinCompiledVersion: {
        ...admitted.templateTwinCompiledVersion,
        sourceArtifact: {
          ...admitted.templateTwinCompiledVersion.sourceArtifact,
          quarantineArtifact: null,
        },
      },
    };
    mocks.noteTemplateFindFirst.mockResolvedValueOnce(legacy);

    await expect(
      activateTemplateTwinVersionAction("template-legacy"),
    ).resolves.toMatchObject({
      ok: false,
      code: "SOURCE_UNSAFE",
    });
    expect(mocks.noteTemplateUpdateMany).not.toHaveBeenCalled();
    expect(mocks.outboxCreate).not.toHaveBeenCalled();
  });

  it("deactivates without mutating template content or certification", async () => {
    mocks.noteTemplateFindFirst.mockResolvedValueOnce(certifiedVersion());

    const result = await deactivateTemplateTwinVersionAction("template-v1");

    expect(result).toMatchObject({ ok: true, status: "inactive" });
    expect(mocks.noteTemplateUpdateMany).toHaveBeenCalledWith({
      where: { id: "template-v1", doctorId: DOCTOR_ID, status: "active" },
      data: { status: "inactive" },
    });
    expect(mocks.outboxCreate.mock.calls[0][0].data.action).toBe(
      "TEMPLATE_TWIN_DEACTIVATED",
    );
  });

  it("retires in place, preserves history, and records both implicit deactivation and retirement", async () => {
    mocks.noteTemplateFindFirst.mockResolvedValueOnce(certifiedVersion());

    const result = await retireTemplateTwinVersionAction("template-v1");

    expect(result).toMatchObject({ ok: true, status: "retired" });
    expect(mocks.noteTemplateUpdateMany).toHaveBeenCalledWith({
      where: {
        id: "template-v1",
        doctorId: DOCTOR_ID,
        status: { not: "retired" },
      },
      data: { status: "retired" },
    });
    expect(
      mocks.outboxCreate.mock.calls.map((call) => call[0].data.action),
    ).toEqual(["TEMPLATE_TWIN_DEACTIVATED", "TEMPLATE_TWIN_RETIRED"]);
    expect(
      mocks.noteTemplateUpdateMany.mock.calls.every(
        (call) => Object.keys(call[0].data).join(",") === "status",
      ),
    ).toBe(true);
  });

  it("refuses activation of an uncertified, retired, or foreign version", async () => {
    mocks.noteTemplateFindFirst.mockResolvedValueOnce(
      certifiedVersion({
        status: "draft",
        templateTwinCompiledVersion: {
          ...certifiedVersion().templateTwinCompiledVersion,
          certificationStatus: "NEEDS_CONFIRMATION",
          certification: null,
        },
      }),
    );
    expect(
      await activateTemplateTwinVersionAction("template-v1"),
    ).toMatchObject({
      ok: false,
      code: "NOT_CERTIFIED",
    });

    mocks.noteTemplateFindFirst.mockResolvedValueOnce(
      certifiedVersion({ status: "retired" }),
    );
    expect(
      await activateTemplateTwinVersionAction("template-v1"),
    ).toMatchObject({
      ok: false,
      code: "RETIRED",
    });

    mocks.noteTemplateFindFirst.mockResolvedValueOnce(null);
    expect(
      await activateTemplateTwinVersionAction("template-other"),
    ).toMatchObject({
      ok: false,
      code: "NOT_FOUND",
    });
    expect(mocks.noteTemplateUpdateMany).not.toHaveBeenCalled();
  });
});

describe("lineage inspection and rollback", () => {
  it("returns metadata-only lineage and marks only prior certified versions rollback-eligible", async () => {
    mocks.noteTemplateFindFirst.mockResolvedValueOnce(
      certifiedVersion({ version: 3 }),
    );
    mocks.noteTemplateFindMany.mockResolvedValueOnce([
      certifiedVersion({ id: "template-v1", version: 1, status: "inactive" }),
      certifiedVersion({ id: "template-v2", version: 2, status: "retired" }),
      certifiedVersion({ id: "template-v3", version: 3, status: "active" }),
    ]);

    const result = await inspectTemplateTwinLineageAction("template-v3");

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.lineage.versions.map((version) => version.version)).toEqual([
      3, 2, 1,
    ]);
    expect(
      result.lineage.versions.find((version) => version.version === 1),
    ).toMatchObject({
      status: "inactive",
      rollbackEligible: true,
    });
    expect(
      result.lineage.versions.find((version) => version.version === 2),
    ).toMatchObject({
      status: "retired",
      rollbackEligible: false,
    });
    expect(JSON.stringify(result)).not.toContain("objectKey");
    expect(JSON.stringify(result)).not.toContain("compiledDocumentIr");
    expect(JSON.stringify(result)).not.toContain("approvedSynonyms");
  });

  it("rolls back only to an older certified inactive version in the same lineage", async () => {
    mocks.noteTemplateFindFirst
      .mockResolvedValueOnce(
        certifiedVersion({ status: "inactive", version: 1 }),
      )
      .mockResolvedValueOnce(
        certifiedVersion({ id: "template-v3", version: 3, status: "active" }),
      );

    const result = await rollbackTemplateTwinVersionAction("template-v1");

    expect(result).toMatchObject({
      ok: true,
      status: "active",
      rolledBackFromVersion: 3,
      rolledBackToVersion: 1,
    });
    expect(mocks.noteTemplateUpdateMany.mock.calls[0][0]).toEqual({
      where: {
        id: "template-v3",
        doctorId: DOCTOR_ID,
        status: "active",
        lineageId: "lineage-synthetic",
      },
      data: { status: "inactive" },
    });
    expect(mocks.noteTemplateUpdateMany.mock.calls[1][0]).toEqual({
      where: {
        id: "template-v1",
        doctorId: DOCTOR_ID,
        status: "inactive",
        lineageId: "lineage-synthetic",
      },
      data: { status: "active" },
    });
    expect(
      mocks.outboxCreate.mock.calls.map((call) => call[0].data.action),
    ).toEqual(["TEMPLATE_TWIN_ROLLED_BACK", "TEMPLATE_TWIN_ACTIVATED"]);
  });

  it("blocks rollback to a retired, newer, or different-lineage version", async () => {
    mocks.noteTemplateFindFirst.mockResolvedValueOnce(
      certifiedVersion({ status: "retired", version: 1 }),
    );
    expect(
      await rollbackTemplateTwinVersionAction("template-v1"),
    ).toMatchObject({
      ok: false,
      code: "RETIRED",
    });

    mocks.noteTemplateFindFirst
      .mockResolvedValueOnce(
        certifiedVersion({ status: "inactive", version: 4 }),
      )
      .mockResolvedValueOnce(
        certifiedVersion({ id: "template-v3", status: "active", version: 3 }),
      );
    expect(
      await rollbackTemplateTwinVersionAction("template-v4"),
    ).toMatchObject({
      ok: false,
      code: "ROLLBACK_NOT_ALLOWED",
    });

    mocks.noteTemplateFindFirst
      .mockResolvedValueOnce(
        certifiedVersion({ status: "inactive", version: 1 }),
      )
      .mockResolvedValueOnce(
        certifiedVersion({
          id: "template-other-lineage",
          status: "active",
          version: 3,
          lineageId: "other-lineage",
        }),
      );
    expect(
      await rollbackTemplateTwinVersionAction("template-v1"),
    ).toMatchObject({
      ok: false,
      code: "ROLLBACK_NOT_ALLOWED",
    });
    expect(mocks.noteTemplateUpdateMany).not.toHaveBeenCalled();
  });
});

describe("server-side rollout boundary", () => {
  it("performs no lifecycle read or write when fresh doctor/rollout authorization fails", async () => {
    const { AuthError } = await import("@/lib/auth");
    mocks.requireDoctorSession.mockRejectedValueOnce(
      new AuthError(
        "FORBIDDEN",
        "Template Twin is not enabled for this practice.",
      ),
    );

    const result = await inspectTemplateTwinLineageAction("template-v1");

    expect(result).toEqual({
      ok: false,
      code: "FORBIDDEN",
      error: "Template Twin is not enabled for this practice.",
    });
    expect(mocks.noteTemplateFindFirst).not.toHaveBeenCalled();
    expect(mocks.noteTemplateFindMany).not.toHaveBeenCalled();
    expect(mocks.noteTemplateUpdateMany).not.toHaveBeenCalled();
  });
});
