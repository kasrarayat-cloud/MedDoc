"""Round r3's repair of int6's residual, lane rules4 (DECISIONS D327 (1); build-v2/a2b/r3b/r3e/rules4/NOTES.md): a
colonoscopy code needs a colon to traverse, and the record may leave none in two more ways. TEXT-ONLY and SYNTHETIC:
every note is written for these tests (fictional clinicians), every pass-1 answer is built by hand with test_settle's
builders and every pass-2 answer by test_r2cl_lesion's faithful oracle, every other FactSet in code; nothing is sent.

The rule (evaluate.whole_colon_absent_possible, read wherever D324 (5) read the colon filed absent as a whole): an
anatomy entry whose subtype may be ileorectal or ileoanal (an anastomosis joining the ileum below the colon), or entries
that may be surgically absent whose union may cover every segment of the colon (the anatomy table's five; a side counts
as the segments it holds), hold 45378-45398 and 44388-44408 with the route table's own hold (44406 and 44407 with
LOWER's class route hold, as D325 (2) built them); a colon that may remain leaves the code exactly as int6 decides it.
- ResidualTests: int6's residual (int6 NOTES 9, the rules lane's Q1: v8, v9, v10), each the verifier's input word for
  word - READY on int6 (build-v2/a2b/r3b/r3d/int6), held here.
- SubtypeTests (the rule's first case), SegmentTests (its second), RangeTests (both ranges, LOWER, an open session, the
  words, the plan), GeneralityTests (constructed notes end to end, each holding or left as before exactly as the rule
  says), MonotonicityTests (P-MONO: no 9.4 weakening releases a held scene).
- The boundary methods (names ending ``_as_before``) name nothing int6 lacks, so they run green on int6 too: what the
  rule must leave alone is pinned on both trees.
"""
from __future__ import annotations

import itertools
from dataclasses import replace

from django.test import SimpleTestCase

from studio.interpretation.contract import types as ct
from studio.interpretation.engine import anatomy, asking, catalogue, evaluate, questions
from studio.interpretation.engine import facts as F
from studio.interpretation.engine.types import Id
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_r2cl_lesion as R2CL
from tests.v2 import test_r3c_rules as RR
from tests.v2 import test_r3d_rules as RD
from tests.v2.test_settle import answer, event, fact, frame, labelled, opening, session, src

A, LM, EX = ct.Attribute, ct.Landmark, ct.Extent
AT, AP, SUB = ct.AnatomyType, ct.Approach, ct.AnastomosisSubtype
E2, X1 = Id.parse('E2'), Id.parse('X1')
Y1, Y2 = Id.parse('Y1'), Id.parse('Y2')
sup, unres, neg, doubted, contra = EF.sup, EF.unres, EF.neg, EF.doubted, EF.contra
UNAPPRAISED = ct.Reason.UNAPPRAISED
ROUTE = RR.ROUTE                                    # 'coding_rule:stoma_route': the route table's own hold
LOWER_RULE = questions.coding_rule(questions.Rule.LOWER)
T, U = evaluate.Truth.T, evaluate.Truth.U
HELD, READY = 'needs_clarification', 'ready'
TABLE_HOLD, LOWER_HOLD = RD.TABLE_HOLD, RD.LOWER_HOLD
BLOCKED = 'ABSENT (no anatomy entry may be a stoma: the route table)'
held_of, route_row, serving, witnesses, entry_of = RR.held_of, RR.route_row, RR.serving, RD.witnesses, RD.entry_of


def guard_held(R, code: str) -> list:
    """Round r3's round 5 (DECISIONS D330 (1), lane rules6): the lower-GI path guard's hold of ``code``'s route row in
    ``R`` (its session X1), where every arm leaves the route met - the table's own hold when an anatomy entry matches no
    row of the ruled harmless set (evaluate.path_guard, the owning function the pins below move by), else none."""
    return TABLE_HOLD if evaluate.path_guard(catalogue.lower_route(code), R, X1) else []


def properties():
    from tests.v2 import test_properties
    return test_properties


