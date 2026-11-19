"""Round r3's repair, lane rules (DECISIONS D324 (5), (6), (7); build-v2/a2b/r3b/r3c/rules/NOTES.md): the engine's
billing-table and exclusion rules the mandatory adversarial pass over int4 refuted, each repaired as a class rule
(D276). TEXT-ONLY and SYNTHETIC: every note is written for these tests (fictional clinicians), every pass-1 answer is
built by hand with test_settle's builders and every pass-2 answer by test_r2cl_lesion's faithful oracle, every other
FactSet in code; nothing is sent anywhere.

Each rule is shown on the finding's own input - red on int4 (build-v2/a2b/r3b/int4) - on constructed variants of its
class (other forms, values, sessions, families, weakenings) and on a boundary it must leave alone:
- ColonicRouteTests (D324 (5), L6-2, high, also on int3): a through-stoma colonoscopy code (44388-44405, 44408) is READY
  only when the route is COLONIC - the colon as a whole is not filed surgically absent, and the stoma's organ is a colon
  segment or the record establishes a colonic reach through the stoma; an ileal or small-bowel reach alone never
  completes it (the attacker's s06: a scope through an end ileostomy after a proctocolectomy into the ileum gave 44389
  READY with no question). Otherwise the route table's own hold, the coder's, worded as before (D320 (i)) - but where
  the route rests on a reach not established that may be colonic (or on no reach filed) the row's witness is that
  reach, asked as COLFULL's extent row already asks it, so a true answer that the scope reached the colon releases the
  code and no existing question is blocked; beside a colon filed absent the hold stays whatever the act's session.
- StomaOrganTests (D324 (5), R2E-STOMA-ORGAN, low): the stoma-possible closure opens only for a stoma of the lower tract
  (a colon or ileum stoma) or of an organ not established - a gastrostomy established at the stomach beside a
  colonoscopy no longer holds 45378-45398.
- BaseDecisionTests (D324 (6), L2-3, medium): 4.6 runs for a group only when R_base's OWN 4.4 decision reaches it - no
  supporting act, no pending candidate, no found or pending XCHG pair, filed or synthetic - computed by the code path
  evaluate._decide reads a group by (``_read_group``); otherwise the group is held, not documented. Pinned:
  EXCLUDED(R, A) == EXCLUDED(R, empty) over 43276's pairs set apart by a duct, a session and a Q-ABSORB answer.
- StructurePlacementTests (D324 (7), L6-4, medium, a regression of int4's R2E-QB-ANAT repair): the QB clause reads a
  statement's target.structure by one typed table over every Structure member (pairing.STRUCTURE_PLACEMENT): a
  lesion-like structure (a lesion, an ulcer, a mass, a varix, a bleeding site) describes the statement's own target
  lesion and adds no place; a structure with a location of its own holds every place; a member the table does not
  classify counts as located. R2E-QB-ANAT's and QB's scenes stay held.
"""
from __future__ import annotations

import datetime
from dataclasses import replace
from types import MappingProxyType, SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from studio.interpretation.contract import settle
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import asking, evaluate, pairing, questions
from studio.interpretation.engine import assess as AS
from studio.interpretation.engine import facts as F
from studio.interpretation.engine.types import Id, IsoDate, Outcome, Span
from studio.types import EvidenceSpan
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA
from tests.v2 import test_r2cl_lesion as R2CL
from tests.v2.test_settle import answer, event, fact, frame, labelled, lesion, opening, session, src

A, LM, EX = ct.Attribute, ct.Landmark, ct.Extent
Kind, Status, SessionKind = ct.Kind, ct.Status, ct.SessionKind
E1, E2, E3, E4, E5, E6, E7 = (Id.parse(f'E{n}') for n in range(1, 8))
L1, L2 = Id.parse('L1'), Id.parse('L2')
X1, X2 = Id.parse('X1'), Id.parse('X2')
Y1, Y2, Y3 = Id.parse('Y1'), Id.parse('Y2'), Id.parse('Y3')
sup, unres, neg, doubted, contra = EF.sup, EF.unres, EF.neg, EF.doubted, EF.contra
STOMA, ABSENT = ct.AnatomyType.STOMA, ct.AnatomyType.SURGICALLY_ABSENT
THROUGH_STOMA = ct.Approach.THROUGH_STOMA
ROUTE = 'coding_rule:stoma_route'
GEOMETRY = ct.Reason.GEOMETRY_SECTION
DAY = datetime.date(2026, 11, 9)
V = ct.VerdictValue
T = evaluate.Truth.T


def properties():
    """tests/v2/test_properties (imported when a test needs it: it builds its fixtures and its harness)."""
    from tests.v2 import test_properties
    return test_properties


def held_of(R, code: str, kept=()) -> list:
    return [(held.fact, held.cause, held.attribute, str(held.subject), held.kind.value)
            for held in evaluate.decide(code, kept, R).held_facts]


def route_row(R, code: int, event: Id = E2):
    return evaluate._row_colon_route(evaluate._code(str(code)), (Kind.BIOPSY,), R, event)


def serving(plan, code: str) -> list:
    return [spec for spec in plan.specs if code in plan.serves.get(spec.key, ())]


# === (5) D324 (5), L6-2: the through-stoma colonoscopy codes need a colonic route ====================================

HEAD = ('SYNTHETIC COLONOSCOPY REPORT\n'                       # S1
        'Date of service: 03/14/2031\n'                         # S2
        'Endoscopist: Corvin Ashdale, MD (fictional)\n'         # S3
        '\n')
# The finding's input (attack/L6-generality/l6/s06_stoma_ileostomy.py, case a-ileostomy), word for word
ILEO = HEAD + ('History: Total proctocolectomy with an end ileostomy in 2024.\n'                                     # S4
               'Findings: The colonoscope was introduced through the ileostomy and advanced 30 cm into the ileum.\n'  # S5
               'Two biopsies of the ileal mucosa were taken with cold forceps.\n')                                    # S6
# The verifier's diagnostic-only variant (44388): the same scope, nothing taken
ILEO_SCOPE = HEAD + ('History: Total proctocolectomy with an end ileostomy in 2024.\n'                               # S4
                     'Findings: The colonoscope was introduced through the ileostomy and advanced 30 cm into the '
                     'ileum.\n'                                                                                     # S5
                     'The ileal mucosa appeared normal.\n')                                                         # S6
# The attacker's controls: a colostomy to the cecum (case b), a gastrostomy beside a colonoscopy per anus (case c)
COLO = HEAD + ('History: Sigmoid colectomy with an end colostomy in 2026.\n'                                          # S4
               'Findings: The colonoscope was introduced through the colostomy and advanced to the cecum.\n'          # S5
               'Two biopsies of the transverse colon were taken with cold forceps.\n')                               # S6
PEG = HEAD + ('History: Percutaneous gastrostomy tube in place since 2029.\n'                                          # S4
              'Findings: The colonoscope was advanced to the cecum.\n'                                                 # S5
              'Two biopsies of the transverse colon were taken with cold forceps.\n')                                 # S6
Q_ILEO = 'Two biopsies of the ileal mucosa were taken with cold forceps.'
Q_SCOPE = 'The colonoscope was introduced through the ileostomy and advanced 30 cm into the ileum.'
Q_COLO = 'Two biopsies of the transverse colon were taken with cold forceps.'


