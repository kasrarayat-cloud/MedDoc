"""Refutation round 3 of the core repair and customer interface (2026-11-04), repair owner "overlay-r3": the details
save's stored state, the office visit a reinstated same-day procedure holds, and the re-check's activity line. Each
finding is reproduced first by the test that names it (refute-r3: lens B's B-01 and B-05, lens C's C-R3-1, C-R3-2 and
C-R3-3).

- B-01 / C-R3-1: every details save - a confirmation of the date, a removal, a correction, a value, an answer - leaves
  the stored list state (Encounter.state: what the document, the list, the review queue and its badge read) equal to
  the derived state (review._derive_state). A save that only confirmed the upload date had left a finished review
  "Ready for review" and on the queue, beside an approved export it allowed.
- B-05: an office visit that a reviewer's reinstatement of a same-day procedure holds is asked what it waits for - a
  significant, separately identifiable visit (fact separate_em), as beside a procedure the engine selected - and reads
  "Needs a detail" with the row that asks it: never "Ready for review" beside no approve.
- C-R3-2: while a re-check's outcome is being confirmed the activity never says it could not be completed.
- C-R3-3: a re-check whose unknown outcome was reconciled says once that it could not be completed, whichever path
  left the outcome unknown (a read that timed out after sending, a worker that died mid-send, an outcome that could
  not be recorded), as the progress panel says it then.

Synthetic data only; every provider is an in-process fake (no network).
"""
import hashlib
import json
from dataclasses import replace
from datetime import timedelta
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from studio import answers, audit, customer_api, jobs, models, progress, review
from studio.types import RawExchange
from studio.validation import checks
from tests.support import pipeline_factories as pf
from tests.test_cux_r2_details import HEAD, NO_DATE, TWO_DATES, PipelineCase
from tests.test_cux_r2_overlay import (EM, NO_COLONOSCOPY, OFFICE_READY_DENIED, VISIT, ApiCase, answer, persist_input,
                                       shape_of)
from tests.test_cux_review import actions, decide
from tests.test_pipeline_api import drain
from tests.test_repairs_7c8_p1reports import COLONOSCOPY
from tests.test_repairs_gi2_present import BIOPSY, SNARE, Harness
from tests.test_repairs_r4c_lead_review import excluded_em_result, selected_em_result
from tests.test_services_second_review import TwoPassProvider

SAME_DAY_WORDS = customer_api.WITHHELD_WORDS[review.SAME_DAY_EM_GATE]
# the visit with no basis for its level, beside two documented dates: its basis is asked and the date confirmed
BASIS_LINE = 'Established patient seen for reflux.'
TWO_DATES_NO_BASIS = (HEAD + 'Office visit\nDate of service: 2026-10-20\nPlace of service: office\n'
                      'Date of service: 2026-10-21\n' + BASIS_LINE + '\n')


def state_pair(encounter):
    """(the stored list state, the state derived from the rows now)."""
    encounter = models.Encounter.objects.get(pk=encounter.pk)
    return encounter.state, review._derive_state(encounter)


# --- B-01 / C-R3-1: the stored state follows every details save ------------------------------------------------------

