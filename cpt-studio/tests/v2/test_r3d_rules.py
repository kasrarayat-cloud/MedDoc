"""Round r3's third repair, lane rules (DECISIONS D325 (2); build-v2/a2b/r3b/r3d/rules/NOTES.md): a colonoscopy code
needs a colon to traverse. TEXT-ONLY and SYNTHETIC: every note is written for these tests (fictional clinicians), every
pass-1 answer is built by hand with test_settle's builders and every pass-2 answer by test_r2cl_lesion's faithful
oracle, every other FactSet in code; nothing is sent anywhere.

Each rule is shown on the finding's own input - red on int5 (build-v2/a2b/r3b/r3c/int5) - on constructed variants of
its class (other forms, values, sessions, codes, weakenings) and on a boundary it must leave alone:
- ValveTests (L6B-1, high, also on int3 and int4): through a stoma, the ileocecal valve counts as a colonic reach only
  when the stoma is established in the colon; from an ileal stoma, or one of an organ not established, only a point at
  or past the cecum counts (evaluate.AT_OR_PAST_CECUM). The finding: a scope through a loop ileostomy's efferent limb to
  the valve gave 44389 READY with no question, and a TRUE answer that the scope reached the valve released it.
- AnusRouteTests (L6B-2, high, also on int3 and int4): a colonoscopy code through the anus (45378-45398) holds with the
  route table's own hold where a colon may not remain - an anatomy entry may file the whole colon surgically absent, an
  entry may be an ileal pouch, or the approach is established or possible through a pouch (evaluate.no_colon_possible):
  a small-bowel reach completes a colonoscopy only when a colon remains. The finding: an ileal pouch after a
  proctocolectomy, reached per anus into the ileum, gave 45380 READY with no question.
- LowerStomaTests (the int5 integrator's Q1, D324 (5)'s range): 44406 and 44407, the EUS colonoscopy codes through a
  stoma, need an established colonic route too (evaluate._lower_colonic), held otherwise by the class's own route hold;
  requirements' LOWER row reads every anatomy entry's organ (P-INDEP's closure).
"""
from __future__ import annotations

import datetime
from dataclasses import replace

from django.test import SimpleTestCase

from studio.interpretation.contract import types as ct
from studio.interpretation.engine import asking, evaluate, questions
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import requirements as RQ
from studio.interpretation.engine.types import Id
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_r2cl_lesion as R2CL
from tests.v2 import test_r3c_rules as RR
from tests.v2.test_settle import answer, event, fact, frame, labelled, opening, session, src

A, LM, EX = ct.Attribute, ct.Landmark, ct.Extent
AT, AP = ct.AnatomyType, ct.Approach
Kind, SessionKind = ct.Kind, ct.SessionKind
E1, E2 = Id.parse('E1'), Id.parse('E2')
X1 = Id.parse('X1')
Y1, Y2, Y3 = Id.parse('Y1'), Id.parse('Y2'), Id.parse('Y3')
sup, unres, neg, doubted, contra = EF.sup, EF.unres, EF.neg, EF.doubted, EF.contra
ROUTE = RR.ROUTE                                    # 'coding_rule:stoma_route': the route table's own hold
LOWER_RULE = questions.coding_rule(questions.Rule.LOWER)
T, U, Fa = evaluate.Truth.T, evaluate.Truth.U, evaluate.Truth.F
HELD, READY = 'needs_clarification', 'ready'
TABLE_HOLD = [('procedure', ROUTE, A.TYPE, 'X1', 'question')]
LOWER_HOLD = [('procedure', LOWER_RULE, A.TYPE, 'X1', 'question')]
UNAPPRAISED = ct.Reason.UNAPPRAISED
held_of, route_row, serving, outcome = RR.held_of, RR.route_row, RR.serving, RR.outcome


def properties():
    from tests.v2 import test_properties
    return test_properties


def witnesses(row) -> list:
    return [(held.cause, held.attribute, held.subject, held.result) for held in row.witnesses]


# === L6B-1: through a stoma, the ileocecal valve is a colonic reach only from a stoma established in the colon ========

LOOP = 'History: Low anterior resection with a diverting loop ileostomy in 2030.\n'                              # S4
BX_I = 'Two biopsies of the ileal mucosa were taken with cold forceps.\n'                                       # S6
# the finding's notes (attack/L6-generality/l6/s12_icv_pipeline.py v1-v3; the verifier's test_verify_l6b1), word for word
ICV = RR.HEAD + LOOP + ('Findings: The colonoscope was introduced through the loop ileostomy into the efferent limb '
                        'and advanced to the ileocecal valve.\n') + BX_I                                       # S5
ICV_NT = RR.HEAD + LOOP + ('Findings: The colonoscope was introduced through the loop ileostomy and advanced to the '
                           'ileocecal valve; the valve was not traversed.\n') + BX_I
ICV_SCOPE = RR.HEAD + LOOP + ('Findings: The colonoscope was introduced through the loop ileostomy into the efferent '
                              'limb and advanced to the ileocecal valve.\n') + 'The ileal mucosa appeared normal.\n'
# the verifier's cost case: a colostomy scope documented as reaching the valve (the stoma's organ never claimed)
COLO_ICV = RR.HEAD + ('History: Sigmoid colectomy with an end colostomy in 2026.\n'
                      'Findings: The colonoscope was introduced through the colostomy and advanced to the ileocecal '
                      'valve.\n'
                      'Two biopsies of the transverse colon were taken with cold forceps.\n')
Q_BX = 'Two biopsies of the ileal mucosa were taken with cold forceps.'
Q_SCOPE = 'The colonoscope was introduced through the loop ileostomy into the efferent limb'
Q_COLO = 'Two biopsies of the transverse colon were taken with cold forceps.'
ICV_REACH = [('ileocecal_valve', 'advanced to the ileocecal valve')]


