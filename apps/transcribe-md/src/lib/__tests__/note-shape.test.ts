// ============================================================================
// F12 / ruling #123 — E/M does not belong on a procedure or operative note.
// ----------------------------------------------------------------------------
// THE FIXTURES ARE THE REAL PRODUCTION TEMPLATES, copied label-for-label from
// `note_templates.sections` on 2026-08-18 (10 rows, read-only). They are here
// rather than invented because #123's positive arm — "a GI OFFICE VISIT still
// SHOWS a level" — is the arm that catches an over-broad suppression, and an
// invented office fixture cannot catch a classifier that is over-broad about
// the office templates production actually has.
//
// ⚠️ THE FOURTH OPERATIVE TEMPLATE IS THE POINT. It spells every label with a
// TRAILING COLON. An exact-match classifier finds 3 of 4 and reports a
// confident, wrong answer, so that row is a fixture specifically so the
// normalisation cannot be dropped later without something going red.
// ============================================================================

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { ultrasoundSpecialtyEnabled } from '@meddoc/shared/specialties';
import {
  emAppliesToVisit,
  isProcedureNoteShape,
  isProcedureNoteShapeFromText,
  OFFICE_SKELETON_FLOOR,
  OFFICE_SKELETON_SECTIONS,
  normalizeSectionLabel,
  normalizedNoteHeadings,
  normalizedSectionLabels,
  noteReadsAsOfficeVisitFromText,
  officeSkeletonCountFromText,
  procedureNoteMarkerCount,
  procedureNoteMarkerCountFromText,
  templateIsSilent,
  PROCEDURE_NOTE_MARKER_FLOOR,
  PROCEDURE_NOTE_SECTION_MARKERS,
} from '../note-shape';

const sec = (labels: string[]) =>
  labels.map((label, i) => ({ key: `k${i}`, label, order: i }));

/** The note body for every arm that predates ruling #126's note-text fallback.
 *  An empty body carries no headings, so the fallback cannot fire and those
 *  arms assert exactly what they asserted before it existed. */
const EMPTY_NOTE = '';

/** A note body rendered from the operative template — the SAME three markers
 *  the 19 production operative notes carry, measured 2026-08-18. */
const OP_NOTE_BODY = [
  '## PROCEDURE',
  'Colonoscopy.',
  '',
  '## PREOPERATIVE DIAGNOSIS',
  'Screening.',
  '',
  '## POSTOPERATIVE FINDINGS',
  'Two polyps.',
  '',
  '## DESCRIPTION OF PROCEDURE',
  'The scope was advanced.',
  '',
  '## RECOMMENDATIONS',
  'Repeat in five years.',
].join('\n');

/** ⚠️ THE FAMILY THE INDEPENDENT ADVERSARIAL PASS FOUND — a routine, billable
 *  POST-OP OFFICE FOLLOW-UP. A full SOAP skeleton PLUS two operative markers.
 *  A bare `markers >= 2` rule calls this an operative note and deletes the
 *  doctor's documentation level from a visit that legitimately has one.
 *
 *  It is one of four families named, verbatim, in this repository's own prior
 *  art at `worker/layers/structure-mismatch-reason.ts:66-70` — where the same
 *  naive rule shipped, was found CONFIDENTLY BACKWARDS, and was corrected with
 *  the office counterweight that #126 now carries here. */
const POST_OP_OFFICE_BODY = [
  '## SUBJECTIVE',
  'Month six after laparoscopic Roux-en-Y gastric bypass. Routine follow-up.',
  '',
  '## OBJECTIVE',
  'BP 122/74. Incisions well healed.',
  '',
  '## POSTOPERATIVE DIAGNOSIS',
  'Status post laparoscopic Roux-en-Y gastric bypass.',
  '',
  '## POSTOPERATIVE FINDINGS',
  'Weight loss on target. No dumping syndrome.',
  '',
  '## ASSESSMENT',
  'Doing well.',
  '',
  '## PLAN',
  'Switch to calcium citrate 1200 mg BID.',
].join('\n');

/** An ordinary office-visit body. No markers anywhere. */
const OFFICE_NOTE_BODY = [
  '## CHIEF COMPLAINT',
  'Follow-up.',
  '',
  '## EXAM',
  'Unremarkable.',
  '',
  '## IMPRESSION & PLAN',
  'Continue current therapy.',
].join('\n');

/** ⚠️ THE HEADINGS OF A REAL SIGNED PRODUCTION OFFICE VISIT — visit
 *  `cmsu1mhrp000h01nsxpvxxshk`, `gastroenterology`, SIGNED, `cptCodes.em.code`
 *  99215 with a FROZEN `signedCode` 99214, bound to that doctor's ACTIVE
 *  colonoscopy-shaped template. Measured 2026-08-18 (F12-d).
 *
 *  It exists because `OFFICE_NOTE_BODY` above is office-SHAPED but carries
 *  **0 of the 4** SOAP sections, while this row carries **4 of 4** — and an
 *  arm whose comment cited this very visit was pinned to the wrong one. The
 *  two are kept side by side deliberately: one is the row the escape must
 *  rescue, the other is the residual it does not (F12-f). */
const REAL_SIGNED_OFFICE_BODY = [
  '## CHIEF COMPLAINT',
  'Follow-up.',
  '',
  '## SUBJECTIVE',
  'Doing well.',
  '',
  '## OBJECTIVE',
  'Unremarkable.',
  '',
  '## ASSESSMENT',
  'Stable.',
  '',
  '## PLAN',
  'Continue current therapy.',
].join('\n');

// ── the real production templates ───────────────────────────────────────────
const OP_NOTE = sec([
  'PROCEDURE',
  'PREOPERATIVE DIAGNOSIS',
  'POSTOPERATIVE FINDINGS',
  'CONSENT',
  'DESCRIPTION OF PROCEDURE',
  'RECOMMENDATIONS',
]);

