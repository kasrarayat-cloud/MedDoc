import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  findUnique: vi.fn(),
  update: vi.fn(),
  updateMany: vi.fn(),
  transaction: vi.fn(),
  computeEmScore: vi.fn(),
  engineToUiScore: vi.fn(),
  mergeAdditions: vi.fn(),
  invalidateTwin: vi.fn(),
  pinStagingMutation: vi.fn(),
  isOwnedStagingVisit: vi.fn(),
  pinTwinMutation: vi.fn(),
  lockTwinMutation: vi.fn(),
  lockOrdinary: vi.fn(),
  loadAdmission: vi.fn(),
  hasTwin: vi.fn(),
  mutationAudit: vi.fn(),
  requireRead: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeVisit: {
      findUnique: mocks.findUnique,
      update: mocks.update,
      updateMany: mocks.updateMany,
    },
    $transaction: mocks.transaction,
  },
}));
vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("@/lib/api-error", () => ({
  apiError: (
    error: string,
    status: number,
    details?: Record<string, unknown>,
  ) => Response.json({ error, ...details }, { status }),
  withApiHandler: (
    _name: string,
    handler: (
      request: Request,
      context: { params: Promise<{ id: string }> },
    ) => Promise<Response>,
  ) => handler,
}));
vi.mock("@/lib/em-coding/score", () => ({
  computeEmScore: mocks.computeEmScore,
}));
vi.mock("@/lib/em-coding/to-ui-score", () => ({
  engineToUiScore: mocks.engineToUiScore,
}));
vi.mock("@/lib/em-coding/displayed-level", () => ({
  extractIcdRows: vi.fn(() => []),
  extractRxRows: vi.fn(() => []),
  extractEmOverride: vi.fn(() => undefined),
}));
vi.mock("@/lib/em-coding/merge-additions", () => ({
  mergeAdditions: mocks.mergeAdditions,
}));
vi.mock("@/lib/template-twin/soap-binding", () => ({
  invalidateTemplateTwinAfterSoapEdit: mocks.invalidateTwin,
}));
vi.mock("@/lib/template-twin/staging-qa-mutation", () => ({
  pinTemplateTwinStagingQaMutation: mocks.pinStagingMutation,
}));
vi.mock("@/lib/template-twin/staging-qa-access", () => ({
  isOwnedTemplateTwinStagingQaVisit: mocks.isOwnedStagingVisit,
}));
vi.mock("@/lib/template-twin/visit-mutation-authority", () => ({
  TEMPLATE_TWIN_CLINICAL_MUTATION_PROVENANCE_SELECT: {},
  TemplateTwinClinicalMutationAuthorizationError: class TemplateTwinClinicalMutationAuthorizationError extends Error {},
  pinTemplateTwinClinicalMutation: mocks.pinTwinMutation,
  lockAndAssertTemplateTwinClinicalMutation: mocks.lockTwinMutation,
  lockAndAssertOrdinaryClinicalMutation: mocks.lockOrdinary,
  loadTemplateTwinClinicalMutationAdmissionTarget: mocks.loadAdmission,
  hasDurableTemplateTwinClinicalMutationProvenance: mocks.hasTwin,
  enqueueTemplateTwinClinicalMutationAudit: mocks.mutationAudit,
}));
vi.mock("@/lib/template-twin/read-authority", () => ({
  TemplateTwinVisitReadAuthorityError: class TemplateTwinVisitReadAuthorityError extends Error {},
  requireTemplateTwinVisitReadAuthority: mocks.requireRead,
}));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));

import { TranscribeVisitStatus } from "@prisma/client";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import { TemplateTwinClinicalMutationAuthorizationError } from "@/lib/template-twin/visit-mutation-authority";

import { POST as applyAdditions } from "../apply-additions/route";
import { POST as applyOverride } from "../override/route";
import { POST as computeScore } from "../route";

const VISIT_ID = "synthetic-visit-1";
const DOCTOR_ID = "synthetic-doctor-1";

const stagingRun = {
  id: "synthetic-run-1",
  practiceId: "synthetic-practice-1",
  doctorId: DOCTOR_ID,
  fixtureVersion: "template-twin-staging-safe-docx/1.0.0",
  attempt: 2,
  pinnedGlobalRolloutGeneration: BigInt(4),
  pinnedPracticeRolloutGeneration: BigInt(7),
};

