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
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));

import { TranscribeVisitStatus } from "@prisma/client";

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
    status: TranscribeVisitStatus.READY,
    deletedAt: null,
    archivedAt: null,
    signedAt: null,
    soapDraft: "## Subjective\nSynthetic evidence only.",
    soapFinal: "## Subjective\nSynthetic evidence only.",
    soapVersion: 3,
    audioDurationSec: 60,
    dictationDurationSec: null,
    inputMode: "text_note",
    icdCodes: [],
    cptCodes: {},
    rxDrafts: [],
    templateTwinSyntheticQaRun,
    noteTemplate: { templateKind: "structured" },
    templateTwinFill: null,
    templateTwinSyntheticQaAdmission: null,
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
  mocks.pinStagingMutation.mockResolvedValue(null);
  mocks.isOwnedStagingVisit.mockResolvedValue(false);
  mocks.updateMany.mockResolvedValue({ count: 1 });
  mocks.update.mockResolvedValue({ id: VISIT_ID });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({ transcribeVisit: { updateMany: mocks.updateMany } }),
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
    expect(mocks.pinStagingMutation).toHaveBeenCalledWith({
      visitId: VISIT_ID,
      userId: DOCTOR_ID,
      run: null,
    });
    expect(mocks.computeEmScore).toHaveBeenCalledTimes(1);
    expect(mocks.updateMany).toHaveBeenCalledTimes(1);
    expect(mocks.invalidateTwin).toHaveBeenCalledTimes(1);
    expect(mocks.logAudit).toHaveBeenCalledWith(
      expect.objectContaining({ action: "EM_BUMP_APPLIED" }),
    );
  });

  it("preserves the existing override mutation path", async () => {
    const response = await applyOverride(request("override"), context);

    expect(response.status).toBe(200);
    expect(mocks.pinStagingMutation).toHaveBeenCalledWith({
      visitId: VISIT_ID,
      userId: DOCTOR_ID,
      run: null,
    });
    expect(mocks.computeEmScore).toHaveBeenCalledTimes(1);
    expect(mocks.update).toHaveBeenCalledTimes(1);
    expect(mocks.logAudit).toHaveBeenCalledWith(
      expect.objectContaining({ action: "EM_OVERRIDE_APPLIED" }),
    );
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
      { noteTemplate: { templateKind: "template_twin_docx" } },
    ],
    [
      "fill with a mutated ordinary template",
      {
        noteTemplate: { templateKind: "structured" },
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
  ] as const;

  it.each(provenanceCases)(
    "rejects base score for %s before caller SOAP reaches the model/cache",
    async (_label, provenance) => {
      mocks.findUnique.mockResolvedValue(visitRow(null, provenance));

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

      expect(response.status).toBe(409);
      await expect(response.json()).resolves.toMatchObject({
        code: "TEMPLATE_TWIN_PROVIDER_BACKED_EM_UNAVAILABLE",
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
    mocks.findUnique.mockResolvedValue(
      visitRow(null, {
        noteTemplate: { templateKind: "template_twin_docx" },
        templateTwinFill: { id: "fill-1" },
      }),
    );

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
