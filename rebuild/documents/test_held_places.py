"""The ONE structure-only authority over signing, initials, identity and attestation places (word_v3.held_places).

Synthetic BLANK forms only; no network, no provider. The pinned parser's readings are used in-process (as the trusted
parent supplies them to the isolated parser); `NoReadings` proves the holding direction when a clause is unread.
"""
import io
import unittest

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from . import word_v3 as w
from .service import DocumentError, fill_template, inspect_template, locate_fields

BODY = "word/document.xml#"


def saved(doc):
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def bordered_box(doc, text=None, pict=False):
    table = doc.add_table(rows=1, cols=1)
    borders = OxmlElement("w:tcBorders")
    for side in ("top", "left", "bottom", "right"):
        edge = OxmlElement("w:" + side)
        edge.set(qn("w:val"), "single")
        borders.append(edge)
    table.cell(0, 0)._tc.get_or_add_tcPr().append(borders)
    if text:
        table.cell(0, 0).text = text
    if pict:
        run = OxmlElement("w:r")
        run.append(OxmlElement("w:pict"))
        table.cell(0, 0).paragraphs[0]._p.append(run)
    return table


def question_box_form(question, variant="empty", heading="Consultant review"):
    """R1: a heading, a printed question and its own one-cell bordered box, empty / holding a drawing / printing ink."""
    doc = Document()
    doc.add_paragraph("Participant ID: __________")
    doc.add_paragraph(heading, style="Heading 2")
    doc.add_paragraph(question)
    bordered_box(doc, text="Use black ink" if variant == "ink" else None, pict=variant == "pict")
    return saved(doc)


def column_form(variant="empty", header="Signature"):
    """R2: a 'Name | <header>' table whose second cell is empty / holds a drawing / prints ink guidance."""
    doc = Document()
    doc.add_paragraph("Clinic record", style="Heading 2")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Name"
    table.cell(0, 1).text = header
    if variant == "ink":
        table.cell(1, 1).text = "Use black ink"
    if variant == "pict":
        run = OxmlElement("w:r")
        run.append(OxmlElement("w:pict"))
        table.cell(1, 1).paragraphs[0]._p.append(run)
    return saved(doc)


def lines_form(*lines):
    doc = Document()
    for line in lines:
        doc.add_paragraph(line)
    return saved(doc)


def admin_grid():
    doc = Document()
    doc.add_paragraph("Medicines given", style="Heading 2")
    table = doc.add_table(rows=3, cols=4)
    for column, header in enumerate(("Drug", "Dose", "Time", "Signature")):
        table.cell(0, column).text = header
    return saved(doc)


def held(data):
    package = w.open_package(data)
    return {slot[len(BODY):] if slot.startswith(BODY) else slot: entry for slot, entry in w.held_places(package).items()}


def text_field(slot, target=None, kind="text", label="Answer", key="probe"):
    part, path = (slot.split("#", 1) if "#" in slot else ("word/document.xml", slot))
    return {"key": key, "label": label, "kind": kind, "context": "",
            "locator": {"contract": w.CONTRACT, "part": part, "slot": path, "target": target or {"type": "paragraph"}}}


class NoReadings:
    """Run the authority with an EMPTY readings map (what the isolated parser has when the parent reads nothing)."""

    def __enter__(self):
        self.saved = w.READINGS
        w.use_readings({})

    def __exit__(self, *exc):
        w.use_readings(self.saved)


class QuestionBoxesWhateverTheyHold(unittest.TestCase):
    """R1: the question and section are read BEFORE and whatever the box holds; the box is held in every variant."""

    def test_signing_and_consent_question_boxes_are_held_empty_drawing_or_guidance(self):
        for question in ("Signed by the consultant:", "I confirm the patient gave consent to proceed:",
                         "Record that the patient consents to proceed:",
                         "Has the report been countersigned?", "Countersignature:"):
            for variant in ("empty", "pict", "ink"):
                with self.subTest(question=question, variant=variant):
                    entry = held(question_box_form(question, variant)).get("b/tbl[0]/tr[0]/tc[0]")
                    self.assertIsNotNone(entry)
                    self.assertIn(entry.code, ("consent", "declaration", "attestation", "signing"))
                    self.assertIsNone(entry.ranges)

    def test_a_signing_section_holds_the_box_under_an_ordinary_question(self):
        entry = held(question_box_form("What was discussed?", "ink", heading="Consultant signature")).get("b/tbl[0]/tr[0]/tc[0]")
        self.assertEqual(entry.code, "consent")

    def test_control_an_ordinary_question_box_is_not_held_in_any_variant(self):
        for variant in ("empty", "pict", "ink"):
            with self.subTest(variant=variant):
                self.assertNotIn("b/tbl[0]/tr[0]/tc[0]", held(question_box_form("Please describe the wound?", variant,
                                                                                 heading="Wound review")))


class ColumnsRowsAndBoxes(unittest.TestCase):
    """R2: a cell under a signing column header is held whatever it holds; an admin grid holds only that column."""

    def test_a_signature_column_cell_is_held_empty_drawing_or_guidance(self):
        for header in ("Signature", "Countersigned", "Countersignature", "Signatory", "Initials", "Sign"):
            for variant in ("empty", "pict", "ink"):
                with self.subTest(header=header, variant=variant):
                    places = held(column_form(variant, header))
                    self.assertEqual(places["b/tbl[0]/tr[1]/tc[1]"].code, "signing")
                    self.assertNotIn("b/tbl[0]/tr[1]/tc[0]", places)

    def test_an_administration_grid_holds_only_its_signature_column(self):
        places = held(admin_grid())
        cells = {slot for slot in places if slot.startswith("b/tbl[0]/")}
        self.assertEqual({slot.split("/")[3] for slot in cells if "/p[" not in slot}, {"tc[3]"})
        field = next(f for f in w.inspect(admin_grid())["fields"] if f["kind"] == "table_rows")
        self.assertNotIn("write_protected", field)      # the drug, dose and time columns stay answerable
        package = w.open_package(admin_grid())
        source = w.Detector(package, layout_proposal=True)
        source.detect()
        authority = w.held_places(package, source)
        self.assertIsNone(w.held_violation(source.index, authority, field))
        self.assertEqual(w.held_table_columns(source.index, authority, field), [3])
        w.fill(admin_grid(), [field], {field["key"]: [["Drug A", "5 mg", "08:00", ""]]})
        with self.assertRaises(w.V3Failure) as refused:
            w.fill(admin_grid(), [field], {field["key"]: [["Drug A", "5 mg", "08:00", "SYNTHETIC-ANSWER"]]})
        self.assertEqual(refused.exception.code, "held_place")

    def test_an_initials_row_holds_its_box_whatever_the_box_prints(self):
        for printed in (None, "Initial here", "Use black ink"):
            with self.subTest(printed=printed):
                doc = Document()
                table = doc.add_table(rows=1, cols=2)
                table.cell(0, 0).text = "Clinician initials"
                if printed:
                    table.cell(0, 1).text = printed
                self.assertEqual(held(saved(doc))["b/tbl[0]/tr[0]/tc[1]"].code, "signing")

    def test_a_signature_box_captioned_inside_holds_its_empty_writing_lines(self):
        doc = Document()
        table = doc.add_table(rows=1, cols=1)
        table.cell(0, 0).text = "Signature of examining clinician"
        table.cell(0, 0).add_paragraph("")
        places = held(saved(doc))
        self.assertEqual(places["b/tbl[0]/tr[0]/tc[0]"].code, "signing")
        index = w.SlotIndex(w.open_package(saved(doc)))
        self.assertTrue(w.held_touches(index, {BODY + k: v for k, v in places.items()},
                                       text_field("b/tbl[0]/tr[0]/tc[0]/p[1]")))

    def test_guidance_that_mentions_signing_is_not_a_signing_caption(self):
        doc = Document()
        table = doc.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "What progress have you made?"
        table.cell(0, 1).text = "Describe your own experience; do not sign this answer for another person."
        self.assertNotIn("b/tbl[0]/tr[0]/tc[1]", held(saved(doc)))
        # A sentence that mentions a signed form is held where it is printed, but it is no caption of a signing box:
        # the answer line below it in the same cell stays an ordinary answer place.
        doc = Document()
        table = doc.add_table(rows=1, cols=1)
        table.cell(0, 0).text = "Describe the procedure performed; the signed consent form is filed with the notes."
        table.cell(0, 0).add_paragraph("")
        places = held(saved(doc))
        self.assertIn("b/tbl[0]/tr[0]/tc[0]/p[0]", places)
        self.assertNotIn("b/tbl[0]/tr[0]/tc[0]", places)
        index = w.SlotIndex(w.open_package(saved(doc)))
        self.assertIsNone(w.held_violation(index, {BODY + k: v for k, v in places.items()},
                                           text_field("b/tbl[0]/tr[0]/tc[0]/p[1]", kind="long_text")))

    def test_a_drawn_box_under_an_initials_instruction_and_a_signing_control_alias_are_held(self):
        from .test_signing_areas import signing_form
        entry = held(signing_form())["b/tbl[0]/tr[0]/tc[1]"]
        self.assertEqual(entry.code, "signing")
        self.assertTrue(entry.evidence.startswith("drawn box under"), entry.evidence)
        doc = Document()
        paragraph = doc.add_paragraph("Reviewer: ")
        sdt = OxmlElement("w:sdt")
        properties = OxmlElement("w:sdtPr")
        alias = OxmlElement("w:alias")
        alias.set(qn("w:val"), "Consultant signature")
        properties.append(alias)
        sdt.append(properties)
        content = OxmlElement("w:sdtContent")
        run = OxmlElement("w:r")
        run.append(OxmlElement("w:t"))
        content.append(run)
        sdt.append(content)
        paragraph._p.append(sdt)
        self.assertEqual(held(saved(doc))["b/p[0]/sdt[0]"].code, "signing")

    def test_a_locked_content_control_is_held_as_protected(self):
        doc = Document()
        paragraph = doc.add_paragraph("Statement: ")
        sdt = OxmlElement("w:sdt")
        properties = OxmlElement("w:sdtPr")
        lock = OxmlElement("w:lock")
        lock.set(qn("w:val"), "sdtContentLocked")
        properties.append(lock)
        sdt.append(properties)
        content = OxmlElement("w:sdtContent")
        run = OxmlElement("w:r")
        text = OxmlElement("w:t")
        text.text = "Printed statement"
        run.append(text)
        content.append(run)
        sdt.append(content)
        paragraph._p.append(sdt)
        self.assertEqual(held(saved(doc))["b/p[0]/sdt[0]"].code, "protected")


