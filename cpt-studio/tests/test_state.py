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
