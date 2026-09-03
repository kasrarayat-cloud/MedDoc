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

/**
 * A control whose content holds `inner`, compiled through the real compiler.
 *
 * `carrierIn` places a `w:fldSimple` inside the control's OWN `w:sdtPr` or
 * `w:sdtEndPr` — the only legal position for those two — so the keep-list loop
 * can exercise them instead of skipping them.
 */
async function admissionOf(inner: string, carrierIn?: 'sdtPr' | 'sdtEndPr', prText = '') {
  const smuggled = `<w:fldSimple w:instr=" PAGE "/>`;
  const documentXml =
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document ${W}><w:body><w:p>` +
    `<w:sdt><w:sdtPr><w:id w:val="1750"/><w:alias w:val="Impression"/><w:tag w:val="imp"/>` +
    `<w:text/>${carrierIn === 'sdtPr' ? smuggled : ''}${prText}</w:sdtPr>` +
    (carrierIn === 'sdtEndPr' ? `<w:sdtEndPr>${smuggled}</w:sdtEndPr>` : '') +
    `<w:sdtContent>${inner}</w:sdtContent></w:sdt></w:p></w:body></w:document>`;
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

// ⚠️ ITS OWN FIXTURE, NOT `admissionOf`. That helper always writes an alias
// AND a tag, so it can never exercise the label FALLBACK — the very path 27 of
// the customer's 28 controls take. A helper that cannot express the case is not
// a helper to widen mid-audit.
async function refusalWithoutIdentity(containerText: string) {
  const documentXml =
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document ${W}><w:body><w:p>` +
    `<w:r><w:t>${containerText}</w:t></w:r>` +
    `<w:sdt><w:sdtPr><w:id w:val="1750"/><w:text/><w:fldSimple w:instr=" PAGE "/></w:sdtPr>` +
    `<w:sdtContent><w:r><w:t>x</w:t></w:r></w:sdtContent></w:sdt>` +
    `</w:p></w:body></w:document>`;
  const source = await buildSyntheticDocx({ documentXml });
  const { compileTemplateDocx } = await import('../compiler');
  const ir = compileTemplateDocx(source);
  return (ir.unsupported as Array<Record<string, unknown>>).filter(
    (u) => u.code === 'UNSUPPORTED_CONTROL_STRUCTURE',
  );
}

