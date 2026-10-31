"""Finding P1 on the actual upload and original-download paths (docs/rebuild/pypdf-6.21.4.md).

A stored PDF original is checked for active content in the isolated worker before its bytes are
served; a refusal serves nothing and is audited with its code. The download's type comes from the
stored format, never from the client's file name. Fixtures are built in memory (the pre-commit
hook forbids tracked PDFs); the payloads are app.alert('synthetic') only.
"""
from io import BytesIO, StringIO
import hashlib
import json
import os
from pathlib import Path
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from docx import Document

from core.models import AuditEvent, Department, Membership, Organization, Template, User
from core.security import private_path
from documents.test_pdf_active_content import form, p1_trigger, after_eof

from .test_workflow import TEST_SETTINGS

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def docx_bytes():
    document = Document()
    document.add_paragraph("Symptoms: {{Symptoms}}")
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@override_settings(**TEST_SETTINGS)
class OriginalDownloadSafety(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        override = override_settings(MEDIA_ROOT=Path(directory.name))
        override.enable()
        self.addCleanup(override.disable)
        self.user = User.objects.create_user(username="original-safety", email="original-safety@synthetic.invalid",
                                             verified_at=timezone.now())
        organization = Organization.objects.create(name="Synthetic original safety")
        self.department = Department.objects.create(organization=organization, name="Synthetic forms")
        Membership.objects.create(user=self.user, department=self.department, role="employee")
        self.client.force_login(self.user)

    def stored(self, data, kind="pdf", name=None):
        """A template row exactly as acceptance would have left it, with these original bytes."""
        relative = f"originals/{hashlib.sha256(data).hexdigest()[:16]}-{kind}.{kind}"
        path = private_path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return Template.objects.create(department=self.department, name="Synthetic form", format=kind,
                                       original_name=name or f"synthetic.{kind}", original_path=relative,
                                       sha256=hashlib.sha256(data).hexdigest(), created_by=self.user)

    def download(self, template):
        return self.client.get(f"/templates/{template.pk}/original/")

    def assert_refused(self, response, template, code):
        self.assertEqual(response.status_code, 409)
        self.assertFalse(getattr(response, "streaming", False))
        self.assertNotIn(b"%PDF", response.content)
        self.assertTrue(response["Content-Type"].startswith("text/plain"))
        refused = AuditEvent.objects.get(action="template.download_refused", target=str(template.pk))
        self.assertEqual(refused.details, {"code": code})
        self.assertEqual(refused.department, self.department)
        self.assertFalse(AuditEvent.objects.filter(action="template.download", target=str(template.pk)).exists())

    def test_a_pdf_original_with_a_hidden_script_is_not_served(self):
        # Accepted as a supported form by the base code (4ebba7732) on pypdf 6.21.1, 6.21.2 and 6.21.4.
        template = self.stored(p1_trigger("type"))
        response = self.download(template)
        self.assert_refused(response, template, "unsafe_upload")
        self.assertIn(b"PDF actions, attachments, XFA, and external resources are not accepted.", response.content)

    def test_a_pdf_original_with_a_script_after_eof_is_not_served(self):
        template = self.stored(after_eof())
        self.assert_refused(self.download(template), template, "unsafe_upload")

    def test_a_pdf_original_pypdf_cannot_read_completely_is_not_served(self):
        template = self.stored(p1_trigger("type", payload=False))
        response = self.download(template)
        self.assert_refused(response, template, "unreadable_pdf")
        self.assertIn(b"could not be read completely", response.content)

    def test_opaque_bytes_recorded_as_a_pdf_are_not_served(self):
        template = self.stored(b"synthetic bytes that are not a PDF")
        self.assert_refused(self.download(template), template, "unsupported_format")

    def test_a_clean_pdf_is_served_as_pdf_attachment_with_nosniff(self):
        data = form()
        template = self.stored(data)
        response = self.download(template)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), data)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response["Content-Disposition"].startswith("attachment;"))
        self.assertIn('filename="synthetic.pdf"', response["Content-Disposition"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(AuditEvent.objects.filter(action="template.download", target=str(template.pk)).count(), 1)
        self.assertFalse(AuditEvent.objects.filter(action="template.download_refused").exists())

    def test_the_type_comes_from_the_stored_format_not_the_client_name(self):
        # The stored name is cut to 200 characters after its suffix was checked, so it can end in anything.
        template = self.stored(form(), name="synthetic-form.html")
        response = self.download(template)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn('filename="synthetic-form.html.pdf"', response["Content-Disposition"])

    def test_a_docx_original_is_served_with_its_type_and_not_reinspected(self):
        data = docx_bytes()
        template = self.stored(data, "docx", name="synthetic.DOCX")
        response = self.download(template)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), data)
        self.assertEqual(response["Content-Type"], DOCX_TYPE)
        self.assertTrue(response["Content-Disposition"].startswith("attachment;"))
        self.assertIn('filename="synthetic.DOCX"', response["Content-Disposition"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_a_changed_original_is_still_refused_before_any_check(self):
        template = self.stored(form())
        private_path(template.original_path).write_bytes(b"%PDF-1.7 changed")
        response = self.download(template)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(AuditEvent.objects.filter(target=str(template.pk)).exists())


@override_settings(**TEST_SETTINGS)
class UploadRefusesHiddenContent(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        override = override_settings(MEDIA_ROOT=Path(directory.name))
        override.enable()
        self.addCleanup(override.disable)
        self.originals = Path(directory.name) / "originals"
        self.user = User.objects.create_user(username="upload-safety", email="upload-safety@synthetic.invalid",
                                             verified_at=timezone.now())
        organization = Organization.objects.create(name="Synthetic upload safety")
        self.department = Department.objects.create(organization=organization, name="Synthetic uploads")
        Membership.objects.create(user=self.user, department=self.department, role="clinician")
        self.client.force_login(self.user)

    def upload(self, data):
        return self.client.post("/templates/upload/", {"name": "Synthetic form", "department": self.department.pk,
                                                       "synthetic_only": "on",
                                                       "file": SimpleUploadedFile("synthetic.pdf", data)})

    def test_a_hidden_script_is_refused_with_the_action_hint_and_leaves_nothing(self):
        response = self.upload(p1_trigger("nosize"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PDF actions, attachments, XFA, and external resources are not accepted.")
        self.assertContains(response, "Remove every link, attachment, document open action")
        self.assertFalse(Template.objects.exists())
        self.assertEqual(list(self.originals.glob("*")), [])

    def test_unreadable_structure_is_refused_with_its_own_message(self):
        response = self.upload(p1_trigger("indexover", payload=False))
        self.assertContains(response, "This PDF could not be read completely, so it cannot be checked for active "
                                      "content. Save it as a new PDF and upload it again.")
        self.assertFalse(Template.objects.exists())
        self.assertEqual(list(self.originals.glob("*")), [])

    def test_the_upload_page_still_says_active_content_is_refused(self):
        page = self.client.get("/templates/upload/")
        self.assertContains(page, "PDFs with links, attachments or actions, and PDFs that cannot be read completely, "
                                  "are refused.")
        self.assertContains(page, "macros and active content are refused")

    def test_an_ordinary_form_is_still_accepted(self):
        self.assertEqual(self.upload(form()).status_code, 302)
        self.assertEqual(Template.objects.get().format, "pdf")


@override_settings(**TEST_SETTINGS)
class CheckStoredOriginalsCommand(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        override = override_settings(MEDIA_ROOT=self.root / "media")
        override.enable()
        self.addCleanup(override.disable)
        self.user = User.objects.create_user(username="command-safety", email="command-safety@synthetic.invalid",
                                             verified_at=timezone.now())
        organization = Organization.objects.create(name="Synthetic command")
        self.department = Department.objects.create(organization=organization, name="Synthetic stored")

    def stored(self, data, kind="pdf", write=True):
        relative = f"originals/{hashlib.sha256(data).hexdigest()[:16]}.{kind}"
        if write:
            path = private_path(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return Template.objects.create(department=self.department, name="Synthetic stored", format=kind,
                                       original_name="synthetic-name-never-reported.pdf", original_path=relative,
                                       sha256=hashlib.sha256(data).hexdigest(), created_by=self.user)

    def test_counts_and_codes_without_contents_names_or_writes(self):
        clean = self.stored(form())
        hidden = self.stored(p1_trigger("widew"))
        unreadable = self.stored(p1_trigger("type", payload=False))
        missing = self.stored(b"%PDF-1.7 synthetic never written", write=False)
        self.stored(docx_bytes(), "docx")                      # DOCX originals are not this command's
        audit_rows, templates = AuditEvent.objects.count(), Template.objects.count()
        output = self.root / "report.json"
        call_command("check_pdf_originals", output=str(output), stdout=StringIO())
        report = json.loads(output.read_text())
        self.assertEqual(report["pdf_originals"], 4)
        self.assertEqual(report["served"], 1)
        self.assertEqual(report["refused"], 3)
        self.assertEqual(report["counts"], {"ok": 1, "source_unavailable": 1, "unreadable_pdf": 1, "unsafe_upload": 1})
        self.assertEqual({row["template_id"]: row["code"] for row in report["templates"]},
                         {str(clean.pk): "ok", str(hidden.pk): "unsafe_upload", str(unreadable.pk): "unreadable_pdf",
                          str(missing.pk): "source_unavailable"})
        text = output.read_text()
        self.assertNotIn("synthetic-name-never-reported", text)
        self.assertNotIn("originals/", text)
        self.assertEqual(oct(os.stat(output).st_mode & 0o777), "0o600")
        self.assertEqual((AuditEvent.objects.count(), Template.objects.count()), (audit_rows, templates))
        with self.assertRaises(CommandError):
            call_command("check_pdf_originals", output=str(output), stdout=StringIO())
