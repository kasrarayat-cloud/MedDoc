// ============================================================================
// Template lifecycle server actions (Phase 2b). prisma + auth mocked; the PHI
// gate + normalize are REAL. Proves the load-bearing invariants:
//   - activation supersede is transactional + deactivates the prior active
//     BEFORE setting the new one active (index-safe ordering)
//   - every read/write is DOCTOR-SCOPED (doctorId in the where; not-owned →
//     error, no writes)
//   - editing an ACTIVE row creates a NEW version (live row never mutated);
//     editing a draft updates in place
//   - the deterministic PHI gate re-runs on save (structural PHI → reject)
// ============================================================================

import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findFirst: vi.fn(),
  findActor: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  updateMany: vi.fn(),
  deleteMany: vi.fn(),
  executeRaw: vi.fn(),
  queryRaw: vi.fn(),
  requireSession: vi.fn(),
}));

vi.mock("@meddoc/db", () => {
  const noteTemplate = {
    findFirst: mocks.findFirst,
    create: mocks.create,
    update: mocks.update,
    updateMany: mocks.updateMany,
    deleteMany: mocks.deleteMany,
  };
  const prisma = {
    noteTemplate,
    user: { findFirst: mocks.findActor },
    // Run the callback synchronously with a tx that shares the same mocks.
    $transaction: async (fn: (tx: unknown) => unknown) =>
      fn({
        noteTemplate,
        $executeRaw: mocks.executeRaw,
        $queryRaw: mocks.queryRaw,
      }),
  };
  return { default: prisma, prisma };
});
vi.mock("@/lib/auth", () => ({ requireSession: mocks.requireSession }));
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));

import {
  saveNoteTemplateAction,
  activateNoteTemplateAction,
  duplicateNoteTemplateAction,
  deleteNoteTemplateAction,
  getNoteTemplateForEditAction,
} from "../note-template-lifecycle";

const CUID = "cjld2cjxh0000qzrmn831i7rn";
const DOCTOR = "doc1";
const PRACTICE = "p1";

function currentAuthorityWhere() {
  return {
    doctorId: DOCTOR,
    doctor: {
      is: {
        id: DOCTOR,
        practiceId: PRACTICE,
        role: "DOCTOR",
        isActive: true,
        deactivatedAt: null,
        suspendedAt: null,
        softDeletedAt: null,
        products: { has: "TRANSCRIBE_MD" },
        practice: { is: { id: PRACTICE, isActive: true } },
      },
    },
  };
}

function bridgeExclusion() {
  return {
    templateKind: { not: "template_twin_docx" },
    templateTwinCompiledVersion: { is: null },
  };
}

function input(over: Record<string, unknown> = {}) {
  return {
    name: "My Format",
    encounterType: "orthopedics",
    sections: [
      {
        key: "subjective",
        label: "Subjective",
        order: 1,
        formatHint: "prose",
        styleInstructions: "Interval hx.",
        defaultText: null,
      },
      {
        key: "objective",
        label: "Exam",
        order: 2,
        formatHint: "bullets",
        styleInstructions: "By region.",
        defaultText: null,
      },
    ],
    styleProfile: { tense: "past", tone: "concise", abbreviations: null },
    ...over,
  };
}

function activationRow(over: Record<string, unknown> = {}) {
  const safe = input();
  return {
    id: CUID,
    name: safe.name,
    encounterType: "cardiology",
    sections: safe.sections,
    styleProfile: safe.styleProfile,
    templateKind: "structured",
    ...over,
  };
}

function duplicateSource(over: Record<string, unknown> = {}) {
  return {
    id: CUID,
    name: "Ortho",
    encounterType: "orthopedics",
    sections: [],
    styleProfile: {},
    specialtyBaseline: null,
    templateKind: "structured",
    version: 3,
    updatedAt: new Date("2026-07-20T00:00:00.000Z"),
    ...over,
  };
}

function rawSql(args: unknown[]): string {
  const strings = args[0];
  return Array.isArray(strings) ? strings.join(" ? ") : String(strings);
}

function defaultRawResult(sql: string): unknown[] {
  if (sql.includes('FROM "practices" practice')) return [{ id: PRACTICE }];
  if (sql.includes('FROM "users" actor')) return [{ id: DOCTOR }];
  if (sql.includes('template."specialtyBaseline"')) return [duplicateSource()];
  if (sql.includes('template."sections"')) return [activationRow()];
  return [{ id: CUID }];
}