class InflectionsAndCaptions(unittest.TestCase):
    """The existing readers' inflection gaps, closed without new vocabulary: consent/consents/consented/consenting,
    'signed' inside countersigned, countersignature, signatory, 'Sign:'/'Sign below' as a caption, the adjective
    'initial', and one blank captioned '... signature and date'."""

    def kinds(self, *lines):
        return [(f["label"], f["kind"], bool(f.get("write_protected"))) for f in w.inspect(lines_form(*lines))["fields"]]

    def test_signing_captions_read_every_inflection(self):
        for line, kind in (("Countersigned by: ______", "signature"), ("Countersignature: ______", "signature"),
                           ("Signatory: ______", "signature"), ("Sign: ______", "signature"),
                           ("Sign below: ______", "signature"), ("Co-signed by: ______", "signature"),
                           ("Consultant signature and date: ______", "signature"),
                           ("Initials: ______", "initials"), ("Initial here: ______", "initials"),
                           ("Initialled by: ______", "initials")):
            with self.subTest(line=line):
                self.assertEqual(self.kinds(line)[0][1], kind)
                self.assertEqual(held(lines_form(line))["b/p[0]"].code, "signing")

    def test_clinical_signs_and_the_adjective_initial_stay_ordinary(self):
        for line, kind in (("Vital signs: ______", "text"), ("Signs and symptoms: ______", "text"),
                           ("Sign of infection: ______", "text"), ("Initial assessment: ______", "text"),
                           ("Initial presentation: ______", "text"), ("Initial dose: ______", "text"),
                           ("Signature date: ______", "date"), ("Date signed: ______", "date"),
                           ("Consent obtained: ______", "text"), ("Type I diabetes: ______", "text")):
            with self.subTest(line=line):
                self.assertEqual(self.kinds(line), [(clean(line), kind, False)])
                self.assertNotIn("b/p[0]", held(lines_form(line)))

    def test_question_box_signing_reads_every_consent_inflection(self):
        for text in ("Record that the patient consents to proceed:", "Patient consented: yes", "Consenting adult?",
                     "Consent given?"):
            with self.subTest(text=text):
                self.assertTrue(w.Detector.question_box_signing(text))
        self.assertFalse(w.Detector.question_box_signing("Vital signs recorded?"))

    def test_an_unread_clause_is_read_as_holding(self):
        with NoReadings():
            self.assertEqual(w.kind_for_label("Initial assessment"), "initials")
            self.assertEqual(w.kind_for_label("Sign of infection"), "signature")
            self.assertEqual(w.statement_codes("Type I diabetes"), {"declaration", "attestation"})
            self.assertEqual(w.statement_codes("Consent obtained"), {"declaration", "attestation"})
            self.assertEqual(w.kind_for_label("Vital signs"), "text")        # a plural is never a candidate
        self.assertEqual(w.kind_for_label("Initial assessment"), "text")
        self.assertEqual(w.statement_codes("Type I diabetes"), frozenset())
        self.assertEqual(w.statement_codes("Consent obtained"), frozenset())


def clean(line):
    return w.clean_label(line.split("_")[0])


class DeclarationsAndAttestations(unittest.TestCase):
    """A first-person declaration (and the block it heads) is held; an embedded consent is an unresolved attestation; a
    factual third-person field stays ordinary."""

    def test_first_person_statements_and_their_heading_are_held(self):
        doc = Document()
        doc.add_paragraph("Declaration", style="Heading 2")
        doc.add_paragraph("I declare the person examined agreed to this examination: ______")
        doc.add_paragraph("☐ Yes ☐ No")
        doc.add_paragraph("Findings", style="Heading 2")
        doc.add_paragraph("Plan: ______")
        places = held(saved(doc))
        self.assertEqual(places["b/p[0]"].code, "declaration")
        self.assertEqual(places["b/p[1]"].code, "declaration")
        self.assertEqual(places["b/p[2]"].code, "declaration")     # its own answer line
        self.assertNotIn("b/p[3]", places)
        self.assertNotIn("b/p[4]", places)
        # The engine reads the answer line as the declaration's Yes/No choice: a new inspection write-protects it.
        fields = w.inspect(saved(doc))["fields"]
        choice = next(f for f in fields if f["locator"]["slot"] == "b/p[2]/glyphs")
        self.assertEqual((choice["kind"], choice["write_protected"]), ("choice", True))
        self.assertFalse(next(f for f in fields if f["label"] == "Plan").get("write_protected"))

    def test_a_declaration_row_holds_its_box_on_either_side(self):
        for statement_first in (True, False):
            with self.subTest(statement_first=statement_first):
                doc = Document()
                table = doc.add_table(rows=1, cols=2)
                statement, box = (0, 1) if statement_first else (1, 0)
                table.cell(0, statement).text = "I confirm the risks were explained"
                table.cell(0, box).text = "☐"
                self.assertEqual(held(saved(doc))["b/tbl[0]/tr[0]/tc[%d]" % box].code, "declaration")

    def test_an_embedded_consent_is_an_unresolved_attestation_and_a_fact_is_ordinary(self):
        places = held(lines_form("Record that the patient consents to proceed: ______", "Consent obtained: ______",
                                 "Patient consented: ______"))
        self.assertEqual(places["b/p[0]"].code, "attestation")
        self.assertNotIn("b/p[1]", places)
        self.assertNotIn("b/p[2]", places)


