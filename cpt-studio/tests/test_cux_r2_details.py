"""Refutation round 2 of the core repair and customer interface (2026-11-04): the details flow's repairs, each
finding reproduced first by the test that names it (lens L7 of refute-r2; the page's half is in
tests/frontend/app.test.cjs).

- L7-02: a date of service typed at the upload that chooses one of the document's own conflicting dates is not taken
  silently - the document's dates are shown beside it and the member settles it with them in view.
- L7-03: a document whose only dates are not dates of service this service reads (another occasion's date, a date it
  cannot read) always has a way to settle: the entered date can be removed, and the physician's addendum is offered
  from the date row - the way such a date is settled (session interpretation 35: "an addendum settles it").
- L7-05: a member's own date of service in effect - saved in the details panel or typed at the upload - stays in the
  panel as a saved answer, attributed, and can be corrected or removed there, each change audited.
- L7-07: the date row serves the document's own dates and its own wording of the date; a context recorded before
  the document's date was stored still quotes what the document says.
- L7-08: one question per service fact (the profiles' required facts), applying to every code it holds; its answer is
  stored for each code, so it survives a re-assessment, and withdrawing it withdraws it for each.

DB-backed; synthetic data only; nothing is sent (the in-process fakes of the pipeline suites).
"""
import gzip
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from studio import answers, customer_api, jobs, models, review
from studio.gi import context as gi_context
from tests.legacy_chain import applied
from tests.support import factories as f
from tests.support import pipeline_factories as pf
from tests.test_cux_flow import COLON, DetailsCase, asks, ready
from tests.test_frontend import PLAIN_STATIC
from tests.test_pipeline_api import FakeProvider, drain

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
TIME = 'Total time on the date of the encounter was 24 minutes.'
VISIT = 'Established patient seen for reflux.\n' + TIME + '\n'
TWO_DATES = (HEAD + 'Office visit\nDate of service: 2026-10-20\nPlace of service: office\nDate of service: 2026-10-21\n'
             + VISIT)
