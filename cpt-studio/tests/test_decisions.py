"""Review decisions (BUILD-SPEC 6; studio.decisions; line identity, FIX-SPEC 1): approve needs the exact attestation for
the reviewer's kind, reject and revoke, append-only rows with the latest per line current, the allowed actions per
status, an agent's label, the audit row and the encounter state each decision leaves. A decision names the round the
page shows and the line; tests/test_line_identity.py holds the findings' cases (two lines with one code, a stale page).
Synthetic data only."""
import json

from django.test import TestCase

from studio import decisions, models, state
from tests.support import rounds as r

Decision = models.CodeDecision
ACK = decisions.ACKNOWLEDGEMENTS


class DecisionCase(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.enc = self.encounter()
        self.round = r.write_round(self.enc, codes=[
            r.row('45385', 'ready'), r.row('43239', 'needs_review', agrees=False, check_reason='Disputed.'),
            r.row('45380', 'needs_answer', question='Was a biopsy taken?'), r.row('43251', 'not_supported')])
        self.client = self.client_for(self.reviewer)

    def decide(self, code, action, *, acknowledgement=None, note='', client=None, line=None, round_number=None):
        """POST a decision as the page sends it: the latest round's number and the line holding ``code``."""
        latest = state.latest_round(self.enc)
        if line is None:
            line = next((row['line'] for row in latest.codes if row.get('code') == code), 'L99')
        body = {'round': latest.number if round_number is None else round_number, 'line': line, 'code': code,
                'action': action, 'note': note,
                'acknowledgement': ACK['human'] if acknowledgement is None and action == 'approve' else
                (acknowledgement or '')}
        return (client or self.client).post(f'/api/encounters/{self.enc.pk}/decisions', data=json.dumps(body),
                                            content_type='application/json')

    def codes(self, client=None):
        payload = (client or self.client).get(f'/api/encounters/{self.enc.pk}').json()
        return payload, {code['code']: code for code in payload['codes']}


class AcknowledgementTests(DecisionCase):
    def test_an_approval_needs_the_attestation_exactly(self):
        for wrong in ('', ACK['human'] + ' ', ACK['human'].lower(), ACK['agent']):
            with self.subTest(acknowledgement=wrong[:30]):
                response = self.decide('45385', 'approve', acknowledgement=wrong or ' ')
                self.assertEqual((response.status_code, response.json()['error']),
                                 (400, decisions.ATTESTATION_REFUSED))
        self.assertEqual(Decision.objects.count(), 0)
        response = self.decide('45385', 'approve', note='Checked against the whole note.')
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual({key: body[key] for key in ('line', 'code', 'action', 'by', 'note')},
                         {'line': 'L1', 'code': '45385', 'action': 'approve', 'by': self.reviewer.label(),
                          'note': 'Checked against the whole note.'})
        decision = Decision.objects.get()
        self.assertEqual((decision.round_id, decision.line, decision.code, decision.reviewer_kind,
                          decision.acknowledgement), (self.round.pk, 'L1', '45385', 'human', ACK['human']))

    def test_an_agent_approves_with_its_own_attestation_and_is_labelled_as_an_agent(self):
        agent = self.client_for(self.agent)
        session = agent.get('/api/session').json()
        self.assertEqual(session['acknowledgement'], ACK['agent'])
        self.assertEqual(self.decide('45385', 'approve', acknowledgement=ACK['human'], client=agent).status_code, 400)
        response = self.decide('45385', 'approve', acknowledgement=ACK['agent'], client=agent)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['by'], 'Reviewbot (automated agent)')
        _, codes = self.codes()
        self.assertEqual(codes['45385']['decision']['by'], 'Reviewbot (automated agent)')
        self.assertEqual(Decision.objects.get().reviewer_kind, 'agent')

    def test_the_attestation_texts_are_exactly_the_d355_texts(self):
        # DECISIONS D355: the earlier attestation's meaning, with its obsolete middle sentence replaced.
        self.assertEqual(decisions.ACKNOWLEDGEMENTS, {
            'human': ('I read the whole source document, not only the quoted passages, and it supports this code as a '
                      'service performed at this encounter. The coding review can be wrong. This synthetic review is not '
                      'clinical approval or billing advice.'),
            'agent': ('I am an automated agent. I read the whole source document, not only the quoted passages, and it '
                      'supports this code as a service performed at this encounter. The coding review can be wrong. This '
                      'agent-executed synthetic review is not clinical approval or billing advice.')})


