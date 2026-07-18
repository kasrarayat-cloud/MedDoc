import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  context: vi.fn(),
  transaction: vi.fn(),
  enqueueCaptured: vi.fn(),
  enqueueTerminal: vi.fn(),
}));

vi.mock("@meddoc/ai", () => ({
  getTemplateTwinSyntheticQaProviderContext: mocks.context,
}));
vi.mock("../automation-locks", () => ({
  runVisitAutomationTransaction: mocks.transaction,
}));
vi.mock("../worker-audit", () => ({
  enqueuePreparedWorkerAuditInTransaction: mocks.enqueueCaptured,
}));
vi.mock("@/lib/template-twin/audit-outbox", () => ({
  enqueueIdempotentTemplateTwinAudit: mocks.enqueueTerminal,
}));

import {
  recordVisitAutomationLayerFailure,
  recordVisitAutomationLayerSuccess,
  type VisitAutomationAttempt,
} from "../automation-manifest";
import type { VisitAutomationLayerId } from "../automation-policy";

const ATTEMPT: VisitAutomationAttempt = {
  manifestId: "manifest-synthetic-1",
  manifestVersion: 2,
  soapVersion: 4,
  soapSha256: "a".repeat(64),
  sourceSha256: "b".repeat(64),
  policy: [
    {
      layerId: "icd_coding" as const,
      layerVersion: "l7a-v1",
      requirement: "REQUIRED" as const,
      initialStatus: "PENDING" as const,
    },
  ],
};

function databaseHarness() {
  let committedTransactions = 0;
  const tx = {
    $queryRaw: vi.fn(async (query: { strings?: readonly string[] }) => {
      const sql = query.strings?.join("?") ?? "";
      if (sql.includes("visit_automation_manifests")) {
        return [
          {
            id: ATTEMPT.manifestId,
            practiceId: "practice-synthetic-1",
            visitId: "visit-synthetic-1",
            stagingAdmissionId: null,
            stagingRunId: null,
            soapVersion: ATTEMPT.soapVersion,
            soapSha256: ATTEMPT.soapSha256,
            sourceVersion: "soap-final-v1",
            sourceSha256: ATTEMPT.sourceSha256,
            policyVersion: "visit-automation-policy-v1",
            manifestVersion: ATTEMPT.manifestVersion,
            status: "RUNNING",
            pinnedGlobalRolloutGeneration: null,
            pinnedPracticeRolloutGeneration: null,
          },
        ];
      }
      if (sql.includes("visit_automation_provider_executions")) {
        return [
          {
            id: "execution-synthetic-1",
            automationLayerId: "layer-synthetic-1",
            manifestId: ATTEMPT.manifestId,
            practiceId: "practice-synthetic-1",
            visitId: "visit-synthetic-1",
            status: "SUCCEEDED",
          },
        ];
      }
      return [
        {
          id: "layer-synthetic-1",
          status: "RUNNING",
          outputSha256: null,
          attemptCount: 1,
        },
      ];
    }),
    transcribeVisit: { update: vi.fn().mockResolvedValue({}) },
    visitAutomationLayer: { update: vi.fn().mockResolvedValue({}) },
  };
  mocks.transaction.mockImplementation(async (input) => {
    const value = await input.transaction(tx, {
      id: "visit-synthetic-1",
      userId: "doctor-synthetic-1",
      status: "AUTOMATING",
      soapVersion: ATTEMPT.soapVersion,
      soapFinal: "Synthetic SOAP",
      reviewReason: null,
      deletedAt: null,
      archivedAt: null,
    });
    committedTransactions += 1;
    return value;
  });
  return { tx, committedTransactions: () => committedTransactions };
}