NO_DATE = HEAD + 'Riverbend Digestive Health (fictional)\nOffice visit\nPlace of service: Office\n' + VISIT
UNUSABLE = {
    # the only date is another occasion's: never this visit's date of service
    'elsewhere': (HEAD + 'Riverbend Digestive Health (fictional)\nOffice visit\nNext procedure date: 11/04/2026\n'
                  'Place of service: Office\n' + VISIT, 'Next procedure date: 11/04/2026'),
    # a date of service this service cannot read as a calendar date
    'unreadable': (HEAD + 'Riverbend Digestive Health (fictional)\nOffice visit\nDate of service: 20-Oct-26\n'
                   'Place of service: Office\n' + VISIT, 'Date of service: 20-Oct-26'),
}
LIVE = dict(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
CLEAR = {'value': answers.CLEAR, 'label': answers.CLEAR_LABEL}


def stated(*days):
    return [{'value': day, 'label': answers.STATED_IN_DOCUMENT.format(value=answers._date_label(day))} for day in days]


@override_settings(**LIVE)
class PipelineCase(TestCase):
    """Documents through the customer API and the real stages, Corti an in-process fake suggesting 99213."""

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.viewer = f.member(self.ws, f.user('viewer'), role=models.Membership.VIEWER)
        self.client = self.login(self.reviewer)
        self.provider = FakeProvider(selections=[('99213', TIME)])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def login(self, user):
        client = Client(enforce_csrf_checks=False)
        client.force_login(user)
        return client

    def upload(self, text, service_date=''):
        response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes',
                                                        'service_date': service_date})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        return response.json()['id']

    def doc(self, encounter_id):
        response = self.client.get(f'/api/encounters/{encounter_id}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def date_row(self, doc):
        (row,) = [item for item in doc['details_needed'] if item['fact'] == 'service_date']
        return row

    def save(self, encounter_id, row, value, client=None):
        response = (client or self.client).post(
            f'/api/encounters/{encounter_id}/details', content_type='application/json',
            data=json.dumps({'answers': [{'id': row['id'], 'fact': row['fact'], 'value': value}]}))
        drain()
        return response

    def addendum(self, encounter_id, text, detail):
        response = self.client.post(f'/api/encounters/{encounter_id}/addenda', content_type='application/json',
                                    data=json.dumps({'text': text, 'clarification_id': detail,
                                                     'synthetic_attestation': 'yes'}))
        drain()
        return response

    def encounter(self, encounter_id):
        return models.Encounter.objects.get(pk=encounter_id)

    def counts(self, encounter_id):
        encounter = self.encounter(encounter_id)
        return {'contexts': encounter.contexts.count(), 'jobs': encounter.jobs.count(),
                'assessments': models.Assessment.objects.filter(encounter=encounter).count(),
                'sent': len(self.provider.sent)}

    def date_events(self, encounter_id):
        return list(models.AuditEvent.objects.filter(encounter_id=encounter_id, event='detail.answered',
                                                     data__fact='service_date').order_by('created_at', 'pk'))


@applied
class DateSettledAtUploadTests(PipelineCase):
    """L7-02: the document states two dates of service and the member typed one of them in the upload form, before the
    document's dates could be seen. The reading takes it (a member's value settles a conflict inside the document by
    choosing one of its values - interpretation 22), but the choice is never silent: the date row shows both of the
    document's dates beside the one entered, asks the member to confirm, and records the confirmation."""

    def test_an_upload_date_choosing_one_of_the_documents_dates_is_asked_with_both_in_view(self):
        encounter_id = self.upload(TWO_DATES, '2026-10-21')
        doc = self.doc(encounter_id)
        self.assertEqual(doc['service_date']['value'], '2026-10-21')  # in effect, as the reading takes it
        row = self.date_row(doc)
        self.assertEqual((row['control'], row['saved'], row['allow'], row['entered_value'], row['document_value']),
                         ('date', None, [], '2026-10-21', None))
        self.assertEqual(row['choices'], stated('2026-10-20', '2026-10-21'))
        self.assertEqual(row['prompt'], answers.DATE_PROMPTS['confirm'])
        self.assertEqual(row['affects'], ['99213'])
        (listed,) = self.client.get('/api/encounters').json()['encounters']
        self.assertEqual(listed['open_details'], 1)

    def test_confirming_the_entered_date_records_it_once_and_sends_nothing(self):
        encounter_id = self.upload(TWO_DATES, '2026-10-21')
        row = self.date_row(self.doc(encounter_id))
        before = self.counts(encounter_id)
        response = self.save(encounter_id, row, '2026-10-21')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json(), {'saved': 1, 'unchanged': 0, 'answer_ids': [], 'reassessing': False})
        self.assertEqual(self.counts(encounter_id), before)  # no context, no stage, nothing sent
        (event,) = self.date_events(encounter_id)
        encounter = self.encounter(encounter_id)
        self.assertEqual((event.actor, event.data['value'], event.data['revision'], event.data['confirmed']),
                         (self.reviewer, '2026-10-21', str(encounter.current_revision_id), True))
        saved = self.date_row(self.doc(encounter_id))
        self.assertEqual({k: saved['saved'][k] for k in ('value', 'label', 'by', 'answer_id')},
                         {'value': '2026-10-21', 'label': '21 October 2026', 'by': self.reviewer.label(),
                          'answer_id': ''})
        self.assertEqual(saved['choices'], stated('2026-10-20', '2026-10-21') + [CLEAR])
        self.assertEqual(saved['prompt'], answers.DATE_PROMPTS['chosen'])
        (listed,) = self.client.get('/api/encounters').json()['encounters']
        self.assertEqual(listed['open_details'], 0)
        again = self.save(encounter_id, saved, '2026-10-21')
        self.assertEqual((again.status_code, again.json()['saved'], again.json()['unchanged']), (200, 0, 1))
        self.assertEqual(len(self.date_events(encounter_id)), 1)

    def test_the_open_confirmation_is_readable_for_a_reader_that_holds_the_approved_export(self):
        encounter_id = self.upload(TWO_DATES, '2026-10-21')
        self.assertTrue(answers.date_confirmation_open(self.encounter(encounter_id)))
        self.assertEqual(self.save(encounter_id, self.date_row(self.doc(encounter_id)), '2026-10-21').status_code, 201)
        self.assertFalse(answers.date_confirmation_open(self.encounter(encounter_id)))
        for text, entered in ((NO_DATE, '2026-10-02'), (TWO_DATES, ''), (TWO_DATES, '1998-01-01')):
            with self.subTest(entered=entered):  # a saved date, the document's own question, a held third date
                self.assertFalse(answers.date_confirmation_open(self.encounter(self.upload(text, entered))))

    def test_a_confirmation_stands_for_its_revision_only(self):
        encounter_id = self.upload(TWO_DATES, '2026-10-21')
        self.assertEqual(self.save(encounter_id, self.date_row(self.doc(encounter_id)), '2026-10-21').status_code, 201)
        self.assertIsNotNone(self.date_row(self.doc(encounter_id))['saved'])
        added = self.addendum(encounter_id, 'Synthetic addendum: the visit note is complete as written.', None)
        self.assertEqual(added.status_code, 201, added.content)
        row = self.date_row(self.doc(encounter_id))  # new documentation: its own dates are asked about again
        self.assertEqual((row['saved'], row['prompt'], row['entered_value']),
                         (None, answers.DATE_PROMPTS['confirm'], '2026-10-21'))

    def test_choosing_the_other_documented_date_re_assesses_with_it(self):
        encounter_id = self.upload(TWO_DATES, '2026-10-21')
        response = self.save(encounter_id, self.date_row(self.doc(encounter_id)), '2026-10-20')
        self.assertEqual((response.status_code, response.json()['reassessing']), (201, True))
        doc = self.doc(encounter_id)
        self.assertEqual((doc['service_date']['value'], doc['service_date']['source']), ('2026-10-20', 'member'))
        row = self.date_row(doc)
        self.assertEqual((row['saved']['value'], row['prompt']), ('2026-10-20', answers.DATE_PROMPTS['chosen']))
        (event,) = self.date_events(encounter_id)
        self.assertEqual((event.data['kind'], event.data['value'], event.data.get('confirmed')),
                         ('context', '2026-10-20', None))

    def test_with_no_upload_date_the_documents_own_conflict_is_asked_as_before(self):
        doc = self.doc(self.upload(TWO_DATES))
        row = self.date_row(doc)
        self.assertEqual((doc['state'], row['saved'], row['prompt'], row['choices']),
                         ('awaiting_detail', None, answers.DATE_PROMPTS['document'], stated('2026-10-20', '2026-10-21')))

    def test_a_date_set_outside_the_details_panel_is_asked_again(self):
        """The edit-context path (POST /context) shows the member none of the document's dates: a date it sets that
        chooses one of them is asked with both in view, as an upload's is."""
        encounter_id = self.upload(TWO_DATES)
        response = self.client.post(f'/api/encounters/{encounter_id}/context', content_type='application/json',
                                    data=json.dumps({'service_date': '2026-10-20'}))
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        row = self.date_row(self.doc(encounter_id))
        self.assertEqual((row['saved'], row['prompt'], row['entered_value']),
                         (None, answers.DATE_PROMPTS['confirm'], '2026-10-20'))


