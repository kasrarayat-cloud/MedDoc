// ============================================================================
// createVisitAction — VISIT_CREATED audit-row guard (F-10 closure)
// ----------------------------------------------------------------------------
// QA Interaction Auditor v3.2 PASS A surfaced F-10: visit creation
// previously had no audit action, so the create-event was invisible
// in the audit trail (only VIEWED_VISIT fired later when the doctor
// navigated into the row). This test pins the post-fix shape:
//
//   - Successful create writes ONE audit row with action='VISIT_CREATED'
//     + targetType='TranscribeVisit' + targetId=<new id> + metadata
//     containing inputMode / specialty / patientId
//   - PHI is excluded from metadata (no patient name, no chief complaint)
//   - The audit call is fire-and-forget — a logAudit failure never
//     breaks the user-facing create flow
// ============================================================================

import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  visitCreate: vi.fn(),
  patientFindUnique: vi.fn(),
  patientFindFirst: vi.fn(),
  patientCreate: vi.fn(),
  requireSession: vi.fn(),
  logAudit: vi.fn(),
  redirect: vi.fn((url: string) => {
    // next/navigation redirect throws; mirror that so the action
    // unwinds at the same point in production code.
    const err = new Error(`NEXT_REDIRECT:${url}`);
    (err as { digest?: string }).digest = `NEXT_REDIRECT;replace;${url};307;`;
    throw err;
  }),
  revalidatePath: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    transcribeVisit: { create: mocks.visitCreate },
    transcribeMdPatient: {
      findUnique: mocks.patientFindUnique,
      findFirst: mocks.patientFindFirst,
      create: mocks.patientCreate,
    },
  },
}));
vi.mock("@/lib/auth", () => ({ requireSession: mocks.requireSession }));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));
vi.mock("@/lib/log", () => ({
  log: { info: vi.fn(), error: vi.fn(), warn: vi.fn() },
}));
vi.mock("next/navigation", () => ({ redirect: mocks.redirect }));
vi.mock("next/cache", () => ({ revalidatePath: mocks.revalidatePath }));

import { createVisitAction } from "@/actions/visits";
import { TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID } from "@/lib/template-twin/synthetic-qa-patient";

const FAKE_USER = "u1";
const FAKE_PRACTICE = "p1";
const FAKE_PATIENT = "pat1";
const FAKE_VISIT = "vis1";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireSession.mockResolvedValue({
    user: { id: FAKE_USER, practiceId: FAKE_PRACTICE },
  });
  // The patientId path: resolvePatient calls findUnique with practice
  // scope; we return a row that passes the scope check.
  mocks.patientFindUnique.mockResolvedValue({
    id: FAKE_PATIENT,
    name: "QA Test Patient",
    practiceId: FAKE_PRACTICE,
    deletedAt: null,
    externalId: null,
  });
  mocks.patientFindFirst.mockResolvedValue({
    id: FAKE_PATIENT,
    name: "QA Test Patient",
  });
  mocks.visitCreate.mockResolvedValue({ id: FAKE_VISIT });
});

function makeFormData(overrides: Record<string, string> = {}) {
  const data = new FormData();
  data.set("inputMode", "text_notes");
  data.set("specialty", "primary-care");
  data.set("patientId", FAKE_PATIENT);
  data.set("patientName", "QA Test Patient");
  for (const [k, v] of Object.entries(overrides)) data.set(k, v);
  return data;
}

describe("createVisitAction VISIT_CREATED audit guard (F-10)", () => {
  it("emits VISIT_CREATED with the right targetType + targetId on success", async () => {
    await expect(createVisitAction(makeFormData())).rejects.toThrow(
      /NEXT_REDIRECT/,
    );

    expect(mocks.visitCreate).toHaveBeenCalledTimes(1);
    expect(mocks.logAudit).toHaveBeenCalledTimes(1);

    const auditArgs = mocks.logAudit.mock.calls[0][0];
    expect(auditArgs.action).toBe("VISIT_CREATED");
    expect(auditArgs.targetType).toBe("TranscribeVisit");
    expect(auditArgs.targetId).toBe(FAKE_VISIT);
  });

  it("audit metadata carries inputMode + specialty + patientId; no PHI", async () => {
    await expect(
      createVisitAction(
        makeFormData({
          inputMode: "audio_upload",
          specialty: "cardiology",
          chiefComplaint: "chest pain", // PHI — must NOT land in metadata
        }),
      ),
    ).rejects.toThrow(/NEXT_REDIRECT/);

    const auditArgs = mocks.logAudit.mock.calls[0][0];
    expect(auditArgs.metadata).toMatchObject({
      source: "action:createVisitAction",
      inputMode: "audio_upload",
      specialty: "cardiology",
      patientId: FAKE_PATIENT,
    });
    // PHI guard: chief complaint, patient name must NOT be in metadata.
    const metadataString = JSON.stringify(auditArgs.metadata);
    expect(metadataString).not.toContain("chest pain");
    expect(metadataString).not.toContain("QA Test Patient");
  });

  it("audit emits AFTER the visit row is created (not before)", async () => {
    const order: string[] = [];
    mocks.visitCreate.mockImplementation(async () => {
      order.push("visit-create");
      return { id: FAKE_VISIT };
    });
    mocks.logAudit.mockImplementation(async () => {
      order.push("log-audit");
    });

    await expect(createVisitAction(makeFormData())).rejects.toThrow(
      /NEXT_REDIRECT/,
    );

    expect(order).toEqual(["visit-create", "log-audit"]);
  });

  it("audit failure does NOT break the create flow (fire-and-forget)", async () => {
    // logAudit rejects — the action must still complete + redirect.
    mocks.logAudit.mockRejectedValue(new Error("audit DB down"));

    // Still throws NEXT_REDIRECT — meaning the create flow finished +
    // the audit failure was swallowed (the helper is internally try/
    // wrapped, but this test pins the void-call pattern at the call
    // site so future refactors don't accidentally `await logAudit()`
    // and break the create flow on transient audit-store failures).
    await expect(createVisitAction(makeFormData())).rejects.toThrow(
      /NEXT_REDIRECT/,
    );

    expect(mocks.visitCreate).toHaveBeenCalledTimes(1);
    expect(mocks.redirect).toHaveBeenCalledWith(`/visits/${FAKE_VISIT}`);
  });

  it("does NOT emit VISIT_CREATED when input validation rejects (no row created)", async () => {
    await expect(
      createVisitAction(makeFormData({ inputMode: "not-a-mode" })),
    ).rejects.toThrow("Invalid visit input");

    // Visit was never created → audit must not fire.
    expect(mocks.visitCreate).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("does not allow an ordinary visit to select the reserved synthetic QA patient", async () => {
    mocks.patientFindUnique.mockResolvedValue({
      id: FAKE_PATIENT,
      name: "Template Twin Synthetic QA",
      practiceId: FAKE_PRACTICE,
      deletedAt: null,
      externalId: TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID,
    });

    await expect(createVisitAction(makeFormData())).rejects.toThrow(
      "Invalid patient",
    );

    expect(mocks.visitCreate).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });
});
