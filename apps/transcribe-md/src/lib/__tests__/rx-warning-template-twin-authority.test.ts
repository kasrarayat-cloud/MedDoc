import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findVisit: vi.fn(),
  createOverride: vi.fn(),
  findOverride: vi.fn(),
  findLockedVisit: vi.fn(),
  transaction: vi.fn(),
  session: vi.fn(),
  hasTwin: vi.fn(),
  loadAdmission: vi.fn(),
  pinMutation: vi.fn(),
  lockMutation: vi.fn(),
  lockOrdinary: vi.fn(),
  mutationAudit: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeVisit: { findUnique: mocks.findVisit },
    rxWarningOverride: {
      create: mocks.createOverride,
      findUnique: mocks.findOverride,
    },
    $transaction: mocks.transaction,
  },
}));
vi.mock("@/lib/auth", () => ({ getSession: mocks.session }));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));
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

import { TemplateTwinClinicalMutationAuthorizationError } from "@/lib/template-twin/visit-mutation-authority";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import { recordOverride } from "../rx-warning-audit";

const INPUT = {
  visitId: "visit-1",
  warningId: "rx-warning-0",
  rxLineNumber: 0,
  severity: "critical",
  headline: "Synthetic interaction warning",
  reason: "Synthetic physician rationale.",
};

function visit(overrides: Record<string, unknown> = {}) {
  return {
    userId: "doctor-1",
    patientId: "patient-1",
    patient: { externalId: null },
    status: "READY",
    deletedAt: null,
    archivedAt: null,
    signedAt: null,
    updatedAt: new Date("2026-07-20T00:00:00.000Z"),
    rxDrafts: { warnings: [{ severity: "critical", message: "Synthetic" }] },
    templateTwinSyntheticQaRun: null,
    noteTemplateId: "ordinary-1",
    noteTemplateVersion: 1,
    noteTemplate: { templateKind: "structured" },
    templateTwinFill: null,
    templateTwinSyntheticQaAdmission: null,
    templateTwinProviderExecutions: [],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.session.mockResolvedValue({
    user: { id: "doctor-1", email: "doctor@example.test" },
  });
  mocks.findVisit.mockResolvedValue(visit());
  mocks.loadAdmission.mockImplementation(async () => mocks.findVisit());
  mocks.hasTwin.mockImplementation(
    (row: {
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
  );
  mocks.pinMutation.mockResolvedValue(null);
  mocks.createOverride.mockResolvedValue({ id: "override-1" });
  mocks.findOverride.mockResolvedValue({ id: "override-1" });
  mocks.findLockedVisit.mockResolvedValue(visit());
  mocks.mutationAudit.mockResolvedValue(undefined);
  mocks.lockOrdinary.mockResolvedValue(undefined);
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        transcribeVisit: { findUnique: mocks.findLockedVisit },
        rxWarningOverride: {
          create: mocks.createOverride,
          findUnique: mocks.findOverride,
        },
      }),
  );
});

