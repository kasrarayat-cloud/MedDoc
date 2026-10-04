"""Focused synthetic regressions from the internal private-beta review.

No email transport, provider request, or live-application mutation is used.
"""
from datetime import timedelta
import json

from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from core.billing import welcome_credit
from core.models import Invitation, LedgerEntry, Membership, Template, User
from core.security import digest, private_path, token
from core.tests.test_security import SyntheticFixture


@override_settings(
    AI_MODE="fixture", ADMIN_SITE=False,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class InternalAccessReview(SyntheticFixture, TestCase):
    def setUp(self):
        self.user, self.org, self.department, self.patient, self.template, self.encounter, _ = self.make_scope("internal-review")
        self.key = self.encounter.template_version.fields[0]['key']
        self.client.force_login(self.user)

    def test_stale_mapping_cannot_silently_replace_newer_labels(self):
        version = self.template.versions.get(number=1)
        url = f"/templates/{self.template.pk}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        first = self.client.post(url, {
            "mapping_version": str(version.pk),
            "labels": json.dumps({self.key: "Current clinically reviewed symptoms"}),
        })
        self.assertEqual(first.status_code, 302)
        self.assertEqual(self.template.versions.count(), 2)
        stale = self.client.post(url, {
            "mapping_version": str(version.pk),
            "labels": json.dumps({self.key: "Stale tab symptoms"}),
        })
        self.assertEqual(stale.status_code, 409)
        self.assertContains(stale, "Your unsaved labels are retained", status_code=409)
        self.assertContains(stale, "Stale tab symptoms", status_code=409)
        self.assertEqual(self.template.versions.count(), 2)
        self.assertEqual(self.template.versions.latest("number").fields[0]["label"], "Current clinically reviewed symptoms")

    def test_missing_mapping_version_cannot_bypass_stale_edit_guard(self):
        response = self.client.post(f"/templates/{self.template.pk}/", {
            "labels": json.dumps({self.key: "Unbound symptoms"}),
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.template.versions.count(), 1)

    @override_settings(QUILLMD_WORD_ENGINE='v3')
    def test_current_v3_label_corrections_bind_the_version_and_preserve_originals(self):
        """The mounted current route has usable corrections and stale/missing-version refusals."""
        original = private_path(self.template.original_path).read_bytes()
        response = self.client.post('/templates/upload/', {'department': self.department.pk,
            'name': 'Synthetic current-v3 review', 'synthetic_only': 'on',
            'file': SimpleUploadedFile('current-v3.docx', original)})
        self.assertEqual(response.status_code, 302, response.content.decode())
        template = Template.objects.get(name='Synthetic current-v3 review')
        first = template.versions.get(number=1)
        self.assertEqual(first.contract, 'v3')
        self.assertEqual(first.import_manifest['source_sha256'], template.sha256)
        key = first.fields[0]['key']
        url = f'/templates/{template.pk}/'
        saved = self.client.post(url, {'action': 'v3_save', 'mapping_version': first.pk,
            'label_' + key: 'Current clinically reviewed symptoms'})
        self.assertEqual(saved.status_code, 302, saved.content.decode())
        self.assertEqual(template.versions.count(), 2)
        current = template.versions.latest('number')
        self.assertEqual(current.fields[0]['label'], 'Current clinically reviewed symptoms')
        self.assertEqual(current.fields[0]['locator'], first.fields[0]['locator'])
        for version_id in (str(first.pk), ''):
            with self.subTest(mapping_version=version_id):
                refused = self.client.post(url, {'action': 'v3_save', 'mapping_version': version_id,
                    'label_' + key: 'Stale tab symptoms'})
                self.assertEqual(refused.status_code, 409)
                self.assertContains(refused, 'Stale tab symptoms', status_code=409)
                self.assertEqual(template.versions.count(), 2)
                self.assertEqual(template.versions.latest('number').fields, current.fields)
        self.assertEqual(template.versions.get(pk=first.pk).fields, first.fields)
        self.assertEqual(private_path(template.original_path).read_bytes(), original)

    def test_inactive_membership_invitation_does_not_claim_success_or_consume_token(self):
        Membership.objects.filter(user=self.user, department=self.department).update(role="owner")
        employee = User.objects.create_user(
            username="inactive-invite", email="inactive-invite@synthetic.invalid", verified_at=timezone.now(),
        )
        member = Membership.objects.create(user=employee, department=self.department, role="employee", active=False)
        welcome_credit(employee)
        raw = token()
        invitation = Invitation.objects.create(
            email=employee.email, department=self.department, role="employee", token_hash=digest(raw),
            expires_at=timezone.now() + timedelta(days=1), invited_by=self.user,
        )
        self.client.force_login(employee)
        response = self.client.post(f"/invite/{raw}/")
        self.assertEqual(response.status_code, 409)
        member.refresh_from_db()
        invitation.refresh_from_db()
        self.assertFalse(member.active)
        self.assertIsNone(invitation.accepted_at)
        self.assertEqual(LedgerEntry.objects.filter(wallet__user=employee, kind="welcome").count(), 1)
        self.assertEqual(self.client.get(f"/api/encounters/{self.encounter.pk}/").status_code, 404)

    def test_stale_source_edit_refused_and_current_draft_preserved(self):
        original_revision = self.encounter.revision
        url = f"/encounters/{self.encounter.pk}/notes/"
        response = self.client.post(url, {"revision": original_revision, "notes": "Symptoms: current reviewed source"})
        self.assertEqual(response.status_code, 302)
        response = self.client.post(url, {"revision": original_revision, "notes": "Symptoms: stale overwritten source"})
        self.assertEqual(response.status_code, 409)
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.notes, "Symptoms: current reviewed source")
        self.assertEqual(self.encounter.revision, original_revision + 1)

    def test_source_and_answer_html_are_escaped(self):
        self.encounter.notes = '<script id="source-injection">alert(1)</script>'
        self.encounter.answers = {self.key: {"text": '<img src=x onerror="alert(2)">', "status": "edited", "evidence": [], "reviewed": False}}
        self.encounter.save(update_fields=["notes", "answers"])
        response = self.client.get(f"/encounters/{self.encounter.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<script id="source-injection">')
        self.assertNotContains(response, '<img src=x onerror=')
        self.assertContains(response, '&lt;script id=&quot;source-injection&quot;&gt;')
        self.assertContains(response, '&lt;img src=x onerror=&quot;alert(2)&quot;&gt;')
