"""Finding P1 on the actual upload and original-download paths (docs/rebuild/pypdf-6.21.4.md).

A stored PDF original is checked for active content in the isolated worker before its bytes are
served; a refusal serves nothing and is audited with its code. The download's type comes from the
stored format, never from the client's file name. Fixtures are built in memory (the pre-commit
hook forbids tracked PDFs); the payloads are app.alert('synthetic') only.

Round 3 (2026-11-01): a stored PDF export is served after its TEMPLATE ORIGINAL passes that check,
and the export itself is not scanned (SI-1, SI-2); a refused form buys no coding run either (SI-3);
and a check that could not run says "try again" and keeps the doctor's recording (SI-4).
"""
from contextlib import contextmanager
import copy
from datetime import date, timedelta
from io import BytesIO, StringIO
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.contrib.messages import get_messages
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from docx import Document

from core.billing import welcome_credit
from core.jobs import enqueue, reap_abandoned_voice_uploads, run_one
from core.models import (AuditEvent, Department, Encounter, Job, Membership, Organization, Patient, Template,
                         TemplateVersion, User)
from core.security import private_path
from core.template_source import (CHECK_UNAVAILABLE_CODES, PdfTemplateCheckUnavailable, PdfTemplateRefused,
                                  assert_pdf_template_usable)
from documents import DocumentError, pdf_raw
from documents.test_pdf_active_content import form, p1_trigger, after_eof
from exercised import requires_input

from .audio_fixtures import wav_bytes
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




