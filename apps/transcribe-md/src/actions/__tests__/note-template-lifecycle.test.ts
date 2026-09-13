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
  // R1: the delete fence counts referencing visits before deleting anything.
  visitCount: vi.fn(),
  findFirst: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  updateMany: vi.fn(),
  deleteMany: vi.fn(),
  requireSession: vi.fn(),
  logAudit: vi.fn(async () => {}),
}));

vi.mock('@meddoc/db', () => {
  const noteTemplate = {
    findFirst: mocks.findFirst,
    create: mocks.create,
    update: mocks.update,
    updateMany: mocks.updateMany,
    deleteMany: mocks.deleteMany,
  };
  const transcribeVisit = { count: mocks.visitCount };
  const prisma = {
    noteTemplate,
    transcribeVisit,
    // Run the callback synchronously with a tx that shares the same mocks.
    $transaction: async (fn: (tx: unknown) => unknown) => fn({ noteTemplate }),
  };
  return { default: prisma, prisma };
});
vi.mock('@/lib/auth', () => ({ requireSession: mocks.requireSession }));
// ⚠️ MOCKED FOR A REASON WORTH RECORDING. R1's audit writers made this action
// import `@/lib/audit`, which reaches `@/lib/nextauth` -> next-auth ->
// `next/server`. Unmocked, that chain fails to RESOLVE and the whole file stops
// COLLECTING — 0 tests run, which in a summary reads as "no failures". Mocking
// it also lets the audit rows be ASSERTED rather than merely tolerated.
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));
vi.mock('next/cache', () => ({ revalidatePath: vi.fn() }));

import {
  saveNoteTemplateAction,
  activateNoteTemplateAction,
  duplicateNoteTemplateAction,
  deleteNoteTemplateAction,
  archiveNoteTemplateAction,
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
  mocks.requireSession.mockResolvedValue({ user: { id: DOCTOR, practiceId: 'p1' } });
  mocks.create.mockResolvedValue({ id: 'created-id' });
  mocks.update.mockResolvedValue({ id: 'updated-id' });
  mocks.updateMany.mockResolvedValue({ count: 1 });
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
    // ⚠️ WHERE-AWARE: the ownership pre-check ({id, doctorId}) returns the active
    // row; the OWNER-RULE active-slot check ({doctorId, encounterType, status:'active'},
    // no id) finds NO active row (thus no certified sibling), so this edit still
    // activates as before. When a certified sibling DOES exist the save is held as
    // a draft — covered by gate-upload-never-displaces-certified.
    mocks.findFirst.mockImplementation(async ({ where }: { where: Record<string, unknown> }) =>
      where.id === undefined ? null : { id: CUID, status: 'active', version: 3 },
    );
    const r = await saveNoteTemplateAction(input({ id: CUID }), true);
    expect(r.ok).toBe(true);
    expect(mocks.update).not.toHaveBeenCalled(); // never mutate the live row
    expect(mocks.create.mock.calls[0][0].data.version).toBe(4);
    expect(mocks.create.mock.calls[0][0].data.status).toBe('active');
    expect(mocks.updateMany).toHaveBeenCalled(); // supersede the old active
  });
});