def stoma_answer(stoma_words, organ, approach_words, reached, reached_words, place=None, place_words='',
                 absent=None):
    """The attacker's pass 1 (s06's ``pass1``): Y1 a stoma (``organ``), Y2 an organ filed surgically absent
    (``absent``: (organ, words)), the colonoscopy X1 through the stoma when ``approach_words``, reaching ``reached``,
    its examination E1, and - ``place`` given - two cold-forceps biopsies E2 there."""
    anatomy = [{'id': 'Y1', 'type': fact('stoma', src(['S4'], stoma_words)),
                'organ': [fact(organ, src(['S4'], stoma_words))], 'subtype': [], 'joins': []}]
    if absent is not None:
        anatomy.append({'id': 'Y2', 'type': fact('surgically_absent', src(['S4'], absent[1])),
                        'organ': [fact(absent[0], src(['S4'], absent[1]))], 'subtype': [], 'joins': []})
    approach = [fact('through_stoma', src(['S5'], approach_words))] if approach_words else []
    through = [fact('Y1', src(['S5'], approach_words))] if approach_words else []
    events = [event('E1', ['S5'], 'colonoscope', 'was introduced' if approach_words else 'was advanced', 'examination',
                    session=[fact('X1', src(['S5']))])]
    if place is not None:
        events.append(event('E2', ['S6'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S6']))],
                            target__places=[fact(place, src(['S6'], place_words))],
                            technique__device=[fact('cold_forceps', src(['S6'], 'cold forceps'))]))
    return answer(
        sections=[opening(), labelled('N1', 'S4', 'History:', 'history'), labelled('N2', 'S5', 'Findings:', 'findings')],
        sessions=[session('X1', fact('colonoscopy', src(['S5'], 'colonoscope')), examination=[fact('E1', src(['S5']))],
                          encounter=[fact('this_encounter', frame(['S2']))], approach=approach, through=through,
                          reached=[fact(reached, src(['S5'], reached_words))])],
        anatomy=anatomy, events=events)


def ileo_answer(**over):
    return stoma_answer('end ileostomy', 'ileum', 'through the ileostomy', 'ileum', 'into the ileum',
                        **{'place': 'ileum', 'place_words': 'ileal mucosa',
                           'absent': ('colon', 'Total proctocolectomy'), **over})


def colo_answer():
    return stoma_answer('end colostomy', 'sigmoid_colon', 'through the colostomy', 'cecum', 'advanced to the cecum',
                        place='transverse_colon', place_words='transverse colon')


def peg_answer():
    return stoma_answer('Percutaneous gastrostomy tube', 'stomach', '', 'cecum', 'advanced to the cecum',
                        place='transverse_colon', place_words='transverse colon')


def outcome(text, data, code, quote):
    """``code`` proposed alone on ``quote``, end to end (test_r2cl_lesion.outcomes): (status, held causes)."""
    return R2CL.outcomes(text, data, R2CL.FAITHFUL, (code, quote))[code][:2]


def stoma_scope(*, reached=(sup(EX.ILEUM),), organ=None, entry_type=sup(STOMA), absent=None,
                approach=sup(THROUGH_STOMA), entries=None, place=LM.ILEUM):
    """A settled colonoscopy X1 through a stoma (``approach``; None: not filed), reaching ``reached``, its examination E1
    and a cold-forceps biopsy E2 at ``place``: Y1 an anatomy entry of type ``entry_type`` whose organ is ``organ`` (a
    Fact; None: not filed), Y2 - ``absent`` given as (type fact, organ fact or None) - an organ entry pass 1 filed
    (surgically absent by default), and ``entries`` more entries {id: facts}."""
    doc = EF.Doc()
    doc.session(1, SessionKind.COLONOSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER), reached=list(reached),
                approach=approach)
    doc.exam(1)
    doc.act(2, Kind.BIOPSY, places=[sup(place)], device=sup(ct.Device.COLD_FORCEPS))
    doc.anatomy[Y1] = {A.TYPE: (entry_type,), **({A.ORGAN: (organ,)} if organ is not None else {})}
    if absent is not None:
        kind, organ_fact = absent
        doc.anatomy[Y2] = {**({A.TYPE: (kind,)} if kind is not None else {}),
                           **({A.ORGAN: (organ_fact,)} if organ_fact is not None else {})}
    doc.anatomy.update(entries or {})
    return doc.build()