def pass1(text, *, anatomy, approach=None, through=None, reached=(), reached_anatomy=None, place, place_words,
          kind='colonoscopy', act=True):
    """The verifier's pass 1 (verify-L6-generality-L6B-2/l6/v_l6b2.pass1, with its subtype and reached_anatomy fields):
    ``anatomy`` [(id, type, type words, organ or None, organ words[, (subtype, words)])]; ``approach`` (value, words);
    ``through`` (Yid, words); ``reached`` [(extent, words)]; ``reached_anatomy`` (Yid, words); the colonoscopy X1, its
    examination E1 and - ``act`` - E2 two cold-forceps biopsies at ``place``."""
    findings = text.split('\n')[5]
    entries = [{'id': row[0], 'type': fact(row[1], src(['S4'], row[2])),
                'organ': [fact(row[3], src(['S4'], row[4]))] if row[3] else [],
                'subtype': [fact(row[5][0], src(['S4'], row[5][1]))] if len(row) > 5 else [], 'joins': []}
               for row in anatomy]
    exam_status = next(w for w in ('was introduced', 'was inserted', 'was advanced') if w in findings)
    sess = session('X1', fact(kind, src(['S5'], 'colonoscope')), examination=[fact('E1', src(['S5']))],
                   encounter=[fact('this_encounter', frame(['S2']))],
                   approach=[fact(approach[0], src(['S5'], approach[1]))] if approach else [],
                   through=[fact(through[0], src(['S5'], through[1]))] if through else [],
                   reached=[fact(value, src(['S5'], words)) for value, words in reached],
                   reached_anatomy=[fact(reached_anatomy[0], src(['S5'], reached_anatomy[1]))] if reached_anatomy
                   else [])
    acts = [event('E2', ['S6'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S6']))],
                  target__places=[fact(place, src(['S6'], place_words))],
                  technique__device=[fact('cold_forceps', src(['S6'], 'cold forceps'))])] if act else []
    return answer(
        sections=[opening(), labelled('N1', 'S4', 'History:', 'history'),
                  labelled('N2', 'S5', 'Findings:', 'findings')],
        sessions=[sess], anatomy=entries,
        events=[event('E1', ['S5'], 'colonoscope', exam_status, 'examination', session=[fact('X1', src(['S5']))]),
                *acts])


note, IRA, F_IRA, BX2, PER_ANUS = RD.note, RD.IRA, RD.F_IRA, RD.BX2, RD.PER_ANUS
ILEOANAL = 'Total proctocolectomy with a straight ileoanal anastomosis in 2025.'
F_ILEOANAL = 'The colonoscope was inserted per anus, advanced across the ileoanal anastomosis and into the ileum.'
TAC = 'Total abdominal colectomy'
FIVE = ('cecum', 'ascending_colon', 'transverse_colon', 'descending_colon', 'sigmoid_colon')


def absent(index, organ, words=TAC):
    """An anatomy entry Y<index> filed surgically absent at ``organ`` (the History sentence's words)."""
    return (f'Y{index}', 'surgically_absent', words, organ, words)


def case(text, data, code, quote):
    return text, data, (code, quote)


def statuses(text, data, *codes) -> dict:
    found = R2CL.outcomes(text, data, R2CL.FAITHFUL, *codes)
    return {code: found[code][:2] for code, _quote in codes}


# int6's residual (int6 NOTES 9; the rules lane's Q1 and logs/x_residual.log): the verifier's v8, v9 and v10, word for
# word (verify-L6-generality-L6B-2/l6/v_l6b2.py) - 45380 READY with no question on int6
RESIDUAL = {
    'v8 an ileorectal anastomosis filed alone': case(
        note(IRA, F_IRA, BX2),
        pass1(note(IRA, F_IRA, BX2),
              anatomy=[('Y2', 'anastomosis', 'ileorectal anastomosis', None, '',
                        ('ileorectal', 'ileorectal anastomosis'))],
              approach=PER_ANUS, reached=[('ileum', '15 cm into the ileum')],
              reached_anatomy=('Y2', 'across the ileorectal anastomosis'), place='ileum', place_words='ileum'),
        '45380', BX2),
    'v9 an ileoanal anastomosis filed alone': case(
        note(ILEOANAL, F_ILEOANAL, BX2),
        pass1(note(ILEOANAL, F_ILEOANAL, BX2),
              anatomy=[('Y2', 'anastomosis', 'ileoanal anastomosis', None, '', ('ileoanal', 'ileoanal anastomosis'))],
              approach=PER_ANUS, reached=[('ileum', 'into the ileum')],
              reached_anatomy=('Y2', 'across the ileoanal anastomosis'), place='ileum', place_words='ileum'),
        '45380', BX2),
    'v10 the colon filed by its five segments, the anastomosis with no subtype': case(
        note(IRA, F_IRA, BX2),
        pass1(note(IRA, F_IRA, BX2),
              anatomy=[absent(index, organ) for index, organ in enumerate(FIVE, start=3)]
              + [('Y2', 'anastomosis', 'ileorectal anastomosis', None, '')],
              approach=PER_ANUS, reached=[('ileum', '15 cm into the ileum')], place='ileum', place_words='ileum'),
        '45380', BX2),
}


class ResidualTests(SimpleTestCase):
    def test_v8_v9_v10_hold_the_colonoscopy_code_with_the_route_tables_own_hold(self):
        # the must-change pin (D327 (1)): int6 gave 45380 READY with no question on each; held now by the route table's
        # own hold (the coder's), the one cause, and the planner serves no question to the code
        for name, (text, data, (code, quote)) in RESIDUAL.items():
            with self.subTest(case=name):
                self.assertEqual(statuses(text, data, (code, quote))[code], (HELD, (ROUTE,)))
                _claims, _out, R, view = R2CL.run(text, data, R2CL.FAITHFUL)
                self.assertTrue(evaluate.no_colon_possible(R, X1))
                self.assertEqual(serving(asking.plan(R, (), view), code), [])

    def test_v8_v9_v10_settle_as_the_verifier_read_them(self):
        # the inputs reach the rule as filed: v8 and v9 an anastomosis whose subtype is supported ileorectal or ileoanal
        # and no entry filed surgically absent; v10 five entries claimed surgically absent, one per segment, and an
        # anastomosis whose subtype is silent - no entry files the colon as a whole (D324 (5)'s reader is False)
        for name, (text, data, _codes) in RESIDUAL.items():
            with self.subTest(case=name):
                _claims, _out, R, _view = R2CL.run(text, data, R2CL.FAITHFUL)
                self.assertFalse(any(evaluate.colon_absent_possible(R, entry) for entry in R.anatomy))
                types = sorted(F.fact(R, entry, A.TYPE).value.value for entry in R.anatomy)
                if name.startswith('v10'):
                    self.assertEqual(types, ['anastomosis'] + ['surgically_absent'] * 5)
                    self.assertEqual(sorted(F.fact(R, entry, A.ORGAN).value.value for entry in R.anatomy
                                            if F.fact(R, entry, A.ORGAN).value is not None), sorted(FIVE))
                    self.assertTrue(all(F.silent(F.fact(R, entry, A.SUBTYPE)) for entry in R.anatomy))
                else:
                    self.assertEqual(types, ['anastomosis'])
                    subtype = F.fact(R, Y2, A.SUBTYPE)
                    self.assertEqual((subtype.result, subtype.value.value),
                                     (ct.Result.SUPPORTED, 'ileorectal' if name.startswith('v8') else 'ileoanal'))


# === the first case: an anastomosis joining the ileum below the colon =================================================

# Every AnastomosisSubtype -> whether no colon remains beside an anastomosis of it - DECLARED from the ruling's words
# ("an anastomosis joining the ileum to the rectum or the anus"), never computed by the functions under test
NO_COLON_BESIDE = {SUB.ILEORECTAL: True, SUB.ILEOANAL: True, SUB.ILEOCOLIC: False, SUB.COLOCOLIC: False,
                   SUB.COLORECTAL: False, SUB.COLOANAL: False, SUB.GASTROJEJUNAL: False, SUB.GASTRODUODENAL: False,
                   SUB.ESOPHAGOJEJUNAL: False, SUB.ESOPHAGOGASTRIC: False, SUB.HEPATICOJEJUNAL: False,
                   SUB.CHOLEDOCHODUODENAL: False, SUB.PANCREATICOJEJUNAL: False, SUB.OTHER: False}
# The subtype's control names its sibling (contract/claims.SUBTYPE_SIBLINGS, 3.2.3), written out here
SIBLING = {SUB.ILEOCOLIC: SUB.COLOCOLIC, SUB.COLOCOLIC: SUB.ILEOCOLIC, SUB.COLORECTAL: SUB.COLOANAL,
           SUB.COLOANAL: SUB.COLORECTAL, SUB.ILEORECTAL: SUB.ILEOANAL, SUB.ILEOANAL: SUB.ILEORECTAL}
OPEN_DENIAL = 'an open denial (not established)'


def subtype_states(value):
    """Each state of a subtype filed at ``value``: (its fact, the subtypes it may be: None for every one) - DECLARED."""
    other = SUB.OTHER if value is not SUB.OTHER else SUB.ILEOCOLIC
    states = {
        'supported': (sup(value), {value}),
        'claimed (unresolved)': (unres(value, UNAPPRAISED), {value}),
        "a doubt's reading of other": (doubted(value, other), {value, other}),
        "a contradiction's sides beside other": (contra(value, other), {value, other}),
        OPEN_DENIAL: (EF.fact(ct.Result.UNRESOLVED, value, ct.FactState.NEGATED,
                              reasons=(ct.Reason.APPRAISAL_UNCLEAR,)), None),
        'established denied (hold-only)': (neg(value), None),
    }
    if value in SIBLING:
        states["its control's sibling unrejected"] = (unres(value, UNAPPRAISED, options=(SIBLING[value],)),
                                                       {value, SIBLING[value]})
    return states


def subtype_holds(may_be) -> bool:
    # round r3's round 6 (DECISIONS D336 (1) (b)): the census's anastomosis files no joins, so its two unnamed ends are
    # its subtype's own where every subtype it may be names them - else (OTHER among them) every landmark, the ileum
    # below the colon included (moved by evaluate.joins_ileum_below_colon_possible)
    return may_be is None or any(NO_COLON_BESIDE[value] for value in may_be) or SUB.OTHER in may_be


class SubtypeTests(SimpleTestCase):
    def test_the_subtype_table_splits_the_enumeration_and_holds_a_new_member(self):
        # the table: the subtypes joining the ileum below the colon are ileorectal and ileoanal; the listed rest
        # leave the colon as before; the three split AnastomosisSubtype completely, so a member the enumeration gains
        # falls in ILEUM_BELOW_COLON (holds) until it is classified
        self.assertEqual(set(NO_COLON_BESIDE), set(SUB))
        self.assertEqual(evaluate.ILEUM_BELOW_COLON, {value for value, gone in NO_COLON_BESIDE.items() if gone})
        self.assertEqual(evaluate.ILEUM_BELOW_COLON, {SUB.ILEORECTAL, SUB.ILEOANAL})
        listed = evaluate._COLON_REMAINS | evaluate._NOT_OF_THE_COLON
        self.assertEqual(listed | evaluate.ILEUM_BELOW_COLON, set(SUB))
        self.assertFalse(listed & evaluate.ILEUM_BELOW_COLON)
        self.assertFalse(evaluate._COLON_REMAINS & evaluate._NOT_OF_THE_COLON)
        self.assertEqual(evaluate._COLON_REMAINS, {SUB.ILEOCOLIC, SUB.COLOCOLIC, SUB.COLORECTAL, SUB.COLOANAL})

    def test_the_census_every_subtype_every_state_every_colonoscopy_code_through_the_anus(self):
        # every subtype x every filing state, on an anastomosis entry beside a colonoscopy per anus to the terminal
        # ileum: the route row holds every colonoscopy code through the anus with the table's own hold exactly when
        # the state may be ileorectal or ileoanal (an open denial or an established one may be any subtype); else T
        checked = 0
        for value in SUB:
            for s_name, (subtype, may_be) in subtype_states(value).items():
                R = RD.anus_scope(approach=sup(AP.TRANSANAL),
                                  entries={Y2: entry_of(type=sup(AT.ANASTOMOSIS), subtype=subtype)})
                hold = subtype_holds(may_be)
                self.assertEqual(evaluate.ileum_below_colon_possible(R, Y2), hold, (value, s_name))
                # round r3's round 5 (D330 (1), lane rules6): the path guard holds too where the entry matches no row of
                # the ruled harmless set - a subtype that may be OTHER, its joins silent (moved by evaluate.path_guard)
                guarded = hold or bool(guard_held(R, '45380'))
                for code in sorted(evaluate.ANUS_ROUTE_CODES):
                    with self.subTest(subtype=value.value, state=s_name, code=code):
                        row = route_row(R, code)
                        if guarded:
                            self.assertIs(row.truth, U)
                            self.assertEqual(witnesses(row), [(ROUTE, A.TYPE, X1, None)])
                        else:
                            self.assertIs(row.truth, T)
                        checked += 1
        self.assertEqual(checked, sum(len(subtype_states(value)) for value in SUB) * len(evaluate.ANUS_ROUTE_CODES))

    def test_the_subtype_holds_whatever_the_entrys_type(self):
        # a subtype names an anastomosis whatever type pass 1 filed: an ileorectal subtype on an entry whose type is
        # supported anastomosis, claimed, silent, or filed as another type holds 45380 by the table's own hold
        # (the entry's type and organ: each alone leaves the colon as before, so the subtype is what holds)
        types = {'anastomosis, supported': (sup(AT.ANASTOMOSIS), None),
                 'anastomosis, claimed': (unres(AT.ANASTOMOSIS, UNAPPRAISED), None),
                 'other alteration': (sup(AT.OTHER_ALTERATION), None),
                 'surgically absent, the sigmoid': (sup(AT.SURGICALLY_ABSENT), sup(LM.SIGMOID_COLON))}
        for t_name, (type_, organ) in types.items():
            alone = RD.anus_scope(approach=sup(AP.TRANSANAL), entries={Y2: entry_of(type=type_, organ=organ)})
            # round r3's round 5 (D330 (1), lane rules6): alone, an anastomosis whose subtype and joins are silent (the
            # D328 addendum's residual) or another alteration of no stated organ matches no row of the ruled harmless
            # set - the path guard's hold (moved by evaluate.path_guard); the sigmoid filed absent matches one
            self.assertEqual(held_of(alone, '45380'), guard_held(alone, '45380'), t_name)
            for value in (SUB.ILEORECTAL, SUB.ILEOANAL):
                with self.subTest(type=t_name, subtype=value.value):
                    R = RD.anus_scope(approach=sup(AP.TRANSANAL),
                                      entries={Y2: entry_of(type=type_, organ=organ, subtype=sup(value))})
                    self.assertEqual(held_of(R, '45380'), TABLE_HOLD)

    def test_a_silent_subtype_and_every_subtype_that_keeps_a_colon_leave_45380_as_before(self):
        # the boundary (green on int6 too): an anastomosis whose subtype is silent - the common right-hemicolectomy
        # filing - or established at a subtype that keeps a colon or says nothing of it, with its control's sibling
        # unrejected, beside a colonoscopy per anus to the terminal ileum: 45380 READY
        kept = [value for value, gone in NO_COLON_BESIDE.items() if not gone]
        scenes = {'the subtype silent': entry_of(type=sup(AT.ANASTOMOSIS))}
        for value in kept:
            scenes[f'{value.value}, supported'] = entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(value))
            if value in SIBLING:
                scenes[f"{value.value}, its control's sibling unrejected"] = entry_of(
                    type=sup(AT.ANASTOMOSIS), subtype=unres(value, UNAPPRAISED, options=(SIBLING[value],)))
        for name, entry in scenes.items():
            with self.subTest(scene=name):
                R = RD.anus_scope(approach=sup(AP.TRANSANAL), entries={Y2: entry})
                # round r3's round 5 (D330 (1), lane rules6): the subtype silent beside silent joins (the D328 addendum's
                # residual) or OTHER - another pair, its joins silent - matches no row of the ruled harmless set: the
                # path guard holds them (moved by evaluate.path_guard); every subtype that keeps a colon or names the
                # upper tract, its sibling too, stays READY
                held = guard_held(R, '45380')
                # round r3's round 6 (DECISIONS D336 (1) (b)): the pancreaticojejunal subtype has no control (3.2.3
                # pairs it with no sibling), so it never decides a release - held too (moved by evaluate.path_guard)
                self.assertEqual(bool(held), name in ('the subtype silent', 'other, supported',
                                                      'pancreaticojejunal, supported'))
                self.assertEqual(held_of(R, '45380'), held)
                self.assertIs(route_row(R, 45380).truth, U if held else T)


