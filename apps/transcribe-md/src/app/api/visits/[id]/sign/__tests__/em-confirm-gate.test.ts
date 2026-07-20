// ============================================================================
// POST /api/visits/[id]/sign — E/M visible-confirm gate (prod smoke #311).
// ----------------------------------------------------------------------------
// All collaborators mocked (prisma / auth / audit / delivery stack); the
// gate logic + the em-pending-change coercion are REAL. Pins the hard
// requirement — a silent suggestion-caused E/M level change must be
// IMPOSSIBLE to sign through:
//   - an UNACKNOWLEDGED recorded change + no `acknowledgedEmChange` in the
//     body → 400 { ok:false, error, code:'EM_CHANGE_UNACKNOWLEDGED' }, NO
//     status write, EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE audit
//   - a STALE acknowledgement (echoing different codes than the record)
//     is refused the same way — content-identity, not a bare boolean
//   - a MATCHING acknowledgement signs; the record is MARKED acknowledged
//     (not cleared) in the same READY→SIGNED update, and the VISIT_SIGNED
//     audit metadata carries emChangeAcknowledged {from, to}
//   - no record / already-acknowledged record → no gate (sign as before)
//   - a malformed-but-present record fails CLOSED ('unknown' sentinel)
//   - already-SIGNED visits (re-deliver path) skip the gate
// ============================================================================

import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findUnique: vi.fn(),
  updateMany: vi.fn(),
  rxOverrideFindMany: vi.fn(),
  auth: vi.fn(),
  logAudit: vi.fn(),
  logWarn: vi.fn(),
  loadVisitExportData: vi.fn(),
  criticalWarningRefs: vi.fn(),
  logDelivery: vi.fn(),
  captureEditPattern: vi.fn(),
  computeDisplayedEmCode: vi.fn(),
  enqueueAudit: vi.fn(),
  authorizeDelivery: vi.fn(),
  requireRead: vi.fn(),
  transaction: vi.fn(),
  lockOrdinary: vi.fn(),
}));

// Minimal NextResponse stand-in — deterministic across vitest
// environments (the route + api-error only use NextResponse.json and
// response.headers.set).
vi.mock("next/server", () => {
  class FakeNextResponse {
    status: number;
    headers = new Map<string, string>();
    private body: unknown;
    constructor(body: unknown, init?: { status?: number }) {
      this.body = body;
      this.status = init?.status ?? 200;
    }
    async json() {
      return this.body;
    }
    static json(body: unknown, init?: { status?: number }) {
      return new FakeNextResponse(body, init);
    }
  }
  return { NextResponse: FakeNextResponse };
});