function overrideRawResult(pattern: string, result: unknown[]): void {
  mocks.queryRaw.mockImplementation(async (...args: unknown[]) => {
    const sql = rawSql(args);
    return sql.includes(pattern) ? result : defaultRawResult(sql);
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  delete process.env.TEMPLATE_TWIN_RUNTIME_MODE;
  mocks.requireSession.mockResolvedValue({
    user: { id: DOCTOR, practiceId: PRACTICE },
  });
  mocks.findActor.mockResolvedValue({ id: DOCTOR, practiceId: PRACTICE });
  mocks.create.mockResolvedValue({ id: "created-id" });
  mocks.update.mockResolvedValue({ id: "updated-id" });
  mocks.updateMany.mockResolvedValue({ count: 1 });
  mocks.executeRaw.mockResolvedValue(1);
  mocks.queryRaw.mockImplementation(async (...args: unknown[]) =>
    defaultRawResult(rawSql(args)),
  );
});

describe("current lifecycle authority", () => {
  it("fails every action closed before template reads when the current actor is revoked", async () => {
    mocks.findActor.mockResolvedValue(null);

    const results = await Promise.all([
      saveNoteTemplateAction(input(), false),
      activateNoteTemplateAction(CUID),
      duplicateNoteTemplateAction(CUID),
      deleteNoteTemplateAction(CUID),
      getNoteTemplateForEditAction(CUID),
    ]);

    expect(results.every((result) => !result.ok)).toBe(true);
    expect(mocks.findActor).toHaveBeenCalledTimes(5);
    expect(mocks.findFirst).not.toHaveBeenCalled();
    expect(mocks.create).not.toHaveBeenCalled();
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.deleteMany).not.toHaveBeenCalled();
  });

  it.each([
    {
      label: "save",
      setup: () => undefined,
      run: () => saveNoteTemplateAction(input(), false),
      wrote: () => mocks.create.mock.calls.length > 0,
    },
    {
      label: "activate",
      setup: () => mocks.findFirst.mockResolvedValue(activationRow()),
      run: () => activateNoteTemplateAction(CUID),
      wrote: () => mocks.updateMany.mock.calls.length > 0,
    },
    {
      label: "duplicate",
      setup: () => mocks.findFirst.mockResolvedValue(duplicateSource()),
      run: () => duplicateNoteTemplateAction(CUID),
      wrote: () => mocks.create.mock.calls.length > 0,
    },
    {
      label: "delete",
      setup: () =>
        mocks.findFirst.mockResolvedValue({ templateKind: "structured" }),
      run: () => deleteNoteTemplateAction(CUID),
      wrote: () => mocks.deleteMany.mock.calls.length > 0,
    },
  ])(
    "blocks $label when authority is revoked between admission and the mutation lock",
    async ({ setup, run, wrote }) => {
      setup();
      overrideRawResult('FROM "users" actor', []);

      const result = await run();

      expect(result).toMatchObject({
        ok: false,
        error: expect.stringMatching(/current physician access/i),
      });
      expect(wrote()).toBe(false);
      expect(mocks.queryRaw).toHaveBeenCalledTimes(2);
    },
  );

  it("binds current actor, practice, lifecycle, role, and product into every template read", async () => {
    mocks.findFirst.mockResolvedValue(null);

    await getNoteTemplateForEditAction(CUID);

    expect(mocks.findFirst).toHaveBeenCalledWith(
      expect.objectContaining({
        where: {
          id: CUID,
          ...currentAuthorityWhere(),
          ...bridgeExclusion(),
        },
      }),
    );
  });

  it("rechecks the locked activation content before either status mutation", async () => {
    mocks.findFirst.mockResolvedValue(activationRow());
    overrideRawResult('template."sections"', [
      activationRow({ name: "Patient Synthetic Person" }),
    ]);

    const result = await activateNoteTemplateAction(CUID);

    expect(result).toMatchObject({
      ok: false,
      error: expect.stringMatching(/populated|patient-like/i),
    });
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });
});

describe("saveNoteTemplateAction — draft (new)", () => {
  it("creates a draft v1 scoped to the doctor, with NO deactivate", async () => {
    const r = await saveNoteTemplateAction(input(), false);
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.status).toBe("draft");
    const data = mocks.create.mock.calls[0][0].data;
    expect(data.doctorId).toBe(DOCTOR);
    expect(data.status).toBe("draft");
    expect(data.version).toBe(1);
    expect(data.isSystemDefault).toBe(false);
    expect(data.lineageId).toEqual(expect.any(String));
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });
});