describe('saveNoteTemplateAction — editing a DRAFT → update in place', () => {
  it('updates the existing draft, no new version, no deactivate', async () => {
    mocks.findFirst.mockResolvedValue({ id: CUID, status: 'draft', version: 2 });
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
    mocks.findFirst.mockResolvedValue({ id: CUID, encounterType: 'cardiology' });
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
  // ⚠️ R1 CHANGED THIS CONTRACT ON PURPOSE. It was a bare scoped `deleteMany`,
  // and the FK was ON DELETE SET NULL — so one click silently erased
  // `noteTemplateId` on every bound visit. Measured on production: 29 of 52
  // visits had their provenance destroyed that way, 18 of them SIGNED. The
  // original test's scoping intent is preserved verbatim in the second case.
  it('refuses when any visit references the template, and does NOT delete', async () => {
    mocks.findFirst.mockResolvedValueOnce({ id: CUID, status: 'active' });
    mocks.visitCount.mockResolvedValueOnce(12);
    const r = await deleteNoteTemplateAction(CUID);
    expect(r.ok).toBe(false);
    expect(r.ok === false && r.error).toContain('12');
    expect(mocks.deleteMany).not.toHaveBeenCalled();
    // ⚠️ THE PROPERTIES, NOT THE OBJECT — canon 70. This asserted the exact
    // where-shape `{ noteTemplateId }`, which is the UNSCOPED form, so it FAILED
    // the practice-scoped fix and would have held the cross-tenant read in place.
    // `transcribeVisit` is clinical and this count is spoken back to the doctor,
    // so BOTH claims are asserted and neither of them is the spelling.
    // ⚠️ THE REFUSAL WRITES AN AUDIT ROW. A fence that blocks silently teaches
    // nobody it exists.
    expect(mocks.logAudit).toHaveBeenCalledWith(
      expect.objectContaining({
        action: 'TEMPLATE_DELETED',
        success: false,
        errorCode: 'REFERENCED_BY_VISITS',
        metadata: expect.objectContaining({ referencingVisits: 12, outcome: 'refused' }),
      }),
    );
    const countWhere = mocks.visitCount.mock.calls[0][0].where;
    expect(countWhere.noteTemplateId).toBe(CUID); // filters to the template
    expect(countWhere.practiceId).toBe('p1');     // and does not cross tenants
  });

  it('deletes an unreferenced owned template, still scoped to the doctor', async () => {
    mocks.findFirst.mockResolvedValueOnce({ id: CUID, status: 'inactive' });
    mocks.visitCount.mockResolvedValueOnce(0);
    mocks.deleteMany.mockResolvedValueOnce({ count: 1 });
    expect((await deleteNoteTemplateAction(CUID)).ok).toBe(true);
    expect(mocks.deleteMany.mock.calls[0][0]).toEqual({ where: { id: CUID, doctorId: DOCTOR } });
    // ⚠️ AND THE SUCCESSFUL DELETE LEAVES A TRACE — the row that did NOT exist
    // before R1, whose absence is why 29 visits lost provenance invisibly.
    expect(mocks.logAudit).toHaveBeenCalledWith(
      expect.objectContaining({
        action: 'TEMPLATE_DELETED',
        success: true,
        metadata: expect.objectContaining({ outcome: 'deleted' }),
      }),
    );
  });

  it('refuses a foreign template without revealing its usage', async () => {
    mocks.findFirst.mockResolvedValueOnce(null);
    expect((await deleteNoteTemplateAction(CUID)).ok).toBe(false);
    // ownership is checked FIRST, so a foreign id cannot be probed for a count
    expect(mocks.visitCount).not.toHaveBeenCalled();
    expect(mocks.deleteMany).not.toHaveBeenCalled();
  });
});

describe('archiveNoteTemplateAction', () => {
  it('sets the row inactive and never deletes', async () => {
    mocks.updateMany.mockResolvedValueOnce({ count: 1 });
    expect((await archiveNoteTemplateAction(CUID)).ok).toBe(true);
    expect(mocks.updateMany.mock.calls[0][0]).toEqual({
      where: { id: CUID, doctorId: DOCTOR },
      data: { status: 'inactive' },
    });
    expect(mocks.deleteMany).not.toHaveBeenCalled();
  });
});

describe('duplicateNoteTemplateAction', () => {
  it('copies an owned row as a fresh draft v1 with a "(copy)" name', async () => {
    mocks.findFirst.mockResolvedValue({
      name: 'Ortho', encounterType: 'orthopedics', sections: [], styleProfile: {}, specialtyBaseline: null,
    });
    const r = await duplicateNoteTemplateAction(CUID);
    expect(r.ok).toBe(true);
    const data = mocks.create.mock.calls[0][0].data;
    expect(data.name).toBe('Ortho (copy)');
    expect(data.status).toBe('draft');
    expect(data.version).toBe(1);
    expect(data.doctorId).toBe(DOCTOR);
  });
});

describe('getNoteTemplateForEditAction', () => {
  it('returns a scoped row mapped to the review model; null → error', async () => {
    mocks.findFirst.mockResolvedValueOnce({
      id: CUID, name: 'Ortho', encounterType: 'orthopedics',
      sections: [{ key: 'subjective', label: 'S', order: 1, formatHint: 'prose', styleInstructions: null, defaultText: null, defaultTextMode: 'omit_unless_supported' }],
      styleProfile: { tense: 'past', tone: 'concise', abbreviations: null },
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
