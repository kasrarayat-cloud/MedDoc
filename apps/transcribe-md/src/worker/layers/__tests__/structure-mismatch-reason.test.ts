// ============================================================================
// The review banner — it must say what the doctor can ACT on.
// ----------------------------------------------------------------------------
// ⚠️ THE FIXTURE IS A REAL PRODUCTION FAILURE, not an invention. Visit
// `cmssgh1w7000r01no7g394xpj` (gastroenterology, READY, unsigned) failed L4
// structure validation with these six operative-note headings absent, on an
// office-visit dictation. The old banner said "SOAP draft didn't match expected
// markdown structure — manual review required."
// ============================================================================

import { describe, expect, it } from 'vitest';

import { structureMismatchReason, templateKind } from '../structure-mismatch-reason';

/** The six, verbatim from the production validator's own metadata. */
const SIX = [
  'PROCEDURE:',
  'PREOPERATIVE DIAGNOSIS:',
  'POSTOPERATIVE FINDINGS:',
  'CONSENT:',
  'DESCRIPTION OF PROCEDURE:',
  'RECOMMENDATIONS:',
];
const OP_TEMPLATE = [...SIX, 'INDICATIONS:', 'ANESTHESIA:'];
const SOAP_TEMPLATE = ['Subjective', 'Objective', 'Assessment', 'Plan'];

describe('the banner names the mismatch, the sections, and where to fix it', () => {
  const reason = structureMismatchReason(SIX, OP_TEMPLATE);

  it('names every missing section BY NAME', () => {
    // The validator knew all six. Printing a count and withholding the names
    // is the defect this replaces.
    for (const s of SIX) expect(reason).toContain(s);
  });

  it('states the COUNT, and the count matches the list', () => {
    // ⚠️ Derived from the array, never a separate tally. "six sections" beside
    // a list of five is the contradiction a reader stops trusting the whole
    // banner over.
    expect(reason).toMatch(/\b6 sections\b/);
    expect(SIX).toHaveLength(6);
  });

  it('names the DOCUMENT KIND — the half a clinician can act on fastest', () => {
    expect(reason).toMatch(/OPERATIVE \/ PROCEDURE note/i);
  });

  it('points at the Note-format picker, by its real path', () => {
    expect(reason).toContain('Settings › My Note Format');
  });

  it('⚠️ CARRIES NO PHI — headings and counts only', () => {
    // The banner sits beside an audit row that is deliberately PHI-free. It
    // must hold the same line: no transcript, no note text, no patient value.
    expect(reason).not.toMatch(/patient|dob|mrn|\b\d{2}\/\d{2}\/\d{4}\b/i);
  });

  it('NEGATIVE CONTROL — it is not the old sentence', () => {
    expect(reason).not.toMatch(/expected markdown structure/i);
  });
});

describe('it degrades honestly rather than lying', () => {
  it('an OFFICE template says so', () => {
    const r = structureMismatchReason(['Objective'], SOAP_TEMPLATE);
    expect(r).toMatch(/OFFICE-VISIT note/i);
    expect(r).toContain('Objective');
    expect(r).toMatch(/\b1 section\b/);   // singular, not "1 sections"
  });

  it('an UNRECOGNISED template still lists the sections', () => {
    // The kind heuristic is allowed to fail. What must not fail is naming the
    // sections — that is the part the doctor acts on.
    const r = structureMismatchReason(['Findings'], ['Findings', 'Notes']);
    expect(r).toContain('Findings');
    expect(r).toMatch(/Settings › My Note Format/);
    expect(r).not.toMatch(/OPERATIVE|OFFICE-VISIT/i);
  });

  it('ZERO missing sections does NOT print "0 sections"', () => {
    // Structure can fail for empty output or a JSON shape, where
    // `missingSections` is []. A banner reading "0 sections had no content"
    // is nonsense in front of a clinician.
    const r = structureMismatchReason([], OP_TEMPLATE);
    expect(r).not.toMatch(/\b0 sections?\b/);
    expect(r).toMatch(/could not be matched section by section/i);
  });

  it('ignores blank entries rather than printing empty names', () => {
    const r = structureMismatchReason(['PROCEDURE:', '', '   '], OP_TEMPLATE);
    expect(r).toMatch(/\b1 section\b/);
  });
});

describe('templateKind — two markers, never one', () => {
  it('one operative marker is a coincidence, not a shape', () => {
    // ⚠️ MY FIRST VERSION OF THIS TEST WAS WRONG, and the code was right:
    // I asserted `['Plan', 'Specimens']` reads operative, but 'Plan' is not an
    // operative MARKER at all — it appears on office notes too, which is
    // exactly why it is absent from the list. That case has ONE match, not two.
    //
    // The property: a single marker must not flip the banner into claiming a
    // document kind it cannot establish.
    expect(templateKind(['Specimens'])).toBe('unknown');                       // one
    expect(templateKind(['Specimens', 'Estimated Blood Loss'])).toBe('operative'); // two
    expect(templateKind(['Plan', 'Specimens'])).toBe('unknown');               // still one
  });

  it('a full SOAP set reads as office', () => {
    expect(templateKind(SOAP_TEMPLATE)).toBe('office');
  });

  it('the production template reads as operative', () => {
    expect(templateKind(OP_TEMPLATE)).toBe('operative');
  });
});

describe('a MODEL failure is not blamed on the clinician', () => {
  // ⚠️ `soap-structure-validator.ts` sets `missingSections` to ALL required
  // sections for three classes where the dictation is blameless: empty output,
  // output-too-short, and a JSON-shaped envelope. Without the reason, the
  // banner reads "N sections had no content the dictation supported" and sends
  // the doctor to change a template that is fine.
  const OP = ['PROCEDURE:', 'PREOPERATIVE DIAGNOSIS:'];

  it.each([
    ['empty output'],
    ['output too short (12 chars, threshold 50)'],
    ['output is JSON-shaped, expected markdown'],
  ])('%s → names it as a generation failure', (reason) => {
    const r = structureMismatchReason(OP, OP, reason);
    expect(r).toMatch(/generation failure/i);
    expect(r).not.toMatch(/the dictation supported/i);
    expect(r).not.toMatch(/Settings › My Note Format/);
  });

  it('NEGATIVE CONTROL — a REAL missing-sections failure still blames neither, but does point at the template', () => {
    // Without this, "always say generation failure" would pass every row above
    // and destroy the whole point of the banner.
    const r = structureMismatchReason(OP, OP, 'missing SOAP sections: PROCEDURE:');
    expect(r).not.toMatch(/generation failure/i);
    expect(r).toMatch(/Settings › My Note Format/);
    expect(r).toContain('PROCEDURE:');
  });

  it('an ABSENT reason degrades to the section-listing form', () => {
    const r = structureMismatchReason(OP, OP);
    expect(r).toContain('PROCEDURE:');
    expect(r).not.toMatch(/generation failure/i);
  });
});
