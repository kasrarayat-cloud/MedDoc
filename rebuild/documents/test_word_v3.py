"""Contract v3 through the sandboxed worker, on synthetic blank forms built here (no patient data)."""

from copy import deepcopy
import io
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree

from .service import DocumentError, fill_template, inspect_template, locate_fields, outline_template

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"


def _sdt(kind, *, options=(), placeholder="Choose an item.", nested=None):
    sdt = OxmlElement("w:sdt")
    pr = OxmlElement("w:sdtPr")
    sdt.append(pr)
    if kind == "dropdown":
        dd = OxmlElement("w:dropDownList")
        for o in options:
            li = OxmlElement("w:listItem")
            li.set(qn("w:displayText"), o)
            li.set(qn("w:value"), o)
            dd.append(li)
        pr.append(dd)
        pr.append(OxmlElement("w:showingPlcHdr"))
    elif kind == "checkbox":
        cb = etree.SubElement(pr, "{%s}checkbox" % W14)
        etree.SubElement(cb, "{%s}checked" % W14).set("{%s}val" % W14, "0")
    content = OxmlElement("w:sdtContent")
    sdt.append(content)
    if nested is not None:
        content.append(nested)
    else:
        r = OxmlElement("w:r")
        t = OxmlElement("w:t")
        t.text = "☐" if kind == "checkbox" else placeholder
        r.append(t)
        content.append(r)
    return sdt


def ff_field(p, kind, options=(), checked=False, name="F"):
    """A legacy form field (FORMDROPDOWN or FORMCHECKBOX) appended to python-docx paragraph `p`."""
    def run(child):
        r = OxmlElement("w:r")
        r.append(child)
        p._p.append(r)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    data = OxmlElement("w:ffData")
    n = OxmlElement("w:name")
    n.set(qn("w:val"), name)
    data.append(n)
    data.append(OxmlElement("w:enabled"))
    if kind == "dropdown":
        dd = OxmlElement("w:ddList")
        for o in options:
            e = OxmlElement("w:listEntry")
            e.set(qn("w:val"), o)
            dd.append(e)
        data.append(dd)
    else:
        cb = OxmlElement("w:checkBox")
        cb.append(OxmlElement("w:sizeAuto"))
        d = OxmlElement("w:default")
        d.set(qn("w:val"), "1" if checked else "0")
        cb.append(d)
        data.append(cb)
    begin.append(data)
    run(begin)
    instr = OxmlElement("w:instrText")
    instr.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    instr.text = " FORMDROPDOWN " if kind == "dropdown" else " FORMCHECKBOX "
    run(instr)
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run(end)


def ff_result(path):
    with ZipFile(path) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    return [r.get("{%s}val" % W) for r in root.iter("{%s}result" % W)]


def build_form(path, *, nested_wrapper=False):
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
    doc.add_paragraph("Clinician signature: ____________")
    if nested_wrapper:
        inner_p = OxmlElement("w:p")
        inner_r = OxmlElement("w:r")
        inner_t = OxmlElement("w:t")
        inner_t.text = "Side: "
        inner_r.append(inner_t)
        inner_p.append(inner_r)
        inner_p.append(_sdt("dropdown", options=["Left", "Right"]))
        wrapper = _sdt("rich", nested=inner_p)
        doc.element.body.insert(len(doc.element.body) - 1, wrapper)
    doc.save(path)


def fields_by_label(fields):
    return {f["label"]: f for f in fields}


def part_text(path, part="word/document.xml"):
    with ZipFile(path) as z:
        root = etree.fromstring(z.read(part))
    return "".join(t.text or "" for t in root.iter("{%s}t" % W))


