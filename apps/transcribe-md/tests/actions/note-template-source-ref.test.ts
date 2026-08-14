// ============================================================================
// GATE — AN EDIT OR DUPLICATE MUST NEVER SILENTLY DESTROY OR FABRICATE THE
// SOURCE REF. RC-2, ruling #106(b).
// ----------------------------------------------------------------------------
// The ref points at the doctor's ORIGINAL uploaded .docx — the only copy of
// their letterhead and logo that exists anywhere. #106(b) exists because one
// customer's was destroyed at upload. A NULL written by omission would destroy
// the next one just as completely, and far more quietly: no error, no log, a
// perfectly successful save.
//
// ⚠️ THE DANGEROUS PATH IS THE VERSION BUMP, NOT THE IN-PLACE EDIT. Prisma
// leaves unnamed fields alone, so updating a draft preserves the ref for free.
// But editing an ACTIVE template CREATES A NEW ROW — and a new row with no
// source columns is exactly the silent destruction. That case is the reason
// this file exists.
// ============================================================================
import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({
  findFirst: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  updateMany: vi.fn(),
  transaction: vi.fn(),
  requireSession: vi.fn(),
  isTenantOwned: vi.fn(() => true),
  applyPhiGate: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: {
    noteTemplate: { findFirst: h.findFirst, create: h.create, update: h.update },
    $transaction: h.transaction,
  },
}));
vi.mock('@/lib/auth', () => ({ requireSession: h.requireSession }));
vi.mock('@/lib/template-twin/storage', () => ({ isTenantOwnedArtifactKey: h.isTenantOwned }));
vi.mock('@/lib/note-template-parse/phi-gate', async (orig) => {
  const actual = await orig<Record<string, unknown>>();
  return { ...actual, applyPhiGate: h.applyPhiGate };
});
vi.mock('next/cache', () => ({ revalidatePath: vi.fn() }));

import {
  duplicateNoteTemplateAction,
  saveNoteTemplateAction,
} from '@/actions/note-template-lifecycle';

const SHA = 'c'.repeat(64);
const KEY = `practices/prac_1/template-twin/uploads/up_1/up_1/${SHA}.docx`;

const PAYLOAD = (over: Record<string, unknown> = {}) => ({
  name: 'My imaging form',
  encounterType: null,
  sections: [
    {
      key: 'technique',
      label: 'TECHNIQUE',
      order: 1,
      formatHint: 'prose',
      styleInstructions: null,
      defaultText: 'A duplex study documenting reflux over 500 milliseconds.',
      structure: null,
    },
  ],
  styleProfile: { tense: 'past', tone: 'clinical', abbreviations: 'expand' },
  ...over,
});

/** Runs the transaction body against the mocked tx client and returns the
 *  create/update payloads it produced. */
function captureTx() {
  const tx = {
    noteTemplate: {
      updateMany: h.updateMany,
      update: h.update.mockResolvedValue({ id: 'tmpl_updated' }),
      create: h.create.mockResolvedValue({ id: 'tmpl_created' }),
    },
  };
  h.transaction.mockImplementation(async (fn: (t: unknown) => unknown) => fn(tx));
}

beforeEach(() => {
  vi.clearAllMocks();
  h.requireSession.mockResolvedValue({ user: { id: 'doc_1', practiceId: 'prac_1' } });
  h.isTenantOwned.mockReturnValue(true);
  h.applyPhiGate.mockImplementation((draft: unknown) => ({
    rejected: false,
    template: draft,
    flags: [],
  }));
  h.findFirst.mockResolvedValue(null);
  captureTx();
});

describe('⚠️ AN EDIT PRESERVES THE REF — proven by attempt', () => {
  it('⚠️ a version bump off an ACTIVE row CARRIES the ref onto the new row', async () => {
    h.findFirst.mockResolvedValue({
      id: 'tmpl_old',
      status: 'active',
      version: 4,
      sourceObjectKey: KEY,
      sourceSha256: SHA,
    });
    await saveNoteTemplateAction(PAYLOAD({ id: 'c'.repeat(25) }), true);
    const data = h.create.mock.calls[0]![0].data;
    expect(data.version).toBe(5);
    // The claim: byte-identical, not merely present.
    expect(data.sourceObjectKey).toBe(KEY);
    expect(data.sourceSha256).toBe(SHA);
  });

  it('an in-place edit of a draft NEVER NAMES the columns, so Prisma preserves them', async () => {
    h.findFirst.mockResolvedValue({
      id: 'tmpl_draft',
      status: 'draft',
      version: 1,
      sourceObjectKey: KEY,
      sourceSha256: SHA,
    });
    await saveNoteTemplateAction(PAYLOAD({ id: 'c'.repeat(25) }), false);
    const data = h.update.mock.calls[0]![0].data;
    // Naming them here would be equivalent today and a silent NULLing the
    // moment somebody spreads a partial object in. Absence is the assertion.
    expect(Object.keys(data)).not.toContain('sourceObjectKey');
    expect(Object.keys(data)).not.toContain('sourceSha256');
  });

  it('⚠️ a version bump off a row with NO ref writes NULL, not something invented', async () => {
    h.findFirst.mockResolvedValue({
      id: 'tmpl_old',
      status: 'active',
      version: 1,
      sourceObjectKey: null,
      sourceSha256: null,
    });
    await saveNoteTemplateAction(PAYLOAD({ id: 'c'.repeat(25) }), true);
    const data = h.create.mock.calls[0]![0].data;
    expect(data.sourceObjectKey).toBeNull();
    expect(data.sourceSha256).toBeNull();
  });

  it('⚠️ a CLIENT-SUPPLIED ref is IGNORED on an edit — the server owns provenance', async () => {
    h.findFirst.mockResolvedValue({
      id: 'tmpl_old',
      status: 'active',
      version: 2,
      sourceObjectKey: KEY,
      sourceSha256: SHA,
    });
    const attacker = `practices/prac_2/template-twin/uploads/x/x/${'d'.repeat(64)}.docx`;
    await saveNoteTemplateAction(
      PAYLOAD({ id: 'c'.repeat(25), source: { objectKey: attacker, sha256: 'd'.repeat(64) } }),
      true
    );
    expect(h.create.mock.calls[0]![0].data.sourceObjectKey).toBe(KEY);
  });
});