describe("saveNoteTemplateAction — activate (new)", () => {
  it("deactivates the prior active BEFORE creating the active row (index-safe)", async () => {
    const r = await saveNoteTemplateAction(input(), true);
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.status).toBe("active");

    // deactivate prior active, scoped to doctor + this encounterType
    expect(mocks.updateMany).toHaveBeenCalledWith({
      where: {
        ...currentAuthorityWhere(),
        encounterType: "orthopedics",
        status: "active",
        ...bridgeExclusion(),
      },
      data: { status: "inactive" },
    });
    expect(mocks.create.mock.calls[0][0].data.status).toBe("active");
    // ORDER: updateMany (deactivate) ran before create (activate)
    expect(mocks.updateMany.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.create.mock.invocationCallOrder[0],
    );
  });

  it("a catch-all (encounterType null) deactivates only the null slot", async () => {
    await saveNoteTemplateAction(input({ encounterType: null }), true);
    expect(mocks.updateMany).toHaveBeenCalledWith({
      where: {
        ...currentAuthorityWhere(),
        encounterType: null,
        status: "active",
        ...bridgeExclusion(),
      },
      data: { status: "inactive" },
    });
  });
});

describe("saveNoteTemplateAction — editing an ACTIVE row → new version", () => {
  it("creates version+1 (live row not mutated) and supersedes the old", async () => {
    mocks.findFirst.mockResolvedValue({
      id: CUID,
      status: "active",
      version: 3,
      lineageId: "lineage-1",
      templateKind: "structured",
    });
    // Model the database truth that the admitted `active` source can only be
    // locked before the active-slot update changes it to `inactive`.
    const r = await saveNoteTemplateAction(input({ id: CUID }), true);
    expect(r.ok).toBe(true);
    expect(mocks.update).not.toHaveBeenCalled(); // never mutate the live row
    expect(mocks.queryRaw).toHaveBeenCalledTimes(3);
    expect(mocks.create.mock.calls[0][0].data.version).toBe(4);
    expect(mocks.create.mock.calls[0][0].data.status).toBe("active");
    expect(mocks.create.mock.calls[0][0].data.lineageId).toBe("lineage-1");
    expect(mocks.create.mock.calls[0][0].data.parentVersionId).toBe(CUID);
    expect(mocks.updateMany).toHaveBeenCalled(); // supersede the old active
    expect(mocks.queryRaw.mock.invocationCallOrder[2]).toBeLessThan(
      mocks.updateMany.mock.invocationCallOrder[0],
    );
    expect(mocks.executeRaw).not.toHaveBeenCalled();
  });

  it("self-roots a transitional null parent before creating its child version", async () => {
    mocks.findFirst.mockResolvedValue({
      id: CUID,
      status: "active",
      version: 3,
      lineageId: null,
      templateKind: "structured",
    });

    const r = await saveNoteTemplateAction(input({ id: CUID }), true);

    expect(r.ok).toBe(true);
    expect(mocks.executeRaw).toHaveBeenCalledOnce();
    const rawCall = mocks.executeRaw.mock.calls[0];
    expect(rawCall?.[1]).toBe(CUID);
    expect(rawCall?.[2]).toBe(CUID);
    const created = mocks.create.mock.calls[0][0].data;
    expect(created.lineageId).toBe(CUID);
    expect(created.parentVersionId).toBe(CUID);
  });
});

describe("saveNoteTemplateAction — editing a DRAFT → update in place", () => {
  it("updates the existing draft, no new version, no deactivate", async () => {
    mocks.findFirst.mockResolvedValue({
      id: CUID,
      status: "draft",
      version: 2,
      lineageId: "lineage-1",
      templateKind: "structured",
    });
    const r = await saveNoteTemplateAction(input({ id: CUID }), false);
    expect(r.ok).toBe(true);
    expect(mocks.updateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: {
          id: CUID,
          ...currentAuthorityWhere(),
          status: "draft",
          version: 2,
          ...bridgeExclusion(),
        },
        data: expect.objectContaining({ status: "draft" }),
      }),
    );
    expect(mocks.create).not.toHaveBeenCalled();
    expect(mocks.updateMany).toHaveBeenCalledTimes(1);
  });
});