class DetailsSaveRefreshesTheStoredStateTests(PipelineCase):
    def decide(self, encounter_id, code, action='approve'):
        encounter = self.encounter(encounter_id)
        proposal = encounter.current_assessment.proposals.get(code=code)
        body = {'proposal_id': str(proposal.pk), 'action': action, 'note': 'Synthetic review.'}
        if action == 'approve':
            body['acknowledgement'] = review.ACKNOWLEDGEMENTS['human']
        response = self.client.post(f'/api/encounters/{encounter_id}/decisions', content_type='application/json',
                                    data=json.dumps(body))
        self.assertEqual(response.status_code, 201, response.content)

    def listed(self, encounter_id):
        (row,) = [item for item in self.client.get('/api/encounters').json()['encounters'] if item['id'] == encounter_id]
        return row

    def assert_current(self, encounter_id, where=''):
        stored, derived = state_pair(self.encounter(encounter_id))
        self.assertEqual(stored, derived, where)
        return stored

    def test_confirming_the_upload_date_last_completes_the_review_on_every_surface(self):
        """B-01's input: 99213 approved, then - as the last act - the upload date confirmed in the details panel."""
        encounter_id = self.upload(TWO_DATES, '2026-10-21')
        self.decide(encounter_id, '99213')
        self.assertEqual(review.readiness(self.encounter(encounter_id))['blockers'], [review.DATE_CONFIRMATION_BLOCKER])
        self.assertEqual(self.assert_current(encounter_id), 'ready_for_review')
        response = self.save(encounter_id, self.date_row(self.doc(encounter_id)), '2026-10-21')
        self.assertEqual(response.json(), {'saved': 1, 'unchanged': 0, 'answer_ids': [], 'reassessing': False})
        self.assertEqual(self.assert_current(encounter_id, 'after the confirmation'), 'reviewed')
        doc = self.doc(encounter_id)
        self.assertEqual((doc['state'], doc['state_label'], doc['readiness']['approved']), ('reviewed', 'Reviewed', True))
        listed = self.listed(encounter_id)
        self.assertEqual((listed['state'], listed['in_queue']), ('reviewed', False))
        self.assertEqual(self.client.get('/api/session').json()['counts']['queue'], 0)
        # the same two acts in the other order read the same
        other = self.upload(TWO_DATES, '2026-10-21')
        self.save(other, self.date_row(self.doc(other)), '2026-10-21')
        self.decide(other, '99213')
        self.assertEqual(self.assert_current(other), 'reviewed')

    def test_an_answer_saved_with_the_confirmation_is_read_with_it(self):
        """C-R3-1's second shape: one save records an answer and confirms the date. The state is derived after both,
        never between them (the answer's refresh had run before the confirmation was written)."""
        self.provider.selections = [('99213', BASIS_LINE)]
        encounter_id = self.upload(TWO_DATES_NO_BASIS, '2026-10-21')
        doc = self.doc(encounter_id)
        (basis,) = [row for row in doc['details_needed'] if row['fact'] == 'em_basis']
        date = self.date_row(doc)
        response = self.client.post(f'/api/encounters/{encounter_id}/details', content_type='application/json',
                                    data=json.dumps({'answers': [
                                        {'id': basis['id'], 'fact': 'em_basis', 'value': 'not_documented'},
                                        {'id': date['id'], 'fact': 'service_date', 'value': '2026-10-21'}]}))
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual((response.json()['saved'], response.json()['reassessing']), (2, False))
        encounter = self.encounter(encounter_id)
        self.assertEqual(review.readiness(encounter), {'draft': True, 'reviewed': True, 'blockers': []})
        self.assertEqual(self.assert_current(encounter_id), 'reviewed')
        self.assertEqual(self.doc(encounter_id)['state'], 'reviewed')

    def test_every_details_save_leaves_the_stored_state_derived(self):
        """Each kind of save made as the review's last act (every code decided first), so that it is the save that moves
        the derived state: a confirmation, the same one again, the other documented date, a correction, a removal, an
        answer and its withdrawal - read as saved, before the stages a save queues run, and after them."""
        def check(encounter_id, where):
            self.assert_current(encounter_id, where + ' (as saved)')
            drain()
            return self.assert_current(encounter_id, where + ' (after the stages it queued)')

        def post(encounter_id, row, value):
            response = self.client.post(f'/api/encounters/{encounter_id}/details', content_type='application/json',
                                        data=json.dumps({'answers': [{'id': row['id'], 'fact': row['fact'],
                                                                      'value': value}]}))
            self.assertIn(response.status_code, (200, 201), response.content)
            return response

        def decided(encounter_id):
            for code in self.doc(encounter_id)['codes']:
                if 'approve' in code['allowed_actions']:
                    self.decide(encounter_id, code['code'])

        confirmed = self.upload(TWO_DATES, '2026-10-21')
        decided(confirmed)
        post(confirmed, self.date_row(self.doc(confirmed)), '2026-10-21')
        self.assertEqual(check(confirmed, 'confirm'), 'reviewed')
        post(confirmed, self.date_row(self.doc(confirmed)), '2026-10-21')
        check(confirmed, 'the same confirmation again')
        post(confirmed, self.date_row(self.doc(confirmed)), '2026-10-20')
        check(confirmed, 'the other documented date')
        entered = self.upload(NO_DATE, '2026-10-02')
        decided(entered)
        post(entered, self.date_row(self.doc(entered)), '2026-10-20')
        check(entered, 'correct')
        decided(entered)
        post(entered, self.date_row(self.doc(entered)), 'clear')
        check(entered, 'clear')
        self.provider.selections = [('99213', BASIS_LINE)]
        answered = self.upload(TWO_DATES_NO_BASIS.replace('Date of service: 2026-10-20\n', ''))
        (basis,) = [row for row in self.doc(answered)['details_needed'] if row['fact'] == 'em_basis']
        post(answered, basis, 'not_documented')
        self.assertEqual(check(answered, 'answer'), 'reviewed')
        saved = next(row for row in self.doc(answered)['details_needed'] if row['fact'] == 'em_basis')['saved']
        withdrawn = self.client.post(f'/api/encounters/{answered}/details/{saved["answer_id"]}/revoke')
        self.assertEqual(withdrawn.status_code, 201, withdrawn.content)
        self.assertNotEqual(check(answered, 'withdraw'), 'reviewed')