class ContractV3(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.original = self.dir / "form.docx"
        build_form(self.original)

    def tearDown(self):
        self.tmp.cleanup()

    def test_inspect_finds_every_structure_through_the_sandbox(self):
        info = inspect_template(self.original, engine="v3")
        self.assertEqual(info.get("contract"), "v3")
        by = fields_by_label(info["fields"])
        self.assertEqual(by["Referring physician"]["locator"]["target"]["type"], "cell")
        self.assertEqual(by["Date of visit"]["kind"], "date")
        self.assertEqual(by["Smoker?"]["kind"], "choice")
        self.assertEqual(by["Smoker?"]["options"], ["Yes", "No"])
        self.assertEqual(by["Laterality"]["options"], ["Left", "Right", "Bilateral"])
        self.assertEqual(by["Clinician signature"]["kind"], "signature")
        self.assertIn("word/header1.xml", {f["locator"]["part"] for f in info["fields"]})

    def test_fill_writes_answers_and_copies_every_other_part(self):
        info = inspect_template(self.original, engine="v3")
        by = fields_by_label(info["fields"])
        answers = {by["Referring physician"]["key"]: "Dr Example", by["Date of visit"]["key"]: "03/14/2026",
                   by["Smoker?"]["key"]: "No", by["Laterality"]["key"]: "Left", by["Patient name"]["key"]: "Synthetic Person"}
        out = self.dir / "out.docx"
        result = fill_template(self.original, info["fields"], answers, out)
        self.assertEqual(result["filled"], 5)
        body = part_text(out)
        self.assertIn("Dr Example", body)
        self.assertIn("03/14/2026", body)
        self.assertIn("Left", body)
        self.assertIn("Synthetic Person", part_text(out, "word/header1.xml"))
        self.assertIn("☐ Yes", body)             # the unchosen option stays printed
        self.assertIn("☒", body)                 # the chosen box is ticked
        with ZipFile(self.original) as a, ZipFile(out) as b:
            changed = {"word/document.xml", "word/header1.xml"}
            self.assertEqual([i.filename for i in a.infolist()], [i.filename for i in b.infolist()])
            for name in a.namelist():
                if name not in changed:
                    self.assertEqual(a.read(name), b.read(name), name)

    def test_signature_is_never_filled_and_a_moved_anchor_is_stale(self):
        info = inspect_template(self.original, engine="v3")
        by = fields_by_label(info["fields"])
        with self.assertRaises(DocumentError) as sig:
            fill_template(self.original, info["fields"], {by["Clinician signature"]["key"]: "Dr X"}, self.dir / "s.docx")
        self.assertEqual(sig.exception.code, "invalid_answer")
        tampered = deepcopy(info["fields"])
        for f in tampered:
            if f["label"] == "Referring physician":
                f["locator"]["fingerprint"] = "0" * 64
        with self.assertRaises(DocumentError) as stale:
            fill_template(self.original, tampered, {by["Referring physician"]["key"]: "x"}, self.dir / "t.docx")
        self.assertEqual(stale.exception.code, "stale_mapping")

    def test_an_option_not_printed_is_refused(self):
        info = inspect_template(self.original, engine="v3")
        by = fields_by_label(info["fields"])
        with self.assertRaises(DocumentError) as bad:
            fill_template(self.original, info["fields"], {by["Smoker?"]["key"]: "Former"}, self.dir / "o.docx")
        self.assertEqual(bad.exception.code, "invalid_answer")

    def test_a_control_wrapping_other_controls_is_read_by_its_parts_and_never_overwritten(self):
        wrapped = self.dir / "wrapped.docx"
        build_form(wrapped, nested_wrapper=True)
        info = inspect_template(wrapped, engine="v3")
        side = [f for f in info["fields"] if f["label"] == "Side"]
        self.assertEqual(len(side), 1)
        self.assertEqual(side[0]["options"], ["Left", "Right"])
        out = self.dir / "wrapped-out.docx"
        fill_template(wrapped, info["fields"], {side[0]["key"]: "Right"}, out)
        with ZipFile(wrapped) as a, ZipFile(out) as b:
            count = lambda z: etree.fromstring(z.read("word/document.xml")).findall(".//{%s}sdt" % W)
            self.assertEqual(len(count(a)), len(count(b)))

    def test_manual_field_is_located_recorded_as_manual_and_filled(self):
        outline = outline_template(self.original)
        slot = next(r for r in outline["slots"] if r["kind"] == "p" and r["preview"] == "Synthetic clinic intake")
        added = locate_fields(self.original, [{"slot": slot["slot"], "kind": "text", "label": "Clinic"}])["fields"]
        self.assertEqual(added[0]["origin"], "manual")
        out = self.dir / "manual.docx"
        fill_template(self.original, added, {added[0]["key"]: "North"}, out)
        self.assertIn("Synthetic clinic intake North", part_text(out))
        with self.assertRaises(DocumentError):
            cell = next(r for r in outline["slots"] if r["kind"] == "tc" and r["preview"] == "Allergies")
            locate_fields(self.original, [{"slot": cell["slot"], "kind": "text", "label": "Overwrite"}])

    def test_legacy_engine_is_unchanged_for_new_inspections_when_selected(self):
        try:
            info = inspect_template(self.original, engine="legacy")
        except DocumentError:
            return                               # the legacy contract refuses content controls, as before
        self.assertNotEqual(info.get("contract"), "v3")


def docx_bytes(doc):
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def knee_form(path):
    """F1: dropdown options that differ only by an abbreviation a list-marker strip would remove."""
    doc = Document()
    doc.add_paragraph("Synthetic knee injection note")
    p = doc.add_paragraph("Injection site: ")
    p._p.append(_sdt("dropdown", options=["Choose an item.", "Rt. knee", "Lt. knee", "Bil. knees"]))
    Path(path).write_bytes(docx_bytes(doc))


class OptionReader(unittest.TestCase):
    """F1: the engine chooses an option exactly as the review reads it: the stored label, trimmed, case only."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_reviewed_option_is_the_exported_option(self):
        knee_form(self.dir / "knee.docx")
        info = inspect_template(self.dir / "knee.docx", engine="v3")
        field = next(f for f in info["fields"] if f["kind"] == "choice")
        self.assertEqual(field["options"], ["Rt. knee", "Lt. knee", "Bil. knees"])
        for answer, shown in (("Lt. knee", "Injection site: Lt. knee"), (" lt. KNEE ", "Injection site: Lt. knee"),
                              ("Bil. knees", "Injection site: Bil. knees")):
            out = self.dir / ("out-%d.docx" % len(list(self.dir.iterdir())))
            fill_template(self.dir / "knee.docx", info["fields"], {field["key"]: answer}, out)
            self.assertIn(shown, part_text(out), answer)
        with self.assertRaises(DocumentError) as refused:
            fill_template(self.dir / "knee.docx", info["fields"], {field["key"]: "knee"}, self.dir / "never.docx")
        self.assertEqual(refused.exception.code, "invalid_answer")

    def test_options_that_differ_only_in_punctuation_stay_distinct(self):
        doc = Document()
        doc.add_paragraph("Synthetic follow-up")
        p = doc.add_paragraph("Imaging reviewed: ")
        p._p.append(_sdt("dropdown", options=["Choose an item.", "Yes", "Yes*", "No"]))
        (self.dir / "star.docx").write_bytes(docx_bytes(doc))
        info = inspect_template(self.dir / "star.docx", engine="v3")
        field = next(f for f in info["fields"] if f["kind"] == "choice")
        self.assertEqual(field["options"], ["Yes", "Yes*", "No"])
        fill_template(self.dir / "star.docx", info["fields"], {field["key"]: "Yes*"}, self.dir / "star-out.docx")
        self.assertIn("Imaging reviewed: Yes*", part_text(self.dir / "star-out.docx"))

    def test_list_markers_are_digits_single_letters_and_roman_numerals_only(self):
        from documents.word_v3 import clean_label
        kept = ["Rt. knee effusion", "Lt. knee", "Bil. knees", "Dr. Example", "No. of lesions", "Mr. Synthetic",
                "Hx. reviewed", "Pt. consent", "(c) Route"]     # R4: a single letter in parentheses is kept (fail closed)
        for text in kept:
            self.assertEqual(clean_label(text), text)
        stripped = {"1. Name": "Name", "12) Plan": "Plan", "a) Yes": "Yes", "B. No": "No", "(3) Dose": "Dose",
                    "c) Route": "Route", "iv. Findings": "Findings", "(xii) Impression": "Impression",
                    "XXX. Item": "Item", "vii) Item": "Item"}
        for text, label in stripped.items():
            self.assertEqual(clean_label(text), label, text)

    def test_laterality_survives_in_detected_and_typed_labels(self):
        doc = Document()
        doc.add_paragraph("Synthetic joint exam")
        doc.add_paragraph("Rt. knee effusion: ____________")
        doc.add_paragraph("Lt. knee effusion: ____________")
        doc.add_paragraph("")
        (self.dir / "joint.docx").write_bytes(docx_bytes(doc))
        info = inspect_template(self.dir / "joint.docx", engine="v3")
        self.assertEqual([f["label"] for f in info["fields"]], ["Rt. knee effusion", "Lt. knee effusion"])
        added = locate_fields(self.dir / "joint.docx", [{"slot": "word/document.xml#b/p[3]", "kind": "text",
                                                          "label": "Rt. knee aspirate volume"}])["fields"]
        self.assertEqual(added[0]["label"], "Rt. knee aspirate volume")



def repeated_options_form(path):
    """F7: one question printing the same option twice (boxes, a dropdown, printed words)."""
    doc = Document()
    doc.add_paragraph("Synthetic swelling check")
    doc.add_paragraph("Swelling:  ☐ Left  ☐ Right  ☐ Left")
    p = doc.add_paragraph("Answer given: ")
    p._p.append(_sdt("dropdown", options=["Choose an item.", "Yes", "No", "Yes"]))
    doc.add_paragraph("Was the dressing changed?")
    doc.add_paragraph("YES\t\tNO\t\tYES")
    Path(path).write_bytes(docx_bytes(doc))


class RepeatedOptions(unittest.TestCase):
    """F7: every printed option can be chosen, even one printed twice; fill maps by position."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.form = self.dir / "repeated.docx"
        repeated_options_form(self.form)
        self.fields = inspect_template(self.form, engine="v3")["fields"]
        self.by = fields_by_label(self.fields)

    def tearDown(self):
        self.tmp.cleanup()

    def test_repeated_options_get_print_order_suffixes(self):
        self.assertEqual(self.by["Swelling"]["options"], ["Left", "Right", "Left (2)"])
        self.assertEqual(self.by["Answer given"]["options"], ["Yes", "No", "Yes (2)"])
        self.assertEqual(self.by["Was the dressing changed?"]["options"], ["YES", "NO", "YES (2)"])
        self.assertEqual(self.by["Swelling"]["locator"]["target"]["printed"], ["Left", "Right", "Left"])

    def test_the_second_printing_is_the_one_ticked(self):
        out = self.dir / "second.docx"
        fill_template(self.form, self.fields, {self.by["Swelling"]["key"]: "Left (2)",
                                               self.by["Answer given"]["key"]: "Yes (2)",
                                               self.by["Was the dressing changed?"]["key"]: "YES (2)"}, out)
        body = part_text(out)
        self.assertIn("Swelling:  ☐ Left  ☐ Right  ☒ Left", body)
        self.assertIn("Answer given: Yes", body)
        self.assertNotIn("Yes (2)", body, "the printed option is written, never the suffix")
        self.assertIn("YESNO☒ YES", body, "tabs are not text: the words read YES, NO, YES")

    def test_a_legacy_dropdown_selects_the_entry_at_its_printing(self):
        doc = Document()
        doc.add_paragraph("Synthetic legacy form")
        ff_field(doc.add_paragraph("Answer given: "), "dropdown", ["Yes", "No", "Yes"])
        form = self.dir / "legacy-dd.docx"
        form.write_bytes(docx_bytes(doc))
        fields = inspect_template(form, engine="v3")["fields"]
        self.assertEqual(fields[0]["options"], ["Yes", "No", "Yes (2)"])
        for answer, index in (("Yes (2)", "2"), ("Yes", "0"), ("No", "1")):
            out = self.dir / ("dd-%s.docx" % index)
            fill_template(form, fields, {fields[0]["key"]: answer}, out)
            self.assertEqual(ff_result(out), [index], answer)

    def test_the_first_printing_stays_the_first(self):
        out = self.dir / "first.docx"
        fill_template(self.form, self.fields, {self.by["Swelling"]["key"]: "Left",
                                               self.by["Was the dressing changed?"]["key"]: "YES"}, out)
        body = part_text(out)
        self.assertIn("Swelling:  ☒ Left  ☐ Right  ☐ Left", body)
        self.assertIn("☒ YESNOYES", body)
        self.assertEqual(body.count("☒"), 2)



def ticked_sdt_checkbox():
    sdt = _sdt("checkbox")
    sdt.find(qn("w:sdtPr")).find("{%s}checkbox" % W14).find("{%s}checked" % W14).set("{%s}val" % W14, "1")
    sdt.find(qn("w:sdtContent")).find(qn("w:r")).find(qn("w:t")).text = "☒"
    return sdt


def prechecked_form(path):
    """F3: a blank form printing some boxes ticked - a checkbox control, a glyph, a legacy checkbox, a choice, a
    check-all-that-apply line, a radio pair, and a box grid with one box ticked."""
    doc = Document()
    doc.add_paragraph("Synthetic procedure checklist")
    doc.add_paragraph("Consent obtained ")._p.append(ticked_sdt_checkbox())
    doc.add_paragraph("History reviewed today.")
    doc.add_paragraph("Hypertension ☒")
    doc.add_paragraph("Medication list reviewed.")
    doc.add_paragraph("Smoker?  ☐ Yes  ☒ No")
    doc.add_paragraph("Symptoms (check all that apply): ☒ Pain ☐ Swelling ☒ Redness")
    ff_field(doc.add_paragraph("Band applied "), "checkbox", checked=True, name="Band")
    doc.add_paragraph("Medication list reviewed again.")
    doc.add_paragraph("Laterality:  ○ Left  ◉ Right")
    grid = doc.add_table(rows=3, cols=3)
    for c, h in enumerate(["Symptom", "Yes", "No"]):
        grid.cell(0, c).text = h
    grid.cell(1, 0).text = "Fever"
    grid.cell(2, 0).text = "Cough"
    for r, c, mark in ((1, 1, "☐"), (1, 2, "☒"), (2, 1, "☐"), (2, 2, "☐")):
        grid.cell(r, c).text = mark
    Path(path).write_bytes(docx_bytes(doc))


def paragraphs(path, part="word/document.xml"):
    with ZipFile(path) as z:
        root = etree.fromstring(z.read(part))
    return ["".join(t.text or "" for t in p.iter("{%s}t" % W)) for p in root.iter("{%s}p" % W)]


def control_states(path):
    with ZipFile(path) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    sdt = [c.get("{%s}val" % W14) for c in root.iter("{%s}checked" % W14)]
    ff = [c.get("{%s}val" % W) for c in root.iter("{%s}checked" % W)]
    return sdt, ff


class Unticking(unittest.TestCase):
    """F3: filling sets every box of an answered field - chosen ticked, every other unticked; unanswered stays."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.form = self.dir / "prechecked.docx"
        prechecked_form(self.form)
        self.fields = inspect_template(self.form, engine="v3")["fields"]
        self.by = fields_by_label(self.fields)

    def tearDown(self):
        self.tmp.cleanup()

    def fill(self, answers, name="out.docx"):
        out = self.dir / name
        fill_template(self.form, self.fields, {self.by[label]["key"]: value for label, value in answers.items()}, out)
        return out

    def test_the_blank_forms_printed_ticks_are_recorded(self):
        printed = {label: f.get("printed_ticked") for label, f in self.by.items()}
        self.assertEqual(printed["Consent obtained"], [0])
        self.assertEqual(printed["Hypertension"], [0])
        self.assertEqual(printed["Smoker?"], [1])
        self.assertEqual(printed["Symptoms (check all that apply)"], [0, 2])
        self.assertEqual(printed["Band applied"], [0])
        self.assertEqual(printed["Laterality"], [1])
        self.assertEqual(printed["Fever"], [1])
        self.assertIsNone(printed["Cough"], "nothing printed ticked, nothing recorded")

    def test_a_checkbox_answered_unticked_is_exported_unticked(self):
        out = self.fill({"Consent obtained": False, "Hypertension": False, "Band applied": False})
        text = paragraphs(out)
        self.assertIn("Consent obtained ☐", text)
        self.assertIn("Hypertension ☐", text)
        self.assertEqual(control_states(out), (["0"], ["0"]))

    def test_a_choice_ticks_the_chosen_and_unticks_the_others(self):
        out = self.fill({"Smoker?": "Yes", "Symptoms (check all that apply)": ["Swelling"], "Laterality": "Left",
                         "Fever": "Yes"})
        text = paragraphs(out)
        self.assertIn("Smoker?  ☒ Yes  ☐ No", text)
        self.assertIn("Symptoms (check all that apply): ☐ Pain ☒ Swelling ☐ Redness", text)
        self.assertIn("Laterality:  ◉ Left  ○ Right", text)
        row = text[text.index("Fever"):text.index("Fever") + 3]
        self.assertEqual(row, ["Fever", "☒", "☐"])

    def test_an_unanswered_field_stays_as_printed(self):
        out = self.fill({"Hypertension": True})
        text = paragraphs(out)
        self.assertIn("Smoker?  ☐ Yes  ☒ No", text)
        self.assertIn("Symptoms (check all that apply): ☒ Pain ☐ Swelling ☒ Redness", text)
        self.assertIn("Consent obtained ☒", text)
        self.assertEqual(control_states(out), (["1"], []))

    def test_a_written_cell_mark_is_removed_when_the_other_option_is_chosen(self):
        from documents import word_v3
        doc = Document()
        grid = doc.add_table(rows=1, cols=3)
        grid.cell(0, 0).text = "Fever"
        grid.cell(0, 2).text = "X"
        yes, no = grid.cell(0, 1)._tc, grid.cell(0, 2)._tc
        self.assertEqual(word_v3.text_of(no).strip(), "X")
        self.assertTrue(word_v3.set_cell_box(yes, True))
        self.assertTrue(word_v3.set_cell_box(no, False))
        self.assertEqual((word_v3.text_of(yes).strip(), word_v3.text_of(no).strip()), ("X", ""))
        self.assertFalse(word_v3.set_cell_box(no, False), "an empty cell has nothing to untick")


class ExportReadBack(unittest.TestCase):
    """F3 belt and braces: an export whose ticked boxes are not exactly the chosen ones is refused."""

    def test_a_writer_that_leaves_a_box_as_printed_refuses_the_export(self):
        from unittest.mock import patch
        from documents import word_v3
        with tempfile.TemporaryDirectory() as tmp:
            form = Path(tmp) / "prechecked.docx"
            prechecked_form(form)
            data = form.read_bytes()
            fields = word_v3.inspect(data)["fields"]
            smoker = fields_by_label(fields)["Smoker?"]
            self.assertIn("☒ Yes", "".join(paragraphs_bytes(word_v3.fill(data, fields, {smoker["key"]: "Yes"}))))
            real = word_v3.set_glyph
            with patch.object(word_v3, "set_glyph", side_effect=lambda p, n, ticked: real(p, n, ticked) if ticked else False):
                with self.assertRaises(word_v3.V3Failure) as refused:
                    word_v3.fill(data, fields, {smoker["key"]: "Yes"})
            self.assertEqual(refused.exception.code, "fill_mismatch")
            self.assertIn('"Smoker?"', str(refused.exception))


def paragraphs_bytes(data):
    root = etree.fromstring(ZipFile(io.BytesIO(data)).read("word/document.xml"))
    return ["".join(t.text or "" for t in p.iter("{%s}t" % W)) for p in root.iter("{%s}p" % W)]


class BoxNumbers(unittest.TestCase):
    """F2/F6: a manually added checkbox is the box the clinician named, and a box the place lacks is refused."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        doc = Document()
        doc.add_paragraph("Synthetic smoking status")
        doc.add_paragraph("Smoker?  ☐ Yes  ☐ No")
        doc.add_paragraph("Diabetes ")._p.append(_sdt("checkbox"))
        table = doc.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "Severity"
        table.cell(0, 1).text = "☐ Mild ☐ Severe"
        self.form = self.dir / "boxes.docx"
        self.form.write_bytes(docx_bytes(doc))
        self.places = {row["slot"]: row for row in outline_template(self.form)["slots"]}

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, slot, box, label="Added box"):
        return locate_fields(self.form, [{"slot": slot, "kind": "checkbox", "label": label, "glyph": box - 1}])["fields"]

    def test_the_outline_counts_each_places_boxes(self):
        self.assertEqual(self.places["word/document.xml#b/p[1]"]["boxes"], 2)
        self.assertEqual(self.places["word/document.xml#b/p[1]/glyphs"]["boxes"], 2)
        self.assertEqual(self.places["word/document.xml#b/p[2]/sdt[0]"]["boxes"], 1)
        self.assertEqual(self.places["word/document.xml#b/tbl[0]/tr[0]/tc[1]"]["boxes"], 2)
        self.assertEqual(self.places["word/document.xml#b/p[0]"]["boxes"], 0)

    def test_a_paragraph_place_takes_the_named_box(self):
        added = self.add("word/document.xml#b/p[1]", 2, "Non-smoker")
        self.assertEqual(added[0]["locator"]["target"]["boxes"][0]["glyph"], 1)
        out = self.dir / "second-box.docx"
        fill_template(self.form, added, {added[0]["key"]: True}, out)
        self.assertIn("Smoker?  ☐ Yes  ☒ No", part_text(out))

    def test_a_cell_place_takes_the_named_box(self):
        try:
            added = self.add("word/document.xml#b/tbl[0]/tr[0]/tc[1]", 2, "Severe")
        except DocumentError as refused:
            self.fail("a cell holding printed boxes was refused as a place: %s" % refused)
        out = self.dir / "cell-box.docx"
        fill_template(self.form, added, {added[0]["key"]: True}, out)
        self.assertIn("☐ Mild ☒ Severe", part_text(out))

    def test_a_box_the_place_does_not_have_is_refused(self):
        for slot, box, count in (("word/document.xml#b/p[1]", 3, "2 printed boxes"),
                                 ("word/document.xml#b/p[1]/glyphs", 7, "2 printed boxes"),
                                 ("word/document.xml#b/p[2]/sdt[0]", 2, "1 printed box;"),
                                 ("word/document.xml#b/tbl[0]/tr[0]/tc[1]", 3, "2 printed boxes"),
                                 ("word/document.xml#b/p[1]", 0, "2 printed boxes")):
            with self.assertRaises(DocumentError) as refused:
                self.add(slot, box)
            self.assertEqual(refused.exception.code, "invalid_mapping", slot)
            self.assertIn(count, str(refused.exception), slot)


