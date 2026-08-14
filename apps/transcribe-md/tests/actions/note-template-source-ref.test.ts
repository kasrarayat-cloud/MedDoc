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
  // ⚠️ TYPED ARGUMENT, DELIBERATELY. `vi.fn(() => true)` infers a ZERO-ARG
  // signature, so `mock.calls[0][0]` is a compile error on an empty tuple —
  // and the assertion that the SESSION practice is what gets validated is
  // exactly the one that must not be dropped to satisfy the compiler.
  isTenantOwned: vi.fn((_input: { objectKey: string; practiceId: string; kind: string }) => true),
  applyPhiGate: vi.fn(),
  // RC-2 — the twin door. `createDraft` is what MUST be reached.
  createDraft: vi.fn(),
  readUpload: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: {
    noteTemplate: { findFirst: h.findFirst, create: h.create, update: h.update },
    $transaction: h.transaction,
  },
}));
vi.mock('@/lib/auth', () => ({ requireSession: h.requireSession }));
vi.mock('@/lib/template-twin/storage', () => ({
  isTenantOwnedArtifactKey: h.isTenantOwned,
  createTemplateTwinArtifactStore: () => ({ readUploadArtifact: h.readUpload }),
}));
vi.mock('@/lib/template-twin/create-draft', () => ({ createTemplateTwinDraft: h.createDraft }));
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
  h.readUpload.mockResolvedValue(Buffer.from('PK\u0003\u0004 not a real docx'));
  h.createDraft.mockResolvedValue({
    noteTemplateId: 'tmpl_created',
    sourceSha256: SHA,
    compilerVersion: 'test',
    fieldCount: 80,
    blockingUnsupportedCount: 0,
    usedFallbackMappings: false,
  });
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
    // `SaveTemplateResult` is a discriminated union; `expect(out.ok).toBe(false)`
    // is a runtime assertion and narrows nothing for the compiler. Throwing on
    // the success arm narrows it AND states the expectation.
    if (out.ok) throw new Error('expected a refusal, got a successful save');
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

// ============================================================================
// RC-2 — THE TWIN DOOR IS REACHABLE, PROVEN BY ATTEMPT
//
// ⚠️ THE ENTIRE DEFECT WAS A DOOR NOBODY COULD OPEN THAT EVERYONE BELIEVED WAS
// OPEN. The compiler worked. The gate was correct. Production held zero
// compiled versions because `NativeTemplateManager` renders **null** under
// `NEXT_PUBLIC_SETTINGS_SIMPLE_ROW=true`, so its server action had no caller —
// and every artefact describing the feature read as though it did.
//
// So the proof is not "the function exists" or "the flag is on". It is: run the
// ordinary upload save, and assert the compiler was ACTUALLY INVOKED, with the
// doctor's own template id, on bytes verified against the stored digest.
// ============================================================================
describe('⚠️ RC-2 — the twin door, proven by ATTEMPT', () => {
  it('AN UPLOAD REACHES THE COMPILER — with the doctor’s OWN template id', async () => {
    const out = await saveNoteTemplateAction(
      PAYLOAD({ source: { objectKey: KEY, sha256: SHA } }),
      true
    );
    if (!out.ok) throw new Error(`expected the save to succeed, got: ${out.error}`);

    expect(
      h.createDraft,
      'the twin compiler was never invoked — the door is shut again, which is ' +
        'the exact defect RC-2 exists to close and the exact thing no other ' +
        'test in this repository would notice',
    ).toHaveBeenCalledTimes(1);

    const arg = h.createDraft.mock.calls[0]![0] as {
      attachToNoteTemplateId?: string;
      actor: { practiceId: string; userId: string };
    };
    // ATTACHED, never minting a second template beside the doctor's own.
    expect(arg.attachToNoteTemplateId).toBe('tmpl_created');
    expect(arg.actor).toMatchObject({ practiceId: 'prac_1', userId: 'doc_1' });
  });

  it('the bytes are read back with the STORED DIGEST — never the key alone', async () => {
    // ⚠️ THIS ARM PERFORMS ITS OWN SAVE. The first draft asserted against the
    // PREVIOUS test's calls — which `beforeEach`'s `clearAllMocks` had already
    // wiped, so it measured an empty mock and said so. A test that depends on
    // its neighbour having run is a test that passes for the wrong reason the
    // day someone reorders the file.
    await saveNoteTemplateAction(PAYLOAD({ source: { objectKey: KEY, sha256: SHA } }), true);
    // A key alone cannot prove the object still holds what was uploaded.
    expect(h.readUpload).toHaveBeenCalledTimes(1);
    expect(h.readUpload.mock.calls[0]![0]).toMatchObject({
      objectKey: KEY,
      practiceId: 'prac_1',
      expectedSha256: SHA,
    });
  });

  it('⚠️ A COMPILE FAILURE NEVER COSTS THE DOCTOR THEIR UPLOAD', async () => {
    h.createDraft.mockRejectedValueOnce(new Error('compiler exploded'));
    const out = await saveNoteTemplateAction(
      PAYLOAD({ source: { objectKey: KEY, sha256: SHA } }),
      true
    );
    // The template is saved. The twin is parked; the note format is not.
    expect(out.ok).toBe(true);
    expect(h.create).toHaveBeenCalled();
  });

  it('A PASTE DOES NOT KNOCK — no file, no compile', async () => {
    await saveNoteTemplateAction(PAYLOAD(), true);
    expect(h.createDraft).not.toHaveBeenCalled();
  });

  it('⚠️ AN EDIT DOES NOT RE-COMPILE — the ref is carried, not re-uploaded', async () => {
    // A version bump carries `sourceObjectKey` forward, so keying off the ref
    // alone would mint a fresh twin lineage on every subsequent save.
    h.findFirst.mockResolvedValue({
      id: 'tmpl_existing',
      status: 'active',
      version: 3,
      sourceObjectKey: KEY,
      sourceSha256: SHA,
    });
    await saveNoteTemplateAction(PAYLOAD(), true);
    expect(h.createDraft).not.toHaveBeenCalled();
  });

  it('A REFUSED KEY NEVER REACHES THE COMPILER', async () => {
    h.isTenantOwned.mockReturnValue(false);
    await saveNoteTemplateAction(PAYLOAD({ source: { objectKey: KEY, sha256: SHA } }), true);
    expect(h.createDraft).not.toHaveBeenCalled();
    expect(h.readUpload).not.toHaveBeenCalled();
  });
});