class SyntheticPractice:
    """A clinician with welcome credit, a department, a patient, and PDF templates stored exactly as
    acceptance (before or after the P1 repair) left them."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        override = override_settings(MEDIA_ROOT=Path(directory.name))
        override.enable()
        self.addCleanup(override.disable)
        self.user = User.objects.create_user(username=self.username, email=self.username + "@synthetic.invalid",
                                             verified_at=timezone.now())
        organization = Organization.objects.create(name="Synthetic " + self.username)
        self.department = Department.objects.create(organization=organization, name="Synthetic forms")
        Membership.objects.create(user=self.user, department=self.department, role="clinician")
        welcome_credit(self.user)
        self.patient = Patient.objects.create(department=self.department, display_name="SYNTHETIC " + self.username,
                                              reference=self.username, created_by=self.user)
        self.client.force_login(self.user)

    def stored_template(self, original, name="Synthetic legacy form"):
        relative = "originals/%s.pdf" % hashlib.sha256(original + name.encode()).hexdigest()[:16]
        template = Template.objects.create(department=self.department, name=name, format="pdf",
                                           original_name="synthetic.pdf", original_path=relative,
                                           sha256=hashlib.sha256(original).hexdigest(), created_by=self.user)
        path = private_path(template.original_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(original)
        version = TemplateVersion.objects.create(template=template, number=1, created_by=self.user, fields=[
            {"key": "Symptoms", "label": "Symptoms", "kind": "text", "locator": {"pdf_field": "Symptoms"}}])
        return template, version

    def encounter(self, version, **extra):
        return Encounter.objects.create(department=self.department, patient=self.patient, template_version=version,
                                        created_by=self.user, service_date=timezone.localdate(),
                                        notes="Symptoms: synthetic", **extra)

    def finalized(self, version, export_bytes):
        """A finalized encounter whose stored export is exactly these bytes (as finalize left it)."""
        relative = "exports/%s.pdf" % hashlib.sha256(export_bytes).hexdigest()[:16]
        path = private_path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(export_bytes)
        encounter = self.encounter(version, answers={"Symptoms": {"text": "x", "status": "supported", "reviewed": True,
                                                                  "evidence": []}})
        encounter.status = "finalized"
        encounter.export_path = relative
        encounter.export_sha256 = hashlib.sha256(export_bytes).hexdigest()
        encounter.finalized_at = timezone.now()
        encounter.finalized_by = self.user
        encounter.save()
        return encounter


def worker_failure(code):
    """The check of an ORIGINAL failing for a reason that is not about the file (e.g. parser_timeout)."""
    messages = {"parser_timeout": "Document processing exceeded its time limit.",
                "parser_failed": "The isolated document processor failed or reached a resource limit.",
                "sandbox_unavailable": "The secure document sandbox is unavailable.",
                "source_unavailable": "The original is unavailable.",
                "source_changed": "The approved document source changed before processing."}
    return patch("documents.check_original", side_effect=DocumentError(messages[code], code))


@contextmanager
def check_times_out():
    """Exactly the audit's SI-4 condition: only the isolated CHECK hits the 20 s wall clock (as on a loaded
    host); inspect and fill run for real, so the real service turns the timeout into parser_timeout."""
    import documents.service as service
    real_run = subprocess.run

    def slow_check(argv, *args, **kwargs):
        request = Path(argv[-1]) / "request.json"
        if request.exists() and json.loads(request.read_text()).get("operation") == "check":
            raise subprocess.TimeoutExpired(argv, service.TIMEOUT_SECONDS)
        return real_run(argv, *args, **kwargs)

    with patch.object(service.subprocess, "run", side_effect=slow_check) as patched:
        yield patched


@override_settings(**TEST_SETTINGS)
class ExportDownloadSafety(SyntheticPractice, TestCase):
    """Finding DL-1, redesigned for SI-1 and SI-2. Before a stored PDF EXPORT is served, its TEMPLATE
    ORIGINAL gets the same check as that original's own download; an export of a refused original is
    refused (409, nothing sent, audited). The export itself is not scanned: it holds the doctor's own
    words and may be up to 30 MiB, and round 2 refused both kinds after finalize, when the document
    could no longer change. (The live rebuild has no PDF templates today.)"""

    username = "export-safety"

    def export(self, encounter):
        return self.client.get("/encounters/%s/export/" % encounter.pk)

    def assert_export_refused(self, response, encounter, code, status=409):
        self.assertEqual(response.status_code, status)
        self.assertFalse(getattr(response, "streaming", False))
        self.assertNotIn(b"%PDF", response.content)
        self.assertTrue(response["Content-Type"].startswith("text/plain"))
        refused = AuditEvent.objects.get(action="encounter.export_refused", target=str(encounter.pk))
        self.assertEqual(refused.details, {"code": code})
        self.assertFalse(AuditEvent.objects.filter(action="encounter.export", target=str(encounter.pk)).exists())

    def assert_served(self, response, encounter, data):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), data)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response["Content-Disposition"].startswith("attachment;"))
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(AuditEvent.objects.filter(action="encounter.export", target=str(encounter.pk)).count(), 1)
        self.assertFalse(AuditEvent.objects.filter(action="encounter.export_refused").exists())

    def test_an_export_of_a_refused_original_is_refused_not_served(self):
        # DL-1's case: an export finalized before the P1 repair from an original the repair refuses.
        # Its bytes need not show anything: the original is what the repair refuses.
        template, version = self.stored_template(p1_trigger("type"))
        encounter = self.finalized(version, form())
        response = self.export(encounter)
        self.assert_export_refused(response, encounter, "unsafe_upload")
        self.assertIn(b"the PDF form it was filled from is no longer accepted.", response.content)
        self.assertIn(b"PDF actions, attachments, XFA, and external resources are not accepted.", response.content)

    def test_an_export_of_an_original_pypdf_cannot_read_completely_is_refused(self):
        template, version = self.stored_template(p1_trigger("type", payload=False))
        encounter = self.finalized(version, form())
        response = self.export(encounter)
        self.assert_export_refused(response, encounter, "unreadable_pdf")
        self.assertIn(b"could not be read completely", response.content)

    def test_the_check_runs_on_the_original_never_on_the_export(self):
        data = form()
        template, version = self.stored_template(data)
        encounter = self.finalized(version, data + b"%synthetic export trailer\n")
        from documents import check_original
        with patch("documents.check_original", wraps=check_original) as checked:
            response = self.export(encounter)
        self.assert_served(response, encounter, data + b"%synthetic export trailer\n")
        self.assertEqual(checked.call_count, 1)
        self.assertEqual(Path(checked.call_args.args[0]), private_path(template.original_path))
        self.assertEqual(checked.call_args.kwargs, {"expected_sha256": template.sha256})

    def test_an_export_between_10_and_30_mib_of_a_clean_form_is_served(self):
        # SI-1: finalize writes exports up to MAX_OUTPUT (30 MiB) while the original check reads at most
        # MAX_UPLOAD (10 MiB); round 2 refused a 10.5 MiB export of a clean form as upload_limit.
        from documents.service import MAX_OUTPUT, MAX_UPLOAD
        data = form()
        exported = data + b"%" + b"0" * (12 * 1024 * 1024) + b"\n"
        requires_input(MAX_UPLOAD < len(exported) <= MAX_OUTPUT, "an export larger than the 10 MiB input limit and "
                       "within the 30 MiB export limit, or the size case is never reached")
        template, version = self.stored_template(data)
        encounter = self.finalized(version, exported)
        self.assert_served(self.export(encounter), encounter, exported)

    def test_a_missing_or_changed_original_refuses_the_export(self):
        data = form()
        missing_template, missing_version = self.stored_template(data, name="Missing original")
        private_path(missing_template.original_path).unlink()
        missing = self.finalized(missing_version, data)
        response = self.export(missing)
        self.assert_export_refused(response, missing, "source_unavailable")
        self.assertIn(b"missing or changed, so it cannot be checked", response.content)
        changed_template, changed_version = self.stored_template(data + b"%changed\n", name="Changed original")
        private_path(changed_template.original_path).write_bytes(data)
        changed = self.finalized(changed_version, data + b"%second export\n")
        self.assertEqual(self.export(changed).status_code, 409)
        self.assertEqual(AuditEvent.objects.get(action="encounter.export_refused", target=str(changed.pk)).details,
                         {"code": "source_changed"})

    def test_a_check_that_could_not_run_refuses_the_export_as_try_again(self):
        data = form()
        template, version = self.stored_template(data)
        encounter = self.finalized(version, data)
        with check_times_out():
            response = self.export(encounter)
        self.assert_export_refused(response, encounter, "parser_timeout", status=503)
        self.assertIn(b"try again in a few minutes", response.content)
        self.assertNotIn(b"no longer accepted", response.content)
        served = self.export(encounter)                                    # once the check runs, it is served
        self.assertEqual(served.status_code, 200)
        self.assertEqual(b"".join(served.streaming_content), data)
        self.assertEqual(AuditEvent.objects.filter(action="encounter.export", target=str(encounter.pk)).count(), 1)


@override_settings(**TEST_SETTINGS)
class ExportOfTheDoctorsOwnWords(SyntheticPractice, TestCase):
    """SI-2 through the real upload, generation, review, finalize and export views and the real worker:
    pypdf writes answers verbatim into uncompressed appearance streams, and the word "trailer" followed
    later by "/Launch" in an answer made round 2 refuse a clean form's finalized export."""

    username = "export-words"

    def finalize_answer(self, answer):
        upload = self.client.post("/templates/upload/", {"name": "Synthetic stock form", "department": self.department.pk,
                                                         "synthetic_only": "on",
                                                         "file": SimpleUploadedFile("synthetic.pdf", form())})
        self.assertEqual(upload.status_code, 302)
        version = Template.objects.get(name="Synthetic stock form").versions.get(number=1)
        created = self.client.post("/encounters/new/", {"patient": self.patient.pk, "template_version": version.pk,
                                                        "notes": "Symptoms: Seen with trailer hitch injury.",
                                                        "synthetic_only": "on",
                                                        "service_date": timezone.localdate().isoformat()})
        self.assertEqual(created.status_code, 302)
        encounter = Encounter.objects.get(template_version=version)
        self.assertEqual(self.client.post("/encounters/%s/generate/" % encounter.pk).status_code, 302)
        self.assertTrue(run_one())
        encounter.refresh_from_db()
        saved = self.client.post("/encounters/%s/save/" % encounter.pk, {"revision": encounter.revision,
                                                                         "answer_Symptoms": answer,
                                                                         "reviewed_Symptoms": "on"})
        self.assertEqual(saved.status_code, 302)
        encounter.refresh_from_db()
        self.client.post("/encounters/%s/finalize/" % encounter.pk, {"reviewed": "on", "revision": encounter.revision})
        encounter.refresh_from_db()
        self.assertEqual(encounter.status, "finalized")
        return encounter

    def test_an_answer_with_trailer_and_launch_is_served(self):
        answer = "Seen with trailer hitch injury; plan /Launch"
        encounter = self.finalize_answer(answer)
        stored = private_path(encounter.export_path).read_bytes()
        # The condition SI-2 needs, asserted rather than assumed: the answer is in the export verbatim and
        # the hostile-input scan WOULD refuse these bytes (so serving them proves the export is not scanned).
        requires_input(answer.encode() in stored, "the answer written verbatim into the export")
        with self.assertRaises(pdf_raw.Refusal):
            pdf_raw.scan(stored)
        response = self.client.get("/encounters/%s/export/" % encounter.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), stored)
        self.assertEqual(AuditEvent.objects.filter(action="encounter.export", target=str(encounter.pk)).count(), 1)
        self.assertFalse(AuditEvent.objects.filter(action="encounter.export_refused").exists())