describe('a NEW template records the ref the upload produced', () => {
  it('stores objectKey + sha on create', async () => {
    await saveNoteTemplateAction(PAYLOAD({ source: { objectKey: KEY, sha256: SHA } }), true);
    const data = h.create.mock.calls[0]![0].data;
    expect(data.sourceObjectKey).toBe(KEY);
    expect(data.sourceSha256).toBe(SHA);
  });

  it('a paste-created template records NULL — absence is not failure', async () => {
    await saveNoteTemplateAction(PAYLOAD(), true);
    const data = h.create.mock.calls[0]![0].data;
    expect(data.sourceObjectKey).toBeNull();
  });
});

describe("⚠️ A KEY FROM ANOTHER PRACTICE IS REFUSED, BY NAME, BEFORE ANY WRITE", () => {
  it('refuses with its OWN message — never the generic save error', async () => {
    h.isTenantOwned.mockReturnValue(false);
    const out = await saveNoteTemplateAction(
      PAYLOAD({ source: { objectKey: KEY, sha256: SHA } }),
      true
    );
    expect(out.ok).toBe(false);
    // The bare catch{} below returns "Could not save the template just now".
    // A security refusal must never be indistinguishable from a DB blip — for
    // the doctor OR for whoever debugs it.
    expect(out.error).toMatch(/not valid for your practice/i);
    expect(out.error).not.toMatch(/could not save/i);
  });

  it('⚠️ NOTHING IS WRITTEN — the refusal precedes the transaction entirely', async () => {
    h.isTenantOwned.mockReturnValue(false);
    await saveNoteTemplateAction(PAYLOAD({ source: { objectKey: KEY, sha256: SHA } }), true);
    expect(h.transaction).not.toHaveBeenCalled();
    expect(h.create).not.toHaveBeenCalled();
  });

  it('validates against the SESSION practice, not one from the payload', async () => {
    await saveNoteTemplateAction(PAYLOAD({ source: { objectKey: KEY, sha256: SHA } }), true);
    expect(h.isTenantOwned.mock.calls[0]![0]).toMatchObject({
      practiceId: 'prac_1',
      kind: 'upload',
    });
  });
});

describe('⚠️ A DUPLICATE CARRIES SHARED ORIGIN — two rows, one file', () => {
  it('copies the ref verbatim rather than dropping it', async () => {
    h.findFirst.mockResolvedValue({
      name: 'Form',
      encounterType: null,
      sections: [],
      styleProfile: null,
      specialtyBaseline: null,
      sourceObjectKey: KEY,
      sourceSha256: SHA,
    });
    h.create.mockResolvedValue({ id: 'tmpl_copy' });
    await duplicateNoteTemplateAction('tmpl_orig');
    const data = h.create.mock.calls[0]![0].data;
    // TRUE provenance: the copy's origin genuinely IS that file. Dropping it
    // would destroy something the copy earned; minting anything else would
    // fabricate one it did not.
    expect(data.sourceObjectKey).toBe(KEY);
    expect(data.sourceSha256).toBe(SHA);
    expect(data.version).toBe(1);
  });

  it('a duplicate of a ref-less template stays ref-less', async () => {
    h.findFirst.mockResolvedValue({
      name: 'Form',
      encounterType: null,
      sections: [],
      styleProfile: null,
      specialtyBaseline: null,
      sourceObjectKey: null,
      sourceSha256: null,
    });
    h.create.mockResolvedValue({ id: 'tmpl_copy' });
    await duplicateNoteTemplateAction('tmpl_orig');
    expect(h.create.mock.calls[0]![0].data.sourceObjectKey).toBeNull();
  });
});
