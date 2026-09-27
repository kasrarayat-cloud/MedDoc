"""Synthetic upload/review/clinical/export checks for protected signing structures. No providers."""
import hashlib
import io
from unittest.mock import patch
from zipfile import ZipFile

from django.test import TestCase, override_settings
from lxml import etree

from core import generation
from core.models import Encounter
from core.security import private_path
from documents import word_v3
from documents.test_signing_areas import signing_form
from .test_word_v3_workflow import V3, V3Fixture


@override_settings(**V3)
class SigningWorkflow(V3Fixture, TestCase):
    def setUp(self):
        super().setUp()
        self.original = signing_form(table=False)
        self.template, self.version = self.uploaded()

    def start(self, version=None):
        self.version = self.confirm(self.template, version)
        self.assertEqual(self.new_encounter(self.version, notes='Participant ID: SYNTHETIC-123').status_code, 302)
        return Encounter.objects.order_by('-created_at').first()

    def save_answers(self, encounter, values):
        encounter.refresh_from_db()
        payload = {'revision': encounter.revision}
        for f in self.version.fields:
            payload['reviewed_' + f['key']] = 'on'
            payload['answer_' + f['key']] = values.get(f['key'], '')
        return self.client.post(f'/encounters/{encounter.pk}/save/', payload)

    def test_review_lists_protected_areas_and_correction_preserves_binding(self):
        page = self.client.get(f'/templates/{self.template.pk}/')
        self.assertEqual(len(page.context['v3_rows']), 4)
        self.assertContains(page, 'Protected signing block')
        name = next(f for f in self.version.fields if f['label'] == 'Name of Participant')
        self.assertEqual(self.client.post(f'/templates/{self.template.pk}/', {
            'action': 'v3_save', 'mapping_version': self.version.pk,
            'label_' + name['key']: 'Participant signing name'}).status_code, 302)
        latest = self.latest(self.template)
        old = self.version.fields
        new = next(f for f in latest.fields if f['key'] == name['key'])
        self.assertTrue(new['write_protected'])
        self.assertEqual(new['locator'], name['locator'])
        self.version.refresh_from_db(); self.assertEqual(self.version.fields, old)
        self.assertEqual(latest.corrections['renamed'][0]['from'], 'Name of Participant')

    def test_notes_never_fill_protected_name_date_or_initials(self):
        fields = word_v3.inspect(signing_form())['fields']
        asked, held, original = generation.v3_generation_fields(fields)
        self.assertEqual([f['label'] for f in asked], ['Participant ID'])
        self.assertIn('Name of Participant', held)
        with patch('socket.socket.connect', side_effect=AssertionError('Network denied')):
            positive = generation.generate('Participant ID: SYNTHETIC-123', fields)[0]
            answers = generation.generate('Participant ID: SYNTHETIC-123\nName of Participant: Test Person\nDate: 2026-09-27', fields)[0]
        self.assertEqual(positive[asked[0]['key']]['text'], 'SYNTHETIC-123')
        for f in fields:
            if f.get('write_protected'):
                self.assertEqual((answers[f['key']]['status'], answers[f['key']]['text']), ('missing', ''))
                self.assertIn('Protected', answers[f['key']]['reason'])

    def test_short_and_long_protected_entries_refuse_without_saving(self):
        encounter = self.start()
        page = self.client.get(f'/encounters/{encounter.pk}/')
        self.assertContains(page, 'Protected signing block')
        fields = [f for f in self.version.fields if f.get('write_protected') and f['kind'] in ('text', 'date')]
        self.assertEqual(len(fields), 2)
        for f in fields:
            for value in ('Test Person', 'Long synthetic text ' * 100):
                before = Encounter.objects.get(pk=encounter.pk)
                response = self.save_answers(encounter, {f['key']: value})
                self.assertEqual(response.status_code, 400)
                self.assertContains(response, 'protected signing area', status_code=400)
                after = Encounter.objects.get(pk=encounter.pk)
                self.assertEqual((after.answers, after.revision), (before.answers, before.revision))

    def test_missing_ordinary_long_supported_answer_round_trip_preserves_signing_regions(self):
        key = next(f['key'] for f in self.version.fields if not f.get('write_protected'))
        for value in ('', 'SYNTHETIC-123', 'SYNTHETIC LONG IDENTIFIER ' * 50):
            encounter = self.start()
            self.assertEqual(self.save_answers(encounter, {key: value}).status_code, 302)
            encounter.refresh_from_db()
            response = self.client.post(f'/encounters/{encounter.pk}/finalize/',
                                        {'revision': encounter.revision, 'reviewed': 'on'}, follow=True)
            self.assertEqual(response.status_code, 200)
            encounter.refresh_from_db(); self.assertEqual(encounter.status, 'finalized')
            output = private_path(encounter.export_path).read_bytes()
            self.assertEqual(hashlib.sha256(output).hexdigest(), encounter.export_sha256)
            with ZipFile(io.BytesIO(self.original)) as before, ZipFile(io.BytesIO(output)) as after:
                old = etree.fromstring(before.read('word/document.xml'))
                new = etree.fromstring(after.read('word/document.xml'))
                self.assertEqual([etree.tostring(x) for x in old.find(word_v3.q('w:body'))][1:],
                                 [etree.tostring(x) for x in new.find(word_v3.q('w:body'))][1:])

    def test_finalization_rejects_a_forged_reviewed_protected_answer(self):
        encounter = self.start()
        self.assertEqual(self.save_answers(encounter, {}).status_code, 302)
        encounter.refresh_from_db()
        field = next(f for f in self.version.fields if f['label'] == 'Name of Participant')
        encounter.answers[field['key']].update(text='Test Person', status='edited', reviewed=True)
        encounter.save()
        response = self.client.post(f'/encounters/{encounter.pk}/finalize/',
                                    {'revision': encounter.revision, 'reviewed': 'on'}, follow=True)
        self.assertEqual(response.status_code, 200)
        encounter.refresh_from_db()
        self.assertNotEqual(encounter.status, 'finalized')
        self.assertEqual(encounter.export_path, '')

    def test_floating_form_warning_and_refused_export_keep_the_draft_and_original(self):
        data = signing_form()
        self.template, self.version = self.uploaded(data=data, name='Synthetic floating signing form')
        page = self.client.get(f'/templates/{self.template.pk}/')
        self.assertContains(page, 'Filled export is unavailable')
        encounter = self.start()
        page = self.client.get(f'/encounters/{encounter.pk}/')
        self.assertContains(page, 'data-export-refusal')
        self.assertContains(page, 'Download unchanged form')
        key = next(f['key'] for f in self.version.fields if not f.get('write_protected'))
        self.assertEqual(self.save_answers(encounter, {key: 'SYNTHETIC-123'}).status_code, 302)
        encounter.refresh_from_db(); before = encounter.answers; prior_status = encounter.status
        response = self.client.post(f'/encounters/{encounter.pk}/finalize/',
                                    {'revision': encounter.revision, 'reviewed': 'on'}, follow=True)
        self.assertContains(response, 'Filled export is unavailable')
        encounter.refresh_from_db()
        self.assertEqual((encounter.status, encounter.export_path, encounter.answers), (prior_status, '', before))
        self.assertEqual(private_path(self.template.original_path).read_bytes(), data)
        self.assertEqual(self.save_answers(encounter, {}).status_code, 302)
        encounter.refresh_from_db()
        self.client.post(f'/encounters/{encounter.pk}/finalize/', {'revision': encounter.revision, 'reviewed': 'on'})
        encounter.refresh_from_db(); self.assertEqual(encounter.status, 'finalized')