class ColonicRouteTests(SimpleTestCase):
    def test_l6_2_the_findings_input_holds_the_through_stoma_code_for_the_coder(self):
        # the must-change pin (L6-2): the attacker's ileostomy note end to end - pass 1 files Y1 a stoma (its organ the
        # ileum, never claimed: unresolved), Y2 the colon surgically absent (not claimed: unresolved), the colonoscope
        # through the stoma into the ileum (supported). int4 (and int3) gave 44389 READY with no question; held now by
        # the route table's own hold, and the planner asks nothing through it (the coder's)
        _claims, _out, R, view = R2CL.run(ILEO, ileo_answer(), R2CL.FAITHFUL)
        self.assertIs(F.fact(R, Y2, A.TYPE).result, ct.Result.UNRESOLVED)
        self.assertTrue(F.holds(F.fact(R, X1, A.APPROACH), THROUGH_STOMA))
        self.assertEqual([(member.value, member.result) for member in F.members(R, X1, A.REACHED)],
                         [(EX.ILEUM, ct.Result.SUPPORTED)])
        self.assertEqual(outcome(ILEO, ileo_answer(), '44389', Q_ILEO), ('needs_clarification', (ROUTE,)))
        plan = asking.plan(R, (), view)
        self.assertEqual(serving(plan, '44389'), [])
        self.assertIn('ABSENT (no anatomy entry may be a stoma: the route table)', plan.blocked)

    def test_l6_2_the_diagnostic_scope_is_held_too(self):
        # the verifier's class: the same scope with nothing taken (44388 proposed alone) - READY on int4; held now
        data = stoma_answer('end ileostomy', 'ileum', 'through the ileostomy', 'ileum', 'into the ileum',
                            absent=('colon', 'Total proctocolectomy'))
        self.assertEqual(outcome(ILEO_SCOPE, data, '44388', Q_SCOPE), ('needs_clarification', (ROUTE,)))

    def test_every_ileal_or_small_bowel_reach_alone_holds_every_through_stoma_code(self):
        # the class (D324 (5): "an ileal or small-bowel reach alone never completes a through-stoma colonoscopy"): every
        # through-stoma code's route row over every reach of the small bowel, the stoma's organ in every state that is
        # not an established colon segment, with and without the colon filed absent - never T, and the one witness is
        # the route table's own hold on the session
        reaches = {'ileum': EX.ILEUM, 'terminal ileum': EX.TERMINAL_ILEUM, 'neo-terminal ileum': EX.NEO_TERMINAL_ILEUM,
                   'small bowel': EX.SMALL_BOWEL, 'jejunum': EX.JEJUNUM, 'the stoma itself': EX.STOMA,
                   'a stated depth': EX.STATED_DEPTH}
        organs = {'not filed': None, 'claimed ileum (unresolved)': unres(LM.ILEUM, ct.Reason.UNAPPRAISED),
                  'ileum': sup(LM.ILEUM), 'small bowel': sup(LM.SMALL_BOWEL), 'terminal ileum': sup(LM.TERMINAL_ILEUM),
                  'claimed sigmoid (unresolved)': unres(LM.SIGMOID_COLON, ct.Reason.UNAPPRAISED)}
        checked = 0
        for (r_name, reach), (o_name, organ) in ((r, o) for r in reaches.items() for o in organs.items()):
            for absent in (None, (unres(ABSENT, ct.Reason.UNAPPRAISED), unres(LM.COLON, ct.Reason.UNAPPRAISED))):
                R = stoma_scope(reached=(sup(reach),), organ=organ, absent=absent)
                self.assertFalse(evaluate.colonic_route(R, X1))
                for code in sorted(evaluate.STOMA_ROUTE_CODES):
                    with self.subTest(reach=r_name, organ=o_name, absent=absent is not None, code=code):
                        row = route_row(R, code)
                        self.assertIsNot(row.truth, T)
                        self.assertEqual([(held.cause, held.attribute, held.subject, held.result)
                                          for held in row.witnesses], [(ROUTE, A.TYPE, X1, None)])
                        checked += 1
                self.assertEqual(held_of(R, '44389'), [('procedure', ROUTE, A.TYPE, 'X1', 'question')])
        self.assertEqual(checked, 7 * 6 * 2 * len(evaluate.STOMA_ROUTE_CODES))

    def test_a_colon_filed_surgically_absent_holds_whatever_the_reach_or_the_stomas_organ(self):
        # the colon as a whole filed surgically absent, in every state pass 1 and pass 2 may leave it (its type or organ
        # supported, claimed, a doubt's reading, a contradiction's side, silent) - and an established negation of its
        # organ or type, which never rules it out (read to hold only: the fact pass has no negated type form and no
        # control for a negated organ) - held even beside a colonic reach and a colostomy established in the colon
        states = {
            'supported': (sup(ABSENT), sup(LM.COLON)),
            'claimed (unappraised)': (unres(ABSENT, ct.Reason.UNAPPRAISED), unres(LM.COLON, ct.Reason.UNAPPRAISED)),
            'its organ silent': (sup(ABSENT), None),
            "a doubt's reading of the type": (doubted(ct.AnatomyType.OTHER_ALTERATION, ABSENT), sup(LM.COLON)),
            "a contradiction's side of the organ": (sup(ABSENT), contra(LM.SIGMOID_COLON, LM.COLON)),
            'another organ established not absent': (sup(ABSENT), neg(LM.RECTUM)),
            'the colon itself established not absent': (sup(ABSENT), neg(LM.COLON)),
            'the type established not surgically absent': (neg(ABSENT), sup(LM.COLON)),
            'its type silent': (None, sup(LM.COLON)),
            'a pass-1 denial of the type, not established': (
                EF.fact(ct.Result.UNRESOLVED, ABSENT, ct.FactState.NEGATED, reasons=(ct.Reason.APPRAISAL_UNCLEAR,)),
                sup(LM.COLON)),
        }
        for name, absent in states.items():
            for reach in (EX.CECUM, EX.TRANSVERSE_COLON, EX.TERMINAL_ILEUM):
                with self.subTest(state=name, reach=reach.value):
                    R = stoma_scope(reached=(sup(reach),), organ=sup(LM.SIGMOID_COLON), absent=absent)
                    self.assertTrue(evaluate.colon_absent_possible(R, Y2))
                    self.assertFalse(evaluate.colonic_route(R, X1))
                    self.assertEqual(held_of(R, '44389'), [('procedure', ROUTE, A.TYPE, 'X1', 'question')])

    def test_the_boundary_a_colonic_route_stays_ready(self):
        # the boundary D324 (5) leaves alone: the attacker's colostomy to the cecum end to end (READY on int4, rightly);
        # a colostomy established in the colon reaching the terminal ileum (the first arm: the colon was traversed); a
        # loop ileostomy whose scope reached the cecum (the second arm); a segment filed absent beside a colostomy (the
        # colon as a whole is not); an entry whose type is SUPPORTED another (an anastomosis of the colon)
        self.assertEqual(outcome(COLO, colo_answer(), '44389', Q_COLO), ('ready', ()))
        cases = {
            'a colostomy in the colon, to the terminal ileum': stoma_scope(reached=(sup(EX.TERMINAL_ILEUM),),
                                                                          organ=sup(LM.SIGMOID_COLON)),
            'a colostomy in the transverse colon, to the neo-terminal ileum': stoma_scope(
                reached=(sup(EX.NEO_TERMINAL_ILEUM),), organ=sup(LM.TRANSVERSE_COLON)),
            'a loop ileostomy, to the cecum': stoma_scope(reached=(sup(EX.CECUM),), organ=sup(LM.ILEUM)),
            'a stoma of no stated organ, to the cecum and the ileum': stoma_scope(reached=(sup(EX.CECUM),
                                                                                         sup(EX.ILEUM))),
            'the sigmoid filed absent': stoma_scope(reached=(sup(EX.CECUM),), absent=(sup(ABSENT),
                                                                                     sup(LM.SIGMOID_COLON))),
            'the right colon claimed absent': stoma_scope(reached=(sup(EX.TRANSVERSE_COLON),),
                                                          absent=(unres(ABSENT), unres(LM.RIGHT_COLON))),
            'the right colon claimed absent, pass 2 never asked': stoma_scope(
                reached=(sup(EX.TRANSVERSE_COLON),), absent=(unres(ABSENT, ct.Reason.UNAPPRAISED),
                                                             unres(LM.RIGHT_COLON, ct.Reason.UNAPPRAISED))),
            'an anastomosis whose organ is the colon': stoma_scope(reached=(sup(EX.CECUM),),
                                                                   absent=(sup(ct.AnatomyType.ANASTOMOSIS),
                                                                           sup(LM.COLON))),
        }
        # round r3's round 5 (DECISIONS D330 (1), lane rules6): the colonic route stays met for each, but an anastomosis
        # whose subtype and joins are both silent is the D328 addendum's residual, which the lower-GI path guard holds
        # after this arm with the table's own hold. Round r3's round 6 (DECISIONS D336 (1) (b)): its two unnamed ends may
        # be every landmark, so it may join the ileum below the colon - the colonic route is not met either (the same
        # table hold; moved by evaluate.joins_ileum_below_colon_possible)
        guarded = {'an anastomosis whose organ is the colon'}
        # round r3's round 7 (DECISIONS D342 (1) (a)): unres's default reason is pass 2's appraisal_unclear - a claim
        # pass 2 was asked and did not establish, read at its WIDEST: the entry may be the colon filed absent as a whole,
        # so the route is not colonic (the table's own hold; moved by evaluate._may_be, settled_narrows). The same
        # absence pass 2 was never asked (unappraised: D340 Q1) decides as filed - READY as before
        guarded |= {'the right colon claimed absent'}
        for name, R in cases.items():
            with self.subTest(case=name):
                self.assertEqual(evaluate.colonic_route(R, X1), name not in guarded)
                for code in sorted(evaluate.STOMA_ROUTE_CODES):
                    self.assertIs(route_row(R, code).truth, evaluate.Truth.U if name in guarded else T)
                self.assertEqual(held_of(R, '44389'), [('procedure', ROUTE, A.TYPE, 'X1', 'question')]
                                 if name in guarded else [])

    def test_an_open_reach_that_may_be_colonic_is_asked_as_the_reach(self):
        # HO-8 and the planner (tests/v2/test_gate6's generated COLFULL U case keeps its extent item): where the route
        # rests on a reach not established that may be colonic - or on an empty reach list - the row's witness is that
        # reach, asked as COLFULL's extent row asks it; a reach that may only be ileal, and any reach beside a colon
        # filed absent, keep the table's own hold
        asked = {
            'the cecum not established': (unres(EX.CECUM, ct.Reason.UNAPPRAISED),),
            'the ileum supported, the cecum not established': (sup(EX.ILEUM), unres(EX.CECUM, GEOMETRY)),
            "a doubt's reading of the transverse colon": (doubted(EX.ILEUM, EX.TRANSVERSE_COLON),),
            'pass 1 denying the cecum, not established': (EF.fact(ct.Result.UNRESOLVED, EX.CECUM, ct.FactState.NEGATED,
                                                                  reasons=(ct.Reason.APPRAISAL_UNCLEAR,)),),
            'no reach filed': (),
        }
        for name, reached in asked.items():
            with self.subTest(case=name):
                row = route_row(stoma_scope(reached=reached), 44389)
                self.assertIs(row.truth, evaluate.Truth.U)
                self.assertEqual([(h.fact, h.attribute, h.subject, h.kind.value) for h in row.witnesses],
                                 [('extent', A.REACHED, X1, 'question')])
        held = {
            'only the ileum, not established': stoma_scope(reached=(unres(EX.ILEUM, ct.Reason.UNAPPRAISED),)),
            'the cecum not established beside the colon filed absent': stoma_scope(
                reached=(unres(EX.CECUM, ct.Reason.UNAPPRAISED),), absent=(sup(ABSENT), sup(LM.COLON))),
            'no reach filed beside the colon claimed absent': stoma_scope(reached=(), absent=(unres(ABSENT),
                                                                                               unres(LM.COLON))),
        }
        for name, R in held.items():
            with self.subTest(case=name):
                self.assertEqual([(h.cause, h.attribute, h.subject, h.result) for h in route_row(R, 44389).witnesses],
                                 [(ROUTE, A.TYPE, X1, None)])

    def test_a_true_answer_that_the_scope_reached_the_colon_releases_the_code(self):
        # the open reach is a reading Fable may establish: the planner asks it for the code, an established answer that
        # the scope reached the cecum makes the route colonic and releases 44389; an established ileal reach never does
        R = stoma_scope(reached=(unres(EX.CECUM, ct.Reason.UNAPPRAISED),))
        self.assertTrue([spec for spec in serving(asking.plan(R, ()), '44389') if spec.attribute is A.REACHED])
        R_q = F._answered(R, {'questions': [fact_record('X1', A.REACHED, EX.CECUM.value)]})
        self.assertTrue(evaluate.colonic_route(R_q, X1))
        self.assertEqual(held_of(R_q, '44389'), [])
        ileal = stoma_scope(reached=(unres(EX.ILEUM, ct.Reason.UNAPPRAISED),))
        ileal_q = F._answered(ileal, {'questions': [fact_record('X1', A.REACHED, EX.ILEUM.value)]})
        self.assertTrue(F.holds(F.members(ileal_q, X1, A.REACHED)[0], EX.ILEUM))
        self.assertEqual(held_of(ileal_q, '44389'), [('procedure', ROUTE, A.TYPE, 'X1', 'question')])

    def test_an_act_whose_session_is_open_beside_the_colon_filed_absent_keeps_the_tables_hold(self):
        # the D312 checker's S3 principle (test_r3b_engine): beside an entry that may file the colon surgically absent no
        # session the act may be in gives a colonic route, so the table's own hold stays whatever the session and the
        # planner serves no question to the code; with no such entry the route is read once the session is known (T)
        def open_session(R):
            return replace(R, events={**R.events, E2: {**R.events[E2], A.SESSION: (unres(X1, GEOMETRY),)}})
        held = open_session(stoma_scope(reached=(sup(EX.CECUM),),
                                        absent=(unres(ABSENT, ct.Reason.UNAPPRAISED),
                                                unres(LM.COLON, ct.Reason.UNAPPRAISED))))
        self.assertEqual([(h.cause, h.attribute, h.subject, h.result) for h in route_row(held, 44389).witnesses],
                         [(ROUTE, A.TYPE, E2, None)])
        self.assertEqual(serving(asking.plan(held, ()), '44389'), [])
        self.assertIs(route_row(open_session(stoma_scope(reached=(sup(EX.CECUM),))), 44389).truth, T)

    def test_the_organ_arm_reads_every_entry_that_may_be_the_stoma(self):
        # the first arm, fail-closed: with a colostomy established in the colon and an ileal reach, a second entry that
        # may be a stoma (its type unresolved, its organ not filed) may be the one passed - held; established a stoma in
        # the colon too, or established another type, it is not
        colostomy = {'reached': (sup(EX.TERMINAL_ILEUM),), 'organ': sup(LM.SIGMOID_COLON)}
        held = stoma_scope(**colostomy, entries={Y3: {A.TYPE: (unres(STOMA),)}})
        self.assertFalse(evaluate.colonic_route(held, X1))
        self.assertEqual(held_of(held, '44389'), [('procedure', ROUTE, A.TYPE, 'X1', 'question')])
        # round r3's round 6 (DECISIONS D336 (1) (b)): an anastomosis whose subtype and joins are silent may join any two
        # ends - the ileum below the colon among them - so it leaves no colonic route (moved by
        # evaluate.joins_ileum_below_colon_possible); with an ileocolic subtype, which decides its ends, it does not
        for name, facts, met in (
                ('a second colostomy', {A.TYPE: (sup(STOMA),), A.ORGAN: (sup(LM.TRANSVERSE_COLON),)}, True),
                ('an anastomosis', {A.TYPE: (sup(ct.AnatomyType.ANASTOMOSIS),)}, False),
                ('an ileocolic anastomosis', {A.TYPE: (sup(ct.AnatomyType.ANASTOMOSIS),),
                                              A.SUBTYPE: (sup(ct.AnastomosisSubtype.ILEOCOLIC),)}, True)):
            with self.subTest(entry=name):
                self.assertEqual(evaluate.colonic_route(stoma_scope(**colostomy, entries={Y3: facts}), X1), met)

    def test_the_hold_is_the_route_tables_own_worded_as_before(self):
        # D320 (i): no new words - the colonic-route hold is the table's own no-stoma hold (procedure at RANK row 8,
        # about the session, no fact, coding_rule:stoma_route), worded by the same message, and the planner reads it
        # ABSENT: no question serves the code, however its other witnesses are asked
        R = stoma_scope()
        no_stoma = EF.colonoscopy()
        no_stoma.sessions[X1][A.APPROACH] = (sup(THROUGH_STOMA),)
        R_none = no_stoma.build()
        new = evaluate.decide('44389', (), R).held_facts
        old = evaluate.decide('44394', (), R_none).held_facts
        self.assertEqual([(h.fact, h.cause, h.attribute, h.subject, h.kind, h.result, h.rank) for h in new],
                         [(h.fact, h.cause, h.attribute, h.subject, h.kind, h.result, h.rank) for h in old])
        self.assertEqual(questions.message_of(new[0], evaluate.code_facts('44389')),
                         questions.message_of(old[0], evaluate.code_facts('44394')))
        plan = asking.plan(R, ())
        self.assertEqual(serving(plan, '44389'), [])
        self.assertIn('ABSENT (no anatomy entry may be a stoma: the route table)', plan.blocked)

    def test_no_weakening_releases_a_through_stoma_code_the_route_holds(self):
        # P-MONO over the rule's own inputs (test_properties.weakenings: every fact of every table, every established
        # member deleted, ERASING included): from each held note no single weakening makes the route row T
        TP = properties()
        held = {
            'the ileostomy (an ileal reach, the colon claimed absent)': stoma_scope(
                organ=unres(LM.ILEUM, ct.Reason.UNAPPRAISED),
                absent=(unres(ABSENT, ct.Reason.UNAPPRAISED), unres(LM.COLON, ct.Reason.UNAPPRAISED))),
            'a colonic reach beside the colon filed absent': stoma_scope(reached=(sup(EX.CECUM),),
                                                                         organ=sup(LM.SIGMOID_COLON),
                                                                         absent=(sup(ABSENT), sup(LM.COLON))),
            'a colostomy with a second possible stoma': stoma_scope(reached=(sup(EX.TERMINAL_ILEUM),),
                                                                    organ=sup(LM.SIGMOID_COLON),
                                                                    entries={Y3: {A.TYPE: (unres(STOMA),)}}),
        }
        for name, R in held.items():
            self.assertIsNot(route_row(R, 44389).truth, T, name)
            count = 0
            for label, weak, _what in TP.weakenings(R):
                count += 1
                with self.subTest(case=name, weakening=label):
                    self.assertTrue(evaluate.decide('44389', (), weak).held_facts)
                    if evaluate._session(weak, E2) is not None:  # an act's open session is SUPPORT row 6's question,
                        self.assertIsNot(route_row(weak, 44389).truth, T)  # the route read once it is known (D310)
            self.assertGreater(count, 30, name)