describe("automation layer result/state/audit atomicity", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.context.mockReturnValue(null);
    mocks.enqueueCaptured.mockResolvedValue(undefined);
    mocks.enqueueTerminal.mockResolvedValue("CREATED");
    ATTEMPT.policy[0]!.layerId = "icd_coding";
    ATTEMPT.policy[0]!.requirement = "REQUIRED";
  });

  it("projects clinical state, terminal layer state, and audits in one transaction", async () => {
    const db = databaseHarness();
    await recordVisitAutomationLayerSuccess({
      attempt: ATTEMPT,
      visitId: "visit-synthetic-1",
      userId: "doctor-synthetic-1",
      practiceId: "practice-synthetic-1",
      layerId: "icd_coding",
      output: { codes: [{ code: "Z00.00" }] },
      providerExecutionId: "execution-synthetic-1",
      effects: {
        visitMutations: [{ data: { icdCodes: [{ code: "Z00.00" }] } }],
        audits: [
          {
            eventKey: "synthetic-layer-audit-1",
            practiceId: "practice-synthetic-1",
            actorId: "doctor-synthetic-1",
            action: "CODING_COACH_REJECTED_INVALID_ICD",
            targetId: "visit-synthetic-1",
            targetType: "TranscribeVisit",
          },
        ],
      },
    });

    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(db.tx.transcribeVisit.update).toHaveBeenCalledTimes(1);
    expect(db.tx.visitAutomationLayer.update).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ status: "SUCCEEDED" }),
      }),
    );
    expect(mocks.enqueueCaptured).toHaveBeenCalledTimes(1);
    expect(mocks.enqueueTerminal).toHaveBeenCalledTimes(1);
    expect(db.committedTransactions()).toBe(1);
  });

  it.each<{
    layerId: VisitAutomationLayerId;
    data: Record<string, unknown>;
  }>([
    { layerId: "icd_coding", data: { icdCodes: [] } },
    { layerId: "cpt_coding", data: { cptCodes: [] } },
    { layerId: "rx_drafting", data: { rxDrafts: [] } },
    { layerId: "referrals", data: { referrals: [] } },
    {
      layerId: "patient_summary",
      data: { patientSummary: "Synthetic summary." },
    },
  ])(
    "commits the $layerId result, terminal state, and audit through one transaction",
    async ({ layerId, data }) => {
      const db = databaseHarness();
      ATTEMPT.policy[0]!.layerId = layerId;
      await recordVisitAutomationLayerSuccess({
        attempt: ATTEMPT,
        visitId: "visit-synthetic-1",
        userId: "doctor-synthetic-1",
        practiceId: "practice-synthetic-1",
        layerId,
        output: { synthetic: true },
        providerExecutionId: "execution-synthetic-1",
        effects: { visitMutations: [{ data }], audits: [] },
      });

      expect(mocks.transaction).toHaveBeenCalledTimes(1);
      expect(db.tx.transcribeVisit.update).toHaveBeenCalledWith(
        expect.objectContaining({ data }),
      );
      expect(db.tx.visitAutomationLayer.update).toHaveBeenCalledWith(
        expect.objectContaining({
          data: expect.objectContaining({ status: "SUCCEEDED" }),
        }),
      );
      expect(mocks.enqueueTerminal).toHaveBeenCalledTimes(1);
      expect(db.committedTransactions()).toBe(1);
    },
  );

  it("does not complete the transaction when its audit outbox insert fails", async () => {
    const db = databaseHarness();
    mocks.enqueueTerminal.mockRejectedValue(
      new Error("synthetic audit outbox unavailable"),
    );
    await expect(
      recordVisitAutomationLayerSuccess({
        attempt: ATTEMPT,
        visitId: "visit-synthetic-1",
        userId: "doctor-synthetic-1",
        practiceId: "practice-synthetic-1",
        layerId: "icd_coding",
        output: { codes: [{ code: "Z00.00" }] },
        providerExecutionId: "execution-synthetic-1",
        effects: { visitMutations: [], audits: [] },
      }),
    ).rejects.toThrow(/audit outbox unavailable/u);
    expect(db.committedTransactions()).toBe(0);
  });

  it("cannot emit a success audit when the clinical result write fails", async () => {
    const db = databaseHarness();
    db.tx.transcribeVisit.update.mockRejectedValue(
      new Error("synthetic clinical result constraint failure"),
    );

    await expect(
      recordVisitAutomationLayerSuccess({
        attempt: ATTEMPT,
        visitId: "visit-synthetic-1",
        userId: "doctor-synthetic-1",
        practiceId: "practice-synthetic-1",
        layerId: "icd_coding",
        output: { codes: [] },
        providerExecutionId: "execution-synthetic-1",
        effects: {
          visitMutations: [{ data: { icdCodes: [] } }],
          audits: [],
        },
      }),
    ).rejects.toThrow(/clinical result constraint/u);

    expect(db.tx.visitAutomationLayer.update).not.toHaveBeenCalled();
    expect(mocks.enqueueTerminal).not.toHaveBeenCalled();
    expect(db.committedTransactions()).toBe(0);
  });

  it("records an optional ordinary-layer failure and its audit atomically", async () => {
    const db = databaseHarness();
    ATTEMPT.policy[0]!.requirement = "OPTIONAL";
    await recordVisitAutomationLayerFailure({
      attempt: ATTEMPT,
      visitId: "visit-synthetic-1",
      userId: "doctor-synthetic-1",
      practiceId: "practice-synthetic-1",
      layerId: "icd_coding",
      error: new Error("synthetic provider unavailable"),
    });
    expect(db.tx.visitAutomationLayer.update).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ status: "FAILED" }),
      }),
    );
    expect(mocks.enqueueTerminal).toHaveBeenCalledWith(
      db.tx,
      expect.objectContaining({
        action: "VISIT_AUTOMATION_INCOMPLETE",
        metadata: expect.objectContaining({ requirement: "OPTIONAL" }),
      }),
    );
    expect(db.committedTransactions()).toBe(1);
  });
});