@applied
class NoUsableDateTests(PipelineCase):
    """L7-03: the document's only date text is not a date of service this service reads, so every member date is held
    (interpretation 35). The date row says what the document states, and always offers a way that settles: removing
    the entered date, and the physician's addendum from the row."""

    def test_the_date_row_quotes_the_document_and_offers_the_addendum(self):
        for name, (text, passage) in UNUSABLE.items():
            with self.subTest(name):
                encounter_id = self.upload(text)
                doc = self.doc(encounter_id)
                row = self.date_row(doc)
                self.assertEqual((doc['state'], row['prompt'], row['choices'], row['document_value']),
                                 ('awaiting_detail', answers.DATE_PROMPTS['asked'], [], None))
                self.assertEqual(row['quote']['text'], passage)
                self.assertEqual(doc['document']['text'][row['quote']['start']:row['quote']['end']], passage)
                self.assertTrue(row['addendum_allowed'])
                viewer = self.login(self.viewer).get(f'/api/encounters/{encounter_id}').json()
                self.assertFalse(self.date_row(viewer)['addendum_allowed'])  # the physician path needs a reviewer

    def test_a_held_member_date_can_be_removed_or_settled_by_the_addendum_from_the_row(self):
        for name, (text, passage) in UNUSABLE.items():
            with self.subTest(name):
                encounter_id = self.upload(text)
                row = self.date_row(self.doc(encounter_id))
                self.assertEqual(self.save(encounter_id, row, '2026-10-20').status_code, 201)
                doc = self.doc(encounter_id)
                held = self.date_row(doc)
                self.assertEqual((doc['state'], held['choices'], held['prompt'], held['addendum_allowed']),
                                 ('action_needed', [CLEAR], answers.DATE_PROMPTS['unconfirmed'], True))
                self.assertEqual(held['quote']['text'], passage)
                refused = self.save(encounter_id, held, 'use_document')  # the document gives no date of its own
                self.assertEqual((refused.status_code, refused.json()['error']), (400, answers.NOT_OFFERED))
                # removing the entered date: the date is asked again, nothing held - and the answer already made for
                # the document without a date is read again, never asked for twice
                sent = len(self.provider.sent)
                removed = self.save(encounter_id, held, 'clear')
                self.assertEqual(removed.status_code, 201, removed.content)
                self.assertEqual(self.encounter(encounter_id).user_values, {})
                self.assertEqual(len(self.provider.sent), sent)
                doc = self.doc(encounter_id)
                self.assertEqual((doc['state'], self.date_row(doc)['prompt']),
                                 ('awaiting_detail', answers.DATE_PROMPTS['asked']))
                # held again, then the physician documents the date of service from the date row
                self.assertEqual(self.save(encounter_id, self.date_row(doc), '2026-10-20').status_code, 201)
                held = self.date_row(self.doc(encounter_id))
                added = self.addendum(encounter_id, 'Date of service: 10/20/2026.', held['id'])
                self.assertEqual(added.status_code, 201, added.content)
                doc = self.doc(encounter_id)
                self.assertNotEqual(doc['state'], 'action_needed')
                self.assertEqual(doc['service_date']['value'], '2026-10-20')
                # settled: no date asked (the member's date in effect may stand as the member's saved answer)
                self.assertFalse([item for item in doc['details_needed']
                                  if item['fact'] == 'service_date' and item['saved'] is None])

    def test_the_addendum_is_offered_only_where_the_document_gives_no_usable_date(self):
        doc = self.doc(self.upload(NO_DATE))  # no date text at all: a member date is taken, no addendum needed
        row = self.date_row(doc)
        self.assertEqual((row['addendum_allowed'], row['quote'], row['choices']), (False, None, []))
        doc = self.doc(self.upload(TWO_DATES))  # the document's own dates settle it
        self.assertFalse(self.date_row(doc)['addendum_allowed'])


