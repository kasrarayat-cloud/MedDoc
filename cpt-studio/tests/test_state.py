"""studio.state (BUILD-SPEC 5; line identity, FIX-SPEC 1): the encounter state from the latest coding round and the
current decisions, per line."""
from django.test import TestCase

from studio import models, state
from tests.support import coding as f

Round, Decision = models.CodingRound, models.CodeDecision


def code(code, status, line=None):
    row = {'code': code, 'status': status, 'units': 1, 'modifiers': [], 'listed_by': 'reader'}
    return {'line': line, **row} if line else row


def lines(*rows):
    """Code rows with lines L1.. in order (as fable.result.combine gives the reader's)."""
    return [{'line': f'L{number}', **row} for number, row in enumerate(rows, start=1)]


class StateTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.user = f.member(self.ws)
        self.enc = f.encounter(self.ws, self.user)
        self.rev = f.paste(self.enc, self.user)

    def round(self, round_state=Round.DONE, codes=(), number=None):
        number = number or self.enc.rounds.count() + 1
        return Round.objects.create(encounter=self.enc, revision=self.rev, number=number, trigger=Round.UPLOAD,
                                    context={}, state=round_state, codes=list(codes))

    def decide(self, round_, line, action):
        code = next(row['code'] for row in round_.codes if row.get('line') == line)
        return Decision.objects.create(encounter=self.enc, round=round_, line=line, code=code, action=action,
                                       reviewer=self.user, reviewer_kind='human')

    def test_the_round_states(self):
        for round_state, expected in ((Round.QUEUED, 'processing'), (Round.RUNNING, 'processing'),
                                      (Round.CANCELLED, 'stopped'), (Round.FAILED, 'failed')):
            with self.subTest(round_state=round_state):
                self.round(round_state)  # each a newer round: the latest one decides
                self.assertEqual(state.compute(self.enc), expected)

    def test_a_done_round_reads_its_final_statuses(self):
        cases = [([code('45385', 'ready'), code('45380', 'needs_answer'), code('45378', 'needs_review')],
                  'awaiting_answer'),
                 ([code('45385', 'ready'), code('45378', 'needs_review')], 'needs_review'),
                 ([code('45385', 'ready'), code('45380', 'not_supported')], 'ready'),
                 ([code('45380', 'not_supported')], 'no_codes'),
                 ([], 'no_codes')]
        for codes, expected in cases:
            with self.subTest(expected=expected):
                self.round(codes=codes)
                self.assertEqual(state.compute(self.enc), expected)

    def test_decisions_move_ready_to_reviewed_and_a_revoke_moves_it_back(self):
        round_ = self.round(codes=lines(code('45385', 'ready'), code('45378', 'needs_review'),
                                        code('45380', 'not_supported')))
        self.assertEqual(state.compute(self.enc), 'needs_review')
        self.decide(round_, 'L2', Decision.REJECT)
        self.assertEqual(state.compute(self.enc), 'ready')
        self.decide(round_, 'L1', Decision.APPROVE)
        self.assertEqual(state.compute(self.enc), 'reviewed')
        self.decide(round_, 'L1', Decision.REVOKE)
        self.assertEqual(state.compute(self.enc), 'ready')
        self.decide(round_, 'L1', Decision.REJECT)
        self.assertEqual(state.compute(self.enc), 'reviewed')
        self.assertEqual({key: value.action for key, value in state.current_decisions(round_).items()},
                         {'L2': 'reject', 'L1': 'reject'})

    def test_two_lines_with_one_code_are_decided_apart(self):
        round_ = self.round(codes=lines(code('20610', 'ready'), code('20610', 'needs_review')))
        self.decide(round_, 'L1', Decision.APPROVE)
        self.assertEqual(state.compute(self.enc), 'needs_review')  # the second 20610 line is still undecided
        self.decide(round_, 'L2', Decision.REJECT)
        self.assertEqual(state.compute(self.enc), 'reviewed')
        self.assertEqual({key: value.action for key, value in state.current_decisions(round_).items()},
                         {'L1': 'approve', 'L2': 'reject'})

    def test_decisions_on_an_earlier_round_do_not_count(self):
        first = self.round(codes=lines(code('45385', 'ready')))
        self.decide(first, 'L1', Decision.APPROVE)
        self.assertEqual(state.compute(self.enc), 'reviewed')
        self.round(codes=lines(code('45385', 'ready')))
        self.assertEqual(state.compute(self.enc), 'ready')

    def test_only_the_latest_round_counts(self):
        self.round(Round.FAILED)
        self.round(codes=[code('45385', 'ready')])
        self.assertEqual(state.compute(self.enc), 'ready')

    def test_refresh_writes_the_state_and_its_label_exists(self):
        self.round(codes=[code('45385', 'ready')])
        self.assertEqual(state.refresh(self.enc), 'ready')
        self.enc.refresh_from_db()
        self.assertEqual((self.enc.state, state.label(self.enc.state)), ('ready', 'Ready for approval'))
        self.assertEqual(set(state.LABELS), {'processing', 'stopped', 'failed', 'awaiting_answer', 'needs_review',
                                             'ready', 'reviewed', 'no_codes'})
        self.assertEqual(state.label('failed'), 'Could not finish')

    def test_an_encounter_with_no_round_keeps_its_state(self):
        models.Encounter.objects.filter(pk=self.enc.pk).update(state='ready_for_review')
        self.enc.refresh_from_db()
        self.assertIsNone(state.compute(self.enc))
        self.assertEqual(state.refresh(self.enc), 'ready_for_review')


