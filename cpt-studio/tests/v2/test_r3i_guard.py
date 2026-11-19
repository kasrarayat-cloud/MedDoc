"""Round r3's round 6 (DECISIONS D336 (1); build-v2/a2b/r3b/r3i/int8/NOTES.md): THE LOWER-GI PATH GUARD'S CONSTRUCTION
RULE (D330 (1)), COMPLETED IN THE RELEASE DIRECTION. TEXT-ONLY and SYNTHETIC: every note is written for these tests or is
the fourth adversarial pass's or the final check's constructed input word for word (r3h/attack: test_l4p_refute.py,
test_l6_oracle.py and the verifiers' scripts; r3h/final-check: test_fc_findings.py; fictional clinicians), every pass-1
answer is built by hand with test_settle's builders and every pass-2 answer by test_r2cl_lesion's faithful oracle (or
that oracle with the claims a finding names contradicted, as an honest reader would), every other FactSet in code;
nothing is sent.

The rule (D336 (1)): an anatomy entry is harmless for a route family only if EVERY reading it may have lies within a row
of the ruled harmless set (catalogue.HARMLESS), where
- (a) no early return: the guard reads every entry whatever the session's approach, but for an established FAILURE of
  the code's own row or class on the established approach (evaluate.path_guard, _accepted_approaches);
- (b) every attribute is read by its widest possible value unless the contract CONTROLS it: a row releases on ONE
  controlled claim (a type of catalogue.CONTROLLED_TYPES, the organ claim of an entry filed surgically absent, a subtype
  of catalogue.CONTROLLED_SUBTYPES); joins and every uncontrolled type are read only to HOLD; a claim pass 2 rejected
  with no control is fully open (evaluate.rejected_open); an empty or one-member joins list of an entry that may be an
  anastomosis names its other ends as every landmark, or as its subtype's own ends (evaluate.release_reading,
  harmless_row, joins_ileum_below_colon_possible); the per-anus approach, which the contract gives no control, is never
  established (evaluate._anus_route_contradicted);
- (c) P-MONO for every hold clause: R5R-9's reach and organ clauses read every value a member may be
  (evaluate.ileal_stoma_contradicted);
- (d) P-CONTROLLED honest: every attribute a READY path reads is declared on it (requirements.RULES: the route rows'
  subtype read moves to READY; joins and the reach stay hold-only), the partition passes with it;
- (e) a contradictory filing is read at its widest: a subtype beside another type, an upper-tract type at a lower-GI
  organ, a join a subtype cannot make, a colonoscopy through a stoma filed outside the lower tract
  (evaluate.release_reading, subtype_ends_contradicted, colonic_route_stoma_contradicted);
- (f) the censuses: every route family x every approach and through state x every attribute state x the widest values
  (StateCensusTests, with its completeness test), 9.4's weakening lattice over every route-table family
  (PMonoCensusTests), every harmless row's reads against the contract's CONTROLS (ControlledCensusTests).

- FindingTests: every confirmed release finding of the fourth pass (L4P-1 to L4P-5) and every finding of the final check
  (1 to 5), each on its own input: RED on int7 (fe6ba4eb; r3i/int8/red/), GREEN on int8.
- ContradictoryFilingTests: the oracle lens's contradictory filings (L6O-2 to L6O-5), D336 (1) (e).
- DevelopmentFilingTests: the development set's own filings and the common controls stay as int7 decides them, each READY
  resting on a controlled reading (an ileocolic subtype decides its ends; filed joins only add holds).
- Int7MonotoneTests: int8 only adds holds to int7's declared release set and per-anus reading (int7's oracle, frozen).
- SurvivorPinTests: the rules the first int8's mutation proof left unpinned (r6.G10, r6.G20; r4.S2, r4.S3, r4.S5), each
  on its input.
"""
from __future__ import annotations

import itertools
from dataclasses import replace

from django.test import SimpleTestCase

from studio.interpretation.contract import types as ct
from studio.interpretation.engine import catalogue, evaluate
from studio.interpretation.engine.types import Id
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_r2cl_lesion as R2CL
from tests.v2 import test_r3c_rules as RR
from tests.v2 import test_r3f_rules as R3F
from tests.v2 import test_r3g_rules as G
from tests.v2.test_settle import answer, event, fact, faithful, frame, labelled, opening, session, src, verdict

A, LM, EX, AT, AP, SUB, SK, Kind = (ct.Attribute, ct.Landmark, ct.Extent, ct.AnatomyType, ct.Approach,
                                    ct.AnastomosisSubtype, ct.SessionKind, ct.Kind)
sup, unres, neg, doubted, contra = EF.sup, EF.unres, EF.neg, EF.doubted, EF.contra
UN = ct.Reason.UNAPPRAISED
X1, E2 = Id.parse('X1'), Id.parse('E2')
Y1, Y2, Y3, Y5, Y7 = (Id.parse(f'Y{n}') for n in (1, 2, 3, 5, 7))
HELD, READY, ROUTE = G.HELD, G.READY, G.ROUTE
entry_of = R3F.entry_of


def claimed(value):
    """A claim pass 1 made that pass 2 was never asked (3.3 row 6: unappraised, its claimed value kept)."""
    return unres(value, UN)


def rejected(value):
    """A claim pass 2 contradicted with no control left, as settle writes an uncontrolled one (settle.appraise:
    CONTRADICTED; 3.3 row 9: unresolved, appraisal_contradicts, no option)."""
    return unres(value, ct.Reason.APPRAISAL_CONTRADICTS)


def absent(organ):
    return entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=organ if isinstance(organ, EF.Fact) else sup(organ))


def anastomosis(*joins, subtype=None, organ=None, typ=None):
    return entry_of(type=typ if typ is not None else sup(AT.ANASTOMOSIS),
                    subtype=subtype if isinstance(subtype, EF.Fact) or subtype is None else sup(subtype),
                    organ=organ, joins=tuple(j if isinstance(j, EF.Fact) else sup(j) for j in joins))


def assessed(R, code, number=2) -> tuple:
    return G.assessed(R, str(code), number)


def held_by_route(test, found, label=''):
    test.assertEqual(found[0], HELD, label)
    test.assertIn(ROUTE, found[1], label)


def pouch_scene(approach, extra):
    """test_l4p_refute.pouch_scene, word for word: a pouchoscopy X1 through the ileal pouch Y1 (its through supported),
    approach ``approach``, a cold-forceps biopsy of the pouch, and ``extra`` anatomy entries."""
    doc = EF.Doc()
    doc.session(1, SK.ENTEROSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER), reached=[sup(EX.POUCH)],
                approach=sup(approach), through=sup(Y1))
    doc.anatomy[Y1] = entry_of(type=sup(AT.ILEAL_POUCH))
    doc.exam(1)
    doc.act(2, Kind.BIOPSY, places=[sup(LM.POUCH)], device=sup(ct.Device.COLD_FORCEPS))
    doc.anatomy.update(extra)
    return doc.build()


# The pouch family's shapes the guard holds beside the pouch route (rules6 Q13, int7 NOTES section 10 Q5; the final
# check's finding 1 and L4P-1's verifier): each must hold whatever approach the pouch class accepts
BESIDE_POUCH = {
    'a second ileal pouch': {Y7: entry_of(type=sup(AT.ILEAL_POUCH))},
    'a colorectal anastomosis [colon, rectum]': {Y7: anastomosis(LM.COLON, LM.RECTUM, subtype=SUB.COLORECTAL)},
    'the anal canal surgically absent': {Y7: absent(LM.ANAL_CANAL)},
    'an anastomosis whose subtype and joins are silent': {Y7: entry_of(type=sup(AT.ANASTOMOSIS))},
    'an unreadable entry (type silent, organ claimed other)': {Y7: entry_of(organ=claimed(LM.OTHER))},
    'a colon-keeping anastomosis (ileocolic claimed)': {Y7: entry_of(type=sup(AT.ANASTOMOSIS),
                                                                     subtype=claimed(SUB.ILEOCOLIC))},
    'a coloanal anastomosis [colon, anal canal]': {Y7: anastomosis(LM.COLON, LM.ANAL_CANAL, subtype=SUB.COLOANAL)},
}

HEAD = ('SYNTHETIC LOWER ENDOSCOPY REPORT\n'                   # S1
        'Date of service: 03/14/2031\n'                         # S2
        'Endoscopist: Corvin Ashdale, MD (fictional)\n'         # S3
        '\n')


