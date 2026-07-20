import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  transaction: vi.fn(),
  queryRaw: vi.fn(),
  patientCreate: vi.fn(),
  visitCreate: vi.fn(),
  requireSession: vi.fn(),
  logAudit: vi.fn(),
  redirect: vi.fn(),
  revalidatePath: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: { $transaction: mocks.transaction },
}));
vi.mock("@/lib/auth", () => ({ requireSession: mocks.requireSession }));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));
vi.mock("next/navigation", () => ({ redirect: mocks.redirect }));
vi.mock("next/cache", () => ({ revalidatePath: mocks.revalidatePath }));

import { ClinicalPatientAuthorityError } from "@/lib/clinical-patient-authority";
import { createVisitAction } from "../visits";

const actor = { userId: "doctor-1", practiceId: "practice-1" };
const admittedAt = new Date("2026-07-20T00:00:00.000Z");

function patient(
  overrides: Partial<{
    id: string;
    practiceId: string;
    name: string;
    externalId: string | null;
    deletedAt: Date | null;
  }> = {},
) {
  return {
    id: "patient-1",
    practiceId: actor.practiceId,
    name: "Synthetic Example",
    dateOfBirth: null,
    externalId: null,
    mrn: null,
    insurance: null,
    problemList: null,
    deletedAt: null,
    createdAt: admittedAt,
    updatedAt: admittedAt,
    ...overrides,
  };
}

function form(input: { patientId?: string; patientName?: string } = {}) {
  const data = new FormData();
  if (input.patientId !== undefined) data.set("patientId", input.patientId);
  if (input.patientName !== undefined) {
    data.set("patientName", input.patientName);
  }
  data.set("specialty", "primary-care");
  data.set("inputMode", "text_notes");
  return data;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireSession.mockResolvedValue({
    user: { id: actor.userId, practiceId: actor.practiceId },
  });
  const tx = {
    $queryRaw: mocks.queryRaw,
    transcribeMdPatient: { create: mocks.patientCreate },
    transcribeVisit: { create: mocks.visitCreate },
  };
  mocks.transaction.mockImplementation(
    async (run: (client: typeof tx) => Promise<unknown>) => run(tx),
  );
  mocks.visitCreate.mockResolvedValue({ id: "visit-1" });
  mocks.redirect.mockReturnValue(undefined);
});

describe("createVisitAction current patient authority", () => {
  it("binds current actor, exact active practice, and patient safety in the locking PHI query", async () => {
    mocks.queryRaw
      .mockResolvedValueOnce([{ id: actor.practiceId }])
      .mockResolvedValueOnce([{ id: actor.userId }])
      .mockResolvedValueOnce([patient()]);

    await expect(
      createVisitAction(form({ patientId: "patient-1" })),
    ).resolves.toBeUndefined();

    expect(mocks.queryRaw).toHaveBeenCalledTimes(3);
    const practiceSql = mocks.queryRaw.mock.calls[0]?.[0];
    const actorSql = mocks.queryRaw.mock.calls[1]?.[0];
    const patientSql = mocks.queryRaw.mock.calls[2]?.[0];
    expect(practiceSql?.strings?.join(" ")).toContain('FROM "practices"');
    expect(actorSql?.strings?.join(" ")).toContain('FROM "users" actor');
    const patientText = patientSql?.strings?.join(" ") ?? "";
    expect(patientText).toContain('FROM "transcribe_md_patients" patient');
    expect(patientText).toContain('JOIN "practices" practice');
    expect(patientText).toContain('JOIN "users" actor');
    expect(patientText).toContain('actor."suspendedAt" IS NULL');
    expect(patientText).toContain("'TRANSCRIBE_MD'::\"Product\"");
    expect(patientText).toContain('patient."deletedAt" IS NULL');
    expect(patientText).toContain('patient."externalId" IS DISTINCT FROM');
    expect(patientText).toContain("FOR UPDATE OF patient");
    expect(mocks.visitCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          userId: actor.userId,
          patientId: "patient-1",
          patientName: "Synthetic Example",
        }),
      }),
    );
  });

  it("blocks practice transfer before any patient PHI projection or visit link", async () => {
    mocks.queryRaw
      .mockResolvedValueOnce([{ id: actor.practiceId }])
      .mockResolvedValueOnce([]);

    await expect(
      createVisitAction(form({ patientId: "patient-1" })),
    ).rejects.toBeInstanceOf(ClinicalPatientAuthorityError);

    expect(mocks.queryRaw).toHaveBeenCalledTimes(2);
    expect(mocks.patientCreate).not.toHaveBeenCalled();
    expect(mocks.visitCreate).not.toHaveBeenCalled();
  });

  it.each(["patient deletion", "reserved-marker transition"])(
    "blocks %s before a PHI row or visit link is returned",
    async () => {
      mocks.queryRaw
        .mockResolvedValueOnce([{ id: actor.practiceId }])
        .mockResolvedValueOnce([{ id: actor.userId }])
        .mockResolvedValueOnce([]);

      await expect(
        createVisitAction(form({ patientId: "patient-1" })),
      ).rejects.toThrow("Invalid patient");
      expect(mocks.visitCreate).not.toHaveBeenCalled();
    },
  );

  it("locks and reuses an authorized free-text exact match", async () => {
    mocks.queryRaw
      .mockResolvedValueOnce([{ id: actor.practiceId }])
      .mockResolvedValueOnce([{ id: actor.userId }])
      .mockResolvedValueOnce([patient()]);

    await createVisitAction(form({ patientName: "Synthetic Example" }));

    const patientSql = mocks.queryRaw.mock.calls[2]?.[0];
    expect(patientSql?.strings?.join(" ")).toContain(
      'LOWER(patient."name") = LOWER(',
    );
    expect(mocks.patientCreate).not.toHaveBeenCalled();
    expect(mocks.visitCreate).toHaveBeenCalledOnce();
  });

  it("creates, reasserts, and links a free-text patient in one transaction", async () => {
    mocks.queryRaw
      .mockResolvedValueOnce([{ id: actor.practiceId }])
      .mockResolvedValueOnce([{ id: actor.userId }])
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([patient({ id: "patient-created" })]);
    mocks.patientCreate.mockResolvedValue({ id: "patient-created" });

    await createVisitAction(form({ patientName: "Synthetic Example" }));

    expect(mocks.patientCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ practiceId: actor.practiceId }),
      }),
    );
    expect(mocks.visitCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ patientId: "patient-created" }),
      }),
    );
    expect(mocks.transaction).toHaveBeenCalledOnce();
  });

  it("does not link a newly created patient when final patient reassertion fails", async () => {
    mocks.queryRaw
      .mockResolvedValueOnce([{ id: actor.practiceId }])
      .mockResolvedValueOnce([{ id: actor.userId }])
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([]);
    mocks.patientCreate.mockResolvedValue({ id: "patient-created" });

    await expect(
      createVisitAction(form({ patientName: "Synthetic Example" })),
    ).rejects.toThrow("Invalid patient");
    expect(mocks.patientCreate).toHaveBeenCalledOnce();
    expect(mocks.visitCreate).not.toHaveBeenCalled();
  });
});
