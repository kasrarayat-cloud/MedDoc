// ============================================================================
// GATE — F12-f. THE OPERATIVE COUNTERWEIGHT AND THE OFFICE ESCAPE ARE TWO
// NAMED PREDICATES OVER ONE BOUNDED VOCABULARY, AND THE VOCABULARY'S BOUND IS
// THE THING BEING GUARDED.
// ----------------------------------------------------------------------------
// F12-a/#126(b) established the counterweight: a label set carrying the full
// SOAP skeleton is an OFFICE VISIT, and operative markers may not overrule it.
// F12-d found the counterweight could not see `ASSESSMENT & PLAN`, widened the
// ESCAPE to count CONCEPTS, and deliberately left the COUNTERWEIGHT alone —
// because both read one function through one floor, so moving it would have
// moved the counterweight in the UNDER-suppression direction.
//
// F12-f removes that coupling (two named floors at two named call sites) and
// then converges the vocabulary, which is what closes three of the four
// families #126(b) exists to protect.
//
// ⚠️ WHAT THIS GATE IS ACTUALLY FOR IS THE **REFUSAL**, NOT THE WIDENING.
// The widening is small and measured. The dangerous edit is the NEXT one: the
// residual F12-f leaves open makes single-concept synonyms look like the
// obvious cure, and the corpus says they un-suppress a SIGNED operative record.
// A refusal recorded only in prose decays; these arms make it a red test.
//
// MEASURED 2026-08-19 against the full production corpus (48 visits, 10
// templates), in the production flag universe read from the running container:
//
//   this change                              +0 suppressed  +0 applied
//   + single-concept synonyms                +0 suppressed  +1 APPLIED  <- harm
//   + synonyms minus RECOMMENDATIONS         +0 suppressed  +0 applied  <- and
//        that zero is worthless: the corpus holds ONE operative vocabulary,
//        emitted 19 times by one generator, so it cannot discriminate.
// ============================================================================

import { describe, it, expect } from 'vitest';
import {
  emAppliesToVisit,
  isProcedureNoteShape,
  isProcedureNoteShapeFromText,
  templateIsSilent,
  noteReadsAsOfficeVisitFromText,
  officeConceptCountFromText,
  officeSkeletonCountFromText,
  procedureNoteMarkerCountFromText,
  OFFICE_COUNTERWEIGHT_FLOOR,
  OFFICE_ESCAPE_FLOOR,
  OFFICE_SKELETON_SECTIONS,
  PROCEDURE_NOTE_MARKER_FLOOR,
  PROCEDURE_NOTE_SECTION_MARKERS,
  REFUSED_OFFICE_CONCEPT_SYNONYMS,
} from '../note-shape';

/** A template `sections` JSONB value, in the shape the column actually holds. */
const sec = (labels: string[]) => labels.map((label) => ({ label }));
/** A note BODY carrying exactly these headings. */
const body = (labels: string[]) => labels.map((l) => `## ${l}`).join('\n\nsome text\n\n');

/** The combined spellings the vocabulary accepts, and the concepts each names.
 *  Declared here rather than imported so the gate states the CLAIM
 *  independently — an arm that imports the list it is checking agrees with any
 *  list at all. */
const ACCEPTED_COMBINED: ReadonlyArray<readonly [string, readonly string[]]> = [
  ['ASSESSMENT & PLAN', ['ASSESSMENT', 'PLAN']],
  ['ASSESSMENT AND PLAN', ['ASSESSMENT', 'PLAN']],
  ['ASSESSMENT/PLAN', ['ASSESSMENT', 'PLAN']],
  ['IMPRESSION & PLAN', ['ASSESSMENT', 'PLAN']],
  ['IMPRESSION AND PLAN', ['ASSESSMENT', 'PLAN']],
  ['IMPRESSION/PLAN', ['ASSESSMENT', 'PLAN']],
  ['SUBJECTIVE & OBJECTIVE', ['SUBJECTIVE', 'OBJECTIVE']],
  ['SUBJECTIVE AND OBJECTIVE', ['SUBJECTIVE', 'OBJECTIVE']],
];