const stagingClaim = {
  runId: stagingRun.id,
  attempt: stagingRun.attempt,
  visitId: VISIT_ID,
  userId: DOCTOR_ID,
  practiceId: stagingRun.practiceId,
  rolloutToken: {
    practiceId: stagingRun.practiceId,
    globalGeneration: BigInt(4),
    practiceGeneration: BigInt(7),
  },
};

function visitRow(
  templateTwinSyntheticQaRun: typeof stagingRun | null = null,
  overrides: Record<string, unknown> = {},
) {
  return {
    id: VISIT_ID,
    userId: DOCTOR_ID,
    patientId: "patient-1",
    noteTemplateId: "ordinary-template-1",
    status: TranscribeVisitStatus.READY,
    deletedAt: null,
    archivedAt: null,
    signedAt: null,
    updatedAt: new Date("2026-07-20T00:00:00.000Z"),
    soapDraft: "## Subjective\nSynthetic evidence only.",
    soapFinal: "## Subjective\nSynthetic evidence only.",
    soapVersion: 3,
    audioDurationSec: 60,
    dictationDurationSec: null,
    inputMode: "text_note",
    icdCodes: [],
    cptCodes: {},
    rxDrafts: [],
    patient: { externalId: null },
    templateTwinSyntheticQaRun,
    noteTemplate: {
      templateKind: "structured",
      templateTwinCompiledVersion: null,
    },
    templateTwinFill: null,
    templateTwinSyntheticQaAdmission: null,
    templateTwinProviderExecutions: [],
    ...overrides,
  };
}

function request(
  route: "apply-additions" | "override" | "score",
  sameOrigin = true,
): NextRequest {
  const body =
    route === "apply-additions"
      ? {
          additions: [
            { criterionId: "synthetic-criterion", text: "Synthetic addition." },
          ],
        }
      : route === "override"
        ? { overrideToCode: "99213", reason: "Synthetic QA reason." }
        : { soapText: "Caller supplied synthetic SOAP." };
  const suffix = route === "score" ? "" : `/${route}`;
  return new Request(
    `https://app.example.test/api/visits/${VISIT_ID}/em-score${suffix}`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
        host: "app.example.test",
        origin: sameOrigin
          ? "https://app.example.test"
          : "https://cross-site.example.test",
        "sec-fetch-site": sameOrigin ? "same-origin" : "cross-site",
      },
      body: JSON.stringify(body),
    },
  ) as unknown as NextRequest;
}

const context = { params: Promise.resolve({ id: VISIT_ID }) };

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({
    user: {
      id: DOCTOR_ID,
      email: "doctor@synthetic.test",
      practiceId: "synthetic-practice-1",
    },
  });
  mocks.findUnique.mockResolvedValue(visitRow());
  mocks.loadAdmission.mockImplementation(async () => mocks.findUnique());
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
  mocks.pinStagingMutation.mockResolvedValue(null);
  mocks.pinTwinMutation.mockResolvedValue(null);
  mocks.mutationAudit.mockResolvedValue(undefined);
  mocks.lockOrdinary.mockResolvedValue(undefined);
  mocks.requireRead.mockResolvedValue({
    isTemplateTwin: false,
    practiceId: null,
  });
  mocks.isOwnedStagingVisit.mockResolvedValue(false);
  mocks.updateMany.mockResolvedValue({ count: 1 });
  mocks.update.mockResolvedValue({ id: VISIT_ID });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        transcribeVisit: {
          update: mocks.update,
          updateMany: mocks.updateMany,
        },
      }),
  );
  mocks.computeEmScore.mockResolvedValue({ code: "99213" });
  mocks.engineToUiScore.mockReturnValue({ suggestedCode: "99213" });
  mocks.mergeAdditions.mockReturnValue({
    newSoap: "## Subjective\nSynthetic evidence only.\nSynthetic addition.",
    applied: [{ criterionId: "synthetic-criterion" }],
    skipped: [],
  });
  mocks.invalidateTwin.mockResolvedValue(undefined);
});

