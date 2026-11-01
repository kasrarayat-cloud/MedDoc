"""Finding P1 on the actual upload and original-download paths (docs/rebuild/pypdf-6.21.4.md).

A stored PDF original is checked for active content in the isolated worker before its bytes are
served; a refusal serves nothing and is audited with its code. The download's type comes from the
stored format, never from the client's file name. Fixtures are built in memory (the pre-commit
hook forbids tracked PDFs); the payloads are app.alert('synthetic') only.

Round 3 (2026-11-01): a stored PDF export is served after its TEMPLATE ORIGINAL passes that check,
and the export itself is not scanned (SI-1, SI-2); a check that could not run says "try again"
(SI-4).

Round 4 (2026-11-01): provider usage is gated in the WORKER, immediately before every provider call
(generation, transcription, the semantic stages and recheck, coding): a refused form, or a check that
could not run, fails that job unsent through its existing failure handling. Round 3's kept-recording
retry flow and its enqueue-time guards are removed, so the voice upload and approval flows are as
they were before P1. The synchronous checks stay where refusing loses nothing: encounter creation,
the generate request, and both downloads. A check that cannot even START (GR-1) is a check that could
not run, everywhere.
"""
from contextlib import contextmanager
import copy
from datetime import date
import errno
from io import BytesIO, StringIO
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from docx import Document

from core.billing import welcome_credit
from core.generation_errors import NoProviderRequest
from core.jobs import enqueue, run_one
from core.models import (AuditEvent, Department, Encounter, Job, Membership, Organization, Patient, ProviderReceipt,
                         Reservation, Template, TemplateVersion, Usage, User)
from core.security import private_path
from core.template_source import (CHECK_UNAVAILABLE_CODES, PdfTemplateCheckUnavailable, PdfTemplateRefused,
                                  assert_pdf_template_usable, provider_refusal)
from documents import DocumentError, pdf_raw
from documents.test_pdf_active_content import form, p1_trigger, after_eof
from exercised import requires_input

from .audio_fixtures import wav_bytes
from .test_workflow import TEST_SETTINGS

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# ⚠️ Stated here, never read from the code under test: a mutation of the code's own constant must not be
# able to make these comparisons pass (round 3's lesson with CHECK_UNAVAILABLE_CODES).
REFUSED_JOB = ("The PDF form of this document can no longer be used: it failed the active-content check. "
               "Upload a clean PDF as a new form.")
UNCHECKED_JOB = ("The PDF form of this document could not be checked right now. This is a temporary problem on "
                 "our side, not a verdict about the form.")
NOT_SENT = " No provider request was made; nothing was charged and the held funds were released."
CODING_RETAINED = " Contact your administrator to review this retained attempt. No automatic retry will be sent."


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


def worker_failure(code):
    """The check of an ORIGINAL failing for a reason that is not about the file (e.g. parser_timeout)."""
    messages = {"parser_timeout": "Document processing exceeded its time limit.",
                "parser_failed": "The isolated document processor failed or reached a resource limit.",
                "sandbox_unavailable": "The secure document sandbox is unavailable.",
                "source_unavailable": "The original is unavailable.",
                "source_changed": "The approved document source changed before processing."}
    return patch("documents.check_original", side_effect=DocumentError(messages[code], code))


def check_operation(argv):
    """True when this subprocess launch is the isolated worker running the CHECK operation."""
    request = Path(argv[-1]) / "request.json"
    return request.exists() and json.loads(request.read_text()).get("operation") == "check"


@contextmanager
def check_times_out():
    """Exactly the audit's SI-4 condition: only the isolated CHECK hits the 20 s wall clock (as on a loaded
    host); inspect and fill run for real, so the real service turns the timeout into parser_timeout."""
    import documents.service as service
    real_run = subprocess.run

    def slow_check(argv, *args, **kwargs):
        if check_operation(argv):
            raise subprocess.TimeoutExpired(argv, service.TIMEOUT_SECONDS)
        return real_run(argv, *args, **kwargs)

    with patch.object(service.subprocess, "run", side_effect=slow_check) as patched:
        yield patched


