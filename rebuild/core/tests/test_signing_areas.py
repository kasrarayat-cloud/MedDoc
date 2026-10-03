"""Synthetic upload/review/clinical/export checks for protected signing structures. No providers."""
import hashlib
import io
from unittest.mock import patch
from zipfile import ZipFile

from django.test import TestCase, override_settings
from lxml import etree

from core import generation
from core.models import Encounter, Job, MappingConfirmation, Reservation, TemplateVersion, Usage
from core.security import private_path
from documents import word_v3
from documents.test_signing_areas import signing_form
from .test_word_v3_workflow import V3, V3Fixture


def review_floating_table_exclusion(case, template, version):
    """Reach the floating-layout checks after an actual, source-bound partial-coverage review.

    This preserves the original and every mapped signing field. The table is explicitly left unchanged, not
    reclassified as supported, and its original automatic mapping remains unconfirmed.
    """
    issues = version.import_manifest['coverage']['selected_engine_issues']
    case.assertEqual([(row['code'], row['part'], row['slot']) for row in issues],
                     [('unmapped_answer', 'word/document.xml', 'b/tbl[0]')])
    original = private_path(template.original_path).read_bytes()
    response = case.client.post(f'/templates/{template.pk}/', {
        'action': 'v3_coverage', 'mapping_version': version.pk,
        'exclude_' + issues[0]['id']: 'on'})
    case.assertEqual(response.status_code, 302)
    reviewed = case.latest(template)
    case.assertEqual(reviewed.number, version.number + 1)
    case.assertEqual((reviewed.fields, reviewed.document_backend, reviewed.import_manifest),
                     (version.fields, version.document_backend, version.import_manifest))
    case.assertEqual(reviewed.corrections['coverage_review'], [{
        'id': issues[0]['id'], 'disposition': 'leave_unchanged',
        'source_sha256': template.sha256, 'reviewed_by': str(case.user.pk)}])
    case.assertEqual(private_path(template.original_path).read_bytes(), original)
    case.assertIsNone(TemplateVersion.objects.get(pk=version.pk).confirmed)
    return reviewed


@override_settings(**V3)
class SigningImportCoverage(V3Fixture, TestCase):
    def test_unreviewed_floating_table_still_refuses_confirmation_without_a_job_or_charge(self):
        original = signing_form()
        template, version = self.uploaded(data=original, name='Synthetic unreviewed floating form')
        issues = version.import_manifest['coverage']['selected_engine_issues']
        self.assertEqual([(row['code'], row['part'], row['slot']) for row in issues],
                         [('unmapped_answer', 'word/document.xml', 'b/tbl[0]')])
        before = (version.fields, version.import_manifest)
        response = self.client.post(f'/templates/{template.pk}/', {
            'action': 'v3_confirm', 'mapping_version': version.pk, 'checked_every_field': 'on'})
        self.assertContains(response, 'This import has unmapped answer areas', status_code=400)
        # A checked confirmation alone does not review any exclusion. Omitting the exact exclusion still refuses.
        response = self.client.post(f'/templates/{template.pk}/', {
            'action': 'v3_coverage', 'mapping_version': version.pk})
        self.assertContains(response, 'explicitly exclude every listed area', status_code=400)
        version.refresh_from_db()
        self.assertEqual((version.fields, version.import_manifest), before)
        self.assertEqual(template.versions.count(), 1)
        self.assertFalse(MappingConfirmation.objects.exists())
        self.assertFalse(Job.objects.exists())
        self.assertFalse(Reservation.objects.exists())
        self.assertFalse(Usage.objects.exists())
        self.assertEqual(private_path(template.original_path).read_bytes(), original)


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
        self.version = review_floating_table_exclusion(self, self.template, self.version)
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


@override_settings(**{**V3, 'AI_MODE': 'live', 'AI_PROVIDER': 'anthropic', 'AI_MODEL': 'claude-sonnet-5',
                      'AI_THINKING': 'disabled', 'AI_EFFORT': 'medium', 'AI_INFERENCE_GEO': '',
                      'AI_INPUT_RATE': '2', 'AI_OUTPUT_RATE': '10', 'AI_CACHED_RATE': '.2'})
