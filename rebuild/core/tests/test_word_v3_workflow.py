"""Contract v3 Word forms through the clinical workflow: upload, mapping review, confirmation, answers, export and
fixture-mode generation. Synthetic blank forms are built here; no patient data, no provider request."""

import hashlib
import io
from pathlib import Path
import tempfile
from zipfile import ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from docx import Document
from lxml import etree

from core.billing import welcome_credit
from core.models import AuditEvent, Department, Encounter, MappingConfirmation, Membership, Organization, Patient, Template, TemplateVersion, User
from core.security import private_path
from documents.test_word_v3 import _sdt
from .test_workflow import TEST_SETTINGS

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
V3 = dict(TEST_SETTINGS, QUILLMD_WORD_ENGINE="v3")


def build_intake_form(path):
    """One synthetic blank form with every v3 kind: header text, table cells, a date line, printed Yes/No boxes, a
    dropdown, check-all-that-apply boxes, a checkbox control, a log table, a signature and initials line."""
    doc = Document()
    doc.sections[0].header.paragraphs[0].text = "Patient name: ____________"
    doc.add_paragraph("Synthetic clinic intake")
    table = doc.add_table(rows=3, cols=2)
    table.cell(0, 0).text = "Referring physician"
    table.cell(1, 0).text = "Reason for visit"
    table.cell(2, 0).text = "Allergies"
    doc.add_paragraph("Date of visit: ____________")
    doc.add_paragraph("Smoker?  ☐ Yes  ☐ No")
    p = doc.add_paragraph("Laterality: ")
    p._p.append(_sdt("dropdown", options=["Choose an item.", "Left", "Right", "Bilateral"]))
    doc.add_paragraph("Symptoms (check all that apply): ☐ Pain ☐ Swelling ☐ Redness")
    p = doc.add_paragraph("Diabetes ")
    p._p.append(_sdt("checkbox"))
    doc.add_paragraph("Medications")
    meds = doc.add_table(rows=4, cols=3)
    meds.cell(0, 0).text = "Medication"
    meds.cell(0, 1).text = "Dose"
    meds.cell(0, 2).text = "Frequency"
    doc.add_paragraph("Clinician signature: ____________")
    doc.add_paragraph("Physician initials: ______")
    buffer = io.BytesIO()
    doc.save(buffer)
    Path(path).write_bytes(buffer.getvalue())
    return buffer.getvalue()


def build_questionnaire(rows, signatures=0):
    doc = Document()
    doc.add_paragraph("Synthetic long questionnaire")
    table = doc.add_table(rows=rows, cols=2)
    for i in range(rows):
        table.cell(i, 0).text = "Question %03d" % (i + 1)
    for i in range(signatures):
        doc.add_paragraph("Clinician signature: ____________" if i % 2 == 0 else "Physician initials: ______")
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def build_legacy_table_form():
    doc = Document()
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Allergies"
    table.cell(1, 0).text = "Plan"
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def part_text(data, part="word/document.xml"):
    with ZipFile(io.BytesIO(data)) as z:
        root = etree.fromstring(z.read(part))
    return "".join(t.text or "" for t in root.iter("{%s}t" % W))


