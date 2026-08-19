// ============================================================================
// GATE — F12-g. THE WATCHER THAT MAKES A STALE OFFICE E/M LEVEL VISIBLE.
// ----------------------------------------------------------------------------
// `emAppliesToVisit` can flip from TRUE to FALSE for entirely ordinary reasons:
// a template is retired (`onDelete: SetNull`, and no read path filters on
// status), a note body is edited, or the classifier itself is corrected —
// F12-a, F12-d and F12-f each moved it. NOTHING CLEARS THE E/M STATE WHEN IT
// FLIPS, so the visit keeps a level the product no longer believes in.
//
// MEASURED ON PRODUCTION 2026-08-19, through the shipped predicate, in the
// production flag universe read from the running worker:
//
//     verdict FALSE + carries E/M state   15   <- the class this watches
//     verdict FALSE + clean               24
//     verdict TRUE  + carries E/M state    7
//     verdict TRUE  + clean                2
//                                         --
//                                         48   == rows
//
// ⚠️ WHAT THIS GATE IS FOR IS THE WATCHED SET AND THE PARTITION, NOT THE COUNT.
// The count belongs to production and moves; the guard's job is that the scan
// keeps asking the right question over the right universe. Two named hazards:
//
//   1. A FIELD SILENTLY LEAVING THE WATCHED SET. The scan reports zero just as
//      happily when it stopped looking as when the class was cleared, and the
//      two are indistinguishable from the outside. Each field therefore has its
//      OWN arm, driven from a list this file declares independently.
//   2. THE PREDICATE BEING RE-IMPLEMENTED. F12-g's filing records that cost: an
//      SQL re-implementation with the specialty axis approximated answered
//      **19** where the shipped predicate answers **15**, and the 19 reached a
//      ledger row. The `consults the shipped predicate` arm below flips a row's
//      BODY and requires the bucket to move — a copied rule would not follow.
// ============================================================================

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { emAppliesToSpecialty } from '@meddoc/shared/specialties';
import {
  scanEmArtifacts,
  assertNoBodyText,
  emStateOn,
  suppressingAxis,
  unknownEmKeys,
  KNOWN_EM_KEYS,
  EM_STATE_FIELDS,
  type EmScanRow,
} from '../em-artifact-scan';

// ⚠️ THE PRODUCTION FLAG UNIVERSE, AND THIS GATE FOUND ITS OWN AUTHOR IN THE
// ROLLBACK. On its first execution FIVE arms failed, every one of them because
// `NEXT_PUBLIC_ULTRASOUND_SPECIALTY` is unset under vitest: with the flag OFF,
// `emAppliesToSpecialty('ultrasound')` returns TRUE, so the fixture built to
// exercise the SPECIALTY axis was silently exercising the note-shape one and
// the `byAxis` split could not discriminate. Production runs the flag ON —
// read from the running worker on 2026-08-19, `NEXT_PUBLIC_ULTRASOUND_
// SPECIALTY=true` — so a gate that defaults it off is a gate about the
// rollback. Read at CALL time, never at import time, which is why assigning
// here works.
const priorFlag = process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY;
beforeAll(() => {
  process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY = 'true';
});
afterAll(() => {
  if (priorFlag === undefined) delete process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY;
  else process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY = priorFlag;
});

describe('F12-g — the universe this gate runs in is production\'s', () => {
  // The same two-directional control the CLI refuses on. Stated here as well as
  // there, deliberately: the CLI's control protects the live scan, this one
  // protects every arm below, and neither implies the other.
  it('suppresses imaging and admits gastroenterology — both directions', () => {
    expect(emAppliesToSpecialty('ultrasound')).toBe(false);
    expect(emAppliesToSpecialty('gastroenterology')).toBe(true);
  });
});

/** ⚠️ THE SPEC'S NAMED SET, DECLARED HERE RATHER THAN IMPORTED.
 *
 *  An arm that imports the list it is checking agrees with any list at all.
 *  These five are the UNION of two sources, and the union is the point:
 *
 *    F12-g names three — `emScoredCode`, `cptCodes.em` (its `code`), and the
 *      frozen `cptCodes.em.signedCode`.
 *    `check-imaging-em-artifacts.sh` additionally watches `emPendingChange`
 *      and `cptCodes.em.override`.
 *
 *  Two watchers over one class with different watched sets is how one of them
 *  ends up reporting a true and worthless zero. */