# --- B-05: the office visit a reinstated same-day procedure holds --------------------------------------------------

class SameDayHeldVisitOverlayTests(SimpleTestCase):
    """The overlay asks the held visit what its gate says approval waits for (checks.same_day_if_reinstated_check:
    "until a significant, separately identifiable E/M service is documented"), exactly as the engine asks it beside a
    procedure it selected (checks.separate_em_clarification), and reads it as needing clarification."""

    def test_the_held_visit_is_asked_the_separate_visit_and_needs_clarification(self):
        shape = shape_of('office_ready_denied')
        plain = shape.view()['99213']
        self.assertEqual((plain.status, plain.questions, plain.same_day_held), ('ready', (), False))  # control
        self.assertEqual(actions(shape, '99213', shape.view()), ['approve', 'reject'])
        views = shape.view({'45378': 'reinstate'})
        visit = views['99213']
        self.assertEqual((visit.status, visit.same_day_held, visit.added, visit.blocker, visit.withheld_by),
                         ('needs_clarification', True, ('separate_em',), '', ''))
        self.assertEqual([(q['id'], q['scope'], q['family'], q['fact'], q['question']) for q in visit.questions],
                         [('', 'proposal', EM, 'separate_em', checks.SEPARATE_EM_QUESTION)])
        self.assertIn('45378', visit.questions[0]['reason'])
        self.assertEqual(actions(shape, '99213', views), ['reject'])
        # the procedure's reinstatement rejected (or never made) releases the visit, as before
        self.assertEqual(shape.view({'45378': 'reject'})['99213'].status, 'ready')

    def test_a_visit_held_on_its_own_question_is_asked_both_and_the_separate_visit_once(self):
        shape = shape_of('office_denied')
        self.assertEqual([q['fact'] for q in shape.view()['99213'].questions], ['em_basis'])
        views = shape.view({'45378': 'reinstate'})
        self.assertEqual(([q['fact'] for q in views['99213'].questions], views['99213'].status),
                         (['em_basis', 'separate_em'], 'needs_clarification'))
        # a stored separate-visit question (the engine's own) is never asked a second time
        ready = shape_of('office_ready_denied')
        stored = ready.by_code['99213']
        own = {'id': 'q1', 'scope': 'proposal', 'family': EM, 'fact': 'separate_em',
               'question': checks.SEPARATE_EM_QUESTION, 'reason': 'Stored with the proposal.'}
        asked = replace(stored, status='needs_clarification', holds=('separate_em',), questions=(own,))
        views = ready.view({'45378': 'reinstate'}, stored=[asked if s.key == stored.key else s for s in ready.stored])
        self.assertEqual(([q['id'] for q in views['99213'].questions], views['99213'].status, views['99213'].added),
                         (['q1'], 'needs_clarification', ()))

    def test_an_approval_made_before_is_held_by_the_same_day_blocker_alone(self):
        shape = shape_of('office_ready_denied')
        visit = shape.view({'99213': 'approve', '45378': 'reinstate'})['99213']
        # the readiness blocker of the same-day gate names it (review._same_day_blocker): no second blocker
        self.assertEqual((visit.status, visit.same_day_held, visit.blocker), ('needs_clarification', True, ''))

    def test_the_answer_to_the_separate_visit_excludes_the_visit_and_nothing_else(self):
        shape = shape_of('office_ready_denied')
        plain = shape.view({'45378': 'reinstate'})
        for value in ('not_documented', 'cannot_confirm'):
            with self.subTest(value):
                views = shape.view({'45378': 'reinstate'}, answers=[answer('99213', EM, 'separate_em', value)])
                self.assertEqual((views['99213'].status, views['99213'].reason, views['99213'].answer),
                                 ('excluded', 'detail_unavailable', value))
                self.assertTrue(views['99213'].same_day_held)
                procedure, before = views['45378'], plain['45378']
                self.assertEqual((procedure.status, procedure.questions, procedure.withheld_by),
                                 (before.status, before.questions, before.withheld_by))
        # an answer about the procedure lifts no hold: the visit is still asked
        views = shape.view({'45378': 'reinstate'}, answers=[answer('45378', 'gi.colonoscopy', 'extent')])
        self.assertEqual((views['99213'].status, [q['fact'] for q in views['99213'].questions]),
                         ('needs_clarification', ['separate_em']))
        # a separate-visit answer given while nothing holds the visit changes nothing
        self.assertEqual(shape.view(answers=[answer('99213', EM, 'separate_em')])['99213'].status, 'ready')