def reached_note(history, findings, act, *, subtypes, joins, words, reached, reached_anatomy_words, place,
                 place_words):
    """The L4P-5 verifier's v3_e2e_claimed.note, word for word: a per-anus colonoscopy X1 whose reached_anatomy names
    the anastomosis Y1 (so pass 2 is asked its type, subtype and joins), its examination E1 and a cold-forceps biopsy E2."""
    text = HEAD + f'History: {history}\n' + f'Findings: {findings}\n' + f'{act}\n'
    entries = [{'id': 'Y1', 'type': fact('anastomosis', src(['S4'], words)), 'organ': [],
                'subtype': [fact(value, src(['S4'], words)) for value in subtypes],
                'joins': [fact(value, src(['S4'], words)) for value in joins]}]
    sess = session('X1', fact('colonoscopy', src(['S5'], 'colonoscope')),
                   examination=[fact('E1', src(['S5']))], encounter=[fact('this_encounter', frame(['S2']))],
                   approach=[fact('transanal', src(['S5'], 'inserted per anus'))],
                   reached=[fact(value, src(['S5'], w)) for value, w in reached],
                   reached_anatomy=[fact('Y1', src(['S5'], reached_anatomy_words))])
    events = [event('E1', ['S5'], 'colonoscope', 'was inserted', 'examination', session=[fact('X1', src(['S5']))]),
              event('E2', ['S6'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S6']))],
                    target__places=[fact(place, src(['S6'], place_words))],
                    technique__device=[fact('cold_forceps', src(['S6'], 'cold forceps'))])]
    data = answer(
        sections=[opening(), labelled('N1', 'S4', 'History:', 'history'), labelled('N2', 'S5', 'Findings:', 'findings')],
        sessions=[sess], anatomy=entries, events=events)
    return text, data


def contradicting(values):
    """The faithful pass 2 with every joins claim of a value in ``values`` contradicted (the L4P-5 verifier's honest
    reader: an uncontrolled claim, so settle leaves it unresolved with no option)."""
    def answer_(claim, role, claim_set):
        if claim.template == 'anatomy.joins' and role == 'claim' and claim.value in values:
            return verdict(claim, 'contradicts')
        return faithful(claim, role, claim_set)
    return answer_


O_BX = 'Two biopsies of the transverse colon were taken with cold forceps.'
O_PER_ANUS = 'The colonoscope was inserted per anus and advanced to the cecum.'


def o_entry(yid, typ, words, organ=None, subtype=None, joins=()):
    """test_l6_oracle.entry, word for word."""
    return {'id': yid, 'type': fact(typ, src(['S4'], words)),
            'organ': [fact(organ[0], src(['S4'], organ[1]))] if organ else [],
            'subtype': [fact(subtype[0], src(['S4'], subtype[1]))] if subtype else [],
            'joins': [fact(value, src(['S4'], w)) for value, w in joins]}


def o_outcome(history, entries, *, code='45380', findings=O_PER_ANUS, approach=('transanal', 'inserted per anus'),
              through=None):
    """test_l6_oracle.outcome, word for word: a colonoscopy X1 to the cecum with a transverse biopsy, through the
    product's own path (test_r2cl_lesion.outcomes, the faithful pass 2)."""
    text = HEAD.replace('LOWER ENDOSCOPY', 'ENDOSCOPY') + f'History: {history}\n' + f'Findings: {findings}\n' + f'{O_BX}\n'
    status = next(w for w in ('was introduced', 'was inserted', 'was advanced') if w in findings)
    sess = session('X1', fact('colonoscopy', src(['S5'], 'colonoscope')), examination=[fact('E1', src(['S5']))],
                   encounter=[fact('this_encounter', frame(['S2']))],
                   approach=[fact(approach[0], src(['S5'], approach[1]))],
                   through=[fact(through[0], src(['S5'], through[1]))] if through else [],
                   reached=[fact('cecum', src(['S5'], 'advanced to the cecum'))])
    data = answer(sections=[opening(), labelled('N1', 'S4', 'History:', 'history'),
                            labelled('N2', 'S5', 'Findings:', 'findings')],
                  sessions=[sess], anatomy=entries,
                  events=[event('E1', ['S5'], 'colonoscope', status, 'examination', session=[fact('X1', src(['S5']))]),
                          event('E2', ['S6'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S6']))],
                                target__places=[fact('transverse_colon', src(['S6'], 'transverse colon'))],
                                technique__device=[fact('cold_forceps', src(['S6'], 'cold forceps'))])])
    return R2CL.outcomes(text, data, R2CL.FAITHFUL, (code, O_BX))[code][:2]


class FindingTests(SimpleTestCase):
    """Each confirmed release finding of the fourth pass and each finding of the final check, on its own input: RED on
    int7 (every assertion marked 'int7:' gave READY there), GREEN on int8 - held with the table's own hold, 0 questions
    asked of Fable for it."""

    def test_l4p_1_and_final_check_1_a_pouchoscopy_per_anus_reads_every_other_entry(self):
        # L4P-1 (high) / final check 1: the guard returned early for a pouch row whose approach was SUPPORTED as another
        # route, but the pouch class accepts per anus (D219) - D336 (1) (a): only an established failure exempts
        for name, extra in BESIDE_POUCH.items():
            for code, number in (('44386', 2), ('44385', 1)):
                with self.subTest(beside=name, code=code):
                    held_by_route(self, assessed(pouch_scene(AP.TRANSANAL, extra), code, number))   # int7: READY
                    held_by_route(self, assessed(pouch_scene(AP.THROUGH_POUCH, extra), code, number))
        for approach in (AP.TRANSANAL, AP.THROUGH_POUCH):   # the pouch alone, per anus or through it: READY (44385,
            with self.subTest(control=approach.value):      # the diagnostic, is held as included in 44386, never routed)
                self.assertEqual(assessed(pouch_scene(approach, {}), '44386'), (READY, ()))
                self.assertNotIn(ROUTE, assessed(pouch_scene(approach, {}), '44385', 1)[1])

    def test_l4p_1_end_to_end_a_pouchoscopy_per_anus_beside_a_second_pouch(self):
        hist = 'Two ileal pouches were described: an ileal J-pouch in 2020 and a Kock pouch in 2010.'
        find = 'The endoscope was inserted per anus into the J-pouch and the pouch body was examined.'
        bx = 'Two biopsies of the pouch body were taken with cold forceps.'
        anat = [('Y1', 'ileal_pouch', 'ileal J-pouch', [], [], []), ('Y2', 'ileal_pouch', 'Kock pouch', [], [], [])]
        case = G.note(hist, find, bx, kind='enteroscopy', kind_words='endoscope', approach=('transanal',
                      'inserted per anus'), through=('Y1', 'into the J-pouch'), reached=[('pouch', 'into the J-pouch')],
                      anatomy=anat, place='pouch', place_words='pouch body')
        held_by_route(self, G.status(case, '44386', bx))    # int7: READY

    def test_l4p_2_a_colon_keeping_join_naming_the_pouch_holds_beside_a_pouch(self):
        # L4P-2 (high): the pouch family's joins-only row read a pouch member as-is; D336 (1) (b): no row releases on
        # joins, and a pouch member of a coloanal or colorectal join is that subtype's colon end - no pouch-family row
        for subtype, joins in ((SUB.COLOANAL, (LM.POUCH, LM.ANAL_CANAL)), (SUB.COLORECTAL, (LM.POUCH, LM.RECTUM))):
            for state in (sup, claimed):
                entry = anastomosis(*joins, subtype=state(subtype))
                R, code, number = G.family_control('POUCH', {Y7: entry})
                with self.subTest(subtype=subtype.value, state=state.__name__):
                    held_by_route(self, assessed(R, code, number))    # int7: READY
        R, code, number = G.family_control('POUCH', {Y7: anastomosis(LM.POUCH, LM.ANAL_CANAL, subtype=SUB.ILEOANAL)})
        self.assertEqual(assessed(R, code, number), (READY, ()))     # the pouch's own join stays READY

    def test_l4p_2_end_to_end_a_colonic_j_pouch_anal_anastomosis_beside_an_ileal_pouch(self):
        hist = 'Low anterior resection with a colonic J-pouch anal anastomosis in 2027.'
        find = 'The endoscope was passed through the anus into the J-pouch and the pouch body was examined.'
        bx = 'Two biopsies of the pouch body were taken with cold forceps.'
        anat = [('Y1', 'ileal_pouch', 'J-pouch', [], [], []),
                ('Y2', 'anastomosis', 'colonic J-pouch anal anastomosis', [], ['coloanal'], ['pouch', 'anal_canal'])]
        case = G.note(hist, find, bx, kind='enteroscopy', kind_words='endoscope',
                      approach=('through_pouch', 'into the J-pouch'), through=('Y1', 'into the J-pouch'),
                      reached=[('pouch', 'into the J-pouch')], anatomy=anat, place='pouch', place_words='pouch body',
                      exam_status='was passed')
        held_by_route(self, G.status(case, '44386', bx))    # int7: READY

    def test_l4p_3_no_9_4_weakening_of_the_colonic_reach_releases_the_ileoscopy(self):
        # L4P-3 (low on verification; R5R-9's own class): the reach clause read only a SUPPORTED colonic point; D336
        # (1) (c): every value a member may be
        base = G.ileoscopy(None, reached=(sup(EX.ILEUM), sup(EX.CECUM)))
        held_by_route(self, assessed(base, '44382'))
        for name, point in (('unresolved', unres(EX.CECUM)), ('claimed only', claimed(EX.CECUM)),
                            ('doubt stated', doubted(EX.CECUM, EX.ILEUM)),
                            ('doubt unclear', unres(EX.CECUM, ct.Reason.DOUBT_UNCLEAR)),
                            ('a contradiction with the ileum', contra(EX.CECUM, EX.ILEUM))):
            for code, number in (('44382', 2), ('44380', 1)):
                with self.subTest(weakening=name, code=code):
                    held_by_route(self, assessed(G.ileoscopy(None, reached=(sup(EX.ILEUM), point)), code, number))
        self.assertEqual(assessed(G.ileoscopy(None), '44382'), (READY, ()))   # an ileal reach alone: READY

    def test_l4p_4_no_added_reading_of_the_stomas_organ_releases_the_ileoscopy(self):
        # L4P-4 (medium): the organ clause held only while the filed organ could lie NOWHERE in the ileum; D336 (1) (c):
        # it holds while it MAY lie outside the ileum
        for organ in (LM.JEJUNUM, LM.STOMACH, LM.DUODENUM, LM.RECTUM):
            held_by_route(self, assessed(G.ileoscopy(sup(organ)), '44382'))
            for name, weak in (('doubt naming the ileum', doubted(organ, LM.ILEUM)),
                               ('contradiction with the ileum', contra(organ, LM.ILEUM)),
                               ('doubt naming the small bowel', doubted(organ, LM.SMALL_BOWEL)),
                               ('doubt naming the terminal ileum', doubted(organ, LM.TERMINAL_ILEUM)),
                               ('contradiction with the small bowel', contra(organ, LM.SMALL_BOWEL))):
                with self.subTest(organ=organ.value, weakening=name):
                    held_by_route(self, assessed(G.ileoscopy(weak), '44382'))    # int7: READY
        # the same class from the other side: an ileal organ with a non-ileal reading (int7 pinned it READY)
        for weak in (doubted(LM.ILEUM, LM.JEJUNUM), contra(LM.ILEUM, LM.STOMACH)):
            with self.subTest(mirror=str(weak.options)):
                held_by_route(self, assessed(G.ileoscopy(weak), '44382'))    # int7: READY
        for control in (claimed(LM.ILEUM), sup(LM.SMALL_BOWEL), None):
            with self.subTest(control=str(control and control.value)):
                self.assertEqual(assessed(G.ileoscopy(control), '44382'), (READY, ()))

    def test_l4p_5_no_release_rests_on_a_joins_member_or_a_type_pass_2_rejected(self):
        # L4P-5 (medium): a rejected uncontrolled joins member or type narrowed an entry onto rows 7 and 3; D336 (1) (b):
        # fully open, and no row releases on joins or on an uncontrolled type
        entries = {
            'joins [ileum, colon], both rejected': anastomosis(rejected(LM.ILEUM), rejected(LM.COLON)),
            'joins [ileum, colon], the colon rejected': anastomosis(LM.ILEUM, rejected(LM.COLON)),
            'joins [colon], rejected': anastomosis(rejected(LM.COLON)),
            'a Roux limb rejected, organ silent': entry_of(type=rejected(AT.ROUX_LIMB)),
            'joins [ileum, colon] supported, subtype silent': anastomosis(LM.ILEUM, LM.COLON),
            'a Roux limb supported, organ silent': entry_of(type=sup(AT.ROUX_LIMB)),
        }
        for name, entry in entries.items():
            for family in ('COLON', 'RECTUM_AND_SIGMOID', 'COLONIC_STOMA'):
                R, code, number = G.family_control(family, {Y7: entry})
                with self.subTest(entry=name, family=family):
                    held_by_route(self, assessed(R, code, number))    # int7: READY

    def test_l4p_5_end_to_end_an_ileorectal_join_misfiled_and_caught_by_pass_2(self):
        # the L4P-5 verifier's S-D4: a subtotal colectomy's ileorectal anastomosis filed with its subtype silent and its
        # joins [ileum, colon]; an honest pass 2 rejects "joins the colon" - the colon is gone and 45380 must hold
        ira = 'Subtotal colectomy with an ileorectal anastomosis in 2025.'
        fd = ('The colonoscope was inserted per anus, advanced to the ileorectal anastomosis and into the neo-terminal '
              'ileum.')
        bx = 'Two biopsies of the neo-terminal ileum were taken with cold forceps.'
        text, data = reached_note(ira, fd, bx, subtypes=[], joins=['ileum', 'colon'], words='ileorectal anastomosis',
                                  reached=[('neo_terminal_ileum', 'into the neo-terminal ileum')],
                                  reached_anatomy_words='to the ileorectal anastomosis', place='neo_terminal_ileum',
                                  place_words='neo-terminal ileum')
        for name, oracle in (('the colon rejected', contradicting({'colon'})),
                             ('both rejected', contradicting({'ileum', 'colon'})), ('faithful', R2CL.FAITHFUL)):
            with self.subTest(pass2=name):
                held_by_route(self, R2CL.outcomes(text, data, oracle, ('45380', bx))['45380'][:2])   # int7: READY

    def test_final_check_2_a_silent_anastomosis_at_the_jejunum_holds(self):
        # final check 2 (and L6O-5): an empty joins list matched row 4 (OUTSIDE) vacuously; D336 (1) (b): an empty list
        # of an entry that may be an anastomosis names every landmark, and no row releases on an uncontrolled type
        for organ in (claimed(LM.JEJUNUM), sup(LM.JEJUNUM), claimed(LM.STOMACH)):
            for code in (45380, 45331):
                R = R3F.scope(code, approach=sup(AP.TRANSANAL), entries={Y1: entry_of(type=sup(AT.ANASTOMOSIS),
                                                                                       organ=organ)})
                with self.subTest(organ=organ.value.value, state=organ.result.value, code=code):
                    held_by_route(self, assessed(R, code))    # int7: READY
        R = R3F.scope(45380, approach=sup(AP.TRANSANAL), entries={Y1: entry_of(type=sup(AT.ANASTOMOSIS),
                                                                               organ=claimed(LM.ILEUM))})
        held_by_route(self, assessed(R, 45380))    # the final check's control, held on int7 too

    def test_final_check_3_a_one_member_small_bowel_joins_list_holds(self):
        # final check 3: a one-member list may be an IRA or an IPAA whose other end pass 1 did not file; D336 (1) (b):
        # that member plus every landmark (supersedes D330 (1) (c)'s release; no row releases on joins)
        for subtype, member in ((None, LM.ILEUM), (None, LM.SMALL_BOWEL), (SUB.OTHER, LM.ILEUM),
                                (None, LM.TERMINAL_ILEUM), (SUB.OTHER, LM.JEJUNUM)):
            for code in (45380, 45331):
                R = R3F.scope(code, approach=sup(AP.TRANSANAL), entries={Y1: anastomosis(member, subtype=subtype)})
                with self.subTest(subtype=subtype and subtype.value, member=member.value, code=code):
                    held_by_route(self, assessed(R, code))    # int7: READY
                    # round r3's round 7 (DECISIONS D342 (1) (d)): the unnamed end pinned on the guard's own reader (the
                    # final check's info finding: mutant FC.b2 survived here, the status held by release_reading anyway)
                    self.assertTrue(evaluate.ileum_below_colon_possible(R, Y1))
        # D342 (1) (b): a filed joins list names an anastomosis whatever the entry's uncontrolled type - an absence filing
        # one ileal end has its unnamed end too (the reader; the status is held by the absent row's empty joins as well)
        for member in (LM.ILEUM, LM.SMALL_BOWEL, LM.TERMINAL_ILEUM):
            R = R3F.scope(45380, approach=sup(AP.TRANSANAL),
                          entries={Y1: entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=sup(LM.RECTUM), joins=(sup(member),))})
            with self.subTest(absence_joins=member.value):
                self.assertTrue(evaluate.ileum_below_colon_possible(R, Y1))
                held_by_route(self, assessed(R, 45380))

    def test_final_check_4_a_stoma_beside_a_per_anus_code_holds(self):
        # final check 4: beside a SUPPORTED per-anus approach any stoma was harmless; D336 (1) (b) and (e): the contract
        # gives per anus no control, so the approach is read at its widest - a stoma may be the route
        for organ in (claimed(LM.ILEUM), claimed(LM.DESCENDING_COLON), claimed(LM.STOMACH), None):
            for code in (45380, 45378, 45331, 45391, 45341):
                R = R3F.scope(code, approach=sup(AP.TRANSANAL), entries={Y1: entry_of(type=sup(AT.STOMA), organ=organ)})
                with self.subTest(organ=organ and organ.value.value, code=code):
                    found = evaluate.decide(str(code), (), R)
                    self.assertTrue(found.held_facts)
                    self.assertIn(ROUTE, {held.cause for held in found.held_facts})    # int7: none

    def test_final_check_5_an_upper_tract_type_or_subtype_at_a_lower_gi_organ_holds(self):
        # final check 5 (and L6O-2): the upper rows took any organ; D336 (1) (e): a contradictory filing is read at its
        # widest - an upper-tract type or subtype never decides a release against a lower-GI organ
        entries = {
            'a gastric pouch (claimed) at the anal canal': entry_of(type=claimed(AT.GASTRIC_POUCH),
                                                                    organ=claimed(LM.ANAL_CANAL)),
            'a gastric pouch (claimed) at the ileum': entry_of(type=claimed(AT.GASTRIC_POUCH), organ=claimed(LM.ILEUM)),
            'a gastric pouch (claimed) at the pouch landmark': entry_of(type=claimed(AT.GASTRIC_POUCH),
                                                                        organ=claimed(LM.POUCH)),
            'a gastric pouch (supported) at the colon': entry_of(type=sup(AT.GASTRIC_POUCH), organ=claimed(LM.COLON)),
            'a gastrojejunal anastomosis (claimed) at the rectum': entry_of(type=sup(AT.ANASTOMOSIS),
                                                                            subtype=claimed(SUB.GASTROJEJUNAL),
                                                                            organ=claimed(LM.RECTUM)),
            'a Roux limb at the ileum': entry_of(type=sup(AT.ROUX_LIMB), organ=claimed(LM.ILEUM)),
        }
        for name, entry in entries.items():
            for code in (45380, 45331):
                R = R3F.scope(code, approach=sup(AP.TRANSANAL), entries={Y1: entry})
                with self.subTest(entry=name, code=code):
                    held_by_route(self, assessed(R, code))    # int7: READY


class ContradictoryFilingTests(SimpleTestCase):
    """The oracle lens's contradictory filings (L6O-2 to L6O-5, low; D336 (1) (e)), end to end through the product's
    path (test_l6_oracle's inputs word for word): READY on int7, held on int8."""

    def test_l6o_2_a_roux_limb_filed_at_the_ileum_is_no_harmless_upper_alteration(self):
        held_by_route(self, o_outcome('Roux-en-Y reconstruction of the ileum in 2020.',
                                      [o_entry('Y1', 'roux_limb', 'Roux-en-Y reconstruction', ('ileum', 'ileum'))]))

    def test_l6o_3_an_organ_above_the_colon_joined_below_it_leaves_no_colon(self):
        held_by_route(self, o_outcome('Duodenorectal anastomosis in 2020.',
                                      [o_entry('Y1', 'anastomosis', 'Duodenorectal anastomosis', None, None,
                                               [('duodenum', 'Duodenorectal'), ('rectum', 'Duodenorectal')])]))
        # the census's variants: an upper organ joined to the rectum or the anal canal, under any subtype
        for upper, below, subtype in itertools.product((LM.STOMACH, LM.ESOPHAGUS, LM.COMMON_BILE_DUCT, LM.PANCREAS),
                                                       (LM.RECTUM, LM.ANAL_CANAL),
                                                       (None, SUB.GASTROJEJUNAL, SUB.ILEOCOLIC, SUB.COLORECTAL)):
            R = R3F.scope(45380, approach=sup(AP.TRANSANAL), entries={Y1: anastomosis(upper, below, subtype=subtype)})
            with self.subTest(upper=upper.value, below=below.value, subtype=subtype and subtype.value):
                held_by_route(self, assessed(R, 45380))

    def test_l6o_4_no_colonoscopy_reaches_the_cecum_through_a_gastrostomy(self):
        held_by_route(self, o_outcome('Percutaneous gastrostomy of the stomach in 2029.',
                                      [o_entry('Y1', 'stoma', 'Percutaneous gastrostomy', ('stomach', 'stomach'))],
                                      code='44389',
                                      findings='The colonoscope was introduced through the gastrostomy and advanced to '
                                               'the cecum.',
                                      approach=('through_stoma', 'introduced through the gastrostomy'),
                                      through=('Y1', 'through the gastrostomy')))
        for organ in (claimed(LM.STOMACH), claimed(LM.JEJUNUM), claimed(LM.DUODENUM), doubted(LM.SIGMOID_COLON,
                                                                                              LM.STOMACH)):
            S = RR.stoma_scope(reached=(sup(EX.CECUM),), organ=organ)
            with self.subTest(organ=str(organ.value), state=organ.result.value):
                self.assertIn(ROUTE, {held.cause for held in evaluate.decide('44389', (), S).held_facts})
        S = RR.stoma_scope(reached=(sup(EX.CECUM),), organ=claimed(LM.SIGMOID_COLON))   # a colostomy: READY
        self.assertEqual(RR.held_of(S, '44389'), [])

    def test_l6o_5_an_anastomosis_of_the_jejunum_with_neither_subtype_nor_joins_is_the_silent_residual(self):
        held_by_route(self, o_outcome('Jejunal anastomosis in 2020.',
                                      [o_entry('Y1', 'anastomosis', 'Jejunal anastomosis', ('jejunum', 'Jejunal'))]))


class DevelopmentFilingTests(SimpleTestCase):
    """D336 (1): the development filings stay as int7 decides them, each READY resting on a controlled reading - an
    ileocolic subtype decides its ends, and filed joins only add holds; an absence decides by its organ claim."""

    def test_the_oracle_lenss_controls_stay_ready_or_held_as_on_int7(self):
        self.assertEqual(o_outcome('Hysterectomy in 2015.',
                                   [o_entry('Y1', 'surgically_absent', 'Hysterectomy', ('other', 'Hysterectomy'))]),
                         (READY, ()))
        self.assertEqual(o_outcome('Right hemicolectomy with an ileocolic anastomosis in 2026.',
                                   [o_entry('Y1', 'anastomosis', 'ileocolic anastomosis', None,
                                            ('ileocolic', 'ileocolic anastomosis'),
                                            [('ileum', 'ileocolic anastomosis'), ('colon', 'ileocolic anastomosis')])]),
                         (READY, ()))
        held_by_route(self, o_outcome('Total abdominal colectomy with an ileorectal anastomosis in 2026.',
                                      [o_entry('Y1', 'anastomosis', 'ileorectal anastomosis', None,
                                               ('ileorectal', 'ileorectal anastomosis'),
                                               [('ileum', 'ileorectal anastomosis'),
                                                ('rectum', 'ileorectal anastomosis')])]))

    def test_the_development_sets_own_filings(self):
        # the shapes the development set files beside every lower-GI READY row (r3i/int8 recheck/gates/anat-*.json): an
        # ileocolic anastomosis (type supported, subtype supported, joins [ileum, colon] supported), absences of the
        # cecum, the ileocecal valve, the ascending colon and the gallbladder (claimed: no reach names them, 3.2.1), the
        # approach per anus supported (or silent), the through naming the anastomosis passed
        ileocolic = anastomosis(LM.ILEUM, LM.COLON, subtype=SUB.ILEOCOLIC)
        cases = {
            'A-v3: the ileocolic anastomosis, approach silent': ({Y1: ileocolic}, None, None),
            'A-v6: the right colon absent by segment (claimed) beside it': (
                {Y1: entry_of(type=claimed(AT.SURGICALLY_ABSENT), organ=claimed(LM.CECUM)),
                 Y2: entry_of(type=claimed(AT.SURGICALLY_ABSENT), organ=claimed(LM.ASCENDING_COLON)),
                 Y3: ileocolic}, None, None),
            'A-note8: the anastomosis passed, a cholecystectomy, the cecum and the valve absent (claimed)': (
                {Y1: ileocolic,
                 Y2: entry_of(type=claimed(AT.SURGICALLY_ABSENT), organ=claimed(LM.GALLBLADDER)),
                 Y3: entry_of(type=claimed(AT.SURGICALLY_ABSENT), organ=claimed(LM.CECUM)),
                 Y5: entry_of(type=claimed(AT.SURGICALLY_ABSENT), organ=claimed(LM.ILEOCECAL_VALVE))},
                sup(AP.TRANSANAL), sup(Y1)),
            'C-C2MEM-023: the same filing, the through silent': (
                {Y1: ileocolic, Y2: entry_of(type=claimed(AT.SURGICALLY_ABSENT), organ=claimed(LM.CECUM)),
                 Y3: entry_of(type=claimed(AT.SURGICALLY_ABSENT), organ=claimed(LM.ILEOCECAL_VALVE)),
                 Y5: entry_of(type=claimed(AT.SURGICALLY_ABSENT), organ=claimed(LM.GALLBLADDER))},
                sup(AP.TRANSANAL), None),
        }
        for name, (entries, approach, through) in cases.items():
            for code in (45380, 45385, 45378):
                R = R3F.scope(code, approach=approach, through=through, entries=entries,
                              reached=sup(EX.NEO_TERMINAL_ILEUM))
                with self.subTest(case=name, code=code):
                    self.assertFalse(evaluate.path_guard(catalogue.lower_route(str(code)), R, X1))
                    self.assertNotIn(ROUTE, {held.cause for held in evaluate.decide(str(code), (), R).held_facts})

    def test_the_common_inputs_end_to_end(self):
        # D328 (1) (c)'s common inputs and D330 (1)'s floor, as test_r3g_rules.CommonInputTests reads them end to end
        G.CommonInputTests('test_the_common_inputs_end_to_end').test_the_common_inputs_end_to_end()


# === int7's declared release set and per-anus reading, FROZEN (r3h/int7 tests/v2/test_r3g_rules.py, fe6ba4eb): the
# baseline int8 only adds holds to - an entry int8 holds harmless int7 held harmless too ============================

def int7_declared_rows(family: str) -> list:
    rows = []
    for shape, types, subtypes, organs, joins, filed in (
            ('absent', None, None, None, None, False),
            ('anastomosis_upper', frozenset({AT.ANASTOMOSIS}), G.UPPER_SUBTYPES, G.ALL_PLACES, G.OUTSIDE | G.lm('pouch'),
             False),
            ('upper_alteration', frozenset({AT.GASTRIC_POUCH, AT.ROUX_LIMB}), G.ALL_SUBTYPES, G.ALL_PLACES,
             G.OUTSIDE | G.lm('pouch'), False),
            ('outside', G.ALL_TYPES - {AT.ILEAL_POUCH}, G.ALL_SUBTYPES, G.OUTSIDE, G.OUTSIDE, False),
            ('stoma', frozenset({AT.STOMA}), G.ALL_SUBTYPES, G.ALL_PLACES, G.ALL_PLACES, False)):
        if shape == 'absent':
            rows.append((shape, frozenset({AT.SURGICALLY_ABSENT}), G.ALL_SUBTYPES, G.ABSENT[family], G.ABSENT[family],
                         False))
        else:
            rows.append((shape, types, subtypes, organs, joins, filed))
    if family == 'POUCH':
        rows += [('anastomosis_pouch', frozenset({AT.ANASTOMOSIS}), G.ILEUM_BELOW, G.ALL_PLACES, G.POUCH_JOINS, False),
                 ('anastomosis_joins', frozenset({AT.ANASTOMOSIS}), G.ALL_SUBTYPES, G.ALL_PLACES,
                  G.POUCH_JOINS | G.OUTSIDE, True)]
    else:
        rows += [('anastomosis_colon', frozenset({AT.ANASTOMOSIS}), G.COLON_KEEPING, G.ALL_PLACES, G.COLON_JOINS, False),
                 ('anastomosis_joins', frozenset({AT.ANASTOMOSIS}), G.ALL_SUBTYPES, G.ALL_PLACES,
                  G.SMALL_BOWEL | G.COLON_ALL | G.lm('rectum', 'anal_canal') | G.OUTSIDE, True)]
    return rows


def int7_ileum_below(subtypes, subtype_silent: bool, joins) -> bool:
    if not subtype_silent and subtypes & G.ILEUM_BELOW:
        return True
    ends = None
    if not subtype_silent and subtypes and all(value in G.SUBTYPE_ENDS for value in subtypes):
        ends = frozenset().union(*(G.SUBTYPE_ENDS[value] for value in subtypes))
    members = [((m - G.NO_ORGAN) | ends) if ends is not None and m & G.NO_ORGAN else m for m in joins]
    below = G.lm('rectum', 'anal_canal') | G.NO_ORGAN
    small = G.SMALL_BOWEL | G.NO_ORGAN
    if len(members) == 1:
        return bool(members[0] & below)
    return any(members[i] & small and members[j] & below for i in range(len(members)) for j in range(len(members))
               if i != j)


def int7_harmless(family: str, types, subtypes, subtype_silent: bool, organs, joins) -> bool:
    """int7's declared release set's verdict (test_r3g_rules.oracle_harmless as int7 committed it, fe6ba4eb)."""
    if family not in G.ILEUM_BELOW_HARMLESS and int7_ileum_below(subtypes, subtype_silent, joins):
        return False
    for _shape, r_types, r_subtypes, r_organs, r_joins, filed in int7_declared_rows(family):
        if not (types <= r_types and subtypes <= r_subtypes and organs <= r_organs):
            continue
        if filed and not joins:
            continue
        if all(member <= r_joins for member in joins):
            return True
    return False


# === D336 (1) (f): THE CENSUSES ======================================================================================
#
# The state census reads every attribute in every state the fact pass files - established (a controlled value
# SUPPORTED: its claim supported, its control rejected), supported uncontrolled (a value the contract does not control,
# SUPPORTED by a single verdict), claimed (unappraised), doubted (a doubt's readings), a contradiction's sides, silent,
# rejected (pass 2 contradicted, no control left), an established negation and an open denial - each read at its widest
# by the DECLARED oracle (test_r3g_rules.oracle_harmless: the release set D336 (1) rules, written from the ruling); the
# route census does the same for the session's approach and through, for every route family.

STATE_LABELS = ('established', 'supported uncontrolled', 'claimed', 'doubted', 'contradicted', 'silent', 'rejected',
                'established negation', 'open denial')


def states_of(enum, value, other, controlled):
    """Every filing state of one field at ``value`` (``other``: the second reading or side): (label, the fact or None for
    silent, the values the declared reading takes - its widest unless the value is established)."""
    every = frozenset(enum)
    yield ('established' if value in controlled else 'supported uncontrolled'), sup(value), frozenset({value})
    yield 'claimed', claimed(value), frozenset({value})
    # round r3's round 7 (DECISIONS D342 (1) (a)): a pass-1 doubt or contradiction is read at its WIDEST - every value
    # (was: its value and its reading or side; tests/v2/test_r3m_guard.py enumerates settle's whole outcome table)
    yield 'doubted', doubted(value, other), every
    yield 'contradicted', contra(value, other), every
    yield 'silent', None, every
    yield 'rejected', rejected(value), every
    yield 'established negation', neg(value), every
    yield 'open denial', R3F.open_denial(value), every


# Each base entry of the state census: (type, subtype, organ, joins) - one per row of every family and the shapes just
# outside them
STATE_BASES = {
    'absent gallbladder': (AT.SURGICALLY_ABSENT, None, LM.GALLBLADDER, ()),
    'absent cecum': (AT.SURGICALLY_ABSENT, None, LM.CECUM, ()),
    'absent rectum': (AT.SURGICALLY_ABSENT, None, LM.RECTUM, ()),
    'absent other (an appendix)': (AT.SURGICALLY_ABSENT, None, LM.OTHER, ()),
    'absent colon': (AT.SURGICALLY_ABSENT, None, LM.COLON, ()),
    'ileocolic [ileum, colon]': (AT.ANASTOMOSIS, SUB.ILEOCOLIC, None, (LM.ILEUM, LM.COLON)),
    'colorectal [colon, rectum]': (AT.ANASTOMOSIS, SUB.COLORECTAL, None, (LM.COLON, LM.RECTUM)),
    'coloanal [pouch, anal canal]': (AT.ANASTOMOSIS, SUB.COLOANAL, None, (LM.POUCH, LM.ANAL_CANAL)),
    'gastrojejunal [stomach, jejunum]': (AT.ANASTOMOSIS, SUB.GASTROJEJUNAL, None, (LM.STOMACH, LM.JEJUNUM)),
    'ileoanal [pouch, anal canal]': (AT.ANASTOMOSIS, SUB.ILEOANAL, None, (LM.POUCH, LM.ANAL_CANAL)),
    'other [ileum]': (AT.ANASTOMOSIS, SUB.OTHER, None, (LM.ILEUM,)),
    'anastomosis, joins silent': (AT.ANASTOMOSIS, SUB.ILEOCOLIC, None, ()),
    'gastric pouch, stomach': (AT.GASTRIC_POUCH, None, LM.STOMACH, ()),
    'roux limb, jejunum': (AT.ROUX_LIMB, None, LM.JEJUNUM, ()),
    'stoma, stomach': (AT.STOMA, None, LM.STOMACH, ()),
    'stoma, ileum': (AT.STOMA, None, LM.ILEUM, ()),
    'other alteration, stomach': (AT.OTHER_ALTERATION, None, LM.STOMACH, ()),
    'ileal pouch': (AT.ILEAL_POUCH, None, None, ()),
}
STATE_OTHERS = {A.TYPE: (AT.STOMA, AT.ANASTOMOSIS, AT.SURGICALLY_ABSENT, AT.ILEAL_POUCH),
                A.SUBTYPE: (SUB.ILEORECTAL, SUB.COLOCOLIC, SUB.OTHER),
                A.ORGAN: (LM.COLON, LM.ANAL_CANAL, LM.STOMACH, LM.POUCH, LM.ILEUM),
                A.JOINS: (LM.RECTUM, LM.COLON, LM.ILEUM, LM.STOMACH, LM.OTHER)}


def census_shapes():
    """The state census's shapes: (label, facts, (types, subtypes, subtype_silent, organs, organ_silent, joins)) - every
    base entry with each of its fields, and each member of its joins, in every state, beside every other of its fields
    as filed (supported)."""
    enums = {A.TYPE: AT, A.SUBTYPE: SUB, A.ORGAN: LM}
    controlled = {A.TYPE: G.CONTROLLED_TYPES, A.SUBTYPE: G.CONTROLLED_SUBTYPES, A.ORGAN: frozenset()}
    for name, (typ, subtype, organ, joins) in STATE_BASES.items():
        plain = {A.TYPE: (sup(typ), frozenset({typ})),
                 A.SUBTYPE: (sup(subtype), frozenset({subtype})) if subtype else (None, G.ALL_SUBTYPES),
                 A.ORGAN: (sup(organ), frozenset({organ})) if organ else (None, G.ALL_PLACES)}
        for attribute in (A.TYPE, A.SUBTYPE, A.ORGAN):
            value = {A.TYPE: typ, A.SUBTYPE: subtype, A.ORGAN: organ}[attribute] or STATE_OTHERS[attribute][0]
            first = True
            for other in STATE_OTHERS[attribute]:
                if other is value:
                    continue
                for label, state, possible in states_of(enums[attribute], value, other, controlled[attribute]):
                    if not first and label not in ('doubted', 'contradicted'):
                        continue  # every other value is read only by the states that name it
                    fields = dict(plain)
                    fields[attribute] = (state, possible)
                    yield ((name, attribute.value, label, other.value),
                           G.shape_facts(fields[A.TYPE][0], fields[A.SUBTYPE][0], fields[A.ORGAN][0],
                                         [sup(j) for j in joins]),
                           (fields[A.TYPE][1], fields[A.SUBTYPE][1], fields[A.SUBTYPE][0] is None, fields[A.ORGAN][1],
                            fields[A.ORGAN][0] is None, tuple(frozenset({j}) for j in joins)))
                first = False
        for position, member in enumerate(joins):
            for other in STATE_OTHERS[A.JOINS]:
                if other is member:
                    continue
                for label, state, possible in states_of(LM, member, other, frozenset()):
                    if state is None:
                        continue  # a member is never silent: an empty list has no member
                    members = [sup(j) for j in joins]
                    members[position] = state
                    sets = [frozenset({j}) for j in joins]
                    sets[position] = possible
                    yield ((name, f'joins[{position}]', label, other.value),
                           G.shape_facts(plain[A.TYPE][0], plain[A.SUBTYPE][0], plain[A.ORGAN][0], members),
                           (plain[A.TYPE][1], plain[A.SUBTYPE][1], plain[A.SUBTYPE][0] is None, plain[A.ORGAN][1],
                            plain[A.ORGAN][0] is None, tuple(sets)))


class StateCensusTests(SimpleTestCase):
    """D336 (1) (f): every route family x every attribute's state (established, supported uncontrolled, claimed,
    doubted, contradicted, silent, rejected, an established negation, an open denial) x the widest values - the guard's
    harmless reading equals the declared release set's, and the census is complete."""

    def test_every_family_every_field_every_state(self):
        R0 = G.bare()
        wrong, checked, harmless, labels = [], 0, 0, set()
        for label, facts, possible in census_shapes():
            R = G.with_entry(R0, facts)
            labels.add((label[1].split('[')[0], label[2]))
            for family in G.FAMILIES:
                expected = G.oracle_harmless(family, *possible)
                if evaluate.harmless(R, Y1, G.needs(family)) != expected:
                    wrong.append((family, label, expected))
                checked += 1
                harmless += expected
        self.assertEqual(wrong[:20], [])
        self.assertTrue(0 < harmless < checked)
        # completeness: every field in every state the fact pass files (a joins member is never silent, and never
        # established through a control: the contract controls no joins)
        for field in ('type', 'subtype', 'organ'):
            for state in STATE_LABELS:
                if state == 'established' and field == 'organ':
                    continue  # the organ is controlled only in the absence form: the census's absences carry it
                with self.subTest(field=field, state=state):
                    self.assertIn((field, state), labels)
        for state in set(STATE_LABELS) - {'silent', 'established'}:
            self.assertIn(('joins', state), labels)

    def test_the_census_reaches_every_row_and_the_shapes_just_outside(self):
        R0 = G.bare()
        reached = {family: set() for family in G.FAMILIES}
        for _label, facts, _possible in census_shapes():
            reading = evaluate.release_reading(G.with_entry(R0, facts), Y1)
            for family in G.FAMILIES:
                if reading is None:
                    reached[family].add(None)
                    continue
                for row in catalogue.HARMLESS[G.needs(family)]:
                    if evaluate.harmless_row(reading, row):
                        reached[family].add(row.shape)
        for family in G.FAMILIES:
            with self.subTest(family=family):
                self.assertEqual(reached[family] - {None}, {row.shape for row in catalogue.HARMLESS[G.needs(family)]})
                self.assertIn(None, reached[family])


# The route census's entries (beside each family's own route entry, family_control's): label -> (facts, the declared
# type values, organ value or None, whether its organ is SUPPORTED)
ROUTE_ENTRIES = {
    'no entry': None,
    'a cholecystectomy': absent(LM.GALLBLADDER),
    'an ileocolic anastomosis': anastomosis(LM.ILEUM, LM.COLON, subtype=SUB.ILEOCOLIC),
    'a Roux limb': entry_of(type=sup(AT.ROUX_LIMB)),
    'a stoma, its organ claimed the ileum': entry_of(type=sup(AT.STOMA), organ=claimed(LM.ILEUM)),
    'a stoma, its organ SUPPORTED the stomach': entry_of(type=sup(AT.STOMA), organ=sup(LM.STOMACH)),
    'a stoma, its organ claimed the stomach': entry_of(type=sup(AT.STOMA), organ=claimed(LM.STOMACH)),
    'an ileal pouch': entry_of(type=sup(AT.ILEAL_POUCH)),
}
EVERY_APPROACH = frozenset(AP)


def approach_states(own):
    """Every approach state: (label, fact or None, the values it may be, controlled - established through a control)."""
    yield 'silent', None, None, False
    for value in AP:
        yield f'{value.value} supported', sup(value), frozenset({value}), value in G.CONTROLLED_APPROACHES
    yield 'per anus claimed', claimed(AP.TRANSANAL), frozenset({AP.TRANSANAL}), False
    yield f'{own.value} claimed', claimed(own), frozenset({own}), False
    yield 'per anus rejected', rejected(AP.TRANSANAL), EVERY_APPROACH, False
    yield "per anus, a doubt's reading through a pouch", doubted(AP.TRANSANAL, AP.THROUGH_POUCH), \
        frozenset({AP.TRANSANAL, AP.THROUGH_POUCH}), False
    yield 'per anus or through a stoma', contra(AP.TRANSANAL, AP.THROUGH_STOMA), \
        frozenset({AP.TRANSANAL, AP.THROUGH_STOMA}), False
    yield 'per anus established denied', neg(AP.TRANSANAL), EVERY_APPROACH, False
    yield 'through a stoma established denied', neg(AP.THROUGH_STOMA), EVERY_APPROACH, False
    yield 'per anus, an open denial', R3F.open_denial(AP.TRANSANAL), EVERY_APPROACH, False


Y9 = Id.parse('Y9')
THROUGH_STATES = {
    'silent': None, 'Y1 supported': sup(Y1), 'Y7 supported': sup(Y7), 'Y1 claimed': claimed(Y1),
    'Y9 supported (no such entry)': sup(Y9), 'Y1 or Y7': contra(Y1, Y7), 'Y1 established denied': neg(Y1),
    'Y1, an open denial': R3F.open_denial(Y1), 'Y1 rejected': rejected(Y1),
}
ACCEPTED = {AP.THROUGH_STOMA: frozenset({AP.THROUGH_STOMA}),                      # DECLARED: the stoma classes
            AP.THROUGH_POUCH: frozenset({AP.THROUGH_POUCH, AP.TRANSANAL})}        # the pouch class (D219)
LOWER_STOMA = G.COLON_ALL | G.lm('ileum', 'terminal_ileum', 'neo_terminal_ileum', 'small_bowel')


def declared_entry(facts):
    """The declared reading of one census entry: (type values, organ fact or None, the oracle's arguments)."""
    type_ = facts.get(A.TYPE, (None,))[0]
    organ = facts.get(A.ORGAN, (None,))[0]
    subtype = facts.get(A.SUBTYPE, (None,))[0]
    types = frozenset({type_.value}) if type_ is not None else G.ALL_TYPES
    args = (types, frozenset({subtype.value}) if subtype is not None else G.ALL_SUBTYPES, subtype is None,
            frozenset({organ.value}) if organ is not None else G.ALL_PLACES, organ is None,
            tuple(frozenset({member.value}) for member in facts.get(A.JOINS, ())))
    return types, organ, args


def declared_guard(family, approach, a_values, controlled, through, t_name, anatomy) -> bool:
    """D330 (1) and D336 (1), DECLARED for one route state: whether the guard holds."""
    route = G.ROUTE_OF[family]
    if route is not AP.TRANSANAL and approach is not None and approach.result is ct.Result.SUPPORTED and \
            approach.value not in ACCEPTED[route]:
        return False  # (a): an established failure of the code's row or class exempts
    read = {entry: declared_entry(facts) for entry, facts in anatomy.items()}
    own = set()
    if route is not AP.TRANSANAL:
        wanted = AT.STOMA if route is AP.THROUGH_STOMA else AT.ILEAL_POUCH
        if through is not None and through.result is ct.Result.SUPPORTED:
            named = [through.value]
        else:
            names = {'silent': set(anatomy), 'Y1 claimed': {Y1}, 'Y1 or Y7': {Y1, Y7}, 'Y1, an open denial': set(anatomy),
                     'Y1 rejected': {Y1}, 'Y1 established denied': set()}[t_name]
            named = [entry for entry in names if entry in read and wanted in read[entry][0]]
        if len(named) == 1 and named[0] in read and read[named[0]][0] == {wanted}:
            own = {named[0]}
    if any(entry not in own and not G.oracle_harmless(family, *read[entry][2]) for entry in anatomy):
        return True
    if route is not AP.TRANSANAL and own_entry_outside_declared(family, through, t_name, anatomy):
        return True  # round r3's round 7 (DECISIONS D342 (1) (c)): the route's own entry within its type's anatomy
    if family == 'COLONIC_STOMA':  # (e): a stoma passed through whose filed organ may lie outside the lower tract
        stomas = [entry for entry in anatomy if AT.STOMA in read[entry][0]]
        if through is not None and through.result is ct.Result.SUPPORTED:
            stomas = [entry for entry in stomas if entry == through.value]
        if any(read[entry][1] is not None and read[entry][1].value not in LOWER_STOMA for entry in stomas):
            return True
    if route is not AP.TRANSANAL:
        return False
    if approach is not None and not a_values <= {AP.TRANSANAL}:
        return True  # R5R-7
    if not controlled:  # (b): per anus has no control - read as int6 reads a silent approach
        for entry, (types, organ, _args) in read.items():
            outside = organ is not None and organ.result is ct.Result.SUPPORTED and organ.value not in LOWER_STOMA \
                and organ.value not in G.NO_ORGAN
            if (AT.STOMA in types and not outside) or AT.ILEAL_POUCH in types:
                return True
    if through is None:
        return False
    names = {'Y1 supported': {Y1}, 'Y7 supported': {Y7}, 'Y1 claimed': {Y1}, 'Y9 supported (no such entry)': {Y9},
             'Y1 or Y7': {Y1, Y7}}.get(t_name, set(anatomy) | {Y1})
    for name in names:   # R5R-8: the through may name an entry that may be a stoma or a pouch
        if name not in read:
            return True  # an entry the FactSet does not hold: its type may be anything
        types, organ, _args = read[name]
        if types & {AT.STOMA, AT.ILEAL_POUCH, AT.GASTRIC_POUCH} or (organ is not None and organ.value in
                                                                     (LM.STOMA, LM.POUCH)):
            return True
    return False


# Round r3's round 7 (DECISIONS D342 (1) (c)), DECLARED from the ruling: the anatomy each through family's own entry may
# file - a colonic stoma the colon's and the ileum's places, an ileal stoma the ileum's, no subtype for a stoma; an
# ileal pouch the ileum's places and the pouch, its own ileorectal or ileoanal join, the pouch family's joins
ILEAL_OWN = G.lm('ileum', 'terminal_ileum', 'neo_terminal_ileum', 'small_bowel')
OWN_DECLARED = {  # family -> (type, organs, subtypes, joins)
    'COLONIC_STOMA': (AT.STOMA, LOWER_STOMA, frozenset(), LOWER_STOMA),
    'ILEAL_STOMA': (AT.STOMA, ILEAL_OWN, frozenset(), ILEAL_OWN),
    'POUCH': (AT.ILEAL_POUCH, ILEAL_OWN | G.lm('pouch'), G.ILEUM_BELOW, G.POUCH_JOINS),
}


def own_entry_outside_declared(family, through, t_name, anatomy) -> bool:
    """D342 (1) (c), DECLARED: every entry that may be the route's own - its type may be the route's type, the session's
    through may name it (a supported through names only its entry; a through not established, every entry it may be:
    a claimed one its value, a contradiction's sides, a silent, denied or rejected one every entry) - files an organ, a
    subtype or a joins member outside its type's own anatomy."""
    wanted, organs, subtypes, joins = OWN_DECLARED[family]
    if through is not None and through.result is ct.Result.SUPPORTED:
        names = {through.value}
    else:
        names = {'Y1 claimed': {Y1}, 'Y1 or Y7': {Y1, Y7}}.get(t_name, set(anatomy))
    for entry in names & set(anatomy):
        facts = anatomy[entry]
        type_ = facts.get(A.TYPE, (None,))[0]
        if type_ is not None and type_.value is not wanted and type_.result is not ct.Result.NEGATED:
            continue  # an entry whose type is established or claimed otherwise is never the route's own
        organ = facts.get(A.ORGAN, (None,))[0]
        subtype = facts.get(A.SUBTYPE, (None,))[0]
        if organ is not None and organ.value not in organs or subtype is not None and subtype.value not in subtypes:
            return True
        if any(member.value not in joins for member in facts.get(A.JOINS, ())):
            return True
    return False


class RouteStateCensusTests(SimpleTestCase):
    """D336 (1) (f): every route family x every approach and through state x the census's entries - the guard equals the
    declared reading: (a) only an established failure exempts; (b) per anus has no control; (e) a colonoscopy through a
    stoma's stoma may not lie outside the lower tract; R5R-7 and R5R-8."""

    def test_every_route_family_every_approach_and_through_state(self):
        wrong, checked, held, seen = [], 0, 0, set()
        for family in G.FAMILIES:
            route = G.ROUTE_OF[family]
            code = {'COLON': '45380', 'RECTUM_AND_SIGMOID': '45331', 'COLONIC_STOMA': '44389', 'ILEAL_STOMA': '44382',
                    'POUCH': '44386'}[family]
            found = catalogue.lower_route(code)
            for (a_name, approach, a_values, controlled), (t_name, through), (e_name, extra) in itertools.product(
                    list(approach_states(route)), THROUGH_STATES.items(), ROUTE_ENTRIES.items()):
                R, _code, _number = G.family_control(family, {Y7: extra} if extra is not None else None)
                session = dict(R.sessions[X1])
                session.pop(A.APPROACH, None)
                session.pop(A.THROUGH, None)
                if approach is not None:
                    session[A.APPROACH] = (approach,)
                if through is not None:
                    session[A.THROUGH] = (through,)
                R = replace(R, sessions={**R.sessions, X1: session})
                expected = declared_guard(family, approach, a_values, controlled, through, t_name, dict(R.anatomy))
                if evaluate.path_guard(found, R, X1) != expected:
                    wrong.append((family, a_name, t_name, e_name, expected))
                checked += 1
                held += expected
                seen.add((family, a_name, t_name))
        self.assertEqual(wrong[:20], [])
        self.assertTrue(0 < held < checked)
        # completeness: every family x every approach state x every through state
        self.assertEqual(len(seen), sum(len(list(approach_states(G.ROUTE_OF[f]))) for f in G.FAMILIES)
                         * len(THROUGH_STATES))


class PMonoCensusTests(SimpleTestCase):
    """D336 (1) (f), (c): 9.4's weakening lattice (test_properties.weakenings: every fact of every table, every
    established member deleted, AMENDMENT-2 4.4's erasing contradictions included) over every route-table family - from
    each family's held scenes (the census's entries the guard holds beside the family's control, and the ileoscopy's
    R5R-9 scenes), no single weakening releases the code, and with the act's session known its route row never turns T."""

    def held_scenes(self):
        scenes = []
        for family in G.FAMILIES:
            for e_name, extra in ROUTE_ENTRIES.items():
                if extra is None:
                    continue
                R, code, number = G.family_control(family, {Y7: extra})
                if evaluate.decide(code, (), R).held_facts:
                    scenes.append((f'{family}: {e_name}', R, code))
            for name, entry in (('a silent anastomosis', entry_of(type=sup(AT.ANASTOMOSIS))),
                                ('one member [ileum]', anastomosis(LM.ILEUM)),
                                ('a rejected Roux limb', entry_of(type=rejected(AT.ROUX_LIMB))),
                                ('a coloanal [pouch, anal canal]', anastomosis(LM.POUCH, LM.ANAL_CANAL,
                                                                              subtype=SUB.COLOANAL))):
                R, code, number = G.family_control(family, {Y7: entry})
                if evaluate.decide(code, (), R).held_facts:
                    scenes.append((f'{family}: {name}', R, code))
        scenes += [('44382, a jejunostomy', G.ileoscopy(sup(LM.JEJUNUM)), '44382'),
                   ('44382, the reach the cecum', G.ileoscopy(None, reached=(sup(EX.ILEUM), sup(EX.CECUM))), '44382'),
                   ('44386 per anus, a second pouch', pouch_scene(AP.TRANSANAL, BESIDE_POUCH['a second ileal pouch']),
                    '44386')]
        return scenes

    def test_no_weakening_releases_a_code_the_guard_holds(self):
        TP = R3F.properties()
        families, count = set(), 0
        for name, R, code in self.held_scenes():
            self.assertTrue(evaluate.decide(code, (), R).held_facts, name)
            families.add(name.split(':')[0])
            for label, weak, what in TP.weakenings(R):
                count += 1
                if label.startswith('deleted ') and what[1] is A.REACHED and code == '44382':
                    continue  # SC-B's list-completeness residual (the L4P-3 verifier): deleting the established colonic
                    # point leaves the record of an ileal reach alone, which stays READY (R5R-9's own control)
                if not evaluate.decide(code, (), weak).held_facts:
                    self.fail(f'{name}: the weakening {label} releases {code}')
                if evaluate._session(weak, E2) is not None:
                    self.assertIsNot(R3F.route_row(weak, int(code)).truth, evaluate.Truth.T, (name, label))
        self.assertTrue(set(G.FAMILIES) <= families)
        self.assertGreater(count, 2000)


class ControlledCensusTests(SimpleTestCase):
    """D336 (1) (f), (d): P-CONTROLLED made honest - every harmless row's reads against the contract's CONTROLS, every
    census release resting on a controlled claim and never on joins, and every READY-path read declared on that path."""

    def test_the_engines_controlled_values_are_the_contracts(self):
        from studio.interpretation.contract import claims as CL
        anatomy, session = CL.ObjectClass.ANATOMY, CL.ObjectClass.SESSION
        supported = ct.FactState.SUPPORTED

        def controlled(object_class, attribute, enum):
            out = set()
            for value in enum:
                rule = CL.control_rule(object_class, attribute, supported, value)
                if rule is None:
                    continue
                if rule.contrary is CL.Contrary.TABLE and CL.table(rule.table).get(value) is None:
                    continue  # no contrary in its table: the claim stands uncontrolled (claims.contrary)
                out.add(value)
            return frozenset(out)
        self.assertEqual(catalogue.CONTROLLED_TYPES, controlled(anatomy, A.TYPE, AT))
        self.assertEqual(catalogue.CONTROLLED_SUBTYPES, controlled(anatomy, A.SUBTYPE, SUB))
        self.assertEqual(catalogue.CONTROLLED_APPROACHES, controlled(session, A.APPROACH, AP))
        self.assertEqual((catalogue.CONTROLLED_TYPES, catalogue.CONTROLLED_SUBTYPES, catalogue.CONTROLLED_APPROACHES),
                         (G.CONTROLLED_TYPES, G.CONTROLLED_SUBTYPES, G.CONTROLLED_APPROACHES))
        # the organ: its claim states the absence (the only organ form) and is controlled by its own negation
        self.assertEqual(controlled(anatomy, A.ORGAN, LM), frozenset(LM))
        self.assertEqual(CL.FORMS[(anatomy, A.ORGAN, supported)], CL.TemplateId.ANATOMY_ORGAN_ABSENT)
        self.assertEqual(catalogue.ABSENCE_TYPE, AT.SURGICALLY_ABSENT)
        self.assertEqual(CL.FORMS[(anatomy, A.SUBTYPE, supported)], CL.TemplateId.ANATOMY_SUBTYPE)
        self.assertEqual(catalogue.SUBTYPE_TYPE, AT.ANASTOMOSIS)
        # joins: no control - read only to hold
        self.assertIsNone(CL.control_rule(anatomy, A.JOINS, supported, LM.ILEUM))

    def test_every_harmless_row_releases_on_a_controlled_claim(self):
        for family in G.FAMILIES:
            for row in catalogue.HARMLESS[G.needs(family)]:
                with self.subTest(family=family, shape=row.shape.value):
                    self.assertIn(row.decided_by, (A.TYPE, A.ORGAN, A.SUBTYPE))
                    if row.decided_by is A.TYPE:
                        self.assertLessEqual(row.values, catalogue.CONTROLLED_TYPES)
                    elif row.decided_by is A.SUBTYPE:
                        self.assertLessEqual(row.values, catalogue.CONTROLLED_SUBTYPES)
                    else:
                        self.assertLessEqual(row.values, frozenset(LM))

    def test_no_census_release_rests_on_joins_or_on_an_uncontrolled_claim(self):
        # every entry the census holds harmless is decided by a controlled claim with controlled values, and stays
        # harmless with its joins list removed - its joins could only have held it
        R0 = G.bare()
        released = 0
        for label, facts, _possible in census_shapes():
            R = G.with_entry(R0, facts)
            reading = evaluate.release_reading(R, Y1)
            for family in G.FAMILIES:
                if not evaluate.harmless(R, Y1, G.needs(family)):
                    continue
                released += 1
                with self.subTest(family=family, entry=label):
                    self.assertIsNotNone(reading)
                    self.assertIn(reading.decided_by, (A.TYPE, A.ORGAN, A.SUBTYPE))
                    if reading.decided_by is A.SUBTYPE:
                        self.assertLessEqual(reading.values, catalogue.CONTROLLED_SUBTYPES)
                    if reading.decided_by is A.TYPE:
                        self.assertLessEqual(reading.values, catalogue.CONTROLLED_TYPES)
                    without = {attribute: found for attribute, found in facts.items() if attribute is not A.JOINS}
                    self.assertTrue(evaluate.harmless(G.with_entry(R0, without), Y1, G.needs(family)))
        self.assertGreater(released, 100)

    def test_every_attribute_a_route_rows_ready_path_reads_is_declared_on_it(self):
        # (d): the route rows read every entry's type, organ and subtype on the READY path (the harmless set releases on
        # them) and its joins and the session's reach only to hold; the partition passes with the declaration true
        from studio.interpretation.engine import requirements as RQ
        from studio.interpretation.engine.requirements_table import Tag
        from tests.v2 import test_requirements as TR
        for rule in (RQ.RULES[RQ.Requirement.ROUTE_TABLE], RQ.RULES[Tag.LOWER], RQ.RULES[Tag.COLFULL]):
            reads = {(read.role, read.attribute): read.paths for read in rule.reads}
            for attribute in (A.TYPE, A.ORGAN, A.SUBTYPE):
                self.assertIn(RQ.Path.READY, reads[(RQ.Role.ANATOMY, attribute)])
            self.assertEqual(reads[(RQ.Role.ANATOMY, A.JOINS)], {RQ.Path.HOLD})
        self.assertEqual({(read.role, read.attribute): read.paths for read in
                          RQ.RULES[RQ.Requirement.ROUTE_TABLE].reads}[(RQ.Role.SESSION, A.REACHED)], {RQ.Path.HOLD})
        ready = TR.ready_reads()
        self.assertEqual(ready - TR.DESIGN_CONTROLLED, set(TR.READ_UNCONTROLLED))
        self.assertIn(('anatomy', 'subtype'), ready & TR.DESIGN_CONTROLLED)
        self.assertNotIn(('anatomy', 'joins'), ready)


class Int7MonotoneTests(SimpleTestCase):
    """int8 only adds holds (D336 (1) is the release direction): over every census shape - every attribute state, and
    test_r3g_rules' every type x subtype x organ x representative joins and every joins list of up to two members - an
    entry int8's guard holds harmless is harmless in int7's declared set (frozen above), for every route family."""

    def shapes(self):
        yield from census_shapes()
        for (tl, tf, tv), (sl, sf, sv), (ol, of, ov), joins in itertools.product(
                G.TYPE_STATES, G.SUBTYPE_STATES, G.ORGAN_STATES, G.JOIN_REPS):
            yield ((tl, sl, ol, tuple(j.value for j in joins)), G.shape_facts(tf, sf, of, [sup(j) for j in joins]),
                   (tv, sv, sf is None, ov, of is None, tuple(frozenset({j}) for j in joins)))
        lists = [()] + [(place,) for place in LM] + list(itertools.combinations_with_replacement(LM, 2))
        for (sl, sf, sv), joins in itertools.product(G.SUBTYPE_STATES, lists):
            yield (('anastomosis', sl, tuple(j.value for j in joins)),
                   G.shape_facts(sup(AT.ANASTOMOSIS), sf, None, [sup(j) for j in joins]),
                   (frozenset({AT.ANASTOMOSIS}), sv, sf is None, G.ALL_PLACES, True,
                    tuple(frozenset({j}) for j in joins)))

    def test_an_entry_int8_holds_harmless_was_harmless_on_int7(self):
        R0 = G.bare()
        released, checked = [], 0
        for label, facts, possible in self.shapes():
            R = G.with_entry(R0, facts)
            types, subtypes, subtype_silent, organs, _organ_silent, joins = possible
            for family in G.FAMILIES:
                checked += 1
                if evaluate.harmless(R, Y1, G.needs(family)) and not int7_harmless(
                        family, types, subtypes, subtype_silent, organs, joins):
                    released.append((family, label))
        self.assertEqual(released[:20], [])
        self.assertGreater(checked, 300000)

    def test_the_per_anus_reading_only_adds_holds(self):
        # int7's per-anus reading (R5R-7, a silent approach's stoma or pouch, R5R-8) holds a subset of int8's
        for (a_name, approach, a_values, _controlled), (t_name, through), (e_name, extra) in itertools.product(
                list(approach_states(AP.TRANSANAL)), THROUGH_STATES.items(), ROUTE_ENTRIES.items()):
            R = G.per_anus_scope(45331, approach=approach, through=through,
                                 entries={Y7: extra} if extra is not None else None)
            int7 = (evaluate.stoma_possible(R, X1) or evaluate.pouch_possible(R, X1)) if approach is None else \
                not a_values <= {AP.TRANSANAL}
            with self.subTest(approach=a_name, through=t_name, entry=e_name):
                if int7:
                    self.assertTrue(evaluate._anus_route_contradicted(R, X1))


class SurvivorPinTests(SimpleTestCase):
    """The mutation proof's survivors on the first int8 (r3i/int8/NOTES.md section 5: r6.G10, r6.G20, r4.S2, r4.S3,
    r4.S5), each pinned by the input its rule exists for:
    - D330 (1) (c) with D336 (1) (b), the ileum-below exclusion of every family but the pouch's: a joins list whose only
      member may lie below the colon may be the ileum joined there (an ileorectal or ileoanal join), WHATEVER controlled
      claim decides the entry - a colorectal or coloanal subtype, a stoma - so the entry is never harmless; beside the
      sigmoidoscopy and the ileoscopy families no other arm of the route table reads a colon gone, so only this
      exclusion holds them (r6.G10, the exclusion dropped, releases 45331 and 44382);
    - D336 (1) (b), the ends a one-member list leaves unnamed: a subtype that names its ends names them (an ileocolic
      anastomosis's lone ileal member is joined to the colon, a gastrojejunal's lone jejunal member to the stomach), and
      an entry that may not be an anastomosis has no unnamed end (a gastric pouch's lone jejunal member) - so a lone
      small-bowel member never holds by itself (r6.G20, the one-member rule widened to the small bowel, holds them);
    - D327 (1) (v8, v9) read by every value (D336 (1) (b), (e)): a subtype FILED on the route's own stoma - which the
      path guard leaves to the route (route_entries) - that may be an ileorectal or ileoanal join leaves no colon for a
      colonoscopy through that stoma, whatever type it was filed beside and whatever state it is in: supported, claimed,
      doubted, an established negation of another subtype, a claim pass 2 rejected (r4.S2 reads only an established
      subtype, r4.S3 no negation or rejection, r4.S5 only beside a type that may be an anastomosis - each releases
      44389)."""

    BELOW = (('a colorectal anastomosis joining only the rectum', anastomosis(LM.RECTUM, subtype=SUB.COLORECTAL)),
             ('a coloanal anastomosis joining only the anal canal', anastomosis(LM.ANAL_CANAL, subtype=SUB.COLOANAL)),
             ('a stoma joining only the rectum', entry_of(type=sup(AT.STOMA), joins=(sup(LM.RECTUM),))))
    SMALL = (('an ileocolic anastomosis joining only the ileum', anastomosis(LM.ILEUM, subtype=SUB.ILEOCOLIC)),
             ('a gastrojejunal anastomosis joining only the jejunum', anastomosis(LM.JEJUNUM, subtype=SUB.GASTROJEJUNAL)),
             ('a gastric pouch joining only the jejunum', entry_of(type=sup(AT.GASTRIC_POUCH), joins=(sup(LM.JEJUNUM),))))

    def test_a_lone_member_below_the_colon_is_never_harmless_beside_a_family_but_the_pouchs(self):
        for family in G.FAMILIES:
            needs = G.needs(family)
            if needs in catalogue.HARMLESS_ILEUM_BELOW:
                continue
            for name, entry in self.BELOW:
                with self.subTest(family=family, entry=name):
                    R, code, number = G.family_control(family, {Y7: entry})
                    self.assertTrue(evaluate.ileum_below_colon_possible(R, Y7))
                    self.assertFalse(evaluate.harmless(R, Y7, needs))
                    held_by_route(self, assessed(R, code, number))

    def test_a_lone_small_bowel_member_never_holds_by_itself(self):
        for family in G.FAMILIES:
            needs = G.needs(family)
            if needs in catalogue.HARMLESS_ILEUM_BELOW:
                continue
            for name, entry in self.SMALL:
                with self.subTest(family=family, entry=name):
                    R, code, number = G.family_control(family, {Y7: entry})
                    self.assertFalse(evaluate.ileum_below_colon_possible(R, Y7))
                    self.assertTrue(evaluate.harmless(R, Y7, needs))
                    self.assertEqual(assessed(R, code, number), (READY, ()))

    def test_the_routes_own_stoma_filing_an_ileum_below_subtype_holds_the_colonoscopy_through_it(self):
        for name, subtype in (('supported ileorectal', sup(SUB.ILEORECTAL)), ('claimed ileorectal', claimed(SUB.ILEORECTAL)),
                              ('ileoanal doubted against ileocolic', doubted(SUB.ILEOANAL, SUB.ILEOCOLIC)),
                              ('ileocolic negated', neg(SUB.ILEOCOLIC)), ('other rejected by pass 2', rejected(SUB.OTHER))):
            own = entry_of(type=sup(AT.STOMA), organ=claimed(LM.SIGMOID_COLON), subtype=subtype)
            with self.subTest(subtype=name):
                R, code, number = G.family_control('COLONIC_STOMA', {Y1: own})
                self.assertTrue(evaluate.ileum_below_colon_possible(R, Y1))
                held_by_route(self, assessed(R, code, number))
