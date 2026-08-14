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
  // ⚠️ SIX OF EIGHT — a PARTIAL miss, deliberately. When EVERY section is
  // absent the banner takes the shape-failure branch instead, because that is
  // not a content problem at all (see the describe below).
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
    expect(reason).toMatch(/\b6 of your template's sections\b/);
    expect(SIX).toHaveLength(6);
  });

  it('names the DOCUMENT KIND — the half a clinician can act on fastest', () => {
    expect(reason).toMatch(/OPERATIVE \/ PROCEDURE note/i);
  });

  it('⚠️ CLAIMS ONLY WHAT WAS MEASURED — "not found", never "unsupported"', () => {
    // THE CORRECTION THAT MATTERS MOST IN THIS FILE. `validateSoapStructure`
    // asks only whether the text contains `## <label>`. It NEVER measures
    // whether the dictation supported anything. The first draft reported that
    // heading-presence result as a CONTENT-PROVENANCE verdict — "N sections had
    // no content the dictation supported" — a claim the validator cannot make,
    // about a note sitting directly below the banner.
    expect(reason).toMatch(/could not be found in this note/i);
    expect(reason).not.toMatch(/the dictation supported/i);
    expect(reason).toMatch(/may be present under a different heading/i);
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
    expect(r).toMatch(/\b1 of your template's section\b/);   // singular
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
    expect(r).toMatch(/\b1 of your template's section\b/);
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
  // ⚠️ PARTIAL, not total. A total miss is a SHAPE failure and takes its own
  // branch, so these rows must leave at least one section found or they would
  // be testing the wrong arm — which is exactly what they did on first write.
  const OP = ['PROCEDURE:', 'PREOPERATIVE DIAGNOSIS:', 'CONSENT:'];
  const MISSING_SOME = ['PROCEDURE:'];

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
    const r = structureMismatchReason(MISSING_SOME, OP, 'missing SOAP sections: PROCEDURE:');
    expect(r).not.toMatch(/generation failure/i);
    expect(r).toMatch(/Settings › My Note Format/);
    expect(r).toContain('PROCEDURE:');
  });

  it('an ABSENT reason degrades to the section-listing form', () => {
    const r = structureMismatchReason(MISSING_SOME, OP);
    expect(r).toContain('PROCEDURE:');
    expect(r).not.toMatch(/generation failure/i);
  });
});

describe('⚠️ EVERY SECTION MISSING IS A SHAPE FAILURE, NOT A CONTENT ONE', () => {
  // THE DEMONSTRATED DEFECT, kept as a test because it is the worst thing this
  // banner could do. The model files a COMPLETE operative dictation under
  // Subjective/Objective/Assessment/Plan — a documented behaviour (`06-polish`
  // records "the model 'helpfully' reverts a sparse custom note back to SOAP").
  // Every clinical fact is present. All eight template headings are absent.
  //
  // The first draft told the doctor: "8 sections had no content the dictation
  // supported … change it in Settings › My Note Format." Affirmatively FALSE,
  // about a note directly below it, prescribing that they discard a correct
  // template. WORSE than the vague sentence it replaced.
  const OP8 = [
    'PREOPERATIVE DIAGNOSIS', 'POSTOPERATIVE DIAGNOSIS', 'PROCEDURE', 'ANESTHESIA',
    'ESTIMATED BLOOD LOSS', 'SPECIMENS', 'DESCRIPTION OF PROCEDURE', 'RECOMMENDATIONS',
  ];

  it('says the HEADINGS differ, and does NOT claim the content is absent', () => {
    const r = structureMismatchReason(OP8, OP8, `missing SOAP sections: ${OP8.join(', ')}`);
    expect(r).toMatch(/different headings from your template/i);
    expect(r).toMatch(/may all be present under other headings/i);
    expect(r).not.toMatch(/the dictation supported/i);
    expect(r).not.toMatch(/did not fill it/i);
  });

  it('does NOT tell the doctor to change a template that may be correct', () => {
    const r = structureMismatchReason(OP8, OP8, `missing SOAP sections: ${OP8.join(', ')}`);
    expect(r).not.toMatch(/Settings › My Note Format/);
  });

  it('NEGATIVE CONTROL — a PARTIAL miss still lists sections and offers Settings', () => {
    // Without this, routing everything to the shape branch would pass the two
    // arms above and destroy the banner's whole purpose.
    const r = structureMismatchReason(OP8.slice(0, 3), OP8, 'missing SOAP sections: …');
    expect(r).toMatch(/could not be found in this note/i);
    expect(r).toContain('Settings › My Note Format');
  });
});

describe('templateKind is not confidently BACKWARDS on office templates', () => {
  // ⚠️ FOUR REAL-WORLD OFFICE TEMPLATES read `operative` in the first draft,
  // because `op >= 2` was tested BEFORE `office >= 3` and operative markers
  // matched by substring while office markers matched exactly — the weaker,
  // looser signal beating the stronger, stricter one. The doctor was told
  // their routine office form was an operative note: the exact INVERSE of the
  // production case this was written for.
  const SOAP = ['SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT', 'PLAN'];
  it.each([
    ['post-op office follow-up', [...SOAP, 'POSTOPERATIVE DIAGNOSIS', 'POSTOPERATIVE FINDINGS']],
    ['derm office with excision', [...SOAP, 'SPECIMENS SENT', 'ESTIMATED BLOOD LOSS']],
    ['pre-op H&P (office)', [...SOAP, 'PREOPERATIVE DIAGNOSIS', 'PLANNED PROCEDURE']],
  ])('%s is NOT called operative', (_label, headings) => {
    expect(templateKind(headings)).not.toBe('operative');
  });

  it('NEGATIVE CONTROL — a genuine operative note is still detected', () => {
    expect(templateKind([
      'PREOPERATIVE DIAGNOSIS', 'POSTOPERATIVE DIAGNOSIS', 'DESCRIPTION OF PROCEDURE',
      'SPECIMENS', 'ESTIMATED BLOOD LOSS',
    ])).toBe('operative');
  });
});
