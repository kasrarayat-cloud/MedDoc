"""Focused synthetic regressions from the internal private-beta review.

No email transport, provider request, or live-application mutation is used.
"""
from datetime import timedelta
import json

from django.test import TestCase, override_settings
from django.utils import timezone

from core.billing import welcome_credit
from core.models import Invitation, LedgerEntry, Membership, User
from core.security import digest, token
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
        self.client.force_login(self.user)

    def test_stale_mapping_cannot_silently_replace_newer_labels(self):
        version = self.template.versions.get(number=1)
        url = f"/templates/{self.template.pk}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        first = self.client.post(url, {
            "mapping_version": str(version.pk),
            "labels": json.dumps({"symptoms": "Current clinically reviewed symptoms"}),
        })
        self.assertEqual(first.status_code, 302)
        self.assertEqual(self.template.versions.count(), 2)
        stale = self.client.post(url, {
            "mapping_version": str(version.pk),
            "labels": json.dumps({"symptoms": "Stale tab symptoms"}),
        })
        self.assertEqual(stale.status_code, 409)
        self.assertContains(stale, "Your unsaved labels are retained", status_code=409)
        self.assertContains(stale, "Stale tab symptoms", status_code=409)
        self.assertEqual(self.template.versions.count(), 2)
        self.assertEqual(self.template.versions.latest("number").fields[0]["label"], "Current clinically reviewed symptoms")

    def test_missing_mapping_version_cannot_bypass_stale_edit_guard(self):
        response = self.client.post(f"/templates/{self.template.pk}/", {
            "labels": json.dumps({"symptoms": "Unbound symptoms"}),
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.template.versions.count(), 1)

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
        self.encounter.answers = {"symptoms": {"text": '<img src=x onerror="alert(2)">', "status": "edited", "evidence": [], "reviewed": False}}
        self.encounter.save(update_fields=["notes", "answers"])
        response = self.client.get(f"/encounters/{self.encounter.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<script id="source-injection">')
        self.assertNotContains(response, '<img src=x onerror=')
        self.assertContains(response, '&lt;script id=&quot;source-injection&quot;&gt;')
        self.assertContains(response, '&lt;img src=x onerror=&quot;alert(2)&quot;&gt;')