# --- D324 (5), R2E-STOMA-ORGAN: the stoma-possible closure opens only for a lower-tract stoma ---------------------------


def peg_note(organ=None, entry_type=sup(STOMA), approach=None):
    """EF.colonoscopy (X1 to the cecum, E1, the cold snare E2 of L1: 45385) with the approach ``approach`` (None: not
    filed) and Y1 an anatomy entry of type ``entry_type`` whose organ is ``organ`` (None: not filed) - R2E-STOMA-ORGAN's
    probe (engine/refute2/probes/p06_stoma_organ.py)."""
    doc = EF.colonoscopy()
    if approach is not None:
        doc.sessions[X1][A.APPROACH] = (approach,)
    doc.anatomy[Y1] = {A.TYPE: (entry_type,), **({A.ORGAN: (organ,)} if organ is not None else {})}
    return doc.build()


class StomaOrganTests(SimpleTestCase):
    def test_r2e_stoma_organ_a_gastrostomy_beside_a_colonoscopy_no_longer_holds(self):
        # the lane item's own input: a gastrostomy (type stoma, organ the stomach, established) beside a colonoscopy
        # whose approach pass 1 left silent - int4 held 45385 on the approach question; READY now, as with no entry
        R = peg_note(sup(LM.STOMACH))
        self.assertFalse(evaluate.stoma_possible(R, X1))
        self.assertEqual(held_of(R, '45385'), [])
        self.assertEqual(held_of(peg_note(), '45385'), [('procedure', 'reading_unknown', A.APPROACH, 'X1',
                                                         'question')])  # the boundary: its organ not filed

    def test_a_stoma_of_any_other_placed_organ_opens_no_colonoscopy_route(self):
        # the class: every placed organ outside the colon and the ileum (the upper tract, the duodenum, the jejunum, the
        # biliary tree, the pancreas), the entry's type supported, claimed or a doubt's reading of a stoma; every
        # colonoscopy code's route row T
        organs = (LM.ESOPHAGUS, LM.DISTAL_ESOPHAGUS, LM.STOMACH, LM.GASTRIC_ANTRUM, LM.PYLORUS, LM.DUODENUM,
                  LM.SECOND_PORTION_DUODENUM, LM.JEJUNUM, LM.BILE_DUCT, LM.GALLBLADDER, LM.PANCREAS, LM.RECTUM)
        types = {'supported': sup(STOMA), 'claimed': unres(STOMA), "a doubt's reading": doubted(ct.AnatomyType.OTHER_ALTERATION,
                                                                                               STOMA),
                 'claimed, pass 2 never asked': unres(STOMA, ct.Reason.UNAPPRAISED)}
        for organ in organs:
            for t_name, entry_type in types.items():
                with self.subTest(organ=organ.value, type=t_name):
                    R = peg_note(sup(organ), entry_type)
                    self.assertFalse(evaluate.lower_stoma_possible(R, Y1))
                    self.assertFalse(evaluate.stoma_possible(R, X1))
                    # round r3's round 5 (DECISIONS D330 (1), lane rules6): the lower-GI path guard reads the entry
                    # against the ruled harmless set - a stoma is harmless whatever its organ, and so is an entry that
                    # may be another alteration of an organ outside the lower GI tract; one that may be another
                    # alteration of the rectum matches no row and holds with the table's own hold
                    # round r3's round 6 (DECISIONS D336 (1) (b)): a doubt between another alteration (a type with no
                    # control) and a stoma leaves no controlled claim to decide the entry - the guard holds it beside
                    # every organ (the OUTSIDE row released on an uncontrolled type; moved by evaluate.path_guard)
                    guarded = t_name == "a doubt's reading"
                    # round r3's round 7 (DECISIONS D342 (1) (a)): 'claimed' is unres's default, pass 2's
                    # appraisal_unclear - a controlled type pass 2 was asked and did not establish is read at its WIDEST
                    # and decides no release (the table's own hold; moved by evaluate._may_be, settled_narrows); the
                    # stoma pass 2 was never asked (unappraised: D340 Q1) decides as filed, as before
                    guarded = guarded or t_name == 'claimed'
                    for code in sorted(evaluate.ANUS_ROUTE_CODES):
                        self.assertIs(route_row(R, code).truth, evaluate.Truth.U if guarded else T)
                    self.assertEqual(held_of(R, '45385'), [('procedure', ROUTE, A.TYPE, 'X1', 'question')]
                                     if guarded else [])

    def test_the_boundary_a_lower_tract_stoma_or_an_organ_not_established_still_holds(self):
        # what the closure keeps open: a colon or ileum stoma (or the small bowel that holds the ileum), and a stoma
        # whose organ is not established - claimed (the fact pass never claims a stoma's organ, so this is pass 1's
        # gastrostomy on the pipeline), silent, a doubt's reading, a contradiction's side, an established negation of
        # the stomach (it names no organ), or no placeable landmark
        organs = {
            'the sigmoid colon': sup(LM.SIGMOID_COLON), 'the colon': sup(LM.COLON), 'the cecum': sup(LM.CECUM),
            'the ileum': sup(LM.ILEUM), 'the neo-terminal ileum': sup(LM.NEO_TERMINAL_ILEUM),
            'the small bowel': sup(LM.SMALL_BOWEL), 'the stomach claimed (unappraised)': unres(LM.STOMACH,
                                                                                               ct.Reason.UNAPPRAISED),
            'not filed': None, "a doubt's reading": doubted(LM.STOMACH, LM.ILEUM),
            "a contradiction's side": contra(LM.STOMACH, LM.TRANSVERSE_COLON), 'the stomach denied': neg(LM.STOMACH),
            'other': sup(LM.OTHER), 'a stoma': sup(LM.STOMA),
        }
        for name, organ in organs.items():
            with self.subTest(organ=name):
                R = peg_note(organ)
                self.assertTrue(evaluate.stoma_possible(R, X1))
                self.assertEqual(held_of(R, '45385'), [('procedure', 'reading_unknown', A.APPROACH, 'X1', 'question')])

    def test_the_pipelines_gastrostomy_keeps_its_hold_its_organ_is_never_established(self):
        # the ruled boundary on today's fact pass (the attacker's case c, end to end): pass 1 files the gastrostomy's
        # organ, the fact pass cannot claim it (claims.py has only the surgically-absent forms for an organ), so it is
        # unresolved - "an organ not established" - and the closure stays open: 45380 held on the approach as on int4
        _claims, _out, R, _view = R2CL.run(PEG, peg_answer(), R2CL.FAITHFUL)
        self.assertEqual((F.fact(R, Y1, A.ORGAN).result, F.fact(R, Y1, A.ORGAN).value),
                         (ct.Result.UNRESOLVED, LM.STOMACH))
        self.assertTrue(evaluate.stoma_possible(R, X1))
        self.assertEqual(outcome(PEG, peg_answer(), '45380', Q_COLO), ('needs_clarification', ('reading_unknown',)))

    def test_every_weakening_of_the_organ_reopens_and_none_releases(self):
        # P-MONO: from the gastrostomy (READY), every 9.4 weakening of its organ opens the route again (held); from each
        # held note no weakening releases
        TP = properties()
        R = peg_note(sup(LM.STOMACH))
        organ = [weak for _label, weak, what in TP.weakenings(R) if what[:2] == (Y1, A.ORGAN)]
        self.assertGreater(len(organ), 2)
        for index, weak in enumerate(organ):
            with self.subTest(weakening=index):
                self.assertTrue(evaluate.stoma_possible(weak, X1))
                self.assertTrue(held_of(weak, '45385'))
        for name, held in (('an ileostomy', peg_note(sup(LM.ILEUM))), ('a claimed gastrostomy', peg_note(
                unres(LM.STOMACH, ct.Reason.UNAPPRAISED)))):
            for label, weak, _what in TP.weakenings(held):
                with self.subTest(case=name, weakening=label):
                    self.assertTrue(held_of(weak, '45385'))


