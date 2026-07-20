import { describe, expect, it, vi } from "vitest";
import type { TransactionHost } from "@/lib/db/transaction-retry";

import {
  aggregateTemplateTwinVisibleVisits,
  countTemplateTwinVisibleVisitsByPatient,
  inspectTemplateTwinVisitReads,
  listLatestTemplateTwinVisibleVisitByPatient,
  listTemplateTwinVisibleVisitIdentities,
  listTemplateTwinVisibleVisitPage,
  readTemplateTwinVisibleVisitPage,
  reassertTemplateTwinVisitReadAuthority,
  requireTemplateTwinVisitReadAuthority,
  TemplateTwinVisitReadAuthorityError,
} from "../read-authority";

function twinRow(overrides: Record<string, unknown> = {}) {
  return {
    visitId: "visit-twin-1",
    isTemplateTwin: true,
    isSyntheticTemplateTwin: false,
    isInternalPreCertification: false,
    authorized: true,
    practiceId: "practice-current",
    templateTwinEnabled: true,
    ...overrides,
  };
}

describe("Template Twin generic visit read authority", () => {
  it("accepts an exact current physician/practice binding without requiring rollout", async () => {
    const query = vi
      .fn()
      .mockResolvedValue([twinRow({ templateTwinEnabled: false })]);

    await expect(
      requireTemplateTwinVisitReadAuthority({
        db: { $queryRaw: query },
        visitId: "visit-twin-1",
        actorUserId: "doctor-1",
      }),
    ).resolves.toEqual({
      visitId: "visit-twin-1",
      isTemplateTwin: true,
      isSyntheticTemplateTwin: false,
      practiceId: "practice-current",
      templateTwinEnabled: false,
    });
  });

  it.each([
    "inactive",
    "deactivated",
    "suspended",
    "soft-deleted",
    "non-doctor role",
    "missing TRANSCRIBE_MD product",
    "practice transfer",
    "inactive practice",
    "inconsistent template/fill/run/admission/execution provenance",
  ])("fails closed for %s current authority", async () => {
    const query = vi
      .fn()
      .mockResolvedValue([
        twinRow({ authorized: false, practiceId: "practice-stale" }),
      ]);

    await expect(
      requireTemplateTwinVisitReadAuthority({
        db: { $queryRaw: query },
        visitId: "visit-twin-1",
        actorUserId: "doctor-1",
      }),
    ).rejects.toBeInstanceOf(TemplateTwinVisitReadAuthorityError);
  });

  it("never admits an internal pre-certification voice visit to a generic read", async () => {
    const query = vi.fn().mockResolvedValue([
      twinRow({
        isSyntheticTemplateTwin: true,
        isInternalPreCertification: true,
        authorized: false,
      }),
    ]);

    await expect(
      requireTemplateTwinVisitReadAuthority({
        db: { $queryRaw: query },
        visitId: "visit-twin-1",
        actorUserId: "doctor-1",
      }),
    ).rejects.toBeInstanceOf(TemplateTwinVisitReadAuthorityError);
  });

  it("returns an ordinary visit only after exact current authority succeeds without promoting tenant claims", async () => {
    const query = vi.fn().mockResolvedValue([
      {
        visitId: "visit-ordinary-1",
        isTemplateTwin: false,
        isSyntheticTemplateTwin: false,
        isInternalPreCertification: false,
        authorized: true,
        practiceId: "practice-from-stale-session",
        templateTwinEnabled: null,
      },
    ]);

    await expect(
      requireTemplateTwinVisitReadAuthority({
        db: { $queryRaw: query },
        visitId: "visit-ordinary-1",
        actorUserId: "doctor-1",
      }),
    ).resolves.toEqual({
      visitId: "visit-ordinary-1",
      isTemplateTwin: false,
      isSyntheticTemplateTwin: false,
      practiceId: null,
      templateTwinEnabled: null,
    });
  });

  it.each([
    "inactive",
    "deactivated",
    "suspended",
    "soft-deleted",
    "non-doctor role",
    "missing TRANSCRIBE_MD product",
    "practice transfer",
    "inactive practice",
    "patient tenant drift",
  ])(
    "fails closed for an ordinary visit after %s current-authority revocation",
    async () => {
      const query = vi.fn().mockResolvedValue([
        {
          visitId: "visit-ordinary-1",
          isTemplateTwin: false,
          isSyntheticTemplateTwin: false,
          isInternalPreCertification: false,
          authorized: false,
          practiceId: "practice-stale",
          templateTwinEnabled: null,
        },
      ]);

      await expect(
        requireTemplateTwinVisitReadAuthority({
          db: { $queryRaw: query },
          visitId: "visit-ordinary-1",
          actorUserId: "doctor-1",
        }),
      ).rejects.toBeInstanceOf(TemplateTwinVisitReadAuthorityError);
    },
  );

  it("fails closed for an ordinary-classified row without a real patient", async () => {
    const query = vi.fn().mockResolvedValue([
      {
        visitId: "visit-missing-patient",
        isTemplateTwin: false,
        isSyntheticTemplateTwin: false,
        isInternalPreCertification: false,
        authorized: false,
        practiceId: "practice-current",
        templateTwinEnabled: null,
      },
    ]);

    await expect(
      inspectTemplateTwinVisitReads({
        db: { $queryRaw: query },
        visitIds: ["visit-missing-patient"],
        actorUserId: "doctor-1",
      }),
    ).resolves.toEqual([]);
  });

  it("suppresses unauthorized Twin rows while retaining ordinary rows in a mixed list", async () => {
    const query = vi.fn().mockResolvedValue([
      twinRow({ authorized: false }),
      {
        visitId: "visit-ordinary-1",
        isTemplateTwin: false,
        isSyntheticTemplateTwin: false,
        isInternalPreCertification: false,
        authorized: true,
        practiceId: null,
        templateTwinEnabled: null,
      },
      twinRow({ visitId: "visit-twin-2" }),
    ]);

    await expect(
      inspectTemplateTwinVisitReads({
        db: { $queryRaw: query },
        visitIds: ["visit-twin-1", "visit-ordinary-1", "visit-twin-2"],
        actorUserId: "doctor-1",
      }),
    ).resolves.toEqual([
      {
        visitId: "visit-ordinary-1",
        isTemplateTwin: false,
        isSyntheticTemplateTwin: false,
        practiceId: null,
        templateTwinEnabled: null,
      },
      {
        visitId: "visit-twin-2",
        isTemplateTwin: true,
        isSyntheticTemplateTwin: false,
        practiceId: "practice-current",
        templateTwinEnabled: true,
      },
    ]);
  });

  it("applies caller scope, cursor, order, and limit in the exact SQL page", async () => {
    const query = vi
      .fn()
      .mockResolvedValue([
        { id: "visit-twin-1", createdAt: new Date("2026-07-19T00:00:00Z") },
      ]);
    await listTemplateTwinVisibleVisitPage({
      db: { $queryRaw: query },
      actorUserId: "doctor-1",
      query: {
        scope: {
          patientId: "patient-1",
          deleted: "active",
          archived: "active",
          statuses: ["READY"],
          needsReview: true,
          search: "bounded",
        },
        orderBy: "updatedAt",
        direction: "desc",
        cursor: {
          value: new Date("2026-07-20T00:00:00Z"),
          id: "visit-cursor",
        },
        skip: 20,
        take: 20,
      },
    });

    const sql = query.mock.calls[0]?.[0];
    const text = sql?.strings?.join(" ") ?? "";
    expect(text).toContain('visit."patientId" =');
    expect(text).toContain('visit."deletedAt" IS NULL');
    expect(text).toContain('visit."archivedAt" IS NULL');
    expect(text).toContain('visit."status"::text IN');
    expect(text).toContain('visit."needsReview" =');
    expect(text).toContain('patient."name" ILIKE');
    expect(text).toContain('visit."updatedAt"');
    expect(text).toContain("DESC");
    expect(text).toContain("LIMIT");
    expect(text).toContain("OFFSET");
    expect(text).toContain('current_actor."role"');
    expect(text).toContain("'TRANSCRIBE_MD'::\"Product\"");
    expect(text).toContain("SYNTHETIC-QA-ONLY");
    expect(sql?.values).toEqual(
      expect.arrayContaining([
        "doctor-1",
        "patient-1",
        "READY",
        true,
        "%bounded%",
        "visit-cursor",
        20,
      ]),
    );
  });

  it("has no lifetime Twin ceiling and returns a bounded page above 128", async () => {
    const identities = Array.from({ length: 130 }, (_, index) => ({
      id: `visit-twin-${index.toString().padStart(3, "0")}`,
      createdAt: new Date(Date.UTC(2026, 6, 19, 0, index)),
    }));
    const query = vi.fn().mockResolvedValue(identities);

    await expect(
      listTemplateTwinVisibleVisitPage({
        db: { $queryRaw: query },
        actorUserId: "doctor-1",
        query: { take: 130, direction: "desc" },
      }),
    ).resolves.toEqual(identities);
    expect(query).toHaveBeenCalledTimes(1);
    expect(query.mock.calls[0]?.[0]?.values).toContain(130);
  });

  it.each([
    ["createdAt" as const, undefined],
    ["updatedAt" as const, undefined],
    ["deletedAt" as const, { deleted: "deleted" as const }],
  ])("supports a progressing %s cursor", async (orderBy, scope) => {
    const query = vi.fn().mockResolvedValue([]);
    await listTemplateTwinVisibleVisitPage({
      db: { $queryRaw: query },
      actorUserId: "doctor-1",
      query: {
        ...(scope ? { scope } : {}),
        orderBy,
        direction: "asc",
        cursor: {
          value: new Date("2026-07-20T00:00:00Z"),
          id: "visit-cursor",
        },
        take: 25,
      },
    });
    const text = query.mock.calls[0]?.[0]?.strings?.join(" ") ?? "";
    expect(text).toContain(`visit."${orderBy}"`);
    expect(text).toContain("ASC");
    expect(text).toContain("> ");
  });

  it("rejects nullable deletedAt ordering outside the deleted-only scope", async () => {
    const query = vi.fn();
    await expect(
      listTemplateTwinVisibleVisitPage({
        db: { $queryRaw: query },
        actorUserId: "doctor-1",
        query: {
          orderBy: "deletedAt",
          direction: "desc",
          cursor: {
            value: new Date("2026-07-20T00:00:00Z"),
            id: "visit-cursor",
          },
          take: 25,
        },
      }),
    ).rejects.toThrow(
      'deletedAt ordering requires scope.deleted to be "deleted".',
    );
    expect(query).not.toHaveBeenCalled();
  });

  it("preserves literal Prisma-contains semantics for SQL wildcard input", async () => {
    const query = vi.fn().mockResolvedValue([]);
    await listTemplateTwinVisibleVisitPage({
      db: { $queryRaw: query },
      actorUserId: "doctor-1",
      query: { scope: { search: "literal%_!" }, take: 10 },
    });
    const sql = query.mock.calls[0]?.[0];
    expect(sql?.strings?.join(" ")).toContain("ESCAPE '!'");
    expect(sql?.values).toContain("%literal!%!_!!%");
  });

  it("bounds direct patient grouping and latest-identity helpers", async () => {
    const query = vi.fn();
    const patientIds = Array.from(
      { length: 257 },
      (_, index) => `patient-${index}`,
    );
    await expect(
      countTemplateTwinVisibleVisitsByPatient({
        db: { $queryRaw: query },
        actorUserId: "doctor-1",
        patientIds,
      }),
    ).rejects.toBeInstanceOf(RangeError);
    await expect(
      listLatestTemplateTwinVisibleVisitByPatient({
        db: { $queryRaw: query },
        actorUserId: "doctor-1",
        patientIds,
      }),
    ).rejects.toBeInstanceOf(RangeError);
    expect(query).not.toHaveBeenCalled();
  });

  it("computes exact aggregate values without enumerating visit identities", async () => {
    const query = vi.fn().mockResolvedValue([
      {
        count: 257,
        maxCreatedAt: new Date("2026-07-20T00:00:00Z"),
        avgDraftedInSeconds: 91.5,
      },
    ]);
    await expect(
      aggregateTemplateTwinVisibleVisits({
        db: { $queryRaw: query },
        actorUserId: "doctor-1",
        scope: { deleted: "active", draftedInSeconds: "present" },
      }),
    ).resolves.toMatchObject({ count: 257, avgDraftedInSeconds: 91.5 });
    const text = query.mock.calls[0]?.[0]?.strings?.join(" ") ?? "";
    expect(text).toContain("COUNT(*)::integer");
    expect(text).toContain('AVG(visit."draftedInSeconds")');
    expect(text).not.toContain(" IN (");
  });

  it("hydrates only bounded exact ids and restores database page order", async () => {
    const query = vi
      .fn()
      .mockResolvedValueOnce([
        { id: "visit-2", createdAt: new Date("2026-07-20T00:00:00Z") },
        { id: "visit-1", createdAt: new Date("2026-07-19T00:00:00Z") },
      ])
      .mockResolvedValueOnce([
        twinRow({ visitId: "visit-1" }),
        twinRow({ visitId: "visit-2" }),
      ]);
    const transaction = vi.fn(
      async (
        callback: (tx: { $queryRaw: typeof query }) => Promise<unknown>,
        options?: unknown,
      ) => {
        void options;
        return callback({ $queryRaw: query });
      },
    );
    const hydrate = vi.fn().mockResolvedValue([
      { id: "visit-1", value: "one" },
      { id: "visit-2", value: "two" },
    ]);

    await expect(
      readTemplateTwinVisibleVisitPage({
        db: { $transaction: transaction } as unknown as TransactionHost,
        actorUserId: "doctor-1",
        query: { take: 2 },
        hydrate,
      }),
    ).resolves.toEqual([
      { id: "visit-2", value: "two" },
      { id: "visit-1", value: "one" },
    ]);
    expect(hydrate).toHaveBeenCalledWith(expect.anything(), [
      "visit-2",
      "visit-1",
    ]);
    expect(transaction.mock.calls[0]?.[1]).toMatchObject({
      isolationLevel: "Serializable",
    });
  });

  it("fails the bounded page when the final exact classifier loses a row", async () => {
    const query = vi
      .fn()
      .mockResolvedValueOnce([
        { id: "visit-twin-1", createdAt: new Date("2026-07-20T00:00:00Z") },
      ])
      .mockResolvedValueOnce([]);
    const transaction = vi.fn(
      async (callback: (tx: { $queryRaw: typeof query }) => Promise<unknown>) =>
        callback({ $queryRaw: query }),
    );

    await expect(
      readTemplateTwinVisibleVisitPage({
        db: { $transaction: transaction } as unknown as TransactionHost,
        actorUserId: "doctor-1",
        query: { take: 1 },
        hydrate: async () => [{ id: "visit-twin-1" }],
      }),
    ).rejects.toBeInstanceOf(TemplateTwinVisitReadAuthorityError);
  });

  it("rejects unbounded page requests", async () => {
    const query = vi.fn();
    await expect(
      listTemplateTwinVisibleVisitPage({
        db: { $queryRaw: query },
        actorUserId: "doctor-1",
        query: { take: 257 },
      }),
    ).rejects.toBeInstanceOf(RangeError);
    expect(query).not.toHaveBeenCalled();
  });

  it("requires the final required-audit claim to retain exact Twin tenant identity", async () => {
    const db = { $queryRaw: vi.fn().mockResolvedValue([twinRow()]) };

    await expect(
      requireTemplateTwinVisitReadAuthority({
        db,
        visitId: "visit-twin-1",
        actorUserId: "doctor-1",
        expectedPracticeId: "practice-other",
        requireTemplateTwin: true,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinVisitReadAuthorityError);

    db.$queryRaw.mockResolvedValue([
      {
        visitId: "visit-twin-1",
        isTemplateTwin: false,
        isSyntheticTemplateTwin: false,
        isInternalPreCertification: false,
        authorized: true,
        practiceId: null,
        templateTwinEnabled: null,
      },
    ]);
    await expect(
      requireTemplateTwinVisitReadAuthority({
        db,
        visitId: "visit-twin-1",
        actorUserId: "doctor-1",
        expectedPracticeId: "practice-current",
        requireTemplateTwin: true,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinVisitReadAuthorityError);
  });

  it("pins every durable marker and current lifecycle predicate in the SQL boundary", async () => {
    const query = vi.fn().mockResolvedValue([twinRow()]);
    await inspectTemplateTwinVisitReads({
      db: { $queryRaw: query },
      visitIds: ["visit-twin-1"],
      actorUserId: "doctor-1",
    });

    const sql = query.mock.calls[0]?.[0];
    const text = sql?.strings?.join(" ") ?? "";
    expect(text).toContain('actor."role"');
    expect(text).toContain('actor."isActive"');
    expect(text).toContain('actor."deactivatedAt"');
    expect(text).toContain('actor."suspendedAt"');
    expect(text).toContain('actor."softDeletedAt"');
    expect(text).toContain("'TRANSCRIBE_MD'::\"Product\"");
    expect(text).toContain('practice."isActive"');
    expect(text).toContain('scoped_patient."externalId"');
    expect(text).toContain("SYNTHETIC-QA-ONLY");
    expect(text).toContain('COALESCE(scoped."templateKind"');
    expect(text).toContain(
      'compiled_provenance."noteTemplateId" = scoped."noteTemplateId"',
    );
    expect(text).toContain('classified."scopedPatientId" IS NOT NULL');
    expect(text).toContain('"template_twin_fill_manifests"');
    expect(text).toContain('"template_twin_synthetic_qa_runs"');
    expect(text).toContain('"template_twin_synthetic_qa_admissions"');
    expect(text).toContain('"template_twin_provider_executions"');
    expect(text).toContain('"preCertificationVoiceEvidence" = TRUE');
    expect(text).toContain('run_admission."id" = run."admissionId"');
    expect(text).toContain(
      'run_parent."id" = run_admission."parentAdmissionId"',
    );
    expect(text).toContain("execution.\"providerMode\" = 'LIVE'");
    expect(text).toContain("execution.\"providerMode\" <> 'LIVE'");
    expect(text).toContain('execution_compiled."noteTemplateId"');
    expect(text).toContain('execution_source."practiceId"');
    expect(text).toContain('source."practiceId"');
    expect(text).toContain('patient."practiceId"');
    expect(text).toContain('IS DISTINCT FROM classified."practiceId"');
  });

  it("treats compiled-version existence as durable Twin provenance across every query-native read", async () => {
    const query = vi.fn().mockResolvedValue([]);
    const db = { $queryRaw: query };

    await inspectTemplateTwinVisitReads({
      db,
      visitIds: ["visit-kind-drift"],
      actorUserId: "doctor-1",
    });
    await listTemplateTwinVisibleVisitPage({
      db,
      actorUserId: "doctor-1",
      query: { take: 10 },
    });
    await aggregateTemplateTwinVisibleVisits({
      db,
      actorUserId: "doctor-1",
    });
    await listTemplateTwinVisibleVisitIdentities({
      db,
      actorUserId: "doctor-1",
    });

    const sqlTexts = query.mock.calls.map(
      (call) => call[0]?.strings?.join(" ") ?? "",
    );
    expect(sqlTexts[0]).toContain(
      'compiled_provenance."noteTemplateId" = scoped."noteTemplateId"',
    );
    for (const text of sqlTexts.slice(1)) {
      expect(text).toContain(
        'provenance_compiled."noteTemplateId" = visit."noteTemplateId"',
      );
      expect(text).toContain(
        "current_template.\"templateKind\" = 'template_twin_docx'",
      );
    }
  });

  it("performs a final serializable practice/actor/visit locked recheck for polling", async () => {
    const query = vi
      .fn()
      .mockResolvedValueOnce([{ id: "practice-current" }])
      .mockResolvedValueOnce([{ id: "doctor-1" }])
      .mockResolvedValueOnce([{ id: "visit-twin-1" }])
      .mockResolvedValueOnce([twinRow()]);
    const transaction = vi.fn(
      async (
        callback: (tx: { $queryRaw: typeof query }) => Promise<unknown>,
        options?: unknown,
      ) => {
        void options;
        return callback({ $queryRaw: query });
      },
    );

    await expect(
      reassertTemplateTwinVisitReadAuthority({
        db: { $transaction: transaction } as unknown as TransactionHost,
        visitId: "visit-twin-1",
        actorUserId: "doctor-1",
        expectedPracticeId: "practice-current",
      }),
    ).resolves.toMatchObject({
      visitId: "visit-twin-1",
      isTemplateTwin: true,
      isSyntheticTemplateTwin: false,
      practiceId: "practice-current",
    });

    expect(transaction.mock.calls[0]?.[1]).toMatchObject({
      isolationLevel: "Serializable",
    });
    const lockSql = query.mock.calls
      .slice(0, 3)
      .map((call) => call[0]?.strings?.join(" ") ?? "")
      .join("\n");
    expect(lockSql).toContain('FROM "practices"');
    expect(lockSql).toContain('FROM "users"');
    expect(lockSql).toContain('FROM "transcribe_visits"');
    expect(lockSql).toContain("FOR SHARE");
  });

  it("does not complete a polling read when the final current-actor lock is lost", async () => {
    const query = vi
      .fn()
      .mockResolvedValueOnce([{ id: "practice-current" }])
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([{ id: "visit-twin-1" }]);
    const transaction = vi.fn(
      async (
        callback: (tx: { $queryRaw: typeof query }) => Promise<unknown>,
        options?: unknown,
      ) => {
        void options;
        return callback({ $queryRaw: query });
      },
    );

    await expect(
      reassertTemplateTwinVisitReadAuthority({
        db: { $transaction: transaction } as unknown as TransactionHost,
        visitId: "visit-twin-1",
        actorUserId: "doctor-1",
        expectedPracticeId: "practice-current",
      }),
    ).rejects.toBeInstanceOf(TemplateTwinVisitReadAuthorityError);
    expect(query).toHaveBeenCalledTimes(3);
  });

  it("returns only a fixed PHI-free denial", () => {
    const error = new TemplateTwinVisitReadAuthorityError();
    expect(error).toMatchObject({
      code: "TEMPLATE_TWIN_VISIT_READ_NOT_AUTHORIZED",
      message: "The requested visit is not available.",
    });
    expect(JSON.stringify(error)).not.toMatch(
      /patient|soap|transcript|audio|practice-current|doctor-1/i,
    );
  });
});
