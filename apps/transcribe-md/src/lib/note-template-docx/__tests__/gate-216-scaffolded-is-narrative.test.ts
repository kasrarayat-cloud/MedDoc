// ============================================================================
// #216 — A SCAFFOLDED **PROSE** CONTROL IS ALWAYS `narrative_text`.
// ----------------------------------------------------------------------------
// `inferTextKind` classifies a control by matching clinical words against its
// LABEL. That is sound for the short furniture labels it was written for
// ("Weight", "Height", "Temp"). It is not sound where the label IS the
// sentence — a scaffolded control's alias is its own default prose, so any word
// the regex happens to list re-types the whole clause.
//
// ⚠️ MEASURED ON THE OWNER'S OWN FORM, AND IT PICKED THE WORST POSSIBLE ONE.
// Control #13 of the regenerated 53-control consult form, alias
//   "The patient denies unintentional weight loss or change in appetite"
// compiled `measurement` on the strength of the word "weight". The other five
// GI-ROS clauses compiled `narrative_text` correctly. The single clause that
// carries the GI ALARM FEATURE was the one mis-typed — and a `measurement`
// field cannot be filled with a clause, so the alarm feature could not be
// documented at all.
//
// ⚠️ WHAT THIS GATE MUST ALSO PROVE IS THE NON-EFFECT. The fix is a compiler
// change, and a compiler change that quietly re-typed existing production
// templates would de-certify them. So every arm below has a DISCRIMINATING
// partner: the same label, unscaffolded, must still infer exactly what it
// inferred before.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { buildSyntheticDocx } from './synthetic-docx';

const W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"';

/** The six GI-ROS clause aliases, verbatim from the regenerated form. */
const GI_ROS_CLAUSES = [
  'The patient denies heartburn, odynophagia, dysphagia',
  'The patient denies nausea or vomiting',
  'The patient denies abdominal pain',
  'The patient denies diarrhea or constipation',
  'The patient denies hematemesis, melena or hematochezia',
  'The patient denies unintentional weight loss or change in appetite',
] as const;

/**
 * Compile ONE rich-text control with `alias`.
 *
 * `scaffolded` decides the only thing that separates the two universes:
 * `isScaffolded` is false when `w:showingPlcHdr` is present and true when the
 * content carries visible text without it. Both variants below carry the SAME
 * visible text, so the difference is the placeholder flag alone and nothing
 * else can account for a divergence.
 */
async function kindOf(alias: string, scaffolded: boolean): Promise<string> {
  const documentXml =
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document ${W}><w:body><w:p>` +
    `<w:sdt><w:sdtPr><w:id w:val="1750"/><w:alias w:val="${alias}"/><w:tag w:val="t"/>` +
    `<w:text/>${scaffolded ? '' : '<w:showingPlcHdr/>'}</w:sdtPr>` +
    `<w:sdtContent><w:r><w:t>${alias}.</w:t></w:r></w:sdtContent></w:sdt>` +
    `</w:p></w:body></w:document>`;
  const source = await buildSyntheticDocx({ documentXml });
  const { compileTemplateDocx } = await import('../compiler');
  const ir = compileTemplateDocx(source);
  const field = ir.fields.find((f) => f.originalLabel === alias);
  expect(field, `no field compiled for ${alias}`).toBeTruthy();
  expect(
    field!.scaffolded,
    `the fixture did not produce the scaffolded=${scaffolded} universe it claims`,
  ).toBe(scaffolded);
  return field!.kind;
}

/**
 * A control with NO alias and NO tag, sitting in a paragraph whose prose the
 * control does not own. The label then falls back to the container text.
 */
async function kindOfUnnamed(paragraph: string, inner: string): Promise<{ kind: string; scaffolded: boolean }> {
  const documentXml =
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document ${W}><w:body><w:p>` +
    `<w:r><w:t>${paragraph}</w:t></w:r>` +
    `<w:sdt><w:sdtPr><w:id w:val="1751"/><w:text/></w:sdtPr>` +
    `<w:sdtContent><w:r><w:t>${inner}</w:t></w:r></w:sdtContent></w:sdt>` +
    `</w:p></w:body></w:document>`;
  const source = await buildSyntheticDocx({ documentXml });
  const { compileTemplateDocx } = await import('../compiler');
  const ir = compileTemplateDocx(source);
  const f = ir.fields[0];
  expect(f, 'no field compiled').toBeTruthy();
  return { kind: f!.kind, scaffolded: Boolean(f!.scaffolded) };
}

