"""Acts from a page that no longer shows the latest (FIX-SPEC-2 section 5; findings LINES-5, LINES-6, LINES-9). An undo
names the decision it undoes (the id the page shows for the current decision) and a download names the coding review
the page shows; either is refused with "This coding review has changed. Reload to see the latest." when it no longer
matches. The activity names the line with the code. The client contract is customer-2026-11-24. Synthetic data only;
nothing reaches the network."""
import json
from pathlib import Path

from django.conf import settings
from django.test import TestCase

from studio import client_contract, models
from tests.support import coding as f
from tests.support import rounds as r

CHANGED = 'This coding review has changed. Reload to see the latest.'
Decision = models.CodeDecision


class StaleCase(r.CustomerCase, TestCase):
    def payload(self, enc, user=None):
        return self.client_for(user or self.reviewer).get(f'/api/encounters/{enc.pk}').json()

    def post(self, enc, action, body, user=None):
        return self.client_for(user or self.reviewer).post(f'/api/encounters/{enc.pk}/{action}',
                                                          data=json.dumps(body), content_type='application/json')

    def undo(self, enc, line, code, decision, user=None, round_number=1):
        body = {'round': round_number, 'line': line, 'code': code, 'action': 'revoke', 'acknowledgement': '',
                'note': ''}
        if decision is not None:
            body['decision'] = decision
        return self.post(enc, 'decisions', body, user=user)


