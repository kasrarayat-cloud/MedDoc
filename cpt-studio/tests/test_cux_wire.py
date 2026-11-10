"""The integration of the core repair and customer interface (2026-11-03): the seams between P3's review overlay, P5's
details flow and progress, and P4's customer contract.

- A member's "Not documented" or "Cannot confirm" (P5's MemberAnswer, read back through review._member_answers) is
  applied by the overlay everywhere a status or an action is read: the allowed actions, readiness, coding completeness,
  the customer payload, the operator payload, both report snapshots and the approved export - until it is withdrawn.
- The approved customer export is stale exactly when its DECISION MARKER moves (the live assessment, the current
  context, the current decisions, the standing answers), never for anything that is not a decision: a queued job, a run
  no assessment reads, an operator report, new customer wording (critic C8).
- "Taking longer than usual" is drawn from the bound each stage really has where it runs, and its wording promises no
  stop the page does not make (critic C4).

DB-backed; synthetic data only; nothing is sent (the engine's own results are persisted, as P3's suite persists them).
"""
import inspect
import json
import re
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.test import Client, SimpleTestCase, TestCase

from studio import answers, customer_api, jobs, models, progress, reports, review
from tests.legacy_chain import applied
from tests.support import factories as f
from tests.support import operator as ops
from tests.support import pipeline_factories as pf
from tests.test_cux_flow import DetailsCase, ProgressCase, asks
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
        # bound to the overlay's own question as it is asked (completion repair 2026-11-06, U11): the overlay reads it
        self.assertEqual(review._member_answers(assessment),
                         [{key: item[key] for key in ('code', 'family', 'fact', 'value', 'answer_id')}
                          for item in answers.saved_answers(assessment)])
        self.assertEqual(answer.question, review.asked_fingerprints(assessment)[('45378', COLON, 'base_included')])

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