@contextmanager
def check_cannot_start(error=None):
    """Finding GR-1: only the isolated CHECK cannot START its worker, the way the kernel reports it on a loaded
    host (fork/clone EAGAIN at a pids limit, ENOMEM, EMFILE for its pipes); inspect and fill run for real."""
    import documents.service as service
    real_run = subprocess.run
    error = error if error is not None else BlockingIOError(errno.EAGAIN, "Resource temporarily unavailable")

    def failing(argv, *args, **kwargs):
        if check_operation(argv):
            raise error
        return real_run(argv, *args, **kwargs)

    with patch.object(service.subprocess, "run", side_effect=failing) as patched:
        yield patched


@contextmanager
def check_workspace_fails(code):
    """Finding GR-1: the CHECK's temporary workspace cannot be created (ENOSPC, EDQUOT); inspect and fill run
    for real."""
    import documents.service as service
    real_run = service._run

    def run(path, operation, *args, **kwargs):
        if operation == "check":
            with patch.object(service.tempfile, "TemporaryDirectory", side_effect=OSError(code, os.strerror(code))):
                return real_run(path, operation, *args, **kwargs)
        return real_run(path, operation, *args, **kwargs)

    with patch.object(service, "_run", side_effect=run):
        yield


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

    def test_a_check_that_cannot_start_is_reported_as_such_not_raised(self):
        # GR-1 at the documents layer: the command calls check_original directly, so only the conversion
        # there keeps a spawn failure from aborting the whole report.
        clean = self.stored(form())
        output = self.root / "report.json"
        with check_cannot_start():
            call_command("check_pdf_originals", output=str(output), stdout=StringIO())
        report = json.loads(output.read_text())
        self.assertEqual(report["templates"], [{"template_id": str(clean.pk), "code": "sandbox_unavailable"}])


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

    def new_encounter(self, version, notes="Symptoms: synthetic words typed by the doctor"):
        return self.client.post("/encounters/new/", {"patient": self.patient.pk, "template_version": version.pk,
                                                     "notes": notes, "synthetic_only": "on",
                                                     "service_date": timezone.localdate().isoformat()})

    def generate_json(self, encounter):
        return self.client.post("/encounters/%s/generate/" % encounter.pk, HTTP_ACCEPT="application/json")

    def assert_failed_unsent(self, job, error):
        """The worker's existing not-processed failure: failed, nothing received, recorded or held."""
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), ("failed", error))
        self.assertFalse(ProviderReceipt.objects.filter(job=job).exists())
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertFalse(Reservation.objects.filter(job=job, state="held").exists())


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
    later by "/Launch" in an answer made round 2 refuse a clean form's finalized export. (Round 4: the
    generation also passes the worker's form guard, with the real sandboxed check.)"""

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
    """Findings DL-2 and SI-3, as round 4 places the gates. A PDF template whose stored original the download
    gate refuses is turned away synchronously where that loses nothing — encounter creation and the generate
    request — and, for every provider call, by the worker immediately before the call: generation,
    transcription, coding, the semantic generation stages and the semantic recheck all fail unsent, through
    their existing failure handling, whenever and however they were queued."""

    username = "refused-tmpl"

    def test_the_guard_refuses_a_refused_original_and_passes_a_clean_one(self):
        refused_template, _ = self.stored_template(p1_trigger("type"), name="Refused form")
        with self.assertRaises(PdfTemplateRefused) as caught:
            assert_pdf_template_usable(refused_template)
        self.assertIn("can no longer be used", "; ".join(caught.exception.messages))
        self.assertEqual(caught.exception.code, "unsafe_upload")
        self.assertEqual(provider_refusal(refused_template), REFUSED_JOB)
        clean_template, _ = self.stored_template(form(), name="Clean form")
        assert_pdf_template_usable(clean_template)      # no raise
        self.assertIsNone(provider_refusal(clean_template))

    def test_encounter_creation_is_refused_for_a_refused_template(self):
        template, version = self.stored_template(p1_trigger("nosize"))
        response = self.new_encounter(version)
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "can no longer be used", status_code=409)
        self.assertContains(response, "synthetic words typed by the doctor", status_code=409)
        self.assertFalse(Encounter.objects.filter(template_version=version).exists())

    def test_the_generate_request_is_refused_and_queues_nothing(self):
        template, version = self.stored_template(p1_trigger("widew"))
        # An encounter that already exists (e.g. created before the repair) must still not buy a generation.
        encounter = self.encounter(version)
        response = self.generate_json(encounter)
        self.assertEqual(response.status_code, 409)
        self.assertIn("can no longer be used", response.json()["message"])
        page = self.client.post("/encounters/%s/generate/" % encounter.pk)
        self.assertEqual(page.status_code, 302)
        self.assertTrue(any("can no longer be used" in str(m) for m in get_messages(page.wsgi_request)))
        self.assertFalse(Job.objects.filter(encounter=encounter).exists())

    def test_a_generation_queued_anyway_fails_in_the_worker_without_a_provider_call(self):
        # enqueue no longer checks the form (round 4): a job queued by another path, or before the deploy,
        # reaches the worker, and the worker's guard is what stops it.
        template, version = self.stored_template(p1_trigger("widew"))
        encounter = self.encounter(version)
        job = enqueue(encounter, self.user, kind="generation")
        self.assertEqual(job.state, "queued")
        with patch("core.generation.generate") as provider:
            self.assertTrue(run_one())
        self.assertEqual(provider.call_count, 0)
        self.assert_failed_unsent(job, "Not processed: " + REFUSED_JOB + NOT_SENT)

    def test_the_same_generation_on_a_clean_form_reaches_the_provider(self):
        # The control: the guard passes a clean form and the provider path runs.
        template, version = self.stored_template(form())
        encounter = self.encounter(version)
        job = enqueue(encounter, self.user, kind="generation")
        with patch("core.generation.generate", side_effect=NoProviderRequest("Synthetic stop after the guard.")) as provider:
            self.assertTrue(run_one())
        self.assertEqual(provider.call_count, 1)
        self.assert_failed_unsent(job, "Not processed: Synthetic stop after the guard." + NOT_SENT)

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

    def test_a_coding_run_on_a_refused_form_fails_in_the_worker_without_a_provider_call(self):
        # SI-3's case. Round 3 refused at the save (on the request path); round 4 lets the save queue the run
        # as before P1, and the coding worker's guard stops it: no request, nothing charged, the reason shown.
        from core import coding_service
        from core.models import CodingRun
        encounter, provider = self.coding_setup(p1_trigger("type"))
        self.save_reviewed(encounter)
        run = CodingRun.objects.get(encounter=encounter)
        self.assertEqual(run.state, "queued")
        self.assertTrue(coding_service.run_one())
        self.assertEqual(provider.call_count, 0)
        run.refresh_from_db()
        self.assertEqual((run.state, run.error_code, run.error), ("failed", "processing_failed", REFUSED_JOB + CODING_RETAINED))
        self.assertEqual((run.actual_cost, run.requests), (0, []))
        self.assertFalse(AuditEvent.objects.filter(action="coding.enqueue_failed").exists())

    def test_the_same_save_on_a_clean_form_does_queue_coding(self):
        # The control that keeps the test above from passing vacuously: this setup does reach the provider.
        from core import coding_service
        from core.models import CodingRun
        encounter, provider = self.coding_setup(form())
        self.save_reviewed(encounter)
        self.assertEqual(list(CodingRun.objects.filter(encounter=encounter).values_list("state", flat=True)), ["queued"])
        self.assertTrue(coding_service.run_one())
        self.assertEqual(provider.call_count, 1)

    def test_a_semantic_generation_job_is_stopped_before_anything_on_its_path(self):
        # Semantic definitions exist for Word forms only, so this cannot happen today; the guard still comes
        # before anything on the path, and the job fails unsent (no stage was ever created or sent).
        template, version = self.stored_template(p1_trigger("type"))
        encounter = self.encounter(version)
        job = Job.objects.create(encounter=encounter, user=self.user, kind="generation", revision=encounter.revision,
                                 request_key="synthetic-semantic-guard", config={"semantic_contract": "semantic-facts-v1"})
        from core import word_contract
        with patch("core.word_contract.require_generation", wraps=word_contract.require_generation) as definitions:
            self.assertTrue(run_one())
        self.assertEqual(definitions.call_count, 0)
        self.assert_failed_unsent(job, "Not processed: " + REFUSED_JOB)
        self.assertFalse(job.ai_stage_receipts.exists())

    def test_a_semantic_recheck_job_is_stopped_before_anything_on_its_path(self):
        from core import semantic_revalidation
        template, version = self.stored_template(p1_trigger("type"))
        encounter = self.encounter(version, status="review")
        job = Job.objects.create(encounter=encounter, user=self.user, kind="generation", revision=encounter.revision,
                                 request_key="synthetic-recheck-guard",
                                 config={"semantic_revalidation_contract": semantic_revalidation.CONTRACT})
        with patch("core.semantic_revalidation._bound_proposal") as bound, patch("core.ai_stages.execute_stage") as stage:
            self.assertTrue(run_one())
        self.assertEqual((bound.call_count, stage.call_count), (0, 0))
        job.refresh_from_db()
        self.assertEqual(job.state, "failed")
        self.assertTrue(job.error.endswith("NoProviderRequest"), job.error)
        self.assertEqual(AuditEvent.objects.get(action="semantic.revalidation_failed", target=str(job.pk)).details,
                         {"error_class": "NoProviderRequest", "provider_calls": 0, "automatic_retries": 0})