vi.mock("@meddoc/db", () => {
  const prisma = {
    transcribeVisit: {
      findUnique: mocks.findUnique,
      updateMany: mocks.updateMany,
    },
    rxWarningOverride: { findMany: mocks.rxOverrideFindMany },
    $transaction: mocks.transaction,
  };
  return { default: prisma, prisma };
});
vi.mock("@/lib/nextauth", () => ({ auth: mocks.auth }));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));
vi.mock("@/lib/log", () => ({
  log: { warn: mocks.logWarn, info: vi.fn(), error: vi.fn() },
}));
vi.mock("@meddoc/ai", () => ({
  redactPhi: (x: unknown) => x,
  delimiterSystemSuffix: () => "",
}));
vi.mock("@/lib/visit-export", () => ({ formatVisitDate: () => "2026-06-12" }));
vi.mock("@/lib/visit-export-server", () => ({
  loadVisitExportData: mocks.loadVisitExportData,
}));
vi.mock("@/lib/ehr-formatters", () => ({ formatForEhr: () => "formatted" }));
vi.mock("@/lib/pdf-generator", () => ({
  generateVisitPdf: vi.fn(async () => Buffer.from("pdf")),
}));
vi.mock("@/lib/email", () => ({ sendVisitPdfEmail: vi.fn() }));
vi.mock("@/lib/deliveries", () => ({ logDelivery: mocks.logDelivery }));
vi.mock("@/lib/edit-tracking", () => ({
  captureEditPattern: mocks.captureEditPattern,
}));
vi.mock("@/lib/rx-warnings", () => ({
  criticalWarningRefs: mocks.criticalWarningRefs,
}));
vi.mock("@/lib/em-coding/displayed-level", () => ({
  computeDisplayedEmCode: mocks.computeDisplayedEmCode,
}));
vi.mock("@/worker/automation-finalization", () => ({
  assessVisitAutomationProof: () => ({ ready: true, blockerCodes: [] }),
  lockAndAssertVisitAutomationProof: vi.fn(async () => ({})),
  VisitAutomationIncompleteError: class VisitAutomationIncompleteError extends Error {},
}));
vi.mock("@/worker/automation-locks", () => ({
  runVisitAutomationTransaction: async (input: {
    ordinaryBeforeVisitLock?: (tx: unknown) => Promise<void>;
    transaction: (tx: unknown, visit: unknown) => Promise<unknown>;
  }) => {
    const tx = { transcribeVisit: { updateMany: mocks.updateMany } };
    await input.ordinaryBeforeVisitLock?.(tx);
    return input.transaction(tx, {
      id: "visit-1",
      userId: "doc1",
      status: "READY",
      soapVersion: 1,
      soapFinal: "## Subjective\nElbow pain.\n\n## Plan\nNSAIDs.",
      reviewReason: null,
      deletedAt: null,
      archivedAt: null,
    });
  },
}));
vi.mock("@/lib/template-twin/audit-outbox", () => ({
  enqueueTemplateTwinAudit: mocks.enqueueAudit,
}));
vi.mock("@/lib/template-twin/delivery-authorization", () => ({
  TemplateTwinDeliveryAuthorizationError: class TemplateTwinDeliveryAuthorizationError extends Error {
    constructor(
      public readonly code: string,
      public readonly status: number,
    ) {
      super("Template Twin delivery authorization changed.");
    }
  },
  authorizeVisitDeliveryFinalClaim: mocks.authorizeDelivery,
}));
vi.mock("@/lib/template-twin/read-authority", () => ({
  TemplateTwinVisitReadAuthorityError: class TemplateTwinVisitReadAuthorityError extends Error {},
  requireTemplateTwinVisitReadAuthority: mocks.requireRead,
}));
vi.mock("@/lib/template-twin/visit-mutation-authority", () => ({
  TemplateTwinClinicalMutationAuthorizationError: class TemplateTwinClinicalMutationAuthorizationError extends Error {},
  lockAndAssertOrdinaryClinicalMutation: mocks.lockOrdinary,
}));

import type { NextRequest } from "next/server";
import { TranscribeVisitStatus } from "@prisma/client";
import { TemplateTwinClinicalMutationAuthorizationError } from "@/lib/template-twin/visit-mutation-authority";

import { POST } from "../route";

const DOCTOR = "doc1";
const VISIT = "visit-1";

const PENDING = {
  from: "99213",
  to: "99214",
  cause: "suggestion_adopted",
  at: "2026-06-12T10:00:00.000Z",
};

const BLOCK_ERROR =
  "Documentation level changed (99213 → 99214) by an AI-suggestion action — confirm the new level before signing.";

function visitRow(over: Record<string, unknown> = {}) {
  return {
    id: VISIT,
    userId: DOCTOR,
    patientId: "patient-1",
    noteTemplateId: null,
    updatedAt: new Date("2026-07-20T03:00:00.000Z"),
    status: TranscribeVisitStatus.READY,
    soapVersion: 1,
    soapFinal: "## Subjective\nElbow pain.\n\n## Plan\nNSAIDs.",
    rxDrafts: null,
    signedAt: null,
    deletedAt: null,
    archivedAt: null,
    patient: { externalId: null },
    automationManifest: null,
    templateTwinSyntheticQaRun: null,
    templateTwinSyntheticQaAdmission: null,
    templateTwinFill: null,
    templateTwinProviderExecutions: [],
    noteTemplate: null,
    user: { practiceId: "p1" },
    emPendingChange: null,
    ...over,
  };
}

