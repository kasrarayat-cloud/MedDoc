"""Focused offline supplemental-output checks; never decide for the real user.

Only the retained response is used. Every decision lives in Django's isolated
test database, and the assessment is rebound to those test-only identifiers.
"""
from copy import deepcopy
import hashlib
import json
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from docx import Document

from core import coding_output as output, coding_service as service
from core.coding_export import eligible_codes
from core.models import (CodingContext, CodingDecision, CodingOutputDecision,
                         CodingRun, Encounter, Membership, Patient, User)
from core.tests import test_corti_workflow as workflow
from core.tests.test_coding_export import document_bytes, texts


@override_settings(CODING_PROVIDER='corti', CORTI_CODING_MODE='replay',
                   CODING_ALLOW_TEST_FIXTURES=True, CORTI_REPLAY_FIXTURE=workflow.FIXTURE,
                   SYNTHETIC_ONLY=True, ADMIN_SITE=False, STORAGES=workflow.STORAGES,
                   CPT_ENTITLEMENT_MANIFEST='/missing-corti-output-test-entitlement.json')
class BoundedOutputReviewTests(TestCase):
    def setUp(self):
        # Reuse fixture construction only, not the completed replay test campaign.
        workflow.CortiWorkflowTests.setUp(self)
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        media = override_settings(MEDIA_ROOT=self.root)
        media.enable(); self.addCleanup(media.disable)
        document = Document(BytesIO(document_bytes()))
        document.paragraphs[0].text = self.encounter.notes
        stream = BytesIO(); document.save(stream)
        self.original = stream.getvalue()
        self.original_path = self.root / 'exports' / 'original.docx'
        self.original_path.parent.mkdir(mode=0o700)
        self.original_path.write_bytes(self.original)
        self.encounter.status = 'finalized'
        self.encounter.finalized_at = timezone.now()
        self.encounter.finalized_by = self.actor
        self.encounter.export_path = 'exports/original.docx'
        self.encounter.export_sha256 = hashlib.sha256(self.original).hexdigest()
        self.encounter.save(update_fields=['status', 'finalized_at', 'finalized_by',
                                          'export_path', 'export_sha256'])
        self.run = workflow.CortiWorkflowTests.complete(self)
        self.run = service.update_selection(self.run, self.actor,
            {'selected_ids': ['selected:0'], 'overrides': {}}, self.run.selection_revision)
        self.base = service.approve(self.run, self.actor, self.run.input_digest,
                                    service.selection_digest(self.run))
        self.before_base = CodingDecision.objects.values().get(pk=self.base.pk)
        self.before_context = CodingContext.objects.values().get(encounter=self.encounter)
        self.before_run = CodingRun.objects.values().get(pk=self.run.pk)
        manifest = Path(__file__).parents[2] / 'ops/fixtures/corti_output_review.json'
        self.assessment = json.loads(manifest.read_text())
        self.assessment['scope'] = {
            'encounter_id': str(self.encounter.pk), 'patient_id': str(self.encounter.patient_id),
            'run_id': str(self.run.pk), 'input_digest': self.run.input_digest,
            'result_digest': service.digest(self.run.result),
            'requests_digest': service.digest(self.run.requests),
            'notes_sha256': hashlib.sha256(self.encounter.notes.encode()).hexdigest(),
            'service_date': self.encounter.service_date.isoformat(),
        }
        self.install(self.assessment)
        # A review/read/decision/export may never queue or send a new request.
        no_enqueue = patch('core.coding_service.ensure_run', side_effect=AssertionError('Review cannot enqueue'))
        self.enqueue = no_enqueue.start(); self.addCleanup(no_enqueue.stop)

    def install(self, assessment):
        path = self.root / 'assessment.json'
        raw = json.dumps(assessment).encode()
        path.write_bytes(raw)
        setting = override_settings(CORTI_OUTPUT_REVIEW_FILE=str(path),
                                    CORTI_OUTPUT_REVIEW_SHA256=hashlib.sha256(raw).hexdigest())
        setting.enable(); self.addCleanup(setting.disable)

    def review(self, actor=None):
        return output.view(self.encounter, self.run, actor or self.actor)

    def decide(self, outcome='accepted', confirmed=True, token=None, actor=None):
        actor = actor or self.actor
        token = token or self.review(actor)['display_token']
        return output.decide(self.encounter, self.run, actor, token, outcome, confirmed)

    def download(self, name='export_with_codes'):
        response = self.client.get(reverse(name, args=[self.encounter.pk]))
        self.assertEqual(response.status_code, 200)
        result = b''.join(response.streaming_content)
        # The test client's streaming wrapper closes its FileResponse itself.
        return result

    def assert_original_state(self):
        self.assertEqual(CodingDecision.objects.values().get(pk=self.base.pk), self.before_base)
        self.assertEqual(CodingContext.objects.values().get(encounter=self.encounter), self.before_context)
        self.assertEqual(CodingRun.objects.values().get(pk=self.run.pk), self.before_run)
        self.assertEqual(self.original_path.read_bytes(), self.original)
        self.assertEqual(CodingRun.objects.count(), 1)
        self.assertEqual(CodingDecision.objects.count(), 1)
        self.send.assert_not_called()
        self.enqueue.assert_not_called()

    def test_pending_review_never_exports_or_creates_a_decision(self):
        review = self.review()
        self.assertTrue(review['available'])
        self.assertEqual(review['state'], 'pending')
        self.assertTrue(review['can_decide'])
        self.assertEqual(review['selection_status'], 'supported')
        self.assertEqual(review['description_status'], output.DESCRIPTION_STATUS)
        self.assertEqual(len(review['evidence_spans']), 3)
        self.assertEqual(len(review['facts']), 8)
        for fact in review['facts']:
            self.assertEqual(self.encounter.notes[fact['start']:fact['end']], fact['quote'])
        self.assertEqual(CodingOutputDecision.objects.count(), 0)
        self.assertEqual([r['code'] for r in eligible_codes(self.encounter)[2]], ['R12'])
        saved = self.download()
        self.assertNotIn('99213', '\n'.join(texts(saved)))
        self.assertNotIn('K59.00', '\n'.join(texts(saved)))
        self.assertEqual(self.download('export'), self.original)
        self.assert_original_state()

    def test_explicit_confirmation_and_acceptance_export_exact_saved_code_and_evidence(self):
        for confirmation in (False, 'true', None):
            with self.subTest(confirmation=confirmation), self.assertRaises(ValidationError):
                self.decide(confirmed=confirmation)
        self.assertEqual(CodingOutputDecision.objects.count(), 0)
        decision = self.decide()
        self.assertTrue(decision.facts_confirmed)
        self.assertEqual(self.review()['state'], 'accepted')
        self.assertFalse(self.review()['can_decide'])
        rows = eligible_codes(self.encounter)[2]
        self.assertEqual([r['code'] for r in rows], ['R12', '99213'])
        self.assertEqual(rows[1]['description'], '')
        self.assertEqual(rows[1]['description_status'], output.DESCRIPTION_STATUS)
        downloaded = self.download()
        content = texts(downloaded)
        self.assertEqual(content.count('Diagnosis and procedure codes'), 1)
        self.assertIn('99213 — clinician-accepted code number', content)
        self.assertNotIn('K59.00', '\n'.join(content))
        self.assertNotIn('15 MINUTES', '\n'.join(content))
        for span in self.run.result['suggestions'][2]['evidence_spans']:
            self.assertIn('Original-note evidence: ' + span['text'], content)
        with ZipFile(BytesIO(self.original)) as old, ZipFile(BytesIO(downloaded)) as new:
            self.assertEqual(old.namelist(), new.namelist())
            for name in old.namelist():
                if name != 'word/document.xml':
                    self.assertEqual(old.read(name), new.read(name), name)
            before, after = old.read('word/document.xml'), new.read('word/document.xml')
            self.assertTrue(after.startswith(before[:before.rindex(b'<w:sectPr')]))
        self.assertEqual(self.download(), downloaded)
        self.assertEqual(self.download('export'), self.original)
        self.assert_original_state()

    def test_rejection_is_explicit_immutable_and_excluded(self):
        decision = self.decide('rejected', False)
        self.assertEqual(self.review()['state'], 'rejected')
        self.assertEqual(self.decide('rejected', False).pk, decision.pk)
        with self.assertRaises(ValidationError): self.decide('accepted', True)
        self.assertEqual([r['code'] for r in eligible_codes(self.encounter)[2]], ['R12'])
        self.assertNotIn('99213', '\n'.join(texts(self.download())))
        self.assertEqual(CodingOutputDecision.objects.count(), 1)
        self.assert_original_state()

    def test_accepted_decision_is_idempotent_and_database_append_only(self):
        first = self.decide()
        self.assertEqual(self.decide().pk, first.pk)
        with self.assertRaises(ValidationError): first.save()
        with self.assertRaises(ValidationError): first.delete()
        with self.assertRaises(DatabaseError), transaction.atomic():
            CodingOutputDecision.objects.filter(pk=first.pk).update(outcome='rejected')
        with self.assertRaises(DatabaseError), transaction.atomic():
            CodingOutputDecision.objects.filter(pk=first.pk).delete()
        self.assertEqual(CodingOutputDecision.objects.count(), 1)
        self.assert_original_state()

    def test_endpoint_requires_confirmation_and_same_clinician_token(self):
        url = reverse('coding_output_decision', args=[self.encounter.pk, self.run.pk])
        token = self.review()['display_token']
        data = {'output_display_token': token, 'outcome': 'accepted'}
        self.assertEqual(self.client.post(url, data, content_type='application/json').status_code, 409)
        self.assertEqual(CodingOutputDecision.objects.count(), 0)
        other = User.objects.create_user(username='other-output-reviewer', email='other-output@synthetic.invalid',
                                        verified_at=timezone.now())
        Membership.objects.create(user=other, department=self.department, role='clinician')
        self.client.force_login(other)
        data['confirm_note_facts'] = True
        self.assertEqual(self.client.post(url, data, content_type='application/json').status_code, 409)
        self.client.force_login(self.actor)
        self.assertEqual(self.client.post(url, data, content_type='application/json').status_code, 200)
        self.assertEqual(str(CodingOutputDecision.objects.get().user_id), str(self.actor.pk))
        self.assert_original_state()

    def test_missing_tampered_expired_and_changed_assessment_tokens_cannot_accept(self):
        token = self.review()['display_token']
        for bad in ('', 'not-a-signed-token', token + 'changed'):
            with self.subTest(token=bad[:20]), self.assertRaises(ValidationError):
                output.decide(self.encounter, self.run, self.actor, bad, 'accepted', True)
        with patch('core.coding_output.signing.loads', side_effect=signing.SignatureExpired('expired')):
            with self.assertRaises(ValidationError): self.decide(token=token)
        changed = deepcopy(self.assessment)
        changed['coverage']['cms_release_date'] = '2026-08-27'
        self.install(changed)
        with self.assertRaises(ValidationError): self.decide(token=token)
        self.assertEqual(CodingOutputDecision.objects.count(), 0)

    def test_stale_revision_refuses_approval_and_accepted_export(self):
        token = self.review()['display_token']
        self.decide(token=token)
        # Finalized rows are immutable in PostgreSQL. Present a changed copy at
        # the service boundary, without disabling that protection or rewriting it.
        changed = deepcopy(self.encounter)
        changed.revision += 1
        with patch('core.coding_output.service.locked_encounter', return_value=changed):
            with self.assertRaises(ValidationError): self.decide(token=token)
        self.assertFalse(output.view(changed, self.run, self.actor)['available'])
        with patch('core.coding_export.get_object_or_404', return_value=changed):
            response = self.client.get(reverse('export_with_codes', args=[self.encounter.pk]))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.original_path.read_bytes(), self.original)

    def test_cross_patient_and_unauthorized_accounts_cannot_use_review(self):
        patient = Patient.objects.create(department=self.department, display_name='Synthetic Other Output',
                                         reference='OTHER-OUTPUT', created_by=self.actor)
        encounter = Encounter.objects.create(department=self.department, patient=patient,
            template_version=self.encounter.template_version, created_by=self.actor,
            notes=self.encounter.notes, answers=self.encounter.answers, status='finalized',
            service_date=self.encounter.service_date, revision=2)
        with self.assertRaises(ValidationError): output.reviewed(encounter, self.run)
        url = reverse('coding_output_decision', args=[encounter.pk, self.run.pk])
        self.assertEqual(self.client.post(url, {'outcome': 'accepted'}).status_code, 404)
        member = Membership.objects.get(user=self.actor, department=self.department)
        member.role = 'employee'; member.save(update_fields=['role'])
        self.assertFalse(self.review()['can_decide'])
        url = reverse('coding_output_decision', args=[self.encounter.pk, self.run.pk])
        self.assertEqual(self.client.post(url, {'outcome': 'accepted'}).status_code, 403)
        member.active = False; member.save(update_fields=['active'])
        self.assertEqual(self.client.post(url, {'outcome': 'accepted'}).status_code, 404)
        self.assertEqual(CodingOutputDecision.objects.count(), 0)

    def test_unavailable_sources_date_permission_unknown_code_and_alternatives_remain_held(self):
        mutations = [
            lambda a: a['coverage'].pop('cms_release'),
            lambda a: a['coverage'].update(service_date='2026-10-17'),
            lambda a: a['sources'][0].update(evidence_sha256=''),
            lambda a: a['permission'].update(contradictory_restriction='Actual fixture restriction'),
            lambda a: a['permission'].update(record_sha256=''),
            lambda a: a['selection'].update(code='99999'),
            lambda a: a.update(identifier='candidate:0'),
            lambda a: a.update(identifier='selected:2:alternative:0'),
            lambda a: a['selection'].update(status='unsupported'),
            lambda a: a['facts'][0].update(quote='Unsupported invented fact'),
            lambda a: a['facts'][0].update(start=-1),
            lambda a: a['facts'].pop(),
        ]
        for number, mutation in enumerate(mutations):
            with self.subTest(mutation=number):
                changed = deepcopy(self.assessment); mutation(changed); self.install(changed)
                self.assertFalse(self.review()['available'])
                with self.assertRaises(ValidationError):
                    output.reviewed(self.encounter, self.run)
                self.assertEqual([r['code'] for r in eligible_codes(self.encounter)[2]], ['R12'])
        self.assertEqual(CodingOutputDecision.objects.count(), 0)
        self.assert_original_state()

    def test_missing_and_mismatched_provider_evidence_cannot_be_promoted(self):
        for evidence in ([], [{'status': 'valid', 'context_index': 0, 'start': 0, 'end': 5, 'text': 'wrong'}]):
            with self.subTest(evidence=evidence):
                run = deepcopy(self.run)
                run.result['suggestions'][2]['evidence_spans'] = evidence
                assessment = deepcopy(self.assessment)
                assessment['scope']['result_digest'] = service.digest(run.result)
                self.install(assessment)
                with self.assertRaises(ValidationError): output.reviewed(self.encounter, run)
        self.assertEqual(CodingOutputDecision.objects.count(), 0)

    def test_missing_corrupt_manifest_and_non_synthetic_scope_fail_closed(self):
        for settings in ({'SYNTHETIC_ONLY': False}, {'CORTI_OUTPUT_REVIEW_SHA256': '0' * 64},
                         {'CORTI_OUTPUT_REVIEW_FILE': '/missing-synthetic-assessment.json'}):
            with self.subTest(settings=settings), override_settings(**settings):
                self.assertFalse(self.review()['available'])
                with self.assertRaises(ValidationError): output.reviewed(self.encounter, self.run)
        self.assertEqual(CodingOutputDecision.objects.count(), 0)

    def test_accepted_cached_export_revalidates_permission_and_source(self):
        self.decide(); self.download()
        for field in ('permission', 'sources'):
            changed = deepcopy(self.assessment)
            if field == 'permission': changed[field]['contradictory_restriction'] = 'New actual restriction'
            else: changed[field][0]['evidence_sha256'] = ''
            self.install(changed)
            response = self.client.get(reverse('export_with_codes', args=[self.encounter.pk]))
            self.assertEqual(response.status_code, 409)
        self.assertEqual(self.original_path.read_bytes(), self.original)
        self.assertEqual(CodingOutputDecision.objects.count(), 1)