class SameDayHeldVisitReviewTests(TestCase):
    """The same through the review layer's gates and the customer contract, for a selected and for a reinstated visit."""

    def test_a_selected_visit_needs_a_detail_with_its_row_and_keeps_its_blocker_until_it_is_rejected(self):
        s = pf.scenario()
        pf.assess(s.encounter, selected_em_result(), ctx=pf.context(s.encounter, s.revision))
        s.decide('exc:1', 'reinstate')
        views = review.effective_view(s.encounter.current_assessment)
        self.assertEqual((views['sel:0'].status, [q['fact'] for q in views['sel:0'].questions]),
                         ('needs_clarification', ['separate_em']))
        blockers = review.readiness(s.encounter)['blockers']
        self.assertIn('99213 needs a separately identifiable E/M: 46221 was reinstated as a same-day procedure', blockers)
        self.assertIn('99213 has an open clarification', blockers)
        (row,) = [item for item in answers.details_needed(s.encounter, s.encounter.current_assessment, views)
                  if item['fact'] == 'separate_em']
        self.assertEqual((row['affects'], row['control'], row['allow'], row['addendum_allowed'], row['prompt']),
                         (['99213'], 'confirm', ['not_documented', 'cannot_confirm'], True,
                          answers.PROMPTS['separate_em']))
        s.encounter.refresh_from_db()
        self.assertEqual(s.encounter.state, 'needs_clarification')
        s.decide('sel:0', 'reject')
        self.assertFalse([item for item in review.readiness(s.encounter)['blockers'] if item.startswith('99213')])

    def test_a_reinstated_visit_the_gate_holds_needs_a_detail_too(self):
        s = pf.scenario()
        pf.assess(s.encounter, excluded_em_result(), ctx=pf.context(s.encounter, s.revision))
        s.decide('exc:1', 'reinstate')
        s.decide('exc:0', 'reinstate')
        assessment = s.encounter.current_assessment
        views = review.effective_view(assessment)
        visit = views['exc:0']
        self.assertEqual((visit.status, visit.withheld_by, [q['fact'] for q in visit.questions]),
                         ('needs_clarification', review.SAME_DAY_EM_GATE, ['separate_em']))
        current = review.current_decisions(assessment)
        details = customer_api.details_rows(s.encounter, assessment, views, s.membership(s.reviewer))
        rows, _ = customer_api.code_rows(assessment, current, views, s.membership(s.reviewer), details)
        code = next(row for row in rows if row['code'] == '99213')
        (row,) = [item for item in details if item['fact'] == 'separate_em']
        self.assertEqual((code['status'], code['sub_label'], code['detail_ids'], code['allowed_actions']),
                         ('needs_detail', customer_api.REINSTATED_SUB_LABEL, [row['id']], ['reject', 'revoke']))