def laterality_form(path):
    """Options that differ only by a side marker, on every detector path that builds options: a box line with
    '(L) knee' / '(R) knee', one with 'L knee' / 'R knee', a dropdown, an option grid's column headers, a column
    checklist's row labels, and narrow tick cells beside printed options."""
    from docx.shared import Twips
    doc = Document()
    doc.add_paragraph("Synthetic joint procedure")
    doc.add_paragraph("Injected joint:  ☐ (L) knee  ☐ (R) knee")
    doc.add_paragraph("Aspirated joint:  ☐ L knee  ☐ R knee")
    doc.add_paragraph("Imaged joint: ")._p.append(_sdt("dropdown", options=["Choose an item.", "(L) knee", "(R) knee"]))
    grid = doc.add_table(rows=4, cols=3)
    for c, h in enumerate(["Finding", "(L) knee", "(R) knee"]):
        grid.cell(0, c).text = h
    for r, name in enumerate(["Effusion", "Warmth", "Crepitus"], 1):
        grid.cell(r, 0).text = name
    doc.add_paragraph("Joints examined")
    check = doc.add_table(rows=4, cols=2)
    check.cell(0, 0).text = "Joint"
    check.cell(0, 1).text = "Examined"
    for r, name in enumerate(["(L) knee", "(R) knee", "(L) hip"], 1):
        check.cell(r, 0).text = name
        check.cell(r, 1).text = "☐"
    doc.add_paragraph("Dressing site")
    ticks = doc.add_table(rows=2, cols=2)
    for r, name in enumerate(["(L) knee", "(R) knee"]):
        ticks.cell(r, 0).width = Twips(300)
        ticks.cell(r, 1).text = name
    Path(path).write_bytes(docx_bytes(doc))