const SPEC_NAMED_FIELDS = [
  'emScoredCode',
  'cptCodes.em.code',
  'cptCodes.em.override.code',
  'cptCodes.em.signedCode',
  'emPendingChange',
] as const;

const body = (labels: string[]) => labels.map((l) => `## ${l}`).join('\n');

/** The production operative vocabulary — 4 of 4 operative templates and 19 of
 *  19 operative note bodies carry it (census, F12-f). */
const OPERATIVE_BODY = [
  'PROCEDURE',
  'PREOPERATIVE DIAGNOSIS',
  'POSTOPERATIVE FINDINGS',
  'CONSENT',
  'DESCRIPTION OF PROCEDURE',
  'RECOMMENDATIONS',
];

/** An unambiguous office visit. */
const OFFICE_BODY = ['CHIEF COMPLAINT', 'SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT', 'PLAN'];

const CLEAN: Omit<EmScanRow, 'visitId' | 'specialty' | 'noteHeadingLines'> = {
  signed: false,
  emScoredCode: null,
  cptEmCode: null,
  cptEmOverrideCode: null,
  cptEmSignedCode: null,
  emPendingChange: false,
  cptEmSuppressed: null,
  templateSections: null,
  cptCodesType: null,
  templateSectionsType: null,
  cptEmType: null,
  cptEmKeys: null,
};

function row(over: Partial<EmScanRow> & { visitId: string }): EmScanRow {
  return {
    ...CLEAN,
    specialty: 'gastroenterology',
    noteHeadingLines: body(OFFICE_BODY),
    ...over,
  };
}

describe('F12-g — the watched set is diffed against what the spec names', () => {
  it('watches exactly the five fields the two specs name between them', () => {
    expect([...EM_STATE_FIELDS].sort()).toEqual([...SPEC_NAMED_FIELDS].sort());
  });

  // ⚠️ ONE ARM PER FIELD, DRIVEN FROM THE INDEPENDENTLY-DECLARED LIST. A field
  // dropped from `emStateOn` reddens HERE, by name, rather than becoming a
  // quietly smaller number in production.
  const FIELD_FIXTURES: Record<(typeof SPEC_NAMED_FIELDS)[number], Partial<EmScanRow>> = {
    emScoredCode: { emScoredCode: '99213' },
    'cptCodes.em.code': { cptEmCode: '99214' },
    'cptCodes.em.override.code': { cptEmOverrideCode: '99215' },
    'cptCodes.em.signedCode': { cptEmSignedCode: '99214', signed: true },
    emPendingChange: { emPendingChange: true },
  };

  for (const field of SPEC_NAMED_FIELDS) {
    it(`detects ${field} alone on an otherwise clean row`, () => {
      const r = row({ visitId: `v-${field}`, ...FIELD_FIXTURES[field] });
      expect(emStateOn(r)).toEqual([field]);
    });

    it(`flags a SUPPRESSED visit carrying only ${field}`, () => {
      const r = row({
        visitId: `s-${field}`,
        noteHeadingLines: body(OPERATIVE_BODY),
        ...FIELD_FIXTURES[field],
      });
      const res = scanEmArtifacts([r]);
      expect(res.buckets.verdictFalseWithState).toBe(1);
      expect(res.artifacts[0].fields).toEqual([field]);
    });
  }

  it('reads a clean row as clean — the negative control for every arm above', () => {
    expect(emStateOn(row({ visitId: 'clean' }))).toEqual([]);
  });
});