describe("saveNoteTemplateAction — doctor-scoping", () => {
  it("refuses to edit a row that is not the doctor’s (findFirst scoped, returns null)", async () => {
    mocks.findFirst.mockResolvedValue(null); // not found under {id, doctorId}
    const r = await saveNoteTemplateAction(input({ id: CUID }), true);
    expect(r.ok).toBe(false);
    expect(mocks.findFirst.mock.calls[0][0].where).toEqual({
      id: CUID,
      ...currentAuthorityWhere(),
      ...bridgeExclusion(),
    });
    expect(mocks.create).not.toHaveBeenCalled();
    expect(mocks.update).not.toHaveBeenCalled();
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });
});

describe("saveNoteTemplateAction — PHI re-scrub on doctor edits", () => {
  it("REJECTS structural-field PHI (no write happens)", async () => {
    const bad = input();
    (bad.sections[0] as Record<string, unknown>).label = "Encounter 2026-01-02";
    const r = await saveNoteTemplateAction(bad, true);
    expect(r.ok).toBe(false);
    expect(mocks.create).not.toHaveBeenCalled();
  });

  it("rejects every populated default before persistence", async () => {
    const bad = input();
    (bad.sections[1] as Record<string, unknown>).defaultText =
      "Seen 01/02/2026; BP fine.";
    const r = await saveNoteTemplateAction(bad, false);
    expect(r).toMatchObject({
      ok: false,
      error: expect.stringMatching(/populated|patient-like/i),
    });
    expect(mocks.create).not.toHaveBeenCalled();
  });

  it.each([
    ["an unstructured patient name", { name: "Patient Synthetic Person" }],
    [
      "patient narrative",
      {
        sections: [
          {
            key: "subjective",
            label: "Subjective",
            order: 1,
            formatHint: "prose",
            styleInstructions: "Patient reports worsening pain.",
            defaultText: null,
          },
        ],
      },
    ],
    ["a clinical value", { name: "Blood pressure 138/88" }],
  ])("rejects %s before any write", async (_label, over) => {
    const r = await saveNoteTemplateAction(input(over), true);
    expect(r).toMatchObject({
      ok: false,
      error: expect.stringMatching(/populated|patient-like/i),
    });
    expect(mocks.findFirst).not.toHaveBeenCalled();
    expect(mocks.create).not.toHaveBeenCalled();
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });
});

describe("activateNoteTemplateAction", () => {
  it("deactivates prior active (excluding self) then sets active — scoped", async () => {
    mocks.findFirst.mockResolvedValue(activationRow());
    const r = await activateNoteTemplateAction(CUID);
    expect(r.ok).toBe(true);
    expect(mocks.findFirst.mock.calls[0][0].where).toEqual({
      id: CUID,
      ...currentAuthorityWhere(),
      ...bridgeExclusion(),
    });
    expect(mocks.updateMany).toHaveBeenCalledWith({
      where: {
        ...currentAuthorityWhere(),
        encounterType: "cardiology",
        status: "active",
        NOT: { id: CUID },
        ...bridgeExclusion(),
      },
      data: { status: "inactive" },
    });
    expect(mocks.updateMany).toHaveBeenLastCalledWith({
      where: {
        id: CUID,
        ...currentAuthorityWhere(),
        ...bridgeExclusion(),
      },
      data: { status: "active" },
    });
    expect(mocks.updateMany.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.updateMany.mock.invocationCallOrder[1],
    );
  });

  it("refuses a row that is not the doctor’s", async () => {
    mocks.findFirst.mockResolvedValue(null);
    const r = await activateNoteTemplateAction(CUID);
    expect(r.ok).toBe(false);
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });

  it("refuses to activate a stored template containing patient-like content", async () => {
    mocks.findFirst.mockResolvedValue(
      activationRow({ name: "Patient Synthetic Person" }),
    );

    const r = await activateNoteTemplateAction(CUID);

    expect(r).toMatchObject({
      ok: false,
      error: expect.stringMatching(/populated|patient-like/i),
    });
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });
});