def scope_answer(stoma_words, organ, approach_words, reached, *, exam_status='was introduced', place=None,
                 place_words='', stations=()):
    """The verifier's pass 1 (test_verify_l6b1.scope_answer): Y1 a stoma of ``organ`` (None: not filed), X1 a
    colonoscopy through it reaching ``reached`` [(extent, words in S5)], its stations [(station, words, state)], E1 its
    examination and - ``place`` given - E2 two cold-forceps biopsies at ``place``."""
    anatomy_ = [{'id': 'Y1', 'type': fact('stoma', src(['S4'], stoma_words)),
                 'organ': [fact(organ, src(['S4'], stoma_words))] if organ else [], 'subtype': [], 'joins': []}]
    events = [event('E1', ['S5'], 'colonoscope', exam_status, 'examination', session=[fact('X1', src(['S5']))])]
    if place is not None:
        events.append(event('E2', ['S6'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S6']))],
                            target__places=[fact(place, src(['S6'], place_words))],
                            technique__device=[fact('cold_forceps', src(['S6'], 'cold forceps'))]))
    return answer(
        sections=[opening(), labelled('N1', 'S4', 'History:', 'history'), labelled('N2', 'S5', 'Findings:', 'findings')],
        sessions=[session('X1', fact('colonoscopy', src(['S5'], 'colonoscope')), examination=[fact('E1', src(['S5']))],
                          encounter=[fact('this_encounter', frame(['S2']))],
                          approach=[fact('through_stoma', src(['S5'], approach_words))],
                          through=[fact('Y1', src(['S5'], approach_words))],
                          reached=[fact(value, src(['S5'], words)) for value, words in reached],
                          stations=[fact(value, src(['S5'], words), state=state) for value, words, state in stations])],
        anatomy=anatomy_, events=events)


VALVE_CASES = {
    # name: (text, pass 1, code, quote) - the finding's v1, v2, v3, the verifier's v3s and its diagnostic scope d1
    'v1 the efferent limb to the valve': (
        ICV, scope_answer('loop ileostomy', 'ileum', 'through the loop ileostomy', ICV_REACH, place='ileum',
                          place_words='ileal mucosa'), '44389', Q_BX),
    'v2 the ileum and the valve both reached': (
        ICV, scope_answer('loop ileostomy', 'ileum', 'through the loop ileostomy',
                          [('ileum', 'into the efferent limb')] + ICV_REACH, place='ileum', place_words='ileal mucosa'),
        '44389', Q_BX),
    'v3 the valve not traversed, the organ not filed': (
        ICV_NT, scope_answer('loop ileostomy', None, 'through the loop ileostomy', ICV_REACH, place='ileum',
                             place_words='ileal mucosa'), '44389', Q_BX),
    'v3s the colon filed not examined': (
        ICV_NT, scope_answer('loop ileostomy', 'ileum', 'through the loop ileostomy', ICV_REACH, place='ileum',
                             place_words='ileal mucosa',
                             stations=[('ileum', 'advanced to the ileocecal valve', 'supported'),
                                       ('colon', 'the valve was not traversed', 'negated')]), '44389', Q_BX),
    'd1 the diagnostic scope (44388 alone)': (
        ICV_SCOPE, scope_answer('loop ileostomy', 'ileum', 'through the loop ileostomy', ICV_REACH), '44388', Q_SCOPE),
}


def missing_reach(claim, role, claim_set):
    """The verifier's question path (s12q): pass 2 gives no verdict on the session's reach claim (C2a, appraisal:missing);
    everything else as test_r2cl_lesion's faithful oracle."""
    if claim.template == 'session.reached' and role == 'claim':
        return None
    return R2CL.FAITHFUL(claim, role, claim_set)


class ValveTests(SimpleTestCase):
    def test_l6b_1_the_findings_notes_hold_the_through_stoma_code_and_nothing_is_asked(self):
        # the must-change pin (L6B-1): int5 gave every one READY with 0 questions; held now by the route table's own
        # hold, and the planner serves no question to the code (the coder's)
        for name, (text, data, code, quote) in VALVE_CASES.items():
            with self.subTest(case=name):
                _claims, _out, R, view = R2CL.run(text, data, R2CL.FAITHFUL)
                self.assertIn(EX.ILEOCECAL_VALVE, [m.value for m in F.members(R, X1, A.REACHED)])
                self.assertFalse(evaluate.colonic_route(R, X1))
                self.assertEqual(outcome(text, data, code, quote), (HELD, (ROUTE,)))
                plan = asking.plan(R, (), view)
                self.assertEqual(serving(plan, code), [])
                self.assertIn('ABSENT (no anatomy entry may be a stoma: the route table)', plan.blocked)

    def test_l6b_1_a_true_answer_that_the_scope_reached_the_valve_never_releases(self):
        # the finding's question path, end to end: pass 2 gives no verdict on the reach (C2a) - int5 asked "In session X1
        # the endoscope itself reached the ileocecal valve." and its TRUE answer released 44389. Now the open valve is
        # no colonic reach through the stoma: nothing serves the code, and an established answer folded leaves it held
        text, data, _code, quote = VALVE_CASES['v1 the efferent limb to the valve']
        _claims, _out, R, view = R2CL.run(text, data, missing_reach)
        reached = F.members(R, X1, A.REACHED)
        self.assertEqual([(m.value, m.result) for m in reached], [(EX.ILEOCECAL_VALVE, ct.Result.UNRESOLVED)])
        self.assertEqual(serving(asking.plan(R, (), view), '44389'), [])
        status, causes, _ = R2CL.outcomes(text, data, missing_reach, ('44389', quote))['44389']
        self.assertEqual((status, ROUTE in causes), (HELD, True))  # beside COLFULL's own appraisal:missing reach
        R_q = F._answered(R, {'questions': [RR.fact_record('X1', A.REACHED, EX.ILEOCECAL_VALVE.value)]})
        self.assertTrue(F.holds(F.members(R_q, X1, A.REACHED)[0], EX.ILEOCECAL_VALVE))
        self.assertFalse(evaluate.colonic_route(R_q, X1))
        self.assertEqual(held_of(R_q, '44389'), TABLE_HOLD)

    def test_the_colonic_reach_through_a_stoma_is_every_colon_point_but_the_valve(self):
        # the table (an enumeration of engine/anatomy's colon region less the ileum's own opening, never a word list)
        self.assertEqual(evaluate.AT_OR_PAST_CECUM, evaluate.COLONIC_REACH - {EX.ILEOCECAL_VALVE})
        self.assertIn(EX.CECUM, evaluate.AT_OR_PAST_CECUM)
        self.assertIn(EX.APPENDICEAL_ORIFICE, evaluate.AT_OR_PAST_CECUM)
        self.assertNotIn(EX.ILEOCECAL_VALVE, evaluate.AT_OR_PAST_CECUM)
        self.assertFalse({EX.ILEUM, EX.TERMINAL_ILEUM, EX.NEO_TERMINAL_ILEUM, EX.SMALL_BOWEL, EX.RECTUM}
                         & evaluate.AT_OR_PAST_CECUM)

    def test_the_valve_alone_never_completes_the_route_from_a_stoma_not_established_colonic(self):
        # the class: every through-stoma code's route row over the valve alone (and the valve beside the small bowel's
        # points), the stoma's organ in every state that is not an established colon segment - never T, and the one
        # witness the route table's own hold on the session
        organs = {'not filed': None, 'claimed ileum (unresolved)': unres(LM.ILEUM, UNAPPRAISED),
                  'ileum': sup(LM.ILEUM), 'terminal ileum': sup(LM.TERMINAL_ILEUM), 'small bowel': sup(LM.SMALL_BOWEL),
                  'claimed sigmoid (unresolved)': unres(LM.SIGMOID_COLON, UNAPPRAISED),
                  "a doubt's reading of the transverse colon": doubted(LM.ILEUM, LM.TRANSVERSE_COLON),
                  'the ileum established not the organ': neg(LM.ILEUM)}
        reaches = {'the valve': (sup(EX.ILEOCECAL_VALVE),),
                   'the ileum and the valve': (sup(EX.ILEUM), sup(EX.ILEOCECAL_VALVE)),
                   'the terminal ileum and the valve': (sup(EX.TERMINAL_ILEUM), sup(EX.ILEOCECAL_VALVE)),
                   'the stoma and the valve': (sup(EX.STOMA), sup(EX.ILEOCECAL_VALVE))}
        checked = 0
        for (o_name, organ), (r_name, reached) in ((o, r) for o in organs.items() for r in reaches.items()):
            R = RR.stoma_scope(reached=reached, organ=organ)
            self.assertFalse(evaluate.colonic_route(R, X1), (o_name, r_name))
            for code in sorted(evaluate.STOMA_ROUTE_CODES):
                with self.subTest(organ=o_name, reach=r_name, code=code):
                    row = route_row(R, code)
                    self.assertIs(row.truth, U)
                    self.assertEqual(witnesses(row), [(ROUTE, A.TYPE, X1, None)])
                    checked += 1
            self.assertEqual(held_of(R, '44389'), TABLE_HOLD)
        self.assertEqual(checked, len(organs) * len(reaches) * len(evaluate.STOMA_ROUTE_CODES))

    def test_the_boundary_the_valve_from_a_colostomy_and_a_point_at_or_past_the_cecum_stay_ready(self):
        # what D325 (2) leaves alone: the valve reached from a stoma ESTABLISHED in the colon (the organ arm, whatever the
        # reach); every point at or past the cecum reached from an ileal stoma or one of an organ not established; the
        # attacker's colostomy to the cecum end to end
        self.assertEqual(outcome(RR.COLO, RR.colo_answer(), '44389', RR.Q_COLO), (READY, ()))
        for organ in (LM.SIGMOID_COLON, LM.DESCENDING_COLON, LM.TRANSVERSE_COLON, LM.COLON):
            with self.subTest(colostomy=organ.value):
                R = RR.stoma_scope(reached=(sup(EX.ILEOCECAL_VALVE),), organ=sup(organ))
                self.assertTrue(evaluate.colonic_route(R, X1))
                self.assertEqual(held_of(R, '44389'), [])
        past = sorted(evaluate.COLONIC_REACH - {EX.ILEOCECAL_VALVE}, key=lambda extent: extent.value)
        for point in past:
            for o_name, organ in {'not filed': None, 'ileum': sup(LM.ILEUM)}.items():
                with self.subTest(point=point.value, organ=o_name):
                    R = RR.stoma_scope(reached=(sup(point),), organ=organ)
                    self.assertTrue(evaluate.colonic_route(R, X1))
                    for code in sorted(evaluate.STOMA_ROUTE_CODES):
                        self.assertIs(route_row(R, code).truth, T)

    def test_the_ruled_cost_a_colostomy_documented_only_to_the_valve_is_held_for_the_coder(self):
        # the verifier's cost case (READY on int5): the fact pass never claims a stoma's organ, so a colostomy scope
        # documented only to the valve has no stoma established in the colon - held by the table's own hold, no question
        data = scope_answer('end colostomy', 'sigmoid_colon', 'through the colostomy', ICV_REACH,
                            place='transverse_colon', place_words='transverse colon')
        _claims, _out, R, view = R2CL.run(COLO_ICV, data, R2CL.FAITHFUL)
        self.assertIsNot(F.fact(R, Y1, A.ORGAN).result, ct.Result.SUPPORTED)
        self.assertEqual(outcome(COLO_ICV, data, '44389', Q_COLO), (HELD, (ROUTE,)))
        self.assertEqual(serving(asking.plan(R, (), view), '44389'), [])

    def test_an_open_reach_is_asked_only_where_it_may_lie_at_or_past_the_cecum(self):
        # the witness: an open reach that may lie at or past the cecum is asked as the reach (a true answer releases);
        # an open reach that may only be the valve (or the ileum) keeps the table's own hold and is never asked
        asked = {'the cecum not established': (unres(EX.CECUM, UNAPPRAISED),),
                 'the valve claimed, a reading of the cecum': (doubted(EX.ILEOCECAL_VALVE, EX.CECUM),),
                 'the valve supported, the ascending colon not established': (
                     sup(EX.ILEOCECAL_VALVE), unres(EX.ASCENDING_COLON, UNAPPRAISED))}
        for name, reached in asked.items():
            with self.subTest(asked=name):
                row = route_row(RR.stoma_scope(reached=reached), 44389)
                self.assertIs(row.truth, U)
                self.assertEqual([(h.fact, h.attribute, h.subject) for h in row.witnesses],
                                 [('extent', A.REACHED, X1)])
        held = {'the valve not established (pass 2 missing)': (unres(EX.ILEOCECAL_VALVE, ct.Reason.APPRAISAL_MISSING),),
                'the valve not established (unappraised)': (unres(EX.ILEOCECAL_VALVE, UNAPPRAISED),),
                'the ileum claimed, a reading of the valve': (doubted(EX.ILEUM, EX.ILEOCECAL_VALVE),),
                "a contradiction's sides the ileum and the valve": (contra(EX.ILEUM, EX.ILEOCECAL_VALVE),)}
        for name, reached in held.items():
            with self.subTest(held=name):
                R = RR.stoma_scope(reached=reached)
                row = route_row(R, 44389)
                if reached[0].result is ct.Result.CONTRADICTED:  # a contradicted reach is COLFULL's rank-1 question
                    self.assertTrue(held_of(R, '44389'))
                    self.assertNotIn(('extent', A.REACHED), [(h.fact, h.attribute) for h in row.witnesses])
                    continue
                self.assertEqual(witnesses(row), [(ROUTE, A.TYPE, X1, None)])
                self.assertEqual([spec for spec in serving(asking.plan(R, ()), '44389')
                                  if spec.attribute is A.REACHED and spec.value == EX.ILEOCECAL_VALVE.value], [])

    def test_no_weakening_releases_a_through_stoma_code_the_valve_rule_holds(self):
        # P-MONO over the rule's own inputs (test_properties.weakenings, ERASING included): from each held valve scene no
        # single weakening makes the route row T (an act's open session is SUPPORT row 6's question)
        TP = properties()
        scenes = {'the valve, the organ not filed': RR.stoma_scope(reached=(sup(EX.ILEOCECAL_VALVE),)),
                  'the ileum and the valve, an ileostomy': RR.stoma_scope(
                      reached=(sup(EX.ILEUM), sup(EX.ILEOCECAL_VALVE)), organ=sup(LM.ILEUM))}
        for name, R in scenes.items():
            self.assertIsNot(route_row(R, 44389).truth, T, name)
            count = 0
            for label, weak, _what in TP.weakenings(R):
                count += 1
                with self.subTest(case=name, weakening=label):
                    self.assertTrue(evaluate.decide('44389', (), weak).held_facts)
                    if evaluate._session(weak, E2) is not None:
                        self.assertIsNot(route_row(weak, 44389).truth, T)
            self.assertGreater(count, 30, name)


# === L6B-2: a colonoscopy code through the anus needs a colon to traverse ============================================


def note(history, findings, act):
    return RR.HEAD + f'History: {history}\n' + f'Findings: {findings}\n' + f'{act}\n'   # S4, S5, S6


def pass1(text, *, anatomy, approach=None, through=None, reached=(), place, place_words, kind='colonoscopy',
          act=True):
    """The verifier's pass 1 (verify-L6-generality-L6B-2/l6/v_l6b2.pass1, equal to the attacker's s14 for its five
    inputs): ``anatomy`` [(id, type, type words, organ or None, organ words[, (subtype, words)])]; ``approach`` (value,
    words); ``through`` (Yid, words); ``reached`` [(extent, words)]; the colonoscopy X1, its examination E1 and - ``act``
    - E2 two cold-forceps biopsies at ``place``."""
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
                   reached=[fact(value, src(['S5'], words)) for value, words in reached])
    acts = [event('E2', ['S6'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S6']))],
                  target__places=[fact(place, src(['S6'], place_words))],
                  technique__device=[fact('cold_forceps', src(['S6'], 'cold forceps'))])] if act else []
    return answer(
        sections=[opening(), labelled('N1', 'S4', 'History:', 'history'), labelled('N2', 'S5', 'Findings:', 'findings')],
        sessions=[sess], anatomy=entries,
        events=[event('E1', ['S5'], 'colonoscope', exam_status, 'examination', session=[fact('X1', src(['S5']))]),
                *acts])


IPAA = 'Total proctocolectomy with an ileal pouch-anal anastomosis in 2025.'
IRA = 'Total abdominal colectomy with an ileorectal anastomosis in 2026.'
BX = 'Two biopsies of the afferent limb were taken with cold forceps.'
BX2 = 'Two biopsies of the ileum were taken with cold forceps.'
ABS_PC = ('Y1', 'surgically_absent', 'Total proctocolectomy', 'colon', 'Total proctocolectomy')
POUCH = ('Y2', 'ileal_pouch', 'ileal pouch-anal anastomosis', None, '')
F_SILENT = 'The colonoscope was advanced through the ileal pouch into the afferent limb of the ileum.'
F_ANUS = ('The colonoscope was inserted per anus, advanced through the ileal pouch and into the afferent limb of the '
          'ileum.')
F_IRA = 'The colonoscope was inserted per anus, advanced across the ileorectal anastomosis and 15 cm into the ileum.'
NTI = [('neo_terminal_ileum', 'into the afferent limb of the ileum')]
ILE = [('ileum', 'into the afferent limb of the ileum')]
PER_ANUS = ('transanal', 'inserted per anus')


def _case(text, data, *codes):
    return text, data, codes


ANUS_CASES = {
    # the finding's five inputs (the attacker's s14 p1-p5) and the verifier's variants of the class (v1, v2, v4, v5,
    # v11) - 45380 or 45378 held on each; 44386 (the pouch code) beside, its status as before
    'p1 an IPAA pouch, the approach silent': _case(
        note(IPAA, F_SILENT, BX), pass1(note(IPAA, F_SILENT, BX), anatomy=[ABS_PC, POUCH], reached=NTI, place='ileum',
                                        place_words='afferent limb'), ('45380', BX), ('44386', BX)),
    'p2 an IPAA pouch, per anus': _case(
        note(IPAA, F_ANUS, BX), pass1(note(IPAA, F_ANUS, BX), anatomy=[ABS_PC, POUCH], approach=PER_ANUS, reached=ILE,
                                      place='ileum', place_words='afferent limb'), ('45380', BX), ('44386', BX)),
    'p3 an ileorectal anastomosis, the colon filed absent': _case(
        note(IRA, F_IRA, BX2),
        pass1(note(IRA, F_IRA, BX2), anatomy=[('Y1', 'surgically_absent', 'Total abdominal colectomy', 'colon',
                                               'Total abdominal colectomy'),
                                              ('Y2', 'anastomosis', 'ileorectal anastomosis', None, '')],
              approach=PER_ANUS, reached=[('ileum', '15 cm into the ileum')], place='ileum', place_words='ileum'),
        ('45380', BX2)),
    'p4 an IPAA pouch, through the pouch': _case(
        note(IPAA, F_SILENT, BX), pass1(note(IPAA, F_SILENT, BX), anatomy=[ABS_PC, POUCH],
                                        approach=('through_pouch', 'through the ileal pouch'), reached=NTI,
                                        place='ileum', place_words='afferent limb'), ('45380', BX), ('44386', BX)),
    'p5 a J-pouch alone, through the pouch': _case(
        note('Ileal J-pouch in place since 2025.',
             'The colonoscope was advanced through the J-pouch into the afferent limb of the ileum.', BX),
        pass1(note('Ileal J-pouch in place since 2025.',
                   'The colonoscope was advanced through the J-pouch into the afferent limb of the ileum.', BX),
              anatomy=[('Y1', 'ileal_pouch', 'Ileal J-pouch', None, '')],
              approach=('through_pouch', 'through the J-pouch'), reached=NTI, place='ileum',
              place_words='afferent limb'), ('45380', BX), ('44386', BX)),
    'v1 through the pouch, naming it': _case(
        note(IPAA, F_SILENT, BX), pass1(note(IPAA, F_SILENT, BX), anatomy=[ABS_PC, POUCH],
                                        approach=('through_pouch', 'through the ileal pouch'),
                                        through=('Y2', 'through the ileal pouch'), reached=NTI, place='ileum',
                                        place_words='afferent limb'), ('45380', BX)),
    'v2 a small-bowel reach': _case(
        note(IPAA, F_SILENT, BX), pass1(note(IPAA, F_SILENT, BX), anatomy=[ABS_PC, POUCH],
                                        approach=('through_pouch', 'through the ileal pouch'),
                                        reached=[('small_bowel', 'into the afferent limb of the ileum')],
                                        place='ileum', place_words='afferent limb'), ('45380', BX)),
    'v4 the absence filed per organ': _case(
        note(IPAA, F_ANUS, BX), pass1(note(IPAA, F_ANUS, BX),
                                      anatomy=[ABS_PC, ('Y3', 'surgically_absent', 'Total proctocolectomy', 'rectum',
                                                        'Total proctocolectomy'), POUCH],
                                      approach=PER_ANUS, reached=ILE, place='ileum', place_words='afferent limb'),
        ('45380', BX)),
    'v5 the colon filed by sides beside the pouch': _case(
        note(IPAA, F_ANUS, BX), pass1(note(IPAA, F_ANUS, BX),
                                      anatomy=[('Y1', 'surgically_absent', 'Total proctocolectomy', 'right_colon',
                                                'Total proctocolectomy'),
                                               ('Y3', 'surgically_absent', 'Total proctocolectomy', 'left_colon',
                                                'Total proctocolectomy'), POUCH],
                                      approach=PER_ANUS, reached=ILE, place='ileum', place_words='afferent limb'),
        ('45380', BX)),
    'v11 a diagnostic pouch exam (45378)': _case(
        note(IPAA, 'The colonoscope was inserted per anus, advanced through the ileal pouch and into the afferent '
                   'limb of the ileum; the mucosa was normal.', 'The examination was otherwise unremarkable.'),
        pass1(note(IPAA, 'The colonoscope was inserted per anus, advanced through the ileal pouch and into the '
                         'afferent limb of the ileum; the mucosa was normal.',
                   'The examination was otherwise unremarkable.'),
              anatomy=[ABS_PC, POUCH], approach=PER_ANUS, reached=ILE, place='ileum', place_words='afferent limb',
              act=False), ('45378', 'the mucosa was normal')),
}
# the case-1 cost the ruling accepts (the verifier's v12, v13): a PARTIAL colectomy pass 1 filed at the organ 'colon'
PARTIAL = 'History of colon cancer; partial colectomy in 2026.'
PARTIAL_CASES = {
    'v12 to the cecum': _case(
        note(PARTIAL, 'The colonoscope was inserted per anus and advanced to the cecum.', Q_COLO),
        pass1(note(PARTIAL, 'The colonoscope was inserted per anus and advanced to the cecum.', Q_COLO),
              anatomy=[('Y1', 'surgically_absent', 'partial colectomy', 'colon', 'partial colectomy')],
              approach=PER_ANUS, reached=[('cecum', 'advanced to the cecum')], place='transverse_colon',
              place_words='transverse colon'), ('45380', Q_COLO)),
    'v13 to the terminal ileum': _case(
        note(PARTIAL, 'The colonoscope was inserted per anus and advanced to the terminal ileum.', Q_COLO),
        pass1(note(PARTIAL, 'The colonoscope was inserted per anus and advanced to the terminal ileum.', Q_COLO),
              anatomy=[('Y1', 'surgically_absent', 'partial colectomy', 'colon', 'partial colectomy')],
              approach=PER_ANUS, reached=[('terminal_ileum', 'advanced to the terminal ileum')],
              place='transverse_colon', place_words='transverse colon'), ('45380', Q_COLO)),
}
# the boundary (the verifier's controls c1, c2 and its other readings v6, v7): a colon remains, or another family
TI_BX = 'Two biopsies of the terminal ileum were taken with cold forceps.'
NTI_BX = 'Two biopsies of the neo-terminal ileum were taken with cold forceps.'
CONTROL_CASES = {
    'c1 an intact colon to the terminal ileum': _case(
        note('Screening; no prior surgery.', 'The colonoscope was inserted per anus and advanced to the terminal ileum.',
             TI_BX),
        pass1(note('Screening; no prior surgery.',
                   'The colonoscope was inserted per anus and advanced to the terminal ileum.', TI_BX),
              anatomy=[], approach=PER_ANUS, reached=[('terminal_ileum', 'advanced to the terminal ileum')],
              place='terminal_ileum', place_words='terminal ileum'), ('45380', TI_BX)),
    'c2 a right hemicolectomy to the neo-terminal ileum': _case(
        note('Right hemicolectomy with an ileocolic anastomosis in 2026.',
             'The colonoscope was inserted per anus and advanced across the ileocolic anastomosis into the '
             'neo-terminal ileum.', NTI_BX),
        pass1(note('Right hemicolectomy with an ileocolic anastomosis in 2026.',
                   'The colonoscope was inserted per anus and advanced across the ileocolic anastomosis into the '
                   'neo-terminal ileum.', NTI_BX),
              anatomy=[('Y1', 'surgically_absent', 'Right hemicolectomy', 'right_colon', 'Right hemicolectomy'),
                       ('Y2', 'anastomosis', 'ileocolic anastomosis', None, '')],
              approach=PER_ANUS, reached=[('neo_terminal_ileum', 'into the neo-terminal ileum')],
              place='neo_terminal_ileum', place_words='neo-terminal ileum'), ('45380', NTI_BX)),
}


def statuses(case) -> dict:
    text, data, codes = case
    found = R2CL.outcomes(text, data, R2CL.FAITHFUL, *codes)
    return {code: found[code][:2] for code, _quote in codes}


def anus_scope(*, reached=(sup(EX.TERMINAL_ILEUM),), approach=None, entries=None, act_session=None):
    """A settled colonoscopy X1 (its approach ``approach``, None: silent) reaching ``reached``, its examination E1 and a
    cold-forceps biopsy E2 of the terminal ileum (45380; its session ``act_session``, a Fact, or X1 supported), with the
    anatomy entries ``entries`` {id: {attribute: fact}}."""
    doc = EF.Doc()
    doc.session(1, SessionKind.COLONOSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER), reached=list(reached),
                approach=approach)
    doc.exam(1)
    doc.act(2, Kind.BIOPSY, places=[sup(LM.TERMINAL_ILEUM)], device=sup(ct.Device.COLD_FORCEPS),
            **({'session': act_session} if act_session is not None else {}))
    doc.anatomy.update({entry: dict(facts) for entry, facts in (entries or {}).items()})
    return doc.build()


