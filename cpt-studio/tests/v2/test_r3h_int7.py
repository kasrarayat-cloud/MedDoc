"""Round r3's round 5 integration (int7; DECISIONS D330 (1) beside D327 (1)): the act's open session of a through-stoma
colonoscopy code where the lower-GI path guard leaves the hold to D327 (1)'s arm.

With the act's session not established, the guard exempts every anatomy entry that may be of the route's type - an
entry whose type may be a stoma may be the stoma the scope entered through once the session is known (evaluate.
route_entries) - so beside such an entry the guard adds nothing, and D327 (1)'s open-session branch of
evaluate._through_stoma_route is what holds the code whatever the session (D312 checker S3's principle: the table's
own hold about the act, and nothing asked through it). Rules4's own pin of that branch (test_r3e_rules RangeTests,
an anastomosis TYPED anastomosis) is now also held by the guard, so its mutant (rules4's C4: the open-session branch
reads only the colon filed absent as a whole) survived int7's suite; the census `repro/c4/survivors_census.py` found
the distinguishing shapes - 544 of 3,564, every one an entry whose type may be a stoma, its organ filed outside the
colon, beside a subtype or joins that may join the ileum below the colon - where C4 would serve a paid session
question that int7 does not ask (decide's held facts equal: never a READY). These tests pin int7's behaviour there.

Every note synthetic; FactSets built with tests/v2's helpers."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation.contract import types as ct
from studio.interpretation.engine import asking, evaluate
from studio.interpretation.engine.types import Id
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_r3e_rules as R3E
from tests.v2 import test_r3f_rules as R3F

A, AT, SUB, LM, EX = ct.Attribute, ct.AnatomyType, ct.AnastomosisSubtype, ct.Landmark, ct.Extent
sup, unres = EF.sup, EF.unres
E2, Y2, Y3 = Id.parse('E2'), Id.parse('Y2'), Id.parse('Y3')
UNAPPRAISED = R3E.UNAPPRAISED
ROUTE = R3E.ROUTE
STOMA = R3F.entry_of(type=sup(AT.STOMA))

# entries whose TYPE may be a stoma (silent, claimed or supported), organ filed outside the colon, beside a subtype or
# joins that may join the ileum below the colon (D327 (1); D328's addendum, rules4 Q3)
SHAPES = {
    'type silent, organ the ileum, subtype ileorectal': R3F.entry_of(organ=sup(LM.ILEUM), subtype=sup(SUB.ILEORECTAL)),
    'type silent, organ the ileum, joins the ileum and the rectum': R3F.entry_of(
        organ=sup(LM.ILEUM), joins=(sup(LM.ILEUM), sup(LM.RECTUM))),
    'type claimed stoma, organ the sigmoid colon, subtype ileoanal claimed': R3F.entry_of(
        type=unres(AT.STOMA, UNAPPRAISED), organ=sup(LM.SIGMOID_COLON), subtype=unres(SUB.ILEOANAL, UNAPPRAISED)),
    'type supported stoma, organ the rectum, subtype ileorectal claimed': R3F.entry_of(
        type=sup(AT.STOMA), organ=sup(LM.RECTUM), subtype=unres(SUB.ILEORECTAL, UNAPPRAISED)),
}


def scene(entry, *, beside_a_stoma: bool):
    """A colonoscopy through a stoma (44389, a cecal reach, the scope's stoma Y1 of organ ileum) whose biopsy E2's session
    is not established (a geometry check failed: SUPPORT row 6's question), with ``entry`` filed as Y2 and, if asked,
    a second stoma Y3."""
    entries = {Y2: entry, **({Y3: STOMA} if beside_a_stoma else {})}
    return R3E.open_session(R3E.RR.stoma_scope(reached=(sup(EX.CECUM),), organ=sup(LM.ILEUM), entries=entries))


class OpenSessionBesideAPossibleStomaTests(SimpleTestCase):
    def test_the_through_stoma_code_keeps_the_tables_hold_about_the_act_and_nothing_is_asked(self):
        for name, entry in SHAPES.items():
            for beside in (False, True):
                with self.subTest(entry=name, beside_a_stoma=beside):
                    R = scene(entry, beside_a_stoma=beside)
                    self.assertTrue(evaluate.whole_colon_absent_possible(R))
                    self.assertEqual(R3E.witnesses(R3E.route_row(R, 44389)), [(ROUTE, A.TYPE, E2, None)])
                    self.assertEqual(R3E.serving(asking.plan(R, ()), '44389'), [])

    def test_the_guard_leaves_these_entries_to_the_arm(self):
        # the reason the arm must hold here: with the act's session open the guard exempts each such entry as possibly
        # the route's own stoma, and no other entry or cover holds it
        found = evaluate.catalogue.lower_route('44389')
        for name, entry in SHAPES.items():
            with self.subTest(entry=name):
                R = scene(entry, beside_a_stoma=False)
                self.assertIn(Y2, evaluate.route_entries(found, R, None))
                self.assertFalse(evaluate.path_guard(found, R, None))

    def test_the_boundary_a_colon_that_remains_beside_a_possible_stoma_asks_the_session(self):
        # an ileocolic join filed by its subtype and joins, its type silent: a colon remains, so no session the act may
        # be in leaves the colon gone - the arm adds nothing, and SUPPORT row 6's session question is served as before
        entry = R3F.entry_of(organ=sup(LM.ILEUM), subtype=sup(SUB.ILEOCOLIC), joins=(sup(LM.ILEUM), sup(LM.COLON)))
        R = scene(entry, beside_a_stoma=False)
        self.assertFalse(evaluate.whole_colon_absent_possible(R))
        self.assertEqual(R3E.witnesses(R3E.route_row(R, 44389)), [])
        self.assertNotEqual(R3E.serving(asking.plan(R, ()), '44389'), [])
