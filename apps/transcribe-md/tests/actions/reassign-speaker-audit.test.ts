// ============================================================================
// reassignSpeakerAction — SPEAKER_ROLE_REASSIGNED audit-row guard (FIND-P1-003)
// ----------------------------------------------------------------------------
// Comprehensive-audit FIND-P1-003 (2026-05-14): the Layer-2 manual override
// at apps/transcribe-md/src/actions/soap.ts:209 mutates `speakerMap` —
// which affects the SOAP note's history-vs-plan segmentation downstream
// — without emitting a HIPAA §164.312(b) audit row. The fix adds a new
// `SPEAKER_ROLE_REASSIGNED` enum value + fire-and-forget logAudit call.
// This test pins the post-fix shape:
//
//   - Successful reassign writes ONE audit row with action=
//     'SPEAKER_ROLE_REASSIGNED' + targetType='TranscribeVisit' +
//     targetId=<visit id> + metadata { source, speakerId, previousRole,
//     newRole }
//   - PHI excluded — speakerId is an internal numeric label, role is
//     enum, no patient name / utterance content
//   - Fire-and-forget — logAudit failure does NOT break the user-facing
//     reassign flow
//   - Early-return branches (visit-not-found, foreign-user, trashed,
//     signed, invalid role) do NOT emit
// ============================================================================

import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  visitFindUnique: vi.fn(),
  visitUpdateMany: vi.fn(),
  transaction: vi.fn(),
  txQueryRaw: vi.fn(),
  requireSession: vi.fn(),
  logAudit: vi.fn(),
  revalidatePath: vi.fn(),
  stagingRunFindFirst: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeVisit: {
      findUnique: mocks.visitFindUnique,
      updateMany: mocks.visitUpdateMany,
    },
    templateTwinSyntheticQaRun: {
      findFirst: mocks.stagingRunFindFirst,
    },
    $transaction: mocks.transaction,
  },
}));
vi.mock("@/lib/auth", () => ({ requireSession: mocks.requireSession }));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));
vi.mock("@/lib/edit-tracking", () => ({
  captureEditPattern: vi.fn(),
}));
vi.mock("next/cache", () => ({ revalidatePath: mocks.revalidatePath }));

import { reassignSpeakerAction } from "@/actions/soap";

const FAKE_USER = "u1";
const FAKE_PRACTICE = "p1";
const FAKE_VISIT = "vis1";
const FAKE_SPEAKER = "0";
const FAKE_PATIENT = "patient-1";
const UPDATED_AT = new Date("2026-07-20T00:00:00.000Z");

const ORDINARY_PROVENANCE = {
  patientId: FAKE_PATIENT,
  patient: {
    id: FAKE_PATIENT,
    practiceId: FAKE_PRACTICE,
    externalId: null,
  },
  noteTemplateId: null,
  noteTemplateVersion: null,
  noteTemplate: null,
  templateTwinFill: null,
  templateTwinSyntheticQaRun: null,
  templateTwinSyntheticQaAdmission: null,
  templateTwinProviderExecutions: [],
} as const;

function ordinaryVisit(overrides: Record<string, unknown> = {}) {
  return {
    id: FAKE_VISIT,
    userId: FAKE_USER,
    updatedAt: UPDATED_AT,
    status: "READY",
    speakerMap: {
      "0": { role: "doctor", confidence: 0.6, reasoning: "L2 inferred" },
      "1": { role: "patient", confidence: 0.9, reasoning: "L2 inferred" },
    },
    deletedAt: null,
    archivedAt: null,
    ...ORDINARY_PROVENANCE,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireSession.mockResolvedValue({
    user: {
      id: FAKE_USER,
      practiceId: FAKE_PRACTICE,
      email: "doctor@synthetic.test",
    },
  });
  mocks.stagingRunFindFirst.mockResolvedValue(null);
  mocks.visitFindUnique.mockResolvedValue(ordinaryVisit());
  mocks.visitUpdateMany.mockResolvedValue({ count: 1 });
  mocks.txQueryRaw.mockImplementation(async (query: { strings?: string[] }) => {
    const sql = query.strings?.join(" ") ?? "";
    if (sql.includes('FROM "practices"')) {
      return [{ id: FAKE_PRACTICE, isActive: true }];
    }
    if (sql.includes('FROM "users"')) return [{ id: FAKE_USER }];
    return [{ id: FAKE_VISIT }];
  });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        $queryRaw: mocks.txQueryRaw,
        transcribeVisit: { updateMany: mocks.visitUpdateMany },
      }),
  );
  mocks.logAudit.mockResolvedValue(undefined);
});