class SameDayHeldVisitApiTests(ApiCase):
    def test_the_held_visit_through_the_customer_api(self):
        s = persist_input('office_ready_denied')
        decide(s, '45378', 'reinstate', note='Synthetic: the reviewer reinstates the colonoscopy.')
        doc = self.payload(s)
        visit = self.codes(doc)['99213']
        asked = [item for item in doc['details_needed'] if item['fact'] == 'separate_em']
        self.assertEqual([item['affects'] for item in asked], [['99213']])
        row = asked[0]
        self.assertEqual((visit['status'], visit['status_label'], visit['allowed_actions'], visit['detail_ids']),
                         ('needs_detail', 'Needs a detail', ['reject'], [row['id']]))
        self.assertEqual((row['control'], row['allow'], row['saved'], row['addendum_allowed']),
                         ('confirm', ['not_documented', 'cannot_confirm'], None, True))
        self.assertIn(SAME_DAY_WORDS, visit['why']['qualifications'])
        self.assertNotIn(customer_api.QUESTION_WORDS['separate_em'], visit['why']['qualifications'])  # said once
        self.ready_means_approvable(doc)
        self.assertEqual(doc['state'], 'awaiting_detail')
        self.assertEqual(self.approve(s, '99213').status_code, 409)
        self.save(s, row, 'not_documented')
        doc = self.payload(s)
        codes = self.codes(doc)
        self.assertEqual((codes['99213']['status'], codes['99213']['sub_label']),
                         ('excluded', customer_api.UNAVAILABLE_SUB_LABEL))
        self.assertEqual(codes['45378']['status'], 'needs_detail')  # the procedure is asked as before
        self.ready_means_approvable(doc)
        stored, derived = state_pair(s.encounter)
        self.assertEqual(stored, derived)
        # the visit the answer excluded is resolved (decision (f)): readiness names no same-day blocker for it any more
        # (integration of round 3, the overlay owner's request), while the procedure still waits on its own question
        self.assertFalse([blocker for blocker in review.readiness(s.encounter)['blockers'] if '99213' in blocker],
                         review.readiness(s.encounter)['blockers'])


class SameDayHeldVisitPipelineTests(PipelineCase):
    def test_the_findings_document_through_the_whole_pipeline(self):
        """B-05's input character for character, through the pasted-document intake and every stage, the provider an
        in-process fake suggesting 99213 on the visit sentence and 45378 on the denial."""
        self.provider.selections = [('99213', VISIT), ('45378', NO_COLONOSCOPY)]
        encounter_id = self.upload(OFFICE_READY_DENIED)
        self.assertTrue(self.encounter(encounter_id).current_revision.text.startswith(HEAD + 'Office visit note'))
        visit = {code['code']: code for code in self.doc(encounter_id)['codes']}['99213']
        self.assertEqual((visit['status'], visit['allowed_actions']), ('ready', ['approve', 'reject']))
        proposal = self.encounter(encounter_id).current_assessment.proposals.get(code='45378')
        response = self.client.post(f'/api/encounters/{encounter_id}/decisions', content_type='application/json',
                                    data=json.dumps({'proposal_id': str(proposal.pk), 'action': 'reinstate',
                                                     'note': 'Synthetic: reinstated for review.'}))
        self.assertEqual(response.status_code, 201, response.content)
        doc = self.doc(encounter_id)
        visit = {code['code']: code for code in doc['codes']}['99213']
        asked = [item for item in doc['details_needed'] if item['fact'] == 'separate_em']
        self.assertEqual([item['affects'] for item in asked], [['99213']])
        self.assertEqual((visit['status'], visit['allowed_actions'], visit['detail_ids']),
                         ('needs_detail', ['reject'], [asked[0]['id']]))
        self.assertFalse([code['code'] for code in doc['codes']
                          if code['status'] == 'ready' and 'approve' not in code['allowed_actions']])
        self.assertEqual((doc['state'], self.encounter(encounter_id).state), ('awaiting_detail', 'needs_clarification'))