describe('#216 — a scaffolded PROSE control is always narrative_text', () => {
  it('⚠️ AN UNNAMED CONTROL IS TYPED BY ITS OWN IDENTITY, NEVER BY THE PARAGRAPH', async () => {
    // ⚠️ THIS ARM EXISTS BECAUSE THE FIRST FIX MEASURED THE WRONG STRING. It read
    // `identity.label ?? context.containerText`, and the container fallback is
    // the PARAGRAPH — which already contains the control's own scaffold text. So
    // an unnamed scaffolded control had its word count taken from a sentence it
    // does not own, and a measurement field re-typed to narrative_text on the
    // strength of somebody else's prose.
    //
    // The ruling says "the ALIAS is the sentence". A control with no identity of
    // its own is not one this rule can speak about.
    const r = await kindOfUnnamed(
      'The patient is measured at each visit and the weight recorded below',
      '72 kg',
    );
    expect(r.scaffolded, 'the fixture is not the scaffolded universe it claims').toBe(true);
    expect(r.kind).toBe('measurement');
  });

  it('⚠️ NON-VACUITY: the heuristic really does fire on this label', async () => {
    // Without this, every arm below is satisfied by a regex that never matched
    // anything — the fix would "pass" because there was nothing to fix.
    expect(await kindOf('The patient denies unintentional weight loss or change in appetite', false)).toBe(
      'measurement',
    );
  });

  it('the GI alarm-feature clause compiles narrative_text when scaffolded', async () => {
    expect(await kindOf('The patient denies unintentional weight loss or change in appetite', true)).toBe(
      'narrative_text',
    );
  });

  it('ALL SIX GI ROS clauses compile narrative_text', async () => {
    for (const alias of GI_ROS_CLAUSES) {
      expect(await kindOf(alias, true), alias).toBe('narrative_text');
    }
  });

  it('⚠️ DISCRIMINATION: an UNSCAFFOLDED furniture label still infers exactly as before', async () => {
    // This is the non-effect the ruling requires. If any of these moved, the
    // change would not be scoped and existing production templates could
    // re-type — which de-certifies them.
    expect(await kindOf('Weight', false)).toBe('measurement');
    expect(await kindOf('Height', false)).toBe('measurement');
    expect(await kindOf('Temperature', false)).toBe('measurement');
    expect(await kindOf('Age', false)).toBe('number');
    expect(await kindOf('Assessment', false)).toBe('narrative_text');
  });

  it('⚠️ A SHORT FURNITURE LABEL SURVIVES EVEN WHEN SCAFFOLDED — the case that corrected the mechanism', async () => {
    // ⚠️ THIS ARM EXISTS BECAUSE THE FIRST MECHANISM WAS WRONG AND THE CENSUS
    // CAUGHT IT. "Scaffolded ⇒ narrative_text", taken alone, re-typed the
    // customer's `Age` control — a genuine one-word field name that SHOULD be a
    // number — because every control in his form is scaffolded. Measured: it
    // moved 5 GI fields, and only 4 of them were the defect.
    //
    // The ruling's own words carry the real discriminator — inference "applies
    // to short furniture labels, never to a control whose default content is
    // prose (the alias IS the sentence)" — so the label's SHAPE is the test.
    expect(await kindOf('Age', true)).toBe('number');
    expect(await kindOf('Weight', true)).toBe('measurement');
    expect(await kindOf('Total minutes spent with patient', true)).toBe('narrative_text');
  });

  it('⚠️ THE THRESHOLD SITS IN A MEASURED GAP, and this arm pins both sides of it', async () => {
    // Across all three real documents every label reaching the keyword lists is
    // either ONE word or EIGHT-plus — nothing in between. These pin that the
    // rule turns over inside that gap rather than at an edge where a real label
    // lives.
    expect(await kindOf('Age count score', true)).toBe('number'); // 3 words: still a field name
    expect(await kindOf('{patient} is a pleasant {age}-year-old presenting for consultation', true)).toBe(
      'narrative_text', // 8 words: prose, and this is the customer's own HPI intro line
    );
  });

  it('the five NON-weight clauses were never affected either way', async () => {
    // They compiled narrative_text before the change and still do. Stated so a
    // future reader does not credit the fix with more than it did: exactly one
    // of the six clauses ever moved.
    for (const alias of GI_ROS_CLAUSES.slice(0, 5)) {
      expect(await kindOf(alias, false), alias).toBe('narrative_text');
    }
  });
});
