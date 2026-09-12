// ============================================================================
// TEMPLATE-CHOICE-1 (#318) — behavioural gate.
// ----------------------------------------------------------------------------
// Two security-relevant surfaces:
//   1. resolveRequestedTemplate — which template a VISIT uses. A pick resolves
//      to the caller's OWN row OR a CERTIFIED template in the caller's PRACTICE,
//      and to NOTHING ELSE (never a co-tenant's draft, never another practice's
//      row). The practice arm uses the EXACT predicate the fill honours.
//   2. setPracticeDefaultTemplateAction — OWNER-gated, validates certified-in-
//      practice, audits, and refuses by name otherwise.
// Each arm plants the OPPOSITE case so a vacuous pass cannot hide a leak.
// ============================================================================
import { describe, it, expect, vi, beforeEach } from 'vitest';

const h = vi.hoisted(() => ({
  noteTemplateFindFirst: vi.fn(),
  practiceFindUnique: vi.fn(),
  practiceUpdate: vi.fn(),
  requirePracticeAdmin: vi.fn(),
  getSession: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: {
    noteTemplate: { findFirst: h.noteTemplateFindFirst },
    practice: { findUnique: h.practiceFindUnique, update: h.practiceUpdate },
  },
}));
vi.mock('@/lib/practice-admin', () => ({
  requirePracticeAdmin: h.requirePracticeAdmin,
}));
vi.mock('@/lib/auth', () => ({ getSession: h.getSession }));
vi.mock('@/lib/audit', () => ({ logAudit: h.logAudit }));
vi.mock('next/cache', () => ({ revalidatePath: vi.fn() }));

import { resolveRequestedTemplate } from '../visits';
import { setPracticeDefaultTemplateAction } from '../practice-template-default';

const DOCTOR = 'doc-1';
const PRACTICE = 'prac-1';
const CERTIFIED = { is: { certificationStatus: 'CERTIFIED' } };

/** Model the DB: `own` = the doctor's own rows; `practiceCertified` = CERTIFIED
 *  rows in the practice. Everything else (co-tenant drafts, other practices) is
 *  absent, i.e. neither query matches. */
function seedDb(opts: { own?: Set<string>; practiceCertified?: Set<string> }) {
  h.noteTemplateFindFirst.mockImplementation(async ({ where }: any) => {
    if (where.doctorId !== undefined) {
      return opts.own?.has(where.id) ? { id: where.id } : null;
    }
    if (where.practiceId !== undefined) {
      // The practice arm MUST carry the CERTIFIED predicate — assert it, so a
      // future edit that drops the filter (widening to any practice template)
      // fails here rather than silently shipping.
      expect(where.templateTwinCompiledVersion).toEqual(CERTIFIED);
      return opts.practiceCertified?.has(where.id) ? { id: where.id } : null;
    }
    if (where.isSystemDefault) return { id: 'sys-default' };
    return null;
  });
}

describe('TEMPLATE-CHOICE-1 — resolveRequestedTemplate (the visit pick)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('null and empty → null (worker resolves the active format)', async () => {
    seedDb({});
    expect(await resolveRequestedTemplate(DOCTOR, PRACTICE, null)).toBeNull();
  });

  it("__default__ → the system default id", async () => {
    seedDb({});
    expect(await resolveRequestedTemplate(DOCTOR, PRACTICE, '__default__')).toBe('sys-default');
  });

  it("the caller's OWN row resolves (any status) — unchanged behaviour", async () => {
    seedDb({ own: new Set(['own-draft']) });
    expect(await resolveRequestedTemplate(DOCTOR, PRACTICE, 'own-draft')).toBe('own-draft');
  });

  it("a co-tenant's CERTIFIED template in the practice resolves (the #318 widening)", async () => {
    seedDb({ practiceCertified: new Set(['cotenant-certified']) });
    expect(await resolveRequestedTemplate(DOCTOR, PRACTICE, 'cotenant-certified')).toBe(
      'cotenant-certified',
    );
  });

  it("a co-tenant's NON-certified template does NOT resolve → null (auto)", async () => {
    // Present as neither own nor practice-certified → both queries miss.
    seedDb({ own: new Set(['own-draft']), practiceCertified: new Set(['cotenant-certified']) });
    expect(await resolveRequestedTemplate(DOCTOR, PRACTICE, 'cotenant-DRAFT')).toBeNull();
  });

  it('another practice’s certified template does NOT resolve → null', async () => {
    // It would be certified in ITS practice, but our practice query is scoped to
    // PRACTICE, so it is absent here.
    seedDb({ practiceCertified: new Set(['ours-only']) });
    expect(await resolveRequestedTemplate(DOCTOR, PRACTICE, 'foreign-practice-certified')).toBeNull();
  });
});

