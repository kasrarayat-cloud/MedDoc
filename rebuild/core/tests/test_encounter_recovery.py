"""Mounted note-only recovery; old clinical and financial history stays on its original version."""
import copy
import hashlib
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import path
from django.utils import timezone

from core import encounter_recovery as recovery
from core.models import (AuditEvent, Encounter, Job, MappingConfirmation, Reservation,
    Template, TemplateVersion, TranscriptReview)
from core.security import private_path
from quillmd.urls_doctor import urlpatterns as doctor_patterns
from .test_template_reinspection import OLD_PROCESSOR, SETTINGS
from .test_word_v3_workflow import V3Fixture, build_legacy_table_form

# The new companion route is mounted with the normal doctor URL set. The lead
# integrates this same one-line mount into quillmd/urls.py before candidate QA.
urlpatterns = [*doctor_patterns, path('encounters/<uuid:pk>/recover/', recovery.page, name='encounter_recovery')]


@override_settings(**SETTINGS, ROOT_URLCONF=__name__)
class EncounterRecovery(V3Fixture, TestCase):
    def setUp(self):
        super().setUp()
        self.doctor_routes = patch('core.middleware.DOCTOR_URLCONF', __name__)
        self.doctor_routes.start(); self.addCleanup(self.doctor_routes.stop)

    def saved_source(self):
        with patch('documents.service.engine_fingerprint', return_value=OLD_PROCESSOR):
            template, version = self.uploaded(data=build_legacy_table_form(), name='Synthetic recovery source')
        # This represents the already-confirmed mapping on which the prior
        # release created a draft, not confirmation through today's stale gate.
        MappingConfirmation.objects.create(version=version, confirmed_by=self.user)
        old = Encounter.objects.create(department=self.department, patient=self.patient,
            template_version=version, created_by=self.user, service_date=timezone.localdate(),
            notes='Allergies: None documented\nPlan: Rest.', status='review', revision=3,
            answers={self.by_label(version)['Plan']['key']:
                {'text': 'Earlier clinician answer', 'status': 'manual', 'reviewed': True}})
        return template, version, old

    def fresh_target(self, template, version, *, confirm=True):
        response = self.client.post(f'/templates/{template.pk}/', {'action': 'reinspect_original',
            'mapping_version': version.pk, 'review_reinspection': 'on'})
        self.assertEqual(response.status_code, 302, response.content.decode())
        target = Template.objects.get(pk=response.url.rstrip('/').split('/')[-1])
        mapping = target.versions.get(number=1)
        return target, self.confirm(target, mapping) if confirm else mapping

    def post(self, old, mapping, **extra):
        return self.client.post(f'/encounters/{old.pk}/recover/', {'revision': old.revision,
            'mapping_version': mapping.pk, 'review_recovery': 'on', **extra})

    def test_note_only_recovery_is_mounted_preserves_old_work_and_has_no_provider_side_effects(self):
        template, version, old = self.saved_source()
        target, mapping = self.fresh_target(template, version)
        before = copy.deepcopy(old.__dict__); original = private_path(template.original_path).read_bytes()
        manifest, fields = copy.deepcopy(version.import_manifest), copy.deepcopy(version.fields)
        old_page = self.client.get(f'/encounters/{old.pk}/')
        self.assertContains(old_page, f'/encounters/{old.pk}/recover/')
        self.assertContains(old_page, old.notes, html=False)
        response = self.client.get(f'/encounters/{old.pk}/recover/')
        self.assertContains(response, old.notes, html=False)
        self.assertContains(response, 'signed transcript context are not copied')
        response = self.post(old, mapping)
        self.assertEqual(response.status_code, 302, response.content.decode())
        new = Encounter.objects.get(pk=response.url.rstrip('/').split('/')[-1])
        self.assertEqual((new.patient_id, new.service_date, new.notes, new.template_version_id),
                         (old.patient_id, old.service_date, old.notes, mapping.pk))
        self.assertEqual((new.answers, new.template_review, new.revision, new.status), ({}, {}, 0, 'draft'))
        new_page = self.client.get(f'/encounters/{new.pk}/')
        self.assertContains(new_page, 'data-source-recovery')
        self.assertContains(new_page, f'/encounters/{old.pk}/')
        self.assertContains(new_page, old.notes, html=False)
        self.assertContains(new_page, 'Earlier answers, code acceptances and reviewed transcript context were not copied')
        self.assertContains(new_page, 'before generating')
        old.refresh_from_db(); version.refresh_from_db()
        for attr in ('notes', 'answers', 'template_review', 'revision', 'status', 'template_version_id'):
            self.assertEqual(getattr(old, attr), before[attr])
        self.assertEqual(version.import_manifest, manifest); self.assertEqual(version.fields, fields)
        self.assertEqual(private_path(template.original_path).read_bytes(), original)
        self.assertEqual(private_path(target.original_path).read_bytes(), original)
        self.assertFalse(Job.objects.exists()); self.assertFalse(Reservation.objects.exists())
        self.assertFalse(TranscriptReview.objects.filter(encounter=new).exists())
        event = AuditEvent.objects.get(action=recovery.ACTION)
        self.assertEqual(event.target, str(new.pk)); self.assertEqual(event.details['source_id'], str(old.pk))
        self.assertEqual(event.details['source_revision'], 3)
        self.assertEqual(event.details['source_sha256'], hashlib.sha256(old.notes.encode()).hexdigest())
        self.assertFalse(event.details['answers_copied']); self.assertFalse(event.details['transcript_context_copied'])
        self.assertNotIn(old.notes, str(event.details))

    def test_retry_reopens_same_new_draft_without_overwriting_later_work(self):
        template, version, old = self.saved_source(); _, mapping = self.fresh_target(template, version)
        first = self.post(old, mapping); new = Encounter.objects.get(pk=first.url.rstrip('/').split('/')[-1])
        self.client.post(f'/encounters/{new.pk}/notes/', {'revision': new.revision,
            'notes': 'Allergies: None documented\nPlan: New reviewed notes.'})
        new.refresh_from_db(); notes, revision = new.notes, new.revision
        second = self.post(old, mapping)
        self.assertEqual(second.status_code, 302); self.assertEqual(second.url, first.url)
        new.refresh_from_db(); self.assertEqual((new.notes, new.revision), (notes, revision))
        self.assertEqual(Encounter.objects.count(), 2); self.assertEqual(AuditEvent.objects.filter(action=recovery.ACTION).count(), 1)
        self.assertFalse(Job.objects.exists()); self.assertFalse(Reservation.objects.exists())

    def test_roles_department_and_admin_host_are_denied_before_source_is_rendered(self):
        template, version, old = self.saved_source(); _, mapping = self.fresh_target(template, version)
        for user in (self.manager, self.employee):
            self.client.force_login(user)
            response = self.client.get(f'/encounters/{old.pk}/recover/')
            self.assertEqual(response.status_code, 403); self.assertNotIn(old.notes.encode(), response.content)
            self.assertEqual(self.post(old, mapping).status_code, 403)
        from core.models import Department, Membership, User
        foreign = User.objects.create_user(username='recovery-foreign', email='recovery-foreign@synthetic.invalid', verified_at=timezone.now())
        department = Department.objects.create(organization=self.department.organization, name='Other recovery department')
        Membership.objects.create(user=foreign, department=department, role='clinician')
        self.client.force_login(foreign); response = self.client.get(f'/encounters/{old.pk}/recover/')
        self.assertEqual(response.status_code, 404); self.assertNotIn(old.notes.encode(), response.content)
        self.client.force_login(self.user)
        self.user.is_staff=True; self.user.save(update_fields=['is_staff'])
        # OTPMiddleware attaches is_verified to this request's user instance.
        # Use its normal confirmed-device/session contract, not a nonexistent
        # method patched onto the User model class.
        from django_otp import DEVICE_ID_SESSION_KEY
        from django_otp.plugins.otp_totp.models import TOTPDevice
        device = TOTPDevice.objects.create(user=self.user, name='Synthetic recovery admin', confirmed=True)
        session = self.client.session
        session[DEVICE_ID_SESSION_KEY] = device.persistent_id
        session.save()
        with override_settings(ADMIN_SITE=True, ROOT_URLCONF='quillmd.urls'):
            self.assertEqual(self.client.get('/console/').status_code, 200, 'Authorized verified administrator is a positive control')
            self.assertEqual(self.client.get(f'/encounters/{old.pk}/recover/').status_code, 404)
        self.assertEqual(Encounter.objects.count(), 1); self.assertFalse(AuditEvent.objects.filter(action=recovery.ACTION).exists())

    def test_acknowledgement_revision_and_current_confirmed_linked_map_are_required(self):
        template, version, old = self.saved_source(); target, mapping = self.fresh_target(template, version, confirm=False)
        self.assertEqual(self.post(old, mapping).status_code, 400)
        mapping = self.confirm(target, mapping)
        self.assertEqual(self.post(old, mapping, review_recovery='').status_code, 400)
        self.assertEqual(self.post(old, mapping, revision=old.revision-1).status_code, 400)
        other, unrelated = self.uploaded(data=build_legacy_table_form(), name='Unrelated same-byte form')
        unrelated = self.confirm(other, unrelated)
        self.assertEqual(self.post(old, unrelated).status_code, 400)
        newer = TemplateVersion.objects.create(template=target, number=2, fields=mapping.fields,
            contract=mapping.contract, import_manifest=mapping.import_manifest, created_by=self.user)
        self.assertEqual(self.post(old, mapping).status_code, 400)
        self.assertEqual(Encounter.objects.count(), 1); self.assertFalse(AuditEvent.objects.filter(action=recovery.ACTION).exists())

    def test_pending_unknown_and_finalized_source_are_not_duplicated(self):
        template, version, old = self.saved_source(); _, mapping = self.fresh_target(template, version)
        for n, state in enumerate(('queued', 'running', 'staged', 'reconciliation', 'unrecognized')):
            candidate = Encounter.objects.create(department=self.department, patient=self.patient,
                template_version=version, created_by=self.user, service_date=old.service_date, notes=old.notes)
            Job.objects.create(encounter=candidate, user=self.user, state=state, request_key=f'recovery-{n}')
            self.assertEqual(self.post(candidate, mapping).status_code, 400)
        self.assertEqual(Encounter.objects.count(), 6)
        # Test the finalized gate without fabricating a finalized DB medical record.
        candidate = copy.copy(old); candidate.status='finalized'
        with self.assertRaises(ValidationError): recovery.require_source(candidate, self.user)
        self.assertFalse(AuditEvent.objects.filter(action=recovery.ACTION).exists()); self.assertFalse(Reservation.objects.exists())

    def test_current_original_and_physical_admission_refusal_leave_old_history_intact(self):
        template, version, old = self.saved_source(); target, mapping = self.fresh_target(template, version)
        notes, answers = old.notes, copy.deepcopy(old.answers)
        with patch('core.encounter_recovery.import_binding.verify_review_places', side_effect=ValidationError('Source-bound destination refused')):
            response = self.post(old, mapping)
            self.assertEqual(response.status_code, 400); self.assertContains(response, 'Source-bound destination refused', status_code=400)
        path = private_path(target.original_path); path.write_bytes(path.read_bytes()+b'changed')
        self.assertEqual(self.post(old, mapping).status_code, 400)
        old.refresh_from_db(); self.assertEqual((old.notes, old.answers), (notes, answers))
        self.assertEqual(Encounter.objects.count(), 1); self.assertFalse(AuditEvent.objects.filter(action=recovery.ACTION).exists())
        self.assertFalse(Job.objects.exists()); self.assertFalse(Reservation.objects.exists())