// ────────────────────────────────────────────────────────────────────────────
describe('F12-f · non-vacuity — the quantities this gate reads must discriminate', () => {
  it('both floors exist, are FOUR, and AGREE — a divergence must be deliberate', () => {
    expect(OFFICE_COUNTERWEIGHT_FLOOR).toBe(4);
    expect(OFFICE_ESCAPE_FLOOR).toBe(4);
    // ⚠️ The two are separate constants ON PURPOSE (that separation IS F12-f),
    // and they carry the same value today. This arm is what makes a future
    // divergence a decision somebody had to overwrite a test to make, rather
    // than a side effect of editing one line.
    expect(OFFICE_COUNTERWEIGHT_FLOOR).toBe(OFFICE_ESCAPE_FLOOR);
    expect(OFFICE_COUNTERWEIGHT_FLOOR).toBe(OFFICE_SKELETON_SECTIONS.length);
  });

  it('the refused list is non-empty and DISJOINT from everything else the module names', () => {
    expect(REFUSED_OFFICE_CONCEPT_SYNONYMS.length).toBeGreaterThan(0);
    // A refused label must not also be a skeleton section (it would be accepted
    // by the literal path) nor an operative marker (it would be counted twice,
    // in opposite directions, off one heading).
    for (const label of REFUSED_OFFICE_CONCEPT_SYNONYMS) {
      expect(OFFICE_SKELETON_SECTIONS, `${label} is both refused and a skeleton section`).not.toContain(label);
      expect(PROCEDURE_NOTE_SECTION_MARKERS, `${label} is both refused and an operative marker`).not.toContain(label);
    }
    // And the accepted combined spellings must be disjoint from the refused
    // list, or the module is saying two things about one heading.
    for (const [label] of ACCEPTED_COMBINED) {
      expect(REFUSED_OFFICE_CONCEPT_SYNONYMS, `${label} is both accepted and refused`).not.toContain(label);
    }
  });

  it('the counters are not the same function wearing two names', () => {
    // If `officeSkeletonCountFromText` and `officeConceptCountFromText` agreed
    // everywhere, every "concepts" assertion below would pass on a literal
    // counterweight and this gate would prove nothing. One input separates
    // them, and it is the input the whole item is about.
    const merged = body(['SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT & PLAN']);
    expect(officeSkeletonCountFromText(merged)).toBe(2);
    expect(officeConceptCountFromText(merged)).toBe(4);
  });
});

// ────────────────────────────────────────────────────────────────────────────
describe('F12-f · THE FIX — orthography no longer strips a billable level', () => {
  // The four families ruling #126(b) names, each written the way a doctor who
  // merges assessment and plan actually writes it. Before F12-f the
  // counterweight scored these THREE and the operative markers won.
  const FAMILIES: ReadonlyArray<readonly [string, string[]]> = [
    ['post-op office follow-up', ['SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT & PLAN', 'POSTOPERATIVE DIAGNOSIS', 'POSTOPERATIVE FINDINGS']],
    ['derm office w/ excision', ['SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT AND PLAN', 'SPECIMENS REMOVED', 'ESTIMATED BLOOD LOSS']],
    ['pre-op H&P (office)', ['SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT/PLAN', 'PREOPERATIVE DIAGNOSIS', 'INDICATIONS FOR PROCEDURE']],
    ['surgical consult (office)', ['SUBJECTIVE & OBJECTIVE', 'ASSESSMENT', 'PLAN', 'DESCRIPTION OF PROCEDURE', 'INDICATIONS FOR PROCEDURE']],
  ];

  it.each(FAMILIES)('%s — merged headings, still an office visit on BOTH arms', (name, labels) => {
    const text = body(labels);

    // NON-VACUITY, PER FIXTURE: it must genuinely carry enough operative
    // markers to be suppressed, or the arm proves nothing about the
    // counterweight — it would pass on a note nothing was ever going to
    // suppress. This is the fixture-monoculture lesson applied per row.
    expect(procedureNoteMarkerCountFromText(text), `${name}: fixture must be suppressible`)
      .toBeGreaterThanOrEqual(PROCEDURE_NOTE_MARKER_FLOOR);

    // DISCRIMINATION: the LITERAL count is below the floor, so a literal
    // counterweight would NOT have rescued this. That is what makes the two
    // assertions below evidence about the CONCEPT path specifically.
    expect(officeSkeletonCountFromText(text), `${name}: a literal counterweight must fail here`)
      .toBeLessThan(OFFICE_COUNTERWEIGHT_FLOOR);
    expect(officeConceptCountFromText(text), `${name}: the concept counterweight must reach the floor`)
      .toBe(OFFICE_COUNTERWEIGHT_FLOOR);

    // ⚠️ BOTH ARMS. The template arm and the note-body arm resolve through one
    // classifier, and an asymmetry between them is exactly the state F12-d left
    // behind and F12-f removed. Asserting one would not see the other.
    expect(isProcedureNoteShape(sec(labels)), `${name}: TEMPLATE arm`).toBe(false);
    expect(isProcedureNoteShapeFromText(text), `${name}: NOTE-BODY arm`).toBe(false);
  });

  it.each(ACCEPTED_COMBINED)('%s satisfies its concepts on BOTH the counterweight and the escape', (label, concepts) => {
    // SPLIT-FAMILY COVERAGE, BOTH DIRECTIONS. The escape gained this vocabulary
    // in F12-d and the counterweight in F12-f; an arm that checked only one
    // would let a future edit remove the other and silently restore the
    // asymmetry.
    const others = OFFICE_SKELETON_SECTIONS.filter((s) => !concepts.includes(s));
    const text = body([label, ...others]);
    expect(officeConceptCountFromText(text), `${label}: escape reach`).toBe(OFFICE_ESCAPE_FLOOR);
    expect(noteReadsAsOfficeVisitFromText(text), `${label}: the ESCAPE must fire`).toBe(true);
    // Counterweight reach: the same labels plus two operative markers must
    // still read as an office visit.
    expect(
      isProcedureNoteShape(sec([label, ...others, 'PREOPERATIVE DIAGNOSIS', 'DESCRIPTION OF PROCEDURE'])),
      `${label}: the COUNTERWEIGHT must fire`,
    ).toBe(false);
  });
});

