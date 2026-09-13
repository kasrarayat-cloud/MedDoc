// ============================================================================
// OWNER RULE — AN UPLOAD/SAVE NEVER DISPLACES A CERTIFIED ACTIVE FORM.
// ----------------------------------------------------------------------------
// When an ACTIVE, CERTIFIED template already exists for a (doctor, encounterType),
// a save that asked to activate is HELD as a draft: the certified form stays
// active, and the new one goes live only through certification or the owner's
// explicit choice. This prevents an uncertified upload from superseding a working
// certified form — the harm behind the parent finding, worst when the new form's
// certification then fails and the doctor is left with no certified form at all.
//
// ⚠️ BOTH CERTIFICATION KINDS ARE PROTECTED, and the PDF-native arm is why this
// test exists in its second form: certification is stored in TWO places — a DOCX
// twin's templateTwinCompiledVersion, and a flat PDF's styleProfile.pdfNativeCertified.
// A twin-only guard silently displaced PDF-native certified forms (adversarial
// finding, clinical-harm). Each arm plants the OPPOSITE case.
// ============================================================================
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  findFirst: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  updateMany: vi.fn(),
  requireSession: vi.fn(),
  logAudit: vi.fn(async () => {}),
}));

vi.mock('@meddoc/db', () => {
  const noteTemplate = {
    findFirst: mocks.findFirst,
    create: mocks.create,
    update: mocks.update,
    updateMany: mocks.updateMany,
  };
  const prisma = {
    noteTemplate,
    transcribeVisit: { count: vi.fn() },
    $transaction: async (fn: (tx: unknown) => unknown) => fn({ noteTemplate }),
  };
  return { default: prisma, prisma };
});
vi.mock('@/lib/auth', () => ({ requireSession: mocks.requireSession }));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));
vi.mock('next/cache', () => ({ revalidatePath: vi.fn() }));

import { saveNoteTemplateAction } from '../note-template-lifecycle';

const DOCTOR = 'doc1';
const CUID = 'cjld2cjxh0000qzrmn831i7rn';

function input(over: Record<string, unknown> = {}) {
  return {
    name: 'GI Consultation',
    encounterType: 'gastroenterology',
    sections: [
      { key: 'subjective', label: 'Subjective', order: 1, formatHint: 'prose', styleInstructions: 'Interval hx.', defaultText: null },
      { key: 'objective', label: 'Exam', order: 2, formatHint: 'bullets', styleInstructions: 'By region.', defaultText: null },
    ],
    styleProfile: { tense: 'past', tone: 'concise', abbreviations: null },
    ...over,
  };
}

const TWIN_CERTIFIED = {
  name: 'GI Consultation',
  styleProfile: {},
  templateTwinCompiledVersion: { certificationStatus: 'CERTIFIED' },
};
const PDF_NATIVE_CERTIFIED = {
  name: 'GI Consultation',
  styleProfile: { pdfNativeCertified: true },
  templateTwinCompiledVersion: null,
};
const UNCERTIFIED_ACTIVE = {
  name: 'Old draft-ish',
  styleProfile: {},
  templateTwinCompiledVersion: null,
};

/** Model the DB. The active-slot check is `{doctorId, encounterType, status:'active'}`
 *  (no `id`); the ownership pre-check is `{id, doctorId}`. */