# === the second case: the colon filed absent by its segments or sides =================================================

# The anatomy table's colon (Region.COLON) split into its four kinds, and each landmark -> the segments its absence
# files absent ("a side counts as its segments") - DECLARED from engine/anatomy's containment as the ruling reads it
SEGMENTS = frozenset({LM.CECUM, LM.ASCENDING_COLON, LM.TRANSVERSE_COLON, LM.DESCENDING_COLON, LM.SIGMOID_COLON})
SIDES = frozenset({LM.RIGHT_COLON, LM.LEFT_COLON, LM.PROXIMAL_COLON, LM.DISTAL_COLON})
POINTS = frozenset({LM.APPENDICEAL_ORIFICE, LM.ILEOCECAL_VALVE, LM.HEPATIC_FLEXURE, LM.SPLENIC_FLEXURE,
                    LM.RECTOSIGMOID})
SEGMENTS_OF = {
    LM.COLON: SEGMENTS,
    LM.RIGHT_COLON: {LM.CECUM, LM.ASCENDING_COLON}, LM.LEFT_COLON: {LM.DESCENDING_COLON, LM.SIGMOID_COLON},
    LM.PROXIMAL_COLON: {LM.CECUM, LM.ASCENDING_COLON, LM.TRANSVERSE_COLON},
    LM.DISTAL_COLON: {LM.DESCENDING_COLON, LM.SIGMOID_COLON},
    **{segment: {segment} for segment in SEGMENTS}, **{point: set() for point in POINTS},
}
# DECISIONS D328's addendum (rules4 Q2, fail-closed): when both sides of the colon may be absent the transverse colon may
# be absent too, so the sides cover the colon - DECLARED: the right colon's segments and the left colon's (every cover
# of the five covers both sides). Round r3's fourth repair (lane rules5) moved this census's oracle to it.
BOTH_SIDES = frozenset(SEGMENTS_OF[LM.RIGHT_COLON] | SEGMENTS_OF[LM.LEFT_COLON])