class V3Fixture:
    """A department with an owner-clinician, a manager and an employee, one synthetic patient, private storage."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="quillmd-v3-http-")
        self.addCleanup(self.directory.cleanup)
        self.override = override_settings(MEDIA_ROOT=Path(self.directory.name) / "private")
        self.override.enable()
        self.addCleanup(self.override.disable)
        organization = Organization.objects.create(name="Synthetic v3 practice")
        self.department = Department.objects.create(organization=organization, name="Synthetic intake clinic")
        self.user = self.person("v3-clinician", "Alpha", "clinician")
        self.manager = self.person("v3-manager", "Beta", "manager")
        self.employee = self.person("v3-employee", "Gamma", "employee")
        welcome_credit(self.user)
        self.patient = Patient.objects.create(department=self.department, display_name="SYNTHETIC V3 PATIENT",
                                              reference="SYNTHETIC-V3", created_by=self.user)
        self.client.force_login(self.user)
        self.original = build_intake_form(Path(self.directory.name) / "intake.docx")

    def person(self, name, last, role):
        user = User.objects.create_user(username=name, email=f"{name}@synthetic.invalid", first_name="Synthetic",
                                        last_name=last + " Clinician", verified_at=timezone.now())
        Membership.objects.create(user=user, department=self.department, role=role)
        return user

    def upload(self, data=None, name="Synthetic v3 intake"):
        return self.client.post("/templates/upload/", {"name": name, "department": self.department.pk,
                                "synthetic_only": "on", "file": SimpleUploadedFile("intake.docx", data or self.original)})

    def uploaded(self, **kwargs):
        response = self.upload(**kwargs)
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context["form"].errors)
        template = Template.objects.get(name=kwargs.get("name", "Synthetic v3 intake"))
        return template, template.versions.get(number=1)

    def by_label(self, version):
        return {f["label"]: f for f in version.fields}

    def latest(self, template):
        return template.versions.order_by("-number").first()

    def confirm(self, template, version=None):
        version = version or self.latest(template)
        response = self.client.post(f"/templates/{template.pk}/", {"action": "v3_confirm", "mapping_version": version.pk,
                                                                   "checked_every_field": "on"})
        self.assertEqual(response.status_code, 302)
        return TemplateVersion.objects.get(pk=version.pk)

    def new_encounter(self, version, notes="Referring physician: Dr Example"):
        return self.client.post("/encounters/new/", {"patient": self.patient.pk, "template_version": version.pk,
                                "notes": notes, "service_date": timezone.localdate().isoformat(), "synthetic_only": "on"})


@override_settings(**V3)
class V3Upload(V3Fixture, TestCase):
    def test_upload_follows_the_engine_setting_and_records_the_contract(self):
        template, version = self.uploaded()
        self.assertEqual(version.contract, "v3")
        self.assertTrue(all(f["locator"]["contract"] == "v3" for f in version.fields))
        by = self.by_label(version)
        self.assertEqual(by["Smoker?"]["kind"], "choice")
        self.assertEqual(by["Laterality"]["options"], ["Left", "Right", "Bilateral"])
        self.assertEqual(by["Symptoms (check all that apply)"]["kind"], "multi_choice")
        self.assertEqual(by["Diabetes"]["kind"], "checkbox")
        self.assertEqual({f["kind"] for f in version.fields if f["kind"] in ("signature", "initials", "table_rows")},
                         {"signature", "initials", "table_rows"})
        self.assertIsNone(version.confirmed)
        self.assertEqual(version.document_backend, {}, "a v3 mapping must never look like the qualified WM form")
        event = AuditEvent.objects.get(action="template.upload", target=str(template.pk))
        self.assertEqual(event.details["contract"], "v3")

    @override_settings(QUILLMD_WORD_ENGINE="legacy")
    def test_the_legacy_setting_keeps_the_legacy_contract(self):
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Template.objects.exists())
        legacy = self.upload(data=build_legacy_table_form(), name="Synthetic legacy table")
        self.assertEqual(legacy.status_code, 302)
        version = Template.objects.get(name="Synthetic legacy table").versions.get()
        self.assertEqual(version.contract, "")
        self.assertFalse(version.needs_confirmation)

    def test_more_than_100_answerable_areas_is_refused_whole_with_the_count(self):
        response = self.upload(data=build_questionnaire(101))
        self.assertEqual(response.status_code, 200)
        errors = " ".join(response.context["form"].non_field_errors())
        self.assertIn("101 answer areas", errors)
        self.assertIn("at most 100", errors)
        self.assertIn("nothing was dropped", errors)
        self.assertFalse(Template.objects.exists())
        originals = Path(self.directory.name) / "private" / "originals"
        self.assertEqual(list(originals.glob("*")) if originals.exists() else [], [], "a refused upload is not kept")

    def test_signature_and_initials_areas_do_not_count_toward_the_limit(self):
        template, version = self.uploaded(data=build_questionnaire(100, signatures=2), name="Synthetic 100")
        self.assertEqual(len(version.fields), 102)
        self.assertEqual(sum(1 for f in version.fields if f["kind"] not in ("signature", "initials")), 100)


@override_settings(**V3)
class V3MappingReview(V3Fixture, TestCase):
    def setUp(self):
        super().setUp()
        self.template, self.version = self.uploaded()

    def post(self, data, version=None):
        return self.client.post(f"/templates/{self.template.pk}/", {"mapping_version": (version or self.latest(self.template)).pk, **data})

    def test_the_review_lists_every_field_in_document_order_with_its_details(self):
        response = self.client.get(f"/templates/{self.template.pk}/")
        self.assertEqual(response.status_code, 200)
        rows = response.context["v3_rows"]
        self.assertEqual([row["key"] for row in rows], [f["key"] for f in self.version.fields])
        self.assertEqual([row["number"] for row in rows], list(range(1, len(rows) + 1)))
        by = {row["field"]["label"]: row for row in rows}
        self.assertTrue(by["Referring physician"]["kind_editable"])
        self.assertFalse(by["Laterality"]["kind_editable"])
        self.assertEqual(by["Laterality"]["options"], ["Left", "Right", "Bilateral"])
        self.assertIn("Header", by["Patient name"]["location"])
        self.assertIn("Body", by["Referring physician"]["location"])
        self.assertEqual(by["Patient name"]["max_chars"], 120)
        self.assertEqual({row["origin"] for row in rows}, {"Automatic"})
        body = response.content.decode()
        self.assertIn("Not an answer &mdash; remove", body)
        self.assertIn("Not yet confirmed", body)
        self.assertNotIn("Use this form", body, "an unconfirmed mapping offers no way to start a document")

    def test_the_add_list_excludes_mapped_places_and_is_searchable(self):
        places = self.client.get(f"/templates/{self.template.pk}/").context["places"]
        slots = {row["slot"] for row in places}
        self.assertIn("word/document.xml#b/p[0]", slots)                      # "Synthetic clinic intake"
        for field in self.version.fields:
            anchor = field["locator"]["part"] + "#" + field["locator"]["slot"]
            self.assertNotIn(anchor, slots)
        self.assertNotIn("word/document.xml#b/tbl[0]/tr[0]/tc[1]/p[0]", slots, "inside a mapped cell")
        self.assertNotIn("word/document.xml#b/p[3]", slots, "holds a mapped dropdown")
        found = self.client.get(f"/templates/{self.template.pk}/?find=clinic intake").context["places"]
        self.assertEqual([row["slot"] for row in found], ["word/document.xml#b/p[0]"])

    def test_rename_kind_change_and_remove_make_a_version_with_recorded_corrections(self):
        by = self.by_label(self.version)
        response = self.post({"action": "v3_save", "label_" + by["Allergies"]["key"]: "Known allergies",
                              "kind_" + by["Referring physician"]["key"]: "long_text",
                              "remove_" + by["Reason for visit"]["key"]: "on"})
        self.assertEqual(response.status_code, 302)
        latest = self.latest(self.template)
        self.assertEqual(latest.number, 2)
        self.assertEqual(latest.contract, "v3")
        new = {f["key"]: f for f in latest.fields}
        self.assertEqual(new[by["Allergies"]["key"]]["label"], "Known allergies")
        self.assertEqual(new[by["Referring physician"]["key"]]["kind"], "long_text")
        self.assertNotIn(by["Reason for visit"]["key"], new)
        self.assertEqual(len(latest.fields), len(self.version.fields) - 1)
        self.assertEqual(latest.corrections, {
            "base_version": 1, "added": [],
            "removed": [{"key": by["Reason for visit"]["key"], "label": "Reason for visit", "kind": "long_text", "origin": "automatic"}],
            "kind_changed": {by["Referring physician"]["key"]: ["text", "long_text"]},
            "renamed": [{"key": by["Allergies"]["key"], "from": "Allergies", "to": "Known allergies"}]})
        # Locators are the engine's, untouched; only label and kind change.
        self.assertEqual(new[by["Allergies"]["key"]]["locator"], by["Allergies"]["locator"])
        event = AuditEvent.objects.get(action="template.mapping_version", target=str(latest.pk))
        self.assertEqual(event.details["removed"], [by["Reason for visit"]["key"]])
        self.assertEqual(event.details["renamed"], [by["Allergies"]["key"]])
        self.version.refresh_from_db()
        self.assertEqual(self.version.fields, Template.objects.get(pk=self.template.pk).versions.get(number=1).fields)
        self.assertIsNone(latest.confirmed, "a corrected mapping needs its own confirmation")
        page = self.client.get(f"/templates/{self.template.pk}/").content.decode()
        self.assertIn("Corrections recorded for version 2", page)
        self.assertIn("Renamed: &ldquo;Allergies&rdquo; to &ldquo;Known allergies&rdquo;", page)
        self.assertIn("Removed (not an answer): Reason for visit", page)

    def test_only_text_like_kinds_change_into_one_another(self):
        by = self.by_label(self.version)
        response = self.post({"action": "v3_save", "kind_" + by["Laterality"]["key"]: "text"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("keeps its kind", response.context["v3_error"])
        response = self.post({"action": "v3_save", "kind_" + by["Referring physician"]["key"]: "choice"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.template.versions.count(), 1)

    def test_a_signature_question_keeps_its_signature_label(self):
        by = self.by_label(self.version)
        response = self.post({"action": "v3_save", "label_" + by["Clinician signature"]["key"]: "Attending"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("keeps a signature label", response.context["v3_error"])
        self.assertEqual(self.template.versions.count(), 1)

    def test_a_missed_field_is_added_as_manual_in_document_order(self):
        response = self.post({"action": "v3_add", "slot": "word/document.xml#b/p[0]", "kind": "text", "label": "Clinic"})
        self.assertEqual(response.status_code, 302)
        latest = self.latest(self.template)
        added = latest.fields[0]
        self.assertEqual((added.get("label"), added.get("kind"), added.get("origin")), ("Clinic", "text", "manual"),
                         "the added paragraph comes first in the document, so it is field 1")
        self.assertTrue(added["key"].startswith("m3_"))
        self.assertEqual(latest.fields[1:], self.version.fields)
        self.assertEqual(latest.corrections, {"base_version": 1, "added": [added["key"]], "removed": [],
                                              "kind_changed": {}, "renamed": []})
        rows = self.client.get(f"/templates/{self.template.pk}/").context["v3_rows"]
        self.assertEqual(rows[0]["origin"], "Manual")

    def test_a_place_that_already_belongs_to_a_field_is_refused(self):
        response = self.post({"action": "v3_add", "slot": "word/document.xml#b/tbl[0]/tr[0]/tc[1]", "kind": "text",
                              "label": "Referrer again"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("already belongs to a field", response.context["v3_error"])
        self.assertEqual(self.template.versions.count(), 1)

    def test_printed_options_need_a_dropdown_place(self):
        response = self.post({"action": "v3_add", "slot": "word/document.xml#b/p[0]", "kind": "choice", "label": "Clinic"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("needs a Word dropdown", response.context["v3_error"])
        self.assertEqual(self.template.versions.count(), 1)

    def test_a_stale_page_saves_nothing(self):
        by = self.by_label(self.version)
        self.assertEqual(self.post({"action": "v3_save", "label_" + by["Allergies"]["key"]: "Known allergies"}).status_code, 302)
        stale = self.post({"action": "v3_save", "label_" + by["Allergies"]["key"]: "Allergy list"}, version=self.version)
        self.assertEqual(stale.status_code, 409)
        added = self.post({"action": "v3_add", "slot": "word/document.xml#b/p[0]", "kind": "text", "label": "Clinic"},
                          version=self.version)
        self.assertEqual(added.status_code, 409)
        self.assertEqual(self.template.versions.count(), 2)
        self.assertEqual(self.by_label(self.latest(self.template))["Known allergies"]["key"], by["Allergies"]["key"])


@override_settings(**V3)
class V3Confirmation(V3Fixture, TestCase):
    def setUp(self):
        super().setUp()
        self.template, self.version = self.uploaded()

    def test_an_unconfirmed_mapping_cannot_start_a_document(self):
        response = self.new_encounter(self.version)
        self.assertEqual(response.status_code, 200)
        errors = " ".join(response.context["form"].non_field_errors())
        self.assertIn("has not been confirmed", errors)
        self.assertFalse(Encounter.objects.exists())

    def test_a_clinician_confirms_and_who_and_when_are_recorded(self):
        before = timezone.now()
        version = self.confirm(self.template)
        self.assertEqual(version.confirmed.confirmed_by, self.user)
        self.assertGreaterEqual(version.confirmed.created_at, before)
        event = AuditEvent.objects.get(action="template.mapping_confirmed", target=str(version.pk))
        self.assertEqual(event.details["number"], 1)
        page = self.client.get(f"/templates/{self.template.pk}/").content.decode()
        self.assertIn("was confirmed by v3-clinician@synthetic.invalid", page)
        self.assertIn("Use this form", page)
        self.assertEqual(self.new_encounter(version).status_code, 302)
        self.assertEqual(Encounter.objects.get().template_version, version)

    def test_confirmation_needs_the_explicit_statement_and_a_clinician(self):
        response = self.client.post(f"/templates/{self.template.pk}/", {"action": "v3_confirm", "mapping_version": self.version.pk})
        self.assertEqual(response.status_code, 400)
        for other in (self.employee, self.manager):
            self.client.force_login(other)
            response = self.client.post(f"/templates/{self.template.pk}/", {"action": "v3_confirm",
                                        "mapping_version": self.version.pk, "checked_every_field": "on"})
            self.assertEqual(response.status_code, 403)
        self.assertFalse(MappingConfirmation.objects.exists())

    def test_a_corrected_mapping_needs_a_new_confirmation(self):
        self.confirm(self.template)
        by = self.by_label(self.version)
        self.client.post(f"/templates/{self.template.pk}/", {"action": "v3_save", "mapping_version": self.version.pk,
                                                             "label_" + by["Allergies"]["key"]: "Known allergies"})
        latest = self.latest(self.template)
        self.assertEqual(latest.number, 2)
        self.assertTrue(latest.needs_confirmation)
        self.assertEqual(self.new_encounter(latest).status_code, 200)
        self.assertEqual(self.new_encounter(self.version).status_code, 302, "the confirmed version stays usable")

    def test_a_mapping_with_no_fields_cannot_be_confirmed(self):
        removal = {"remove_" + f["key"]: "on" for f in self.version.fields}
        self.client.post(f"/templates/{self.template.pk}/", {"action": "v3_save", "mapping_version": self.version.pk, **removal})
        empty = self.latest(self.template)
        self.assertEqual((empty.number, empty.fields), (2, []))
        response = self.client.post(f"/templates/{self.template.pk}/", {"action": "v3_confirm", "mapping_version": empty.pk,
                                                                        "checked_every_field": "on"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("no fields", response.context["v3_error"])
        self.assertFalse(MappingConfirmation.objects.exists())

    def test_the_legacy_label_editor_cannot_bypass_the_recorded_review(self):
        labels = {f["key"]: f["label"] + " renamed" for f in self.version.fields if f["kind"] not in ("signature", "initials")}
        response = self.client.post(f"/templates/{self.template.pk}/", {"mapping_version": self.version.pk,
                                    "labels": __import__("json").dumps(labels)})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.template.versions.count(), 1)

    def test_a_stale_page_cannot_confirm_the_newer_version(self):
        by = self.by_label(self.version)
        self.client.post(f"/templates/{self.template.pk}/", {"action": "v3_save", "mapping_version": self.version.pk,
                                                             "label_" + by["Allergies"]["key"]: "Known allergies"})
        response = self.client.post(f"/templates/{self.template.pk}/", {"action": "v3_confirm",
                                    "mapping_version": self.version.pk, "checked_every_field": "on"})
        self.assertEqual(response.status_code, 409, "the page showed version 1; version 2 was never shown")
        self.assertIn("This mapping changed after you opened it", response.context["v3_error"])
        self.assertFalse(MappingConfirmation.objects.exists())

    def test_an_employee_can_neither_correct_nor_add(self):
        by = self.by_label(self.version)
        self.client.force_login(self.employee)
        saved = self.client.post(f"/templates/{self.template.pk}/", {"action": "v3_save", "mapping_version": self.version.pk,
                                                                     "remove_" + by["Reason for visit"]["key"]: "on"})
        added = self.client.post(f"/templates/{self.template.pk}/", {"action": "v3_add", "mapping_version": self.version.pk,
                                 "slot": "word/document.xml#b/p[0]", "kind": "text", "label": "Clinic"})
        self.assertEqual((saved.status_code, added.status_code), (403, 403))
        self.assertEqual(self.template.versions.count(), 1)

    def test_a_confirmation_is_append_only_in_the_model_and_in_the_database(self):
        from django.core.exceptions import ValidationError
        from django.db import DatabaseError, transaction
        confirmation = MappingConfirmation.objects.create(version=self.version, confirmed_by=self.user)
        confirmation.confirmed_by = self.manager
        for act in (confirmation.save, confirmation.delete):
            try:
                with transaction.atomic():
                    act()
            except ValidationError:
                continue                    # refused by the model, before any SQL
            except DatabaseError:
                self.fail("the model let a change to a confirmation reach the database (%s)" % act.__name__)
            self.fail("a confirmation was changed (%s)" % act.__name__)
        for write in (lambda: MappingConfirmation.objects.filter(pk=confirmation.pk).update(confirmed_by=self.manager),
                      lambda: MappingConfirmation.objects.filter(pk=confirmation.pk).delete()):
            with self.assertRaises(DatabaseError), transaction.atomic():
                write()
        stored = MappingConfirmation.objects.get(pk=confirmation.pk)
        self.assertEqual(stored.confirmed_by, self.user)

    @override_settings(QUILLMD_WORD_ENGINE="legacy")
    def test_legacy_templates_need_no_confirmation(self):
        legacy = self.upload(data=build_legacy_table_form(), name="Synthetic legacy table")
        self.assertEqual(legacy.status_code, 302)
        version = Template.objects.get(name="Synthetic legacy table").versions.get()
        self.assertEqual(self.new_encounter(version, notes="Allergies: none documented").status_code, 302)


class V3EncounterFixture(V3Fixture):
    """A confirmed v3 mapping and one draft encounter on it."""

    def setUp(self):
        super().setUp()
        self.template, self.version = self.uploaded()
        self.version = self.confirm(self.template)
        self.assertEqual(self.new_encounter(self.version).status_code, 302)
        self.encounter = Encounter.objects.get()
        self.by = self.by_label(self.version)

    def key(self, label):
        return self.by[label]["key"]

    def answers_payload(self, values, reviewed=True):
        payload = {"revision": Encounter.objects.get(pk=self.encounter.pk).revision}
        for field in self.version.fields:
            if field["kind"] in ("signature", "initials"):
                continue
            if field["label"] in values:
                payload["answer_" + field["key"]] = values[field["label"]]
            if reviewed:
                payload["reviewed_" + field["key"]] = "on"
        return payload

    def save(self, values, reviewed=True, extra=None):
        return self.client.post(f"/encounters/{self.encounter.pk}/save/", {**self.answers_payload(values, reviewed), **(extra or {})})

    def stored(self, label):
        return Encounter.objects.get(pk=self.encounter.pk).answers[self.key(label)]["text"]

    FULL = {"Patient name": "Synthetic Person", "Referring physician": "Dr Example", "Reason for visit": "Knee pain",
            "Allergies": "None documented", "Date of visit": "03/14/2026", "Smoker?": "Yes", "Laterality": "Left",
            "Symptoms (check all that apply)": ["Redness", "Pain"], "Diabetes": "checked",
            "Table": "Aspirin | 81 mg | daily\nMetformin | 500 mg | twice daily"}

    def finalize(self):
        return self.client.post(f"/encounters/{self.encounter.pk}/finalize/",
                                {"revision": Encounter.objects.get(pk=self.encounter.pk).revision, "reviewed": "on"}, follow=True)


@override_settings(**V3)
class V3Answers(V3EncounterFixture, TestCase):
    def test_the_review_page_asks_for_each_kind_in_its_own_way(self):
        response = self.client.get(f"/encounters/{self.encounter.pk}/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        rows = {row["label"]: row for row in response.context["answer_rows"]}
        self.assertEqual(rows["Laterality"]["v3_input"], "select")
        self.assertIn(f'<select id="answer-{self.key("Laterality")}" name="answer_{self.key("Laterality")}" data-v3-choice>', body)
        for option in ("Left", "Right", "Bilateral"):
            self.assertIn(f'<option value="{option}" >{option}</option>', body)
        self.assertEqual(body.count(f'name="answer_{self.key("Symptoms (check all that apply)")}"'), 3)
        self.assertIn(f'name="answer_{self.key("Diabetes")}" value="checked" data-v3-checkbox', body)
        self.assertIn("in this order: Medication | Dose | Frequency", body)
        self.assertEqual(body.count("Signed by hand on the printed form &mdash; never filled."), 2)
        self.assertNotIn(f'name="answer_{self.key("Clinician signature")}"', body)
        self.assertNotIn(f'name="reviewed_{self.key("Clinician signature")}"', body)
        self.assertNotIn(f'name="blank_{self.key("Physician initials")}"', body, "nothing to leave blank in a hand-signed area")
        self.assertIn(f'name="blank_{self.key("Allergies")}"', body)
        self.assertIn(f'name="answer_{self.key("Patient name")}" rows="4" maxlength="120"', body)

    def test_each_kind_is_saved_in_its_text_form(self):
        response = self.save(dict(self.FULL, **{"Smoker?": "yes"}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.stored("Smoker?"), "Yes", "a printed option is stored as printed")
        self.assertEqual(self.stored("Laterality"), "Left")
        self.assertEqual(self.stored("Symptoms (check all that apply)"), "Pain\nRedness", "one option per line, printed order")
        self.assertEqual(self.stored("Diabetes"), "checked")
        self.assertEqual(self.stored("Table"), "Aspirin | 81 mg | daily\nMetformin | 500 mg | twice daily")
        self.assertEqual(self.stored("Date of visit"), "03/14/2026", "dates are kept as typed")
        unticked = self.save({"Diabetes": ""})
        self.assertEqual(unticked.status_code, 302)
        self.assertEqual(self.stored("Diabetes"), "")

    def refused(self, values, *expected):
        before = Encounter.objects.get(pk=self.encounter.pk)
        response = self.save(values)
        self.assertEqual(response.status_code, 400)
        body = response.content.decode()
        for text in expected:
            self.assertIn(text, body)
        after = Encounter.objects.get(pk=self.encounter.pk)
        self.assertEqual((after.revision, after.answers), (before.revision, before.answers), "nothing was saved")

    def test_an_option_not_printed_on_the_form_is_refused_naming_the_question(self):
        self.refused({"Smoker?": "Former"}, "&quot;Smoker?&quot;", "not one of the printed options", "Nothing was saved.")
        self.refused({"Laterality": "Left and right"}, "&quot;Laterality&quot;", "not one of the printed options")
        self.refused({"Symptoms (check all that apply)": ["Pain", "Fever"]}, "&quot;Symptoms (check all that apply)&quot;",
                     "&quot;Fever&quot; is not one of the printed options")

    def test_a_checkbox_takes_only_its_ticked_form(self):
        self.refused({"Diabetes": "yes"}, "&quot;Diabetes&quot; is a checkbox")

    def test_an_answer_longer_than_its_space_is_refused(self):
        self.refused({"Patient name": "X" * 121}, "&quot;Patient name&quot;", "at most 120 characters", "this answer has 121")
        self.assertEqual(self.save({"Patient name": "X" * 120}).status_code, 302)

    def test_table_rows_are_checked_against_the_columns(self):
        self.refused({"Table": "Aspirin | 81 mg | daily | extra"}, "&quot;Table&quot;, row 1: 4 cells",
                     "3 columns (Medication | Dose | Frequency)")

    def test_a_hand_signed_area_takes_no_answer(self):
        payload = self.answers_payload({})
        payload["answer_" + self.key("Clinician signature")] = "Synthetic Alpha Clinician"
        response = self.client.post(f"/encounters/{self.encounter.pk}/save/", payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("signed by hand on the printed form", response.content.decode())


@override_settings(**V3)
class V3Export(V3EncounterFixture, TestCase):
    def test_finalize_writes_every_kind_and_copies_every_other_part(self):
        self.assertEqual(self.save(self.FULL).status_code, 302)
        response = self.finalize()
        encounter = Encounter.objects.get(pk=self.encounter.pk)
        self.assertEqual(encounter.status, "finalized", [str(m) for m in response.context["messages"]])
        exported = private_path(encounter.export_path).read_bytes()
        self.assertEqual(hashlib.sha256(exported).hexdigest(), encounter.export_sha256)
        body = part_text(exported)
        for text in ("Dr Example", "Knee pain", "None documented", "Date of visit: 03/14/2026", "Smoker?  ☒ Yes  ☐ No",
                     "Laterality: Left", "☒ Pain ☐ Swelling ☒ Redness", "Diabetes ☒", "Aspirin81 mgdaily",
                     "Metformin500 mgtwice daily", "Clinician signature: ____________", "Physician initials: ______"):
            self.assertIn(text, body)
        self.assertIn("Patient name: Synthetic Person", part_text(exported, "word/header1.xml"))
        with ZipFile(io.BytesIO(self.original)) as before, ZipFile(io.BytesIO(exported)) as after:
            self.assertEqual([i.filename for i in before.infolist()], [i.filename for i in after.infolist()])
            changed = {"word/document.xml", "word/header1.xml"}
            for name in before.namelist():
                if name not in changed:
                    self.assertEqual(before.read(name), after.read(name), name)
        download = self.client.get(f"/encounters/{self.encounter.pk}/export/")
        self.assertEqual(b"".join(download.streaming_content), exported)
        page = self.client.get(f"/encounters/{self.encounter.pk}/").content.decode()
        self.assertIn("Box exported ticked.", page)
        self.assertIn("Signed by hand on the printed form; never filled.", page)

    def test_signed_areas_need_no_review_but_every_other_field_does(self):
        self.assertEqual(self.save(self.FULL, reviewed=False).status_code, 302)
        self.assertEqual(self.save(self.FULL, extra={}).status_code, 302)
        self.assertEqual(self.finalize().status_code, 200)
        self.assertEqual(Encounter.objects.get(pk=self.encounter.pk).status, "finalized")

    def test_an_unreviewed_field_still_blocks_finalization(self):
        payload = self.answers_payload(self.FULL)
        payload.pop("reviewed_" + self.key("Laterality"))
        self.assertEqual(self.client.post(f"/encounters/{self.encounter.pk}/save/", payload).status_code, 302)
        response = self.finalize()
        self.assertNotEqual(Encounter.objects.get(pk=self.encounter.pk).status, "finalized")
        self.assertIn("Not yet reviewed: Laterality.", " ".join(str(m) for m in response.context["messages"]))

    def test_finalization_re_reads_every_stored_answer(self):
        self.assertEqual(self.save(self.FULL).status_code, 302)
        encounter = Encounter.objects.get(pk=self.encounter.pk)
        answers = dict(encounter.answers)
        answers[self.key("Smoker?")] = {**answers[self.key("Smoker?")], "text": "Former"}
        Encounter.objects.filter(pk=encounter.pk).update(answers=answers)
        response = self.finalize()
        self.assertNotEqual(Encounter.objects.get(pk=self.encounter.pk).status, "finalized")
        self.assertIn('"Smoker?": "Former" is not one of the printed options',
                      " ".join(str(m) for m in response.context["messages"]))

    def test_a_stale_anchor_is_refused_with_the_engine_message(self):
        fields = [dict(f) for f in self.version.fields]
        for f in fields:
            if f["label"] == "Referring physician":
                f["locator"] = {**f["locator"], "fingerprint": "0" * 64}
        stale = TemplateVersion.objects.create(template=self.template, number=2, fields=fields, contract="v3",
                                               corrections={"base_version": 1}, created_by=self.user)
        MappingConfirmation.objects.create(version=stale, confirmed_by=self.user)
        Encounter.objects.all().delete()
        self.assertEqual(self.new_encounter(stale).status_code, 302)
        self.encounter = Encounter.objects.get()
        self.version = stale
        self.assertEqual(self.save(self.FULL).status_code, 302)
        response = self.finalize()
        self.assertNotEqual(Encounter.objects.get(pk=self.encounter.pk).status, "finalized")
        self.assertIn("The stored mapping no longer matches this form. Review the mapping again.",
                      " ".join(str(m) for m in response.context["messages"]))


@override_settings(**V3)
class V3Generation(V3EncounterFixture, TestCase):
    """Fixture-mode generation through the worker: text kinds as before; options only when named exactly."""

    def generate(self, notes):
        from core.jobs import enqueue, run_one
        encounter = Encounter.objects.get(pk=self.encounter.pk)
        saved = self.client.post(f"/encounters/{encounter.pk}/notes/", {"revision": encounter.revision, "notes": notes})
        self.assertEqual(saved.status_code, 302)
        job = enqueue(Encounter.objects.get(pk=encounter.pk), self.user)
        self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(job.state, "succeeded", job.error)
        return Encounter.objects.get(pk=encounter.pk).answers

    def answer(self, answers, label):
        return answers[self.key(label)]

    def test_an_option_is_filled_only_when_its_labelled_value_names_it_exactly(self):
        answers = self.generate("Referring physician: Dr Example\nSmoker: yes\nLaterality: LEFT\n"
                                "Symptoms (check all that apply): Pain\nDiabetes: present")
        expected = {"Referring physician": "Dr Example", "Smoker?": "Yes", "Laterality": "Left",
                    "Symptoms (check all that apply)": "Pain", "Diabetes": "checked"}
        for label, text in expected.items():
            self.assertEqual((self.answer(answers, label)["status"], self.answer(answers, label)["text"]), ("supported", text), label)

    def test_anything_else_is_held_for_the_clinician_with_its_quote(self):
        candidates = {"Smoker?": "former smoker", "Laterality": "left side",
                      "Symptoms (check all that apply)": "Pain, Redness", "Diabetes": "no"}
        answers = self.generate("Smoker: former smoker\nLaterality: left side\n"
                                "Symptoms (check all that apply): Pain, Redness\nDiabetes: no")
        for label, candidate in candidates.items():
            answer = self.answer(answers, label)
            self.assertEqual((answer["status"], answer["text"]), ("conflict", ""), label)
            self.assertEqual(answer["held_candidate"]["text"], candidate, label)
            self.assertEqual([e["quote"] for e in answer["held_candidate"]["evidence"]], [candidate], label)
            self.assertIn("NOT used as an answer", answer["held_candidate"]["reason"])
        page = self.client.get(f"/encounters/{self.encounter.pk}/").content.decode()
        self.assertIn("Read from the notes &mdash; not offered as an answer.", page)
        self.assertIn("left side", page)
        self.assertIn("An empty box is never read as No.", page)

    def test_absence_is_never_turned_into_no(self):
        answers = self.generate("Referring physician: Dr Example")
        for label in ("Smoker?", "Laterality", "Symptoms (check all that apply)", "Diabetes"):
            self.assertEqual((self.answer(answers, label)["status"], self.answer(answers, label)["text"]), ("missing", ""), label)

    def test_table_rows_signature_and_initials_are_never_generated(self):
        answers = self.generate("Referring physician: Dr Example\nTable: Aspirin | 81 mg | daily\n"
                                "Clinician signature: Synthetic Alpha Clinician\nPhysician initials: SAC")
        for label in ("Table", "Clinician signature", "Physician initials"):
            answer = self.answer(answers, label)
            self.assertEqual((answer["status"], answer["text"], answer["evidence"]), ("missing", "", []), label)
        self.assertIn("never generated", self.answer(answers, "Table")["reason"])
        self.assertEqual(self.answer(answers, "Referring physician")["text"], "Dr Example",
                         "their labelled lines are still read as labelled, so the note stays fully labelled")

    def test_an_offer_on_an_option_question_names_a_printed_option_or_is_held(self):
        answers = self.generate("Smoker: yes\nLaterality: left side\nPatient seen today.")
        smoker, laterality = self.answer(answers, "Smoker?"), self.answer(answers, "Laterality")
        self.assertEqual((smoker["status"], smoker["text"], smoker.get("suggestion")), ("conflict", "", "Yes"))
        self.assertNotIn("suggestion", laterality, "a value that names no printed option is never one click away")
        self.assertEqual(laterality["held_candidate"]["text"], "left side")

    def test_a_held_option_is_the_clinicians_decision_and_is_exported(self):
        self.generate("Referring physician: Dr Example\nLaterality: left side")
        page = self.client.get(f"/encounters/{self.encounter.pk}/").content.decode()
        self.assertIn(f'name="held_shown_{self.key("Laterality")}" value="1"', page)
        values = dict(self.FULL, Laterality="Left")
        self.assertEqual(self.save(values, extra={"held_shown_" + self.key("Laterality"): "1"}).status_code, 302)
        self.assertEqual(self.stored("Laterality"), "Left")
        response = self.finalize()
        encounter = Encounter.objects.get(pk=self.encounter.pk)
        self.assertEqual(encounter.status, "finalized", [str(m) for m in response.context["messages"]])
        self.assertIn("Laterality: Left", part_text(private_path(encounter.export_path).read_bytes()))


def prechecked_form_bytes():
    from documents.test_word_v3 import ticked_sdt_checkbox
    doc = Document()
    doc.add_paragraph("Synthetic procedure checklist")
    doc.add_paragraph("Indication: ____________")
    doc.add_paragraph("Consent obtained ")._p.append(ticked_sdt_checkbox())
    doc.add_paragraph("History reviewed today.")
    doc.add_paragraph("Hypertension ☒")
    doc.add_paragraph("Medication list reviewed.")
    doc.add_paragraph("Smoker?  ☐ Yes  ☒ No")
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


@override_settings(**V3)
class V3PrintedTicks(V3Fixture, TestCase):
    """F3 end to end: what the page says the export does is what the export does."""

    def setUp(self):
        super().setUp()
        self.template, version = self.uploaded(data=prechecked_form_bytes(), name="Synthetic checklist")
        self.version = self.confirm(self.template)
        self.by = self.by_label(self.version)
        self.assertEqual(self.new_encounter(self.version, notes="Indication: synthetic").status_code, 302)
        self.encounter = Encounter.objects.get()

    def save(self, values):
        payload = {"revision": Encounter.objects.get(pk=self.encounter.pk).revision}
        for f in self.version.fields:
            if f["label"] in values:
                payload["answer_" + f["key"]] = values[f["label"]]
            payload["reviewed_" + f["key"]] = "on"
        self.assertEqual(self.client.post(f"/encounters/{self.encounter.pk}/save/", payload).status_code, 302)

    def finalized_export(self):
        response = self.client.post(f"/encounters/{self.encounter.pk}/finalize/",
                                    {"revision": Encounter.objects.get(pk=self.encounter.pk).revision, "reviewed": "on"}, follow=True)
        encounter = Encounter.objects.get(pk=self.encounter.pk)
        self.assertEqual(encounter.status, "finalized", [str(m) for m in response.context["messages"]])
        return private_path(encounter.export_path).read_bytes()

    def test_boxes_left_unticked_are_exported_unticked_and_an_unanswered_choice_stays_as_printed(self):
        self.assertEqual(self.by["Smoker?"]["printed_ticked"], [1])
        page = self.client.get(f"/encounters/{self.encounter.pk}/").content.decode()
        self.assertIn("Ticked here, the box is exported ticked; left unticked, it is exported unticked, although the "
                      "blank form prints it ticked.", page)
        self.assertIn("With no option chosen, the form keeps what it prints: No ticked.", page)
        self.save({"Indication": "synthetic"})
        exported = self.finalized_export()
        text = part_text(exported)
        self.assertIn("Consent obtained ☐", text)
        self.assertIn("Hypertension ☐", text)
        self.assertIn("Smoker?  ☐ Yes  ☒ No", text, "an unanswered choice keeps what the form prints")
        with ZipFile(io.BytesIO(exported)) as z:
            root = etree.fromstring(z.read("word/document.xml"))
        self.assertEqual([c.get("{http://schemas.microsoft.com/office/word/2010/wordml}val")
                          for c in root.iter("{http://schemas.microsoft.com/office/word/2010/wordml}checked")], ["0"])
        page = self.client.get(f"/encounters/{self.encounter.pk}/").content.decode()
        self.assertEqual(page.count("Box exported unticked."), 2)
        self.assertIn("No option chosen; the form keeps what it prints: No ticked.", page)

    def test_a_chosen_option_unticks_the_printed_one(self):
        self.save({"Indication": "synthetic", "Smoker?": "Yes", "Hypertension": "checked"})
        text = part_text(self.finalized_export())
        self.assertIn("Smoker?  ☒ Yes  ☐ No", text)
        self.assertIn("Hypertension ☒", text)
        self.assertIn("Consent obtained ☐", text)


@override_settings(**V3)
class V3ControlCells(V3Fixture, TestCase):
    """R2 end to end: a checklist whose boxes are checkbox controls in cells. The page names the box the blank form
    prints ticked, and an answer sets every control of the checklist."""

    def setUp(self):
        super().setUp()
        from documents.test_word_v3 import control_checklist_bytes
        self.template, _ = self.uploaded(data=control_checklist_bytes(), name="Synthetic reconciliation")
        self.version = self.confirm(self.template)
        self.field = next(f for f in self.version.fields if f["kind"] == "multi_choice")
        self.assertEqual(self.new_encounter(self.version, notes="Synthetic reconciliation notes").status_code, 302)
        self.encounter = Encounter.objects.get()

    def test_the_page_names_the_printed_tick_and_the_answer_is_exported(self):
        from documents.test_word_v3 import controls_shown
        page = self.client.get(f"/encounters/{self.encounter.pk}/").content.decode()
        self.assertIn("With no option chosen, the form keeps what it prints: Warfarin ticked.", page)
        self.assertIn("decided no answer belongs here; the exported form keeps what it prints: Warfarin ticked.", page)
        payload = {"revision": Encounter.objects.get(pk=self.encounter.pk).revision, "answer_" + self.field["key"]: ["Metformin"]}
        for f in self.version.fields:
            payload["reviewed_" + f["key"]] = "on"
        self.assertEqual(self.client.post(f"/encounters/{self.encounter.pk}/save/", payload).status_code, 302)
        response = self.client.post(f"/encounters/{self.encounter.pk}/finalize/",
                                    {"revision": Encounter.objects.get(pk=self.encounter.pk).revision, "reviewed": "on"}, follow=True)
        encounter = Encounter.objects.get(pk=self.encounter.pk)
        self.assertEqual(encounter.status, "finalized", [str(m) for m in response.context["messages"]])
        self.assertEqual(controls_shown(private_path(encounter.export_path).read_bytes()), [("☐", "0"), ("☒", "1"), ("☐", "0")])

    def test_a_printed_state_that_cannot_be_read_is_never_called_unticked(self):
        from core import v3_mapping
        choice = {"kind": "choice", "options": ["Yes", "No"], "printed_unread": [0],
                  "locator": {"contract": "v3", "target": {"type": "checkboxes"}}}
        self.assertEqual(v3_mapping.review_note(choice), "The chosen option is ticked and every other printed option is "
                         "left unticked. With no option chosen, the form keeps what it prints; QuillMD cannot read "
                         "whether Yes is ticked on the blank form.")
        self.assertEqual(v3_mapping.blank_note(choice), "the exported form keeps what it prints; QuillMD cannot read "
                         "whether Yes is ticked on the blank form")
        both = {**choice, "options": ["Yes", "No", "Unsure"], "printed_ticked": [1], "printed_unread": [0, 2]}
        self.assertEqual(v3_mapping.finalized_note(both, {"text": ""}), "No option chosen; the form keeps what it prints: "
                         "No ticked; QuillMD cannot read whether Yes, Unsure are ticked on the blank form.")
        box = {"kind": "checkbox", "options": ["Consent"], "printed_unread": [0], "locator": choice["locator"]}
        self.assertEqual(v3_mapping.review_note(box), "Ticked here, the box is exported ticked; left unticked, it is "
                         "exported unticked. QuillMD cannot read whether the blank form prints this box ticked.")


def smoker_form_bytes():
    doc = Document()
    doc.add_paragraph("Synthetic smoking status")
    doc.add_paragraph("Indication: ____________")
    doc.add_paragraph("Smoker?  ☐ Yes  ☐ No")
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


@override_settings(**V3)
class V3BoxNumbers(V3Fixture, TestCase):
    """F2/F6 end to end: the box the clinician named is the box exported; a box the form lacks never confirms."""

    def setUp(self):
        super().setUp()
        self.template, version = self.uploaded(data=smoker_form_bytes(), name="Synthetic smoker")
        smoker = next(f for f in version.fields if f["label"] == "Smoker?")
        self.client.post(f"/templates/{self.template.pk}/", {"action": "v3_save", "mapping_version": version.pk,
                                                             "remove_" + smoker["key"]: "on"})
        self.version = self.latest(self.template)

    def add(self, slot, box, label):
        return self.client.post(f"/templates/{self.template.pk}/", {"action": "v3_add", "mapping_version": self.version.pk,
                                "slot": slot, "kind": "checkbox", "label": label, "box": str(box)})

    def test_box_two_of_a_paragraph_place_is_box_two(self):
        response = self.add("word/document.xml#b/p[2]", 2, "Non-smoker")
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context.get("v3_error"))
        latest = self.latest(self.template)
        added = next(f for f in latest.fields if f.get("origin") == "manual")
        self.assertEqual(added["locator"]["target"]["boxes"][0]["glyph"], 1)
        rows = self.client.get(f"/templates/{self.template.pk}/").context["v3_rows"]
        self.assertIn("printed box 2 of 2", next(r for r in rows if r["key"] == added["key"])["location"])
        latest = self.confirm(self.template, latest)
        self.assertEqual(self.new_encounter(latest, notes="Indication: synthetic").status_code, 302)
        encounter = Encounter.objects.get()
        payload = {"revision": encounter.revision}
        for f in latest.fields:
            payload["reviewed_" + f["key"]] = "on"
        payload["answer_" + added["key"]] = "checked"
        payload["answer_" + next(f["key"] for f in latest.fields if f["label"] == "Indication")] = "synthetic"
        self.assertEqual(self.client.post(f"/encounters/{encounter.pk}/save/", payload).status_code, 302)
        response = self.client.post(f"/encounters/{encounter.pk}/finalize/", {"revision": encounter.revision + 1, "reviewed": "on"}, follow=True)
        encounter = Encounter.objects.get()
        self.assertEqual(encounter.status, "finalized", [str(m) for m in response.context["messages"]])
        self.assertIn("Smoker?  ☐ Yes  ☒ No", part_text(private_path(encounter.export_path).read_bytes()))

    def test_a_box_beyond_the_line_is_refused_when_added(self):
        response = self.add("word/document.xml#b/p[2]/glyphs", 7, "Pack-years over 20")
        self.assertEqual(response.status_code, 400)
        self.assertIn("That place has 2 printed boxes; choose a box number from 1 to 2.", response.context["v3_error"])
        self.assertEqual(self.latest(self.template).pk, self.version.pk)

    def test_a_stored_box_the_form_lacks_can_never_be_confirmed(self):
        response = self.add("word/document.xml#b/p[2]", 1, "Current smoker")
        self.assertEqual(response.status_code, 302)
        latest = self.latest(self.template)
        fields = [dict(f) for f in latest.fields]
        for f in fields:
            if f.get("origin") == "manual":
                f["locator"] = {**f["locator"], "target": {**f["locator"]["target"], "boxes": [
                    {**f["locator"]["target"]["boxes"][0], "glyph": 6}]}}
        stale = TemplateVersion.objects.create(template=self.template, number=latest.number + 1, fields=fields,
                                               contract="v3", corrections={"base_version": latest.number}, created_by=self.user)
        response = self.client.post(f"/templates/{self.template.pk}/", {"action": "v3_confirm", "mapping_version": stale.pk,
                                                                        "checked_every_field": "on"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("point at a printed box the form does not have: Current smoker.", response.context["v3_error"])
        self.assertFalse(MappingConfirmation.objects.filter(version=stale).exists())


def two_knees_form_bytes():
    doc = Document()
    doc.add_paragraph("Synthetic knee examination")
    doc.add_paragraph("Indication: ____________")
    doc.add_paragraph("RIGHT KNEE")
    doc.add_paragraph("Pain?  ☐ Yes  ☐ No")
    doc.add_paragraph("Comments: ____________")
    doc.add_paragraph("LEFT KNEE")
    doc.add_paragraph("PAIN:  ☐ Yes  ☐ No")
    doc.add_paragraph("Comments: ____________")
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


@override_settings(**V3)
class V3RepeatedQuestions(V3Fixture, TestCase):
    """F4: a label the form repeats names no one question; the review flags it with generation's normalizer."""

    def setUp(self):
        super().setUp()
        self.template, self.version = self.uploaded(data=two_knees_form_bytes(), name="Synthetic knees")

    def generate(self, version, notes):
        from core.jobs import enqueue, run_one
        if not Encounter.objects.filter(template_version=version).exists():
            self.assertEqual(self.new_encounter(version).status_code, 302)
        encounter = Encounter.objects.get(template_version=version)
        self.assertEqual(self.client.post(f"/encounters/{encounter.pk}/notes/",
                                          {"revision": encounter.revision, "notes": notes}).status_code, 302)
        enqueue(Encounter.objects.get(pk=encounter.pk), self.user)
        self.assertTrue(run_one())
        encounter = Encounter.objects.get(pk=encounter.pk)
        return {f["key"]: encounter.answers[f["key"]] for f in version.fields}, encounter

    def test_the_review_flags_labels_that_generation_reads_as_one(self):
        rows = self.client.get(f"/templates/{self.template.pk}/").context["v3_rows"]
        flagged = {(row["label"], row["duplicate"]) for row in rows}
        self.assertIn(("Pain?", True), flagged)
        self.assertIn(("PAIN", True), flagged)
        self.assertIn(("Comments", True), flagged)
        self.assertIn(("Indication", False), flagged)

    def test_a_labelled_line_fills_none_of_the_repeated_questions(self):
        version = self.confirm(self.template)
        answers, encounter = self.generate(version, "Indication: synthetic knee review\nPain: yes\nComments: settled")
        for f in version.fields:
            answer = answers[f["key"]]
            if f["label"] == "Indication":
                self.assertEqual((answer["status"], answer["text"]), ("supported", "synthetic knee review"))
                continue
            self.assertEqual((answer["status"], answer["text"]), ("conflict", ""), f["label"])
            self.assertIn("appears 2 times on the form", answer["held_candidate"]["reason"])
            self.assertEqual(answer["held_candidate"]["text"], "yes" if f["kind"] == "choice" else "settled")
        page = self.client.get(f"/encounters/{encounter.pk}/").content.decode()
        self.assertIn("This question appears 2 times on the form; the notes do not say which one", page)

    def test_absence_stays_missing(self):
        version = self.confirm(self.template)
        answers, _ = self.generate(version, "Indication: synthetic knee review")
        self.assertEqual({a["status"] for key, a in answers.items() if key != self.by_label(version)["Indication"]["key"]},
                         {"missing"})

    def test_renamed_questions_are_filled_from_their_own_lines(self):
        by = {(f["label"], n): f for n, f in enumerate(self.version.fields)}
        pains = [f for f in self.version.fields if f["label"] in ("Pain?", "PAIN")]
        comments = [f for f in self.version.fields if f["label"] == "Comments"]
        response = self.client.post(f"/templates/{self.template.pk}/", {"action": "v3_save", "mapping_version": self.version.pk,
            "label_" + pains[0]["key"]: "Right knee pain", "label_" + pains[1]["key"]: "Left knee pain",
            "label_" + comments[0]["key"]: "Right knee comments", "label_" + comments[1]["key"]: "Left knee comments"})
        self.assertEqual(response.status_code, 302)
        version = self.confirm(self.template)
        self.assertFalse(any(row["duplicate"] for row in self.client.get(f"/templates/{self.template.pk}/").context["v3_rows"]))
        answers, _ = self.generate(version, "Indication: synthetic\nRight knee pain: yes\nLeft knee pain: no\n"
                                            "Right knee comments: settled\nLeft knee comments: swollen")
        texts = {f["label"]: answers[f["key"]]["text"] for f in version.fields}
        self.assertEqual(texts, {"Indication": "synthetic", "Right knee pain": "Yes", "Left knee pain": "No",
                                 "Right knee comments": "settled", "Left knee comments": "swollen"})


