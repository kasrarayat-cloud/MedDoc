"""Real private HTTP/model/Word sandbox workflows with synthetic clinical data.

Requires the separately built qualified SDK runtime. Missing runtime is an
explicit skip; it is never replaced by a mocked document engine.
"""
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import tempfile
from unittest import skipUnless
from unittest.mock import patch
from zipfile import ZipFile
from io import BytesIO
from html.parser import HTMLParser

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from core.billing import welcome_credit
from core.generation import configuration
from core.jobs import enqueue, run_one
from core.models import Department, Encounter, Job, Membership, Organization, Patient, Template, User
from core.security import private_path
from core.wm_review import BACKEND, ORIGINAL_SHA256
from documents import DocumentError, resolve_template
from .test_workflow import TEST_SETTINGS
from core.tests.audio_fixtures import wav_bytes


def word_runtime_is_usable():
    """Every condition sdk_service.configuration() needs, so a partly-configured host SKIPS rather than fails.

    This predicate named two of the THREE variables the service requires, and said nothing about
    ownership. With two of three set, these eight tests ran and failed for an environment reason —
    reporting a defect in the document workflow when the only thing wrong was the host. A skip that
    is narrower than the thing it guards is a check that cries wolf; this one now lists exactly what
    is missing, so whoever meets it can fix it or accept it knowingly.
    """
    missing = [name for name in ('QUILLMD_WORD_RUNTIME', 'QUILLMD_WORD_MANIFEST',
                                 'QUILLMD_WORD_MANIFEST_SHA256') if not os.getenv(name)]
    if missing:
        return False, 'not configured here: ' + ', '.join(missing)
    runtime = Path(os.getenv('QUILLMD_WORD_RUNTIME'))
    if not runtime.exists():
        return False, 'the configured runtime does not exist: %s' % runtime
    # The service refuses a processor the running account can modify, which is the point of the
    # separate service identity. Running these as the owner proves nothing about the shipped path.
    try:
        owned_by_us = runtime.stat().st_uid == os.getuid()
    except OSError as error:
        return False, 'the runtime cannot be stat()ed: %s' % error
    if owned_by_us:
        return False, ('this account owns the Word processor, and the service refuses a processor it '
                       'can modify — run these where the runtime belongs to another identity')
    return True, ''


WORD_RUNTIME_USABLE, WORD_RUNTIME_REASON = word_runtime_is_usable()
if os.getenv('QUILLMD_REQUIRE_WORD_TESTS') == '1':
    if not WORD_RUNTIME_USABLE:
        raise RuntimeError('Required Word integration tests cannot run: ' + WORD_RUNTIME_REASON)
    if os.getenv('QUILLMD_WORD_QUALIFICATION') == '1':
        raise RuntimeError('Required Word integration tests must use the ordinary ownership boundary.')


@skipUnless(WORD_RUNTIME_USABLE,
            'Live Word document workflow NOT EXERCISED — ' + (WORD_RUNTIME_REASON or 'unknown reason') +
            '. No claim is made about this path from this run.')
