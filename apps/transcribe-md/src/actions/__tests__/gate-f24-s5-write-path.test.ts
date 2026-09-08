// ============================================================================
// F24-S5 — THE WRITE PATH. The clinical write, which had NO ARM AT ALL.
// ----------------------------------------------------------------------------
// ⚠️ THE REFUTED SLICE'S GATE NEVER TOUCHED THIS FILE. The adversarial pass
// deleted the `upsert` entirely and the gate read 16/16 green and `tsc` clean:
// the chat replied "SIDE OF EXAM set to Left" and NOTHING WAS WRITTEN. That is
// the worst outcome this arc can produce — a doctor told a correction landed
// when it did not — and it was invisible because every arm was a substring scan
// over a DIFFERENT file.
//
// So this file drives `setTemplateControlAction` against the REAL compiled IR
// of the customer's form and asserts what reached the database.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { compileTemplateDocx } from '@/lib/note-template-docx';
import {
  isWordPlaceholderOption,
  withoutPlaceholderOptions,
} from '@/lib/note-template-docx/placeholder-option';

const visitFindFirst = vi.fn();
const templateFindFirst = vi.fn();
const overrideUpsert = vi.fn();
const defFindUnique = vi.fn();
const lockedVisit = vi.fn();
const invalidate = vi.fn();
const audit = vi.fn();

// ⚠️ THE DROPDOWN DOOR NOW WRITES UNDER A LOCK — ROUND FIVE.
// It used to be a bare upsert: the status was read at the top of the action and
// never re-asserted, so a sign landing in the window wrote a correction onto a
// SIGNED visit, where there is no panel and therefore no Undo. Round four fixed
// exactly this on the INSERT door and left this one; the fix now lives in one
// `underVisitLock` helper that all three writers call.
//
// ⚠️ THE TRANSACTIONAL CLIENT IS A **DIFFERENT OBJECT** from the top-level one,
// deliberately. A mock that returns the same client makes `tx.` and `prisma.`
// the same function, and the one mistake that matters here — taking the write
// out of the transaction, so the lock guards a row the write never touches —
// becomes invisible.
const onTx = { upsert: false, queryRaw: false };

const dbRoot = {
  transcribeVisit: { findFirst: (...a: unknown[]) => visitFindFirst(...a) },
  noteTemplate: { findFirst: (...a: unknown[]) => templateFindFirst(...a) },
  templateTwinFieldOverride: { upsert: (...a: unknown[]) => overrideUpsert(...a) },
  templateTwinFieldDefinition: { findUnique: (...a: unknown[]) => defFindUnique(...a) },
  $queryRaw: (...a: unknown[]) => lockedVisit(...a),
};

const dbTx = {
  ...dbRoot,
  templateTwinFieldOverride: {
    upsert: (...a: unknown[]) => {
      onTx.upsert = true;
      return overrideUpsert(...a);
    },
  },
  $queryRaw: (...a: unknown[]) => {
    onTx.queryRaw = true;
    return lockedVisit(...a);
  },
};

vi.mock('@meddoc/db', () => ({
  default: {
    ...dbRoot,
    $transaction: (fn: (client: unknown) => unknown) => fn(dbTx),
  },
}));
vi.mock('@/lib/auth', () => ({
  requireSession: async () => ({ user: { id: 'doc-1', practiceId: 'prac-1' } }),
}));
vi.mock('@/lib/audit', () => ({ logAudit: (...a: unknown[]) => audit(...a) }));
vi.mock('@/lib/practice-scope', () => ({
  visitByIdScope: (id: string, practiceId: string) => ({ id, practiceId }),
  asPracticeId: (p: string) => p,
}));
vi.mock('@/lib/docx-preview/fill-cache', () => ({
  invalidateVisitFills: (...a: unknown[]) => invalidate(...a),
}));

const WM_IOV_PATH = path.resolve(process.cwd(), '../../WM IOV Template.docx');
const ir = compileTemplateDocx(new Uint8Array(readFileSync(WM_IOV_PATH)));
const selects = ir.fields.filter(
  (f) => f.rendererBinding.bindingType === 'content_control' && f.allowedOptions.length > 0,
);