describe('the final pass fixes — the refusal must INFORM, and a checkbox is never blank', () => {
  it('⚠️ A REFUSED CONTROL WITH NO ALIAS AND NO TAG STILL GETS A REAL LABEL', async () => {
    // ⚠️ MEASURED ON THE REAL CUSTOMER TEMPLATE: 28 controls, ONE alias, ONE
    // tag, TWENTY-SEVEN carrying neither. The refusal path passed
    // `identity.label` — `alias ?? tag`, i.e. NULL for all 27 — while
    // `chooseFieldLabel`, forty lines away in the same function, falls back to
    // the container's own text.
    //
    // Without this the doctor-facing list from #175(2)(b) renders 27 identical
    // "Unnamed control" rows: the count became a list carrying no more
    // information than the number did, which was the entire point of building
    // it. The harm is one layer down from the thing that was proved.
    const refused = await refusalWithoutIdentity('Anticoagulation status:');
    expect(refused.length).toBe(1);
    expect(refused[0]!.label, 'the refusal carried no label at all').not.toBeNull();
    expect(String(refused[0]!.label)).toContain('Anticoagulation');
  });

  it('⚠️ A CHECKBOX CAN NEVER EARN BLANK CREDIT — the renderer always writes to it', async () => {
    // The renderer writes TWO things for a null checkbox — `w:val="0"` and the
    // `☐` glyph — so a `blank` proof about one asserts something demonstrably
    // false. ⚠️ ALL THREE EXISTING GUARDS PASS FOR A CHECKBOX BY CONSTRUCTION:
    // it genuinely resolves null, its eligibility is whatever the writer wrote,
    // and the kind list did not name it. Two token edits — relabel to `blank`,
    // add `blankEligible: 'eligible'` — took a template from BLOCKED to
    // CERTIFIED, and `blank` returns before the expectation check so no hash
    // was needed either.
    const { countsAsBlankProof } = await import('../../template-twin/blank-proof-count');
    const ctx = (kind: string) => ({
      bindingOf: () => 'content_control',
      resolvedNull: () => true,
      kindOf: () => kind,
    });
    const forged = { kind: 'blank', fieldId: 'f1', blankEligible: 'eligible' };
    expect(
      countsAsBlankProof(forged as never, ctx('checkbox') as never),
      'a checkbox bought blank credit',
    ).toBe(false);
    // and under the `emptied` label too, which carries a real hash
    expect(
      countsAsBlankProof(
        { ...forged, kind: 'emptied', expectedSpanSha256: 'a'.repeat(64) } as never,
        ctx('checkbox') as never,
      ),
    ).toBe(false);
    // ⚠️ NON-VACUITY: the same shape on a narrative field STILL counts, so this
    // measures the KIND and not a census that refuses everything.
    expect(countsAsBlankProof(forged as never, ctx('narrative_text') as never)).toBe(true);
  });
});

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
    const misattributed: string[] = [];
    for (const container of STRUCTURE_KEEP_WHOLE) {
      // `w:sdtPr`/`w:sdtEndPr` belong to the control itself, so they are placed
      // where they legally sit rather than inside the content.
      // ⚠️ #175 FINAL PASS — `sdtPr`/`sdtEndPr` USED TO BE `continue`d PAST,
      // UNDER A FAILURE MESSAGE SAYING *EVERY* CONTAINER. They are the control's
      // own children, so they cannot be placed in the content — but skipping
      // them left the loop's watched set two names short of its named set
      // (canon 28), and BOTH of those two turned out to be the hole: the
      // renderer's `sdtBoundedClearPatches` skips them outright, so neither
      // `subtreeHasNoCharacterData` nor `gapIsInvisible` has ever seen them.
      // They are now exercised where they LEGALLY SIT, via `admissionOf`'s
      // third argument, instead of being excused.
      const inner =
        container === 'sdtPr' || container === 'sdtEndPr'
          ? `<w:p><w:r><w:t>x</w:t></w:r></w:p>`
          : `<w:p><w:${container}><w:fldSimple w:instr=" PAGE "/></w:${container}>` +
            `<w:r><w:t>x</w:t></w:r></w:p>`;
      const { refused } = await admissionOf(inner, container === 'sdtPr' || container === 'sdtEndPr' ? container : undefined);
      if (refused.length === 0) {
        admitted.push(container);
        continue;
      }
      // ⚠️ AND THE REFUSAL MUST NAME *THIS* CONTAINER — the arm's own headline
      // says "the refusal names IT", and for the container half it did not
      // check. Any refusal, for any reason, satisfied the iteration: making the
      // doctor-facing detail always say `a w:pPr block contains a …`,
      // misnaming the container on every refusal in the product, redded 0 of
      // 756. A refusal that misdirects is worse than a count, because it sends
      // the doctor to the wrong control in their own document.
      if (!refused.some((r) => String(r.detail).includes(`w:${container}`))) {
        misattributed.push(`${container} -> ${String(refused[0]!.detail).slice(0, 90)}`);
      }
    }
    expect(
      misattributed,
      'the refusal names a DIFFERENT container than the one holding the ' +
        'carrier — the doctor is pointed at the wrong part of their document',
    ).toEqual([]);
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