describe('F12-g — the partition is exhaustive, disjoint, and reconciles', () => {
  const corpus: EmScanRow[] = [
    // verdict FALSE + state, by NOTE SHAPE — the class F12-g is about
    row({
      visitId: 'false-state-shape',
      noteHeadingLines: body(OPERATIVE_BODY),
      emScoredCode: '99213',
    }),
    // verdict FALSE + state, by SPECIALTY — already owned by the imaging watcher
    row({ visitId: 'false-state-specialty', specialty: 'ultrasound', emScoredCode: '99213' }),
    // verdict FALSE + clean
    row({ visitId: 'false-clean', noteHeadingLines: body(OPERATIVE_BODY) }),
    // verdict TRUE + state
    row({ visitId: 'true-state', emScoredCode: '99214' }),
    // verdict TRUE + clean
    row({ visitId: 'true-clean' }),
  ];

  it('sorts every row into exactly one named bucket and the total reconciles', () => {
    const r = scanEmArtifacts(corpus);
    expect(r.buckets).toEqual({
      verdictFalseWithState: 2,
      verdictFalseClean: 1,
      verdictTrueWithState: 1,
      verdictTrueClean: 1,
    });
    expect(r.total).toBe(corpus.length);
    expect(r.control.rows).toBe(corpus.length);
  });

  // ⚠️ NON-VACUITY OF THE FIXTURE SET ITSELF. If the corpus held one verdict or
  // one axis, every arm above would be a statement about a constant.
  it('the fixture corpus contains BOTH verdicts and BOTH axes', () => {
    const r = scanEmArtifacts(corpus);
    expect(r.buckets.verdictFalseWithState + r.buckets.verdictFalseClean).toBeGreaterThan(0);
    expect(r.buckets.verdictTrueWithState + r.buckets.verdictTrueClean).toBeGreaterThan(0);
    expect(r.byAxis['note-shape']).toBe(1);
    expect(r.byAxis.specialty).toBe(1);
  });

  it('names the suppressing axis, so the imaging watcher\'s territory is visible', () => {
    expect(suppressingAxis(row({ visitId: 'a', specialty: 'ultrasound' }))).toBe('specialty');
    expect(suppressingAxis(row({ visitId: 'b', specialty: 'gastroenterology' }))).toBe(
      'note-shape'
    );
  });

  // ⚠️ THE SUCCESS DIRECTION — the half everybody skips. A guard proven only in
  // the red direction is half-proven: if F12-g's remediation succeeded
  // completely, this check must print ZERO rather than the same number.
  it('MOVES when the class is cleared — clearing the state empties the finding', () => {
    const cleared = corpus.map((r) => ({
      ...r,
      emScoredCode: null,
      cptEmCode: null,
      cptEmOverrideCode: null,
      cptEmSignedCode: null,
      emPendingChange: false,
    }));
    const r = scanEmArtifacts(cleared);
    expect(r.artifacts).toHaveLength(0);
    expect(r.buckets.verdictFalseWithState).toBe(0);
    // and the rows did not vanish — they moved into the clean buckets
    expect(r.buckets.verdictFalseClean).toBe(3);
    expect(r.buckets.verdictTrueClean).toBe(2);
    expect(r.total).toBe(corpus.length);
  });
});

describe('F12-g — the scan CONSULTS the shipped predicate rather than copying it', () => {
  // Same row, same state, only the BODY changes. A re-implemented rule would
  // have to be edited to follow `emAppliesToVisit`; consulting it cannot fail
  // to. This is the arm that would redden if anyone "optimised" the scan by
  // inlining a marker count.
  it('flips bucket when the note body flips the verdict, nothing else changing', () => {
    const office = row({ visitId: 'flip', emScoredCode: '99213' });
    const operative = { ...office, noteHeadingLines: body(OPERATIVE_BODY) };

    expect(scanEmArtifacts([office]).buckets.verdictTrueWithState).toBe(1);
    expect(scanEmArtifacts([office]).buckets.verdictFalseWithState).toBe(0);
    expect(scanEmArtifacts([operative]).buckets.verdictFalseWithState).toBe(1);
    expect(scanEmArtifacts([operative]).buckets.verdictTrueWithState).toBe(0);
  });

  // The real signed production row named in note-shape.ts and in ruling #130:
  // three operative markers plus S/O/A (three SOAP concepts, no PLAN), frozen
  // at 99214. It is the row #126(b) set the floor of FOUR against, and the row
  // the refused synonyms would have un-suppressed.
  it('flags the signed bariatric row shape that ruling #130 refuses to un-suppress', () => {
    const r = scanEmArtifacts([
      row({
        visitId: 'cmrxxj1rn-shape',
        specialty: 'bariatric-surgery',
        signed: true,
        noteHeadingLines: body([...OPERATIVE_BODY, 'SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT']),
        cptEmCode: '99214',
        cptEmSignedCode: '99214',
      }),
    ]);
    expect(r.buckets.verdictFalseWithState).toBe(1);
    expect(r.artifacts[0].axis).toBe('note-shape');
    expect(r.artifacts[0].frozenOnSigned).toBe(true);
    expect(r.artifacts[0].fields).toEqual(['cptCodes.em.code', 'cptCodes.em.signedCode']);
  });
});