def entry_of(**facts):
    """An anatomy entry's facts by attribute name (type, organ, subtype; None or absent: not filed)."""
    names = {'type': A.TYPE, 'organ': A.ORGAN, 'subtype': A.SUBTYPE}
    return {names[name]: (value,) for name, value in facts.items() if value is not None}


# Each entry state: (its facts, whether it may file the whole colon absent, may be an ileal pouch, may be a lower-tract
# stoma) - DECLARED from the ruling's words, never computed by the functions under test
ENTRY_STATES = {
    'no entry': (None, False, False, False),
    'the colon absent, supported': (entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=sup(LM.COLON)), True, False, False),
    'the colon absent, claimed': (entry_of(type=unres(AT.SURGICALLY_ABSENT, UNAPPRAISED),
                                           organ=unres(LM.COLON, UNAPPRAISED)), True, False, False),
    'an absent entry, its organ silent': (entry_of(type=sup(AT.SURGICALLY_ABSENT)), True, False, False),
    "a doubt's reading of the colon absent": (entry_of(type=doubted(AT.OTHER_ALTERATION, AT.SURGICALLY_ABSENT),
                                                       organ=sup(LM.COLON)), True, False, False),
    'the sigmoid absent (a segment)': (entry_of(type=sup(AT.SURGICALLY_ABSENT), organ=sup(LM.SIGMOID_COLON)),
                                       False, False, False),
    'the right colon claimed absent (a segment)': (entry_of(type=unres(AT.SURGICALLY_ABSENT, UNAPPRAISED),
                                                            organ=unres(LM.RIGHT_COLON, UNAPPRAISED)),
                                                   False, False, False),
    'an ileal pouch, supported': (entry_of(type=sup(AT.ILEAL_POUCH)), False, True, False),
    'an ileal pouch, claimed': (entry_of(type=unres(AT.ILEAL_POUCH, UNAPPRAISED)), False, True, False),
    "a doubt's reading of an ileal pouch": (entry_of(type=doubted(AT.OTHER_ALTERATION, AT.ILEAL_POUCH)),
                                            False, True, False),
    "a contradiction's side an ileal pouch": (entry_of(type=contra(AT.ANASTOMOSIS, AT.ILEAL_POUCH)),
                                              False, True, False),
    'the type established not an ileal pouch (hold-only)': (entry_of(type=neg(AT.ILEAL_POUCH)), True, True, False),
    'a gastric pouch (another type)': (entry_of(type=sup(AT.GASTRIC_POUCH)), False, False, False),
    'a Roux limb (another type)': (entry_of(type=sup(AT.ROUX_LIMB)), False, False, False),
    'an ileocolic anastomosis': (entry_of(type=sup(AT.ANASTOMOSIS), subtype=sup(ct.AnastomosisSubtype.ILEOCOLIC)),
                                 False, False, False),
    'an entry whose type is silent': (entry_of(organ=None), True, True, True),
}
# Each approach state: (its fact, possibly through a pouch, its through_stoma reading possible, closed - established
# as another route) - DECLARED; 'through the stoma' is the table's F (the explanation), whatever else. An ESTABLISHED
# denial names no pouch (the record must name the pouch route), so it never opens the pouch case; its weakening, an
# open denial, leaves every route open
APPROACH_STATES = {
    'silent': (None, False, False, False),
    'per anus, supported': (sup(AP.TRANSANAL), False, False, True),
    'through the pouch, supported': (sup(AP.THROUGH_POUCH), True, False, True),
    'through the pouch, claimed': (unres(AP.THROUGH_POUCH, UNAPPRAISED), True, False, False),
    "per anus claimed, a doubt's reading of the pouch": (doubted(AP.TRANSANAL, AP.THROUGH_POUCH), True, False, False),
    "a contradiction's sides per anus and the pouch": (contra(AP.TRANSANAL, AP.THROUGH_POUCH), True, False, False),
    'per anus established denied': (neg(AP.TRANSANAL), False, True, False),
    'through the pouch established denied': (neg(AP.THROUGH_POUCH), False, True, False),
    'through the stoma established denied (D312 boundary)': (neg(AP.THROUGH_STOMA), False, False, True),
    'per anus, an open denial (not established)': (
        EF.fact(ct.Result.UNRESOLVED, AP.TRANSANAL, ct.FactState.NEGATED, reasons=(ct.Reason.APPRAISAL_UNCLEAR,)),
        True, True, False),
    'through the stoma, supported': (sup(AP.THROUGH_STOMA), False, True, False),
}