@override_settings(**TEST_SETTINGS)
class RefusedTemplateNotUsable(SyntheticPractice, TestCase):
    """Findings DL-2 and SI-3. A PDF template whose stored original the download gate refuses is turned
    away at encounter creation and on EVERY path that can buy a provider call for an encounter —
    generation and transcription (jobs.enqueue), coding (coding_service.ensure_run, automatic after a
    save and on request) and the semantic recheck — not only at finalize."""

    username = "refused-tmpl"

    def test_the_guard_refuses_a_refused_original_and_passes_a_clean_one(self):
        refused_template, _ = self.stored_template(p1_trigger("type"), name="Refused form")
        with self.assertRaises(PdfTemplateRefused) as caught:
            assert_pdf_template_usable(refused_template)
        self.assertIn("can no longer be used", "; ".join(caught.exception.messages))
        self.assertEqual(caught.exception.code, "unsafe_upload")
        clean_template, _ = self.stored_template(form(), name="Clean form")
        assert_pdf_template_usable(clean_template)      # no raise

    def test_encounter_creation_is_refused_for_a_refused_template(self):
        template, version = self.stored_template(p1_trigger("nosize"))
        response = self.client.post("/encounters/new/", {"patient": self.patient.pk, "template_version": version.pk,
                                                         "notes": "Symptoms: synthetic", "synthetic_only": "on",
                                                         "service_date": timezone.localdate().isoformat()})
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "can no longer be used", status_code=409)
        self.assertFalse(Encounter.objects.filter(template_version=version).exists())

    def test_generation_enqueue_is_refused_before_any_provider_call(self):
        template, version = self.stored_template(p1_trigger("widew"))
        # An encounter that already exists (e.g. created before the repair) must still not buy a generation.
        encounter = self.encounter(version)
        with self.assertRaises(ValidationError) as caught:
            enqueue(encounter, self.user, kind="generation")
        self.assertIn("can no longer be used", "; ".join(caught.exception.messages))
        self.assertFalse(Job.objects.filter(encounter=encounter).exists())

    def coding_setup(self, original):
        """An encounter in review with answers (as a generation before the repair left it), a coding reference
        for its date, and the provider boundary mocked exactly as core.tests.test_coding_workflow mocks it."""
        from core import coding_service
        from core.models import CodeSet, CodingContext, CodingRelease
        template, version = self.stored_template(original)
        encounter = self.encounter(version, answers={"Symptoms": {"text": "Nausea", "status": "supported",
                                                                  "reviewed": False, "evidence": []}},
                                   status="review", revision=2)
        encounter.notes = "The patient reports nausea."
        encounter.save(update_fields=["notes"])
        release = CodeSet.objects.create(system="ICD-10-CM", version="SYNTHETIC-SI3", effective_from=date(2000, 1, 1),
                                         effective_until=date(2099, 12, 31), source_url="https://synthetic.invalid/codes",
                                         sha256="b" * 64)
        CodingRelease.objects.create(release=release, index=[], tabular={}, digest="c" * 64)
        CodingContext.objects.create(encounter=encounter, updated_by=self.user,
                                     data={**coding_service.CONTEXT_DEFAULTS, "setting": "outpatient_office"})
        result = {"suggestions": [{"id": "finding", "system": "ICD-10-CM", "code": "R11.0",
                                   "description": "Synthetic fixture nausea", "evidence": "The patient reports nausea.",
                                   "explanation": "Synthetic workflow fixture", "instructions": [], "eligible": True}],
                  "questions": [], "excluded": [], "global_blockers": []}
        mocks = {}
        for target, kwargs in [
                ("core.coding_provider.configuration", {"return_value": {"provider": "synthetic-test"}}),
                ("core.coding_engine.generate", {"side_effect": lambda _: copy.deepcopy(result)}),
                ("core.coding_service.cpt_status", {"return_value": {"available": False}})]:
            mocked = patch(target, **kwargs)
            mocks[target] = mocked.start()
            self.addCleanup(mocked.stop)
        return encounter, mocks["core.coding_engine.generate"]

    def save_reviewed(self, encounter):
        with self.captureOnCommitCallbacks(execute=True):
            saved = self.client.post("/encounters/%s/save/" % encounter.pk, {"revision": encounter.revision,
                                                                             "answer_Symptoms": "Nausea",
                                                                             "reviewed_Symptoms": "on"})
        self.assertEqual(saved.status_code, 302)

    def test_saving_answers_queues_no_coding_run_for_a_refused_template(self):
        # SI-3: on round 2 this save queued a run and the coding worker called the provider once.
        from core import coding_service
        from core.models import CodingRun
        encounter, provider = self.coding_setup(p1_trigger("type"))
        self.save_reviewed(encounter)
        self.assertFalse(CodingRun.objects.filter(encounter=encounter).exists())
        self.assertFalse(coding_service.run_one())
        self.assertEqual(provider.call_count, 0)
        failed = AuditEvent.objects.get(action="coding.enqueue_failed", target=str(encounter.pk))
        self.assertEqual(failed.details, {"error_type": "PdfTemplateRefused"})
        # The explicit request is refused the same way, with the form's verdict, and creates nothing.
        from core.coding_engine import CURRENT_IDENTITY_CONTRACT
        with self.assertRaises(PdfTemplateRefused) as caught:
            coding_service.ensure_run(encounter, self.user, identity_policy=CURRENT_IDENTITY_CONTRACT)
        self.assertIn("can no longer be used", caught.exception.messages[0])
        self.assertFalse(CodingRun.objects.filter(encounter=encounter).exists())

    def test_the_same_save_on_a_clean_form_does_queue_coding(self):
        # The control that keeps the test above from passing vacuously: this setup does queue a run.
        from core import coding_service
        from core.models import CodingRun
        encounter, provider = self.coding_setup(form())
        self.save_reviewed(encounter)
        self.assertEqual(list(CodingRun.objects.filter(encounter=encounter).values_list("state", flat=True)), ["queued"])
        self.assertTrue(coding_service.run_one())
        self.assertEqual(provider.call_count, 1)

    def test_the_semantic_recheck_enqueue_runs_the_guard_first(self):
        from core import semantic_revalidation
        template, version = self.stored_template(p1_trigger("type"))
        encounter = self.encounter(version, status="review")
        token = signing.dumps({"contract": semantic_revalidation.CONTRACT, "binding": {}}, salt=semantic_revalidation.SALT)
        with self.assertRaises(PdfTemplateRefused) as caught:
            semantic_revalidation.enqueue(encounter, self.user, token, encounter.revision)
        # The guard's verdict, not the recheck's own later refusal of this empty binding.
        self.assertIn("can no longer be used", caught.exception.messages[0])
        self.assertFalse(Job.objects.filter(encounter=encounter).exists())