/** ⚠️ The fourth operative template — every label carries a trailing colon. */
const OP_NOTE_TRAILING_COLON = sec([
  'PROCEDURE:',
  'PREOPERATIVE DIAGNOSIS:',
  'POSTOPERATIVE FINDINGS:',
  'CONSENT:',
  'DESCRIPTION OF PROCEDURE:',
  'RECOMMENDATIONS:',
]);

const PRIMARY_CARE = sec([
  'CHIEF COMPLAINT',
  'INTERVAL HISTORY',
  'EXAM',
  'IMPRESSION & PLAN',
  'PATIENT INSTRUCTIONS',
]);

const SYSTEM_SOAP = sec(['Subjective', 'Objective', 'Assessment', 'Plan']);

const ULTRASOUND = sec([
  'Exam',
  'Indication',
  'Technique',
  'Comparison',
  'Findings',
  'Impression',
]);

const VENOUS_DUPLEX = sec([
  'Exam Metadata',
  'TECHNIQUE',
  'FINDINGS',
  'IMPRESSION',
  'DIAMETER AND REFLUX TIME',
]);

/** Every production template, with the verdict it must receive. The count is
 *  the reconciliation: 10 rows on production, 10 rows here. */
const PRODUCTION_TEMPLATES: ReadonlyArray<{
  name: string;
  sections: unknown;
  isProcedure: boolean;
}> = [
  { name: 'Colonoscopy Operative Note', sections: OP_NOTE, isProcedure: true },
  { name: 'Operative Note (a)', sections: OP_NOTE, isProcedure: true },
  { name: 'Operative Note (b) — TRAILING COLON', sections: OP_NOTE_TRAILING_COLON, isProcedure: true },
  { name: 'Operative Note (c)', sections: OP_NOTE, isProcedure: true },
  { name: 'Primary Care Chronic Disease Follow-up', sections: PRIMARY_CARE, isProcedure: false },
  { name: 'System Default — SOAP', sections: SYSTEM_SOAP, isProcedure: false },
  { name: 'Ultrasound Imaging Report', sections: ULTRASOUND, isProcedure: false },
  { name: 'Venous Duplex Lower Extremities Report', sections: VENOUS_DUPLEX, isProcedure: false },
  { name: 'Venous Duplex LE US Report (a)', sections: VENOUS_DUPLEX, isProcedure: false },
  { name: 'Venous Duplex LE US Report (b)', sections: VENOUS_DUPLEX, isProcedure: false },
];

describe('note shape — the classifier, against production', () => {
  it('NON-VACUITY: the fixture set is the whole production population, 4 procedure / 6 not', () => {
    // If this reconciliation drifts, every verdict below is being asserted over
    // a set that is no longer the one production has.
    expect(PRODUCTION_TEMPLATES).toHaveLength(10);
    expect(PRODUCTION_TEMPLATES.filter((t) => t.isProcedure)).toHaveLength(4);
    expect(PRODUCTION_TEMPLATES.filter((t) => !t.isProcedure)).toHaveLength(6);
  });

  it.each(PRODUCTION_TEMPLATES)(
    'classifies $name correctly',
    ({ sections, isProcedure }) => {
      expect(isProcedureNoteShape(sections)).toBe(isProcedure);
    }
  );

  it('the TRAILING-COLON template is classified by NORMALISATION, not by luck', () => {
    // The discriminating assertion: strip the normalisation and this row reads
    // 0 markers while its three colon-free siblings still read 3.
    expect(procedureNoteMarkerCount(OP_NOTE_TRAILING_COLON)).toBe(3);
    expect(procedureNoteMarkerCount(OP_NOTE)).toBe(3);
  });

  it('every operative template clears the floor WITH MARGIN — 3, not 2', () => {
    // A verdict-only assertion cannot see a silent drift from 3 markers to 1;
    // the floor is 2, so that drift would flip the answer with nothing to read.
    for (const t of PRODUCTION_TEMPLATES.filter((t) => t.isProcedure)) {
      expect(procedureNoteMarkerCount(t.sections)).toBeGreaterThan(
        PROCEDURE_NOTE_MARKER_FLOOR
      );
    }
  });

  it('every NON-procedure production template carries ZERO markers', () => {
    // Not merely "below the floor" — zero. A one-marker office template would
    // be one careless edit away from suppression.
    for (const t of PRODUCTION_TEMPLATES.filter((t) => !t.isProcedure)) {
      expect(procedureNoteMarkerCount(t.sections)).toBe(0);
    }
  });
});

describe('note shape — the OVER-SUPPRESSION guard, which is the arm that matters', () => {
  it('a bare PROCEDURE section does NOT make an office visit an operative note', () => {
    // An in-office biopsy or injection. #123: an over-broad suppression that
    // strips E/M from office visits is WORSE than the defect being fixed.
    const officeWithProcedure = sec([
      'CHIEF COMPLAINT',
      'EXAM',
      'PROCEDURE',
      'ASSESSMENT & PLAN',
    ]);
    expect(isProcedureNoteShape(officeWithProcedure)).toBe(false);
    expect(
      emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections: officeWithProcedure, noteText: EMPTY_NOTE })
    ).toBe(true);
  });

  it('CONSENT alone does NOT make an office visit an operative note', () => {
    const officeWithConsent = sec(['CHIEF COMPLAINT', 'CONSENT', 'EXAM', 'PLAN']);
    expect(isProcedureNoteShape(officeWithConsent)).toBe(false);
  });

  it('ONE marker is below the floor — two independent signals are required', () => {
    const oneMarker = sec(['CHIEF COMPLAINT', 'ESTIMATED BLOOD LOSS', 'PLAN']);
    expect(procedureNoteMarkerCount(oneMarker)).toBe(1);
    expect(isProcedureNoteShape(oneMarker)).toBe(false);
  });

  it('neither PROCEDURE nor CONSENT is on the marker list, and that is deliberate', () => {
    // Pins the omission itself. Adding either would silently re-open the
    // over-suppression the two tests above exist to refuse.
    expect(PROCEDURE_NOTE_SECTION_MARKERS).not.toContain('PROCEDURE');
    expect(PROCEDURE_NOTE_SECTION_MARKERS).not.toContain('CONSENT');
  });
});

