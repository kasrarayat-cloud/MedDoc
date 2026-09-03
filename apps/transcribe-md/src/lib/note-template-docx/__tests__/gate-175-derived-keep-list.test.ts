// ============================================================================
// #175(1) — THE COMPILER SCANS EVERY CONTAINER THE RENDERER COPIES VERBATIM.
// ----------------------------------------------------------------------------
// ⚠️ THIS IS THE BEHAVIOURAL HALF OF "ONE SYMBOL, ONE FILE". Sharing the symbol
// makes the two sets identical by construction; this asserts the CONSEQUENCE —
// that admission actually refuses a content carrier in EVERY one of them.
//
// The two used to be hand-written lists that drifted by nine names, and a
// `w:fldSimple` inside a `w:bookmarkStart` — the element Word emits as
// `_GoBack` in nearly every document — was admitted, survived the clear, and
// earned counted blank credit.
//
// Adding a name to `STRUCTURE_KEEP_WHOLE` without teaching admission reds this.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { FieldResolutionSchema, type TemplateTwinValidationResult } from '../../template-twin/ir';
import { STRUCTURE_KEEP_WHOLE } from '../structure-keep';
import { renderTemplateDocx } from '../renderer';
import { buildSyntheticDocx } from './synthetic-docx';

const VALIDATION: TemplateTwinValidationResult = {
  valid: true,
  issues: [],
  checkedAt: '2026-01-01T00:00:00.000Z',
  validatorVersion: 'template-field-validator/1.0.0',
};
const W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"';