describe("ordinary visit compatibility", () => {
  it("preserves same-origin provider-backed scoring for an ordinary visit", async () => {
    const response = await computeScore(request("score"), context);

    expect(response.status).toBe(200);
    expect(mocks.computeEmScore).toHaveBeenCalledWith(
      "Caller supplied synthetic SOAP.",
      expect.objectContaining({
        practiceId: "synthetic-practice-1",
        visitId: VISIT_ID,
        userId: DOCTOR_ID,
      }),
    );
  });

  it("preserves the existing additions mutation path", async () => {
    const response = await applyAdditions(request("apply-additions"), context);

    expect(response.status).toBe(200);
    expect(mocks.pinStagingMutation).not.toHaveBeenCalled();
    expect(mocks.computeEmScore).toHaveBeenCalledTimes(1);
    expect(mocks.updateMany).toHaveBeenCalledTimes(1);
    expect(mocks.invalidateTwin).toHaveBeenCalledTimes(1);
    expect(mocks.logAudit).toHaveBeenCalledWith(
      expect.objectContaining({ action: "EM_BUMP_APPLIED" }),
    );
  });

  it("reasserts ownership, content, lifecycle, and ordinary provenance at the post-provider write", async () => {
    const admitted = visitRow();
    mocks.findUnique.mockResolvedValue(admitted);

    const response = await applyAdditions(request("apply-additions"), context);

    expect(response.status).toBe(200);
    expect(mocks.updateMany).toHaveBeenCalledWith({
      where: {
        id: VISIT_ID,
        userId: DOCTOR_ID,
        status: TranscribeVisitStatus.READY,
        deletedAt: null,
        archivedAt: null,
        signedAt: null,
        updatedAt: admitted.updatedAt,
        soapDraft: admitted.soapDraft,
        soapFinal: admitted.soapFinal,
        soapVersion: admitted.soapVersion,
        ...TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE,
      },
      data: {
        soapDraft:
          "## Subjective\nSynthetic evidence only.\nSynthetic addition.",
        soapFinal:
          "## Subjective\nSynthetic evidence only.\nSynthetic addition.",
        soapVersion: { increment: 1 },
      },
    });
  });

  it("blocks additions before provider egress when ordinary provenance changes", async () => {
    mocks.lockOrdinary.mockRejectedValueOnce(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
      ),
    );

    const response = await applyAdditions(request("apply-additions"), context);

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_CONFLICT",
    });
    expect(mocks.computeEmScore).not.toHaveBeenCalled();
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });

  it("discards the additions provider result when provenance changes before final commit", async () => {
    mocks.lockOrdinary
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(
        new TemplateTwinClinicalMutationAuthorizationError(
          "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
        ),
      );

    const response = await applyAdditions(request("apply-additions"), context);

    expect(response.status).toBe(409);
    expect(mocks.computeEmScore).toHaveBeenCalledTimes(1);
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it.each([
    "durable Twin marker or template conversion",
    "owner transfer",
    "archive or deletion",
    "signing",
    "metadata updatedAt drift",
    "SOAP content or version drift",
  ])(
    "discards the provider result when a concurrent %s makes the final CAS miss",
    async () => {
      mocks.updateMany.mockResolvedValueOnce({ count: 0 });

      const response = await applyAdditions(
        request("apply-additions"),
        context,
      );

      expect(response.status).toBe(409);
      await expect(response.json()).resolves.toMatchObject({
        code: "SOAP_VERSION_CONFLICT",
      });
      expect(mocks.computeEmScore).toHaveBeenCalledTimes(1);
      expect(mocks.invalidateTwin).not.toHaveBeenCalled();
      expect(mocks.logAudit).not.toHaveBeenCalled();
    },
  );

  it("preserves the existing override mutation path", async () => {
    const response = await applyOverride(request("override"), context);

    expect(response.status).toBe(200);
    expect(mocks.pinStagingMutation).not.toHaveBeenCalled();
    expect(mocks.computeEmScore).toHaveBeenCalledTimes(1);
    expect(mocks.update).toHaveBeenCalledTimes(1);
    expect(mocks.lockOrdinary).toHaveBeenCalledTimes(1);
    expect(mocks.logAudit).toHaveBeenCalledWith(
      expect.objectContaining({ action: "EM_OVERRIDE_APPLIED" }),
    );
  });

  it("discards an ordinary override provider result when Twin provenance appears before the write", async () => {
    mocks.lockOrdinary.mockRejectedValueOnce(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
      ),
    );

    const response = await applyOverride(request("override"), context);

    expect(response.status).toBe(409);
    expect(mocks.computeEmScore).toHaveBeenCalledTimes(1);
    expect(mocks.update).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });
});