# === (6) D324 (6), L2-3: an exclusion reads the base's own decision ===================================================

CITE = Span(400, 425)  # E4's status words: 43276 proposed citing the exchange statement's own words


def dated(R):
    """``R`` with its encounter's date of service supported BEFORE any answer is folded, so R_q and R_base share it."""
    return replace(R, encounter={A.DATE_OF_SERVICE: (sup(IsoDate(DAY, ct.Precision.DAY)),)})


def verdict(value):
    return SimpleNamespace(verdict=SimpleNamespace(verdict=value, qualifiers=(), attached=ct.Attached.YES),
                           quotes_bound=False, quotes=())


def settle_request(R, specs, answers):
    """The attacker's helper (attack/L2-exclusion-hold/.../test_l2_refute.settle_request): settle.settle_questions over
    one request of ``specs`` and ONE calibration item (the pool's first, answered rightly), each question answered
    ``answers[spec.key]`` = (claim verdict, control verdict), every supported claim's proof located; then
    settle.exclusive, as the stage applies it. The fact pass's controlled facts a hand-built FactSet lacks are the
    acts' established sessions (only the pool's source)."""
    controlled = frozenset((event_, A.SESSION) for event_ in R.events
                           if F.fact(R, event_, A.SESSION).result is ct.Result.SUPPORTED)
    pool = asking.calibration_pool(replace(R, controlled=controlled))
    items, verdicts, locations = [], {}, {}
    for number, spec in enumerate(specs, start=1):
        claim, control = f'q{number}', f'q{number}n'
        items.append(SimpleNamespace(role='question', spec=spec, claim=claim, control=control, controls=(control,)))
        verdicts[claim], verdicts[control] = verdict(answers[spec.key][0]), verdict(answers[spec.key][1])
        locations[claim] = SimpleNamespace(located=True, spans=((1000 + 10 * number, 1000 + 10 * number + 30),),
                                           reason='')
    items.append(SimpleNamespace(role='calibration', spec=pool[0], claim='c1', control='c1n', controls=('c1n',)))
    verdicts['c1'], verdicts['c1n'] = verdict(V.CONTRADICTS), verdict(V.SUPPORTS)
    request = SimpleNamespace(items=tuple(items), round=1, batch=1)
    found = settle.settle_questions(request, SimpleNamespace(verdicts=verdicts, missing=(), repeated=()), locations, R,
                                    'answered')
    return settle.exclusive(list(found.questions)), found.health


def fact_record(subject: str, attribute: ct.Attribute, value: str) -> dict:
    """One established Q-FACT answer as contract/settle stores it (the fields the fold reads)."""
    return {'family': 'Q-FACT', 'form': 'fact', 'subjects': [subject], 'unlisted': None, 'attribute': attribute.value,
            'value': value, 'negated': False, 'result': 'supported', 'reasons': [],
            'proof': [{'start': 1000, 'end': 1030}]}


def absorb_record(index: int) -> dict:
    """One established Q-ABSORB answer about the kept unlisted entry ``index`` as contract/settle stores it."""
    return {'family': 'Q-ABSORB', 'form': 'absorb', 'subjects': [f'u:{index}'], 'unlisted': index, 'attribute': None,
            'value': '', 'negated': False, 'result': 'supported', 'reasons': [], 'proof': [{'start': 1000, 'end': 1030}]}


def statement_event(doc, kind=Kind.STENT_EXCHANGE, how='denial', session_=X1):
    """E4, the statement 43276 cites: a current broad denial of ``kind`` (``how`` 'denial'), a plan of it ('plan'), or
    one done at an earlier date ('earlier') or by another clinician ('other') - in ``session_``, its kind words 403-411
    and its status words 400-425."""
    words = dict(kind_words=Span(403, 411), status_words=Span(400, 425))
    if how == 'denial':
        return doc.event(4, kind=sup(kind), status=neg(Status.PERFORMED), session=sup(session_), date=sup(EF.ON),
                         breadth=sup(ct.Breadth.ALL_OF_KIND), **words)
    if how == 'plan':
        return doc.event(4, kind=sup(kind), status=sup(Status.PLANNED), session=sup(session_), **words)
    if how == 'earlier':
        return doc.act(4, kind, session=session_, date=sup(EF.EARLIER), **words)
    return doc.act(4, kind, session=session_, performer=sup(ct.Performer.OTHER_CLINICIAN), **words)