class UndoNamesItsDecisionTests(StaleCase):
    def test_an_undo_from_a_page_showing_an_earlier_decision_is_refused(self):
        # LINES-5: a stale Undo revoked a rejection its sender never saw
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready')])
        approver = r.f.member(self.ws)
        self.assertEqual(self.decide(enc, 'L1', '45385', 'approve', user=approver).status_code, 201)
        agent_page = self.payload(enc, self.agent)
        shown = agent_page['codes'][0]['decision']
        self.assertEqual((shown['action'], shown['id']), ('approve', str(Decision.objects.get().pk)))
        self.assertEqual(self.undo(enc, 'L1', '45385', shown['id'], user=approver).status_code, 201)
        rejector = r.f.member(self.ws)
        self.assertEqual(self.decide(enc, 'L1', '45385', 'reject', user=rejector, note='Not documented.').status_code,
                         201)
        stale = self.undo(enc, 'L1', '45385', shown['id'], user=self.agent)
        self.assertEqual((stale.status_code, stale.json()['error']), (409, CHANGED))
        current = self.payload(enc)['codes'][0]['decision']
        self.assertEqual((current['action'], current['note']), ('reject', 'Not documented.'))
        self.assertEqual(list(Decision.objects.order_by('sequence').values_list('action', flat=True)),
                         ['approve', 'revoke', 'reject'])
        fresh = self.undo(enc, 'L1', '45385', current['id'], user=self.agent)  # the page reloaded: it names the rejection
        self.assertEqual(fresh.status_code, 201, fresh.content)
        self.assertIsNone(self.payload(enc)['codes'][0]['decision'])

    def test_an_undo_must_name_a_decision_and_one_that_is_gone_is_refused_as_changed(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready'), r.row('45380', 'ready')])
        self.assertEqual(self.decide(enc, 'L1', '45385', 'approve').status_code, 201)
        for decision in (None, '', 7):
            with self.subTest(decision=decision):
                response = self.undo(enc, 'L1', '45385', decision)
                self.assertEqual((response.status_code, response.json()['error']), (400, 'Name the decision to undo.'))
        unknown = self.undo(enc, 'L1', '45385', 'f6100000-0000-4000-8000-000000000001')
        self.assertEqual((unknown.status_code, unknown.json()['error']), (409, CHANGED))
        # the page showed a decision on L2 that is no longer there (or never was): changed, not "nothing to undo"
        other = self.undo(enc, 'L2', '45380', str(Decision.objects.get().pk))
        self.assertEqual((other.status_code, other.json()['error']), (409, CHANGED))
        self.assertEqual(Decision.objects.count(), 1)

    def test_the_decision_answer_and_every_decision_shown_carry_its_id(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready')])
        made = self.decide(enc, 'L1', '45385', 'approve')
        self.assertEqual(made.status_code, 201)
        self.assertEqual(made.json()['id'], str(Decision.objects.get().pk))
        self.assertEqual(self.payload(enc)['codes'][0]['decision']['id'], made.json()['id'])


class ExportNamesItsRoundTests(StaleCase):
    def round_two(self):
        """LINES-6's input: round 1 asks about L2; member A approves L1 on round 1 and keeps that page; member B answers
        and approves round 2's L1, which now carries modifier 25."""
        enc = self.started()
        self.code_round(enc, reader=f.reader_result([f.code('99214'), f.code('20610', 'needs_answer',
                                                                              question='Which knee?')]),
                        checker=f.checker_result([r.review('L1', '99214'), r.review('L2', '20610')]))
        self.assertEqual(self.decide(enc, 'L1', '99214', 'approve').status_code, 201)
        page_a = self.payload(enc)
        member_b = r.f.member(self.ws)
        question = self.payload(enc, member_b)['questions'][0]['id']
        self.assertEqual(self.post(enc, 'answers', {'answers': [{'question_id': question, 'text': 'The right knee.'}]},
                                   user=member_b).status_code, 201)
        self.code_round(enc, reader=f.reader_result([f.code('99214', modifiers=['25']), f.code('20610',
                                                                                              modifiers=['RT'])]),
                        checker=f.checker_result([r.review('L1', '99214'), r.review('L2', '20610')]))
        self.assertEqual(self.decide(enc, 'L1', '99214', 'approve', user=member_b).status_code, 201)
        return enc, page_a

    def test_a_download_from_a_page_showing_an_earlier_round_is_refused(self):
        enc, page_a = self.round_two()
        self.assertEqual(page_a['round']['number'], 1)
        for kind in ('approved', 'draft'):  # the PDF report, the only format since 2026-11-21
            with self.subTest(kind=kind):
                response = self.post(enc, 'reports', {'kind': kind, 'fmt': 'pdf', 'round': page_a['round']['number']})
                self.assertEqual((response.status_code, response.json()['error']), (409, CHANGED))
        self.assertEqual(models.ExportArtifact.objects.count(), 0)
        made = self.post(enc, 'reports', {'kind': 'approved', 'fmt': 'pdf', 'round': 2})
        self.assertEqual(made.status_code, 201, made.content)
        self.assertIn('-r2-', made.json()['filename'])

    def test_a_download_must_name_its_round(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready')])
        for value in (None, '1', 0, True, 1.0):
            with self.subTest(round=value):
                body = {'kind': 'draft', 'fmt': 'pdf'}
                if value is not None:
                    body['round'] = value
                response = self.post(enc, 'reports', body)
                self.assertEqual((response.status_code, response.json()['error']),
                                 (400, 'Name the coding review the export is made from.'))
        self.assertEqual(models.ExportArtifact.objects.count(), 0)
        self.assertEqual(self.post(enc, 'reports', {'kind': 'draft', 'fmt': 'pdf', 'round': 1}).status_code, 201)

    def test_a_round_that_is_named_but_still_running_is_not_ready_yet(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready')])
        r.write_round(enc, state_=models.CodingRound.RUNNING)
        running = self.post(enc, 'reports', {'kind': 'draft', 'fmt': 'pdf', 'round': 2})
        self.assertEqual((running.status_code, running.json()['error']), (409, 'There is nothing to export yet.'))
        stale = self.post(enc, 'reports', {'kind': 'draft', 'fmt': 'pdf', 'round': 1})
        self.assertEqual((stale.status_code, stale.json()['error']), (409, CHANGED))


class ActivityNamesTheLineTests(StaleCase):
    def test_the_activity_names_the_line_of_each_decision(self):
        # LINES-9: "approved 20610." and "rejected 20610." could not be told apart
        enc = self.started()
        self.code_round(enc, reader=f.reader_result([f.code('20610', modifiers=['RT']), f.code('20610',
                                                                                              modifiers=['LT'])]),
                        checker=f.checker_result([r.review('L1', '20610'), r.review('L2', '20610')]))
        self.assertEqual(self.decide(enc, 'L1', '20610', 'approve').status_code, 201)
        self.assertEqual(self.decide(enc, 'L2', '20610', 'reject').status_code, 201)
        self.assertEqual(self.decide(enc, 'L1', '20610', 'revoke').status_code, 201)
        label = self.reviewer.label()
        self.assertEqual([item['text'] for item in self.payload(enc)['activity']][-3:],
                         [f'{label} approved L1 20610.', f'{label} rejected L2 20610.',
                          f'{label} undid the decision on L1 20610.'])


class ClientContractTests(StaleCase):
    def test_the_client_contract_is_the_stale_action_build(self):
        self.assertEqual(client_contract.VERSION, 'customer-2026-11-24')
        for earlier in ('customer-2026-11-21', 'customer-2026-11-20'):
            with self.subTest(earlier=earlier):
                response = self.client_for(self.reviewer).get('/api/session', HTTP_X_CPT_STUDIO_CLIENT=earlier)
                self.assertEqual((response.status_code, response.json()), (409, client_contract.OUTDATED))
        contract = json.loads((Path(settings.BASE_DIR) / 'ops' / 'verification' / 'customer-contract.json')
                              .read_text(encoding='utf-8'))
        self.assertIn('customer-2026-11-24', contract['about'])
        self.assertEqual(contract['types']['decision']['keys']['id'], 'string')

    def test_a_decided_encounter_is_held_to_the_contract(self):
        sc = r.scan_customer()
        enc = self.done()
        self.assertEqual(self.decide(enc, 'L1', '45385', 'approve').status_code, 201)
        self.assertEqual(self.post(enc, 'reports', {'kind': 'approved', 'fmt': 'pdf', 'round': 1}).status_code, 201)
        payload = self.payload(enc)
        self.assertEqual(sc.shape_problems(payload, sc.CONTRACT['encounter']), [])
        self.assertEqual(set(payload['codes'][0]['decision']), {'id', 'action', 'by', 'at', 'note'})
        self.assertEqual([(item['kind'], item['fmt']) for item in payload['reports']], [('approved', 'pdf')])