class SigningGenerationAdmission(V3Fixture, TestCase):
    """Financial admission controls use synthetic wallets and mocked results; network is denied."""
    def setUp(self):
        super().setUp()
        self.original = signing_form()
        self.template, self.version = self.uploaded(data=self.original, name='Synthetic floating admission')
        self.version = review_floating_table_exclusion(self, self.template, self.version)
        self.version = self.confirm(self.template, self.version)
        self.assertEqual(self.new_encounter(self.version, notes='Participant ID: SYNTHETIC-123').status_code, 302)
        self.encounter = Encounter.objects.latest('created_at')
        self.network = patch('socket.socket.connect', side_effect=AssertionError('Network denied'))
        self.network.start(); self.addCleanup(self.network.stop)

    def assert_no_financial_request(self):
        from core.models import Job, Reservation, Usage, ProviderReceipt, Wallet
        self.assertFalse(Job.objects.exists())
        self.assertFalse(Reservation.objects.exists())
        self.assertFalse(Usage.objects.exists())
        self.assertFalse(ProviderReceipt.objects.exists())
        self.assertFalse(Wallet.objects.exclude(reserved=0).exists())

    def test_http_refuses_before_quote_and_leaves_original_and_mapping_available(self):
        from core import billing, views
        with patch('core.views.usage_quote', wraps=views.usage_quote) as quote, \
                patch('core.jobs.reserve', wraps=billing.reserve) as reserve, \
                patch('core.jobs.generation.generate') as provider:
            token = self.client.get(f'/encounters/{self.encounter.pk}/').context['usage_quote']
            response = self.client.post(f'/encounters/{self.encounter.pk}/generate/',
                                       {'revision': self.encounter.revision, 'usage_quote': token}, follow=True)
        self.assert_no_financial_request()
        quote.assert_not_called(); reserve.assert_not_called(); provider.assert_not_called()
        self.assertContains(response, 'Generation is unavailable')
        self.assertContains(response, 'Nothing was sent or charged')
        self.assertEqual(self.client.get(f'/templates/{self.template.pk}/').status_code, 200)
        download = self.client.get(f'/templates/{self.template.pk}/original/')
        self.assertEqual(b''.join(download.streaming_content), self.original)

    def test_direct_enqueue_refuses_before_job_and_reservation(self):
        from core.jobs import enqueue
        from django.core.exceptions import ValidationError
        with patch('core.jobs.reserve') as reserve, patch('core.jobs.generation.generate') as provider:
            with self.assertRaisesMessage(ValidationError, 'Generation is unavailable'):
                enqueue(self.encounter, self.user)
        self.assert_no_financial_request()
        reserve.assert_not_called(); provider.assert_not_called()

    def test_old_queued_job_refuses_before_provider_and_releases_real_hold(self):
        from decimal import Decimal
        from core.billing import reserve
        from core.jobs import run_one
        from core.models import Job, Reservation, Usage, ProviderReceipt, Wallet
        from core.models import Template
        Template.objects.filter(pk=self.template.pk).update(warnings=[])
        config = generation.configuration()
        job = Job.objects.create(encounter=self.encounter, user=self.user, kind='generation',
                                 revision=self.encounter.revision, request_key='synthetic-old-floating', config=config)
        reserve(job, Decimal('.02'))
        self.assertTrue(Reservation.objects.filter(job=job, state='held').exists())
        fixture = generation.generate(self.encounter.notes, self.version.fields, {**config, 'mode': 'fixture'})
        result = (fixture[0], Decimal('.01'), {'input_tokens': 5000, 'output_tokens': 0},
                  {'input_per_million': '2', 'output_per_million': '10'},
                  'anthropic:synthetic-offline', 'synthetic-admission', False)
        with patch('core.jobs.generation.generate', return_value=result) as provider:
            self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(job.state, 'failed', {'state': job.state, 'provider_calls': provider.call_count,
                         'usage_costs': list(Usage.objects.filter(job=job).values_list('actual_cost', 'charged_cost')),
                         'receipt_count': ProviderReceipt.objects.filter(job=job).count()})
        provider.assert_not_called()
        self.assertIn('Generation is unavailable', job.error)
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertFalse(ProviderReceipt.objects.filter(job=job).exists())
        self.assertFalse(Reservation.objects.filter(job=job, state='held').exists())
        self.assertEqual(Reservation.objects.get(job=job).state, 'released')
        self.assertFalse(Wallet.objects.exclude(reserved=0).exists())
        self.encounter.refresh_from_db(); self.assertEqual(self.encounter.answers, {})


    def test_missing_historical_warning_still_refuses_direct_enqueue(self):
        from core.jobs import enqueue
        from core.models import Template
        from django.core.exceptions import ValidationError
        Template.objects.filter(pk=self.template.pk).update(warnings=[])
        with self.assertRaisesMessage(ValidationError, 'Generation is unavailable'):
            enqueue(self.encounter, self.user)
        self.assert_no_financial_request()

    def test_integrity_or_unavailable_parser_refuses_without_source_detail(self):
        from core.jobs import enqueue
        from core.models import Template
        from documents import DocumentError
        from django.core.exceptions import ValidationError
        Template.objects.filter(pk=self.template.pk).update(warnings=[])
        path = private_path(self.template.original_path)
        path.write_bytes(signing_form(table=False))
        with self.assertRaisesMessage(ValidationError, 'could not be verified'):
            enqueue(self.encounter, self.user)
        path.write_bytes(self.original)
        with patch('documents.inspect_template', side_effect=DocumentError('SYNTHETIC PRIVATE DETAIL')):
            with self.assertRaisesMessage(ValidationError, 'could not be verified') as caught:
                enqueue(self.encounter, self.user)
        self.assertNotIn('SYNTHETIC PRIVATE DETAIL', str(caught.exception))
        self.assert_no_financial_request()

    def test_nonfloating_form_can_queue_hold_and_complete_generation(self):
        from decimal import Decimal
        from core.jobs import enqueue, run_one
        from core.models import Reservation, Usage, ProviderReceipt
        template, version = self.uploaded(data=signing_form(table=False), name='Synthetic supported admission')
        version = self.confirm(template, version)
        self.new_encounter(version, notes='Participant ID: SYNTHETIC-123')
        encounter = Encounter.objects.latest('created_at')
        job = enqueue(encounter, self.user)
        self.assertTrue(Reservation.objects.filter(job=job, state='held').exists())
        config = generation.configuration()
        fixture = generation.generate(encounter.notes, version.fields, {**config, 'mode': 'fixture'})
        result = (fixture[0], Decimal('.01'), {'input_tokens': 5000, 'output_tokens': 0},
                  {'input_per_million': '2', 'output_per_million': '10'},
                  'anthropic:synthetic-offline', 'synthetic-supported-admission', False)
        with patch('core.jobs.generation.generate', return_value=result) as provider:
            self.assertTrue(run_one())
        provider.assert_called_once()
        job.refresh_from_db(); self.assertEqual(job.state, 'succeeded')
        self.assertEqual(Usage.objects.get(job=job).charged_cost, Decimal('.015'))
        self.assertTrue(ProviderReceipt.objects.filter(job=job).exists())
        encounter.refresh_from_db()
        key = next(f['key'] for f in version.fields if not f.get('write_protected'))
        self.assertEqual(encounter.answers[key]['text'], 'SYNTHETIC-123')

    def test_independent_voice_on_floating_form_keeps_its_reviewed_transcript_path(self):
        import os
        from decimal import Decimal
        from core.jobs import enqueue, run_one
        from core.models import Reservation, Usage
        from core.tests.audio_fixtures import wav_bytes
        path = private_path('audio/' + 'a'*48 + '.wav')
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(wav_bytes())
        with patch.dict(os.environ, {'QUILLMD_DEEPGRAM_RATE_PER_MINUTE': '.006', 'QUILLMD_DEEPGRAM_RATE_PER_SECOND': ''}):
            config = {**generation.configuration(), 'transcript_review_required': True}
            job = enqueue(self.encounter, self.user, kind='transcription', input_path='audio/'+'a'*48+'.wav', config=config)
        self.assertTrue(Reservation.objects.filter(job=job, state='held').exists())
        response = ('SYNTHETIC dictated note', Decimal('.001'), {'duration_seconds': '10'},
                    {'usd_per_minute': '.006'}, 'deepgram:synthetic-offline', 'synthetic-voice-admission', False)
        with patch('core.jobs.transcribe', return_value=response) as provider:
            self.assertTrue(run_one())
        provider.assert_called_once()
        job.refresh_from_db(); self.assertEqual(job.state, 'succeeded')
        self.assertEqual(Usage.objects.get(job=job).charged_cost, Decimal('.0015'))
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.notes, 'Participant ID: SYNTHETIC-123')
        self.assertIn('SYNTHETIC dictated note', private_path(job.result_path).read_text())