def repeated_option_form_bytes():
    doc = Document()
    doc.add_paragraph("Synthetic swelling check")
    doc.add_paragraph("Indication: ____________")
    doc.add_paragraph("Swelling:  ☐ Left  ☐ Right  ☐ Left")
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


@override_settings(**V3)
class V3RepeatedOptions(V3Fixture, TestCase):
    """F7: an option printed twice is two options; the notes naming its words do not say which printing."""

    def setUp(self):
        super().setUp()
        self.template, version = self.uploaded(data=repeated_option_form_bytes(), name="Synthetic swelling")
        self.version = self.confirm(self.template)
        self.field = next(f for f in self.version.fields if f["label"] == "Swelling")

    def generated(self, notes):
        from core.jobs import enqueue, run_one
        if not Encounter.objects.exists():
            self.assertEqual(self.new_encounter(self.version).status_code, 302)
        encounter = Encounter.objects.get()
        saved = self.client.post(f"/encounters/{encounter.pk}/notes/", {"revision": encounter.revision, "notes": notes})
        self.assertEqual(saved.status_code, 302)
        enqueue(Encounter.objects.get(), self.user)
        self.assertTrue(run_one())
        return Encounter.objects.get().answers[self.field["key"]]

    def test_each_printing_is_offered_and_a_repeated_word_is_held(self):
        self.assertEqual(self.field["options"], ["Left", "Right", "Left (2)"])
        right = self.generated("Indication: synthetic\nSwelling: Right")
        self.assertEqual((right["status"], right["text"]), ("supported", "Right"))
        left = self.generated("Indication: synthetic\nSwelling: Left")
        self.assertEqual((left["status"], left["text"], (left.get("held_candidate") or {}).get("text")), ("conflict", "", "Left"),
                         "Left is printed twice; the notes do not say which printing")
        page = self.client.get(f"/encounters/{Encounter.objects.get().pk}/").content.decode()
        self.assertIn('<option value="Left (2)" >Left (2)</option>', page)