describe('note shape — malformed and absent input fails OPEN, never into suppression', () => {
  it.each([
    ['null', null],
    ['undefined', undefined],
    ['an empty array', []],
    ['a string', 'PROCEDURE'],
    ['a number', 7],
    ['an object', { label: 'PREOPERATIVE DIAGNOSIS' }],
    ['an array of nulls', [null, null]],
    ['an array of strings', ['PREOPERATIVE DIAGNOSIS', 'DESCRIPTION OF PROCEDURE']],
    ['sections with no label key', [{ key: 'a' }, { key: 'b' }]],
    ['sections with non-string labels', [{ label: 1 }, { label: {} }]],
  ])('%s is NOT an operative note', (_name, input) => {
    expect(isProcedureNoteShape(input)).toBe(false);
  });

  it('an untemplated visit keeps whatever its specialty decided — WHEN ITS NOTE IS SILENT TOO', () => {
    // 30 of 46 production visits have no template at all (measured
    // 2026-08-18; the recon's population of 45 had grown by one). The safe
    // direction is
    // that they are unaffected by this change — the alternative silently
    // deletes levels from two thirds of the population.
    //
    // ⚠️ THE TITLE OF THIS ARM WAS NARROWED BY RULING #126 AND THE NARROWING IS
    // THE POINT. It used to read "an untemplated visit keeps whatever its
    // specialty decided", full stop — and that sentence became FALSE the
    // moment the note-text fallback landed, for the 9 untemplated production
    // visits whose own headings say operative. A test whose NAME outlives its
    // claim is how a stale guarantee gets re-read as a current one.
    expect(emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections: null, noteText: EMPTY_NOTE })).toBe(true);
    expect(emAppliesToVisit({ specialtyId: 'primary-care', templateSections: undefined, noteText: EMPTY_NOTE })).toBe(true);
    // The measured majority case: untemplated AND an ordinary office body.
    expect(
      emAppliesToVisit({ specialtyId: 'bariatric-surgery', templateSections: null, noteText: OFFICE_NOTE_BODY })
    ).toBe(true);
  });
});

describe('normalizeSectionLabel', () => {
  it.each([
    ['PROCEDURE:', 'PROCEDURE'],
    ['  PROCEDURE:  ', 'PROCEDURE'],
    ['Description  of   Procedure', 'DESCRIPTION OF PROCEDURE'],
    ['description of procedure:::', 'DESCRIPTION OF PROCEDURE'],
    // A space BEFORE the colon still normalises — trim · strip · trim again.
    ['\tPreoperative Diagnosis :', 'PREOPERATIVE DIAGNOSIS'],
    ['', ''],
  ])('%s → %s', (input, expected) => {
    expect(normalizeSectionLabel(input)).toBe(expected);
  });

  it('a non-string label normalises to the empty string rather than throwing', () => {
    expect(normalizeSectionLabel(undefined)).toBe('');
    expect(normalizeSectionLabel(null)).toBe('');
    expect(normalizeSectionLabel(42)).toBe('');
  });

  it('normalizedSectionLabels drops empties instead of emitting blanks', () => {
    expect(normalizedSectionLabels([{ label: 'A:' }, { label: '' }, { label: null }])).toEqual(['A']);
  });
});

describe('emAppliesToVisit — BOTH axes, and the conjunction lives in ONE place', () => {
  it('THE DEFECT F12 FIXES: a GI operative note gets NO office level', () => {
    expect(
      emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections: OP_NOTE, noteText: EMPTY_NOTE })
    ).toBe(false);
    expect(
      emAppliesToVisit({ specialtyId: 'bariatric-surgery', templateSections: OP_NOTE, noteText: EMPTY_NOTE })
    ).toBe(false);
    // The trailing-colon template must suppress identically — it is the same
    // clinical document, and a colon is not a semantic difference.
    expect(
      emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections: OP_NOTE_TRAILING_COLON, noteText: EMPTY_NOTE })
    ).toBe(false);
  });

  it('THE POSITIVE ARM: the SAME specialties keep E/M on their office visits', () => {
    // #123: "the POSITIVE arm is the one that catches an over-broad
    // suppression silently stripping E/M from office visits". Same specialty
    // ids as the row above — only the note shape differs.
    expect(
      emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections: PRIMARY_CARE, noteText: EMPTY_NOTE })
    ).toBe(true);
    expect(
      emAppliesToVisit({ specialtyId: 'bariatric-surgery', templateSections: SYSTEM_SOAP, noteText: EMPTY_NOTE })
    ).toBe(true);
  });

  // ⚠️ THE SPECIALTY AXIS IS FLAG-GATED, AND THE SUITE'S DEFAULT IS THE
  // ROLLBACK, NOT PRODUCTION. `emAppliesToSpecialty` returns
  // `!(ultrasoundSpecialtyEnabled() && isImagingReportSpecialty(id))`, and
  // `ultrasoundSpecialtyEnabled()` reads `NEXT_PUBLIC_ULTRASOUND_SPECIALTY`,
  // which `vitest.setup.ts` does not set. Measured from the RUNNING production
  // container (`docker exec meddoc-pro-transcribe-md-1 printenv`), production
  // runs it `true`. Asserting the imaging arm without pinning the flag would
  // test the rollback and pass for the wrong reason.
  describe('with production\'s flag set (NEXT_PUBLIC_ULTRASOUND_SPECIALTY=true)', () => {
    const prev = process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY;
    beforeEach(() => {
      process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY = 'true';
    });
    afterEach(() => {
      if (prev === undefined) delete process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY;
      else process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY = prev;
    });

    it('CONTROL: the flag is actually on inside this block', () => {
      // Without this, every assertion below could be passing because the flag
      // never took effect, and a suppression arm that cannot fail is not a
      // check.
      expect(ultrasoundSpecialtyEnabled()).toBe(true);
    });

    it('the specialty axis suppresses, and it is FIRST — shape is never consulted', () => {
      // ⚠️ RENAMED. The old title — *"shape cannot re-admit it"* — reads as a
      // claim about the shape sources, and `emAppliesToVisit` returns on the
      // specialty check before either is read, so it stayed green with both
      // shape halves deleted. It asserts the ORDER; it now says so. The full
      // combination matrix lives on the arm of that name further down.
      expect(
        emAppliesToVisit({ specialtyId: 'ultrasound', templateSections: PRIMARY_CARE, noteText: EMPTY_NOTE })
      ).toBe(false);
      expect(
        emAppliesToVisit({ specialtyId: 'ultrasound', templateSections: null, noteText: EMPTY_NOTE })
      ).toBe(false);
    });

    it('and the office arm is unaffected by the flag', () => {
      expect(
        emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections: PRIMARY_CARE, noteText: EMPTY_NOTE })
      ).toBe(true);
      expect(
        emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections: OP_NOTE, noteText: EMPTY_NOTE })
      ).toBe(false);
    });
  });
});