@applied
class DateCorrectionTests(PipelineCase):
    """L7-05: a member's date of service in effect where the document gives no single date of its own is the member's
    saved answer, attributed, and the same row corrects or removes it - each change one context change, audited."""

    def test_a_date_saved_in_the_panel_can_be_corrected_and_removed(self):
        encounter_id = self.upload(NO_DATE)
        row = self.date_row(self.doc(encounter_id))
        self.assertEqual(self.save(encounter_id, row, '2026-10-02').status_code, 201)  # a typo for 2026-10-20
        doc = self.doc(encounter_id)
        self.assertEqual((doc['state'], doc['service_date']['value']), ('ready', '2026-10-02'))
        saved = self.date_row(doc)
        self.assertEqual({k: saved['saved'][k] for k in ('value', 'label', 'by', 'answer_id')},
                         {'value': '2026-10-02', 'label': '2 October 2026', 'by': self.reviewer.label(),
                          'answer_id': ''})
        self.assertEqual((saved['choices'], saved['prompt'], saved['id']),
                         ([CLEAR], answers.DATE_PROMPTS['entered'], row['id']))
        viewer = self.save(encounter_id, saved, '2026-10-20', client=self.login(self.viewer))
        self.assertEqual(viewer.status_code, 403)
        colleague = f.member(self.ws, f.user('colleague'))  # another reviewer corrects it: the row names who did
        corrected = self.save(encounter_id, saved, '2026-10-20', client=self.login(colleague))
        self.assertEqual((corrected.status_code, corrected.json()['reassessing']), (201, True), corrected.content)
        doc = self.doc(encounter_id)
        self.assertEqual(doc['service_date']['value'], '2026-10-20')
        self.assertEqual({k: self.date_row(doc)['saved'][k] for k in ('value', 'by')},
                         {'value': '2026-10-20', 'by': colleague.label()})
        removed = self.save(encounter_id, self.date_row(doc), 'clear')
        self.assertEqual(removed.status_code, 201, removed.content)
        doc = self.doc(encounter_id)
        self.assertEqual((doc['service_date']['value'], self.date_row(doc)['saved'], self.date_row(doc)['prompt']),
                         (None, None, answers.DATE_PROMPTS['asked']))
        self.assertEqual([(event.actor, event.data['kind'], event.data['value'])
                          for event in self.date_events(encounter_id)],
                         [(self.reviewer, 'context', '2026-10-02'), (colleague, 'context', '2026-10-20'),
                          (self.reviewer, 'context', '')])

    def test_a_date_typed_at_the_upload_is_the_uploaders_saved_answer(self):
        encounter_id = self.upload(NO_DATE, '2026-10-02')
        encounter = self.encounter(encounter_id)
        colleague = self.login(f.member(self.ws, f.user('colleague')))
        row = self.date_row(colleague.get(f'/api/encounters/{encounter_id}').json())  # read by another member
        self.assertEqual({k: row['saved'][k] for k in ('value', 'by', 'at', 'answer_id')},
                         {'value': '2026-10-02', 'by': self.reviewer.label(), 'at': encounter.created_at.isoformat(),
                          'answer_id': ''})
        corrected = self.save(encounter_id, row, '2026-10-20')
        self.assertEqual(corrected.status_code, 201, corrected.content)
        self.assertEqual(self.doc(encounter_id)['service_date']['value'], '2026-10-20')

    def test_a_date_set_by_the_edit_context_path_names_who_set_it(self):
        encounter_id = self.upload(NO_DATE)
        colleague = f.member(self.ws, f.user('colleague'))
        response = self.login(colleague).post(f'/api/encounters/{encounter_id}/context', content_type='application/json',
                                              data=json.dumps({'service_date': '2026-10-02'}))
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        row = self.date_row(self.doc(encounter_id))
        self.assertEqual((row['saved']['value'], row['saved']['by']), ('2026-10-02', colleague.label()))

    def test_no_row_where_the_document_states_the_date_entered(self):
        single = HEAD + 'Office visit\nDate of service: 10/21/2026\nPlace of service: Office\n' + VISIT
        doc = self.doc(self.upload(single, '2026-10-21'))
        self.assertEqual((doc['service_date']['value'], doc['details_needed']), ('2026-10-21', []))