@override_settings(**TEST_SETTINGS)
class WMDocumentWorkflow(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.state = patch.dict(os.environ, {'QUILLMD_STATE_DIR': self.directory.name})
        self.state.start(); self.addCleanup(self.state.stop)
        self.override = override_settings(MEDIA_ROOT=Path(self.directory.name) / 'private')
        self.override.enable(); self.addCleanup(self.override.disable)
        self.user = User.objects.create_user(username='wm-clinician', email='wm@synthetic.invalid',
                                             first_name='SYNTHETIC', last_name='Actual Clinician',
                                             verified_at=timezone.now())
        self.organization = Organization.objects.create(name='Synthetic WM organization')
        self.department = Department.objects.create(organization=self.organization, name='Synthetic X-ray')
        Membership.objects.create(user=self.user, department=self.department, role='clinician')
        welcome_credit(self.user)
        self.client.force_login(self.user)
        self.patient = Patient.objects.create(department=self.department, display_name='SYNTHETIC WM PATIENT',
                                               reference='WM-SYNTHETIC', created_by=self.user)
        original_path = Path(__file__).resolve().parents[3] / 'WM IOV Template.docx'
        self.original = original_path.read_bytes()
        self.assertEqual(hashlib.sha256(self.original).hexdigest(), ORIGINAL_SHA256)
        response = self.client.post('/templates/upload/', {'name': 'Synthetic WM workflow',
            'department': self.department.pk, 'synthetic_only': 'on',
            'file': SimpleUploadedFile('WM IOV Template.docx', self.original)})
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None))
        self.template = Template.objects.get(name='Synthetic WM workflow')
        self.version = self.template.versions.get(number=1)
        self.assertEqual(self.version.document_backend['backend'], BACKEND)
        self.assertEqual((len(self.version.fields), len(self.version.review_requirements)), (90, 14))

    def prepare(self, *, positive=False, missing_measurement=False, long_answer=False, select_variants=True):
        values = {}
        for field in self.version.fields:
            if field['kind'] == 'choice':
                value = next(v for v in field['options'] if v not in ('reflux positive.', 'Asymptomatic'))
            elif field['kind'] == 'measurement':
                value = '3.2 mm' if field['locator']['unit'] == 'mm' else '400 ms'
            else:
                value = 'SYNTHETIC ' + field['key']
            values[field['key']] = value
        if positive:
            values['sdt_-213273323'] = 'reflux positive.'
            values['measurement_1_2'] = '650 ms'
            values['sdt_1706206184'] = ', however, there has been a recurrence.'
        if missing_measurement: values['measurement_15_1'] = ''
        if long_answer: values['patient_name'] = 'SYNTHETIC 😀 ' + ('documented ' * 1800) + 'END-OF-COMPLETE-ANSWER'
        variants = {row['key']: row['default_variant'] for row in self.version.review_requirements}
        for key in ('claim_23', 'claim_27'): variants[key] = 'original'
        for key in ('claim_30', 'claim_31', 'claim_34', 'claim_35'): variants[key] = 'selected'
        variants.update(claim_19='technique_only', claim_32='positive' if positive else 'negative', claim_36='negative')
        answers = {key: {'text': value, 'status': 'supported' if value else 'missing',
                         'reviewed_by': '', 'revision': 0, 'evidence': []} for key, value in values.items()}
        context = {'reviewer_id': str(self.user.pk), 'revision': 0, 'notes': '',
                   'signer_name': self.user.get_full_name(), 'finalized_at': timezone.now().isoformat()}
        resolved = resolve_template(private_path(self.template.original_path), self.version.document_backend,
                                    answers, claim_variants=variants, trusted_context=context)['review_requirements']
        lines = [field['label'] + ': ' + values[field['key']] for field in self.version.fields if values[field['key']]]
        lines += [row['label'] + ': ' + row['text'] for row in resolved if row['kind'] == 'assertion']
        notes = '\n'.join(lines)
        response = self.client.post('/encounters/new/', {'patient': self.patient.pk,
            'template_version': self.version.pk, 'notes': notes, 'service_date': timezone.localdate().isoformat(), 'synthetic_only': 'on'})
        self.assertEqual(response.status_code, 302)
        encounter = Encounter.objects.get(template_version=self.version)
        self.client.post(f'/encounters/{encounter.pk}/generate/')
        self.assertTrue(run_one())
        encounter.refresh_from_db()
        self.assertEqual(Job.objects.get(encounter=encounter).state, 'succeeded')
        for key, value in values.items(): self.assertEqual(encounter.answers[key]['text'], value)
        # First select alternatives without claiming to have seen new wording.
        self.values, self.variants = values, variants
        if select_variants:self.save(encounter, reviewed=False)
        return encounter

    def payload(self, encounter, *, reviewed=True):
        response = self.client.get(f'/encounters/{encounter.pk}/')
        self.assertEqual(response.status_code, 200)
        if reviewed:self.assertFalse(response.context['wm_review_error'], response.context['wm_review_error'])
        payload = {'revision': encounter.revision}
        for field in self.version.fields:
            key, value = field['key'], self.values[field['key']]
            payload['answer_' + key] = value
            payload['source_' + key] = field['label'] + ': ' + value if value else ''
            if reviewed: payload['reviewed_' + key] = 'on'
        for row in response.context['wm_requirements']:
            key = row['key']
            payload['claim_variant_' + key] = self.variants[key]
            payload['claim_token_' + key] = row.get('review_token', '')
            payload['claim_source_' + key] = row['label'] + ': ' + row['text'] if row['kind'] == 'assertion' else ''
            if reviewed: payload['claim_reviewed_' + key] = 'on'
        return payload

    def save(self, encounter, *, reviewed=True, payload=None):
        response = self.client.post(f'/encounters/{encounter.pk}/save/', payload or self.payload(encounter, reviewed=reviewed))
        self.assertEqual(response.status_code, 302)
        encounter.refresh_from_db()
        return response

    def finalize(self, encounter):
        response = self.client.post(f'/encounters/{encounter.pk}/finalize/', {'revision': encounter.revision, 'reviewed': 'on'})
        self.assertEqual(response.status_code, 302)
        encounter.refresh_from_db()
        self.assertEqual(encounter.status, 'finalized', encounter.template_review.get('assessment', {}).get('blockers'))
        response = self.client.get(f'/encounters/{encounter.pk}/export/')
        self.assertEqual(response.status_code, 200)
        payload = b''.join(response.streaming_content)
        self.assertEqual(hashlib.sha256(payload).hexdigest(), encounter.export_sha256)
        self.assertEqual(private_path(self.template.original_path).read_bytes(), self.original)
        return payload

    def test_upload_generate_review_original_export_actual_identity_and_blank_measurement(self):
        encounter = self.prepare(missing_measurement=True)
        self.save(encounter)
        self.assertTrue(encounter.template_review['assessment']['complete'])
        self.assertEqual(encounter.answers['measurement_15_1']['text'], '')
        exported = self.finalize(encounter)
        with ZipFile(BytesIO(exported)) as zipped:
            document = zipped.read('word/document.xml').decode()
        self.assertIn(self.user.get_full_name(), document)
        self.assertIn('No saphenous reflux in right lower extremity.', document)
        self.assertNotIn('Evaluation Only', document)
        self.assertEqual(encounter.finalized_by_id, self.user.pk)

    def test_positive_reflux_approved_statement_and_long_answer_are_not_truncated(self):
        encounter = self.prepare(positive=True, long_answer=True)
        self.save(encounter)
        exported = self.finalize(encounter)
        with ZipFile(BytesIO(exported)) as zipped:
            document = zipped.read('word/document.xml').decode()
        self.assertIn('END-OF-COMPLETE-ANSWER', document)
        self.assertNotIn('No saphenous reflux in right lower extremity.', document)
        self.assertIn('reflux positive.', document)

    def test_initial_positive_conflict_page_submits_rendered_hidden_identity_variants(self):
        encounter = self.prepare(positive=True, select_variants=False)
        response = self.client.get(f'/encounters/{encounter.pk}/')
        self.assertTrue(response.context['wm_review_error'])
        class HiddenVariants(HTMLParser):
            def __init__(self):
                super().__init__(); self.values = {}
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'input' and attrs.get('type') == 'hidden' and attrs.get('name', '').startswith('claim_variant_'):
                    self.values[attrs['name']] = attrs.get('value', '')
        rendered = HiddenVariants(); rendered.feed(response.content.decode())
        self.assertEqual(rendered.values, {'claim_variant_claim_11': 'trusted',
                                          'claim_variant_claim_39': 'original',
                                          'claim_variant_claim_45': 'trusted',
                                          'claim_variant_claim_46': 'trusted'})
        payload = self.payload(encounter, reviewed=False)
        payload.update(rendered.values)
        self.save(encounter, payload=payload)
        self.assertEqual(encounter.template_review['schema'], 1)
        self.assertEqual(encounter.template_review['decisions']['claim_32']['variant'], 'positive')
        self.assertFalse(encounter.template_review['assessment']['complete'])
        response = self.client.get(f'/encounters/{encounter.pk}/')
        self.assertFalse(response.context['wm_review_error'], response.context['wm_review_error'])

    def test_changed_statement_or_forged_visible_proof_requires_new_review(self):
        encounter = self.prepare()
        payload = self.payload(encounter)
        payload['claim_variant_claim_19'] = 'original'
        self.save(encounter, payload=payload)
        self.assertFalse(encounter.template_review['decisions']['claim_19']['reviewed'])
        self.assertFalse(encounter.template_review['assessment']['complete'])
        self.variants['claim_19'] = 'original'
        payload = self.payload(encounter)
        payload['claim_token_claim_9'] = 'forged-proof'
        self.save(encounter, payload=payload)
        self.assertFalse(encounter.template_review['decisions']['claim_9']['reviewed'])
        self.client.post(f'/encounters/{encounter.pk}/finalize/', {'revision': encounter.revision, 'reviewed': 'on'})
        encounter.refresh_from_db(); self.assertNotEqual(encounter.status, 'finalized')
        payload = self.payload(encounter)
        with patch('documents.resolve_template', side_effect=DocumentError('Synthetic busy-processor failure.')):
            self.save(encounter, payload=payload)
        self.assertEqual(encounter.template_review['schema'], 0)
        self.assertTrue(all(not row['reviewed'] for row in encounter.template_review['decisions'].values()))

    def test_unsupported_choice_stays_visible_and_cannot_export(self):
        encounter = self.prepare()
        payload = self.payload(encounter)
        payload['answer_sdt_-213273323'] = 'Unsupported synthetic option'
        self.save(encounter, payload=payload)
        self.assertEqual(encounter.answers['sdt_-213273323']['text'], 'Unsupported synthetic option')
        response = self.client.get(f'/encounters/{encounter.pk}/')
        self.assertContains(response, 'Unsupported current value: Unsupported synthetic option')
        self.client.post(f'/encounters/{encounter.pk}/finalize/', {'revision': encounter.revision, 'reviewed': 'on'})
        encounter.refresh_from_db(); self.assertFalse(encounter.export_path)

    def test_source_edit_and_simulated_voice_adoption_clear_reviews(self):
        encounter = self.prepare(); self.save(encounter)
        self.client.post(f'/encounters/{encounter.pk}/notes/', {'revision': encounter.revision,
                          'notes': encounter.notes + '\nSynthetic correction: revised source'})
        encounter.refresh_from_db()
        self.assertEqual(encounter.template_review, {}); self.assertEqual(encounter.answers, {})
        # Explicitly simulated transcription: this verifies adoption/invalidation,
        # not microphone capture or a live transcription provider.
        audio = private_path('audio/synthetic.wav'); audio.parent.mkdir(parents=True)
        audio.write_bytes(wav_bytes(tag='wm-voice')); audio.chmod(0o600)
        config = {**configuration(), 'voice_rate_minute': '0', 'voice_rate_second': '', 'voice_max_cost': '0'}
        encounter.template_review = {'schema': 0, 'synthetic_test_marker': True}
        encounter.save(update_fields=['template_review'])
        enqueue(encounter, self.user, kind='transcription', input_path='audio/synthetic.wav', config=config)
        with patch('core.jobs.transcribe', return_value=('SYNTHETIC voice correction', Decimal('0'),
                   {'duration_seconds': '1'}, {'usd_per_minute': '0'}, 'synthetic-transcription-fixture', '', True)) as provider:
            self.assertTrue(run_one())
        provider.assert_called_once()
        encounter.refresh_from_db()
        self.assertIn('SYNTHETIC voice correction', encounter.notes)
        self.assertEqual(encounter.template_review, {}); self.assertEqual(encounter.answers, {})

    def test_employee_read_scope_review_denial_and_other_department_isolation(self):
        encounter = self.prepare()
        employee = User.objects.create_user(username='wm-employee', email='wm-employee@synthetic.invalid', verified_at=timezone.now())
        Membership.objects.create(user=employee, department=self.department, role='employee')
        self.client.force_login(employee)
        self.assertEqual(self.client.get(f'/encounters/{encounter.pk}/').status_code, 200)
        before = encounter.revision
        response = self.client.post(f'/encounters/{encounter.pk}/save/', {'revision': before, 'claim_reviewed_claim_9': 'on'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/finalize/', {'revision': before, 'reviewed': 'on'}).status_code, 403)
        encounter.refresh_from_db(); self.assertEqual(encounter.revision, before)
        other = Department.objects.create(organization=self.organization, name='Synthetic ultrasound')
        Membership.objects.filter(user=employee).update(department=other)
        for suffix in ('', 'export/', 'save/', 'finalize/'):
            url = f'/encounters/{encounter.pk}/' + suffix
            response = self.client.post(url, {'revision': before}) if suffix in ('save/', 'finalize/') else self.client.get(url)
            self.assertEqual(response.status_code, 404)

    def test_mapping_versions_copy_backend_and_requirements_but_reject_label_changes(self):
        labels = {row['key']: row['label'] for row in self.version.fields}
        response = self.client.post(f'/templates/{self.template.pk}/', {'labels': json.dumps(labels), 'mapping_version': str(self.version.pk)})
        self.assertEqual(response.status_code, 302)
        second = self.template.versions.get(number=2)
        self.assertEqual(second.document_backend, self.version.document_backend)
        self.assertEqual(second.review_requirements, self.version.review_requirements)
        labels['patient_name'] = 'Changed qualified label'
        response = self.client.post(f'/templates/{self.template.pk}/', {'labels': json.dumps(labels), 'mapping_version': str(second.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'fixed question labels')
        self.assertEqual(self.template.versions.count(), 2)