function call(body: unknown) {
  const req = { json: async () => body } as unknown as NextRequest;
  return POST(req, { params: Promise.resolve({ id: VISIT }) });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({
    user: { id: DOCTOR, email: "doc@test.dev", practiceId: "p1" },
  });
  mocks.requireRead.mockResolvedValue({
    visitId: VISIT,
    isTemplateTwin: false,
    isSyntheticTemplateTwin: false,
    practiceId: null,
    templateTwinEnabled: null,
  });
  mocks.findUnique.mockResolvedValue(visitRow());
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) => callback({}),
  );
  mocks.lockOrdinary.mockResolvedValue(undefined);
  mocks.updateMany.mockResolvedValue({ count: 1 });
  mocks.rxOverrideFindMany.mockResolvedValue([]);
  mocks.criticalWarningRefs.mockReturnValue([]);
  mocks.computeDisplayedEmCode.mockResolvedValue("99214");
  mocks.authorizeDelivery.mockResolvedValue({ templateTwin: false });
  mocks.loadVisitExportData.mockResolvedValue({
    clinicianName: "Dr. Test",
    patientName: "P",
    signedAt: new Date("2026-06-12T11:00:00.000Z"),
    createdAt: new Date("2026-06-12T09:00:00.000Z"),
  });
});

describe("sign gate — unacknowledged E/M change blocks (fail-closed)", () => {
  it("REJECTS 400 { ok:false, error } when an unacknowledged change exists and no ack is in the request", async () => {
    mocks.findUnique.mockResolvedValue(visitRow({ emPendingChange: PENDING }));

    const res = await call({ destinations: [] });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.error).toBe(BLOCK_ERROR);
    expect(body.code).toBe("EM_CHANGE_UNACKNOWLEDGED");
    expect(body.pendingEmChange).toEqual({ from: "99213", to: "99214" });

    // Fail-closed: the READY→SIGNED transition never ran.
    expect(mocks.updateMany).not.toHaveBeenCalled();

    const blocked = mocks.logAudit.mock.calls
      .map((c) => c[0])
      .find((c) => c.action === "EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE");
    expect(blocked).toBeDefined();
    expect(blocked.success).toBe(false);
    expect(blocked.metadata).toEqual({
      from: "99213",
      to: "99214",
      cause: "suggestion_adopted",
    });
  });

  it("REJECTS a STALE acknowledgement — the echo must match the recorded {from, to} exactly", async () => {
    mocks.findUnique.mockResolvedValue(visitRow({ emPendingChange: PENDING }));

    const res = await call({
      destinations: [],
      acknowledgedEmChange: { from: "99212", to: "99214" },
    });
    expect(res.status).toBe(400);
    expect((await res.json()).code).toBe("EM_CHANGE_UNACKNOWLEDGED");
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });

  it("a malformed-but-present record fails CLOSED (unknown sentinel still demands confirmation)", async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({ emPendingChange: { bogus: true } }),
    );

    const res = await call({ destinations: [] });
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.ok).toBe(false);
    expect(body.pendingEmChange).toEqual({ from: "unknown", to: "unknown" });
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });
});