describe("same-origin mutation boundary", () => {
  it.each([
    ["score", computeScore, "score"],
    ["additions", applyAdditions, "apply-additions"],
    ["override", applyOverride, "override"],
  ] as const)(
    "rejects cross-site %s before reading visit data",
    async (_label, handler, route) => {
      const response = await handler(request(route, false), context);

      expect(response.status).toBe(403);
      await expect(response.json()).resolves.toMatchObject({
        code: "CROSS_SITE_MUTATION",
      });
      expect(mocks.findUnique).not.toHaveBeenCalled();
      expect(mocks.computeEmScore).not.toHaveBeenCalled();
    },
  );
});

describe("durable Template Twin provider-backed E/M boundary", () => {
  const provenanceCases = [
    [
      "current Twin template",
      {
        noteTemplate: {
          templateKind: "template_twin_docx",
          templateTwinCompiledVersion: { id: "compiled-1" },
        },
      },
    ],
    [
      "fill with a mutated ordinary template",
      {
        noteTemplate: {
          templateKind: "structured",
          templateTwinCompiledVersion: null,
        },
        templateTwinFill: { id: "fill-1" },
      },
    ],
    [
      "fill with a detached template",
      { noteTemplate: null, templateTwinFill: { id: "fill-1" } },
    ],
    ["synthetic run", { templateTwinSyntheticQaRun: stagingRun }],
    [
      "pre-certification admission",
      { templateTwinSyntheticQaAdmission: { id: "voice-admission-1" } },
    ],
    [
      "detached provider execution",
      { templateTwinProviderExecutions: [{ id: "execution-1" }] },
    ],
    [
      "orphaned reserved synthetic patient",
      { patient: { externalId: "SYNTHETIC-QA-ONLY" } },
    ],
  ] as const;

  it.each(provenanceCases)(
    "rejects base score for %s before caller SOAP reaches the model/cache",
    async (_label, provenance) => {
      mocks.findUnique.mockResolvedValue(visitRow(null, provenance));
      mocks.requireRead.mockResolvedValue({
        isTemplateTwin: true,
        practiceId: "synthetic-practice-1",
      });

      const response = await computeScore(request("score"), context);

      expect(response.status).toBe(409);
      await expect(response.json()).resolves.toMatchObject({
        code: "TEMPLATE_TWIN_PROVIDER_BACKED_EM_UNAVAILABLE",
      });
      expect(mocks.computeEmScore).not.toHaveBeenCalled();
      expect(mocks.engineToUiScore).not.toHaveBeenCalled();
    },
  );

  it.each(provenanceCases)(
    "rejects apply-additions for %s before scoring or mutation",
    async (_label, provenance) => {
      mocks.findUnique.mockResolvedValue(visitRow(null, provenance));

      const response = await applyAdditions(
        request("apply-additions"),
        context,
      );

      expect(response.status).toBe(_label === "synthetic run" ? 404 : 409);
      await expect(response.json()).resolves.toMatchObject({
        code:
          _label === "synthetic run"
            ? "TEMPLATE_TWIN_STAGING_QA_MUTATION_UNAVAILABLE"
            : "TEMPLATE_TWIN_PROVIDER_BACKED_EM_UNAVAILABLE",
      });
      expect(mocks.mergeAdditions).not.toHaveBeenCalled();
      expect(mocks.computeEmScore).not.toHaveBeenCalled();
      expect(mocks.updateMany).not.toHaveBeenCalled();
      expect(mocks.transaction).not.toHaveBeenCalled();
      expect(mocks.invalidateTwin).not.toHaveBeenCalled();
      expect(mocks.logAudit).not.toHaveBeenCalled();
    },
  );

  it("retains the explicitly deterministic live Twin override", async () => {
    const liveTwin = visitRow(null, {
      noteTemplate: { templateKind: "template_twin_docx" },
      templateTwinFill: { id: "fill-1" },
    });
    mocks.findUnique.mockResolvedValue(liveTwin);
    mocks.pinTwinMutation.mockResolvedValue({ visitId: VISIT_ID });
    mocks.lockTwinMutation.mockResolvedValue(liveTwin);

    const response = await applyOverride(request("override"), context);

    expect(response.status).toBe(200);
    expect(mocks.computeEmScore).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ mdmCachedJudgement: null }),
    );
    expect(mocks.computeEmScore.mock.calls[0]?.[1]).not.toHaveProperty(
      "practiceId",
    );
    expect(mocks.update).toHaveBeenCalledTimes(1);
    expect(mocks.lockTwinMutation).toHaveBeenCalledTimes(1);
  });

  it("blocks live Twin override when physician or rollout authority changes at the final claim", async () => {
    const liveTwin = visitRow(null, {
      noteTemplate: { templateKind: "template_twin_docx" },
      templateTwinFill: { id: "fill-1" },
    });
    mocks.findUnique.mockResolvedValue(liveTwin);
    mocks.pinTwinMutation.mockResolvedValue({ visitId: VISIT_ID });
    mocks.lockTwinMutation.mockRejectedValue(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
      ),
    );

    const response = await applyOverride(request("override"), context);

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      code: "TEMPLATE_TWIN_AUTHORIZATION_CHANGED",
    });
    expect(mocks.update).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("blocks a live Twin override when SOAP state changes before the locked write", async () => {
    const liveTwin = visitRow(null, {
      noteTemplate: { templateKind: "template_twin_docx" },
      templateTwinFill: { id: "fill-1" },
    });
    mocks.findUnique.mockResolvedValue(liveTwin);
    mocks.pinTwinMutation.mockResolvedValue({ visitId: VISIT_ID });
    mocks.lockTwinMutation.mockResolvedValue({
      ...liveTwin,
      soapFinal: "A concurrently edited synthetic SOAP.",
    });

    const response = await applyOverride(request("override"), context);

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      code: "TEMPLATE_TWIN_MUTATION_CONFLICT",
    });
    expect(mocks.update).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("blocks a pre-certification admission from even deterministic generic override mutation", async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow(null, {
        templateTwinSyntheticQaAdmission: { id: "voice-admission-1" },
      }),
    );

    const response = await applyOverride(request("override"), context);

    expect(response.status).toBe(404);
    expect(mocks.computeEmScore).not.toHaveBeenCalled();
    expect(mocks.update).not.toHaveBeenCalled();
  });
});

