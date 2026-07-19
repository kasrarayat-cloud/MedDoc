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

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  findFirst: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  updateMany: vi.fn(),
  deleteMany: vi.fn(),
  executeRaw: vi.fn(),
  requireSession: vi.fn(),
}));

vi.mock('@meddoc/db', () => {
  const noteTemplate = {
    findFirst: mocks.findFirst,
    create: mocks.create,
    update: mocks.update,
    updateMany: mocks.updateMany,
    deleteMany: mocks.deleteMany,
  };
  const prisma = {
    noteTemplate,
    // Run the callback synchronously with a tx that shares the same mocks.
    $transaction: async (fn: (tx: unknown) => unknown) =>
      fn({ noteTemplate, $executeRaw: mocks.executeRaw }),
  };
  return { default: prisma, prisma };
});
vi.mock('@/lib/auth', () => ({ requireSession: mocks.requireSession }));
vi.mock('next/cache', () => ({ revalidatePath: vi.fn() }));

import {
  saveNoteTemplateAction,
  activateNoteTemplateAction,
  duplicateNoteTemplateAction,
  deleteNoteTemplateAction,
  getNoteTemplateForEditAction,
} from '../note-template-lifecycle';

const CUID = 'cjld2cjxh0000qzrmn831i7rn';
const DOCTOR = 'doc1';

function input(over: Record<string, unknown> = {}) {
  return {
    name: 'My Format',
    encounterType: 'orthopedics',
    sections: [
      { key: 'subjective', label: 'Subjective', order: 1, formatHint: 'prose', styleInstructions: 'Interval hx.', defaultText: null },
      { key: 'objective', label: 'Exam', order: 2, formatHint: 'bullets', styleInstructions: 'By region.', defaultText: 'Normal gait. No effusion.' },
    ],
    styleProfile: { tense: 'past', tone: 'concise', abbreviations: null },
    ...over,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  delete process.env.TEMPLATE_TWIN_RUNTIME_MODE;
  mocks.requireSession.mockResolvedValue({ user: { id: DOCTOR, practiceId: 'p1' } });
  mocks.create.mockResolvedValue({ id: 'created-id' });
  mocks.update.mockResolvedValue({ id: 'updated-id' });
  mocks.updateMany.mockResolvedValue({ count: 1 });
  mocks.executeRaw.mockResolvedValue(1);
});

describe('saveNoteTemplateAction — draft (new)', () => {
  it('creates a draft v1 scoped to the doctor, with NO deactivate', async () => {
    const r = await saveNoteTemplateAction(input(), false);
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.status).toBe('draft');
    const data = mocks.create.mock.calls[0][0].data;
    expect(data.doctorId).toBe(DOCTOR);
    expect(data.status).toBe('draft');
    expect(data.version).toBe(1);
    expect(data.isSystemDefault).toBe(false);
    expect(data.lineageId).toEqual(expect.any(String));
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });
});

describe('saveNoteTemplateAction — activate (new)', () => {
  it('deactivates the prior active BEFORE creating the active row (index-safe)', async () => {
    const r = await saveNoteTemplateAction(input(), true);
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.status).toBe('active');

    // deactivate prior active, scoped to doctor + this encounterType
    expect(mocks.updateMany).toHaveBeenCalledWith({
      where: { doctorId: DOCTOR, encounterType: 'orthopedics', status: 'active' },
      data: { status: 'inactive' },
    });
    expect(mocks.create.mock.calls[0][0].data.status).toBe('active');
    // ORDER: updateMany (deactivate) ran before create (activate)
    expect(mocks.updateMany.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.create.mock.invocationCallOrder[0],
    );
  });

  it('a catch-all (encounterType null) deactivates only the null slot', async () => {
    await saveNoteTemplateAction(input({ encounterType: null }), true);
    expect(mocks.updateMany).toHaveBeenCalledWith({
      where: { doctorId: DOCTOR, encounterType: null, status: 'active' },
      data: { status: 'inactive' },
    });
  });
});