describe("sign gate — explicit acknowledgement signs + leaves the trail", () => {
  it("signs with a matching ack: record MARKED acknowledged in the same update, VISIT_SIGNED metadata carries emChangeAcknowledged", async () => {
    mocks.findUnique
      .mockResolvedValueOnce(visitRow({ emPendingChange: PENDING }))
      .mockResolvedValue({
        signedAt: new Date("2026-06-12T11:00:00.000Z"),
        status: TranscribeVisitStatus.SIGNED,
      });

    const res = await call({
      destinations: [],
      acknowledgedEmChange: { from: "99213", to: "99214" },
    });
    expect(res.status).toBe(200);

    expect(mocks.updateMany).toHaveBeenCalledTimes(1);
    const args = mocks.updateMany.mock.calls[0][0];
    expect(args.where).toEqual({
      id: VISIT,
      status: TranscribeVisitStatus.READY,
      soapVersion: 1,
      soapFinal: "## Subjective\nElbow pain.\n\n## Plan\nNSAIDs.",
    });
    expect(args.data.status).toBe(TranscribeVisitStatus.SIGNED);
    // MARKED, not cleared — the row keeps the forensic record.
    expect(args.data.emPendingChange).toEqual({
      ...PENDING,
      acknowledgedAt: expect.any(String),
    });

    const signed = mocks.enqueueAudit.mock.calls
      .map((c) => c[1])
      .find((c) => c.action === "VISIT_SIGNED");
    expect(signed).toBeDefined();
    expect(signed.metadata.emChangeAcknowledged).toEqual({
      from: "99213",
      to: "99214",
    });
    // No block audit on the success path.
    expect(
      mocks.logAudit.mock.calls
        .map((c) => c[0])
        .find((c) => c.action === "EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE"),
    ).toBeUndefined();
  });

  it("no recorded change → signs without an ack, never touches emPendingChange, no acknowledgement metadata", async () => {
    const res = await call({ destinations: [] });
    expect(res.status).toBe(200);

    const args = mocks.updateMany.mock.calls[0][0];
    expect("emPendingChange" in args.data).toBe(false);

    const signed = mocks.enqueueAudit.mock.calls
      .map((c) => c[1])
      .find((c) => c.action === "VISIT_SIGNED");
    expect(signed).toBeDefined();
    expect("emChangeAcknowledged" in signed.metadata).toBe(false);
  });

  it("an already-ACKNOWLEDGED record does not gate (it was confirmed when recorded sign happened)", async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({
        emPendingChange: {
          ...PENDING,
          acknowledgedAt: "2026-06-12T10:30:00.000Z",
        },
      }),
    );

    const res = await call({ destinations: [] });
    expect(res.status).toBe(200);
    expect("emPendingChange" in mocks.updateMany.mock.calls[0][0].data).toBe(
      false,
    );
  });

  it("already-SIGNED visit (re-deliver path) skips the gate even with an unacknowledged record", async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({
        status: TranscribeVisitStatus.SIGNED,
        signedAt: new Date("2026-06-11T11:00:00.000Z"),
        emPendingChange: PENDING,
      }),
    );

    const res = await call({ destinations: [] });
    expect(res.status).toBe(200);
    // Deliver-only: no READY→SIGNED transition attempted.
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });
});