// ============================================================================
// RULING #126 — THE NOTE-TEXT FALLBACK.
// ----------------------------------------------------------------------------
// F12-a's own adversarial pass found that the shape axis hung on a LIVE
// RELATION: `TranscribeVisit.noteTemplate` is `onDelete: SetNull`, so deleting
// a template re-admits an office E/M level onto a signed operative record.
//
// ⚠️ AND THE MEASUREMENT MADE IT BIGGER THAN THE FINDING SAID. Production,
// 2026-08-18, all 46 visits:
//
//     30 of 46 carry NO template at all
//      9 of those 30 are operative notes BY THEIR OWN HEADINGS (7 SIGNED)
//      4 of those 9 currently carry an office E/M code
//      2 of those 4 carry a FROZEN signedCode on a signed operative record
//
// So the template-only classifier suppressed ONE production row. The hole was
// the common case, not a future hazard.
//
// The marker distribution over those 46 notes is BIMODAL — 27 notes with 0
// markers and 19 with exactly 3, nothing in between — so the floor of 2 has a
// margin of one in BOTH directions on the real corpus.
// ============================================================================

describe('ruling #126 — the note body is read when the template is silent', () => {
  it('THE FINDING: a deleted template no longer re-admits an office level', () => {
    // The exact sequence from the adversarial pass: a signed colonoscopy
    // op-note whose bound template row is deleted, so `noteTemplateId` nulls.
    expect(
      emAppliesToVisit({
        specialtyId: 'gastroenterology',
        templateSections: null, // ← the template was deleted
        noteText: OP_NOTE_BODY, // ← the record itself still says what it is
      })
    ).toBe(false);
  });

  it('and the 9 untemplated production operative notes are covered by the same arm', () => {
    for (const specialtyId of ['gastroenterology', 'bariatric-surgery']) {
      expect(
        emAppliesToVisit({ specialtyId, templateSections: null, noteText: OP_NOTE_BODY })
      ).toBe(false);
    }
  });

  it('THE POSITIVE ARM: an untemplated OFFICE visit keeps its level', () => {
    // #123: an over-broad suppression that strips E/M from office visits is
    // WORSE than the defect being fixed. 21 of the 30 untemplated production
    // visits are this case.
    expect(
      emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections: null, noteText: OFFICE_NOTE_BODY })
    ).toBe(true);
  });

  it('⚠️ THE FALLBACK FIRES ONLY INTO SILENCE — a template that said OFFICE is not overruled', () => {
    // This is the whole narrowness of #126, and the arm that goes red if
    // somebody "simplifies" the fallback into an OR across both sources.
    // A template WITH labels and no markers has an opinion: office visit.
    //
    // ⚠️ F12-d PROPOSED INVERTING THIS ARM AND THE ADVERSARIAL PASS KILLED IT —
    // recorded here because the next session will have the same idea. Ruling
    // #126 names the OR as "a TIGHTENING and therefore the legal direction to
    // be wrong in", and it changes ZERO production verdicts, so it guards a
    // hole with no instance. A refuter then showed it INTRODUCES one: template
    // `cmpz63jsw000501tayag818lq` is ACTIVE and spells its sections
    // `CHIEF COMPLAINT · INTERVAL HISTORY · EXAM · IMPRESSION & PLAN ·
    // PATIENT INSTRUCTIONS`, so an ordinary office visit with an in-room
    // excision scores 0 on the office counterweight (exact-match cannot see
    // `IMPRESSION & PLAN`) while the excision supplies two operative markers.
    // Measured: `true -> false`. That is the "derm office w/ excision" family
    // #126(b)'s counterweight exists to protect, losing its billable level.
    //
    // **The OR waits for the combined-heading forms to be named — F12-f.**
    expect(templateIsSilent(PRIMARY_CARE)).toBe(false);
    expect(
      emAppliesToVisit({
        specialtyId: 'gastroenterology',
        templateSections: PRIMARY_CARE, // ← says office
        noteText: OP_NOTE_BODY, // ← says operative, and does NOT win
      })
    ).toBe(true);
  });

  it('an empty or absent template is SILENT', () => {
    expect(templateIsSilent(null)).toBe(true);
    expect(templateIsSilent(undefined)).toBe(true);
    expect(templateIsSilent([])).toBe(true);
    expect(templateIsSilent('nonsense')).toBe(true);
    expect(templateIsSilent([{ key: 'a' }, { key: 'b' }])).toBe(true); // no labels
    expect(templateIsSilent(OP_NOTE)).toBe(false);
    expect(templateIsSilent(PRIMARY_CARE)).toBe(false);
  });

  it('🔴 AND SO IS A BARE-SOAP TEMPLATE — without this, #126a is INERT for every future visit', () => {
    // Found by the independent adversarial pass, and it is the finding that
    // would have made the whole fallback decorative going forward.
    //
    // `04-generate-soap.ts` writes `noteTemplateId` UNCONDITIONALLY on both
    // paths, falling back to SYSTEM_DEFAULT_NOTE_TEMPLATE — whose sections are
    // exactly Subjective/Objective/Assessment/Plan. So a doctor with no
    // operative template dictates an op note, the resolver binds the system
    // default, and a `labels.length === 0` definition of silence would skip the
    // note body entirely and hand the operative note its office E/M level.
    //
    // MEASURED: that template is bound on 2 production visits today, both with
    // zero operative markers — so this changes no current verdict. It is the
    // forward population it saves.
    expect(templateIsSilent(SYSTEM_SOAP)).toBe(true);

    // THE CONSEQUENCE, end to end: the same bare-SOAP binding, two bodies,
    // two opposite and correct answers.
    expect(
      emAppliesToVisit({
        specialtyId: 'bariatric-surgery',
        templateSections: SYSTEM_SOAP,
        noteText: OP_NOTE_BODY,
      }),
      'an operative note bound to the SYSTEM DEFAULT must still be suppressed',
    ).toBe(false);
    expect(
      emAppliesToVisit({
        specialtyId: 'bariatric-surgery',
        templateSections: SYSTEM_SOAP,
        noteText: OFFICE_NOTE_BODY,
      }),
      'and an office visit bound to the same default must keep its level',
    ).toBe(true);
    // …and an empty body still fails OPEN.
    expect(
      emAppliesToVisit({
        specialtyId: 'bariatric-surgery',
        templateSections: SYSTEM_SOAP,
        noteText: EMPTY_NOTE,
      })
    ).toBe(true);
  });

  it('a template that says anything BEYOND the SOAP skeleton is NOT silent', () => {
    // The boundary. `PRIMARY_CARE` (CHIEF COMPLAINT · INTERVAL HISTORY · EXAM …)
    // is a real clinical declaration and keeps its veto over the note body —
    // which is what stops the fallback becoming an OR across both sources.
    expect(templateIsSilent(PRIMARY_CARE)).toBe(false);
    expect(templateIsSilent(sec(['SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT', 'PLAN', 'EXAM']))).toBe(false);
    // A strict subset of the skeleton is still just a skeleton.
    expect(templateIsSilent(sec(['SUBJECTIVE', 'PLAN']))).toBe(true);
  });

  it('⚠️ THE FIXTURE DID NOT MATCH THE ROW ITS OWN COMMENT DESCRIBED — F12-d', () => {
    // ⚠️ THIS ARM USED TO ASSERT `false` AND TO CITE, IN ITS COMMENT, "the one
    // production visit where the two sources disagree in the other direction …
    // 1 visit, SIGNED, with a frozen signedCode". That visit is
    // `cmsu1mhrp000h01nsxpvxxshk`, and `OFFICE_NOTE_BODY` DOES NOT RESEMBLE IT.
    //
    //   OFFICE_NOTE_BODY          CHIEF COMPLAINT · EXAM · IMPRESSION & PLAN
    //                             -> 0 of the 4 SOAP sections
    //   cmsu1mhrp… (the real row) CHIEF COMPLAINT · SUBJECTIVE · OBJECTIVE ·
    //                             ASSESSMENT · PLAN
    //                             -> 4 of 4
    //
    // The arm was office-SHAPED, so it read as a faithful reproduction of the
    // production disagreement to its own author, and it went on passing
    // unchanged when F12-d's escape landed — for a reason that has nothing to
    // do with the behaviour it claims to pin. Canon: a well-chosen fixture
    // disguises a wrong universe.
    //
    // Both shapes are now asserted, with the real one first.
    expect(officeSkeletonCountFromText(REAL_SIGNED_OFFICE_BODY)).toBe(4);
    expect(
      emAppliesToVisit({
        specialtyId: 'gastroenterology',
        templateSections: OP_NOTE, // ← the GI doctor's ONE active template
        noteText: REAL_SIGNED_OFFICE_BODY, // ← an unambiguous office visit
      }),
      'a SIGNED office visit must not lose its level to a colonoscopy template',
    ).toBe(true);

    // ⚠️ AND THE RESIDUAL, ASSERTED RATHER THAN LEFT TO BE DISCOVERED — F12-f.
    // The escape is the FULL SOAP skeleton, so an office note that spells its
    // sections some other way is STILL over-suppressed under an operative
    // template. `OFFICE_NOTE_BODY` is exactly that shape, and it is the
    // PRIMARY_CARE template's own vocabulary — an ordinary office note, not a
    // contrived one. Filed as F12-f; NOT fixed here, because the cure is to
    // widen `countOfficeSkeleton`, which also feeds the operative-note
    // counterweight and would move suppression in the under- direction on a
    // signed row #126(b) measured by hand.
    expect(officeSkeletonCountFromText(OFFICE_NOTE_BODY)).toBe(0);
    expect(
      emAppliesToVisit({
        specialtyId: 'gastroenterology',
        templateSections: OP_NOTE,
        noteText: OFFICE_NOTE_BODY,
      }),
      'KNOWN RESIDUAL (F12-f): a non-SOAP-worded office note is still suppressed',
    ).toBe(false);
  });

  it('the template arm still wins when the body says NOTHING — the fail-safe is unchanged', () => {
    // A body with no headings at all (a stub, a visit mid-pipeline) must not
    // un-suppress an operative-templated visit. This is what keeps F12-d an
    // AFFIRMATIVE exception rather than a wholesale inversion of precedence.
    expect(
      emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections: OP_NOTE, noteText: EMPTY_NOTE })
    ).toBe(false);
  });

  it('THE SPECIALTY AXIS SHORT-CIRCUITS BEFORE EITHER SHAPE SOURCE IS READ', () => {
    // ⚠️ RENAMED AFTER THE INDEPENDENT ADVERSARIAL PASS, AND THE RENAME IS THE
    // FIX. It used to be called *"the specialty axis cannot be re-admitted by
    // either source"* — which sounds like a claim about the two shape sources
    // and is not one, because `emAppliesToVisit` returns on the specialty check
    // BEFORE either is consulted. Delete the whole #126 fallback AND the
    // counterweight and this arm stays green: the "sources" it names are
    // variables the branch provably never reads.
    //
    // What it actually proves is worth exactly one arm — THE ORDER — so it is
    // now named that, and the two duplicate copies of it elsewhere in this file
    // were folded into this one. `AGENTS.md`: if the work a check guards
    // regressed completely, what number would it print? The same one.
    const prev = process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY;
    process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY = 'true';
    try {
      expect(ultrasoundSpecialtyEnabled()).toBe(true); // control
      // Every combination of the two shape sources, including the ones that
      // would otherwise say "keep the level" — the specialty answer wins in
      // all four.
      for (const templateSections of [null, PRIMARY_CARE]) {
        for (const noteText of [OFFICE_NOTE_BODY, OP_NOTE_BODY]) {
          expect(
            emAppliesToVisit({ specialtyId: 'ultrasound', templateSections, noteText }),
            'an imaging report has no office level whatever its shape says',
          ).toBe(false);
        }
      }
    } finally {
      if (prev === undefined) delete process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY;
      else process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY = prev;
    }
  });
});

