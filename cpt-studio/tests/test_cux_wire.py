"""The integration of the core repair and customer interface (2026-11-03): the seams between P3's review overlay, P5's
details flow and progress, and P4's customer contract.

- A member's "Not documented" or "Cannot confirm" (P5's MemberAnswer, read back through review._member_answers) is
  applied by the overlay everywhere a status or an action is read: the allowed actions, readiness, coding completeness,
  the customer payload, the operator payload, both report snapshots and the approved export - until it is withdrawn.
- The approved customer export is stale exactly when its DECISION MARKER moves (the live assessment, the current
  context, the current decisions, the standing answers), never for anything that is not a decision: a queued job, a run
  no assessment reads, an operator report, new customer wording (critic C8).

DB-backed; synthetic data only; nothing is sent (the engine's own results are persisted, as P3's suite persists them).
"""
import json
from unittest import mock

from django.test import Client, TestCase

from studio import answers, customer_api, jobs, models, progress, reports, review
from tests.support import factories as f
from tests.support import operator as ops
from tests.support import pipeline_factories as pf
from tests.test_cux_review import allowed, decide, persist

COLON = 'gi.colonoscopy'
BASE_ROW = answers.detail_id('base_included', COLON, '45378')


class WireCase(TestCase):
    def client_for(self, user):
        client = Client(enforce_csrf_checks=False)
        client.force_login(user)
        return client

    def payload(self, s, user=None):
        response = self.client_for(user or s.reviewer).get(f'/api/encounters/{s.encounter.pk}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def post(self, s, path, body, user=None):
        return self.client_for(user or s.reviewer).post(path, data=json.dumps(body), content_type='application/json')

    def codes(self, doc):
        return {code['code']: code for code in doc['codes']}

    def export(self, s, kind='approved', fmt='txt', user=None):
        response = self.post(s, f'/api/encounters/{s.encounter.pk}/reports', {'kind': kind, 'fmt': fmt}, user)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def download(self, s, report, user=None):
        return self.client_for(user or s.reviewer).get(report['download_url'])

    def listed(self, s, report):
        return {item['id']: item for item in self.payload(s)['reports']}[report['id']]['current']


class MemberAnswerEffectTests(WireCase):
    def test_an_overlay_question_answered_not_documented_excludes_the_code_everywhere_until_withdrawn(self):
        """R8 D14's shape: reinstating 45385 beside a selected 45378 makes the overlay ask whether 45378 is reported
        separately - a question no stored row holds. Answered "not documented" through the details endpoint, 45378 is
        excluded in every reader; withdrawn, it is asked again."""
        s = persist('denied')
        decide(s, '45385', 'reinstate', note='Synthetic: the reviewer reads the snare as done.')
        assessment = s.encounter.current_assessment
        self.assertFalse(assessment.clarifications.filter(fact='base_included').exists())  # the overlay's own question
        doc = self.payload(s)
        (row,) = [item for item in doc['details_needed'] if item['id'] == BASE_ROW]
        self.assertEqual((row['control'], row['affects'], row['allow'], row['saved']),
                         ('confirm', ['45378'], ['not_documented', 'cannot_confirm'], None))
        self.assertEqual((self.codes(doc)['45378']['status'], self.codes(doc)['45378']['detail_ids']),
                         ('needs_detail', [BASE_ROW]))
        self.assertNotIn('approve', self.codes(doc)['45378']['allowed_actions'])

        saved = self.post(s, f'/api/encounters/{s.encounter.pk}/details',
                          {'answers': [{'id': BASE_ROW, 'fact': 'base_included', 'value': 'not_documented'}]})
        self.assertEqual(saved.status_code, 201, saved.content)
        (answer,) = models.MemberAnswer.objects.filter(encounter=s.encounter)
        self.assertEqual((answer.code, answer.family, answer.fact, answer.value),
                         ('45378', COLON, 'base_included', 'not_documented'))
        self.assertEqual(review._member_answers(assessment), answers.saved_answers(assessment))

        # every reader of the overlay
        view = review.effective_view(assessment)[assessment.proposals.get(code='45378').key]
        self.assertEqual((view.status, view.reason, view.answer), ('excluded', 'detail_unavailable', 'not_documented'))
        self.assertEqual(allowed(s, '45378'), [])
        self.assertEqual(review.readiness(s.encounter)['blockers'], ['45385 was reinstated and has no decision'])
        self.assertIn('45378 excluded: a needed detail was answered as not documented or not confirmable',
                      review.coding_completeness(s.encounter)['reasons'])
        doc = self.payload(s)
        code = self.codes(doc)['45378']
        self.assertEqual((code['status'], code['sub_label'], code['allowed_actions'], code['why']['quotes']),
                         ('excluded', customer_api.UNAVAILABLE_SUB_LABEL, [], []))
        self.assertEqual(doc['readiness']['blockers'], ['45385 was reinstated and has no decision yet.'])
        (row,) = [item for item in doc['details_needed'] if item['id'] == BASE_ROW]
        self.assertEqual((row['saved']['value'], row['saved']['answer_id']), ('not_documented', str(answer.pk)))
        operator = ops.client(f.user('platform-operator'))
        full = operator.get(f'/ops/api/encounters/{s.encounter.pk}').json()
        self.assertEqual({p['code']: p['status'] for p in full['assessment']['proposals']}['45378'], 'excluded')
        draft = {item['code']: item for item in reports.snapshot(s.encounter, reports.DRAFT)['proposals']}
        self.assertEqual(draft['45378']['list'], 'excluded')

        # the rest decided, the approved export lists the approved code only
        decide(s, '45385', 'approve', user=s.agent)
        self.assertTrue(self.payload(s)['readiness']['approved'])
        approved = self.export(s)
        body = self.download(s, approved).content.decode()
        self.assertIn('1. 45385 — units 1', body)
        self.assertNotIn('45378', body)
        listing = self.download(s, self.export(s, kind='draft')).content.decode()
        self.assertIn('45378 — Excluded', listing)
        self.assertIn(customer_api.UNAVAILABLE_SUB_LABEL, listing)

        # withdrawn: the detail is asked again, the code waits again, and the export made meanwhile is stale
        revoked = self.post(s, f'/api/encounters/{s.encounter.pk}/details/{answer.pk}/revoke', {})
        self.assertEqual(revoked.status_code, 201, revoked.content)
        self.assertEqual(review._member_answers(assessment), [])
        doc = self.payload(s)
        self.assertEqual(self.codes(doc)['45378']['status'], 'needs_detail')
        self.assertEqual((doc['readiness']['approved'], doc['readiness']['blockers']), (False, ['45378 needs a detail.']))
        self.assertEqual(self.download(s, approved).status_code, 409)

    def test_a_rejected_code_s_stored_question_asks_nothing_until_the_rejection_is_revoked(self):
        s = persist('selected')
        self.assertIn(BASE_ROW, [item['id'] for item in self.payload(s)['details_needed']])
        decide(s, '45378', 'reject', note='Synthetic: included in the snare removal.')
        doc = self.payload(s)
        self.assertNotIn(BASE_ROW, [item['id'] for item in doc['details_needed']])
        self.assertEqual(self.codes(doc)['45378']['status'], 'excluded')
        self.assertNotEqual(progress.encounter_progress(s.encounter)['phase'], 'awaiting_detail')
        decide(s, '45378', 'revoke')
        self.assertIn(BASE_ROW, [item['id'] for item in self.payload(s)['details_needed']])

    def test_cannot_confirm_on_a_stored_question_excludes_the_code_as_not_confirmable(self):
        s = persist('selected')  # 45378 held on its stored base_included question beside 45385
        doc = self.payload(s)
        (row,) = [item for item in doc['details_needed'] if item['id'] == BASE_ROW]
        self.assertEqual(self.codes(doc)['45378']['status'], 'needs_detail')
        self.post(s, f'/api/encounters/{s.encounter.pk}/details',
                  {'answers': [{'id': row['id'], 'fact': 'base_included', 'value': 'cannot_confirm'}]})
        code = self.codes(self.payload(s))['45378']
        self.assertEqual((code['status'], code['sub_label']),
                         ('excluded', customer_api.UNAVAILABLE_SUB_LABELS['cannot_confirm']))
        self.assertEqual(review.readiness(s.encounter)['blockers'], ['45385 has no decision'])


class ApprovedExportMarkerTests(WireCase):
    """An approved export answers 409 exactly when the decisions it was made from changed (critic C8)."""

    def setUp(self):
        self.s = persist('pair')  # 45380 and 45385 on separate lesions, each with the separate-lesion modifier review
        for code, modifiers in (('45380', ['XS']), ('45385', [])):
            proposal = self.s.encounter.current_assessment.proposals.get(code=code)
            response = self.post(self.s, f'/api/encounters/{self.s.encounter.pk}/decisions', {
                'proposal_id': str(proposal.pk), 'action': 'approve', 'modifiers': modifiers,
                'acknowledgement': review.ACKNOWLEDGEMENTS['agent']}, self.s.agent)
            self.assertEqual(response.status_code, 201, response.content)
        self.report = self.export(self.s)
        self.assertEqual(self.download(self.s, self.report).status_code, 200)
        self.marker = reports.customer_marker(self.s.encounter)

    def assertCurrent(self):
        self.assertEqual(reports.customer_marker(self.s.encounter), self.marker)
        self.assertEqual(self.download(self.s, self.report).status_code, 200)
        self.assertTrue(self.listed(self.s, self.report))

    def assertStale(self):
        stale = self.download(self.s, self.report)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()['error'], customer_api.STALE_EXPORT)
        self.assertFalse(self.listed(self.s, self.report))

    def test_nothing_that_is_not_a_decision_makes_it_stale(self):
        s = self.s
        self.assertIn('modifiers: XS', self.download(s, self.report).content.decode())
        # a stage queued (readiness waits, so a snapshot of readiness would have moved) and then finished
        job = pf.job(s.encounter, s.revision, models.Job.ASSESS, models.Job.QUEUED, context=s.encounter.current_context)
        self.assertFalse(self.payload(s)['readiness']['approved'])
        self.assertCurrent()
        models.Job.objects.filter(pk=job.pk).update(state=models.Job.SUCCEEDED)
        # a run no assessment reads, and an operator's own report
        pf.provider_run(s.encounter, s.revision, state='failed')
        operator = f.user('platform-operator')
        ops.grant(operator)
        reports.generate(s.encounter, reports.DRAFT, 'txt', operator, operator=True)
        self.assertCurrent()
        # new customer wording: the summary sentence and the limitations a release words differently
        with mock.patch.object(customer_api, 'LIMITATIONS', customer_api.LIMITATIONS + ('A reworded limitation.',)), \
                mock.patch.object(customer_api, 'code_summary', lambda proposal, view: 'Reworded summary.'):
            self.assertIn('Reworded summary.', json.dumps(self.payload(s)))
            self.assertCurrent()

    def test_every_part_of_the_decision_marker_makes_it_stale(self):
        s = self.s
        proposal = s.encounter.current_assessment.proposals.get(code='45385')
        revoked = self.post(s, f'/api/encounters/{s.encounter.pk}/decisions',
                            {'proposal_id': str(proposal.pk), 'action': 'revoke'}, s.agent)
        self.assertEqual(revoked.status_code, 201, revoked.content)
        self.assertStale()
        again = self.post(s, f'/api/encounters/{s.encounter.pk}/decisions', {
            'proposal_id': str(proposal.pk), 'action': 'approve',
            'acknowledgement': review.ACKNOWLEDGEMENTS['agent']}, s.agent)
        self.assertEqual(again.status_code, 201, again.content)
        self.assertStale()  # the same codes approved again: a new decision, so not the export's
        fresh = self.export(s)
        self.assertEqual(self.download(s, fresh).status_code, 200)
        self.report, self.marker = fresh, reports.customer_marker(s.encounter)
        jobs.change_context(s.encounter, s.reviewer, {'setting': 'office'})  # a member's saved detail value
        self.assertStale()
