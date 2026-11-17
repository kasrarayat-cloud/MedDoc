"""Round r2f's lane f-engine (DECISIONS D309 lane E, with D311), TEXT-ONLY and SYNTHETIC: every FactSet is hand-built
from engine/types' records (tests/v2/evaluate_fixtures' Doc), every note was written for these tests (fictional
clinicians, no patient) and is checked against the acceptance set's DEV-EXCLUSION list, every pass-1 answer is
constructed by hand with tests/v2/test_settle's builders, and nothing is sent anywhere.

What is proved:
- e-engine's KEEPERS (round r2e's test_r2ee_engine, split from its patch as D309 rules: nothing of P4-PLAN or P3-CARDS),
  ported unchanged in what they assert:
  - D302 RCG-T1..T3 (refutation rf-r2c-geom of round r2c's P3-PART): check()-level tests for every subject family a
    procedure part reaches - a section's own fact, a session through its examination, a lesion through its
    description, a person through its name - and the part head's closers and words outside its start source never
    holding (R2FEProcedurePartCheckTests); tests of int2's own code, which the refuter's surviving mutants MX1-MX3 fail;
  - D303 RFA3-1..4 (refutation rf-eng-a3 of round r2d's eng-a3): a must-change test for each widening term of
    evaluate.may_exclude and its premise, each beside its boundary twin (R2FEMayExcludeTermTests); tests of int2's own
    code, which the refuter's surviving mutants MAYBE-OF-NO-FAMILY, Q-TODAY-ANY, Q-SESSION-ANY, CITED-DENIAL-ANY and
    PREMISE-PERFORMED-ONLY fail;
  - D303 RF3-1/2 (refutation rf-eng-b3 of round r2d's eng-b3): "a device of another kind" admits no instrument another
    member's row names, and "a catheter" admits the cold forceps and the retrieval snare a single-operator
    cholangioscope delivers (R2FEDeviceTests) - the device-table corrections in pairing.ADMITS, each with its
    must-change test and its boundary;
- D309 e-engine's Q4 (round 2's Q4, the which-pairs corner DECISIONS D228 keeps as built), reproduced on int2 and fixed
  as a class rule in the reader that released (engine/pairing: ``possibly_statement``, ``possibly_other_date``,
  ``possibly_other_performer``, ``paired``'s claimed arm): a claimed pair (D's scope.covers names A) is read whenever D
  MAY be a statement, so no 9.4 weakening of the date relation or performer that made an event of established status a
  statement drops it - the must-change inputs (an established plan of a later date, an act of an earlier date, an act of
  another clinician, a denial of the date of service or of the team, each naming today's removal in its covers) held
  under every weakening, READY on int2 (R2FEWhichPairsClaimedTests); the boundaries left alone (an unclaimed pair, a
  silent date or performer, today's team act naming another in its covers, D228's DQ2 corner); and P-MONO over a
  generated family of such scenes, every weakening of the corner's two facts checked by tests/v2/test_properties' own
  P-MONO check (its named releases, D264's every-row rule) and every item worded by the renderer
  (R2FEWhichPairsMonotoneTests).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import hypothesis
from django.test import SimpleTestCase
from hypothesis import strategies as st

from studio import interpretation
from studio.interpretation.contract import checks, extract_read, segment
from studio.interpretation.contract import extract_schema as xs
from studio.interpretation.contract import types as ct
from studio.interpretation.contract.extract_read import FactKey
from studio.interpretation.engine import evaluate as EV
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import pairing as P
from studio.interpretation.engine.types import Id, IdFamily, Span
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA
from tests.v2 import test_properties as TP
from tests.v2.test_settle import DEV_EXCLUSION, answer, event, fact, labelled, lesion, opening, session, src

A, Rs, Kind, Status = ct.Attribute, ct.Reason, ct.Kind, ct.Status
Device, Landmark, Breadth = ct.Device, ct.Landmark, ct.Breadth
sup, neg, unres = EF.sup, EF.neg, EF.unres
E, X, L = EF.E, EF.X, EF.L
PLANNED, PERFORMED, ATTEMPTED = Status.PLANNED, Status.PERFORMED, Status.ATTEMPTED_NOT_COMPLETED
ON, LATER, EARLIER = ct.DateRelation.ON_DATE_OF_SERVICE, ct.DateRelation.LATER_DATE, ct.DateRelation.EARLIER_DATE
TEAM, DC = ct.Performer.DOCUMENTING_TEAM, ct.Owner.DOCUMENTING_CLINICIAN
OTHER, FACILITY = ct.Performer.OTHER_CLINICIAN, ct.Performer.OTHER_FACILITY


def code_of(R, code, where) -> tuple:
    """engine/assess over ``R`` with ``code`` proposed on ``where`` (tests/v2/test_assess.run): (status, its held facts'
    causes, sorted and each once)."""
    found = TA.by_code(TA.run(R, (code, where)))[code]
    return found.status.value, sorted({held.cause for held in found.held_facts})


# --- the synthetic notes (round r2e's, kept for RCG-T1..T3) ---------------------------------------------------

# D302 RCG-T1..T3: a note in procedure parts whose findings part tells every subject family - the colonoscopy's own
# examination, a lesion's description and a person's name lie in N4, below 'PART 2: COLONOSCOPY' (S1-S12)
FAMILIES = ('SYNTHETIC ENDOSCOPY NOTE\n'                                                      # S1: N0
            'Date of service: 03/14/2031\n'                                                   # S2
            'Endoscopist: Corvin Ashdale, MD (fictional)\n'                                   # S3
            '\n'
            'PART 1: UPPER ENDOSCOPY\n'                                                       # S4: N1, procedure
            'The gastroscope was advanced to the second part of the duodenum.\n'              # S5: E1, X1
            'FINDINGS:\n'                                                                     # S6: N2, findings
            'Biopsies of the gastric antrum were taken with cold forceps.\n'                  # S7: E2
            '\n'
            'PART 2: COLONOSCOPY\n'                                                           # S8: N3, procedure
            'FINDINGS:\n'                                                                     # S9: N4, findings
            'The colonoscope was advanced to the cecum.\n'                                    # S10: E3, X2
            'A 5 mm polyp in the sigmoid colon was removed with a cold snare.\n'              # S11: E4, L1
            'Assistant: Ines Varro, RN (fictional)\n')                                        # S12: P2's name
# RCG-T2: PART 2's heading section gives a closing source, its own signature line, before its findings part (S1-S12)
CLOSER = 'End of colonoscopy part; Corvin Ashdale, MD (fictional).'
CLOSING = ('SYNTHETIC ENDOSCOPY NOTE\n'                                                       # S1
           'Date of service: 03/14/2031\n'                                                    # S2
           'Endoscopist: Corvin Ashdale, MD (fictional)\n'                                    # S3
           '\n'
           'PART 1: UPPER ENDOSCOPY\n'                                                        # S4: N1
           'The gastroscope was advanced to the second part of the duodenum.\n'               # S5: E1
           'FINDINGS:\n'                                                                      # S6: N2
           'Biopsies of the gastric antrum were taken with cold forceps.\n'                   # S7: E2
           '\n'
           'PART 2: COLONOSCOPY\n'                                                            # S8: N3
           'The colonoscope was advanced to the cecum.\n'                                     # S9: E3
           f'{CLOSER}\n'                                                                      # S10: N3's closer
           'FINDINGS (COLON):\n'                                                              # S11: N4
           'A 5 mm polyp in the sigmoid colon was removed with a cold snare.\n')              # S12: E4
# RCG-T3: PART 2's heading line holds more than its start words (S1-S11)
HEADING = 'PART 2: COLONOSCOPY (outside report reviewed, done 03/10/2031)'
LONG_HEADING = ('SYNTHETIC ENDOSCOPY NOTE\n'                                                  # S1
                'Date of service: 03/14/2031\n'                                               # S2
                'Endoscopist: Corvin Ashdale, MD (fictional)\n'                               # S3
                '\n'
                'PART 1: UPPER ENDOSCOPY\n'                                                   # S4: N1
                'The gastroscope was advanced to the second part of the duodenum.\n'          # S5: E1
                'FINDINGS:\n'                                                                 # S6: N2
                'Biopsies of the gastric antrum were taken with cold forceps.\n'              # S7: E2
                '\n'
                f'{HEADING}\n'                                                                # S8: N3
                'The colonoscope was advanced to the cecum.\n'                                # S9: E3
                'FINDINGS (COLON):\n'                                                         # S10: N4
                'A 5 mm polyp in the sigmoid colon was removed with a cold snare.\n')         # S11: E4


NOTES = {'FAMILIES': FAMILIES, 'CLOSING': CLOSING, 'LONG_HEADING': LONG_HEADING}


class R2FEFixtureTests(SimpleTestCase):
    """The keeper notes (ported from round r2e's R2EEFixtureTests, DECISIONS D309): none on the acceptance set's
    exclusion list, each cut one unit per line."""

    def test_rfe_no_note_here_is_on_the_acceptance_exclusion_list(self):
        with open(DEV_EXCLUSION, encoding='ascii') as handle:
            excluded = {line.strip() for line in handle if line.strip()}
        self.assertTrue(excluded and all(len(value) == 64 for value in excluded), 'the exclusion list is readable')
        listed = [name for name, text in NOTES.items()
                  if {hashlib.sha256(text.encode('utf-8')).hexdigest(),
                      hashlib.sha256(text.strip().encode('utf-8')).hexdigest()} & excluded]
        self.assertEqual(listed, [])

    def test_rfe_the_notes_cut_one_unit_per_line(self):
        for name, text in NOTES.items():
            with self.subTest(note=name):
                lines = [line for line in text.split('\n') if line]
                self.assertEqual([text[unit.start:unit.end] for unit in segment.units(text)], lines)


# --- D302 RCG-T1..T3 (P3-PART at check(), every subject family; the part's start only) -------------------------------


def _key(family, name, attribute, index=0):
    return FactKey(family, name, attribute, index)


def _read(text, data):
    found = extract_read.read(json.dumps(data), len(segment.units(text)),
                              version=interpretation.INTERPRETATION_VERSION_V3)
    assert not isinstance(found, extract_read.Refusal), found
    return found


def _findings(text, data, keys):
    checked = checks.check(text, (), _read(text, data))
    return {f'{name}.{attribute.value}': checked.findings.get(_key(family, name, attribute), ())
            for family, name, attribute in keys}


PART1, PART2 = ('S4', 'PART 1: UPPER ENDOSCOPY'), ('S8', 'PART 2: COLONOSCOPY')


def families_answer(cite):
    """FAMILIES' pass-1 answer: N0; N1 'PART 1: UPPER ENDOSCOPY' (procedure), N2 'FINDINGS:'; N3 'PART 2: COLONOSCOPY'
    (procedure) and its findings part N4 'FINDINGS:', which tells the colonoscopy's own examination E3 (S10: X2's
    examination), the cold-snare removal E4 of L1 (S11: L1's description) and the assistant P2's name (S12). ``cite``
    maps a subject family's fact - 'section' (N4's occasion and performer), 'session' (X2's encounter), 'lesion' (L1's
    multiplicity) and 'person' (P2's role) - to the (unit, words) its ``section`` source cites."""
    def at(name):
        unit, words = cite[name]
        return src([unit], words, 'section')

    n4 = labelled('N4', 'S9', 'FINDINGS:', 'findings')
    n4['occasion'] = [fact('on_date_of_service', at('section'))]
    n4['performer'] = [fact('documenting_team', at('section'))]
    return answer(
        sections=[opening(), labelled('N1', 'S4', 'PART 1: UPPER ENDOSCOPY', 'procedure'),
                  labelled('N2', 'S6', 'FINDINGS:', 'findings'),
                  labelled('N3', 'S8', 'PART 2: COLONOSCOPY', 'procedure'), n4],
        people=[{'id': 'P1', 'name': src(['S3'], 'Corvin Ashdale'),
                 'role': fact('documenting_clinician', src(['S3'], 'Endoscopist'))},
                {'id': 'P2', 'name': src(['S12'], 'Ines Varro'), 'role': fact('assistant', at('person'))}],
        sessions=[session('X1', fact('egd', src(['S5'], 'gastroscope')), examination=[fact('E1', src(['S5']))],
                          encounter=[fact('this_encounter', src(['S2'], '', 'document_frame'))],
                          reached=[fact('duodenum', src(['S5'], 'advanced to the second part of the duodenum'))]),
                  session('X2', fact('colonoscopy', src(['S10'], 'colonoscope')), examination=[fact('E3', src(['S10']))],
                          encounter=[fact('this_encounter', at('session'))],
                          reached=[fact('cecum', src(['S10'], 'advanced to the cecum'))])],
        lesions=[lesion('L1', src(['S11'], 'A 5 mm polyp'), multiplicity=[fact('single', at('lesion'))],
                        places=[fact('sigmoid_colon', src(['S11'], 'sigmoid colon'))])],
        events=[event('E1', ['S5'], 'gastroscope', 'was advanced', 'examination', session=[fact('X1', src(['S5']))]),
                event('E2', ['S7'], 'Biopsies', 'were taken', 'biopsy',
                      session=[fact('X1', src(['S4'], 'PART 1: UPPER ENDOSCOPY', 'section'))],
                      target__places=[fact('gastric_antrum', src(['S7'], 'gastric antrum'))],
                      technique__device=[fact('cold_forceps', src(['S7'], 'cold forceps'))]),
                event('E3', ['S10'], 'colonoscope', 'was advanced', 'examination', session=[fact('X2', src(['S10']))]),
                event('E4', ['S11'], 'cold snare', 'was removed', 'snare',
                      session=[fact('X2', src(['S8'], 'PART 2: COLONOSCOPY', 'section'))],
                      target__lesion=[fact('L1', src(['S11'], 'A 5 mm polyp'))],
                      target__places=[fact('sigmoid_colon', src(['S11'], 'sigmoid colon'))],
                      technique__device=[fact('cold_snare', src(['S11'], 'cold snare'))])])


FAMILY_KEYS = {'section': ((xs.Family.SECTION, 'N4', A.OCCASION), (xs.Family.SECTION, 'N4', A.PERFORMER)),
               'session': ((xs.Family.SESSION, 'X2', A.ENCOUNTER),),
               'lesion': ((xs.Family.LESION, 'L1', A.MULTIPLICITY),),
               'person': ((xs.Family.PERSON, 'P2', A.ROLE),)}


def two_part(text, part2_line, e4_cite):
    """CLOSING's or LONG_HEADING's answer: test_r2cg_geometry's two-part note, its N3 opened by ``part2_line`` (its start
    words 'PART 2: COLONOSCOPY'), N3's closer when CLOSING tells one, N4 'FINDINGS (COLON):'; E4's session cited at
    ``e4_cite`` (unit, words) through the link section."""
    units = {text[unit.start:unit.end]: unit.id for unit in segment.units(text)}
    n3 = labelled('N3', units[part2_line], 'PART 2: COLONOSCOPY', 'procedure')
    if CLOSER in units:
        n3['end'] = [src([units[CLOSER]], CLOSER, 'section')]
    n4 = labelled('N4', units['FINDINGS (COLON):'], 'FINDINGS (COLON):', 'findings')
    egd_exam = units['The gastroscope was advanced to the second part of the duodenum.']
    col_exam = units['The colonoscope was advanced to the cecum.']
    biopsy = units['Biopsies of the gastric antrum were taken with cold forceps.']
    snare = units['A 5 mm polyp in the sigmoid colon was removed with a cold snare.']
    return answer(
        sections=[opening(), labelled('N1', 'S4', 'PART 1: UPPER ENDOSCOPY', 'procedure'),
                  labelled('N2', 'S6', 'FINDINGS:', 'findings'), n3, n4],
        sessions=[session('X1', fact('egd', src([egd_exam], 'gastroscope')), examination=[fact('E1', src([egd_exam]))],
                          encounter=[fact('this_encounter', src(['S2'], '', 'document_frame'))]),
                  session('X2', fact('colonoscopy', src([col_exam], 'colonoscope')),
                          examination=[fact('E3', src([col_exam]))],
                          encounter=[fact('this_encounter', src(['S2'], '', 'document_frame'))])],
        lesions=[lesion('L1', src([snare], 'A 5 mm polyp'), multiplicity=[fact('single', src([snare], 'A 5 mm polyp'))],
                        places=[fact('sigmoid_colon', src([snare], 'sigmoid colon'))])],
        events=[event('E1', [egd_exam], 'gastroscope', 'was advanced', 'examination',
                      session=[fact('X1', src([egd_exam]))]),
                event('E2', [biopsy], 'Biopsies', 'were taken', 'biopsy',
                      session=[fact('X1', src(['S4'], 'PART 1: UPPER ENDOSCOPY', 'section'))],
                      target__places=[fact('gastric_antrum', src([biopsy], 'gastric antrum'))]),
                event('E3', [col_exam], 'colonoscope', 'was advanced', 'examination',
                      session=[fact('X2', src([col_exam]))]),
                event('E4', [snare], 'cold snare', 'was removed', 'snare',
                      session=[fact('X2', src([e4_cite[0]], e4_cite[1], 'section'))],
                      target__lesion=[fact('L1', src([snare], 'A 5 mm polyp'))],
                      target__places=[fact('sigmoid_colon', src([snare], 'sigmoid colon'))])])


class R2FEProcedurePartCheckTests(SimpleTestCase):
    """Ported from round r2e's e-engine (R2EEProcedurePartCheckTests; DECISIONS D309 keeps it). DECISIONS D302
    RCG-T1..T3 (refutation rf-r2c-geom of round r2c): D299's P3-PART at contract/checks.check, for every subject
    family that has a containing section, and its START only."""

    def test_rfe_every_subject_family_reads_its_procedure_parts_heading(self):
        """RCG-T1: a section's own fact (N4's occasion and performer), a session through its examination (X2's,
        told in N4), a lesion through its description (L1's, in N4) and a person through its name (P2's, in N4) - each
        cited at its procedure part's heading through ``section`` passes G1; at another part's heading it fails
        (geometry_section). Mutant MX2 (the procedure parts handed to the event family only) fails here."""
        for family, keys in FAMILY_KEYS.items():
            cite = {name: PART2 for name in FAMILY_KEYS}
            with self.subTest(family=family, heading='its own part'):
                found = _findings(FAMILIES, families_answer(cite), keys)
                self.assertEqual(set(found.values()), {()}, found)
            cite[family] = PART1
            with self.subTest(family=family, heading="another part's"):
                found = _findings(FAMILIES, families_answer(cite), keys)
                self.assertEqual(set(found.values()), {(Rs.GEOMETRY_SECTION,)}, found)

    def test_rfe_the_part_heads_closers_never_hold(self):
        """RCG-T2: PART 2's heading section gives a closing source (its signature line); E4, told in the findings part
        N4, cites that closer through ``section`` - it fails (D299 names the part's START; the containing section's own
        closers hold, the part head's never). Its part's heading holds. Mutant MX1 (the head's start or its closers)
        fails here."""
        units = {CLOSING[unit.start:unit.end]: unit.id for unit in segment.units(CLOSING)}
        keys = ((xs.Family.EVENT, 'E4', A.SESSION),)
        found = _findings(CLOSING, two_part(CLOSING, 'PART 2: COLONOSCOPY', (units[CLOSER], CLOSER)), keys)
        self.assertEqual(found, {'E4.session': (Rs.GEOMETRY_SECTION,)})
        found = _findings(CLOSING, two_part(CLOSING, 'PART 2: COLONOSCOPY', (units['PART 2: COLONOSCOPY'],
                                                                            'PART 2: COLONOSCOPY')), keys)
        self.assertEqual(found, {'E4.session': ()})

    def test_rfe_words_of_the_heading_unit_outside_its_start_words_never_hold(self):
        """RCG-T3: PART 2's heading line holds more than its start words ('PART 2: COLONOSCOPY'); E4's session cited at
        words of that unit outside the start words fails, as ``_cites_section`` reads a section's own start - by offsets,
        never by unit; words inside the start words hold. Mutant MX3 (the head's start read by unit) fails here."""
        units = {LONG_HEADING[unit.start:unit.end]: unit.id for unit in segment.units(LONG_HEADING)}
        keys = ((xs.Family.EVENT, 'E4', A.SESSION),)
        for words, expected in (('outside report reviewed', (Rs.GEOMETRY_SECTION,)),
                                ('done 03/10/2031', (Rs.GEOMETRY_SECTION,)),
                                ('PART 2: COLONOSCOPY', ()), ('COLONOSCOPY', ())):
            with self.subTest(words=words):
                found = _findings(LONG_HEADING, two_part(LONG_HEADING, HEADING, (units[HEADING], words)), keys)
                self.assertEqual(found, {'E4.session': expected})


# --- D303 RFA3-1..4 (evaluate.may_exclude: a must-change test per widening term, each beside its twin) -----------------


def _addon(doc, primary, where):
    """(the primary's status and causes, may_exclude for it on its kept spans, 43273's status and causes) - 43273 on E3's
    cholangioscopy (test_assess.ercp), the primary proposed on ``where``."""
    R = doc.build()
    found = TA.by_code(TA.run(R, (primary, where), ('43273', 3)))
    first, addon = found[primary], found['43273']
    may = EV.may_exclude(primary, first.evidence.kept, TA.dated(R), kept_words=first.evidence.runs)
    return (first.status.value, sorted({held.cause for held in first.held_facts}), may, addon.status.value,
            sorted({held.cause for held in addon.held_facts}))


def _stone_denial(**over):
    """test_assess.ercp(stone=False) with E6, a stone-extraction denial (status negated performed, breadth all_of_kind)
    whose kind and status words lie at 600-660 (test_assess.R2A_CITED); ``over`` replaces E6's facts."""
    doc = TA.ercp(stone=False)
    facts = dict(status=neg(PERFORMED), breadth=sup(Breadth.ALL_OF_KIND), kind_words=Span(600, 630),
                 status_words=Span(630, 660))
    facts.update(over)
    doc.act(6, Kind.STONE_EXTRACTION, **facts)
    return doc


HELD_ADDON = ['coding_rule:ADDON']


class R2FEMayExcludeTermTests(SimpleTestCase):
    """Ported from round r2e's e-engine (R2EEMayExcludeTermTests; DECISIONS D309 keeps it). DECISIONS D303
    (refutation rf-eng-a3 of round r2d's eng-a3, RFA3-1..4): each term by which evaluate.may_exclude
    widens what a statement may be, or by which it or its premise narrows, pinned by an input where the outcome rests on
    that term alone (the add-on 43273 held by ADDON, or READY) beside its twin."""

    def test_rfe_rfa3_1_a_statement_whose_kind_is_not_established_may_be_any_kind_of_its_sessions_family(self):
        """RFA3-1 (medium): 4.2's statement arm in ``_may_be_of`` - E6 a denial whose KIND is unresolved claiming a
        biopsy (or a sphincterotomy), so every ERCP kind (the stone extraction among them) through its session's family
        only, its date unresolved claiming today, by another clinician (it never pairs with the cholangioscopy E3):
        43264 held by 4.6's statement_scope question, may_exclude True, 43273 held by ADDON, cited or not. Its twin, the
        kind ESTABLISHED as a biopsy (which covers no stone extraction): may_exclude False and 43273 READY. Mutant
        MAYBE-OF-NO-FAMILY (only what the kind claims) fails here."""
        for claimed in (Kind.BIOPSY, Kind.SPHINCTEROTOMY):
            for cover, where in (('cited', TA.R2A_CITED), ('not cited', 4)):
                with self.subTest(claimed=claimed.value, cover=cover):
                    doc = TA.ercp(stone=False)
                    doc.event(6, kind_words=Span(600, 630), status_words=Span(630, 660),
                              kind=unres(claimed), status=neg(PERFORMED), breadth=sup(Breadth.ALL_OF_KIND),
                              session=sup(X(1)), date=unres(ON), performer=sup(ct.Performer.OTHER_CLINICIAN),
                              entry=sup(DC))
                    self.assertEqual(_addon(doc, '43264', where),
                                     ('needs_clarification', ['coding_rule:statement_scope'], True,
                                      'needs_clarification', HELD_ADDON))
                    twin = TA.ercp(stone=False)
                    twin.event(6, kind_words=Span(600, 630), status_words=Span(630, 660), kind=sup(claimed),
                               status=neg(PERFORMED), breadth=sup(Breadth.ALL_OF_KIND), session=sup(X(1)),
                               date=unres(ON), performer=sup(ct.Performer.OTHER_CLINICIAN), entry=sup(DC))
                    self.assertEqual(_addon(twin, '43264', where)[2:], (False, 'ready', []))

    def test_rfe_rfa3_2_the_question_term_reads_the_date_and_the_session(self):
        """RFA3-2 (low): 4.6's last paragraph needs possibly today AND possibly this session - a broad stone-extraction
        denial of an ESTABLISHED earlier date (its session unresolved, claiming X1), and one SUPPORTED in an EGD X2 (its
        date unresolved, claiming today), neither cited: 4.6 never asks or excludes, so may_exclude False and 43273 READY
        (mutants Q-TODAY-ANY and Q-SESSION-ANY fail here). Their twin, the same denial possibly today in X1's session
        (date and session unresolved): may_exclude True, 43273 held by ADDON."""
        earlier = _stone_denial(date=sup(EARLIER), session=unres(X(1)))
        self.assertEqual(_addon(earlier, '43264', 4)[2:], (False, 'ready', []))
        egd = _stone_denial(session=sup(X(2)), date=unres(ON))
        egd.session(2, ct.SessionKind.EGD, reached=[sup(ct.Extent.SECOND_PORTION_DUODENUM)])
        egd.exam(8, session=X(2))
        self.assertEqual(_addon(egd, '43264', 4)[2:], (False, 'ready', []))
        twin = _stone_denial(session=unres(X(1)), date=unres(ON))
        self.assertEqual(_addon(twin, '43264', 4)[2:], (True, 'needs_clarification', HELD_ADDON))

    def test_rfe_rfa3_3_the_cited_arm_reads_a_denial(self):
        """RFA3-3 (low): the cited arm's breadth disjunct needs a denial - E5, a stone extraction performed today by the
        team whose KIND is unresolved (claiming it), cited by 43264: under every reading E5 supports 43264 or is no
        statement of its kind, so may_exclude False and 43273 READY (mutant CITED-DENIAL-ANY fails here). Its twin, a
        cited stone-extraction denial whose breadth is unresolved (possibly all of its kind): may_exclude True, 43273
        held by ADDON."""
        doc = TA.ercp(stone=False)
        doc.act(5, unres(Kind.STONE_EXTRACTION), duct=sup(ct.Duct.BILIARY))
        self.assertEqual(_addon(doc, '43264', 5)[2:], (False, 'ready', []))
        twin = _stone_denial(breadth=unres(Breadth.ALL_OF_KIND))
        self.assertEqual(_addon(twin, '43264', TA.R2A_CITED)[2:], (True, 'needs_clarification', HELD_ADDON))

    def test_rfe_rfa3_4_the_premise_reads_a_begun_act_as_surely_positive(self):
        """RFA3-4 (low): an act ATTEMPTED today by the team is a positive candidate under every reading (4.4: possibly
        attempted_not_completed) - E5, a stone extraction attempted (established), and E6 a placed single-target denial
        of it, both cited by 43264: may_exclude False and 43273 READY (mutant PREMISE-PERFORMED-ONLY fails here). Its
        twin, E5's status unresolved: may_exclude True, 43273 held by ADDON."""
        doc = _stone_denial(breadth=sup(Breadth.SINGLE_TARGET))
        doc.act(5, Kind.STONE_EXTRACTION, duct=sup(ct.Duct.BILIARY), status=sup(ATTEMPTED))
        self.assertEqual(_addon(doc, '43264', TA.R2A_CITED)[2:], (False, 'ready', []))
        twin = _stone_denial(breadth=sup(Breadth.SINGLE_TARGET))
        twin.act(5, Kind.STONE_EXTRACTION, duct=sup(ct.Duct.BILIARY), status=unres(ATTEMPTED))
        self.assertEqual(_addon(twin, '43264', TA.R2A_CITED)[2:], (True, 'needs_clarification', HELD_ADDON))


# --- D303 RF3-1/2 (pairing.ADMITS: "a device of another kind" and "a catheter") ----------------------------------------


def egd_bleeding(act_device, denial_device, kind=Kind.BLEEDING_CONTROL, place=Landmark.DUODENAL_BULB, code='43255'):
    """rf-eng-b3's p02 scene: an EGD (EF.egd) with E2, a bleeding control of the bulb ulcer (or ``kind`` at ``place``)
    done with ``act_device``, its cause a lesion present before the session and its purpose hemostasis, beside E3, an
    all-of-kind denial of its kind naming ``denial_device`` - every fact established. (the technique row, the code's
    status)."""
    doc = EF.egd()
    extra = dict(cause=sup(ct.Cause.PRE_EXISTING_LESION), purpose=sup(ct.Purpose.HEMOSTASIS)) \
        if kind is Kind.BLEEDING_CONTROL else {}
    doc.act(2, kind, places=[sup(place)], device=sup(act_device), **extra)
    doc.event(3, kind=sup(kind), status=neg(PERFORMED), session=sup(X(1)), date=sup(ON),
              breadth=sup(Breadth.ALL_OF_KIND), device=sup(denial_device))
    R = doc.build()
    return P.row(R, P.Row.TECHNIQUE, E(3), E(2)), code_of(R, code, 2)[0]


def ercp_device(kind, act_device, denial_device, code):
    """rf-eng-b3's p05 scene: an ERCP X1 (E1) with an achieved biliary cannulation E4; E2 the act of ``kind`` with
    ``act_device`` in the bile duct; E3 an all-of-kind denial of its kind naming ``denial_device`` - every fact
    established. (the technique row, the code's status)."""
    doc = EF.Doc()
    doc.session(1, ct.SessionKind.ERCP)
    doc.exam(1)
    doc.act(2, kind, device=sup(act_device), duct=sup(ct.Duct.BILIARY), places=[sup(Landmark.COMMON_BILE_DUCT)])
    doc.event(3, kind=sup(kind), status=neg(PERFORMED), session=sup(X(1)), date=sup(ON),
              breadth=sup(Breadth.ALL_OF_KIND), device=sup(denial_device))
    doc.act(4, Kind.CANNULATION, duct=sup(ct.Duct.BILIARY), access=sup(ct.AccessOutcome.ACHIEVED))
    R = doc.build()
    return P.row(R, P.Row.TECHNIQUE, E(3), E(2)), code_of(R, code, 2)[0]


class R2FEDeviceTests(SimpleTestCase):
    """Ported from round r2e's e-engine (R2EEDeviceTests; DECISIONS D309 keeps it). DECISIONS D303 (refutation
    rf-eng-b3 of round r2d's eng-b3): RF3-1 and RF3-2, each a class rule over ADMITS."""

    def test_rfe_rf3_1_a_device_of_another_kind_admits_no_instrument_a_listed_members_row_names(self):
        """RF3-1: the needle-type knife (a needle's row), the water-jet knife used to inject (an injection device's) and
        the cryoablation balloon (cryotherapy's) are never "a device of another kind" - so an all-of-kind denial naming
        "a device of another kind" ("No hemostatic powder was used.") beside an injection, a needle or a cryotherapy
        ablation is INDEPENDENT on technique and the code READY (held on technique before round r2e)."""
        for instrument in (P.Instrument.NEEDLE_TYPE_KNIFE, P.Instrument.WATER_JET_KNIFE,
                           P.Instrument.CRYOABLATION_BALLOON):
            self.assertNotIn(instrument, P.ADMITS[Device.OTHER])
        for device in (Device.NEEDLE, Device.INJECTION, Device.CRYOTHERAPY):
            with self.subTest(device=device.value):
                self.assertNotIn(Device.OTHER, P.DEVICE_MAY_BE[device])
        for device in (Device.INJECTION, Device.NEEDLE):
            with self.subTest(act=device.value):
                self.assertEqual(egd_bleeding(device, Device.OTHER), (P.RowResult.INDEPENDENT, 'ready'))
        self.assertEqual(egd_bleeding(Device.CRYOTHERAPY, Device.OTHER, Kind.ABLATION, Landmark.DISTAL_ESOPHAGUS,
                                      '43270'), (P.RowResult.INDEPENDENT, 'ready'))

    def test_rfe_rf3_1_its_boundary_carrier_and_energy_pairs_stay(self):
        """The boundary RF3-1 leaves alone: "a device of another kind" stays possibly a catheter (a powder applicator on
        its catheter) and possibly electrocautery or radiofrequency energy (an electrosurgical knife) - UNRESOLVED; a
        clip beside it stays INDEPENDENT."""
        for device in (Device.CATHETER, Device.ELECTROCAUTERY, Device.RADIOFREQUENCY):
            with self.subTest(device=device.value):
                self.assertIn(Device.OTHER, P.DEVICE_MAY_BE[device])
        self.assertEqual(egd_bleeding(Device.CATHETER, Device.OTHER)[0], P.RowResult.UNRESOLVED)
        self.assertEqual(egd_bleeding(Device.CLIP, Device.OTHER), (P.RowResult.INDEPENDENT, 'ready'))

    def test_rfe_rf3_2_a_catheter_admits_the_forceps_and_snare_a_cholangioscope_delivers(self):
        """RF3-2: "a catheter" admits every device delivered through a device the module reads as a catheter - the
        single-operator cholangioscope's cold forceps and retrieval snare as well as its fibre and basket - so a biopsy
        with cold forceps (or forceps) beside an all-of-kind denial naming a catheter, and the reverse, are UNRESOLVED on
        technique and 43261 held (READY before round r2e), as the lithotripter and the basket already were."""
        for device in (Device.FORCEPS, Device.COLD_FORCEPS, Device.SNARE, Device.COLD_SNARE):
            with self.subTest(device=device.value):
                self.assertIn(device, P.DEVICE_MAY_BE[Device.CATHETER])
        for act_device, denial_device in ((Device.COLD_FORCEPS, Device.CATHETER), (Device.CATHETER, Device.COLD_FORCEPS),
                                          (Device.FORCEPS, Device.CATHETER)):
            with self.subTest(act=act_device.value, denial=denial_device.value):
                self.assertEqual(ercp_device(Kind.BIOPSY, act_device, denial_device, '43261'),
                                 (P.RowResult.UNRESOLVED, 'needs_clarification'))
        self.assertEqual(ercp_device(Kind.STONE_EXTRACTION, Device.BASKET, Device.CATHETER, '43264')[0],
                         P.RowResult.UNRESOLVED)

    def test_rfe_rf3_2_its_boundary_a_device_used_with_current_or_a_denial_of_another_device(self):
        """The boundary RF3-2 leaves alone: a hot snare and hot forceps carry current and are no device a cholangioscope
        delivers - apart from "a catheter"; a cold-forceps biopsy beside a denial naming a basket stays INDEPENDENT and
        43261 READY."""
        for device in (Device.HOT_SNARE, Device.HOT_FORCEPS):
            with self.subTest(device=device.value):
                self.assertNotIn(device, P.DEVICE_MAY_BE[Device.CATHETER])
        self.assertEqual(ercp_device(Kind.BIOPSY, Device.COLD_FORCEPS, Device.BASKET, '43261'),
                         (P.RowResult.INDEPENDENT, 'ready'))


# --- D309 e-engine's Q4: a claimed pair of an event that MAY be a statement (round 2's Q4, the which-pairs corner) -----


N1 = Id(IdFamily.SECTION, 1)  # a section an inherited fact names (the FactSet need not hold it: inherited_from is read)
CLAIMED = 'relation:unresolved'  # a claimed pair's cause (4.5 step 1: never INDEPENDENT)
Q4_CODES = (('45385', 2), ('45378', 1))


def q4_scene(status=None, *, kind='plan', date=None, performer=None, covers=(E(2),)):
    """EF.colonoscopy() - X1 to the cecum (its examination E1) and the cold snare removal E2 of L1 in the sigmoid colon
    (45385) - beside E3, an event whose STATUS IS ESTABLISHED (``status``, supported planned by default), its date
    relation ``date`` (supported later_date by default) and performer ``performer`` (supported documenting_team), in the
    documenting clinician's entry, its scope.covers naming ``covers`` (each member claimed, not established: covers is
    UNCONTROLLED, 3.2.3). ``kind`` 'plan': e-engine's p4plan_mono scene - a surveillance examination in a second
    colonoscopy X2, its kind and session qualified planned_only by pass 2 (as pair 4's plan was); 'snare': a cold snare
    removal of L3 in the sigmoid colon in X1; 'biopsy': a cold-forceps biopsy of the rectum in X1. Dated once
    (test_assess.dated: the P-MONO harness never re-dates a FactSet)."""
    doc = EF.colonoscopy()
    facts = dict(status=status if status is not None else sup(PLANNED), date=date if date is not None else sup(LATER),
                 performer=performer if performer is not None else sup(TEAM), entry=sup(DC),
                 covers=[unres(target) for target in covers] if covers else None)
    if kind == 'plan':
        doc.session(2, ct.SessionKind.COLONOSCOPY)
        doc.event(3, kind=unres(Kind.EXAMINATION, Rs.APPRAISAL_QUALIFIED_PLANNED_ONLY),
                  session=unres(X(2), Rs.APPRAISAL_QUALIFIED_PLANNED_ONLY), **facts)
    elif kind == 'snare':
        doc.lesion(3, lesion_places=[sup(Landmark.SIGMOID_COLON)])
        doc.event(3, kind=sup(Kind.SNARE), session=sup(X(1)), places=[sup(Landmark.SIGMOID_COLON)], lesion=sup(L(3)),
                  device=sup(Device.COLD_SNARE), **facts)
    else:
        doc.event(3, kind=sup(Kind.BIOPSY), session=sup(X(1)), places=[sup(Landmark.RECTUM)],
                  device=sup(Device.COLD_FORCEPS), **facts)
    return TA.dated(doc.build())


def corner_weakenings(R, attributes=(A.DATE_RELATION, A.PERFORMER)):
    """Every 9.4 weakening tests/v2/test_properties.weakenings makes of E3's date relation and performer (the corner's
    two facts) - to unresolved, a stated, an unclear and a conflict doubt, and AMENDMENT-2 4.4's value-erasing
    contradictions (pass 1's own contradiction, the two overfilled views): (label, the weakened FactSet, what)."""
    return [(label, changed, what) for label, changed, what in TP.weakenings(R)
            if isinstance(what, tuple) and len(what) == 4 and what[0] == E(3) and what[1] in attributes]


def status_of(R, code='45385', codes=Q4_CODES) -> tuple:
    """``code``'s (status, its held facts' causes, sorted and each once) over ``R`` as given (test_properties.assessed:
    its date of service read from ``R``)."""
    found = {item.code: item for item in TP.assessed(R, codes).codes}[code]
    return found.status.value, sorted({held.cause for held in found.held_facts})


DQ2_CODES = (('45380', 3), ('45378', 1))


def dq2_scene(*, covers=False):
    """D228's DQ2 corner as tests/v2/test_properties builds it (inherited_other_clinician_beside_a_biopsy, its pair
    controls from claims, dated once), E2's covers naming E3 when ``covers``: (the FactSet, its one weakening of E2's
    inherited performer to unresolved, that weakening's label and what)."""
    R = TA.dated(TP.paired(TP.inherited_other_clinician_beside_a_biopsy()))
    if covers:
        R = replace(R, events={**R.events, E(2): {**R.events[E(2)], A.SCOPE_COVERS: (unres(E(3)),)}})
    found = [(weak, label, what) for label, weak, what in TP.weakenings(R)
             if label == f'unresolved {E(2)} {A.PERFORMER.value}[0]']
    assert len(found) == 1, found
    weak, label, what = found[0]
    return R, weak, label, what


class R2FEWhichPairsClaimedTests(SimpleTestCase):
    """DECISIONS D309 e-engine's Q4 (round 2's Q4, the which-pairs corner D228 keeps as built): reproduced on int2 - an
    event whose status is established is a statement only by an established other date or performer, so 9.4's weakening
    of that one fact took it out of 4.5's which pairs and released every pair it held, a claimed one included (45385
    READY under each weakening, e-engine's probe/p4plan_mono.out and this lane's probe/R2FE_q4_mono-base.out) - and
    fixed as a class rule in the reader that released (engine/pairing.paired's claimed arm, ``possibly_statement``):
    D's covers naming A is read whenever D MAY be a statement."""

    # (name, q4_scene's arguments, the attribute whose established value makes E3 a statement): every deciding value
    # 4.5 names - an earlier and a later date, the date of service denied, another clinician, another facility, the
    # documenting team denied - own and inherited, on a plan, a done act and a begun act
    MUST = (
        ('an established plan of a later date (e-engine p4plan_mono)', {}, A.DATE_RELATION),
        ('a snare removal done on an earlier date', dict(status=sup(PERFORMED), kind='snare', date=sup(EARLIER)),
         A.DATE_RELATION),
        ('a snare removal whose date of service is denied', dict(status=sup(PERFORMED), kind='snare', date=neg(ON)),
         A.DATE_RELATION),
        ('a plan of a later date inherited from a section', dict(date=sup(LATER, inherited_from=N1)),
         A.DATE_RELATION),
        ('a snare removal begun by another clinician', dict(status=sup(ATTEMPTED), kind='snare', date=sup(ON),
                                                           performer=sup(OTHER)), A.PERFORMER),
        ('a snare removal whose documenting team is denied', dict(status=sup(PERFORMED), kind='snare', date=sup(ON),
                                                                  performer=neg(TEAM)), A.PERFORMER),
        ('a snare removal at another facility, inherited', dict(status=sup(PERFORMED), kind='snare', date=sup(ON),
                                                                performer=sup(FACILITY, inherited_from=N1)),
         A.PERFORMER),
    )

    def test_rfe_q4_no_weakening_of_what_made_it_a_statement_drops_its_claimed_pair(self):
        """MUST CHANGE (READY on int2 under every weakening): each scene's E3 is a statement by its established deciding
        fact and its covers names today's removal E2 - a claimed pair, so 45385 is held (relation:unresolved). Every 9.4
        weakening of that fact (unresolved, a stated, an unclear and a conflict doubt, and each value-erasing
        contradiction that applies) takes E3 out of 4.5's which pairs as before, and the claimed pair stays: paired,
        claimed, never INDEPENDENT, 45385 held with the pair's cause."""
        for name, over, attribute in self.MUST:
            R = q4_scene(**over)
            with self.subTest(scene=name, weakening='none'):
                self.assertTrue(P.is_statement(R, E(3)))
                self.assertTrue(P.paired(R, E(3), E(2)) and P.relation(R, E(3), E(2)).claimed)
                status, causes = status_of(R)
                self.assertEqual(status, 'needs_clarification')
                self.assertIn(CLAIMED, causes)
            weakened = corner_weakenings(R, (attribute,))
            self.assertGreaterEqual(len(weakened), 5, name)
            for label, weak, _what in weakened:
                with self.subTest(scene=name, weakening=label):
                    status, causes = status_of(weak)
                    self.assertEqual(status, 'needs_clarification')
                    self.assertIn(CLAIMED, causes)
                    self.assertTrue(P.paired(weak, E(3), E(2)))
                    pair = P.relation(weak, E(3), E(2))
                    self.assertTrue(pair.claimed)
                    self.assertIsNot(pair.relation, P.Relation.INDEPENDENT)
                    self.assertFalse(P.is_statement(weak, E(3)))  # out of which pairs: the claimed arm keeps the pair
                    self.assertTrue(P.possibly_statement(weak, E(3)))

    def test_rfe_q4_a_date_or_performer_pass_2_left_unresolved_keeps_the_claimed_pair(self):
        """MUST CHANGE (READY on int2): the same claims as pass 2 leaves them, never established - the plan's later date
        unresolved under pass 1's conditional qualifier (as pair 4's plan's date was), a snare's earlier date in doubt
        with a later reading, a snare's other clinician qualified - each held by its claimed pair."""
        for name, over in (
                ('a plan whose later date is qualified', dict(date=unres(LATER, Rs.QUALIFIED_CONDITIONAL))),
                ('a snare whose earlier date is in doubt', dict(status=sup(PERFORMED), kind='snare',
                                                                date=EF.doubted(EARLIER, LATER))),
                ('a snare whose other clinician is qualified', dict(status=sup(PERFORMED), kind='snare', date=sup(ON),
                                                                    performer=unres(OTHER, Rs.APPRAISAL_QUALIFIED)))):
            R = q4_scene(**over)
            with self.subTest(scene=name):
                status, causes = status_of(R)
                self.assertEqual(status, 'needs_clarification')
                self.assertIn(CLAIMED, causes)
                self.assertTrue(P.paired(R, E(3), E(2)) and P.relation(R, E(3), E(2)).claimed)
                self.assertFalse(P.is_statement(R, E(3)))
                self.assertTrue(P.possibly_statement(R, E(3)))

    def test_rfe_q4_an_unclaimed_pair_is_left_as_it_was(self):
        """BOUNDARY (as on int2): the plan of a later date with no covers - its pair with E2 INDEPENDENT on the timing
        row, 45385 READY; every weakening of its date takes it out of which pairs (no pair is formed for an unclaimed
        act), 45385 READY still. The class rule reads covers only: no new unclaimed pair, so no new hold."""
        R = q4_scene(covers=())
        self.assertIs(P.relation(R, E(3), E(2)).relation, P.Relation.INDEPENDENT)
        self.assertEqual(status_of(R), ('ready', []))
        weakened = corner_weakenings(R, (A.DATE_RELATION,))
        self.assertGreaterEqual(len(weakened), 5)
        for label, weak, _what in weakened:
            with self.subTest(weakening=label):
                self.assertFalse(P.paired(weak, E(3), E(2)))
                self.assertEqual(status_of(weak), ('ready', []))

    def test_rfe_q4_silence_claims_no_other_date_or_performer(self):
        """BOUNDARY (as on int2): a silent date relation or performer claims nothing - a plan whose date relation is
        silent, today's snare whose performer is silent, each naming E2 in its covers: no pair, 45385 READY."""
        for name, over in (('a plan whose date relation is silent', dict(date=F.SILENT)),
                           ("today's snare whose performer is silent", dict(status=sup(PERFORMED), kind='snare',
                                                                            date=sup(ON), performer=F.SILENT))):
            R = q4_scene(**over)
            with self.subTest(scene=name):
                self.assertFalse(P.paired(R, E(3), E(2)))
                self.assertEqual(status_of(R), ('ready', []))

    def test_rfe_q4_todays_team_act_naming_another_pairs_with_nothing(self):
        """BOUNDARY (as on int2): an event of today by the team is no statement of another date or performer - a snare
        done today by the team, its date established, or unresolved claiming today alone, its covers naming E2: no
        pair; 45385 READY."""
        for name, date in (('its date established today', sup(ON)), ('its date unresolved, claiming today', unres(ON))):
            R = q4_scene(status=sup(PERFORMED), kind='snare', date=date)
            with self.subTest(scene=name):
                self.assertFalse(P.paired(R, E(3), E(2)))
                self.assertEqual(status_of(R), ('ready', []))

    def test_rfe_q4_d228s_dq2_corner_is_left_as_built(self):
        """BOUNDARY (as on int2): D228's DQ2 corner - tests/v2/test_properties' inherited_other_clinician_beside_a_biopsy,
        another clinician's biopsy E2 (its performer inherited from a section, which the performer row reads as naming
        none: D188) beside the team's biopsy E3, an UNCLAIMED pair that holds 45380 - weakening the inherited performer
        to unresolved still takes E2 out of which pairs and releases 45380, named D228_DQ2 (held to D264's every-row
        rule): the class rule forms no unclaimed pair."""
        R, weak, label, what = dq2_scene()
        self.assertEqual(status_of(R, '45380', DQ2_CODES)[0], 'needs_clarification')
        self.assertEqual(status_of(weak, '45380', DQ2_CODES), ('ready', []))
        self.assertEqual(TP._named(label, what, '45380', R), TP.D228_DQ2)
        self.assertFalse(P.paired(weak, E(2), E(3)))

    def test_rfe_q4_dq2s_claimed_twin_keeps_its_pair(self):
        """MUST CHANGE (READY on int2): DQ2's scene with E2's covers naming the team's biopsy E3 - a claimed pair: after
        the same weakening of the inherited performer 45380 is held by it, never released."""
        R, weak, _label, _what = dq2_scene(covers=True)
        self.assertEqual(status_of(R, '45380', DQ2_CODES)[0], 'needs_clarification')
        status, causes = status_of(weak, '45380', DQ2_CODES)
        self.assertEqual(status, 'needs_clarification')
        self.assertIn(CLAIMED, causes)
        self.assertTrue(P.paired(weak, E(2), E(3)) and P.relation(weak, E(2), E(3)).claimed)

    def test_rfe_q4_the_possibility_readers(self):
        """pairing.possibly_other_date, possibly_other_performer and possibly_statement: True for every MUST scene and
        every weakening of its deciding fact (each keeps the claimed other value, a side naming it, or an open denial),
        and for the claims pass 2 left unresolved; False for silence (a silent slot claims nothing) and for today's
        team act (its date established, or claiming today alone); is_statement is unchanged (its arms established)."""
        for name, over, attribute in self.MUST:
            R = q4_scene(**over)
            reader = P.possibly_other_date if attribute is A.DATE_RELATION else P.possibly_other_performer
            for label, weak, _what in [('none', R, None)] + corner_weakenings(R, (attribute,)):
                with self.subTest(scene=name, weakening=label):
                    self.assertTrue(reader(weak, E(3)))
                    self.assertTrue(P.possibly_statement(weak, E(3)))
                    self.assertEqual(P.is_statement(weak, E(3)), label == 'none')
        for name, over, expected in (
                ('a plan whose date relation is silent', dict(date=F.SILENT), False),
                ("today's snare whose performer is silent", dict(status=sup(PERFORMED), kind='snare', date=sup(ON),
                                                                 performer=F.SILENT), False),
                ("today's snare by the team", dict(status=sup(PERFORMED), kind='snare', date=sup(ON)), False),
                ("today's snare, its date unresolved claiming today", dict(status=sup(PERFORMED), kind='snare',
                                                                          date=unres(ON)), False),
                ('a plan whose later date is qualified', dict(date=unres(LATER, Rs.QUALIFIED_CONDITIONAL)), True),
                ('a snare whose date of service is denied, unresolved', dict(
                    status=sup(PERFORMED), kind='snare', date=EF.fact(ct.Result.UNRESOLVED, ON, ct.FactState.NEGATED,
                                                                      reasons=(Rs.APPRAISAL_UNCLEAR,))), True)):
            R = q4_scene(**over)
            with self.subTest(scene=name):
                self.assertEqual(P.possibly_statement(R, E(3)), expected)
                self.assertFalse(P.is_statement(R, E(3)))


# The generated family: every deciding value 4.5 names, own and inherited; a plan, a done and a begun act; covers naming
# today's removal, naming today's examination, or nothing
DECIDING = {
    'own earlier date': dict(date=sup(EARLIER)),
    'own later date': dict(date=sup(LATER)),
    'own date of service denied': dict(date=neg(ON)),
    'inherited later date': dict(date=sup(LATER, inherited_from=N1)),
    'own other clinician': dict(date=sup(ON), performer=sup(OTHER)),
    'own other facility': dict(date=sup(ON), performer=sup(FACILITY)),
    'own documenting team denied': dict(date=sup(ON), performer=neg(TEAM)),
    'inherited other clinician': dict(date=sup(ON), performer=sup(OTHER, inherited_from=N1)),
}
STATUSES = {'planned': sup(PLANNED), 'performed': sup(PERFORMED), 'begun': sup(ATTEMPTED)}
COVERS = {"today's removal": (E(2),), "today's examination": (E(1),), 'nothing': ()}


@st.composite
def corner_scenes(draw):
    """(name, the dated FactSet, the proposals): q4_scene over the generated family; 45380 is proposed on a biopsy
    E3."""
    status = draw(st.sampled_from(sorted(STATUSES)))
    kind = draw(st.sampled_from(('plan', 'snare', 'biopsy')))
    deciding = draw(st.sampled_from(sorted(DECIDING)))
    covers = draw(st.sampled_from(sorted(COVERS)))
    R = q4_scene(STATUSES[status], kind=kind, covers=COVERS[covers], **DECIDING[deciding])
    codes = Q4_CODES + ((('45380', 3),) if kind == 'biopsy' else ())
    return f'{status} {kind}, {deciding}, covers {covers}', R, codes


class R2FEWhichPairsMonotoneTests(SimpleTestCase):
    """DECISIONS D309 e-engine's Q4: P-MONO (FINAL-V2 9.4) over the which-pairs corner, by test_properties' own
    check."""

    @hypothesis.settings(**TP.SETTINGS)
    @hypothesis.given(corner_scenes())
    def test_rfe_q4_p_mono_no_weakening_of_the_corner_releases_but_d228s_dq2(self, scene):
        """For a generated scene (an event of established status whose established date relation or performer - own or
        inherited, every deciding value 4.5 names - makes it a statement, its covers naming today's removal, today's
        examination or nothing) and every 9.4 weakening of that event's date relation and performer: no code newly
        READY or EXCLUDED and no claim shrunk but as a ruling names it (tests/v2/test_properties.PMonoTests.check: the
        named releases - here D228's DQ2, an inherited other date or performer, held to D264's every-row rule), and
        every claimed pair the event held is held still (pairing.paired, never INDEPENDENT). Red on int2: an own
        deciding fact's claimed pair released under its weakening, which no ruling names."""
        name, R, codes = scene
        base = TP.assessed(R, codes)
        claimed = [act for act in R.events if P.paired(R, E(3), act) and P.relation(R, E(3), act).claimed]
        for label, weak, what in corner_weakenings(R):
            after = TP.assessed(weak, codes)
            TP.PMonoTests.check(self, base, after, label, what, R)
            for act in claimed:
                self.assertTrue(P.paired(weak, E(3), act), (name, label, act))
                self.assertIsNot(P.relation(weak, E(3), act).relation, P.Relation.INDEPENDENT, (name, label, act))

    def test_rfe_q4_every_item_of_the_corner_is_worded(self):
        """P-WORDED (DECISIONS D246) over the must-change scenes and every weakening of their deciding fact: the
        renderer (studio/jobs.word_item) words every item the engine makes, a claimed pair of a possible statement of
        another date or performer among them, and read time agrees on every TEXT_FREE item (test_properties.findings)."""
        scenes = []
        for name, over, attribute in R2FEWhichPairsClaimedTests.MUST:
            R = q4_scene(**over)
            scenes.append(TP.Scene('r2fe', name, R, TA.TEXT, TP.assessed(R, Q4_CODES)))
            for label, weak, _what in corner_weakenings(R, (attribute,)):
                scenes.append(TP.Scene('r2fe', f'{name}: {label}', weak, TA.TEXT, TP.assessed(weak, Q4_CODES)))
        self.assertGreater(sum(1 for scene in scenes for found in scene.assessment.codes if found.item is not None), 40)
        self.assertEqual(TP.findings(scenes), {})