class ActionTests(DecisionCase):
    def test_reject_then_revoke_then_approve_append_rows_and_the_latest_is_current(self):
        self.round = r.write_round(self.enc, codes=[
            r.row('45385', 'ready'), r.row('43239', 'needs_review', agrees=False, check_reason='Disputed.'),
            r.row('43251', 'not_supported')])
        self.assertEqual(self.codes()[0]['state'], 'needs_review')
        response = self.decide('43239', 'reject', note='The practice codes this differently.')
        self.assertEqual(response.status_code, 201)
        payload, codes = self.codes()
        self.assertEqual(codes['43239']['decision']['action'], 'reject')
        self.assertEqual(codes['43239']['decision']['note'], 'The practice codes this differently.')
        self.assertEqual(codes['43239']['allowed_actions'], ['revoke'])
        self.assertEqual(payload['state'], 'ready')  # the disputed code is decided; a ready code waits
        again = self.decide('43239', 'approve')
        self.assertEqual((again.status_code, again.json()['error']), (409, decisions.DECIDED_ALREADY))
        self.assertEqual(self.decide('43239', 'revoke').status_code, 201)
        payload, codes = self.codes()
        self.assertIsNone(codes['43239']['decision'])
        self.assertEqual(codes['43239']['allowed_actions'], ['approve', 'reject'])
        self.assertEqual(payload['state'], 'needs_review')
        self.assertEqual(self.decide('43239', 'approve').status_code, 201)
        self.assertEqual(self.decide('45385', 'approve').status_code, 201)
        payload, codes = self.codes()
        self.assertEqual((codes['43239']['decision']['action'], payload['state']), ('approve', 'reviewed'))
        rows = list(Decision.objects.filter(code='43239').order_by('sequence'))
        self.assertEqual([row.action for row in rows], ['reject', 'revoke', 'approve'])
        self.assertEqual([row.sequence for row in rows], sorted(row.sequence for row in rows))
        self.assertEqual(set(state.current_decisions(self.round)), {'L2', 'L1'})  # 43239 is L2 of this round
        events = models.AuditEvent.objects.filter(encounter=self.enc, event='decision.recorded').order_by('created_at')
        self.assertEqual([(e.data['line'], e.data['code'], e.data['action']) for e in events],
                         [('L2', '43239', 'reject'), ('L2', '43239', 'revoke'), ('L2', '43239', 'approve'),
                          ('L1', '45385', 'approve')])
        self.assertEqual(payload['readiness'], {'draft': True, 'approved': True, 'blockers': []})
        texts = [item['text'] for item in payload['activity']]
        label = self.reviewer.label()
        self.assertEqual(texts[-4:], [f'{label} rejected 43239.', f'{label} undid the decision on 43239.',
                                      f'{label} approved 43239.', f'{label} approved 45385.'])

    def test_only_the_actions_a_status_allows_are_recorded(self):
        _, codes = self.codes()
        self.assertEqual({code: row['allowed_actions'] for code, row in codes.items()},
                         {'45385': ['approve', 'reject'], '43239': ['approve', 'reject'], '45380': [], '43251': []})
        for code, action, status, message in (
                ('45380', 'approve', 409, decisions.NOT_DECIDABLE['needs_answer']),
                ('43251', 'reject', 409, decisions.NOT_DECIDABLE['not_supported']),
                ('45385', 'revoke', 409, decisions.NOTHING_TO_UNDO),
                ('99999', 'approve', 409, decisions.NOT_IN_ROUND),
                ('45385', 'confirm', 400, 'Choose approve, reject or undo.'),
                ('', 'approve', 400, 'Name the code to decide on.')):
            with self.subTest(code=code, action=action):
                response = self.decide(code, action)
                self.assertEqual((response.status_code, response.json()['error']), (status, message))
        long_note = self.decide('45385', 'reject', note='x' * 2001)
        self.assertEqual((long_note.status_code, long_note.json()['error']),
                         (400, 'The note can be at most 2,000 characters.'))
        self.assertEqual(Decision.objects.count(), 0)

    def test_a_code_too_long_to_record_offers_no_decision(self):
        r.write_round(self.enc, codes=[r.row('LONGCODE99', 'ready')])
        _, codes = self.codes()
        self.assertEqual(codes['LONGCODE99']['allowed_actions'], [])
        response = self.decide('LONGCODE99', 'approve')
        self.assertEqual((response.status_code, response.json()['error']), (409, 'This code cannot be decided here.'))
        self.assertEqual(Decision.objects.count(), 0)

    def test_no_decision_is_recorded_on_a_round_that_is_not_the_latest_done_one(self):
        self.assertEqual(self.decide('45385', 'approve').status_code, 201)
        r.write_round(self.enc, state_=models.CodingRound.QUEUED)
        response = self.decide('45385', 'revoke', line='L1', round_number=1)
        self.assertEqual((response.status_code, response.json()['error']), (409, decisions.ROUND_CHANGED))
        payload, _ = self.codes()
        self.assertEqual((payload['codes'], payload['readiness']['draft']), ([], False))
        self.assertEqual(Decision.objects.count(), 1)

    def test_a_new_round_starts_without_the_earlier_rounds_decisions(self):
        self.assertEqual(self.decide('45385', 'approve').status_code, 201)
        r.write_round(self.enc, codes=[r.row('45385', 'ready')])
        payload, codes = self.codes()
        self.assertIsNone(codes['45385']['decision'])
        self.assertEqual(codes['45385']['allowed_actions'], ['approve', 'reject'])
        self.assertEqual((payload['state'], payload['readiness']['approved']), ('ready', False))
