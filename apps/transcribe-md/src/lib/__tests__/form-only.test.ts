// ============================================================================
// Form-only export helpers — numbered-list normalization + signature block.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { renumberFormSections, formSignatureLines, coerceFormSignature } from '../form-only';

describe('renumberFormSections', () => {
  it('numbers a multi-sentence FINDINGS prose block (the kokab flatten → list)', () => {
    // The note-gen flattened the dictated enumeration into double-spaced prose.
    const note = `## POSTOPERATIVE FINDINGS
An 8 mm polyp in the sigmoid colon, removed by hot snare.  A 3 mm polyp in the cecum, removed by cold snare.  Mild inflammation of the rectal mucosa.  Boston Bowel Prep score of 9.

## CONSENT
Informed consent obtained.`;
    const out = renumberFormSections(note);
    expect(out).toMatch(/## POSTOPERATIVE FINDINGS\n\n1\. An 8 mm polyp/);
    expect(out).toMatch(/2\. A 3 mm polyp/);
    expect(out).toMatch(/3\. Mild inflammation/);
    expect(out).toMatch(/4\. Boston Bowel Prep score of 9\./);
    // Non-enumerable sections are untouched.
    expect(out).toMatch(/## CONSENT\nInformed consent obtained\./);
  });

  it('numbers RECOMMENDATIONS and preserves a decimal within a sentence', () => {
    const note = `## RECOMMENDATIONS
High-fiber diet.  Repeat colonoscopy in 5 years if pathology is benign.  Increase fluids to 2.5 liters daily.`;
    const out = renumberFormSections(note);
    expect(out).toMatch(/1\. High-fiber diet\./);
    expect(out).toMatch(/2\. Repeat colonoscopy in 5 years/);
    // The decimal "2.5" is inside one item — NOT split on the period.
    expect(out).toMatch(/3\. Increase fluids to 2\.5 liters daily\./);
    expect(out).not.toMatch(/4\. 5 liters/);
  });

  it('leaves an already-numbered / bulleted / single-item / set-aside section untouched', () => {
    const already = `## FINDINGS\n1. First.\n2. Second.`;
    expect(renumberFormSections(already)).toBe(already);
    const bullets = `## FINDINGS\n- First.\n- Second.`;
    expect(renumberFormSections(bullets)).toBe(bullets);
    const single = `## FINDINGS\nA single normal finding.`;
    expect(renumberFormSections(single)).toBe(single);
    const setAside = `## FINDINGS\n_[All AI-drafted content for this section was set aside for your review.]_`;
    expect(renumberFormSections(setAside)).toBe(setAside);
  });

  it('does not touch narrative sections (PROCEDURE / DESCRIPTION)', () => {
    const note = `## DESCRIPTION OF PROCEDURE\nThe scope was advanced to the cecum.  It was withdrawn slowly.  The patient tolerated it well.`;
    expect(renumberFormSections(note)).toBe(note);
  });
});

describe('formSignatureLines', () => {
  it('signed: renders the form signature with DD/DT when the form has them', () => {
    const lines = formSignatureLines('Dr. Enayati', new Date('2026-07-24'), { dd: true, dt: true });
    expect(lines[0]).toMatch(/^Electronically Signed – Dr\. Enayati\s+/);
    expect(lines).toEqual([lines[0], expect.stringMatching(/^DD: /), expect.stringMatching(/^DT: /)]);
  });

  it('signed without DD/DT → just the signed line', () => {
    const lines = formSignatureLines('Dr. Lee', new Date('2026-07-24'), null);
    expect(lines).toHaveLength(1);
    expect(lines[0]).toMatch(/^Electronically Signed – Dr\. Lee/);
  });

  it('unsigned → the blank form stubs', () => {
    expect(formSignatureLines(null, null, { dd: true, dt: true })).toEqual([
      'Electronically Signed –',
      'DD:',
      'DT:',
    ]);
  });
});

describe('coerceFormSignature', () => {
  it('keeps a real DD/DT capture, drops an all-false / malformed one', () => {
    expect(coerceFormSignature({ dd: true, dt: false })).toEqual({ dd: true, dt: false });
    expect(coerceFormSignature({ dd: false, dt: false })).toBeNull();
    expect(coerceFormSignature(null)).toBeNull();
    expect(coerceFormSignature('nope')).toBeNull();
  });

  it('leaves a FINDINGS section with ### sub-blocks or a table UNTOUCHED (WARN-3, WM_IOV)', () => {
    const subBlocks = `## FINDINGS\nBilateral study.\n### Right\nnormal\n### Left\nnormal`;
    expect(renumberFormSections(subBlocks)).toBe(subBlocks);
    const table = `## FINDINGS\n| Vein | Reflux |\n| --- | --- |\n| GSV | 3.2s |`;
    expect(renumberFormSections(table)).toBe(table);
  });
});
