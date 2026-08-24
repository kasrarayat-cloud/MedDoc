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
import { isWordPlaceholderOption } from '@/lib/note-template-docx/placeholder-option';

const visitFindFirst = vi.fn();
const templateFindFirst = vi.fn();
const overrideUpsert = vi.fn();
const invalidate = vi.fn();
const audit = vi.fn();

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: { findFirst: (...a: unknown[]) => visitFindFirst(...a) },
    noteTemplate: { findFirst: (...a: unknown[]) => templateFindFirst(...a) },
    templateTwinFieldOverride: { upsert: (...a: unknown[]) => overrideUpsert(...a) },
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

const UNSIGNED = {
  id: 'v1',
  status: 'READY',
  noteTemplateId: 'tpl-1',
  noteTemplateVersion: 1,
  user: { practiceId: 'prac-1' },
};

beforeEach(() => {
  visitFindFirst.mockReset();
  templateFindFirst.mockReset();
  overrideUpsert.mockReset();
  invalidate.mockReset();
  audit.mockReset();
  visitFindFirst.mockResolvedValue(UNSIGNED);
  templateFindFirst.mockResolvedValue({
    templateTwinCompiledVersion: {
      certificationStatus: 'CERTIFIED',
      compiledDocumentIr: ir,
    },
  });
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
    const option = field.allowedOptions[0];
    const out = await run(field.fieldId, option.displayText);

    expect(out.ok).toBe(true);
    // The claim in the reply and the write are ONE fact, or the doctor is told
    // something that did not happen.
    expect(overrideUpsert).toHaveBeenCalledTimes(1);
    const arg = overrideUpsert.mock.calls[0][0] as Record<string, never>;
    expect(arg).toMatchObject({
      where: { visitId_fieldId: { visitId: 'v1', fieldId: field.fieldId } },
      create: {
        practiceId: 'prac-1',
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
    await run(field.fieldId, field.allowedOptions[0].displayText);
    const arg = overrideUpsert.mock.calls[0][0] as { where: { visitId_fieldId: unknown } };
    expect(arg.where.visitId_fieldId).toEqual({ visitId: 'v1', fieldId: field.fieldId });
  });

  it('⚠️ the cached document is INVALIDATED — a correction nobody can see is made twice', async () => {
    const field = selects[0];
    await run(field.fieldId, field.allowedOptions[0].displayText);
    expect(invalidate).toHaveBeenCalledWith('v1');
  });

  it('⚠️ A SIGNED VISIT IS REFUSED AT THE DOOR, AND NOTHING IS WRITTEN', async () => {
    visitFindFirst.mockResolvedValue({ ...UNSIGNED, status: 'SIGNED' });
    const field = selects[0];
    const out = await run(field.fieldId, field.allowedOptions[0].displayText);
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
      field.allowedOptions.map((o) => o.displayText),
    );
  });

  it('⚠️ "Choose an item." IS NOT SETTABLE — the third layer, at the door', async () => {
    // The compiler now strips the placeholder, so on THIS compiled IR it is
    // already absent. The arm is written against the WRITE PATH's own filter so
    // that it still refuses on a compiled version that predates the compiler
    // change — which is the state of the ONE certified twin in production.
    const field = selects[0];
    const out = await run(field.fieldId, 'Choose an item.');
    expect(out.ok).toBe(false);
    expect(overrideUpsert).not.toHaveBeenCalled();
    // And it is not offered back as a choice either.
    expect(out.options?.some((o) => isWordPlaceholderOption(o))).toBe(false);
  });

  it('⚠️ AN UNCERTIFIED TWIN OFFERS NOTHING — addressing into a structure that does not ship', async () => {
    templateFindFirst.mockResolvedValue({
      templateTwinCompiledVersion: {
        certificationStatus: 'NEEDS_CONFIRMATION',
        compiledDocumentIr: ir,
      },
    });
    const out = await run(selects[0].fieldId, selects[0].allowedOptions[0].displayText);
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
    const out = await run(selects[0].fieldId, selects[0].allowedOptions[0].displayText);
    expect(out.ok).toBe(false);
    expect(out.error).toMatch(/not found/i);
    expect(overrideUpsert).not.toHaveBeenCalled();
  });

  it('the write is ATTRIBUTED and AUDITED', async () => {
    const field = selects[0];
    await run(field.fieldId, field.allowedOptions[0].displayText);
    expect(audit).toHaveBeenCalledTimes(1);
    const a = audit.mock.calls[0][0] as { metadata: Record<string, unknown>; targetId: string };
    expect(a.targetId).toBe('v1');
    expect(a.metadata.surface).toBe('template_control_override');
    expect(a.metadata.fieldId).toBe(field.fieldId);
  });

  it('⚠️ NON-VACUITY — the happy path really can succeed for every one of the 28', async () => {
    // A suite of refusals proves nothing if the accept path is broken: that is
    // the half-proven direction canon names, and `retire-branch.sh`'s false
    // green is the reference case.
    for (const field of selects) {
      overrideUpsert.mockClear();
      const out = await run(field.fieldId, field.allowedOptions[0].displayText);
      expect(out.ok, `${field.fieldId} could not be set`).toBe(true);
      expect(overrideUpsert).toHaveBeenCalledTimes(1);
    }
  });
});