@override_settings(**TEST_SETTINGS)
class CheckUnavailableIsNotAVerdict(SyntheticPractice, TestCase):
    """Finding SI-4. A check that could not run (the worker timed out, failed or hit a limit, the
    sandbox would not start, the stored file changed between two reads) refuses just the same — nothing
    is sent — but says "try again", never the permanent "can no longer be used", and never discards the
    doctor's input. In the worker it fails the job unsent with its own sentence."""

    username = "check-unavailable"

    def test_worker_failures_are_try_again_and_verdicts_are_refusals(self):
        # ⚠️ The codes are stated here, not read from the code under test: iterating CHECK_UNAVAILABLE_CODES
        # let a mutation that emptied it pass this loop vacuously (found by the round-3 mutation run).
        failures = ("parser_timeout", "parser_failed", "sandbox_unavailable", "source_unavailable", "source_changed")
        self.assertEqual(CHECK_UNAVAILABLE_CODES, frozenset(failures))
        template, _ = self.stored_template(form())
        for code in failures:
            with self.subTest(code=code):
                with worker_failure(code), self.assertRaises(PdfTemplateCheckUnavailable) as caught:
                    assert_pdf_template_usable(template)
                self.assertEqual(caught.exception.code, code)
                self.assertIn("could not check this form right now", caught.exception.messages[0])
                self.assertIn("try again", caught.exception.messages[0])
                self.assertNotIn("can no longer be used", caught.exception.messages[0])
        verdicts = {"unsafe_upload": "PDF actions, attachments, XFA, and external resources are not accepted.",
                    "unreadable_pdf": "This PDF could not be read completely.", "upload_limit": "Too large.",
                    "invalid_document": "The document is malformed.", "unsupported_format": "Not a PDF."}
        for code, message in verdicts.items():
            with self.subTest(code=code):
                with patch("documents.check_original", side_effect=DocumentError(message, code)), \
                        self.assertRaises(PdfTemplateRefused) as caught:
                    assert_pdf_template_usable(template)
                self.assertEqual(caught.exception.code, code)
                self.assertTrue(caught.exception.messages[0].startswith("This form can no longer be used: " + message))

    def test_encounter_creation_and_generation_say_try_again_and_send_nothing(self):
        template, version = self.stored_template(form())
        with check_times_out():
            response = self.new_encounter(version, notes="Symptoms: synthetic words kept")
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "could not check this form right now", status_code=409)
        self.assertContains(response, "synthetic words kept", status_code=409)       # the doctor's notes are kept
        self.assertNotContains(response, "can no longer be used", status_code=409)
        self.assertFalse(Encounter.objects.filter(template_version=version).exists())
        encounter = self.encounter(version)
        with check_times_out():
            generated = self.generate_json(encounter)
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

    def test_in_the_worker_a_check_that_could_not_run_fails_the_job_unsent(self):
        template, version = self.stored_template(form())
        encounter = self.encounter(version)
        job = enqueue(encounter, self.user, kind="generation")
        with check_times_out(), patch("core.generation.generate") as provider:
            self.assertTrue(run_one())
        self.assertEqual(provider.call_count, 0)
        self.assert_failed_unsent(job, "Not processed: " + UNCHECKED_JOB + NOT_SENT)

    def test_the_worker_guard_never_raises_into_the_worker(self):
        # A guard that raised anything but the not-sent failure would leave the job in reconciliation with its
        # hold kept. Here the stored location itself is invalid (the database forbids changing it afterwards,
        # so the row is created that way), and the guard cannot even find the file.
        template = Template.objects.create(department=self.department, name="Synthetic invalid location", format="pdf",
                                           original_name="synthetic.pdf", original_path="", sha256="a" * 64,
                                           created_by=self.user)
        version = TemplateVersion.objects.create(template=template, number=1, created_by=self.user, fields=[
            {"key": "Symptoms", "label": "Symptoms", "kind": "text", "locator": {"pdf_field": "Symptoms"}}])
        with self.assertRaises(ValidationError):
            assert_pdf_template_usable(template)
        self.assertEqual(provider_refusal(template), UNCHECKED_JOB)
        job = enqueue(self.encounter(version), self.user, kind="generation")
        with patch("core.generation.generate") as provider:
            self.assertTrue(run_one())
        self.assertEqual(provider.call_count, 0)
        self.assert_failed_unsent(job, "Not processed: " + UNCHECKED_JOB + NOT_SENT)


