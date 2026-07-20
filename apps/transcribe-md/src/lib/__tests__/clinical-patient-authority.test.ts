import { describe, expect, it, vi } from "vitest";

import {
  ClinicalPatientAuthorityError,
  currentClinicalPatientCollectionWhere,
  currentClinicalPatientReadAuthoritySql,
  currentClinicalPatientWhere,
  lockAndReadCurrentClinicalPatient,
} from "../clinical-patient-authority";

const actor = { userId: "doctor-1", practiceId: "practice-1" };

function patient() {
  const now = new Date("2026-07-20T00:00:00.000Z");
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
    createdAt: now,
    updatedAt: now,
  };
}

describe("current clinical patient authority", () => {
  it("builds a same-query current actor, active practice, and patient predicate", () => {
    expect(
      currentClinicalPatientWhere({ actor, patientId: "patient-1" }),
    ).toMatchObject({
      id: "patient-1",
      practiceId: actor.practiceId,
      deletedAt: null,
      practice: {
        is: {
          id: actor.practiceId,
          isActive: true,
          users: {
            some: {
              id: actor.userId,
              practiceId: actor.practiceId,
              role: "DOCTOR",
              isActive: true,
              deactivatedAt: null,
              suspendedAt: null,
              softDeletedAt: null,
              products: { has: "TRANSCRIBE_MD" },
            },
          },
        },
      },
    });
  });

  it("builds the same current-authority predicate for roster reads and counts", () => {
    expect(currentClinicalPatientCollectionWhere({ actor })).toMatchObject({
      practiceId: actor.practiceId,
      deletedAt: null,
      practice: {
        is: {
          id: actor.practiceId,
          isActive: true,
          users: {
            some: {
              id: actor.userId,
              practiceId: actor.practiceId,
              role: "DOCTOR",
              isActive: true,
              suspendedAt: null,
              products: { has: "TRANSCRIBE_MD" },
            },
          },
        },
      },
    });
  });

  it("builds a raw-query boundary that rebinds roster PHI to the exact current actor", () => {
    const statement = currentClinicalPatientReadAuthoritySql({
      actor,
      patientAlias: "p",
    });
    const sql = statement.strings.join(" ");

    expect(statement.values).toContain(actor.userId);
    expect(statement.values).toContain(actor.practiceId);
    expect(sql).toContain('p."practiceId"');
    expect(sql).toContain('p."deletedAt" IS NULL');
    expect(sql).toContain('p."externalId" IS DISTINCT FROM');
    expect(sql).toContain('FROM "practices" current_practice');
    expect(sql).toContain('JOIN "users" current_actor');
    expect(sql).toContain('current_practice."isActive" = TRUE');
    expect(sql).toContain("current_actor.\"role\" = 'DOCTOR'");
    expect(sql).toContain('current_actor."deactivatedAt" IS NULL');
    expect(sql).toContain('current_actor."suspendedAt" IS NULL');
    expect(sql).toContain('current_actor."softDeletedAt" IS NULL');
    expect(sql).toContain("'TRANSCRIBE_MD'::\"Product\"");
  });

  it("locks practice, actor, then patient and reasserts authority in the PHI query", async () => {
    const query = vi
      .fn()
      .mockResolvedValueOnce([{ id: actor.practiceId }])
      .mockResolvedValueOnce([{ id: actor.userId }])
      .mockResolvedValueOnce([patient()]);

    await expect(
      lockAndReadCurrentClinicalPatient({
        tx: { $queryRaw: query },
        actor,
        patientId: "patient-1",
      }),
    ).resolves.toMatchObject({ id: "patient-1" });

    const sql = query.mock.calls.map(
      ([statement]) => statement?.strings?.join(" ") ?? "",
    );
    expect(sql[0]).toContain('FROM "practices"');
    expect(sql[1]).toContain('FROM "users" actor');
    expect(sql[2]).toContain('FROM "transcribe_md_patients" patient');
    expect(sql[2]).toContain('practice."isActive" = TRUE');
    expect(sql[2]).toContain('actor."practiceId" = practice."id"');
    expect(sql[2]).toContain("actor.\"role\" = 'DOCTOR'");
    expect(sql[2]).toContain('actor."deactivatedAt" IS NULL');
    expect(sql[2]).toContain('actor."suspendedAt" IS NULL');
    expect(sql[2]).toContain('actor."softDeletedAt" IS NULL');
    expect(sql[2]).toContain("'TRANSCRIBE_MD'::\"Product\"");
    expect(sql[2]).toContain('patient."deletedAt" IS NULL');
    expect(sql[2]).toContain('patient."externalId" IS DISTINCT FROM');
    expect(sql[2]).toContain("FOR UPDATE OF patient");
  });

  it("fails before patient PHI when the exact practice is inactive", async () => {
    const query = vi.fn().mockResolvedValueOnce([]);
    await expect(
      lockAndReadCurrentClinicalPatient({
        tx: { $queryRaw: query },
        actor,
        patientId: "patient-1",
      }),
    ).rejects.toBeInstanceOf(ClinicalPatientAuthorityError);
    expect(query).toHaveBeenCalledOnce();
  });

  it.each([
    "practice transfer",
    "role removal",
    "deactivation",
    "suspension",
    "soft deletion",
    "product removal",
  ])("fails before patient PHI on actor %s", async () => {
    const query = vi
      .fn()
      .mockResolvedValueOnce([{ id: actor.practiceId }])
      .mockResolvedValueOnce([]);
    await expect(
      lockAndReadCurrentClinicalPatient({
        tx: { $queryRaw: query },
        actor,
        patientId: "patient-1",
      }),
    ).rejects.toBeInstanceOf(ClinicalPatientAuthorityError);
    expect(query).toHaveBeenCalledTimes(2);
  });

  it.each(["deleted patient", "reserved synthetic patient"])(
    "returns no PHI row for a %s",
    async () => {
      const query = vi
        .fn()
        .mockResolvedValueOnce([{ id: actor.practiceId }])
        .mockResolvedValueOnce([{ id: actor.userId }])
        .mockResolvedValueOnce([]);
      await expect(
        lockAndReadCurrentClinicalPatient({
          tx: { $queryRaw: query },
          actor,
          patientId: "patient-1",
        }),
      ).resolves.toBeNull();
    },
  );
});
