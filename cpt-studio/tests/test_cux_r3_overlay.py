"""Refutation round 3 of the core repair and customer interface (2026-11-04), repair owner "overlay-r3": the details
save's stored state. Each finding is reproduced first by the test that names it (refute-r3: lens B's B-01, lens C's
C-R3-1).

- B-01 / C-R3-1: every details save - a confirmation of the date, a removal, a correction, a value, an answer - leaves
  the stored list state (Encounter.state: what the document, the list, the review queue and its badge read) equal to
  the derived state (review._derive_state). A save that only confirmed the upload date had left a finished review
  "Ready for review" and on the queue, beside an approved export it allowed.

Synthetic data only; every provider is an in-process fake (no network).
"""
import json

from studio import models, review
from tests.test_cux_r2_details import HEAD, NO_DATE, TWO_DATES, PipelineCase
from tests.test_pipeline_api import drain

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
