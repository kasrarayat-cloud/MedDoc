import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  compare: vi.fn(),
  transaction: vi.fn(),
  userFind: vi.fn(),
  visitCount: vi.fn(),
  visitFind: vi.fn(),
  sourceCount: vi.fn(),
  certificationCount: vi.fn(),
  waiverCount: vi.fn(),
  fieldIntentCount: vi.fn(),
  staticAssetCount: vi.fn(),
  staticAssetDecisionCount: vi.fn(),
  staticAssetReviewReceiptCount: vi.fn(),
  customExampleExecutionCount: vi.fn(),
  noteTemplateCount: vi.fn(),
  fillCount: vi.fn(),
  objectLedgerCount: vi.fn(),
  auditOutboxCount: vi.fn(),
  auditLogCount: vi.fn(),
  outboxCreate: vi.fn(),
  ownerLock: vi.fn(),
  accountDeletionCreate: vi.fn(),
  aiCallDeleteMany: vi.fn(),
  userDelete: vi.fn(),
  practiceDelete: vi.fn(),
  deleteAudio: vi.fn(),
  sendEmail: vi.fn(),
}));

vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("bcryptjs", () => ({ default: { compare: mocks.compare } }));
vi.mock("@/lib/rate-limit", () => ({
  RATE_LIMITS: { SETTINGS: {} },
  rateLimitOr429: vi.fn(() => null),
}));
vi.mock("@/lib/api-error", () => ({
  apiError: (error: string, status: number) =>
    Response.json({ error }, { status }),
  withApiHandler: (
    _name: string,
    handler: (req: Request) => Promise<Response>,
  ) => handler,
}));
vi.mock("@/lib/minio", () => ({
  deleteAudioObjectsByPrefix: mocks.deleteAudio,
}));
vi.mock("@/lib/email", () => ({
  sendAccountDeletedConfirmation: mocks.sendEmail,
}));
vi.mock("@/lib/constants", () => ({ MARKETING_URL: "https://example.test" }));
vi.mock("@/lib/log", () => ({
  log: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock("@/lib/audit", () => ({ logAudit: vi.fn() }));
vi.mock("@meddoc/ai", () => ({ redactPhi: (value: unknown) => String(value) }));
vi.mock("@meddoc/db", () => ({
  default: {
    user: { findUnique: mocks.userFind },
    transcribeVisit: {
      count: mocks.visitCount,
      findFirst: mocks.visitFind,
    },
    templateTwinSourceArtifact: { count: mocks.sourceCount },
    templateTwinCertification: { count: mocks.certificationCount },
    templateTwinFieldTestWaiver: { count: mocks.waiverCount },
    templateTwinFieldIntentDecision: { count: mocks.fieldIntentCount },
    templateTwinStaticAsset: { count: mocks.staticAssetCount },
    templateTwinStaticAssetDecision: {
      count: mocks.staticAssetDecisionCount,
    },
    templateTwinStaticAssetReviewReceipt: {
      count: mocks.staticAssetReviewReceiptCount,
    },
    templateTwinCustomExampleExecution: {
      count: mocks.customExampleExecutionCount,
    },
    noteTemplate: { count: mocks.noteTemplateCount },
    templateTwinFillManifest: { count: mocks.fillCount },
    templateTwinObjectLedger: { count: mocks.objectLedgerCount },
    templateTwinAuditOutbox: {
      count: mocks.auditOutboxCount,
      create: mocks.outboxCreate,
    },
    auditLog: { count: mocks.auditLogCount },
    $transaction: mocks.transaction,
  },
}));

import { POST } from "../route";

function request(): NextRequest {
  return new Request("https://app.example.test/api/settings/delete-account", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      password: "synthetic-password",
      confirmation: "DELETE",
    }),
  }) as unknown as NextRequest;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({ user: { id: "doctor-1" } });
  mocks.userFind.mockResolvedValue({
    id: "doctor-1",
    email: "doctor@example.test",
    name: "Synthetic Doctor",
    passwordHash: "synthetic-hash",
    practiceId: "practice-1",
  });
  mocks.compare.mockResolvedValue(true);
  mocks.visitCount.mockResolvedValue(0);
  mocks.visitFind.mockResolvedValue(null);
  mocks.sourceCount.mockResolvedValue(0);
  mocks.certificationCount.mockResolvedValue(0);
  mocks.waiverCount.mockResolvedValue(0);
  mocks.fieldIntentCount.mockResolvedValue(0);
  mocks.staticAssetCount.mockResolvedValue(0);
  mocks.staticAssetDecisionCount.mockResolvedValue(0);
  mocks.staticAssetReviewReceiptCount.mockResolvedValue(0);
  mocks.customExampleExecutionCount.mockResolvedValue(0);
  mocks.noteTemplateCount.mockResolvedValue(0);
  mocks.fillCount.mockResolvedValue(0);
  mocks.objectLedgerCount.mockResolvedValue(0);
  mocks.auditOutboxCount.mockResolvedValue(0);
  mocks.auditLogCount.mockResolvedValue(0);
  mocks.outboxCreate.mockResolvedValue({ id: "outbox-1" });
  mocks.ownerLock.mockResolvedValue([{ userId: "doctor-1" }]);
  mocks.accountDeletionCreate.mockResolvedValue({ id: "deletion-1" });
  mocks.aiCallDeleteMany.mockResolvedValue({ count: 0 });
  mocks.userDelete.mockResolvedValue({ id: "doctor-1" });
  mocks.practiceDelete.mockResolvedValue({ id: "practice-1" });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => unknown) =>
      callback({
        $queryRaw: mocks.ownerLock,
        accountDeletion: { create: mocks.accountDeletionCreate },
        aiCall: { deleteMany: mocks.aiCallDeleteMany },
        user: { delete: mocks.userDelete },
        practice: { delete: mocks.practiceDelete },
        templateTwinSourceArtifact: { count: mocks.sourceCount },
        templateTwinCertification: { count: mocks.certificationCount },
        templateTwinFieldTestWaiver: { count: mocks.waiverCount },
        templateTwinFieldIntentDecision: { count: mocks.fieldIntentCount },
        templateTwinStaticAsset: { count: mocks.staticAssetCount },
        templateTwinStaticAssetDecision: {
          count: mocks.staticAssetDecisionCount,
        },
        templateTwinStaticAssetReviewReceipt: {
          count: mocks.staticAssetReviewReceiptCount,
        },
        templateTwinCustomExampleExecution: {
          count: mocks.customExampleExecutionCount,
        },
        noteTemplate: { count: mocks.noteTemplateCount },
        templateTwinFillManifest: { count: mocks.fillCount },
        templateTwinObjectLedger: { count: mocks.objectLedgerCount },
        templateTwinAuditOutbox: {
          count: mocks.auditOutboxCount,
          create: mocks.outboxCreate,
        },
        auditLog: { count: mocks.auditLogCount },
      }),
  );
  mocks.deleteAudio.mockResolvedValue({ deleted: 0, failures: [] });
});