def covered(organs) -> set:
    return set().union(*(SEGMENTS_OF.get(organ, set()) for organ in organs))


def absences(*organs, type_=None):
    """Anatomy entries Y3.. each filed surgically absent (``type_``, supported by default) at one of ``organs``."""
    return {Id.parse(f'Y{index}'): entry_of(type=type_ if type_ is not None else sup(AT.SURGICALLY_ABSENT),
                                            organ=organ if isinstance(organ, EF.Fact) else sup(organ))
            for index, organ in enumerate(organs, start=3)}


class SegmentTests(SimpleTestCase):
    def test_the_segment_table_splits_the_colon_region(self):
        # the five segments; with the colon itself, its four sides and the points within or between segments they split
        # every landmark of anatomy.Region.COLON, so a colon landmark the table gains fails here until it is classified
        self.assertEqual(evaluate.COLON_SEGMENTS, SEGMENTS)
        colon = {landmark for landmark in LM if anatomy.region(landmark) is anatomy.Region.COLON}
        kinds = ({LM.COLON}, SIDES, SEGMENTS, POINTS)
        self.assertEqual(set().union(*kinds), colon)
        self.assertEqual(sum(len(kind) for kind in kinds), len(colon))
        for side in SIDES | {LM.COLON}:  # a side holds segments; a segment and a point hold none
            self.assertTrue({segment for segment in SEGMENTS if anatomy.contains(side, segment)}, side)
        for place in SEGMENTS | POINTS:
            self.assertFalse({segment for segment in SEGMENTS if anatomy.contains(place, segment)}, place)

    def test_a_side_counts_as_its_segments_and_a_point_as_none(self):
        # one entry supported surgically absent at every landmark: its one reading files absent exactly the declared
        # segments (the colon all five; the right colon the cecum and the ascending colon; a flexure none; any place
        # outside the colon none)
        for organ in LM:
            with self.subTest(organ=organ.value):
                R = RD.anus_scope(entries=absences(organ))
                self.assertEqual(evaluate._absent_readings(R, Id.parse('Y3')),
                                 {frozenset(SEGMENTS_OF.get(organ, set()))})

    def test_the_census_every_set_of_absences_of_the_segments_sides_and_a_flexure(self):
        # every subset of the five segments, the four sides and a flexure, each filed absent by an entry of its own,
        # beside a colonoscopy per anus to the terminal ileum: the colon is gone exactly when the declared segments
        # cover both sides (BOTH_SIDES: D328's addendum Q2 - was "all five") - then every colonoscopy code through the
        # anus is held by the table's own hold; else T
        pool = sorted(SEGMENTS | SIDES | {LM.HEPATIC_FLEXURE}, key=lambda landmark: landmark.value)
        checked = 0
        for size in range(len(pool) + 1):
            for organs in itertools.combinations(pool, size):
                R = RD.anus_scope(approach=sup(AP.TRANSANAL), entries=absences(*organs))
                gone = covered(organs) >= BOTH_SIDES
                with self.subTest(organs=[organ.value for organ in organs]):
                    self.assertEqual(evaluate.segments_absent_possible(R), gone)
                    self.assertEqual(evaluate.no_colon_possible(R, X1), gone)
                    row = route_row(R, 45380)
                    if gone:
                        self.assertEqual((row.truth, witnesses(row)), (U, [(ROUTE, A.TYPE, X1, None)]))
                    else:
                        self.assertIs(row.truth, T)
                checked += 1
        self.assertEqual(checked, 2 ** len(pool))

    def test_each_entry_is_read_fail_closed(self):
        # one entry's type and organ in every filing state (DECLARED: the segments each may file absent), beside four
        # segments supported absent - the fifth, the cecum, covered exactly when the entry may file it absent
        # (the type's fact, whether it may be surgically absent, whether it may be an ileal pouch - D325 (2)'s own
        # case, which holds the anus route whatever the organ)
        types = {'supported': (sup(AT.SURGICALLY_ABSENT), True, False),
                 'claimed (unresolved)': (unres(AT.SURGICALLY_ABSENT, UNAPPRAISED), True, False),
                 "a doubt's reading": (doubted(AT.OTHER_ALTERATION, AT.SURGICALLY_ABSENT), True, False),
                 "a contradiction's side": (contra(AT.ANASTOMOSIS, AT.SURGICALLY_ABSENT), True, False),
                 'silent': (None, True, True),
                 'established not an anastomosis (hold-only)': (neg(AT.ANASTOMOSIS), True, True),
                 'an anastomosis, supported': (sup(AT.ANASTOMOSIS), False, False),
                 'a stoma, supported': (sup(AT.STOMA), False, False)}
        organs = {'the cecum, supported': (sup(LM.CECUM), True),
                  'the cecum, claimed': (unres(LM.CECUM, UNAPPRAISED), True),
                  "the valve claimed, a doubt's reading of the cecum": (doubted(LM.ILEOCECAL_VALVE, LM.CECUM), True),
                  "a contradiction's sides the valve and the right colon": (
                      contra(LM.ILEOCECAL_VALVE, LM.RIGHT_COLON), True),
                  'the proximal colon, supported': (sup(LM.PROXIMAL_COLON), True),
                  'silent': (None, True),
                  'established not the rectum (hold-only)': (neg(LM.RECTUM), True),
                  'an open denial of the sigmoid': (
                      EF.fact(ct.Result.UNRESOLVED, LM.SIGMOID_COLON, ct.FactState.NEGATED,
                              reasons=(ct.Reason.APPRAISAL_UNCLEAR,)), True),
                  'the valve, supported (a point of the cecum)': (sup(LM.ILEOCECAL_VALVE), False),
                  'the appendiceal orifice, claimed': (unres(LM.APPENDICEAL_ORIFICE, UNAPPRAISED), False),
                  'the hepatic flexure, supported': (sup(LM.HEPATIC_FLEXURE), False),
                  'the terminal ileum, supported': (sup(LM.TERMINAL_ILEUM), False),
                  'other, supported': (sup(LM.OTHER), False)}
        four = absences(LM.ASCENDING_COLON, LM.TRANSVERSE_COLON, LM.DESCENDING_COLON, LM.SIGMOID_COLON)
        for (t_name, (type_, t_absent, pouch)), (o_name, (organ, o_cecum)) in itertools.product(types.items(),
                                                                                            organs.items()):
            with self.subTest(type=t_name, organ=o_name):
                R = RD.anus_scope(approach=sup(AP.TRANSANAL), entries={**four, Y1: entry_of(type=type_, organ=organ)})
                self.assertEqual(evaluate.segments_absent_possible(R), t_absent and o_cecum)
                # round r3's round 5 (D330 (1), lane rules6): beside them the path guard holds an entry that matches no
                # row of the ruled harmless set - a type that may be another alteration or an anastomosis of no subtype
                # or joins, an organ silent or unreadable (moved by evaluate.path_guard)
                self.assertEqual(held_of(R, '45380'), TABLE_HOLD if (t_absent and o_cecum) or pouch
                                 else guard_held(R, '45380'))

    def test_one_reading_of_the_entries_together_must_cover_every_segment(self):
        # "whose union may cover": one reading of all the entries at once - an entry that may be either of two sides
        # completes the cover as either, and two such entries may be both sides between them; held by the table's own
        # hold exactly then
        right_or_left = contra(LM.RIGHT_COLON, LM.LEFT_COLON)
        held = {'either side beside the transverse, descending and sigmoid colon (the right completes it)':
                    absences(right_or_left, LM.TRANSVERSE_COLON, LM.DESCENDING_COLON, LM.SIGMOID_COLON),
                'either side beside the cecum, the ascending and the transverse colon (the left completes it)':
                    absences(right_or_left, LM.CECUM, LM.ASCENDING_COLON, LM.TRANSVERSE_COLON),
                'two entries each either side, beside the transverse colon': absences(
                    right_or_left, right_or_left, LM.TRANSVERSE_COLON),
                "a doubt's reading of the left colon beside the right, then the transverse colon": absences(
                    doubted(LM.RIGHT_COLON, LM.LEFT_COLON), LM.RIGHT_COLON, LM.TRANSVERSE_COLON)}
        for name, entries in held.items():
            with self.subTest(case=name):
                R = RD.anus_scope(approach=sup(AP.TRANSANAL), entries=entries)
                self.assertTrue(evaluate.segments_absent_possible(R))
                self.assertEqual(held_of(R, '45380'), TABLE_HOLD)

    def test_the_census_two_entries_of_one_or_two_readings_beside_the_transverse_colon(self):
        # every pair of entries, each supported at one of the places that file segments (and a flexure) or contradicted
        # between two of them, beside the transverse colon filed absent: held exactly when some choice of one reading
        # per entry covers all five - computed here by brute force over the declared SEGMENTS_OF, never by the DP
        places = sorted(set(SEGMENTS_OF) - POINTS | {LM.HEPATIC_FLEXURE}, key=lambda landmark: landmark.value)
        states = [((place,), sup(place)) for place in places]
        states += [((one, other), contra(one, other)) for one, other in itertools.combinations(places, 2)]
        checked = held = 0
        for (first, f_fact), (second, s_fact) in itertools.product(states, repeat=2):
            gone = any(covered((a, b, LM.TRANSVERSE_COLON)) >= SEGMENTS for a in first for b in second)
            # round r3's round 7 (DECISIONS D342 (1) (a)): a pass-1 contradiction is read at its WIDEST - every place, the
            # colon as a whole among them - so a contradicted entry covers the colon alone (moved by evaluate._may_be,
            # settled_narrows; was: one of its two sides per reading)
            gone = gone or len(first) > 1 or len(second) > 1
            R = RD.anus_scope(approach=sup(AP.TRANSANAL), entries=absences(f_fact, s_fact, LM.TRANSVERSE_COLON))
            with self.subTest(first=[p.value for p in first], second=[p.value for p in second]):
                self.assertEqual(evaluate.segments_absent_possible(R), gone)
                self.assertIs(route_row(R, 45380).truth, U if gone else T)
            checked += 1
            held += gone
        self.assertEqual(checked, len(states) ** 2)
        self.assertTrue(0 < held < checked)

    def test_an_entry_that_may_be_either_side_is_never_both_sides_as_before(self):
        # the boundary (green on int6 too): beside the transverse colon, ONE entry contradicted between the right and
        # the left colon (or a doubt of one with a reading of the other) leaves a colon in every reading - 45380 READY.
        # Round r3's round 7 (DECISIONS D342 (1) (a)): a pass-1 contradiction or doubt is read at its WIDEST - every
        # place, the colon as a whole among them - so either entry may file the colon gone: the table's own hold (moved
        # by evaluate._may_be, settled_narrows); the same sides filed as two claims pass 2 was never asked
        # (unappraised) leave a colon in every reading, READY as before
        for name, first in {"a contradiction's sides the right and the left colon": contra(LM.RIGHT_COLON,
                                                                                             LM.LEFT_COLON),
                            "the right colon claimed, a doubt's reading of the left": doubted(LM.RIGHT_COLON,
                                                                                            LM.LEFT_COLON)}.items():
            with self.subTest(case=name):
                R = RD.anus_scope(approach=sup(AP.TRANSANAL), entries=absences(first, LM.TRANSVERSE_COLON))
                self.assertEqual(held_of(R, '45380'), TABLE_HOLD)
                self.assertIs(route_row(R, 45380).truth, U)
        R = RD.anus_scope(approach=sup(AP.TRANSANAL),
                          entries=absences(EF.unres(LM.RIGHT_COLON, ct.Reason.UNAPPRAISED), LM.TRANSVERSE_COLON))
        self.assertEqual(held_of(R, '45380'), [])
        self.assertIs(route_row(R, 45380).truth, T)

    def test_four_segments_of_five_or_sides_that_leave_a_segment_out_leave_45380_as_before(self):
        # the boundary (green on int6 too): every four of the five segments filed absent that keeps a segment of a
        # side, a right hemicolectomy, a sigmoid colectomy and a transverse colectomy, beside a colonoscopy per anus to
        # the terminal ileum: 45380 READY, the route row T. (DECISIONS D328's addendum Q2 moved two scenes to the hold,
        # pinned in test_r3f_rules.AddendumTests.test_q2_both_sides_cover_the_colon: the four segments that keep the
        # transverse colon, and the right and the left colon - both sides, so the transverse may be absent too)
        scenes = {f'four, the {kept.value} kept': absences(*sorted(SEGMENTS - {kept}, key=lambda s: s.value))
                  for kept in SEGMENTS - {LM.TRANSVERSE_COLON}}
        scenes.update({'the proximal colon and the sigmoid': absences(LM.PROXIMAL_COLON, LM.SIGMOID_COLON),
                       'the right colon (a right hemicolectomy)': absences(LM.RIGHT_COLON),
                       'the sigmoid (a sigmoid colectomy)': absences(LM.SIGMOID_COLON),
                       'the transverse colon (a segmental colectomy)': absences(LM.TRANSVERSE_COLON),
                       'every flexure and point': absences(*sorted(POINTS, key=lambda p: p.value))})
        for name, entries in scenes.items():
            with self.subTest(scene=name):
                R = RD.anus_scope(approach=sup(AP.TRANSANAL), entries=entries)
                self.assertEqual(held_of(R, '45380'), [])
                self.assertIs(route_row(R, 45380).truth, T)