describe("deleteNoteTemplateAction", () => {
  it("scoped deleteMany; count 0 → error, count 1 → ok", async () => {
    mocks.findFirst.mockResolvedValue({ templateKind: "structured" });
    mocks.deleteMany.mockResolvedValueOnce({ count: 0 });
    expect((await deleteNoteTemplateAction(CUID)).ok).toBe(false);
    expect(mocks.deleteMany.mock.calls[0][0]).toEqual({
      where: {
        id: CUID,
        ...currentAuthorityWhere(),
        ...bridgeExclusion(),
      },
    });

    mocks.deleteMany.mockResolvedValueOnce({ count: 1 });
    expect((await deleteNoteTemplateAction(CUID)).ok).toBe(true);
  });
});

describe("duplicateNoteTemplateAction", () => {
  it('copies an owned row as a fresh draft v1 with a "(copy)" name', async () => {
    const source = duplicateSource();
    mocks.findFirst.mockResolvedValue(source);
    const r = await duplicateNoteTemplateAction(CUID);
    expect(r.ok).toBe(true);
    expect(mocks.findFirst.mock.calls[0][0].where).toEqual({
      id: CUID,
      ...currentAuthorityWhere(),
      ...bridgeExclusion(),
    });
    const data = mocks.create.mock.calls[0][0].data;
    expect(data.name).toBe("Ortho (copy)");
    expect(data.status).toBe("draft");
    expect(data.version).toBe(1);
    expect(data.doctorId).toBe(DOCTOR);
    expect(data.lineageId).toEqual(expect.any(String));
    expect(mocks.queryRaw).toHaveBeenCalledTimes(3);
  });

  it("fails when the source owner, kind, version, or content changes before duplicate create", async () => {
    process.env.TEMPLATE_TWIN_RUNTIME_MODE = "live-v1";
    mocks.findFirst.mockResolvedValue({
      id: CUID,
      name: "Ortho",
      encounterType: "orthopedics",
      sections: [],
      styleProfile: {},
      specialtyBaseline: null,
      templateKind: "structured",
      version: 3,
      updatedAt: new Date("2026-07-20T00:00:00.000Z"),
    });
    overrideRawResult('template."specialtyBaseline"', []);

    await expect(duplicateNoteTemplateAction(CUID)).resolves.toMatchObject({
      ok: false,
    });
    expect(mocks.create).not.toHaveBeenCalled();
  });
});

describe("getNoteTemplateForEditAction", () => {
  it("returns a scoped row mapped to the review model; null → error", async () => {
    mocks.findFirst.mockResolvedValueOnce({
      id: CUID,
      name: "Ortho",
      encounterType: "orthopedics",
      sections: [
        {
          key: "subjective",
          label: "S",
          order: 1,
          formatHint: "prose",
          styleInstructions: null,
          defaultText: null,
          defaultTextMode: "omit_unless_supported",
        },
      ],
      styleProfile: { tense: "past", tone: "concise", abbreviations: null },
      templateKind: "structured",
    });
    const r = await getNoteTemplateForEditAction(CUID);
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.template.id).toBe(CUID);
      expect(r.template.sections[0].label).toBe("S");
    }
    expect(mocks.findFirst.mock.calls[0][0].where).toEqual({
      id: CUID,
      ...currentAuthorityWhere(),
      ...bridgeExclusion(),
    });

    mocks.findFirst.mockResolvedValueOnce(null);
    expect((await getNoteTemplateForEditAction(CUID)).ok).toBe(false);
  });
});

