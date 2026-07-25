// ============================================================================
// resolveActiveTemplate — fallback-chain unit tests (Phase 0).
// ----------------------------------------------------------------------------
// Targets the PURE core `selectTemplate`. @meddoc/db is mocked so importing
// the module under test never constructs the real Prisma client (the pure
// resolver does no I/O; the async shell is exercised separately in Phase 1).
// ============================================================================

import { describe, expect, it, vi } from 'vitest';

vi.mock('@meddoc/db', () => ({
  default: { noteTemplate: { findMany: vi.fn() } },
}));

import type { NoteTemplate } from '@prisma/client';
import {
  selectTemplate,
  MissingSystemDefaultTemplateError,
} from '../resolve-active-template';

/** Build a NoteTemplate row with sane Phase-0 defaults. */
function tmpl(overrides: Partial<NoteTemplate> = {}): NoteTemplate {
  return {
    id: 'tmpl',
    doctorId: null,
    name: 'T',
    encounterType: null,
    specialtyBaseline: null,
    sections: [],
    styleProfile: null,
    version: 1,
    status: 'active',
    isSystemDefault: false,
    createdAt: new Date('2026-06-03T00:00:00Z'),
    updatedAt: new Date('2026-06-03T00:00:00Z'),
    ...overrides,
  } as NoteTemplate;
}

const systemDefault = tmpl({
  id: 'sys',
  doctorId: null,
  isSystemDefault: true,
  name: 'System Default — SOAP',
});

describe('selectTemplate — fallback chain', () => {
  it('Phase-0 reality: returns the system default when the doctor has no custom template', () => {
    expect(
      selectTemplate([systemDefault], { doctorId: 'doc1', encounterType: 'cardiology' })
    ).toBe(systemDefault);
  });

  it('returns the system default when no encounter type is requested and there is no doctor template', () => {
    expect(selectTemplate([systemDefault], { doctorId: 'doc1' })).toBe(systemDefault);
  });

  it("returns the doctor's catch-all (encounterType null) over the system default", () => {
    const doctorDefault = tmpl({ id: 'dd', doctorId: 'doc1', encounterType: null });
    expect(
      selectTemplate([systemDefault, doctorDefault], { doctorId: 'doc1' })
    ).toBe(doctorDefault);
  });

  it("prefers the doctor's exact encounter-type match over the catch-all", () => {
    const doctorDefault = tmpl({ id: 'dd', doctorId: 'doc1', encounterType: null });
    const exact = tmpl({ id: 'ex', doctorId: 'doc1', encounterType: 'cardiology' });
    expect(
      selectTemplate([systemDefault, doctorDefault, exact], {
        doctorId: 'doc1',
        encounterType: 'cardiology',
      })
    ).toBe(exact);
  });

  it('falls back to the catch-all when no template matches the requested encounter type', () => {
    const doctorDefault = tmpl({ id: 'dd', doctorId: 'doc1', encounterType: null });
    const exact = tmpl({ id: 'ex', doctorId: 'doc1', encounterType: 'cardiology' });
    expect(
      selectTemplate([systemDefault, doctorDefault, exact], {
        doctorId: 'doc1',
        encounterType: 'dermatology',
      })
    ).toBe(doctorDefault);
  });

  it("ignores another doctor's templates", () => {
    const otherDoc = tmpl({ id: 'od', doctorId: 'doc2', encounterType: 'cardiology' });
    expect(
      selectTemplate([systemDefault, otherDoc], {
        doctorId: 'doc1',
        encounterType: 'cardiology',
      })
    ).toBe(systemDefault);
  });

  it('ignores non-active (draft) templates', () => {
    const draftCatchAll = tmpl({
      id: 'dr',
      doctorId: 'doc1',
      encounterType: null,
      status: 'draft',
    });
    expect(selectTemplate([systemDefault, draftCatchAll], { doctorId: 'doc1' })).toBe(
      systemDefault
    );
  });

  it('ignores a draft exact match and continues down the chain', () => {
    const draftExact = tmpl({
      id: 'dx',
      doctorId: 'doc1',
      encounterType: 'cardiology',
      status: 'draft',
    });
    const doctorDefault = tmpl({ id: 'dd', doctorId: 'doc1', encounterType: null });
    expect(
      selectTemplate([systemDefault, draftExact, doctorDefault], {
        doctorId: 'doc1',
        encounterType: 'cardiology',
      })
    ).toBe(doctorDefault);
  });

  it('throws MissingSystemDefaultTemplateError when no system default is present', () => {
    expect(() => selectTemplate([], { doctorId: 'doc1' })).toThrow(
      MissingSystemDefaultTemplateError
    );
    // A doctor draft with no active fallback + no system default also throws.
    const draft = tmpl({ id: 'dr', doctorId: 'doc1', status: 'draft' });
    expect(() => selectTemplate([draft], { doctorId: 'doc1' })).toThrow(
      MissingSystemDefaultTemplateError
    );
  });
});