/**
 * The options this control actually offers — the door's own admission set.
 *
 * ⚠️ THESE ARMS USED TO READ `f.allowedOptions[0]` DIRECTLY, and that worked
 * only because the compiler was deleting Word's "Choose an item." from the
 * stored array. F24-S5 ITEM A proved that deletion orphans every
 * already-compiled twin (`renderer.ts:assertSourceMatchesIr` re-compiles and
 * hashes `fields` — 10 of 10 CERTIFIED twins on QA began refusing), so the IR
 * carries the document's array verbatim and the exclusion lives on the readers.
 *
 * `allowedOptions[0]` is therefore FURNITURE, and the door refuses it — as it
 * should. Asking the same question the door asks is the honest fixture.
 */
const selectableOf = (f: (typeof selects)[number]) =>
  withoutPlaceholderOptions(f.allowedOptions);

const UNSIGNED = {
  id: 'v1',
  status: 'READY',
  noteTemplateId: 'tpl-1',
  noteTemplateVersion: 1,
  // ⚠️ THREE DISTINCT VALUES — RULING #267, AND THIS FIXTURE IS `SF-2`.
  // Round five found the SIBLING door's fixture still giving the session and
  // the visit author ONE value (`prac-1`), so the exact defect `8cc89b7c` fixed
  // in the insert door could be transplanted into the option door with 135 of
  // 135 green. A fixture that gives two distinct things the same value cannot
  // witness them being confused — and this one gave THREE things one value.
  //
  //   · `prac-1`            the SESSION's practice   — may this actor act?
  //   · `visit-tenant-7`    the VISIT'S tenant       — what owns this chart?
  //   · `author-practice-9` the AUTHOR's practice    — whose form fills it?
  //
  practiceId: 'visit-tenant-7',
  user: { practiceId: 'author-practice-9' },
};

beforeEach(() => {
  onTx.upsert = false;
  onTx.queryRaw = false;
  // The visit is READY unless an arm says otherwise — the lock's happy path.
  lockedVisit.mockResolvedValue([{ status: 'READY', signedAt: null }]);
  visitFindFirst.mockReset();
  templateFindFirst.mockReset();
  overrideUpsert.mockReset();
  defFindUnique.mockReset();
  invalidate.mockReset();
  audit.mockReset();
  visitFindFirst.mockResolvedValue(UNSIGNED);
  templateFindFirst.mockResolvedValue({
    templateTwinCompiledVersion: {
      id: 'cv-1',
      certificationStatus: 'CERTIFIED',
      compiledDocumentIr: ir,
    },
  });
  // The ORDINARY case: a field carrying an approved clinical concept, which is
  // what `applyClinicianOverrides` requires before it will apply an override.
  defFindUnique.mockResolvedValue({ mapping: { clinicalConcept: 'exam.side' } });
  overrideUpsert.mockResolvedValue({});
  invalidate.mockResolvedValue(undefined);
});

async function run(fieldId: string, value: string) {
  const { setTemplateControlAction } = await import('../set-template-control');
  return setTemplateControlAction('v1', fieldId, value);
}