// ============================================================================
// THE OFFICE COUNTERWEIGHT — found by F12-a's INDEPENDENT adversarial pass.
// ----------------------------------------------------------------------------
// ⚠️ THE PASS DID NOT INVENT THIS. It found PRIOR ART IN THIS REPOSITORY:
// `worker/layers/structure-mismatch-reason.ts:53-76` had already shipped the
// naive `markers >= 2` rule, already found it CONFIDENTLY BACKWARDS on four
// families of ordinary office visit, and already fixed it by testing the SOAP
// skeleton FIRST. Nothing in F12-a's own proofs could have found this — the
// suite, the four mutation proofs and the production census all shared the
// author's assumption that markers alone decide.
//
// The consequence was priced the way #123 prices it: `templateKind` only
// chooses the wording of a BANNER, while this predicate decides whether a
// billable level appears on a signed clinical document.
// ============================================================================

describe('ruling #126 — the OFFICE COUNTERWEIGHT, and it is tested FIRST', () => {
  it('🔴 THE FINDING: a post-op office follow-up KEEPS its level', () => {
    // S/O/A/P + POSTOPERATIVE DIAGNOSIS + POSTOPERATIVE FINDINGS. Two markers,
    // so a bare `markers >= 2` deletes this doctor's documentation level from
    // a routine billable office visit — and silently, on export.
    expect(procedureNoteMarkerCountFromText(POST_OP_OFFICE_BODY)).toBe(2);
    expect(procedureNoteMarkerCountFromText(POST_OP_OFFICE_BODY)).toBeGreaterThanOrEqual(
      PROCEDURE_NOTE_MARKER_FLOOR,
    );
    // …and the verdict is nevertheless NOT an operative note.
    expect(isProcedureNoteShapeFromText(POST_OP_OFFICE_BODY)).toBe(false);
    expect(
      emAppliesToVisit({
        specialtyId: 'bariatric-surgery',
        templateSections: null,
        noteText: POST_OP_OFFICE_BODY,
      })
    ).toBe(true);
  });

  it('the COUNT and the VERDICT are no longer interchangeable, and that is the shape of the fix', () => {
    // Stated as a measurement so nobody "simplifies" the verdict back into
    // `count >= floor`. The margin is still exported as evidence; it is no
    // longer the answer.
    const count = procedureNoteMarkerCountFromText(POST_OP_OFFICE_BODY);
    expect(count >= PROCEDURE_NOTE_MARKER_FLOOR).toBe(true);
    expect(isProcedureNoteShapeFromText(POST_OP_OFFICE_BODY)).toBe(false);
  });

  it('the same family on the TEMPLATE arm, because one arm fixed is a half fix', () => {
    const postOpTemplate = sec([
      'SUBJECTIVE',
      'OBJECTIVE',
      'POSTOPERATIVE DIAGNOSIS',
      'POSTOPERATIVE FINDINGS',
      'ASSESSMENT',
      'PLAN',
    ]);
    expect(procedureNoteMarkerCount(postOpTemplate)).toBe(2);
    expect(isProcedureNoteShape(postOpTemplate)).toBe(false);
    expect(
      emAppliesToVisit({
        specialtyId: 'bariatric-surgery',
        templateSections: postOpTemplate,
        noteText: EMPTY_NOTE,
      })
    ).toBe(true);
  });

  it('the other three families the prior art names', () => {
    const families: Array<[string, string[]]> = [
      // derm office with excision
      ['derm excision', ['SUBJECTIVE', 'OBJECTIVE', 'SPECIMENS REMOVED', 'ESTIMATED BLOOD LOSS', 'ASSESSMENT', 'PLAN']],
      // pre-op H&P, done in the office
      ['pre-op H&P', ['SUBJECTIVE', 'OBJECTIVE', 'PREOPERATIVE DIAGNOSIS', 'INDICATIONS FOR PROCEDURE', 'ASSESSMENT', 'PLAN']],
      // surgical consult, done in the office
      ['surgical consult', ['SUBJECTIVE', 'OBJECTIVE', 'DESCRIPTION OF PROCEDURE', 'OPERATIVE FINDINGS', 'ASSESSMENT', 'PLAN']],
    ];
    for (const [name, labels] of families) {
      expect(procedureNoteMarkerCount(sec(labels)), `${name}: fixture must be non-vacuous`).toBeGreaterThanOrEqual(
        PROCEDURE_NOTE_MARKER_FLOOR,
      );
      expect(isProcedureNoteShape(sec(labels)), `${name} is an OFFICE visit`).toBe(false);
      expect(
        isProcedureNoteShapeFromText(labels.map((l) => '## ' + l).join('\n')),
        `${name} is an OFFICE visit on the note-text arm too`,
      ).toBe(false);
    }
  });

  it('⚠️ ALL FOUR, NOT THREE — the measured signed row that decided the threshold', () => {
    // Production visit `cmrxxj1rn000h01pnoloiiajx`, SIGNED, signedCode 99214:
    // SUBJECTIVE · OBJECTIVE · ASSESSMENT (no PLAN) alongside a full operative
    // skeleton. The prior art's SECOND clause (`op >= 2 && office < 3`) would
    // hand this signed operative record its office level back. Copying prior
    // art verbatim would have been the error.
    const threeOfFour = [
      'SUBJECTIVE',
      'OBJECTIVE',
      'ASSESSMENT',
      'PROCEDURE',
      'PREOPERATIVE DIAGNOSIS',
      'DESCRIPTION OF PROCEDURE',
      'POSTOPERATIVE FINDINGS',
      'CONSENT',
      'RECOMMENDATIONS',
    ];
    expect(OFFICE_SKELETON_FLOOR).toBe(4);
    expect(isProcedureNoteShape(sec(threeOfFour))).toBe(true);
    expect(isProcedureNoteShapeFromText(threeOfFour.map((l) => '## ' + l).join('\n'))).toBe(true);
  });

  // ⛔ AN ARM WAS DELETED HERE, DELIBERATELY. It was titled *"the counterweight
  // cannot re-admit a level the SPECIALTY axis refused"* and asserted
  // `ultrasound` + `POST_OP_OFFICE_BODY` is false — which is true, and is a
  // fact about the specialty short-circuit rather than about the
  // counterweight. It stayed green with the counterweight deleted. The claim
  // it was reaching for is asserted once, over all four shape combinations, by
  // "THE SPECIALTY AXIS SHORT-CIRCUITS BEFORE EITHER SHAPE SOURCE IS READ"
  // above. Three arms named after an unreachable branch are not three times
  // the coverage.

  it('⚠️ EXACT MATCH, NEVER `includes` — "IMPLANT" contains "plan"', () => {
    // The prior art matches office markers by substring. Copying that here
    // would let an operative note score an office point off `IMPLANT REMOVAL`
    // and, with three more, keep its office E/M level. This repository has a
    // canon section on exactly this family ('dashboard' contains 'board').
    expect('IMPLANT'.toLowerCase().includes('plan')).toBe(true); // the trap, demonstrated
    const opWithImplant = [
      'IMPLANT REMOVAL',
      'SUBJECTIVE',
      'OBJECTIVE',
      'ASSESSMENT',
      'PREOPERATIVE DIAGNOSIS',
      'DESCRIPTION OF PROCEDURE',
    ];
    // Exact matching scores office = 3 (SUBJECTIVE/OBJECTIVE/ASSESSMENT), below
    // the floor, so the operative markers still decide. A substring scan would
    // score 4 and hand this operative note a level.
    expect(isProcedureNoteShape(sec(opWithImplant))).toBe(true);
  });

  it('the office skeleton is exactly the four SOAP sections', () => {
    expect([...OFFICE_SKELETON_SECTIONS]).toEqual(['SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT', 'PLAN']);
    // Non-vacuity: none of them may also be an operative marker, or the
    // counterweight and the trigger would fight over the same heading.
    for (const s of OFFICE_SKELETON_SECTIONS) {
      expect(PROCEDURE_NOTE_SECTION_MARKERS).not.toContain(s);
    }
  });

  it('and a pure operative note is untouched by the counterweight', () => {
    // The regression direction: the counterweight must not have quietly
    // switched the whole classifier off.
    expect(isProcedureNoteShape(OP_NOTE)).toBe(true);
    expect(isProcedureNoteShapeFromText(OP_NOTE_BODY)).toBe(true);
  });
});

