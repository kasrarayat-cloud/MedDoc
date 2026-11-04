"""Refutation round 3 of the core repair and customer interface (2026-11-04), repair owner "overlay-r3": the details
save's stored state and the office visit a reinstated same-day procedure holds. Each finding is reproduced first
by the test that names it (refute-r3: lens B's B-01 and B-05, lens C's C-R3-1).

- B-01 / C-R3-1: every details save - a confirmation of the date, a removal, a correction, a value, an answer - leaves
  the stored list state (Encounter.state: what the document, the list, the review queue and its badge read) equal to
  the derived state (review._derive_state). A save that only confirmed the upload date had left a finished review
  "Ready for review" and on the queue, beside an approved export it allowed.
- B-05: an office visit that a reviewer's reinstatement of a same-day procedure holds is asked what it waits for - a
  significant, separately identifiable visit (fact separate_em), as beside a procedure the engine selected - and reads
  "Needs a detail" with the row that asks it: never "Ready for review" beside no approve.

Synthetic data only; every provider is an in-process fake (no network).
"""
import json
from dataclasses import replace

from django.test import SimpleTestCase, TestCase

from studio import answers, customer_api, models, review
from studio.validation import checks
from tests.support import pipeline_factories as pf
from tests.test_cux_r2_details import HEAD, NO_DATE, TWO_DATES, PipelineCase
from tests.test_cux_r2_overlay import (EM, NO_COLONOSCOPY, OFFICE_READY_DENIED, VISIT, ApiCase, answer, persist_input,
                                       shape_of)
from tests.test_cux_review import actions, decide
from tests.test_pipeline_api import drain
from tests.test_repairs_r4c_lead_review import excluded_em_result, selected_em_result

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
