// ============================================================================
// persistFailedState — FIND-P1-014 hardening
// ----------------------------------------------------------------------------
// Pins the post-fix behavior:
//   - Update succeeds → returns { persistOk: true, persistErr: null }
//   - Update rejects  → returns { persistOk: false, persistErr: <err> }
//                       AND logs structured + captures the SECONDARY
//                       failure to Sentry (the original failure was
//                       already in Sentry before this is called).
//
// Pre-fix behavior was `.update().catch(() => console.error(...))` which
// silently swallowed write failures. Combined with the worker's outer
// `throw err`, a DB outage at the wrong moment left visits in their
// non-terminal status (POLISHING / AUTOMATING / etc.) until the stuck-
// visit watchdog rescued them 15 minutes later.
//
// Policy (Kasra, 2026-05-14): the caller re-throws persistErr to BullMQ
// so the job is marked failed with the persist context. Silent
// stuck-in-non-terminal is the worse failure mode.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  update: vi.fn(),
  enqueueAudit: vi.fn(),
  markManifestFailed: vi.fn(),
  captureWorkerException: vi.fn(),
  logError: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: { transcribeVisit: { update: mocks.update } },
}));

vi.mock("@meddoc/ai", () => ({
  // Identity redactor for tests — we don't care about PHI scrubbing
  // shape here; that's covered by worker-redact-phi.test.ts.
  redactPhi: (s: unknown) => (typeof s === "string" ? s : String(s ?? "")),
  getTemplateTwinSyntheticQaProviderContext: () => null,
}));

vi.mock("@/worker/automation-locks", () => ({
  runVisitAutomationTransaction: async (input: {
    transaction: (tx: unknown) => Promise<unknown>;
  }) =>
    input.transaction({
      transcribeVisit: { update: mocks.update },
    }),
}));

vi.mock("@/worker/automation-manifest", () => ({
  markVisitAutomationManifestFailed: mocks.markManifestFailed,
}));

vi.mock("@/lib/template-twin/audit-outbox", () => ({
  enqueueTemplateTwinAudit: mocks.enqueueAudit,
}));

vi.mock("@/lib/log", () => ({
  log: {
    info: vi.fn(),
    warn: vi.fn(),
    error: mocks.logError,
  },
}));

// The worker-sentry module exposes captureWorkerException; we mock it
// to assert the helper captures the SECONDARY (persist) failure.
vi.mock("../../src/worker-sentry", () => ({
  captureWorkerException: mocks.captureWorkerException,
}));

import { persistFailedState } from "@/worker/persist-failed";

const VISIT_ID = "vis-1";
const USER_ID = "u1";
const PRACTICE_ID = "p1";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.markManifestFailed.mockResolvedValue(null);
  mocks.enqueueAudit.mockResolvedValue(undefined);
});

describe("persistFailedState — happy path", () => {
  it("returns persistOk=true when the update succeeds", async () => {
    mocks.update.mockResolvedValue({ id: VISIT_ID });

    const result = await persistFailedState({
      visitId: VISIT_ID,
      category: "transient",
      layer: "L1",
      originalErr: new Error("upstream timeout"),
      reviewReason: "Transcription failed during transcription.",
      userId: USER_ID,
      practiceId: PRACTICE_ID,
    });

    expect(result).toEqual({ persistOk: true, persistErr: null });
    expect(mocks.update).toHaveBeenCalledTimes(1);

    const updateArgs = mocks.update.mock.calls[0][0];
    expect(updateArgs.where).toEqual({ id: VISIT_ID });
    expect(updateArgs.data.status).toBe("FAILED");
    expect(updateArgs.data.needsReview).toBe(true);
    expect(updateArgs.data.reviewReason).toBe(
      "Transcription failed during transcription.",
    );
    expect(updateArgs.data.failureCategory).toBe("transient");
    expect(updateArgs.data.processingFinishedAt).toBeInstanceOf(Date);

    // Happy path → no secondary Sentry event, no error-level log.
    expect(mocks.captureWorkerException).not.toHaveBeenCalled();
    expect(mocks.logError).not.toHaveBeenCalled();
  });

  it("does NOT throw on success (return-value contract)", async () => {
    mocks.update.mockResolvedValue({ id: VISIT_ID });

    await expect(
      persistFailedState({
        visitId: VISIT_ID,
        category: "permanent",
        layer: "L4",
        originalErr: new Error("zod validation failed"),
        reviewReason: "SOAP generation failed.",
        userId: USER_ID,
        practiceId: PRACTICE_ID,
      }),
    ).resolves.toMatchObject({ persistOk: true });
  });
});