@override_settings(**TEST_SETTINGS)
class CheckThatCannotStart(SyntheticPractice, TestCase):
    """Finding GR-1. A failure to START the check — the worker cannot be spawned (EAGAIN, ENOMEM), its pipes
    cannot be opened (EMFILE), its workspace cannot be created (ENOSPC, EDQUOT) — raised a plain OSError past
    every gate: 500s, typed notes lost, unaudited refusals. It is a check that could not run, everywhere:
    "try again", never a 500, never a discarded input, audited where the route audits."""

    username = "check-start"

    def test_every_start_failure_is_a_check_that_could_not_run(self):
        template, _ = self.stored_template(form())
        starts = {"spawn EAGAIN": check_cannot_start(BlockingIOError(errno.EAGAIN, "Resource temporarily unavailable")),
                  "spawn ENOMEM": check_cannot_start(OSError(errno.ENOMEM, "Cannot allocate memory")),
                  "pipes EMFILE": check_cannot_start(OSError(errno.EMFILE, "Too many open files")),
                  "child setup": check_cannot_start(subprocess.SubprocessError("Exception occurred in preexec_fn.")),
                  "workspace ENOSPC": check_workspace_fails(errno.ENOSPC),
                  "workspace EDQUOT": check_workspace_fails(errno.EDQUOT)}
        for name, failure in starts.items():
            with self.subTest(name=name):
                with failure, self.assertRaises(PdfTemplateCheckUnavailable) as caught:
                    assert_pdf_template_usable(template)
                self.assertEqual(caught.exception.code, "sandbox_unavailable")
                self.assertIn("try again", caught.exception.messages[0])

    def test_anything_else_the_check_raises_is_not_a_verdict_either(self):
        template, _ = self.stored_template(form())
        with patch("documents.check_original", side_effect=RuntimeError("synthetic unexpected failure")), \
                self.assertRaises(PdfTemplateCheckUnavailable) as caught:
            assert_pdf_template_usable(template)
        self.assertEqual(caught.exception.code, "sandbox_unavailable")

    def test_an_original_that_exists_but_cannot_be_read_is_not_skipped(self):
        template, _ = self.stored_template(form())

        class Unreadable:
            def read_bytes(self):
                raise OSError(errno.EIO, "Input/output error")

        with patch("core.template_source.private_path", return_value=Unreadable()), \
                self.assertRaises(PdfTemplateCheckUnavailable) as caught:
            assert_pdf_template_usable(template)
        self.assertEqual(caught.exception.code, "source_unavailable")
        missing, _ = self.stored_template(form(), name="Missing original")
        private_path(missing.original_path).unlink()
        assert_pdf_template_usable(missing)            # a missing original is still left to the step that reads it

    def test_encounter_creation_keeps_the_typed_notes_and_says_try_again(self):
        template, version = self.stored_template(form())
        with check_cannot_start():
            response = self.new_encounter(version)
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "synthetic words typed by the doctor", status_code=409)
        self.assertContains(response, "could not check this form right now", status_code=409)
        self.assertFalse(Encounter.objects.filter(template_version=version).exists())

    def test_the_generate_request_says_try_again(self):
        template, version = self.stored_template(form())
        encounter = self.encounter(version)
        with check_cannot_start():
            response = self.generate_json(encounter)
        self.assertEqual(response.status_code, 503)
        self.assertIn("could not check this form right now", response.json()["message"])
        self.assertFalse(Job.objects.filter(encounter=encounter).exists())

    def test_both_downloads_say_try_again_and_are_audited(self):
        data = form()
        template, version = self.stored_template(data)
        finalized = self.finalized(version, data)
        with check_cannot_start():
            original = self.client.get("/templates/%s/original/" % template.pk)
            exported = self.client.get("/encounters/%s/export/" % finalized.pk)
        for response in (original, exported):
            self.assertEqual(response.status_code, 503)
            self.assertNotIn(b"%PDF", response.content)
            self.assertIn(b"try again in a few minutes", response.content)
        self.assertEqual(AuditEvent.objects.get(action="template.download_refused", target=str(template.pk)).details,
                         {"code": "sandbox_unavailable"})
        self.assertEqual(AuditEvent.objects.get(action="encounter.export_refused", target=str(finalized.pk)).details,
                         {"code": "sandbox_unavailable"})

    def test_in_the_worker_a_check_that_cannot_start_fails_the_job_unsent(self):
        template, version = self.stored_template(form())
        job = enqueue(self.encounter(version), self.user, kind="generation")
        with check_cannot_start(), patch("core.generation.generate") as provider:
            self.assertTrue(run_one())
        self.assertEqual(provider.call_count, 0)
        self.assert_failed_unsent(job, "Not processed: " + UNCHECKED_JOB + NOT_SENT)