def duct_scene(how='denial', *, open_part='placement'):
    """The finding's input (ExchangeExclusionTests' scene): ERCP X1, E1 its examination; E2 a stent placement and E3 a
    stent removal from the bile duct - the duct of ``open_part`` claimed pancreatic, its check failed (unresolved), the
    other's supported biliary; E4 the exchange statement (``statement_event``); E5 a biliary sphincterotomy (43262:
    STENT_INCLUDED asks whether the stent is of its duct); E6 the biliary cannulation, achieved."""
    doc = EF.Doc()
    doc.session(1, SessionKind.ERCP)
    doc.exam(1)
    open_duct, known = unres(ct.Duct.PANCREATIC, GEOMETRY), sup(ct.Duct.BILIARY)
    doc.act(2, Kind.STENT, duct=open_duct if open_part == 'placement' else known)
    doc.act(3, Kind.STENT_REMOVAL, duct=open_duct if open_part == 'removal' else known)
    statement_event(doc, how=how)
    doc.act(5, Kind.SPHINCTEROTOMY, duct=sup(ct.Duct.BILIARY))
    doc.act(6, Kind.CANNULATION, access=sup(ct.AccessOutcome.ACHIEVED), duct=sup(ct.Duct.BILIARY))
    return dated(doc.build())


def absorb_scene(part=Kind.STENT):
    """The verifier's Q-ABSORB variant: a filed stent removal E2 from the bile duct beside a kept unlisted act of kind
    ``part`` in X1 (D216: a synthetic other part - a pair pending on R_base), the denial E4, E5 a biliary
    sphincterotomy, E6 the cannulation."""
    doc = EF.Doc()
    doc.session(1, SessionKind.ERCP)
    doc.exam(1)
    filed = Kind.STENT_REMOVAL if part is Kind.STENT else Kind.STENT
    doc.act(2, filed, duct=sup(ct.Duct.BILIARY))
    doc.unlisted.append(EF.unlisted(ct.UnlistedWhat.ACT, part, X1, Span(900, 960)))
    statement_event(doc)
    doc.act(5, Kind.SPHINCTEROTOMY, duct=sup(ct.Duct.BILIARY))
    doc.act(6, Kind.CANNULATION, access=sup(ct.AccessOutcome.ACHIEVED), duct=sup(ct.Duct.BILIARY))
    return dated(doc.build())


def session_scene(how='denial'):
    """The pair set apart by a session: two ERCP sessions (X1: E1; X2: E7), the biliary stent E2 whose session pass 1
    claimed X2 (unresolved), the biliary stent removal E3 in X1, the statement E4 in X1, the cannulation E6."""
    doc = EF.Doc()
    doc.session(1, SessionKind.ERCP)
    doc.session(2, SessionKind.ERCP)
    doc.exam(1)
    doc.exam(7, session=X2)
    doc.act(2, Kind.STENT, duct=sup(ct.Duct.BILIARY), session=unres(X2, GEOMETRY))
    doc.act(3, Kind.STENT_REMOVAL, duct=sup(ct.Duct.BILIARY))
    statement_event(doc, how=how)
    doc.act(6, Kind.CANNULATION, access=sup(ct.AccessOutcome.ACHIEVED), duct=sup(ct.Duct.BILIARY))
    return dated(doc.build())


def planned_answer(R, *, release):
    """R_q from the planner's own round-1 plan over ``R``, each question answered in its release direction when
    ``release(spec)`` (TRUE by the scene's construction) and in the holding direction otherwise, through settle."""
    plan = asking.plan(R, ())
    answers = {spec.key: ((V.SUPPORTS, V.CONTRADICTS) if release(spec) else (V.CONTRADICTS, V.SUPPORTS))
               for spec in plan.specs}
    records, health = settle_request(R, list(plan.specs), answers)
    return plan, records, health, F._answered(R, {'questions': records})


def excluded(R, codes=('43276', '43274', '43275', '43262')) -> dict:
    return {code: evaluate.decide(code, (CITE,) if code == '43276' else (), R).exclusion is not None for code in codes}


def assess(R, *codes):
    return TA.by_code(AS.assess_facts(R, date_of_service=DAY, text=TA.TEXT, pages=(), integrity=TA.Integrity(),
                                      provider_status='succeeded', proposals=TA.corti(*codes),
                                      reference=TA.Lookup(), member=TA.ENTERED, label=lambda s: str(s.id)))


CITED = EvidenceSpan(0, 400, 425, TA.TEXT[400:425], True)
NOT_DOCUMENTED = ('performed_status', 'coding_rule:not_documented')


class BaseDecisionTests(SimpleTestCase):
    def answered_scenes(self) -> dict:
        """Every scene of the class with its answered row: (R_base, R_q) - through the planner and settle where the
        planner asks the answer (the duct of the finding's scene beside a denial, a plan or an exchange of an earlier
        date; the unlisted stent's absorption), else the stored record folded (an exchange by another clinician, whose
        silent duct blocks 43262's question; the removal's duct; the unlisted removal, which 43262's STENT_INCLUDED
        blocks; a session): the rule is the engine's reading of an established answer, whoever asked it."""
        out = {}
        for how in ('denial', 'plan', 'earlier'):
            R = duct_scene(how)
            _plan, _records, _health, R_q = planned_answer(
                R, release=lambda spec: spec.attribute is A.TARGET_DUCT and spec.subjects == ('E2',))
            out[f'the placement duct answered, a {how}'] = (R, R_q)
        R = duct_scene('other')
        out['the placement duct answered, an exchange by another clinician'] = (R, F._answered(R, {'questions': [
            fact_record('E2', A.TARGET_DUCT, ct.Duct.PANCREATIC.value)]}))
        R = duct_scene(open_part='removal')
        out['the removal duct answered'] = (R, F._answered(R, {'questions': [
            fact_record('E3', A.TARGET_DUCT, ct.Duct.PANCREATIC.value)]}))
        R = absorb_scene(Kind.STENT)
        _plan, _records, _health, R_q = planned_answer(R, release=lambda spec: spec.family is asking.Family.Q_ABSORB)
        out['the unlisted stent absorbed'] = (R, R_q)
        R = absorb_scene(Kind.STENT_REMOVAL)
        out['the unlisted stent removal absorbed'] = (R, F._answered(R, {'questions': [absorb_record(0)]}))
        for how in ('denial', 'plan'):
            R = session_scene(how)
            out[f'the session answered, a {how}'] = (R, F._answered(R, {'questions': [
                fact_record('E2', A.SESSION, 'X2')]}))
        return out

    def test_l2_3_the_findings_input_is_never_excluded_by_an_answer(self):
        # the must-change pin (L2-3): the planner asks only E2's duct (serving 43262), the answer is established and
        # true; on R_q the pair is set apart, so int4's guard (candidate positivity only) sent 43276 to 4.6 on R_base,
        # where the cited denial excluded it although R_base's own 4.4 holds it pending by the pair. Held now, not
        # documented; 43262 released as before
        R = duct_scene()
        plan, records, health, R_q = planned_answer(
            R, release=lambda spec: spec.attribute is A.TARGET_DUCT and spec.subjects == ('E2',))
        duct = [spec for spec in plan.specs if spec.attribute is A.TARGET_DUCT and spec.subjects == ('E2',)]
        self.assertEqual(len(duct), 1)
        self.assertEqual(sorted(plan.serves[duct[0].key]), ['43262'])
        self.assertEqual(health['refused'], [])
        self.assertTrue(F.holds(F.fact(R_q, E2, A.TARGET_DUCT), ct.Duct.PANCREATIC))
        self.assertIs(R_q.base, R)
        self.assertTrue(evaluate._pairs(evaluate._code('43276'), R).pending)
        self.assertFalse(evaluate._pairs(evaluate._code('43276'), R_q).pending)
        decided = evaluate.decide('43276', (CITE,), R_q)
        self.assertIsNone(decided.exclusion)
        self.assertEqual([(h.fact, h.cause) for h in decided.held_facts], [NOT_DOCUMENTED])
        full_base, full_q = assess(R, ('43276', CITED), ('43262', 5)), assess(R_q, ('43276', CITED), ('43262', 5))
        self.assertIsNot(full_q['43276'].status, Outcome.EXCLUDED)
        self.assertIs(full_q['43276'].status, Outcome.NEEDS_CLARIFICATION)
        self.assertIs(full_q['43262'].status, Outcome.READY)
        self.assertIsNot(full_base['43276'].status, Outcome.EXCLUDED)

    def test_every_pair_an_answer_sets_apart_is_held_never_excluded(self):
        # the class (D324 (6)): 43276's pair set apart on R_q by a duct answer (either part's duct; the exchange
        # denied, planned, done at an earlier date or by another clinician), by a Q-ABSORB answer (the D216 synthetic
        # part, either part unlisted) and by a session answer (denied or planned): R_base's own 4.4 decision holds the
        # group by its pending pair, so 4.6 never runs - held, not documented, never excluded
        for name, (R, R_q) in self.answered_scenes().items():
            with self.subTest(scene=name):
                self.assertIsNot(R_q.base, None)
                c = evaluate._code('43276')
                self.assertFalse(evaluate._read_group(c, (Kind.STENT_EXCHANGE,), R).reaches_exclusion)
                self.assertTrue(evaluate._read_group(c, (Kind.STENT_EXCHANGE,), R_q).reaches_exclusion)
                decided = evaluate.decide('43276', (CITE,), R_q)
                self.assertIsNone(decided.exclusion)
                self.assertEqual([(h.fact, h.cause) for h in decided.held_facts], [NOT_DOCUMENTED])

    def test_the_pin_excluded_with_the_answers_is_excluded_without_them(self):
        # DESIGN-v2 f.2's P-MONO-Q pin, D324 (6): EXCLUDED(R, A) == EXCLUDED(R, empty) over every scene, for 43276 and
        # its neighbours
        for name, (R, R_q) in self.answered_scenes().items():
            with self.subTest(scene=name):
                self.assertEqual(excluded(R_q), excluded(R))

    def test_the_boundary_an_exclusion_r_base_itself_reaches_is_unchanged(self):
        # left alone: where R_base's own decision reaches 4.6 (no stent act at all, the denial cited) an answer about
        # another act changes nothing - EXCLUDED on R_base and on R_q alike; and a row with no answer reads as before
        doc = EF.Doc()
        doc.session(1, SessionKind.ERCP)
        doc.exam(1)
        statement_event(doc)
        doc.act(5, Kind.SPHINCTEROTOMY, duct=unres(ct.Duct.BILIARY, GEOMETRY))
        doc.act(6, Kind.CANNULATION, access=sup(ct.AccessOutcome.ACHIEVED), duct=sup(ct.Duct.BILIARY))
        R = dated(doc.build())
        R_q = F._answered(R, {'questions': [fact_record('E5', A.TARGET_DUCT, ct.Duct.BILIARY.value)]})
        self.assertIs(R_q.base, R)
        for found in (R, R_q):
            self.assertTrue(evaluate._read_group(evaluate._code('43276'), (Kind.STENT_EXCHANGE,), found.excluding)
                            .reaches_exclusion)
            self.assertIsNotNone(evaluate.decide('43276', (CITE,), found).exclusion)
        R_alone = duct_scene()  # a row with no answer (no base): held by its pending pair's own witnesses, as on int4
        self.assertIsNone(R_alone.base)
        alone = evaluate.decide('43276', (CITE,), R_alone)
        self.assertIsNone(alone.exclusion)
        self.assertTrue(alone.held_facts)
        self.assertNotIn(NOT_DOCUMENTED, [(h.fact, h.cause) for h in alone.held_facts])

    def test_the_premise_is_read_by_the_code_path_decide_reads_the_group_by(self):
        # D324 (6): "computed by the same code path _decide uses" - for every scene, on R_base and on R_q, the group's
        # reading (``_read_group``) is what _decide recorded for it: its supporting acts and its pending candidates
        c = evaluate._code('43276')
        for name, (R, R_q) in self.answered_scenes().items():
            for label, found in (('R_base', R), ('R_q', R_q)):
                with self.subTest(scene=name, row=label):
                    read = evaluate._read_group(c, (Kind.STENT_EXCHANGE,), found)
                    decided = evaluate._decide('43276', (CITE,), found, None)
                    group = next(entry for entry in decided.groups if entry.kinds == (Kind.STENT_EXCHANGE,))
                    self.assertEqual(read.reaches_exclusion, not group.supporting and not group.positive)
                    self.assertEqual(tuple(entry.event for entry in read.pending),
                                     tuple(candidate.event for candidate in group.positive))