class RangedCaptionLines(unittest.TestCase):
    def test_only_the_signature_part_of_a_mixed_caption_line_is_held(self):
        data = lines_form("Name: ______ Signature: ______ Date: ______")
        entry = held(data)["b/p[0]"]
        self.assertEqual(entry.code, "signing")
        self.assertEqual(len(entry.ranges), 1)
        fields = w.inspect(data)["fields"]
        self.assertEqual([(f["label"], f["kind"], bool(f.get("write_protected"))) for f in fields],
                         [("Name", "text", False), ("Signature", "signature", False), ("Date", "date", False)])
        name, _, date = fields
        written = w.fill(data, fields, {name["key"]: "SYNTHETIC NAME", date["key"]: "2026-09-29"})
        self.assertIn("SYNTHETIC NAME", w.text_of(w.SlotIndex(w.open_package(written)).by_id[BODY + "b/p[0]"].el))
        # A text field at the signature part itself is refused by fill (the stored-mapping protection).
        start, end = entry.ranges[0]
        forged = {**name, "key": "forged", "locator": {**name["locator"], "target": {"type": "span", "start": start + 12,
                                                                                         "end": start + 12, "shape": "after_label"}}}
        with self.assertRaises(w.V3Failure) as refused:
            w.fill(data, [forged], {"forged": "SYNTHETIC-ANSWER"})
        self.assertEqual(refused.exception.code, "held_place")

    def test_a_signed_question_with_boxes_holds_a_written_answer_but_not_a_box_selection(self):
        entry = held(lines_form("Consent form signed? ☐ Yes ☐ No"))["b/p[0]"]
        self.assertTrue(entry.selection)
        package = w.open_package(lines_form("Consent form signed? ☐ Yes ☐ No"))
        index = w.SlotIndex(package)
        authority = {BODY + "b/p[0]": entry}
        box = {"key": "box", "label": "Yes", "kind": "checkbox", "options": ["Yes"],
               "locator": {"contract": w.CONTRACT, "part": "word/document.xml", "slot": "b/p[0]",
                           "target": {"type": "checkboxes", "boxes": [{"kind": "glyph", "part": "word/document.xml",
                                                                        "slot": "b/p[0]/glyphs", "glyph": 0}]}}}
        self.assertIsNone(w.held_violation(index, authority, box))
        self.assertIsNotNone(w.held_violation(index, authority, text_field("b/p[0]")))


class OneAuthorityEveryWriter(unittest.TestCase):
    """Fill, inspect and locate consult the SAME authority; it reads only the original's structure."""

    def test_fill_refuses_a_stored_answerable_field_on_every_held_shape(self):
        cases = [(question_box_form("Signed by the consultant:", variant), "b/tbl[0]/tr[0]/tc[0]", {"type": "cell"})
                 for variant in ("empty", "pict", "ink")]
        cases += [(column_form(variant), "b/tbl[0]/tr[1]/tc[1]", {"type": "cell"}) for variant in ("empty", "pict", "ink")]
        cases += [(lines_form("Signature: ______"), "b/p[0]", {"type": "span", "start": 10, "end": 10, "shape": "after_label"})]
        for data, slot, target in cases:
            with self.subTest(slot=slot):
                index = w.SlotIndex(w.open_package(data))
                field = text_field(slot, target)
                field["locator"]["fingerprint"] = w.fingerprint(index.by_id[BODY + slot].el)
                with self.assertRaises(w.V3Failure) as refused:
                    w.fill(data, [field], {"probe": "SYNTHETIC-ANSWER"})
                self.assertEqual(refused.exception.code, "held_place")

    def test_locate_refuses_a_non_signing_kind_on_a_held_place_and_allows_a_signing_kind(self):
        data = column_form("pict")
        with self.assertRaises(w.V3Failure) as refused:
            w.locate(data, [{"slot": BODY + "b/tbl[0]/tr[1]/tc[1]/p[0]", "kind": "text", "label": "Clinic record"}])
        self.assertEqual(refused.exception.code, "held_place")
        located = w.locate(data, [{"slot": BODY + "b/tbl[0]/tr[1]/tc[1]/p[0]", "kind": "signature", "label": "Signature"}])
        self.assertEqual(located[0]["kind"], "signature")

    def test_the_authority_never_depends_on_emptiness_or_on_an_engine_area(self):
        for question in ("Signed by the consultant:", "I confirm the patient gave consent to proceed:"):
            places = [held(question_box_form(question, variant)).get("b/tbl[0]/tr[0]/tc[0]")
                      for variant in ("empty", "pict", "ink")]
            self.assertEqual(len({(p.code, p.ranges) for p in places}), 1, question)
        places = [held(column_form(variant))["b/tbl[0]/tr[1]/tc[1]"] for variant in ("empty", "pict", "ink")]
        self.assertEqual(len({(p.code, p.ranges) for p in places}), 1)


