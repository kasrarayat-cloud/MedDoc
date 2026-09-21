"""Isolated authenticated original-form workflow; manual review creates no jobs."""

import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
from zipfile import ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from docx import Document

from core.billing import welcome_credit
from core.models import AuditEvent, Department, Encounter, Job, LedgerEntry, Membership, Organization, Patient, Template, Usage, User
from core.security import private_path
from documents.test_tab_form import ORIGINAL, SOURCE_SHA256
from .test_workflow import TEST_SETTINGS


@override_settings(**TEST_SETTINGS)
class TabFormWorkflowTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="quillmd-tab-http-")
        self.addCleanup(self.directory.cleanup)
        self.override = override_settings(MEDIA_ROOT=Path(self.directory.name) / "private")
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.user = User.objects.create_user(username="tab-alpha", email="tab-alpha@synthetic.invalid",
                                             first_name="Synthetic", last_name="Alpha Clinician",
                                             verified_at=timezone.now())
        self.other = User.objects.create_user(username="tab-beta", email="tab-beta@synthetic.invalid",
                                              first_name="Synthetic", last_name="Beta Clinician",
                                              verified_at=timezone.now())
        organization = Organization.objects.create(name="Synthetic tab-form practice")
        self.department = Department.objects.create(organization=organization, name="Synthetic endoscopy")
        for clinician in (self.user, self.other):
            Membership.objects.create(user=clinician, department=self.department, role="clinician")
        welcome_credit(self.user)
        self.ledger_before = LedgerEntry.objects.count()
        self.client.force_login(self.user)
        self.patient = Patient.objects.create(department=self.department, display_name="SYNTHETIC TAB PATIENT",
                                               reference="SYNTHETIC-TAB", created_by=self.user)
        self.original = ORIGINAL.read_bytes()
        self.assertEqual(hashlib.sha256(self.original).hexdigest(), SOURCE_SHA256)
        response = self.client.post("/templates/upload/", {"name": "Synthetic original colonoscopy form",
            "department": self.department.pk, "synthetic_only": "on",
            "file": SimpleUploadedFile("Colonoscopy_Operative_Template.docx", self.original)})
        self.assertEqual(response.status_code, 302, getattr(response, "context", None))
        self.template = Template.objects.get(name="Synthetic original colonoscopy form")
        self.version = self.template.versions.get(number=1)
        self.assertEqual(len(self.version.fields), 24)
        self.signature_key = next(f["key"] for f in self.version.fields if f.get("answer_policy") == "clinician_identity")

    def encounter(self, version=None):
        version = version or self.version
        response = self.client.post("/encounters/new/", {"patient": self.patient.pk,
            "template_version": version.pk, "notes": "PATIENT NAME: SYNTHETIC TAB PATIENT",
            "service_date": timezone.localdate().isoformat(), "synthetic_only": "on"})
        self.assertEqual(response.status_code, 302)
        return Encounter.objects.get(template_version=version)

    def save(self, encounter, signature):
        values = {field["key"]: f"Synthetic documented answer {index:02d}"
                  for index, field in enumerate(encounter.template_version.fields)}
        values[self.signature_key] = signature
        payload = {"revision": encounter.revision}
        for key, value in values.items():
            payload["answer_" + key] = value
            payload["reviewed_" + key] = "on"
        response = self.client.post(f"/encounters/{encounter.pk}/save/", payload)
        self.assertEqual(response.status_code, 302)
        encounter.refresh_from_db()
        self.assertTrue(all(answer["reviewed"] for answer in encounter.answers.values()))
        return values

    def finish(self, encounter):
        response = self.client.post(f"/encounters/{encounter.pk}/finalize/",
                                   {"revision": encounter.revision, "reviewed": "on"}, follow=True)
        self.assertEqual(response.status_code, 200)
        encounter.refresh_from_db()
        return response

    def assert_no_billable_work(self):
        self.assertEqual(Job.objects.count(), 0)
        self.assertEqual(Usage.objects.count(), 0)
        self.assertEqual(LedgerEntry.objects.count(), self.ledger_before)

    def test_mapping_manual_review_and_authenticated_original_format_download(self):
        mapping = self.client.get(f"/templates/{self.template.pk}/")
        self.assertContains(mapping, "Confirm that these consecutive answer lines belong to one question.")
        original_fields = self.version.fields
        labels = {field["key"]: field["label"] for field in original_fields}
        labels[original_fields[0]["key"]] = "Patient display name"
        response = self.client.post(f"/templates/{self.template.pk}/",
                                   {"mapping_version": self.version.pk, "labels": json.dumps(labels)})
        self.assertEqual(response.status_code, 302)
        revised = self.template.versions.get(number=2)
        self.version.refresh_from_db()
        self.assertEqual(self.version.fields, original_fields)
        self.assertEqual(revised.fields[0]["locator"], original_fields[0]["locator"])
        encounter = self.encounter(revised)
        page = self.client.get(f"/encounters/{encounter.pk}/")
        self.assertContains(page, "enter and review the documented answers below")
        for field in revised.fields:
            self.assertContains(page, f'name="answer_{field["key"]}"', count=1)
        self.assertEqual(encounter.answers, {})
        values = self.save(encounter, self.user.get_full_name())
        self.finish(encounter)
        self.assertEqual(encounter.status, "finalized")
        self.assertEqual(encounter.finalized_by_id, self.user.pk)
        response = self.client.get(f"/encounters/{encounter.pk}/export/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        output = b"".join(response.streaming_content)
        self.assertEqual(hashlib.sha256(output).hexdigest(), encounter.export_sha256)
        document = Document(BytesIO(output))
        self.assertEqual(len(document.paragraphs), 31)
        text = "\n".join(p.text for p in document.paragraphs)
        self.assertIn("PATIENT NAME:", text)
        self.assertNotIn("Patient display name", text)
        for value in values.values():
            self.assertEqual(text.count(value), 1)
        with ZipFile(BytesIO(self.original)) as original, ZipFile(BytesIO(output)) as export:
            self.assertEqual(original.namelist(), export.namelist())
            for name in original.namelist():
                if name != "word/document.xml":
                    self.assertEqual(original.read(name), export.read(name), name)
        self.assertEqual(private_path(self.template.original_path).read_bytes(), self.original)
        original_download = self.client.get(f"/templates/{self.template.pk}/original/")
        self.assertEqual(b"".join(original_download.streaming_content), self.original)
        self.assertEqual(AuditEvent.objects.filter(action="encounter.finalize", target=str(encounter.pk)).count(), 1)
        self.assert_no_billable_work()

    def test_other_person_signature_is_refused_before_export(self):
        encounter = self.encounter()
        self.save(encounter, self.other.get_full_name())
        response = self.finish(encounter)
        self.assertContains(response, "signature must match your signed-in clinician name")
        self.assertEqual(encounter.status, "review")
        self.assertFalse(encounter.export_path)
        self.assertFalse(AuditEvent.objects.filter(action="encounter.finalize", target=str(encounter.pk)).exists())
        self.assert_no_billable_work()

    def test_named_finalizer_cannot_inherit_another_clinicians_signature_review(self):
        encounter = self.encounter()
        self.save(encounter, self.other.get_full_name())
        self.assertEqual(encounter.answers[self.signature_key]["reviewed_by"], str(self.user.pk))
        self.client.force_login(self.other)
        self.finish(encounter)
        self.assertEqual(encounter.status, "review")
        self.assertFalse(encounter.export_path)
        self.assertFalse(AuditEvent.objects.filter(action="encounter.finalize", target=str(encounter.pk)).exists())
        # Explicit review by the named finalizer repairs the refusal without new generation.
        self.save(encounter, self.other.get_full_name())
        self.finish(encounter)
        self.assertEqual(encounter.status, "finalized")
        self.assertEqual(encounter.finalized_by_id, self.other.pk)
        self.assert_no_billable_work()

    def test_explicit_blank_signature_can_finalize_and_remains_blank(self):
        encounter = self.encounter()
        self.save(encounter, "")
        self.finish(encounter)
        self.assertEqual(encounter.status, "finalized")
        response = self.client.get(f"/encounters/{encounter.pk}/export/")
        document = Document(BytesIO(b"".join(response.streaming_content)))
        self.assertEqual(document.paragraphs[29].text, "Electronically signed by: \t")
        self.assert_no_billable_work()
