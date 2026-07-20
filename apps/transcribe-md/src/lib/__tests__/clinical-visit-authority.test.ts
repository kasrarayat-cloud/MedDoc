import { describe, expect, it, vi } from "vitest";
import type { Prisma } from "@prisma/client";

import {
  claimCurrentOrdinaryVisitDeliveryActor,
  currentClinicalVisitActorWhere,
} from "../clinical-visit-authority";

function sqlText(query: Prisma.Sql): string {
  return query.strings.join("?").replace(/\s+/gu, " ").trim();
}

describe("current clinical visit authority", () => {
  it("binds actor lifecycle, product, active practice, and patient tenant in the PHI query", () => {
    expect(currentClinicalVisitActorWhere("doctor-1")).toEqual({
      userId: "doctor-1",
      user: {
        is: {
          id: "doctor-1",
          role: "DOCTOR",
          isActive: true,
          deactivatedAt: null,
          suspendedAt: null,
          softDeletedAt: null,
          products: { has: "TRANSCRIBE_MD" },
        },
      },
      patient: {
        is: {
          practice: {
            is: {
              isActive: true,
              users: {
                some: {
                  id: "doctor-1",
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
        },
      },
    });
  });

  it("claims an ordinary delivery only through one fully bound locking statement", async () => {
    const queryRaw = vi.fn(async (query: Prisma.Sql) => {
      const sql = sqlText(query);
      expect(sql).toContain('practice."isActive" = TRUE');
      expect(sql).toContain('actor."role" = \'DOCTOR\'::"UserRole"');
      expect(sql).toContain('actor."deactivatedAt" IS NULL');
      expect(sql).toContain('actor."suspendedAt" IS NULL');
      expect(sql).toContain('actor."softDeletedAt" IS NULL');
      expect(sql).toContain('\'TRANSCRIBE_MD\'::"Product" = ANY');
      expect(sql).toContain(
        'patient."practiceId" = practice."id"',
      );
      expect(sql).toContain(
        'patient."externalId" IS DISTINCT FROM \'SYNTHETIC-QA-ONLY\'',
      );
      expect(sql).toContain(
        "FOR SHARE OF practice, actor, patient, visit",
      );
      for (const marker of [
        "template_twin_compiled_versions",
        "template_twin_fill_manifests",
        "template_twin_synthetic_qa_runs",
        "template_twin_synthetic_qa_admissions",
        "template_twin_provider_executions",
      ]) {
        expect(sql).toContain(marker);
      }
      return [
        {
          id: "doctor-1",
          practiceId: "practice-1",
          email: "current@example.test",
        },
      ];
    });

    await expect(
      claimCurrentOrdinaryVisitDeliveryActor(
        { visitId: "visit-1", actorUserId: "doctor-1" },
        {
          $queryRaw: async <T>(query: Prisma.Sql): Promise<T> =>
            (await queryRaw(query)) as unknown as T,
        },
      ),
    ).resolves.toEqual({
      id: "doctor-1",
      practiceId: "practice-1",
      email: "current@example.test",
    });
    expect(queryRaw).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["no matching current actor", []],
    [
      "duplicate/malformed projection",
      [
        {
          id: "doctor-1",
          practiceId: "practice-1",
          email: "current@example.test",
        },
        {
          id: "doctor-1",
          practiceId: "practice-1",
          email: "current@example.test",
        },
      ],
    ],
    [
      "empty current email",
      [{ id: "doctor-1", practiceId: "practice-1", email: "" }],
    ],
  ])("fails closed for %s", async (_label, rows) => {
    await expect(
      claimCurrentOrdinaryVisitDeliveryActor(
        { visitId: "visit-1", actorUserId: "doctor-1" },
        {
          $queryRaw: async <T>(): Promise<T> => rows as unknown as T,
        },
      ),
    ).resolves.toBeNull();
  });
});