// ============================================================================
// S6 — selection must be DETERMINISTIC regardless of candidate-set order.
// ----------------------------------------------------------------------------
// resolveActiveTemplate() used to load candidates with an unordered findMany,
// and selectTemplate() takes the first match. Postgres returns rows in physical
// heap order, which shifts when a row is updated — so a tie in the candidate
// set meant the chosen template could change between two otherwise identical
// visits, with nothing in the data to explain it.
//
// Worth recording precisely, because it changes what this test is FOR: the
// database already prevents the tie for real doctors. A partial unique index,
// note_templates_one_active_per_doctor_encounter ON ("doctorId",
// "encounterType") NULLS NOT DISTINCT WHERE status='active', predates this
// work and was verified to reject a second active catch-all. So this is not
// guarding a live production bug.
//
// It guards the PURE function, which is exported and takes an arbitrary
// candidate set: callers other than resolveActiveTemplate (tests, future
// resolvers, a cross-practice admin view) are not covered by that index, and a
// pure selector that depends on input order is a latent trap regardless.
// ============================================================================
describe('selectTemplate — deterministic under candidate reordering', () => {
  const older = tmpl({
    id: 'aaa',
    doctorId: 'doc1',
    name: 'older catch-all',
    encounterType: null,
    updatedAt: new Date('2026-07-01T00:00:00Z'),
  });
  const newer = tmpl({
    id: 'zzz',
    doctorId: 'doc1',
    name: 'newer catch-all',
    encounterType: null,
    updatedAt: new Date('2026-07-20T00:00:00Z'),
  });

  it('picks the SAME catch-all whichever order the rows arrive in', () => {
    const a = selectTemplate([older, newer, systemDefault], { doctorId: 'doc1' });
    const b = selectTemplate([newer, older, systemDefault], { doctorId: 'doc1' });
    const c = selectTemplate([systemDefault, newer, older], { doctorId: 'doc1' });
    expect(a.id).toBe(b.id);
    expect(b.id).toBe(c.id);
  });

  it('resolves the tie toward the most recently updated template', () => {
    const picked = selectTemplate([older, newer, systemDefault], { doctorId: 'doc1' });
    expect(picked.id).toBe('zzz');
  });

  it('falls back to id when updatedAt is identical', () => {
    const sameTime = new Date('2026-07-20T00:00:00Z');
    const t1 = tmpl({ id: 'aaa', doctorId: 'doc1', encounterType: null, updatedAt: sameTime });
    const t2 = tmpl({ id: 'zzz', doctorId: 'doc1', encounterType: null, updatedAt: sameTime });
    expect(selectTemplate([t1, t2, systemDefault], { doctorId: 'doc1' }).id).toBe(
      selectTemplate([t2, t1, systemDefault], { doctorId: 'doc1' }).id
    );
  });
});