# === (7) D324 (7), L6-4: QB reads a lesion-like structure as its lesion ================================================

# The finding's input (attack/L6-generality/l6/s08_qb_structure.py), word for word
EGD = ('SYNTHETIC UPPER ENDOSCOPY REPORT\n'                                                              # S1
       'Date of service: 03/14/2031\n'                                                                    # S2
       'Endoscopist: Corvin Ashdale, MD (fictional)\n'                                                    # S3
       '\n'
       'Findings: The gastroscope was advanced to the second part of the duodenum.\n'                    # S4
       'A 12 mm ulcer with a visible vessel was seen in the gastric antrum.\n'                           # S5
       'No biopsies of the antral ulcer were taken because of the visible vessel.\n'                     # S6
       'Biopsies of the gastric antrum and body were taken to evaluate for Helicobacter pylori.\n')      # S7
Q_EGD = 'Biopsies of the gastric antrum and body were taken to evaluate for Helicobacter pylori.'


def egd_answer(structure):
    """The attacker's pass 1 (s08's ``pass1``): L1 the antral ulcer (single); E2 "No biopsies of the antral ulcer"
    (negated, single target L1, target.structure ``structure``, placed in the antrum); E3 the H. pylori biopsies of
    the antrum and the body, naming no lesion."""
    return answer(
        sections=[opening(), labelled('N1', 'S4', 'Findings:', 'findings')],
        sessions=[session('X1', fact('egd', src(['S4'], 'gastroscope')), examination=[fact('E1', src(['S4']))],
                          encounter=[fact('this_encounter', frame(['S2']))],
                          reached=[fact('duodenum', src(['S4'], 'advanced to the second part of the duodenum'))])],
        lesions=[lesion('L1', src(['S5'], 'A 12 mm ulcer with a visible vessel'),
                        multiplicity=[fact('single', src(['S5'], 'A 12 mm ulcer'))],
                        places=[fact('gastric_antrum', src(['S5'], 'gastric antrum'))])],
        events=[event('E1', ['S4'], 'gastroscope', 'was advanced', 'examination', session=[fact('X1', src(['S4']))]),
                event('E2', ['S6'], 'biopsies', 'were taken', 'biopsy', state='negated',
                      status_source=src(['S6'], 'No biopsies of the antral ulcer were taken'),
                      session=[fact('X1', src(['S6']))],
                      scope__breadth=[fact('single_target', src(['S6'], 'of the antral ulcer'))],
                      target__lesion=[fact('L1', src(['S6'], 'antral ulcer'))],
                      target__structure=[fact(structure, src(['S6'], 'ulcer'))],
                      target__places=[fact('gastric_antrum', src(['S6'], 'antral'))]),
                event('E3', ['S7'], 'Biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S7']))],
                      target__places=[fact('gastric_antrum', src(['S7'], 'gastric antrum')),
                                      fact('gastric_body', src(['S7'], 'body'))])])


def ulcer_scene(structure, *, lesion_place=LM.GASTRIC_ANTRUM, act_places=(LM.GASTRIC_ANTRUM, LM.GASTRIC_BODY),
                listed=False):
    """The settled FactSet of the finding's shape, built in code: an EGD X1 (E1); L1 (single) at ``lesion_place``; E2
    a denial of biopsy on its single target L1 (``listed``: listed targets L1 and L2, L2 single in the gastric body),
    its target.structure ``structure`` (a Fact; the fact pass never claims a statement's structure, so unresolved on
    the pipeline), placed at its lesions' places; E3 a biopsy at ``act_places`` naming no lesion; the controls the
    fact pass makes - the denial asked about each act place none of its own holds (rejected) and the act-lesion pair
    (E3, distinct_from, L) of each lesion established."""
    doc = EF.egd()
    doc.lesion(1, multiplicity=sup(ct.Multiplicity.SINGLE), lesion_places=[sup(lesion_place)])
    places = [lesion_place]
    over = dict(lesion=sup(L1))
    if listed:
        doc.lesion(2, multiplicity=sup(ct.Multiplicity.SINGLE), lesion_places=[sup(LM.GASTRIC_BODY)])
        places.append(LM.GASTRIC_BODY)
        over = dict(targets=[sup(L1), sup(L2)])
    doc.act(2, Kind.BIOPSY, status=neg(Status.PERFORMED),
            breadth=sup(ct.Breadth.LISTED_TARGETS if listed else ct.Breadth.SINGLE_TARGET),
            structure=structure, places=[sup(place) for place in places], **over)
    doc.act(3, Kind.BIOPSY, places=[sup(place) for place in act_places])
    for place in act_places:
        if place not in places:
            doc.controls[(E2, A.TARGET_PLACES, place)] = True
    for lesion_ in ((L1, L2) if listed else (L1,)):
        doc.controls[(E3, A.DISTINCT_FROM, lesion_)] = True
    return doc.build()


LESION_LIKE = (ct.Structure.LESION, ct.Structure.ULCER, ct.Structure.MASS, ct.Structure.VARIX,
               ct.Structure.BLEEDING_SITE)