def laterality_form_bytes():
    doc = Document()
    doc.add_paragraph("Synthetic joint procedure")
    doc.add_paragraph("Indication: ____________")
    doc.add_paragraph("Injected joint:  ☐ (L) knee  ☐ (R) knee")
    doc.add_paragraph("Aspirated joint:  ☐ L knee  ☐ R knee")
    doc.add_paragraph("Imaged joint: ")._p.append(_sdt("dropdown", options=["Choose an item.", "(L) knee", "(R) knee"]))
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


@override_settings(**V3)
class V3LateralityRoundTrip(V3Fixture, TestCase):
    """Notes -> answer -> export keeps the side: '(L) knee' / '(R) knee' and 'L knee' / 'R knee' are options as printed."""

    def test_the_side_in_the_notes_is_the_box_ticked(self):
        from core.jobs import enqueue, run_one
        template, version = self.uploaded(data=laterality_form_bytes(), name="Synthetic joints")
        by = self.by_label(version)
        self.assertEqual(by["Injected joint"]["options"], ["(L) knee", "(R) knee"])
        version = self.confirm(template)
        notes = ("Indication: synthetic\nInjected joint: (R) knee\nAspirated joint: L knee\nImaged joint: (L) knee")
        self.assertEqual(self.new_encounter(version, notes=notes).status_code, 302)
        encounter = Encounter.objects.get()
        enqueue(encounter, self.user)
        self.assertTrue(run_one())
        encounter = Encounter.objects.get()
        texts = {f["label"]: (encounter.answers[f["key"]]["status"], encounter.answers[f["key"]]["text"]) for f in version.fields}
        self.assertEqual(texts, {"Indication": ("supported", "synthetic"), "Injected joint": ("supported", "(R) knee"),
                                 "Aspirated joint": ("supported", "L knee"), "Imaged joint": ("supported", "(L) knee")})
        payload = {"revision": encounter.revision}
        for f in version.fields:
            payload["answer_" + f["key"]] = encounter.answers[f["key"]]["text"]
            payload["reviewed_" + f["key"]] = "on"
        self.assertEqual(self.client.post(f"/encounters/{encounter.pk}/save/", payload).status_code, 302)
        response = self.client.post(f"/encounters/{encounter.pk}/finalize/", {"revision": encounter.revision + 1, "reviewed": "on"}, follow=True)
        encounter = Encounter.objects.get()
        self.assertEqual(encounter.status, "finalized", [str(m) for m in response.context["messages"]])
        body = part_text(private_path(encounter.export_path).read_bytes())
        self.assertIn("Injected joint:  ☐ (L) knee  ☒ (R) knee", body)
        self.assertIn("Aspirated joint:  ☒ L knee  ☐ R knee", body)
        self.assertIn("Imaged joint: (L) knee", body)

    def test_a_side_the_notes_leave_out_is_never_guessed(self):
        from core.jobs import enqueue, run_one
        template, version = self.uploaded(data=laterality_form_bytes(), name="Synthetic joints")
        version = self.confirm(template)
        self.assertEqual(self.new_encounter(version, notes="Indication: synthetic\nInjected joint: knee").status_code, 302)
        enqueue(Encounter.objects.get(), self.user)
        self.assertTrue(run_one())
        answer = Encounter.objects.get().answers[self.by_label(version)["Injected joint"]["key"]]
        self.assertEqual((answer["status"], answer["text"], answer["held_candidate"]["text"]), ("conflict", "", "knee"))


