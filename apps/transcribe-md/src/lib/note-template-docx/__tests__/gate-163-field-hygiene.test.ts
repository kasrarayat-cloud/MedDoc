// ============================================================================
// #163 RULE (2) — TEMPLATE HYGIENE IS FLAGGED AT COMPILE, LOUDLY, AND BLOCKS
// NOTHING.
// ----------------------------------------------------------------------------
// The runtime no longer clears an unfilled field (#163 rule 1), so leftover
// content in a template now PRINTS. That is the deliberate trade: a wrong
// deletion is silent and removes clinical text nobody notices is gone, while a
// wrong flag is loud and costs a doctor ten seconds once, at the template.
//
// This gate exists because the instrument it replaces had NONE. #162(c)'s byte
// comparison could be deleted entirely — `if (false && …)` — and 676 tests
// stayed green, including the two arms named for it. A check nothing fails
// without is not a check.
//
// ⚠️ THE ARMS ARE WRITTEN IN BOTH DIRECTIONS. "It fires" is half a gate; a
// detector that fires on everything is as useless as one that fires on
// nothing, and only the clean-field arm can tell them apart.
// ============================================================================
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import { canonicalSha256 } from '../../template-twin/canonical';
import { validateTemplateTwin } from '../../template-twin/validation';
import { compileTemplateDocx } from '../compiler';
import {
  FIELD_LEFTOVER_CONTENT,
  FIELD_RESTING_CONTENT_IS_OPTION,
} from '../field-hygiene';
import { buildSyntheticDocx } from './synthetic-docx';

const doc = (body: string) =>
  `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
  `<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" ` +
  `xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml">` +
  `<w:body>${body}</w:body></w:document>`;

/** One `w:text` content control, with whatever content the arm needs. */
const control = (id: string, alias: string, content: string) =>
  `<w:p><w:sdt><w:sdtPr><w:alias w:val="${alias}"/><w:tag w:val="${alias}"/>` +
  `<w:id w:val="${id}"/><w:text/></w:sdtPr>` +
  `<w:sdtContent>${content}</w:sdtContent></w:sdt></w:p>`;

async function compile(body: string) {
  return compileTemplateDocx(await buildSyntheticDocx({ documentXml: doc(body) }));
}
// ⚠️ SCOPED BY LABEL, NOT BY GLOBAL COUNT. `buildSyntheticDocx` contributes a
// header part carrying its own content control, so a whole-document count
// measures the fixture as much as the arm. Selecting the field under test is
// what keeps each assertion about the thing it names.
const hygieneOf = (ir: Awaited<ReturnType<typeof compile>>, label: string) =>
  ir.unsupported.filter((u) => u.code === FIELD_LEFTOVER_CONTENT && u.label === label);
const fieldNamed = (ir: Awaited<ReturnType<typeof compile>>, label: string) =>
  ir.fields.filter((f) => f.originalLabel === label);