# --- C-R3-2 and C-R3-3: the re-check's activity line ------------------------------------------------------------------

NOT_COMPLETED = customer_api.RECHECK_NOT_COMPLETED[0]


def said(encounter):
    return [entry['event'] for entry in customer_api.activity(encounter)].count(NOT_COMPLETED)


class RecheckActivityRowsTests(TestCase):
    """The rows the line is read from: the re-check's own outcome where it is known at the send (failed, not sent),
    and the reconciliation of one whose outcome was unknown - never the unknown outcome itself."""

    def test_the_line_follows_the_outcome_once_it_is_known(self):
        s = pf.scenario()
        for state in ('unknown', 'succeeded'):
            audit.record(s.workspace, 'provider.finished', encounter=s.encounter, run='r', state=state,
                         http_status=None, usage={}, latency_ms=1.0, purpose='second_review')
        self.assertEqual(said(s.encounter), 0)  # being confirmed, or answered
        for state in ('failed', 'not_sent'):
            audit.record(s.workspace, 'provider.finished', encounter=s.encounter, run='r', state=state,
                         http_status=None, usage={}, latency_ms=1.0, purpose='second_review')
        self.assertEqual(said(s.encounter), 2)
        primary = pf.provider_run(s.encounter, s.revision, state='unknown')
        second = pf.provider_run(s.encounter, s.revision, state='unknown')
        models.ProviderRun.objects.filter(pk=second.pk).update(purpose=models.ProviderRun.SECOND_REVIEW)
        audit.record(s.workspace, 'provider.reconciled', encounter=s.encounter, actor=s.reviewer, run=str(second.pk))
        self.assertEqual(said(s.encounter), 2)  # a row naming a run no reconciliation settled says nothing
        models.ProviderRun.objects.filter(pk__in=(primary.pk, second.pk)).update(reconciled_at=timezone.now(),
                                                                               reconciled_by=s.reviewer)
        audit.record(s.workspace, 'provider.reconciled', encounter=s.encounter, actor=s.reviewer, run=str(primary.pk))
        self.assertEqual(said(s.encounter), 3)  # the re-check's reconciliation only, never the document review's
        for bad in ('not-a-run', str(pf.provider_run(pf.scenario().encounter, s.revision).pk), None):
            audit.record(s.workspace, 'provider.reconciled', encounter=s.encounter, actor=s.reviewer, run=bad)
        self.assertEqual(said(s.encounter), 3)  # a row naming no run of this document's says nothing
        entries = [entry for entry in customer_api.activity(s.encounter) if entry['event'] == NOT_COMPLETED]
        self.assertEqual({(entry['summary'], entry['actor']) for entry in entries},
                         {(customer_api.RECHECK_NOT_COMPLETED[1], 'CPT Studio')})