VOICE_ENV = {"QUILLMD_DEEPGRAM_RATE_PER_MINUTE": "0.006", "QUILLMD_DEEPGRAM_RATE_PER_SECOND": "",
             "QUILLMD_VOICE_MAX_COST": "0.20", "QUILLMD_PROVIDER_DISCOUNT_RATE": "0",
             "DEEPGRAM_API_KEY": "synthetic-placeholder-not-a-key"}
# $60 per minute: a two-second recording is above the $0.30 displayed limit (same device as test_recording_limit).
EXPENSIVE_VOICE_ENV = dict(VOICE_ENV, QUILLMD_DEEPGRAM_RATE_PER_MINUTE="60")


@override_settings(**TEST_SETTINGS)
class VoiceFlowsAsBeforeP1(SyntheticPractice, TestCase):
    """Round 4: the voice upload and over-limit approval run no form check, exactly as before P1, so a check
    that cannot run can no longer cost the doctor the recording they dictated. The worker checks the form
    immediately before the transcription request; a refused form, or a check that could not run, fails the
    job unsent and the recording stays that job's input, as for any failed job. Round 3's retry page, its
    signed offers and the reaper's kept-recording rules are gone."""

    username = "voice-flows"

    def recordings(self):
        folder = private_path("audio")
        return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []

    def dictate(self, encounter, tag, env=VOICE_ENV):
        with patch.dict(os.environ, env):
            return self.client.post("/encounters/%s/voice/" % encounter.pk, {
                "audio": SimpleUploadedFile(tag + ".wav", wav_bytes(seconds=2, tag=tag), content_type="audio/wav"),
                "consent": "on"})

    def queued(self, response, encounter):
        self.assertEqual(response.status_code, 302)
        self.assertTrue(any(str(m).startswith("Transcription queued") for m in get_messages(response.wsgi_request)))
        job = Job.objects.get(encounter=encounter, kind="transcription")
        self.assertEqual(job.state, "queued")
        self.assertEqual(self.recordings(), [Path(job.input_path).name])
        return job

    def process(self, job, provider_side_effect=None):
        with patch.dict(os.environ, VOICE_ENV), patch("core.jobs.transcribe", side_effect=provider_side_effect) as provider:
            self.assertTrue(run_one())
        return provider

    def assert_kept_as_failed_input(self, job, error):
        self.assert_failed_unsent(job, error)
        self.assertEqual(self.recordings(), [Path(job.input_path).name])         # the recording is not discarded
        self.assertEqual(AuditEvent.objects.get(action="job.failed", target=str(job.pk)).details["billing"],
                         "not_processed")

    def test_no_check_runs_on_upload_and_a_clean_form_reaches_the_provider(self):
        template, version = self.stored_template(form())
        encounter = self.encounter(version)
        from documents import check_original
        with patch("documents.check_original", wraps=check_original) as checked:
            job = self.queued(self.dictate(encounter, "clean"), encounter)
        self.assertEqual(checked.call_count, 0)
        provider = self.process(job, NoProviderRequest("Synthetic stop after the guard."))
        self.assertEqual(provider.call_count, 1)

    def test_a_refused_form_fails_the_job_in_the_worker_and_keeps_the_recording(self):
        template, version = self.stored_template(p1_trigger("type"))
        encounter = self.encounter(version)
        job = self.queued(self.dictate(encounter, "refused"), encounter)
        provider = self.process(job)
        self.assertEqual(provider.call_count, 0)
        self.assert_kept_as_failed_input(job, "Not processed: " + REFUSED_JOB + NOT_SENT)

    def test_a_check_that_could_not_run_fails_the_job_and_keeps_the_recording(self):
        template, version = self.stored_template(form())
        encounter = self.encounter(version)
        with check_times_out():
            job = self.queued(self.dictate(encounter, "timeout"), encounter)
            provider = self.process(job)
        self.assertEqual(provider.call_count, 0)
        self.assert_kept_as_failed_input(job, "Not processed: " + UNCHECKED_JOB + NOT_SENT)

    def test_a_check_that_cannot_start_is_no_500_and_no_lost_recording(self):
        # GR-1 on the voice route: round 3 answered 500 and left the recording on disk with no audit.
        template, version = self.stored_template(form())
        encounter = self.encounter(version)
        with check_cannot_start():
            job = self.queued(self.dictate(encounter, "spawn"), encounter)
            provider = self.process(job)
        self.assertEqual(provider.call_count, 0)
        self.assert_kept_as_failed_input(job, "Not processed: " + UNCHECKED_JOB + NOT_SENT)

    def test_an_over_limit_approval_queues_without_a_check_and_the_worker_checks(self):
        template, version = self.stored_template(form())
        encounter = self.encounter(version)
        over = self.dictate(encounter, "over", env=EXPENSIVE_VOICE_ENV)
        self.assertEqual(over.status_code, 409)
        with check_times_out(), patch.dict(os.environ, EXPENSIVE_VOICE_ENV):
            approved = self.client.post("/encounters/%s/voice/approve/" % encounter.pk,
                                        {"approval": over.context["approval"], "decision": "approve"})
            self.assertEqual(approved.status_code, 302)
            job = Job.objects.get(encounter=encounter, kind="transcription")
            provider = self.process(job)
        self.assertEqual(provider.call_count, 0)
        self.assert_kept_as_failed_input(job, "Not processed: " + UNCHECKED_JOB + NOT_SENT)

    def test_the_retry_route_and_its_audit_rows_are_gone(self):
        template, version = self.stored_template(form())
        encounter = self.encounter(version)
        self.assertEqual(self.client.post("/encounters/%s/voice/retry/" % encounter.pk,
                                          {"retry": "x", "decision": "retry"}).status_code, 404)
        with check_times_out():
            self.dictate(encounter, "no-offer")
        self.assertFalse(AuditEvent.objects.filter(action__startswith="voice.check").exists())