V3_FIELDS = [
    {"key": "v3_1", "label": "Smoker?", "kind": "choice", "options": ["Yes", "No"], "locator": {"contract": "v3"}},
    {"key": "v3_2", "label": "Allergies", "kind": "text", "locator": {"contract": "v3"}},
    {"key": "v3_3", "label": "Clinician signature", "kind": "signature", "locator": {"contract": "v3"}},
]


def live_result(notes, quotes, v3=True):
    """A synthetic completed provider response for the legacy evidence contract (nothing is sent anywhere)."""
    import json
    from types import SimpleNamespace
    asked = [f for f in V3_FIELDS if f["kind"] != "signature"]
    body = {"fields": [{"key": f["key"], "quotes": quotes.get(f["key"], []), "conflict": False} for f in asked]}
    response = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(body))])
    raw = {"anthropic_response": response, "notes": notes, "fields": asked, "context_labels": ["Clinician signature"],
           "evidence_contract": "legacy"}
    if v3:
        raw["v3_fields"] = V3_FIELDS
    return raw


class V3OptionMatch(TestCase):
    def test_an_option_is_named_by_its_printed_words_ignoring_case_only(self):
        from core.v3_mapping import option_for
        self.assertEqual(option_for(["Yes", "No"], "  yes "), "Yes")
        self.assertIsNone(option_for(["Yes", "No"], "Yes."))
        self.assertIsNone(option_for(["Maß"], "MASS"), "case folding would equate ß with ss")
        self.assertIsNone(option_for(["Yes"], "Ye\u017f"), "a long s is not an s")
        self.assertIsNone(option_for(["Left", "LEFT"], "left"), "two printed options that differ by case name neither")

    def test_the_review_and_the_engine_share_one_reader(self):
        from core.v3_mapping import option_for
        from documents.word_v3 import option_position
        options = ["Rt. knee", "Lt. knee", "Yes", "YES", " No "]
        for value in ("Lt. knee", "lt. knee", "knee", "Yes", "yes", "No", "no ", "", "Rt knee", "Maß"):
            position = option_position(options, value)
            self.assertEqual(option_for(options, value), None if position is None else options[position], value)
        self.assertEqual(option_position(options, " lt. KNEE "), 1)
        self.assertIsNone(option_position(options, "yes"), "two stored labels that differ by case name neither")
        from unittest.mock import patch
        with patch("documents.word_v3.option_position", return_value=1):
            self.assertEqual(option_for(["first", "second"], "anything"), "second",
                             "the review reads an option through the engine's reader, not a copy of it")