class LegacyContextDateRowTests(DetailsCase):
    """L7-07: a context recorded before the document's date was stored (document_date NULL) shows no document date
    value - one is never read back from the note's prose - but still says what is known: the document's own wording
    of its date, as an exact slice of the text, and the way back (removing the entered date)."""

    def test_a_held_legacy_context_quotes_the_documents_date_passage(self):
        text = self.s.revision.text
        start = text.index(pf.DATE_PASSAGE)
        conflict = pf.facts(service_date=pf.Fact(
            name='service_date', value=None, origin='conflict',
            evidence=(pf.Span(start, start + len(pf.DATE_PASSAGE), pf.DATE_PASSAGE),),
            note=gi_context.USER_CONFLICT_NOTE.format(user='1998-01-01', document='2026-10-21')))
        pf.context(self.s.encounter, self.s.revision, fact_values=conflict, user_values={'service_date': '1998-01-01'})
        self.s.encounter.refresh_from_db()
        self.assertIsNone(self.s.encounter.current_context.document_date)
        (row,) = answers.details_needed(self.s.encounter, None)
        self.assertEqual((row['document_value'], row['entered_value'], row['choices'], row['prompt'],
                          row['addendum_allowed']),
                         (None, '1998-01-01', [CLEAR], answers.DATE_PROMPTS['disagree'], False))
        self.assertEqual(row['quote'], {'text': pf.DATE_PASSAGE, 'start': start, 'end': start + len(pf.DATE_PASSAGE)})