class StructurePlacementTests(SimpleTestCase):
    def test_l6_4_the_findings_input_is_ready(self):
        # the must-change pin (L6-4): the attacker's EGD end to end - the denial "No biopsies of the antral ulcer"
        # filed with target lesion L1 and target.structure ulcer, the H. pylori biopsies naming no lesion set apart
        # from it by the fact pass's act-lesion pair. int4 held 43239 relation:contradiction (the structure "any but a
        # lesion" held every place); int3 and the same note with the structure written lesion released it
        for structure in ('ulcer', 'lesion'):
            with self.subTest(structure=structure):
                _claims, _out, R, _view = R2CL.run(EGD, egd_answer(structure), R2CL.FAITHFUL)
                self.assertIs(F.established_not_on(R, E3, L1), True)
                self.assertIs(pairing.relation(R, E2, E3).relation, pairing.Relation.INDEPENDENT)
                self.assertIs(pairing.not_on_sets_apart(R, E2, E3), True)
                self.assertEqual(outcome(EGD, egd_answer(structure), '43239', Q_EGD), ('ready', ()))

    def test_every_lesion_like_structure_describing_its_target_lesion_sets_apart(self):
        # the class: every lesion-like structure (end to end, and in code in every state pass 2 may leave it: claimed,
        # supported, a doubt reading only lesion-like structures, a contradiction of two), the verifier's second shape
        # (a duodenal-bulb ulcer not biopsied beside celiac biopsies of the bulb and the second portion), and a listed
        # denial of two ulcers: INDEPENDENT, 43239 READY
        for structure in LESION_LIKE:
            with self.subTest(structure=structure.value, how='end to end'):
                self.assertEqual(outcome(EGD, egd_answer(structure.value), '43239', Q_EGD), ('ready', ()))
        states = {'claimed': lambda s: unres(s, ct.Reason.UNAPPRAISED), 'supported': sup,
                  "a doubt's readings": lambda s: doubted(s, ct.Structure.MASS),
                  "a contradiction's sides": lambda s: contra(s, ct.Structure.VARIX)}
        shapes = {'the antral ulcer': {}, 'a duodenal-bulb ulcer': dict(
            lesion_place=LM.DUODENAL_BULB, act_places=(LM.DUODENAL_BULB, LM.SECOND_PORTION_DUODENUM)),
            'a listed denial of two ulcers': dict(listed=True)}
        for structure in LESION_LIKE:
            for s_name, state in states.items():
                for shape, over in shapes.items():
                    with self.subTest(structure=structure.value, state=s_name, shape=shape):
                        R = ulcer_scene(state(structure), **over)
                        self.assertEqual(pairing.row(R, pairing.Row.TARGET, E2, E3), pairing.RowResult.INDEPENDENT)
                        self.assertEqual(held_of(R, '43239'), [])

    def test_every_located_structure_holds_every_place(self):
        # the boundary D324 (7) keeps: a structure with a location of its own - an anastomosis, a duct, a stent, the
        # wall, the mucosa, the lumen, a named organ - and every member the ruling names in neither list (a stricture,
        # a vessel, a stone, a collection, a foreign body, other), in any state but an established negation, and a
        # doubt one of whose readings is located: SAME, 43239 held relation:contradiction
        located = [member for member in ct.Structure if member not in LESION_LIKE]
        self.assertEqual(len(located), 15)
        for structure in located:
            for s_name, found in (('claimed', unres(structure, ct.Reason.UNAPPRAISED)), ('supported', sup(structure)),
                                  ("a doubt's reading", doubted(ct.Structure.ULCER, structure)),
                                  ("a contradiction's side", contra(ct.Structure.ULCER, structure))):
                with self.subTest(structure=structure.value, state=s_name):
                    R = ulcer_scene(found)
                    self.assertEqual(pairing.row(R, pairing.Row.TARGET, E2, E3), pairing.RowResult.SAME)
                    self.assertEqual(sorted({held.cause for held in evaluate.decide('43239', (), R).held_facts}),
                                     ['relation:contradiction'])
        for name, found in (('an established negation of the wall', neg(ct.Structure.WALL)), ('silent', F.SILENT)):
            with self.subTest(state=name):  # names nothing: the boundary of the boundary
                self.assertEqual(held_of(ulcer_scene(found), '43239'), [])

    def test_the_table_classifies_every_structure_member(self):
        # D324 (7): the typed table splits the Structure enum completely, into the two placements the ruling names
        self.assertEqual(set(pairing.STRUCTURE_PLACEMENT), set(ct.Structure))
        self.assertEqual({member for member, placement in pairing.STRUCTURE_PLACEMENT.items()
                          if placement is pairing.StructurePlacement.LESION_LIKE}, set(LESION_LIKE))
        self.assertEqual(set(pairing.STRUCTURE_PLACEMENT.values()), set(pairing.StructurePlacement))
        for member in ct.Structure:
            self.assertIs(pairing.structure_placement(member), pairing.STRUCTURE_PLACEMENT[member])

    def test_a_member_the_table_does_not_classify_counts_as_located(self):
        # D324 (7): "a new member counts as located, and so holds, until classified" - the table without the ulcer (as a
        # member contract/types.py would add reads) holds the finding's scene again
        unclassified = MappingProxyType({member: placement for member, placement in pairing.STRUCTURE_PLACEMENT.items()
                                         if member is not ct.Structure.ULCER})
        with mock.patch.object(pairing, 'STRUCTURE_PLACEMENT', unclassified):
            self.assertIs(pairing.structure_placement(ct.Structure.ULCER), pairing.StructurePlacement.LOCATED)
            R = ulcer_scene(unres(ct.Structure.ULCER, ct.Reason.UNAPPRAISED))
            self.assertEqual(pairing.row(R, pairing.Row.TARGET, E2, E3), pairing.RowResult.SAME)
        self.assertEqual(pairing.row(ulcer_scene(unres(ct.Structure.ULCER, ct.Reason.UNAPPRAISED)), pairing.Row.TARGET,
                                     E2, E3), pairing.RowResult.INDEPENDENT)

    def test_r2e_qb_anats_and_qbs_scenes_stay_held(self):
        # R2E-QB-ANAT's scene (the denial's own anastomosis, its target.anatomy) and QB's (a statement place beyond its
        # lesion's) stay SAME, held - with a lesion-like structure filed on the denial too: the table frees only the
        # structure, never the clause's other targets
        from tests.v2 import test_r3b_engine as RE
        from tests.v2 import test_r3b_int4 as I4
        for structure in (None, ct.Structure.ULCER, ct.Structure.LESION):
            for name, R in (("R2E-QB-ANAT's scene", I4.at_the_anastomosis()), ("QB's scene", RE.qb())):
                if structure is not None:
                    R = I4.with_facts(R, E3, TARGET_STRUCTURE=unres(structure, ct.Reason.UNAPPRAISED))
                with self.subTest(scene=name, structure=getattr(structure, 'value', None)):
                    self.assertEqual(I4.target(R), pairing.RowResult.SAME)
                    self.assertEqual(I4.held_causes(R, '45381'), ['relation:contradiction'])
                    self.assertIs(pairing.not_on_sets_apart(R, E3, E4), False)

    def test_no_weakening_releases_a_located_structures_hold(self):
        # P-MONO: from the held scene (the denial's structure the wall, claimed), no single 9.4 weakening sets the pair
        # apart but D316's QD (the one named release of D245's class, unchanged here: 9.4's deletion of an ACT place no
        # control asks either object about - the act's antrum, which the denial's own antrum holds); from the released
        # scene (the ulcer), a weakening that adds a located reading holds it
        TP = properties()
        R = ulcer_scene(unres(ct.Structure.WALL, ct.Reason.UNAPPRAISED))
        count = 0
        for label, weak, what in TP.weakenings(R):
            if label.startswith('deleted') and what[:2] == (E3, A.TARGET_PLACES) and not any(
                    key[0] in (E2, E3) and key[2] == what[3].value for key in R.pair_controls):
                continue  # D316 QD: the named release, read by test_properties
            count += 1
            with self.subTest(weakening=label):
                self.assertNotEqual(pairing.row(weak, pairing.Row.TARGET, E2, E3), pairing.RowResult.INDEPENDENT)
        self.assertGreater(count, 20)
        released = ulcer_scene(unres(ct.Structure.ULCER, ct.Reason.UNAPPRAISED))
        widened = replace(released, events={**released.events, E2: {
            **released.events[E2], A.TARGET_STRUCTURE: (doubted(ct.Structure.ULCER, ct.Structure.DUCT),)}})
        self.assertEqual(pairing.row(widened, pairing.Row.TARGET, E2, E3), pairing.RowResult.SAME)