describe('saveNoteTemplateAction — editing an ACTIVE row → new version', () => {
  it('creates version+1 (live row not mutated) and supersedes the old', async () => {
    mocks.findFirst.mockResolvedValue({
      id: CUID,
      status: 'active',
      version: 3,
      lineageId: 'lineage-1',
      templateKind: 'structured',
    });
    const r = await saveNoteTemplateAction(input({ id: CUID }), true);
    expect(r.ok).toBe(true);
    expect(mocks.update).not.toHaveBeenCalled(); // never mutate the live row
    expect(mocks.create.mock.calls[0][0].data.version).toBe(4);
    expect(mocks.create.mock.calls[0][0].data.status).toBe('active');
    expect(mocks.create.mock.calls[0][0].data.lineageId).toBe('lineage-1');
    expect(mocks.create.mock.calls[0][0].data.parentVersionId).toBe(CUID);
    expect(mocks.updateMany).toHaveBeenCalled(); // supersede the old active
    expect(mocks.executeRaw).not.toHaveBeenCalled();
  });

  it('self-roots a transitional null parent before creating its child version', async () => {
    mocks.findFirst.mockResolvedValue({
      id: CUID,
      status: 'active',
      version: 3,
      lineageId: null,
      templateKind: 'structured',
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

describe('saveNoteTemplateAction — editing a DRAFT → update in place', () => {
  it('updates the existing draft, no new version, no deactivate', async () => {
    mocks.findFirst.mockResolvedValue({
      id: CUID,
      status: 'draft',
      version: 2,
      lineageId: 'lineage-1',
      templateKind: 'structured',
    });
    const r = await saveNoteTemplateAction(input({ id: CUID }), false);
    expect(r.ok).toBe(true);
    expect(mocks.update).toHaveBeenCalledWith(
      expect.objectContaining({ where: { id: CUID }, data: expect.objectContaining({ status: 'draft' }) }),
    );
    expect(mocks.create).not.toHaveBeenCalled();
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });
});

describe('saveNoteTemplateAction — doctor-scoping', () => {
  it('refuses to edit a row that is not the doctor’s (findFirst scoped, returns null)', async () => {
    mocks.findFirst.mockResolvedValue(null); // not found under {id, doctorId}
    const r = await saveNoteTemplateAction(input({ id: CUID }), true);
    expect(r.ok).toBe(false);
    expect(mocks.findFirst.mock.calls[0][0].where).toEqual({ id: CUID, doctorId: DOCTOR });
    expect(mocks.create).not.toHaveBeenCalled();
    expect(mocks.update).not.toHaveBeenCalled();
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });
});

describe('saveNoteTemplateAction — PHI re-scrub on doctor edits', () => {
  it('REJECTS structural-field PHI (no write happens)', async () => {
    const bad = input();
    (bad.sections[0] as Record<string, unknown>).label = 'Encounter 2026-01-02';
    const r = await saveNoteTemplateAction(bad, true);
    expect(r.ok).toBe(false);
    expect(mocks.create).not.toHaveBeenCalled();
  });

  it('SCRUBS a default-text PHI and still persists (flagged)', async () => {
    const bad = input();
    (bad.sections[1] as Record<string, unknown>).defaultText = 'Seen 01/02/2026; BP fine.';
    const r = await saveNoteTemplateAction(bad, false);
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.flags.length).toBeGreaterThan(0);
    const persisted = JSON.stringify(mocks.create.mock.calls[0][0].data.sections);
    expect(persisted).not.toContain('01/02/2026');
  });
});

describe('activateNoteTemplateAction', () => {
  it('deactivates prior active (excluding self) then sets active — scoped', async () => {
    mocks.findFirst.mockResolvedValue({
      id: CUID,
      encounterType: 'cardiology',
      templateKind: 'structured',
    });
    const r = await activateNoteTemplateAction(CUID);
    expect(r.ok).toBe(true);
    expect(mocks.findFirst.mock.calls[0][0].where).toEqual({ id: CUID, doctorId: DOCTOR });
    expect(mocks.updateMany).toHaveBeenCalledWith({
      where: { doctorId: DOCTOR, encounterType: 'cardiology', status: 'active', NOT: { id: CUID } },
      data: { status: 'inactive' },
    });
    expect(mocks.update).toHaveBeenCalledWith({ where: { id: CUID }, data: { status: 'active' } });
    expect(mocks.updateMany.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.update.mock.invocationCallOrder[0],
    );
  });

  it('refuses a row that is not the doctor’s', async () => {
    mocks.findFirst.mockResolvedValue(null);
    const r = await activateNoteTemplateAction(CUID);
    expect(r.ok).toBe(false);
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });
});

describe('deleteNoteTemplateAction', () => {
  it('scoped deleteMany; count 0 → error, count 1 → ok', async () => {
    mocks.findFirst.mockResolvedValue({ templateKind: 'structured' });
    mocks.deleteMany.mockResolvedValueOnce({ count: 0 });
    expect((await deleteNoteTemplateAction(CUID)).ok).toBe(false);
    expect(mocks.deleteMany.mock.calls[0][0]).toEqual({ where: { id: CUID, doctorId: DOCTOR } });

    mocks.deleteMany.mockResolvedValueOnce({ count: 1 });
    expect((await deleteNoteTemplateAction(CUID)).ok).toBe(true);
  });
});

describe('duplicateNoteTemplateAction', () => {
  it('copies an owned row as a fresh draft v1 with a "(copy)" name', async () => {
    mocks.findFirst.mockResolvedValue({
      name: 'Ortho', encounterType: 'orthopedics', sections: [], styleProfile: {}, specialtyBaseline: null,
      templateKind: 'structured',
    });
    const r = await duplicateNoteTemplateAction(CUID);
    expect(r.ok).toBe(true);
    const data = mocks.create.mock.calls[0][0].data;
    expect(data.name).toBe('Ortho (copy)');
    expect(data.status).toBe('draft');
    expect(data.version).toBe(1);
    expect(data.doctorId).toBe(DOCTOR);
    expect(data.lineageId).toEqual(expect.any(String));
  });
});

describe('getNoteTemplateForEditAction', () => {
  it('returns a scoped row mapped to the review model; null → error', async () => {
    mocks.findFirst.mockResolvedValueOnce({
      id: CUID, name: 'Ortho', encounterType: 'orthopedics',
      sections: [{ key: 'subjective', label: 'S', order: 1, formatHint: 'prose', styleInstructions: null, defaultText: null, defaultTextMode: 'omit_unless_supported' }],
      styleProfile: { tense: 'past', tone: 'concise', abbreviations: null },
      templateKind: 'structured',
    });
    const r = await getNoteTemplateForEditAction(CUID);
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.template.id).toBe(CUID);
      expect(r.template.sections[0].label).toBe('S');
    }
    expect(mocks.findFirst.mock.calls[0][0].where).toEqual({ id: CUID, doctorId: DOCTOR });

    mocks.findFirst.mockResolvedValueOnce(null);
    expect((await getNoteTemplateForEditAction(CUID)).ok).toBe(false);
  });
});

describe('Template Twin isolation from legacy lifecycle actions', () => {
  it('refuses legacy edit, activation, duplication, deletion, and editor hydration', async () => {
    mocks.findFirst.mockResolvedValue({
      id: CUID,
      status: 'draft',
      version: 1,
      lineageId: 'twin-lineage',
      encounterType: 'primary-care',
      templateKind: 'template_twin_docx',
      name: 'Twin',
      sections: [],
      styleProfile: {},
      specialtyBaseline: null,
    });

    expect((await saveNoteTemplateAction(input({ id: CUID }), false)).ok).toBe(false);
    expect((await activateNoteTemplateAction(CUID)).ok).toBe(false);
    expect((await duplicateNoteTemplateAction(CUID)).ok).toBe(false);
    expect((await deleteNoteTemplateAction(CUID)).ok).toBe(false);
    expect((await getNoteTemplateForEditAction(CUID)).ok).toBe(false);

    expect(mocks.update).not.toHaveBeenCalled();
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.deleteMany).not.toHaveBeenCalled();
  });

  it('server-excludes Twin rows while ordinary lifecycle actions continue in bridge mode', async () => {
    process.env.TEMPLATE_TWIN_RUNTIME_MODE = 'rollback-compat-v2';
    mocks.findFirst.mockResolvedValue({
      id: CUID,
      encounterType: 'cardiology',
      templateKind: 'structured',
    });

    await expect(activateNoteTemplateAction(CUID)).resolves.toMatchObject({
      ok: true,
    });
    expect(mocks.findFirst).toHaveBeenCalledWith(
      expect.objectContaining({
        where: {
          id: CUID,
          doctorId: DOCTOR,
          templateKind: { not: 'template_twin_docx' },
        },
      }),
    );
    expect(mocks.updateMany).toHaveBeenCalledWith({
      where: {
        doctorId: DOCTOR,
        encounterType: 'cardiology',
        status: 'active',
        NOT: { id: CUID },
        templateKind: { not: 'template_twin_docx' },
      },
      data: { status: 'inactive' },
    });
  });

  it('fails closed and server-excludes Twin rows for an invalid runtime mode', async () => {
    process.env.TEMPLATE_TWIN_RUNTIME_MODE = 'legacy-image-bypass';
    mocks.findFirst.mockResolvedValue({
      id: CUID,
      encounterType: 'cardiology',
      templateKind: 'structured',
    });

    await expect(activateNoteTemplateAction(CUID)).resolves.toMatchObject({
      ok: true,
    });
    expect(mocks.findFirst).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          templateKind: { not: 'template_twin_docx' },
        }),
      }),
    );
  });
});