@override_settings(**TEST_SETTINGS)
class CheckUnavailableIsNotAVerdict(SyntheticPractice, TestCase):
    """Finding SI-4. A check that could not run (the worker timed out, failed or hit a limit, the
    sandbox would not start, the stored file changed between two reads) refuses just the same — nothing
    is sent — but says "try again", never the permanent "can no longer be used", and never discards the
    doctor's input."""

    username = "check-unavailable"

    def test_worker_failures_are_try_again_and_verdicts_are_refusals(self):
        # ⚠️ The codes are stated here, not read from the code under test: iterating CHECK_UNAVAILABLE_CODES
        # let a mutation that emptied it pass this loop vacuously (found by the round-3 mutation run).
        failures = ("parser_timeout", "parser_failed", "sandbox_unavailable", "source_unavailable", "source_changed")
        self.assertEqual(CHECK_UNAVAILABLE_CODES, frozenset(failures))
        template, _ = self.stored_template(form())
        for code in failures:
            with self.subTest(code=code), worker_failure(code), self.assertRaises(PdfTemplateCheckUnavailable) as caught:
                assert_pdf_template_usable(template)
            self.assertEqual(caught.exception.code, code)
            self.assertIn("could not check this form right now", caught.exception.messages[0])
            self.assertIn("try again", caught.exception.messages[0])
            self.assertNotIn("can no longer be used", caught.exception.messages[0])
        verdicts = {"unsafe_upload": "PDF actions, attachments, XFA, and external resources are not accepted.",
                    "unreadable_pdf": "This PDF could not be read completely.", "upload_limit": "Too large.",
                    "invalid_document": "The document is malformed.", "unsupported_format": "Not a PDF."}
        for code, message in verdicts.items():
            with self.subTest(code=code), patch("documents.check_original", side_effect=DocumentError(message, code)), \
                    self.assertRaises(PdfTemplateRefused) as caught:
                assert_pdf_template_usable(template)
            self.assertEqual(caught.exception.code, code)
            self.assertTrue(caught.exception.messages[0].startswith("This form can no longer be used: " + message))

    def test_encounter_creation_and_generation_say_try_again_and_send_nothing(self):
        template, version = self.stored_template(form())
        with check_times_out():
            response = self.client.post("/encounters/new/", {"patient": self.patient.pk, "template_version": version.pk,
                                                             "notes": "Symptoms: synthetic words kept", "synthetic_only": "on",
                                                             "service_date": timezone.localdate().isoformat()})
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "could not check this form right now", status_code=409)
        self.assertContains(response, "synthetic words kept", status_code=409)       # the doctor's notes are kept
        self.assertNotContains(response, "can no longer be used", status_code=409)
        self.assertFalse(Encounter.objects.filter(template_version=version).exists())
        encounter = self.encounter(version)
        with check_times_out():
            generated = self.client.post("/encounters/%s/generate/" % encounter.pk, HTTP_ACCEPT="application/json")
        self.assertEqual(generated.status_code, 503)
        self.assertIn("could not check this form right now", generated.json()["message"])
        self.assertFalse(Job.objects.filter(encounter=encounter).exists())

    def test_the_original_download_says_try_again(self):
        template, _ = self.stored_template(form())
        with check_times_out():
            response = self.client.get("/templates/%s/original/" % template.pk)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"%PDF", response.content)
        self.assertIn(b"try again in a few minutes", response.content)
        self.assertEqual(AuditEvent.objects.get(action="template.download_refused", target=str(template.pk)).details,
                         {"code": "parser_timeout"})