class OptionsKeepTheirPrintedText(unittest.TestCase):
    """An option label is the printed option text, trimmed only; the list-marker strip is for question labels."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.form = self.dir / "laterality.docx"
        laterality_form(self.form)
        self.fields = inspect_template(self.form, engine="v3")["fields"]
        self.by = fields_by_label(self.fields)

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_option_path_keeps_the_side(self):
        sides = ["(L) knee", "(R) knee"]
        self.assertEqual(self.by["Injected joint"]["options"], sides)                  # box line
        self.assertEqual(self.by["Aspirated joint"]["options"], ["L knee", "R knee"])  # box line, bare letters
        self.assertEqual(self.by["Imaged joint"]["options"], sides)                    # dropdown
        for finding in ("Effusion", "Warmth", "Crepitus"):                             # option grid headers
            self.assertIn(finding, self.by, "each grid row is one choice between the two sides")
            self.assertEqual((self.by[finding]["kind"], self.by[finding]["options"]), ("choice", sides), finding)
        self.assertEqual(self.by["Examined"]["options"], sides + ["(L) hip"])          # column checklist rows
        ticks = [f for f in self.fields if f["label"] == "Choose"]                     # narrow tick cells
        self.assertEqual([f["options"] for f in ticks], [sides])
        for f in self.fields:
            self.assertNotIn("knee (2)", f.get("options") or [], f["label"])

    def test_each_side_is_exported_in_its_own_box(self):
        out = self.dir / "sides.docx"
        answers = {"Injected joint": "(R) knee", "Aspirated joint": "L knee", "Imaged joint": "(L) knee",
                   "Effusion": "(R) knee", "Examined": ["(R) knee", "(L) hip"]}
        fill_template(self.form, self.fields, {self.by[k]["key"]: v for k, v in answers.items()}, out)
        text = [line for line in paragraphs(out)]
        self.assertIn("Injected joint:  ☐ (L) knee  ☒ (R) knee", text)
        self.assertIn("Aspirated joint:  ☒ L knee  ☐ R knee", text)
        self.assertIn("Imaged joint: (L) knee", text)
        at = text.index("Effusion")
        self.assertEqual(text[at:at + 3], ["Effusion", "", "X"])
        at = text.index("Joint")
        self.assertEqual(text[at + 2:at + 8], ["(L) knee", "☐", "(R) knee", "☒", "(L) hip", "☒"])

    def test_the_other_option_paths_keep_the_printed_text(self):
        doc = Document()
        doc.add_paragraph("Synthetic joint log")
        site = doc.add_table(rows=2, cols=2)                         # a slash header over an answer cell
        site.cell(0, 0).text = "Joint"
        site.cell(0, 1).text = "L. / R."
        site.cell(1, 0).text = "Knee"
        doc.add_paragraph("Doses given")
        log = doc.add_table(rows=3, cols=3)                          # a log table's column headers
        for c, h in enumerate(["Drug", "(L) dose", "(R) dose"]):
            log.cell(0, c).text = h
        ff_field(doc.add_paragraph("Splinted side: "), "dropdown", ["(L) knee ", " (R) knee"])
        form = self.dir / "paths.docx"
        form.write_bytes(docx_bytes(doc))
        fields = inspect_template(form, engine="v3")["fields"]
        by = fields_by_label(fields)
        self.assertIn("Knee", by, "'L. / R.' over the answer cell makes it a choice")
        self.assertEqual((by["Knee"]["kind"], by["Knee"]["options"]), ("choice", ["L.", "R."]))
        self.assertEqual(next(f for f in fields if f["kind"] == "table_rows")["options"], ["Drug", "(L) dose", "(R) dose"])
        self.assertEqual(by["Splinted side"]["options"], ["(L) knee", "(R) knee"])
        out = self.dir / "paths-out.docx"
        fill_template(form, fields, {by["Knee"]["key"]: "R.", by["Splinted side"]["key"]: "(R) knee"}, out)
        self.assertEqual(ff_result(out), ["1"])
        text = paragraphs(out)
        self.assertEqual(text[text.index("Knee"):text.index("Knee") + 2], ["Knee", "R."])
        outline = outline_template(form)["slots"]
        place = next(r for r in outline if r["kind"] == "p" and r["preview"] == "Synthetic joint log")
        added = locate_fields(form, [{"slot": place["slot"], "kind": "choice", "label": "Side",
                                      "options": [" (L) knee", "(R)  knee "]}])["fields"]
        self.assertEqual(added[0]["options"], ["(L) knee", "(R) knee"])

    def test_option_cells_and_lettered_items_keep_the_side(self):
        doc = Document()
        doc.add_paragraph("Synthetic procedure")
        row = doc.add_table(rows=1, cols=3)                          # one box and its option per cell
        row.cell(0, 0).text = "Injected side"
        row.cell(0, 1).text = "☐ (L) knee"
        row.cell(0, 2).text = "☐ (R) knee"
        doc.add_paragraph("Which knee was examined?")                # lettered list items under a question
        numbering = doc.part.numbering_part.element
        abstract = OxmlElement("w:abstractNum")
        abstract.set(qn("w:abstractNumId"), "90")
        lvl = OxmlElement("w:lvl")
        lvl.set(qn("w:ilvl"), "0")
        for tag, val in (("w:start", "1"), ("w:numFmt", "lowerLetter"), ("w:lvlText", "%1)")):
            x = OxmlElement(tag)
            x.set(qn("w:val"), val)
            lvl.append(x)
        abstract.append(lvl)
        numbering.insert(0, abstract)
        num = OxmlElement("w:num")
        num.set(qn("w:numId"), "90")
        ref = OxmlElement("w:abstractNumId")
        ref.set(qn("w:val"), "90")
        num.append(ref)
        numbering.append(num)
        for side in ("(L) knee", "(R) knee"):
            ppr = doc.add_paragraph(side)._p.get_or_add_pPr()
            numpr = OxmlElement("w:numPr")
            for tag, val in (("w:ilvl", "0"), ("w:numId", "90")):
                x = OxmlElement(tag)
                x.set(qn("w:val"), val)
                numpr.append(x)
            ppr.append(numpr)
        form = self.dir / "cells-and-items.docx"
        form.write_bytes(docx_bytes(doc))
        fields = inspect_template(form, engine="v3")["fields"]
        by = fields_by_label(fields)
        self.assertEqual(by["Injected side"]["options"], ["(L) knee", "(R) knee"])
        self.assertEqual((by["Which knee was examined?"]["locator"]["target"]["type"], by["Which knee was examined?"]["options"]),
                         ("paragraph_options", ["(L) knee", "(R) knee"]))
        out = self.dir / "cells-and-items-out.docx"
        fill_template(form, fields, {by["Injected side"]["key"]: "(R) knee", by["Which knee was examined?"]["key"]: "(L) knee"}, out)
        text = paragraphs(out)
        self.assertIn("☐ (L) knee", text)
        self.assertIn("☒ (R) knee", text)
        self.assertIn("☒ (L) knee", text)

    def test_question_labels_keep_the_marker_rule_and_options_do_not(self):
        from documents.word_v3 import clean_label, option_text
        self.assertEqual(clean_label("a) Pain"), "Pain")
        self.assertEqual(option_text("a) Pain"), "a) Pain")
        self.assertEqual(option_text("(a) Pain"), "(a) Pain")
        self.assertEqual(option_text("  (L)\tknee  "), "(L) knee")
        self.assertEqual(option_text("Other: ______"), "Other", "the write-in blank is not the option")
        self.assertEqual(option_text("b) Left knee -"), "b) Left knee")


def checkbox_control(checked=False, *, states=True, flag=True):
    """A checkbox content control as Word writes it: the w14:checked flag, the checkedState/uncheckedState glyphs
    (MS Gothic U+2612 / U+2610) and the glyph the state names as its content."""
    sdt = _sdt("checkbox")
    cb = sdt.find(qn("w:sdtPr")).find("{%s}checkbox" % W14)
    cb.find("{%s}checked" % W14).set("{%s}val" % W14, "1" if checked else "0")
    if not flag:
        cb.remove(cb.find("{%s}checked" % W14))
    if states:
        for tag, code in (("checkedState", "2612"), ("uncheckedState", "2610")):
            state = etree.SubElement(cb, "{%s}%s" % (W14, tag))
            state.set("{%s}val" % W14, code)
            state.set("{%s}font" % W14, "MS Gothic")
    sdt.find(qn("w:sdtContent")).find(qn("w:r")).find(qn("w:t")).text = "☒" if checked else "☐"
    return sdt


def text_run(text):
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = text
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    r.append(t)
    return r


def controls_shown(data):
    """[(glyph shown, w14:checked flag)] for every checkbox content control of an exported package, in order."""
    root = etree.fromstring(ZipFile(io.BytesIO(data)).read("word/document.xml"))
    out = []
    for sdt in root.iter(qn("w:sdt")):
        cb = sdt.find(".//{%s}checkbox" % W14)
        if cb is None:
            continue
        flag = cb.find("{%s}checked" % W14)
        out.append(("".join(t.text or "" for t in sdt.find(qn("w:sdtContent")).iter(qn("w:t"))),
                    flag.get("{%s}val" % W14) if flag is not None else None))
    return out


class ControlReadBack(unittest.TestCase):
    """R3: a checkbox control reads as ticked or unticked only when its flag AND the glyph it displays agree."""

    def anticoagulated(self):
        doc = Document()
        doc.add_paragraph("Synthetic intake")
        p = doc.add_paragraph("Anticoagulated? ")
        p._p.append(checkbox_control(checked=True))
        p._p.append(text_run(" Yes  "))
        p._p.append(checkbox_control())
        p._p.append(text_run(" No"))
        return docx_bytes(doc)

    def test_a_writer_that_leaves_the_ticked_glyph_is_refused(self):
        from unittest.mock import patch
        from documents import word_v3
        data = self.anticoagulated()
        fields = word_v3.inspect(data)["fields"]
        self.assertEqual((fields[0]["label"], fields[0]["options"]), ("Anticoagulated?", ["Yes", "No"]))
        real = word_v3.set_sdt_checkbox

        def regressed(sdt, ticked):             # the refuter's writer: the flag set, the printed glyph left
            if ticked:
                return real(sdt, True)
            cb = sdt.find(word_v3.q("w:sdtPr")).find(word_v3.q("w14:checkbox"))
            cb.find(word_v3.q("w14:checked")).set(word_v3.q("w14:val"), "0")
            return True
        with patch.object(word_v3, "set_sdt_checkbox", side_effect=regressed):
            with self.assertRaises(word_v3.V3Failure) as refused:
                word_v3.fill(data, fields, {fields[0]["key"]: "No"})
        self.assertEqual(refused.exception.code, "fill_mismatch")

    def test_unticking_a_control_shows_its_unchecked_glyph(self):
        from documents import word_v3
        data = self.anticoagulated()
        fields = word_v3.inspect(data)["fields"]
        self.assertEqual(fields[0].get("printed_ticked"), [0])
        out = word_v3.fill(data, fields, {fields[0]["key"]: "No"})
        self.assertEqual(controls_shown(out), [("☐", "0"), ("☒", "1")])

    def test_an_added_flag_keeps_the_schema_order(self):
        """R5: w14:checked precedes w14:checkedState and w14:uncheckedState (CT_SdtCheckbox is a sequence)."""
        from documents import word_v3
        doc = Document()
        doc.add_paragraph("Synthetic intake")
        p = doc.add_paragraph("Smoker? ")
        p._p.append(checkbox_control(flag=False))      # an unticked control written without its optional flag
        p._p.append(text_run(" Yes  "))
        p._p.append(checkbox_control(flag=False))
        p._p.append(text_run(" No"))
        data = docx_bytes(doc)
        fields = word_v3.inspect(data)["fields"]
        out = word_v3.fill(data, fields, {fields[0]["key"]: "Yes"})
        root = etree.fromstring(ZipFile(io.BytesIO(out)).read("word/document.xml"))
        orders = [[etree.QName(c).localname for c in cb] for cb in root.iter("{%s}checkbox" % W14)]
        self.assertEqual(orders, [["checked", "checkedState", "uncheckedState"]] * 2)
        self.assertEqual(controls_shown(out), [("☒", "1"), ("☐", "0")])


def control_checklist_bytes():
    """The refuter's p1c input: a check-all-that-apply column whose boxes are checkbox controls, Warfarin printed
    ticked."""
    doc = Document()
    doc.add_paragraph("Synthetic medication reconciliation")
    table = doc.add_table(rows=4, cols=2)
    table.cell(0, 0).text = "Medication"
    table.cell(0, 1).text = "Continue (check all that apply)"
    for r, name in ((1, "Warfarin"), (2, "Metformin"), (3, "Aspirin")):
        table.cell(r, 0).text = name
        table.cell(r, 1).paragraphs[0]._p.append(checkbox_control(checked=(r == 1)))
    return docx_bytes(doc)


def control_grid_bytes():
    """The refuter's p1 input: a Yes/No grid whose answer cells are checkbox controls, Chest pain printed Yes."""
    doc = Document()
    doc.add_paragraph("Synthetic review of systems")
    table = doc.add_table(rows=3, cols=3)
    for c, h in enumerate(["Symptom", "Yes", "No"]):
        table.cell(0, c).text = h
    table.cell(1, 0).text = "Chest pain"
    table.cell(2, 0).text = "Dyspnea"
    for r in (1, 2):
        for c in (1, 2):
            table.cell(r, c).paragraphs[0]._p.append(checkbox_control(checked=(r == 1 and c == 1)))
    return docx_bytes(doc)


