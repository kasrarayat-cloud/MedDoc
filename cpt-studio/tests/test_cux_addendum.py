"""An addendum sent from a details row (the wiring report's item 2, 2026-11-04).

The customer page sends its details row's id in ``clarification_id`` (API.md, the customer contract: "the server
accepts a details row id there"), and api.addenda used to answer 404 "That clarification is not open on this
document." to every one. The server now reads a details row id as the open confirmation row of the live assessment it
names, and answers the stored clarification that row shows - none for a question only the review overlay asks. A row
that is not open, or whose detail takes a value rather than documentation (the date, a setting), is refused and
nothing is made. A clarification's own id is read as before.

DB-backed; synthetic data only; nothing is sent.
"""
import json

from django.test import Client

from studio import answers, models
from tests.support import pipeline_factories as pf
from tests.test_cux_flow import DetailsCase, asks
from tests.test_cux_review import decide, persist
from tests.test_cux_wire import BASE_ROW, COLON, WireCase

TEXT = 'Synthetic addendum: the reviewer documents that the base examination was reported separately.'
NOT_OPEN = 'That detail is not open on this document.'


def addendum(client, encounter, clarification_id):
    return client.post(f'/api/encounters/{encounter.pk}/addenda', content_type='application/json',
                       data=json.dumps({'text': TEXT, 'clarification_id': clarification_id,
                                        'synthetic_attestation': 'yes'}))


class DetailsRowAddendumTests(WireCase):
    def test_a_row_showing_a_stored_question_answers_it(self):
        s = persist('selected')  # 45378 held on its stored base_included question beside 45385
        stored = s.encounter.current_assessment.clarifications.get(fact='base_included',
                                                                   state=models.Clarification.OPEN)
        (row,) = [item for item in self.payload(s)['details_needed'] if item['id'] == BASE_ROW]
        self.assertTrue(row['addendum_allowed'])
        response = addendum(self.client_for(s.reviewer), s.encounter, BASE_ROW)
        self.assertEqual(response.status_code, 201, response.content)
        revision = models.SourceRevision.objects.get(pk=response.json()['revision_id'])
        stored.refresh_from_db()
        self.assertEqual((revision.kind, revision.answers_clarification_id, stored.state,
                          stored.answered_by_revision_id),
                         (models.SourceRevision.ADDENDUM, stored.pk, models.Clarification.ANSWERED, revision.pk))
        s.encounter.refresh_from_db()
        self.assertEqual(s.encounter.current_revision_id, revision.pk)
        self.assertTrue(revision.addendum_text.endswith('reported separately.'))

    def test_a_question_only_the_overlay_asks_takes_an_addendum_that_answers_no_stored_row(self):
        s = persist('denied')
        decide(s, '45385', 'reinstate', note='Synthetic: the reviewer reads the snare as done.')
        self.assertFalse(s.encounter.current_assessment.clarifications.filter(fact='base_included').exists())
        (row,) = [item for item in self.payload(s)['details_needed'] if item['id'] == BASE_ROW]
        self.assertTrue(row['addendum_allowed'])
        response = addendum(self.client_for(s.reviewer), s.encounter, BASE_ROW)
        self.assertEqual(response.status_code, 201, response.content)
        revision = models.SourceRevision.objects.get(pk=response.json()['revision_id'])
        self.assertIsNone(revision.answers_clarification_id)
        self.assertEqual(s.encounter.current_assessment.clarifications.filter(
            state=models.Clarification.ANSWERED).count(), 0)

    def test_a_row_that_is_not_open_is_refused_and_nothing_is_made(self):
        s = persist('selected')
        before = (models.SourceRevision.objects.count(), models.Job.objects.count(), models.Clarification.objects.filter(
            state=models.Clarification.ANSWERED).count())
        client = self.client_for(s.reviewer)
        for value in (answers.detail_id('base_included', COLON, '45380'),  # a code that asks nothing
                      answers.detail_id('extent', COLON, '45378'),  # a fact nobody asks
                      'd' + '0' * 15):
            with self.subTest(value=value):
                response = addendum(client, s.encounter, value)
                self.assertEqual((response.status_code, response.json()['error']), (404, NOT_OPEN))
        # not a details row id: read as a clarification id, as before
        for value in ('D' + '0' * 15, 'd' + '0' * 14, 'not-an-id'):
            with self.subTest(value=value):
                response = addendum(client, s.encounter, value)
                self.assertEqual((response.status_code, response.json()['error']),
                                 (404, 'That clarification is not open on this document.'))
        stored = s.encounter.current_assessment.clarifications.get(fact='base_included')
        response = addendum(client, s.encounter, str(stored.pk))  # the clarification's own id still answers it
        self.assertEqual(response.status_code, 201, response.content)
        stored.refresh_from_db()
        self.assertEqual(stored.state, models.Clarification.ANSWERED)
        self.assertEqual(models.SourceRevision.objects.count(), before[0] + 1)

    def test_a_viewer_is_refused_before_any_row_is_read(self):
        s = persist('selected')
        response = addendum(self.client_for(s.viewer), s.encounter, BASE_ROW)
        self.assertEqual(response.status_code, 403, response.content)


class ValueRowAddendumTests(DetailsCase):
    def test_a_row_that_takes_a_value_takes_no_documentation(self):
        self.assess(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent', 'billing_context'))
        self.s.encounter.refresh_from_db()
        extent = self.row('extent', '45385')
        choice = self.row('billing_context', '45385')
        self.assertEqual((extent['control'], extent['addendum_allowed'], choice['control'], choice['addendum_allowed']),
                         ('confirm', True, 'choice', False))
        before = models.SourceRevision.objects.count()
        response = addendum(self.client, self.s.encounter, choice['id'])
        self.assertEqual((response.status_code, response.json()['error']), (404, NOT_OPEN))
        self.assertEqual(models.SourceRevision.objects.count(), before)
        stored = self.s.encounter.current_assessment.clarifications.get(fact='extent')
        response = addendum(self.client, self.s.encounter, extent['id'])
        self.assertEqual(response.status_code, 201, response.content)
        stored.refresh_from_db()
        self.assertEqual(stored.state, models.Clarification.ANSWERED)