describe('F24-S5 write path — the correction reaches the database', () => {
  it('⚠️ KILLS "delete the upsert" — a successful reply means a ROW WAS WRITTEN', async () => {
    const field = selects[0];
    const option = selectableOf(field)[0];
    const out = await run(field.fieldId, option.displayText);

    expect(out.ok).toBe(true);
    // The claim in the reply and the write are ONE fact, or the doctor is told
    // something that did not happen.
    expect(overrideUpsert).toHaveBeenCalledTimes(1);
    const arg = overrideUpsert.mock.calls[0][0] as Record<string, never>;
    expect(arg).toMatchObject({
      where: { visitId_fieldId: { visitId: 'v1', fieldId: field.fieldId } },
      create: {
        // ⚠️ THE VISIT'S TENANT — #267. It read `prac-1` when the fixture gave
        // every identity that one value, which is exactly why it could not
        // witness the row being stamped with the wrong one.
        practiceId: 'visit-tenant-7',
        visitId: 'v1',
        fieldId: field.fieldId,
        selectedOptionOrdinal: option.ordinal,
        optionValue: option.value,
        overriddenBy: 'doc-1',
      },
      update: {
        selectedOptionOrdinal: option.ordinal,
        optionValue: option.value,
      },
    });
  });

  it('⚠️ KILLS "drop visitId from the where" — the key is (visit, field), not field', async () => {
    // Without `visitId` in the key, one patient's correction to a control would
    // overwrite another patient's correction to the same control on the same
    // form. Cross-PATIENT contamination, and the reply would say "done".
    const field = selects[1];
    await run(field.fieldId, selectableOf(field)[0].displayText);
    const arg = overrideUpsert.mock.calls[0][0] as { where: { visitId_fieldId: unknown } };
    expect(arg.where.visitId_fieldId).toEqual({ visitId: 'v1', fieldId: field.fieldId });
  });

  it('⚠️ the cached document is INVALIDATED — a correction nobody can see is made twice', async () => {
    const field = selects[0];
    await run(field.fieldId, selectableOf(field)[0].displayText);
    expect(invalidate).toHaveBeenCalledWith('v1');
  });

  it('⚠️ A SIGNED VISIT IS REFUSED AT THE DOOR, AND NOTHING IS WRITTEN', async () => {
    visitFindFirst.mockResolvedValue({ ...UNSIGNED, status: 'SIGNED' });
    const field = selects[0];
    const out = await run(field.fieldId, selectableOf(field)[0].displayText);
    expect(out.ok).toBe(false);
    expect(out.error).toMatch(/signed/i);
    expect(overrideUpsert).not.toHaveBeenCalled();
  });

  it('⚠️ AN OFF-LIST VALUE IS REFUSED **WITH THE OPTIONS** — never coerced', async () => {
    const field = selects[0];
    const out = await run(field.fieldId, 'something the doctor improvised');
    expect(out.ok).toBe(false);
    expect(overrideUpsert).not.toHaveBeenCalled();
    // The refusal must ASK AN ANSWERABLE QUESTION: name the options back.
    expect(out.options?.length).toBeGreaterThan(0);
    expect(out.options).toEqual(
      selectableOf(field).map((o) => o.displayText),
    );
  });

  it('⚠️ "Choose an item." IS NOT SETTABLE — the third layer, at the door', async () => {
    // *Previous wording:* "the compiler now strips the placeholder, so on THIS
    // compiled IR it is already absent."
    //
    // ⚠️ NO LONGER TRUE, AND THE ARM IS STRONGER FOR IT. The compiler persists
    // the document's array verbatim (F24-S5 ITEM A — stripping it orphaned
    // every already-compiled twin), so the placeholder IS present here and this
    // arm now exercises the door's own filter against a real one rather than
    // against a fixture where the thing had already been removed for it.
    const field = selects[0];
    expect(
      field.allowedOptions.some((o) => isWordPlaceholderOption(o.displayText)),
      'the fixture must carry the placeholder, or this arm proves nothing',
    ).toBe(true);
    const out = await run(field.fieldId, 'Choose an item.');
    expect(out.ok).toBe(false);
    expect(overrideUpsert).not.toHaveBeenCalled();
    // And it is not offered back as a choice either.
    expect(out.options?.some((o) => isWordPlaceholderOption(o))).toBe(false);
  });

  it('⚠️ AN UNCERTIFIED TWIN OFFERS NOTHING — addressing into a structure that does not ship', async () => {
    templateFindFirst.mockResolvedValue({
      templateTwinCompiledVersion: {
        id: 'cv-1',
        certificationStatus: 'NEEDS_CONFIRMATION',
        compiledDocumentIr: ir,
      },
    });
    const out = await run(selects[0].fieldId, selectableOf(selects[0])[0].displayText);
    expect(out.ok).toBe(false);
    expect(overrideUpsert).not.toHaveBeenCalled();
  });

  it('⚠️ a field that is not on this form is refused, not written', async () => {
    const out = await run('ttf_' + 'f'.repeat(24), 'Left');
    expect(out.ok).toBe(false);
    expect(overrideUpsert).not.toHaveBeenCalled();
  });

  it('⚠️ ANOTHER PRACTICE’S VISIT DOES NOT RESOLVE — and nothing is written', async () => {
    visitFindFirst.mockResolvedValue(null);
    const out = await run(selects[0].fieldId, selectableOf(selects[0])[0].displayText);
    expect(out.ok).toBe(false);
    expect(out.error).toMatch(/not found/i);
    expect(overrideUpsert).not.toHaveBeenCalled();
  });

  it('the write is ATTRIBUTED and AUDITED', async () => {
    const field = selects[0];
    await run(field.fieldId, selectableOf(field)[0].displayText);
    expect(audit).toHaveBeenCalledTimes(1);
    const a = audit.mock.calls[0][0] as { metadata: Record<string, unknown>; targetId: string };
    expect(a.targetId).toBe('v1');
    expect(a.metadata.surface).toBe('template_control_override');
    expect(a.metadata.fieldId).toBe(field.fieldId);
  });

  // ==========================================================================
  // ⚠️ THE DOOR'S ADMISSION SET MIRRORS THE FILL'S — found by the independent
  // adversarial pass (run 20260824-073818-b1, session 02), which did not author
  // this branch.
  //
  // `applyClinicianOverrides` declines `no_approved_concept` when the field's
  // mapping carries no `clinicalConcept`. The door did not check it, so the
  // sequence was: row written, `ok: true` returned, chat reports the correction
  // applied and redraws — and then EVERY fill declines it. The document never
  // changes, on this run and on every future one, because the decline is STATIC
  // rather than a race.
  //
  // ⚠️ REACHABLE ON THE ONE CERTIFIED TWIN IN PRODUCTION, measured read-only
  // 2026-08-24 (counts only; no note text read). 80 mappings partition as
  // 52 extraction + 23 verified_note_selection + 5 manual, and FOUR of the
  // manual ones carry `clinicalConcept = NULL`. All four are
  // `single_select` / `content_control` with 5-8 options — Address, REFERRING
  // PHYSICIAN, ULTRASOUND TECHNOLOGIST, LOCATION — so all four are inside the
  // 28 this surface offers. 4 of 28, told they were set and never applied.
  //
  // The cause is not a certification defect: `mappings-readiness.ts` certifies a
  // `manual` field with a null concept ON PURPOSE. So CERTIFIED does not imply
  // "has a concept", and this door was assuming it did.
  // ==========================================================================
  it('⚠️ A CONCEPT-LESS CONTROL IS REFUSED AT THE DOOR — never stored and never claimed', async () => {
    defFindUnique.mockResolvedValue({ mapping: { clinicalConcept: null } });
    const field = selects[0];
    const out = await run(field.fieldId, selectableOf(field)[0].displayText);

    // The whole defect in one assertion pair: the reply must not say yes...
    expect(out.ok).toBe(false);
    // ...and nothing may reach the database, because a stored override that
    // every fill declines is a correction the doctor believes is live.
    expect(overrideUpsert).not.toHaveBeenCalled();
    // The refusal names the control, so the doctor knows WHICH one and why.
    expect(out.label).toBe(field.originalLabel);
    expect(out.error).toMatch(/by hand|cannot be set/i);
  });

  it('⚠️ AND A MISSING MAPPING ROW IS THE SAME REFUSAL — absent is not permission', async () => {
    // `mapping` is an optional 1:1 relation, so "no row" and "row with a null
    // concept" are two distinct database states that must not diverge here.
    // Fail closed on both: `applyClinicianOverrides` declines both identically.
    defFindUnique.mockResolvedValue({ mapping: null });
    const field = selects[0];
    expect((await run(field.fieldId, selectableOf(field)[0].displayText)).ok).toBe(false);
    expect(overrideUpsert).not.toHaveBeenCalled();

    // ...and so is no field-definition row at all.
    defFindUnique.mockResolvedValue(null);
    expect((await run(field.fieldId, selectableOf(field)[0].displayText)).ok).toBe(false);
    expect(overrideUpsert).not.toHaveBeenCalled();
  });

  it('⚠️ THE CONCEPT IS READ FOR **THIS** COMPILED VERSION AND **THIS** FIELD', async () => {
    // A lookup keyed on the wrong compiled version would read another
    // template's mapping and admit or refuse on somebody else's answer.
    const field = selects[2];
    await run(field.fieldId, selectableOf(field)[0].displayText);
    expect(defFindUnique).toHaveBeenCalledTimes(1);
    const arg = defFindUnique.mock.calls[0][0] as { where: unknown };
    expect(arg.where).toEqual({
      compiledVersionId_fieldId: { compiledVersionId: 'cv-1', fieldId: field.fieldId },
    });
  });

  it('⚠️ NON-VACUITY — the happy path really can succeed for every one of the 28', async () => {
    // A suite of refusals proves nothing if the accept path is broken: that is
    // the half-proven direction canon names, and `retire-branch.sh`'s false
    // green is the reference case.
    for (const field of selects) {
      overrideUpsert.mockClear();
      const out = await run(field.fieldId, selectableOf(field)[0].displayText);
      expect(out.ok, `${field.fieldId} could not be set`).toBe(true);
      expect(overrideUpsert).toHaveBeenCalledTimes(1);
    }
  });

  // ══════════════════════════════════════════════════════════════════════════
  // ROUND FIVE — THE SIGN WINDOW, ON THIS DOOR TOO.
  // Round four closed it on the INSERT door and left the other two writers in
  // the same file read-then-act. These arms are the ones that were missing.
  // ══════════════════════════════════════════════════════════════════════════
  it('⚠️ THE WRITE HAPPENS ON THE **LOCKED** CONNECTION — kills `tx.` -> `prisma.`', async () => {
    const f = selects[0];
    const res = await run(f.fieldId, selectableOf(f)[0].displayText);
    expect(res.ok).toBe(true);
    expect(onTx.queryRaw, 'the FOR UPDATE re-read ran OUTSIDE the transaction').toBe(true);
    expect(
      onTx.upsert,
      'the correction was written on the top-level client, NOT the transactional ' +
        'one — the lock then guards a row this write never touches',
    ).toBe(true);
  });

  it('⚠️ THE RE-READ IS A REAL `FOR UPDATE` ON THE VISIT ROW', async () => {
    const f = selects[0];
    await run(f.fieldId, selectableOf(f)[0].displayText);
    const sql = String((lockedVisit.mock.calls[0][0] as { strings?: string[] }).strings?.join('?') ?? lockedVisit.mock.calls[0][0]);
    expect(sql).toMatch(/FOR UPDATE/);
    expect(sql).toMatch(/transcribe_visits/);
  });

  it('⚠️ REFUSES when the visit was SIGNED while the form was being checked', async () => {
    lockedVisit.mockResolvedValue([{ status: 'SIGNED', signedAt: new Date() }]);
    const f = selects[0];
    const res = await run(f.fieldId, selectableOf(f)[0].displayText);
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/signed while your form was being checked/);
    expect(overrideUpsert, 'a correction was written onto a signed visit').not.toHaveBeenCalled();
    expect(audit, 'an audit row claims a doctor act on a signed record').not.toHaveBeenCalled();
  });

  it('⚠️ BOTH SPELLINGS — `signedAt` alone refuses, even with status still READY', async () => {
    lockedVisit.mockResolvedValue([{ status: 'READY', signedAt: new Date() }]);
    const f = selects[0];
    const res = await run(f.fieldId, selectableOf(f)[0].displayText);
    expect(res.ok).toBe(false);
    expect(overrideUpsert).not.toHaveBeenCalled();
  });
});