describe('ruling #126 — heading extraction from the note body', () => {
  it('counts DISTINCT markers, and the operative body carries exactly three', () => {
    // The margin, not only the verdict — the same reason the template arm
    // exports its count. Production's operative notes carry 3; a silent drift
    // to 1 would flip the verdict with nothing to see.
    expect(procedureNoteMarkerCountFromText(OP_NOTE_BODY)).toBe(3);
    expect(procedureNoteMarkerCountFromText(OFFICE_NOTE_BODY)).toBe(0);
  });

  it('a repeated heading counts ONCE — two signals means two DIFFERENT markers', () => {
    const repeated = '## PREOPERATIVE DIAGNOSIS\na\n## PREOPERATIVE DIAGNOSIS\nb';
    expect(procedureNoteMarkerCountFromText(repeated)).toBe(1);
    expect(isProcedureNoteShapeFromText(repeated)).toBe(false);
  });

  it('ONE marker is below the floor in the note body too', () => {
    const oneMarker = '## CHIEF COMPLAINT\nx\n## ESTIMATED BLOOD LOSS\n50 mL\n## PLAN\ny';
    expect(procedureNoteMarkerCountFromText(oneMarker)).toBe(1);
    expect(isProcedureNoteShapeFromText(oneMarker)).toBe(false);
  });

  it('PROCEDURE and CONSENT in the BODY do not suppress either', () => {
    // The over-suppression omission has to hold on both arms, or the fallback
    // is a second, laxer classifier wearing the same name.
    const officeWithProcedure =
      '## CHIEF COMPLAINT\nx\n## PROCEDURE\nbiopsy\n## CONSENT\nobtained\n## PLAN\ny';
    expect(procedureNoteMarkerCountFromText(officeWithProcedure)).toBe(0);
    expect(isProcedureNoteShapeFromText(officeWithProcedure)).toBe(false);
  });

  it('the trailing colon is stripped in the BODY as well as in the template', () => {
    // The fourth production template spells every label with a colon, and the
    // notes it generates carry the colon into the body.
    const colons = '## PREOPERATIVE DIAGNOSIS:\na\n## DESCRIPTION OF PROCEDURE:\nb';
    expect(isProcedureNoteShapeFromText(colons)).toBe(true);
  });

  it('heading depth 1..6 all count, and prose mentioning a marker does not', () => {
    expect(normalizedNoteHeadings('# A\n## B\n###### C')).toEqual(['A', 'B', 'C']);
    // ⚠️ PROSE IS NOT A HEADING. A note that says the words "preoperative
    // diagnosis" in a sentence must not classify the document — this codebase
    // has been bitten four times by a matcher satisfied by prose.
    const prose = 'The preoperative diagnosis was X and the description of procedure follows.';
    expect(procedureNoteMarkerCountFromText(prose)).toBe(0);
    // Seven hashes is not a heading in markdown either.
    expect(normalizedNoteHeadings('####### G')).toEqual([]);
  });

  it('a heading with no space after the hashes is NOT read as a heading', () => {
    // The controlled choice: both this form and the permissive one returned an
    // IDENTICAL distribution over all 46 production notes (27 zero / 19 three),
    // so the strictness costs nothing on the real corpus. Pinned so the choice
    // is visible if the corpus ever changes.
    expect(normalizedNoteHeadings('##PREOPERATIVE DIAGNOSIS')).toEqual([]);
  });

  it.each([
    ['null', null],
    ['undefined', undefined],
    ['an empty string', ''],
    ['a number', 7],
    ['an object', { text: '## PREOPERATIVE DIAGNOSIS' }],
    ['an array', ['## PREOPERATIVE DIAGNOSIS', '## DESCRIPTION OF PROCEDURE']],
  ])('%s reads as NO headings and therefore fails OPEN', (_name, input) => {
    expect(normalizedNoteHeadings(input)).toEqual([]);
    expect(isProcedureNoteShapeFromText(input)).toBe(false);
  });

  it('the two arms share ONE marker list — EVERY marker, both arms, plus a negative control', () => {
    // ⚠️ THIS ARM WAS REWRITTEN AFTER THE INDEPENDENT ADVERSARIAL PASS PROVED
    // THE FIRST VERSION DID NOT MAKE ITS OWN CLAIM. It read
    // `PROCEDURE_NOTE_SECTION_MARKERS.slice(0, FLOOR)` and asserted both
    // functions accepted those two — which two INDEPENDENT COPIES of the list
    // satisfy equally well. It could only see drift by REMOVAL of the first
    // two entries; drift by ADDITION — the overwhelmingly likely edit — was
    // invisible, which is the opposite of what its own comment claimed.
    //
    // ⚠️ AND IT LEFT 3 OF THE 11 MARKERS NEVER EXERCISED AT ALL:
    // `PRE-OPERATIVE DIAGNOSIS`, `POST-OPERATIVE DIAGNOSIS` and
    // `POST-OPERATIVE FINDINGS` had ZERO occurrences anywhere in this file, and
    // all three could be deleted from the module with the whole suite green.
    // They exist only for a template the classifier has not met yet, which is
    // the entire reason they were written down — a guard that cannot see their
    // removal is not guarding them.
    //
    // Iterating the WHOLE list on BOTH arms fixes both defects at once.
    for (const marker of PROCEDURE_NOTE_SECTION_MARKERS) {
      expect(
        procedureNoteMarkerCountFromText('## ' + marker),
        `${marker} must be a marker on the NOTE-TEXT arm`,
      ).toBe(1);
      expect(
        procedureNoteMarkerCount(sec([marker])),
        `${marker} must be a marker on the TEMPLATE arm`,
      ).toBe(1);
    }

    // NEGATIVE CONTROL — without it, an arm that scored 1 for everything would
    // pass every row above. `ANESTHESIA` is a plausible operative heading that
    // is deliberately NOT on the list.
    for (const notAMarker of ['ANESTHESIA', 'RECOMMENDATIONS', 'TECHNIQUE']) {
      expect(procedureNoteMarkerCountFromText('## ' + notAMarker)).toBe(0);
      expect(procedureNoteMarkerCount(sec([notAMarker]))).toBe(0);
    }

    // NON-VACUITY on the list itself: a cohort that collapsed to nothing would
    // satisfy every loop above while checking nothing.
    expect(PROCEDURE_NOTE_SECTION_MARKERS.length).toBe(11);
  });

  it('⚠️ THE FLOOR IS NOT "two independent signals" FOR THE HYPHENATED PAIRS — recorded, not fixed', () => {
    // `normalizeSectionLabel` strips colons and collapses whitespace but does
    // NOT normalise hyphens, so the 11 entries cover 9 CONCEPTS:
    // PREOPERATIVE/PRE-OPERATIVE DIAGNOSIS and POSTOPERATIVE/POST-OPERATIVE
    // FINDINGS are each one concept spelled twice — and `countMarkers` scores
    // the two spellings as TWO signals, reaching the floor on ONE concept.
    //
    // The floor's stated purpose is "two INDEPENDENT signals". For these pairs
    // it is not what it enforces. Found by the independent adversarial pass.
    //
    // ⛔ DELIBERATELY PINNED RATHER THAN CHANGED, and the reason is direction:
    // de-duplicating by concept would make the floor HARDER to reach, which is
    // LESS suppression — the under-suppression direction, on the clinical
    // export path, decided late in a session and measured against nothing.
    // Production carries ZERO hyphenated spellings today (measured
    // 2026-08-18), so the behaviour is unreachable on the real corpus. This arm
    // exists so the next reader meets the fact instead of the comment's claim.
    const oneConceptTwoSpellings = '## PREOPERATIVE DIAGNOSIS\na\n## PRE-OPERATIVE DIAGNOSIS\nb';
    expect(procedureNoteMarkerCountFromText(oneConceptTwoSpellings)).toBe(2);
    expect(isProcedureNoteShapeFromText(oneConceptTwoSpellings)).toBe(true);
  });
});