/** A control whose content holds `inner`, compiled through the real compiler. */
async function admissionOf(inner: string) {
  const documentXml =
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document ${W}><w:body><w:p>` +
    `<w:sdt><w:sdtPr><w:id w:val="1750"/><w:alias w:val="Impression"/><w:tag w:val="imp"/>` +
    `<w:text/></w:sdtPr><w:sdtContent>${inner}</w:sdtContent></w:sdt></w:p></w:body></w:document>`;
  const source = await buildSyntheticDocx({ documentXml });
  const { compileTemplateDocx } = await import('../compiler');
  const ir = compileTemplateDocx(source);
  const refused = (ir.unsupported as Array<Record<string, unknown>>).filter(
    (u) => u.code === 'UNSUPPORTED_CONTROL_STRUCTURE',
  );
  const fields = ir.fields.filter(
    (f) => f.rendererBinding.partName === 'word/document.xml',
  );
  return { refused, fields, ir, source };
}

describe('#175(3) — every carrier is EXERCISED, and the refusal names IT', () => {
  it('⚠️ EACH CARRIER ALONE IN A PROPERTY BLOCK REFUSES, AND IS NAMED', async () => {
    // ⚠️ 24 OF 27 CARRIERS WERE DEAD MEMBERS, and the cause was laundering:
    // `r` and `t` cover each other, so a fixture holding `<w:r><w:t>` still
    // refuses with `r` removed from the set — naming `w:t`. A gate asserting
    // only `refused.length === 1` cannot tell the difference.
    //
    // So each carrier is placed ALONE, self-closing, with nothing else that
    // could refuse — and the DETAIL is asserted to name that carrier. Dropping
    // any member now reds its own iteration.
    const { CONTENT_CARRIERS } = await import('../compiler');
    expect(CONTENT_CARRIERS.size, 'the carrier set is suspiciously small').
      toBeGreaterThanOrEqual(20);
    const unexercised: string[] = [];
    for (const carrier of CONTENT_CARRIERS) {
      const { refused } = await admissionOf(
        `<w:p><w:pPr><w:${carrier}/></w:pPr><w:r><w:t>x</w:t></w:r></w:p>`,
      );
      const named = refused.some((r) => String(r.detail).includes(`w:${carrier}`));
      if (!named) unexercised.push(carrier);
    }
    expect(
      unexercised,
      'these carriers are in the set and no fixture proves they do anything — ' +
        'either they are dead members to prune, or the refusal is being made ' +
        'by a neighbour and the member is unproved',
    ).toEqual([]);
  });

  it('⚠️ THE w:tabs EXEMPTION, ARMED WITH A NON-CARRIER CONTROL', async () => {
    // ⚠️ THE PREVIOUS CONTROL WAS LAUNDERED AND NEVER REACHED `tab`. It used
    // `<w:pPr><w:r><w:tab/></w:r></w:pPr>` — `w:r` is itself a carrier, so the
    // refusal named `w:r` and the `tab` membership was never exercised.
    //
    // A tab STOP must be admitted; a BARE tab character — no run, nothing else
    // that could refuse — must be refused, and the detail must name `w:tab`.
    const stop = await admissionOf(
      '<w:p><w:pPr><w:tabs><w:tab w:val="left" w:pos="720"/></w:tabs></w:pPr>' +
        '<w:r><w:t>x</w:t></w:r></w:p>',
    );
    expect(stop.refused.length, 'a tab STOP was read as a tab character').toBe(0);
    expect(stop.fields.length).toBe(1);

    const character = await admissionOf(
      '<w:p><w:pPr><w:tab/></w:pPr><w:r><w:t>x</w:t></w:r></w:p>',
    );
    expect(character.refused.length, 'a bare tab CHARACTER was admitted').toBe(1);
    expect(String(character.refused[0]!.detail)).toContain('w:tab');
  });

  it('⚠️ THE RECURSION, ARMED AT DEPTH 2 — every fixture before this was depth 1', async () => {
    // `<w:pPr><w:rPr><w:sym/></w:rPr></w:pPr>` is the paragraph mark's run
    // properties, where a Wingdings tick legitimately nests. Removing
    // `propertyBlockCarrier`'s descent redded nothing, because every carrier
    // fixture placed the carrier one level down.
    const { refused, fields } = await admissionOf(
      '<w:p><w:pPr><w:rPr><w:sym w:font="Wingdings" w:char="F0FE"/></w:rPr></w:pPr>' +
        '<w:r><w:t>x</w:t></w:r></w:p>',
    );
    expect(refused.length, 'a depth-2 carrier was admitted').toBe(1);
    expect(fields.length).toBe(0);
  });

  it('⚠️ THE REFUSAL HAS TEETH — blocksCertification and clinicallyMaterial', async () => {
    // ⚠️ FLIPPING BOTH FLAGS TO `false` LEFT 5638 TESTS PASSING, byte-identical.
    // Every arm read only the `code`. With them off the refusal neither blocks
    // certification nor reaches the doctor — a template with a control nobody
    // understands would certify silently, which is the entire product the rule
    // exists to buy.
    const { refused } = await admissionOf(
      '<w:p><w:pPr><w:sym w:font="Wingdings" w:char="F0FE"/></w:pPr>' +
        '<w:r><w:t>x</w:t></w:r></w:p>',
    );
    expect(refused.length).toBe(1);
    expect(refused[0]!.blocksCertification, 'the refusal does not block').toBe(true);
    expect(refused[0]!.clinicallyMaterial, 'the refusal is not clinically material').
      toBe(true);
  });
});

describe('#175(1) — the derived keep-list, asserted behaviourally', () => {
  it('⚠️ EVERY container the clear copies verbatim refuses a carrier inside it', async () => {
    // ⚠️ NON-VACUITY FLOOR FIRST. A set that had silently emptied would make
    // this loop pass while testing nothing, and this codebase has shipped
    // exactly that shape.
    expect(STRUCTURE_KEEP_WHOLE.size, 'the keep-list is suspiciously small').
      toBeGreaterThanOrEqual(15);

    const admitted: string[] = [];
    for (const container of STRUCTURE_KEEP_WHOLE) {
      // `w:sdtPr`/`w:sdtEndPr` belong to the control itself, so they are placed
      // where they legally sit rather than inside the content.
      const inner =
        container === 'sdtPr' || container === 'sdtEndPr'
          ? `<w:p><w:r><w:t>x</w:t></w:r></w:p>`
          : `<w:p><w:${container}><w:fldSimple w:instr=" PAGE "/></w:${container}>` +
            `<w:r><w:t>x</w:t></w:r></w:p>`;
      if (container === 'sdtPr' || container === 'sdtEndPr') continue;
      const { refused } = await admissionOf(inner);
      if (refused.length === 0) admitted.push(container);
    }
    expect(
      admitted,
      'these containers are copied VERBATIM by the clear and admission does ' +
        'not scan them — a content carrier inside one survives into the ' +
        'rendered document under a counted blank proof',
    ).toEqual([]);
  });

  it('a clean control is still admitted — the other way to be wrong', async () => {
    const { refused, fields } = await admissionOf(
      '<w:p><w:pPr><w:jc w:val="left"/></w:pPr><w:r><w:t>Enter impression</w:t></w:r></w:p>',
    );
    expect(refused.length).toBe(0);
    expect(fields.length).toBe(1);
  });

  it('⚠️ THE RENDERER AND THE COMPILER READ THE SAME SYMBOL, not two lists', async () => {
    // A structural assertion to sit beside the behavioural one: if somebody
    // reintroduces a local list in either file, the loop above still passes
    // while the drift is back. This is the cheap direct check.
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    for (const file of ['renderer.ts', 'compiler.ts']) {
      const text = readFileSync(join(__dirname, '..', file), 'utf8');
      // ⚠️ QUOTE-AGNOSTIC ON PURPOSE. The two files use different quote styles,
      // and an assertion that pins one of them would red on a formatting
      // change while the property it cares about was untouched — canon 72.
      expect(
        /from ['"]\.\/structure-keep['"]/.test(text),
        `${file} does not import the shared keep-list`,
      ).toBe(true);
      expect(
        /const STRUCTURE_KEEP_WHOLE[^=]*=\s*new Set/.test(text),
        `${file} declares its own copy of the keep-list`,
      ).toBe(false);
    }
  });
});