describe("sign — E/M parity freeze (#315 obs#2): the confirmed displayed level is persisted as the authoritative billing code", () => {
  const EM_BLOB = {
    em: {
      code: "99213",
      description: "Established, low",
      reasoning: { problems: [], data: "", risk: "" },
      evidence_quote: "",
    },
  };

  it("freezes cptCodes.em.signedCode = computeDisplayedEmCode(signedSoap) in the SAME READY→SIGNED update; raw em.code preserved", async () => {
    mocks.computeDisplayedEmCode.mockResolvedValue("99214");
    mocks.findUnique
      .mockResolvedValueOnce(
        visitRow({
          emPendingChange: PENDING,
          cptCodes: EM_BLOB,
          icdCodes: null,
        }),
      )
      .mockResolvedValue({
        signedAt: new Date(),
        status: TranscribeVisitStatus.SIGNED,
      });

    const res = await call({
      destinations: [],
      acknowledgedEmChange: { from: "99213", to: "99214" },
    });
    expect(res.status).toBe(200);

    const data = mocks.updateMany.mock.calls[0][0].data;
    // signedCode === the acknowledged TO-level → printed === confirmed.
    expect(data.cptCodes.em.signedCode).toBe("99214");
    expect(data.cptCodes.em.signedCode).toBe(PENDING.to);
    // The raw L7b suggestion is preserved for provenance.
    expect(data.cptCodes.em.code).toBe("99213");
    // It rode the SAME atomic transition that flips status → SIGNED.
    expect(data.status).toBe(TranscribeVisitStatus.SIGNED);
    expect(mocks.lockOrdinary).toHaveBeenCalledTimes(3);
  });

  it("blocks an ordinary-to-Twin transition immediately before the sign-time E/M provider", async () => {
    mocks.findUnique.mockResolvedValueOnce(visitRow({ cptCodes: EM_BLOB }));
    mocks.lockOrdinary.mockRejectedValueOnce(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
      ),
    );

    const res = await call({ destinations: [] });

    expect(res.status).toBe(409);
    expect((await res.json()).code).toBe("TEMPLATE_TWIN_MUTATION_CONFLICT");
    expect(mocks.computeDisplayedEmCode).not.toHaveBeenCalled();
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });

  it("discards the E/M provider result when provenance changes after return", async () => {
    mocks.findUnique.mockResolvedValueOnce(visitRow({ cptCodes: EM_BLOB }));
    mocks.lockOrdinary
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(
        new TemplateTwinClinicalMutationAuthorizationError(
          "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
        ),
      );

    const res = await call({ destinations: [] });

    expect(res.status).toBe(409);
    expect(mocks.computeDisplayedEmCode).toHaveBeenCalledTimes(1);
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });

  it("re-fences the exact ordinary snapshot inside the final sign transaction", async () => {
    const admitted = visitRow({ cptCodes: EM_BLOB });
    mocks.findUnique.mockResolvedValueOnce(admitted);
    mocks.lockOrdinary
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(
        new TemplateTwinClinicalMutationAuthorizationError(
          "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
        ),
      );

    const res = await call({ destinations: [] });

    expect(res.status).toBe(409);
    expect(mocks.computeDisplayedEmCode).toHaveBeenCalledTimes(1);
    expect(mocks.lockOrdinary).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({
        visitId: VISIT,
        actorUserId: DOCTOR,
        admittedVisitUpdatedAt: admitted.updatedAt,
        admittedPatientId: admitted.patientId,
        admittedNoteTemplateId: admitted.noteTemplateId,
      }),
    );
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });

  it("an OVERRIDDEN visit freezes the override level (computeDisplayedEmCode returns override ?? engine)", async () => {
    mocks.computeDisplayedEmCode.mockResolvedValue("99215");
    mocks.findUnique
      .mockResolvedValueOnce(
        visitRow({
          cptCodes: {
            em: {
              ...EM_BLOB.em,
              override: { code: "99215", overriddenAt: "x" },
            },
          },
        }),
      )
      .mockResolvedValue({
        signedAt: new Date(),
        status: TranscribeVisitStatus.SIGNED,
      });

    const res = await call({ destinations: [] });
    expect(res.status).toBe(200);
    expect(mocks.updateMany.mock.calls[0][0].data.cptCodes.em.signedCode).toBe(
      "99215",
    );
  });

  it("FAIL-SAFE: a scoring error never blocks signing — no cptCodes write, status still flips", async () => {
    mocks.computeDisplayedEmCode.mockRejectedValue(new Error("judge down"));
    mocks.findUnique
      .mockResolvedValueOnce(visitRow({ cptCodes: EM_BLOB }))
      .mockResolvedValue({
        signedAt: new Date(),
        status: TranscribeVisitStatus.SIGNED,
      });

    const res = await call({ destinations: [] });
    expect(res.status).toBe(200);
    const data = mocks.updateMany.mock.calls[0][0].data;
    expect(data.status).toBe(TranscribeVisitStatus.SIGNED);
    expect("cptCodes" in data).toBe(false);
  });

  it("a visit with NO em block does not compute or write a signed code (backward compatible)", async () => {
    mocks.findUnique
      .mockResolvedValueOnce(visitRow({ cptCodes: { procedures: [] } }))
      .mockResolvedValue({
        signedAt: new Date(),
        status: TranscribeVisitStatus.SIGNED,
      });

    const res = await call({ destinations: [] });
    expect(res.status).toBe(200);
    expect(mocks.computeDisplayedEmCode).not.toHaveBeenCalled();
    expect("cptCodes" in mocks.updateMany.mock.calls[0][0].data).toBe(false);
  });
});