function seed(opts: { ownership?: unknown; activeInSlot?: unknown }) {
  mocks.findFirst.mockImplementation(async ({ where }: { where: Record<string, unknown> }) => {
    if (where.status === 'active' && where.id === undefined) return opts.activeInSlot ?? null;
    return opts.ownership ?? null; // ownership pre-check ({id, doctorId})
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireSession.mockResolvedValue({ user: { id: DOCTOR, practiceId: 'p1' } });
  mocks.create.mockResolvedValue({ id: 'created-id' });
  mocks.update.mockResolvedValue({ id: 'updated-id' });
  mocks.updateMany.mockResolvedValue({ count: 1 });
});

describe('OWNER RULE — an active certified sibling holds the save as a draft', () => {
  it('⚠️ a TWIN-certified active form holds the save as a draft (not superseded)', async () => {
    seed({ activeInSlot: TWIN_CERTIFIED });
    const r = await saveNoteTemplateAction(input(), true);
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.status).toBe('draft');
      expect(r.activationHeld).toContain('GI Consultation');
      expect(r.activationHeld).toMatch(/stays active/i);
    }
    expect(mocks.updateMany).not.toHaveBeenCalled(); // certified form untouched
    expect(mocks.create.mock.calls[0][0].data.status).toBe('draft');
  });

  it('⚠️ a PDF-NATIVE-certified active form ALSO holds the save (the adversarial gap)', async () => {
    // styleProfile.pdfNativeCertified === true, NO twin row — the case a
    // twin-only guard silently displaced.
    seed({ activeInSlot: PDF_NATIVE_CERTIFIED });
    const r = await saveNoteTemplateAction(input(), true);
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.status).toBe('draft');
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.create.mock.calls[0][0].data.status).toBe('draft');
  });

  it('⚠️ OPPOSITE: an UNCERTIFIED active form does NOT hold — the save activates', async () => {
    seed({ activeInSlot: UNCERTIFIED_ACTIVE });
    const r = await saveNoteTemplateAction(input(), true);
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.status).toBe('active');
      expect(r.activationHeld ?? null).toBeNull();
    }
    expect(mocks.updateMany).toHaveBeenCalledWith({
      where: { doctorId: DOCTOR, encounterType: 'gastroenterology', status: 'active' },
      data: { status: 'inactive' },
    });
    expect(mocks.create.mock.calls[0][0].data.status).toBe('active');
  });

  it('⚠️ OPPOSITE: NO active form in the slot → the first form activates as before', async () => {
    seed({ activeInSlot: null });
    const r = await saveNoteTemplateAction(input(), true);
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.status).toBe('active');
    expect(mocks.create.mock.calls[0][0].data.status).toBe('active');
  });

  it('editing the ACTIVE certified row itself is also held (an edit drops certification)', async () => {
    seed({ ownership: { id: CUID, status: 'active', version: 3 }, activeInSlot: TWIN_CERTIFIED });
    const r = await saveNoteTemplateAction(input({ id: CUID }), true);
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.status).toBe('draft');
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.create).toHaveBeenCalled(); // new version, as a draft
    expect(mocks.create.mock.calls[0][0].data.status).toBe('draft');
  });

  it('a deliberate DRAFT save (activate=false) is unaffected and carries no held notice', async () => {
    seed({ activeInSlot: TWIN_CERTIFIED });
    const r = await saveNoteTemplateAction(input(), false);
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.status).toBe('draft');
      expect(r.activationHeld ?? null).toBeNull();
    }
    // The guard's active-slot check never runs when activate is false.
    const ranSlotCheck = mocks.findFirst.mock.calls.some(
      (c) => c[0]?.where?.status === 'active' && c[0]?.where?.id === undefined,
    );
    expect(ranSlotCheck).toBe(false);
  });

  it('the active-slot check is scoped to THIS doctor and encounterType', async () => {
    seed({ activeInSlot: null });
    await saveNoteTemplateAction(input({ encounterType: 'cardiology' }), true);
    const slotCall = mocks.findFirst.mock.calls.find(
      (c) => c[0]?.where?.status === 'active' && c[0]?.where?.id === undefined,
    );
    expect(slotCall).toBeTruthy();
    expect(slotCall![0].where).toEqual({
      doctorId: DOCTOR,
      encounterType: 'cardiology',
      status: 'active',
    });
    // and it selects BOTH certification signals, so neither cert kind is missed
    expect(slotCall![0].select).toMatchObject({
      styleProfile: true,
      templateTwinCompiledVersion: { select: { certificationStatus: true } },
    });
  });
});