def knee_form_bytes():
    doc = Document()
    doc.add_paragraph("Synthetic knee injection note")
    doc.add_paragraph("Indication: ____________")
    p = doc.add_paragraph("Injection site: ")
    p._p.append(_sdt("dropdown", options=["Choose an item.", "Rt. knee", "Lt. knee", "Bil. knees"]))
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


@override_settings(**V3)
class V3ReviewedOptionIsExported(V3Fixture, TestCase):
    """F1 end to end: the left knee reviewed is the left knee exported."""

    def test_left_knee_generated_reviewed_and_exported(self):
        from core.jobs import enqueue, run_one
        template, version = self.uploaded(data=knee_form_bytes(), name="Synthetic knee")
        field = next(f for f in version.fields if f["kind"] == "choice")
        version = self.confirm(template)
        self.assertEqual(self.new_encounter(version, notes="Indication: synthetic knee pain\nInjection site: Lt. knee").status_code, 302)
        encounter = Encounter.objects.get()
        enqueue(encounter, self.user)
        self.assertTrue(run_one())
        encounter = Encounter.objects.get(pk=encounter.pk)
        self.assertEqual((encounter.answers[field["key"]]["status"], encounter.answers[field["key"]]["text"]), ("supported", "Lt. knee"))
        payload = {"revision": encounter.revision}
        for f in version.fields:
            payload["answer_" + f["key"]] = encounter.answers[f["key"]]["text"]
            payload["reviewed_" + f["key"]] = "on"
        self.assertEqual(self.client.post(f"/encounters/{encounter.pk}/save/", payload).status_code, 302)
        response = self.client.post(f"/encounters/{encounter.pk}/finalize/", {"revision": encounter.revision + 1, "reviewed": "on"}, follow=True)
        encounter = Encounter.objects.get(pk=encounter.pk)
        self.assertEqual(encounter.status, "finalized", [str(m) for m in response.context["messages"]])
        body = part_text(private_path(encounter.export_path).read_bytes())
        self.assertIn("Injection site: Lt. knee", body)
        self.assertNotIn("Rt. knee", body)