class ControlsInBoxCells(unittest.TestCase):
    """R2: a table cell whose box is a checkbox control is read and written as that control."""

    def test_a_control_cell_printed_ticked_is_recorded_and_kept_when_unanswered(self):
        from documents import word_v3
        data = control_checklist_bytes()
        fields = word_v3.inspect(data)["fields"]
        field = next(f for f in fields if f["kind"] == "multi_choice")
        self.assertEqual(field["options"], ["Warfarin", "Metformin", "Aspirin"])
        self.assertEqual(field.get("printed_ticked"), [0], "Warfarin is printed ticked")
        self.assertEqual(controls_shown(word_v3.fill(data, fields, {})), [("☒", "1"), ("☐", "0"), ("☐", "0")])

    def test_an_answer_sets_every_control_of_the_checklist(self):
        from documents import word_v3
        data = control_checklist_bytes()
        fields = word_v3.inspect(data)["fields"]
        field = next(f for f in fields if f["kind"] == "multi_choice")
        out = word_v3.fill(data, fields, {field["key"]: ["Metformin"]})
        self.assertEqual(controls_shown(out), [("☐", "0"), ("☒", "1"), ("☐", "0")])
        out = word_v3.fill(data, fields, {field["key"]: ["Aspirin", "Warfarin"]})
        self.assertEqual(controls_shown(out), [("☒", "1"), ("☐", "0"), ("☒", "1")])

    def test_a_grid_of_controls_takes_the_other_option(self):
        from documents import word_v3
        data = control_grid_bytes()
        fields = word_v3.inspect(data)["fields"]
        chest = fields_by_label(fields)["Chest pain"]
        self.assertEqual((chest["kind"], chest["options"], chest.get("printed_ticked")), ("choice", ["Yes", "No"], [0]))
        out = word_v3.fill(data, fields, {chest["key"]: "No"})
        self.assertEqual(controls_shown(out), [("☐", "0"), ("☒", "1"), ("☐", "0"), ("☐", "0")])

    def test_a_cell_holding_a_control_beside_another_box_is_unread_and_refused(self):
        from documents import word_v3
        doc = Document()
        doc.add_paragraph("Synthetic review of systems")
        table = doc.add_table(rows=2, cols=3)
        for c, h in enumerate(["Symptom", "Yes", "No"]):
            table.cell(0, c).text = h
        table.cell(1, 0).text = "Cough"
        table.cell(1, 1).text = "☐"                   # a printed box, and a legacy checkbox printed ticked beside it
        ff_field(table.cell(1, 1).paragraphs[0], "checkbox", checked=True, name="CoughYes")
        table.cell(1, 2).text = "☐"
        data = docx_bytes(doc)
        fields = word_v3.inspect(data)["fields"]
        cough = fields_by_label(fields)["Cough"]
        self.assertEqual((cough["options"], cough.get("printed_ticked"), cough.get("printed_unread")),
                         (["Yes", "No"], None, [0]), "never read as unticked")
        with self.assertRaises(word_v3.V3Failure) as refused:
            word_v3.fill(data, fields, {cough["key"]: "No"})
        self.assertEqual(refused.exception.code, "unsupported_layout")
        self.assertIn("checkbox control beside another box", str(refused.exception))


def mixed_side_bytes(control="sdt"):
    """The refuter's p2 input: one printed line mixing a checkbox control between two printed glyph boxes."""
    doc = Document()
    doc.add_paragraph("Synthetic knee note")
    p = doc.add_paragraph("Side: ☐ Right ")
    if control == "sdt":
        p._p.append(checkbox_control())
    else:
        ff_field(p, "checkbox", name="Left")
    p._p.append(text_run(" Left ☐ Bilateral"))
    return docx_bytes(doc)


def mixed_cell_bytes():
    """D03's shape (DEV corpus, place b/tbl[0]/tr[17]/tc[0]/p[4]): printed boxes and two checkbox controls on one
    line in a table cell, and a cell mixing a printed box, a control and a printed box."""
    doc = Document()
    doc.add_paragraph("Synthetic social history")
    table = doc.add_table(rows=2, cols=1)
    p = table.cell(0, 0).paragraphs[0]
    p.add_run("☐ Alcohol beverages: ☐ Wine [")
    p._p.append(checkbox_control())
    p._p.append(text_run(" Red "))
    p._p.append(checkbox_control())
    p._p.append(text_run(" White ], ☐ Other:__________"))
    q = table.cell(1, 0).paragraphs[0]
    q.add_run("☐ Mild ")
    q._p.append(checkbox_control())
    q._p.append(text_run(" Moderate ☐ Severe"))
    return docx_bytes(doc)


def glyphs_shown(data, contains):
    """The printed text (glyphs, controls as their glyph) of the exported paragraph containing `contains`."""
    return next(line for line in paragraphs_bytes(data) if contains in line)


def side_questions_bytes():
    """The refuter's p6 input: questions whose only difference is a side marker, in table rows and in paragraphs."""
    doc = Document()
    doc.add_paragraph("Synthetic knee examination")
    table = doc.add_table(rows=3, cols=2)
    table.cell(0, 0).text = "Finding"
    table.cell(0, 1).text = "Present?"
    table.cell(1, 0).text = "(L) Effusion"
    table.cell(1, 1).text = "☐ Yes ☐ No"
    table.cell(2, 0).text = "(R) Effusion"
    table.cell(2, 1).text = "☐ Yes ☐ No"
    doc.add_paragraph("L. Tenderness? ☐ Yes ☐ No")
    doc.add_paragraph("R. Tenderness? ☐ Yes ☐ No")
    return docx_bytes(doc)


class SideMarkersInQuestions(unittest.TestCase):
    """R4: a side written as a list marker - (L) (R) L. R. - stays in the question label; so does any single letter in
    parentheses (fail closed). '(L) Effusion' and '(R) Effusion' both became 'Effusion'."""

    def test_the_side_stays_in_every_question_label(self):
        from documents import word_v3
        fields = word_v3.inspect(side_questions_bytes())["fields"]
        self.assertEqual([(f["label"], f["kind"], f["options"]) for f in fields],
                         [("(L) Effusion", "choice", ["Yes", "No"]), ("(R) Effusion", "choice", ["Yes", "No"]),
                          ("L. Tenderness?", "choice", ["Yes", "No"]), ("R. Tenderness?", "choice", ["Yes", "No"])])

    def test_side_letters_and_single_letters_in_parentheses_are_kept(self):
        from documents.word_v3 import clean_label
        for text in ("(L) Effusion", "(R) Effusion", "(l) knee", "(r) knee", "L. Tenderness?", "R. Tenderness?",
                     "L) knee", "R) knee", "l. knee", "r) knee", "(a) Pain", "(B) Hip", "(i) Item", "(x) Item"):
            self.assertEqual(clean_label(text), text)
        for text, label in (("a) Yes", "Yes"), ("B. No", "No"), ("(3) Dose", "Dose"), ("12) Plan", "Plan"),
                            ("iv. Findings", "Findings"), ("(xii) Impression", "Impression"), ("(ii) Item", "Item")):
            self.assertEqual(clean_label(text), label, text)


class LegacyDropdownDefault(unittest.TestCase):
    """R6: a legacy dropdown with no w:result shows its w:default entry (ECMA-376 ddList), not the first."""

    def test_the_default_entry_is_the_one_printed(self):
        from documents import word_v3
        doc = Document()
        doc.add_paragraph("Synthetic injection note")
        p = doc.add_paragraph("Side: ")
        ff_field(p, "dropdown", options=["Left", "Right", "Bilateral"], name="Side")
        default = OxmlElement("w:default")
        default.set(qn("w:val"), "1")
        p._p.find(".//" + qn("w:ddList")).insert(0, default)
        data = docx_bytes(doc)
        fields = word_v3.inspect(data)["fields"]
        self.assertEqual((fields[0]["options"], fields[0].get("printed_ticked")), (["Left", "Right", "Bilateral"], [1]))
        for answer, shown in (("Left", "0"), ("Bilateral", "2")):
            with tempfile.TemporaryDirectory() as tmp:
                Path(tmp, "out.docx").write_bytes(word_v3.fill(data, fields, {fields[0]["key"]: answer}))
                self.assertEqual(ff_result(Path(tmp, "out.docx")), [shown], answer)