describe("Template Twin isolation from legacy lifecycle actions", () => {
  it("server-excludes kind-drifted rows that retain immutable compiled lineage", async () => {
    // Prisma applies this relation predicate before returning a row; null
    // models a compiled row being absent from every generic lifecycle lookup.
    mocks.findFirst.mockResolvedValue(null);

    expect((await saveNoteTemplateAction(input({ id: CUID }), false)).ok).toBe(
      false,
    );
    expect((await activateNoteTemplateAction(CUID)).ok).toBe(false);
    expect((await duplicateNoteTemplateAction(CUID)).ok).toBe(false);
    expect((await deleteNoteTemplateAction(CUID)).ok).toBe(false);
    expect((await getNoteTemplateForEditAction(CUID)).ok).toBe(false);

    expect(mocks.findFirst).toHaveBeenCalledTimes(5);
    for (const [args] of mocks.findFirst.mock.calls) {
      expect(args.where).toEqual(
        expect.objectContaining({
          templateKind: { not: "template_twin_docx" },
          templateTwinCompiledVersion: { is: null },
        }),
      );
    }
    expect(mocks.create).not.toHaveBeenCalled();
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.deleteMany).not.toHaveBeenCalled();
  });

  it("refuses legacy edit, activation, duplication, deletion, and editor hydration", async () => {
    mocks.findFirst.mockResolvedValue({
      id: CUID,
      status: "draft",
      version: 1,
      lineageId: "twin-lineage",
      encounterType: "primary-care",
      templateKind: "template_twin_docx",
      name: "Twin",
      sections: [],
      styleProfile: {},
      specialtyBaseline: null,
    });

    expect((await saveNoteTemplateAction(input({ id: CUID }), false)).ok).toBe(
      false,
    );
    expect((await activateNoteTemplateAction(CUID)).ok).toBe(false);
    expect((await duplicateNoteTemplateAction(CUID)).ok).toBe(false);
    expect((await deleteNoteTemplateAction(CUID)).ok).toBe(false);
    expect((await getNoteTemplateForEditAction(CUID)).ok).toBe(false);

    expect(mocks.update).not.toHaveBeenCalled();
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.deleteMany).not.toHaveBeenCalled();
  });

  it("server-excludes Twin rows while ordinary lifecycle actions continue in bridge mode", async () => {
    process.env.TEMPLATE_TWIN_RUNTIME_MODE = "rollback-compat-v2";
    mocks.findFirst.mockResolvedValue(activationRow());

    await expect(activateNoteTemplateAction(CUID)).resolves.toMatchObject({
      ok: true,
    });
    expect(mocks.findFirst).toHaveBeenCalledWith(
      expect.objectContaining({
        where: {
          id: CUID,
          ...currentAuthorityWhere(),
          ...bridgeExclusion(),
        },
      }),
    );
    expect(mocks.updateMany).toHaveBeenCalledWith({
      where: {
        ...currentAuthorityWhere(),
        encounterType: "cardiology",
        status: "active",
        NOT: { id: CUID },
        ...bridgeExclusion(),
      },
      data: { status: "inactive" },
    });
  });

  it("fails closed and server-excludes Twin rows for an invalid runtime mode", async () => {
    process.env.TEMPLATE_TWIN_RUNTIME_MODE = "legacy-image-bypass";
    mocks.findFirst.mockResolvedValue(activationRow());

    await expect(activateNoteTemplateAction(CUID)).resolves.toMatchObject({
      ok: true,
    });
    expect(mocks.findFirst).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          templateKind: { not: "template_twin_docx" },
          templateTwinCompiledVersion: { is: null },
        }),
      }),
    );
  });

  it("fails a runtime-enabled draft edit when owner or kind changes before the final update", async () => {
    process.env.TEMPLATE_TWIN_RUNTIME_MODE = "live-v1";
    mocks.findFirst.mockResolvedValue({
      id: CUID,
      status: "draft",
      version: 2,
      lineageId: "lineage-1",
      templateKind: "structured",
    });
    mocks.updateMany.mockResolvedValueOnce({ count: 0 });

    await expect(
      saveNoteTemplateAction(input({ id: CUID }), false),
    ).resolves.toMatchObject({ ok: false });
    expect(mocks.create).not.toHaveBeenCalled();
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it("fails runtime-enabled activation when the target becomes Twin before the final write", async () => {
    process.env.TEMPLATE_TWIN_RUNTIME_MODE = "live-v1";
    mocks.findFirst.mockResolvedValue(activationRow());
    mocks.updateMany
      .mockResolvedValueOnce({ count: 1 })
      .mockResolvedValueOnce({ count: 0 });

    await expect(activateNoteTemplateAction(CUID)).resolves.toMatchObject({
      ok: false,
    });
    expect(mocks.updateMany).toHaveBeenLastCalledWith({
      where: {
        id: CUID,
        ...currentAuthorityWhere(),
        ...bridgeExclusion(),
      },
      data: { status: "active" },
    });
  });

  it("fails active-version creation when the parent becomes Twin before it is locked", async () => {
    process.env.TEMPLATE_TWIN_RUNTIME_MODE = "live-v1";
    mocks.findFirst.mockResolvedValue({
      id: CUID,
      status: "active",
      version: 3,
      lineageId: "lineage-1",
      templateKind: "structured",
    });
    overrideRawResult('template."status"', []);

    await expect(
      saveNoteTemplateAction(input({ id: CUID }), false),
    ).resolves.toMatchObject({ ok: false });
    expect(mocks.create).not.toHaveBeenCalled();
  });
});