describe('#163 rule (2) — leftover content is flagged at compile', () => {
  it('TEXT: a placeholder is flagged, and the detail names what will print', async () => {
    const ir = await compile(control('200', 'Assessment', '<w:r><w:t>Enter assessment</w:t></w:r>'));
    expect(fieldNamed(ir, 'Assessment').length, 'fixture compiled no such field — the arm would be vacuous').toBe(1);
    const found = hygieneOf(ir, 'Assessment');
    expect(found.length).toBe(1);
    // ⚠️ THE DETAIL IS THE PRODUCT. A finding a doctor cannot act on is a log
    // line, so the arm pins that the offending text reaches the sentence.
    expect(found[0]!.detail).toContain('Enter assessment');
    expect(found[0]!.label).toBe('Assessment');
  });

  it('OBJECT: a w:sym is flagged — the case no text-clearing could ever reach', async () => {
    // This is the shape that ended #162's approach: a Wingdings check mark
    // printed for a field the encounter never mentioned, and every version of
    // the clearing machinery missed it because it carries no `w:t`.
    const ir = await compile(
      control('201', 'Anticoagulated', '<w:r><w:sym w:font="Wingdings" w:char="F0FC"/></w:r>'),
    );
    expect(fieldNamed(ir, 'Anticoagulated').length).toBe(1);
    const found = hygieneOf(ir, 'Anticoagulated');
    expect(found.length).toBe(1);
    expect([found[0]!.label, found[0]!.detail.includes('sym')]).toEqual(['Anticoagulated', true]);
  });

  it('⚠️ THE OTHER DIRECTION: a genuinely empty field is NOT flagged', async () => {
    // Without this, a detector that flags everything passes both arms above.
    const ir = await compile(control('202', 'Clean', '<w:r><w:t></w:t></w:r>'));
    expect(fieldNamed(ir, 'Clean').length, 'fixture compiled no such field — the arm would be vacuous').toBe(1);
    expect(hygieneOf(ir, 'Clean').length).toBe(0);
  });

  it('LOUD, NOT FATAL: the finding is a warning and blocks nothing', async () => {
    const ir = await compile(control('203', 'Assessment', '<w:r><w:t>Enter assessment</w:t></w:r>'));
    const found = hygieneOf(ir, 'Assessment');
    expect(found.length).toBe(1);
    expect([found[0]!.blocksCertification, found[0]!.clinicallyMaterial]).toEqual([false, false]);
    expect(ir.stats.blockingUnsupported).toBe(0);

    // ⚠️ AND THROUGH THE VALIDATOR, NOT ONLY ON THE FLAGS. The generic arm
    // grades `blocksCertification || clinicallyMaterial` as BLOCKING, and
    // `clinicallyMaterial` is true at every other compiler site — so this code
    // needs its own named arm to come out a warning, and asserting the flags
    // alone would not prove it got one.
    const issues = validateTemplateTwin({
      fields: ir.fields,
      mappings: [],
      resolutions: [],
      facts: [],
      unsupported: ir.unsupported,
      tables: ir.tables,
    }).issues.filter((i) => i.code === FIELD_LEFTOVER_CONTENT);
    // Both fields carry leftover content (the fixture's header control too), so
    // the claim is about SEVERITY across all of them, not about the count.
    expect(issues.length).toBeGreaterThan(0);
    expect(issues.every((i) => i.severity === 'warning')).toBe(true);
    expect(issues.some((i) => i.message.includes('Enter assessment'))).toBe(true);
  });

  // ══ A(ii) — THE ONE SHAPE THAT BLOCKS ═════════════════════════════════════

  it('BLOCKS: a selection control resting on ONE OF ITS OWN OPTIONS', async () => {
    // ⚠️ THE FIXTURE IS THE PROOF. `synthetic-docx`'s comboBox rests on
    // "Initial", which is one of its own two options — so on a note where the
    // encounter said nothing, that control prints as if the choice had been
    // made. This is the seventeenth failure of the #157(d) collision: the only
    // one of them that was a real defect rather than a definition change.
    const ir = compileTemplateDocx(await buildSyntheticDocx());
    const blocking = ir.unsupported.filter(
      (u) => u.code === FIELD_RESTING_CONTENT_IS_OPTION,
    );
    expect(blocking.length).toBe(1);
    expect(blocking[0]!.label).toBe('Encounter category');
    expect(blocking[0]!.blocksCertification).toBe(true);
    // The refusal NAMES the offending value, or the doctor cannot act on it.
    expect(blocking[0]!.detail).toContain('Initial');
    expect(ir.stats.blockingUnsupported).toBeGreaterThan(0);
  });

  it('⚠️ AND IT IS SET MEMBERSHIP, NOT RESEMBLANCE — a near-miss does NOT block', async () => {
    // Without this the rule could be a substring or fuzzy match and both arms
    // above would still pass. "Initial assessment" CONTAINS an option value and
    // is not one, so it is ordinary hygiene.
    const ir = await compile(
      `<w:p><w:sdt><w:sdtPr><w:alias w:val="Category"/><w:id w:val="210"/>` +
        `<w:comboBox><w:listItem w:displayText="Initial" w:value="initial"/>` +
        `<w:listItem w:displayText="Follow-up" w:value="follow_up"/></w:comboBox>` +
        `</w:sdtPr><w:sdtContent><w:r><w:t>Initial assessment</w:t></w:r></w:sdtContent></w:sdt></w:p>`,
    );
    expect(fieldNamed(ir, 'Category').length).toBe(1);
    expect(
      ir.unsupported.filter(
        (u) => u.code === FIELD_RESTING_CONTENT_IS_OPTION && u.label === 'Category',
      ).length,
    ).toBe(0);
    expect(hygieneOf(ir, 'Category').length).toBe(1);
  });

  it('⚠️ THE REAL CUSTOMER TEMPLATE: 28 dropdowns, and NOT ONE of them blocks', async () => {
    // ⚠️ THIS ARM EXISTS BECAUSE THE FIRST VERSION OF A(ii) FAILED IT, HARD.
    //
    // Word seeds every dropdown with a first `listItem` reading "Choose an
    // item." — stored exactly like a real option. The rule matched it and
    // BLOCKED ALL 28 DROPDOWNS of the only real form this programme has,
    // refusing the customer's entire template on Word's own furniture. A(iii)
    // rules stock scaffolding a non-blocking flag; A(ii) blocks only a REAL
    // option value. The synthetic fixture could never have shown this, because
    // its comboBox rests on a genuine option.
    // Same resolution the other WM_IOV suites use, rather than a hand-counted
    // chain of `..` that breaks the day this file moves.
    const bytes = new Uint8Array(
      readFileSync(resolve(process.cwd(), '../../WM IOV Template.docx')),
    );
    const ir = compileTemplateDocx(bytes);
    expect(ir.fields.length, 'fixture is not the expected template').toBe(80);
    expect(
      ir.unsupported.filter((u) => u.code === FIELD_RESTING_CONTENT_IS_OPTION).length,
    ).toBe(0);
    // NON-VACUITY: the dropdowns really are dirty, they are just dirty in the
    // way A(iii) covers — so this is "flagged, not blocked", not "nothing seen".
    expect(
      ir.unsupported.filter((u) => u.code === FIELD_LEFTOVER_CONTENT).length,
    ).toBe(28);
    expect(ir.stats.blockingUnsupported).toBe(0);
  });

  // ══ A(iii) — WORD SCAFFOLDING, AND THE CHECKBOX THAT MUST NOT BE FLAGGED ══

  it('an UNCHECKED checkbox is the blank state, NOT leftover content', async () => {
    // ⚠️ THIS ARM EXISTS BECAUSE THE FIRST VERSION GOT IT WRONG. It flagged
    // every checkbox, since an unfilled one holds `☐` and that is visible text.
    // But `☐` is exactly what a blank checkbox should look like — the doctor's
    // own blank representation, which is the thing #163 rule (1) preserves. A
    // check that fires on every checkbox is one nobody reads.
    const ir = compileTemplateDocx(await buildSyntheticDocx());
    expect(
      ir.fields.some((f) => f.originalLabel === 'Medication reviewed'),
      'fixture has no checkbox — the arm would be vacuous',
    ).toBe(true);
    expect(hygieneOf(ir, 'Medication reviewed').length).toBe(0);
  });

  it('a CHECKED checkbox blocks — it prints as an answer nobody gave', async () => {
    // The other direction, and it is the same rule: a checkbox's two declared
    // states ARE its option values, so resting on the CHECKED one is a false
    // assertion exactly as resting on a dropdown option is. Read from the
    // control's own `w:checkedState`, never from a list of known glyphs.
    const ir = await compile(
      `<w:p><w:sdt><w:sdtPr><w:alias w:val="Anticoagulated"/><w:id w:val="211"/>` +
        `<w14:checkbox><w14:checked w14:val="1"/><w14:checkedState w14:val="2612"/>` +
        `<w14:uncheckedState w14:val="2610"/></w14:checkbox>` +
        `</w:sdtPr><w:sdtContent><w:r><w:t>\u2612</w:t></w:r></w:sdtContent></w:sdt></w:p>`,
    );
    expect(fieldNamed(ir, 'Anticoagulated').length).toBe(1);
    expect(
      ir.unsupported.filter(
        (u) => u.code === FIELD_RESTING_CONTENT_IS_OPTION && u.label === 'Anticoagulated',
      ).length,
    ).toBe(1);
  });

  it('⚠️ THE OUTAGE GUARD: hygiene findings are EXCLUDED from structureSha256', async () => {
    // `assertSourceMatchesIr` compares this hash on EVERY fill against the
    // STORED IR of every already-compiled template. If a new advisory moved it,
    // every certified twin in the database — production's included — becomes
    // unfillable, and each recompute path degrades SILENTLY to the styled
    // export. `gate-twin-certified-pin-matches-compiler` caught exactly that
    // when these findings first joined the register.
    //
    // ⚠️ THE OBVIOUS ARM IS THE WRONG ONE, AND IT WAS WRITTEN FIRST: comparing
    // a "dirty" document against a "clean" one asserts nothing, because the two
    // differ STRUCTURALLY — the placeholder text IS part of the structure. That
    // version failed for a correct reason and would have been "fixed" by
    // deleting it.
    //
    // The property is about what the hash READS, so it is asserted there: the
    // register the hash sees must NOT be the register the IR carries. Remove
    // the filter in `compiler.ts` and these two hashes become equal.
    const ir = await compile(control('204', 'Assessment', '<w:r><w:t>Enter assessment</w:t></w:r>'));
    expect(hygieneOf(ir, 'Assessment').length, 'nothing to exclude — the arm would be vacuous').toBe(1);

    const withHygiene = canonicalSha256({
      fields: ir.fields,
      tables: ir.tables,
      nodes: ir.nodes,
      unsupported: ir.unsupported,
    });
    const withoutHygiene = canonicalSha256({
      fields: ir.fields,
      tables: ir.tables,
      nodes: ir.nodes,
      unsupported: ir.unsupported.filter((u) => u.code !== FIELD_LEFTOVER_CONTENT),
    });
    // The two registers really do differ, or the comparison below is vacuous.
    expect(withHygiene).not.toBe(withoutHygiene);
    // And the shipped hash is the one that never saw them.
    expect(ir.structureSha256).toBe(withoutHygiene);
  });
});