class AnusRouteTests(SimpleTestCase):
    def test_l6b_2_the_findings_inputs_hold_the_colonoscopy_code_for_the_coder(self):
        # the must-change pin (L6B-2): int5 gave 45380 (45378 on v11) READY with no question on every one; held now by
        # the route table's own hold, and no question serves it; the pouch code 44386 beside keeps its status
        for name, case in ANUS_CASES.items():
            text, data, codes = case
            with self.subTest(case=name):
                found = statuses(case)
                code = codes[0][0]
                self.assertEqual(found[code], (HELD, (ROUTE,)))
                if len(codes) > 1:
                    self.assertEqual(found['44386'][0], HELD)
                _claims, _out, R, view = R2CL.run(text, data, R2CL.FAITHFUL)
                self.assertTrue(evaluate.no_colon_possible(R, X1))
                self.assertEqual(serving(asking.plan(R, (), view), code), [])

    def test_the_ruled_cost_a_partial_colectomy_filed_as_the_colon_holds(self):
        # D325 (2)'s first case, fail-closed: an entry pass 1 filed as the colon surgically absent holds 45380 whatever
        # the reach (the verifier's v12 and v13: READY on int5) - pass 1's misfiling, for the coder
        for name, case in PARTIAL_CASES.items():
            with self.subTest(case=name):
                status, causes = statuses(case)['45380']
                self.assertEqual(status, HELD)
                self.assertIn(ROUTE, causes)  # v12 also by K's anatomy_conflict (a cecal reach beside the colon absent)

    def test_the_boundary_a_colon_that_remains_stays_ready(self):
        # what D325 (2) leaves alone, end to end: an intact colon to the terminal ileum, a right hemicolectomy to the
        # neo-terminal ileum (an ileocolic anastomosis, the right colon filed absent: a colon remains). Round r3's round
        # 5 (DECISIONS D330 (1), lane rules6): c2 files its anastomosis with subtype and joins both silent - the D328
        # addendum's residual, which the lower-GI path guard holds with the table's own hold
        for name, case in CONTROL_CASES.items():
            with self.subTest(case=name):
                self.assertEqual(statuses(case)['45380'],
                                 (HELD, (ROUTE,)) if name.startswith('c2 ') else (READY, ()))

    def test_the_census_every_code_every_entry_state_every_approach(self):
        # the rule over its whole table: every colonoscopy code through the anus x every anatomy entry state x every
        # approach state. The route row is F when the approach is supported through the stoma; else the table's own
        # hold exactly when the entry may file the colon absent or be an ileal pouch, or the approach may be through a
        # pouch; else the approach question exactly when a stoma route is possible; else T (states DECLARED above)
        checked = 0
        for (e_name, (facts, absent, pouch, stoma)), (a_name, (approach, by_pouch, stoma_reading, closed)) in (
                (e, a) for e in ENTRY_STATES.items() for a in APPROACH_STATES.items()):
            R = anus_scope(approach=approach, entries={Y2: facts} if facts is not None else None)
            for code in sorted(evaluate.ANUS_ROUTE_CODES):
                with self.subTest(entry=e_name, approach=a_name, code=code):
                    row = route_row(R, code)
                    if a_name == 'through the stoma, supported':
                        self.assertIs(row.truth, Fa)
                        self.assertEqual([(h.attribute, h.kind.value) for h in row.witnesses],
                                         [(A.APPROACH, 'explanation')])
                    elif absent or pouch or by_pouch:
                        self.assertIs(row.truth, U)
                        self.assertEqual(witnesses(row), [(ROUTE, A.TYPE, X1, None)])
                    elif not closed and (stoma_reading or stoma):
                        self.assertIs(row.truth, U)
                        self.assertEqual([h.attribute for h in row.witnesses], [A.APPROACH])
                    elif a_name == 'through the stoma established denied (D312 boundary)':
                        # round r3's round 5 (DECISIONS D330 (1), lane rules6, R5R-7): an approach filed - here denied -
                        # as anything but per anus establishes no per-anus route: the path guard's table hold
                        self.assertIs(row.truth, U)
                        self.assertEqual(witnesses(row), [(ROUTE, A.TYPE, X1, None)])
                    else:
                        self.assertIs(row.truth, T)
                    checked += 1
        self.assertEqual(checked, len(ENTRY_STATES) * len(APPROACH_STATES) * len(evaluate.ANUS_ROUTE_CODES))

    def test_each_case_holds_the_code_with_the_tables_own_hold_and_nothing_is_asked(self):
        # decide over the three cases, each alone beside a reach into the small bowel: the one held fact is the table's
        # own hold (procedure at RANK row 8, about the session, no fact), the planner serves nothing to the code
        scenes = {
            'the colon claimed absent': anus_scope(entries={Y2: ENTRY_STATES['the colon absent, claimed'][0]}),
            'an ileal pouch': anus_scope(entries={Y2: ENTRY_STATES['an ileal pouch, supported'][0]}),
            'through the pouch, no entry': anus_scope(approach=sup(AP.THROUGH_POUCH)),
            'through the pouch claimed, no entry': anus_scope(approach=unres(AP.THROUGH_POUCH, UNAPPRAISED)),
            'the colon absent beside a cecal reach': anus_scope(
                reached=(sup(EX.CECUM),), entries={Y2: ENTRY_STATES['the colon absent, supported'][0]}),
        }
        for name, R in scenes.items():
            for code in ('45378', '45380'):  # the examination's and the biopsy's codes (E1, E2)
                with self.subTest(case=name, code=code):
                    self.assertEqual(held_of(R, code), TABLE_HOLD)
            plan = asking.plan(R, ())
            self.assertEqual(serving(plan, '45380'), [], name)
            self.assertIn('ABSENT (no anatomy entry may be a stoma: the route table)', plan.blocked)

    def test_a_small_bowel_reach_completes_the_colonoscopy_only_when_a_colon_remains(self):
        # the reach: every point of COLONOSCOPY_FULL_REACH (members unchanged: asking and assess read them) completes
        # 45380 beside an intact colon; beside each case none does - the route row holds whatever the reach
        cases = {'no case': (None, None),
                 'the colon absent': (ENTRY_STATES['the colon absent, claimed'][0], None),
                 'an ileal pouch': (ENTRY_STATES['an ileal pouch, claimed'][0], None),
                 'through a pouch': (None, sup(AP.THROUGH_POUCH))}
        from studio.interpretation.engine import catalogue
        self.assertEqual(catalogue.COLONOSCOPY_FULL_REACH, frozenset({
            EX.CECUM, EX.APPENDICEAL_ORIFICE, EX.ILEOCECAL_VALVE, EX.TERMINAL_ILEUM, EX.ILEUM, EX.NEO_TERMINAL_ILEUM,
            EX.SMALL_BOWEL}))
        for point in sorted(catalogue.COLONOSCOPY_FULL_REACH, key=lambda extent: extent.value):
            for name, (facts, approach) in cases.items():
                with self.subTest(reach=point.value, case=name):
                    R = anus_scope(reached=(sup(point),), approach=approach,
                                   entries={Y2: facts} if facts is not None else None)
                    self.assertEqual(held_of(R, '45380'), [] if name == 'no case' else TABLE_HOLD)

    def test_an_act_whose_session_is_open_beside_an_anatomy_case_keeps_the_tables_hold(self):
        # D312 checker S3's principle (as the through-stoma codes read it): beside an entry that may file the colon
        # absent or be an ileal pouch no session the act may be in leaves a colon, so the hold stays whatever the
        # session and nothing is asked through it; a pouch approach is read once the act's session is known
        open_ = unres(X1, ct.Reason.GEOMETRY_SECTION)
        for name, facts in (('the colon claimed absent', ENTRY_STATES['the colon absent, claimed'][0]),
                            ('an ileal pouch', ENTRY_STATES['an ileal pouch, supported'][0])):
            with self.subTest(case=name):
                R = anus_scope(entries={Y2: facts}, act_session=open_)
                self.assertEqual(witnesses(route_row(R, 45380)), [(ROUTE, A.TYPE, E2, None)])
                self.assertEqual(serving(asking.plan(R, ()), '45380'), [])
        R = anus_scope(approach=sup(AP.THROUGH_POUCH), act_session=open_)
        self.assertIs(route_row(R, 45380).truth, T)  # SUPPORT row 6 holds the code; the route is read once known
        self.assertTrue(held_of(R, '45380'))

    def test_the_hold_is_the_route_tables_own_worded_as_before(self):
        # D320 (i): no new words - the hold is the table's own no-stoma hold (procedure at RANK row 8, about the session,
        # no fact, coding_rule:stoma_route), worded by the same message as a through-stoma code's on a note naming no stoma
        R = anus_scope(entries={Y2: ENTRY_STATES['an ileal pouch, supported'][0]})
        no_stoma = EF.colonoscopy()
        no_stoma.sessions[X1][A.APPROACH] = (sup(AP.THROUGH_STOMA),)
        new = evaluate.decide('45380', (), R).held_facts
        old = evaluate.decide('44394', (), no_stoma.build()).held_facts
        self.assertEqual([(h.fact, h.cause, h.attribute, h.subject, h.kind, h.result, h.rank) for h in new],
                         [(h.fact, h.cause, h.attribute, h.subject, h.kind, h.result, h.rank) for h in old])
        self.assertEqual(questions.message_of(new[0], evaluate.code_facts('45380')),
                         questions.message_of(old[0], evaluate.code_facts('44394')))

    def test_no_weakening_releases_a_colonoscopy_code_a_case_holds(self):
        # P-MONO over the rule's own inputs (test_properties.weakenings, ERASING included): from each held scene no
        # single weakening makes the route row T (an act's open session is SUPPORT row 6's question) or 45380 READY
        TP = properties()
        scenes = {
            'p1 (the colon claimed absent, an ileal pouch, the approach silent)': anus_scope(
                reached=(sup(EX.NEO_TERMINAL_ILEUM),),
                entries={Y1: ENTRY_STATES['the colon absent, claimed'][0],
                         Y2: ENTRY_STATES['an ileal pouch, supported'][0]}),
            'p5 (a lone ileal pouch, through the pouch)': anus_scope(
                reached=(sup(EX.NEO_TERMINAL_ILEUM),), approach=sup(AP.THROUGH_POUCH),
                entries={Y1: ENTRY_STATES['an ileal pouch, supported'][0]}),
            'through the pouch alone': anus_scope(approach=sup(AP.THROUGH_POUCH)),
        }
        for name, R in scenes.items():
            self.assertIsNot(route_row(R, 45380).truth, T, name)
            count = 0
            for label, weak, _what in TP.weakenings(R):
                count += 1
                with self.subTest(case=name, weakening=label):
                    self.assertTrue(evaluate.decide('45380', (), weak).held_facts)
                    if evaluate._session(weak, E2) is not None:
                        self.assertIsNot(route_row(weak, 45380).truth, T)
            self.assertGreater(count, 30, name)


