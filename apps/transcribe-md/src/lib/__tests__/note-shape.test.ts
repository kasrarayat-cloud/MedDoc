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
  normalizeSectionLabel,
  normalizedSectionLabels,
  procedureNoteMarkerCount,
  PROCEDURE_NOTE_MARKER_FLOOR,
  PROCEDURE_NOTE_SECTION_MARKERS,
} from '../note-shape';

const sec = (labels: string[]) =>
  labels.map((label, i) => ({ key: `k${i}`, label, order: i }));

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
      emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections: officeWithProcedure })
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

  it('an untemplated visit keeps whatever its specialty decided', () => {
    // 30 of 45 production visits have no template at all. The safe direction is
    // that they are unaffected by this change — the alternative silently
    // deletes levels from two thirds of the population.
    expect(emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections: null })).toBe(true);
    expect(emAppliesToVisit({ specialtyId: 'primary-care', templateSections: undefined })).toBe(true);
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
      emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections: OP_NOTE })
    ).toBe(false);
    expect(
      emAppliesToVisit({ specialtyId: 'bariatric-surgery', templateSections: OP_NOTE })
    ).toBe(false);
    // The trailing-colon template must suppress identically — it is the same
    // clinical document, and a colon is not a semantic difference.
    expect(
      emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections: OP_NOTE_TRAILING_COLON })
    ).toBe(false);
  });

  it('THE POSITIVE ARM: the SAME specialties keep E/M on their office visits', () => {
    // #123: "the POSITIVE arm is the one that catches an over-broad
    // suppression silently stripping E/M from office visits". Same specialty
    // ids as the row above — only the note shape differs.
    expect(
      emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections: PRIMARY_CARE })
    ).toBe(true);
    expect(
      emAppliesToVisit({ specialtyId: 'bariatric-surgery', templateSections: SYSTEM_SOAP })
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

    it('the specialty axis still suppresses, and shape cannot re-admit it', () => {
      // An imaging report stays suppressed whatever its sections say — the two
      // axes are AND-ed, so neither can override the other.
      expect(
        emAppliesToVisit({ specialtyId: 'ultrasound', templateSections: PRIMARY_CARE })
      ).toBe(false);
      expect(
        emAppliesToVisit({ specialtyId: 'ultrasound', templateSections: null })
      ).toBe(false);
    });

    it('and the office arm is unaffected by the flag', () => {
      expect(
        emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections: PRIMARY_CARE })
      ).toBe(true);
      expect(
        emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections: OP_NOTE })
      ).toBe(false);
    });
  });
});