describe("reassignSpeakerAction SPEAKER_ROLE_REASSIGNED audit guard (FIND-P1-003)", () => {
  it("emits SPEAKER_ROLE_REASSIGNED with the right targetType + targetId on success", async () => {
    const result = await reassignSpeakerAction(
      FAKE_VISIT,
      FAKE_SPEAKER,
      "patient",
    );

    expect(result).toEqual({ ok: true });
    expect(mocks.visitUpdateMany).toHaveBeenCalledTimes(1);
    expect(mocks.logAudit).toHaveBeenCalledTimes(1);

    const auditArgs = mocks.logAudit.mock.calls[0][0];
    expect(auditArgs.action).toBe("SPEAKER_ROLE_REASSIGNED");
    expect(auditArgs.targetType).toBe("TranscribeVisit");
    expect(auditArgs.targetId).toBe(FAKE_VISIT);
  });

  it("audit metadata carries source + speakerId + previousRole + newRole", async () => {
    await reassignSpeakerAction(FAKE_VISIT, FAKE_SPEAKER, "patient");

    const auditArgs = mocks.logAudit.mock.calls[0][0];
    expect(auditArgs.metadata).toEqual({
      source: "server_action",
      speakerId: FAKE_SPEAKER,
      previousRole: "doctor", // from the seeded speakerMap
      newRole: "patient",
    });
  });

  it("previousRole is null when the speaker has no prior entry", async () => {
    // Reassigning a speakerId that's not in the existing speakerMap —
    // edge case but well-formed (the action creates a fresh entry).
    mocks.visitFindUnique.mockResolvedValue(
      ordinaryVisit({
        speakerMap: {}, // empty
      }),
    );

    await reassignSpeakerAction(FAKE_VISIT, "unknown-speaker", "doctor");

    const auditArgs = mocks.logAudit.mock.calls[0][0];
    expect(auditArgs.metadata.previousRole).toBe(null);
    expect(auditArgs.metadata.newRole).toBe("doctor");
    expect(auditArgs.metadata.speakerId).toBe("unknown-speaker");
  });

  it("no PHI in metadata — speakerId is internal, role is enum", async () => {
    await reassignSpeakerAction(FAKE_VISIT, FAKE_SPEAKER, "family");

    const auditArgs = mocks.logAudit.mock.calls[0][0];
    const metadataString = JSON.stringify(auditArgs.metadata);

    // Sanity-check: nothing in metadata should resemble PHI shapes —
    // no patient names, no email-like strings, no transcript fragments.
    expect(metadataString).not.toContain("@");
    expect(metadataString).not.toContain("doc@example.com");
    expect(metadataString).not.toMatch(/Manually reassigned/i);
    expect(metadataString).not.toContain(FAKE_USER);
  });

  it("audit emits AFTER the visit row is updated (not before)", async () => {
    const order: string[] = [];
    mocks.visitUpdateMany.mockImplementation(async () => {
      order.push("visit-update");
      return { count: 1 };
    });
    mocks.logAudit.mockImplementation(async () => {
      order.push("log-audit");
    });

    await reassignSpeakerAction(FAKE_VISIT, FAKE_SPEAKER, "patient");

    expect(order).toEqual(["visit-update", "log-audit"]);
  });

  it("audit failure does NOT break the reassign flow (fire-and-forget)", async () => {
    mocks.logAudit.mockRejectedValue(new Error("audit DB down"));

    const result = await reassignSpeakerAction(
      FAKE_VISIT,
      FAKE_SPEAKER,
      "patient",
    );

    expect(result).toEqual({ ok: true });
    expect(mocks.visitUpdateMany).toHaveBeenCalledTimes(1);
  });

  it("does NOT emit when role is invalid (zod rejects before any mutation)", async () => {
    const result = await reassignSpeakerAction(
      FAKE_VISIT,
      FAKE_SPEAKER,
      "not-a-role",
    );

    expect(result).toEqual({ ok: false, error: "Invalid speaker role." });
    expect(mocks.visitUpdateMany).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("does NOT emit when visit is not found", async () => {
    mocks.visitFindUnique.mockResolvedValue(null);

    const result = await reassignSpeakerAction(
      FAKE_VISIT,
      FAKE_SPEAKER,
      "patient",
    );

    expect(result).toEqual({ ok: false, error: "Visit not found." });
    expect(mocks.visitUpdateMany).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("does NOT emit when visit belongs to a different user", async () => {
    mocks.visitFindUnique.mockResolvedValue(
      ordinaryVisit({
        userId: "other-user",
        speakerMap: {},
      }),
    );

    const result = await reassignSpeakerAction(
      FAKE_VISIT,
      FAKE_SPEAKER,
      "patient",
    );

    expect(result).toEqual({ ok: false, error: "Visit not found." });
    expect(mocks.visitUpdateMany).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("does NOT emit when visit is trashed/archived", async () => {
    mocks.visitFindUnique.mockResolvedValue(
      ordinaryVisit({
        speakerMap: {},
        deletedAt: new Date(),
      }),
    );

    const result = await reassignSpeakerAction(
      FAKE_VISIT,
      FAKE_SPEAKER,
      "patient",
    );

    expect(result).toEqual({
      ok: false,
      error: "Visit is no longer active. Restore it first.",
    });
    expect(mocks.visitUpdateMany).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("does NOT emit when visit is already SIGNED (signed notes are locked)", async () => {
    mocks.visitFindUnique.mockResolvedValue(
      ordinaryVisit({
        status: "SIGNED",
        speakerMap: {},
      }),
    );

    const result = await reassignSpeakerAction(
      FAKE_VISIT,
      FAKE_SPEAKER,
      "patient",
    );

    expect(result).toEqual({
      ok: false,
      error: "Signed notes cannot be edited.",
    });
    expect(mocks.visitUpdateMany).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });
});