# === both ranges: the anus route, the through-stoma codes and LOWER's stoma class =====================================

IRA_ENTRY = entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(SUB.ILEORECTAL))
CASES = {
    'an ileorectal anastomosis': {Y2: IRA_ENTRY},
    'an ileoanal anastomosis, claimed': {Y2: entry_of(type=sup(AT.ANASTOMOSIS),
                                                      subtype=unres(SUB.ILEOANAL, UNAPPRAISED))},
    'the five segments absent': absences(*sorted(SEGMENTS, key=lambda s: s.value)),
    'the proximal and the distal colon absent': absences(LM.PROXIMAL_COLON, LM.DISTAL_COLON),
    'the right colon, the transverse and the left colon claimed absent': absences(
        unres(LM.RIGHT_COLON, UNAPPRAISED), unres(LM.TRANSVERSE_COLON, UNAPPRAISED), unres(LM.LEFT_COLON, UNAPPRAISED),
        type_=unres(AT.SURGICALLY_ABSENT, UNAPPRAISED)),
}


def open_session(R):
    """``R`` with its act E2's session not established (a geometry check failed): SUPPORT row 6's question."""
    return replace(R, events={**R.events, E2: {**R.events[E2], A.SESSION: (unres(X1, RR.GEOMETRY),)}})