describe('TEMPLATE-CHOICE-1 — setPracticeDefaultTemplateAction (OWNER setter)', () => {
  beforeEach(() => vi.clearAllMocks());

  const fd = (templateId: string) => {
    const f = new FormData();
    f.set('templateId', templateId);
    return f;
  };

  it('a non-owner is refused BY NAME, and nothing is written or audited', async () => {
    h.requirePracticeAdmin.mockResolvedValue({
      ok: false,
      reason: 'NOT_PRACTICE_ADMIN',
      message: 'Only a practice owner can do that.',
    });
    const res = await setPracticeDefaultTemplateAction(null, fd('any'));
    expect(res).toMatchObject({ ok: false, reason: 'NOT_PRACTICE_ADMIN' });
    expect(h.practiceUpdate).not.toHaveBeenCalled();
    expect(h.logAudit).not.toHaveBeenCalled();
  });

  it('an OWNER setting a CERTIFIED-in-practice template writes it and audits old→new', async () => {
    h.requirePracticeAdmin.mockResolvedValue({ ok: true, actorId: DOCTOR, practiceId: PRACTICE });
    h.noteTemplateFindFirst.mockImplementation(async ({ where }: any) => {
      expect(where.practiceId).toBe(PRACTICE);
      expect(where.templateTwinCompiledVersion).toEqual(CERTIFIED);
      return where.id === 'cert-1' ? { id: 'cert-1' } : null;
    });
    h.practiceFindUnique.mockResolvedValue({ defaultNoteTemplateId: null });
    h.practiceUpdate.mockResolvedValue({});
    const res = await setPracticeDefaultTemplateAction(null, fd('cert-1'));
    expect(res).toMatchObject({ ok: true, defaultNoteTemplateId: 'cert-1' });
    expect(h.practiceUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ data: { defaultNoteTemplateId: 'cert-1' } }),
    );
    expect(h.logAudit).toHaveBeenCalledWith(
      expect.objectContaining({
        action: 'PRACTICE_UPDATED',
        metadata: expect.objectContaining({ field: 'defaultNoteTemplateId', from: null, to: 'cert-1' }),
      }),
    );
  });

  it('an OWNER picking an UNCERTIFIED template is refused; nothing is written', async () => {
    h.requirePracticeAdmin.mockResolvedValue({ ok: true, actorId: DOCTOR, practiceId: PRACTICE });
    h.noteTemplateFindFirst.mockResolvedValue(null); // not certified in practice
    const res = await setPracticeDefaultTemplateAction(null, fd('not-certified'));
    expect(res).toMatchObject({ ok: false, reason: 'TEMPLATE_NOT_CERTIFIED' });
    expect(h.practiceUpdate).not.toHaveBeenCalled();
    expect(h.logAudit).not.toHaveBeenCalled();
  });

  it('__clear__ clears the default (no certified lookup needed)', async () => {
    h.requirePracticeAdmin.mockResolvedValue({ ok: true, actorId: DOCTOR, practiceId: PRACTICE });
    h.practiceFindUnique.mockResolvedValue({ defaultNoteTemplateId: 'cert-1' });
    h.practiceUpdate.mockResolvedValue({});
    const res = await setPracticeDefaultTemplateAction(null, fd('__clear__'));
    expect(res).toMatchObject({ ok: true, defaultNoteTemplateId: null });
    expect(h.noteTemplateFindFirst).not.toHaveBeenCalled();
    expect(h.practiceUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ data: { defaultNoteTemplateId: null } }),
    );
  });
});