describe('F12-g — the projection carries headings and never a body', () => {
  it('agrees with itself on a well-formed projection', () => {
    const r = assertNoBodyText([
      row({ visitId: 'ok', noteHeadingLines: body(OFFICE_BODY) }),
    ]);
    expect(r.deliveredLines).toBe(OFFICE_BODY.length);
    expect(r.headingLines).toBe(OFFICE_BODY.length);
  });

  // ⚠️ THE ARM THAT MATTERS. If the SQL filter is ever relaxed and starts
  // handing over prose, the counts diverge and the caller must refuse. A
  // watcher that silently carries note text is a PHI incident wearing a
  // measurement's clothes.
  it('DETECTS body text smuggled into the projection', () => {
    const r = assertNoBodyText([
      row({
        visitId: 'leak',
        noteHeadingLines: `## SUBJECTIVE\nPatient reports worsening reflux.\n## PLAN`,
      }),
    ]);
    expect(r.deliveredLines).toBe(3);
    expect(r.headingLines).toBe(2);
    expect(r.deliveredLines).not.toBe(r.headingLines);
  });

  it('blank lines are not counted as smuggled text', () => {
    const r = assertNoBodyText([
      row({ visitId: 'blanks', noteHeadingLines: `## SUBJECTIVE\n\n   \n## PLAN` }),
    ]);
    expect(r.deliveredLines).toBe(2);
    expect(r.headingLines).toBe(2);
  });

  it('a visit with no note text at all contributes nothing either way', () => {
    const r = assertNoBodyText([row({ visitId: 'empty', noteHeadingLines: '' })]);
    expect(r.deliveredLines).toBe(0);
    expect(r.headingLines).toBe(0);
  });
});