class RangeTests(SimpleTestCase):
    def test_each_case_holds_every_colonoscopy_code_through_the_anus(self):
        for name, entries in CASES.items():
            R = RD.anus_scope(approach=sup(AP.TRANSANAL), entries=entries)
            self.assertTrue(evaluate.whole_colon_absent_possible(R), name)
            for code in sorted(evaluate.ANUS_ROUTE_CODES):
                with self.subTest(case=name, code=code):
                    row = route_row(R, code)
                    self.assertEqual((row.truth, witnesses(row)), (U, [(ROUTE, A.TYPE, X1, None)]))
            for code in ('45378', '45380'):  # decide: the one held fact is the table's own hold
                with self.subTest(case=name, decide=code):
                    self.assertEqual(held_of(R, code), TABLE_HOLD)
            plan = asking.plan(R, ())
            self.assertEqual(serving(plan, '45380'), [], name)
            self.assertIn(BLOCKED, plan.blocked)

    def test_each_case_holds_every_through_stoma_code_whatever_its_colonic_route(self):
        # 44388-44405 and 44408 through a stoma established, the approach supported through it: int6 gave the route T on
        # a cecal reach through an ileostomy, and on the organ arm of a colostomy established in the sigmoid; beside
        # each case no colon remains to traverse - the route row holds by the table's own hold, the code with it
        for name, entries in CASES.items():
            for s_name, scope in {'a cecal reach through an ileostomy': dict(reached=(sup(EX.CECUM),),
                                                                            organ=sup(LM.ILEUM)),
                                  'a colostomy established in the sigmoid, to the valve': dict(
                                      reached=(sup(EX.ILEOCECAL_VALVE),), organ=sup(LM.SIGMOID_COLON))}.items():
                R = RR.stoma_scope(entries=entries, **scope)
                self.assertFalse(evaluate.colonic_route(R, X1), (name, s_name))
                for code in sorted(evaluate.STOMA_ROUTE_CODES):
                    with self.subTest(case=name, scope=s_name, code=code):
                        row = route_row(R, code)
                        self.assertEqual((row.truth, witnesses(row)), (U, [(ROUTE, A.TYPE, X1, None)]))
                self.assertEqual(held_of(R, '44389'), TABLE_HOLD)
                self.assertEqual(serving(asking.plan(R, ()), '44389'), [])

    def test_an_open_cecal_reach_through_a_stoma_beside_a_case_is_never_asked(self):
        # the witness: beside a case a true answer that the scope reached the cecum would not give a colonic route, so
        # the open reach is not asked (D324 (5)'s colon filed absent reads so already) - the table's own hold, nothing
        # served to the code
        for name, entries in CASES.items():
            with self.subTest(case=name):
                R = RR.stoma_scope(reached=(unres(EX.CECUM, UNAPPRAISED),), organ=sup(LM.ILEUM), entries=entries)
                self.assertEqual(witnesses(route_row(R, 44389)), [(ROUTE, A.TYPE, X1, None)])
                self.assertEqual([spec for spec in serving(asking.plan(R, ()), '44389')
                                  if spec.attribute is A.REACHED], [])

    def test_each_case_holds_44406_and_44407_by_lowers_class_route_hold(self):
        # LOWER's stoma class (D325 (2), as built: the class's own route hold, coding_rule:lower): a cecal reach through
        # an ileostomy, or a colostomy established in the colon, READY on int6, held beside each case
        for name, entries in CASES.items():
            for s_name, scope in {'a cecal reach through an ileostomy': dict(organ=sup(LM.ILEUM)),
                                  'a colostomy established in the sigmoid': dict(organ=sup(LM.SIGMOID_COLON))}.items():
                with self.subTest(case=name, scope=s_name):
                    self.assertEqual(held_of(RD.eus_stoma(sup(EX.CECUM), entries=entries, **scope), '44406'),
                                     LOWER_HOLD)
                    self.assertEqual(held_of(RD.eus_stoma(sup(EX.CECUM), entries=entries, fna=True, **scope),
                                             '44407'), LOWER_HOLD)
                    # an open reach that may be the cecum is no release here: LOWER's own question beside the hold
                    held = evaluate.decide('44406', (), RD.eus_stoma(unres(EX.CECUM, UNAPPRAISED), entries=entries,
                                                                     **scope)).held_facts
                    self.assertIn(('procedure', LOWER_RULE), [(h.fact, h.cause) for h in held])

    def test_an_acts_open_session_beside_a_case_keeps_the_tables_hold(self):
        # D312 checker S3's principle: beside a case no session the act may be in leaves a colon, so the table's own
        # hold (about the act) stands whatever the session, and nothing is asked through it
        for name, entries in CASES.items():
            for range_, R in {'the anus': open_session(RD.anus_scope(approach=sup(AP.TRANSANAL), entries=entries)),
                              'a stoma': open_session(RR.stoma_scope(reached=(sup(EX.CECUM),), organ=sup(LM.ILEUM),
                                                                     entries=entries))}.items():
                code = 45380 if range_ == 'the anus' else 44389
                with self.subTest(case=name, route=range_):
                    self.assertEqual(witnesses(route_row(R, code)), [(ROUTE, A.TYPE, E2, None)])
                    self.assertEqual(serving(asking.plan(R, ()), str(code)), [])

    def test_the_hold_is_the_route_tables_own_worded_as_before(self):
        # D320 (i): no new words - the route table's own no-stoma hold for both ranges, LOWER's class hold for 44406
        no_stoma = EF.colonoscopy()
        no_stoma.sessions[X1][A.APPROACH] = (sup(AP.THROUGH_STOMA),)
        old = evaluate.decide('44394', (), no_stoma.build()).held_facts
        shape = lambda held: [(h.fact, h.cause, h.attribute, h.subject, h.kind, h.result, h.rank) for h in held]  # noqa
        for name, entries in CASES.items():
            with self.subTest(case=name):
                new = evaluate.decide('45380', (), RD.anus_scope(approach=sup(AP.TRANSANAL),
                                                                 entries=entries)).held_facts
                stoma = evaluate.decide('44389', (), RR.stoma_scope(reached=(sup(EX.CECUM),), organ=sup(LM.ILEUM),
                                                                    entries=entries)).held_facts
                self.assertEqual(shape(new), shape(old))
                self.assertEqual(shape(stoma), shape(old))
                self.assertEqual(questions.message_of(new[0], evaluate.code_facts('45380')),
                                 questions.message_of(old[0], evaluate.code_facts('44394')))
                lower = evaluate.decide('44406', (), RD.eus_stoma(sup(EX.CECUM), organ=sup(LM.ILEUM),
                                                                  entries=entries)).held_facts
                self.assertEqual(questions.message_of(lower[0], evaluate.code_facts('44406')),
                                 questions.MessageId.EXAMINATION_ROUTE)

    def test_a_colon_that_remains_leaves_both_ranges_as_before(self):
        # the boundary (green on int6 too): beside an anastomosis whose subtype keeps a colon (ileocolic, colorectal) or
        # is silent, and a segment or a side filed absent, the through-stoma codes keep their colonic route and the
        # anus-route codes their T
        kept = {'an ileocolic anastomosis and the right colon absent': {
                    Y2: entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(SUB.ILEOCOLIC)), **absences(LM.RIGHT_COLON)},
                'a colorectal anastomosis and the sigmoid absent': {
                    Y2: entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(SUB.COLORECTAL)), **absences(LM.SIGMOID_COLON)},
                'an anastomosis of no subtype and four segments absent': {
                    Y2: entry_of(type=sup(AT.ANASTOMOSIS)),
                    **absences(LM.CECUM, LM.ASCENDING_COLON, LM.TRANSVERSE_COLON, LM.DESCENDING_COLON)}}
        for name, entries in kept.items():
            with self.subTest(case=name):
                # round r3's round 5 (D330 (1), lane rules6): the anastomosis of no subtype (and no joins) is the D328
                # addendum's residual, which the path guard holds in all three ranges (moved by evaluate.path_guard)
                guarded = name == 'an anastomosis of no subtype and four segments absent'
                anus = RD.anus_scope(approach=sup(AP.TRANSANAL), entries=entries)
                self.assertEqual(held_of(anus, '45380'), guard_held(anus, '45380'))
                S = RR.stoma_scope(reached=(sup(EX.CECUM),), organ=sup(LM.ILEUM), entries=entries)
                # round r3's round 6 (DECISIONS D336 (1) (b)): the anastomosis of no subtype and no joins may join any
                # two ends, so it leaves no colonic route either (moved by evaluate.joins_ileum_below_colon_possible)
                self.assertEqual(evaluate.colonic_route(S, X1), not guarded)
                self.assertEqual(held_of(S, '44389'), guard_held(S, '44389'))
                E = RD.eus_stoma(sup(EX.CECUM), organ=sup(LM.SIGMOID_COLON), entries=entries)
                # round r3's round 6 (DECISIONS D336 (1) (b)): beside the anastomosis of no subtype and no joins LOWER's
                # own colonic route is not met (its ends may be any two), so LOWER's hold answers before the guard's
                # (moved by evaluate.joins_ileum_below_colon_possible: the same status, an existing reason)
                self.assertEqual(held_of(E, '44406'), LOWER_HOLD if guarded else guard_held(E, '44406'))
                self.assertEqual(bool(guard_held(anus, '45380')), guarded)


