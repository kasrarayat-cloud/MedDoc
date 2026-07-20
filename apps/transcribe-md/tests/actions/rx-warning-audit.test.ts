// ============================================================================
// recordOverride — warningId + severity correlation guard
// ----------------------------------------------------------------------------
// fix/rx-override-gate-correlation: the override-count-inflation bypass let a
// visit owner mint fabricated 'critical' override rows (bogus warningIds) to
// satisfy the sign-gate's bare count. recordOverride now resolves the submitted
// warningId against the visit's persisted rxDrafts.warnings[] and rejects:
//   - a warningId that matches NO real warning (malformed / out-of-range), and
//   - a severity that doesn't match the warning's server-derived severity.
// Client-supplied warning identity is never trusted verbatim into the audit
// row. This pins that contract; the per-warning sign-gate coverage check is
// proven end-to-end in e2e scenario 25.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  visitFindUnique: vi.fn(),
  overrideCreate: vi.fn(),
  overrideFindUnique: vi.fn(),
  txVisitFindUnique: vi.fn(),
  transaction: vi.fn(),
  txQueryRaw: vi.fn(),
  getSession: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeVisit: { findUnique: mocks.visitFindUnique },
    rxWarningOverride: {
      create: mocks.overrideCreate,
      findUnique: mocks.overrideFindUnique,
    },
    $transaction: mocks.transaction,
  },
}));
vi.mock("@/lib/auth", () => ({ getSession: mocks.getSession }));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));
// NB: '@/lib/rx-warnings' is intentionally NOT mocked — the real, pure
// derivation must run so the validation is exercised for real.

import {
  recordOverride,
  type RecordOverrideInput,
} from "@/lib/rx-warning-audit";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";

const USER = "doc-1";
const VISIT = "vis-1";
const PATIENT = "pat-1";
const PRACTICE = "practice-1";
const UPDATED_AT = new Date("2026-07-20T00:00:00.000Z");

// rxDrafts.warnings[] fixture: index 0 = critical (id rx-warning-0),
// index 1 = minor → rail 'info' (id rx-warning-1).
const RX_DRAFTS = {
  warnings: [
    { severity: "critical", rx_drug: "warfarin", message: "INR risk" },
    { severity: "minor", rx_drug: "ibuprofen", message: "verify dose" },
  ],
};

const REASON =
  "Reviewed with the patient; benefit outweighs the risk, will monitor closely.";

function ordinaryVisit(overrides: Record<string, unknown> = {}) {
  return {
    id: VISIT,
    userId: USER,
    updatedAt: UPDATED_AT,
    patientId: PATIENT,
    patient: { id: PATIENT, practiceId: PRACTICE, externalId: null },
    noteTemplateId: null,
    noteTemplateVersion: null,
    noteTemplate: null,
    templateTwinFill: null,
    templateTwinSyntheticQaRun: null,
    templateTwinSyntheticQaAdmission: null,
    templateTwinProviderExecutions: [],
    rxDrafts: RX_DRAFTS,
    status: "READY",
    deletedAt: null,
    archivedAt: null,
    signedAt: null,
    ...overrides,
  };
}

function input(overrides: Partial<RecordOverrideInput>): RecordOverrideInput {
  return {
    visitId: VISIT,
    warningId: "rx-warning-0",
    rxLineNumber: 1,
    severity: "critical",
    headline: "warfarin",
    reason: REASON,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getSession.mockResolvedValue({ user: { id: USER } });
  mocks.visitFindUnique.mockResolvedValue(ordinaryVisit());
  mocks.overrideCreate.mockResolvedValue({ id: "ovr-1" });
  mocks.overrideFindUnique.mockResolvedValue({ id: "ovr-1" });
  mocks.txVisitFindUnique.mockResolvedValue(ordinaryVisit());
  mocks.txQueryRaw.mockImplementation(
    async (query: { strings?: readonly string[] }) => {
      const sql = query.strings?.join(" ") ?? "";
      if (sql.includes('FROM "practices" practice')) {
        return [{ id: PRACTICE, isActive: true }];
      }
      if (sql.includes('FROM "users" actor')) {
        return [{ id: USER }];
      }
      return [{ id: VISIT }];
    },
  );
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        $queryRaw: mocks.txQueryRaw,
        transcribeVisit: { findUnique: mocks.txVisitFindUnique },
        rxWarningOverride: {
          create: mocks.overrideCreate,
          findUnique: mocks.overrideFindUnique,
        },
      }),
  );
  mocks.logAudit.mockResolvedValue(undefined);
});