class DateHoldRowsTests(DetailsCase):
    """While a member's date conflicts with the document, the date is the one detail asked (the page says "Choose the
    date of service. Nothing is checked until you do."): every other question belongs to a reading made without a
    settled date."""

    def test_only_the_date_is_asked_while_it_is_held_and_the_rest_once_it_is_settled(self):
        encounter = self.context_for(pf.GI_NOTE, '1998-01-01')
        held = pf.assess(encounter, pf.result(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent')))
        encounter.refresh_from_db()
        self.assertTrue(progress.date_held(encounter))
        rows = answers.details_needed(encounter, held, review.effective_view(held))
        self.assertEqual([(row['fact'], row['choices']) for row in rows],
                         [('service_date', [{'value': 'use_document', 'label': 'Use document date'}])])
        extent = {'id': answers.detail_id('extent', COLON, '45385'), 'fact': 'extent', 'value': 'not_documented'}
        with self.assertRaisesMessage(jobs.Refused, answers.STALE):
            answers.save_details(encounter, self.s.reviewer, [extent])
        pf.context(encounter, encounter.current_revision, fact_values=pf.facts())  # the document's own date in force
        settled = pf.assess(encounter, pf.result(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent')))
        encounter.refresh_from_db()
        self.assertFalse(progress.date_held(encounter))
        rows = answers.details_needed(encounter, settled, review.effective_view(settled))
        self.assertEqual([(row['fact'], row['affects']) for row in rows], [('extent', ['45385'])])


@applied
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


class SlowWordingTests(ProgressCase):
    """"Taking longer than usual" from the bounds that are enforced (critic C4), worded as a display threshold."""

    def progress(self, now):
        self.enc.refresh_from_db()
        return progress.encounter_progress(self.enc, now)

    def test_each_stage_s_bound_is_the_one_enforced_where_it_runs(self):
        self.assertEqual({kind: progress.stage_bound(kind) for kind in (
            'extract', 'analyze', 'predict', 'review2', 'assess', 'astra', 'fable', 'astra_peer', 'fable_peer')}, {
            'extract': 240, 'analyze': 60, 'predict': 150, 'review2': 150, 'assess': 120,
            'astra': 580, 'fable': 580, 'astra_peer': 580, 'fable_peer': 580})
        # read where each is enforced, so a change there moves the threshold with it
        self.assertIn('timeout_s=settings.EXTRACTION_TIMEOUT_SECONDS', inspect.getsource(jobs._limits))
        self.assertIn('deadline_s=settings.PROVIDER_READ_TIMEOUT_SECONDS + 30', inspect.getsource(jobs._send))
        self.assertIn("seconds=settings.JOB_DEADLINE_SECONDS['assess']", inspect.getsource(jobs.stage_assess))
        self.assertIn('settings.JOB_DEADLINE_SECONDS.get(job.kind', inspect.getsource(jobs._check_loop_time))
        self.assertEqual(settings.EXTRACTION_TIMEOUT_SECONDS, 240)
        self.assertNotEqual(settings.JOB_DEADLINE_SECONDS['extract'], progress.stage_bound('extract'))
        self.assertNotEqual(settings.JOB_DEADLINE_SECONDS['predict'], progress.stage_bound('predict'))

    def test_slow_past_sixty_percent_of_the_real_bound_overdue_past_it(self):
        for kind, before in (('extract', ()), ('predict', ('extract', 'analyze'))):
            with self.subTest(kind):
                models.Job.objects.filter(encounter=self.enc).delete()
                self.chain(*before)
                running = self.job(kind, 'running', 2 * len(before))
                bound = progress.stage_bound(kind)
                for share, slow, message in ((0.59, False, progress.MESSAGES['processing']),
                                             (0.61, True, progress.SLOW_MESSAGES[kind]),
                                             (1.01, True, progress.OVERDUE)):
                    out = self.progress(now=running.started_at + timedelta(seconds=share * bound))
                    self.assertEqual((out['phase'], out['slow'], out['message']), ('processing', slow, message), share)

    def test_no_slow_wording_implies_a_limit_the_page_enforces(self):
        promised = re.compile(r'(?i)automatic|\bwill (?:be )?(?:stop|end|cancel|start)|\blimit|deadline|time ?out|'
                              r'timed out|expire|cut off|\bstopped\b')
        for message in [*progress.SLOW_MESSAGES.values(), progress.OVERDUE, progress.QUEUE_SLOW, progress.TAKING_TURN]:
            self.assertIsNone(promised.search(message), message)


class UnresolvedWordingTests(SimpleTestCase):
    def test_an_office_visit_without_a_code_is_documented_not_merely_mentioned(self):
        """reconcile.Unresolved names a service performed today with no supported code: an office visit among them is
        documented (its time or decision making are in the note), so it is never said to be "not documented"."""
        completeness = {'unresolved_items': [{'service': 'S1', 'family': 'gi.office_em', 'act': '',
                                              'reason': 'no_proposal'}]}
        self.assertEqual(customer_api._unresolved(completeness, [{'id': 'S1', 'family': 'gi.office_em',
                                                                  'status': 'performed'}]),
                         ['Office / outpatient evaluation and management: no supported code was found for it.'])
        self.assertEqual(customer_api._unresolved({}, [{'id': 'S1', 'family': 'gi.office_em', 'status': 'uncertain'}]),
                         ['An office visit is mentioned but is not documented as a separate service.'])


class OverlayBlockerWordingTests(SimpleTestCase):
    def test_every_blocker_the_overlay_raises_is_worded_for_the_member(self):
        """The readiness blockers of an approval the review overlay no longer supports (review_view.review_view,
        _held_blocker) in the member's words, never the generic sentence nor the machinery's."""
        from tests.test_cux_review import D14_BLOCKER
        cases = {
            D14_BLOCKER: '45378 was approved, but 45385 was reinstated: its diagnostic examination is normally included '
                         'in that intervention; undo one of the decisions.',
            '45378 was approved, but a detail it needs was answered as not documented: revoke the approval':
                '45378 was approved, but a detail it needs was answered as not documented; undo the decision.',
            '43235 was approved, but its examination is the endoscopic portion of the endoscopic ultrasound documented '
            'with it and is normally included in it; revoke the approval':
                '43235 was approved, but its examination is part of the endoscopic ultrasound documented with it and is '
                'normally included in it; undo the decision.',
            '45378 was approved, but the documented colonoscopy includes snare removal, which this diagnostic code does '
            'not account for; revoke the approval':
                '45378 was approved, but the documented colonoscopy includes snare removal, which this diagnostic code '
                'does not account for; undo the decision.',
            '45378 was approved, but it now needs clarification; revoke the approval':
                '45378 was approved, but it now needs a detail; undo the decision.',
            '45380 was approved with modifier XS, but the separate-lesion modifier review no longer applies to it; revoke '
            'the approval and decide it again':
                '45380 was approved with modifier XS, but the separate-lesion modifier review no longer applies to it; '
                'undo the decision and decide it again.',
        }
        for blocker, words in cases.items():
            with self.subTest(blocker):
                self.assertEqual(customer_api.customer_blocker(blocker), words)
        # a composed tail the guard refuses falls back to the generic sentence
        self.assertEqual(customer_api.customer_blocker('45378 was approved, but the documented colonoscopy includes the '
                                                       'routing reading, which this diagnostic code does not account '
                                                       'for; revoke the approval'), 'The review is not complete yet.')