# === constructed notes end to end (the task's generality list), each as the rule says =================================

RECTUM_BX = 'Two biopsies of the rectum were taken with cold forceps.'
SB_BX = 'Two biopsies of the small bowel were taken with cold forceps.'
AFFERENT_BX = 'Two biopsies of the afferent limb were taken with cold forceps.'
CECUM_BX = 'Two biopsies of the cecum were taken with cold forceps.'
TI_BX, NTI_BX = RD.TI_BX, RD.NTI_BX
IPAA_ANAST = 'Restorative proctocolectomy with an ileal pouch-anal anastomosis in 2025.'
SIDES_NOTE = 'Total colectomy in 2026: the proximal colon and the distal colon were resected.'
RL_NOTE = 'Total colectomy in 2026: the right colon and the left colon were resected.'
FIVE_NOTE = 'Colectomy in 2026: cecum, ascending, transverse, descending and sigmoid colon resected.'
FOUR_NOTE = 'Subtotal colectomy in 2026 with an ileosigmoid anastomosis; the sigmoid colon remains.'
RHC = 'Right hemicolectomy with an ileocolic anastomosis in 2026.'
F_RHC = ('The colonoscope was inserted per anus and advanced across the ileocolic anastomosis into the '
         'neo-terminal ileum.')
SIG = 'Sigmoid colectomy with a colorectal anastomosis in 2026.'
TRANSVERSE = 'Transverse colectomy with a colocolic anastomosis in 2026.'
F_CECUM = 'The colonoscope was inserted per anus and advanced to the cecum.'
F_TI = 'The colonoscope was inserted per anus and advanced to the terminal ileum.'
F_SB = 'The colonoscope was inserted per anus and advanced 20 cm into the small bowel.'
F_ILEUM = 'The colonoscope was inserted per anus and advanced 20 cm into the ileum.'
F_RECTUM = 'The colonoscope was inserted per anus and advanced to the ileorectal anastomosis; the rectum was examined.'
F_POUCH = 'The colonoscope was inserted per anus, advanced across the anastomosis and into the afferent limb.'
HARTMANN = 'Hartmann procedure (sigmoid colectomy with an end colostomy) in 2026.'
F_COLOSTOMY = 'The colonoscope was introduced through the colostomy and advanced to the cecum.'
SB = [('small_bowel', '20 cm into the small bowel')]
ILEUM = [('ileum', '20 cm into the ileum')]