def ff_text_field(p, name="Consent"):
    """A legacy text form field (FORMTEXT) appended to python-docx paragraph `p`, with an empty result."""
    for kind, child in (("begin", None), ("instr", None), ("separate", None), ("end", None)):
        r = OxmlElement("w:r")
        if kind == "instr":
            node = OxmlElement("w:instrText")
            node.text = " FORMTEXT "
        else:
            node = OxmlElement("w:fldChar")
            node.set(qn("w:fldCharType"), kind)
            if kind == "begin":
                data = OxmlElement("w:ffData")
                n = OxmlElement("w:name")
                n.set(qn("w:val"), name)
                data.append(n)
                data.append(OxmlElement("w:enabled"))
                data.append(OxmlElement("w:textInput"))
                node.append(data)
        r.append(node)
        p._p.append(r)


class CheckboxNeedsABox(unittest.TestCase):
    """R7: a manual checkbox on a text content control or a legacy text field is refused when it is added, instead
    of being accepted, confirmed, and refused at every export."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        doc = Document()
        doc.add_paragraph("Synthetic consent")
        doc.add_paragraph("Consent obtained: ")._p.append(_sdt("rich", placeholder="Click or tap here to enter text."))
        ff_text_field(doc.add_paragraph("Witness: "), name="Witness")
        self.form = self.dir / "consent.docx"
        self.form.write_bytes(docx_bytes(doc))
        self.places = {row["slot"]: row for row in outline_template(self.form)["slots"]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_checkbox_on_a_text_control_or_text_field_is_refused(self):
        for slot in ("word/document.xml#b/p[1]/sdt[0]", "word/document.xml#b/p[2]/ff[0]"):
            self.assertIn(slot, self.places)
            with self.assertRaises(DocumentError) as refused:
                locate_fields(self.form, [{"slot": slot, "kind": "checkbox", "label": "Consent obtained", "glyph": 0}])
            self.assertEqual(refused.exception.code, "invalid_mapping", slot)
            self.assertIn("is not a checkbox", str(refused.exception), slot)

    def test_the_same_places_still_take_text(self):
        for n, slot in enumerate(("word/document.xml#b/p[1]/sdt[0]", "word/document.xml#b/p[2]/ff[0]")):
            field = locate_fields(self.form, [{"slot": slot, "kind": "text", "label": "Consent note"}])["fields"][0]
            out = self.dir / ("text-%d.docx" % n)
            fill_template(self.form, [field], {field["key"]: "Signed by synthetic patient"}, out)
            self.assertIn("Signed by synthetic patient", part_text(out))


class SurvivingMutantPins(unittest.TestCase):
    """Guards the round-2 mutation batch showed no test would miss: M01, M13 and M16."""

    def test_a_repeat_suffix_never_takes_a_printed_options_words(self):
        """M01: 'Left' printed again after a printed 'Left (2)' is 'Left (3)', or two options share one label and
        neither can be chosen."""
        from documents import word_v3
        self.assertEqual(word_v3.unique_options(["Left", "Left (2)", "Left"]), ["Left", "Left (2)", "Left (3)"])
        doc = Document()
        doc.add_paragraph("Synthetic swelling check")
        doc.add_paragraph("Swelling:  ☐ Left  ☐ Left (2)  ☐ Left")
        data = docx_bytes(doc)
        fields = word_v3.inspect(data)["fields"]
        self.assertEqual(fields[0]["options"], ["Left", "Left (2)", "Left (3)"])
        for answer, line in (("Left (3)", "Swelling:  ☐ Left  ☐ Left (2)  ☒ Left"),
                             ("Left (2)", "Swelling:  ☐ Left  ☒ Left (2)  ☐ Left")):
            self.assertIn(line, paragraphs_bytes(word_v3.fill(data, fields, {fields[0]["key"]: answer})), answer)

    def test_a_manual_checkbox_records_its_printed_tick(self):
        """M13: a box added by hand on a box the blank form prints ticked says so on the page."""
        with tempfile.TemporaryDirectory() as tmp:
            form = Path(tmp) / "prechecked.docx"
            prechecked_form(form)
            place = next(r for r in outline_template(form)["slots"] if r["kind"] == "p" and r["preview"] == "Hypertension ☒")
            added = locate_fields(form, [{"slot": place["slot"], "kind": "checkbox", "label": "Hypertension", "glyph": 0}])
            self.assertEqual(added["fields"][0].get("printed_ticked"), [0])

    def test_a_dropdown_or_option_cell_showing_other_words_is_refused(self):
        """M16: the read-back of a dropdown control and of an option-text cell compares the words shown."""
        from unittest.mock import patch
        from documents import word_v3
        doc = Document()
        doc.add_paragraph("Synthetic joint log")
        doc.add_paragraph("Laterality: ")._p.append(_sdt("dropdown", options=["Choose an item.", "Left", "Right"]))
        site = doc.add_table(rows=2, cols=2)
        site.cell(0, 0).text = "Joint"
        site.cell(0, 1).text = "L. / R."
        site.cell(1, 0).text = "Knee"
        data = docx_bytes(doc)
        by = fields_by_label(word_v3.inspect(data)["fields"])
        fields = [by["Laterality"], by["Knee"]]
        self.assertEqual((by["Knee"]["locator"]["target"].get("write"), by["Knee"]["options"]), ("option_text", ["L.", "R."]))
        self.assertIn("Laterality: Left", paragraphs_bytes(word_v3.fill(data, fields, {by["Laterality"]["key"]: "Left",
                                                                                          by["Knee"]["key"]: "L."})))
        real_sdt, real_cell = word_v3.write_sdt_text, word_v3.write_cell
        for name, wrong, answers in (
                ("write_sdt_text", lambda sdt, answer: real_sdt(sdt, "Right"), {by["Laterality"]["key"]: "Left"}),
                ("write_cell", lambda tc, answer, *a: real_cell(tc, "R.", *a), {by["Knee"]["key"]: "L."})):
            with patch.object(word_v3, name, side_effect=wrong):
                with self.assertRaises(word_v3.V3Failure) as refused:
                    word_v3.fill(data, fields, answers)
            self.assertEqual(refused.exception.code, "fill_mismatch", name)


def fever_cell_bytes():
    """A cell 'Yes' printed box and a legacy checkbox 'No': the cell's text shows the printed box only."""
    doc = Document()
    doc.add_paragraph("Synthetic review of systems")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Fever"
    cell = table.cell(0, 1).paragraphs[0]
    cell.add_run("☐ Yes ")
    ff_field(cell, "checkbox", name="FeverNo")
    cell._p.append(text_run(" No"))
    return docx_bytes(doc)