# === the int5 integrator's Q1: 44406 and 44407 (EUS through a stoma) need an established colonic route ===============


def eus_stoma(*reached, approach=sup(AP.THROUGH_STOMA), organ=None, absent=None, entries=None, fna=False):
    """A lower EUS X1 (its examination E1) of the stoma class, reaching ``reached``, its approach ``approach``, Y1 an
    anatomy entry of type stoma supported whose organ is ``organ`` (None: not filed), Y2 - ``absent`` (type, organ) - an
    organ entry, ``entries`` more; ``fna``: E2 an FNA of the rectum (44407's act)."""
    doc = EF.Doc()
    doc.session(1, SessionKind.EUS, tract=sup(ct.Tract.LOWER), reached=list(reached), approach=approach)
    doc.exam(1)
    if fna:
        doc.act(2, Kind.FNA, places=[sup(LM.RECTUM)])
    doc.anatomy[Y1] = {A.TYPE: (sup(AT.STOMA),), **({A.ORGAN: (organ,)} if organ is not None else {})}
    if absent is not None:
        doc.anatomy[Y2] = entry_of(type=absent[0], organ=absent[1])
    doc.anatomy.update(entries or {})
    return doc.build()


class LowerStomaTests(SimpleTestCase):
    def test_q1_an_eus_through_an_ileostomy_into_the_ileum_is_held(self):
        # the integrator's Q1 (int5 NOTES 10): an EUS through an end ileostomy into the ileum read 44406 READY (STOMA_REACH
        # holds the ileum); held now by the class's own route hold - the colon was never entered
        for o_name, organ in {'not filed': None, 'claimed ileum': unres(LM.ILEUM, UNAPPRAISED),
                              'ileum': sup(LM.ILEUM)}.items():
            with self.subTest(organ=o_name):
                R = eus_stoma(sup(EX.ILEUM), organ=organ)
                self.assertEqual(held_of(R, '44406'), LOWER_HOLD)
                self.assertEqual(serving(asking.plan(R, ()), '44406'), [])

    def test_the_moved_expectation_the_classs_canonical_input_is_held(self):
        # the expectations D325 (2) moves (test_evaluate's CodeRows.test_lower and LowerApproach, test_gate6's 40
        # generated 44406/44407 cases): a reach to the stoma alone, the stoma's organ never established - READY on int5,
        # held now; 44407 (with its FNA) likewise
        R = eus_stoma(sup(EX.STOMA))
        self.assertEqual(held_of(R, '44406'), LOWER_HOLD)
        self.assertEqual(held_of(eus_stoma(sup(EX.STOMA), fna=True), '44407'), LOWER_HOLD)

    def test_every_non_colonic_reach_holds_both_codes(self):
        # the class: the stoma, every point of the small bowel in STOMA_REACH and the valve, each alone, the stoma's organ
        # in every state that is not an established colon segment; the colon filed absent beside a cecal reach
        from studio.interpretation.engine import catalogue
        reaches = [point for point in catalogue.STOMA_REACH
                   if point not in evaluate.COLONIC_REACH or point is EX.ILEOCECAL_VALVE]
        self.assertEqual(set(reaches), {EX.STOMA, EX.ILEOCECAL_VALVE, EX.TERMINAL_ILEUM, EX.ILEUM,
                                        EX.NEO_TERMINAL_ILEUM, EX.RECTUM})
        organs = {'not filed': None, 'claimed ileum': unres(LM.ILEUM, UNAPPRAISED), 'ileum': sup(LM.ILEUM),
                  'small bowel': sup(LM.SMALL_BOWEL), 'claimed sigmoid': unres(LM.SIGMOID_COLON, UNAPPRAISED)}
        for point in sorted(reaches, key=lambda extent: extent.value):
            for o_name, organ in organs.items():
                with self.subTest(reach=point.value, organ=o_name):
                    self.assertEqual(held_of(eus_stoma(sup(point), organ=organ), '44406'), LOWER_HOLD)
                    self.assertEqual(held_of(eus_stoma(sup(point), organ=organ, fna=True), '44407'), LOWER_HOLD)
        absent = eus_stoma(sup(EX.CECUM), organ=sup(LM.SIGMOID_COLON),
                           absent=(unres(AT.SURGICALLY_ABSENT, UNAPPRAISED), unres(LM.COLON, UNAPPRAISED)))
        self.assertEqual(held_of(absent, '44406'), LOWER_HOLD)

    def test_the_boundary_a_colonic_route_stays_ready_and_the_other_classes_are_unchanged(self):
        # left alone: a stoma established in the colon (any reach in the class), a point at or past the cecum reached
        # from any stoma, the sigmoidoscopic and colonoscopic classes (no route read)
        for name, R in {'a colostomy, to the stoma': eus_stoma(sup(EX.STOMA), organ=sup(LM.SIGMOID_COLON)),
                        'a colostomy, to the valve': eus_stoma(sup(EX.ILEOCECAL_VALVE), organ=sup(LM.DESCENDING_COLON)),
                        'an ileostomy, to the cecum': eus_stoma(sup(EX.CECUM), organ=sup(LM.ILEUM)),
                        'no organ, to the transverse colon': eus_stoma(sup(EX.TRANSVERSE_COLON)),
                        'no organ, the stoma and the sigmoid': eus_stoma(sup(EX.STOMA), sup(EX.SIGMOID_COLON))}.items():
            with self.subTest(case=name):
                self.assertEqual(held_of(R, '44406'), [])
        doc = EF.Doc()
        doc.session(1, SessionKind.EUS, tract=sup(ct.Tract.LOWER), reached=[sup(EX.SIGMOID_COLON)],
                    approach=sup(AP.TRANSANAL))
        doc.exam(1)
        self.assertEqual(held_of(doc.build(), '45341'), [])

    def test_an_open_reach_that_may_be_colonic_is_lowers_own_question_and_a_true_answer_releases(self):
        # an open reach that may lie at or past the cecum, or no reach filed: LOWER's own reach question holds the row
        # alone; an open reach that can only be the stoma keeps the route hold beside it. A true answer that the scope
        # reached the cecum releases 44406; an established ileal answer never does
        for name, reached in {'the cecum not established': (unres(EX.CECUM, UNAPPRAISED),),
                              'no reach filed': ()}.items():
            with self.subTest(case=name):
                held = evaluate.decide('44406', (), eus_stoma(*reached)).held_facts
                self.assertEqual([(h.fact, h.attribute) for h in held], [('extent', A.REACHED)])
        for only in (EX.STOMA, EX.ILEOCECAL_VALVE, EX.TERMINAL_ILEUM):  # open, but never at or past the cecum
            with self.subTest(open_reach=only.value):
                held = evaluate.decide('44406', (), eus_stoma(unres(only, UNAPPRAISED))).held_facts
                self.assertEqual([(h.fact, h.cause) for h in held if h.fact == 'procedure'],
                                 [('procedure', LOWER_RULE)])
        R = eus_stoma(unres(EX.CECUM, UNAPPRAISED))
        R_q = F._answered(R, {'questions': [RR.fact_record('X1', A.REACHED, EX.CECUM.value)]})
        self.assertEqual(held_of(R_q, '44406'), [])
        ileal = eus_stoma(unres(EX.ILEUM, UNAPPRAISED))
        ileal_q = F._answered(ileal, {'questions': [RR.fact_record('X1', A.REACHED, EX.ILEUM.value)]})
        self.assertTrue(F.holds(F.members(ileal_q, X1, A.REACHED)[0], EX.ILEUM))
        self.assertEqual(held_of(ileal_q, '44406'), LOWER_HOLD)

    def test_the_hold_is_the_classs_own_route_hold_worded_as_before(self):
        # D320 (i): the colonic-route hold is the hold the class gives a stoma route with no stoma entry (procedure at
        # RANK row 8, about the session, coding_rule:lower), worded by the same message (EXAMINATION_ROUTE)
        new = evaluate.decide('44406', (), eus_stoma(sup(EX.ILEUM))).held_facts
        doc = EF.Doc()
        doc.session(1, SessionKind.EUS, tract=sup(ct.Tract.LOWER), reached=[sup(EX.ILEUM)],
                    approach=sup(AP.THROUGH_STOMA))
        doc.exam(1)
        old = evaluate.decide('44406', (), doc.build()).held_facts
        self.assertEqual([(h.fact, h.cause, h.attribute, h.subject, h.kind, h.result, h.rank) for h in new],
                         [(h.fact, h.cause, h.attribute, h.subject, h.kind, h.result, h.rank) for h in old])
        self.assertEqual(questions.message_of(new[0], evaluate.code_facts('44406')),
                         questions.MessageId.EXAMINATION_ROUTE)
        self.assertEqual(questions.message_of(old[0], evaluate.code_facts('44406')),
                         questions.MessageId.EXAMINATION_ROUTE)

    def test_no_weakening_releases_44406_the_route_holds(self):
        TP = properties()
        scenes = {'the ileum, an ileostomy': eus_stoma(sup(EX.ILEUM), organ=sup(LM.ILEUM)),
                  'the stoma, the organ not filed': eus_stoma(sup(EX.STOMA))}
        for name, R in scenes.items():
            count = 0
            for label, weak, _what in TP.weakenings(R):
                count += 1
                with self.subTest(case=name, weakening=label):
                    self.assertTrue(evaluate.decide('44406', (), weak).held_facts)
            self.assertGreater(count, 15, name)

    def test_lowers_closure_reads_every_anatomy_entrys_organ(self):
        # P-INDEP (DESIGN-v2 f.3): the colonic route reads the organ, so LOWER's row declares (anatomy, organ) - an organ
        # perturbation that moves 44406 lies inside its closure
        self.assertIn(A.ORGAN, RQ.dependencies('44406').reads[RQ.Role.ANATOMY])
        self.assertIn(A.ORGAN, RQ.dependencies('44407').reads[RQ.Role.ANATOMY])
        before = held_of(eus_stoma(sup(EX.STOMA)), '44406')
        after = held_of(eus_stoma(sup(EX.STOMA), organ=sup(LM.SIGMOID_COLON)), '44406')
        self.assertNotEqual(before, after)