describe("delete account with retained Template Twin records", () => {
  it("returns a deterministic 409 before any transaction or object deletion", async () => {
    mocks.certificationCount.mockResolvedValue(1);

    const response = await POST(request(), { params: Promise.resolve({}) });
    await expect(response.json()).resolves.toEqual({
      error:
        "This account has retained Template Twin records. Deletion requires an approved retention or anonymization policy.",
      code: "TEMPLATE_TWIN_RETENTION_POLICY_REQUIRED",
    });
    expect(response.status).toBe(409);
    expect(mocks.transaction).not.toHaveBeenCalled();
    expect(mocks.deleteAudio).not.toHaveBeenCalled();
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(1);
  });

  it("preserves the existing deletion path when no Twin record exists", async () => {
    const response = await POST(request(), { params: Promise.resolve({}) });
    expect(response.status).toBe(200);
    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(mocks.transaction.mock.calls[0]?.[1]).toEqual({
      isolationLevel: "Serializable",
    });
    expect(mocks.ownerLock).toHaveBeenCalledTimes(1);
    expect(mocks.accountDeletionCreate).toHaveBeenCalledTimes(1);
    expect(mocks.userDelete).toHaveBeenCalledTimes(1);
    expect(mocks.practiceDelete).toHaveBeenCalledTimes(1);
    expect(mocks.deleteAudio).toHaveBeenCalledWith("doctor-1/");
  });

  it("rechecks after locking and blocks a retained row that races the initial check", async () => {
    mocks.sourceCount
      .mockResolvedValueOnce(0)
      .mockResolvedValueOnce(1);

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      code: "TEMPLATE_TWIN_RETENTION_POLICY_REQUIRED",
    });
    expect(mocks.transaction).toHaveBeenCalledTimes(1);
    expect(mocks.ownerLock).toHaveBeenCalledTimes(1);
    expect(mocks.accountDeletionCreate).not.toHaveBeenCalled();
    expect(mocks.userDelete).not.toHaveBeenCalled();
    expect(mocks.practiceDelete).not.toHaveBeenCalled();
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(1);
    expect(mocks.deleteAudio).not.toHaveBeenCalled();
  });

  it("maps a restrictive FK race to a deterministic 409 without object deletion", async () => {
    mocks.transaction.mockRejectedValueOnce({
      code: "P2003",
      message: "Foreign key constraint failed",
    });

    const response = await POST(request(), { params: Promise.resolve({}) });

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toMatchObject({
      code: "TEMPLATE_TWIN_RETENTION_POLICY_REQUIRED",
    });
    expect(mocks.outboxCreate).toHaveBeenCalledTimes(1);
    expect(mocks.deleteAudio).not.toHaveBeenCalled();
  });

  it.each([
    ["orphan object", "objectLedgerCount"],
    ["pending audit outbox", "auditOutboxCount"],
    ["delivered Twin audit", "auditLogCount"],
    ["field-intent decision", "fieldIntentCount"],
    ["practice static asset", "staticAssetCount"],
    ["static-asset decision", "staticAssetDecisionCount"],
    ["static-asset preview-review receipt", "staticAssetReviewReceiptCount"],
    ["custom-example execution", "customExampleExecutionCount"],
  ] as const)(
    "blocks deletion for a retained %s without entering the transaction",
    async (_label, counter) => {
      mocks[counter].mockResolvedValue(1);

      const response = await POST(request(), { params: Promise.resolve({}) });

      expect(response.status).toBe(409);
      expect(mocks.transaction).not.toHaveBeenCalled();
      expect(mocks.deleteAudio).not.toHaveBeenCalled();
    },
  );
});