class IsolatedParserExchange(unittest.TestCase):
    """Through the service: the isolated parser asks for its clause readings, the parent reads them with the pinned
    parser, and the result equals the in-process reading - bound to the original's sha256."""

    def test_the_sandboxed_authority_equals_the_in_process_one(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from .service import held_places
        data = lines_form("Initial assessment: ______", "Initial here: ______", "I confirm the plan: ______",
                          "Vital signs: ______", "Sign below: ______")
        with tempfile.TemporaryDirectory(prefix="held-places-") as directory:
            path = Path(directory) / "form.docx"
            path.write_bytes(data)
            report = held_places(path)
            self.assertEqual(report["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual({row["slot"]: row["code"] for row in report["held"]},
                             {BODY + k: v.code for k, v in held(data).items()})
            inspected = inspect_template(path, engine="v3")
            self.assertEqual([(f["kind"], bool(f.get("write_protected"))) for f in inspected["fields"]],
                             [(f["kind"], bool(f.get("write_protected"))) for f in w.inspect(data)["fields"]])
            with self.assertRaises(DocumentError) as refused:
                locate_fields(path, [{"slot": BODY + "b/p[4]", "kind": "text", "label": "Sign below"}])
            self.assertEqual(refused.exception.code, "held_place")
            field = text_field("b/p[2]", {"type": "span", "start": 18, "end": 18, "shape": "after_label"})
            field["locator"]["fingerprint"] = w.fingerprint(w.SlotIndex(w.open_package(data)).by_id[BODY + "b/p[2]"].el)
            with self.assertRaises(DocumentError) as refused:
                fill_template(path, [field], {"probe": "SYNTHETIC-ANSWER"}, Path(directory) / "out.docx")
            self.assertEqual(refused.exception.code, "held_place")
            self.assertFalse((Path(directory) / "out.docx").exists())



# ─── Refutation round against be5fba45: every CONFIRMED finding, red there, green here ───────────────────────────────

def table_form(rows, title="Administration record", heading=False, between=None, more=None):
    """A table of printed rows (None/'' = an empty cell), optionally a printed line and a second table after it."""
    doc = Document()
    doc.add_paragraph(title, style="Heading 2" if heading else None)
    for n, block in enumerate([rows] + ([more] if more else [])):
        if n:
            doc.add_paragraph(between)
        table = doc.add_table(rows=len(block), cols=len(block[0]))
        for r, row in enumerate(block):
            for c, value in enumerate(row):
                if value:
                    table.cell(r, c).text = value
    return saved(doc)


def text_box_form(*lines):
    from lxml import etree
    doc = Document()
    doc.add_paragraph("Sign-off")
    paragraph = doc.add_paragraph()
    pict = OxmlElement("w:pict")
    shape = etree.SubElement(pict, "{urn:schemas-microsoft-com:vml}shape")
    box = etree.SubElement(shape, "{urn:schemas-microsoft-com:vml}textbox")
    content = OxmlElement("w:txbxContent")
    box.append(content)
    for line in lines:
        inner = OxmlElement("w:p"); run = OxmlElement("w:r"); text = OxmlElement("w:t")
        text.text = line; run.append(text); inner.append(run); content.append(inner)
    paragraph.add_run()._r.append(pict)
    return saved(doc)


def stored_text(data, slot, target=None, kind="text"):
    """A field as a mapping stored before the rule would carry it (fingerprinted, answerable)."""
    field = text_field(slot, target, kind=kind)
    field["locator"]["fingerprint"] = w.fingerprint(w.SlotIndex(w.open_package(data)).by_id[BODY + slot].el)
    return field


class RefutedAnswerPlaces(unittest.TestCase):
    """F1, F6, F9, R2-F2: an answer place is governed by its caption, wherever the engine put its area."""

    def assertFillRefused(self, data, slot, target=None):
        field = stored_text(data, slot, target)
        with self.assertRaises(w.V3Failure) as refused:
            w.fill(data, [field], {"probe": "SYNTHETIC-ANSWER"})
        self.assertEqual(refused.exception.code, "held_place")

    def test_F1_a_signing_caption_holds_the_lines_printed_after_it(self):
        for caption, line in (("Signature of consultant:", "_" * 30), ("Signature of consultant:", ""),
                              ("Initials of checking nurse:", "_" * 10)):
            with self.subTest(caption=caption, line=line):
                data = lines_form("Authorisation", caption, line)
                self.assertEqual(held(data)["b/p[2]"].code, "signing")
                self.assertFillRefused(data, "b/p[2]", {"type": "paragraph"})
        # Control: an ordinary caption's line stays answerable; guidance that mentions signing captions nothing.
        self.assertNotIn("b/p[2]", held(lines_form("Authorisation", "Plan:", "_" * 30)))
        self.assertNotIn("b/p[2]", held(lines_form("Authorisation", "Describe the wound; the signed consent form is filed "
                                                                    "with the notes and must be kept.", "_" * 30)))

    def test_F9_any_number_of_empty_lines_between_a_signing_caption_and_its_box(self):
        for gaps in (0, 3, 6):
            with self.subTest(gaps=gaps):
                doc = Document()
                doc.add_paragraph("Participant ID: __________")
                doc.add_paragraph("Consultant review", style="Heading 2")
                doc.add_paragraph("Signed by the consultant:")
                for _ in range(gaps):
                    doc.add_paragraph("")
                bordered_box(doc)
                places = held(saved(doc))
                self.assertEqual(places["b/tbl[0]/tr[0]/tc[0]"].code, "consent")
                for n in range(gaps):
                    self.assertEqual(places["b/p[%d]" % (3 + n)].code, "signing")

    def test_F1_d_a_text_box_caption_holds_its_writing_line(self):
        places = held(text_box_form("Signature of clinician", "______"))
        self.assertEqual(places["b/p[1]/txbx[0]/p[1]"].code, "signing")
        self.assertNotIn("b/p[1]/txbx[0]/p[1]", held(text_box_form("Plan", "______")))

    def test_F1_e_a_line_over_a_signing_caption_printed_below_it(self):
        data = lines_form("Discharge summary", "____\t\t____", "Signature\t\tDate")
        self.assertEqual(held(data)["b/p[1]"].code, "signing")
        engine = next(f for f in w.inspect(data)["fields"] if f["locator"]["slot"] == "b/p[1]")
        self.assertTrue(engine.get("write_protected"))
        # Two separately printed blanks pair with two captions: only the signature's is held.
        data = lines_form("Discharge summary", "________ / ________", "Signature\t\t\tDate")
        self.assertEqual(held(data)["b/p[1]"].ranges, ((0, 8),))
        data = lines_form("Discharge summary", "________ / ________", "Date\t\t\tSignature")
        self.assertEqual(held(data)["b/p[1]"].ranges, ((11, 19),))
        # Control: a line over an ordinary caption stays answerable.
        self.assertNotIn("b/p[1]", held(lines_form("Discharge summary", "____\t\t____", "Plan\t\tDate")))

    def test_F1_f_a_table_cell_over_a_signing_caption_printed_below_it(self):
        places = held(table_form([["", ""], ["Signature of clinician", "Date"]], title="Review"))
        self.assertEqual(places["b/tbl[0]/tr[0]/tc[0]"].code, "signing")
        self.assertNotIn("b/tbl[0]/tr[0]/tc[1]", places)
        places = held(table_form([[""], ["Signature of clinician"]], title="Review"))
        self.assertEqual(places["b/tbl[0]/tr[0]/tc[0]"].code, "signing")

    def test_F6_a_heading_caption_holds_its_drawn_line(self):
        for heading in ("Patient signature", "Sign & date", "Signature"):
            with self.subTest(heading=heading):
                doc = Document()
                doc.add_paragraph("Consent form")
                doc.add_paragraph(heading, style="Heading 2")
                paragraph = doc.add_paragraph()
                paragraph.add_run("\t\t\t").underline = True
                self.assertEqual(held(saved(doc))["b/p[2]"].code, "signing")

    def test_R2_F2_an_empty_line_in_a_declaration_block_after_its_table_is_held(self):
        doc = Document()
        doc.add_paragraph("Declaration", style="Heading 2")
        doc.add_paragraph("I declare the person examined agreed to this examination.")
        doc.add_paragraph("Signature of examining clinician: ______________")
        table = doc.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "Clinician initials"
        doc.add_paragraph("")
        doc.add_paragraph("Findings", style="Heading 2")
        doc.add_paragraph("")
        places = held(saved(doc))
        self.assertEqual(places["b/p[3]"].code, "declaration")
        self.assertNotIn("b/p[5]", places)          # control: another section's empty line


class RefutedTableCaptions(unittest.TestCase):
    """F2, F7: a table's signing column read from structure, whatever the engine made of its header."""

    def signing_cells(self, data):
        return {slot for slot, entry in held(data).items() if slot.count("/") == 3 and entry.code == "signing"}

    def test_F2_corner_mid_table_trailing_empty_and_boxed_headers_and_a_continued_table(self):
        places = held(table_form([["", "Name", "Signature", "Date"], ["Nurse", "", "", ""], ["Doctor", "", "", ""]]))
        self.assertTrue({"b/tbl[0]/tr[1]/tc[2]", "b/tbl[0]/tr[2]/tc[2]"} <= set(places))
        self.assertFalse({"b/tbl[0]/tr[1]/tc[1]", "b/tbl[0]/tr[1]/tc[3]"} & set(places))
        places = held(table_form([["Check", "Result", "Notes"], ["Consent", "", ""], ["Site marked", "", ""],
                                  ["Check", "Result", "Signature"], ["Swab count", "", ""], ["Instrument count", "", ""]]))
        self.assertTrue({"b/tbl[0]/tr[4]/tc[2]", "b/tbl[0]/tr[5]/tc[2]"} <= set(places))
        self.assertFalse({"b/tbl[0]/tr[1]/tc[2]", "b/tbl[0]/tr[2]/tc[2]", "b/tbl[0]/tr[5]/tc[1]"} & set(places))
        for header in (["Drug", "Dose", "Time", "Signature", ""], ["Drug", "Dose", "Given \u2610", "Signature"]):
            with self.subTest(header=header):
                rows = [header] + [["Paracetamol"] + [""] * (len(header) - 1), ["Ibuprofen"] + [""] * (len(header) - 1)]
                places = held(table_form(rows))
                self.assertTrue({"b/tbl[0]/tr[1]/tc[3]", "b/tbl[0]/tr[2]/tc[3]"} <= set(places))
                self.assertFalse({"b/tbl[0]/tr[1]/tc[1]", "b/tbl[0]/tr[1]/tc[2]"} & set(places))
        data = table_form([["Drug", "Dose", "Time", "Signature"], ["Ibuprofen", "", "", ""]], between="Continued from previous page",
                          more=[["Paracetamol", "", "", ""], ["Codeine", "", "", ""]])
        places = held(data)
        self.assertTrue({"b/tbl[1]/tr[0]/tc[3]", "b/tbl[1]/tr[1]/tc[3]"} <= set(places))
        self.assertFalse({"b/tbl[1]/tr[0]/tc[1]", "b/tbl[1]/tr[0]/tc[2]"} & set(places))
        # A column of option lists ('☐ checked ☐ deferred') is a column of answers: the header above them captions the
        # cell below.
        places = held(table_form([["", "Name", "Signed"], ["Nurse", "", "\u2610 checked \u2610 deferred"], ["Doctor", "", ""]]))
        self.assertEqual(places["b/tbl[0]/tr[2]/tc[2]"].code, "signing")
        self.assertNotIn("b/tbl[0]/tr[2]/tc[1]", places)
        # Control: a printed caption between the tables starts another table; nothing is inherited.
        data = table_form([["Drug", "Dose", "Time", "Signature"], ["Ibuprofen", "", "", ""]], between="Observations:",
                          more=[["Pulse", "", "", ""]])
        self.assertNotIn("b/tbl[1]/tr[0]/tc[3]", held(data))

    def test_F7_a_header_or_row_label_inside_a_locked_content_control(self):
        def control(cell, text):
            sdt = OxmlElement("w:sdt"); properties = OxmlElement("w:sdtPr"); lock = OxmlElement("w:lock")
            lock.set(qn("w:val"), "sdtContentLocked"); properties.append(lock); properties.append(OxmlElement("w:text"))
            content = OxmlElement("w:sdtContent"); run = OxmlElement("w:r"); t = OxmlElement("w:t"); t.text = text
            run.append(t); content.append(run); sdt.append(properties); sdt.append(content)
            cell.paragraphs[0]._p.append(sdt)
        doc = Document(); doc.add_paragraph("Clinic record")
        table = doc.add_table(rows=2, cols=2); control(table.cell(0, 0), "Name"); control(table.cell(0, 1), "Signature")
        places = held(saved(doc))
        self.assertEqual(places["b/tbl[0]/tr[1]/tc[1]"].code, "signing")
        self.assertNotIn("b/tbl[0]/tr[1]/tc[0]", places)
        doc = Document(); doc.add_paragraph("Clinic record")
        table = doc.add_table(rows=2, cols=2); table.cell(0, 0).text = "Plan"; control(table.cell(1, 0), "Consultant signature")
        self.assertEqual(held(saved(doc))["b/tbl[0]/tr[1]/tc[1]"].code, "signing")

    def test_R3_H2_a_declaration_row_holds_its_answer_cells_not_a_cell_with_its_own_caption(self):
        doc = Document(); doc.add_paragraph("Clinic letter")
        table = doc.add_table(rows=1, cols=3)
        table.cell(0, 0).text = "I confirm the findings above are accurate"
        table.cell(0, 1).text = "\u2610"
        table.cell(0, 2).text = "Date of visit: ____"
        places = held(saved(doc))
        self.assertEqual(places["b/tbl[0]/tr[0]/tc[1]"].code, "declaration")
        self.assertNotIn("b/tbl[0]/tr[0]/tc[2]", places)
        date = next(f for f in w.inspect(saved(doc))["fields"] if f["kind"] == "date")
        self.assertFalse(date.get("write_protected"))


class RefutedReadings(unittest.TestCase):
    """F3, F4, F8, F10, R3-H1, R3-H2, R3-H3, R3-M2, R3-M3, R3-L2: the readers, by structure."""

    def test_F3_first_person_declarations_in_every_shape_are_held(self):
        for line in ("I ____________________ (full name) consent to the procedure described above.",
                     "To the best of my knowledge I confirm that the information above is correct: ____________",
                     "Having read the leaflet I agree to proceed: ____________",
                     "The information I have provided is accurate: ____________",
                     "To the best of my knowledge I confirm the above is correct: ____________",
                     "I CONFIRM THAT THE INFORMATION ABOVE IS CORRECT: ____________",
                     "I confirm that the information above is correct: ____________"):
            with self.subTest(line=line):
                data = lines_form("Patient declaration", line)
                self.assertEqual(held(data)["b/p[1]"].code, "declaration")
                self.assertTrue(all(f.get("write_protected") for f in w.inspect(data)["fields"]
                                    if f["locator"]["slot"].startswith("b/p[1]") and f["kind"] not in w.SIGNING_KINDS))
        doc = Document(); doc.add_paragraph("Patient declaration")
        paragraph = doc.add_paragraph("I ")
        sdt = OxmlElement("w:sdt"); properties = OxmlElement("w:sdtPr"); alias = OxmlElement("w:alias")
        alias.set(qn("w:val"), "Full name"); properties.append(alias); properties.append(OxmlElement("w:text"))
        content = OxmlElement("w:sdtContent"); run = OxmlElement("w:r"); t = OxmlElement("w:t"); t.text = "Click here to enter text."
        run.append(t); content.append(run); sdt.append(properties); sdt.append(content); paragraph._p.append(sdt)
        paragraph.add_run(" confirm that the information I have given is correct.")
        self.assertEqual(held(saved(doc))["b/p[1]"].code, "declaration")

    def test_a_first_person_statement_answered_by_a_selection_stays_held(self):
        # Released only where the answer completes the statement with text (R3-H2); a statement the declarant answers by
        # ticking stays a declaration, on its own line or with the boxes on the next line (no weakening of be5fba45).
        for lines in (("I agree to: \u2610 photographs \u2610 teaching",), ("I agree to:", "\u2610 photographs \u2610 teaching"),
                      ("Consent (I agree to the operation): \u2610",)):
            with self.subTest(lines=lines):
                places = held(lines_form("Plan: ______", *lines))
                for n in range(len(lines)):
                    self.assertEqual(places["b/p[%d]" % (n + 1)].code, "declaration")
        for answer in ("\u2610", "\u2610 photographs \u2610 teaching"):
            with self.subTest(row=answer):
                doc = Document(); doc.add_paragraph("Consent to teaching")
                table = doc.add_table(rows=1, cols=2)
                table.cell(0, 0).text = "I agree to"
                table.cell(0, 1).text = answer
                self.assertEqual(held(saved(doc))["b/tbl[0]/tr[0]/tc[1]"].code, "declaration")
        # Control: the same row answered in words stays an ordinary answer ('We recommend review in | ____').
        doc = Document(); doc.add_paragraph("Plan")
        table = doc.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "We recommend review in"
        self.assertNotIn("b/tbl[0]/tr[0]/tc[1]", held(saved(doc)))

    def test_R3_H1_H2_numerals_asides_conditions_and_completed_statements_stay_ordinary(self):
        for line in ("NYHA class: I, II, III, IV __________", "Tear grade (I, II, III): __________",
                     "ST elevation in leads: I, II, III __________", "Heart block type: I or II __________",
                     "Mobitz (I or II): __________", "I and D of abscess: __________", "Diabetes: Type I diabetes __________",
                     "Diabetes:\tType I\tType II\t__________", "Grade:\tI\tII\tIII\t__________",
                     "Allergies (so we can keep you safe): __________", "We recommend review in: __________",
                     "If we need to contact you, telephone: __________", "I reviewed this patient in clinic on __________.",
                     "If we need to contact you, telephone: \u2610 mobile \u2610 landline",
                     "Allergies (so we can keep you safe): \u2610 None known"):
            with self.subTest(line=line):
                data = lines_form("Presenting complaint: __________", line)
                self.assertNotIn("b/p[1]", held(data))
                self.assertFalse(any(f.get("write_protected") for f in w.inspect(data)["fields"]))

    def test_F4_R3_H3_the_signing_act_and_the_clinical_sign(self):
        for caption in ("Sign & date", "Signature, date", "Signature, name and date", "Signature/stamp/date",
                        "Signature (and date)", "Sign, date and time", "Doctor sign/date", "Nurse sign", "Sign & print name",
                        "eSignature", "Sig\u00adnature", "Signa\u200bture"):
            with self.subTest(caption=caption):
                data = lines_form("Plan: ______", caption + ": ____________")
                self.assertEqual(held(data)["b/p[1]"].code, "signing")
                self.assertEqual(w.kind_for_label(caption), "signature")
        for caption, kind in (("Sign(s) of infection", "text"), ("Sign present", "text"), ("SIGN PRESENT", "text"),
                              ("Signature da\u00adte", "date"), ("Da\u00adte signed", "date"),
                              ("Murphy's sign", "text"), ("Sign elicited", "text"),
                              ("Sign language interpreter required", "text"), ("Sign and symptom review", "text"),
                              ("Sign of infection", "text"), ("Vital signs", "text"), ("Signs and symptoms", "text"),
                              ("Signature date", "date"), ("Date signed", "date"), ("Date of signature", "date")):
            with self.subTest(caption=caption):
                self.assertEqual(w.kind_for_label(caption), kind)
                self.assertNotIn("b/p[1]", held(lines_form("Plan: ______", caption + ": ____________")))
        for header in ("Sign & date", "Nurse sign"):
            with self.subTest(header=header):
                doc = Document(); doc.add_paragraph("Administration record")
                table = doc.add_table(rows=3, cols=4)
                for column, text in enumerate(("Drug", "Dose", "Time", header)):
                    table.cell(0, column).text = text
                data = saved(doc)
                field = next(f for f in w.inspect(data)["fields"] if f["kind"] == "table_rows")
                with self.assertRaises(w.V3Failure) as refused:
                    w.fill(data, [field], {field["key"]: [["Paracetamol", "1 g", "08:00", "SYNTHETIC-SIG"]]})
                self.assertEqual(refused.exception.code, "held_place")
                w.fill(data, [field], {field["key"]: [["Paracetamol", "1 g", "08:00", ""]]})

    def test_F8_a_consent_declaration_in_a_patient_section_is_never_answered_under_its_policy(self):
        data = lines_form("Pre-operative questionnaire", "Completed by the patient:",
                          "I consent to the procedure described above: ____________", "I have read the leaflet: ____________")
        fields = {f["label"]: f for f in w.inspect(data)["fields"]}
        consent = fields["I consent to the procedure described above"]
        self.assertTrue(consent.get("write_protected"))
        self.assertEqual(consent["review_reason"], w.HELD_REASONS["attestation"])
        package = w.open_package(data)
        source = w.Detector(package, layout_proposal=True); source.detect()
        authority = w.held_places(package, source)
        stored = {**consent, "write_protected": False}
        found = w.held_violation(source.index, authority, stored)
        self.assertEqual(found[1].code, "attestation")         # what the patient-source policy does not cover
        # A statement the patient REPORTS stays answerable under the printed patient-source policy.
        reported = fields["I have read the leaflet"]
        self.assertIsNone(w.held_violation(source.index, authority, {**reported, "write_protected": False}))

    def test_R3_M2_M3_L2_consent_is_read_by_the_same_readers_in_a_box_and_on_a_line(self):
        for title in ("Minor surgery consent and procedure record", "Procedure, consent and signature record"):
            with self.subTest(title=title):
                # The box's own section is its innermost heading; an outer title (even one naming signing) is not.
                doc = Document()
                doc.add_paragraph(title, style="Heading 1")
                doc.add_paragraph("Wound review", style="Heading 2")
                doc.add_paragraph("Please describe the wound?")
                bordered_box(doc)
                self.assertNotIn("b/tbl[0]/tr[0]/tc[0]", held(saved(doc)))
        for caption in ("Consent obtained by (name and grade):", "Consent obtained - state who explained the risks:",
                        "Consent obtained - state that the risks were explained:",
                        "Patient consented and said that the pain had settled:"):
            with self.subTest(caption=caption):
                doc = Document(); doc.add_paragraph("Procedure record"); doc.add_paragraph(caption); bordered_box(doc)
                self.assertNotIn("b/tbl[0]/tr[0]/tc[0]", held(saved(doc)))
                self.assertNotIn("b/p[1]", held(lines_form("Procedure record", caption + " __________")))
        self.assertEqual(held(lines_form("Procedure record", "Record that the patient consents to proceed: ______"))["b/p[1]"].code,
                         "attestation")


class RefutedExchange(unittest.TestCase):
    """R3-M1, R2-F4: the isolated parser asks for every key a reader meets, and the readings never count against the
    mapping and answer limit."""

    def test_R3_M1_the_sandboxed_authority_equals_the_in_process_one_on_tab_and_break_lines(self):
        import tempfile
        from pathlib import Path
        from .service import held_places
        doc = Document()
        doc.add_paragraph("Presenting complaint: __________")
        doc.add_paragraph("Diabetes:\tType I\tType II\t__________")
        doc.add_paragraph("Grade:\tI\tII\tIII\t__________")
        paragraph = doc.add_paragraph("Stage I")
        paragraph.add_run().add_break()
        paragraph.add_run("Stage II: __________")
        doc.add_paragraph("I confirm the plan:\t__________")
        data = saved(doc)
        with tempfile.TemporaryDirectory(prefix="held-exchange-") as directory:
            path = Path(directory) / "form.docx"
            path.write_bytes(data)
            report = held_places(path)
        self.assertEqual({row["slot"]: row["code"] for row in report["held"]}, {BODY + k: v.code for k, v in held(data).items()})
        self.assertEqual(set(held(data)), {"b/p[4]"})

    def test_a_key_met_without_a_reading_is_asked_for_and_only_the_last_round_reads_it_as_holding(self):
        import json
        import tempfile
        from pathlib import Path
        from . import engine
        data = lines_form("Plan: ______", "Sign present: ______")
        saved_readings = w.READINGS
        try:
            with tempfile.TemporaryDirectory(prefix="held-rounds-") as directory:
                workspace = Path(directory)
                (workspace / "input.docx").write_bytes(data)
                request = {"operation": "held_places", "format": "docx", "engine": "v3", "mapping": None}
                first = engine.process(workspace, request)
                self.assertIn("s:Sign present", first["readings_needed"])
                # Readings for nothing, nothing asked yet: the consulted keys are asked for, never defaulted.
                (workspace / "readings.json").write_text(json.dumps({"readings": {}, "asked": []}))
                again = engine.process(workspace, request)
                self.assertIn("s:Sign present", again["readings_needed"])
                # The last round reads an unread key as holding.
                (workspace / "readings.json").write_text(json.dumps({"readings": {}, "asked": [], "final": True}))
                last = engine.process(workspace, request)
                self.assertIn(BODY + "b/p[1]", [row["slot"] for row in last["held"]])
                # With the parent's reading the clinical sign is ordinary.
                from .syntax_readings import read_clauses
                readings, asked, response = {}, [], first
                for _ in range(w.MAX_READING_ROUNDS):
                    if "readings_needed" not in response:
                        break
                    readings.update({w.reading_digest(k): v for k, v in read_clauses(response["readings_needed"]).items()})
                    asked += [w.reading_digest(k) for k in response["readings_needed"]]
                    (workspace / "readings.json").write_text(json.dumps({"readings": readings, "asked": asked}))
                    response = engine.process(workspace, request)
                self.assertNotIn(BODY + "b/p[1]", [row["slot"] for row in response["held"]])
        finally:
            w.use_readings(saved_readings)

    def test_R2_F4_readings_travel_beside_the_request_keyed_by_digest(self):
        import json
        import subprocess
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from . import service
        seen = []
        real = subprocess.run

        def spy(command, *args, **kwargs):
            workspace = Path(command[-1])
            exchange = workspace / "readings.json"
            seen.append(((workspace / "request.json").read_bytes(), exchange.read_bytes() if exchange.exists() else None))
            return real(command, *args, **kwargs)
        data = lines_form("Plan: ______", "Sign present: ______", "I confirm the plan: ______")
        with tempfile.TemporaryDirectory(prefix="held-digest-") as directory:
            path = Path(directory) / "form.docx"
            path.write_bytes(data)
            with patch.object(service.subprocess, "run", side_effect=spy):
                service.held_places(path)
        self.assertGreaterEqual(len(seen), 2)
        self.assertEqual({request for request, _ in seen}, {seen[0][0]})       # the request never grows
        self.assertNotIn("readings", json.loads(seen[0][0]))
        exchange = json.loads(seen[-1][1])
        self.assertTrue(exchange["readings"])
        self.assertTrue(all(len(key) == 32 and all(c in "0123456789abcdef" for c in key) for key in exchange["readings"]))
        self.assertNotIn("Sign present", seen[-1][1].decode())

#: The round-3 over-hold battery (rebuild/.runtime/v1-closeout-20260929 RR3-1, RR3-2): ordinary examination and grading
#: labels that the signing and declaration readers must leave answerable, on the v3 authority and the legacy fill.
CLINICAL_SIGNS = ("Babinski sign", "Romberg sign", "Kernig sign", "Murphy sign", "Rovsing sign", "Tinel sign",
                  "Sign of infection", "Meningeal sign", "Warning sign", "Target sign", "Halo sign", "Crescent sign",
                  "String sign", "Lachman sign", "McMurray sign", "Blumberg sign", "Obturator sign", "Psoas sign",
                  "Battle sign", "Phalen sign", "Lhermitte sign", "Trendelenburg sign", "Chvostek sign", "Homans sign",
                  "Grey Turner sign", "Kehr sign", "Trousseau sign", "Brudzinski sign", "Hawkins sign")
NUMERAL_LABELS = ("Grade I reflux", "Grade I haemorrhoids", "Grade I varices", "Grade I oesophageal varices",
                  "Grade I sprain", "Grade I tear", "Grade I perineal tear", "Grade I diastolic dysfunction",
                  "Grade I hydronephrosis", "Grade I spondylolisthesis", "Stage I disease", "Stage I pressure ulcer",
                  "Stage I hypertension", "Stage I cancer", "Stage I AKI", "Class I obesity", "Class I malocclusion",
                  "Class I heart failure", "Class I angina", "Class I recommendation", "Type I endoleak",
                  "Type I respiratory failure", "Type I error", "Type I fracture", "ASA I", "ASA grade I",
                  "Mallampati class I airway", "Level I trauma", "Dose I given", "Phase I trial", "Grade I", "Stage I",
                  "Class I", "Grade I-II reflux", "Grade I/IV murmur", "Grade I murmur", "Degree I heart block",
                  "Grade I lesion seen", "Grade I tumour")
ORDINARY = ("Vital signs", "Initial assessment", "Consent obtained", "Signs and symptoms", "Initial dose",
            "Sign language interpreter required", "Sign present", "Positive Romberg sign", "Murphy's sign")


def body_marker(doc, tag, **attrs):
    """Append a body-level element that prints nothing (a range marker) before the section properties."""
    element = OxmlElement(tag)
    for name, value in attrs.items():
        element.set(qn("w:" + name), value)
    doc.element.body.insert(len(doc.element.body) - 1, element)
    return element


def block_control(doc, text, placeholder=False, alias=None):
    """Append a BLOCK-level plain-text content control holding one paragraph `text`."""
    sdt, pr, content, paragraph, run, t = (OxmlElement(x) for x in ("w:sdt", "w:sdtPr", "w:sdtContent", "w:p", "w:r", "w:t"))
    identifier = OxmlElement("w:id"); identifier.set(qn("w:val"), "41"); pr.append(identifier)
    if alias:
        name = OxmlElement("w:alias"); name.set(qn("w:val"), alias); pr.append(name)
    if placeholder:
        pr.append(OxmlElement("w:showingPlcHdr"))
    pr.append(OxmlElement("w:text"))
    t.text = text; t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    run.append(t); paragraph.append(run); content.append(paragraph); sdt.append(pr); sdt.append(content)
    doc.element.body.insert(len(doc.element.body) - 1, sdt)
    return sdt


class RoundThreeAuthority(unittest.TestCase):
    """Round 3 of the signing/identity/attestation authority: the over-holds RR3-1 (a clinical 'sign' noun) and RR3-2
    (a roman-numeral 'I') are ordinary answers again, and the leak gaps RR1-RR4 and RR7 are closed by structure."""

    def test_RR3_1_a_clinical_sign_noun_is_ordinary_and_the_signing_act_is_not(self):
        for label in CLINICAL_SIGNS + ORDINARY:
            with self.subTest(label=label):
                self.assertNotIn(w.kind_for_label(label), w.SIGNING_KINDS)
        data = lines_form("Neurological and abdominal examination", *("%s: ____" % x for x in CLINICAL_SIGNS[:6]))
        self.assertEqual(held(data), {})
        self.assertFalse(any(f.get("write_protected") or f["kind"] in w.SIGNING_KINDS for f in w.inspect(data)["fields"]))
        doc = Document(); doc.add_paragraph("Neurological examination")
        table = doc.add_table(rows=3, cols=2); table.cell(0, 1).text = "Finding"
        table.cell(1, 0).text = "Babinski sign"; table.cell(2, 0).text = "Romberg sign"
        self.assertEqual(held(saved(doc)), {})
        # The signing ACT stays held: a verb, a list of acts, the bare caption, a person who signs.
        for label in ("Sign", "Sign below", "Please sign", "Patient to sign", "Sign here", "Sign & date", "Sign, date and time",
                      "Doctor sign/date", "Sign/date", "Sign & print name", "Nurse sign", "Patient sign", "Witness sign",
                      "Patient must sign", "Countersign"):
            with self.subTest(act=label):
                self.assertEqual(w.kind_for_label(label), "signature")
                self.assertEqual(held(lines_form("Plan: ______", label + ": ____________"))["b/p[1]"].code, "signing")

    def test_RR3_2_a_roman_numeral_I_is_never_a_first_person_declaration(self):
        for label in NUMERAL_LABELS + ("Type I diabetes", "NYHA class I"):
            with self.subTest(label=label):
                self.assertEqual(w.statement_codes(label), frozenset())
                self.assertEqual(w.statement_codes(label + " \u2610 Yes \u2610 No", selection=True), frozenset())
        data = lines_form("Findings", *("%s: ____________" % x for x in NUMERAL_LABELS))
        self.assertEqual(held(data), {})
        self.assertFalse(any(f.get("write_protected") for f in w.inspect(data)["fields"]))
        # Controls: the declarant 'I' of a finite verb, however the sentence opens.
        for line in ("I confirm the above is correct: ____", "Today I confirm the above is correct: ____",
                     "To the best of my knowledge I confirm that the information above is correct: ____",
                     "I, the undersigned, confirm the above: ____", "I understood the risks: ____"):
            with self.subTest(line=line):
                self.assertIn("declaration", held(lines_form("Plan: ______", line))["b/p[1]"].codes)

    def test_RR1_a_declaration_completed_by_its_blank_is_held_with_the_ticks_it_governs(self):
        for line in ("I hereby certify that ______", "I agree to ______", "I understand that ______",
                     "I have been informed that ______", "I am aware that ______", "I confirm that ______"):
            with self.subTest(line=line):
                data = lines_form("Consent form", "Patient declaration", line, "Plan: ______")
                self.assertIn("declaration", held(data)["b/p[2]"].codes)
                field = next(f for f in w.inspect(data)["fields"] if f["label"] != "Plan")
                self.assertTrue(field.get("write_protected"))
        data = lines_form("Consent form", "Patient declaration", "I declare that:", "______", "Plan: ______")
        places = held(data)
        self.assertIn("declaration", places["b/p[2]"].codes)
        self.assertIn("declaration", places["b/p[3]"].codes)
        doc = Document(); doc.add_paragraph("Patient declaration"); doc.add_paragraph("I agree to:")
        box = doc.add_table(rows=1, cols=1); box.cell(0, 0).text = "\u2610 photographs \u2610 teaching"
        doc.add_paragraph("Plan: ______")
        places = held(saved(doc))
        self.assertIn("declaration", places["b/tbl[0]/tr[0]/tc[0]"].codes)
        self.assertFalse(places["b/tbl[0]/tr[0]/tc[0]"].selection)
        # Controls (R3-H2): a statement whose blank answers an adjunct or an object's preposition stays answerable.
        for line in ("We recommend review in: ____", "I reviewed this patient in clinic on ____.", "I am allergic to: ____",
                     "If we need to contact you, telephone: ____", "Allergies (so we can keep you safe): ____",
                     "I was admitted to hospital on: ____"):
            with self.subTest(control=line):
                self.assertNotIn("b/p[1]", held(lines_form("Plan: ______", line)))

    def test_RR2_options_printed_in_a_table_answer_the_consent_declaration_before_it(self):
        question = "I confirm that I consent to the operation described above:"
        for rows in ((("\u2610 Yes", "\u2610 No"),), (("\u2610 Yes",), ("\u2610 No",)), (("Yes", "\u2610"), ("No", "\u2610"))):
            with self.subTest(rows=rows):
                doc = Document(); doc.add_paragraph("Patient consent"); doc.add_paragraph(question)
                table = doc.add_table(rows=len(rows), cols=len(rows[0]))
                for r, row in enumerate(rows):
                    for c, value in enumerate(row):
                        table.cell(r, c).text = value
                doc.add_paragraph("Plan: ______")
                data = saved(doc)
                places = held(data)
                cells = [slot for slot in places if slot.startswith("b/tbl[0]/") and slot.count("/") == 3]
                self.assertEqual(len(cells), len(rows) * len(rows[0]))
                self.assertTrue(all("declaration" in places[c].codes and not places[c].selection for c in cells))
                choices = [f for f in w.inspect(data)["fields"] if f["locator"]["slot"].startswith("b/tbl[0]")]
                self.assertTrue(choices)
                self.assertTrue(all(f.get("write_protected") for f in choices), choices)
        # Control: the same table under an ordinary question is not held.
        doc = Document(); doc.add_paragraph("Smoking history"); doc.add_paragraph("Current smoker:")
        table = doc.add_table(rows=1, cols=2); table.cell(0, 0).text = "\u2610 Yes"; table.cell(0, 1).text = "\u2610 No"
        self.assertFalse([slot for slot in held(saved(doc)) if slot.startswith("b/tbl[0]")])

    def test_RR3_range_markers_and_block_controls_are_transparent_to_the_caption_walk(self):
        for tag, attrs in (("w:bookmarkStart", {"id": "7", "name": "sig"}), ("w:bookmarkEnd", {"id": "7"}),
                           ("w:permStart", {"id": "3", "edGrp": "everyone"}), ("w:commentRangeStart", {"id": "1"}),
                           ("w:proofErr", {"type": "spellStart"})):
            with self.subTest(marker=tag):
                doc = Document(); doc.add_paragraph("Clinic letter"); doc.add_paragraph("Plan: ______")
                doc.add_paragraph("Signature of consultant:"); body_marker(doc, tag, **attrs); doc.add_paragraph("_" * 30)
                data = saved(doc)
                self.assertEqual(held(data)["b/p[3]"].code, "signing")
                self.assertEqual(w.held_report(data, [text_field("b/p[3]")])["violations"]["probe"]["code"], "signing")
        for placeholder, text in ((False, "_" * 30), (True, "Click or tap here to enter text.")):
            with self.subTest(block_control=text):
                doc = Document(); doc.add_paragraph("Clinic letter"); doc.add_paragraph("Signature of consultant:")
                block_control(doc, text, placeholder=placeholder)
                self.assertEqual(held(saved(doc))["b/sdt[0]"].code, "signing")
        doc = Document(); doc.add_paragraph("Clinic letter"); block_control(doc, "Signature of consultant:")
        doc.add_paragraph("_" * 30)
        self.assertEqual(held(saved(doc))["b/p[1]"].code, "signing")
        doc = Document(); doc.add_paragraph("Clinic letter"); doc.add_paragraph("_" * 30)
        body_marker(doc, "w:permEnd", id="3"); doc.add_paragraph("Signature of consultant")
        self.assertEqual(held(saved(doc))["b/p[1]"].code, "signing")
        doc = Document(); doc.add_paragraph("Administration record")
        first = doc.add_table(rows=2, cols=4)
        for c, value in enumerate(("Drug", "Dose", "Time", "Signature")):
            first.cell(0, c).text = value
        first.cell(1, 0).text = "Ibuprofen"
        body_marker(doc, "w:bookmarkEnd", id="9"); doc.add_paragraph("Continued from previous page")
        second = doc.add_table(rows=2, cols=4); second.cell(0, 0).text = "Paracetamol"; second.cell(1, 0).text = "Codeine"
        places = held(saved(doc))
        self.assertEqual({slot for slot in places if slot.startswith("b/tbl[1]/")},
                         {"b/tbl[1]/tr[0]/tc[3]", "b/tbl[1]/tr[1]/tc[3]"})

    def test_RR4_a_caption_whose_head_is_a_signature_governs_whatever_its_length(self):
        for caption in ("Signature of the patient or person with parental responsibility",
                        "Signature of witness (if the patient is unable to sign)",
                        "Signature of interpreter (where an interpreter has been used)",
                        "Name and signature of the person obtaining consent on behalf of the team"):
            with self.subTest(caption=caption):
                self.assertTrue(w.signing_caption(caption))
                self.assertEqual(held(lines_form("Consent: ______", "_" * 30, caption))["b/p[1]"].code, "signing")
                self.assertEqual(held(lines_form("Consent: ______", caption, "_" * 30))["b/p[2]"].code, "signing")
        doc = Document(); table = doc.add_table(rows=2, cols=3)
        for c, value in enumerate(("", "Name", "Signature of witness (if the patient is unable to sign)")):
            table.cell(0, c).text = value
        table.cell(1, 0).text = "Witness"
        self.assertEqual(held(saved(doc))["b/tbl[0]/tr[1]/tc[2]"].code, "signing")
        # Guidance that merely mentions signing captions nothing.
        for guidance in ("Describe the procedure; the signed consent form is filed with the notes.",
                         "Please ensure the patient has signed the form before the operation begins today"):
            with self.subTest(guidance=guidance):
                self.assertFalse(w.signing_caption(guidance))
                self.assertNotIn("b/p[2]", held(lines_form("Consent: ______", guidance, "_" * 30)))

    def test_RR7_a_block_control_in_a_signature_column_is_an_answer_place(self):
        doc = Document(); doc.add_paragraph("Theatre checklist")
        table = doc.add_table(rows=3, cols=4)
        for c, value in enumerate(("", "Name", "Signature", "Date")):
            table.cell(0, c).text = value
        table.cell(1, 0).text = "Nurse"; table.cell(2, 0).text = "Doctor"
        for r in (1, 2):
            tc = table.cell(r, 2)._tc
            paragraph = tc.findall(qn("w:p"))[0]
            holder = Document(); control = block_control(holder, "Click or tap here to enter text.", placeholder=True)
            tc.replace(paragraph, control)
        places = held(saved(doc))
        self.assertEqual(places["b/tbl[0]/tr[1]/tc[2]"].code, "signing")
        self.assertEqual(places["b/tbl[0]/tr[2]/tc[2]"].code, "signing")
        self.assertNotIn("b/tbl[0]/tr[1]/tc[3]", places)

    def test_RR6_an_agreement_to_a_procedure_is_never_answered_under_the_patients_policy(self):
        for line in ("I agree to the operation described above: ____________",
                     "I am happy to go ahead with the operation described above: ____________",
                     "I agree to the operation described above: \u2610 Yes \u2610 No"):
            with self.subTest(line=line):
                data = lines_form("Pre-operative questionnaire", "Completed by the patient:", line)
                self.assertIn("attestation", held(data)["b/p[2]"].codes)
                field = next(f for f in w.inspect(data)["fields"] if f["locator"]["slot"].startswith("b/p[2]"))
                self.assertTrue(field.get("write_protected"))
        data = lines_form("Pre-operative questionnaire", "Completed by the patient:", "I have read the leaflet: ____________")
        field = next(f for f in w.inspect(data)["fields"] if f["locator"]["slot"] == "b/p[2]")
        self.assertFalse(field.get("write_protected"))


class LegacyOverHoldBattery(unittest.TestCase):
    """THE LEGACY (non-v3, default) FILL refuses only what the battery's readings hold: every ordinary examination,
    grading and assessment row is written, and an administration record refuses only its signature answer."""

    def legacy(self, doc):
        import tempfile
        from pathlib import Path
        directory = tempfile.TemporaryDirectory(prefix="legacy-battery-"); self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "form.docx"
        path.write_bytes(saved(doc))
        return path, inspect_template(path, engine="legacy")["fields"], Path(directory.name)

    def test_every_battery_row_is_written_by_the_legacy_fill(self):
        labels = CLINICAL_SIGNS + NUMERAL_LABELS + ORDINARY
        doc = Document(); doc.add_paragraph("Examination")
        table = doc.add_table(rows=len(labels), cols=2)
        for r, label in enumerate(labels):
            table.cell(r, 0).text = label
        path, fields, directory = self.legacy(doc)
        self.assertEqual(len(fields), len(labels))
        fill_template(path, fields, {f["key"]: "SYNTHETIC-ANSWER" for f in fields}, directory / "out.docx")

    def test_an_administration_record_refuses_only_its_signature(self):
        doc = Document(); doc.add_paragraph("Medicines given")
        table = doc.add_table(rows=2, cols=4)
        for r, row in enumerate((("Drug", "", "Dose", ""), ("Time", "", "Signature", ""))):
            for c, value in enumerate(row):
                if value:
                    table.cell(r, c).text = value
        path, fields, directory = self.legacy(doc)
        by_label = {f["label"]: f for f in fields}
        fill_template(path, fields, {by_label[x]["key"]: "SYNTHETIC-ANSWER" for x in ("Drug", "Dose", "Time")},
                      directory / "out.docx")
        with self.assertRaises(DocumentError) as refused:
            fill_template(path, fields, {by_label["Signature"]["key"]: "SYNTHETIC-ANSWER"}, directory / "sig.docx")
        self.assertEqual(refused.exception.code, "held_place")


if __name__ == "__main__":
    unittest.main()