describe('F12-g — an unknown key under cptCodes.em is a CANNOT-TELL, not a clean row', () => {
  // ⚠️ FOUND BY THIS BRANCH'S OWN REFUTATION PASS, BEFORE MERGE. The scan reads
  // three fixed paths under `em`. State arriving under a FOURTH key would read
  // as a perfectly clean row — silently, and indistinguishably from a row that
  // really is clean. Zero instances on production today; this is for the row
  // nobody has written yet.
  // ⚠️ THIS ARM WAS NAMED `the known key set is exactly what production
  // carries` AND ITS BODY COMPARES TWO CONSTANTS. It never touched production
  // and, from a unit test with no database, it never could — so the name made a
  // claim the implementation cannot make. Canon's "A check whose TITLE is
  // narrower than what it MEASURES", caught by this gate's own author in the
  // pass that shipped it.
  //
  // The arm is KEPT, because what it actually does is worth doing: it is a PIN
  // on `KNOWN_EM_KEYS`, and the pin is what forces the partition decision. The
  // constant's own doc-comment sets the retirement condition — *"a key added
  // here alone silences the control without widening the watch"* — and this arm
  // is what makes an edit to it LOUD instead of quiet. So it is renamed to what
  // it measures rather than deleted.
  //
  // ⚠️ WHERE THE LIVE MEASUREMENT ACTUALLY LIVES: `unknownEmKeys`, run against
  // the real column by `scripts/check-em-note-shape-artifacts.sh`. That is the
  // only thing that can compare this list to production, and it reports a
  // non-empty result as CANNOT-TELL rather than as a finding about a visit.
  // A green here says the list has not drifted since the census; it does not
  // say the census is still true.
  it('PINS KNOWN_EM_KEYS to the 2026-08-19 census — a pin, not a live measurement', () => {
    expect([...KNOWN_EM_KEYS].sort()).toEqual(
      ['code', 'description', 'evidence_quote', 'override', 'reasoning', 'signedCode'].sort()
    );
  });

  // Same reading applied one arm down: this is a FIXTURE built from the census
  // (five of the six known keys — `override` is absent, which is the ordinary
  // shape), not a row read from production. Named for what it is.
  it('accepts a row carrying only CENSUSED keys without complaint', () => {
    expect(
      unknownEmKeys([
        row({
          visitId: 'known',
          cptEmType: 'object',
          cptEmKeys: ['code', 'description', 'evidence_quote', 'reasoning', 'signedCode'],
        }),
      ])
    ).toEqual([]);
  });

  it('DETECTS a key the scan does not model', () => {
    expect(
      unknownEmKeys([
        row({ visitId: 'u1', cptEmType: 'object', cptEmKeys: ['code', 'levelOverrideV2'] }),
        row({ visitId: 'u2', cptEmType: 'object', cptEmKeys: ['frozenAt', 'code'] }),
      ])
    ).toEqual(['frozenAt', 'levelOverrideV2']);
  });

  // ⚠️ THE ARM THAT RECORDS WHY PRIOR ART WAS NOT COPIED.
  // `check-imaging-em-artifacts.sh` tests bare KEY EXISTENCE (`cptCodes ? 'em'`)
  // and its comment explains why — for ITS question that is right. Here it is
  // wrong: measured 2026-08-19, 17 of the 27 rows carrying the key hold JSON
  // `null`, and bare existence would have invented FIVE findings out of rows
  // that explicitly record NO E/M level. Copying prior art verbatim would have
  // been the error; measuring the corpus is what chose the predicate.
  it('{"em": null} is an EXPLICIT no-E/M and is NOT an artifact', () => {
    const r = scanEmArtifacts([
      row({
        visitId: 'em-json-null',
        noteHeadingLines: body(OPERATIVE_BODY), // verdict FALSE — the flaggable side
        cptCodesType: 'object',
        cptEmType: 'null',
        cptEmKeys: null,
      }),
    ]);
    expect(r.buckets.verdictFalseWithState).toBe(0);
    expect(r.buckets.verdictFalseClean).toBe(1);
    expect(r.artifacts).toHaveLength(0);
    expect(unknownEmKeys([row({ visitId: 'x', cptEmType: 'null', cptEmKeys: null })])).toEqual([]);
  });

  it('counts the em shape census, so "null" is visible rather than surprising', () => {
    const r = scanEmArtifacts([
      row({ visitId: 'a', cptEmType: 'null' }),
      row({ visitId: 'b', cptEmType: 'null' }),
      row({ visitId: 'c', cptEmType: 'object', cptEmKeys: ['code'], cptEmCode: '99213' }),
      row({ visitId: 'd' }),
    ]);
    expect(r.control.cptEmTypes).toEqual({ null: 2, object: 1, absent: 1 });
  });
});

describe('F12-g — the shape census is a measurement, not an assumption', () => {
  it('counts jsonb_typeof per column, including nulls', () => {
    const r = scanEmArtifacts([
      row({ visitId: 'a', cptCodesType: 'object', templateSectionsType: 'array' }),
      row({ visitId: 'b', cptCodesType: 'object', templateSectionsType: null }),
      row({ visitId: 'c', cptCodesType: null, templateSectionsType: null }),
    ]);
    expect(r.control.cptCodesTypes).toEqual({ object: 2, null: 1 });
    expect(r.control.templateSectionsTypes).toEqual({ array: 1, null: 2 });
  });

  it('counts the non-vacuity controls the CLI refuses on', () => {
    const r = scanEmArtifacts([
      row({ visitId: 'a', specialty: 'ultrasound', noteHeadingLines: '' }),
      row({ visitId: 'b', templateSections: [{ label: 'SUBJECTIVE' }] }),
    ]);
    // one specialty-eligible (b), one with headings (b), one with labels (b)
    expect(r.control.specialtyEligible).toBe(1);
    expect(r.control.rowsWithHeadings).toBe(1);
    expect(r.control.rowsWithTemplateLabels).toBe(1);
  });
});