describe("recordOverride — correlation guard (fix/rx-override-gate-correlation)", () => {
  it("requires a current physician session even for the development preview sentinel", async () => {
    mocks.getSession.mockResolvedValueOnce(null);

    const result = await recordOverride(input({ visitId: "dev-preview" }));

    expect(result).toEqual({ ok: false, error: "Not signed in." });
    expect(mocks.visitFindUnique).not.toHaveBeenCalled();
    expect(mocks.overrideCreate).not.toHaveBeenCalled();
  });

  it("keeps the authenticated development preview free of warning writes", async () => {
    const result = await recordOverride(input({ visitId: "dev-preview" }));

    expect(result).toEqual({ ok: true, auditId: "dev-preview-audit" });
    expect(mocks.getSession).toHaveBeenCalledOnce();
    expect(mocks.visitFindUnique).not.toHaveBeenCalled();
    expect(mocks.overrideCreate).not.toHaveBeenCalled();
  });

  it("accepts a genuine override of the real critical warning", async () => {
    const result = await recordOverride(
      input({ warningId: "rx-warning-0", severity: "critical" }),
    );
    expect(result.ok).toBe(true);
    expect(mocks.overrideCreate).toHaveBeenCalledTimes(1);
    expect(mocks.overrideCreate.mock.calls[0][0].data.severity).toBe(
      "critical",
    );
    expect(mocks.overrideCreate.mock.calls[0][0].data.warningId).toBe(
      "rx-warning-0",
    );
    expect(mocks.txVisitFindUnique).toHaveBeenCalledWith({
      where: {
        id: VISIT,
        AND: [currentClinicalVisitActorWhere(USER)],
      },
      select: {
        status: true,
        deletedAt: true,
        archivedAt: true,
        signedAt: true,
        updatedAt: true,
        rxDrafts: true,
      },
    });
  });

  it("accepts a non-critical override when the severity matches (minor → info)", async () => {
    const result = await recordOverride(
      input({ warningId: "rx-warning-1", severity: "info" }),
    );
    expect(result.ok).toBe(true);
    expect(mocks.overrideCreate).toHaveBeenCalledTimes(1);
  });

  it("REJECTS a malformed/fabricated warningId (matches no real warning) and writes nothing", async () => {
    const result = await recordOverride(input({ warningId: "totally-bogus" }));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toMatch(/not on this visit/i);
    expect(mocks.overrideCreate).not.toHaveBeenCalled();
  });

  it("REJECTS an out-of-range positional warningId (no such warning) and writes nothing", async () => {
    const result = await recordOverride(
      input({ warningId: "rx-warning-9999" }),
    );
    expect(result.ok).toBe(false);
    expect(mocks.overrideCreate).not.toHaveBeenCalled();
  });

  it("REJECTS a severity that lies about a real warning (minor claimed critical) — kills inflation", async () => {
    // index 1 is a MINOR warning (rail 'info'); claiming 'critical' would mint a
    // gate-counting row for a non-critical warning. Must be rejected.
    const result = await recordOverride(
      input({ warningId: "rx-warning-1", severity: "critical" }),
    );
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toMatch(/severity/i);
    expect(mocks.overrideCreate).not.toHaveBeenCalled();
  });

  it("still rejects a non-owner before any warning resolution (defense in depth)", async () => {
    mocks.visitFindUnique.mockResolvedValueOnce(
      ordinaryVisit({ userId: "someone-else" }),
    );
    const result = await recordOverride(input({}));
    expect(result.ok).toBe(false);
    expect(mocks.overrideCreate).not.toHaveBeenCalled();
  });

  it.each([
    ["signed", { status: "SIGNED", signedAt: new Date(UPDATED_AT.getTime()) }],
    ["deleted", { deletedAt: new Date(UPDATED_AT.getTime()) }],
    ["archived", { archivedAt: new Date(UPDATED_AT.getTime()) }],
    ["not READY", { status: "PROCESSING" }],
  ])(
    "rejects an ordinary override when the final locked visit is %s",
    async (_label, finalState) => {
      mocks.txVisitFindUnique.mockResolvedValueOnce(ordinaryVisit(finalState));

      const result = await recordOverride(input({}));

      expect(result.ok).toBe(false);
      expect(mocks.overrideCreate).not.toHaveBeenCalled();
      expect(mocks.logAudit).not.toHaveBeenCalled();
    },
  );

  it("rejects an ordinary override when warnings change after projection", async () => {
    mocks.txVisitFindUnique.mockResolvedValueOnce(
      ordinaryVisit({
        rxDrafts: {
          warnings: [
            {
              severity: "critical",
              rx_drug: "warfarin",
              message: "Changed synthetic warning snapshot",
            },
          ],
        },
      }),
    );

    const result = await recordOverride(input({}));

    expect(result.ok).toBe(false);
    expect(mocks.overrideCreate).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });
});