class V3LiveAdoption(TestCase):
    """The provider's selections for a v3 form get the same option rule; the request carries no options."""

    def test_an_unlabelled_line_is_never_read_as_an_option(self):
        from core.generation import validated
        answers = validated(live_result("Yes", {"v3_1": ["Yes"]}))
        self.assertEqual((answers["v3_1"]["status"], answers["v3_1"]["text"]), ("conflict", ""))
        self.assertEqual(answers["v3_1"]["held_candidate"]["text"], "Yes")
        self.assertEqual(answers["v3_3"]["status"], "missing")

    def test_its_own_labelled_value_or_line_names_the_option(self):
        from core.generation import validated
        notes = "Smoker: yes\nAllergies: none documented"
        for quote in ("yes", "Smoker: yes"):
            answers = validated(live_result(notes, {"v3_1": [quote], "v3_2": ["none documented"]}))
            self.assertEqual((answers["v3_1"]["status"], answers["v3_1"]["text"]), ("supported", "Yes"), quote)
            self.assertEqual(answers["v3_2"]["text"], "none documented")

    def test_the_source_must_be_the_labelled_value_at_its_own_position(self):
        from core.generation import recognized_labels, v3_labelled_source
        notes = "Smoker: yes\nAllergies: none documented"
        labels = recognized_labels(V3_FIELDS[:2])
        self.assertTrue(v3_labelled_source(notes, labels, "smoker", [{"quote": "yes", "start": 8, "end": 11}]))
        self.assertTrue(v3_labelled_source(notes, labels, "smoker", [{"quote": "Smoker: yes", "start": 0, "end": 11}]))
        self.assertFalse(v3_labelled_source(notes, labels, "smoker", [{"quote": "yes", "start": 0, "end": 3}]),
                         "a quote that is not the value at its own position is not the labelled value")
        self.assertFalse(v3_labelled_source(notes, labels, "smoker", [{"quote": "none documented", "start": 8, "end": 23}]))

    def test_other_forms_are_adopted_exactly_as_before(self):
        from core.generation import validated
        raw = live_result("Smoker: former\nAllergies: none", {"v3_1": ["former"]}, v3=False)
        answers = validated(raw)
        self.assertEqual((answers["v3_1"]["status"], answers["v3_1"]["text"]), ("supported", "former"))

    def captured_payload(self, fields, context_labels=()):
        import json
        from unittest.mock import MagicMock, patch
        from core import generation
        captured = {}

        def create(**kwargs):
            captured["payload"] = json.loads(kwargs["messages"][0]["content"])
            raise RuntimeError("stop before any request")

        client = MagicMock()
        client.messages.create.side_effect = create
        config = {**generation.configuration(), "mode": "live", "provider": "anthropic", "model": "synthetic-model",
                  "input_rate": "0.000003", "output_rate": "0.000015", "cached_rate": "0.0000003"}
        with patch("anthropic.Anthropic", return_value=client):
            with self.assertRaises(RuntimeError):
                generation.generate("Smoker: yes", fields, config, context_labels=context_labels)
        return captured["payload"]

    def test_the_request_asks_only_the_generated_kinds_and_carries_no_options(self):
        payload = self.captured_payload(V3_FIELDS)
        self.assertEqual(payload["questions"], [
            {"key": "v3_1", "label": "Smoker?", "answer_policy": "documented_source_only"},
            {"key": "v3_2", "label": "Allergies", "answer_policy": "documented_source_only"}])
        self.assertEqual(payload["context_labels"], ["Clinician signature"])
        self.assertNotIn("options", __import__("json").dumps(payload))

    def test_the_request_for_any_other_form_is_unchanged(self):
        fields = [{"key": "cell_0", "label": "Allergies", "kind": "text", "locator": {"cell": 0}},
                  {"key": "cell_1", "label": "Electronically signed by", "kind": "text", "locator": {"cell": 1}}]
        payload = self.captured_payload(fields, context_labels=("Statement",))
        self.assertEqual(payload, {"questions": [
            {"key": "cell_0", "label": "Allergies", "answer_policy": "documented_source_only"},
            {"key": "cell_1", "label": "Electronically signed by", "answer_policy": "documented_source_only"}],
            "context_labels": ["Statement"], "notes": "Smoker: yes"})