// ────────────────────────────────────────────────────────────────────────────
describe('F12-f · THE REFUSAL — single-concept synonyms stay out, and here is why', () => {
  it.each(REFUSED_OFFICE_CONCEPT_SYNONYMS.map((l) => [l]))('%s supplies ZERO office concepts', (label) => {
    // ⚠️ ASSERTED THROUGH THE DATA STRUCTURE, NEVER THROUGH THE FILE TEXT. A
    // grep answers a question about a file; membership is a question about the
    // counter. They agree right up until they don't.
    expect(officeConceptCountFromText(body([label]))).toBe(0);
    // And it must not sneak in as a partial contribution alongside three real
    // sections — which is the only shape in which it would ever matter.
    const threeReal = ['SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT'];
    expect(officeConceptCountFromText(body([...threeReal, label])), `${label} must not be the fourth concept`).toBe(3);
  });

  it('⚠️ THE COUNTEREXAMPLE — a SIGNED operative record the synonyms would un-suppress', () => {
    // Production visit `cmrxxj1rn000h01pnoloiiajx`: bariatric surgery, SIGNED,
    // `cptCodes.em.signedCode` FROZEN at 99214. Its note body, verbatim by
    // heading:
    const SIGNED_OP_NOTE = [
      'PROCEDURE',
      'PREOPERATIVE DIAGNOSIS',
      'POSTOPERATIVE FINDINGS',
      'CONSENT',
      'DESCRIPTION OF PROCEDURE',
      'RECOMMENDATIONS',
      'SUBJECTIVE',
      'OBJECTIVE',
      'ASSESSMENT',
    ];
    const text = body(SIGNED_OP_NOTE);

    // Three operative markers and THREE office concepts — one short of the
    // floor, which is exactly where ruling #126(b) set it, by hand, against
    // this row. `RECOMMENDATIONS -> PLAN` is the single edit that takes it to
    // four, and `RECOMMENDATIONS` appears in 4 of 4 operative templates and 19
    // of 19 operative bodies on production: it is the operative note's own plan
    // section, not an office synonym.
    expect(procedureNoteMarkerCountFromText(text)).toBe(3);
    expect(officeConceptCountFromText(text)).toBe(3);
    expect(officeConceptCountFromText(text)).toBeLessThan(OFFICE_COUNTERWEIGHT_FLOOR);
    expect(isProcedureNoteShapeFromText(text), 'a SIGNED operative record must stay suppressed').toBe(true);
    expect(REFUSED_OFFICE_CONCEPT_SYNONYMS).toContain('RECOMMENDATIONS');
  });

  it('⚠️ AND REMOVING ONLY `RECOMMENDATIONS` IS NOT A FIX — the monoculture argument, as a shape', () => {
    // The measured corpus diff for "synonyms minus RECOMMENDATIONS" is ZERO
    // rows. That zero is not evidence of safety: production holds exactly one
    // operative vocabulary, emitted 19 times by one generator, so it cannot
    // discriminate. This is an ordinary operative-note heading set that the
    // remaining synonyms would score FOUR on — and nothing in today's data
    // would have objected.
    const OP_IN_SYNONYM_VOCABULARY = [
      'CHIEF COMPLAINT',
      'FINDINGS',
      'DIAGNOSIS',
      'PATIENT INSTRUCTIONS',
      'DESCRIPTION OF PROCEDURE',
      'POSTOPERATIVE FINDINGS',
    ];
    const text = body(OP_IN_SYNONYM_VOCABULARY);
    expect(procedureNoteMarkerCountFromText(text)).toBeGreaterThanOrEqual(PROCEDURE_NOTE_MARKER_FLOOR);
    expect(officeConceptCountFromText(text), 'the refused synonyms must supply nothing here').toBe(0);
    expect(isProcedureNoteShapeFromText(text)).toBe(true);
    // Each of the four labels above is on the refused list — so this fixture
    // goes red the moment any one of them is admitted, not only the worst one.
    for (const l of ['CHIEF COMPLAINT', 'FINDINGS', 'DIAGNOSIS', 'PATIENT INSTRUCTIONS']) {
      expect(REFUSED_OFFICE_CONCEPT_SYNONYMS).toContain(l);
    }
  });
});