@override_settings(**TEST_SETTINGS)
class RecordingKeptWhenTheFormCannotBeChecked(SyntheticPractice, TestCase):
    """SI-4 on the voice route: on round 2 a check timeout on a clean form deleted the doctor's uploaded
    recording and called the form unusable. The recording is now kept, nothing is sent, and the doctor
    sends the same recording again (or discards it) from the page the response shows."""

    username = "recording-kept"
    VOICE_ENV = {"QUILLMD_DEEPGRAM_RATE_PER_MINUTE": "0.006", "QUILLMD_DEEPGRAM_RATE_PER_SECOND": "",
                 "QUILLMD_VOICE_MAX_COST": "0.20", "QUILLMD_PROVIDER_DISCOUNT_RATE": "0",
                 "DEEPGRAM_API_KEY": "synthetic-placeholder-not-a-key"}

    def recordings(self):
        folder = private_path("audio")
        return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []

    def dictate(self, encounter, tag):
        with patch.dict(os.environ, self.VOICE_ENV):
            return self.client.post("/encounters/%s/voice/" % encounter.pk, {
                "audio": SimpleUploadedFile(tag + ".wav", wav_bytes(seconds=2, tag=tag), content_type="audio/wav"),
                "consent": "on"})

    def decide(self, encounter, response, decision):
        with patch.dict(os.environ, self.VOICE_ENV):
            return self.client.post("/encounters/%s/voice/retry/" % encounter.pk,
                                    {"retry": response.context["retry"], "decision": decision})

    def kept(self):
        template, version = self.stored_template(form())
        encounter = self.encounter(version)
        with check_times_out():
            response = self.dictate(encounter, "kept")
        self.assertEqual(response.status_code, 409)               # never 5xx: Django saves no session on one
        self.assertIn(settings.SESSION_COOKIE_NAME, response.cookies)        # so this page extends the session
        self.assertContains(response, "could not check this form right now", status_code=409)
        self.assertNotContains(response, "can no longer be used", status_code=409)
        self.assertFalse(Job.objects.filter(encounter=encounter).exists())
        self.assertEqual(len(self.recordings()), 1)                                   # kept, not deleted
        offered = AuditEvent.objects.get(action="voice.check_unavailable", target=str(encounter.pk))
        self.assertEqual(offered.details["code"], "parser_timeout")
        self.assertEqual(Path(offered.details["path"]).name, self.recordings()[0])
        return encounter, response, offered.details["path"]

    def test_the_kept_recording_is_sent_again_without_recording_it_again(self):
        encounter, response, kept = self.kept()
        answer = self.decide(encounter, response, "retry")
        self.assertEqual(answer.status_code, 302)
        job = Job.objects.get(encounter=encounter, kind="transcription")
        self.assertEqual((job.input_path, job.state), (kept, "queued"))
        self.assertEqual(self.recordings(), [Path(kept).name])

    def test_a_retry_while_the_check_still_fails_keeps_it_and_offers_again(self):
        encounter, response, kept = self.kept()
        with check_times_out():
            again = self.decide(encounter, response, "retry")
        self.assertEqual(again.status_code, 409)
        self.assertEqual(self.recordings(), [Path(kept).name])
        self.assertFalse(Job.objects.filter(encounter=encounter).exists())
        self.assertEqual(self.decide(encounter, again, "retry").status_code, 302)
        self.assertEqual(Job.objects.get(encounter=encounter, kind="transcription").input_path, kept)

    def test_discarding_removes_it_and_sends_nothing(self):
        encounter, response, kept = self.kept()
        self.decide(encounter, response, "discard")
        self.assertEqual(self.recordings(), [])
        self.assertFalse(Job.objects.filter(encounter=encounter).exists())

    def test_a_kept_recording_nobody_sends_is_removed_after_the_window(self):
        encounter, response, kept = self.kept()
        self.assertEqual(reap_abandoned_voice_uploads(), 0)                      # still inside the window
        with patch("core.jobs.timezone.now", return_value=timezone.now() + timedelta(minutes=41)):
            self.assertEqual(reap_abandoned_voice_uploads(), 1)
        self.assertEqual(self.recordings(), [])
        self.assertEqual(AuditEvent.objects.filter(action="voice.kept_upload_removed").count(), 1)

    def test_a_renewed_offer_holds_the_recording_but_not_past_the_first_offers_window(self):
        encounter, response, kept = self.kept()
        start = timezone.now()

        def at(minutes):
            moment = start + timedelta(minutes=minutes)
            return patch("django.core.signing.time.time", return_value=moment.timestamp()), \
                patch("django.utils.timezone.now", return_value=moment)

        clock, now = at(25)
        with clock, now, check_times_out():
            renewed = self.decide(encounter, response, "retry")                    # the first offer, still valid
        self.assertEqual(renewed.status_code, 409)
        self.assertEqual(AuditEvent.objects.filter(action="voice.check_unavailable").count(), 2)
        with patch("core.jobs.timezone.now", return_value=start + timedelta(minutes=41)):
            self.assertEqual(reap_abandoned_voice_uploads(), 0)                  # the newer offer still holds it
        self.assertEqual(self.recordings(), [Path(kept).name])
        # The renewed page is 10 minutes old, but the first offer ended at 30: nothing is sent. (Only the
        # signing clock moves here, so the session's own 30-minute expiry plays no part in the outcome.)
        clock, _ = at(35)
        with clock:
            late = self.decide(encounter, renewed, "retry")
        self.assertEqual(late.status_code, 302)
        self.assertFalse(Job.objects.filter(encounter=encounter).exists())
        self.assertTrue(any("no longer kept for sending" in str(m) for m in get_messages(late.wsgi_request)))
        with patch("core.jobs.timezone.now", return_value=start + timedelta(minutes=25 + 41)):
            self.assertEqual(reap_abandoned_voice_uploads(), 1)                  # and its own window ends too
        self.assertEqual(self.recordings(), [])

    def test_a_refused_form_still_removes_the_upload_and_says_so(self):
        template, version = self.stored_template(p1_trigger("type"))
        encounter = self.encounter(version)
        response = self.dictate(encounter, "refused")
        self.assertEqual(response.status_code, 302)
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("can no longer be used" in m for m in messages), messages)
        self.assertEqual(self.recordings(), [])
        self.assertFalse(AuditEvent.objects.filter(action="voice.check_unavailable").exists())