class MixedBoxNumbers(unittest.TestCase):
    """R1: the box number a clinician gives counts EXACTLY the boxes the place's preview shows, in its order - printed
    glyph boxes and checkbox controls alike - and the export ticks exactly that box, whatever its kind."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def form(self, data, name):
        path = self.dir / name
        path.write_bytes(data)
        return path, {row["slot"]: row for row in outline_template(path)["slots"]}

    def add_and_fill(self, path, slot, box, label):
        field = locate_fields(path, [{"slot": slot, "kind": "checkbox", "label": label, "glyph": box - 1}])["fields"][0]
        out = self.dir / ("%s-%d.docx" % (label.replace(" ", "-"), box))
        fill_template(path, [field], {field["key"]: True}, out)
        return field, out.read_bytes()

    def test_a_line_mixing_a_control_counts_every_box_it_shows(self):
        path, places = self.form(mixed_side_bytes(), "side.docx")
        for slot in ("word/document.xml#b/p[1]", "word/document.xml#b/p[1]/glyphs"):
            self.assertEqual(places[slot]["preview"], "Side: ☐ Right ☐ Left ☐ Bilateral")
            self.assertEqual(places[slot]["boxes"], 3, slot)
        _, out = self.add_and_fill(path, "word/document.xml#b/p[1]", 2, "Left")
        self.assertEqual(controls_shown(out), [("☒", "1")], "box 2 is the control printed before 'Left'")
        self.assertEqual(glyphs_shown(out, "Right"), "Side: ☐ Right ☒ Left ☐ Bilateral")
        _, out = self.add_and_fill(path, "word/document.xml#b/p[1]/glyphs", 3, "Bilateral")
        self.assertEqual((controls_shown(out), glyphs_shown(out, "Right")), ([("☐", "0")], "Side: ☐ Right ☐ Left ☒ Bilateral"))
        _, out = self.add_and_fill(path, "word/document.xml#b/p[1]", 1, "Right")
        self.assertEqual((controls_shown(out), glyphs_shown(out, "Right")), ([("☐", "0")], "Side: ☒ Right ☐ Left ☐ Bilateral"))
        with self.assertRaises(DocumentError) as refused:
            self.add_and_fill(path, "word/document.xml#b/p[1]", 4, "Beyond")
        self.assertIn("That place has 3 printed boxes", str(refused.exception))

    def test_a_legacy_checkbox_on_the_line_is_numbered_where_it_shows(self):
        path, places = self.form(mixed_side_bytes("ff"), "side-ff.docx")
        self.assertEqual((places["word/document.xml#b/p[1]"]["preview"], places["word/document.xml#b/p[1]"]["boxes"]),
                         ("Side: ☐ Right ☐ Left ☐ Bilateral", 3))
        _, out = self.add_and_fill(path, "word/document.xml#b/p[1]", 2, "Left")
        self.assertEqual(control_states(self.dir / "Left-2.docx"), ([], ["1"]))
        self.assertEqual(glyphs_shown(out, "Right"), "Side: ☐ Right  Left ☐ Bilateral")

    def test_d03s_red_wine_is_the_third_box_shown(self):
        path, places = self.form(mixed_cell_bytes(), "social.docx")
        line = "word/document.xml#b/tbl[0]/tr[0]/tc[0]/p[0]"
        self.assertEqual(places[line]["preview"], "☐ Alcohol beverages: ☐ Wine [☐ Red ☐ White ], ☐ Other:__________")
        self.assertEqual(places[line]["boxes"], 5)
        _, out = self.add_and_fill(path, line, 3, "Red wine")
        self.assertEqual(controls_shown(out)[:2], [("☒", "1"), ("☐", "0")], "box 3 is the control before 'Red'")
        self.assertIn("☐ Other", glyphs_shown(out, "Alcohol"))
        _, out = self.add_and_fill(path, line, 5, "Other drink")
        self.assertEqual(controls_shown(out)[:2], [("☐", "0"), ("☐", "0")])
        self.assertIn("☒ Other", glyphs_shown(out, "Alcohol"))

    def test_a_cell_counts_its_controls_as_its_preview_shows_them(self):
        path, places = self.form(mixed_cell_bytes(), "severity.docx")
        cell = "word/document.xml#b/tbl[0]/tr[1]/tc[0]"
        self.assertEqual((places[cell]["preview"], places[cell]["boxes"]), ("☐ Mild ☐ Moderate ☐ Severe", 3))
        _, out = self.add_and_fill(path, cell, 2, "Moderate")
        self.assertEqual(controls_shown(out)[2:], [("☒", "1")])
        self.assertEqual(glyphs_shown(out, "Mild"), "☐ Mild ☒ Moderate ☐ Severe")
        _, out = self.add_and_fill(path, cell, 3, "Severe")
        self.assertEqual((controls_shown(out)[2:], glyphs_shown(out, "Mild")), ([("☐", "0")], "☐ Mild ☐ Moderate ☒ Severe"))

    def test_a_cell_whose_preview_does_not_show_its_boxes_refuses_a_number(self):
        path, places = self.form(fever_cell_bytes(), "fever.docx")
        tc, line = "word/document.xml#b/tbl[0]/tr[0]/tc[1]", "word/document.xml#b/tbl[0]/tr[0]/tc[1]/p[0]"
        self.assertEqual((places[tc]["preview"], places[tc]["boxes"], places[tc].get("unnumbered_boxes")), ("☐ Yes No", 0, True))
        with self.assertRaises(DocumentError) as refused:
            self.add_and_fill(path, tc, 2, "No fever")
        self.assertEqual(refused.exception.code, "invalid_mapping")
        self.assertIn("choose the line inside the cell, or the checkbox itself", str(refused.exception))
        self.assertEqual((places[line]["preview"], places[line]["boxes"]), ("☐ Yes ☐ No", 2))
        _, out = self.add_and_fill(path, line, 2, "No fever")
        self.assertEqual(control_states(self.dir / "No-fever-2.docx"), ([], ["1"]))

    def test_a_cell_whose_preview_shows_boxes_nested_inside_it_refuses_a_number(self):
        doc = Document()
        doc.add_paragraph("Synthetic severity")
        outer = doc.add_table(rows=1, cols=3)
        outer.cell(0, 0).paragraphs[0].text = "☐ Mild ☐ Severe"          # its own line, and a nested table's box
        outer.cell(0, 0).add_table(rows=1, cols=1).cell(0, 0).text = "☐ Other"
        control = checkbox_control()                                   # a control showing no box, and a nested box
        control.find(qn("w:sdtContent")).find(qn("w:r")).find(qn("w:t")).text = "x"
        outer.cell(0, 1).paragraphs[0]._p.append(control)
        outer.cell(0, 1).add_table(rows=1, cols=1).cell(0, 0).text = "☐"
        ff_field(outer.cell(0, 2).paragraphs[0], "checkbox", name="Hidden")   # a legacy checkbox the preview hides,
        outer.cell(0, 2).add_table(rows=1, cols=1).cell(0, 0).text = "☐"   # and a nested box: 1 shown, 1 of its own
        path, places = self.form(docx_bytes(doc), "nested.docx")
        for tc, preview in (("word/document.xml#b/tbl[0]/tr[0]/tc[0]", "☐ Mild ☐ Severe☐ Other"),
                            ("word/document.xml#b/tbl[0]/tr[0]/tc[1]", "x☐"),
                            ("word/document.xml#b/tbl[0]/tr[0]/tc[2]", "☐")):
            self.assertEqual((places[tc]["preview"], places[tc]["boxes"], places[tc].get("unnumbered_boxes")),
                             (preview, 0, True), tc)
            with self.assertRaises(DocumentError) as refused:
                self.add_and_fill(path, tc, 1, "Box one")
            self.assertEqual(refused.exception.code, "invalid_mapping", tc)
        self.assertEqual(places["word/document.xml#b/tbl[0]/tr[0]/tc[0]/p[0]"]["boxes"], 2)


def wrapper_control(inner, kind="richText"):
    """An inline content control (a rich text or a group control) wrapping `inner`, as Word nests them."""
    sdt = OxmlElement("w:sdt")
    pr = OxmlElement("w:sdtPr")
    pr.append(OxmlElement("w:" + kind))
    sdt.append(pr)
    content = OxmlElement("w:sdtContent")
    content.append(inner)
    sdt.append(content)
    return sdt


def own_controls_shown(data):
    """[(glyph shown, flag)] for every checkbox content control of an export - the control itself, never a control that
    only wraps one - in document order."""
    root = etree.fromstring(ZipFile(io.BytesIO(data)).read("word/document.xml"))
    out = []
    for sdt in root.iter(qn("w:sdt")):
        cb = sdt.find(qn("w:sdtPr") + "/{%s}checkbox" % W14)
        if cb is None:
            continue
        flag = cb.find("{%s}checked" % W14)
        out.append(("".join(t.text or "" for t in sdt.find(qn("w:sdtContent")).iter(qn("w:t"))),
                    flag.get("{%s}val" % W14) if flag is not None else None))
    return out


def wrapped_grid_bytes(kind="richText"):
    """The refuter's F1 grid: Chest pain's Yes cell holds a checkbox control printed ticked INSIDE another control."""
    doc = Document()
    doc.add_paragraph("Synthetic review of systems")
    table = doc.add_table(rows=3, cols=3)
    for c, h in enumerate(["Symptom", "Yes", "No"]):
        table.cell(0, c).text = h
    table.cell(1, 0).text = "Chest pain"
    table.cell(2, 0).text = "Dyspnea"
    table.cell(1, 1).paragraphs[0]._p.append(wrapper_control(checkbox_control(checked=True), kind))
    for r, c in ((1, 2), (2, 1), (2, 2)):
        table.cell(r, c).paragraphs[0]._p.append(checkbox_control())
    return docx_bytes(doc)


def wrapped_checklist_bytes():
    """The refuter's F1 check-all column: Warfarin's box, printed ticked, is a checkbox control inside a control."""
    doc = Document()
    doc.add_paragraph("Synthetic medication reconciliation")
    table = doc.add_table(rows=4, cols=2)
    table.cell(0, 0).text = "Medication"
    table.cell(0, 1).text = "Continue (check all that apply)"
    for r, name in ((1, "Warfarin"), (2, "Metformin"), (3, "Aspirin")):
        table.cell(r, 0).text = name
        box = checkbox_control(checked=(r == 1))
        table.cell(r, 1).paragraphs[0]._p.append(wrapper_control(box) if r == 1 else box)
    return docx_bytes(doc)


def wrapped_line_bytes(legacy=False):
    """The refuter's F1 line: 'Smoker? [wrapped ☒] Yes ☐ No' (or its Yes a legacy checkbox inside a control)."""
    doc = Document()
    doc.add_paragraph("Synthetic intake")
    p = doc.add_paragraph("Smoker? ")
    if legacy:
        inner = Document().add_paragraph()
        ff_field(inner, "checkbox", checked=True, name="SmokerYes")
        wrapper = wrapper_control(inner._p[0])
        for run in list(inner._p)[1:]:
            wrapper.find(qn("w:sdtContent")).append(run)
    else:
        wrapper = wrapper_control(checkbox_control(checked=True))
    p._p.append(wrapper)
    p._p.append(text_run(" Yes ☐ No"))
    return docx_bytes(doc)