// ────────────────────────────────────────────────────────────────────────────
describe('F12-f · `templateIsSilent` MOVED WITH THE COUNTERWEIGHT — the half-landed fix', () => {
  // ⚠️ THIS WHOLE BLOCK EXISTS BECAUSE THE REFUTATION PASS FOUND F12-f SHIPPED
  // HALF-APPLIED. The counterweight was moved to concepts and `templateIsSilent`
  // was left literal, and the two then disagreed about one template with a
  // concrete wrong output. It is the canonical shape: the failure that ships is
  // the first edit the code's own comment invites, with the other layer missing.
  const OPERATIVE_BODY = body(['PROCEDURE', 'PREOPERATIVE DIAGNOSIS', 'POSTOPERATIVE FINDINGS', 'DESCRIPTION OF PROCEDURE']);

  const BARE_SKELETON_SPELLINGS: ReadonlyArray<readonly [string, string[]]> = [
    ['literal', ['SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT', 'PLAN']],
    ['merged A&P', ['SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT & PLAN']],
    ['merged S&O', ['SUBJECTIVE & OBJECTIVE', 'ASSESSMENT', 'PLAN']],
    ['both merged', ['SUBJECTIVE & OBJECTIVE', 'ASSESSMENT AND PLAN']],
  ];

  it.each(BARE_SKELETON_SPELLINGS)('a bare skeleton spelled "%s" is SILENT', (_name, labels) => {
    // A template naming only the document's SKELETON has said nothing about the
    // ENCOUNTER, whichever way the doctor spelled it.
    expect(templateIsSilent(sec(labels))).toBe(true);
  });

  it.each(BARE_SKELETON_SPELLINGS)('… and an OPERATIVE body under it is suppressed — "%s"', (_name, labels) => {
    // ⚠️ THE ARM THAT ACTUALLY CAUGHT IT. Before the second half landed, the
    // merged spellings returned TRUE here — an operative note keeping an office
    // E/M level purely because the doctor merged two headings in the TEMPLATE.
    expect(
      emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections: sec(labels), noteText: OPERATIVE_BODY }),
      'an operative note must not keep a level because of template orthography',
    ).toBe(false);
  });

  it('but a template that says something REAL is still not silent', () => {
    // Non-vacuity in the other direction: if everything were silent, the arms
    // above would pass on a predicate that returned a constant, and the whole
    // narrowness of the fallback (ruling #126) would be gone.
    expect(templateIsSilent(sec(['SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT', 'PLAN', 'CHIEF COMPLAINT']))).toBe(false);
    expect(templateIsSilent(sec(['TECHNIQUE', 'FINDINGS', 'IMPRESSION']))).toBe(false);
    expect(templateIsSilent(sec(['PROCEDURE', 'CONSENT', 'DESCRIPTION OF PROCEDURE']))).toBe(false);
    // Production's real templates, by their real labels — 8 of 10 say something.
    expect(templateIsSilent(sec(['Exam Metadata', 'TECHNIQUE', 'FINDINGS', 'IMPRESSION', 'DIAMETER AND REFLUX TIME']))).toBe(false);
    // and the two that do not: no template at all, and the system default.
    expect(templateIsSilent(null)).toBe(true);
    expect(templateIsSilent(sec(['Subjective', 'Objective', 'Assessment', 'Plan']))).toBe(true);
  });
});