# --- release 2, R2-25: one read of the round and its decisions (RELEASE-2-SPEC R2-25; 2.1) ------------------------------
# state.py changes by extraction only: compute's rules move verbatim into derive (its one change: the current decisions
# a caller has read are used, current_decisions(round_) otherwise), and current_decisions' loop into current_of. Release
# 1's compute and current_decisions (studio/state.py at 9ee0c85be) are kept here verbatim as the oracle: run on every
# round state and decision history, and compared statement by statement with the moved text.

import ast  # noqa: E402 - this section's own imports
import inspect  # noqa: E402
import random  # noqa: E402
import textwrap  # noqa: E402

R2_25_RELEASE_1_STATE_SOURCE = '''
def current_decisions(round_) -> dict[str, models.CodeDecision]:
    """{line: its current decision} for ``round_``: the latest row per line by sequence; a revoke leaves none."""
    current: dict[str, models.CodeDecision] = {}
    for decision in Decision.objects.filter(round_id=round_.pk).select_related('reviewer').order_by('sequence'):
        if decision.action == Decision.REVOKE:
            current.pop(decision.line, None)
        else:
            current[decision.line] = decision
    return current


def compute(encounter) -> Optional[str]:
    """The state ``encounter`` reads now, or None when it has no coding round."""
    round_ = latest_round(encounter)
    if round_ is None:
        return None
    if round_.state in (Round.QUEUED, Round.RUNNING):
        return PROCESSING
    if round_.state == Round.CANCELLED:
        return STOPPED
    if round_.state != Round.DONE:
        return FAILED
    codes = [code for code in round_.codes or () if isinstance(code, dict)]
    if any(code.get('status') == 'needs_answer' for code in codes):
        return AWAITING_ANSWER
    decided = {line for line, decision in current_decisions(round_).items() if decision.action in DECIDED}
    for status, state in (('needs_review', NEEDS_REVIEW), ('ready', READY)):
        if any(code.get('status') == status and code.get('line') not in decided for code in codes):
            return state
    if any(code.get('status') in ('needs_review', 'ready') for code in codes):
        return REVIEWED
    return NO_CODES
'''
# the one change R2-25 makes to a rule line (RELEASE-2-SPEC R2-25, "derive")
R2_25_CHANGED_FROM = 'current_decisions(round_).items()'
R2_25_CHANGED_TO = '(current if current is not None else current_decisions(round_)).items()'


def r2_25_release_1():
    """(compute, current_decisions) of release 1, run in a namespace of today's module: the oracle."""
    namespace = dict(vars(state))
    exec(compile(R2_25_RELEASE_1_STATE_SOURCE, 'release-1-state', 'exec'), namespace)  # noqa: S102 - the oracle's text
    return namespace['compute'], namespace['current_decisions']


def r2_25_body(function_source, name):
    """The statements of ``name``'s body in ``function_source``, its docstring left out."""
    tree = ast.parse(textwrap.dedent(function_source))
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name)
    body = node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    return body