class NestedCheckboxControls(unittest.TestCase):
    """Round 3 F1: a checkbox control nested inside another control is read and written as that control, end to end -
    detection, the printed state, the writer and the read-back - or its place is refused; never invisible."""

    def test_a_wrapped_control_in_a_grid_cell_is_read_and_written_as_that_control(self):
        from documents import word_v3
        for kind in ("richText", "group"):
            data = wrapped_grid_bytes(kind)
            fields = word_v3.inspect(data)["fields"]
            chest = fields_by_label(fields)["Chest pain"]
            self.assertEqual((chest["kind"], chest["options"], chest.get("printed_ticked"), chest.get("printed_unread")),
                             ("choice", ["Yes", "No"], [0], None), kind)
            self.assertEqual(own_controls_shown(word_v3.fill(data, fields, {chest["key"]: "No"})),
                             [("☐", "0"), ("☒", "1"), ("☐", "0"), ("☐", "0")], kind)
            self.assertEqual(own_controls_shown(word_v3.fill(data, fields, {}))[:2], [("☒", "1"), ("☐", "0")],
                             "left blank it stays as printed - and the page was told it is printed ticked")

    def test_a_wrapped_control_in_a_checklist_is_unticked_when_not_chosen(self):
        from documents import word_v3
        data = wrapped_checklist_bytes()
        fields = word_v3.inspect(data)["fields"]
        field = next(f for f in fields if f["kind"] == "multi_choice")
        self.assertEqual((field["options"], field.get("printed_ticked")), (["Warfarin", "Metformin", "Aspirin"], [0]))
        self.assertEqual(own_controls_shown(word_v3.fill(data, fields, {field["key"]: ["Metformin"]})),
                         [("☐", "0"), ("☒", "1"), ("☐", "0")])

    def test_a_wrapped_control_on_a_line_is_one_of_the_questions_options(self):
        from documents import word_v3
        data = wrapped_line_bytes()
        fields = word_v3.inspect(data)["fields"]
        self.assertEqual([(f["label"], f["kind"], f["options"], f.get("printed_ticked")) for f in fields],
                         [("Smoker?", "choice", ["Yes", "No"], [0])])
        out = word_v3.fill(data, fields, {fields[0]["key"]: "No"})
        self.assertEqual(own_controls_shown(out), [("☐", "0")])
        self.assertEqual(glyphs_shown(out, "Smoker"), "Smoker? ☐ Yes ☒ No")
        places = {row["slot"]: row for row in word_v3.outline(data)["slots"]}
        self.assertEqual((places["word/document.xml#b/p[1]"]["preview"], places["word/document.xml#b/p[1]"]["boxes"]),
                         ("Smoker? ☐ Yes ☐ No", 2))

    def test_a_wrapped_legacy_checkbox_is_read_and_written_too(self):
        from documents import word_v3
        data = wrapped_line_bytes(legacy=True)
        fields = word_v3.inspect(data)["fields"]
        self.assertEqual([(f["label"], f["options"], f.get("printed_ticked")) for f in fields],
                         [("Smoker?", ["Yes", "No"], [0])])
        out = word_v3.fill(data, fields, {fields[0]["key"]: "No"})
        root = etree.fromstring(ZipFile(io.BytesIO(out)).read("word/document.xml"))
        self.assertEqual([c.get(qn("w:val")) for c in root.iter(qn("w:checked"))], ["0"])
        self.assertIn("☒ No", glyphs_shown(out, "Smoker"))

    def test_the_read_back_sees_a_control_the_writer_missed(self):
        """Belt and braces: a reader that loses a nested control (the round-3 shape) can never pass an export."""
        from unittest.mock import patch
        from documents import word_v3
        data = wrapped_grid_bytes()
        fields = word_v3.inspect(data)["fields"]
        chest = fields_by_label(fields)["Chest pain"]
        real = word_v3.box_pieces

        def blind(p):                              # the round-3 reader: a control inside a control is not seen
            return [(kind, node, n) for kind, node, n in real(p) if node is None or node.getparent().tag != qn("w:sdtContent")]
        with patch.object(word_v3, "box_pieces", side_effect=blind):
            with self.assertRaises(word_v3.V3Failure) as refused:
                word_v3.fill(data, fields, {chest["key"]: "No"})
        self.assertIn(refused.exception.code, ("fill_mismatch", "unsupported_layout"))

    def test_a_control_that_cannot_be_read_in_place_refuses_its_line(self):
        """A checkbox control inside a checkbox control: the line shows one box where the package holds two, so the
        line is not read as a question, its boxes are not numbered, and no box on it is ever called unticked."""
        from documents import word_v3
        doc = Document()
        doc.add_paragraph("Synthetic intake")
        p = doc.add_paragraph("Allergy? ")
        outer = checkbox_control()
        outer.find(qn("w:sdtContent")).append(checkbox_control(checked=True))
        p._p.append(outer)
        p._p.append(text_run(" Yes ☐ No"))
        data = docx_bytes(doc)
        info = word_v3.inspect(data)
        self.assertEqual([f["label"] for f in info["fields"] if f["kind"] in ("choice", "checkbox")], [])
        self.assertTrue(any("cannot read in place" in note for note in info["notes"]), info["notes"])
        places = {row["slot"]: row for row in word_v3.outline(data)["slots"]}
        self.assertEqual((places["word/document.xml#b/p[1]"]["boxes"], places["word/document.xml#b/p[1]"].get("unnumbered_boxes")),
                         (0, True))
        index = word_v3.SlotIndex(word_v3.open_package(data))
        glyph = {"kind": "glyph", "part": "word/document.xml", "slot": "b/p[1]/glyphs", "glyph": 0}
        self.assertIsNone(word_v3.box_state(index, glyph))
        with self.assertRaises(word_v3.V3Failure) as refused:
            word_v3.locate(data, [{"slot": "word/document.xml#b/p[1]", "kind": "checkbox", "label": "No", "glyph": 1}])
        self.assertEqual(refused.exception.code, "invalid_mapping")


def wrap_in_control(el):
    """Wrap a table cell (w:tr/w:sdt/w:tc) or a whole row (w:tbl/w:sdt/w:tr) in a content control, in place."""
    sdt = OxmlElement("w:sdt")
    sdt.append(OxmlElement("w:sdtPr"))
    content = OxmlElement("w:sdtContent")
    sdt.append(content)
    el.getparent().replace(el, sdt)
    content.append(el)
    return sdt


def yes_no_grid(doc, rows=("Chest pain", "Dyspnea")):
    table = doc.add_table(rows=len(rows) + 1, cols=3)
    for c, h in enumerate(["Symptom", "Yes", "No"]):
        table.cell(0, c).text = h
    for r, label in enumerate(rows, 1):
        table.cell(r, 0).text = label
        table.cell(r, 1).text = "☐"
        table.cell(r, 2).text = "☐"
    return table


class WrappedCellsAndRows(unittest.TestCase):
    """Round 3 P1: a content control wrapping a whole table cell (w:tr/w:sdt/w:tc) or a whole row (w:tbl/w:sdt/w:tr)
    is looked through, so every cell keeps its column; the table_rows writer counts columns as the index does."""

    def test_a_wrapped_yes_cell_keeps_every_later_cell_in_its_column(self):
        from documents import word_v3
        doc = Document()
        doc.add_paragraph("Synthetic review of systems")
        table = yes_no_grid(doc)
        wrap_in_control(table.cell(1, 1)._tc)
        data = docx_bytes(doc)
        fields = word_v3.inspect(data)["fields"]
        chest = fields_by_label(fields)["Chest pain"]
        self.assertEqual((chest["kind"], chest["options"]), ("choice", ["Yes", "No"]))
        rows = paragraphs_bytes(word_v3.fill(data, fields, {chest["key"]: "No"}))
        self.assertEqual(rows[rows.index("Chest pain"):rows.index("Chest pain") + 3], ["Chest pain", "☐", "☒"])
        rows = paragraphs_bytes(word_v3.fill(data, fields, {chest["key"]: "Yes"}))
        self.assertEqual(rows[rows.index("Chest pain"):rows.index("Chest pain") + 3], ["Chest pain", "☒", "☐"])
        places = {row["slot"]: row for row in word_v3.outline(data)["slots"]}
        self.assertIn("word/document.xml#b/tbl[0]/tr[1]/tc[1]", places, "the wrapped cell is a place of its own")
        self.assertFalse([f for f in fields if f["locator"]["target"].get("type") == "sdt_text"],
                         "the control around the cell is not an answer area")

    def test_a_wrapped_answer_cell_takes_its_answer(self):
        from documents import word_v3
        doc = Document()
        doc.add_paragraph("Synthetic intake")
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Allergies"
        table.cell(1, 0).text = "Plan"
        wrap_in_control(table.cell(0, 1)._tc)
        data = docx_bytes(doc)
        fields = word_v3.inspect(data)["fields"]
        self.assertEqual([(f["label"], f["locator"]["target"]["type"]) for f in fields], [("Allergies", "cell"), ("Plan", "cell")])
        out = word_v3.fill(data, fields, {fields[0]["key"]: "None documented", fields[1]["key"]: "Review"})
        self.assertEqual(paragraphs_bytes(out)[1:], ["Allergies", "None documented", "Plan", "Review"])

    def test_a_wrapped_row_is_read_in_its_place(self):
        from documents import word_v3
        doc = Document()
        doc.add_paragraph("Synthetic review of systems")
        table = yes_no_grid(doc, rows=("Chest pain", "Dyspnea", "Cough"))
        wrap_in_control(table.rows[1]._tr)
        data = docx_bytes(doc)
        fields = word_v3.inspect(data)["fields"]
        by = fields_by_label(fields)
        self.assertEqual({label: by[label]["options"] for label in ("Chest pain", "Dyspnea", "Cough")},
                         {"Chest pain": ["Yes", "No"], "Dyspnea": ["Yes", "No"], "Cough": ["Yes", "No"]})
        rows = paragraphs_bytes(word_v3.fill(data, fields, {by["Chest pain"]["key"]: "No", by["Cough"]["key"]: "Yes"}))
        self.assertEqual(rows[rows.index("Chest pain"):], ["Chest pain", "☐", "☒", "Dyspnea", "☐", "☐", "Cough", "☒", "☐"])

    def medication_log(self, wrapped):
        doc = Document()
        doc.add_paragraph("Synthetic medications")
        table = doc.add_table(rows=3, cols=3)
        for c, h in enumerate(["Medication", "Dose", "Route"]):
            table.cell(0, c).text = h
        for r in (1, 2):
            tr = table.rows[r]._tr
            before = OxmlElement("w:gridBefore")
            before.set(qn("w:val"), "1")
            tr.get_or_add_trPr().append(before)
            tr.remove(tr.findall(qn("w:tc"))[0])
        if wrapped:
            wrap_in_control(table.rows[2]._tr)
        return docx_bytes(doc)

    def test_the_table_rows_writer_counts_columns_as_the_index_does(self):
        """Found repairing P1: log rows that skip a grid column (w:gridBefore) - the writer put the dose under Route and
        dropped the route."""
        from documents import word_v3
        for wrapped in (False, True):
            data = self.medication_log(wrapped)
            field = next(f for f in word_v3.inspect(data)["fields"] if f["kind"] == "table_rows")
            self.assertEqual((field["options"], field["locator"]["target"]["rows"]), (["Dose", "Route"], [1, 2]), wrapped)
            out = word_v3.fill(data, [field], {field["key"]: [["10 mg", "oral"], ["5 mg", "iv"], ["1 g", "topical"]]})
            self.assertEqual(paragraphs_bytes(out)[4:], ["10 mg", "oral", "5 mg", "iv", "1 g", "topical"], wrapped)


if __name__ == "__main__":
    unittest.main()