describe("marked staging visits never enter model-backed E/M mutations", () => {
  beforeEach(() => {
    mocks.findUnique.mockResolvedValue(visitRow(stagingRun));
    mocks.pinStagingMutation.mockResolvedValue(stagingClaim);
  });

  it.each([
    ["additions", applyAdditions, "apply-additions"],
    ["override", applyOverride, "override"],
  ] as const)(
    "blocks active staging %s before provider, clinical, or audit calls",
    async (_label, handler, route) => {
      const response = await handler(request(route), context);

      expect(response.status).toBe(404);
      await expect(response.json()).resolves.toMatchObject({
        code: "TEMPLATE_TWIN_STAGING_QA_MUTATION_UNAVAILABLE",
      });
      expect(mocks.computeEmScore).not.toHaveBeenCalled();
      expect(mocks.update).not.toHaveBeenCalled();
      expect(mocks.updateMany).not.toHaveBeenCalled();
      expect(mocks.transaction).not.toHaveBeenCalled();
      expect(mocks.invalidateTwin).not.toHaveBeenCalled();
      expect(mocks.logAudit).not.toHaveBeenCalled();
    },
  );

  it.each([
    "TEMPLATE_TWIN_ROLLOUT_DISABLED",
    "TEMPLATE_TWIN_STAGING_QA_ROLLOUT_STALE",
    "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
  ])(
    "a rejected %s admission cannot call a provider or mutate",
    async (reasonCode) => {
      mocks.pinStagingMutation.mockRejectedValueOnce(new Error(reasonCode));

      const response = await applyAdditions(
        request("apply-additions"),
        context,
      );

      expect(response.status).toBe(404);
      expect(mocks.computeEmScore).not.toHaveBeenCalled();
      expect(mocks.updateMany).not.toHaveBeenCalled();
      expect(mocks.transaction).not.toHaveBeenCalled();
      expect(mocks.logAudit).not.toHaveBeenCalled();
    },
  );
});