class OneQuestionPerServiceFactTests(DetailsCase):
    """L7-08: the extent of one colonoscopy is one question, whichever of its codes holds on it."""

    def extent_rows(self, assessment=None):
        return [row for row in self.rows(assessment) if row['fact'] == 'extent']

    def test_two_codes_of_one_service_share_one_row_and_one_answer_applies_to_both(self):
        assessment = self.assess(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent'),
                                 asks('sel:1', '45380', pf.CECUM_PASSAGE, 'extent'))
        (row,) = self.extent_rows()
        self.assertEqual((row['id'], row['affects'], row['prompt'], row['allow']),
                         (answers.detail_id('extent', COLON, ''), ['45385', '45380'], answers.PROMPTS['extent'],
                          ['not_documented', 'cannot_confirm']))
        response = self.post([self.answer(row, 'not_documented')])
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual((response.json()['saved'], len(response.json()['answer_ids'])), (1, 2))
        self.assertEqual(sorted(models.MemberAnswer.objects.values_list('code', 'family', 'fact', 'value')),
                         [('45380', COLON, 'extent', 'not_documented'), ('45385', COLON, 'extent', 'not_documented')])
        views = review.effective_view(assessment)
        self.assertEqual({views[key].reason for key in ('sel:0', 'sel:1')}, {review.DETAIL_UNAVAILABLE})
        (saved,) = self.extent_rows()
        self.assertEqual((saved['saved']['label'], saved['affects']), ('Not documented', ['45385', '45380']))
        again = self.post([self.answer(saved, 'not_documented')])
        self.assertEqual((again.status_code, again.json()['unchanged']), (200, 1))
        # bound to each code, never to a position: the re-assessment swaps the keys and both still stand
        later = self.assess(asks('sel:0', '45380', pf.CECUM_PASSAGE, 'extent'),
                            asks('sel:1', '45385', pf.SNARE_PASSAGE, 'extent'))
        (kept,) = self.extent_rows(later)
        self.assertIsNotNone(kept['saved'])
        self.assertEqual(sorted(item['code'] for item in answers.saved_answers(later)), ['45380', '45385'])

    def test_withdrawing_the_answer_withdraws_it_for_every_code(self):
        self.assess(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent'), asks('sel:1', '45380', pf.CECUM_PASSAGE, 'extent'))
        (row,) = self.extent_rows()
        self.post([self.answer(row, 'not_documented')])
        (saved,) = self.extent_rows()
        response = self.client.post(f'/api/encounters/{self.s.encounter.pk}/details/{saved["saved"]["answer_id"]}/revoke')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(models.MemberAnswerRevocation.objects.filter(reason='withdrawn').count(), 2)
        self.assertEqual(models.AuditEvent.objects.filter(event='detail.revoked').count(), 2)
        (asked,) = self.extent_rows()
        self.assertIsNone(asked['saved'])
        self.assertEqual(answers.saved_answers(self.s.encounter.current_assessment), [])

    def test_a_code_the_answer_does_not_yet_cover_keeps_the_row_open_and_one_save_covers_it(self):
        assessment = self.assess(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent'),
                                 asks('sel:1', '45380', pf.CECUM_PASSAGE, 'extent'))
        # an answer saved while only 45385 asked it - bound to 45385's question as it was asked (completion repair
        # 2026-11-06, U11), which the assessment asks the same way now
        earlier = models.MemberAnswer.objects.create(
            encounter=self.s.encounter, revision=self.s.revision, assessment=assessment, fact='extent', family=COLON,
            code='45385', value='not_documented', answered_by=self.s.reviewer,
            question=review.asked_fingerprints(assessment)[('45385', COLON, 'extent')])
        (row,) = self.extent_rows()
        self.assertIsNone(row['saved'])  # 45380 has no answer: asked, never answered for it silently
        response = self.post([self.answer(row, 'not_documented')])
        self.assertEqual((response.status_code, len(response.json()['answer_ids'])), (201, 1))
        self.assertFalse(models.MemberAnswerRevocation.objects.filter(answer=earlier).exists())  # kept as it was
        self.assertEqual(sorted(item['code'] for item in answers.saved_answers(assessment)), ['45380', '45385'])

    def test_an_answer_saved_in_the_earlier_form_binds_by_its_key(self):
        """Completion repair (2026-11-06, U11), as refutation cycle 2 decided (answers W2, W4): an answer recorded before
        answers carried their question's fingerprint was given to the installed release's fixed prompt for its (code,
        family, fact) - no question, reason or passage reached the member - so it binds by that key, as the installed
        release bound it: to the question its own assessment asked, and to the same key asked for another reason by a
        later assessment of its revision (cycle 1 bound it by the engine's words, which this release rewords). Applied to
        its code only, and kept as it was."""
        first = self.assess(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent'),
                            asks('sel:1', '45380', pf.CECUM_PASSAGE, 'extent'))
        legacy = models.MemberAnswer.objects.create(
            encounter=self.s.encounter, revision=self.s.revision, assessment=first, fact='extent', family=COLON,
            code='45385', value='not_documented', answered_by=self.s.reviewer)
        self.assertEqual(legacy.question, '')
        views = review.effective_view(first)
        self.assertEqual((views['sel:0'].reason, views['sel:1'].reason), (review.DETAIL_UNAVAILABLE, ''))
        self.assertEqual(answers.earlier_answers(self.s.encounter, first), [])
        (row,) = self.extent_rows()
        self.assertIsNone(row['saved'])  # 45380 has no answer: the row still asks it
        # the same (code, family, fact) asked for another reason: bound by its key, applied to 45385 alone
        second = self.assess(
            pf.proposal('sel:0', '45385', [pf.SNARE_PASSAGE], status='needs_clarification', clarifications=(
                pf.clarification('extent', scope='proposal', family=COLON, proposal_key='sel:0',
                                 reason='The extent is asked for another reason.'),)),
            asks('sel:1', '45380', pf.CECUM_PASSAGE, 'extent'))
        views = review.effective_view(second)
        self.assertEqual((views['sel:0'].reason, views['sel:1'].reason), (review.DETAIL_UNAVAILABLE, ''))
        self.assertEqual(answers.earlier_answers(self.s.encounter, second), [])
        self.assertFalse(models.MemberAnswerRevocation.objects.filter(answer=legacy).exists())  # kept as it was

    def test_a_question_about_one_code_stays_that_codes_own(self):
        self.assess(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'base_included', 'performed_status'),
                    asks('sel:1', '45380', pf.CECUM_PASSAGE, 'base_included', 'performed_status'))
        rows = self.rows()
        self.assertEqual(sorted((row['fact'], tuple(row['affects'])) for row in rows),
                         [('base_included', ('45380',)), ('base_included', ('45385',)),
                          ('performed_status', ('45380',)), ('performed_status', ('45385',))])

    def test_the_customer_payload_asks_it_once_and_excludes_both_codes_on_one_answer(self):
        self.assess(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent'), asks('sel:1', '45380', pf.CECUM_PASSAGE, 'extent'),
                    ready('sel:2', '43239', pf.EGD_PASSAGE))
        doc = self.client.get(f'/api/encounters/{self.s.encounter.pk}').json()
        (row,) = [item for item in doc['details_needed'] if item['fact'] == 'extent']
        codes = {code['code']: code for code in doc['codes']}
        self.assertEqual({code: codes[code]['detail_ids'] for code in ('45385', '45380')},
                         {'45385': [row['id']], '45380': [row['id']]})
        self.post([self.answer(row, 'not_documented')])
        doc = self.client.get(f'/api/encounters/{self.s.encounter.pk}').json()
        self.assertEqual({code['code']: code['status'] for code in doc['codes']},
                         {'45385': 'excluded', '45380': 'excluded', '43239': 'ready'})
        self.assertEqual({code['code']: code['sub_label'] for code in doc['codes'] if code['status'] == 'excluded'},
                         {code: customer_api.UNAVAILABLE_SUB_LABELS['not_documented'] for code in ('45385', '45380')})

    def test_the_physicians_addendum_from_the_shared_row_answers_a_stored_question(self):
        self.assess(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent'), asks('sel:1', '45380', pf.CECUM_PASSAGE, 'extent'))
        (row,) = self.extent_rows()
        found, stored = answers.addendum_detail(self.s.encounter, row['id'])
        self.assertTrue(found)
        self.assertEqual((stored.fact, stored.state, stored.proposal.code in ('45385', '45380')),
                         ('extent', models.Clarification.OPEN, True))
        response = self.client.post(f'/api/encounters/{self.s.encounter.pk}/addenda', content_type='application/json',
                                    data=json.dumps({'text': 'The colonoscope was advanced to the cecum.',
                                                     'clarification_id': row['id'], 'synthetic_attestation': 'yes'}))
        self.assertEqual(response.status_code, 201, response.content)
        stored.refresh_from_db()
        self.assertEqual(stored.state, models.Clarification.ANSWERED)


class SaveRefusalsTests(DetailsCase):
    """The new values are taken only where the row offers them."""

    def test_removing_the_date_is_refused_where_the_row_does_not_offer_it(self):
        encounter = self.context_for(pf.GI_NOTE, '1998-01-01')  # one documented date: "Use document date" instead
        (row,) = answers.details_needed(encounter, None)
        self.assertEqual([choice['value'] for choice in row['choices']], [answers.USE_DOCUMENT])
        response = self.post([self.answer(row, 'clear')], encounter=encounter)
        self.assertEqual((response.status_code, response.json()['error']), (400, answers.NOT_OFFERED))
        self.assertEqual(encounter.contexts.count(), 1)

    def test_a_value_for_a_clinical_detail_is_still_refused_on_a_shared_row(self):
        self.assess(asks('sel:0', '45385', pf.SNARE_PASSAGE, 'extent'), asks('sel:1', '45380', pf.CECUM_PASSAGE, 'extent'))
        (row,) = [item for item in self.rows() if item['fact'] == 'extent']
        for value in ('cecum', 'clear', 'use_document', '2026-10-21'):
            with self.subTest(value):
                response = self.post([self.answer(row, value)])
                self.assertEqual((response.status_code, response.json()['error']), (400, answers.CLINICAL))
        self.assertFalse(models.MemberAnswer.objects.exists())
        self.assertFalse(jobs.busy(self.s.encounter))


def shipped_scanner():
    """ops/scan_customer.py, the shipped reader the install's scan runs (loaded from its file: ops is no package)."""
    name = 'cux_r2_scan_customer'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(settings.BASE_DIR) / 'ops' / 'scan_customer.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module  # its dataclasses read their module back while it loads
        spec.loader.exec_module(module)
    return sys.modules[name]


class BundleScanTests(TestCase):
    """L4-1: the customer bundle - the page HTML and every file a collectstatic with the release's own storage writes,
    which WhiteNoise serves (hashed and compressed copies included) - passes the shipped denylist's bundle scan as
    ops/scan_customer.py reads it (the walk's reader, ops/verify_browser.cjs, is held to it in
    tests/frontend/app.test.cjs): two developer comments naming an HTTP status had failed it while the suite's own
    narrower net passed."""

    def test_the_shipped_scanner_finds_nothing_in_the_customer_bundle(self):
        scan = shipped_scanner()
        ctx = scan.scan_context(allowed=['cpt.quillmd.com'])
        client = Client()
        client.force_login(f.member(f.workspace(), f.user('reviewer')))
        with override_settings(STORAGES=PLAIN_STATIC):
            page = client.get('/')
        self.assertEqual(page.status_code, 200)
        self.assertEqual(scan.scan_text(page.content.decode('utf-8'), ctx, 'bundle', 'GET /'), [])
        scanned = []
        with tempfile.TemporaryDirectory(dir=settings.STATE_DIR) as root, override_settings(STATIC_ROOT=root):
            call_command('collectstatic', interactive=False, verbosity=0)
            for path in sorted(Path(root, 'studio').rglob('*')):
                plain = path.name[:-3] if path.name.endswith('.gz') else path.name
                if not path.is_file() or not plain.endswith(('.js', '.css')):
                    continue
                data = path.read_bytes()
                text = (gzip.decompress(data) if path.name.endswith('.gz') else data).decode('utf-8', 'replace')
                scanned.append(path.name)
                self.assertEqual(scan.scan_text(text, ctx, 'bundle', path.name), [], path.name)
        self.assertTrue({'app.js', 'app.js.gz', 'styles.css'} <= set(scanned), scanned)
        planted = scan.scan_text('// HTTP 409 with {"error_code": "client_outdated"}', ctx, 'bundle', 'planted')
        self.assertEqual([(hit['id'], hit['severity']) for hit in planted], [('http_status', 'hard')])