class R2DeriveTests(TestCase):
    """derive(latest_round(e), current_of(decisions_of(r))) equals compute(e) - and release 1's compute - for every round
    state and every decision history, revokes included; compute is the one line that calls derive."""

    setUp, round = StateTests.setUp, StateTests.round  # the fixture of the tests above, not their tests

    CODE_SETS = (
        [],
        [code('45385', 'ready', 'L1')],
        [code('45378', 'needs_review', 'L1')],
        lines(code('45385', 'ready'), code('45378', 'needs_review'), code('45380', 'not_supported')),
        lines(code('45385', 'ready'), code('45380', 'needs_answer')),
        lines(code('20610', 'ready'), code('20610', 'needs_review')),  # one code on two lines
        [code('45385', 'ready'), code('45378', 'needs_review')],  # rows written with no line (an older shape)
        [*lines(code('45385', 'ready')), 'not a row', None, {'status': 'ready', 'line': 'L9'}],
    )
    STEPS = [(line, action) for line in ('L1', 'L2') for action in (Decision.APPROVE, Decision.REJECT,
                                                                    Decision.REVOKE)]

    def assert_same(self, round_, release_1_compute, where):
        derived = state.derive(state.latest_round(self.enc), state.current_of(state.decisions_of(round_)))
        expected = release_1_compute(self.enc)
        self.assertEqual((derived, state.compute(self.enc), state.derive(state.latest_round(self.enc))),
                         (expected, expected, expected), where)

    def history(self, round_, steps):
        for line, action in steps:
            codes = {row.get('line'): row.get('code') for row in round_.codes if isinstance(row, dict)}
            Decision.objects.create(encounter=self.enc, round=round_, line=line, code=codes.get(line) or '45385',
                                    action=action, reviewer=self.user, reviewer_kind='human')

    def test_derive_equals_compute_and_release_1_for_every_round_state(self):
        release_1_compute, _ = r2_25_release_1()
        self.assertIsNone(state.derive(None))
        self.assertEqual(release_1_compute(self.enc), state.compute(self.enc))  # no round at all: None, both
        for round_state in (Round.QUEUED, Round.RUNNING, Round.CANCELLED, Round.FAILED, Round.DONE):
            for codes in self.CODE_SETS:
                round_ = self.round(round_state, codes=codes)
                self.history(round_, [('L1', Decision.APPROVE)])
                self.assert_same(round_, release_1_compute, (round_state, codes))

    def test_derive_equals_release_1_for_every_history_of_two_steps_and_for_long_random_ones(self):
        release_1_compute, release_1_current = r2_25_release_1()
        histories = [[]] + [[step] for step in self.STEPS] + [[a, b] for a in self.STEPS for b in self.STEPS]
        seen = set()
        for codes in self.CODE_SETS:
            for steps in histories:
                round_ = self.round(codes=codes)
                self.history(round_, steps)
                self.assert_same(round_, release_1_compute, (codes, steps))
                self.assertEqual({line: row.pk for line, row in state.current_decisions(round_).items()},
                                 {line: row.pk for line, row in release_1_current(round_).items()})
                seen.add(release_1_compute(self.enc))
        chance = random.Random(20261126)  # seeded: the same walks every run
        for codes in self.CODE_SETS:
            for _walk in range(3):
                round_ = self.round(codes=codes)
                for _step in range(12):  # checked after every decision of a walk over three lines
                    self.history(round_, [(chance.choice(('L1', 'L2', 'L3')),
                                           chance.choice((Decision.APPROVE, Decision.REJECT, Decision.REVOKE)))])
                    self.assert_same(round_, release_1_compute, (codes, 'walk'))
                    seen.add(release_1_compute(self.enc))
        # the table is not vacuous: every state a done round can read was reached
        self.assertLessEqual({'awaiting_answer', 'needs_review', 'ready', 'reviewed', 'no_codes'}, seen)

    def test_the_current_decisions_given_are_the_ones_used(self):
        round_ = self.round(codes=lines(code('45385', 'ready')))
        self.history(round_, [('L1', Decision.APPROVE)])
        self.assertEqual(state.derive(round_), 'reviewed')
        self.assertEqual(state.derive(round_, {}), 'ready')  # an empty reading is a reading: none decided
        self.assertEqual(state.derive(round_, state.current_of(state.decisions_of(round_))), 'reviewed')
        with self.assertNumQueries(0):
            state.derive(round_, {})
        with self.assertNumQueries(1):
            found = state.decisions_of(round_)
        with self.assertNumQueries(0):
            self.assertEqual([row.reviewer.pk for row in found], [self.user.pk])  # the reviewer came with it

    def test_compute_is_one_line_and_the_rules_moved_verbatim(self):
        compute_body = r2_25_body(inspect.getsource(state.compute), 'compute')
        self.assertEqual([ast.unparse(item) for item in compute_body], ['return derive(latest_round(encounter))'])
        current_body = r2_25_body(inspect.getsource(state.current_decisions), 'current_decisions')
        self.assertEqual([ast.unparse(item) for item in current_body], ['return current_of(decisions_of(round_))'])
        self.assertEqual(R2_25_RELEASE_1_STATE_SOURCE.count(R2_25_CHANGED_FROM), 1)
        moved = R2_25_RELEASE_1_STATE_SOURCE.replace(R2_25_CHANGED_FROM, R2_25_CHANGED_TO)
        release_1_rules = r2_25_body(moved, 'compute')[1:]  # after `round_ = latest_round(encounter)`
        self.assertEqual(ast.unparse(r2_25_body(R2_25_RELEASE_1_STATE_SOURCE, 'compute')[0]),
                         'round_ = latest_round(encounter)')
        self.assertEqual([ast.dump(item) for item in r2_25_body(inspect.getsource(state.derive), 'derive')],
                         [ast.dump(item) for item in release_1_rules])
        loop = r2_25_body(R2_25_RELEASE_1_STATE_SOURCE, 'current_decisions')
        today = r2_25_body(inspect.getsource(state.current_of), 'current_of')
        self.assertEqual([ast.dump(item) for item in today[:1] + today[2:]], [ast.dump(item) for item in loop[:1] + loop[2:]])
        self.assertEqual(ast.unparse(today[1].iter), 'decisions')  # the loop reads what it is given, nothing else
        self.assertEqual(ast.dump(today[1].body[0]), ast.dump(loop[1].body[0]))