HOLDS = {
    'g1 a total abdominal colectomy with an IRA, the scope in the rectum': case(
        note(IRA, F_RECTUM, RECTUM_BX),
        pass1(note(IRA, F_RECTUM, RECTUM_BX),
              anatomy=[('Y2', 'anastomosis', 'ileorectal anastomosis', None, '',
                        ('ileorectal', 'ileorectal anastomosis'))],
              approach=PER_ANUS, reached=[('rectum', 'the rectum was examined')],
              reached_anatomy=('Y2', 'advanced to the ileorectal anastomosis'), place='rectum', place_words='rectum'),
        '45380', RECTUM_BX),
    'g2 a total abdominal colectomy with an IRA, the scope into the small bowel': case(
        note(IRA, F_SB, SB_BX),
        pass1(note(IRA, F_SB, SB_BX),
              anatomy=[('Y2', 'anastomosis', 'ileorectal anastomosis', None, '',
                        ('ileorectal', 'ileorectal anastomosis'))],
              approach=PER_ANUS, reached=SB, place='small_bowel', place_words='small bowel'),
        '45380', SB_BX),
    'g3 an IPAA filed as an anastomosis rather than a pouch': case(
        note(IPAA_ANAST, F_POUCH, AFFERENT_BX),
        pass1(note(IPAA_ANAST, F_POUCH, AFFERENT_BX),
              anatomy=[('Y1', 'anastomosis', 'ileal pouch-anal anastomosis', None, '',
                        ('ileoanal', 'ileal pouch-anal anastomosis'))],
              approach=PER_ANUS, reached=[('ileum', 'into the afferent limb')], place='ileum',
              place_words='afferent limb'),
        '45380', AFFERENT_BX),
    'g4 the colon filed absent by sides (the proximal and the distal colon)': case(
        note(SIDES_NOTE, F_SB, SB_BX),
        pass1(note(SIDES_NOTE, F_SB, SB_BX),
              anatomy=[absent(3, 'proximal_colon', 'the proximal colon'),
                       absent(4, 'distal_colon', 'the distal colon')],
              approach=PER_ANUS, reached=SB, place='small_bowel', place_words='small bowel'),
        '45380', SB_BX),
    'g5 the colon filed absent by all five segments, no anastomosis filed': case(
        note(FIVE_NOTE, F_SB, SB_BX),
        pass1(note(FIVE_NOTE, F_SB, SB_BX),
              anatomy=[absent(index, organ, 'Colectomy') for index, organ in enumerate(FIVE, start=3)],
              approach=PER_ANUS, reached=SB, place='small_bowel', place_words='small bowel'),
        '45380', SB_BX),
    # DECISIONS D328's addendum Q2 (round r3's fourth repair, lane rules5) moved g6b here from AS_BEFORE: both sides of
    # the colon may be absent, so the transverse colon may be absent too
    'g6b the colon filed by the right and the left colon (both sides: the transverse may be absent too)': case(
        note(RL_NOTE, F_ILEUM, BX2),
        pass1(note(RL_NOTE, F_ILEUM, BX2),
              anatomy=[absent(3, 'right_colon', 'the right colon'), absent(4, 'left_colon', 'the left colon')],
              approach=PER_ANUS, reached=ILEUM, place='ileum', place_words='ileum'),
        '45380', BX2),
}
AS_BEFORE = {
    'g6 the colon filed absent by four of five segments (the sigmoid kept)': case(
        note(FOUR_NOTE, F_ILEUM, BX2),
        pass1(note(FOUR_NOTE, F_ILEUM, BX2),
              anatomy=[absent(index, organ, 'Subtotal colectomy') for index, organ in enumerate(FIVE[:4], start=3)]
              + [('Y2', 'anastomosis', 'ileosigmoid anastomosis', None, '')],
              approach=PER_ANUS, reached=ILEUM, place='ileum', place_words='ileum'),
        '45380', BX2),
    'g7 a right hemicolectomy to the neo-terminal ileum, the subtype filed': case(
        note(RHC, F_RHC, NTI_BX),
        pass1(note(RHC, F_RHC, NTI_BX),
              anatomy=[absent(1, 'right_colon', 'Right hemicolectomy'),
                       ('Y2', 'anastomosis', 'ileocolic anastomosis', None, '',
                        ('ileocolic', 'ileocolic anastomosis'))],
              approach=PER_ANUS, reached=[('neo_terminal_ileum', 'into the neo-terminal ileum')],
              place='neo_terminal_ileum', place_words='neo-terminal ileum'),
        '45380', NTI_BX),
    'g7b a right hemicolectomy to the neo-terminal ileum, the subtype not filed (the verifier c2)': case(
        note(RHC, F_RHC, NTI_BX),
        pass1(note(RHC, F_RHC, NTI_BX),
              anatomy=[absent(1, 'right_colon', 'Right hemicolectomy'),
                       ('Y2', 'anastomosis', 'ileocolic anastomosis', None, '')],
              approach=PER_ANUS, reached=[('neo_terminal_ileum', 'into the neo-terminal ileum')],
              place='neo_terminal_ileum', place_words='neo-terminal ileum'),
        '45380', NTI_BX),
    'g8 an ordinary colonoscopy to the cecum': case(
        note('Screening; no prior surgery.', F_CECUM, CECUM_BX),
        pass1(note('Screening; no prior surgery.', F_CECUM, CECUM_BX), anatomy=[], approach=PER_ANUS,
              reached=[('cecum', 'advanced to the cecum')], place='cecum', place_words='cecum'),
        '45380', CECUM_BX),
    'g8b an ordinary colonoscopy to the terminal ileum': case(
        note('Screening; no prior surgery.', F_TI, TI_BX),
        pass1(note('Screening; no prior surgery.', F_TI, TI_BX), anatomy=[], approach=PER_ANUS,
              reached=[('terminal_ileum', 'advanced to the terminal ileum')], place='terminal_ileum',
              place_words='terminal ileum'),
        '45380', TI_BX),
    'g8c a sigmoid colectomy with a colorectal anastomosis, to the cecum': case(
        note(SIG, F_CECUM, CECUM_BX),
        pass1(note(SIG, F_CECUM, CECUM_BX),
              anatomy=[absent(1, 'sigmoid_colon', 'Sigmoid colectomy'),
                       ('Y2', 'anastomosis', 'colorectal anastomosis', None, '',
                        ('colorectal', 'colorectal anastomosis'))],
              approach=PER_ANUS, reached=[('cecum', 'advanced to the cecum')], place='cecum', place_words='cecum'),
        '45380', CECUM_BX),
    'g8d a transverse colectomy with a colocolic anastomosis, to the terminal ileum': case(
        note(TRANSVERSE, F_TI, TI_BX),
        pass1(note(TRANSVERSE, F_TI, TI_BX),
              anatomy=[absent(1, 'transverse_colon', 'Transverse colectomy'),
                       ('Y2', 'anastomosis', 'colocolic anastomosis', None, '',
                        ('colocolic', 'colocolic anastomosis'))],
              approach=PER_ANUS, reached=[('terminal_ileum', 'advanced to the terminal ileum')],
              place='terminal_ileum', place_words='terminal ileum'),
        '45380', TI_BX),
    'g9 a through-stoma colonoscopy, the colostomy to the cecum (the attacker control b)': case(
        RR.COLO, RR.colo_answer(), '44389', RR.Q_COLO),
    'g9b a through-stoma colonoscopy after a Hartmann procedure, to the cecum': case(
        RR.HEAD + f'History: {HARTMANN}\nFindings: {F_COLOSTOMY}\n{RR.Q_COLO}\n',
        RR.stoma_answer('end colostomy', 'sigmoid_colon', 'through the colostomy', 'cecum', 'advanced to the cecum',
                        place='transverse_colon', place_words='transverse colon',
                        absent=('sigmoid_colon', 'Hartmann procedure')),
        '44389', RR.Q_COLO),
}


class GeneralityTests(SimpleTestCase):
    def test_the_constructed_variants_the_rule_holds(self):
        # each a colon gone in a way int6 did not read (an IRA or IPAA filed as an anastomosis, the colon filed by sides
        # or by its five segments; g6b both sides, D328's addendum Q2): held, the route table's own hold among the
        # causes, nothing served
        for name, (text, data, (code, quote)) in HOLDS.items():
            with self.subTest(case=name):
                status, causes = statuses(text, data, (code, quote))[code]
                self.assertEqual(status, HELD)
                self.assertIn(ROUTE, causes)
                _claims, _out, R, view = R2CL.run(text, data, R2CL.FAITHFUL)
                self.assertTrue(evaluate.whole_colon_absent_possible(R))
                self.assertEqual(serving(asking.plan(R, (), view), code), [])

    def test_the_constructed_variants_the_rule_leaves_as_before(self):
        # the boundary end to end (green on int6 too): a colon that may remain - four segments of five (the sigmoid
        # kept), a right hemicolectomy (its subtype filed or not), a sigmoid or segmental colectomy, an intact
        # colon to the cecum or the terminal ileum, a colostomy or a Hartmann colostomy scoped to the cecum - READY
        for name, (text, data, (code, quote)) in AS_BEFORE.items():
            with self.subTest(case=name):
                # round r3's round 5 (D330 (1), lane rules6): g6 and g7b file their anastomosis with subtype and joins
                # both silent - the D328 addendum's residual, which the lower-GI path guard holds with the table's hold
                guarded = name.startswith(('g6 ', 'g7b '))
                self.assertEqual(statuses(text, data, (code, quote))[code], (HELD, (ROUTE,)) if guarded else (READY, ()))


# === P-MONO: no 9.4 weakening releases a held scene ===================================================================


class MonotonicityTests(SimpleTestCase):
    def test_no_weakening_releases_a_code_the_rule_holds(self):
        # test_properties.weakenings (ERASING included) from each held scene: the code stays held, and its route row
        # never turns T once the act's session is known
        TP = properties()
        scenes = {
            '45380, an ileorectal anastomosis': (RD.anus_scope(approach=sup(AP.TRANSANAL), entries={Y2: IRA_ENTRY}),
                                                 '45380'),
            '45380, the five segments': (
                RD.anus_scope(approach=sup(AP.TRANSANAL), entries=CASES['the five segments absent']),
                                         '45380'),
            '45380, the proximal and the distal colon': (
                RD.anus_scope(approach=sup(AP.TRANSANAL), entries=CASES['the proximal and the distal colon absent']),
                '45380'),
            '44389, a colostomy beside an ileoanal subtype': (
                RR.stoma_scope(reached=(sup(EX.ILEOCECAL_VALVE),), organ=sup(LM.SIGMOID_COLON),
                               entries={Y2: entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(SUB.ILEOANAL))}), '44389'),
            '44406, a cecal reach beside the five segments': (
                RD.eus_stoma(sup(EX.CECUM), organ=sup(LM.ILEUM), entries=CASES['the five segments absent']), '44406'),
        }
        for name, (R, code) in scenes.items():
            self.assertTrue(evaluate.decide(code, (), R).held_facts, name)
            count = 0
            for label, weak, _what in TP.weakenings(R):
                count += 1
                with self.subTest(case=name, weakening=label):
                    self.assertTrue(evaluate.decide(code, (), weak).held_facts)
                    if code != '44406' and evaluate._session(weak, E2) is not None:
                        self.assertIsNot(route_row(weak, int(code)).truth, T)
            self.assertGreater(count, 15, name)