// ────────────────────────────────────────────────────────────────────────────
describe('F12-f · REGRESSION — the classifier still classifies', () => {
  it('⚠️ HONEST LIMIT — TWO headings can now satisfy a FOUR-concept floor', () => {
    // Recorded rather than discovered later. `SUBJECTIVE & OBJECTIVE` plus
    // `ASSESSMENT & PLAN` is two headings and four concepts, so the effective
    // heading count the counterweight demands has fallen from four to two.
    //
    // That is correct BY DESIGN — the floor counts what the doctor DOCUMENTED,
    // not how many headings they typed — and it is the direct consequence of
    // the widening rather than an oversight. It is pinned here because it is
    // the strongest available argument for keeping the vocabulary bounded to
    // SPELLINGS: every synonym admitted lowers this number further, and at two
    // headings there is not much floor left to give.
    expect(officeConceptCountFromText(body(['SUBJECTIVE & OBJECTIVE', 'ASSESSMENT & PLAN']))).toBe(4);
    expect(isProcedureNoteShape(sec(['SUBJECTIVE & OBJECTIVE', 'ASSESSMENT & PLAN', 'PREOPERATIVE DIAGNOSIS', 'DESCRIPTION OF PROCEDURE']))).toBe(false);
    // No production template or note body carries either heading — measured
    // 2026-08-19 over 10 templates and 48 bodies. Forward-only, like the rest.
  });

  it('a pure operative note is untouched by the wider counterweight', () => {
    // Production's actual operative shape, on 19 note bodies and 4 templates.
    const OP = ['PROCEDURE', 'PREOPERATIVE DIAGNOSIS', 'POSTOPERATIVE FINDINGS', 'CONSENT', 'DESCRIPTION OF PROCEDURE', 'RECOMMENDATIONS'];
    expect(officeConceptCountFromText(body(OP))).toBe(0);
    expect(isProcedureNoteShape(sec(OP))).toBe(true);
    expect(isProcedureNoteShapeFromText(body(OP))).toBe(true);
  });

  it('the trailing-colon template is still classified — normalisation survives the widening', () => {
    // One of production's four operative templates spells every label with a
    // trailing colon. An exact-match classifier that lost `normalizeSectionLabel`
    // would find 3 of 4 and report a confident, wrong answer.
    const COLONS = ['PROCEDURE:', 'PREOPERATIVE DIAGNOSIS:', 'POSTOPERATIVE FINDINGS:', 'CONSENT:', 'DESCRIPTION OF PROCEDURE:', 'RECOMMENDATIONS:'];
    expect(isProcedureNoteShape(sec(COLONS))).toBe(true);
    // and the combined spellings normalise too, or the widening is half-applied
    expect(officeConceptCountFromText(body(['SUBJECTIVE:', 'OBJECTIVE:', 'Assessment & Plan:']))).toBe(4);
  });

  it('⚠️ NEVER A SUBSTRING SCAN — "IMPLANT" contains "plan", and now so does the concept path', () => {
    // The widening added named spellings, not a looser matcher. A substring
    // scan would score `IMPLANT REMOVAL` as a PLAN and hand this operative note
    // a level off three real sections plus one false one.
    expect('IMPLANT'.toLowerCase().includes('plan')).toBe(true); // the trap, demonstrated
    const opWithImplant = ['IMPLANT REMOVAL', 'SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT', 'PREOPERATIVE DIAGNOSIS', 'DESCRIPTION OF PROCEDURE'];
    expect(officeConceptCountFromText(body(opWithImplant))).toBe(3);
    expect(isProcedureNoteShape(sec(opWithImplant))).toBe(true);
  });

  it('KNOWN RESIDUAL — F12-f does NOT close the non-SOAP office vocabulary, and says so', () => {
    // Production's ACTIVE template `cmpz63jsw000501tayag818lq` spells its
    // sections this way. Under an operative template, an office note in this
    // vocabulary is STILL over-suppressed. Measured 2026-08-19: that template
    // is bound to ZERO visits, so the residual is forward-only.
    //
    // ⚠️ THIS ARM IS PINNED SO THE RESIDUAL CANNOT BE CLOSED SILENTLY. Anyone
    // who widens the vocabulary far enough to fix it turns this red and has to
    // come here, read the refusal above, and update the ledger.
    const NON_SOAP_OFFICE = ['CHIEF COMPLAINT', 'INTERVAL HISTORY', 'EXAM', 'IMPRESSION & PLAN', 'PATIENT INSTRUCTIONS'];
    const text = body([...NON_SOAP_OFFICE, 'SPECIMENS REMOVED', 'ESTIMATED BLOOD LOSS']);
    // TWO, not zero — `IMPRESSION & PLAN` IS seen now. The refuter's original
    // figure was 0 against the literal counterweight; F12-f moved the count and
    // not the conclusion.
    expect(officeConceptCountFromText(text)).toBe(2);
    expect(officeConceptCountFromText(text)).toBeLessThan(OFFICE_COUNTERWEIGHT_FLOOR);
    expect(isProcedureNoteShapeFromText(text)).toBe(true);
  });
});