describe("persistFailedState — persist failure (FIND-P1-014)", () => {
  it("returns persistOk=false + persistErr when update rejects", async () => {
    const writeErr = new Error("postgres connection refused");
    mocks.update.mockRejectedValue(writeErr);

    const originalErr = new Error("L4 model output malformed");
    const result = await persistFailedState({
      visitId: VISIT_ID,
      category: "permanent",
      layer: "L4",
      originalErr,
      reviewReason: "SOAP generation failed.",
      userId: USER_ID,
      practiceId: PRACTICE_ID,
    });

    expect(result.persistOk).toBe(false);
    expect(result.persistErr).toBe(writeErr);
  });

  it("does NOT throw on persist failure — caller decides via persistOk", async () => {
    mocks.update.mockRejectedValue(new Error("db down"));

    // The contract: this function never throws. The caller (worker
    // outer catch) inspects persistOk and re-throws persistErr to
    // BullMQ as appropriate. Throwing here would bypass the admin
    // notify call that runs between this and the final throw.
    await expect(
      persistFailedState({
        visitId: VISIT_ID,
        category: "transient",
        layer: "L1",
        originalErr: new Error("upstream 503"),
        reviewReason: "Transcription failed.",
        userId: USER_ID,
        practiceId: PRACTICE_ID,
      }),
    ).resolves.toMatchObject({ persistOk: false });
  });

  it("logs the double-failure with both error messages", async () => {
    const writeErr = new Error("postgres connection refused");
    mocks.update.mockRejectedValue(writeErr);

    const originalErr = new Error("L4 model output malformed");
    await persistFailedState({
      visitId: VISIT_ID,
      category: "permanent",
      layer: "L4",
      originalErr,
      reviewReason: "SOAP generation failed.",
      userId: USER_ID,
      practiceId: PRACTICE_ID,
    });

    expect(mocks.logError).toHaveBeenCalledTimes(1);
    const [scope, msg, ctx] = mocks.logError.mock.calls[0];
    expect(scope).toBe("transcribe-md-worker");
    expect(msg).toBe("FAILED-state persist also failed");
    expect(ctx).toMatchObject({
      visitId: VISIT_ID,
      layer: "L4",
      category: "permanent",
      originalErrMessage: "L4 model output malformed",
      persistErrMessage: "postgres connection refused",
    });
  });

  it("captures the SECONDARY (persist) failure to Sentry with finalize tag", async () => {
    const writeErr = new Error("postgres connection refused");
    mocks.update.mockRejectedValue(writeErr);

    await persistFailedState({
      visitId: VISIT_ID,
      category: "transient",
      layer: "L1",
      originalErr: new Error("upstream 503"),
      reviewReason: "Transcription failed.",
      userId: USER_ID,
      practiceId: PRACTICE_ID,
    });

    expect(mocks.captureWorkerException).toHaveBeenCalledTimes(1);
    const [capturedErr, tags] = mocks.captureWorkerException.mock.calls[0];
    expect(capturedErr).toBe(writeErr);
    // 'finalize' tag distinguishes the secondary (persist) Sentry
    // event from the primary error which the worker already captured
    // with the pipeline layer tag.
    expect(tags).toEqual({
      visitId: VISIT_ID,
      layer: "finalize",
      userId: USER_ID,
      practiceId: PRACTICE_ID,
    });
  });

  it("handles non-Error throws (string, undefined) without crashing", async () => {
    mocks.update.mockRejectedValue("postgres unavailable");

    const result = await persistFailedState({
      visitId: VISIT_ID,
      category: "transient",
      layer: "L1",
      originalErr: undefined,
      reviewReason: "Transcription failed.",
      userId: USER_ID,
      practiceId: "practice-synthetic.test",
    });

    expect(result.persistOk).toBe(false);
    expect(result.persistErr).toBe("postgres unavailable");
    expect(mocks.logError).toHaveBeenCalledTimes(1);
    const ctx = mocks.logError.mock.calls[0][2];
    expect(ctx.persistErrMessage).toBe("postgres unavailable");
    expect(ctx.originalErrMessage).toBe("");
  });
});