describe("Rx override Template Twin final authority", () => {
  it("returns no warning snapshot when durable lineage appears after ordinary admission", async () => {
    const ordinary = visit();
    mocks.loadAdmission.mockResolvedValueOnce(ordinary);
    mocks.findVisit.mockResolvedValueOnce(null);

    await expect(recordOverride(INPUT)).resolves.toMatchObject({ ok: false });
    expect(mocks.findVisit).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          ...currentClinicalVisitActorWhere("doctor-1"),
          ...TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE,
        }),
      }),
    );
    expect(mocks.createOverride).not.toHaveBeenCalled();
  });

  it("preserves the ordinary write behind the exact final ordinary lock", async () => {
    await expect(recordOverride(INPUT)).resolves.toEqual({
      ok: true,
      auditId: "override-1",
    });
    expect(mocks.createOverride).toHaveBeenCalledTimes(1);
    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(mocks.lockOrdinary).toHaveBeenCalledWith(
      expect.objectContaining({
        visitId: "visit-1",
        actorUserId: "doctor-1",
        admittedPatientId: "patient-1",
        admittedNoteTemplateId: "ordinary-1",
      }),
    );
    expect(mocks.lockMutation).not.toHaveBeenCalled();
  });

  it("does not write an ordinary override when Twin provenance appears before the side-table write", async () => {
    mocks.lockOrdinary.mockRejectedValueOnce(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
      ),
    );

    await expect(recordOverride(INPUT)).resolves.toMatchObject({
      ok: false,
      error: expect.stringContaining("visit changed"),
    });
    expect(mocks.createOverride).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("writes a live Twin override only inside the locked final claim", async () => {
    const current = visit({
      noteTemplate: { templateKind: "template_twin_docx" },
      templateTwinFill: { id: "fill-1" },
    });
    mocks.findVisit.mockResolvedValue(current);
    mocks.pinMutation.mockResolvedValue({ visitId: "visit-1" });
    mocks.lockMutation.mockResolvedValue(current);

    await expect(recordOverride(INPUT)).resolves.toEqual({
      ok: true,
      auditId: "override-1",
    });
    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(mocks.lockMutation).toHaveBeenCalledTimes(1);
    expect(mocks.createOverride).toHaveBeenCalledTimes(1);
  });

  it("blocks suspension, role/product loss, practice transfer, or rollout revoke at final claim", async () => {
    const current = visit({
      noteTemplate: { templateKind: "template_twin_docx" },
      templateTwinFill: { id: "fill-1" },
    });
    mocks.findVisit.mockResolvedValue(current);
    mocks.pinMutation.mockResolvedValue({ visitId: "visit-1" });
    mocks.lockMutation.mockRejectedValue(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
      ),
    );

    await expect(recordOverride(INPUT)).resolves.toMatchObject({
      ok: false,
      error: expect.stringContaining("authorization changed"),
    });
    expect(mocks.createOverride).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("blocks a warning-set race before creating the sign-critical override", async () => {
    const admitted = visit({
      noteTemplate: { templateKind: "template_twin_docx" },
      templateTwinFill: { id: "fill-1" },
    });
    mocks.findVisit.mockResolvedValue(admitted);
    mocks.pinMutation.mockResolvedValue({ visitId: "visit-1" });
    mocks.lockMutation.mockResolvedValue(
      visit({
        noteTemplate: { templateKind: "template_twin_docx" },
        templateTwinFill: { id: "fill-1" },
        rxDrafts: {
          warnings: [{ severity: "major", message: "Changed synthetic" }],
        },
      }),
    );

    await expect(recordOverride(INPUT)).resolves.toMatchObject({
      ok: false,
      error: expect.stringContaining("warnings changed"),
    });
    expect(mocks.createOverride).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("rolls back the Twin override row when required outbox enqueue fails", async () => {
    const current = visit({
      noteTemplate: { templateKind: "template_twin_docx" },
      templateTwinFill: { id: "fill-1" },
    });
    mocks.findVisit.mockResolvedValue(current);
    mocks.pinMutation.mockResolvedValue({ visitId: "visit-1" });
    mocks.lockMutation.mockResolvedValue(current);
    mocks.mutationAudit.mockRejectedValueOnce(new Error("outbox unavailable"));
    let committed = false;
    mocks.transaction.mockImplementationOnce(
      async (callback: (tx: unknown) => Promise<unknown>) => {
        let staged = false;
        try {
          const result = await callback({
            rxWarningOverride: {
              create: vi.fn(async (...args: unknown[]) => {
                staged = true;
                return mocks.createOverride(...args);
              }),
              findUnique: mocks.findOverride,
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

    await expect(recordOverride(INPUT)).resolves.toMatchObject({ ok: false });
    expect(committed).toBe(false);
    expect(mocks.mutationAudit).toHaveBeenCalledTimes(1);
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("excludes pre-certification provenance before a clinical override", async () => {
    mocks.pinMutation.mockRejectedValue(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
      ),
    );

    await expect(recordOverride(INPUT)).resolves.toEqual({
      ok: false,
      error: "Visit not found.",
    });
    expect(mocks.transaction).not.toHaveBeenCalled();
    expect(mocks.createOverride).not.toHaveBeenCalled();
  });

  it("excludes an orphaned reserved synthetic patient before reading warnings", async () => {
    mocks.findVisit.mockResolvedValue(
      visit({ patient: { externalId: "SYNTHETIC-QA-ONLY" } }),
    );
    mocks.pinMutation.mockRejectedValueOnce(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
      ),
    );

    await expect(recordOverride(INPUT)).resolves.toEqual({
      ok: false,
      error: "Visit not found.",
    });
    expect(mocks.transaction).not.toHaveBeenCalled();
    expect(mocks.createOverride).not.toHaveBeenCalled();
  });
});