// ============================================================================
// #175 FINAL PASS — THE ADMITTED SET LOSES TWO SHAPES IT NEVER UNDERSTOOD.
// ----------------------------------------------------------------------------
// The terminal adversarial pass drove the real compiler and the real renderer
// and found the single question answered YES twice: a control ADMITTED, its
// content SURVIVING verbatim into `word/document.xml` inside the field's own
// binding span, and the field holding a COUNTED blank proof with
// `verification.verified === true`.
//
//   1. FOURTEEN members of `EG_RunInnerContent` were absent from
//      `CONTENT_CARRIERS`. Placed inside a kept-whole `w:rPr` — the position
//      the #174 pass measured a `w:sym` surviving and printing from — each was
//      admitted and counted. Six of them PRINT TEXT: `w:pgNum`, and the six
//      date elements, which put TODAY'S DATE into a field certified blank.
//
//   2. CHARACTER DATA in the control's OWN `w:sdtPr`/`w:sdtEndPr` was invisible
//      to both sides. `propertyBlockCarrier` skipped `#text`; the renderer's
//      `sdtBoundedClearPatches` skips those two children outright, so neither
//      `subtreeHasNoCharacterData` (#173) nor `gapIsInvisible` (#172(3)) has
//      ever looked at them. The byte-identical string one element over, inside
//      `w:sdtContent`, is a hard refusal.
//
// ⚠️ THESE ARMS ASSERT THE HARM, NOT THE LABEL. Every earlier version of this
// gate read `refused.length` and stopped. The whole arc's lesson is that a
// label is not an outcome, so each row here renders the document and asserts
// that nothing survives holding blank credit.
// ============================================================================
describe('#175 final — the admitted set, asserted by OUTCOME', () => {
  /** Compile AND render all-null, and report what actually reached the page. */
  async function harmOf(opts: { pr?: string; end?: string; inner?: string }) {
    const inner = opts.inner ?? '<w:r><w:t>Enter anticoagulation</w:t></w:r>';
    const documentXml =
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document ${W} ` +
      `xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" ` +
      `xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">` +
      `<w:body><w:p><w:sdt><w:sdtPr><w:id w:val="1751"/><w:alias w:val="Anticoagulation"/>` +
      `<w:tag w:val="anticoag"/><w:text/>${opts.pr ?? ''}</w:sdtPr>${opts.end ?? ''}` +
      `<w:sdtContent>${inner}</w:sdtContent></w:sdt></w:p></w:body></w:document>`;
    const source = await buildSyntheticDocx({ documentXml });
    const { compileTemplateDocx } = await import('../compiler');
    const { countsAsBlankProof } = await import('../../template-twin/blank-proof-count');
    const ir = compileTemplateDocx(source);
    const refused = (ir.unsupported as Array<Record<string, unknown>>).filter(
      (u) => u.code === 'UNSUPPORTED_CONTROL_STRUCTURE',
    );
    const resolutions = ir.fields.map((f) =>
      FieldResolutionSchema.parse({
        fieldId: f.fieldId, status: 'not_mentioned', value: null, sourceFactIds: [],
        evidenceAnchorIds: [], selectedOptionOrdinal: null,
        reasonCode: 'blank_when_unsaid', clinicianReviewed: false,
      }),
    );
    const rendered = await renderTemplateDocx({ source, ir, resolutions, validation: VALIDATION });
    const { inspectDocxPackage } = await import('../package-security');
    const read = (buf: Buffer | Uint8Array) =>
      Buffer.from(
        inspectDocxPackage(buf).zip.entries.get('word/document.xml')!.bytes,
      ).toString('utf8');
    const bindingOf = (id: string) =>
      ir.fields.find((f) => f.fieldId === id)?.rendererBinding.bindingType as string | undefined;
    const kindOf = (id: string) => ir.fields.find((f) => f.fieldId === id)?.kind as string | undefined;
    const bodyProofs = ((rendered.verification.fields ?? []) as unknown as Array<
      Record<string, unknown>
    >).filter((p) => p.partName === 'word/document.xml');
    return {
      refused,
      bodyFields: ir.fields.filter((f) => f.rendererBinding.partName === 'word/document.xml'),
      sourceXml: read(source),
      outputXml: read(rendered.document),
      counted: bodyProofs.filter((p) =>
        countsAsBlankProof(p as never, { bindingOf, resolvedNull: () => true, kindOf })),
    };
  }

  /**
   * `EG_RunInnerContent` — every element OOXML permits as a direct child of
   * `w:r`, i.e. every element the schema itself says can PRINT.
   *
   * ⚠️ WRITTEN DOWN HERE, NOT DERIVED FROM `CONTENT_CARRIERS`. A list read out
   * of the thing it is checking cannot fail (canon 31's predetermined control);
   * this one is transcribed from the schema group and reds when the set drifts
   * from it.
   */
  const RUN_INNER_CONTENT: readonly string[] = [
    'br', 't', 'contentPart', 'delText', 'instrText', 'delInstrText',
    'noBreakHyphen', 'softHyphen', 'dayShort', 'monthShort', 'yearShort',
    'dayLong', 'monthLong', 'yearLong', 'annotationRef', 'footnoteRef',
    'endnoteRef', 'separator', 'continuationSeparator', 'sym', 'pgNum', 'cr',
    'tab', 'object', 'pict', 'fldChar', 'ruby', 'footnoteReference',
    'endnoteReference', 'commentReference', 'drawing', 'ptab',
    'lastRenderedPageBreak',
  ];

  // ⚠️ THE OTHER TEN. `RUN_INNER_CONTENT` covers 33 of the 43 members, and the
  // pass measured what the remaining ten cost: dropping `txbxContent` — a text
  // box's entire body — redded 0 of 756. The carrier LOOP cannot catch a
  // deletion because it iterates the set, so deleting a member deletes its own
  // test; only a list written somewhere else can.
  //
  // These are not run-inner-content: they are the BLOCK and FIELD constructs
  // that can sit inside a property container and lead to printed text.
  //
  // ⚠️ WHAT THIS ARM CLAIMS, EXACTLY — it is a DELETION DETECTOR for the set,
  // not a proof that each member is independently NECESSARY. Several are
  // reachable only through `w:p`/`w:r`/`w:t`, which are members already, so a
  // neighbour would refuse even with them absent (canon 62). Presence is still
  // worth pinning: a member dropped by a refactor is otherwise invisible, and
  // `txbxContent` was measured red-nothing on deletion.
  //
  // ⚠️ AND ONE ENTRY WAS REFUTED BY MEASUREMENT AND REMOVED, recorded because
  // the refutation is the useful part (canon 17). `w:tc` was on this list on
  // the reasoning that a table cell carries content. It does — but ONLY through
  // `w:p`, which is already a member, so a `w:tc` holding a doctor's stale text
  // refuses today with `tc` absent from the set (measured: 1 refusal, identical
  // to the `w:tbl` control). Asserting it would have pinned a member the code
  // does not need. Each entry is named with what a doctor would see if it
  // survived a clear it should not have:
  const STRUCTURAL_CARRIERS: readonly (readonly [string, string])[] = [
    ['r', 'a run — the ordinary carrier of every visible character'],
    ['p', 'a whole paragraph, with its runs'],
    ['tbl', 'a whole table, with every row and cell'],
    ['sdt', 'a nested content control, and everything inside it'],
    ['fldSimple', 'a simple field — its cached result is literal text'],
    ['txbxContent', "a text box's entire body"],
    ['oMath', 'an equation'],
    ['oMathPara', 'an equation paragraph'],
    ['subDoc', 'an embedded subdocument reference'],
    ['altChunk', 'imported external content (HTML/RTF/another .docx)'],
  ];

  it('⚠️ CONTENT_CARRIERS ALSO HOLDS THE BLOCK CONSTRUCTS THAT PRINT', async () => {
    const { CONTENT_CARRIERS } = await import('../compiler');
    const missing = STRUCTURAL_CARRIERS.filter(([n]) => !CONTENT_CARRIERS.has(n));
    expect(
      missing.map(([n, why]) => `w:${n} (${why})`),
      'a member of the shipped carrier set vanished; the carrier LOOP cannot ' +
        'see this because it iterates the set, so deleting a member deletes ' +
        'its own test — this list is the only thing that reds',
    ).toEqual([]);
  });

  it('⚠️ CONTENT_CARRIERS CONTAINS EVERY ELEMENT THE SCHEMA LETS A RUN PRINT', async () => {
    const { CONTENT_CARRIERS } = await import('../compiler');
    const missing = RUN_INNER_CONTENT.filter((n) => !CONTENT_CARRIERS.has(n));
    expect(
      missing,
      'these are legal children of w:r — the schema says they PRINT — and a ' +
        'kept-whole property block holding one is admitted, survives the ' +
        'clear verbatim, and earns counted blank credit',
    ).toEqual([]);
  });

  it('⚠️ EACH ONE, IN A KEPT-WHOLE w:rPr, IS REFUSED — AND NOTHING COUNTS', async () => {
    // ⚠️ THE POSITION IS THE MEASURED ONE. `<w:r><w:rPr>…</w:rPr>…</w:r>` is
    // where #174 found a Wingdings tick surviving and printing: the run shell
    // is STRUCTURE_RECURSE so it is kept, and its `w:rPr` is kept WHOLE.
    const survivors: string[] = [];
    for (const name of RUN_INNER_CONTENT) {
      const h = await harmOf({
        inner: `<w:p><w:r><w:rPr><w:${name}/></w:rPr><w:t>Enter x</w:t></w:r></w:p>`,
      });
      // POSITIVE CONTROL — it really is in the source.
      expect([name, h.sourceXml.includes(`<w:${name}/>`)]).toEqual([name, true]);
      if (h.refused.length === 0 && h.counted.length > 0) survivors.push(name);
    }
    expect(
      survivors,
      'admitted, survived into word/document.xml inside the field binding, ' +
        'and still bought the certification blank requirement',
    ).toEqual([]);
  });

  it('⚠️ CHARACTER DATA IN THE CONTROL\'S OWN sdtPr / sdtEndPr IS REFUSED', async () => {
    // ⚠️ THE ONE HOLE NO ADDITION TO `CONTENT_CARRIERS` COULD HAVE CLOSED:
    // character data has no element name. Three syntaxes for the same bytes.
    const NEEDLE = 'WARFARIN5MGDAILY';
    const cases: ReadonlyArray<readonly [string, { pr?: string; end?: string }]> = [
      ['bare text in w:sdtPr', { pr: NEEDLE }],
      ['CDATA in w:sdtPr', { pr: `<![CDATA[${NEEDLE}]]>` }],
      ['text in a w:rPr inside w:sdtPr', { pr: `<w:rPr>${NEEDLE}</w:rPr>` }],
      ['w:delInstrText in w:sdtPr', { pr: `<w:rPr><w:delInstrText>${NEEDLE}</w:delInstrText></w:rPr>` }],
      ['bare text in w:sdtEndPr', { end: `<w:sdtEndPr>${NEEDLE}</w:sdtEndPr>` }],
      ['CDATA in w:sdtEndPr', { end: `<w:sdtEndPr><![CDATA[${NEEDLE}]]></w:sdtEndPr>` }],
    ];
    for (const [label, opts] of cases) {
      const h = await harmOf(opts);
      // POSITIVE CONTROL — the bytes really are in the source document.
      expect([label, h.sourceXml.includes(NEEDLE)]).toEqual([label, true]);
      expect([label, h.refused.length]).toEqual([label, 1]);
      expect([label, h.bodyFields.length]).toEqual([label, 0]);
      expect(
        [label, h.counted.length],
        'the drug string reached the rendered document under a counted blank proof',
      ).toEqual([label, 0]);
    }
  });

  it('⚠️ AND THE OTHER DIRECTION: WHITESPACE IS NOT CHARACTER DATA', async () => {
    // A pretty-printed template puts a newline and an indent between every pair
    // of elements. Refusing that would refuse every control in a formatted
    // document — the false-refusal half, which costs a doctor a certification.
    const h = await harmOf({ pr: '\n        ', inner: '<w:r><w:t>Enter x</w:t></w:r>' });
    expect(h.refused.length, 'whitespace between sdtPr children was read as content').toBe(0);
    expect(h.bodyFields.length).toBe(1);
    expect(h.counted.length).toBe(1);
    expect(h.outputXml.includes('Enter x')).toBe(false);
  });
});
