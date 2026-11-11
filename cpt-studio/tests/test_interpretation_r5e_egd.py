"""DECISIONS D154 (round 5e; the round-5d review of D149, egd4 problems 1, 2, 4 and 6), SYNTHETIC. (1), the withdrawal
of D149 (2)'s adjective key, is STOPPED and not built here: built as specified, it makes moves the narrowing rule
forbids on constructed inputs - an EXCLUSION among them (a bleeding-control denial the code cites alone, beside the
device-named control the restoration puts in doubt, excludes 43255 where 4f82e5056 and c2e53f8e hold it); see D154's
entry and round5e/egd5/patch-with-1.diff. Only the corrected claims are built:
- (2) problems 1 and 2: no change to the question order. Its claim is corrected (coverage.in_doubt_questions'
  docstring): one service question per (family, fact), the act asked about the first in doubt that no proposed code
  reads or names in its own question, so the question that decides a missing code is not guaranteed - F1 with 43249 asks
  the dilation's question and not the biopsy's, which decides the missing 43239; the biopsy stays listed in doubt.
- (3) problems 4 and 6: ``holding`` is inert on the live path (assess passes none) - pinned on assess's own call;
  catalogue_kind's docstring says that a device-named event with a verified hemostasis purpose is in doubt too.
Built with the round-5 EGD builders (tests/test_interpretation_r5_egd.py). Nothing is sent."""
from __future__ import annotations

import ast
import copy
from pathlib import Path

from django.test import SimpleTestCase

from studio.interpretation import coverage, events
from tests import test_interpretation_r5_egd as e5
from tests import test_interpretation_r5c_egd as e5c
from tests.test_interpretation_events import proposal

at, tgt, event, report, case = e5.at, e5.tgt, e5.event, e5.report, e5.case
built, assessed, items = e5.built, e5.assessed, e5.items
held, ready = e5.held, e5.ready
EGD, ADV, NORMAL = e5.EGD, e5.ADV, e5.NORMAL
APP = Path(__file__).resolve().parents[1]
NAMES: list = []

PYLORUS = 'The pyloric stricture was dilated with a 15 mm balloon.'
ESO_LATER = 'At that time, the distal esophageal stricture was dilated with an 18 mm balloon.'
BX_LATER = e5c.TIMED_BIOPSY_LINE
F1_LINES = report(P5=ADV, P6=PYLORUS, P7=ESO_LATER, P8=BX_LATER, P9=NORMAL)


def f1_events() -> list:
    timed_bx = copy.deepcopy(e5c.TIMED_BIOPSY)
    timed_bx['id'] = 'E4'
    return [e5.examination(),
            event('E2', EGD, at('dilation', 'dilated', ['P6']), status=at('performed', 'was dilated', ['P6']),
                  technique=at('balloon', '15 mm balloon', ['P6']),
                  target=tgt('', 'pylorus', 'The pyloric stricture', ['P6'])),
            event('E3', EGD, at('dilation', 'dilated', ['P7']), status=at('performed', 'was dilated', ['P7']),
                  technique=at('balloon', '18 mm balloon', ['P7']),
                  target=tgt('', 'distal_esophagus', 'the distal esophageal stricture', ['P7']),
                  time=at('current_encounter', 'At that time', ['P7'])),
            timed_bx]


# the egd4 review's problem-1 input: Corti also proposes 43249 citing P7, beside 43245 citing P6
F1_43249 = case('d154_f1_43245_43249', F1_LINES, f1_events(), [('43245', (PYLORUS,)), ('43249', (ESO_LATER,))])
NAMES.append(F1_43249)
DILATION_QUESTION = 'Was the dilation (balloon) at the distal esophagus (“was dilated”) done at this encounter?'


class D154QuestionOrderClaim(SimpleTestCase):
    """D154 (2) and (3): the order is unchanged; its claim is what the rule does. c2e53f8e on F1 with 43249: 43245 and
    43249 READY, the biopsy listed not covered, no service question; e5628be56 asked the biopsy's question."""

    def test_d154_f1_with_43249_the_dilations_question_is_asked_not_the_biopsys(self):
        result = assessed(F1_43249)
        ready(self, result, '43245')
        held(self, result, '43249', ['act_target'])
        p = proposal(result, '43249')
        with self.subTest(part="43249's records name the pyloric dilation (E2), not the doubted one"):
            self.assertEqual((p.support['reason'], p.support['acts'], p.support['question_events']),
                             (events.ANOTHER_SITE, [], ['E2']))
        with self.subTest(part="the reading's order: the dilation's question, the biopsy's not asked"):
            self.assertEqual([(spec.fact, spec.question) for spec in result.clarifications],
                             [('event_time', DILATION_QUESTION)])
        with self.subTest(part='the biopsy stays listed in doubt'):
            self.assertEqual(items(result), [('dilation', 'in_doubt'), ('biopsy', 'in_doubt')])
        reading = events.Reading.of(built(F1_43249)[0])
        item = {'service': 'gi.egd', 'family': 'gi.egd'}
        for holding in ((), ('E2',)):
            with self.subTest(part="wired with 43249's records, the same question", holding=holding):
                found = coverage.in_doubt_questions(reading, coverage.Coverage(
                    in_doubt=[(item, 'E3'), (item, 'E4')], covered={'gi.egd': ['43245', '43249']}), holding=holding)
                self.assertEqual([spec.question for spec in found], [DILATION_QUESTION])

    def test_d154_holding_is_inert_on_the_live_path(self):
        """assess calls coverage.in_doubt_questions(reading, final, asked) and passes no ``holding`` (the docstring's
        claim): every call in assess.py has three positional arguments and no keyword."""
        tree = ast.parse((APP / 'studio' / 'interpretation' / 'assess.py').read_text(encoding='utf-8'))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == 'in_doubt_questions']
        self.assertEqual([(len(call.args), [k.arg for k in call.keywords]) for call in calls], [(3, [])])