class RecheckActivityPathTests(Harness):
    """End to end: the re-check asked from the customer page (session decision (n)) and each way it can end."""

    NOTE = 'Synthetic reconciliation: the outcome was settled from the vendor console.'

    def ask(self, provider):
        self.use(provider)
        encounter_id = self.create(COLONOSCOPY)
        drain()
        self.approve(encounter_id, '45385')
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 201)
        return encounter_id

    def second(self, encounter_id):
        (run,) = models.ProviderRun.objects.filter(encounter_id=encounter_id, purpose='second_review')
        return run

    def doc(self, encounter_id):
        reply = self.client.get(f'/api/encounters/{encounter_id}')
        self.assertEqual(reply.status_code, 200, reply.content)
        return reply.json()

    def events(self, doc):
        return [entry['event'] for entry in doc['activity']]

    def reconcile(self, encounter_id):
        reply = self.post(f'/ops/api/encounters/{encounter_id}/reconcile',
                          {'provider_run_id': str(self.second(encounter_id).pk), 'note': self.NOTE})
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()

    def assert_confirming_then_said_once(self, encounter_id):
        doc = self.doc(encounter_id)
        self.assertEqual(doc['progress']['phase'], 'being_confirmed')
        self.assertNotIn(NOT_COMPLETED, self.events(doc))  # C-R3-2: never while it is being confirmed
        self.reconcile(encounter_id)
        doc = self.doc(encounter_id)
        self.assertEqual((doc['progress']['phase'], doc['progress']['message']), ('partial', progress.RECHECK_INCOMPLETE))
        events = self.events(doc)
        self.assertEqual(events.count(NOT_COMPLETED), 1, events)  # C-R3-3: said once it is settled
        self.assertLess(events.index('check_requested'), events.index(NOT_COMPLETED))

    def test_a_read_that_timed_out_after_sending(self):
        encounter_id = self.ask(TwoPassProvider(first=[SNARE], later=[BIOPSY], outcomes=['succeeded', 'unknown']))
        drain()
        self.assertEqual((self.second(encounter_id).state, self.second(encounter_id).sent), ('unknown', True))
        self.assert_confirming_then_said_once(encounter_id)

    def test_a_worker_that_died_mid_send(self):
        provider = TwoPassProvider(first=[SNARE], later=[BIOPSY])
        encounter_id = self.ask(provider)
        job = jobs.claim_next()
        self.assertEqual(job.kind, models.Job.REVIEW2)

        class Died(BaseException):
            """A worker death after the request left: run_job's handler never sees it."""

        def dying(request, *, deadline_s):
            provider.requests.append(request)
            raise Died()

        with mock.patch.object(provider, 'send', side_effect=dying), self.assertRaises(Died):
            jobs.run_job(job)
        earlier = timezone.now() - timedelta(hours=1)
        models.Job.objects.filter(pk=job.pk).update(started_at=earlier)
        models.ProviderRun.objects.filter(pk=self.second(encounter_id).pk).update(
            created_at=earlier + timedelta(seconds=1))
        jobs.mark_stale()
        self.assertEqual(self.second(encounter_id).state, 'unknown')
        self.assertFalse(models.AuditEvent.objects.filter(encounter_id=encounter_id, event='provider.finished',
                                                          data__purpose='second_review').exists())
        self.assert_confirming_then_said_once(encounter_id)

    def test_an_outcome_that_could_not_be_recorded(self):
        encounter_id = self.ask(TwoPassProvider(first=[SNARE], later=[BIOPSY]))
        real = jobs._finish_run

        def failing(run, exchange):
            if run.purpose == models.ProviderRun.SECOND_REVIEW:
                raise RuntimeError('synthetic: the outcome write failed')
            return real(run, exchange)

        with mock.patch('studio.jobs._finish_run', side_effect=failing), self.assertLogs('studio.jobs', 'ERROR'):
            drain()
        self.assertEqual((self.second(encounter_id).state, self.second(encounter_id).sent), ('unknown', True))
        self.assert_confirming_then_said_once(encounter_id)

    def test_control_an_answered_re_check_says_nothing(self):
        encounter_id = self.ask(TwoPassProvider(first=[SNARE], later=[BIOPSY, SNARE]))
        drain()
        self.assertEqual(self.second(encounter_id).state, 'succeeded')
        self.assertNotIn(NOT_COMPLETED, self.events(self.doc(encounter_id)))

    def test_control_a_failed_re_check_says_it_once_when_it_ends(self):
        class Refused(TwoPassProvider):
            """The re-check is sent and answered HTTP 503: a recorded failure."""

            def send(self, request, *, deadline_s):
                if self.requests:
                    self.requests.append(request)
                    return RawExchange(outcome='failed', sent=True, http_status=503, response_bytes=b'{}',
                                       response_sha256=hashlib.sha256(b'{}').hexdigest(), error='synthetic 503')
                return super().send(request, deadline_s=deadline_s)

        encounter_id = self.ask(Refused(first=[SNARE], later=[BIOPSY]))
        drain()
        self.assertEqual(self.second(encounter_id).state, 'failed')
        events = self.events(self.doc(encounter_id))
        self.assertEqual(events.count(NOT_COMPLETED), 1, events)
        self.assertLess(events.index('check_requested'), events.index(NOT_COMPLETED))
